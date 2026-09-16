"""Real client/server/SQLite/test-RS256/file transfer; modeled external boundary.

HTTPS connections, GitHub HTTP, Docker and root/RO syscalls are modeled. The
existing origin subprocess stand-in is NOT Sigstore cryptography. No listener,
mount, secret, SDK, hosted job or protected signing authority is exercised.
"""
import asyncio
from dataclasses import replace
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import ssl
from types import SimpleNamespace

import pytest

from scripts import android_protected_capture_intake as intake
from scripts import android_controller_rendezvous as rendezvous
from scripts import android_preview12_external_rebuilder as fleet
from scripts import android_artifact_origin as origin
from scripts import android_builder_handoff as capture
import test_android_controller_rendezvous as flows
import test_android_builder_handoff as builders
import test_android_preview12_protected_transaction as transaction
from test_android_controller_rendezvous import flow, store, signing_key

BEARER = "PUBLIC-TEST-protected-intake-" + "x" * 40
sha = lambda raw: hashlib.sha256(raw).hexdigest()


@pytest.fixture
def model(tmp_path, monkeypatch, request):
    value = builders.model.__wrapped__(tmp_path, monkeypatch)
    size = getattr(request, "param", None)
    if size is not None:
        raw = b"X" * size
        value.paths["unsignedAab"].write_bytes(raw)
        graph = value.paths["sourceGraph"].read_bytes()
        sidecar = (sha(raw) + "  artifacts/" + value.paths["unsignedAab"].name + "\n"
                   + sha(graph) + "  artifacts/" + value.paths["sourceGraph"].name + "\n").encode()
        value.paths["buildSidecar"].write_bytes(sidecar)
        request_raw = fleet._pretty_json(transaction.external_request(fleet, graph, raw, sidecar))
        value.paths["externalSignerRequest"].write_bytes(request_raw)
        manifest = json.loads(value.manifest.read_bytes())
        manifest["bindings"].update(unsignedAabSizeBytes=size, unsignedAabSha256=sha(raw), requestSha256=sha(request_raw))
        value.manifest.write_bytes(fleet._pretty_json(manifest))
        value.expected = {path.name: path.read_bytes() for path in value.fixture.iterdir()}
    return value


@pytest.fixture
def exported(flow):
    flows.emitting(flow)
    assert flows.request(flow, "emission", "bundle", flow.verifier.pins[1].path.read_bytes())[0] == 202
    flows.wait(flow, "complete")
    job = replace(flow.first, check_run_id="911", environment="android-preview12-release-builder")
    args = dict(job_policy=job, bearer_sha256=sha(BEARER.encode()), approval_bearer_sha256="1" * 64,
                binary_bearer_sha256="2" * 64)
    exporter = intake.PublicCaptureExport(flow.r, **args)
    value = SimpleNamespace(flow=flow, export=exporter, args=args, app=intake.PublicCaptureApp(exporter),
                            seen=[], calls=[], mutate=None, lost=None)
    yield value
    exporter.close()


def exchange(value, action, raw=b"", alter=None):
    path = (value.export.prefix + "/" + action).encode()
    scope = {"type": "http", "method": "POST", "scheme": "https", "path": path.decode(), "raw_path": path,
             "root_path": "", "query_string": b"", "client": ("127.0.0.1", 1234), "headers": [
                 (b"host", b"controller.example"), (b"authorization", b"Bearer " + BEARER.encode()),
                 (b"content-type", b"application/octet-stream"), (b"content-length", str(len(raw)).encode())]}
    if alter:
        alter(scope)
    sent, reads = [], []
    async def receive():
        reads.append(1)
        return {"type": "http.request", "body": raw}
    async def send(message):
        sent.append(message)
    asyncio.run(value.app(scope, receive, send))
    return sent[0]["status"], sent[1]["body"], len(reads)


def connect(value, monkeypatch):
    class Response:
        def __init__(self, status, raw):
            self.status, self.raw = status, io.BytesIO(raw)
            self.headers = [("Content-Type", "application/octet-stream"), ("Content-Length", str(len(raw)))]
        def getheaders(self): return self.headers
        def read1(self, count): return self.raw.read(count)
    class Connection:
        def __init__(self, host, *, timeout, context):
            assert host == "controller.example" and timeout == 10
            assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
            self.sock = SimpleNamespace(settimeout=lambda _: None)
        def request(self, method, path, *, body, headers):
            assert method == "POST" and headers["Authorization"] == "Bearer " + BEARER
            assert path.startswith(value.export.prefix + "/")
            action = path.removeprefix(value.export.prefix + "/")
            value.seen.append(action)
            status, raw, _ = exchange(value, action, body)
            self.response = Response(status, raw)
            value.calls.append((action, len(raw)))
            if value.mutate:
                value.mutate(action, self.response)
            if action == value.lost:
                raise ConnectionError("PRIVATE-TEST-response-lost")
        def getresponse(self): return self.response
        def close(self): pass
    monkeypatch.setattr(rendezvous.http.client, "HTTPSConnection", Connection)
    return intake.PublicCaptureClient(base_url="https://controller.example", job_policy=value.args["job_policy"],
        artifact_policy=value.flow.policy, bearer=BEARER, tls_context=ssl.create_default_context())


def begin(value, monkeypatch):
    client = connect(value, monkeypatch)
    value.export.arm()
    issued = value.export._issued
    assert client.challenge() == issued.audience
    value.flow.serve(issued, 709)
    client.begin(value.flow.token(issued))
    return client


def model_mounts(value, monkeypatch):
    """Only root/RO kernel boundaries are simulated; bytes/validators stay real."""
    mappings, mounted = {}, []
    original_stamp = intake._stamp
    def root(path):
        assert path.is_absolute() and path.resolve() == path and path.is_dir()
        assert path.stat().st_uid == os.getuid() and path.stat().st_mode & 0o777 == 0o700
    def mount(source, target, flags):
        mounted.append(flags)
        if flags == 4096:
            assert target.is_dir() and not list(target.iterdir())
            mappings[target] = source
            for item in source.iterdir():
                shutil.copy2(item, target / item.name)
        else:
            assert source is None and target in mappings
    def custody(path, label, *, directory=False):
        assert path.is_absolute() and path.resolve() == path and not path.is_symlink()
        assert path.is_dir() if directory else path.is_file()
    monkeypatch.setattr(intake, "_root_directory", root)
    monkeypatch.setattr(intake, "_mount", mount)
    monkeypatch.setattr(intake, "_mount_record", lambda path: (b"42", frozenset((b"ro", b"nosuid", b"nodev", b"noexec")), ())
                        if path in mappings else (None, frozenset(), ()))
    monkeypatch.setattr(intake, "_stamp", lambda path: original_stamp(mappings.get(path, path)))
    monkeypatch.setattr(intake.os, "statvfs", lambda path: SimpleNamespace(f_flag=os.ST_RDONLY))
    monkeypatch.setattr(fleet, "_preserved_path", custody)
    return mounted


def receive(value, client):
    return client.receive(value.flow.tmp_path / "job-intake", lock=value.flow.model.lock,
                          verifier=value.flow.verifier.pins[2], trusted_root=value.flow.verifier.pins[3])


@pytest.mark.parametrize("model", [None, intake.CHUNK * 2, intake.CHUNK * 2 + 17], indirect=True)
def test_actual_end_to_end_session_stream_and_closed_custody_with_modeled_tls_mounts(exported, monkeypatch):
    client = begin(exported, monkeypatch)
    mounted = model_mounts(exported, monkeypatch)
    result = receive(exported, client)
    assert type(result) is intake.CapturedPublicIntake and not isinstance(result, fleet.AuthenticatedRebuildHandoff)
    assert type(result.retained) is fleet.PreservedRebuildHandoff
    assert result.artifact_origin.policy == exported.flow.policy
    assert {path.name: path.read_bytes() for path in result.custody.target.iterdir()} == exported.flow.model.expected
    assert len(list(result.custody.target.iterdir())) == 7
    assert all(size <= intake.CHUNK for action, size in exported.calls if action.startswith("file/"))
    assert mounted == [4096, 1 << 18, 4096 | 32 | 1 | 2 | 4 | 8]
    assert all(path.stat().st_mode & 0o777 == 0o400 for path in result.custody.source.iterdir())
    assert result.retained.handoff["eligibleForProtectedSigner"] is False
    assert exported.export._authenticated.job_id == 709
    assert exported.flow.store.status(hashlib.sha256(exported.export._issued.audience.encode()).hexdigest()) == "consumed"
    result.assert_exact()
    assert exported.seen.count("submit") == 1 and exported.seen.count("bundle") == 1
    assert not hasattr(result, "provenance") and not hasattr(client, "sign")
    with pytest.raises(intake.IntakeError): receive(exported, client)


@pytest.mark.parametrize("attack", ["same-job", "source", "attempt", "environment-type", "self-hosted", "completed",
                                   "capture-token", "approval-token", "binary-token", "duration", "idle"])
def test_independent_admission_rejects_wrong_role_context_or_bounds(exported, attack):
    args = dict(exported.args)
    changes = {"same-job": {"check_run_id": exported.flow.first.check_run_id}, "source": {"sha": "a" * 40},
        "attempt": {"transaction_id": "a" * 64}, "environment-type": {"environment": None},
        "self-hosted": {"runner_environment": "self-hosted"},
        "completed": {"job_status": "completed", "job_conclusion": "success"}}
    if attack == "environment-type":
        args["job_policy"] = replace(args["job_policy"])
        object.__setattr__(args["job_policy"], "environment", None)
    elif attack in changes: args["job_policy"] = replace(args["job_policy"], **changes[attack])
    elif attack == "capture-token": args["bearer_sha256"] = sha(flows.TOKENS["capture"].encode())
    elif attack == "approval-token": args["bearer_sha256"] = "1" * 64
    elif attack == "binary-token": args["bearer_sha256"] = "2" * 64
    elif attack == "duration": args["maximum_seconds"] = True
    else: args["idle_seconds"] = 121
    with pytest.raises(intake.IntakeError): intake.PublicCaptureExport(exported.flow.r, **args)


def test_detached_facts_or_incomplete_controller_are_not_export_authority(exported):
    with pytest.raises(intake.IntakeError):
        intake.PublicCaptureExport(exported.flow.r.completed(), **exported.args)
    exported.flow.r.close()
    with pytest.raises(intake.IntakeError):
        intake.PublicCaptureExport(exported.flow.r, **exported.args)


@pytest.mark.parametrize("field,value", [("aud", "wrong"), ("check_run_id", "910"), ("run_attempt", "3"),
                                        ("environment", "wrong"), ("sha", "a" * 40)])
def test_transport_bearer_does_not_authenticate_wrong_job(exported, monkeypatch, field, value):
    client = connect(exported, monkeypatch)
    exported.export.arm()
    issued = exported.export._issued
    exported.flow.serve(issued, 709)
    with pytest.raises(intake.IntakeError): client.begin(exported.flow.token(issued, **{field: value}))
    assert exported.export._stopped and exported.export._fds == {}
    assert not (exported.flow.tmp_path / "job-intake").exists()


@pytest.mark.parametrize("attack", ["bearer", "http", "host", "query", "forwarded", "duplicate", "body", "role", "path"])
def test_raw_http_rejection_precedes_body_and_job_consumption(exported, attack):
    def alter(scope):
        headers = dict(scope["headers"])
        if attack == "bearer": headers[b"authorization"] = b"Bearer " + flows.TOKENS["capture"].encode()
        elif attack == "http": scope["scheme"] = "http"
        elif attack == "host": headers[b"host"] = b"other.example"
        elif attack == "query": scope["query_string"] = b"path=secrets"
        elif attack == "forwarded": headers[b"x-forwarded-proto"] = b"https"
        elif attack == "duplicate": scope["headers"].append((b"Host", headers[b"host"])); return
        elif attack == "body": headers[b"content-length"] = b"1"
        else:
            scope["path"] += "/.." if attack == "path" else "/sign"
            scope["raw_path"] = scope["path"].encode()
        scope["headers"] = list(headers.items())
    status, raw, reads = exchange(exported, "challenge", alter=alter)
    assert status >= 400 and reads == 0 and exported.export._issued is None
    assert b"secret" not in raw


@pytest.mark.parametrize("phase", ["submit", "check", "file", "bundle"])
def test_lost_reply_never_retries_or_resumes(exported, monkeypatch, phase):
    client = connect(exported, monkeypatch)
    exported.export.arm()
    exported.flow.serve(exported.export._issued, 709)
    if phase == "submit": exported.lost = "submit"
    try:
        client.begin(exported.flow.token(exported.export._issued))
        model_mounts(exported, monkeypatch)
        exported.lost = "file/" + sorted(exported.export._limits)[0] + "/0" if phase == "file" else phase
        receive(exported, client)
    except intake.IntakeError:
        pass
    else:
        pytest.fail("lost response must fail")
    calls = list(exported.seen)
    with pytest.raises(intake.IntakeError): client.assert_live()
    with pytest.raises(intake.IntakeError): client.begin("not-a-retry")
    assert exported.seen == calls and exported.seen.count(exported.lost) == 1


@pytest.mark.parametrize("attack", ["oversize", "truncated", "correlation", "body", "extra-header"])
def test_response_bounds_integrity_and_correlation_fail_closed(exported, monkeypatch, attack):
    client = begin(exported, monkeypatch)
    model_mounts(exported, monkeypatch)
    def mutate(action, response):
        if action == "check" and attack == "correlation": response.raw = io.BytesIO(b"x" * 8)
        elif action.startswith("file/"):
            if attack == "oversize": response.headers[1] = ("Content-Length", str(intake.CHUNK + 1))
            elif attack == "truncated": response.raw = io.BytesIO(b"")
            elif attack == "body": response.raw = io.BytesIO(b"X" * len(response.raw.getvalue()))
            elif attack == "extra-header": response.headers.append(("Content-Encoding", "gzip"))
    exported.mutate = mutate
    with pytest.raises(intake.IntakeError): receive(exported, client)
    assert client._failed


@pytest.mark.parametrize("attack", ["source-bytes", "source-inode", "controller-close", "result-swap", "idle", "maximum", "out-of-order"])
def test_live_custody_and_transfer_order_drift_poison_the_attempt(exported, monkeypatch, attack):
    client = begin(exported, monkeypatch)
    path = exported.flow.retained.artifact_subject_path
    if attack == "source-bytes": path.write_bytes(path.read_bytes() + b"\n")
    elif attack == "source-inode":
        replacement = path.with_name("replacement")
        replacement.write_bytes(path.read_bytes())
        replacement.replace(path)
    elif attack == "controller-close": exported.flow.r.close()
    elif attack == "result-swap": exported.flow.r._result = replace(exported.flow.r._result)
    elif attack == "idle": exported.export._last -= 121
    elif attack == "maximum": exported.export._started -= 7201
    else:
        name = exported.export._names[0]
        assert exchange(exported, "file/" + name + "/1")[0] == 409
    with pytest.raises(intake.IntakeError): client.assert_live()
    assert exported.export._stopped and not exported.export._fds


def test_oidc_expiry_does_not_renew_or_reconsume_long_lived_admitted_transfer(exported, monkeypatch):
    client = begin(exported, monkeypatch)
    monkeypatch.setattr(exported.export._store, "_match", lambda *_: pytest.fail("expired admission must not be replayed"))
    client.assert_live()
    with pytest.raises(intake.IntakeError): exported.export.arm()


def test_old_challenge_job_slot_cannot_be_reissued_after_loss(exported, monkeypatch):
    begin(exported, monkeypatch)
    exported.export.close()
    successor = intake.PublicCaptureExport(exported.flow.r, **exported.args)
    with pytest.raises(intake.IntakeError): successor.arm()
    assert successor._stopped


def test_real_nonroot_or_writable_intake_cannot_claim_root_ro_custody(tmp_path):
    with pytest.raises((intake.IntakeError, fleet.RebuilderError)):
        intake._root_directory(tmp_path)


@pytest.mark.parametrize("attack", ["existing", "symlink", "hardlink", "fifo", "extra", "origin", "mount-failed"])
def test_exclusive_intake_and_actual_origin_validation_reject_hostile_state(exported, monkeypatch, attack):
    client = begin(exported, monkeypatch)
    mounted = model_mounts(exported, monkeypatch)
    packet = exported.flow.tmp_path / "job-intake"
    if attack == "existing": packet.mkdir(mode=0o700)
    elif attack == "symlink": packet.symlink_to(exported.flow.preserved, target_is_directory=True)
    elif attack == "origin": client._policy = replace(client._policy, subject_sha256="a" * 64)
    elif attack == "mount-failed":
        monkeypatch.setattr(intake, "_mount", lambda *_: (_ for _ in ()).throw(OSError("PRIVATE-mount")))
    else:
        original = intake.ReadOnlyIntake
        def changed(target, names):
            path = target / "files" / sorted(names)[0]
            if attack == "hardlink": os.link(path, target / "alias")
            elif attack == "fifo": path.unlink(); os.mkfifo(path, 0o600)
            else: (target / "files" / "extra").write_bytes(b"unselected")
            return original(target, names)
        monkeypatch.setattr(intake, "ReadOnlyIntake", changed)
    with pytest.raises(intake.IntakeError) as error: receive(exported, client)
    assert "PRIVATE" not in str(error.value) and client._failed
    if attack in {"existing", "symlink", "hardlink", "fifo", "extra"}: assert not mounted


@pytest.mark.parametrize("attack", ["writable", "exec", "suid", "device", "shared", "mount-id", "source-directory", "packet"])
def test_post_intake_mount_or_local_custody_drift_poison_continuation(exported, monkeypatch, attack):
    client = begin(exported, monkeypatch)
    model_mounts(exported, monkeypatch)
    result = receive(exported, client)
    mount_id, options, propagation = intake._mount_record(result.custody.target)
    if attack == "writable": options = (options - {b"ro"}) | {b"rw"}
    elif attack == "exec": options -= {b"noexec"}
    elif attack == "suid": options -= {b"nosuid"}
    elif attack == "device": options -= {b"nodev"}
    elif attack == "shared": propagation = (b"shared:99",)
    elif attack == "mount-id": mount_id = b"99"
    elif attack == "source-directory": result.custody.source.chmod(0o755)
    else: (result.custody.packet / "unexpected").write_bytes(b"drift")
    monkeypatch.setattr(intake, "_mount_record", lambda _: (mount_id, options, propagation))
    with pytest.raises(intake.IntakeError): result.assert_exact()
    assert client._failed


@pytest.mark.parametrize("attack", ["symlink", "public", "missing"])
def test_source_directory_is_rejected_before_any_bind(tmp_path, monkeypatch, attack):
    tmp_path.chmod(0o700)
    source = tmp_path / "files"
    source.mkdir(mode=0o700)
    member = source / "public"
    member.write_bytes(b"public")
    member.chmod(0o400)
    monkeypatch.setattr(intake, "_root_directory", lambda _: None)
    monkeypatch.setattr(intake, "_mount", lambda *_: pytest.fail("unsafe source reached mount"))
    if attack == "symlink":
        source.rename(tmp_path / "other")
        source.symlink_to(tmp_path / "other", target_is_directory=True)
    elif attack == "public": source.chmod(0o755)
    else: member.unlink()
    with pytest.raises(intake.IntakeError): intake.ReadOnlyIntake(tmp_path, ("public",))


def test_mountinfo_allocation_bound_and_exact_flags(monkeypatch):
    counts = []
    class Reader(io.BytesIO):
        def read(self, count):
            counts.append(count)
            return super().read(count)
    raw = b"42 1 0:1 / /private/intake ro,nosuid,nodev,noexec - ext4 /dev/disk ro\n"
    monkeypatch.setattr(Path, "open", lambda *_: Reader(raw))
    assert intake._mount_record(Path("/private/intake")) == (
        b"42", frozenset((b"ro", b"nosuid", b"nodev", b"noexec")), ())
    raw = b"x" * (1024 * 1024 + 1)
    with pytest.raises(intake.IntakeError): intake._mount_record(Path("/private/intake"))
    assert counts == [1024 * 1024 + 1] * 2


def test_malformed_challenge_poisoned_without_second_exchange(exported, monkeypatch):
    client = connect(exported, monkeypatch)
    exported.export.arm()
    def mutate(action, response):
        assert action == "challenge"
        response.raw = io.BytesIO(b"not-an-admitted-audience")
        response.headers[1] = ("Content-Length", str(len(response.raw.getvalue())))
    exported.mutate = mutate
    with pytest.raises(intake.IntakeError): client.challenge()
    with pytest.raises(intake.IntakeError): client.challenge()
    assert exported.seen == ["challenge"] and client._failed


def test_explicit_unmount_is_exact_and_never_force_or_lazy(exported, monkeypatch):
    client = begin(exported, monkeypatch)
    model_mounts(exported, monkeypatch)
    result = receive(exported, client)
    calls = []
    def unmount(path, flags):
        calls.append((path, flags))
        return 0
    monkeypatch.setattr(intake.ctypes, "CDLL", lambda *_args, **_kwargs: SimpleNamespace(umount2=unmount))
    result.custody.close()
    result.custody.close()
    assert calls == [(os.fsencode(result.custody.target), 0)]
    assert (result.custody.packet / "no-replay").exists() and result.custody.source.is_dir()
