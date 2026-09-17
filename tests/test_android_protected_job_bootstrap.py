"""Fixed executable composition; synthetic files and explicitly modeled host.

No keys, Docker, mounts, hosted tokens, SDK or network. Root/public-validation
boundaries are modeled; policy parsing and held-file/pipe behavior are real.
"""
from dataclasses import asdict, replace
import hashlib
import json
import os
from pathlib import Path
import ssl
import stat
import subprocess
import sys
from types import SimpleNamespace

import pytest

from scripts import android_protected_job_bootstrap as boot
from scripts import android_workflow_job_binder as binder
from scripts import android_artifact_origin as origin
import test_android_artifact_origin as origin_tests
import test_android_workflow_identity as identity_tests
import test_android_protected_job_launcher as launcher_tests


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


@pytest.fixture
def model(tmp_path, monkeypatch):
    events, opened, owners, clients = [], [], [], []
    dirs = {name: tmp_path / name for name in ("public", "secrets", "transport", "code", "state", "control", "inputs")}
    for path in dirs.values(): path.mkdir(mode=0o700)
    def file(path, raw):
        path.write_bytes(raw); path.chmod(0o600)
        return str(path)
    pins = {}
    for name in boot.PIN_LIMITS:
        raw = ("PUBLIC-TEST-" + name).encode()
        pins[name] = {"path": file(dirs["public"] / name, raw), "sha256": hashlib.sha256(raw).hexdigest()}
    secrets = {name: file(dirs["secrets"] / str(i), b"NEVER-READ-SYNTHETIC-KEY")
               for i, name in enumerate(boot.credentials.SECRET_NAMES)}
    texts = {"intake_bearer": "PUBLIC-TEST-intake-" + "x" * 40,
             "binary_bearer": "PUBLIC-TEST-binary-" + "y" * 40,
             "oidc_request_url": "https://token.actions.githubusercontent.com/issue/test?api-version=2.0",
             "oidc_request_credential": "PUBLIC-TEST-job-request-" + "z" * 40}
    transport = {name: file(dirs["transport"] / name, text.encode()) for name, text in texts.items()}
    job = replace(identity_tests.policy.__wrapped__(), environment="android-preview12-release-builder")
    artifact = replace(origin_tests.policy(), signer_commit=job.workflow_sha)
    runtime = launcher_tests.policy()
    config = dict(mode="execute", attempt=job.transaction_id, artifact_id=42, artifact_sha256="e" * 64,
        fleet_root=str(dirs["code"]), lock=pins["lock"]["path"], handoff=str(tmp_path / "intake" / "preserved"),
        validation={name: str(dirs["inputs"] / name) for name in boot.VALIDATION_FIELDS},
        recovery=str(dirs["state"] / "recovery"), output=str(dirs["state"] / "outputs" / job.transaction_id),
        requests=str(dirs["control"] / "requests"), responses=str(dirs["control"] / "responses"),
        credentials="/private-keys", socket=str(dirs["control"] / "socket"),
        code_pins={"scripts/__init__.py": "a" * 64})
    for name in boot.VALIDATION_FILE_LIMITS:
        file(Path(config["validation"][name]), ("PUBLIC-TEST-" + name).encode())
    value = dict(launcher=config, job_policy=asdict(job), artifact_policy=asdict(artifact), runtime_policy=asdict(runtime),
        pins=pins, persistent={"parent": str(dirs["state"]), "mount_row_sha256": "a" * 64},
        operation_directory=str(dirs["state"] / "operations" / "once"), secret_inputs=secrets,
        transport_inputs=transport, base_url="https://controller.example", release_wait_seconds=60)
    # JSON collection representation, not dataclass/capability serialization.
    value = json.loads(encoded(value))
    deployment = tmp_path / "deployment.json"
    def save():
        deployment.write_bytes(encoded(value)); deployment.chmod(0o600)
        return hashlib.sha256(deployment.read_bytes()).hexdigest()
    save()
    def metadata(path, limit, *, private=True):
        # Model ONLY root ownership/ancestry (test process is unprivileged).
        assert path.is_absolute()
        boot.require(path.resolve(strict=True) == path)
        info = path.lstat()
        boot.require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and 0 < info.st_size <= limit
            and (stat.S_IMODE(info.st_mode) in {0o400, 0o600} if private else not info.st_mode & 0o022))
        return origin._identity(info)
    monkeypatch.setattr(boot, "_metadata", metadata)
    monkeypatch.setattr(boot.os, "getuid", lambda: 0)
    monkeypatch.setattr(boot.os, "geteuid", lambda: 0)
    monkeypatch.setattr(boot, "_release_fd", lambda fd: (1, 2))
    monkeypatch.setattr(boot, "_wait_release", lambda *_: events.append("owner-release"))
    real_open = os.open
    def opened_file(path, *args, **kwargs):
        opened.append(Path(path))
        assert Path(path) not in {Path(value) for value in secrets.values()}, "signing bytes opened before reserve"
        return real_open(path, *args, **kwargs)
    monkeypatch.setattr(boot.os, "open", opened_file)
    monkeypatch.setattr(boot.fleet, "load_lock", lambda _: ({"toolchain": {"signer_image": runtime.requested_image}},
                                                         Path(pins["lock"]["path"]).read_bytes()))
    monkeypatch.setattr(boot.fleet, "validate_lock", lambda *_: [])
    monkeypatch.setattr(boot.worker, "code_inputs", lambda *_: events.append("code"))
    monkeypatch.setattr(boot.launcher, "RecoveryMount", lambda *args: events.append("mount") or SimpleNamespace(args=args))
    monkeypatch.setattr(boot.fleet, "PreservedProtectedValidation", lambda *_args, **_kwargs: events.append("public-validation"))
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    monkeypatch.setattr(boot, "_tls", lambda _: context)
    original_client = boot.intake.PublicCaptureClient
    def client(**kwargs):
        events.append("client"); result = original_client(**kwargs); clients.append(result); return result
    monkeypatch.setattr(boot.intake, "PublicCaptureClient", client)
    def owner(**kwargs): events.append("launcher"); owners.append(kwargs); return SimpleNamespace(**kwargs)
    monkeypatch.setattr(boot.launcher, "ProtectedJobLauncher", owner)
    class Entry:
        def __init__(self, own, **kwargs): events.append("entrypoint"); self.own = own
        def run(self, **kwargs):
            events.append("entrypoint.run")
            assert kwargs == ({name: texts[name] for name in ("oidc_request_url", "oidc_request_credential")}
                              | {"preparation_wait_seconds": value.get("preparation_wait_seconds", 0)})
            return {"PUBLIC-TEST-modeled-audit": True}
    monkeypatch.setattr(boot.entrypoint, "ProtectedJobEntrypoint", Entry)
    return SimpleNamespace(value=value, path=deployment, save=save, events=events, opened=opened,
                           owners=owners, clients=clients, texts=texts, metadata=metadata)


def execute(model):
    return boot.run(model.path, model.save(), 8)


@pytest.mark.parametrize("startup_enabled", [False, True])
def test_admitted_protected_binding_is_consumed_before_mount_and_transport(model, monkeypatch, startup_enabled):
    binder_path = Path(model.value["launcher"]["fleet_root"]) / "scripts/android_workflow_job_binder.py"
    binder_path.parent.mkdir(mode=0o700)
    binder_path.write_bytes(Path(binder.__file__).read_bytes()); binder_path.chmod(0o600)
    model.value["launcher"]["code_pins"]["scripts/android_workflow_job_binder.py"] = hashlib.sha256(
        binder_path.read_bytes()).hexdigest()
    protected = dict(model.value["job_policy"])
    capture = dict(protected); capture["environment"] = "capture"
    emission = dict(protected); emission["environment"] = "emission"
    model.value["role_binding"] = {
        "job_names": {role: "preview12-" + role for role in binder.ROLES},
        "templates": {"capture": capture, "emission": emission, "protected": protected},
    }
    if startup_enabled:
        from scripts import android_startup_scheduling as startup
        model.value["startup_barrier"] = {"publisher_id": 123}
        monkeypatch.setattr(startup, "wait_for_stage", lambda *_args, **_kwargs:
                            pytest.fail("child must not repeat the supervisor startup wait"))
    calls = []
    def bind(*, role_policies, job_names, deadline):
        calls.append((role_policies, job_names))
        return {role: replace(policy, check_run_id=str(1300 + index))
                for index, (role, policy) in enumerate(
                    {**{role: binder.identity.WorkflowJobPolicy(**model.value["role_binding"]["templates"][role])
                       for role in binder.ROLES}}.items(), 1)}
    monkeypatch.setattr(binder, "bind_live_roles", bind)
    assert execute(model) == {"PUBLIC-TEST-modeled-audit": True}
    assert len(calls) == 1 and model.events[:2] == ["code", "code"]
    assert model.events[2:] == ["mount", "public-validation", "client", "launcher", "entrypoint",
                                "owner-release", "entrypoint.run"]
    assert model.clients[0]._job.check_run_id == "1303"


def test_pending_protected_binding_stops_before_mount_or_client(model, monkeypatch):
    protected = dict(model.value["job_policy"])
    capture = dict(protected); capture["environment"] = "capture"
    emission = dict(protected); emission["environment"] = "emission"
    model.value["role_binding"] = {"job_names": {role: "preview12-" + role for role in binder.ROLES},
        "templates": {"capture": capture, "emission": emission, "protected": protected}}
    monkeypatch.setattr(binder, "bind_live_roles", lambda **_: None)
    with pytest.raises(boot.BootstrapError): execute(model)
    assert model.events == ["code"] and model.clients == [] and model.owners == []


def test_fixed_executable_composes_existing_types_once_after_owner_release(model, capsys):
    result = execute(model)
    assert result == {"PUBLIC-TEST-modeled-audit": True}
    assert model.events == ["code", "mount", "public-validation", "client", "launcher", "entrypoint",
                            "owner-release", "entrypoint.run"]
    own = model.owners[0]
    assert type(own["policy"]) is boot.runtime.RuntimePolicy
    assert type(own["docker"]) is origin.PinnedFile
    assert own["secret_inputs"] == {name: Path(path) for name, path in model.value["secret_inputs"].items()}
    assert own["connection"]._job == boot.identity.WorkflowJobPolicy(**model.value["job_policy"])
    assert model.clients[0]._failed
    output = capsys.readouterr()
    assert output.out == boot.READY + "\n" and not output.err
    assert all(text not in output.out for text in model.texts.values())


@pytest.mark.parametrize("field", ["authenticated", "runtimeVerified", "durable", "factory", "module", "capability"])
def test_claims_and_import_factories_rejected_before_any_other_input(model, field):
    model.value[field] = True
    with pytest.raises(boot.BootstrapError, match="^" + boot.ERROR + "$"): execute(model)
    assert model.events == [] and model.opened == [model.path]


@pytest.mark.parametrize("seconds", [0, 1, 1800])
def test_public_preparation_wait_option_passes_only_after_existing_owner_pipe(model, seconds):
    model.value["preparation_wait_seconds"] = seconds
    assert execute(model) == {"PUBLIC-TEST-modeled-audit": True}
    assert model.events[-2:] == ["owner-release", "entrypoint.run"]
    assert model.clients[0]._failed


@pytest.mark.parametrize("seconds", [-1, 1801, True, False, 1.0, None, "1"])
def test_invalid_preparation_wait_rejects_before_transport_or_secrets(model, seconds):
    model.value["preparation_wait_seconds"] = seconds
    with pytest.raises(boot.BootstrapError): execute(model)
    assert model.events == [] and model.opened == [model.path]


@pytest.mark.parametrize("attack", ["missing-pin", "extra-pin", "null-mount", "self-hosted", "wrong-run", "wrong-attempt",
    "wrong-role", "secret-env", "wrong-job", "reconcile", "bool-artifact", "bad-endpoint", "extra-validation", "expired-wait"])
def test_bad_deployment_rejects_before_transport_or_challenge(model, attack):
    value = model.value
    if attack == "missing-pin": del value["pins"]["oidc_ca"]
    elif attack == "extra-pin": value["pins"]["fake"] = value["pins"]["lock"]
    elif attack == "null-mount": value["persistent"]["mount_row_sha256"] = None
    elif attack == "self-hosted": value["job_policy"]["runner_environment"] = "self-hosted"
    elif attack == "wrong-run": value["job_policy"]["run_id"] = "4567"
    elif attack == "wrong-attempt": value["job_policy"]["run_attempt"] = "1"
    elif attack == "wrong-role": value["runtime_policy"]["process_role"] = "builder"
    elif attack == "secret-env": value["runtime_policy"]["environment"].append("SECRET=PUBLIC-TEST-leak")
    elif attack == "wrong-job": value["job_policy"]["transaction_id"] = "f" * 64
    elif attack == "reconcile": value["launcher"]["mode"] = "reconcile"
    elif attack == "bool-artifact": value["launcher"]["artifact_id"] = True
    elif attack == "bad-endpoint": value["base_url"] = "https://controller.example/other"
    elif attack == "extra-validation": value["launcher"]["validation"]["verified"] = True
    else: value["release_wait_seconds"] = 1801
    with pytest.raises(boot.BootstrapError): execute(model)
    assert model.events == [] and model.opened == [model.path]


@pytest.mark.parametrize("attack", ["digest", "symlink", "hardlink", "mode", "oversize", "duplicate-json", "replacement"])
def test_stable_deployment_rejects_aliases_mutation_and_missing_external_pin(model, attack):
    expected = model.save()
    if attack == "digest": expected = "a" * 64
    elif attack == "symlink":
        moved = model.path.with_suffix(".original"); model.path.rename(moved); model.path.symlink_to(moved)
    elif attack == "hardlink": os.link(model.path, model.path.with_suffix(".alias"))
    elif attack == "mode": model.path.chmod(0o666)
    elif attack == "oversize": model.path.write_bytes(b"X" * (boot.MAX_DEPLOYMENT + 1))
    elif attack == "duplicate-json":
        model.path.write_bytes(b'{"launcher":{},"launcher":{}}'); expected = hashlib.sha256(model.path.read_bytes()).hexdigest()
    else:
        held = boot._OwnedFile(model.path, boot.MAX_DEPLOYMENT, expected=expected)
        try:
            moved = model.path.with_suffix(".original"); model.path.rename(moved)
            model.path.write_bytes(moved.read_bytes()); model.path.chmod(0o600)
            with pytest.raises(boot.BootstrapError): held.recheck()
        finally: held.close()
        return
    with pytest.raises(boot.BootstrapError): boot.run(model.path, expected, 8)
    assert model.events == []


@pytest.mark.parametrize("attack", ["key-key", "key-transport", "key-public", "key-code", "transport-source", "transport-equal",
                                     "key-extra-bind", "transport-extra-bind", "key-validation"])
def test_credentials_cannot_alias_public_inputs_or_mounted_roots(model, attack):
    value = model.value; names = boot.credentials.SECRET_NAMES
    if attack == "key-key": value["secret_inputs"][names[1]] = value["secret_inputs"][names[0]]
    elif attack == "key-transport": value["transport_inputs"]["intake_bearer"] = value["secret_inputs"][names[0]]
    elif attack == "key-public": value["secret_inputs"][names[0]] = value["pins"]["trusted_root"]["path"]
    elif attack == "key-code": value["secret_inputs"][names[0]] = value["launcher"]["fleet_root"] + "/key"
    elif attack == "transport-source": value["transport_inputs"]["intake_bearer"] = value["launcher"]["validation"]["workspace_root"] + "/token"
    elif attack.endswith("extra-bind"):
        path = value["secret_inputs"][names[0]] if attack.startswith("key") else value["transport_inputs"]["intake_bearer"]
        value["runtime_policy"]["binds"].append({"source": str(Path(path).parent), "target": "/extra", "read_only": True})
    elif attack == "key-validation": value["launcher"]["validation"]["bundletool"] = value["secret_inputs"][names[0]]
    else: Path(value["transport_inputs"]["binary_bearer"]).write_text(model.texts["intake_bearer"])
    with pytest.raises(boot.BootstrapError): execute(model)
    assert not model.clients
    if attack != "transport-equal":
        assert not set(map(Path, value["transport_inputs"].values())) & set(model.opened)


@pytest.mark.parametrize("private", ["signing", "transport"])
@pytest.mark.parametrize("name", list(boot.VALIDATION_FILE_LIMITS))
def test_distinct_path_bind_alias_to_validation_inode_rejects_before_reads(model, monkeypatch, private, name):
    # A file bind can alias an inode without increasing st_nlink. No mount here.
    validation = Path(model.value["launcher"]["validation"][name])
    secret = Path(next(iter(model.value["secret_inputs"].values())) if private == "signing"
                  else model.value["transport_inputs"]["intake_bearer"])
    stamp = model.metadata(secret, 1400000)
    def metadata(path, *args, **kwargs):
        actual = model.metadata(path, *args, **kwargs)
        return (*stamp[:2], *actual[2:]) if path == validation else actual
    monkeypatch.setattr(boot, "_metadata", metadata)
    with pytest.raises(boot.BootstrapError): execute(model)
    assert model.events == [] and model.opened == [model.path]


@pytest.mark.parametrize("stage", ["lock", "mount", "public-validation", "release", "pin-drift", "key-drift", "entry"])
def test_failures_never_run_or_replay_and_errors_are_closed(model, monkeypatch, stage, capsys):
    def fail(*_args, **_kwargs): raise RuntimeError("SECRET-PATH-JWT-MUST-NOT-LEAK")
    if stage == "lock": monkeypatch.setattr(boot.fleet, "validate_lock", lambda *_: ["dormant"])
    elif stage == "mount": monkeypatch.setattr(boot.launcher, "RecoveryMount", fail)
    elif stage == "public-validation": monkeypatch.setattr(boot.fleet, "PreservedProtectedValidation", fail)
    elif stage == "release": monkeypatch.setattr(boot, "_wait_release", fail)
    elif stage in {"pin-drift", "key-drift"}:
        path = Path(model.value["pins"]["lock"]["path"] if stage == "pin-drift" else next(iter(model.value["secret_inputs"].values())))
        monkeypatch.setattr(boot, "_wait_release", lambda *_: path.chmod(0o400))
    else: monkeypatch.setattr(boot.entrypoint.ProtectedJobEntrypoint, "run", fail)
    assert boot.main(["--deployment", str(model.path), "--deployment-sha256", model.save(), "--owner-release-fd", "8"]) == 1
    output = capsys.readouterr()
    assert output.err == boot.ERROR + "\n" and "SECRET-PATH-JWT" not in output.out
    assert "entrypoint.run" not in model.events
    assert all(client._failed for client in model.clients)
    if stage in {"lock", "mount", "public-validation"}:
        assert not set(map(Path, model.value["transport_inputs"].values())) & set(model.opened)


@pytest.mark.parametrize("args", [[], ["--help"], ["--factory", "SECRET"], ["--owner-release-fd", "SECRET"]])
def test_parser_never_echoes_arbitrary_arguments(args, capsys):
    assert boot.main(args) == 1
    assert capsys.readouterr().err == boot.ERROR + "\n"


@pytest.mark.parametrize("content", [b"1", b"", b"11", b"0", b"SECRET"])
def test_actual_anonymous_pipe_fixed_release_and_eof(monkeypatch, content):
    read, write = os.pipe()
    try:
        # Only UID0 metadata requirement is modeled; actual FIFO/mode/direction.
        info = os.fstat(read)
        original = boot.os.fstat
        def metadata(fd):
            item = original(fd)
            return SimpleNamespace(st_mode=item.st_mode, st_nlink=item.st_nlink,
                st_uid=0, st_gid=0, st_dev=item.st_dev, st_ino=item.st_ino)
        monkeypatch.setattr(boot.os, "fstat", metadata)
        stamp = boot._release_fd(read)
        os.write(write, content); os.close(write); write = -1
        if content == b"1": boot._wait_release(read, stamp, 1)
        else:
            with pytest.raises(boot.BootstrapError): boot._wait_release(read, stamp, 1)
        with pytest.raises(boot.BootstrapError): boot._wait_release(read, stamp, 1)
    finally:
        os.close(read)
        if write >= 0: os.close(write)


def test_release_rejects_nonpipe_and_write_end(tmp_path):
    path = tmp_path / "regular"; path.write_bytes(b"1")
    fd = os.open(path, os.O_RDONLY)
    read, write = os.pipe()
    try:
        with pytest.raises(boot.BootstrapError): boot._release_fd(fd)
        with pytest.raises(boot.BootstrapError): boot._release_fd(write)
    finally:
        os.close(fd); os.close(read); os.close(write)


def test_tls_uses_only_supplied_pinned_ca_and_retains_certificate_validation():
    with pytest.raises((ssl.SSLError, ValueError)): boot._tls(b"NOT A CA")


@pytest.mark.parametrize("attack", ["owner", "group", "mode", "symlink", "hardlink", "fifo", "empty", "oversize", "ancestry"])
def test_actual_metadata_checks_with_only_filesystem_objects_modeled(monkeypatch, attack):
    values = dict(st_dev=1, st_ino=2, st_mode=stat.S_IFREG | 0o600, st_uid=0, st_gid=0,
                  st_nlink=1, st_size=1, st_mtime_ns=2, st_ctime_ns=3)
    if attack == "owner": values["st_uid"] = 1000
    elif attack == "group": values["st_gid"] = 1000
    elif attack == "mode": values["st_mode"] = stat.S_IFREG | 0o644
    elif attack == "hardlink": values["st_nlink"] = 2
    elif attack == "fifo": values["st_mode"] = stat.S_IFIFO | 0o600
    elif attack == "empty": values["st_size"] = 0
    elif attack == "oversize": values["st_size"] = 9
    path = SimpleNamespace(parent=Path("/public-test"))
    path.resolve = lambda **_: object() if attack == "symlink" else path
    path.lstat = lambda: SimpleNamespace(**values)
    def ancestry(*_): boot.require(attack != "ancestry")
    monkeypatch.setattr(boot.fleet, "_trusted_root", ancestry)
    with pytest.raises(boot.BootstrapError): boot._metadata(path, 8)


def test_partial_failure_closes_only_owned_file_descriptors(model, monkeypatch):
    opened, real_open = [], boot.os.open
    def remember(*args, **kwargs):
        fd = real_open(*args, **kwargs); opened.append(fd); return fd
    monkeypatch.setattr(boot.os, "open", remember)
    monkeypatch.setattr(boot.fleet, "validate_lock", lambda *_: ["not-ready"])
    with pytest.raises(boot.BootstrapError): execute(model)
    assert opened
    for fd in opened:
        with pytest.raises(OSError): os.fstat(fd)
    assert all(Path(path).exists() for path in model.value["secret_inputs"].values())


def test_real_cli_import_ignores_ambient_pythonpath_and_cwd(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "__init__.py").write_text("raise RuntimeError('UNTRUSTED-IMPORT')\n")
    root = str(Path(boot.__file__).resolve().parents[1])
    # Test-only fixed admitted root; this does not qualify a deployed code tree.
    command = "import sys; sys.path.insert(0, " + repr(root) + "); from scripts.android_protected_job_bootstrap import main; raise SystemExit(main())"
    result = subprocess.run([sys.executable, "-I", "-B", "-c", command], cwd=tmp_path,
        env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(tmp_path), "PYTHONHOME": "/nonexistent"},
        capture_output=True, timeout=10, check=False)
    assert result.returncode == 1 and result.stdout == b""
    assert result.stderr == (boot.ERROR + "\n").encode()
