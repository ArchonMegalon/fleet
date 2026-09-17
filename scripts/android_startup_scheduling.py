"""Bounded public scheduling markers for the already-admitted Android roles.

This is scheduling metadata only. It authenticates no job, issues no
challenge, and never replaces the existing binder/OIDC/Jobs-API checks.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import select
import selectors
import signal
import subprocess
import sys
import tempfile
import time
from urllib.parse import quote

from scripts import android_artifact_origin as origin
from scripts import android_workflow_identity as identity
from scripts import android_workflow_job_binder as binder

ROLES = binder.ROLES
STAGES = frozenset(("listener", "export"))
ERROR = "startup scheduling stopped; reconcile before any new attempt"
MAX_STATUS_BYTES = 2 * 1024 * 1024
MAX_HEADERS_BYTES = 16 * 1024
MAX_STATUS_ROWS = 100
MAX_POST_BYTES = 16 * 1024
LISTENER_OBSERVATIONS = 8
EXPORT_OBSERVATIONS = 16
LISTENER_DELAY = 10.0
EXPORT_DELAYS = (30.0, 60.0, 120.0, 240.0, 480.0, 900.0)
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_LOGIN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,38}(?:\[bot\])?)?\Z")
_TIMESTAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z")
_BARRIER_FIELDS = frozenset(("publisher_id",))
_UNSET = object()


class StartupSchedulingError(RuntimeError):
    """Constant errors only; never expose remote metadata or credentials."""


@dataclass(frozen=True, slots=True)
class StartupBinding:
    publisher_id: int
    templates: dict
    status_write_token: str | None


def _require(value):
    if not value:
        raise StartupSchedulingError(ERROR)


def _positive_id(value):
    return type(value) is int and 0 < value < 10**20


def _path(value):
    _require(type(value) is str and value.startswith("/") and "\x00" not in value
             and "\\" not in value and all(32 < ord(char) < 127 for char in value))
    path = Path(value)
    _require(str(path) == value and value != "/"
             and not any(part in {"", ".", ".."} for part in value.split("/")[1:]))
    return path


def validate_deployment(value, *, owner=False):
    """Validate optional barrier configuration without network or file reads."""
    try:
        _require(type(value) is dict)
        barrier = value.get("startup_barrier", _UNSET)
        token = value.get("status_write_token", _UNSET)
        if barrier is _UNSET:
            _require(token is _UNSET)
            return None
        _require(type(barrier) is dict and set(barrier) == _BARRIER_FIELDS
                 and _positive_id(barrier["publisher_id"]))
        _require("role_binding" in value)
        _names, templates = binder.validate_role_binding(value["role_binding"])
        if token is not _UNSET:
            _require(owner)
            token = str(_path(token))
        else:
            token = None
        return StartupBinding(barrier["publisher_id"], templates, token)
    except StartupSchedulingError:
        raise
    except Exception:
        raise StartupSchedulingError(ERROR) from None


def _canonical(values):
    try:
        return json.dumps(values, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode("ascii")
    except (TypeError, ValueError, UnicodeError):
        raise StartupSchedulingError(ERROR) from None


def binding_digest(bound_deployment):
    """Digest actual check IDs in capture/emission/protected order."""
    try:
        _require(type(bound_deployment) is dict and set(bound_deployment) == set(ROLES))
        ids = []
        for role in ROLES:
            policy = bound_deployment[role]
            _require(type(policy) is identity.WorkflowJobPolicy and identity._number(policy.check_run_id))
            ids.append(policy.check_run_id)
        _require(len(set(ids)) == len(ROLES))
        return hashlib.sha256(_canonical(ids)).hexdigest()
    except StartupSchedulingError:
        raise
    except Exception:
        raise StartupSchedulingError(ERROR) from None


def _context(config, stage):
    _require(stage in STAGES)
    first = config.templates["capture"]
    values = [first.repository, first.workflow_sha, first.run_id, first.run_attempt, first.transaction_id]
    _require(identity._text(first.repository, 255) and identity._hex(first.workflow_sha, 40)
             and identity._number(first.run_id) and identity._number(first.run_attempt)
             and identity._hex(first.transaction_id, 64))
    return "android-start/" + stage + "/" + hashlib.sha256(_canonical(values)).hexdigest()


def _attempt_url(policy):
    return "https://github.com/" + policy.repository + "/actions/runs/" + policy.run_id + "/attempts/" + policy.run_attempt


def _status_url(policy):
    return identity.API + "/repos/" + policy.repository + "/statuses/" + policy.sha


def _status_endpoint(policy):
    return identity.API + "/repos/" + policy.repository + "/commits/" + policy.sha + "/statuses?per_page=100&page=1"


_GET_SCRIPT = r'''
import re,ssl,sys,urllib.request
url=sys.argv[1]
if not re.fullmatch(r"https://api\.github\.com/repos/[A-Za-z0-9-]+/[A-Za-z0-9_.-]+/commits/[0-9a-f]{40}/statuses\?per_page=100&page=1", url):
    raise SystemExit(2)
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): raise ValueError("redirect")
try:
    ctx=ssl.create_default_context(cafile="/etc/ssl/certs/ca-certificates.crt")
    ctx.minimum_version=ssl.TLSVersion.TLSv1_2
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect(),urllib.request.HTTPSHandler(context=ctx))
    req=urllib.request.Request(url,headers={"Accept":"application/vnd.github+json","User-Agent":"fleet-android-startup","X-GitHub-Api-Version":"2022-11-28"},method="GET")
    with opener.open(req,timeout=20) as response:
        headers=list(response.headers.items()); names=[key.lower() for key,value in headers]
        if response.geturl()!=url or response.status!=200 or len(headers)>64 or len(names)!=len(set(names)) or sum(len(str(k))+len(str(v))+4 for k,v in headers)>16384 or "link" in names or "content-encoding" in names or "transfer-encoding" in names or response.headers.get_content_type()!="application/json" or response.headers.get_content_charset() not in (None,"utf-8"): raise ValueError("response")
        length=response.headers.get("Content-Length")
        if length is not None and (not re.fullmatch(r"[1-9][0-9]{0,7}",length) or int(length)>2097152): raise ValueError("length")
        data=bytearray()
        while len(data)<=2097152:
            chunk=response.read(min(65536,2097153-len(data)))
            if not chunk: break
            data.extend(chunk)
        if not 0<len(data)<=2097152 or length is not None and len(data)!=int(length): raise ValueError("body")
    sys.stdout.buffer.write(data)
except Exception:
    raise SystemExit(2)
'''


_POST_SCRIPT = r'''
import json,re,ssl,sys,urllib.request
try:
    envelope=json.loads(sys.stdin.buffer.read(32768).decode("utf-8"))
    url,body,token=envelope["url"],envelope["body"],envelope["token"]
    if not re.fullmatch(r"https://api\.github\.com/repos/[A-Za-z0-9-]+/[A-Za-z0-9_.-]+/statuses/[0-9a-f]{40}",url): raise ValueError("url")
    if not isinstance(body,str) or not 0<len(body.encode("ascii"))<=16384 or not isinstance(token,str) or not 1<=len(token)<=4096: raise ValueError("request")
    ctx=ssl.create_default_context(cafile="/etc/ssl/certs/ca-certificates.crt")
    ctx.minimum_version=ssl.TLSVersion.TLSv1_2
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs): raise ValueError("redirect")
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect(),urllib.request.HTTPSHandler(context=ctx))
    req=urllib.request.Request(url,data=body.encode("ascii"),headers={"Accept":"application/vnd.github+json","Content-Type":"application/json","User-Agent":"fleet-android-startup","X-GitHub-Api-Version":"2022-11-28","Authorization":"Bearer "+token},method="POST")
    with opener.open(req,timeout=20) as response:
        headers=list(response.headers.items()); names=[key.lower() for key,value in headers]
        if response.geturl()!=url or response.status!=201 or len(headers)>64 or len(names)!=len(set(names)) or sum(len(str(k))+len(str(v))+4 for k,v in headers)>16384 or "link" in names or "content-encoding" in names or "transfer-encoding" in names or response.headers.get_content_type()!="application/json" or response.headers.get_content_charset() not in (None,"utf-8"): raise ValueError("response")
        length=response.headers.get("Content-Length")
        if length is not None and (not re.fullmatch(r"[1-9][0-9]{0,7}",length) or int(length)>16384): raise ValueError("length")
        data=bytearray()
        while len(data)<=16384:
            chunk=response.read(min(65536,16385-len(data)))
            if not chunk: break
            data.extend(chunk)
        if not 0<len(data)<=16384 or length is not None and len(data)!=int(length): raise ValueError("body")
    sys.stdout.buffer.write(data)
except Exception:
    raise SystemExit(2)
'''


def _run_transport(command, input_bytes, directory, timeout, out_limit):
    """Run one fixed transport child with bounded pipes and process-group cleanup."""
    process = pidfd = None
    _require(type(input_bytes) is bytes and 0 < len(input_bytes) < 32768
             and type(timeout) in (int, float) and math.isfinite(timeout) and 0 < timeout <= 20
             and type(out_limit) is int and 0 < out_limit <= MAX_STATUS_BYTES
             and signal.getsignal(signal.SIGCHLD) == signal.SIG_DFL)
    deadline = time.monotonic() + timeout
    output = bytearray()
    written = 0
    try:
        process = subprocess.Popen(
            command, cwd=directory, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, close_fds=True, start_new_session=True, bufsize=0,
            env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
        )
        pidfd = os.pidfd_open(process.pid)
        with selectors.DefaultSelector() as selector:
            os.set_blocking(process.stdin.fileno(), False)
            selector.register(process.stdin, selectors.EVENT_WRITE)
            for stream in (process.stdout, process.stderr):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise StartupSchedulingError(ERROR)
                for key, _ in selector.select(min(remaining, 0.05)):
                    if key.fileobj is process.stdin:
                        count = os.write(key.fd, input_bytes[written:written + 4096])
                        _require(count > 0)
                        written += count
                        if written == len(input_bytes):
                            selector.unregister(process.stdin)
                            process.stdin.close()
                        continue
                    available = out_limit - len(output) if key.fileobj is process.stdout else 0
                    chunk = os.read(key.fd, min(65536, available + 1))
                    if not chunk:
                        selector.unregister(key.fileobj)
                    else:
                        _require(key.fileobj is process.stdout and len(chunk) <= available)
                        output.extend(chunk)
            _require(written == len(input_bytes))
            _require(select.select([pidfd], [], [], _remaining(deadline))[0] == [pidfd])
            _remaining(deadline)
    except StartupSchedulingError:
        raise
    except Exception:
        raise StartupSchedulingError(ERROR) from None
    finally:
        if process is not None:
            cleanup_failed = False
            try:
                # No poll/wait above: our unreaped child's PID still fences
                # this process group, including descendants holding pipes.
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except OSError:
                cleanup_failed = True
            try:
                process.wait(timeout=1)
            except Exception:
                cleanup_failed = True
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None:
                    try:
                        stream.close()
                    except Exception:
                        cleanup_failed = True
            if pidfd is not None:
                os.close(pidfd)
            _require(not cleanup_failed)
    _require(process.returncode == 0)
    return bytes(output)


def _remaining(deadline):
    _require(type(deadline) in (int, float) and not isinstance(deadline, bool)
             and math.isfinite(deadline) and time.monotonic() < deadline)
    return deadline - time.monotonic()


def _http(url, *, method, body=None, token=None, deadline=None):
    """One bounded request; callers deliberately never retry this function."""
    try:
        _remaining(deadline)
        request_deadline = min(deadline, time.monotonic() + 20.0)
        base = r"https://api\.github\.com/repos/[A-Za-z0-9-]+/[A-Za-z0-9_.-]+/"
        if method == "GET":
            _require(type(url) is str and re.fullmatch(base + r"commits/[0-9a-f]{40}/statuses\?per_page=100&page=1", url)
                     and body is None and token is None and "/../" not in url and "/./" not in url)
            with tempfile.TemporaryDirectory(prefix="fleet-startup-", dir="/tmp") as temporary:
                result = origin._run([sys.executable, "-I", "-B", "-c", _GET_SCRIPT, url], Path(temporary),
                                     _remaining(request_deadline), MAX_STATUS_BYTES, MAX_HEADERS_BYTES)
                _remaining(request_deadline)
                return result
        _require(method == "POST" and type(body) is bytes and 0 < len(body) <= MAX_POST_BYTES)
        _require(type(url) is str and re.fullmatch(base + r"statuses/[0-9a-f]{40}", url)
                 and "/../" not in url and "/./" not in url)
        _require(type(token) is str and 1 <= len(token) <= 4096
                 and all(33 <= ord(char) < 127 and not char.isspace() for char in token))
        envelope = _canonical({"url": url, "body": body.decode("ascii"), "token": token})
        _require(len(envelope) < 32768)
        with tempfile.TemporaryDirectory(prefix="fleet-startup-", dir="/tmp") as temporary:
            result = _run_transport([sys.executable, "-I", "-B", "-c", _POST_SCRIPT], envelope,
                                    Path(temporary), _remaining(request_deadline), MAX_POST_BYTES)
            _remaining(request_deadline)
            return result
    except StartupSchedulingError:
        raise
    except Exception:
        raise StartupSchedulingError(ERROR) from None


def _json(raw, *, list_value=False):
    try:
        _require(type(raw) is bytes and 0 < len(raw) <= MAX_STATUS_BYTES)
        def unique(pairs):
            result = {}
            for key, value in pairs:
                _require(key not in result)
                result[key] = value
            return result
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        _require((type(value) is list) if list_value else (type(value) is dict))
        pending, count = [(value, 0)], 0
        while pending:
            item, depth = pending.pop()
            count += 1
            _require(count <= 30000 and depth <= 32)
            if type(item) is dict:
                _require(all(identity._text(key, 256) for key in item))
                pending.extend((child, depth + 1) for child in item.values())
            elif type(item) is list:
                pending.extend((child, depth + 1) for child in item)
            elif type(item) is float:
                _require(math.isfinite(item))
            elif type(item) is str:
                _require(len(item) <= 32768 and all((ord(char) >= 32 or char in "\n\r\t")
                         and not 0xD800 <= ord(char) <= 0xDFFF for char in item))
        return value
    except StartupSchedulingError:
        raise
    except Exception:
        raise StartupSchedulingError(ERROR) from None


def _timestamp(value):
    _require(type(value) is str and _TIMESTAMP.fullmatch(value))
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        raise StartupSchedulingError(ERROR) from None


def _description(digest):
    _require(type(digest) is str and _SHA.fullmatch(digest))
    return "ids-sha256:" + digest + " ordered[capture,emission,protected] checkIDs"


def _creator(row, publisher_id=None):
    creator = row.get("creator")
    _require(type(creator) is dict and _positive_id(creator.get("id"))
             and identity._text(creator.get("login"), 64) and _LOGIN.fullmatch(creator["login"])
             and creator.get("url") == identity.API + "/users/" + quote(creator["login"], safe=""))
    if publisher_id is not None:
        _require(creator["id"] == publisher_id)


def _validate_status(row, config, context, target, status_url):
    _require(type(row) is dict and _positive_id(row.get("id"))
             and type(row.get("state")) is str and row["state"] in {"pending", "success", "error", "failure"}
             and type(row.get("context")) is str and len(row["context"]) <= 255
             and row.get("url") == status_url)
    matching = row.get("context").casefold() == context.casefold()
    _creator(row, config.publisher_id if matching else None)
    created, updated = _timestamp(row.get("created_at")), _timestamp(row.get("updated_at"))
    _require(created <= updated)
    target_url, description = row.get("target_url"), row.get("description")
    # Other CI producers may use Unicode or empty/null display metadata. Only
    # our exact context carries fixed scheduling semantics; _json bounds all
    # strings and control characters before this generic row validation.
    _require((target_url is None or type(target_url) is str and len(target_url) <= 2048)
             and (description is None or type(description) is str and len(description) <= 2048))
    if matching:
        _require(row["context"] == context and target_url == target and description is not None)
        match = re.fullmatch(r"ids-sha256:([0-9a-f]{64}) ordered\[capture,emission,protected\] checkIDs", description)
        _require(match is not None)
        return updated, match.group(1), row["state"]
    return updated, None, None


def _observe(raw, config, stage):
    rows = _json(raw, list_value=True)
    _require(len(rows) <= MAX_STATUS_ROWS)
    policy = config.templates["capture"]
    context, target, status_url = _context(config, stage), _attempt_url(policy), _status_url(policy)
    seen, matches = set(), []
    for row in rows:
        _require(type(row) is dict and _positive_id(row.get("id")) and row["id"] not in seen)
        seen.add(row["id"])
        updated, digest, state = _validate_status(row, config, context, target, status_url)
        if digest is not None:
            matches.append((updated, digest, state))
    _require(all(matches[index][0] >= matches[index + 1][0] for index in range(len(matches) - 1)))
    if not matches:
        _require(len(rows) < MAX_STATUS_ROWS)
        return None
    _, digest, state = matches[0]
    if state == "success":
        return digest
    if state == "pending":
        return None
    raise StartupSchedulingError(ERROR)


def _wait(target, deadline, recheck):
    while True:
        _remaining(deadline)
        recheck()
        _remaining(deadline)
        remaining = target - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(1.0, remaining, deadline - time.monotonic()))


def wait_for_stage(value, stage, *, deadline, recheck):
    """Wait for a matching successful public status, before role binding."""
    config = validate_deployment(value)
    _require(config is not None and stage in STAGES and callable(recheck))
    _remaining(deadline)
    observations = LISTENER_OBSERVATIONS if stage == "listener" else EXPORT_OBSERVATIONS
    prep = None
    if stage == "export":
        limits = value.get("limits")
        prep = limits.get("preparation_wait_seconds") if type(limits) is dict else None
        prep = value.get("preparation_wait_seconds") if prep is None else prep
        _require(type(prep) is int and 1 <= prep <= 1800)
    for index in range(observations):
        _remaining(deadline); recheck()
        result = _observe(_http(_status_endpoint(config.templates["capture"]), method="GET", deadline=deadline), config, stage)
        _remaining(deadline); recheck()
        if result is not None:
            _remaining(deadline)
            return result
        if index + 1 == observations:
            break
        delay = LISTENER_DELAY if stage == "listener" else EXPORT_DELAYS[min(index, len(EXPORT_DELAYS) - 1)]
        if prep is not None:
            delay = min(delay, prep / 2.0)
        _wait(min(deadline, time.monotonic() + delay), deadline, recheck)
    raise StartupSchedulingError(ERROR)


def _bound_matches(config, bound_roles):
    _require(type(bound_roles) is dict and set(bound_roles) == set(ROLES))
    for role in ROLES:
        policy, template = bound_roles[role], config.templates[role]
        _require(type(policy) is identity.WorkflowJobPolicy and identity._number(policy.check_run_id)
                 and all(getattr(policy, field) == getattr(template, field)
                         for field in template.__dataclass_fields__ if field != "check_run_id"))
    _require(len({bound_roles[role].check_run_id for role in ROLES}) == len(ROLES))


def _held_token(config, held_token):
    _require(held_token is not None and not isinstance(held_token, (str, bytes, Path))
             and callable(getattr(held_token, "read", None))
             and callable(getattr(held_token, "recheck", None)) and config.status_write_token is not None)
    _require(getattr(held_token, "path", None) is not None
             and str(held_token.path) == config.status_write_token)
    held_token.recheck()
    raw = held_token.read()
    _require(type(raw) is bytes and 1 <= len(raw) <= 4096)
    token = raw.decode("ascii")
    _require(all(33 <= ord(char) < 127 and not char.isspace() for char in token))
    return token


def publish_stage(value, stage, bound_roles, held_token, *, deadline, recheck):
    """Publish exactly one successful commit status for one owner event."""
    config = validate_deployment(value, owner=True)
    _require(config is not None and config.status_write_token is not None and stage in STAGES
             and callable(recheck))
    _bound_matches(config, bound_roles)
    body = _canonical({"state": "success", "target_url": _attempt_url(config.templates["capture"]),
                       "description": _description(binding_digest(bound_roles)), "context": _context(config, stage)})
    _require(len(body) <= MAX_POST_BYTES)
    _remaining(deadline); recheck()
    token = _held_token(config, held_token)
    response = _http(_status_url(config.templates["capture"]), method="POST", body=body, token=token, deadline=deadline)
    published = _json(response)
    updated, published_digest, state = _validate_status(
        published, config, _context(config, stage), _attempt_url(config.templates["capture"]),
        _status_url(config.templates["capture"]))
    _require(state == "success" and published_digest == binding_digest(bound_roles))
    held_token.recheck()
    recheck()
    _remaining(deadline)
