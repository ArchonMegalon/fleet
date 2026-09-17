"""Source-only tests for the fixed four-role deployment renderer."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import stat

import pytest

from scripts import android_artifact_origin as origin
from scripts import android_container_runtime as runtime
from scripts import android_deployment_materializer as materializer
from scripts import android_preview12_signer_credentials as credentials
from scripts import android_protected_job_bootstrap as bootstrap
from scripts import android_protected_job_launcher as launcher
from scripts import android_workflow_identity as identity


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _job(role, sha, tx, *, check):
    return identity.WorkflowJobPolicy(
        repository="example/repo", repository_id="123", repository_owner="example",
        repository_owner_id="456", subject=role, sha=sha, ref="refs/heads/main",
        workflow_ref="example/repo/.github/workflows/fleet.yml@refs/heads/main",
        workflow_sha=sha, run_id="42", run_attempt="2", check_run_id=str(check),
        environment="android-preview12-release-builder" if role == "protected" else "android-preview12",
        event_name="workflow_dispatch", runner_environment="github-hosted",
        run_status="in_progress", run_conclusion=None, job_status="in_progress",
        job_conclusion=None, transaction_id=tx, challenge_nonce="c" * 64,
        challenge_issued_at=100, challenge_expires_at=500, job_workflow_ref=None,
        job_workflow_sha=None)


def _artifact(sha, tx):
    return origin.OriginPolicy(
        repository="example/repo", repository_id="123", repository_uri="https://github.com/example/repo",
        owner_id="456", owner_uri="https://github.com/example", source_commit=sha,
        signer_commit=sha, source_ref="refs/heads/main",
        workflow_identity="https://github.com/example/repo/.github/workflows/fleet.yml@refs/heads/main",
        build_config_identity="https://github.com/example/repo/.github/workflows/fleet.yml@refs/heads/main",
        issuer=identity.ISSUER, predicate_type="https://example.test/predicate/v1",
        trigger="workflow_dispatch", run_id="42", run_attempt="2",
        subject_name="FLEET_ANDROID_PREVIEW12_REBUILD_HANDOFF.generated.json",
        subject_sha256="e" * 64, visibility="public", runner_environment="github-hosted",
        timestamp_types=("TimestampAuthority",), maximum_age_seconds=3600, future_skew_seconds=30)


def _runtime(process_role, user):
    return asdict(runtime.RuntimePolicy(
        image_id="sha256:" + "1" * 64,
        requested_image="ghcr.io/example/image:base@sha256:" + "2" * 64,
        user=user, workdir="/work", entrypoint=("/usr/bin/python3",), command=(),
        environment=launcher.PUBLIC_ENVIRONMENT if process_role == "signer" else ("PATH=/usr/bin:/bin",),
        resources=runtime.ResourceLimits(64 * 1024 * 1024, 1, 64), process_role=process_role))


def _pin(path, digest="a" * 64):
    return {"path": str(path), "sha256": digest}


def _profile(tmp_path):
    sha = "a" * 40
    tx = "b" * 64
    jobs = {role: _job(role, sha, tx, check=900 + index)
            for index, role in enumerate(materializer.ROLES[1:], 1)}
    artifact = asdict(_artifact(sha, tx))
    binding = {"job_names": {role: "preview12-" + role for role in materializer.ROLES[1:]},
               "templates": {role: asdict(job) for role, job in jobs.items()}}
    public = tmp_path / "public"
    public.mkdir(mode=0o700)
    output_root = tmp_path / "runner-temp"
    output_root.mkdir(mode=0o700)
    owner_value = {
        "fleet_root": str(tmp_path / "fleet"), "code_pins": {"scripts/x.py": "d" * 64},
        "pins": {name: _pin(public / name) for name in ("lock", "docker", "verifier", "trusted_root", "tls_certificate")},
        "journal": {"path": str(tmp_path / "journal.db"), "controller_id": "controller01", "database_id": "e" * 64},
        "capture_policy": asdict(jobs["capture"]), "emission_policy": asdict(jobs["emission"]),
        "protected_job_policy": asdict(jobs["protected"]), "artifact_policy": artifact,
        "runtime_policy": _runtime("builder", "1000:1000"),
        "operation_directory": str(tmp_path / "operation"), "attempt_directory": str(tmp_path / "attempt"),
        "custody_packet": str(tmp_path / "custody"), "output_bind_target": "/output",
        "handoff_child_name": "handoff", "base_url": "https://controller.example",
        "bearer_sha256": {name: (str(index) * 64) for index, name in enumerate(("capture", "emission", "intake", "approval", "binary"), 1)},
        "tls": {"bind_address": "127.0.0.1", "key_file": str(tmp_path / "key"), "trusted_proxy_addresses": []},
        "limits": {"whole_seconds": 600, "preparation_wait_seconds": 60}, "role_binding": deepcopy(binding),
    }
    hosted_common = {
        "base_url": "https://controller.example",
        "pins": {name: _pin(public / name) for name in ("controller_ca", "oidc_ca")},
        "transport_inputs": {name: str(tmp_path / name) for name in ("role_bearer", "oidc_request_url", "oidc_request_credential")},
        "attempt_directory": str(tmp_path / "hosted-attempt"), "attestation_output_root": str(output_root),
        "deadline_seconds": 60, "role_binding": deepcopy(binding),
    }
    capture = dict(hosted_common, role="capture", job_policy=asdict(jobs["capture"]), artifact_policy=artifact,
                   attestation_output_root=None)
    emission = dict(hosted_common, role="emission", job_policy=asdict(jobs["emission"]), artifact_policy=artifact)
    persistent = tmp_path / "persistent"
    lock_path = tmp_path / "lock"
    launcher_config = {"mode": "execute", "attempt": tx, "artifact_id": 42, "artifact_sha256": "f" * 64,
        "fleet_root": str(tmp_path / "fleet"), "lock": str(tmp_path / "lock"), "handoff": str(tmp_path / "handoff"),
        "validation": {name: str(tmp_path / name) for name in bootstrap.VALIDATION_FIELDS},
        "recovery": str(persistent / "recovery"), "output": str(persistent / "outputs" / tx),
        "requests": str(tmp_path / "requests"), "responses": str(tmp_path / "responses"),
        "credentials": str(tmp_path / "credentials"), "socket": str(tmp_path / "socket"),
        "code_pins": {"scripts/x.py": "d" * 64}}
    protected_pins = {name: _pin(public / name) for name in bootstrap.PIN_LIMITS}
    protected_pins["lock"]["path"] = str(lock_path)
    protected_value = {"launcher": launcher_config, "job_policy": asdict(jobs["protected"]), "artifact_policy": artifact,
        "runtime_policy": _runtime("signer", "0:0"),
        "pins": protected_pins,
        "persistent": {"parent": str(persistent), "mount_row_sha256": "9" * 64},
        "operation_directory": str(tmp_path / "protected-operation"),
        "secret_inputs": {name: str(tmp_path / ("secret-" + name)) for name in credentials.SECRET_NAMES},
        "transport_inputs": {name: str(tmp_path / ("transport-" + name)) for name in bootstrap.TRANSPORT_LIMITS},
        "base_url": "https://controller.example", "release_wait_seconds": 60, "preparation_wait_seconds": 60,
        "role_binding": deepcopy(binding)}
    return {"owner": owner_value, "capture": capture, "emission": emission, "protected": protected_value}


def _context():
    return {"fleet_sha": "c" * 40, "workflow_sha": "c" * 40, "ref": "refs/heads/main",
            "run_id": "77", "run_attempt": "3", "transaction_id": "d" * 64}


def _set_job_workflow(profile, role, workflow_ref, workflow_sha):
    owner_name = {"capture": "capture_policy", "emission": "emission_policy",
                  "protected": "protected_job_policy"}[role]
    policies = [profile["owner"][owner_name], profile[role]["job_policy"]]
    for document in profile.values():
        policies.append(document["role_binding"]["templates"][role])
    for policy in policies:
        policy["job_workflow_ref"] = workflow_ref
        policy["job_workflow_sha"] = workflow_sha


def _set_artifact_signer(profile, workflow_ref, signer_sha):
    for document in profile.values():
        document["artifact_policy"]["workflow_identity"] = "https://github.com/" + workflow_ref
        document["artifact_policy"]["signer_commit"] = signer_sha


def test_render_uses_real_role_parsers_and_changes_only_invocation_fields(tmp_path):
    profile = _profile(tmp_path)
    before = deepcopy(profile)
    rendered = materializer.render(profile, _context(), "emission")
    value = json.loads(rendered)
    protected = json.loads(materializer.render(profile, _context(), "protected"))
    assert protected["launcher"]["attempt"] == _context()["transaction_id"]
    assert protected["launcher"]["output"].endswith("/outputs/" + _context()["transaction_id"])
    assert value["job_policy"]["check_run_id"] == before["emission"]["job_policy"]["check_run_id"]
    assert value["artifact_policy"]["subject_sha256"] == before["emission"]["artifact_policy"]["subject_sha256"]
    assert protected["runtime_policy"]["image_id"] == before["protected"]["runtime_policy"]["image_id"]
    assert protected["runtime_policy"]["user"] == before["protected"]["runtime_policy"]["user"]
    assert protected["runtime_policy"]["process_role"] == before["protected"]["runtime_policy"]["process_role"]
    assert value["artifact_policy"]["source_commit"] == _context()["fleet_sha"]
    assert value["job_policy"]["transaction_id"] == _context()["transaction_id"]


@pytest.mark.parametrize("change", [
    lambda value: value.update(workflow_sha="f" * 40),
    lambda value: value.update(ref="refs/heads/other"),
])
def test_render_rejects_context_that_cannot_satisfy_existing_identity(change, tmp_path):
    context = _context(); change(context)
    with pytest.raises(materializer.MaterializerError):
        materializer.render(_profile(tmp_path), context, "capture")


def test_materialize_requires_admitted_hashes_and_exclusive_private_output(tmp_path):
    profile = tmp_path / "profile.json"; context = tmp_path / "context.json"
    profile.write_bytes(json.dumps(_profile(tmp_path), sort_keys=True).encode()); profile.chmod(0o600)
    context.write_bytes(json.dumps(_context(), sort_keys=True).encode()); context.chmod(0o600)
    output_parent = tmp_path / "output"; output_parent.mkdir(mode=0o700)
    output = output_parent / "deployment-profile.json"
    digest = materializer.materialize(profile, _sha(profile.read_bytes()), context, _sha(context.read_bytes()), output, "emission")
    assert digest == _sha(output.read_bytes()) and stat.S_IMODE(output.stat().st_mode) == 0o600
    with pytest.raises(materializer.MaterializerError):
        materializer.materialize(profile, "0" * 64, context, _sha(context.read_bytes()), output_parent / "second.json", "emission")
    with pytest.raises(materializer.MaterializerError):
        materializer.materialize(profile, _sha(profile.read_bytes()), context, _sha(context.read_bytes()), output, "emission")


def test_render_preserves_input_object_and_rejects_role_binding_drift(tmp_path):
    profile = _profile(tmp_path)
    original = deepcopy(profile)
    profile["emission"]["role_binding"]["templates"]["protected"]["check_run_id"] = "999"
    with pytest.raises(materializer.MaterializerError):
        materializer.render(profile, _context(), "emission")
    assert profile["owner"]["artifact_policy"] == original["owner"]["artifact_policy"]


@pytest.mark.parametrize("selected_role", materializer.ROLES)
def test_self_referential_reusable_pair_tracks_current_workflow_sha(tmp_path, selected_role):
    profile = _profile(tmp_path)
    own_ref = profile["owner"]["emission_policy"]["workflow_ref"]
    old_sha = profile["owner"]["emission_policy"]["workflow_sha"]
    for role in ("capture", "emission", "protected"):
        _set_job_workflow(profile, role, own_ref, old_sha)
    value = json.loads(materializer.render(profile, _context(), selected_role))
    jobs = [value[name] for name in ("capture_policy", "emission_policy", "protected_job_policy")] if selected_role == "owner" else [value["job_policy"]]
    jobs.extend(value["role_binding"]["templates"].values())
    for job in jobs:
        assert job["job_workflow_ref"] == own_ref
        assert job["job_workflow_sha"] == _context()["workflow_sha"]
    assert value["artifact_policy"]["signer_commit"] == _context()["workflow_sha"]


@pytest.mark.parametrize("same_source_commit", [False, True])
def test_separate_reusable_workflow_identity_remains_immutable(tmp_path, same_source_commit):
    profile = _profile(tmp_path)
    reusable_ref = "example/signer/.github/workflows/reusable.yml@refs/heads/main"
    reusable_sha = profile["owner"]["emission_policy"]["workflow_sha"] if same_source_commit else "f" * 40
    _set_job_workflow(profile, "emission", reusable_ref, reusable_sha)
    _set_job_workflow(profile, "protected", reusable_ref, reusable_sha)
    _set_artifact_signer(profile, reusable_ref, reusable_sha)
    value = json.loads(materializer.render(profile, _context(), "emission"))
    assert value["job_policy"]["job_workflow_ref"] == reusable_ref
    assert value["job_policy"]["job_workflow_sha"] == reusable_sha
    assert value["artifact_policy"]["workflow_identity"] == "https://github.com/" + reusable_ref
    assert value["artifact_policy"]["signer_commit"] == reusable_sha


def test_partial_self_reference_is_rejected(tmp_path):
    profile = _profile(tmp_path)
    own_ref = profile["owner"]["emission_policy"]["workflow_ref"]
    _set_job_workflow(profile, "emission", own_ref, "f" * 40)
    _set_job_workflow(profile, "protected", own_ref, "f" * 40)
    _set_artifact_signer(profile, own_ref, "f" * 40)
    with pytest.raises(materializer.MaterializerError):
        materializer.render(profile, _context(), "emission")


def test_capture_may_keep_a_separate_reusable_identity(tmp_path):
    profile = _profile(tmp_path)
    reusable_ref = "example/capture/.github/workflows/reusable.yml@refs/heads/main"
    reusable_sha = "f" * 40
    _set_job_workflow(profile, "capture", reusable_ref, reusable_sha)
    value = json.loads(materializer.render(profile, _context(), "capture"))
    assert value["job_policy"]["job_workflow_ref"] == reusable_ref
    assert value["job_policy"]["job_workflow_sha"] == reusable_sha
    assert value["artifact_policy"]["signer_commit"] == _context()["workflow_sha"]
