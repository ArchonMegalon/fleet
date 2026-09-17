"""Real disposable custody and consumer reads; no credentials or live services.

Profiles and environment values are explicitly synthetic. No production owner,
client, OIDC request, workflow execution or source/runtime admission is modeled
as successful; only the actual renderer and file primitives are exercised.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import stat
from types import SimpleNamespace

import pytest

from scripts import android_hosted_input_stager as stager
import test_android_deployment_materializer as fixtures

URL = "https://token.actions.githubusercontent.com/issue/synthetic?api-version=2.0"
TOKEN = "SYNTHETIC-REQUEST-CREDENTIAL-NOT-REAL"
BEARER = b"SYNTHETIC-ROLE-BEARER-NOT-REAL"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def put(path, raw, mode=0o600):
    if path.exists():
        path.chmod(0o600)  # Disposable fixtures only; production never chmods.
    path.write_bytes(raw)
    path.chmod(mode)
    return sha(raw)


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode() + b"\n"


class Injected(dict):
    """Only the two explicit lookups are available; environment scans fail."""
    def __init__(self):
        super().__init__(ACTIONS_ID_TOKEN_REQUEST_URL=URL, ACTIONS_ID_TOKEN_REQUEST_TOKEN=TOKEN)
        self.reads = []
    def get(self, key, *args):
        self.reads.append(key)
        assert key in {variable for _, variable in stager.ENVIRONMENT}
        return super().get(key, *args)
    def __iter__(self):
        pytest.fail("environment scan")
    def items(self):
        pytest.fail("environment scan")
    def keys(self):
        pytest.fail("environment scan")


@pytest.fixture(autouse=True)
def forbid_actions(monkeypatch):
    attempts = []
    def forbidden(*_args, **_kwargs):
        attempts.append(True)
        pytest.fail("unexpected operational action")
    monkeypatch.setattr(stager.hosted.oidc, "_request_token", forbidden)
    monkeypatch.setattr(stager.hosted.identity, "_fetch", forbidden)
    monkeypatch.setattr(stager.hosted.rendezvous, "HostedClient", forbidden)
    monkeypatch.setattr(stager.materializer.owner, "LocalCaptureOwner", forbidden)
    monkeypatch.setattr(stager.hosted, "run", forbidden)
    yield
    assert attempts == []  # Even a normalized BaseException cannot hide a call.


def reseal(p, *, render=True):
    p.args["profile_sha256"] = put(p.args["profile"], encode(p.profile), 0o444)
    p.args["context_sha256"] = put(p.args["context"], encode(p.context), 0o444)
    if render:
        p.args["deployment_sha256"] = put(p.args["deployment"],
            stager.materializer.render(p.profile, p.context, p.args["role"]))


@pytest.fixture
def packet(tmp_path, request):
    tmp_path.chmod(0o700)
    role = getattr(request, "param", "capture")
    profile = deepcopy(fixtures._profile(tmp_path))
    outputs = tmp_path / "oidc-inputs"
    outputs.mkdir(mode=0o700)
    inputs = profile[role]["transport_inputs"]
    inputs["oidc_request_url"] = str(outputs / "url")
    inputs["oidc_request_credential"] = str(outputs / "request")
    bearer = Path(inputs["role_bearer"])
    profile["owner"]["bearer_sha256"][role] = put(bearer, BEARER)
    for pin in profile[role]["pins"].values():
        pin["sha256"] = put(Path(pin["path"]), b"PUBLIC-SYNTHETIC-CA-BYTES")
    p = SimpleNamespace(profile=profile, context=fixtures._context(), outputs=outputs,
        bearer=bearer, environment=Injected(), args={"role": role, "profile": tmp_path / "profile.json",
        "context": tmp_path / "context.json", "deployment": tmp_path / "deployment.json"})
    reseal(p)
    return p


def invoke(p):
    return stager.stage(**p.args, environment=p.environment)


def rejected(p):
    with pytest.raises(stager.StagingError, match="^" + stager.ERROR + "$"):
        invoke(p)


def no_outputs(p):
    assert list(p.outputs.iterdir()) == []


@pytest.mark.parametrize("packet", ["capture", "emission"], indirect=True)
def test_exact_two_files_are_consumed_by_real_input_and_existing_inputs_unchanged(packet):
    p = packet
    originals = [p.args[name] for name in ("profile", "context", "deployment")] + [p.bearer]
    before = {path: (path.read_bytes(), path.stat()) for path in originals}
    assert invoke(p) == stager.COMPLETE
    assert p.environment.reads == [variable for _, variable in stager.ENVIRONMENT]
    assert {path.name for path in p.outputs.iterdir()} == {"url", "request"}
    for name, expected in (("oidc_request_url", URL.encode()), ("oidc_request_credential", TOKEN.encode())):
        path = Path(p.profile[p.args["role"]]["transport_inputs"][name])
        held = stager.hosted._Input(path, stager.hosted.INPUT_LIMITS[name], expected=sha(expected))
        try:
            assert held.read() == expected and held.raw == expected
            assert stat.S_IMODE(path.stat().st_mode) == 0o600 and path.stat().st_nlink == 1
        finally:
            held.close()
    for path, (raw, info) in before.items():
        assert path.read_bytes() == raw
        assert stager.hosted.origin._identity(path.stat()) == stager.hosted.origin._identity(info)
    assert not Path(p.profile[p.args["role"]]["attempt_directory"]).exists()


@pytest.mark.parametrize("name", ["profile", "context", "deployment"])
def test_admitted_byte_drift_rejects_before_environment_or_outputs(packet, name):
    path = packet.args[name]
    path.chmod(0o600)
    path.write_bytes(path.read_bytes() + b" ")
    rejected(packet)
    assert packet.environment.reads == []
    no_outputs(packet)


@pytest.mark.parametrize("change", ["equivalent-json", "new-context", "mismatched-sha", "wrong-bearer"])
def test_rehashed_inputs_do_not_replace_exact_render_or_owner_bearer_binding(packet, change):
    p = packet
    if change == "equivalent-json":
        raw = json.dumps(json.loads(p.args["deployment"].read_bytes()), indent=2).encode()
        p.args["deployment_sha256"] = put(p.args["deployment"], raw)
    elif change == "new-context":
        p.context["run_id"] = "78"
        reseal(p, render=False)
    elif change == "mismatched-sha":
        p.context["workflow_sha"] = "f" * 40
        reseal(p, render=False)
    else:
        p.profile["owner"]["bearer_sha256"][p.args["role"]] = "f" * 64
        reseal(p)
    rejected(p)
    assert p.environment.reads == []
    no_outputs(p)


@pytest.mark.parametrize("attack", ["same-output", "output-is-bearer", "output-is-profile",
    "ca-is-bearer", "bearer-is-profile", "ca-hardlink-bearer", "second-exists", "parent-mode",
    "parent-symlink", "profile-symlink", "bearer-symlink", "output-symlink", "attempt-exists"])
def test_aliases_replay_and_unsafe_paths_reject_before_secret_read_or_write(packet, monkeypatch, attack):
    p = packet
    role = p.args["role"]
    inputs = p.profile[role]["transport_inputs"]
    if attack == "same-output": inputs["oidc_request_credential"] = inputs["oidc_request_url"]
    elif attack == "output-is-bearer": inputs["oidc_request_url"] = str(p.bearer)
    elif attack == "output-is-profile": inputs["oidc_request_url"] = str(p.args["profile"])
    elif attack == "ca-is-bearer":
        p.profile[role]["pins"]["controller_ca"] = {"path": str(p.bearer), "sha256": sha(BEARER)}
    elif attack == "bearer-is-profile": inputs["role_bearer"] = str(p.args["profile"])
    elif attack == "ca-hardlink-bearer":
        ca = Path(p.profile[role]["pins"]["controller_ca"]["path"])
        ca.unlink(); os.link(p.bearer, ca)
    elif attack == "second-exists": put(p.outputs / "request", b"PREEXISTING")
    elif attack == "parent-mode": p.outputs.chmod(0o755)
    elif attack == "parent-symlink":
        real = p.outputs.with_name("retained-input-parent")
        p.outputs.rename(real); p.outputs.symlink_to(real, target_is_directory=True)
    elif attack in {"profile-symlink", "bearer-symlink"}:
        path = p.args["profile"] if attack == "profile-symlink" else p.bearer
        real = path.with_name(path.name + ".original")
        path.rename(real); path.symlink_to(real)
    elif attack == "output-symlink": (p.outputs / "url").symlink_to(p.bearer)
    else: Path(p.profile[role]["attempt_directory"]).mkdir(mode=0o700)
    if attack in {"same-output", "output-is-bearer", "output-is-profile", "ca-is-bearer", "bearer-is-profile"}:
        reseal(p)
    reads, writes = [], []
    actual_read = stager.hosted._Input.read
    def read(item):
        reads.append(item.path)
        return actual_read(item)
    monkeypatch.setattr(stager.hosted._Input, "read", read)
    monkeypatch.setattr(stager.materializer, "_write_exclusive", lambda *_: writes.append(True))
    rejected(p)
    assert p.environment.reads == [] and writes == []
    assert p.bearer not in reads


@pytest.mark.parametrize("field,value", [
    ("ACTIONS_ID_TOKEN_REQUEST_URL", None), ("ACTIONS_ID_TOKEN_REQUEST_TOKEN", None),
    ("ACTIONS_ID_TOKEN_REQUEST_TOKEN", ""), ("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "x" * 16385),
    ("ACTIONS_ID_TOKEN_REQUEST_URL", "x" * 8193), ("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "nön-ascii"),
    ("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "white space"), ("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "line\nbreak"),
    ("ACTIONS_ID_TOKEN_REQUEST_TOKEN", BEARER.decode()),
    ("ACTIONS_ID_TOKEN_REQUEST_URL", "http://token.actions.githubusercontent.com/issue/test"),
    ("ACTIONS_ID_TOKEN_REQUEST_URL", "https://evil.invalid/issue/test"),
    ("ACTIONS_ID_TOKEN_REQUEST_URL", URL + "&audience=caller-selected"),
])
def test_missing_invalid_or_shared_environment_values_never_write(packet, field, value):
    packet.environment[field] = value
    rejected(packet)
    no_outputs(packet)


@pytest.mark.parametrize("name", ["profile", "context", "deployment", "bearer", "ca", "first-output"])
def test_drift_after_first_write_is_detected_and_partial_output_retained(packet, monkeypatch, name):
    p = packet
    target = p.args.get(name)
    if name == "bearer": target = p.bearer
    elif name == "ca": target = Path(p.profile[p.args["role"]]["pins"]["controller_ca"]["path"])
    elif name == "first-output": target = p.outputs / "url"
    actual = stager.materializer._write_exclusive
    calls = []
    def write(path, raw):
        calls.append(path)
        actual(path, raw)
        target.chmod(0o600)
        target.write_bytes(b"SYNTHETIC-DRIFT")
    monkeypatch.setattr(stager.materializer, "_write_exclusive", write)
    rejected(p)
    assert calls == [p.outputs / "url"]
    assert (p.outputs / "url").exists() and not (p.outputs / "request").exists()


@pytest.mark.parametrize("failure_call", [1, 2, 3, 4])
def test_fsync_failure_preserves_partial_files_and_replay_cannot_erase_them(packet, monkeypatch, failure_call):
    actual = os.fsync
    calls = []
    def fsync(fd):
        calls.append(fd)
        if len(calls) == failure_call: raise OSError("SYNTHETIC-PRIVATE-FSYNC-DETAIL")
        return actual(fd)
    monkeypatch.setattr(stager.materializer.os, "fsync", fsync)
    rejected(packet)
    retained = {path: path.read_bytes() for path in packet.outputs.iterdir()}
    assert retained and (packet.outputs / "url") in retained
    count = len(calls)
    rejected(packet)
    assert len(calls) == count
    assert {path: path.read_bytes() for path in packet.outputs.iterdir()} == retained


def test_held_first_output_replacement_during_second_fsync_cannot_pass(packet, monkeypatch):
    actual = os.fsync
    count = 0
    def fsync(fd):
        nonlocal count
        count += 1
        actual(fd)
        if count == 4:
            original = packet.outputs / "url"
            original.rename(packet.outputs / "retained-url")
            put(original, URL.encode())  # Same bytes, different inode.
    monkeypatch.setattr(stager.materializer.os, "fsync", fsync)
    rejected(packet)
    assert (packet.outputs / "retained-url").read_bytes() == URL.encode()


def test_parent_rebinding_during_write_is_detected_and_original_preserved(packet, monkeypatch):
    actual = os.fsync
    moved = packet.outputs.with_name("retained-original-parent")
    fired = False
    def fsync(fd):
        nonlocal fired
        actual(fd)
        if not fired:
            fired = True
            packet.outputs.rename(moved)
            packet.outputs.mkdir(mode=0o700)
    monkeypatch.setattr(stager.materializer.os, "fsync", fsync)
    rejected(packet)
    assert (moved / "url").read_bytes() == URL.encode()
    no_outputs(packet)


def test_input_drift_during_explicit_environment_lookup_precedes_output(packet):
    original = packet.environment.get
    def get(key, *args):
        packet.bearer.write_bytes(b"CHANGED-SYNTHETIC-BEARER")
        return original(key, *args)
    packet.environment.get = get
    rejected(packet)
    no_outputs(packet)


@pytest.mark.parametrize("role", ["owner", "protected", "emission-submit", "anything"])
def test_no_additional_role_is_accepted(packet, role):
    packet.args["role"] = role
    rejected(packet)
    assert packet.environment.reads == []
    no_outputs(packet)


def cli_args(p):
    return [item for name, value in p.args.items() for item in ("--" + name.replace("_", "-"), str(value))]


@pytest.mark.parametrize("success", [False, True])
def test_cli_emits_only_constant_not_private_bytes_hashes_or_paths(packet, monkeypatch, capsys, success):
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_URL", URL)
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", TOKEN if success else TOKEN + "\n")
    assert stager.main(cli_args(packet)) == (0 if success else 1)
    captured = capsys.readouterr()
    assert captured.out == (stager.COMPLETE + "\n" if success else "")
    assert captured.err == ("" if success else stager.ERROR + "\n")
    for private in (TOKEN, URL, BEARER.decode(), sha(BEARER), str(packet.outputs)):
        assert private not in captured.out + captured.err


def test_cli_rejects_secret_argument_without_printing_it(packet, capsys):
    assert stager.main(cli_args(packet) + ["--oidc-token", TOKEN]) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == stager.ERROR + "\n"
    assert packet.environment.reads == []
    no_outputs(packet)
