"""Private GitHub OIDC job authentication, not a release or runtime capability.

The controller independently admits this module, its Fleet imports, interpreter,
PyJWT (patched >=2.13), cryptography and TLS CA closure, exact policy, clock and
one fresh transaction challenge. Neither policy nor challenge may come from the
candidate. No environment identity is trusted. Bearer tokens stay in memory,
never in subprocess arguments/environment, public API requests, errors or facts.
Public repositories only; no credential acquisition or forwarding is supported.

RS256 proves GitHub-issued workflow/job claims; public API readback locates that
signed check_run_id in one exact run attempt. It does not prove logical job-role
code, container custody, artifact production by that job, signing authorization,
or replay consumption. The controller must atomically consume its own challenge
and revalidate current facts at the action boundary. Frozen results are ordinary
data, not AuthenticatedRebuildHandoff or another authorization capability.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import UTC, datetime
import hashlib
import json
import math
import re
import sys
import tempfile
import time
from pathlib import Path

import cryptography
from cryptography.hazmat.primitives.asymmetric import rsa
import jwt

from scripts import android_artifact_origin as origin

ISSUER = "https://token.actions.githubusercontent.com"
JWKS_URL = ISSUER + "/.well-known/jwks"
API = "https://api.github.com"
MAX_JSON = 2 * 1024 * 1024
MAX_TOKEN = 32768
TOTAL_SECONDS = 20.0
_NUMERIC = r"[1-9][0-9]{0,19}"
_REPOSITORY = r"[A-Za-z0-9-]+/[A-Za-z0-9_.-]+"
_WORKFLOW = _REPOSITORY + r"/\.github/workflows/[A-Za-z0-9_.-]+\.ya?ml@(?:refs/(?:heads|tags)/[A-Za-z0-9._/-]+|[0-9a-f]{40})"


class WorkflowIdentityError(RuntimeError):
    """Only constant codes; never tokens, URLs or server bodies."""


def _require(condition, code):
    if not condition:
        raise WorkflowIdentityError(code)


def _text(value, limit=2048):
    return type(value) is str and 0 < len(value) <= limit and all(
        32 <= ord(char) < 127 for char in value)


def _hex(value, count):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{%d}" % count, value) is not None


def _number(value):
    return type(value) is str and re.fullmatch(_NUMERIC, value) is not None


def _positive(value):
    return type(value) is int and 0 < value < 10**20


def _ref(value):
    return (_text(value) and re.fullmatch(r"refs/(heads|tags)/[A-Za-z0-9._/-]+", value)
            and not any(part in {"", ".", ".."} for part in value.split("/"))
            and ".." not in value and not value.endswith(".lock"))


def _workflow(value):
    if not _text(value) or not re.fullmatch(_WORKFLOW, value):
        return False
    path, ref = value.rsplit("@", 1)
    return not any(part in {".", ".."} for part in path.split("/")) and (_hex(ref, 40) or _ref(ref))


def _status(status, conclusion):
    return (status == "in_progress" and conclusion is None) or (status == "completed" and conclusion == "success")


@dataclass(frozen=True, slots=True, repr=False)
class WorkflowJobPolicy:
    repository: str
    repository_id: str
    repository_owner: str
    repository_owner_id: str
    subject: str
    sha: str
    ref: str
    workflow_ref: str
    workflow_sha: str
    run_id: str
    run_attempt: str
    check_run_id: str
    environment: str
    event_name: str
    runner_environment: str
    run_status: str
    run_conclusion: str | None
    job_status: str
    job_conclusion: str | None
    transaction_id: str
    challenge_nonce: str = field(repr=False)
    challenge_issued_at: int
    challenge_expires_at: int
    job_workflow_ref: str | None = None
    job_workflow_sha: str | None = None
    maximum_token_age_seconds: int = 300

    @property
    def audience(self):
        return "urn:chummer:fleet:workflow-job:" + self.transaction_id + ":" + self.challenge_nonce

    def __post_init__(self):
        _require(_text(self.repository) and re.fullmatch(_REPOSITORY, self.repository)
                 and self.repository.split("/")[1] not in {".", ".."}
                 and self.repository_owner == self.repository.split("/")[0], "policy-repository")
        _require(all(_number(value) for value in (self.repository_id, self.repository_owner_id,
                 self.run_id, self.run_attempt, self.check_run_id)), "policy-identities")
        _require(_hex(self.sha, 40) and _hex(self.workflow_sha, 40) and _ref(self.ref)
                 and _workflow(self.workflow_ref) and self.workflow_ref.startswith(self.repository + "/")
                 and self.workflow_ref.endswith("@" + self.ref), "policy-workflow")
        _require((self.job_workflow_ref is None and self.job_workflow_sha is None)
                 or (_workflow(self.job_workflow_ref) and _hex(self.job_workflow_sha, 40)), "policy-reusable")
        _require(_text(self.subject) and _text(self.environment, 255)
                 and self.event_name in {"push", "workflow_dispatch", "workflow_call", "workflow_run", "release", "schedule"}
                 and self.runner_environment in {"github-hosted", "self-hosted"}, "policy-context")
        _require(_status(self.run_status, self.run_conclusion) and _status(self.job_status, self.job_conclusion), "policy-status")
        _require(_hex(self.transaction_id, 64) and _hex(self.challenge_nonce, 64)
                 and _positive(self.challenge_issued_at) and _positive(self.challenge_expires_at)
                 and 0 < self.challenge_expires_at - self.challenge_issued_at <= 600
                 and type(self.maximum_token_age_seconds) is int
                 and 1 <= self.maximum_token_age_seconds <= 600, "policy-challenge")


@dataclass(frozen=True, slots=True)
class WorkflowJobIdentity:
    repository: str
    repository_id: str
    repository_owner_id: str
    source_sha: str
    workflow_ref: str
    workflow_sha: str
    job_workflow_ref: str | None
    job_workflow_sha: str | None
    run_id: str
    run_attempt: str
    check_run_id: str
    job_id: int
    environment: str
    transaction_id: str
    audience_sha256: str
    token_sha256: str
    token_identifier_sha256: str
    jwks_sha256: str
    issued_at: int
    expires_at: int
    valid_until: int
    checked_at: int
    job_status: str
    pyjwt_version: str
    cryptography_version: str


@dataclass(frozen=True, slots=True)
class WorkflowOriginIdentity:
    """Same execution context, NEVER proof that this job produced the artifact."""
    artifact_origin: origin.OriginFacts
    workflow_job: WorkflowJobIdentity


def _json(raw):
    _require(type(raw) is bytes and 0 < len(raw) <= MAX_JSON, "json-bound")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            _require(key not in result, "json-duplicate")
            result[key] = value
        return result
    def invalid(_):
        raise WorkflowIdentityError("json-nonfinite")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique, parse_constant=invalid)
        pending, count = [(value, 0)], 0
        while pending:
            item, depth = pending.pop()
            count += 1
            _require(count <= 30000 and depth <= 32, "json-bound")
            if type(item) is dict:
                _require(all(_text(key, 256) for key in item), "json-key")
                pending.extend((child, depth + 1) for child in item.values())
            elif type(item) is list:
                pending.extend((child, depth + 1) for child in item)
            elif type(item) is str:
                # API metadata may contain escaped newlines/tabs (commit text).
                # Consumed identities still get exact, stronger checks below.
                _require(len(item) <= 32768 and not any((ord(c) < 32 and c not in "\n\r\t")
                         or 0xD800 <= ord(c) <= 0xDFFF for c in item), "json-string")
            elif type(item) is float:
                _require(math.isfinite(item), "json-nonfinite")
        _require(type(value) is dict, "json-shape")
        return value
    except (ValueError, UnicodeError, RecursionError):
        raise WorkflowIdentityError("json-invalid") from None


def _b64(value, limit):
    _require(type(value) is str and 0 < len(value) <= limit and re.fullmatch(r"[A-Za-z0-9_-]+", value), "jwt-encoding")
    try:
        raw = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
        _require(base64.urlsafe_b64encode(raw).decode().rstrip("=") == value, "jwt-encoding")
        return raw
    except ValueError:
        raise WorkflowIdentityError("jwt-encoding") from None


# Standard-library-only fixed HTTPS child. The existing origin runner imposes
# the parent's absolute budget on DNS, TLS, headers and body, kills the process
# group and reaps the child. No policy/token/candidate code enters this process.
_HTTPS_SCRIPT = r'''
import re,ssl,sys,urllib.request
url=sys.argv[1]
allowed=(url=="https://token.actions.githubusercontent.com/.well-known/jwks" or
 re.fullmatch(r"https://api\.github\.com/repos/[A-Za-z0-9-]+/[A-Za-z0-9_.-]+/actions/runs/[1-9][0-9]{0,19}/attempts/[1-9][0-9]{0,19}(?:/jobs\?per_page=100&page=1)?",url))
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs): raise ValueError("redirect")
try:
 if not allowed or "/../" in url or "/./" in url: raise ValueError("endpoint")
 context=ssl.create_default_context(cafile="/etc/ssl/certs/ca-certificates.crt")
 context.minimum_version=ssl.TLSVersion.TLSv1_2
 opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect(),urllib.request.HTTPSHandler(context=context))
 request=urllib.request.Request(url,headers={"Accept":"application/json","User-Agent":"fleet-workflow-identity","X-GitHub-Api-Version":"2022-11-28"},method="GET")
 with opener.open(request,timeout=20) as response:
  headers=list(response.headers.items())
  names=[key.lower() for key,value in headers]
  if response.status!=200 or response.geturl()!=url or len(headers)>64 or sum(len(k)+len(v)+4 for k,v in headers)>16384 or len(names)!=len(set(names)): raise ValueError("headers")
  if response.headers.get_content_type()!="application/json" or response.headers.get_content_charset() not in (None,"utf-8") or "content-encoding" in names or "link" in names: raise ValueError("type-or-page")
  length=response.headers.get("Content-Length")
  if length is not None and (not re.fullmatch(r"[1-9][0-9]{0,7}",length) or int(length)>2097152): raise ValueError("length")
  data=response.read(2097153)
  if not 0<len(data)<=2097152 or length is not None and len(data)!=int(length): raise ValueError("body")
 sys.stdout.buffer.write(data)
except Exception:
 sys.exit(2)
'''


def _remaining(deadline):
    value = deadline - time.monotonic()
    _require(value > 0, "workflow-deadline")
    return value


def _endpoint(url):
    return url == JWKS_URL or (type(url) is str and re.fullmatch(
        re.escape(API) + r"/repos/" + _REPOSITORY + r"/actions/runs/" + _NUMERIC + r"/attempts/" + _NUMERIC
        + r"(?:/jobs\?per_page=100&page=1)?", url) and "/../" not in url and "/./" not in url)


def _fetch(url, deadline):
    _require(_endpoint(url), "workflow-endpoint")
    try:
        with tempfile.TemporaryDirectory(prefix="fleet-oidc-", dir="/tmp") as temporary:
            raw = origin._run([sys.executable, "-I", "-c", _HTTPS_SCRIPT, url], Path(temporary),
                              _remaining(deadline), MAX_JSON, 1024)
        _remaining(deadline)
        return raw
    except (origin.OriginError, OSError):
        raise WorkflowIdentityError("workflow-fetch") from None


def _key(jwks, kid):
    _require(set(jwks) == {"keys"} and type(jwks["keys"]) is list and 1 <= len(jwks["keys"]) <= 32, "jwks-shape")
    ids, selected = set(), None
    for row in jwks["keys"]:
        required = {"kid", "kty", "use", "alg", "n", "e"}
        allowed = required | {"x5c", "x5t", "x5t#S256", "key_ops"}
        _require(type(row) is dict and required <= set(row) <= allowed
                 and _text(row["kid"], 256) and row["kid"] not in ids
                 and row["kty"] == "RSA" and row["use"] == "sig" and row["alg"] == "RS256", "jwks-key")
        ids.add(row["kid"])
        _require("key_ops" not in row or row["key_ops"] == ["verify"], "jwks-key")
        for name, size in (("x5t", 20), ("x5t#S256", 32)):
            if name in row:
                _require(len(_b64(row[name], 64)) == size, "jwks-key")
        if "x5c" in row:
            _require(type(row["x5c"]) is list and 1 <= len(row["x5c"]) <= 8
                     and all(_text(cert, 16384) for cert in row["x5c"]), "jwks-key")
            # Public certificates are not selected as roots or followed. n/e
            # from this fixed TLS-authenticated JWKS are the verification key.
            for cert in row["x5c"]:
                _require(0 < len(base64.b64decode(cert, validate=True)) <= 12288, "jwks-key")
        modulus, exponent = _b64(row["n"], 1024), _b64(row["e"], 16)
        _require(modulus[0] != 0 and exponent[0] != 0, "jwks-key")
        n, e = int.from_bytes(modulus, "big"), int.from_bytes(exponent, "big")
        _require(2048 <= n.bit_length() <= 4096 and n % 2 == 1 and e == 65537, "jwks-key")
        if row["kid"] == kid:
            selected = rsa.RSAPublicNumbers(e, n).public_key()
    _require(selected is not None, "jwks-key-missing")
    return selected


def _claims(claims, policy, now):
    expected = {"iss": ISSUER, "sub": policy.subject, "aud": policy.audience,
        "repository": policy.repository, "repository_id": policy.repository_id,
        "repository_owner": policy.repository_owner, "repository_owner_id": policy.repository_owner_id,
        "sha": policy.sha, "ref": policy.ref, "workflow_ref": policy.workflow_ref, "workflow_sha": policy.workflow_sha,
        "run_id": policy.run_id, "run_attempt": policy.run_attempt, "check_run_id": policy.check_run_id,
        "environment": policy.environment, "event_name": policy.event_name,
        "runner_environment": policy.runner_environment, "repository_visibility": "public"}
    _require(all(type(claims.get(key)) is str and claims[key] == value for key, value in expected.items()), "jwt-claims")
    for key in ("job_workflow_ref", "job_workflow_sha"):
        value = getattr(policy, key)
        _require((key not in claims if value is None else type(claims.get(key)) is str and claims[key] == value), "jwt-reusable")
    _require(all(_positive(claims.get(key)) for key in ("iat", "nbf", "exp"))
             and _text(claims.get("jti"), 256), "jwt-time-shape")
    issued, not_before, expires = claims["iat"], claims["nbf"], claims["exp"]
    _require(policy.challenge_issued_at <= issued <= now < policy.challenge_expires_at
             and not_before <= issued < expires and not_before <= now < expires
             and now - issued < policy.maximum_token_age_seconds
             and 0 < expires - issued <= 600, "jwt-time")


def _run_attempt(value, policy):
    _require("conclusion" in value and type(value.get("id")) is int and value["id"] == int(policy.run_id)
             and type(value.get("run_attempt")) is int and value["run_attempt"] == int(policy.run_attempt)
             and value.get("head_sha") == policy.sha and value.get("event") == policy.event_name
             and value.get("status") == policy.run_status and value.get("conclusion") == policy.run_conclusion,
             "api-run")
    base = API + "/repos/" + policy.repository
    _require(value.get("url") == base + "/actions/runs/" + policy.run_id
             and value.get("html_url") == "https://github.com/" + policy.repository + "/actions/runs/" + policy.run_id
             and value.get("path") == policy.workflow_ref.split("/", 2)[2].split("@", 1)[0], "api-run-location")
    repository = value.get("repository")
    _require(type(repository) is dict and type(repository.get("id")) is int
             and repository["id"] == int(policy.repository_id) and repository.get("full_name") == policy.repository
             and repository.get("private") is False, "api-repository")
    owner = repository.get("owner")
    _require(type(owner) is dict and type(owner.get("id")) is int and owner["id"] == int(policy.repository_owner_id)
             and owner.get("login") == policy.repository_owner, "api-owner")


def _job(value, policy):
    _require(set(value) == {"total_count", "jobs"} and type(value["total_count"]) is int
             and type(value["jobs"]) is list and 1 <= value["total_count"] <= 100
             and value["total_count"] == len(value["jobs"]), "api-jobs-page")
    base = API + "/repos/" + policy.repository
    expected_check = base + "/check-runs/" + policy.check_run_id
    seen_ids, seen_checks, matches = set(), set(), []
    for row in value["jobs"]:
        _require(type(row) is dict and _positive(row.get("id")) and row["id"] not in seen_ids
                 and type(row.get("run_id")) is int and row["run_id"] == int(policy.run_id)
                 and row.get("run_url") == base + "/actions/runs/" + policy.run_id
                 and row.get("url") == base + "/actions/jobs/" + str(row["id"])
                 and row.get("head_sha") == policy.sha, "api-job")
        check = row.get("check_run_url")
        _require(type(check) is str and re.fullmatch(re.escape(base) + r"/check-runs/" + _NUMERIC, check)
                 and check not in seen_checks, "api-check-run")
        if "run_attempt" in row:
            _require(type(row["run_attempt"]) is int and row["run_attempt"] == int(policy.run_attempt), "api-job-attempt")
        seen_ids.add(row["id"])
        seen_checks.add(check)
        if check == expected_check:
            matches.append(row)
    _require(len(matches) == 1, "api-check-cardinality")
    selected = matches[0]
    _require("conclusion" in selected and selected.get("status") == policy.job_status
             and selected.get("conclusion") == policy.job_conclusion, "api-job-status")
    return selected["id"]


def _authenticate(token, policy, deadline):
    version = re.fullmatch(r"([0-9]+)\.([0-9]+)\.([0-9]+)", jwt.__version__)
    _require(version is not None and tuple(map(int, version.groups())) >= (2, 13, 0), "workflow-dependency")
    _require(type(policy) is WorkflowJobPolicy, "workflow-policy")
    policy.__post_init__()
    _require(_text(token, MAX_TOKEN), "jwt-shape")
    parts = token.split(".")
    _require(len(parts) == 3, "jwt-shape")
    header = _json(_b64(parts[0], 2048))
    _require(set(header) == {"alg", "kid", "typ"} and header.get("alg") == "RS256"
             and header.get("typ") == "JWT" and _text(header.get("kid"), 256), "jwt-header")
    claims = _json(_b64(parts[1], MAX_TOKEN))
    _b64(parts[2], 1024)
    _claims(claims, policy, int(time.time()))  # Rejection only, not authentication.
    _remaining(deadline)
    raw_keys = _fetch(JWKS_URL, deadline)
    key = _key(_json(raw_keys), header["kid"])
    _remaining(deadline)
    try:
        # Raw RSAPublicKey avoids the PyJWK algorithm-selection path. Controller
        # admission still requires patched PyJWT/import closure, not ambient pip.
        verified = jwt.decode(token, key=key, algorithms=["RS256"], issuer=ISSUER,
            audience=policy.audience, options={"strict_aud": True,
            "require": ["iss", "sub", "aud", "iat", "nbf", "exp", "jti"]})
    except (jwt.PyJWTError, ValueError, TypeError):
        raise WorkflowIdentityError("jwt-signature-or-validity") from None
    _require(verified == claims, "jwt-decoding-drift")
    _claims(verified, policy, int(time.time()))
    base = API + "/repos/" + policy.repository + "/actions/runs/" + policy.run_id + "/attempts/" + policy.run_attempt
    _run_attempt(_json(_fetch(base, deadline)), policy)
    job_id = _job(_json(_fetch(base + "/jobs?per_page=100&page=1", deadline)), policy)
    _remaining(deadline)
    now = int(time.time())
    _claims(verified, policy, now)
    sha = lambda value: hashlib.sha256(value).hexdigest()
    return WorkflowJobIdentity(policy.repository, policy.repository_id, policy.repository_owner_id, policy.sha,
        policy.workflow_ref, policy.workflow_sha, policy.job_workflow_ref, policy.job_workflow_sha,
        policy.run_id, policy.run_attempt, policy.check_run_id, job_id, policy.environment, policy.transaction_id,
        sha(policy.audience.encode()), sha(token.encode()), sha(verified["jti"].encode()), sha(raw_keys),
        verified["iat"], verified["exp"], min(verified["exp"], policy.challenge_expires_at,
        verified["iat"] + policy.maximum_token_age_seconds), now, policy.job_status, jwt.__version__, cryptography.__version__)


def authenticate_workflow_job(token: str, policy: WorkflowJobPolicy) -> WorkflowJobIdentity:
    """Authenticate one fresh signed identity; do not consume/authorize its transaction."""
    try:
        return _authenticate(token, policy, time.monotonic() + TOTAL_SECONDS)
    except (ValueError, TypeError, OSError, RecursionError, OverflowError):
        raise WorkflowIdentityError("workflow-invalid") from None


def _same_context(job, artifact):
    signer_ref = job.job_workflow_ref or job.workflow_ref
    signer_sha = job.job_workflow_sha or job.workflow_sha
    _require(artifact.repository == job.repository and artifact.repository_id == job.repository_id
             and artifact.owner_id == job.repository_owner_id
             and artifact.owner_uri == "https://github.com/" + job.repository_owner
             and artifact.issuer == ISSUER and artifact.source_commit == job.sha
             and artifact.source_ref == job.ref and artifact.run_id == job.run_id and artifact.run_attempt == job.run_attempt
             and artifact.build_config_identity == "https://github.com/" + job.workflow_ref
             and artifact.source_commit == job.workflow_sha
             and artifact.workflow_identity == "https://github.com/" + signer_ref and artifact.signer_commit == signer_sha
             and artifact.trigger == job.event_name and artifact.visibility == "public"
             and artifact.runner_environment == job.runner_environment, "origin-workflow-context")


def authenticate_workflow_origin(token: str, policy: WorkflowJobPolicy, artifact_policy: origin.OriginPolicy,
        subject: origin.PinnedFile, bundle: origin.PinnedFile, verifier: origin.PinnedFile,
        trusted_root: origin.PinnedFile) -> WorkflowOriginIdentity:
    """Run real origin verification then OIDC authentication; not producer-job attribution.

    The caller retains all origin files in immutable custody through subsequent
    use. No serialized envelope, capability or existing handoff is constructed.
    """
    deadline = time.monotonic() + TOTAL_SECONDS
    try:
        _require(type(policy) is WorkflowJobPolicy and type(artifact_policy) is origin.OriginPolicy, "workflow-policy")
        policy.__post_init__()
        artifact_policy.__post_init__()
        _same_context(policy, artifact_policy)
        facts = origin.verify_origin(artifact_policy, subject, bundle, verifier, trusted_root,
            now=datetime.now(UTC), timeout_seconds=_remaining(deadline))
        _require(type(facts) is origin.OriginFacts and facts.policy == artifact_policy, "origin-result")
        identity = _authenticate(token, policy, deadline)
        _same_context(policy, facts.policy)
        _remaining(deadline)
        return WorkflowOriginIdentity(facts, identity)
    except origin.OriginError:
        raise WorkflowIdentityError("workflow-origin") from None
    except (ValueError, TypeError, OSError, RecursionError, OverflowError):
        raise WorkflowIdentityError("workflow-invalid") from None
