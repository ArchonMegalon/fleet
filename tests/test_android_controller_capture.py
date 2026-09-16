"""Real SQLite, test-key RS256, seven-file capture and origin-policy subprocess.

GitHub HTTP replies, Docker execution, root-owned RO custody and the origin
verifier's cryptography are modeled. No real hosted artifact emission, runtime,
mount, protected controller or signing authority is claimed by these tests.
"""
from dataclasses import replace
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import shutil
import time
from types import SimpleNamespace
import traceback

import pytest

from scripts import android_controller_capture as controller
from scripts import android_artifact_origin as origin
from scripts import android_builder_handoff as capture
from scripts import android_preview12_external_rebuilder as fleet
from scripts import android_workflow_identity as identity
from scripts import android_workflow_challenge_store as journal
import test_android_artifact_origin as origins
import test_android_workflow_challenge_store as journals
from test_android_builder_handoff import model
from test_android_workflow_challenge_store import signing_key, store


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


@pytest.fixture
def flow(model, store, signing_key, monkeypatch, tmp_path, request):
    template = journals.template()
    if getattr(request, "param", False):
        template = replace(template, job_workflow_ref=template.workflow_ref,
            job_workflow_sha=template.workflow_sha)
    first = store.issue(template)
    second = replace(template, check_run_id="910")
    policy = replace(origins.policy(), source_commit=first.sha,
        subject_name=capture.MANIFEST, subject_sha256=sha(model.expected[capture.MANIFEST]))
    preserved = tmp_path / "preserved"
    session = controller.ControllerCaptureSession(store, first, second, policy, preserved)
    value = SimpleNamespace(model=model, store=store, first=first, second=second,
        policy=policy, preserved=preserved, session=session, emitted=[], key=signing_key,
        monkeypatch=monkeypatch, tmp_path=tmp_path)

    def serve(selected, job_id):
        replies = journals.reply_bytes(signing_key, selected)
        for url, raw in list(replies.items()):
            if "/jobs?" in url:
                document = json.loads(raw)
                document["jobs"][0].update(id=job_id, url=identity.API + "/repos/" + selected.repository + "/actions/jobs/" + str(job_id))
                replies[url] = json.dumps(document).encode()
        monkeypatch.setattr(identity, "_fetch", lambda url, deadline: replies[url])
    value.serve = serve
    value.token = lambda selected, **changes: journals.token_for(selected, signing_key,
        **({"jti": "test-only-" + selected.check_run_id} | changes))
    serve(first, 707)
    return value


def run_capture(flow, **changes):
    arguments = dict(policy=flow.model.policy, docker=flow.model.docker, lock=flow.model.lock,
        operation_directory=flow.model.operation, output_bind_target="/output", handoff_child_name=flow.model.child)
    return flow.session.capture(flow.token(flow.first), **(arguments | changes))


def retain(flow, directory=None):
    directory = directory or flow.preserved
    shutil.copytree(flow.model.operation / capture.COPY_DIRECTORY, directory)
    lock = directory.with_name(directory.name + "-lock.json")
    shutil.copyfile(flow.model.lock.path, lock)
    # Only custody metadata is modeled; real closed inventory, byte/inode
    # fences, lock/request/source semantics and hashes remain exercised.
    def modeled_custody(path, label, *, directory=False):
        assert isinstance(path, Path) and path.is_absolute() and not path.is_symlink()
        assert path.resolve(strict=True) == path
        assert path.is_dir() if directory else path.is_file()
        assert path == lock or path == flow.preserved or flow.preserved in path.parents
    flow.monkeypatch.setattr(fleet, "_preserved_path", modeled_custody)
    return fleet.PreservedRebuildHandoff(lock, directory)


def ready(flow, *, mutation="", response_change=None, capture_first=True):
    if capture_first:
        run_capture(flow)
    flow.retained = retain(flow)
    flow.issued = flow.store.issue(flow.second)
    flow.serve(flow.issued, 708)
    response = origins.response()
    verified = response[0]["verificationResult"]
    verified["statement"]["subject"] = [{"name": capture.MANIFEST, "digest": {"sha256": flow.policy.subject_sha256}}]
    verified["signature"]["certificate"].update(sourceRepositoryDigest=flow.first.sha, buildConfigDigest=flow.first.sha)
    verified["verifiedTimestamps"][0]["timestamp"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    if response_change:
        response_change(verified)
    fixture = flow.tmp_path / "verifier-fixture"
    fixture.mkdir()
    flow.verifier = origins.standin(fixture, value=response, mutation=mutation)
    def emitter(retained, facts):
        assert retained is flow.retained and facts.check_run_id == flow.second.check_run_id
        assert flow.store.status(journals.key_of(flow.issued)) == "consumed"
        flow.emitted.append(facts.job_id)
        return flow.verifier.pins[1]
    flow.emitter = emitter
    return flow


def emit(flow, **changes):
    arguments = dict(emitter=flow.emitter, verifier=flow.verifier.pins[2], trusted_root=flow.verifier.pins[3])
    return flow.session.emit(flow.issued, flow.token(flow.issued), flow.retained, **(arguments | changes))


@pytest.mark.parametrize("flow", [False, True], indirect=True, ids=["absent", "explicit-direct"])
def test_authentication_precedes_actual_copy_and_emission_reuses_exact_seven_bytes(flow):
    flow.model.emitted = lambda directory: pytest.fail("capture before durable consume") \
        if flow.store.status(journals.key_of(flow.first)) != "consumed" else None
    ready(flow)
    result = emit(flow)
    assert type(result) is controller.ControllerEmission
    assert result.capture_job.job_id == 707 and result.emission_job.job_id == 708
    assert result.capture_job.check_run_id == "909" and result.emission_job.check_run_id == "910"
    for facts, issued in ((result.capture_job, flow.first), (result.emission_job, flow.issued)):
        assert facts.job_workflow_ref == issued.job_workflow_ref
        assert facts.job_workflow_sha == issued.job_workflow_sha
        assert facts.job_id != int(facts.check_run_id)
        assert flow.store.status(journals.key_of(issued)) == "consumed"
    assert result.capture.artifact_closure_sha256 == result.artifact_origin.policy.subject_sha256
    assert dict(result.capture.file_sha256) == {name: sha(raw) for name, raw in flow.model.expected.items()}
    assert flow.model.calls == ["builder"] and flow.emitted == [708]
    assert not hasattr(result, "eligibleForProtectedSigner") and not hasattr(result, "provenance")
    assert flow.retained.handoff["eligibleForProtectedSigner"] is False
    marker = json.loads((flow.model.operation / "capture-complete.json").read_bytes())
    assert marker["authenticatedJob"] is False
    assert flow.verifier.marker.is_file()  # Existing verifier subprocess really ran.
    flow.retained.assert_exact()


@pytest.mark.parametrize("changes", [{"run_attempt": "3"}, {"check_run_id": "910"},
    {"sha": "e" * 40}, {"runner_environment": "self-hosted"}, {"aud": "other"}])
def test_wrong_real_signed_request_never_builds(flow, changes):
    flow.token = lambda selected: journals.token_for(selected, flow.key, **changes)
    with pytest.raises(controller.ControllerCaptureError, match="capture-failed"):
        run_capture(flow)
    assert flow.model.calls == [] and flow.store.status(journals.key_of(flow.first)) == "pending"
    with pytest.raises(controller.ControllerCaptureError, match="already-started"):
        run_capture(flow)


@pytest.mark.parametrize("change", [{"check_run_id": "909"}, {"run_attempt": "3"},
    {"transaction_id": "e" * 64}, {"sha": "e" * 40}, {"runner_environment": "self-hosted"}])
def test_admission_rejects_same_job_or_foreign_invocation(flow, change):
    with pytest.raises(controller.ControllerCaptureError, match="admission-failed"):
        controller.ControllerCaptureSession(flow.store, flow.first, replace(flow.second, **change), flow.policy, flow.preserved)


def test_stored_full_policy_must_match_even_fields_omitted_from_returned_facts(flow):
    flow.session = controller.ControllerCaptureSession(flow.store, replace(flow.first, event_name="push"),
        flow.second, flow.policy, flow.preserved)
    with pytest.raises(controller.ControllerCaptureError, match="capture-failed"):
        run_capture(flow)
    assert flow.model.calls == [] and flow.store.status(journals.key_of(flow.first)) == "pending"


@pytest.mark.parametrize("flow", [True], indirect=True, ids=["explicit-direct"])
@pytest.mark.parametrize("change", [
    {"job_workflow_ref": None, "job_workflow_sha": None},
    {"job_workflow_ref": "foreign/repo/.github/workflows/build.yml@refs/heads/main"},
    {"job_workflow_sha": "e" * 40},
], ids=["removed-pair", "foreign-workflow", "changed-sha"])
def test_stored_capture_workflow_tuple_drift_rejected_before_consume_or_build(flow, change, monkeypatch):
    flow.session = controller.ControllerCaptureSession(flow.store, replace(flow.first, **change),
        flow.second, flow.policy, flow.preserved)
    consumed = []
    monkeypatch.setattr(flow.store, "authenticate_and_consume", lambda *args: consumed.append(args))
    with pytest.raises(controller.ControllerCaptureError, match="capture-failed"):
        run_capture(flow)
    assert consumed == [] and flow.model.calls == []
    assert flow.store.status(journals.key_of(flow.first)) == "pending"
    assert flow.store._read(journals.key_of(flow.first))[1] == flow.first
    with pytest.raises(controller.ControllerCaptureError, match="already-started"):
        run_capture(flow)
    assert consumed == []


def test_interrupted_builder_keeps_consumed_challenge_and_never_replays(flow):
    flow.model.fail = True
    with pytest.raises(controller.ControllerCaptureError) as error:
        run_capture(flow)
    assert "PRIVATE" not in "".join(traceback.format_exception(error.value))
    assert flow.store.status(journals.key_of(flow.first)) == "consumed"
    flow.session = controller.ControllerCaptureSession(flow.store, flow.first, flow.second, flow.policy, flow.preserved)
    with pytest.raises(controller.ControllerCaptureError):
        run_capture(flow)
    with pytest.raises(journal.ChallengeStoreError):
        flow.store.issue(journals.template())
    assert flow.model.calls == ["builder"] and flow.model.operation.is_dir()


@pytest.mark.parametrize("field", ["directory", "lock_sha256", "artifact_closure_sha256", "file_sha256"])
def test_swapped_capture_result_rejected(flow, monkeypatch, field):
    original = capture.run_builder_capture_handoff
    def swapped(*args):
        value = original(*args)
        changes = {"directory": flow.tmp_path / "other-session", "lock_sha256": "e" * 64,
            "artifact_closure_sha256": "e" * 64, "file_sha256": value.file_sha256 + value.file_sha256[:1]}
        return replace(value, **{field: changes[field]})
    monkeypatch.setattr(capture, "run_builder_capture_handoff", swapped)
    with pytest.raises(controller.ControllerCaptureError, match="capture-failed"):
        run_capture(flow)
    assert flow.session._captured is None


def test_independently_admitted_manifest_not_derived_from_builder(flow):
    flow.session = controller.ControllerCaptureSession(flow.store, flow.first, flow.second,
        replace(flow.policy, subject_sha256="e" * 64), flow.preserved)
    with pytest.raises(controller.ControllerCaptureError):
        run_capture(flow)
    assert flow.model.calls == ["builder"]


@pytest.mark.parametrize("field", ["check_run_id", "run_attempt", "transaction_id", "environment"])
def test_wrong_emission_policy_rejected_before_callback_or_consume(flow, field):
    ready(flow)
    flow.issued = replace(flow.issued, **{field: {"check_run_id": "911", "run_attempt": "3",
        "transaction_id": "e" * 64, "environment": "other"}[field]})
    with pytest.raises(controller.ControllerCaptureError):
        emit(flow)
    assert flow.emitted == [] and not flow.verifier.marker.exists()


@pytest.mark.parametrize("flow", [True], indirect=True, ids=["explicit-direct"])
@pytest.mark.parametrize("change", [
    {"job_workflow_ref": None, "job_workflow_sha": None},
    {"job_workflow_ref": "foreign/repo/.github/workflows/build.yml@refs/heads/main"},
    {"job_workflow_sha": "e" * 40},
], ids=["removed-pair", "foreign-workflow", "changed-sha"])
def test_issued_emission_workflow_tuple_drift_rejected_before_consume_or_callback(flow, change, monkeypatch):
    ready(flow)
    issued = flow.issued
    flow.issued = replace(issued, **change)
    consumed = []
    monkeypatch.setattr(flow.store, "authenticate_and_consume", lambda *args: consumed.append(args))
    with pytest.raises(controller.ControllerCaptureError, match="emission-failed"):
        emit(flow)
    assert consumed == [] and flow.emitted == [] and flow.model.calls == ["builder"]
    assert not flow.verifier.marker.exists()
    assert flow.store.status(journals.key_of(flow.first)) == "consumed"
    assert flow.store.status(journals.key_of(issued)) == "pending"
    assert flow.store._read(journals.key_of(issued))[1] == issued
    with pytest.raises(controller.ControllerCaptureError, match="emission-state"):
        emit(flow)
    assert consumed == []


def test_actual_authenticated_emission_job_must_differ_from_capture(flow):
    ready(flow)
    flow.serve(flow.issued, 707)
    with pytest.raises(controller.ControllerCaptureError):
        emit(flow)
    assert flow.emitted == [] and flow.store.status(journals.key_of(flow.issued)) == "consumed"


def test_swapped_preserved_session_rejected_even_same_bytes(flow):
    ready(flow)
    # A second actual preserved snapshot with byte-identical but foreign path.
    other = flow.tmp_path / "other-preserved"
    shutil.copytree(flow.preserved, other)
    original = fleet._preserved_path
    flow.monkeypatch.setattr(fleet, "_preserved_path", lambda path, label, **kwargs:
        None if path == other or other in path.parents else original(path, label, **kwargs))
    flow.retained = fleet.PreservedRebuildHandoff(flow.preserved.with_name("preserved-lock.json"), other)
    with pytest.raises(controller.ControllerCaptureError):
        emit(flow)
    assert flow.emitted == [] and not flow.verifier.marker.exists()


@pytest.mark.parametrize("member", range(7))
def test_each_retained_member_drift_rejected_before_emission(flow, member):
    ready(flow)
    target = sorted(flow.preserved.iterdir())[member]
    target.write_bytes(target.read_bytes() + b" ")
    with pytest.raises(controller.ControllerCaptureError):
        emit(flow)
    assert flow.emitted == [] and flow.store.status(journals.key_of(flow.issued)) == "pending"


def test_callback_error_is_sanitized_consumed_and_nonreplayable(flow):
    ready(flow)
    def failed(retained, facts):
        flow.emitted.append(facts.job_id)
        raise RuntimeError("PRIVATE callback token diagnostic")
    with pytest.raises(controller.ControllerCaptureError) as error:
        emit(flow, emitter=failed)
    assert "PRIVATE" not in "".join(traceback.format_exception(error.value))
    assert flow.store.status(journals.key_of(flow.issued)) == "consumed"
    with pytest.raises(controller.ControllerCaptureError, match="emission-state"):
        emit(flow)
    assert flow.emitted == [708] and flow.retained.artifact_subject_path.is_file()


def test_successful_emission_cannot_repeat_or_reenter(flow):
    ready(flow)
    original = flow.emitter
    def reenter(retained, facts):
        with pytest.raises(controller.ControllerCaptureError, match="emission-state"):
            emit(flow)
        return original(retained, facts)
    emit(flow, emitter=reenter)
    with pytest.raises(controller.ControllerCaptureError, match="emission-state"):
        emit(flow)
    assert flow.emitted == [708]


@pytest.mark.parametrize("target", ["manifest", "lock", "verifier", "root"])
def test_emitter_cannot_change_retained_or_verifier_authority(flow, target):
    ready(flow)
    selected = {"manifest": flow.retained.artifact_subject_path, "lock": flow.model.lock.path,
        "verifier": flow.verifier.pins[2].path, "root": flow.verifier.pins[3].path}[target]
    def drift(retained, facts):
        selected.write_bytes(selected.read_bytes() + b" ")
        return flow.emitter(retained, facts)
    with pytest.raises(controller.ControllerCaptureError):
        emit(flow, emitter=drift)
    assert flow.emitted == [708] and not flow.verifier.marker.exists()


def test_drift_during_actual_verifier_subprocess_rejected(flow):
    target = flow.preserved / capture.MANIFEST
    ready(flow, mutation=f"Path({str(target)!r}).write_bytes(b'changed during verifier')")
    with pytest.raises(controller.ControllerCaptureError):
        emit(flow)
    assert flow.verifier.marker.exists() and flow.emitted == [708]


@pytest.mark.parametrize("fault", ["subject", "workflow", "run", "predicate"])
def test_existing_origin_policy_still_mandatory_after_callback(flow, fault):
    def change(value):
        if fault == "subject":
            value["statement"]["subject"][0]["digest"]["sha256"] = "e" * 64
        elif fault == "predicate":
            value["statement"]["predicateType"] = "https://unadmitted.invalid"
        else:
            field = "buildSignerDigest" if fault == "workflow" else "runInvocationURI"
            value["signature"]["certificate"][field] = "wrong"
    ready(flow, response_change=change)
    with pytest.raises(controller.ControllerCaptureError):
        emit(flow)
    assert flow.emitted == [708] and flow.verifier.marker.exists()


def test_emission_authentication_must_remain_fresh_through_callback(flow, monkeypatch):
    ready(flow)
    def expired(retained, facts):
        monkeypatch.setattr(controller, "time", SimpleNamespace(time=lambda: facts.valid_until))
        return flow.emitter(retained, facts)
    with pytest.raises(controller.ControllerCaptureError):
        emit(flow, emitter=expired)
    assert flow.emitted == [708] and not flow.verifier.marker.exists()


def test_long_build_uses_fresh_distinct_emission_challenge_not_capture_renewal(flow):
    # Let a genuinely signed, consumed short-lived request expire. Do not mock
    # the cryptographic clock or extend/reissue that permanent job slot.
    alternate = replace(journals.template(), check_run_id="908")
    flow.first = flow.store.issue(alternate, lifetime_seconds=5)
    flow.session = controller.ControllerCaptureSession(flow.store, flow.first, flow.second, flow.policy, flow.preserved)
    flow.serve(flow.first, 707)
    run_capture(flow)
    time.sleep(max(0, flow.first.challenge_expires_at - time.time()) + 0.05)
    assert int(time.time()) >= flow.first.challenge_expires_at
    # Ready the second phase using the already captured bytes, not another run.
    ready(flow, capture_first=False)
    result = emit(flow)
    assert result.capture_job.valid_until <= result.emission_job.checked_at
    assert flow.model.calls == ["builder"] and flow.emitted == [708]
    with pytest.raises(journal.ChallengeStoreError):
        flow.store.issue(alternate)


@pytest.mark.parametrize("member", range(7))
def test_preserved_bytes_must_equal_actual_capture_not_just_a_valid_other_handoff(flow, member):
    ready(flow)
    value = flow.session._captured
    changed = list(value.file_sha256)
    name, _digest = changed[member]
    changed[member] = (name, "e" * 64)
    flow.session._captured = replace(value, file_sha256=tuple(changed))
    with pytest.raises(controller.ControllerCaptureError):
        emit(flow)
    assert flow.emitted == [] and flow.store.status(journals.key_of(flow.issued)) == "pending"


def test_expiry_during_verification_still_denies_composition(flow, monkeypatch):
    ready(flow)
    original = origin.verify_rebuild_handoff_origin
    def expires(*args, **kwargs):
        result = original(*args, **kwargs)
        monkeypatch.setattr(controller, "time", SimpleNamespace(time=lambda: flow.issued.challenge_expires_at))
        return result
    monkeypatch.setattr(origin, "verify_rebuild_handoff_origin", expires)
    with pytest.raises(controller.ControllerCaptureError):
        emit(flow)
    assert flow.verifier.marker.exists() and flow.emitted == [708]
