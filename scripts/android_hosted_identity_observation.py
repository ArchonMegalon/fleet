#!/usr/bin/env python3
"""Public compatibility observation only; never authenticate or authorize work.

The JWT is requested directly from the hosted runner's TLS endpoint and decoded
in memory WITHOUT signature verification. Neither it nor any request credential,
header value, response body, subject or JTI is persisted or logged. This diagnostic
does not import or change the production workflow identity verifier.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import re
import signal
import ssl
import stat
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

REPOSITORY = "ArchonMegalon/fleet"
REPOSITORY_ID = "1176287728"
WORKFLOW = ".github/workflows/android-hosted-identity-observation.yml"
WORKFLOW_REF = REPOSITORY + "/" + WORKFLOW + "@refs/heads/main"
API = "https://api.github.com/repos/" + REPOSITORY
ISSUER = "https://token.actions.githubusercontent.com"
AUDIENCE_PREFIX = "urn:chummer:fleet:diagnostic:oidc-check-run-id:"
MAX_JSON = 2 * 1024 * 1024
MAX_TOKEN = 32768
OUTPUT_NAME = "hosted-identity-observation.json"
STAGES = frozenset(("startup", "context", "branch-request", "branch-validation", "oidc-url",
    "oidc-request", "oidc-response", "oidc-token", "oidc-header", "oidc-claims", "oidc-times",
    "oidc-check-run", "run-request", "run-validation", "repository-validation", "jobs-request",
    "jobs-validation", "job-validation", "report-write"))
REASONS = frozenset(("validation", "unexpected-exception", "deadline", "json-bounds", "json-duplicate-key",
    "json-nonfinite", "http-status", "http-url", "http-header-count", "http-header-duplicates",
    "http-header-bounds", "http-content-type", "http-charset", "http-content-encoding", "http-pagination",
    "http-body-bounds", "header-schema", "header-alg", "header-typ", "header-string", "claim-mismatch"))
TYPE_FIELDS = {
    "branch": ("name", "protected", "commit"), "oidc-response": ("value",),
    "header": ("alg", "kid", "typ", "x5t"),
    "claims": ("iss", "aud", "repository", "repository_id", "repository_owner", "repository_owner_id",
        "sha", "ref", "workflow_ref", "workflow_sha", "run_id", "run_attempt", "event_name",
        "runner_environment", "repository_visibility", "iat", "nbf", "exp", "check_run_id",
        "environment", "job_workflow_ref", "job_workflow_sha"),
    "run": ("id", "run_attempt", "head_sha", "path", "event", "status", "conclusion", "repository"),
    "jobs": ("total_count", "jobs"),
    "job": ("id", "run_id", "run_attempt", "head_sha", "run_url", "url", "check_run_url", "name", "status", "conclusion"),
}
TYPE_NAMES = frozenset(group + "." + key for group, keys in TYPE_FIELDS.items() for key in keys) | frozenset(TYPE_FIELDS)
JSON_TYPES = frozenset(("missing", "null", "boolean", "integer", "number", "string", "array", "object", "other"))
MISSING = object()


class ObservationError(RuntimeError):
    def __init__(self, reason="validation"):
        # Even accidentally supplied arbitrary error text cannot reach output.
        self.reason = reason if type(reason) is str and reason in REASONS else "unexpected-exception"
        super().__init__("identity-observation-rejected")


def require(value, reason="validation"):
    if not value:
        raise ObservationError(reason)


class Diagnostic:
    """Closed failure vocabulary: never keep or serialize observed field values."""
    def __init__(self):
        self.stage, self.field, self.types = "startup", None, {}

    def at(self, stage):
        require(stage in STAGES)
        self.stage, self.field = stage, None

    def record(self, group, value):
        require(group in TYPE_FIELDS)
        def kind(item):
            if item is MISSING:
                return "missing"
            return {type(None): "null", bool: "boolean", int: "integer", float: "number",
                str: "string", list: "array", dict: "object"}.get(type(item), "other")
        self.types[group] = kind(value)
        for key in TYPE_FIELDS[group]:
            self.types[group + "." + key] = kind(value.get(key, MISSING) if type(value) is dict else MISSING)

    def failure(self, error):
        # Re-filter even our internal state; an arbitrary exception/callback must
        # never turn a failure into an exception-text, unknown-name or value dump.
        result = {"classification": "diagnostic_only_not_authority", "outcome": "failed",
            "stage": self.stage if type(self.stage) is str and self.stage in STAGES else "startup",
            "reason": error.reason if type(error) is ObservationError and type(error.reason) is str and error.reason in REASONS else "unexpected-exception",
            "fieldTypes": {key: value for key, value in self.types.items()
                if type(key) is str and key in TYPE_NAMES and type(value) is str and value in JSON_TYPES}}
        if type(self.field) is str and self.field in TYPE_NAMES:
            result["field"] = self.field
        return json.dumps(result, sort_keys=True, separators=(",", ":"))


def number(value):
    return type(value) is str and re.fullmatch(r"[1-9][0-9]{0,19}", value) is not None


def strict_json(raw):
    require(type(raw) is bytes and 0 < len(raw) <= MAX_JSON, "json-bounds")
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "json-duplicate-key")
            result[key] = value
        return result
    def invalid(_value):
        raise ObservationError("json-nonfinite")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=invalid)


def context(environment):
    require(environment.get("EXECUTION_REPOSITORY") == REPOSITORY
        and environment.get("EXECUTION_REPOSITORY_ID") == REPOSITORY_ID
        and environment.get("EXECUTION_OWNER") == "ArchonMegalon"
        and environment.get("EXECUTION_REF") == "refs/heads/main"
        and environment.get("EXECUTION_REF_PROTECTED") == "true"
        and environment.get("EXECUTION_EVENT") == "workflow_dispatch"
        and environment.get("WORKFLOW_REPOSITORY") == REPOSITORY
        and environment.get("WORKFLOW_REF") == WORKFLOW_REF
        and environment.get("EXECUTION_JOB") == "observe"
        and environment.get("EXECUTION_RUN_ATTEMPT") == "1")
    sha = environment.get("EXPECTED_EXECUTION_SHA")
    require(type(sha) is str and re.fullmatch(r"[0-9a-f]{40}", sha)
        and environment.get("EXECUTION_SHA") == environment.get("WORKFLOW_SHA") == sha)
    run, attempt, owner = (environment.get(name) for name in
        ("EXECUTION_RUN_ID", "EXECUTION_RUN_ATTEMPT", "EXECUTION_OWNER_ID"))
    require(all(number(value) for value in (run, attempt, owner)))
    encoded_check = environment.get("EXECUTION_CHECK_RUN_JSON")
    require(type(encoded_check) is str and len(encoded_check) <= 22)
    check = strict_json(encoded_check.encode())
    require(type(check) in (str, int) and number(str(check)))
    return {"sha": sha, "run": run, "attempt": attempt, "owner": owner,
        "check": str(check), "contextValue": check, "contextType": "string" if type(check) is str else "number"}


def audience(expected):
    return AUDIENCE_PREFIX + expected["run"] + ":" + expected["attempt"] + ":" + expected["check"]


def oidc_url(value, expected):
    require(type(value) is str and 0 < len(value) <= 8192 and not re.search(r"[\x00-\x20\x7f]", value))
    parsed = urllib.parse.urlsplit(value)
    require(parsed.scheme == "https" and parsed.hostname is not None
        and parsed.hostname.endswith(".actions.githubusercontent.com")
        and parsed.port in (None, 443) and not parsed.username and not parsed.password
        and not parsed.fragment and parsed.path.startswith("/") and parsed.path != "/")
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True)
    require(len(query) <= 32 and all(key != "audience" for key, _value in query))
    return urllib.parse.urlunsplit(parsed._replace(query=urllib.parse.urlencode(query + [("audience", audience(expected))])))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        raise ObservationError("identity-observation-rejected")


def get_json(url, credential, limit):
    """One fixed GET, no proxy, redirect, retries, response or credential logs."""
    require(type(credential) is str and 0 < len(credential) <= 16384
        and not re.search(r"[\x00-\x20\x7f]", credential))
    tls = ssl.create_default_context()
    tls.minimum_version = ssl.TLSVersion.TLSv1_2
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(),
        urllib.request.HTTPSHandler(context=tls))
    request = urllib.request.Request(url, method="GET", headers={
        "Authorization": "Bearer " + credential, "Accept": "application/json",
        "User-Agent": "fleet-hosted-identity-diagnostic", "X-GitHub-Api-Version": "2022-11-28"})
    try:
        response = opener.open(request, timeout=15)
    except urllib.error.HTTPError:
        # urllib raises before returning a response on real 4xx/5xx statuses.
        # Do not read, stringify or log the exception, its URL, headers or body.
        raise ObservationError("http-status") from None
    with response:
        headers = list(response.headers.items())
        names = [key.lower() for key, _value in headers]
        require(response.status == 200, "http-status")
        require(response.geturl() == url, "http-url")
        require(len(headers) <= 64, "http-header-count")
        require(len(names) == len(set(names)), "http-header-duplicates")
        require(sum(len(key) + len(value) for key, value in headers) <= 16384, "http-header-bounds")
        require(response.headers.get_content_type() == "application/json", "http-content-type")
        require(response.headers.get_content_charset() in (None, "utf-8"), "http-charset")
        require("content-encoding" not in names, "http-content-encoding")
        require("link" not in names, "http-pagination")
        raw = response.read(limit + 1)
        require(0 < len(raw) <= limit, "http-body-bounds")
        return strict_json(raw)


def decode_observation(value, expected, diagnostic=None):
    diagnostic = Diagnostic() if diagnostic is None else diagnostic
    diagnostic.at("oidc-response")
    diagnostic.record("oidc-response", value)
    # The official toolkit selects response.value, not a closed response schema.
    # The HTTP body is bounded; all additional response metadata is discarded.
    require(type(value) is dict and "value" in value)
    token = value["value"]
    require(type(token) is str and 0 < len(token) <= MAX_TOKEN)
    diagnostic.at("oidc-token")
    parts = token.split(".")
    require(len(parts) == 3)
    decoded = []
    for index, part in enumerate(parts):
        require(0 < len(part) <= (2048, MAX_TOKEN, 1024)[index]
            and re.fullmatch(r"[A-Za-z0-9_-]+", part))
        raw = base64.b64decode(part + "=" * (-len(part) % 4), altchars=b"-_", validate=True)
        require(base64.urlsafe_b64encode(raw).decode().rstrip("=") == part)
        decoded.append(raw)
    header, claims = strict_json(decoded[0]), strict_json(decoded[1])
    diagnostic.at("oidc-header")
    diagnostic.record("header", header)
    diagnostic.record("claims", claims)
    # GitHub documents optional x5t. Observe only these known names/types, never
    # values; this diagnostic does not change the production header verifier.
    require(type(header) is dict and {"alg", "kid", "typ"} <= set(header) <= {"alg", "kid", "typ", "x5t"}, "header-schema")
    require(header["alg"] == "RS256", "header-alg")
    require(header["typ"] == "JWT", "header-typ")
    require(all(type(header[key]) is str and 0 < len(header[key]) <= 256 for key in header), "header-string")
    diagnostic.at("oidc-claims")
    require(type(claims) is dict)
    selected = {"iss": ISSUER, "aud": audience(expected), "repository": REPOSITORY,
        "repository_id": REPOSITORY_ID, "repository_owner": "ArchonMegalon",
        "repository_owner_id": expected["owner"], "sha": expected["sha"], "ref": "refs/heads/main",
        "workflow_ref": WORKFLOW_REF, "workflow_sha": expected["sha"], "run_id": expected["run"],
        "run_attempt": expected["attempt"], "event_name": "workflow_dispatch",
        "runner_environment": "github-hosted", "repository_visibility": "public"}
    for key, value in selected.items():
        diagnostic.field = "claims." + key
        require(type(claims.get(key)) is str and claims[key] == value, "claim-mismatch")
    diagnostic.field = None
    require(not any(key in claims for key in ("environment", "job_workflow_ref", "job_workflow_sha")))
    diagnostic.at("oidc-times")
    now = int(time.time())
    require(all(type(claims.get(key)) is int for key in ("iat", "nbf", "exp"))
        and 0 <= now - claims["iat"] <= 300 and claims["nbf"] <= now < claims["exp"]
        and 0 < claims["exp"] - claims["iat"] <= 600)
    diagnostic.at("oidc-check-run")
    diagnostic.field = "claims.check_run_id"
    check = claims.get("check_run_id")
    require(type(check) in (str, int) and number(str(check)) and str(check) == expected["check"])
    # Return only an equality-checked public integer/string; no arbitrary JWT values.
    return {"checkRunId": {"jsonType": "string" if type(check) is str else "number", "value": check},
        "headerTypes": {key: "string" for key in sorted(header)}}


def observe(environment, fetch=get_json, diagnostic=None):
    diagnostic = Diagnostic() if diagnostic is None else diagnostic
    diagnostic.at("context")
    expected = context(environment)
    token = environment.get("OBSERVATION_GITHUB_TOKEN")
    diagnostic.at("branch-request")
    branch = fetch(API + "/branches/main", token, MAX_JSON)
    diagnostic.at("branch-validation")
    diagnostic.record("branch", branch)
    require(type(branch) is dict and branch.get("name") == "main" and branch.get("protected") is True
        and type(branch.get("commit")) is dict and branch["commit"].get("sha") == expected["sha"])
    diagnostic.at("oidc-url")
    request_url = oidc_url(environment.get("ACTIONS_ID_TOKEN_REQUEST_URL"), expected)
    diagnostic.at("oidc-request")
    observed = decode_observation(fetch(request_url,
        environment.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN"), MAX_TOKEN + 1024), expected, diagnostic)
    run_url = API + "/actions/runs/" + expected["run"]
    attempt_url = run_url + "/attempts/" + expected["attempt"]
    diagnostic.at("run-request")
    run = fetch(attempt_url, token, MAX_JSON)
    diagnostic.at("run-validation")
    diagnostic.record("run", run)
    require(type(run) is dict and type(run.get("id")) is int and str(run["id"]) == expected["run"]
        and type(run.get("run_attempt")) is int and str(run["run_attempt"]) == expected["attempt"]
        and run.get("head_sha") == expected["sha"] and run.get("path") == WORKFLOW
        and run.get("event") == "workflow_dispatch" and run.get("status") == "in_progress"
        and "conclusion" in run and run["conclusion"] is None and run.get("url") == run_url
        and run.get("html_url") == "https://github.com/" + REPOSITORY + "/actions/runs/" + expected["run"])
    diagnostic.at("repository-validation")
    repo = run.get("repository")
    require(type(repo) is dict and type(repo.get("id")) is int and str(repo["id"]) == REPOSITORY_ID
        and repo.get("full_name") == REPOSITORY and repo.get("private") is False
        and type(repo.get("owner")) is dict and type(repo["owner"].get("id")) is int
        and str(repo["owner"]["id"]) == expected["owner"] and repo["owner"].get("login") == "ArchonMegalon")
    diagnostic.at("jobs-request")
    jobs = fetch(attempt_url + "/jobs?per_page=100&page=1", token, MAX_JSON)
    diagnostic.at("jobs-validation")
    diagnostic.record("jobs", jobs)
    require(type(jobs) is dict and set(jobs) == {"total_count", "jobs"}
        and type(jobs["total_count"]) is int and jobs["total_count"] == 1
        and type(jobs["jobs"]) is list and len(jobs["jobs"]) == 1)
    diagnostic.at("job-validation")
    job = jobs["jobs"][0]
    diagnostic.record("job", job)
    require(type(job) is dict and type(job.get("id")) is int and number(str(job["id"]))
        and type(job.get("run_id")) is int and str(job["run_id"]) == expected["run"]
        and job.get("head_sha") == expected["sha"] and job.get("run_url") == run_url
        and job.get("url") == API + "/actions/jobs/" + str(job["id"])
        and job.get("check_run_url") == API + "/check-runs/" + expected["check"]
        and job.get("name") == "Observe hosted identity (diagnostic only)"
        and job.get("status") == "in_progress" and "conclusion" in job and job["conclusion"] is None)
    if "run_attempt" in job:
        require(type(job["run_attempt"]) is int and str(job["run_attempt"]) == expected["attempt"])
    return {"classification": "diagnostic_only_not_authority", "signatureVerified": False,
        "repository": REPOSITORY, "repositoryId": REPOSITORY_ID, "sourceSha": expected["sha"],
        "workflowRef": WORKFLOW_REF, "runId": expected["run"], "runAttempt": expected["attempt"],
        "oidcCheckRunId": observed["checkRunId"], "jwtHeaderTypes": observed["headerTypes"],
        "contextCheckRunId": {"jsonType": expected["contextType"], "value": expected["contextValue"]},
        "apiJobId": job["id"], "apiCheckRunId": expected["check"], "comparison": "exact_match"}


def write_report(report, root):
    require(type(root) is str and root and Path(root).is_absolute())
    directory = Path(root)
    require(directory.resolve(strict=True) == directory and not directory.is_symlink())
    metadata = directory.stat()
    require(stat.S_ISDIR(metadata.st_mode) and metadata.st_uid == os.getuid() and not metadata.st_mode & 0o022)
    raw = (json.dumps(report, sort_keys=True, indent=2) + "\n").encode()
    require(len(raw) <= 4096)
    fd = os.open(directory / OUTPUT_NAME, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def main(environment=None):
    diagnostic = Diagnostic()
    try:
        signal.signal(signal.SIGALRM, lambda *_args: require(False, "deadline"))
        signal.alarm(60)
        env = os.environ if environment is None else environment
        report = observe(env, diagnostic=diagnostic)
        diagnostic.at("report-write")
        write_report(report, env.get("RUNNER_TEMP"))
    except BaseException as error:
        # Never print exceptions or tracebacks: they may contain HTTP credentials.
        print("Hosted identity diagnostic failed; no authority was produced.", file=sys.stderr)
        print(diagnostic.failure(error), file=sys.stderr)
        return 1
    finally:
        signal.alarm(0)
    print("Hosted identity diagnostic completed; public metadata only, not authority.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
