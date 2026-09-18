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


BEARER_VARIABLE = "ANDROID_PREVIEW12_ROLE_BEARER"


class BearerEnvironment(dict):
    """Delivery has exactly one explicit capability, not an environment scan."""
    def __init__(self, value=BEARER.decode()):
        super().__init__({} if value is None else {BEARER_VARIABLE: value})
        self.reads = []
    def get(self, key, *args):
        self.reads.append(key)
        assert key == BEARER_VARIABLE
        return super().get(key, *args)
    def __iter__(self):
        pytest.fail("bearer environment scan")
    def items(self):
        pytest.fail("bearer environment scan")
    def keys(self):
        pytest.fail("bearer environment scan")


@pytest.fixture
def delivery_packet(packet, monkeypatch):
    # The original staging fixture and all its tests stay unchanged. Only this
    # derived disposable fixture starts with a fresh bearer destination.
    packet.bearer.unlink()
    parent = packet.args["profile"].parent / "bearer-custody"
    parent.mkdir(mode=0o700)
    packet.bearer = parent / "role-bearer"
    packet.profile[packet.args["role"]]["transport_inputs"]["role_bearer"] = str(packet.bearer)
    packet.bearer_environment = BearerEnvironment()
    reseal(packet)
    live = set()
    actual_open, actual_close = os.open, os.close
    def opening(*args, **kwargs):
        fd = actual_open(*args, **kwargs); live.add(fd); return fd
    def closing(fd):
        actual_close(fd); live.discard(fd)
    monkeypatch.setattr(os, "open", opening)
    monkeypatch.setattr(os, "close", closing)
    yield packet
    assert live == set(), "delivery leaked held file/directory descriptors"


def deliver(p):
    return stager.deliver_role_bearer(**p.args, environment=p.bearer_environment)


def delivery_rejected(p, *, before_environment=False):
    with pytest.raises(stager.StagingError, match="^" + stager.ERROR + "$"):
        deliver(p)
    if before_environment:
        assert p.bearer_environment.reads == []
    no_outputs(p)


@pytest.mark.parametrize("packet", ["capture", "emission"], indirect=True)
def test_delivered_bearer_is_consumed_by_real_input_then_unchanged_stage(delivery_packet, monkeypatch):
    p = delivery_packet
    originals = [p.args[name] for name in ("profile", "context", "deployment")]
    originals += [Path(pin["path"]) for pin in p.profile[p.args["role"]]["pins"].values()]
    before = {path: (path.read_bytes(), stager.hosted.origin._identity(path.stat())) for path in originals}
    reads = []
    actual_read = stager.hosted._Input.read
    def read(item):
        result = actual_read(item); reads.append(item.path); return result
    monkeypatch.setattr(stager.hosted._Input, "read", read)
    actual_get = p.bearer_environment.get
    def get(key, *args):
        assert set(originals) <= set(reads)
        assert not p.bearer.exists() and list(p.outputs.iterdir()) == []
        return actual_get(key, *args)
    p.bearer_environment.get = get
    assert deliver(p) == stager.BEARER_COMPLETE
    assert p.bearer_environment.reads == [BEARER_VARIABLE]
    assert stat.S_IMODE(p.bearer.stat().st_mode) == 0o600 and p.bearer.stat().st_nlink == 1
    held = stager.hosted._Input(p.bearer, stager.hosted.INPUT_LIMITS["role_bearer"], expected=sha(BEARER))
    try:
        assert held.raw == held.read() == BEARER
    finally:
        held.close()
    no_outputs(p)
    assert invoke(p) == stager.COMPLETE
    for name, raw in (("role_bearer", BEARER), ("oidc_request_url", URL.encode()),
                      ("oidc_request_credential", TOKEN.encode())):
        path = Path(p.profile[p.args["role"]]["transport_inputs"][name])
        held = stager.hosted._Input(path, stager.hosted.INPUT_LIMITS[name], expected=sha(raw))
        try:
            assert held.raw == held.read() == raw
        finally:
            held.close()
    for path, (raw, identity) in before.items():
        assert path.read_bytes() == raw and stager.hosted.origin._identity(path.stat()) == identity


@pytest.mark.parametrize("value", [None, "", "x" * 4097, "nön-ascii", "white space", "line\nbreak",
                                   "tab\tvalue", "nul\x00value", "SYNTHETIC-WRONG-BEARER", True, b"bytes"])
def test_delivery_rejects_missing_invalid_or_wrong_digest_value_without_output(delivery_packet, value):
    p = delivery_packet; p.bearer_environment = BearerEnvironment(value)
    if type(value) is str and value != "SYNTHETIC-WRONG-BEARER":
        # Matching hashes cannot make malformed text an admitted credential.
        p.profile["owner"]["bearer_sha256"][p.args["role"]] = sha(value.encode("utf-8"))
        reseal(p)
    delivery_rejected(p)
    assert p.bearer_environment.reads == [BEARER_VARIABLE]
    assert not p.bearer.exists()


def test_delivery_accepts_the_exact_existing_4096_byte_boundary(delivery_packet):
    p = delivery_packet; raw = b"S" * 4096
    p.profile["owner"]["bearer_sha256"][p.args["role"]] = sha(raw)
    p.bearer_environment = BearerEnvironment(raw.decode())
    reseal(p)
    assert deliver(p) == stager.BEARER_COMPLETE
    assert p.bearer_environment.reads == [BEARER_VARIABLE] and p.bearer.read_bytes() == raw
    held = stager.hosted._Input(p.bearer, stager.hosted.INPUT_LIMITS["role_bearer"], expected=sha(raw))
    try:
        assert held.raw == held.read() == raw
    finally:
        held.close()
    no_outputs(p)


@pytest.mark.parametrize("role", ["owner", "protected", "emission-submit", "anything"])
def test_delivery_rejects_other_roles_before_environment(delivery_packet, role):
    p = delivery_packet; p.args["role"] = role
    delivery_rejected(p, before_environment=True)
    assert not p.bearer.exists()


def test_delivery_cannot_use_the_other_roles_hash(delivery_packet):
    p = delivery_packet
    other = "SYNTHETIC-OTHER-ROLE-BEARER"
    p.profile["owner"]["bearer_sha256"]["emission"] = sha(other.encode())
    p.bearer_environment = BearerEnvironment(other)
    reseal(p)
    delivery_rejected(p)
    assert p.bearer_environment.reads == [BEARER_VARIABLE] and not p.bearer.exists()


@pytest.mark.parametrize("name", ["profile", "context", "deployment", "ca"])
def test_delivery_public_drift_precedes_bearer_environment(delivery_packet, name):
    p = delivery_packet
    path = p.args[name] if name != "ca" else Path(p.profile[p.args["role"]]["pins"]["controller_ca"]["path"])
    put(path, path.read_bytes() + b" ")
    delivery_rejected(p, before_environment=True)
    assert not p.bearer.exists()


@pytest.mark.parametrize("change", ["equivalent-json", "new-context", "mismatched-sha"])
def test_delivery_requires_exact_existing_renderer_equality(delivery_packet, change):
    p = delivery_packet
    if change == "equivalent-json":
        p.args["deployment_sha256"] = put(p.args["deployment"], json.dumps(json.loads(p.args["deployment"].read_bytes()), indent=2).encode())
    else:
        p.context["run_id" if change == "new-context" else "workflow_sha"] = "78" if change == "new-context" else "f" * 40
        reseal(p, render=False)
    delivery_rejected(p, before_environment=True)
    assert not p.bearer.exists()


@pytest.mark.parametrize("attack", ["bearer-profile", "bearer-ca", "bearer-oidc", "same-oidc",
    "attempt-bearer", "attempt-oidc", "bearer-in-attempt", "bearer-under-document", "oidc-ca",
    "attempt-ca", "existing-bearer", "existing-url", "existing-request", "existing-attempt",
    "bearer-symlink", "oidc-symlink", "bearer-parent-mode", "bearer-parent-symlink", "ca-hardlink"])
def test_delivery_aliases_and_existing_custody_reject_without_lookup_or_write(delivery_packet, monkeypatch, attack):
    p = delivery_packet; role = p.args["role"]; inputs = p.profile[role]["transport_inputs"]
    ca = Path(p.profile[role]["pins"]["controller_ca"]["path"])
    if attack == "bearer-profile": inputs["role_bearer"] = str(p.args["profile"])
    elif attack == "bearer-ca": inputs["role_bearer"] = str(ca)
    elif attack == "bearer-oidc": inputs["role_bearer"] = inputs["oidc_request_url"]
    elif attack == "same-oidc": inputs["oidc_request_credential"] = inputs["oidc_request_url"]
    elif attack == "attempt-bearer": p.profile[role]["attempt_directory"] = str(p.bearer)
    elif attack == "attempt-oidc": p.profile[role]["attempt_directory"] = inputs["oidc_request_url"]
    elif attack == "bearer-in-attempt": inputs["role_bearer"] = str(Path(p.profile[role]["attempt_directory"]) / "bearer")
    elif attack == "bearer-under-document": inputs["role_bearer"] = str(p.args["profile"] / "bearer")
    elif attack == "oidc-ca": inputs["oidc_request_url"] = str(ca)
    elif attack == "attempt-ca": p.profile[role]["attempt_directory"] = str(ca)
    elif attack == "existing-bearer": put(p.bearer, b"PREEXISTING-BEARER")
    elif attack in {"existing-url", "existing-request"}: put(p.outputs / attack.removeprefix("existing-"), b"PREEXISTING-OIDC")
    elif attack == "existing-attempt": Path(p.profile[role]["attempt_directory"]).mkdir(mode=0o700)
    elif attack == "bearer-symlink": p.bearer.symlink_to(ca)
    elif attack == "oidc-symlink": (p.outputs / "url").symlink_to(ca)
    elif attack == "bearer-parent-mode": p.bearer.parent.chmod(0o755)
    elif attack == "bearer-parent-symlink":
        parent = p.bearer.parent; moved = parent.with_name("retained-custody")
        parent.rename(moved); parent.symlink_to(moved, target_is_directory=True)
    else:
        os.link(ca, ca.with_name("retained-ca-alias"))
    # The real renderer already rejects these shapes. Admit their raw profile
    # hash without pre-rendering so the subject owns that fail-closed check.
    reseal(p, render=attack not in {"attempt-bearer", "attempt-oidc", "bearer-in-attempt", "attempt-ca"})
    before = {path: path.read_bytes() for path in [p.args["profile"], p.args["context"], p.args["deployment"], ca]}
    writes = []
    monkeypatch.setattr(stager.materializer, "_write_exclusive", lambda *_: writes.append(True))
    with pytest.raises(stager.StagingError, match="^" + stager.ERROR + "$"):
        deliver(p)
    assert p.bearer_environment.reads == [] and writes == []
    for path, raw in before.items(): assert path.read_bytes() == raw
    if attack == "existing-bearer": assert p.bearer.read_bytes() == b"PREEXISTING-BEARER"
    if attack in {"existing-url", "existing-request"}:
        assert (p.outputs / attack.removeprefix("existing-")).read_bytes() == b"PREEXISTING-OIDC"


@pytest.mark.parametrize("packet", ["emission"], indirect=True)
@pytest.mark.parametrize("slot", ["role_bearer", "oidc_request_url", "oidc_request_credential", "attempt"])
def test_delivery_rejects_all_custody_slots_inside_action_output(delivery_packet, slot):
    p = delivery_packet; profile = p.profile["emission"]
    path = str(Path(profile["attestation_output_root"]) / "collision")
    if slot == "attempt": profile["attempt_directory"] = path
    else: profile["transport_inputs"][slot] = path
    reseal(p, render=slot != "attempt")
    delivery_rejected(p, before_environment=True)
    assert not p.bearer.exists()


@pytest.mark.parametrize("name", ["profile", "context", "deployment", "ca"])
def test_delivery_rechecks_public_inputs_after_environment_lookup(delivery_packet, name):
    p = delivery_packet
    path = p.args[name] if name != "ca" else Path(p.profile[p.args["role"]]["pins"]["controller_ca"]["path"])
    actual_get = p.bearer_environment.get
    def get(key, *args):
        put(path, path.read_bytes() + b" ")
        return actual_get(key, *args)
    p.bearer_environment.get = get
    delivery_rejected(p)
    assert p.bearer_environment.reads == [BEARER_VARIABLE] and not p.bearer.exists()


@pytest.mark.parametrize("name", ["profile", "context", "deployment", "ca", "bearer"])
def test_delivery_postwrite_drift_preserves_the_created_file(delivery_packet, monkeypatch, name):
    p = delivery_packet
    path = p.bearer if name == "bearer" else p.args.get(name)
    if name == "ca": path = Path(p.profile[p.args["role"]]["pins"]["controller_ca"]["path"])
    actual = stager.materializer._write_exclusive
    calls = []
    def write(destination, raw):
        calls.append(destination); actual(destination, raw); put(path, b"SYNTHETIC-POSTWRITE-DRIFT")
    monkeypatch.setattr(stager.materializer, "_write_exclusive", write)
    delivery_rejected(p)
    assert calls == [p.bearer] and p.bearer.exists()
    assert p.bearer.read_bytes() == (b"SYNTHETIC-POSTWRITE-DRIFT" if name == "bearer" else BEARER)


@pytest.mark.parametrize("failure_call", [1, 2])
def test_delivery_fsync_failure_retains_partial_bearer_and_replay_never_erases_it(delivery_packet, monkeypatch, failure_call):
    p = delivery_packet; actual = os.fsync; calls = []
    def fsync(fd):
        calls.append(fd)
        if len(calls) == failure_call: raise OSError("SYNTHETIC-PRIVATE-FSYNC-DETAIL")
        return actual(fd)
    monkeypatch.setattr(stager.materializer.os, "fsync", fsync)
    delivery_rejected(p)
    assert p.bearer.read_bytes() == BEARER
    count, reads = len(calls), list(p.bearer_environment.reads)
    delivery_rejected(p)
    assert len(calls) == count and p.bearer_environment.reads == reads
    assert p.bearer.read_bytes() == BEARER


@pytest.mark.parametrize("mutation", ["parent", "same-byte-file"])
def test_delivery_name_or_parent_rebinding_during_fsync_retains_original(delivery_packet, monkeypatch, mutation):
    p = delivery_packet; actual = os.fsync; fired = False
    retained = p.bearer.parent.with_name("retained-delivery-parent") if mutation == "parent" else p.bearer.with_name("retained-bearer")
    def fsync(fd):
        nonlocal fired
        actual(fd)
        if not fired:
            fired = True
            if mutation == "parent":
                p.bearer.parent.rename(retained); p.bearer.parent.mkdir(mode=0o700)
            else:
                p.bearer.rename(retained); put(p.bearer, BEARER)
    monkeypatch.setattr(stager.materializer.os, "fsync", fsync)
    delivery_rejected(p)
    assert (retained / p.bearer.name if mutation == "parent" else retained).read_bytes() == BEARER
    if mutation == "parent": assert not p.bearer.exists()
    else: assert p.bearer.read_bytes() == BEARER


def test_successful_delivery_cannot_be_replayed_or_overwritten(delivery_packet):
    p = delivery_packet
    assert deliver(p) == stager.BEARER_COMPLETE
    before = (p.bearer.read_bytes(), stager.hosted.origin._identity(p.bearer.stat()))
    p.bearer_environment.reads.clear()
    delivery_rejected(p, before_environment=True)
    assert (p.bearer.read_bytes(), stager.hosted.origin._identity(p.bearer.stat())) == before


@pytest.mark.parametrize("success", [False, True])
def test_delivery_cli_is_explicit_and_emits_only_constant(delivery_packet, monkeypatch, capsys, success):
    p = delivery_packet
    monkeypatch.setenv(BEARER_VARIABLE, BEARER.decode() if success else "SYNTHETIC-WRONG-BEARER")
    assert stager.main(cli_args(p) + ["--deliver-role-bearer"]) == (0 if success else 1)
    captured = capsys.readouterr()
    assert captured.out == (stager.BEARER_COMPLETE + "\n" if success else "")
    assert captured.err == ("" if success else stager.ERROR + "\n")
    for private in (BEARER.decode(), sha(BEARER), str(p.bearer), "SYNTHETIC-WRONG-BEARER"):
        assert private not in captured.out + captured.err
    no_outputs(p)


def test_delivery_cli_rejects_bearer_in_arguments(delivery_packet, capsys):
    p = delivery_packet
    assert stager.main(cli_args(p) + ["--deliver-role-bearer", "--role-bearer", BEARER.decode()]) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == stager.ERROR + "\n"
    assert BEARER.decode() not in captured.out + captured.err and not p.bearer.exists()


def protected_reseal(p, *, render=True):
    p.args["profile_sha256"] = put(p.args["profile"], encode(p.profile), 0o444)
    p.args["context_sha256"] = put(p.args["context"], encode(p.context), 0o444)
    if render:
        p.args["deployment_sha256"] = put(p.args["deployment"],
            stager.materializer.render(p.profile, p.context, "protected"))


@pytest.fixture
def protected_packet(tmp_path, monkeypatch):
    """Use real root custody when root; otherwise explicitly model ownership.

    The unprivileged test owner represents root for these private fixture
    directories. External ancestry above tmp_path is trusted by this model,
    not proven suitable for real protected provisioning. A real-root canary
    uses TMPDIR=/proof (root-owned 0700) and retains production admission,
    _metadata and _trusted_root checks, with observation-only metadata tracing.
    """
    actual_root = os.getuid() == os.geteuid() == os.getgid() == os.getegid() == 0
    tmp_path.chmod(0o700)
    boot = stager.materializer.protected
    profile = deepcopy(fixtures._profile(tmp_path)); value = profile["protected"]
    directories = {name: tmp_path / ("protected-" + name) for name in
                   ("keys", "bearers", "oidc", "validation", "control", "operations")}
    for directory in directories.values(): directory.mkdir(mode=0o700)
    keys = {name: directories["keys"] / str(index) for index, name in enumerate(boot.credentials.SECRET_NAMES)}
    for path in keys.values(): put(path, b"SYNTHETIC-SIGNING-FILE-NEVER-READ")
    value["secret_inputs"] = {name: str(path) for name, path in keys.items()}
    texts = {"intake_bearer": b"SYNTHETIC-PROTECTED-INTAKE-BEARER",
             "binary_bearer": b"SYNTHETIC-PROTECTED-BINARY-BEARER"}
    for name, raw in texts.items():
        path = directories["bearers"] / name
        value["transport_inputs"][name] = str(path)
        profile["owner"]["bearer_sha256"][name.removesuffix("_bearer")] = put(path, raw)
    for name, _ in stager.ENVIRONMENT:
        value["transport_inputs"][name] = str(directories["oidc"] / name)
    for name, pin in value["pins"].items():
        pin["sha256"] = put(Path(pin["path"]), ("PUBLIC-SYNTHETIC-" + name).encode())
    profile["owner"]["pins"]["lock"]["sha256"] = value["pins"]["lock"]["sha256"]
    config = value["launcher"]
    for name in ("requests", "responses", "credentials", "socket"):
        config[name] = str(directories["control"] / name)
    value["operation_directory"] = str(directories["operations"] / "once")
    for name in boot.VALIDATION_FIELDS:
        path = directories["validation"] / name
        config["validation"][name] = str(path)
        if name in boot.VALIDATION_FILE_LIMITS: put(path, ("PUBLIC-VALIDATION-" + name).encode())
        else: path.mkdir(mode=0o700)
    Path(value["persistent"]["parent"]).mkdir(mode=0o700)
    Path(config["fleet_root"]).mkdir(mode=0o700)
    p = SimpleNamespace(root=tmp_path, boot=boot, profile=profile, context=fixtures._context(),
        keys=keys, texts=texts, outputs=directories["oidc"], environment=Injected(),
        metadata_seen=[], reads=[], live=set(), forbidden=[], args={"profile": tmp_path / "protected-profile.json",
        "context": tmp_path / "protected-context.json", "deployment": tmp_path / "protected-deployment.json"})
    protected_reseal(p)
    def trusted_root(path, _label):
        boot.require(path.is_absolute() and path.is_relative_to(tmp_path)
                     and path.resolve(strict=True) == path and path.is_dir())
        for part in (path, *path.parents):
            if not part.is_relative_to(tmp_path): break
            info = part.lstat()
            boot.require(info.st_uid == os.getuid() and info.st_gid == os.getgid()
                         and not info.st_mode & 0o022)
        return path
    def metadata(path, limit, *, private=True):
        p.metadata_seen.append(path)
        trusted_root(path.parent, "modeled protected input")
        boot.require(path.resolve(strict=True) == path)
        info = path.lstat()
        boot.require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_gid == os.getgid()
                     and info.st_nlink == 1 and 0 < info.st_size <= limit
                     and (stat.S_IMODE(info.st_mode) in {0o400, 0o600} if private else not info.st_mode & 0o022))
        return boot.origin._identity(info)
    class RootAdmission:
        getuid = geteuid = getgid = getegid = staticmethod(lambda: 0)
        def __getattr__(self, name): return getattr(os, name)
    if actual_root:
        actual_metadata = boot._metadata
        def observed_metadata(path, limit, *, private=True):
            p.metadata_seen.append(path)
            return actual_metadata(path, limit, private=private)
        monkeypatch.setattr(boot, "_metadata", observed_metadata)
    else:
        monkeypatch.setattr(stager, "os", RootAdmission())
        monkeypatch.setattr(boot, "_metadata", metadata)
        monkeypatch.setattr(boot.fleet, "_trusted_root", trusted_root)
    real_open, real_close, real_read = os.open, os.close, boot._OwnedFile.read
    def opening(path, *args, **kwargs):
        if Path(path) in keys.values():
            p.forbidden.append("key-open"); pytest.fail("signing file opened")
        fd = real_open(path, *args, **kwargs); p.live.add(fd); return fd
    def closing(fd): real_close(fd); p.live.discard(fd)
    def read(item):
        if item.path in keys.values():
            p.forbidden.append("key-read"); pytest.fail("signing bytes read")
        if item.path in {Path(value["transport_inputs"][name]) for name in texts}:
            assert set(keys.values()) <= set(p.metadata_seen)
        result = real_read(item); p.reads.append(item.path); return result
    monkeypatch.setattr(os, "open", opening); monkeypatch.setattr(os, "close", closing)
    monkeypatch.setattr(boot._OwnedFile, "read", read)
    def forbidden(*_args, **_kwargs):
        p.forbidden.append("operation"); pytest.fail("protected operational action")
    for module, names in ((boot, ("run", "_tls", "_release_fd", "_wait_release")),
        (boot.launcher, ("ProtectedJobLauncher", "RecoveryMount")),
        (boot.entrypoint, ("ProtectedJobEntrypoint",)), (boot.intake, ("PublicCaptureClient",)),
        (boot.fleet, ("PreservedProtectedValidation",))):
        for name in names: monkeypatch.setattr(module, name, forbidden)
    yield p
    assert p.forbidden == [] and p.live == set()


def invoke_protected(p):
    return stager.stage_protected_request_inputs(**p.args, environment=p.environment)


def protected_rejected(p, *, before_environment=False, before_transport=False):
    with pytest.raises(stager.StagingError, match="^" + stager.ERROR + "$"):
        invoke_protected(p)
    if before_environment: assert p.environment.reads == []
    if before_transport:
        transport = p.profile["protected"]["transport_inputs"]
        assert not set(p.reads) & {Path(transport[name]) for name in p.texts}


def test_protected_staging_uses_real_ownedfiles_without_signing_file_reads(protected_packet):
    p = protected_packet; value = p.profile["protected"]
    preserved = [p.args[name] for name in ("profile", "context", "deployment")]
    preserved += [Path(pin["path"]) for pin in value["pins"].values()]
    preserved += [Path(value["transport_inputs"][name]) for name in p.texts]
    before = {path: (path.read_bytes(), p.boot.origin._identity(path.stat())) for path in preserved}
    key_stamps = {path: p.boot.origin._identity(path.stat()) for path in p.keys.values()}
    original_get = p.environment.get
    def get(key, *args):
        assert set(p.keys.values()) <= set(p.metadata_seen)
        assert set(preserved) <= set(p.reads)
        return original_get(key, *args)
    p.environment.get = get
    assert invoke_protected(p) == stager.PROTECTED_COMPLETE
    assert p.environment.reads == [name for _, name in stager.ENVIRONMENT]
    for name, raw in (("oidc_request_url", URL.encode()), ("oidc_request_credential", TOKEN.encode())):
        path = Path(value["transport_inputs"][name])
        held = p.boot._OwnedFile(path, p.boot.TRANSPORT_LIMITS[name], expected=sha(raw))
        try: assert held.raw == held.read() == raw
        finally: held.close()
        assert stat.S_IMODE(path.stat().st_mode) == 0o600 and path.stat().st_nlink == 1
    for path, (raw, identity) in before.items():
        assert path.read_bytes() == raw and p.boot.origin._identity(path.stat()) == identity
    for path, identity in key_stamps.items(): assert p.boot.origin._identity(path.stat()) == identity
    assert not Path(value["operation_directory"]).exists()


def test_protected_request_staging_remains_root_only(protected_packet, monkeypatch):
    monkeypatch.setattr(stager.os, "geteuid", lambda: 1000)
    protected_rejected(protected_packet, before_environment=True, before_transport=True)
    no_outputs(protected_packet)


@pytest.mark.parametrize("name", ["profile", "context", "deployment", "pin", "key"])
def test_protected_bad_public_or_key_custody_precedes_transport_and_environment(protected_packet, name):
    p = protected_packet
    if name == "key": next(iter(p.keys.values())).chmod(0o644)
    else:
        path = p.args[name] if name != "pin" else Path(p.profile["protected"]["pins"]["intake_ca"]["path"])
        put(path, path.read_bytes() + b" ")
    protected_rejected(p, before_environment=True, before_transport=True); no_outputs(p)


@pytest.mark.parametrize("change", ["equivalent-json", "new-context", "mismatched-sha"])
def test_protected_requires_exact_existing_renderer_equality(protected_packet, change):
    p = protected_packet
    if change == "equivalent-json":
        p.args["deployment_sha256"] = put(p.args["deployment"],
            json.dumps(json.loads(p.args["deployment"].read_bytes()), indent=2).encode())
    else:
        p.context["run_id" if change == "new-context" else "workflow_sha"] = "78" if change == "new-context" else "f" * 40
        protected_reseal(p, render=False)
    protected_rejected(p, before_environment=True, before_transport=True); no_outputs(p)


@pytest.mark.parametrize("attack", ["key-key", "key-bearer", "key-pin", "key-validation", "bearer-validation",
    "key-runtime-bind", "bearer-runtime-bind", "output-key", "output-bearer", "same-output", "existing-url",
    "existing-request", "existing-operation", "output-symlink", "key-symlink", "bearer-hardlink", "output-recovery"])
def test_protected_aliases_reject_before_any_transport_bytes(protected_packet, attack):
    p = protected_packet; value = p.profile["protected"]; config = value["launcher"]
    transport = value["transport_inputs"]; keys = value["secret_inputs"]; key_names = list(keys)
    if attack == "key-key": keys[key_names[1]] = keys[key_names[0]]
    elif attack == "key-bearer": transport["intake_bearer"] = keys[key_names[0]]
    elif attack == "key-pin": keys[key_names[0]] = value["pins"]["trusted_root"]["path"]
    elif attack == "key-validation": config["validation"]["bundletool"] = keys[key_names[0]]
    elif attack == "bearer-validation": config["validation"]["bundletool"] = transport["intake_bearer"]
    elif attack in {"key-runtime-bind", "bearer-runtime-bind"}:
        path = keys[key_names[0]] if attack.startswith("key") else transport["intake_bearer"]
        value["runtime_policy"]["binds"] = [*value["runtime_policy"]["binds"],
            {"source": str(Path(path).parent), "target": "/synthetic-extra", "read_only": True}]
    elif attack == "output-key": transport["oidc_request_url"] = keys[key_names[0]]
    elif attack == "output-bearer": transport["oidc_request_url"] = transport["intake_bearer"]
    elif attack == "same-output": transport["oidc_request_credential"] = transport["oidc_request_url"]
    elif attack in {"existing-url", "existing-request"}:
        name = "oidc_request_url" if attack == "existing-url" else "oidc_request_credential"
        put(Path(transport[name]), b"SYNTHETIC-PREEXISTING")
    elif attack == "existing-operation": Path(value["operation_directory"]).mkdir(mode=0o700)
    elif attack == "output-symlink": Path(transport["oidc_request_url"]).symlink_to(Path(transport["intake_bearer"]))
    elif attack == "key-symlink":
        path = next(iter(p.keys.values())); retained = path.with_name("retained-key")
        path.rename(retained); path.symlink_to(retained)
    elif attack == "bearer-hardlink":
        path = Path(transport["intake_bearer"]); os.link(path, path.with_name("retained-bearer"))
    else: transport["oidc_request_url"] = str(Path(config["recovery"]) / "nested-output")
    protected_reseal(p)
    protected_rejected(p, before_environment=True, before_transport=True)


@pytest.mark.parametrize("kind", ["wrong-intake", "wrong-binary", "shared-bearers", "shared-token"])
def test_protected_transport_hash_and_distinctness_bindings(protected_packet, kind):
    p = protected_packet; transport = p.profile["protected"]["transport_inputs"]
    if kind in {"wrong-intake", "wrong-binary"}:
        name = "intake_bearer" if kind == "wrong-intake" else "binary_bearer"
        put(Path(transport[name]), b"SYNTHETIC-WRONG-ROLE")
    elif kind == "shared-bearers":
        put(Path(transport["binary_bearer"]), p.texts["intake_bearer"])
        p.profile["owner"]["bearer_sha256"]["binary"] = sha(p.texts["intake_bearer"])
        protected_reseal(p, render=False)
    else: p.environment["ACTIONS_ID_TOKEN_REQUEST_TOKEN"] = p.texts["intake_bearer"].decode()
    protected_rejected(p, before_environment=kind != "shared-token"); no_outputs(p)


@pytest.mark.parametrize("value", [None, "", "x" * 16385, "nön-ascii", "white space", "line\nbreak"],
    ids=["missing", "empty", "oversize", "non-ascii", "space", "newline"])
def test_protected_invalid_explicit_oidc_value_never_writes(protected_packet, value):
    p = protected_packet; p.environment["ACTIONS_ID_TOKEN_REQUEST_TOKEN"] = value
    protected_rejected(p); no_outputs(p)


@pytest.mark.parametrize("value", ["http://token.actions.githubusercontent.com/issue", "https://evil.invalid/issue",
    "https://user@token.actions.githubusercontent.com/issue", "https://token.actions.githubusercontent.com/issue#fragment"])
def test_protected_invalid_oidc_endpoint_never_writes(protected_packet, value):
    p = protected_packet; p.environment["ACTIONS_ID_TOKEN_REQUEST_URL"] = value
    protected_rejected(p); no_outputs(p)


@pytest.mark.parametrize("when", ["environment", "first-write"])
@pytest.mark.parametrize("name", ["profile", "pin", "key", "intake_bearer"])
def test_protected_input_drift_fails_and_retains_partial_output(protected_packet, monkeypatch, when, name):
    p = protected_packet; value = p.profile["protected"]
    path = p.args["profile"] if name == "profile" else (Path(value["pins"]["lock"]["path"]) if name == "pin"
        else (next(iter(p.keys.values())) if name == "key" else Path(value["transport_inputs"][name])))
    def change():
        if name == "key": path.chmod(0o644)
        else: put(path, b"SYNTHETIC-PUBLIC-OR-TRANSPORT-DRIFT")
    if when == "environment":
        actual = p.environment.get
        def get(key, *args): change(); return actual(key, *args)
        p.environment.get = get
    else:
        actual = stager.materializer._write_exclusive
        def write(destination, raw): actual(destination, raw); change()
        monkeypatch.setattr(stager.materializer, "_write_exclusive", write)
    protected_rejected(p)
    if when == "environment":
        assert p.environment.reads == ["ACTIONS_ID_TOKEN_REQUEST_URL"]
        no_outputs(p)
    else:
        assert (p.outputs / "oidc_request_url").read_bytes() == URL.encode()
        assert not (p.outputs / "oidc_request_credential").exists()


@pytest.mark.parametrize("failure_call", [1, 2, 3, 4])
def test_protected_fsync_failure_preserves_partial_and_blocks_replay(protected_packet, monkeypatch, failure_call):
    p = protected_packet; actual = os.fsync; calls = []
    def fsync(fd):
        calls.append(fd)
        if len(calls) == failure_call: raise OSError("SYNTHETIC-PRIVATE-DETAIL")
        return actual(fd)
    monkeypatch.setattr(os, "fsync", fsync)
    protected_rejected(p)
    retained = {path: path.read_bytes() for path in p.outputs.iterdir()}
    assert retained
    count = len(calls); p.environment.reads.clear(); p.reads.clear()
    protected_rejected(p, before_environment=True, before_transport=True)
    assert len(calls) == count and {path: path.read_bytes() for path in p.outputs.iterdir()} == retained


@pytest.mark.parametrize("mutation", ["parent", "same-byte-file"])
@pytest.mark.parametrize("write_index", [0, 1])
def test_protected_name_or_parent_rebinding_during_fsync_retains_original(protected_packet, monkeypatch, mutation, write_index):
    p = protected_packet; actual = os.fsync; calls = 0
    destination = p.outputs / ("oidc_request_url" if write_index == 0 else "oidc_request_credential")
    raw = URL.encode() if write_index == 0 else TOKEN.encode()
    retained = p.outputs.with_name("retained-protected-oidc") if mutation == "parent" else destination.with_name("retained-request")
    def fsync(fd):
        nonlocal calls
        actual(fd); calls += 1
        if calls == 1 + 2 * write_index:
            if mutation == "parent":
                p.outputs.rename(retained); p.outputs.mkdir(mode=0o700)
            else:
                destination.rename(retained); put(destination, raw)
    monkeypatch.setattr(os, "fsync", fsync)
    protected_rejected(p)
    assert (retained / destination.name if mutation == "parent" else retained).read_bytes() == raw
    if mutation == "parent": assert not destination.exists()
    else: assert destination.read_bytes() == raw


@pytest.mark.parametrize("name", ["oidc_request_url", "oidc_request_credential"])
def test_protected_second_write_rechecks_both_output_files(protected_packet, monkeypatch, name):
    p = protected_packet; actual = stager.materializer._write_exclusive; calls = []
    def write(path, raw):
        calls.append(path); actual(path, raw)
        if len(calls) == 2: put(p.outputs / name, b"SYNTHETIC-POSTWRITE-DRIFT")
    monkeypatch.setattr(stager.materializer, "_write_exclusive", write)
    protected_rejected(p)
    assert len(calls) == 2
    assert (p.outputs / name).read_bytes() == b"SYNTHETIC-POSTWRITE-DRIFT"
    assert {path.name for path in p.outputs.iterdir()} == {"oidc_request_url", "oidc_request_credential"}


@pytest.mark.parametrize("extra", [[], ["--role", "capture"], ["--deliver-role-bearer"], ["--oidc-token", TOKEN]])
def test_protected_cli_optin_has_no_role_or_secret_arguments(protected_packet, monkeypatch, capsys, extra):
    p = protected_packet
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_URL", URL)
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", TOKEN)
    assert stager.main(cli_args(p) + ["--stage-protected-request-inputs", *extra]) == (1 if extra else 0)
    captured = capsys.readouterr()
    assert captured.out == ("" if extra else stager.PROTECTED_COMPLETE + "\n")
    assert captured.err == (stager.ERROR + "\n" if extra else "")
    for private in (TOKEN, URL, *(raw.decode() for raw in p.texts.values()), str(p.outputs)):
        assert private not in captured.out + captured.err
