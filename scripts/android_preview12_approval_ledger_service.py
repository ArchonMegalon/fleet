"""Factory-only PR11 HTTP boundary; no app instance, credentials or deployment.

This does not load an approval key or prove protected signing custody. An
explicit service provisioner supplies an existing store, reviewed ledger policy,
bearer digest and receipt-signing capability. Nothing here creates a database.
"""
from __future__ import annotations

import asyncio
import base64
import copy
import hashlib
import hmac
import math
import re
import threading
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from starlette.responses import Response

from scripts import android_preview12_approval_ledger as protocol
from scripts import android_preview12_approval_ledger_store as persistence


_HEADER_NAME = re.compile(rb"[!#$%&'*+.^_`|~0-9a-z-]+\Z")
_BEARER = re.compile(rb"Bearer ([A-Za-z0-9._~+/-]+={0,})\Z")
_ERRORS = {
    400: b'{"error":"invalid_request"}',
    401: b'{"error":"unauthorized"}',
    403: b'{"error":"origin_rejected"}',
    404: b'{"error":"not_found"}',
    405: b'{"error":"method_not_allowed"}',
    408: b'{"error":"request_timeout"}',
    409: b'{"error":"conflict"}',
    413: b'{"error":"request_too_large"}',
    415: b'{"error":"unsupported_media_type"}',
    429: b'{"error":"capacity_unavailable"}',
    503: b'{"error":"service_unavailable"}',
}


class ServiceConfigurationError(ValueError):
    """Only fixed diagnostics; never expose injected configuration values."""


def _response(status: int, body: bytes | None = None) -> Response:
    return Response(
        _ERRORS[status] if body is None else body, status_code=status,
        media_type="application/json",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


class _HttpBoundary:
    """Raw ASGI header/path checks run before FastAPI or any body receive."""

    def __init__(self, app: Any, *, hostname: bytes, paths: dict[bytes, str], token_digest: bytes):
        self.app = app
        self.hostname = hostname
        self.paths = paths
        self.token_digest = token_digest

    def _check(self, scope: dict[str, Any]) -> tuple[int | None, str | None, int | None]:
        raw_path = scope.get("raw_path")
        if type(raw_path) is not bytes or raw_path not in self.paths \
                or scope.get("path") != raw_path.decode("ascii") or scope.get("root_path", "") != "":
            return 404, None, None
        if scope.get("method") != "POST":
            return 405, None, None
        if scope.get("scheme") != "https" or scope.get("query_string") != b"":
            return 400, None, None
        raw_headers = scope.get("headers")
        if not isinstance(raw_headers, (list, tuple)) or len(raw_headers) > 32:
            return 400, None, None
        headers: dict[bytes, bytes] = {}
        total = 0
        for pair in raw_headers:
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                return 400, None, None
            name, value = pair
            if type(name) is not bytes or type(value) is not bytes:
                return 400, None, None
            name = name.lower()
            total += len(name) + len(value)
            if total > 16384 or not _HEADER_NAME.fullmatch(name) or name in headers \
                    or any(character < 32 or character > 126 for character in value):
                return 400, None, None
            headers[name] = value
        if headers.get(b"host") != self.hostname:
            return 400, None, None
        if b"origin" in headers:
            return 403, None, None
        if any(name == b"forwarded" or name.startswith(b"x-forwarded-") for name in headers):
            return 400, None, None
        authorization = headers.get(b"authorization", b"")
        match = _BEARER.fullmatch(authorization) if len(authorization) <= 4103 else None
        if match is None or not hmac.compare_digest(hashlib.sha256(match[1]).digest(), self.token_digest):
            return 401, None, None
        if headers.get(b"content-type") != b"application/json" or b"content-encoding" in headers:
            return 415, None, None
        # PR11 sends known byte bodies. Do not accept alternate transfer framing.
        if b"transfer-encoding" in headers:
            return 400, None, None
        length = headers.get(b"content-length")
        declared = None
        if length is not None:
            if not re.fullmatch(rb"0|[1-9][0-9]{0,5}", length):
                return 400, None, None
            declared = int(length)
            if declared > 65536:
                return 413, None, None
        return None, self.paths[raw_path], declared

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        error, operation, declared = self._check(scope)
        if error is not None:
            await _response(error)(scope, receive, send)
            return
        scope = dict(scope)
        scope["ledger.operation"] = operation
        scope["ledger.length"] = declared
        await self.app(scope, receive, send)


async def _read_body(request: Request) -> tuple[int | None, bytes]:
    body = bytearray()
    async for chunk in request.stream():
        if type(chunk) is not bytes:
            return 400, b""
        if len(body) + len(chunk) > 65536:
            return 413, b""
        body.extend(chunk)
    declared = request.scope["ledger.length"]
    if not body or (declared is not None and declared != len(body)):
        return 400, b""
    return None, bytes(body)


def create_app(
    *, ledger_policy: Mapping[str, Any], store: persistence.SQLiteApprovalLedgerStore,
    bearer_token_sha256: str, sign_receipt: Callable[[bytes], bytes],
    maximum_in_flight: int = 2, body_timeout_seconds: float = 10.0,
) -> FastAPI:
    """Create only an explicitly bound app; no ambient or unconfigured mode.

    The token must be a high-entropy bearer provisioned independently. This
    factory retains its SHA256, not its bytes. Limits are local resource bounds,
    not a replacement policy dialect. A wedged signer keeps admission occupied;
    a request timeout never claims its thread stopped or its commit rolled back.
    """
    invalid = False
    try:
        policy = copy.deepcopy(protocol.validate_ledger_policy(ledger_policy, require_configured=True))
        if not isinstance(store, persistence.SQLiteApprovalLedgerStore) \
                or policy["expected_service_identity"] != store.service_identity \
                or type(bearer_token_sha256) is not str or not protocol.SHA256.fullmatch(bearer_token_sha256) \
                or not callable(sign_receipt) or type(maximum_in_flight) is not int \
                or not 1 <= maximum_in_flight <= 8 \
                or type(body_timeout_seconds) not in {int, float} \
                or not math.isfinite(body_timeout_seconds) or not 0 < body_timeout_seconds <= 10:
            invalid = True
    except Exception:
        invalid = True
    if invalid:
        raise ServiceConfigurationError("explicit ledger service configuration is invalid")

    admission = threading.BoundedSemaphore(maximum_in_flight)
    paths = {policy[operation + "_path"].encode("ascii"): operation
             for operation in ("reserve", "commit", "abort", "status")}

    def execute(raw: bytes, parsed: dict[str, Any]) -> tuple[int, bytes | None]:
        # Only this worker releases its admission after submission. Cancelling
        # the ASGI await cannot allow another worker while this one still runs.
        try:
            try:
                receipt_bytes = store.process(raw)
            except persistence.InvalidRequest:
                return 400, None
            except persistence.Conflict:
                return 409, None
            except persistence.NotFound:
                return 404, None
            if type(receipt_bytes) is not bytes or len(receipt_bytes) > policy["maximum_response_bytes"]:
                return 503, None
            receipt = protocol.strict_json_bytes(receipt_bytes, "ledger receipt", policy["maximum_response_bytes"])
            if protocol.canonical_bytes(receipt) != receipt_bytes:
                return 503, None
            signature = sign_receipt(receipt_bytes)
            if type(signature) is not bytes or len(signature) != 64:
                return 503, None
            envelope = {
                "contractName": protocol.RESPONSE_CONTRACT, "contractVersion": 1,
                "receipt": receipt, "receiptSha256": hashlib.sha256(receipt_bytes).hexdigest(),
                "signature": {
                    "algorithm": "Ed25519",
                    "publicKeySpkiSha256": policy["receipt_public_key_spki_sha256"],
                    "signatureBase64": base64.b64encode(signature).decode("ascii"),
                },
            }
            protocol.validate_response(envelope, request=parsed, policy=policy)
            result = protocol.canonical_bytes(envelope)
            return (200, result) if len(result) <= policy["maximum_response_bytes"] else (503, None)
        except BaseException:
            # No exception (including a provider's private sentinel) crosses the
            # worker boundary, gets logged, or becomes an exception chain.
            return 503, None
        finally:
            admission.release()

    async def handle(request: Request) -> Response:
        if not admission.acquire(blocking=False):
            return _response(429)
        submitted = False
        try:
            try:
                error, raw = await asyncio.wait_for(_read_body(request), timeout=body_timeout_seconds)
            except asyncio.TimeoutError:
                return _response(408)
            except asyncio.CancelledError:
                raise
            except Exception:
                return _response(400)
            if error is not None:
                return _response(error)
            try:
                parsed, _ = persistence._parse_request(raw)
            except persistence.InvalidRequest:
                return _response(400)
            if parsed["operation"] != request.scope["ledger.operation"]:
                return _response(400)
            try:
                future = asyncio.get_running_loop().run_in_executor(None, execute, raw, parsed)
            except Exception:
                return _response(503)
            submitted = True
            status, body = await asyncio.shield(future)
            return _response(status, body)
        finally:
            if not submitted:
                admission.release()

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, redirect_slashes=False)
    for path in paths:
        app.add_api_route(path.decode("ascii"), handle, methods=["POST"], response_model=None)
    app.add_middleware(
        _HttpBoundary, hostname=urlsplit(policy["base_url"]).hostname.encode("ascii"),
        paths=paths, token_digest=bytes.fromhex(bearer_token_sha256),
    )
    return app
