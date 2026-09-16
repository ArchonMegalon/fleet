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


class ObservationError(RuntimeError):
    pass


def require(value):
    if not value:
        raise ObservationError("identity-observation-rejected")


def number(value):
    return type(value) is str and re.fullmatch(r"[1-9][0-9]{0,19}", value) is not None


def strict_json(raw):
    require(type(raw) is bytes and 0 < len(raw) <= MAX_JSON)
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result)
            result[key] = value
        return result
    def invalid(_value):
        raise ObservationError("identity-observation-rejected")
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
    with opener.open(request, timeout=15) as response:
        headers = list(response.headers.items())
        names = [key.lower() for key, _value in headers]
        require(response.status == 200 and response.geturl() == url and len(headers) <= 64
            and len(names) == len(set(names)) and sum(len(key) + len(value) for key, value in headers) <= 16384
            and response.headers.get_content_type() == "application/json"
            and response.headers.get_content_charset() in (None, "utf-8")
            and "content-encoding" not in names and "link" not in names)
        raw = response.read(limit + 1)
        require(0 < len(raw) <= limit)
        return strict_json(raw)


def decode_observation(value, expected):
    # The official toolkit selects response.value, not a closed response schema.
    # The HTTP body is bounded; all additional response metadata is discarded.
    require(type(value) is dict and "value" in value)
    token = value["value"]
    require(type(token) is str and 0 < len(token) <= MAX_TOKEN)
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
    # GitHub documents optional x5t. Observe only these known names/types, never
    # values; this diagnostic does not change the production header verifier.
    require(type(header) is dict and {"alg", "kid", "typ"} <= set(header) <= {"alg", "kid", "typ", "x5t"}
        and header["alg"] == "RS256" and header["typ"] == "JWT"
        and all(type(header[key]) is str and 0 < len(header[key]) <= 256 for key in header)
        and type(claims) is dict)
    selected = {"iss": ISSUER, "aud": audience(expected), "repository": REPOSITORY,
        "repository_id": REPOSITORY_ID, "repository_owner": "ArchonMegalon",
        "repository_owner_id": expected["owner"], "sha": expected["sha"], "ref": "refs/heads/main",
        "workflow_ref": WORKFLOW_REF, "workflow_sha": expected["sha"], "run_id": expected["run"],
        "run_attempt": expected["attempt"], "event_name": "workflow_dispatch",
        "runner_environment": "github-hosted", "repository_visibility": "public"}
    require(all(type(claims.get(key)) is str and claims[key] == value for key, value in selected.items()))
    require(not any(key in claims for key in ("environment", "job_workflow_ref", "job_workflow_sha")))
    now = int(time.time())
    require(all(type(claims.get(key)) is int for key in ("iat", "nbf", "exp"))
        and 0 <= now - claims["iat"] <= 300 and claims["nbf"] <= now < claims["exp"]
        and 0 < claims["exp"] - claims["iat"] <= 600)
    check = claims.get("check_run_id")
    require(type(check) in (str, int) and number(str(check)) and str(check) == expected["check"])
    # Return only an equality-checked public integer/string; no arbitrary JWT values.
    return {"checkRunId": {"jsonType": "string" if type(check) is str else "number", "value": check},
        "headerTypes": {key: "string" for key in sorted(header)}}


def observe(environment, fetch=get_json):
    expected = context(environment)
    token = environment.get("OBSERVATION_GITHUB_TOKEN")
    branch = fetch(API + "/branches/main", token, MAX_JSON)
    require(type(branch) is dict and branch.get("name") == "main" and branch.get("protected") is True
        and type(branch.get("commit")) is dict and branch["commit"].get("sha") == expected["sha"])
    observed = decode_observation(fetch(oidc_url(environment.get("ACTIONS_ID_TOKEN_REQUEST_URL"), expected),
        environment.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN"), MAX_TOKEN + 1024), expected)
    run_url = API + "/actions/runs/" + expected["run"]
    attempt_url = run_url + "/attempts/" + expected["attempt"]
    run = fetch(attempt_url, token, MAX_JSON)
    require(type(run) is dict and type(run.get("id")) is int and str(run["id"]) == expected["run"]
        and type(run.get("run_attempt")) is int and str(run["run_attempt"]) == expected["attempt"]
        and run.get("head_sha") == expected["sha"] and run.get("path") == WORKFLOW
        and run.get("event") == "workflow_dispatch" and run.get("status") == "in_progress"
        and "conclusion" in run and run["conclusion"] is None and run.get("url") == run_url
        and run.get("html_url") == "https://github.com/" + REPOSITORY + "/actions/runs/" + expected["run"])
    repo = run.get("repository")
    require(type(repo) is dict and type(repo.get("id")) is int and str(repo["id"]) == REPOSITORY_ID
        and repo.get("full_name") == REPOSITORY and repo.get("private") is False
        and type(repo.get("owner")) is dict and type(repo["owner"].get("id")) is int
        and str(repo["owner"]["id"]) == expected["owner"] and repo["owner"].get("login") == "ArchonMegalon")
    jobs = fetch(attempt_url + "/jobs?per_page=100&page=1", token, MAX_JSON)
    require(type(jobs) is dict and set(jobs) == {"total_count", "jobs"}
        and type(jobs["total_count"]) is int and jobs["total_count"] == 1
        and type(jobs["jobs"]) is list and len(jobs["jobs"]) == 1)
    job = jobs["jobs"][0]
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
    try:
        signal.signal(signal.SIGALRM, lambda *_args: require(False))
        signal.alarm(60)
        env = os.environ if environment is None else environment
        report = observe(env)
        write_report(report, env.get("RUNNER_TEMP"))
    except BaseException:
        # Never print exceptions or tracebacks: they may contain HTTP credentials.
        print("Hosted identity diagnostic failed; no authority was produced.", file=sys.stderr)
        return 1
    finally:
        signal.alarm(0)
    print("Hosted identity diagnostic completed; public metadata only, not authority.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
