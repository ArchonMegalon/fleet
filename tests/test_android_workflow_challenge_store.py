"""Real SQLite/files/processes + real test-key RS256, modeled GitHub replies.

No token is GitHub-issued; no deployed controller, physical durability, artifact
emission, container custody, signing or authorization is claimed by these tests.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
import ast
import base64
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import threading
import time
import traceback
from types import SimpleNamespace

from cryptography.hazmat.primitives.asymmetric import rsa
import jwt
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import android_workflow_challenge_store as journal
from scripts import android_workflow_identity as identity

PINS = {"controller_id": "test.controller", "database_id": "a" * 64}


def key_of(policy):
    return hashlib.sha256(policy.audience.encode()).hexdigest()


def template():
    return identity.WorkflowJobPolicy(repository="example/repo", repository_id="123", repository_owner="example",
        repository_owner_id="456", subject="repo:example/repo:environment:protected", sha="b" * 40,
        ref="refs/heads/main", workflow_ref="example/repo/.github/workflows/build.yml@refs/heads/main",
        workflow_sha="b" * 40, run_id="1234", run_attempt="2", check_run_id="909", environment="protected",
        event_name="workflow_dispatch", runner_environment="github-hosted", run_status="in_progress",
        run_conclusion=None, job_status="in_progress", job_conclusion=None, transaction_id="c" * 64,
        challenge_nonce="d" * 64, challenge_issued_at=1, challenge_expires_at=2)


def self_reference(policy):
    return replace(policy, job_workflow_ref=policy.workflow_ref, job_workflow_sha=policy.workflow_sha)


@pytest.fixture(scope="module")
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def store(tmp_path):
    return journal.SQLiteWorkflowChallengeStore.create(tmp_path / "private.sqlite", **PINS)


def token_for(policy, key, **changes):
    now = int(time.time())
    value = {"iss": identity.ISSUER, "sub": policy.subject, "aud": policy.audience,
        "repository": policy.repository, "repository_id": policy.repository_id,
        "repository_owner": policy.repository_owner, "repository_owner_id": policy.repository_owner_id,
        "sha": policy.sha, "ref": policy.ref, "workflow_ref": policy.workflow_ref, "workflow_sha": policy.workflow_sha,
        "run_id": policy.run_id, "run_attempt": policy.run_attempt, "check_run_id": policy.check_run_id,
        "environment": policy.environment, "event_name": policy.event_name, "runner_environment": policy.runner_environment,
        "repository_visibility": "public", "iat": now, "nbf": now, "exp": now + 300, "jti": "PRIVATE-TEST-JTI"}
    for name in ("job_workflow_ref", "job_workflow_sha"):
        if getattr(policy, name) is not None:
            value[name] = getattr(policy, name)
    value.update(changes)
    return jwt.encode(value, key, algorithm="RS256", headers={"kid": "test-only"})


def reply_bytes(key, policy, *, job_id=707):
    b64 = lambda value: base64.urlsafe_b64encode(value).decode().rstrip("=")
    numbers = key.public_key().public_numbers()
    api = identity.API + "/repos/" + policy.repository
    run = api + "/actions/runs/" + policy.run_id
    attempt = run + "/attempts/" + policy.run_attempt
    replies = {identity.JWKS_URL: {"keys": [{"kid": "test-only", "kty": "RSA", "alg": "RS256", "use": "sig",
        "n": b64(numbers.n.to_bytes(256, "big")), "e": "AQAB"}]},
        attempt: {"id": int(policy.run_id), "run_attempt": int(policy.run_attempt), "head_sha": policy.sha,
            "event": policy.event_name, "status": policy.run_status, "conclusion": policy.run_conclusion,
            "url": run, "html_url": "https://github.com/" + policy.repository + "/actions/runs/" + policy.run_id,
            "path": ".github/workflows/build.yml", "head_commit": {"message": "Actual fixture\nwith body"},
            "repository": {"id": int(policy.repository_id), "full_name": policy.repository, "private": False,
                "owner": {"id": int(policy.repository_owner_id), "login": policy.repository_owner}}},
        attempt + "/jobs?per_page=100&page=1": {"total_count": 1, "jobs": [{"id": job_id,
            "run_id": int(policy.run_id), "run_url": run, "url": api + "/actions/jobs/" + str(job_id), "head_sha": policy.sha,
            "check_run_url": api + "/check-runs/" + policy.check_run_id,
            "status": policy.job_status, "conclusion": policy.job_conclusion}]}}
    return {url: json.dumps(value).encode() for url, value in replies.items()}


def serve(monkeypatch, key, policy, *, job_id=707):
    replies = reply_bytes(key, policy, job_id=job_id)
    seen = []
    def fetch(url, deadline):
        seen.append(url)
        return replies[url]
    monkeypatch.setattr(identity, "_fetch", fetch)
    return seen


def reopen(store, **changes):
    return journal.SQLiteWorkflowChallengeStore(store._path, **(PINS | changes))


def test_real_authentication_commits_only_existing_identity_and_no_token_or_jti(store, signing_key, monkeypatch):
    policy = store.issue(template())
    assert type(policy) is identity.WorkflowJobPolicy
    assert policy.challenge_nonce != template().challenge_nonce
    assert len(policy.challenge_nonce) == 64 and policy.challenge_issued_at > 1
    assert policy.challenge_expires_at - policy.challenge_issued_at == 300
    seen = serve(monkeypatch, signing_key, policy)
    token = token_for(policy, signing_key)
    assert store.status(key_of(policy)) == "pending"
    facts = store.authenticate_and_consume(key_of(policy), token)
    assert type(facts) is identity.WorkflowJobIdentity
    assert facts.job_id == 707 and facts.check_run_id == "909" and len(seen) == 3
    assert facts.transaction_id == policy.transaction_id and facts.audience_sha256 == key_of(policy)
    assert reopen(store).status(key_of(policy)) == "consumed"
    raw = store._path.read_bytes()
    assert token.encode() not in raw and b"PRIVATE-TEST-JTI" not in raw
    assert token not in repr(facts) and policy.challenge_nonce not in repr(policy)
    with pytest.raises(journal.ChallengeStoreError, match="consumed"):
        reopen(store).authenticate_and_consume(key_of(policy), token)
    assert len(seen) == 3  # consumed check precedes network/crypto
    with sqlite3.connect(store._path) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone() == ("delete",)
        assert connection.execute("PRAGMA application_id").fetchone() == (journal.APPLICATION_ID,)
        assert connection.execute("SELECT count(*) FROM challenges").fetchone() == (1,)


@pytest.mark.parametrize("change", [{"sha": "e" * 40}, {"environment": "other"}, {"run_status": "completed", "run_conclusion": "success"}, {}])
def test_same_slot_cannot_be_reissued_or_changed_even_after_expiry(store, monkeypatch, change):
    policy = store.issue(template(), lifetime_seconds=1)
    monkeypatch.setattr(journal, "time", SimpleNamespace(time=lambda: policy.challenge_expires_at + 100))
    assert store.status(key_of(policy)) == "expired"
    with pytest.raises(journal.ChallengeStoreError):
        store.issue(replace(template(), **change))


@pytest.mark.parametrize("slot_field,value", [("transaction_id", "e" * 64), ("check_run_id", "910"), ("run_attempt", "3")])
def test_distinct_controller_admitted_slots_have_independent_random_challenges(store, slot_field, value):
    first = store.issue(template())
    second = store.issue(replace(template(), **{slot_field: value}))
    assert first.audience != second.audience
    assert store.status(key_of(first)) == store.status(key_of(second)) == "pending"


@pytest.mark.parametrize("completed", [False, True])
def test_exact_reusable_workflow_and_explicit_job_lifecycle_preserved(store, signing_key, monkeypatch, completed):
    expected = replace(template(), job_workflow_ref="reviewed/roles/.github/workflows/builder.yml@" + "e" * 40,
        job_workflow_sha="e" * 40, job_status="completed" if completed else "in_progress",
        job_conclusion="success" if completed else None)
    policy = store.issue(expected)
    for name, value in asdict(expected).items():
        if not name.startswith("challenge_"):
            assert getattr(policy, name) == value
    serve(monkeypatch, signing_key, policy)
    facts = store.authenticate_and_consume(key_of(policy), token_for(policy, signing_key))
    assert facts.job_workflow_ref == expected.job_workflow_ref
    assert facts.job_workflow_sha == expected.job_workflow_sha
    assert facts.job_status == expected.job_status


@pytest.mark.parametrize("job_id", [707, 909], ids=["distinct-job-id", "equal-numeric-job-id"])
def test_explicit_direct_self_reference_persists_exact_policy_and_identity(store, signing_key, monkeypatch, job_id):
    policy = store.issue(self_reference(template()))
    seen = serve(monkeypatch, signing_key, policy, job_id=job_id)
    token = token_for(policy, signing_key)
    facts = store.authenticate_and_consume(key_of(policy), token)
    assert facts.job_id == job_id and facts.check_run_id == "909"
    reopened = reopen(store)
    assert reopened.status(key_of(policy)) == "consumed"
    row, persisted_policy = reopened._read(key_of(policy))
    assert persisted_policy == policy
    assert json.loads(row[3]) == asdict(policy)
    assert json.loads(row[9]) == asdict(facts)
    for document in (json.loads(row[3]), json.loads(row[9])):
        assert type(document["job_workflow_ref"]) is str
        assert type(document["job_workflow_sha"]) is str
        assert document["job_workflow_ref"] == policy.workflow_ref
        assert document["job_workflow_sha"] == policy.workflow_sha
    with pytest.raises(journal.ChallengeStoreError, match="consumed"):
        reopened.authenticate_and_consume(key_of(policy), token)
    assert len(seen) == 3  # Replay fails before any additional modeled HTTPS.


@pytest.mark.parametrize("claim_pair", [
    {},
    {"job_workflow_ref": template().workflow_ref},
    {"job_workflow_sha": template().workflow_sha},
    {"job_workflow_ref": "foreign/repo/.github/workflows/build.yml@refs/heads/main",
     "job_workflow_sha": template().workflow_sha},
    {"job_workflow_ref": template().workflow_ref, "job_workflow_sha": "e" * 40},
    {"job_workflow_ref": None, "job_workflow_sha": template().workflow_sha},
    {"job_workflow_ref": template().workflow_ref, "job_workflow_sha": None},
    {"job_workflow_ref": True, "job_workflow_sha": template().workflow_sha},
    {"job_workflow_ref": template().workflow_ref, "job_workflow_sha": 123},
])
def test_explicit_self_reference_rejects_missing_partial_or_wrong_signed_pair_without_consuming(
        store, signing_key, monkeypatch, claim_pair):
    policy = store.issue(self_reference(template()))
    serve(monkeypatch, signing_key, policy)
    no_pair = replace(policy, job_workflow_ref=None, job_workflow_sha=None)
    token = token_for(no_pair, signing_key, **claim_pair)
    with pytest.raises(journal.ChallengeStoreError):
        store.authenticate_and_consume(key_of(policy), token)
    assert reopen(store).status(key_of(policy)) == "pending"


@pytest.mark.parametrize("fields", [("job_workflow_ref",), ("job_workflow_sha",),
                                  ("job_workflow_ref", "job_workflow_sha")])
def test_absent_pair_policy_never_infers_direct_self_reference(store, signing_key, monkeypatch, fields):
    policy = store.issue(template())
    serve(monkeypatch, signing_key, policy)
    direct = self_reference(policy)
    token = token_for(policy, signing_key, **{name: getattr(direct, name) for name in fields})
    with pytest.raises(journal.ChallengeStoreError):
        store.authenticate_and_consume(key_of(policy), token)
    assert reopen(store).status(key_of(policy)) == "pending"


@pytest.mark.parametrize("expired", [False, True])
@pytest.mark.parametrize("direction", ["absent-to-self", "self-to-absent", "self-to-foreign"])
def test_workflow_tuple_changes_cannot_renew_the_same_job_slot(store, monkeypatch, expired, direction):
    initial = template() if direction == "absent-to-self" else self_reference(template())
    policy = store.issue(initial)
    changed = self_reference(template()) if direction == "absent-to-self" else template()
    if direction == "self-to-foreign":
        changed = replace(initial, job_workflow_ref="foreign/repo/.github/workflows/build.yml@refs/heads/main",
                          job_workflow_sha="e" * 40)
    if expired:
        monkeypatch.setattr(journal, "time", SimpleNamespace(time=lambda: policy.challenge_expires_at + 1))
    with pytest.raises(journal.ChallengeStoreError):
        store.issue(changed)
    row, persisted_policy = reopen(store)._read(key_of(policy))
    assert persisted_policy == policy and row[6] is None
    assert store.status(key_of(policy)) == ("expired" if expired else "pending")
    with sqlite3.connect(store._path) as connection:
        assert connection.execute("SELECT count(*) FROM challenges").fetchone() == (1,)


@pytest.mark.parametrize("field,value", [
    ("job_workflow_ref", None), ("job_workflow_ref", True),
    ("job_workflow_ref", "foreign/repo/.github/workflows/build.yml@refs/heads/main"),
    ("job_workflow_sha", None), ("job_workflow_sha", 123), ("job_workflow_sha", "e" * 40),
])
@pytest.mark.parametrize("location", ["returned", "persisted"])
def test_exact_self_reference_result_tuple_rejects_corruption(
        store, signing_key, monkeypatch, field, value, location):
    policy = store.issue(self_reference(template()))
    serve(monkeypatch, signing_key, policy)
    token = token_for(policy, signing_key)
    if location == "returned":
        real = identity.authenticate_workflow_job
        monkeypatch.setattr(identity, "authenticate_workflow_job",
            lambda raw, selected: replace(real(raw, selected), **{field: value}))
        with pytest.raises(journal.ChallengeStoreError, match="authentication-binding"):
            store.authenticate_and_consume(key_of(policy), token)
        assert reopen(store).status(key_of(policy)) == "pending"
    else:
        facts = store.authenticate_and_consume(key_of(policy), token)
        changed = journal._canonical(asdict(replace(facts, **{field: value})))
        # Model corrupted history while restoring the exact schema, so the
        # persisted tuple binding itself must reject, not just schema checks.
        with sqlite3.connect(store._path) as connection:
            connection.execute("DROP TRIGGER challenge_consumption_immutable")
            connection.execute("UPDATE challenges SET identity_bytes=? WHERE challenge_sha=?", (changed, key_of(policy)))
            connection.execute(journal._SCHEMA[-1])
        with pytest.raises(journal.ChallengeStoreError, match="authentication-binding"):
            reopen(store).status(key_of(policy))


def test_quota_never_purges_old_or_consumed_history(tmp_path, monkeypatch):
    store = journal.SQLiteWorkflowChallengeStore.create(tmp_path / "limited.sqlite", **PINS, maximum_challenges=1)
    policy = store.issue(template(), lifetime_seconds=1)
    monkeypatch.setattr(journal, "time", SimpleNamespace(time=lambda: policy.challenge_expires_at + 100000))
    with pytest.raises(journal.ChallengeStoreError, match="quota"):
        store.issue(replace(template(), transaction_id="e" * 64))
    assert store.status(key_of(policy)) == "expired"
    with pytest.raises(journal.ChallengeStoreError):
        reopen(store)


@pytest.mark.parametrize("change", [{"aud": "wrong"}, {"repository_id": "999"}, {"check_run_id": "707"},
    {"run_attempt": "3"}, {"sha": "f" * 40}, {"exp": 1}, {"jti": ""}])
def test_invalid_real_signed_claims_never_consume(store, signing_key, monkeypatch, change):
    policy = store.issue(template())
    serve(monkeypatch, signing_key, policy)
    with pytest.raises(journal.ChallengeStoreError):
        store.authenticate_and_consume(key_of(policy), token_for(policy, signing_key, **change))
    assert store.status(key_of(policy)) == "pending"


def test_bad_real_signature_then_valid_signature(store, signing_key, monkeypatch):
    policy = store.issue(template())
    serve(monkeypatch, signing_key, policy)
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(journal.ChallengeStoreError):
        store.authenticate_and_consume(key_of(policy), token_for(policy, other))
    assert store.status(key_of(policy)) == "pending"
    store.authenticate_and_consume(key_of(policy), token_for(policy, signing_key))


@pytest.mark.parametrize("value", [None, 1, True, "", "not-a-jwt", "PRIVATE-BEARER\n"])
def test_invalid_tokens_and_errors_do_not_echo_token_or_exception_context(store, value):
    policy = store.issue(template())
    try:
        store.authenticate_and_consume(key_of(policy), value)
    except journal.ChallengeStoreError as error:
        assert error.__context__ is None
        assert "PRIVATE-BEARER" not in "".join(traceback.format_exception(error))
    else:
        pytest.fail("invalid bearer admitted")
    assert store.status(key_of(policy)) == "pending"


@pytest.mark.parametrize("field,value", [("repository", "other/repo"), ("repository_id", "999"),
    ("source_sha", "f" * 40), ("workflow_sha", "f" * 40), ("run_attempt", "3"),
    ("check_run_id", "707"), ("job_id", True), ("environment", "other"), ("transaction_id", "f" * 64),
    ("audience_sha256", "f" * 64), ("token_sha256", "f" * 64), ("token_identifier_sha256", "bad"),
    ("valid_until", 1), ("checked_at", True), ("pyjwt_version", "2.12.1")])
def test_exact_result_binding_defends_against_corrupted_trusted_dependency_result(store, signing_key, monkeypatch, field, value):
    # Still executes real RS256 first. This is defense in depth, not an auth seam.
    policy = store.issue(template())
    serve(monkeypatch, signing_key, policy)
    real = identity.authenticate_workflow_job
    monkeypatch.setattr(identity, "authenticate_workflow_job", lambda token, p: replace(real(token, p), **{field: value}))
    with pytest.raises(journal.ChallengeStoreError):
        store.authenticate_and_consume(key_of(policy), token_for(policy, signing_key))
    assert store.status(key_of(policy)) == "pending"


def test_reused_raw_jti_cannot_authenticate_second_challenge(store, signing_key, monkeypatch):
    first = store.issue(template())
    serve(monkeypatch, signing_key, first)
    store.authenticate_and_consume(key_of(first), token_for(first, signing_key))
    second = store.issue(replace(template(), check_run_id="910"))
    serve(monkeypatch, signing_key, second)
    with pytest.raises(journal.ChallengeStoreError):
        store.authenticate_and_consume(key_of(second), token_for(second, signing_key))
    assert store.status(key_of(second)) == "pending"


def test_failure_after_commit_is_consumed_and_status_never_returns_identity(store, signing_key, monkeypatch):
    policy = store.issue(template())
    serve(monkeypatch, signing_key, policy)
    token = token_for(policy, signing_key)
    def lost_response(_):
        raise OSError("PRIVATE-BEARER-response-lost")
    monkeypatch.setattr(journal, "_sync_directory", lost_response)
    with pytest.raises(journal.ChallengeStoreError) as raised:
        store.authenticate_and_consume(key_of(policy), token)
    assert raised.value.__context__ is None
    assert reopen(store).status(key_of(policy)) == "consumed"
    with pytest.raises(journal.ChallengeStoreError):
        reopen(store).authenticate_and_consume(key_of(policy), token)


def test_expiry_during_postcommit_sync_never_returns_stale_identity(store, signing_key, monkeypatch):
    policy = store.issue(template())
    serve(monkeypatch, signing_key, policy)
    token = token_for(policy, signing_key)
    real_sync = journal._sync_directory
    def sync_then_expire(path):
        real_sync(path)
        monkeypatch.setattr(journal, "time", SimpleNamespace(time=lambda: policy.challenge_expires_at))
    monkeypatch.setattr(journal, "_sync_directory", sync_then_expire)
    with pytest.raises(journal.ChallengeStoreError):
        store.authenticate_and_consume(key_of(policy), token)
    assert reopen(store).status(key_of(policy)) == "consumed"
    with pytest.raises(journal.ChallengeStoreError):
        reopen(store).authenticate_and_consume(key_of(policy), token)


def _process_auth(path, challenge, token, replies, output, barrier=None):
    # Fresh process + fresh connection; only HTTPS replies are modeled.
    identity._fetch = lambda url, deadline: replies[url]
    try:
        store = journal.SQLiteWorkflowChallengeStore(Path(path), **PINS)
        if barrier is not None:
            barrier.wait(timeout=20)
        facts = store.authenticate_and_consume(challenge, token)
        output.put(("ok", facts.job_id))
    except journal.ChallengeStoreError:
        output.put(("rejected", None))


def test_actual_process_restart_and_concurrent_consumption_have_one_winner(store, signing_key):
    policy = store.issue(template())
    token = token_for(policy, signing_key)
    context = multiprocessing.get_context("spawn")
    output, barrier = context.Queue(), context.Barrier(3)
    arguments = (str(store._path), key_of(policy), token, reply_bytes(signing_key, policy), output)
    workers = [context.Process(target=_process_auth, args=arguments + (barrier,)) for _ in range(2)]
    try:
        for worker in workers: worker.start()
        barrier.wait(timeout=20)
        observed = [output.get(timeout=20) for _ in workers]
        assert sorted(observed) == [("ok", 707), ("rejected", None)]
        for worker in workers:
            worker.join(timeout=20)
            assert worker.exitcode == 0
        # A third newly spawned interpreter cannot replay the already committed token.
        replay = context.Process(target=_process_auth, args=arguments)
        workers.append(replay)
        replay.start()
        assert output.get(timeout=20) == ("rejected", None)
        replay.join(timeout=20)
        assert replay.exitcode == 0
    finally:
        for worker in workers:
            if worker.is_alive(): worker.kill()
            worker.join(timeout=5)
        output.close()
        output.join_thread()
    assert store.status(key_of(policy)) == "consumed"


def test_fresh_expiry_is_checked_after_actual_sqlite_writer_wait(store, signing_key, monkeypatch):
    policy = store.issue(template(), lifetime_seconds=5)
    serve(monkeypatch, signing_key, policy)
    token = token_for(policy, signing_key)
    waiting = threading.Event()
    real_connect = store._connection
    def connect():
        connection = real_connect()
        connection.set_trace_callback(lambda sql: waiting.set() if sql == "BEGIN IMMEDIATE" else None)
        return connection
    monkeypatch.setattr(store, "_connection", connect)
    with sqlite3.connect(store._path, isolation_level=None) as blocker, ThreadPoolExecutor(max_workers=1) as pool:
        blocker.execute("BEGIN IMMEDIATE")
        future = pool.submit(store.authenticate_and_consume, key_of(policy), token)
        try:
            assert waiting.wait(timeout=10)
            monkeypatch.setattr(journal, "time", SimpleNamespace(time=lambda: policy.challenge_expires_at))
        finally:
            blocker.rollback()
        with pytest.raises(journal.ChallengeStoreError):
            future.result(timeout=10)
    assert store.status(key_of(policy)) == "expired"


def test_schema_drift_during_real_authentication_prevents_consume(store, signing_key, monkeypatch):
    policy = store.issue(template())
    replies = reply_bytes(signing_key, policy)
    def fetch(url, deadline):
        if "/jobs?" in url:
            with sqlite3.connect(store._path) as connection:
                connection.execute("CREATE TABLE unrelated (value TEXT)")
        return replies[url]
    monkeypatch.setattr(identity, "_fetch", fetch)
    with pytest.raises(journal.ChallengeStoreError, match="schema"):
        store.authenticate_and_consume(key_of(policy), token_for(policy, signing_key))
    with sqlite3.connect(store._path) as connection:
        assert connection.execute("SELECT consumed_at FROM challenges").fetchone() == (None,)


@pytest.mark.parametrize("pins", [{"controller_id": "other.controller"}, {"database_id": "e" * 64}, {"maximum_challenges": 7}])
def test_existing_database_requires_exact_external_identity_pins(store, pins):
    with pytest.raises(journal.ChallengeStoreError): reopen(store, **pins)


@pytest.mark.parametrize("pins", [{"controller_id": ""}, {"controller_id": True}, {"database_id": "A" * 64},
    {"database_id": None}, {"maximum_challenges": 0}, {"maximum_challenges": True},
    {"maximum_challenges": 4097}, {"maximum_challenges": 1.0}])
def test_invalid_store_configuration_never_creates_file(tmp_path, pins):
    path = tmp_path / "missing.sqlite"
    with pytest.raises(journal.ChallengeStoreError):
        journal.SQLiteWorkflowChallengeStore.create(path, **(PINS | pins))
    assert not path.exists()


@pytest.mark.parametrize("lifetime", [0, -1, 601, True, 1.0, "300", None])
def test_invalid_lifetimes_do_not_issue(store, lifetime):
    with pytest.raises(journal.ChallengeStoreError): store.issue(template(), lifetime_seconds=lifetime)
    with sqlite3.connect(store._path) as connection:
        assert connection.execute("SELECT count(*) FROM challenges").fetchone() == (0,)


@pytest.mark.parametrize("value", [None, {}, {"repository_id": "123"}, True, "candidate-policy"])
def test_candidate_shapes_cannot_replace_controller_policy_type(store, value):
    with pytest.raises(journal.ChallengeStoreError): store.issue(value)
    with sqlite3.connect(store._path) as connection:
        assert connection.execute("SELECT count(*) FROM challenges").fetchone() == (0,)


def test_lost_issuance_response_does_not_allow_new_nonce_for_same_slot(store, monkeypatch):
    def unavailable(_):
        raise OSError("sync acknowledgment unavailable")
    monkeypatch.setattr(journal, "_sync_directory", unavailable)
    with pytest.raises(journal.ChallengeStoreError): store.issue(template())
    with sqlite3.connect(store._path) as connection:
        key = connection.execute("SELECT challenge_sha FROM challenges").fetchone()[0]
    assert reopen(store).status(key) == "pending"
    with pytest.raises(journal.ChallengeStoreError): reopen(store).issue(template())


@pytest.mark.parametrize("existing", [b"", b"not a database", b"SQLite format 3\x00garbage"])
def test_existing_unknown_database_is_never_reset(tmp_path, existing):
    path = tmp_path / "unknown.sqlite"
    path.write_bytes(existing)
    path.chmod(0o600)
    with pytest.raises(journal.ChallengeStoreError): journal.SQLiteWorkflowChallengeStore(path, **PINS)
    with pytest.raises(journal.ChallengeStoreError): journal.SQLiteWorkflowChallengeStore.create(path, **PINS)
    assert path.read_bytes() == existing


def test_missing_open_never_creates_and_failed_creation_preserves_file(tmp_path, monkeypatch):
    path = tmp_path / "missing.sqlite"
    with pytest.raises(journal.ChallengeStoreError): journal.SQLiteWorkflowChallengeStore(path, **PINS)
    assert not path.exists()
    monkeypatch.setattr(journal.SQLiteWorkflowChallengeStore, "_open", lambda p: (_ for _ in ()).throw(sqlite3.OperationalError("private")))
    with pytest.raises(journal.ChallengeStoreError): journal.SQLiteWorkflowChallengeStore.create(path, **PINS)
    assert path.is_file() and path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("mutation", ["symlink", "hardlink", "replace", "mode", "parent-mode", "parent-link", "wal", "shm", "journal-link"])
def test_real_filesystem_custody_changes_fail_closed(store, tmp_path, mutation):
    policy = store.issue(template())
    path = store._path
    if mutation == "symlink":
        moved = tmp_path / "moved.sqlite"
        path.rename(moved)
        path.symlink_to(moved)
    elif mutation == "hardlink": os.link(path, tmp_path / "alias")
    elif mutation == "replace":
        replacement = tmp_path / "replacement"
        shutil.copyfile(path, replacement)
        replacement.chmod(0o600)
        replacement.replace(path)
    elif mutation == "mode": path.chmod(0o640)
    elif mutation == "parent-mode": tmp_path.chmod(0o770)
    elif mutation == "parent-link":
        alias = tmp_path / "alias-dir"
        alias.symlink_to(tmp_path, target_is_directory=True)
        with pytest.raises(journal.ChallengeStoreError): journal.SQLiteWorkflowChallengeStore(alias / path.name, **PINS)
        return
    elif mutation in {"wal", "shm"}: Path(str(path) + "-" + mutation).write_bytes(b"")
    else: Path(str(path) + "-journal").symlink_to(path)
    try:
        with pytest.raises(journal.ChallengeStoreError): store.status(key_of(policy))
    finally:
        if mutation == "parent-mode": tmp_path.chmod(0o700)


@pytest.mark.parametrize("statement", ["PRAGMA application_id=1", "PRAGMA user_version=2",
    "CREATE TABLE extra (value TEXT)", "CREATE TABLE sqliteXhidden (value TEXT)",
    "DROP TRIGGER challenge_no_delete", "CREATE INDEX extra ON challenges(expires_at)"])
def test_actual_schema_and_application_identity_tampering_rejected(store, statement):
    policy = store.issue(template())
    with sqlite3.connect(store._path) as connection: connection.execute(statement)
    with pytest.raises(journal.ChallengeStoreError): store.status(key_of(policy))
    with pytest.raises(journal.ChallengeStoreError): reopen(store)


def test_unbounded_identity_view_rejected_by_physical_schema_before_execution(tmp_path):
    path = tmp_path / "hostile.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute(f"PRAGMA application_id={journal.APPLICATION_ID}")
        connection.execute(f"PRAGMA user_version={journal.SCHEMA_VERSION}")
        connection.execute("""CREATE VIEW store_identity AS WITH RECURSIVE endless(x) AS
            (VALUES(1) UNION ALL SELECT x+1 FROM endless) SELECT x FROM endless""")
    path.chmod(0o600)
    with pytest.raises(journal.ChallengeStoreError, match="schema"):
        journal.SQLiteWorkflowChallengeStore(path, **PINS)


def test_actual_sqlite_vm_progress_budget_interrupts_unbounded_work(store):
    connection = store._connection()
    try:
        with pytest.raises(sqlite3.OperationalError, match="interrupted"):
            connection.execute("""WITH RECURSIVE endless(x) AS (VALUES(1) UNION ALL
                SELECT x+1 FROM endless) SELECT sum(x) FROM endless""").fetchone()
    finally:
        connection.close()


@pytest.mark.parametrize("mutation", ["policy", "digest", "slot", "expiry"])
def test_policy_rows_are_bound_even_if_owner_restores_exact_schema(store, mutation):
    policy = store.issue(template())
    with sqlite3.connect(store._path) as connection:
        connection.execute("DROP TRIGGER challenge_identity_immutable")
        connection.execute("DROP TRIGGER challenge_consumption_immutable")
        field, value = {"policy": ("policy_bytes", b"{}"), "digest": ("policy_sha", "e" * 64),
                        "slot": ("slot_sha", "e" * 64), "expiry": ("expires_at", 1)}[mutation]
        connection.execute("UPDATE challenges SET " + field + "=?", (value,))
        for statement in journal._SCHEMA[-2:]: connection.execute(statement)
    with pytest.raises(journal.ChallengeStoreError): store.status(key_of(policy))


def test_permanent_history_triggers_prohibit_delete_and_rewrite(store, signing_key, monkeypatch):
    policy = store.issue(template())
    serve(monkeypatch, signing_key, policy)
    store.authenticate_and_consume(key_of(policy), token_for(policy, signing_key))
    with sqlite3.connect(store._path) as connection:
        for sql in ("DELETE FROM challenges", "UPDATE challenges SET consumed_at=NULL",
                    "UPDATE challenges SET expires_at=expires_at+1", "DELETE FROM store_identity"):
            with pytest.raises(sqlite3.IntegrityError): connection.execute(sql)


def test_status_after_expiry_is_diagnostic_consumed_not_renewed(store, signing_key, monkeypatch):
    policy = store.issue(template())
    serve(monkeypatch, signing_key, policy)
    store.authenticate_and_consume(key_of(policy), token_for(policy, signing_key))
    monkeypatch.setattr(journal, "time", SimpleNamespace(time=lambda: policy.challenge_expires_at + 9999))
    assert reopen(store).status(key_of(policy)) == "consumed"
    with pytest.raises(journal.ChallengeStoreError): store.issue(template())


def test_no_capability_signer_runtime_or_ledger_imports_and_no_auth_callback():
    tree = ast.parse(Path(journal.__file__).read_text())
    imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert imports == ["__future__", "dataclasses", "pathlib", "urllib.parse", "scripts"]
    assert next(node for node in tree.body if isinstance(node, ast.ImportFrom) and node.module == "scripts").names[0].name == "android_workflow_identity"
    function = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "authenticate_and_consume")
    assert [arg.arg for arg in function.args.args] == ["self", "challenge_sha256", "token"]
    assert not function.args.kwonlyargs
