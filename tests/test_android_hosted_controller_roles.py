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
from scripts import android_workflow_job_binder as binder
from scripts import android_artifact_origin as origin
import test_android_controller_rendezvous as flows
import test_android_workflow_identity as identity_fixtures
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


def test_admitted_capture_binding_is_consumed_before_hosted_oidc(prepared, monkeypatch):
    capture = dict(prepared.documents["capture"]["job_policy"])
    emission = dict(prepared.documents["emission"]["job_policy"])
    protected = dict(capture); protected["environment"] = "android-preview12-release-builder"
    prepared.documents["capture"]["role_binding"] = {
        "job_names": {role: "preview12-" + role for role in binder.ROLES},
        "templates": {"capture": capture, "emission": emission, "protected": protected},
    }
    save(prepared, "capture")
    calls = []
    def bind(*, binding, current_policies, role, deadline):
        calls.append((binding, current_policies, role, deadline))
        return {"capture": binder.identity.WorkflowJobPolicy(**capture),
                "emission": binder.identity.WorkflowJobPolicy(**emission),
                "protected": binder.identity.WorkflowJobPolicy(**protected)}
    monkeypatch.setattr(binder, "bind_deployment_roles", bind)
    monkeypatch.setattr(roles, "_hold_for_protected_success", lambda *_: None)
    prepared.r.arm_capture(); prepared.serve(prepared.r._issued_capture, 707)
    assert invoke(prepared, "capture") == roles.COMPLETE["capture"]
    assert len(calls) == 1 and len(prepared.oidc_calls) == 1


def _optional_binding(prepared):
    capture = dict(prepared.documents["capture"]["job_policy"])
    emission = dict(prepared.documents["emission"]["job_policy"])
    protected = dict(capture); protected["environment"] = "android-preview12-release-builder"
    return {"job_names": {role: "preview12-" + role for role in binder.ROLES},
            "templates": {"capture": capture, "emission": emission, "protected": protected}}


def test_optional_lookup_failure_precedes_hosted_input_and_client(prepared, monkeypatch):
    prepared.documents["capture"]["role_binding"] = _optional_binding(prepared)
    save(prepared, "capture")
    monkeypatch.setattr(binder, "bind_deployment_roles",
                        lambda **_: (_ for _ in ()).throw(binder.JobBindingError(binder.ERROR)))
    with pytest.raises(roles.RoleError): invoke(prepared, "capture")
    assert prepared.oidc_calls == [] and prepared.seen == []


def _startup(prepared):
    binding = _optional_binding(prepared)
    binding["templates"]["protected"]["check_run_id"] = "911"
    for role in ("capture", "emission"):
        prepared.documents[role].update(role_binding=binding, startup_barrier={"publisher_id": 123})
        save(prepared, role)
    return {name: binder.identity.WorkflowJobPolicy(**item) for name, item in binding["templates"].items()}


def test_startup_precedes_binder_and_private_role_work(prepared, monkeypatch):
    from scripts import android_startup_scheduling as startup
    bound = _startup(prepared)
    order = []
    def wait(value, stage, *, deadline, recheck):
        recheck()
        assert stage == "listener" and not prepared.oidc_calls and not prepared.seen
        assert not Path(value["attempt_directory"]).exists()
        order.append("startup")
        return startup.binding_digest(bound)
    def bind(**kwargs):
        assert order == ["startup"]
        order.append("binder")
        return bound
    monkeypatch.setattr(startup, "wait_for_stage", wait)
    monkeypatch.setattr(binder, "bind_deployment_roles", bind)
    monkeypatch.setattr(roles, "_hold_for_protected_success", lambda *_: None)
    captured(prepared)
    assert order == ["startup", "binder"] and len(prepared.oidc_calls) == 1


@pytest.mark.parametrize("failure", ["pending-exhausted", "different-jobs", "deployment-drift", "deadline"])
def test_startup_failure_stops_before_credentials_and_no_retry(prepared, monkeypatch, failure):
    from scripts import android_startup_scheduling as startup
    bound = _startup(prepared)
    lookups = []
    def wait(value, stage, *, deadline, recheck):
        recheck()
        if failure == "pending-exhausted":
            raise RuntimeError("synthetic public scheduling failure")
        if failure == "deployment-drift":
            prepared.configs["capture"].write_bytes(b"PUBLIC drift")
        if failure == "deadline":
            monkeypatch.setattr(roles.time, "monotonic", lambda: deadline + 1)
        return "0" * 64 if failure == "different-jobs" else startup.binding_digest(bound)
    monkeypatch.setattr(startup, "wait_for_stage", wait)
    monkeypatch.setattr(binder, "bind_deployment_roles", lambda **_: lookups.append(True) or bound)
    with pytest.raises(roles.RoleError): invoke(prepared, "capture")
    assert len(lookups) == (1 if failure == "different-jobs" else 0)
    assert not prepared.oidc_calls and not prepared.seen
    assert not Path(prepared.documents["capture"]["attempt_directory"]).exists()


def test_submit_does_not_rewait_listener_or_reconsume_oidc(prepared, monkeypatch):
    from scripts import android_startup_scheduling as startup
    bound = _startup(prepared)
    stages = []
    monkeypatch.setattr(startup, "wait_for_stage", lambda value, stage, **_:
                        stages.append(stage) or startup.binding_digest(bound))
    monkeypatch.setattr(binder, "bind_deployment_roles", lambda **_: bound)
    monkeypatch.setattr(roles, "_hold_for_protected_success", lambda *_: None)
    manifest_ready(prepared)
    assert stages == ["listener", "listener"]
    monkeypatch.setattr(startup, "wait_for_stage", lambda *_args, **_kwargs: pytest.fail("submit waited again"))
    monkeypatch.setattr(roles.oidc, "_request_token", lambda *_: pytest.fail("submit read OIDC"))
    assert invoke(prepared, "emission-submit", actual_test_bundle(prepared)) == roles.COMPLETE["emission-submit"]


def test_optional_lookup_rechecks_held_deployment_before_hosted_inputs(prepared, monkeypatch):
    prepared.documents["capture"]["role_binding"] = _optional_binding(prepared)
    save(prepared, "capture")
    completed = []
    def live(*, role_policies, job_names, deadline):
        return {role: replace(role_policies[role], check_run_id=str(1500 + index))
                for index, role in enumerate(binder.ROLES)}
    monkeypatch.setattr(binder, "bind_live_roles", live)
    original = binder.bind_deployment_roles
    def drift(**kwargs):
        result = original(**kwargs)
        prepared.configs["capture"].write_bytes(b"PUBLIC-TEST-deployment-drift")
        completed.append("lookup-succeeded-and-deployment-changed")
        return result
    monkeypatch.setattr(binder, "bind_deployment_roles", drift)
    with pytest.raises(roles.RoleError): invoke(prepared, "capture")
    assert completed == ["lookup-succeeded-and-deployment-changed"]
    assert prepared.oidc_calls == [] and prepared.seen == []


def test_optional_three_phase_sequence_preserves_markers_and_submit_no_reconsume(prepared, monkeypatch):
    binding = _optional_binding(prepared)
    prepared.documents["capture"]["role_binding"] = binding
    prepared.documents["emission"]["role_binding"] = binding
    save(prepared, "capture"); save(prepared, "emission")
    calls = []
    def bind(*, binding, current_policies, role, deadline):
        calls.append(role)
        return {"capture": binder.identity.WorkflowJobPolicy(**binding["templates"]["capture"]),
                "emission": binder.identity.WorkflowJobPolicy(**binding["templates"]["emission"]),
                "protected": binder.identity.WorkflowJobPolicy(**binding["templates"]["protected"])}
    monkeypatch.setattr(binder, "bind_deployment_roles", bind)
    holds = []
    monkeypatch.setattr(roles, "_hold_for_protected_success",
                        lambda policy, deadline, check: holds.append(policy.check_run_id))
    directory = manifest_ready(prepared)
    bundle = actual_test_bundle(prepared)
    before = list(prepared.oidc_calls)
    monkeypatch.setattr(roles.oidc, "_request_token", lambda *_: pytest.fail("submit re-read OIDC"))
    monkeypatch.setattr(roles.rendezvous.HostedClient, "challenge", lambda *_: pytest.fail("submit re-challenged"))
    assert invoke(prepared, "emission-submit", bundle) == roles.COMPLETE["emission-submit"]
    assert calls == ["capture", "emission", "emission"]
    assert holds == [binding["templates"]["protected"]["check_run_id"]] * 2
    assert prepared.oidc_calls == before and (directory / "bundle-started").exists()


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


def _protected_policy(prepared):
    return replace(prepared.first, check_run_id="911", environment="android-preview12-release-builder")


def _protected_attempt(*, status="in_progress", conclusion=None, sha=None):
    value = identity_fixtures.api_attempt()
    value.update(status=status, conclusion=conclusion)
    value["head_sha"] = "b" * 40 if sha is None else sha
    return value


def _protected_jobs(*, status="in_progress", conclusion=None, check="911"):
    value = identity_fixtures.api_jobs()
    value["jobs"][0].update(status=status, conclusion=conclusion,
        head_sha="b" * 40,
        check_run_url=identity_fixtures.identity.API + "/repos/example/repo/check-runs/" + check)
    return value


def _observe_protected(prepared, monkeypatch, responses, *, deadline=None, check=None):
    calls = []
    clock = [100.0]
    def fetch(url, fetch_deadline):
        calls.append((url, fetch_deadline))
        value = responses.pop(0)
        return value if type(value) is bytes else json.dumps(value, separators=(",", ":")).encode()
    monkeypatch.setattr(roles.identity, "_fetch", fetch)
    monkeypatch.setattr(roles.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(roles.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    roles._hold_for_protected_success(_protected_policy(prepared),
        5000.0 if deadline is None else deadline,
        (check or (lambda: None)))
    return calls


def test_protected_observer_accepts_exact_terminal_success(prepared, monkeypatch):
    calls = _observe_protected(prepared, monkeypatch,
        [_protected_attempt(),
         _protected_jobs(status="completed", conclusion="success")])
    assert calls[0][0].endswith("/attempts/2")
    assert calls[1][0].endswith("/attempts/2/jobs?per_page=100&page=1")
    assert calls[0][1] == calls[1][1]
    assert all(deadline > time.monotonic() for _, deadline in calls)


def test_protected_observer_polls_pending_then_success_without_rebinding(prepared, monkeypatch):
    calls = _observe_protected(prepared, monkeypatch,
        [_protected_attempt(), _protected_jobs(),
         _protected_attempt(),
         _protected_jobs(status="completed", conclusion="success")])
    assert len(calls) == 4 and calls[0][0].endswith("/attempts/2")


@pytest.mark.parametrize("responses", [
    [_protected_attempt(status="queued"), _protected_jobs()],
    [_protected_attempt(status="completed", conclusion="failure"), _protected_jobs()],
    [_protected_attempt(status="completed", conclusion="success"),
     _protected_jobs(status="completed", conclusion="success")],
    [_protected_attempt(), {"total_count": 1, "jobs": [{"bad": True}]}],
    [_protected_attempt(sha="c" * 40), _protected_jobs()],
])
def test_protected_observer_rejects_failure_mismatch_or_malformed_without_retry(prepared, monkeypatch, responses):
    calls = []
    def fetch(url, deadline):
        calls.append(url)
        value = responses.pop(0)
        return json.dumps(value, separators=(",", ":")).encode()
    monkeypatch.setattr(roles.identity, "_fetch", fetch)
    with pytest.raises(roles.RoleError):
        roles._hold_for_protected_success(_protected_policy(prepared), time.monotonic() + 5, lambda: None)
    assert len(calls) <= 2


@pytest.mark.parametrize("failure", [identity_fixtures.identity.WorkflowIdentityError("workflow-fetch"), OSError("PUBLIC-TEST")])
def test_protected_observer_transport_failure_is_terminal_without_retry_or_sleep(prepared, monkeypatch, failure):
    calls, sleeps = [], []
    def fetch(url, deadline):
        calls.append(url)
        raise failure
    monkeypatch.setattr(roles.identity, "_fetch", fetch)
    monkeypatch.setattr(roles.time, "sleep", sleeps.append)
    with pytest.raises(roles.RoleError):
        roles._hold_for_protected_success(_protected_policy(prepared), time.monotonic() + 60, lambda: None)
    assert len(calls) == 1 and sleeps == []


def test_protected_observer_short_phase_expires_without_a_second_snapshot(prepared, monkeypatch):
    calls, clock = [], [100.0]
    def fetch(url, deadline):
        calls.append(url)
        value = _protected_attempt() if url.endswith("/attempts/2") else _protected_jobs()
        return json.dumps(value, separators=(",", ":")).encode()
    monkeypatch.setattr(roles.identity, "_fetch", fetch)
    monkeypatch.setattr(roles.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(roles.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    with pytest.raises(roles.RoleError):
        roles._hold_for_protected_success(_protected_policy(prepared), 120.0, lambda: None)
    assert len(calls) == 2


def test_protected_observer_rechecks_held_inputs_between_public_reads(prepared, monkeypatch):
    checks = []
    def check():
        checks.append(True)
        if len(checks) == 2: raise roles.RoleError(roles.ERROR)
    calls = []
    def fetch(url, deadline):
        calls.append(url)
        return json.dumps(_protected_attempt()).encode()
    monkeypatch.setattr(roles.identity, "_fetch", fetch)
    with pytest.raises(roles.RoleError):
        roles._hold_for_protected_success(_protected_policy(prepared), time.monotonic() + 5, check)
    assert len(calls) == 1 and len(checks) == 2


def test_protected_observer_expiry_stops_before_public_fetch(prepared, monkeypatch):
    calls = []
    monkeypatch.setattr(roles.identity, "_fetch", lambda *args: calls.append(args))
    with pytest.raises(roles.RoleError):
        roles._hold_for_protected_success(_protected_policy(prepared), time.monotonic() - 1, lambda: None)
    assert calls == []


def test_protected_observer_final_custody_check_cannot_cross_lookup_deadline(prepared, monkeypatch):
    responses = [_protected_attempt(), _protected_jobs(status="completed", conclusion="success")]
    monkeypatch.setattr(roles.identity, "_fetch", lambda url, deadline:
        json.dumps(responses.pop(0), separators=(",", ":")).encode())
    clock, checks = [100.0], []
    monkeypatch.setattr(roles.time, "monotonic", lambda: clock[0])
    def check():
        checks.append(True)
        if len(checks) == 4: clock[0] = 106.0
    with pytest.raises(roles.RoleError):
        roles._hold_for_protected_success(_protected_policy(prepared), 105.0, check)
    assert len(checks) == 4


def test_protected_observer_has_a_small_paced_snapshot_budget(prepared, monkeypatch):
    calls, read_times, sleeps, clock = [], [], [], [100.0]
    def fetch(url, deadline):
        calls.append(url)
        read_times.append(clock[0])
        value = _protected_attempt() if url.endswith("/attempts/2") else _protected_jobs()
        return json.dumps(value, separators=(",", ":")).encode()
    monkeypatch.setattr(roles.identity, "_fetch", fetch)
    monkeypatch.setattr(roles.time, "monotonic", lambda: clock[0])
    def sleep(seconds):
        sleeps.append(seconds); clock[0] += seconds
    monkeypatch.setattr(roles.time, "sleep", sleep)
    with pytest.raises(roles.RoleError):
        roles._hold_for_protected_success(_protected_policy(prepared), 4100.0, lambda: None)
    assert len(calls) == 2 * roles.PROTECTED_OBSERVATION_MAX_SNAPSHOTS
    assert all(0 < value <= 1.0 for value in sleeps)
    assert sum(sleeps) == sum(roles.PROTECTED_OBSERVATION_DELAYS)
    assert read_times[::2] == [100.0, 130.0, 190.0, 310.0, 550.0, 1030.0, 1990.0, 2950.0]


def test_protected_observer_checks_custody_during_pacing_without_another_fetch(prepared, monkeypatch):
    calls, clock, checks = [], [100.0], []
    def fetch(url, deadline):
        calls.append(url)
        value = _protected_attempt() if url.endswith("/attempts/2") else _protected_jobs()
        return json.dumps(value, separators=(",", ":")).encode()
    def check():
        checks.append(True)
        if len(checks) == 4: raise roles.RoleError(roles.ERROR)
    monkeypatch.setattr(roles.identity, "_fetch", fetch)
    monkeypatch.setattr(roles.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(roles.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    with pytest.raises(roles.RoleError):
        roles._hold_for_protected_success(_protected_policy(prepared), 4100.0, check)
    assert len(calls) == 2 and len(checks) == 4


def test_optional_capture_failure_does_not_start_protected_hold(prepared, monkeypatch):
    capture = dict(prepared.documents["capture"]["job_policy"])
    emission = dict(prepared.documents["emission"]["job_policy"])
    protected = dict(capture); protected["environment"] = "android-preview12-release-builder"
    prepared.documents["capture"]["role_binding"] = {
        "job_names": {role: "preview12-" + role for role in binder.ROLES},
        "templates": {"capture": capture, "emission": emission, "protected": protected}}
    save(prepared, "capture")
    monkeypatch.setattr(binder, "bind_deployment_roles", lambda **_: {
        "capture": binder.identity.WorkflowJobPolicy(**capture),
        "emission": binder.identity.WorkflowJobPolicy(**emission),
        "protected": binder.identity.WorkflowJobPolicy(**protected)})
    monkeypatch.setattr(roles.rendezvous.HostedClient, "_post",
                        lambda *_: (_ for _ in ()).throw(ConnectionError("PUBLIC-TEST-action-failure")))
    monkeypatch.setattr(roles, "_hold_for_protected_success",
                        lambda *_: pytest.fail("protected hold started before action success"))
    prepared.r.arm_capture(); prepared.serve(prepared.r._issued_capture, 707)
    with pytest.raises(roles.RoleError): invoke(prepared, "capture")
    assert prepared.oidc_calls == []


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
