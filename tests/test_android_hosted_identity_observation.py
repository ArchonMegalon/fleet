"""Synthetic diagnostic fixtures only: no real tokens, HTTP or hosted authority."""
import base64
from copy import deepcopy
from email.message import Message
import importlib.util
import json
from pathlib import Path
import time
from types import SimpleNamespace
import urllib.error

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("hosted_diagnostic", ROOT / "scripts/android_hosted_identity_observation.py")
observation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(observation)


def encoded(raw):
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def token(claims, header=None):
    # Deliberately NOT a signature: diagnostic parsing is never authentication.
    header = {"alg": "RS256", "typ": "JWT", "kid": "test-only"} if header is None else header
    return ".".join((encoded(json.dumps(header).encode()),
        encoded(json.dumps(claims).encode()), encoded(b"not-a-real-signature")))


@pytest.fixture
def model(tmp_path):
    env = {"EXECUTION_REPOSITORY": observation.REPOSITORY, "EXECUTION_REPOSITORY_ID": observation.REPOSITORY_ID,
        "EXECUTION_OWNER": "ArchonMegalon", "EXECUTION_OWNER_ID": "123", "EXECUTION_REF": "refs/heads/main",
        "EXECUTION_REF_PROTECTED": "true", "EXECUTION_EVENT": "workflow_dispatch", "EXPECTED_EXECUTION_SHA": "a" * 40,
        "EXECUTION_SHA": "a" * 40, "WORKFLOW_SHA": "a" * 40, "WORKFLOW_REPOSITORY": observation.REPOSITORY,
        "WORKFLOW_REF": observation.WORKFLOW_REF, "EXECUTION_RUN_ID": "456", "EXECUTION_RUN_ATTEMPT": "1",
        "EXECUTION_JOB": "observe", "EXECUTION_CHECK_RUN_JSON": "789",
        "OBSERVATION_GITHUB_TOKEN": "PRIVATE-GITHUB-TEST-TOKEN",
        "ACTIONS_ID_TOKEN_REQUEST_URL": "https://run-actions.example.actions.githubusercontent.com/oidc?job=private-query",
        "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "PRIVATE-OIDC-REQUEST-TOKEN", "RUNNER_TEMP": str(tmp_path)}
    now = int(time.time())
    claims = {"iss": observation.ISSUER, "aud": observation.audience(observation.context(env)),
        "repository": observation.REPOSITORY, "repository_id": observation.REPOSITORY_ID,
        "repository_owner": "ArchonMegalon", "repository_owner_id": "123", "sha": "a" * 40,
        "ref": "refs/heads/main", "workflow_ref": observation.WORKFLOW_REF, "workflow_sha": "a" * 40,
        "run_id": "456", "run_attempt": "1", "check_run_id": "789", "event_name": "workflow_dispatch",
        "runner_environment": "github-hosted", "repository_visibility": "public", "iat": now, "nbf": now,
        "exp": now + 300, "sub": "PRIVATE-SUBJECT", "jti": "PRIVATE-JTI", "arbitrary": "PRIVATE-OTHER-CLAIM"}
    run_url = observation.API + "/actions/runs/456"
    run = {"id": 456, "run_attempt": 1, "head_sha": "a" * 40, "path": observation.WORKFLOW,
        "event": "workflow_dispatch", "status": "in_progress", "conclusion": None, "url": run_url,
        "html_url": "https://github.com/" + observation.REPOSITORY + "/actions/runs/456",
        "repository": {"id": int(observation.REPOSITORY_ID), "full_name": observation.REPOSITORY, "private": False,
            "owner": {"id": 123, "login": "ArchonMegalon"}}, "unselected": "PRIVATE-API-EXTRA"}
    job = {"id": 990, "run_id": 456, "run_attempt": 1, "head_sha": "a" * 40,
        "run_url": run_url, "url": observation.API + "/actions/jobs/990",
        "check_run_url": observation.API + "/check-runs/789", "status": "in_progress", "conclusion": None,
        "name": "Observe hosted identity (diagnostic only)", "steps": [{"name": "PRIVATE-STEP"}]}
    value = SimpleNamespace(env=env, claims=claims, run=run, job=job, calls=[], count=1, header=None, oidc_extra={})
    def fetch(url, credential, limit):
        value.calls.append((url, credential, limit))
        if url == observation.API + "/branches/main":
            assert credential == env["OBSERVATION_GITHUB_TOKEN"]
            return {"name": "main", "protected": True, "commit": {"sha": "a" * 40}}
        if url.startswith("https://run-actions."):
            assert credential == env["ACTIONS_ID_TOKEN_REQUEST_TOKEN"] and "audience=" in url
            assert "urn%3Achummer%3Afleet%3Adiagnostic%3A" in url
            return {"value": token(claims, value.header), **value.oidc_extra}
        assert credential == env["OBSERVATION_GITHUB_TOKEN"]
        if url == run_url + "/attempts/1":
            return deepcopy(run)
        assert url == run_url + "/attempts/1/jobs?per_page=100&page=1"
        return {"total_count": value.count, "jobs": [deepcopy(job)]}
    value.fetch = fetch
    return value


@pytest.mark.parametrize("claim,context", [("789", "789"), (789, "789"), (789, '"789"'), ("789", '"789"')])
def test_whitelisted_types_and_exact_attempt_mapping_never_promote_authority(model, claim, context):
    model.claims["check_run_id"] = claim
    model.env["EXECUTION_CHECK_RUN_JSON"] = context
    result = observation.observe(model.env, model.fetch)
    assert result["oidcCheckRunId"] == {"jsonType": "number" if type(claim) is int else "string", "value": claim}
    assert result["contextCheckRunId"]["value"] == json.loads(context)
    assert result["apiJobId"] == 990 and result["apiCheckRunId"] == "789"
    assert result["jwtHeaderTypes"] == {"alg": "string", "kid": "string", "typ": "string"}
    assert result["signatureVerified"] is False and result["classification"] == "diagnostic_only_not_authority"
    assert len(model.calls) == 4
    serialized = json.dumps(result)
    assert "PRIVATE" not in serialized and token(model.claims) not in serialized
    assert "Authorization" not in serialized and "audience" not in serialized and "private-query" not in serialized
    assert set(result) == {"classification", "signatureVerified", "repository", "repositoryId", "sourceSha",
        "workflowRef", "runId", "runAttempt", "oidcCheckRunId", "contextCheckRunId", "apiJobId", "apiCheckRunId",
        "comparison", "jwtHeaderTypes"}


def test_documented_x5t_header_and_extra_response_metadata_never_expose_values(model):
    model.header = {"alg": "RS256", "typ": "JWT", "kid": "PRIVATE-KEY-ID", "x5t": "PRIVATE-THUMBPRINT"}
    model.oidc_extra = {"PRIVATE-RESPONSE-FIELD": {"nested": "PRIVATE-RESPONSE-VALUE"}}
    result = observation.observe(model.env, model.fetch)
    assert result["jwtHeaderTypes"] == {"alg": "string", "kid": "string", "typ": "string", "x5t": "string"}
    assert "PRIVATE" not in json.dumps(result)
    assert token(model.claims, model.header) not in json.dumps(result)


@pytest.mark.parametrize("field,value", [("PRIVATE-HEADER-NAME", "PRIVATE-HEADER-VALUE"),
    ("x5t", {}), ("x5t", True), ("x5t", ""), ("x5t", "x" * 257), ("alg", "none"), ("typ", "OTHER")])
def test_unknown_or_malformed_header_is_rejected_without_echo(model, monkeypatch, capsys, field, value):
    model.header = {"alg": "RS256", "typ": "JWT", "kid": "PRIVATE-KEY-ID", field: value}
    monkeypatch.setattr(observation, "observe", lambda env: observation_decode(model))
    assert observation.main(model.env) == 1
    output = capsys.readouterr()
    assert output.out == "" and output.err == "Hosted identity diagnostic failed; no authority was produced.\n"
    assert not (Path(model.env["RUNNER_TEMP"]) / observation.OUTPUT_NAME).exists()


def observation_decode(model):
    return observation.decode_observation({"value": token(model.claims, model.header)}, observation.context(model.env))


@pytest.mark.parametrize("value", [None, True, False, 789.0, [], {}, "0789", "789\n", "PRIVATE", 10**20, "790"])
def test_unexpected_oidc_scalar_or_wrong_job_rejected_without_normalizing_production(model, value):
    model.claims["check_run_id"] = value
    with pytest.raises(observation.ObservationError):
        observation.observe(model.env, model.fetch)
    assert len(model.calls) == 2


@pytest.mark.parametrize("field,value", [("run_id", "457"), ("run_attempt", "2"), ("sha", "b" * 40),
    ("aud", "urn:chummer:fleet:workflow-job:production"), ("repository", "foreign/repo"),
    ("workflow_ref", "wrong"), ("runner_environment", "self-hosted"), ("exp", 0), ("iat", True)])
def test_wrong_token_context_fails_before_jobs_api(model, field, value):
    model.claims[field] = value
    with pytest.raises(observation.ObservationError):
        observation.observe(model.env, model.fetch)
    assert len(model.calls) == 2


@pytest.mark.parametrize("field,value", [("EXECUTION_EVENT", "pull_request"), ("EXECUTION_RUN_ATTEMPT", "2"),
    ("WORKFLOW_SHA", "b" * 40), ("EXECUTION_REF_PROTECTED", "false"), ("EXECUTION_JOB", "other"),
    ("EXECUTION_CHECK_RUN_JSON", "true"), ("EXECUTION_CHECK_RUN_JSON", '"0789"')])
def test_bad_workflow_context_never_requests_tokens(model, field, value):
    model.env[field] = value
    with pytest.raises(observation.ObservationError):
        observation.observe(model.env, model.fetch)
    assert model.calls == []


@pytest.mark.parametrize("field,value", [("id", 457), ("run_attempt", 2), ("head_sha", "b" * 40),
    ("path", "other.yml"), ("event", "push"), ("status", "completed"), ("url", "https://foreign.invalid")])
def test_wrong_exact_run_attempt_rejected(model, field, value):
    model.run[field] = value
    with pytest.raises(observation.ObservationError):
        observation.observe(model.env, model.fetch)


@pytest.mark.parametrize("field,value", [("id", True), ("run_id", 457), ("run_attempt", 2), ("head_sha", "b" * 40),
    ("check_run_url", observation.API + "/check-runs/790"), ("url", "https://foreign.invalid"),
    ("name", "unselected job"), ("status", "completed"), ("conclusion", "success")])
def test_wrong_jobs_mapping_rejected(model, field, value):
    model.job[field] = value
    with pytest.raises(observation.ObservationError):
        observation.observe(model.env, model.fetch)


def test_single_job_cardinality_is_required(model):
    model.count = 2
    with pytest.raises(observation.ObservationError):
        observation.observe(model.env, model.fetch)


@pytest.mark.parametrize("raw", [b'{"x":1,"x":2}', b'{"x":NaN}', b'\xff', b'{', b'{}\ntrailing', b'x' * (2*1024*1024+1)])
def test_strict_json_and_bounds(raw):
    with pytest.raises((observation.ObservationError, ValueError)):
        observation.strict_json(raw)


@pytest.mark.parametrize("value", [{}, {"value": "PRIVATE"}, {"value": "x" * 32769},
    {"value": "a.b.c", "extra": "PRIVATE"}, {"value": "a.b.c"}])
def test_malformed_oidc_response(model, value):
    with pytest.raises((observation.ObservationError, ValueError)):
        observation.decode_observation(value, observation.context(model.env))


@pytest.mark.parametrize("url", ["http://run.actions.githubusercontent.com/x", "https://evil.invalid/x",
    "https://actions.githubusercontent.com.evil.invalid/x", "https://user@run.actions.githubusercontent.com/x",
    "https://run.actions.githubusercontent.com:444/x", "https://run.actions.githubusercontent.com/x#fragment",
    "https://run.actions.githubusercontent.com/x?audience=production", "https://run.actions.githubusercontent.com/x\n"])
def test_oidc_request_credentials_cannot_be_redirected(model, url):
    with pytest.raises((observation.ObservationError, ValueError)):
        observation.oidc_url(url, observation.context(model.env))


def test_network_errors_and_raw_claims_never_appear_in_cli_errors(model, monkeypatch, capsys):
    def failed(_env):
        raise urllib.error.URLError("PRIVATE JWT " + token(model.claims) + " PRIVATE request header")
    monkeypatch.setattr(observation, "observe", failed)
    assert observation.main(model.env) == 1
    output = capsys.readouterr()
    assert output.out == "" and output.err == "Hosted identity diagnostic failed; no authority was produced.\n"
    assert not (Path(model.env["RUNNER_TEMP"]) / observation.OUTPUT_NAME).exists()


def test_report_is_private_exclusive_and_never_overwritten(model, tmp_path):
    result = observation.observe(model.env, model.fetch)
    observation.write_report(result, str(tmp_path))
    target = tmp_path / observation.OUTPUT_NAME
    assert target.stat().st_mode & 0o777 == 0o600
    before = target.read_bytes()
    with pytest.raises(FileExistsError):
        observation.write_report(result, str(tmp_path))
    assert target.read_bytes() == before and b"PRIVATE" not in before and len(before) <= 4096


def test_report_rejects_alias_parent_and_symlink_output(model, tmp_path):
    alias = tmp_path / "alias"
    alias.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(observation.ObservationError):
        observation.write_report({}, str(alias))
    target = tmp_path / observation.OUTPUT_NAME
    target.symlink_to(tmp_path / "other")
    with pytest.raises(FileExistsError):
        observation.write_report({}, str(tmp_path))
    assert not (tmp_path / "other").exists()


@pytest.mark.parametrize("fault", ["oversize", "redirect", "content-type", "encoding", "pagination", "duplicate-header", "status"])
def test_actual_http_reader_rejects_bounds_redirect_and_malformed_responses(monkeypatch, fault):
    endpoint = observation.API + "/branches/main"
    headers = Message()
    headers["Content-Type"] = "application/json"
    if fault == "content-type":
        headers.replace_header("Content-Type", "text/html")
    elif fault == "encoding":
        headers["Content-Encoding"] = "gzip"
    elif fault == "pagination":
        headers["Link"] = "PRIVATE"
    elif fault == "duplicate-header":
        headers["Content-Type"] = "application/json"
    class Response:
        status = 500 if fault == "status" else 200
        def __enter__(self): return self
        def __exit__(self, *_args): pass
        def geturl(self): return "https://foreign.invalid" if fault == "redirect" else endpoint
        def read(self, size):
            assert size == 17
            return b"x" * 17 if fault == "oversize" else b'{}'
    response = Response()
    response.headers = headers
    def opener(*handlers):
        assert any(isinstance(handler, observation.NoRedirect) for handler in handlers)
        assert any(isinstance(handler, observation.urllib.request.ProxyHandler) and handler.proxies == {} for handler in handlers)
        def opened(request, timeout):
            assert request.full_url == endpoint and timeout == 15 and request.method == "GET"
            assert request.get_header("Authorization") == "Bearer PRIVATE-TEST-TOKEN"
            return response
        return SimpleNamespace(open=opened)
    monkeypatch.setattr(observation.urllib.request, "build_opener", opener)
    with pytest.raises(observation.ObservationError):
        observation.get_json(endpoint, "PRIVATE-TEST-TOKEN", 16)
    with pytest.raises(observation.ObservationError):
        observation.NoRedirect().redirect_request(None, None, None, None, None, "https://foreign.invalid")


def test_wrong_current_main_stops_before_oidc(model):
    def drift(url, credential, limit):
        assert url == observation.API + "/branches/main"
        return {"name": "main", "protected": True, "commit": {"sha": "b" * 40}}
    with pytest.raises(observation.ObservationError):
        observation.observe(model.env, drift)


@pytest.mark.parametrize("credential", ["", None, "PRIVATE\nHEADER", "x" * 16385])
def test_invalid_request_credentials_rejected_before_http(credential):
    with pytest.raises(observation.ObservationError):
        observation.get_json(observation.API + "/branches/main", credential, 16)


def test_workflow_is_manual_secretless_nondeploying_and_only_uploads_public_file():
    raw = (ROOT / ".github/workflows/android-hosted-identity-observation.yml").read_text()
    assert "  workflow_dispatch:" in raw
    assert not any(value in raw for value in ("  push:", "  pull_request:", "  schedule:", "secrets.", "environment:",
        "attestations:", "packages:", "actions/attest", "curl", "set -x", "pip install"))
    assert "toJSON(job.check_run_id)" in raw
    assert "persist-credentials: false" in raw and "id-token: write" in raw
    assert "runner.temp }}/hosted-identity-observation.json" in raw
    assert "always()" not in raw and "overwrite: false" in raw
    assert "11d5960a326750d5838078e36cf38b85af677262" in raw
    assert "ea165f8d65b6e75b540449e92b4886f43607fa02" in raw
