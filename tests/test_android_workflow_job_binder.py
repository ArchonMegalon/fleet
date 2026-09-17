"""Existing validators and synthetic signed OIDC; all metadata transport modeled."""
from copy import deepcopy
from dataclasses import asdict, replace
from types import SimpleNamespace

import pytest

from scripts import android_workflow_job_binder as binder
from scripts import android_workflow_identity as identity
import test_android_workflow_identity as fixtures
from test_android_workflow_identity import policy, keys


@pytest.fixture(autouse=True)
def no_real_transport(monkeypatch):
    monkeypatch.setattr(identity, "_fetch", lambda *_: pytest.fail("unexpected transport"))
    monkeypatch.setattr(identity.origin, "_run", lambda *_: pytest.fail("real subprocess transport"))


@pytest.fixture
def model(policy, monkeypatch):
    names = dict(zip(binder.ROLES, ("Capture reviewed input", "Emit exact manifest", "Protected signer")))
    policies, jobs = {}, {"total_count": 3, "jobs": []}
    for index, role in enumerate(binder.ROLES):
        environment = "android-preview12-release-builder" if role == "protected" else role
        policies[role] = replace(policy, check_run_id="1", environment=environment,
            subject="repo:example/repo:environment:" + environment)
        row = deepcopy(fixtures.api_jobs()["jobs"][0])
        row.update(id=707 + index, name=names[role], run_attempt=2,
            url=identity.API + "/repos/example/repo/actions/jobs/" + str(707 + index),
            check_run_url=identity.API + "/repos/example/repo/check-runs/" + str(909 + index))
        jobs["jobs"].append(row)
    value = SimpleNamespace(policies=policies, names=names, attempt=fixtures.api_attempt(),
                            jobs=jobs, calls=[], callback=None)
    def fetch(url, deadline):
        value.calls.append((url, deadline))
        assert url in {fixtures.ATTEMPT, fixtures.JOBS}
        if value.callback: value.callback(url)
        response = value.attempt if url == fixtures.ATTEMPT else value.jobs
        return response if type(response) is bytes else fixtures.raw(response)
    monkeypatch.setattr(identity, "_fetch", fetch)
    return value


def bind(model):
    return binder.bind_live_roles(role_policies=model.policies, job_names=model.names)


@pytest.mark.parametrize("equal_ids", [False, True])
def test_real_api_helpers_replace_only_check_ids_and_keep_all_owner_fields(model, equal_ids):
    if equal_ids:
        for row in model.jobs["jobs"]:
            row["id"] = int(row["check_run_url"].rsplit("/", 1)[1])
            row["url"] = identity.API + "/repos/example/repo/actions/jobs/" + str(row["id"])
    before = deepcopy(model.policies)
    result = bind(model)
    assert set(result) == set(binder.ROLES) and model.policies == before
    for index, role in enumerate(binder.ROLES):
        assert type(result[role]) is identity.WorkflowJobPolicy
        assert asdict(result[role]) == asdict(before[role]) | {"check_run_id": str(909 + index)}
        assert result[role] is not before[role]
    assert [url for url, _ in model.calls] == [fixtures.ATTEMPT, fixtures.JOBS]
    assert len({deadline for _, deadline in model.calls}) == 1


def test_role_specific_reusable_subject_environment_and_challenge_fields_are_preserved(model):
    for index, role in enumerate(binder.ROLES):
        model.policies[role] = replace(model.policies[role],
            job_workflow_ref=f"example/repo/.github/workflows/{role}.yml@refs/heads/main",
            job_workflow_sha=str(index + 1) * 40, challenge_nonce=str(index + 1) * 64,
            challenge_issued_at=1, challenge_expires_at=2, maximum_token_age_seconds=100 + index)
    result = bind(model)
    for index, role in enumerate(binder.ROLES):
        assert asdict(result[role]) == asdict(model.policies[role]) | {"check_run_id": str(909 + index)}


@pytest.mark.parametrize("count", [0, 1, 2])
def test_fully_validated_missing_roles_are_pending_without_invented_ids(model, count):
    model.jobs["jobs"] = model.jobs["jobs"][:count]
    model.jobs["total_count"] = count
    assert bind(model) is None and len(model.calls) == 2


@pytest.mark.parametrize("index", [0, 1, 2])
@pytest.mark.parametrize("status", sorted(binder.PENDING))
def test_only_closed_pending_states_can_wait(model, index, status):
    model.jobs["jobs"][index]["status"] = status
    assert bind(model) is None and len(model.calls) == 2


@pytest.mark.parametrize("attack", ["missing-role", "extra-role", "wrong-policy-type", "bad-policy", "missing-name",
    "extra-name", "duplicate-name", "empty-name", "long-name", "newline-name", "leading-space", "bool-name",
    "self-hosted", "completed-policy", "wrong-protected-environment"])
def test_bad_owner_inputs_reject_before_any_fetch(model, attack):
    if attack == "missing-role": del model.policies["emission"]
    elif attack == "extra-role": model.policies["other"] = model.policies["capture"]
    elif attack == "wrong-policy-type": model.policies["capture"] = asdict(model.policies["capture"])
    elif attack == "bad-policy": object.__setattr__(model.policies["capture"], "run_id", 1234)
    elif attack == "missing-name": del model.names["emission"]
    elif attack == "extra-name": model.names["other"] = "Other"
    elif attack == "duplicate-name": model.names["emission"] = model.names["capture"]
    elif attack == "empty-name": model.names["capture"] = ""
    elif attack == "long-name": model.names["capture"] = "x" * 256
    elif attack == "newline-name": model.names["capture"] = "name\n"
    elif attack == "leading-space": model.names["capture"] = " name"
    elif attack == "bool-name": model.names["capture"] = True
    elif attack == "self-hosted": model.policies["emission"] = replace(model.policies["emission"], runner_environment="self-hosted")
    elif attack == "completed-policy":
        model.policies["emission"] = replace(model.policies["emission"], job_status="completed", job_conclusion="success")
    else: model.policies["protected"] = replace(model.policies["protected"], environment="unprotected")
    with pytest.raises(binder.JobBindingError, match="^" + binder.ERROR + "$"): bind(model)
    assert model.calls == []


@pytest.mark.parametrize("field,value", [("repository_id", "999"), ("repository_owner_id", "999"),
    ("sha", "b" * 40), ("workflow_sha", "b" * 40), ("run_id", "999"), ("run_attempt", "3"),
    ("event_name", "push"), ("transaction_id", "f" * 64)])
def test_valid_but_mixed_owner_context_rejects_before_fetch(model, field, value):
    model.policies["emission"] = replace(model.policies["emission"], **{field: value})
    with pytest.raises(binder.JobBindingError): bind(model)
    assert model.calls == []


@pytest.mark.parametrize("field,value", [("id", "1234"), ("run_attempt", 3), ("head_sha", "b" * 40),
    ("status", "completed"), ("conclusion", "success"), ("event", "push"),
    ("path", ".github/workflows/unreviewed.yml"), ("url", "https://evil.invalid"),
    ("html_url", "https://evil.invalid")])
def test_wrong_run_readback_never_fetches_jobs(model, field, value):
    model.attempt[field] = value
    with pytest.raises(binder.JobBindingError): bind(model)
    assert [url for url, _ in model.calls] == [fixtures.ATTEMPT]


@pytest.mark.parametrize("attack", ["private", "repository-id", "owner-id", "owner-login"])
def test_public_repository_and_owner_api_identity_remain_exact(model, attack):
    repo = model.attempt["repository"]
    if attack == "private": repo["private"] = True
    elif attack == "repository-id": repo["id"] = 999
    elif attack == "owner-id": repo["owner"]["id"] = 999
    else: repo["owner"]["login"] = "foreign"
    with pytest.raises(binder.JobBindingError): bind(model)
    assert len(model.calls) == 1


@pytest.mark.parametrize("attack", ["duplicate-job", "duplicate-check", "duplicate-name", "missing-conclusion",
    "conclusion", "status", "completed", "attempt", "run", "sha", "url", "run-url", "null-check", "foreign-check",
    "check-leading-zero", "job-bool", "name-type", "extra-page", "bool-count", "truncated", "empty-mismatch"])
def test_pending_first_cannot_mask_any_later_malformed_or_terminal_row(model, attack):
    model.jobs["jobs"][0]["status"] = "queued"
    row = model.jobs["jobs"][2]
    changes = {"duplicate-job": {"id": 707}, "duplicate-check": {"check_run_url": model.jobs["jobs"][0]["check_run_url"]},
        "duplicate-name": {"name": model.names["capture"]}, "conclusion": {"conclusion": "failure"},
        "status": {"status": "requested"}, "completed": {"status": "completed", "conclusion": "success"},
        "attempt": {"run_attempt": 3}, "run": {"run_id": 999}, "sha": {"head_sha": "b" * 40},
        "url": {"url": "https://evil.invalid"}, "run-url": {"run_url": "https://evil.invalid"},
        "null-check": {"check_run_url": None}, "foreign-check": {"check_run_url": "https://evil.invalid/check-runs/911"},
        "check-leading-zero": {"check_run_url": identity.API + "/repos/example/repo/check-runs/0911"},
        "job-bool": {"id": True}, "name-type": {"name": True}}
    if attack in changes: row.update(changes[attack])
    elif attack == "missing-conclusion": del row["conclusion"]
    elif attack == "extra-page": model.jobs["next"] = "unreviewed"
    elif attack == "bool-count": model.jobs["total_count"] = True
    elif attack == "truncated": model.jobs["total_count"] = 4
    else: model.jobs["jobs"] = []
    with pytest.raises(binder.JobBindingError): bind(model)
    assert len(model.calls) == 2


def test_unrelated_rows_still_fully_validated_before_missing_role_pending(model):
    model.jobs["jobs"][2]["name"] = "Unrelated live job"
    assert bind(model) is None
    model.jobs["jobs"][2]["run_attempt"] = 3
    with pytest.raises(binder.JobBindingError): bind(model)


@pytest.mark.parametrize("conclusion", ["success", "failure", "skipped"])
def test_completed_unrelated_preflight_does_not_authenticate_or_block_live_roles(model, conclusion):
    preflight = deepcopy(model.jobs["jobs"][0])
    preflight.update(id=700, name="Unrelated preflight", status="completed", conclusion=conclusion,
        url=identity.API + "/repos/example/repo/actions/jobs/700",
        check_run_url=identity.API + "/repos/example/repo/check-runs/900")
    model.jobs["jobs"].insert(0, preflight)
    model.jobs["total_count"] = 4
    result = bind(model)
    assert {role: value.check_run_id for role, value in result.items()} == dict(zip(binder.ROLES, ("909", "910", "911")))
    assert all(type(value) is identity.WorkflowJobPolicy for value in result.values())


@pytest.mark.parametrize("fault", ["sha", "attempt", "duplicate-id", "duplicate-check", "bad-status", "bad-conclusion", "missing-conclusion"])
def test_unrelated_completed_row_malformed_metadata_still_rejects_before_pending(model, fault):
    row = model.jobs["jobs"][2]
    row.update(name="Unrelated preflight", status="completed", conclusion="success")
    model.jobs["jobs"][0]["status"] = "queued"
    if fault == "sha": row["head_sha"] = "f" * 40
    elif fault == "attempt": row["run_attempt"] = 3
    elif fault == "duplicate-id": row["id"] = 707
    elif fault == "duplicate-check": row["check_run_url"] = model.jobs["jobs"][0]["check_run_url"]
    elif fault == "bad-status": row["status"] = False
    elif fault == "bad-conclusion": row["conclusion"] = {}
    else: del row["conclusion"]
    with pytest.raises(binder.JobBindingError): bind(model)


@pytest.mark.parametrize("raw", [b'{"total_count":0,"total_count":0,"jobs":[]}', b'[]',
    b'{"total_count":0,"jobs":[],"metadata":NaN}', b'not json'])
def test_existing_json_parser_rejects_before_pending(model, raw):
    model.jobs = raw
    with pytest.raises(binder.JobBindingError): bind(model)


@pytest.mark.parametrize("stage", [fixtures.ATTEMPT, fixtures.JOBS])
def test_network_error_is_constant_and_never_retried(model, stage, capsys):
    def fail(url):
        if url == stage: raise OSError("PRIVATE_TEST upstream details")
    model.callback = fail
    with pytest.raises(binder.JobBindingError) as caught: bind(model)
    assert str(caught.value) == binder.ERROR and caught.value.__suppress_context__
    assert len(model.calls) == (1 if stage == fixtures.ATTEMPT else 2)
    assert capsys.readouterr() == ("", "")


def test_late_successful_metadata_never_returns_a_binding(model, monkeypatch):
    clock = SimpleNamespace(now=100.0)
    monkeypatch.setattr(binder, "time", SimpleNamespace(monotonic=lambda: clock.now))
    def remaining(deadline):
        identity._require(clock.now < deadline, "workflow-deadline")
        return deadline - clock.now
    monkeypatch.setattr(identity, "_remaining", remaining)
    model.callback = lambda _: setattr(clock, "now", clock.now + identity.TOTAL_SECONDS)
    with pytest.raises(binder.JobBindingError): bind(model)
    assert len(model.calls) == 1


def test_discovered_policy_still_requires_actual_existing_signed_identity(model, keys, monkeypatch):
    bound = bind(model)["protected"]
    values = fixtures.claims() | {"sub": bound.subject, "environment": bound.environment,
                                "check_run_id": bound.check_run_id}
    token = fixtures.sign(keys[0], values)
    fixtures.replies(monkeypatch, keys[0], jobs=model.jobs)
    facts = identity.authenticate_workflow_job(token, bound)
    assert facts.job_id == 709 and facts.check_run_id == "911"
    with pytest.raises(identity.WorkflowIdentityError):
        identity.authenticate_workflow_job(fixtures.sign(keys[1], values), bound)
    with pytest.raises(identity.WorkflowIdentityError):
        identity.authenticate_workflow_job(fixtures.sign(keys[0], dict(values, check_run_id="909")), bound)
