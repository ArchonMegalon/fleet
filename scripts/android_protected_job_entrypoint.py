"""Concrete one-shot job3 composition, called by the admitted hosted owner.

This is not a deployment loader or a new authority. The caller must already own
an actual ProtectedJobLauncher/client, their runtime, roots and policies. No
dictionary, imported factory, environment scan or detached artifact can replace
those objects. Only the existing remote RS256/SQLite admission authenticates the
returned token. Importing this module performs no I/O.
"""
from __future__ import annotations

import hashlib
from http.client import HTTPSConnection
import os
from pathlib import Path
import re
import ssl
import threading
import time
from urllib.parse import parse_qsl, urlencode, urlsplit

from scripts import android_artifact_origin as origin
from scripts import android_preview12_external_rebuilder as fleet
from scripts import android_protected_capture_intake as intake
from scripts import android_protected_job_launcher as launcher
from scripts import android_protected_job_worker as worker
from scripts import android_workflow_identity as identity

ERROR = "protected job entrypoint stopped; do not replay"
OIDC_SECONDS = 15
MAX_RESPONSE = identity.MAX_TOKEN + 16384


class EntrypointError(RuntimeError):
    """Constant message only; never credential, JWT, URL or upstream details."""


def _require(value):
    if not value:
        raise EntrypointError(ERROR)


def _endpoint(value):
    _require(type(value) is str and 0 < len(value) <= 8192
             and not re.search(r"[\x00-\x20\x7f]", value))
    parsed = urlsplit(value)
    _require(parsed.scheme == "https" and parsed.hostname is not None
             and re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)*\.actions\.githubusercontent\.com", parsed.hostname)
             and parsed.netloc in {parsed.hostname, parsed.hostname + ":443"}
             and parsed.port in (None, 443) and not parsed.username and not parsed.password
             and not parsed.fragment and parsed.path.startswith("/") and parsed.path != "/")
    query = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True, max_num_fields=32)
    _require(all(key.lower() != "audience" for key, _ in query))
    return parsed, query


def _tls(context):
    _require(type(context) is ssl.SSLContext and context.check_hostname
             and context.verify_mode == ssl.CERT_REQUIRED
             and context.minimum_version >= ssl.TLSVersion.TLSv1_2)


def _request_token(endpoint, credential, audience, tls_context):
    """One direct HTTPS GET; no proxy, redirect, retry, decoding or token log.

    Socket/between-call elapsed limits are not a hard whole-request deadline:
    DNS and trickled header/chunk parsing can exceed it. The admitted owner must
    supervise the entire job. Interrupted reads and other exceptions are
    replaced at the entrypoint boundary without rendering upstream text.
    """
    parsed, query = _endpoint(endpoint)
    _tls(tls_context)
    _require(identity._text(credential, 16384) and not re.search(r"\s", credential))
    target = parsed.path + "?" + urlencode(query + [("audience", audience)])
    deadline = time.monotonic() + OIDC_SECONDS
    connection = HTTPSConnection(parsed.hostname, port=443, timeout=OIDC_SECONDS, context=tls_context)
    try:
        connection.request("GET", target, headers={"Authorization": "Bearer " + credential,
            "Accept": "application/json", "User-Agent": "fleet-protected-job-entrypoint"})
        active_socket = connection.sock
        remaining = deadline - time.monotonic()
        _require(remaining > 0)
        active_socket.settimeout(remaining)
        response = connection.getresponse()
        headers = response.getheaders()
        names = [key.lower() for key, _ in headers]
        _require(response.status == 200 and len(headers) <= 64 and len(set(names)) == len(names)
                 and sum(len(key) + len(value) + 4 for key, value in headers) <= 16384)
        fields = dict((key.lower(), value) for key, value in headers)
        _require(re.fullmatch(r"application/json(?:;\s*charset=utf-8)?", fields.get("content-type", ""), re.I)
                 and "content-encoding" not in fields and "link" not in fields)
        length, transfer = fields.get("content-length"), fields.get("transfer-encoding")
        _require(transfer in (None, "chunked") and not (transfer and length is not None))
        if length is not None:
            _require(re.fullmatch(r"[1-9][0-9]{0,7}", length) and int(length) <= MAX_RESPONSE)
        raw = bytearray()
        while True:
            remaining = deadline - time.monotonic()
            _require(remaining > 0)
            active_socket.settimeout(remaining)
            chunk = response.read1(min(4096, MAX_RESPONSE + 1 - len(raw)))
            _require(time.monotonic() < deadline)
            if not chunk:
                break
            raw.extend(chunk)
            _require(len(raw) <= MAX_RESPONSE)
        _require(raw and (length is None or len(raw) == int(length)))
        value = identity._json(bytes(raw))
        # GitHub's API may include other response metadata. Bound and discard it;
        # neither it nor unverified JWT claims are authentication here.
        token = value.get("value")
        _require(identity._text(token, identity.MAX_TOKEN)
                 and re.fullmatch(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", token))
        return token
    finally:
        connection.close()


class ProtectedJobEntrypoint:
    """Prepare before owner arm; execute one genuine hosted job3 intake/sign.

    Existing launcher construction must have completed its key-free validation.
    The outer deployment bootstrap is still required; this deliberately does not
    deserialize policies/custody or discover endpoints, keys or secret paths.
    """

    def __init__(self, owned_launcher, *, verifier, trusted_root, oidc_tls_context):
        self._mutex, self._attempted = threading.Lock(), False
        self.captured = None
        try:
            _require(type(owned_launcher) is launcher.ProtectedJobLauncher
                     and os.getuid() == os.geteuid() == 0)
            self._owner, self._client = owned_launcher, owned_launcher.connection
            _require(type(self._client) is intake.PublicCaptureClient
                     and type(owned_launcher.persistent) is launcher.RecoveryMount
                     and type(owned_launcher.validation) is fleet.PreservedProtectedValidation)
            _require(owned_launcher.config["mode"] == "execute"
                     and self._client._job.environment == "android-preview12-release-builder")
            self._config = fleet._canonical_json(owned_launcher.config)
            self._lock_raw = owned_launcher.lock_raw
            self._job, self._origin = self._client._job, self._client._policy
            self._persistent, self._validation = owned_launcher.persistent, owned_launcher.validation
            self._packet = Path(owned_launcher.config["handoff"]).parent
            _require(owned_launcher.config["handoff"] == str(self._packet / "preserved"))
            self._lock = origin.PinnedFile(owned_launcher.lock_path, hashlib.sha256(self._lock_raw).hexdigest())
            self._verifier, self._trusted_root = verifier, trusted_root
            _require(type(verifier) is origin.PinnedFile and type(trusted_root) is origin.PinnedFile)
            self._pins = (origin._capture(self._lock, 1024 * 1024),
                          origin._capture(verifier, 256 * 1024 * 1024, executable=True),
                          origin._capture(trusted_root, 16 * 1024 * 1024))
            self._tls = oidc_tls_context
            _tls(self._tls)
            self._preflight()
        except BaseException:
            raise EntrypointError(ERROR) from None

    def _preflight(self):
        own, client = self._owner, self._client
        _require(own.connection is client and not own.used and not client._failed
                 and not client._begun and client._intake is None
                 and not getattr(client, "_host_entrypoint_claimed", False)
                 and own.persistent is self._persistent and own.validation is self._validation
                 and fleet._canonical_json(own.config) == self._config
                 and own.lock_raw == self._lock_raw and client._job == self._job and client._policy == self._origin
                 and own.config["attempt"] == client._job.transaction_id)
        current, raw = fleet.load_lock(own.lock_path)
        _require(raw == self._lock_raw and current == own.lock and not fleet.validate_lock(current, raw))
        for value in self._pins:
            value.recheck()
        _require(worker.code_inputs(own.root, own.config["code_pins"]) == own.pins)
        _require(own.validation._capture_inputs() == own.validation._bindings)
        own.persistent.assert_exact()
        own.tool.recheck()
        intake._root_directory(self._packet.parent)
        _require(self._packet.is_absolute() and self._packet.resolve(strict=False) == self._packet
                 and not os.path.lexists(self._packet))
        _tls(self._tls)

    def run(self, *, oidc_request_url, oidc_request_credential, preparation_wait_seconds=0):
        """Explicit job-injected request inputs; no ambient environment default.

        Return the launcher's actual audit unchanged. Keep captured custody for
        explicit owner cleanup; never automatically erase/unmount partial work.
        Even a failed/ambiguous request cannot be retried on this client.
        """
        with self._mutex:
            _require(not self._attempted)
            self._attempted = True
        claimed = False
        try:
            # Invalid or absent job request inputs reject before even challenge.
            _endpoint(oidc_request_url)
            _require(identity._text(oidc_request_credential, 16384)
                     and not re.search(r"\s", oidc_request_credential))
            _require(type(preparation_wait_seconds) is int and 0 <= preparation_wait_seconds <= 1800)
            with self._client._mutex:
                self._preflight()
                # Pair-wide latch, not an authority bit. Release the mutex before
                # launch: its broker/heartbeat must use the same live client.
                self._client._host_entrypoint_claimed = True
                claimed = True
            audience = self._client.challenge(preparation_wait_seconds=preparation_wait_seconds)
            # Cheap identity/state fences after a possibly long pending wait.
            # Full source/tool gates still run at their original launch points.
            _require(self._owner.connection is self._client and not self._owner.used
                     and not self._client._failed and not self._client._begun
                     and self._client._host_entrypoint_claimed
                     and self._client._job == self._job and self._client._policy == self._origin
                     and fleet._canonical_json(self._owner.config) == self._config)
            _require(re.fullmatch(r"urn:chummer:fleet:workflow-job:" + self._job.transaction_id
                                 + r":[0-9a-f]{64}", audience))
            token = _request_token(oidc_request_url, oidc_request_credential, audience, self._tls)
            self._client.begin(token)  # Existing real RS256/Jobs API/SQLite authority.
            del token
            self.captured = self._client.receive(self._packet, lock=self._lock,
                verifier=self._verifier, trusted_root=self._trusted_root)
            _require(self._owner.connection is self._client and self._client._intake is self.captured
                     and self.captured.connection is self._client
                     and fleet._canonical_json(self._owner.config) == self._config)
            for value in self._pins:
                value.recheck()
            # launch enforces current source/lock/runtime/freshness again. No
            # locally decoded claims, detached receipt or callback supplies it.
            return self._owner.launch(self.captured)
        except BaseException:
            raise EntrypointError(ERROR) from None
        finally:
            # A competing preconstructed wrapper must not revoke the owner
            # which already claimed this client and may be mid-exchange.
            if claimed:
                self._client.close()
