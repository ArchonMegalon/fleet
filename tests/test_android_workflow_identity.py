"""Real RS256 under TEST-ONLY keys, modeled GitHub API/HTTPS replies.

No fixture is a GitHub-issued token, Fleet job, custody or artifact-to-job proof.
Origin composition uses an explicitly noncryptographic gh process stand-in;
existing genuine gh tests qualify that separate boundary. No network activation.
"""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
from email.message import Message
import base64
import hashlib
import json
import io
import os
from pathlib import Path
import ssl
import sys
import time
import traceback
from types import SimpleNamespace
import urllib.request

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
import jwt
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import android_workflow_identity as identity
from scripts import android_artifact_origin as origin

NOW = int(time.time())
SECRET = "THIS-IS-A-TEST-BEARER-NOT-A-REAL-TOKEN"
AUDIENCE = "urn:chummer:fleet:workflow-job:" + "c"*64 + ":" + "d"*64
ATTEMPT = "https://api.github.com/repos/example/repo/actions/runs/1234/attempts/2"
JOBS = ATTEMPT + "/jobs?per_page=100&page=1"


def b64(raw):
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def raw(value):
    return json.dumps(value, separators=(",", ":")).encode()


@pytest.fixture(scope="module")
def keys():
    return tuple(rsa.generate_private_key(public_exponent=65537, key_size=2048) for _ in range(2))


@pytest.fixture
def policy():
    return identity.WorkflowJobPolicy(repository="example/repo", repository_id="123", repository_owner="example",
        repository_owner_id="456", subject="repo:example/repo:environment:protected", sha="a"*40,
        ref="refs/heads/main", workflow_ref="example/repo/.github/workflows/build.yml@refs/heads/main",
        workflow_sha="a"*40, run_id="1234", run_attempt="2", check_run_id="909", environment="protected",
        event_name="workflow_dispatch", runner_environment="github-hosted", run_status="in_progress",
        run_conclusion=None, job_status="in_progress", job_conclusion=None, transaction_id="c"*64,
        challenge_nonce="d"*64, challenge_issued_at=NOW-2, challenge_expires_at=NOW+300)


def claims():
    return {"iss": "https://token.actions.githubusercontent.com", "sub": "repo:example/repo:environment:protected",
        "aud": AUDIENCE, "repository": "example/repo", "repository_id": "123", "repository_owner": "example",
        "repository_owner_id": "456", "sha": "a"*40, "ref": "refs/heads/main",
        "workflow_ref": "example/repo/.github/workflows/build.yml@refs/heads/main", "workflow_sha": "a"*40,
        "run_id": "1234", "run_attempt": "2", "check_run_id": "909", "environment": "protected",
        "event_name": "workflow_dispatch", "runner_environment": "github-hosted", "repository_visibility": "public",
        "iat": NOW, "nbf": NOW, "exp": NOW+300, "jti": "test-only-token-id"}


def jwks(key):
    numbers = key.public_key().public_numbers()
    return {"keys": [{"kid": "test-only", "kty": "RSA", "use": "sig", "alg": "RS256",
        "n": b64(numbers.n.to_bytes(256, "big")), "e": "AQAB"}]}


def sign(key, value=None, header=None, raw_header=None, raw_claims=None):
    # Sign even malformed literal JSON independently of PyJWT's encoder.
    encoded = b64(raw(header or {"alg": "RS256", "kid": "test-only", "typ": "JWT"}) if raw_header is None else raw_header)
    encoded += "." + b64(raw(claims() if value is None else value) if raw_claims is None else raw_claims)
    signature = key.sign(encoded.encode(), padding.PKCS1v15(), hashes.SHA256())
    return encoded + "." + b64(signature)


def api_attempt():
    # Realistic non-identity metadata, including multiline commit text.
    return {"id": 1234, "run_attempt": 2, "run_number": 41, "workflow_id": 111, "node_id": "WFR_example",
        "name": "Public workflow name", "display_title": "Merge reviewed changes", "head_branch": "main",
        "head_sha": "a"*40, "event": "workflow_dispatch", "status": "in_progress", "conclusion": None,
        "path": ".github/workflows/build.yml", "url": "https://api.github.com/repos/example/repo/actions/runs/1234",
        "html_url": "https://github.com/example/repo/actions/runs/1234", "pull_requests": [],
        "created_at": "2026-09-13T10:00:00Z", "updated_at": "2026-09-13T10:01:00Z",
        "head_commit": {"id": "a"*40, "message": "Merge pull request #58\n\nReviewed change\r\n\twith body",
                        "author": {"name": "Example", "email": "noreply@example.invalid"}},
        "repository": {"id": 123, "full_name": "example/repo", "name": "repo", "private": False,
            "owner": {"id": 456, "login": "example", "type": "Organization"}}}


def api_jobs():
    return {"total_count": 1, "jobs": [{"id": 707, "run_id": 1234,
        "run_url": "https://api.github.com/repos/example/repo/actions/runs/1234", "head_sha": "a"*40,
        "url": "https://api.github.com/repos/example/repo/actions/jobs/707",
        "html_url": "https://github.com/example/repo/actions/runs/1234/job/707",
        "check_run_url": "https://api.github.com/repos/example/repo/check-runs/909", "name": "display name not role authority",
        "status": "in_progress", "conclusion": None, "steps": [], "runner_name": "GitHub Actions"}]}


def replies(monkeypatch, key, *, key_data=None, attempt=None, jobs=None, callback=None):
    values = {identity.JWKS_URL: jwks(key) if key_data is None else key_data,
              ATTEMPT: api_attempt() if attempt is None else attempt, JOBS: api_jobs() if jobs is None else jobs}
    seen = []
    def fetch(url, deadline):
        seen.append((url, deadline))
        assert url in values and SECRET not in url
        if callback: callback(url)
        result = values[url]
        return result if type(result) is bytes else raw(result)
    monkeypatch.setattr(identity, "_fetch", fetch)
    return seen


def test_genuine_rs256_maps_distinct_job_id_and_detaches(policy, keys, monkeypatch):
    seen = replies(monkeypatch, keys[0])
    token = sign(keys[0])
    facts = identity.authenticate_workflow_job(token, policy)
    assert facts.job_id == 707 and facts.check_run_id == "909"
    assert [url for url, _ in seen] == [identity.JWKS_URL, ATTEMPT, JOBS]
    assert len({deadline for _, deadline in seen}) == 1
    assert facts.token_sha256 == hashlib.sha256(token.encode()).hexdigest()
    assert facts.audience_sha256 == hashlib.sha256(AUDIENCE.encode()).hexdigest()
    assert facts.valid_until == min(NOW+300, policy.challenge_expires_at)
    assert token not in repr(facts) and AUDIENCE not in repr(facts) and policy.challenge_nonce not in repr(policy)
    assert facts.pyjwt_version == jwt.__version__
    with pytest.raises(FrozenInstanceError): facts.job_id = 909


def test_actual_pyjwt_uses_raw_rsa_key_and_one_algorithm(policy, keys, monkeypatch):
    replies(monkeypatch, keys[0])
    actual = jwt.decode
    def decode(*args, **kwargs):
        assert isinstance(kwargs["key"], rsa.RSAPublicKey)
        assert kwargs["algorithms"] == ["RS256"] and kwargs["options"]["strict_aud"] is True
        return actual(*args, **kwargs)
    monkeypatch.setattr(identity.jwt, "decode", decode)
    assert identity.authenticate_workflow_job(sign(keys[0]), policy).job_id == 707


@pytest.mark.parametrize("kind", ["other-key", "changed-body", "changed-signature"])
def test_invalid_real_signature_never_reaches_run_api(policy, keys, monkeypatch, kind):
    seen = replies(monkeypatch, keys[0])
    token = sign(keys[1] if kind == "other-key" else keys[0])
    parts = token.split(".")
    if kind == "changed-body": parts[1] = b64(raw(dict(claims(), jti="other")))
    if kind == "changed-signature": parts[2] = b64(b"\x00"*256)
    with pytest.raises(identity.WorkflowIdentityError, match="jwt-signature-or-validity"):
        identity.authenticate_workflow_job(".".join(parts), policy)
    assert [row[0] for row in seen] == [identity.JWKS_URL]


@pytest.mark.parametrize("field,value", [("alg", "none"), ("alg", "HS256"), ("alg", "PS256"),
    ("alg", "RS512"), ("typ", "not-JWT"), ("kid", ""), ("kid", True), ("jku", "https://evil.invalid"),
    ("x5u", "https://evil.invalid"), ("jwk", {}), ("crit", ["b64"]), ("b64", False)])
def test_header_confusion_rejects_before_network(policy, keys, monkeypatch, field, value):
    header = {"alg": "RS256", "typ": "JWT", "kid": "test-only", field: value}
    monkeypatch.setattr(identity, "_fetch", lambda *_: pytest.fail("must reject before transport"))
    with pytest.raises(identity.WorkflowIdentityError):
        identity.authenticate_workflow_job(sign(keys[0], header=header), policy)


@pytest.mark.parametrize("field,value", [("iss", "https://evil.invalid"), ("aud", "https://github.com/example"),
    ("aud", [AUDIENCE]), ("sub", "repo:other/repo:environment:protected"), ("repository", "other/repo"),
    ("repository_id", 123), ("repository_id", "124"), ("repository_owner", "other"), ("repository_owner_id", "457"),
    ("sha", "b"*40), ("ref", "refs/heads/other"), ("workflow_ref", "example/repo/.github/workflows/other.yml@refs/heads/main"),
    ("workflow_sha", "b"*40), ("run_id", "1235"), ("run_attempt", "1"), ("check_run_id", "707"),
    ("environment", "unprotected"), ("event_name", "pull_request_target"), ("runner_environment", "self-hosted"),
    ("repository_visibility", "private"), ("environment", "protected\n"), ("jti", "")])
def test_exact_signed_claims_cannot_be_replaced(policy, keys, monkeypatch, field, value):
    replies(monkeypatch, keys[0])
    with pytest.raises(identity.WorkflowIdentityError):
        identity.authenticate_workflow_job(sign(keys[0], dict(claims(), **{field: value})), policy)


@pytest.mark.parametrize("field,value", [("iat", True), ("nbf", float(NOW)), ("exp", str(NOW+300)),
    ("exp", NOW-1), ("iat", NOW+60), ("nbf", NOW+60), ("exp", NOW+601), ("iat", NOW-1000), ("nbf", -1)])
def test_token_numeric_date_shape_and_bounds(policy, keys, monkeypatch, field, value):
    replies(monkeypatch, keys[0])
    with pytest.raises(identity.WorkflowIdentityError):
        identity.authenticate_workflow_job(sign(keys[0], dict(claims(), **{field: value})), policy)


@pytest.mark.parametrize("field", list(claims()))
def test_missing_required_claim_rejects(policy, keys, monkeypatch, field):
    replies(monkeypatch, keys[0])
    value = claims()
    del value[field]
    with pytest.raises(identity.WorkflowIdentityError):
        identity.authenticate_workflow_job(sign(keys[0], value), policy)


@pytest.mark.parametrize("header,payload", [
    (b'{"alg":"none","alg":"RS256","typ":"JWT","kid":"test-only"}', None),
    (None, b'{"repository_id":"123","repository_id":"123"}'), (None, b'{"x":NaN}'),
    (None, b'{"x":Infinity}'), (None, b'{"x":1e999}'), (None, b'{"x":"\\ud800"}'),
    (None, b'{"x":' + b'['*40+b'0'+b']'*40+b'}'), (None, b'[]'), (None, b'{}{}'),
    (None, b'{"x":"unescaped\nline"}'),
])
def test_hostile_signed_json_rejects(policy, keys, monkeypatch, header, payload):
    monkeypatch.setattr(identity, "_fetch", lambda *_: pytest.fail("must reject before transport"))
    with pytest.raises(identity.WorkflowIdentityError):
        identity.authenticate_workflow_job(sign(keys[0], raw_header=header, raw_claims=payload), policy)


@pytest.mark.parametrize("value", [None, True, "", "x.y", "x.y.z.a", "x"*32769, "e30=.e30.abc", "e30.e30.aa+"])
def test_token_shape_is_bounded(policy, value):
    with pytest.raises(identity.WorkflowIdentityError): identity.authenticate_workflow_job(value, policy)


@pytest.mark.parametrize("field,value", [("repository", "example/.."), ("repository_owner", "other"),
    ("repository_id", True), ("run_attempt", "01"), ("check_run_id", "0"), ("sha", "a"*39),
    ("ref", "refs/heads/a/../b"), ("workflow_ref", "other/repo/.github/workflows/build.yml@refs/heads/main"),
    ("job_workflow_ref", "example/repo/.github/workflows/reuse.yml@refs/heads/main"),
    ("environment", ""), ("event_name", "pull_request"), ("runner_environment", "unknown"),
    ("job_status", "queued"), ("job_conclusion", "success"), ("run_conclusion", "failure"),
    ("transaction_id", "short"), ("challenge_nonce", "short"), ("challenge_issued_at", True),
    ("challenge_expires_at", NOW-3), ("challenge_expires_at", NOW+700), ("maximum_token_age_seconds", True)])
def test_policy_shapes_are_exact(policy, field, value):
    with pytest.raises(identity.WorkflowIdentityError): replace(policy, **{field: value})


@pytest.mark.parametrize("field,value", [("kty", "oct"), ("alg", "PS256"), ("use", "enc"), ("kid", "missing"),
    ("n", "AQAB"), ("e", "Aw"), ("e", "AAEAAQ"), ("d", "private"), ("jku", "https://evil.invalid"),
    ("key_ops", ["sign"]), ("x5t", "short"), ("x5c", "not-an-array")])
def test_jwks_key_confusion_rejects(policy, keys, monkeypatch, field, value):
    data = jwks(keys[0])
    data["keys"][0][field] = value
    replies(monkeypatch, keys[0], key_data=data)
    with pytest.raises(identity.WorkflowIdentityError): identity.authenticate_workflow_job(sign(keys[0]), policy)


@pytest.mark.parametrize("kind", ["duplicate-kid", "empty", "overflow", "duplicate-json"])
def test_jwks_cardinality_is_closed(policy, keys, monkeypatch, kind):
    data = jwks(keys[0])
    if kind == "duplicate-kid": data["keys"] *= 2
    if kind == "empty": data["keys"] = []
    if kind == "overflow": data["keys"] *= 33
    if kind == "duplicate-json": data = b'{"keys":[],"keys":[]}'
    replies(monkeypatch, keys[0], key_data=data)
    with pytest.raises(identity.WorkflowIdentityError): identity.authenticate_workflow_job(sign(keys[0]), policy)


@pytest.mark.parametrize("field,value", [("id", True), ("id", 1235), ("run_attempt", 1), ("head_sha", "b"*40),
    ("event", "push"), ("status", "completed"), ("conclusion", "success"),
    ("url", "https://evil.invalid"), ("html_url", "https://evil.invalid"), ("path", ".github/workflows/other.yml")])
def test_api_attempt_cannot_replace_signed_context(policy, keys, monkeypatch, field, value):
    data = api_attempt()
    data[field] = value
    replies(monkeypatch, keys[0], attempt=data)
    with pytest.raises(identity.WorkflowIdentityError): identity.authenticate_workflow_job(sign(keys[0]), policy)


@pytest.mark.parametrize("kind", ["repo-id", "private", "owner-id", "owner-name", "missing-repo"])
def test_api_repository_owner_is_independent_exact_binding(policy, keys, monkeypatch, kind):
    data = api_attempt()
    if kind == "repo-id": data["repository"]["id"] = 124
    if kind == "private": data["repository"]["private"] = True
    if kind == "owner-id": data["repository"]["owner"]["id"] = True
    if kind == "owner-name": data["repository"]["owner"]["login"] = "other"
    if kind == "missing-repo": del data["repository"]
    replies(monkeypatch, keys[0], attempt=data)
    with pytest.raises(identity.WorkflowIdentityError): identity.authenticate_workflow_job(sign(keys[0]), policy)


@pytest.mark.parametrize("kind", ["total-bool", "overflow", "truncated", "duplicate-row", "duplicate-check", "missing-check", "no-match"])
def test_jobs_page_membership_and_check_run_are_unique(policy, keys, monkeypatch, kind):
    data = api_jobs()
    if kind == "total-bool": data["total_count"] = True
    if kind == "overflow": data["total_count"] = 101
    if kind == "truncated": data["total_count"] = 2
    if kind == "duplicate-row": data["jobs"] *= 2; data["total_count"] = 2
    if kind == "duplicate-check":
        duplicate = dict(data["jobs"][0], id=708, url="https://api.github.com/repos/example/repo/actions/jobs/708")
        data["jobs"].append(duplicate); data["total_count"] = 2
    if kind == "missing-check": del data["jobs"][0]["check_run_url"]
    if kind == "no-match": data["jobs"][0]["check_run_url"] = "https://api.github.com/repos/example/repo/check-runs/707"
    replies(monkeypatch, keys[0], jobs=data)
    with pytest.raises(identity.WorkflowIdentityError): identity.authenticate_workflow_job(sign(keys[0]), policy)


@pytest.mark.parametrize("field,value", [("run_id", 1235), ("run_id", True), ("run_attempt", 1), ("head_sha", "b"*40),
    ("run_url", "https://evil.invalid"), ("url", "https://evil.invalid"),
    ("check_run_url", "https://api.github.com/repos/example/other/check-runs/909"),
    ("check_run_url", "https://api.github.com/repos/example/repo/check-runs/909?x=1"),
    ("status", "completed"), ("conclusion", "failure")])
def test_job_has_no_name_based_identity_fallback(policy, keys, monkeypatch, field, value):
    data = api_jobs()
    data["jobs"][0][field] = value
    replies(monkeypatch, keys[0], jobs=data)
    with pytest.raises(identity.WorkflowIdentityError): identity.authenticate_workflow_job(sign(keys[0]), policy)


def test_completed_builder_is_distinct_from_live_workflow(policy, keys, monkeypatch):
    data = api_jobs()
    data["jobs"][0].update(status="completed", conclusion="success", name="arbitrary display name")
    replies(monkeypatch, keys[0], jobs=data)
    facts = identity.authenticate_workflow_job(sign(keys[0]), replace(policy, job_status="completed", job_conclusion="success"))
    assert facts.job_status == "completed" and facts.job_id == 707


def test_reusable_workflow_is_separate_signed_identity(policy, keys, monkeypatch):
    reusable = "shared/automation/.github/workflows/build.yml@" + "b"*40
    selected = replace(policy, job_workflow_ref=reusable, job_workflow_sha="b"*40)
    replies(monkeypatch, keys[0])
    token = sign(keys[0], dict(claims(), job_workflow_ref=reusable, job_workflow_sha="b"*40))
    facts = identity.authenticate_workflow_job(token, selected)
    assert facts.workflow_sha == "a"*40 and facts.job_workflow_sha == "b"*40
    with pytest.raises(identity.WorkflowIdentityError): identity.authenticate_workflow_job(token, policy)
    with pytest.raises(identity.WorkflowIdentityError): identity.authenticate_workflow_job(sign(keys[0]), selected)


@pytest.mark.parametrize("point", ["keys", "attempt", "jobs"])
def test_shared_deadline_is_not_reset(policy, keys, monkeypatch, point):
    clock = [0.0]
    monkeypatch.setattr(identity.time, "monotonic", lambda: clock[0])
    target = {"keys": identity.JWKS_URL, "attempt": ATTEMPT, "jobs": JOBS}[point]
    replies(monkeypatch, keys[0], callback=lambda url: clock.__setitem__(0, 21.0) if url == target else None)
    with pytest.raises(identity.WorkflowIdentityError, match="workflow-deadline"):
        identity.authenticate_workflow_job(sign(keys[0]), policy)


def test_final_claim_readmission_detects_expiry_after_api(policy, keys, monkeypatch):
    def expire(url):
        if url == JOBS: monkeypatch.setattr(identity.time, "time", lambda: NOW+301)
    replies(monkeypatch, keys[0], callback=expire)
    with pytest.raises(identity.WorkflowIdentityError, match="jwt-time"):
        identity.authenticate_workflow_job(sign(keys[0]), policy)


@pytest.mark.parametrize("url", ["http://api.github.com/repos/example/repo/actions/runs/1234/attempts/2",
    "https://apiXgithubYcom/repos/example/repo/actions/runs/1234/attempts/2", ATTEMPT+"/jobs?per_page=101&page=1",
    ATTEMPT+"/jobs?per_page=100&page=2", "https://evil.invalid/.well-known/jwks", ATTEMPT+"#fragment"])
def test_transport_rejects_nonfixed_endpoint(url, monkeypatch):
    monkeypatch.setattr(origin, "_run", lambda *_: pytest.fail("no child allowed"))
    with pytest.raises(identity.WorkflowIdentityError): identity._fetch(url, time.monotonic()+20)


def test_fetch_has_only_public_endpoint_and_isolated_constant_helper(monkeypatch):
    seen = []
    def run(command, directory, timeout, out_limit, err_limit):
        seen.append(directory)
        assert command == [sys.executable, "-I", "-c", identity._HTTPS_SCRIPT, identity.JWKS_URL]
        assert directory.is_dir() and directory.parent == Path("/tmp")
        assert 0 < timeout <= 20 and out_limit == 2097152 and err_limit == 1024
        return b'{"keys":[]}'
    monkeypatch.setattr(origin, "_run", run)
    assert identity._fetch(identity.JWKS_URL, time.monotonic()+20) == b'{"keys":[]}'
    assert not seen[0].exists()


def test_actual_helper_process_timeout_is_reaped(monkeypatch):
    # Actual process, but substituted sleep body makes no network requests.
    monkeypatch.setattr(identity, "_HTTPS_SCRIPT", "import time; time.sleep(60)")
    began = time.monotonic()
    with pytest.raises(identity.WorkflowIdentityError, match="workflow-fetch"):
        identity._fetch(identity.JWKS_URL, began+0.15)
    assert time.monotonic()-began < 2


@pytest.mark.parametrize("kind", ["status", "redirect", "duplicate", "oversize-header", "encoding", "pagination", "length", "oversize-body", "truncated"])
def test_constant_https_code_rejects_hostile_modeled_response(monkeypatch, kind):
    reached = []
    response = SimpleNamespace(status=200, headers=Message())
    response.headers["Content-Type"] = "application/json"
    response.headers["Content-Length"] = "2"
    response.geturl = lambda: identity.JWKS_URL
    response.read = lambda limit: b"{}"
    if kind == "status": response.status = 403
    if kind == "redirect": response.geturl = lambda: "https://evil.invalid/"
    if kind == "duplicate": response.headers["Content-Length"] = "2"
    if kind == "oversize-header": response.headers["X-Long"] = "a"*16385
    if kind == "encoding": response.headers["Content-Encoding"] = "gzip"
    if kind == "pagination": response.headers["Link"] = "<https://evil.invalid>; rel=next"
    if kind == "length": response.headers.replace_header("Content-Length", "2097153")
    if kind == "oversize-body": response.read = lambda _: b"a"*2097153
    if kind == "truncated": response.read = lambda _: b"{"
    class Opened:
        def __enter__(self): return response
        def __exit__(self, *_): pass
    def build(*handlers):
        reached.append("build")
        assert handlers[0].proxies == {}
        assert handlers[2]._context.verify_mode == ssl.CERT_REQUIRED and handlers[2]._context.check_hostname
        with pytest.raises(ValueError): handlers[1].redirect_request(None, None, 302, None, None, "https://evil.invalid")
        def open_request(request, timeout):
            assert request.get_method() == "GET" and not request.has_header("Authorization")
            assert request.full_url == identity.JWKS_URL and timeout == 20
            reached.append("request")
            return Opened()
        return SimpleNamespace(open=open_request)
    monkeypatch.setattr(urllib.request, "build_opener", build)
    monkeypatch.setattr(sys, "argv", ["helper", identity.JWKS_URL])
    with pytest.raises(SystemExit) as failure: exec(identity._HTTPS_SCRIPT, {})
    assert failure.value.code == 2
    assert reached == ["build", "request"]


def test_errors_never_disclose_jwt_or_server_content(policy, keys, monkeypatch):
    def fail(*_): raise origin.OriginError(SECRET)
    monkeypatch.setattr(origin, "_run", fail)
    token = sign(keys[0])
    with pytest.raises(identity.WorkflowIdentityError) as failure: identity.authenticate_workflow_job(token, policy)
    rendered = "".join(traceback.format_exception(failure.value))
    assert token not in rendered and SECRET not in rendered and "workflow-fetch" in str(failure.value)


def test_old_pyjwt_rejects_before_network(policy, keys, monkeypatch):
    monkeypatch.setattr(identity.jwt, "__version__", "2.12.1")
    monkeypatch.setattr(identity, "_fetch", lambda *_: pytest.fail("old verifier rejected"))
    with pytest.raises(identity.WorkflowIdentityError, match="workflow-dependency"):
        identity.authenticate_workflow_job(sign(keys[0]), policy)


def origin_policy(policy):
    return origin.OriginPolicy(repository="example/repo", repository_id="123", repository_uri="https://github.com/example/repo",
        owner_id="456", owner_uri="https://github.com/example", source_commit="a"*40,
        signer_commit=policy.job_workflow_sha or "a"*40, source_ref="refs/heads/main",
        workflow_identity="https://github.com/" + (policy.job_workflow_ref or policy.workflow_ref),
        build_config_identity="https://github.com/example/repo/.github/workflows/build.yml@refs/heads/main",
        issuer=identity.ISSUER, predicate_type="https://slsa.dev/provenance/v1", trigger="workflow_dispatch",
        run_id="1234", run_attempt="2", subject_name="unit.bin", subject_sha256=hashlib.sha256(b"unit").hexdigest(),
        visibility="public", runner_environment="github-hosted", timestamp_types=("TimestampAuthority",),
        maximum_age_seconds=600, future_skew_seconds=0)


@pytest.mark.parametrize("field,value", [("repository_id", "124"), ("owner_id", "457"), ("source_commit", "b"*40),
    ("signer_commit", "b"*40), ("run_id", "1235"), ("run_attempt", "3"), ("trigger", "push"),
    ("source_ref", "refs/heads/other"), ("workflow_identity", "https://github.com/shared/repo/.github/workflows/other.yml@refs/heads/main")])
def test_origin_mismatch_rejects_before_verifier(policy, monkeypatch, field, value):
    artifact = origin_policy(policy)
    if field == "source_ref":
        artifact = replace(artifact, build_config_identity="https://github.com/example/repo/.github/workflows/build.yml@refs/heads/other", source_ref=value)
    else: artifact = replace(artifact, **{field: value})
    monkeypatch.setattr(origin, "verify_origin", lambda *_args, **_kw: pytest.fail("mismatch precedes verification"))
    with pytest.raises(identity.WorkflowIdentityError):
        identity.authenticate_workflow_origin(SECRET, policy, artifact, None, None, None, None)


@pytest.mark.parametrize("reusable", [False, True])
def test_composed_real_origin_process_path_then_real_rs256_with_test_only_origin_output(policy, keys, monkeypatch, tmp_path, reusable):
    # Real origin parser/process; executable is NOT gh/Sigstore. Its output
    # proves composition plumbing only, never genuine artifact authentication.
    if reusable:
        policy = replace(policy, job_workflow_ref="shared/automation/.github/workflows/sign.yml@"+"b"*40, job_workflow_sha="b"*40)
    artifact = origin_policy(policy)
    certificate = {"issuer": identity.ISSUER, "subjectAlternativeName": artifact.workflow_identity,
        "buildSignerURI": artifact.workflow_identity, "buildSignerDigest": artifact.signer_commit,
        "runnerEnvironment": "github-hosted", "sourceRepositoryURI": artifact.repository_uri,
        "sourceRepositoryIdentifier": "123", "sourceRepositoryOwnerIdentifier": "456", "sourceRepositoryDigest": "a"*40,
        "sourceRepositoryRef": "refs/heads/main", "sourceRepositoryOwnerURI": "https://github.com/example",
        "sourceRepositoryVisibilityAtSigning": "public", "buildConfigURI": artifact.build_config_identity,
        "buildConfigDigest": "a"*40, "buildTrigger": "workflow_dispatch",
        "runInvocationURI": "https://github.com/example/repo/actions/runs/1234/attempts/2"}
    output = [{"verificationResult": {"statement": {"_type": "https://in-toto.io/Statement/v1",
        "predicateType": artifact.predicate_type, "predicate": {}, "subject": [{"name": "unit.bin", "digest": {"sha256": artifact.subject_sha256}}]},
        "signature": {"certificate": certificate}, "verifiedTimestamps": [{"type": "TimestampAuthority",
        "timestamp": datetime.fromtimestamp(NOW, UTC).isoformat()}]}}]
    marker = tmp_path / "origin-called"
    program = ("#!"+sys.executable+"\nimport base64,sys\nfrom pathlib import Path\n"
        + "Path("+repr(str(marker))+").write_text('unit-origin-called')\n"
        + "sys.stdout.buffer.write(base64.b64decode("+repr(base64.b64encode(raw(output)).decode())+"))\n").encode()
    pins = []
    for name, data in (("subject", b"unit"), ("bundle", b"{}"), ("standin", program), ("root", b"{}")):
        path = tmp_path / name
        path.write_bytes(data); path.chmod(0o700 if name == "standin" else 0o600)
        pins.append(origin.PinnedFile(path, hashlib.sha256(data).hexdigest()))
    def after_origin(_): assert marker.read_text() == "unit-origin-called"
    replies(monkeypatch, keys[0], callback=after_origin)
    value = claims()
    if reusable: value.update(job_workflow_ref=policy.job_workflow_ref, job_workflow_sha=policy.job_workflow_sha)
    result = identity.authenticate_workflow_origin(sign(keys[0], value), policy, artifact, *pins)
    assert result.artifact_origin.policy == artifact and result.workflow_job.job_id == 707
    assert result.workflow_job.job_workflow_sha == ("b"*40 if reusable else None)


@pytest.mark.parametrize("section", ["attempt", "job"])
def test_missing_conclusion_is_not_implicit_in_progress_null(policy, keys, monkeypatch, section):
    attempt, jobs = api_attempt(), api_jobs()
    del (attempt if section == "attempt" else jobs["jobs"][0])["conclusion"]
    replies(monkeypatch, keys[0], attempt=attempt, jobs=jobs)
    with pytest.raises(identity.WorkflowIdentityError):
        identity.authenticate_workflow_job(sign(keys[0]), policy)


def test_constant_https_success_uses_fixed_ca_and_ignores_proxy_environment(monkeypatch):
    for name in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY", "SSL_CERT_FILE", "DOCKER_HOST"):
        monkeypatch.setenv(name, "https://not-trusted.invalid/")
    headers = Message()
    headers["Content-Type"] = "application/json; charset=utf-8"
    headers["Content-Length"] = "2"
    reached = []
    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def geturl(self): return identity.JWKS_URL
        def read(self, limit):
            assert limit == 2097153
            reached.append("body")
            return b"{}"
    Response.headers = headers
    actual_context = ssl.create_default_context
    def context(**kwargs):
        assert kwargs == {"cafile": "/etc/ssl/certs/ca-certificates.crt"}
        reached.append("tls")
        return actual_context(**kwargs)
    def build(*handlers):
        assert handlers[0].proxies == {}
        assert handlers[2]._context.check_hostname and handlers[2]._context.verify_mode == ssl.CERT_REQUIRED
        def open_request(request, timeout):
            assert request.full_url == identity.JWKS_URL and request.get_method() == "GET"
            assert not request.has_header("Authorization") and timeout == 20
            reached.append("request")
            return Response()
        return SimpleNamespace(open=open_request)
    output = io.BytesIO()
    monkeypatch.setattr(ssl, "create_default_context", context)
    monkeypatch.setattr(urllib.request, "build_opener", build)
    monkeypatch.setattr(sys, "argv", ["helper", identity.JWKS_URL])
    monkeypatch.setattr(sys, "stdout", SimpleNamespace(buffer=output))
    exec(identity._HTTPS_SCRIPT, {})
    assert output.getvalue() == b"{}" and reached == ["tls", "request", "body"]


@pytest.mark.parametrize("stage", ["open", "body"])
def test_actual_constant_child_deadline_covers_slow_open_and_body_and_reaps(monkeypatch, stage, tmp_path):
    # Execute the real constant child code. A local in-process urllib adapter
    # sleeps instead of DNS/TLS or reading a remote body; no network is contacted.
    prefix = """
import urllib.request,time
from email.message import Message
from pathlib import Path
def pause():
 Path(MARKER).write_text(STAGE)
 time.sleep(60)
class FixtureResponse:
 status=200
 headers=Message()
 headers["Content-Type"]="application/json"
 headers["Content-Length"]="2"
 def __enter__(self): return self
 def __exit__(self,*args): pass
 def geturl(self): return "https://token.actions.githubusercontent.com/.well-known/jwks"
 def read(self,limit):
  if STAGE=="body": pause()
  return b"{}"
class FixtureOpener:
 def open(self,*args,**kwargs):
  if STAGE=="open": pause()
  return FixtureResponse()
urllib.request.build_opener=lambda *args:FixtureOpener()
"""
    marker = tmp_path / "reached-stage"
    setup = "STAGE=" + repr(stage) + "\nMARKER=" + repr(str(marker)) + "\n"
    monkeypatch.setattr(identity, "_HTTPS_SCRIPT", setup + prefix + identity._HTTPS_SCRIPT)
    actual_popen, children = origin.subprocess.Popen, []
    def popen(*args, **kwargs):
        process = actual_popen(*args, **kwargs)
        children.append(process)
        return process
    monkeypatch.setattr(origin.subprocess, "Popen", popen)
    began = time.monotonic()
    with pytest.raises(identity.WorkflowIdentityError, match="workflow-fetch"):
        identity._fetch(identity.JWKS_URL, began+1.0)
    assert marker.read_text() == stage
    assert len(children) == 1 and children[0].returncode is not None
    with pytest.raises(ProcessLookupError): os.kill(children[0].pid, 0)
    assert time.monotonic()-began < 3


@pytest.mark.parametrize("field,value", [("challenge_nonce", "e"*64), ("transaction_id", "e"*64)])
def test_another_transaction_or_nonce_cannot_reuse_valid_token(policy, keys, monkeypatch, field, value):
    replies(monkeypatch, keys[0])
    with pytest.raises(identity.WorkflowIdentityError, match="jwt-claims"):
        identity.authenticate_workflow_job(sign(keys[0]), replace(policy, **{field: value}))


def test_unknown_policy_fields_do_not_construct_authority():
    with pytest.raises(TypeError): identity.WorkflowJobPolicy(unreviewed=True)


def test_json_decoded_metadata_allows_only_bounded_valid_escapes():
    assert identity._json(b'{"message":"line1\\nline2\\r\\n\\tindent"}')["message"] == "line1\nline2\r\n\tindent"
    with pytest.raises(identity.WorkflowIdentityError): identity._json(b'{"message":"\\u0000"}')
    with pytest.raises(identity.WorkflowIdentityError): identity._json(b'{"message":"\\udfff"}')
