"""Fixed-attempt capture/emission transport; no listener, provisioning or authority.

An independently admitted owner opens the existing journal, supplies exact
policies and distinct role credential digests, then arms each action in process.
HTTP cannot select policy, supply custody, renew a challenge or resume an attempt.
The emitter below exchanges actual public manifest/bundle bytes, not a callback
selected by a request. TLS/runtime/role-secret custody remain deployment inputs.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import hashlib
import hmac
import http.client
import ipaddress
import os
from pathlib import Path
import re
import ssl
import threading
import time
from urllib.parse import urlsplit

from scripts import android_artifact_origin as origin
from scripts import android_builder_handoff as capture
from scripts import android_container_runtime as runtime
from scripts import android_controller_capture as controller
from scripts import android_preview12_external_rebuilder as fleet
from scripts import android_workflow_challenge_store as journal
from scripts import android_workflow_identity as identity

MAX_BUNDLE = MAX_MANIFEST = 8 * 1024 * 1024
_BEARER = re.compile(rb"Bearer ([A-Za-z0-9._~+/-]+={0,})\Z")
_HEADER = re.compile(rb"[!#$%&'*+.^_`|~0-9a-z-]+\Z")
_MARKER = b"Interrupted attempts require reconciliation; never replay.\n"
_STATES = {"unarmed", "capture-ready", "capture-queued", "capture-complete",
           "emission-ready", "emission-queued", "awaiting-bundle", "verifying", "complete", "stopped"}


class RendezvousError(RuntimeError):
    """Constant diagnostics only; never tokens, credentials or remote content."""


def _require(value, code="rendezvous-admission"):
    if not value:
        raise RendezvousError(code)


def _hostname(base_url):
    _require(type(base_url) is str and len(base_url) <= 253)
    host = urlsplit(base_url).hostname
    _require(host is not None and re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)*", host)
             and base_url == "https://" + host)
    return host


def _write_new(path, raw):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    journal._sync_directory(path.parent)
    journal._file(path)


@dataclass(frozen=True, slots=True)
class CaptureInputs:
    policy: runtime.RuntimePolicy
    docker: origin.PinnedFile
    lock: origin.PinnedFile
    operation_directory: Path
    output_bind_target: str
    handoff_child_name: str


class ControllerRendezvous:
    """Owner-only assembly; one executor, no action retry or reconstructed session.

    ``attempt_directory`` is a separate, initially absent private directory,
    never the builder's also-initially-absent operation directory. Its durable
    marker is diagnostic custody, not an authentication/receipt dialect.
    """

    def __init__(self, *, journal_path: Path, controller_id: str, database_id: str,
                 capture_policy: identity.WorkflowJobPolicy, emission_policy: identity.WorkflowJobPolicy,
                 artifact_policy: origin.OriginPolicy, preserved_directory: Path,
                 inputs: CaptureInputs, attempt_directory: Path, verifier: origin.PinnedFile,
                 trusted_root: origin.PinnedFile, base_url: str, capture_bearer_sha256: str,
                 emission_bearer_sha256: str, approval_bearer_sha256: str, binary_bearer_sha256: str):
        self._condition = threading.Condition(threading.RLock())
        self._state, self._stopped = "unarmed", False
        self._capture_armed = self._emission_armed = self._bundle_claimed = False
        self._session = self._retained = self._facts = self._bundle = self._result = None
        self._issued_capture = self._issued_emission = None
        self._manifest = None
        try:
            self.hostname = _hostname(base_url)
            digests = (capture_bearer_sha256, emission_bearer_sha256, approval_bearer_sha256, binary_bearer_sha256)
            _require(all(identity._hex(value, 64) for value in digests) and len(set(digests)) == 4)
            _require(type(inputs) is CaptureInputs and type(inputs.policy) is runtime.RuntimePolicy
                     and inputs.policy.process_role == "builder" and type(inputs.docker) is origin.PinnedFile
                     and type(inputs.lock) is origin.PinnedFile)
            inputs.policy.__post_init__()
            # Validate the complete job relation before creating any attempt or challenge.
            store = journal.SQLiteWorkflowChallengeStore(journal_path, controller_id=controller_id, database_id=database_id)
            controller.ControllerCaptureSession(store, capture_policy, emission_policy, artifact_policy, preserved_directory)
            origin._capture(verifier, 256 * 1024 * 1024, executable=True)
            origin._capture(trusted_root, 16 * 1024 * 1024)
            lock = origin._capture(inputs.lock, 1024 * 1024)
            self._manifest_limit = capture._limits(fleet._strict_json(lock.raw, "rendezvous lock"))[capture.MANIFEST]
            _require(0 < self._manifest_limit <= MAX_MANIFEST)
            _require(type(attempt_directory) is type(Path()) and attempt_directory.is_absolute()
                     and attempt_directory.resolve(strict=False) == attempt_directory)
            journal._parent(attempt_directory)  # Require a private owner-controlled parent.
            for other in (inputs.operation_directory, preserved_directory,
                          *(Path(bind.source) for bind in inputs.policy.binds)):
                _require(other != attempt_directory and other not in attempt_directory.parents
                         and attempt_directory not in other.parents)
            _require(not os.path.lexists(inputs.operation_directory))
            os.mkdir(attempt_directory, 0o700)  # Never reuse, repair or remove a failed attempt.
            journal._sync_directory(attempt_directory.parent)
            _write_new(attempt_directory / "no-replay", _MARKER)
            self._parents = journal._parent(attempt_directory / "bundle.json")
            self._marker = origin._capture(origin.PinnedFile(attempt_directory / "no-replay",
                hashlib.sha256(_MARKER).hexdigest()), len(_MARKER))
            self._store, self._inputs = store, inputs
            self._capture_policy, self._emission_policy = capture_policy, emission_policy
            self._artifact_policy, self._preserved_directory = artifact_policy, preserved_directory
            self._directory, self._verifier, self._trusted_root = attempt_directory, verifier, trusted_root
            self._digests = dict(zip(("capture", "emission"), (bytes.fromhex(value) for value in digests[:2])))
            self.prefix = "/android-controller/" + capture_policy.transaction_id
            self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="fixed-controller-attempt")
        except BaseException:
            raise RendezvousError("rendezvous-admission-failed-no-reset") from None

    def _exact(self):
        _require(not self._stopped, "rendezvous-stopped")
        _require(journal._parent(self._directory / "bundle.json") == self._parents, "attempt-custody-drift")
        journal._file(self._directory / "no-replay")
        self._marker.recheck()

    def _fail(self):
        with self._condition:
            self._stopped, self._state = True, "stopped"
            self._condition.notify_all()

    def close(self):
        """Stop admission; a running Python worker is NOT claimed terminated."""
        self._fail()
        self._executor.shutdown(wait=False, cancel_futures=True)

    def arm_capture(self):
        """Owner-only operation; never exposed as an HTTP route."""
        with self._condition:
            _require(not self._capture_armed, "capture-already-armed")
            self._capture_armed = True  # issue() may commit and then fail.
            try:
                self._exact()
                self._issued_capture = self._store.issue(self._capture_policy)
                self._session = controller.ControllerCaptureSession(self._store, self._issued_capture,
                    self._emission_policy, self._artifact_policy, self._preserved_directory)
                self._state = "capture-ready"
            except BaseException:
                self._fail()
                raise RendezvousError("capture-arm-failed-no-retry") from None

    def arm_emission(self, retained: fleet.PreservedRebuildHandoff):
        """Owner custodian supplies the ACTUAL existing object, never HTTP flags."""
        with self._condition:
            _require(not self._emission_armed and self._state == "capture-complete", "emission-not-armable")
            self._emission_armed = True
            try:
                self._exact()
                self._session._retained(retained)  # Includes actual root-owned RO and all seven file checks.
                self._retained = retained
                self._issued_emission = self._store.issue(self._emission_policy)
                self._state = "emission-ready"
            except BaseException:
                self._fail()
                raise RendezvousError("emission-arm-failed-no-retry") from None

    def _fresh(self, issued):
        _require(issued is not None and issued.challenge_issued_at <= int(time.time()) < issued.challenge_expires_at,
                 "challenge-not-fresh")

    def _emission_exact(self):
        self._exact()
        self._store._match(self._facts, self._issued_emission, int(time.time()))
        self._retained.assert_exact()
        self._store._match(self._facts, self._issued_emission, int(time.time()))

    def _run(self, role, token):
        try:
            with self._condition:
                self._exact()
            if role == "capture":
                value = self._inputs
                self._session.capture(token, policy=value.policy, docker=value.docker, lock=value.lock,
                    operation_directory=value.operation_directory, output_bind_target=value.output_bind_target,
                    handoff_child_name=value.handoff_child_name)
                with self._condition:
                    self._exact()
                    self._state = "capture-complete"
                    self._condition.notify_all()
            else:
                result = self._session.emit(self._issued_emission, token, self._retained,
                    emitter=self._emit, verifier=self._verifier, trusted_root=self._trusted_root)
                with self._condition:
                    self._emission_exact()
                    self._result, self._state = result, "complete"
                    self._condition.notify_all()
        except BaseException:
            self._fail()  # No private exception or traceback retained in the future.

    def _emit(self, retained, facts):
        # Called only by the real authenticated session. Its mutex is occupied;
        # HTTP intake must not use that mutex or this executor while we wait.
        with self._condition:
            _require(retained is self._retained and self._state == "emission-queued", "emitter-state")
            self._facts = facts
            self._emission_exact()
            self._manifest = origin._capture(origin.PinnedFile(retained.artifact_subject_path,
                self._artifact_policy.subject_sha256), self._manifest_limit)
            self._state = "awaiting-bundle"
            self._condition.notify_all()
            while self._bundle is None:
                self._exact()
                self._store._match(facts, self._issued_emission, int(time.time()))
                remaining = facts.valid_until - time.time()
                _require(remaining > 0, "emitter-expired")
                self._condition.wait(min(remaining, 1.0))  # Releases adapter lock for upload.
            self._emission_exact()
            self._manifest.recheck()
            self._bundle.recheck()
            self._state = "verifying"
            return self._bundle.pin

    def exchange(self, role, operation, raw):
        """Internal dispatch AFTER the fixed HTTPS/bearer/framing boundary."""
        with self._condition:
            try:
                self._exact()
                _require(role in {"capture", "emission"} and type(raw) is bytes)
                if operation == "status" and not raw:
                    return 200, (self._state + "\n").encode()
                if operation == "challenge" and not raw:
                    if self._state == role + "-ready":
                        issued = self._issued_capture if role == "capture" else self._issued_emission
                        self._fresh(issued)
                        return 200, issued.audience.encode("ascii")
                    return (200, b"pending\n") if self._state in {"unarmed", "capture-ready", "capture-queued", "capture-complete"} else (409, b"conflict\n")
                if operation == "submit":
                    if self._state != role + "-ready":
                        return 409, b"conflict\n"
                    _require(0 < len(raw) <= identity.MAX_TOKEN and all(32 <= byte < 127 for byte in raw), "token-shape")
                    self._fresh(self._issued_capture if role == "capture" else self._issued_emission)
                    self._state = role + "-queued"  # Irreversible before executor submission.
                    self._executor.submit(self._run, role, raw.decode("ascii"))
                    return 202, b"queued-not-authenticated\n"
                if role == "emission" and operation == "manifest" and not raw:
                    if self._state == "emission-queued":
                        return 200, b"pending\n"
                    if self._state != "awaiting-bundle":
                        return 409, b"conflict\n"
                    self._emission_exact()
                    self._manifest.recheck()
                    self._store._match(self._facts, self._issued_emission, int(time.time()))
                    return 200, self._manifest.raw
                if role == "emission" and operation == "bundle":
                    if self._state != "awaiting-bundle" or self._bundle_claimed:
                        return 409, b"conflict\n"
                    self._bundle_claimed = True  # A failed/partial write is never replayed.
                    self._emission_exact()
                    _require(0 < len(raw) <= MAX_BUNDLE, "bundle-bound")
                    origin._json(raw)
                    path = self._directory / "bundle.json"
                    _write_new(path, raw)
                    self._emission_exact()
                    self._bundle = origin._capture(origin.PinnedFile(path, hashlib.sha256(raw).hexdigest()), MAX_BUNDLE)
                    self._condition.notify_all()
                    return 202, b"received-not-verified\n"
                return 404, b"not-found\n"
            except BaseException:
                self._fail()
                return 409, b"stopped-reconcile\n"

    def completed(self):
        """Owner-only access to existing ordinary ControllerEmission facts."""
        with self._condition:
            self._exact()
            _require(self._state == "complete" and type(self._result) is controller.ControllerEmission, "not-complete")
            self._retained.assert_exact()
            return self._result


class _FixedApp:
    """Raw ASGI factory product, no listener. Two bounded readers, one action worker.

    Follows the existing ledger's verified-TLS/exact-Host/bearer boundary. Proxy
    metadata is allowed only from explicit local TLS peers and is never identity.
    Infrastructure must disable proxy rewriting/access logs and supervise stalls.
    """

    def __init__(self, controller, routes, *, trusted_proxy_addresses=(), body_limits=None):
        networks = tuple(ipaddress.ip_network(value) for value in
            ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8", "fc00::/7", "::1/128"))
        _require(type(trusted_proxy_addresses) is tuple and len(trusted_proxy_addresses) <= 4)
        try:
            _require(len(set(trusted_proxy_addresses)) == len(trusted_proxy_addresses))
            for value in trusted_proxy_addresses:
                address = ipaddress.ip_address(value)
                _require(type(value) is str and str(address) == value and "%" not in value
                         and any(address in network for network in networks))
        except (ValueError, TypeError):
            raise RendezvousError("proxy-admission") from None
        self._controller, self._peers = controller, trusted_proxy_addresses
        self._readers = threading.BoundedSemaphore(2)
        self._routes = dict(routes)
        self._body_limits = dict(body_limits or {})

    def _check(self, scope):
        path = scope.get("raw_path")
        if type(path) is not bytes or path not in self._routes or scope.get("path") != path.decode() \
                or scope.get("root_path", "") != "" or scope.get("query_string") != b"":
            return 404, None
        if scope.get("method") != "POST" or scope.get("scheme") != "https":
            return 400, None
        rows = scope.get("headers")
        if type(rows) not in {list, tuple} or len(rows) > 32:
            return 400, None
        headers, total = {}, 0
        for pair in rows:
            if type(pair) not in {list, tuple} or len(pair) != 2 or any(type(v) is not bytes for v in pair):
                return 400, None
            name, value = pair[0].lower(), pair[1]
            total += len(name) + len(value)
            if total > 16384 or not _HEADER.fullmatch(name) or name in headers or any(c < 32 or c > 126 for c in value):
                return 400, None
            headers[name] = value
        if headers.get(b"host") != self._controller.hostname.encode() or b"origin" in headers:
            return 400, None
        forwarded = {name for name in headers if name == b"forwarded" or name.startswith(b"x-forwarded-")}
        if self._peers:
            peer = scope.get("client")
            if type(peer) not in {list, tuple} or len(peer) != 2 or peer[0] not in self._peers \
                    or type(peer[1]) is not int or not 0 < peer[1] <= 65535 \
                    or forwarded != {b"x-forwarded-for", b"x-forwarded-proto"} \
                    or headers.get(b"x-forwarded-proto") != b"https" \
                    or not 0 < len(headers.get(b"x-forwarded-for", b"")) <= 1024 \
                    or not headers[b"x-forwarded-for"].strip():
                return 400, None
        elif forwarded:
            return 400, None
        role, action = self._routes[path]
        bearer = headers.get(b"authorization", b"")
        match = _BEARER.fullmatch(bearer) if len(bearer) <= 4103 else None
        if match is None or not hmac.compare_digest(hashlib.sha256(match[1]).digest(), self._controller._digests[role]):
            return 401, None
        if headers.get(b"content-type") != b"application/octet-stream" or b"content-encoding" in headers \
                or b"transfer-encoding" in headers:
            return 400, None
        limit = self._body_limits.get(action,
            MAX_BUNDLE if action == "bundle" else identity.MAX_TOKEN if action == "submit" else 0)
        length = headers.get(b"content-length", b"")
        if not re.fullmatch(rb"0|[1-9][0-9]{0,7}", length) or int(length) > limit:
            return 413, None
        return None, (role, action, int(length), limit)

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        if scope.get("type") != "http":
            raise RendezvousError("http-only-owner-managed-lifecycle")
        status, request = self._check(scope)
        body = b"rejected\n"
        if status is None:
            if not self._readers.acquire(blocking=False):
                status = 429
            else:
                try:
                    async def read():
                        raw = bytearray()
                        while True:
                            item = await receive()
                            _require(item.get("type") == "http.request" and type(item.get("body", b"")) is bytes, "body-disconnected")
                            chunk = item.get("body", b"")
                            _require(len(raw) + len(chunk) <= min(request[2], request[3]), "body-bound")
                            raw.extend(chunk)
                            if not item.get("more_body", False):
                                break
                            await asyncio.sleep(0)  # Empty/immediate fragments cannot starve the deadline.
                        _require(len(raw) == request[2], "body-length")
                        return bytes(raw)
                    raw = await asyncio.wait_for(read(), timeout=10)
                    status, body = self._controller.exchange(request[0], request[1], raw)
                except asyncio.CancelledError:
                    raise  # No action is retried or cancelled by a disconnected HTTP await.
                except Exception:
                    status = 400
                finally:
                    self._readers.release()
        await send({"type": "http.response.start", "status": status, "headers": [
            (b"content-type", b"application/octet-stream"), (b"content-length", str(len(body)).encode()),
            (b"cache-control", b"no-store"), (b"x-content-type-options", b"nosniff")]})
        await send({"type": "http.response.body", "body": body})


class RendezvousApp(_FixedApp):
    """The original two-role boundary; private transport reuse adds no roles."""

    def __init__(self, controller: ControllerRendezvous, *, trusted_proxy_addresses=()):
        _require(type(controller) is ControllerRendezvous)
        routes = {(controller.prefix + "/" + role + "/" + action).encode(): (role, action)
            for role in ("capture", "emission") for action in
            (("challenge", "submit", "status") if role == "capture" else ("challenge", "submit", "status", "manifest", "bundle"))}
        super().__init__(controller, routes, trusted_proxy_addresses=trusted_proxy_addresses)


class HostedClient:
    """Explicit hosted-side exchanges; no ambient credentials, proxies or retry.

    The admitted workflow obtains actual OIDC using the returned audience, runs
    its independently SHA-pinned attestation action, then submits that real
    bundle. This class neither generates nor authenticates a substitute token.
    """

    def __init__(self, *, base_url: str, transaction_id: str, role: str, bearer: str,
                 manifest_sha256: str, tls_context: ssl.SSLContext):
        self._host = _hostname(base_url)
        _require(identity._hex(transaction_id, 64) and identity._hex(manifest_sha256, 64)
                 and role in {"capture", "emission"} and type(bearer) is str
                 and 32 <= len(bearer) <= 4096 and all(32 <= ord(c) < 127 for c in bearer)
                 and _BEARER.fullmatch(("Bearer " + bearer).encode("ascii"))
                 and type(tls_context) is ssl.SSLContext and tls_context.check_hostname
                 and tls_context.verify_mode == ssl.CERT_REQUIRED)
        self._prefix, self._role = "/android-controller/" + transaction_id + "/" + role + "/", role
        self._bearer, self._manifest_sha = bearer, manifest_sha256
        self._transaction, self._submitted, self._bundle_submitted = transaction_id, False, False
        self._tls = tls_context  # Independently admitted CA/process environment, never a remote input.

    def _post(self, action, body=b"", limit=4096):
        connection = None
        try:
            deadline = time.monotonic() + 10
            _require(self._tls.check_hostname and self._tls.verify_mode == ssl.CERT_REQUIRED, "tls-admission-drift")
            connection = http.client.HTTPSConnection(self._host, timeout=10, context=self._tls)
            connection.request("POST", self._prefix + action, body=body, headers={
                "Authorization": "Bearer " + self._bearer, "Content-Type": "application/octet-stream",
                "Content-Length": str(len(body)), "Host": self._host})
            active_socket = connection.sock  # HTTP/1.0 may detach it from the connection after headers.
            remaining = deadline - time.monotonic()
            _require(remaining > 0, "response-deadline")
            active_socket.settimeout(remaining)
            response = connection.getresponse()
            headers = response.getheaders()
            names = [name.lower() for name, _ in headers]
            _require(len(headers) <= 32 and len(set(names)) == len(names)
                     and sum(len(k) + len(v) for k, v in headers) <= 16384, "response-headers")
            fields = dict((k.lower(), v) for k, v in headers)
            _require(fields.get("content-type") == "application/octet-stream"
                     and "content-encoding" not in fields and "transfer-encoding" not in fields
                     and re.fullmatch(r"0|[1-9][0-9]{0,7}", fields.get("content-length", "")), "response-framing")
            length = int(fields["content-length"])
            _require(length <= limit and response.status in {200, 202}, "response-rejected-no-retry")
            raw = bytearray()
            while len(raw) < length:
                remaining = deadline - time.monotonic()
                _require(remaining > 0, "response-deadline")
                active_socket.settimeout(remaining)
                chunk = response.read1(min(65536, length - len(raw)))
                _require(chunk, "response-truncated")
                raw.extend(chunk)
            _require(time.monotonic() < deadline, "response-deadline")
            return response.status, bytes(raw)
        except Exception:
            raise RendezvousError("hosted-exchange-failed-no-retry") from None
        finally:
            if connection is not None:
                connection.close()

    def challenge(self):
        status, raw = self._post("challenge")
        if (status, raw) == (200, b"pending\n"):
            return None
        _require(status == 200 and re.fullmatch(
            rb"urn:chummer:fleet:workflow-job:" + self._transaction.encode() + rb":[0-9a-f]{64}", raw), "challenge-response")
        return raw.decode("ascii")

    def submit(self, token):
        _require(not self._submitted, "hosted-action-already-submitted")
        self._submitted = True
        _require(identity._text(token, identity.MAX_TOKEN), "hosted-token-shape")
        _require(self._post("submit", token.encode()) == (202, b"queued-not-authenticated\n"), "queue-response")

    def status(self):
        status, raw = self._post("status")
        _require(status == 200 and all(0 <= byte < 128 for byte in raw)
                 and raw.decode("ascii").removesuffix("\n") in _STATES, "status-response")
        return raw.decode("ascii").removesuffix("\n")

    def save_manifest(self, directory: Path):
        _require(self._role == "emission", "emission-client-required")
        status, raw = self._post("manifest", limit=MAX_MANIFEST)
        if (status, raw) == (200, b"pending\n"):
            return None
        _require(status == 200 and hashlib.sha256(raw).hexdigest() == self._manifest_sha, "manifest-response")
        path = directory / capture.MANIFEST
        parents = journal._parent(path)
        _write_new(path, raw)
        _require(journal._parent(path) == parents, "hosted-directory-drift")
        pin = origin.PinnedFile(path, self._manifest_sha)
        origin._capture(pin, MAX_MANIFEST)
        return pin

    def submit_bundle(self, bundle: origin.PinnedFile):
        _require(self._role == "emission" and not self._bundle_submitted, "bundle-already-submitted")
        self._bundle_submitted = True
        snapshot = origin._capture(bundle, MAX_BUNDLE)
        try:
            _require(self._post("bundle", snapshot.raw) == (202, b"received-not-verified\n"), "bundle-response")
        finally:
            snapshot.recheck()
