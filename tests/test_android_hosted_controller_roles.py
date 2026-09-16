"""Real hosted-client/controller/test-key RS256/SQLite and public file bytes.

Only HTTPS/OIDC-provider, Docker, root-preserved mounts and the upstream attester
are modeled. Existing origin stand-in is NOT cryptographic Sigstore evidence.
No production token, action, listener, network, SDK, key or deployment runs.
"""
from dataclasses import asdict, replace
import hashlib
import json
import os
from pathlib import Path
import ssl
import time

import pytest

from scripts import android_hosted_controller_roles as roles
from scripts import android_artifact_origin as origin
import test_android_controller_rendezvous as flows
from test_android_controller_rendezvous import flow, model, store, signing_key


@pytest.fixture
def prepared(flow, monkeypatch):
    flow.seen = flows.hosted_connection(flow, monkeypatch)
    flow.documents, flow.configs, flow.oidc_calls = {}, {}, []
    flow.output = flow.tmp_path / "attester-output"
    flow.output.mkdir(mode=0o700)
    def write(path, raw, mode=0o600):
        path.write_bytes(raw); path.chmod(mode); return str(path)
    for role, job in (("capture", flow.first), ("emission", flow.second)):
        root = flow.tmp_path / (role + "-inputs"); root.mkdir(mode=0o700)
        ca = write(root / "ca.pem", b"PUBLIC-TEST-CA")
        transport = {"role_bearer": write(root / "bearer", flows.TOKENS[role].encode()),
            "oidc_request_url": write(root / "url", b"https://token.actions.githubusercontent.com/issue/test?api-version=2.0"),
            "oidc_request_credential": write(root / "request", ("PUBLIC-TEST-OIDC-" + role).encode())}
        value = dict(role=role, job_policy=asdict(job), artifact_policy=asdict(flow.policy),
            base_url=flow.args["base_url"], pins={name: {"path": ca, "sha256": hashlib.sha256(b"PUBLIC-TEST-CA").hexdigest()}
            for name in roles.PIN_NAMES}, transport_inputs=transport,
            attempt_directory=str(flow.tmp_path / (role + "-attempt")),
            attestation_output_root=str(flow.output) if role == "emission" else None, deadline_seconds=10)
        path = root / "deployment.json"
        flow.documents[role] = json.loads(json.dumps(value))
        flow.configs[role] = path
        write(path, json.dumps(value).encode())
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    monkeypatch.setattr(roles, "_tls", lambda _: context)
    def token(url, credential, audience, tls):
        flow.oidc_calls.append(audience)
        issued = flow.r._issued_emission if flow.r._issued_emission else flow.r._issued_capture
        assert url.startswith("https://token.actions.githubusercontent.com/issue/") and audience == issued.audience
        assert credential == "PUBLIC-TEST-OIDC-" + ("emission" if issued.check_run_id == flow.second.check_run_id else "capture")
        return flow.token(issued)
    monkeypatch.setattr(roles.oidc, "_request_token", token)
    actual_sleep = time.sleep
    monkeypatch.setattr(roles.time, "sleep", lambda seconds: actual_sleep(min(seconds, .002)))
    flow.write = write
    return flow


def save(prepared, role):
    raw = json.dumps(prepared.documents[role]).encode()
    prepared.configs[role].write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def invoke(prepared, phase, bundle=None):
    role = "capture" if phase == "capture" else "emission"
    path = prepared.configs[role]
    return roles.run(phase, path, hashlib.sha256(path.read_bytes()).hexdigest(), bundle_path=bundle)


def captured(prepared):
    prepared.r.arm_capture()
    prepared.serve(prepared.r._issued_capture, 707)
    assert invoke(prepared, "capture") == roles.COMPLETE["capture"]


def manifest_ready(prepared):
    captured(prepared)
    prepared.retained = flows.sessions.retain(prepared)
    prepared.r.arm_emission(prepared.retained)
    prepared.serve(prepared.r._issued_emission, 708)
    assert invoke(prepared, "emission-prepare") == roles.COMPLETE["emission-prepare"]
    directory = Path(prepared.documents["emission"]["attempt_directory"])
    assert (directory / roles.capture.MANIFEST).read_bytes() == prepared.retained.artifact_subject_path.read_bytes()
    return directory


def actual_test_bundle(prepared):
    # Deliberately synthetic existing verifier stand-in, not an attester run.
    directory = prepared.output / "random-action-child"; directory.mkdir(mode=0o700)
    return Path(prepared.write(directory / "attestation.json", prepared.verifier.pins[1].path.read_bytes(), 0o644))


def test_real_three_step_sequence_retains_live_server_authority_and_no_oidc_reconsume(prepared, monkeypatch):
    directory = manifest_ready(prepared)
    bundle = actual_test_bundle(prepared)
    before = list(prepared.oidc_calls)
    def forbidden(*_args, **_kwargs): pytest.fail("emission-submit must not challenge, acquire token or submit identity")
    monkeypatch.setattr(roles.oidc, "_request_token", forbidden)
    monkeypatch.setattr(roles.rendezvous.HostedClient, "challenge", forbidden)
    monkeypatch.setattr(roles.rendezvous.HostedClient, "submit", forbidden)
    original_open = os.open
    oidc_paths = {Path(prepared.documents["emission"]["transport_inputs"][name])
                  for name in ("oidc_request_url", "oidc_request_credential")}
    def opened(path, *args, **kwargs):
        assert Path(path) not in oidc_paths, "submit cannot read OIDC inputs"
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(roles.os, "open", opened)
    assert invoke(prepared, "emission-submit", bundle) == roles.COMPLETE["emission-submit"]
    assert prepared.r.completed().artifact_origin.policy == prepared.policy
    assert prepared.oidc_calls == before and len(before) == 2
    assert prepared.seen.count(("capture", "submit")) == prepared.seen.count(("emission", "submit")) == 1
    assert prepared.seen.count(("emission", "bundle")) == 1 and (directory / "bundle-started").exists()
    # A new process cannot retry submission after a successful response either.
    with pytest.raises(roles.RoleError): invoke(prepared, "emission-submit", bundle)
    assert prepared.seen.count(("emission", "bundle")) == 1


@pytest.mark.parametrize("phase", ["capture", "emission-prepare", "emission-submit"])
def test_lost_submission_reply_leaves_marker_and_blocks_repeat(prepared, monkeypatch, phase):
    bundle = None
    if phase == "emission-submit": manifest_ready(prepared); bundle = actual_test_bundle(prepared)
    elif phase == "emission-prepare":
        captured(prepared); prepared.retained = flows.sessions.retain(prepared)
        prepared.r.arm_emission(prepared.retained); prepared.serve(prepared.r._issued_emission, 708)
    else:
        prepared.r.arm_capture(); prepared.serve(prepared.r._issued_capture, 707)
    original = roles.rendezvous.HostedClient._post
    calls = []
    def lost(self, action, *args, **kwargs):
        result = original(self, action, *args, **kwargs)
        calls.append(action)
        if action == ("bundle" if phase == "emission-submit" else "submit"):
            raise ConnectionError("PRIVATE-TEST-lost-after-commit")
        return result
    monkeypatch.setattr(roles.rendezvous.HostedClient, "_post", lost)
    with pytest.raises(roles.RoleError, match="^" + roles.ERROR + "$"): invoke(prepared, phase, bundle)
    count = len(calls)
    with pytest.raises(roles.RoleError): invoke(prepared, phase, bundle)
    assert len(calls) == count and count > 0


@pytest.mark.parametrize("claim,value", [("check_run_id", "999"), ("run_id", "999"), ("run_attempt", "9"),
                                        ("sha", "f" * 40), ("aud", "wrong-audience")])
def test_genuine_crypto_fixture_rejects_wrong_job_not_local_success(prepared, monkeypatch, claim, value):
    prepared.r.arm_capture(); issued = prepared.r._issued_capture; prepared.serve(issued, 707)
    monkeypatch.setattr(roles.oidc, "_request_token", lambda *_: prepared.token(issued, **{claim: value}))
    with pytest.raises(roles.RoleError): invoke(prepared, "capture")
    assert prepared.r._stopped and prepared.model.calls == []


@pytest.mark.parametrize("attack", ["config-drift", "manifest-drift", "missing-ready", "wrong-phase", "expired", "controller-lost",
    "bundle-outside", "bundle-link", "bundle-hardlink", "bundle-oversize", "bundle-parent-mode", "malformed-bundle", "input-alias", "manifest-alias"])
def test_submit_never_reconstructs_capability_from_local_files(prepared, monkeypatch, attack):
    directory = manifest_ready(prepared); bundle = actual_test_bundle(prepared)
    if attack == "config-drift": prepared.documents["emission"]["deadline_seconds"] = 9; save(prepared, "emission")
    elif attack == "manifest-drift": (directory / roles.capture.MANIFEST).write_bytes(b"different")
    elif attack == "missing-ready": (directory / "manifest-ready").unlink()
    elif attack == "wrong-phase": prepared.documents["emission"]["role"] = "capture"; save(prepared, "emission")
    elif attack == "expired": monkeypatch.setattr(roles.rendezvous.time, "time", lambda: prepared.r._facts.valid_until)
    elif attack == "controller-lost": prepared.r.close()
    elif attack == "bundle-outside": bundle = prepared.verifier.pins[1].path
    elif attack == "bundle-link": original = bundle.with_suffix(".original"); bundle.rename(original); bundle.symlink_to(original)
    elif attack == "bundle-hardlink": os.link(bundle, bundle.with_suffix(".alias"))
    elif attack == "bundle-oversize": bundle.write_bytes(b"X" * (roles.rendezvous.MAX_BUNDLE + 1))
    elif attack == "bundle-parent-mode": bundle.parent.chmod(0o755)
    elif attack == "malformed-bundle": bundle.write_bytes(b"not-json")
    else:
        path = bundle if attack == "input-alias" else directory / roles.capture.MANIFEST
        token_path = Path(prepared.documents["emission"]["transport_inputs"]["oidc_request_credential"])
        key_stamp, _ = roles._metadata(token_path, 16384)
        original = roles._metadata
        def alias(item, *args, **kwargs):
            stamp, parents = original(item, *args, **kwargs)
            return ((*key_stamp[:2], *stamp[2:]), parents) if item == path else (stamp, parents)
        monkeypatch.setattr(roles, "_metadata", alias)  # File bind alias without a hardlink; no mount.
    with pytest.raises(roles.RoleError): invoke(prepared, "emission-submit", bundle)
    if attack not in {"expired", "controller-lost"}:
        assert prepared.seen.count(("emission", "bundle")) == 0


@pytest.mark.parametrize("attack", ["unknown-field", "unknown-pin", "digest", "wrong-role", "self-hosted", "wrong-run",
    "wrong-attempt", "wrong-subject", "wrong-origin", "bad-deadline", "ca-token-alias", "token-token-alias", "token-in-attempt"])
def test_bad_admission_rejects_before_challenge_or_token(prepared, attack):
    value = prepared.documents["capture"]
    if attack == "unknown-field": value["authenticated"] = True
    elif attack == "unknown-pin": value["pins"]["arbitrary_factory"] = "private"
    elif attack == "wrong-role": value["role"] = "emission"
    elif attack == "self-hosted": value["job_policy"]["runner_environment"] = "self-hosted"
    elif attack == "wrong-run": value["job_policy"]["run_id"] = "999"
    elif attack == "wrong-attempt": value["job_policy"]["run_attempt"] = "9"
    elif attack == "wrong-subject": value["artifact_policy"]["subject_name"] = "wrong.json"
    elif attack == "wrong-origin": value["base_url"] += "/path"
    elif attack == "bad-deadline": value["deadline_seconds"] = True
    elif attack == "ca-token-alias": value["pins"]["oidc_ca"]["path"] = value["transport_inputs"]["role_bearer"]
    elif attack == "token-token-alias": value["transport_inputs"]["oidc_request_credential"] = value["transport_inputs"]["role_bearer"]
    elif attack == "token-in-attempt": value["transport_inputs"]["role_bearer"] = value["attempt_directory"] + "/bearer"
    digest = save(prepared, "capture")
    if attack == "digest": digest = "f" * 64
    with pytest.raises(roles.RoleError): roles.run("capture", prepared.configs["capture"], digest)
    assert prepared.seen == [] and prepared.oidc_calls == []


def test_capture_direct_job_does_not_claim_emission_reusable_identity(prepared):
    value = prepared.documents["capture"]
    value["job_policy"]["job_workflow_ref"] = value["job_policy"]["job_workflow_sha"] = None
    parsed = roles._document(json.dumps(value).encode(), "capture")
    assert parsed[1].job_workflow_ref is None and parsed[2].workflow_identity == prepared.policy.workflow_identity


def test_pending_poll_observes_without_reissuing_challenge(prepared, monkeypatch):
    original = roles.rendezvous.HostedClient.challenge
    called = []
    def challenge(client):
        result = original(client); called.append(result)
        if result is None:
            prepared.r.arm_capture(); prepared.serve(prepared.r._issued_capture, 707)
        return result
    monkeypatch.setattr(roles.rendezvous.HostedClient, "challenge", challenge)
    assert invoke(prepared, "capture") == roles.COMPLETE["capture"]
    assert len(called) == 2 and called[0] is None and len(prepared.oidc_calls) == 1


def test_deadline_crossing_blocks_identity_submit_and_retains_attempt(prepared, monkeypatch):
    prepared.r.arm_capture(); prepared.serve(prepared.r._issued_capture, 707)
    original = roles.oidc._request_token
    def expired(*args):
        token = original(*args)
        monkeypatch.setattr(roles.time, "monotonic", lambda: 10**20)
        return token
    monkeypatch.setattr(roles.oidc, "_request_token", expired)
    with pytest.raises(roles.RoleError): invoke(prepared, "capture")
    assert (Path(prepared.documents["capture"]["attempt_directory"]) / "started").exists()
    assert ("capture", "submit") not in prepared.seen


@pytest.mark.parametrize("phase", ["capture", "emission-submit"])
def test_failed_directory_fsync_poisoned_phase_precedes_every_network_write(prepared, monkeypatch, phase):
    bundle = None
    if phase == "emission-submit": manifest_ready(prepared); bundle = actual_test_bundle(prepared)
    before = list(prepared.seen)
    def failed_sync(*_): raise OSError("PRIVATE-TEST-fsync")
    monkeypatch.setattr(roles.journal, "_sync_directory", failed_sync)
    with pytest.raises(roles.RoleError): invoke(prepared, phase, bundle)
    with pytest.raises(roles.RoleError): invoke(prepared, phase, bundle)
    assert prepared.seen == before


def test_upstream_oidc_error_is_constant_and_attempt_cannot_restart(prepared, monkeypatch, capsys):
    prepared.r.arm_capture(); prepared.serve(prepared.r._issued_capture, 707)
    def failed(*_): raise OSError("PRIVATE-TEST-token-url-secret")
    monkeypatch.setattr(roles.oidc, "_request_token", failed)
    path = prepared.configs["capture"]
    args = ["capture", "--deployment", str(path), "--deployment-sha256", hashlib.sha256(path.read_bytes()).hexdigest()]
    assert roles.main(args) == 1
    observed = list(prepared.seen)
    assert roles.main(args) == 1 and prepared.seen == observed
    output = capsys.readouterr()
    assert not output.out and output.err == (roles.ERROR + "\n") * 2


@pytest.mark.parametrize("phase,args", [("emission-submit", []), ("capture", ["--bundle", "/PUBLIC-TEST"]),
                                       ("fake", []), ("--help", []), ("capture", ["--factory", "PRIVATE-TEST"] )])
def test_cli_errors_never_echo_values(prepared, capsys, phase, args):
    path = prepared.configs["capture"]
    assert roles.main([phase, "--deployment", str(path), "--deployment-sha256", hashlib.sha256(path.read_bytes()).hexdigest(), *args]) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == roles.ERROR + "\n"
