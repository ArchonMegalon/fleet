"""Real capture/byte fences and job crypto; modeled Docker, mounts and attester.

No SDK build, live credentials, GitHub attestation or signing occurs here.
"""
from dataclasses import replace
import json

import pytest

from scripts import android_builder_handoff as capture
from scripts import android_controller_capture as controller
from scripts import android_preview12_external_rebuilder as fleet
import test_android_controller_capture as sessions
import test_android_preview12_external_rebuilder as locks
import test_android_workflow_challenge_store as journals
from test_android_builder_handoff import model, sha
from test_android_controller_capture import flow
from test_android_preview12_preserved_handoff import rewrite
from test_android_workflow_challenge_store import signing_key, store


def select_single(model):
    lock = locks.synthetic_ready_lock()
    lock["toolchain"]["builder_image"] = model.policy.requested_image
    lock["rebuild"].update(verification_mode="internal-single-build", distribution_track="internal",
        authenticated_builder_execution_required=True,
        deterministic_unsigned_digest_match_required=False, full_test_suite_required=False)
    model.lock.path.write_bytes(json.dumps(lock).encode())
    model.lock = replace(model.lock, sha256=sha(model.lock.path.read_bytes()))
    def request(value):
        value["contractName"] = fleet.SINGLE_BUILD_REQUEST_CONTRACT
        value["buildVerification"] = {"mode": "single-isolated-build", "distributionTrack": "internal"}
        value["requiredExternalSigner"].update(mustRebuildAndMatchUnsignedAab=False,
                                               mustAuthenticateBuilderExecutionProvenance=True)
    rewrite(model.paths["externalSignerRequest"], request)
    def manifest(value):
        value["contractName"] = fleet.SINGLE_BUILD_HANDOFF_CONTRACT
        value["bindings"].update(lockSha256=model.lock.sha256,
                                 requestSha256=sha(model.paths["externalSignerRequest"].read_bytes()))
    rewrite(model.manifest, manifest)
    model.expected = {path.name: path.read_bytes() for path in model.fixture.iterdir()}


def prepare(model):
    return controller.OwnedSingleBuild(policy=model.policy, docker=model.docker, lock=model.lock,
        operation_directory=model.operation, output_bind_target="/output", handoff_child_name=model.child)


def attach(flow, owned):
    flow.policy = replace(flow.policy, subject_sha256=owned.manifest_sha256)
    flow.session = controller.ControllerCaptureSession(flow.store, flow.first, flow.second,
        flow.policy, flow.preserved, owned_single_build=owned)


def test_one_owned_build_then_real_job_authentication_and_exact_emission(flow):
    select_single(flow.model)
    owned = prepare(flow.model)
    assert flow.model.calls == ["builder"]
    assert flow.store.status(journals.key_of(flow.first)) == "pending"
    attach(flow, owned)
    sessions.run_capture(flow)
    sessions.ready(flow, capture_first=False)
    result = sessions.emit(flow)
    assert flow.model.calls == ["builder"]
    assert result.capture_order == "owner-build-before-authenticated-transfer"
    assert result.capture.artifact_closure_sha256 == owned.manifest_sha256
    assert result.artifact_origin.policy == flow.policy
    assert flow.retained.handoff["eligibleForProtectedSigner"] is False
    assert json.loads((flow.model.operation / "capture-complete.json").read_bytes())["authenticatedJob"] is False


def test_single_mode_without_live_preparation_rejects_before_build_or_authentication(flow):
    select_single(flow.model)
    with pytest.raises(controller.ControllerCaptureError):
        sessions.run_capture(flow)
    assert flow.model.calls == []
    assert flow.store.status(journals.key_of(flow.first)) == "pending"


@pytest.mark.parametrize("change", [
    lambda value: value["rebuild"].pop("verification_mode"),
    lambda value: value["rebuild"].update(distribution_track="production"),
    lambda value: value.update(state="dormant"),
])
def test_only_explicit_ready_internal_policy_can_start(model, change):
    select_single(model)
    rewrite(model.lock.path, change)
    model.lock = replace(model.lock, sha256=sha(model.lock.path.read_bytes()))
    with pytest.raises(controller.ControllerCaptureError, match="owned-single-build-failed"):
        prepare(model)
    assert model.calls == []


@pytest.mark.parametrize("fault", ["bytes", "inode", "lock", "extra"])
def test_changed_capture_is_rejected_before_job_authentication(flow, fault):
    select_single(flow.model)
    owned = prepare(flow.model)
    attach(flow, owned)
    path = flow.model.operation / capture.COPY_DIRECTORY / capture.MANIFEST
    if fault == "bytes":
        path.write_bytes(path.read_bytes() + b" ")
    elif fault == "inode":
        raw = path.read_bytes()
        path.rename(path.with_name("held-original"))
        path.write_bytes(raw)
        path.chmod(0o600)
        path.with_name("held-original").rename(flow.tmp_path / "original-manifest")
    elif fault == "lock":
        flow.model.lock.path.write_bytes(flow.model.lock.path.read_bytes() + b" ")
    else:
        (path.parent / "unexpected").write_bytes(b"extra")
    with pytest.raises(controller.ControllerCaptureError):
        sessions.run_capture(flow)
    assert flow.store.status(journals.key_of(flow.first)) == "pending"
    assert flow.model.calls == ["builder"]


@pytest.mark.parametrize("fault", ["operation", "docker", "policy", "subject"])
def test_preparation_cannot_bind_another_input_or_subject(flow, fault):
    select_single(flow.model)
    owned = prepare(flow.model)
    attach(flow, owned)
    changes = {}
    if fault == "operation":
        changes["operation_directory"] = flow.tmp_path / "another-operation"
    elif fault == "docker":
        changes["docker"] = replace(flow.model.docker, sha256="a" * 64)
    elif fault == "policy":
        changes["policy"] = replace(flow.model.policy, maximum_runtime_seconds=11)
    else:
        with pytest.raises(controller.ControllerCaptureError):
            controller.ControllerCaptureSession(flow.store, flow.first, flow.second,
                replace(flow.policy, subject_sha256="0" * 64), flow.preserved, owned_single_build=owned)
        assert flow.model.calls == ["builder"]
        return
    with pytest.raises(controller.ControllerCaptureError):
        sessions.run_capture(flow, **changes)
    assert flow.store.status(journals.key_of(flow.first)) == "pending"
    assert flow.model.calls == ["builder"]


def test_bad_transfer_token_consumes_preparation_without_rebuild_or_reassignment(flow):
    select_single(flow.model)
    owned = prepare(flow.model)
    attach(flow, owned)
    valid = flow.token
    flow.token = lambda selected: valid(selected, aud="wrong")
    with pytest.raises(controller.ControllerCaptureError):
        sessions.run_capture(flow)
    flow.token = valid
    attach(flow, owned)
    with pytest.raises(controller.ControllerCaptureError):
        sessions.run_capture(flow)
    assert flow.model.calls == ["builder"]
    assert flow.store.status(journals.key_of(flow.first)) == "pending"


def test_serialized_or_detached_capture_is_not_owned_preparation(flow):
    select_single(flow.model)
    owned = prepare(flow.model)
    for supplied in ({"manifest_sha256": owned.manifest_sha256}, owned._result):
        with pytest.raises(controller.ControllerCaptureError):
            controller.ControllerCaptureSession(flow.store, flow.first, flow.second,
                flow.policy, flow.preserved, owned_single_build=supplied)
    assert flow.model.calls == ["builder"]


def test_failed_builder_preserves_failure_without_preparation(model):
    select_single(model)
    model.fail = True
    with pytest.raises(controller.ControllerCaptureError):
        prepare(model)
    assert model.calls == ["builder"]
    assert not (model.operation / "capture-complete.json").exists()
