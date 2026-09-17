"""Synthetic public-status scheduling tests; no GitHub, credentials or listener."""
from dataclasses import asdict, replace
from pathlib import Path
import json
from types import SimpleNamespace
import sys
import tempfile

import pytest

from scripts import android_startup_scheduling as scheduling
from scripts import android_workflow_identity as identity
from scripts import android_workflow_job_binder as binder
import test_android_workflow_identity as fixtures


def _model():
    base = fixtures.policy.__wrapped__()
    names, templates = {}, {}
    for role in binder.ROLES:
        environment = "android-preview12-release-builder" if role == "protected" else role
        names[role] = "Preview12 " + role
        templates[role] = replace(base, check_run_id="1", environment=environment,
                                   subject="repo:example/repo:environment:" + environment)
    value = {"role_binding": {"job_names": names, "templates": {k: asdict(v) for k, v in templates.items()}},
             "startup_barrier": {"publisher_id": 777}, "limits": {"preparation_wait_seconds": 60}}
    return value, templates


def _bound(templates):
    return {role: replace(policy, check_run_id=str(900 + index))
            for index, (role, policy) in enumerate(templates.items())}


def _status(config, stage, bound, state="success", *, creator=777, context=None,
            target=None, description=None, updated="2026-09-17T00:00:01Z", ident=1):
    policy = bound["capture"]
    return {"id": ident, "state": state, "context": context or scheduling._context(config, stage),
            "description": description if description is not None else scheduling._description(scheduling.binding_digest(bound)),
            "target_url": target if target is not None else scheduling._attempt_url(policy),
            "url": scheduling._status_url(policy), "created_at": "2026-09-17T00:00:00Z",
            "updated_at": updated, "creator": {"id": creator, "login": "publisher", "url": identity.API + "/users/publisher"}}


@pytest.fixture
def model():
    value, templates = _model()
    return SimpleNamespace(value=value, templates=templates, bound=_bound(templates))


def test_static_mode_has_no_io_and_barrier_requires_role_binding(monkeypatch):
    assert scheduling.validate_deployment({}) is None
    with pytest.raises(scheduling.StartupSchedulingError):
        scheduling.validate_deployment({"startup_barrier": {"publisher_id": 1}})
    monkeypatch.setattr(scheduling, "_http", lambda **_: pytest.fail("static mode IO"))


def test_binding_digest_is_ordered(model):
    digest = scheduling.binding_digest(model.bound)
    assert len(digest) == 64
    swapped = dict(model.bound)
    swapped["capture"], swapped["emission"] = swapped["emission"], swapped["capture"]
    assert digest != scheduling.binding_digest(swapped)


def test_wait_listener_returns_digest_before_binder_and_allows_queued_protected(model, monkeypatch):
    config = scheduling.validate_deployment(model.value)
    page = [_status(config, "listener", model.bound, ident=i) for i in range(1, 4)]
    page[2]["state"] = "pending"
    monkeypatch.setattr(scheduling, "_http", lambda *args, **kwargs: json.dumps(page).encode())
    assert scheduling.wait_for_stage(model.value, "listener", deadline=scheduling.time.monotonic() + 1,
                                     recheck=lambda: None) == scheduling.binding_digest(model.bound)


def test_case_variant_context_or_wrong_creator_target_is_terminal(model, monkeypatch):
    config = scheduling.validate_deployment(model.value)
    for change in (dict(context=scheduling._context(config, "listener").upper()), dict(creator=778),
                   dict(target="https://evil.invalid")):
        row = _status(config, "listener", model.bound, **change)
        monkeypatch.setattr(scheduling, "_http", lambda *args, row=row, **kwargs: json.dumps([row]).encode())
        with pytest.raises(scheduling.StartupSchedulingError):
            scheduling.wait_for_stage(model.value, "listener", deadline=scheduling.time.monotonic() + 1,
                                      recheck=lambda: None)


def test_malformed_or_terminal_status_never_waits(model, monkeypatch):
    config = scheduling.validate_deployment(model.value)
    for state in ("failure", "error"):
        row = _status(config, "listener", model.bound, state=state)
        monkeypatch.setattr(scheduling, "_http", lambda *args, row=row, **kwargs: json.dumps([row]).encode())
        with pytest.raises(scheduling.StartupSchedulingError):
            scheduling.wait_for_stage(model.value, "listener", deadline=scheduling.time.monotonic() + 1,
                                      recheck=lambda: None)


@pytest.mark.parametrize("state", ["failure", "error", "pending"])
def test_newest_matching_status_never_falls_back_to_older_success(model, state):
    config = scheduling.validate_deployment(model.value)
    newest = _status(config, "listener", model.bound, state=state, ident=2, updated="2026-09-17T00:00:02Z")
    older = _status(config, "listener", model.bound, ident=1)
    raw = json.dumps([newest, older]).encode()
    if state == "pending":
        assert scheduling._observe(raw, config, "listener") is None
    else:
        with pytest.raises(scheduling.StartupSchedulingError): scheduling._observe(raw, config, "listener")


@pytest.mark.parametrize("stage,expected", [("listener", 8), ("export", 16)])
def test_valid_absence_has_exact_finite_observation_budget(model, monkeypatch, stage, expected):
    clock, reads, waits, checks = [100.0], [], [], []
    monkeypatch.setattr(scheduling.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(scheduling, "_http", lambda *args, **kwargs: reads.append(kwargs) or b"[]")
    def wait(target, deadline, recheck):
        waits.append(target - clock[0]); clock[0] = target; recheck()
    monkeypatch.setattr(scheduling, "_wait", wait)
    with pytest.raises(scheduling.StartupSchedulingError):
        scheduling.wait_for_stage(model.value, stage, deadline=20000, recheck=lambda: checks.append(1))
    assert len(reads) == expected and len(waits) == expected - 1
    assert all(delay == 10 if stage == "listener" else delay <= 30 for delay in waits)
    assert checks and all(row["method"] == "GET" and "token" not in row for row in reads)


def test_success_cannot_outlive_final_custody_check(model, monkeypatch):
    clock, checked = [100.0], []
    config = scheduling.validate_deployment(model.value)
    row = _status(config, "listener", model.bound)
    monkeypatch.setattr(scheduling.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(scheduling, "_http", lambda *args, **kwargs: json.dumps([row]).encode())
    def check():
        checked.append(1)
        if len(checked) == 2: clock[0] = 200.0
    with pytest.raises(scheduling.StartupSchedulingError):
        scheduling.wait_for_stage(model.value, "listener", deadline=120, recheck=check)


def test_unrelated_statuses_are_absence_but_full_page_without_match_is_terminal(model):
    config = scheduling.validate_deployment(model.value)
    unrelated = _status(config, "listener", model.bound, context="other-check", creator=778)
    unrelated["creator"] = {"id": 778, "login": "github-actions[bot]",
                             "url": identity.API + "/users/github-actions%5Bbot%5D"}
    assert scheduling._observe(json.dumps([unrelated]).encode(), config, "listener") is None
    full = [dict(unrelated, id=index + 1) for index in range(100)]
    with pytest.raises(scheduling.StartupSchedulingError):
        scheduling._observe(json.dumps(full).encode(), config, "listener")


@pytest.mark.parametrize("display", ["✅ Prüfungen bestanden", "", None])
def test_unrelated_unicode_or_empty_display_metadata_is_not_authority(model, display):
    config = scheduling.validate_deployment(model.value)
    unrelated = _status(config, "listener", model.bound, context="anderen Prüfungen", creator=778)
    unrelated.update(description=display, target_url=display)
    desired = _status(config, "listener", model.bound, ident=2)
    assert scheduling._observe(json.dumps([unrelated, desired]).encode(), config, "listener") == scheduling.binding_digest(model.bound)


def test_public_transport_error_is_terminal_without_retry(model, monkeypatch):
    calls = []
    def fail(*args, **kwargs):
        calls.append(1)
        raise scheduling.StartupSchedulingError(scheduling.ERROR)
    monkeypatch.setattr(scheduling, "_http", fail)
    with pytest.raises(scheduling.StartupSchedulingError):
        scheduling.wait_for_stage(model.value, "listener", deadline=scheduling.time.monotonic() + 1,
                                  recheck=lambda: None)
    assert calls == [1]


def test_transport_child_has_hard_timeout_and_output_bound():
    with tempfile.TemporaryDirectory(prefix="startup-test-") as directory:
        with pytest.raises(scheduling.StartupSchedulingError):
            scheduling._run_transport([sys.executable, "-c", "import time; time.sleep(2)"],
                                      b"{}", Path(directory), 0.05, 1024)
        with pytest.raises(scheduling.StartupSchedulingError):
            scheduling._run_transport([sys.executable, "-c", "print('x' * 2048)"],
                                      b"{}", Path(directory), 1, 128)


def test_export_uses_preparation_half_cap_and_one_second_custody_slices(model, monkeypatch):
    config = scheduling.validate_deployment(model.value)
    calls, sleeps = [], []
    row = _status(config, "export", model.bound, state="pending")
    monkeypatch.setattr(scheduling, "_http", lambda *args, **kwargs: calls.append(1) or json.dumps([row]).encode())
    clock = [100.0]
    def sleep(seconds):
        sleeps.append(seconds)
        clock[0] += seconds
    monkeypatch.setattr(scheduling.time, "sleep", sleep)
    monkeypatch.setattr(scheduling.time, "monotonic", lambda: clock[0])
    with pytest.raises(scheduling.StartupSchedulingError):
        scheduling.wait_for_stage(model.value, "export", deadline=130.0, recheck=lambda: None)
    assert len(calls) == 1 and sleeps and all(0 < value <= 1 for value in sleeps)


def test_publish_is_one_authenticated_post_and_never_retries(model, monkeypatch):
    posted, rechecked = [], []
    token = SimpleNamespace(path=Path("/private/status-token"), read=lambda: b"token-value",
                            recheck=lambda: rechecked.append(1))
    owner_value = dict(model.value, status_write_token="/private/status-token")
    config = scheduling.validate_deployment(owner_value, owner=True)
    response = _status(config, "listener", model.bound)
    monkeypatch.setattr(scheduling, "_http", lambda *args, **kwargs: posted.append(kwargs) or json.dumps(response).encode())
    scheduling.publish_stage(owner_value, "listener", model.bound, token,
                             deadline=scheduling.time.monotonic() + 2, recheck=lambda: rechecked.append(1))
    assert len(posted) == 1 and posted[0]["method"] == "POST" and posted[0]["token"] == "token-value"
    assert b"token-value" not in posted[0]["body"] and len(rechecked) >= 3


def test_publish_rejects_wrong_held_path_and_bad_barrier(model):
    wrong = SimpleNamespace(path=Path("/private/other"), read=lambda: b"token", recheck=lambda: None)
    with pytest.raises(scheduling.StartupSchedulingError):
        scheduling.publish_stage(dict(model.value, status_write_token="/private/status-token"), "export", model.bound, wrong,
                                 deadline=scheduling.time.monotonic() + 1, recheck=lambda: None)
    bad = dict(model.value, status_write_token="relative")
    with pytest.raises(scheduling.StartupSchedulingError): scheduling.validate_deployment(bad, owner=True)


@pytest.mark.parametrize("field", ["creator", "context", "digest", "state", "final-expiry"])
def test_post_201_body_and_final_custody_must_match_exact_notice(model, monkeypatch, field):
    value = dict(model.value, status_write_token="/private/status-token")
    config = scheduling.validate_deployment(value, owner=True)
    row = _status(config, "listener", model.bound)
    if field == "creator": row["creator"]["id"] = 999
    elif field == "context": row["context"] = "unrelated"
    elif field == "digest": row["description"] = scheduling._description("0" * 64)
    elif field == "state": row["state"] = "pending"
    posted, clock = [], [100.0]
    monkeypatch.setattr(scheduling.time, "monotonic", lambda: clock[0])
    def request(*args, **kwargs):
        posted.append(True)
        return json.dumps(row).encode()
    monkeypatch.setattr(scheduling, "_http", request)
    def check():
        if posted and field == "final-expiry": clock[0] = 200.0
    token = SimpleNamespace(path=Path(value["status_write_token"]), read=lambda: b"test-only", recheck=lambda: None)
    with pytest.raises(scheduling.StartupSchedulingError):
        scheduling.publish_stage(value, "listener", model.bound, token, deadline=120, recheck=check)
    assert posted == [True]
