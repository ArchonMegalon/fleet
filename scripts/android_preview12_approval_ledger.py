#!/usr/bin/env python3
"""Durable exactly-once ledger client for the dormant Preview12 approval lane.

The client talks only to one reviewed HTTPS origin, authenticates with an
environment-only bearer credential, and accepts only Ed25519-signed, strict,
bounded response receipts from the reviewed service identity.  It never signs
an Android artifact and never contacts Google Play.
"""

from __future__ import annotations

import argparse
import base64
import binascii
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import ssl
import stat
import subprocess
import tempfile
import time
from typing import Any, Callable, Mapping, Protocol
import urllib.error
import urllib.parse
import urllib.request


LEDGER_POLICY_CONTRACT = "fleet.android_preview12_approval_ledger_policy.v1"
SUBJECT_CONTRACT = "fleet.android_preview12_approval_ledger_subject.v1"
REQUEST_CONTRACT = "fleet.android_preview12_approval_ledger_request.v1"
RECEIPT_CONTRACT = "fleet.android_preview12_approval_ledger_receipt.v1"
RESPONSE_CONTRACT = "fleet.android_preview12_approval_ledger_response.v1"
PACKAGE_ID = "com.myexternalbrain.chummer"
VERSION_NAME = "0.1.0-preview.12"
VERSION_CODE = 12
CREDENTIAL_ENV_NAME = "ANDROID_PREVIEW12_APPROVAL_LEDGER_BEARER_TOKEN"
SPKI_ED25519_PREFIX = bytes.fromhex("302a300506032b6570032100")
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
SERVICE_ID = re.compile(r"^[a-z][a-z0-9._-]{2,127}$")
HOSTNAME = re.compile(r"^[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?$")
RESERVATION_ID = re.compile(r"^rsv_[A-Za-z0-9_-]{16,128}$")
MAX_APPROVAL_BYTES = 32 * 1024
MAX_LEDGER_RESPONSE_BYTES = 256 * 1024
UNIQUENESS_SUBJECTS = ["approvalRequestNonce", "twoGreenArtifactId"]
TRANSIENT_STATUSES = {408, 425, 429, 500, 502, 503, 504}


class LedgerError(RuntimeError):
    """One fail-closed durable-ledger contract violation."""


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, allow_nan=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def pretty_bytes(value: object) -> bytes:
    return (json.dumps(value, allow_nan=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _strict_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    output: dict[str, object] = {}
    for key, value in pairs:
        if key in output:
            raise LedgerError(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def strict_json_bytes(data: bytes, label: str, limit: int) -> dict[str, Any]:
    if not data or len(data) > limit:
        raise LedgerError(f"{label} is not bounded")
    try:
        value = json.loads(
            data.decode("utf-8", errors="strict"),
            object_pairs_hook=_strict_pairs,
            parse_constant=lambda token: (_ for _ in ()).throw(
                LedgerError(f"non-finite JSON value in {label}: {token}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise LedgerError(f"{label} is not strict UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise LedgerError(f"{label} must contain one JSON object")
    return value


def stable_file(path: Path, label: str, limit: int) -> tuple[bytes, str]:
    if not path.is_absolute() or path.is_symlink() or path.resolve(strict=True) != path:
        raise LedgerError(f"{label} must be an absolute canonical non-symlink file")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_size <= 0 or before.st_size > limit:
            raise LedgerError(f"{label} is not one bounded regular file")
        data = bytearray()
        while chunk := os.read(descriptor, min(64 * 1024, limit + 1 - len(data))):
            data.extend(chunk)
            if len(data) > limit:
                raise LedgerError(f"{label} exceeds its byte limit")
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    identity = lambda item: (
        item.st_dev, item.st_ino, item.st_mode, item.st_size,
        item.st_mtime_ns, item.st_ctime_ns,
    )
    if identity(before) != identity(after) or len(data) != before.st_size:
        raise LedgerError(f"{label} changed during capture")
    captured = bytes(data)
    return captured, hashlib.sha256(captured).hexdigest()


def atomic_write(path: Path, data: bytes, label: str) -> None:
    if not path.is_absolute() or path.is_symlink():
        raise LedgerError(f"{label} output must be absolute and non-symlinked")
    parent = path.parent
    if parent.is_symlink() or parent.resolve(strict=True) != parent:
        raise LedgerError(f"{label} output parent must be canonical and non-symlinked")
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=parent, prefix=f".{path.name}.", delete=False) as stream:
            temporary = stream.name
            os.fchmod(stream.fileno(), 0o600)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
        directory = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temporary:
            Path(temporary).unlink(missing_ok=True)


def dormant_ledger_policy() -> dict[str, Any]:
    return {
        "contract_name": LEDGER_POLICY_CONTRACT,
        "contract_version": 1,
        "configured": False,
        "base_url": None,
        "allowed_hosts": [],
        "expected_service_identity": None,
        "credential_source": "github_environment_secret_only",
        "credential_env_name": CREDENTIAL_ENV_NAME,
        "receipt_public_key_spki_der_base64": None,
        "receipt_public_key_spki_sha256": None,
        "tls_required": True,
        "reserve_path": "/v1/preview12-approval-reservations/reserve",
        "commit_path": "/v1/preview12-approval-reservations/commit",
        "abort_path": "/v1/preview12-approval-reservations/abort",
        "status_path": "/v1/preview12-approval-reservations/status",
        "maximum_request_bytes": 65536,
        "maximum_response_bytes": 262144,
        "reservation_lease_seconds": 900,
        "timeout_seconds": 10,
        "maximum_attempts": 3,
    }


def validate_ledger_policy(value: object, *, require_configured: bool) -> dict[str, Any]:
    template = dormant_ledger_policy()
    if not isinstance(value, dict) or set(value) != set(template):
        raise LedgerError("durable ledger policy fields are not exact")
    fixed = {
        key: member for key, member in template.items()
        if key not in {
            "configured", "base_url", "allowed_hosts", "expected_service_identity",
            "receipt_public_key_spki_der_base64", "receipt_public_key_spki_sha256",
        }
    }
    if any(
        type(value.get(key)) is not type(member) or value.get(key) != member
        for key, member in fixed.items()
    ):
        raise LedgerError("durable ledger policy constants differ")
    configured = value.get("configured")
    if type(configured) is not bool:
        raise LedgerError("durable ledger configured posture is invalid")
    if not configured:
        if value != template:
            raise LedgerError("unconfigured durable ledger policy contains authority material")
        if require_configured:
            raise LedgerError("durable external ledger is not configured")
        return dict(value)
    if not require_configured:
        raise LedgerError("configured durable ledger is not valid in dormant policy")
    base_url = str(value.get("base_url") or "")
    parsed = urllib.parse.urlsplit(base_url)
    if (
        parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
        or parsed.password is not None or parsed.port not in {None, 443}
        or parsed.path not in {"", "/"} or parsed.query or parsed.fragment
        or HOSTNAME.fullmatch(parsed.hostname) is None
        or base_url != f"https://{parsed.hostname}"
    ):
        raise LedgerError("durable ledger base URL must be one canonical HTTPS origin")
    hosts = value.get("allowed_hosts")
    if (
        not isinstance(hosts, list) or hosts != sorted(set(hosts))
        or hosts != [parsed.hostname]
    ):
        raise LedgerError("durable ledger hostname is not the exact allowlisted service")
    service = value.get("expected_service_identity")
    if not isinstance(service, str) or SERVICE_ID.fullmatch(service) is None:
        raise LedgerError("durable ledger service identity is invalid")
    encoded = value.get("receipt_public_key_spki_der_base64")
    digest = value.get("receipt_public_key_spki_sha256")
    try:
        public_der = base64.b64decode(encoded, validate=True) if isinstance(encoded, str) else b""
    except (binascii.Error, ValueError) as error:
        raise LedgerError("durable ledger receipt key is not strict Base64") from error
    if (
        len(public_der) != len(SPKI_ED25519_PREFIX) + 32
        or not public_der.startswith(SPKI_ED25519_PREFIX)
        or not isinstance(digest, str) or SHA256.fullmatch(digest) is None
        or hashlib.sha256(public_der).hexdigest() != digest
    ):
        raise LedgerError("durable ledger receipt key does not match the reviewed Ed25519 authority")
    return dict(value)


def make_subject(
    *, approval_request_nonce: str, two_green_artifact_id: int,
    two_green_artifact_sha256: str, two_green_receipt_sha256: str,
    main_tree: str, policy_sha256: str, version_name: str, version_code: int,
) -> dict[str, Any]:
    values = {
        "approvalRequestNonce": approval_request_nonce,
        "twoGreenArtifactId": two_green_artifact_id,
        "twoGreenArtifactSha256": two_green_artifact_sha256,
        "twoGreenReceiptSha256": two_green_receipt_sha256,
        "mainTree": main_tree,
        "policySha256": policy_sha256,
    }
    for label in (
        "approvalRequestNonce", "twoGreenArtifactSha256",
        "twoGreenReceiptSha256", "policySha256",
    ):
        if not isinstance(values[label], str) or SHA256.fullmatch(values[label]) is None:
            raise LedgerError(f"{label} must be a lowercase SHA-256")
    if not isinstance(main_tree, str) or SHA40.fullmatch(main_tree) is None:
        raise LedgerError("mainTree must be a lowercase SHA-40")
    if type(two_green_artifact_id) is not int or two_green_artifact_id <= 0:
        raise LedgerError("twoGreenArtifactId must be a positive integer")
    if (version_name, version_code) != (VERSION_NAME, VERSION_CODE):
        raise LedgerError("ledger subject release identity is not exact Preview12/code12")
    return {
        "contractName": SUBJECT_CONTRACT,
        "contractVersion": 1,
        **values,
        "release": {
            "packageId": PACKAGE_ID,
            "versionName": VERSION_NAME,
            "versionCode": VERSION_CODE,
        },
    }


def _request(
    operation: str, subject: Mapping[str, Any], *,
    approval: dict[str, Any] | None = None, abort_reason: str | None = None,
    prior_reservation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if operation not in {"reserve", "commit", "abort", "status"}:
        raise LedgerError("unsupported durable ledger operation")
    subject_sha256 = canonical_sha256(subject)
    operation_binding: dict[str, Any] = {
        "operation": operation,
        "subjectSha256": subject_sha256,
    }
    if approval is not None:
        operation_binding["approvalSha256"] = approval["sha256"]
    if abort_reason is not None:
        operation_binding["abortReason"] = abort_reason
    if prior_reservation is not None:
        operation_binding["priorReservation"] = prior_reservation
    return {
        "contractName": REQUEST_CONTRACT,
        "contractVersion": 1,
        "operation": operation,
        "requestId": canonical_sha256(operation_binding),
        "subject": dict(subject),
        "subjectSha256": subject_sha256,
        "approval": approval,
        "abortReason": abort_reason,
        "priorReservation": prior_reservation,
    }


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


class Transport(Protocol):
    def __call__(self, url: str, body: bytes, headers: Mapping[str, str], timeout: int) -> HttpResponse: ...


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        return None


def _https_transport(url: str, body: bytes, headers: Mapping[str, str], timeout: int) -> HttpResponse:
    opener = urllib.request.build_opener(
        _NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context())
    )
    request = urllib.request.Request(url, data=body, headers=dict(headers), method="POST")
    try:
        with opener.open(request, timeout=timeout) as response:
            return HttpResponse(
                response.status, dict(response.headers.items()),
                response.read(MAX_LEDGER_RESPONSE_BYTES + 1),
            )
    except urllib.error.HTTPError as error:
        return HttpResponse(
            error.code, dict(error.headers.items()),
            error.read(MAX_LEDGER_RESPONSE_BYTES + 1),
        )


def _openssl_verify(public_der: bytes, message: bytes, signature: bytes) -> None:
    descriptors: list[int] = []
    try:
        for name, data in (("public", public_der), ("message", message), ("signature", signature)):
            descriptor = os.memfd_create(f"preview12-ledger-{name}", flags=getattr(os, "MFD_CLOEXEC", 0))
            descriptors.append(descriptor)
            os.write(descriptor, data)
            os.lseek(descriptor, 0, os.SEEK_SET)
        completed = subprocess.run(
            [
                "/usr/bin/openssl", "pkeyutl", "-verify", "-rawin", "-pubin",
                "-inkey", f"/proc/self/fd/{descriptors[0]}", "-keyform", "DER",
                "-in", f"/proc/self/fd/{descriptors[1]}",
                "-sigfile", f"/proc/self/fd/{descriptors[2]}",
            ],
            check=False, capture_output=True, timeout=10,
            env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
            pass_fds=tuple(descriptors),
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise LedgerError("durable ledger Ed25519 verifier is unavailable") from error
    finally:
        for descriptor in descriptors:
            os.close(descriptor)
    if completed.returncode != 0:
        raise LedgerError("durable ledger receipt signature is invalid")


def validate_response(
    value: Mapping[str, Any], *, request: Mapping[str, Any], policy: Mapping[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo != timezone.utc:
        raise LedgerError("durable ledger validation clock must be UTC")
    if set(value) != {"contractName", "contractVersion", "receipt", "receiptSha256", "signature"}:
        raise LedgerError("durable ledger response fields are not exact")
    if (
        value.get("contractName") != RESPONSE_CONTRACT
        or type(value.get("contractVersion")) is not int
        or value.get("contractVersion") != 1
    ):
        raise LedgerError("durable ledger response contract differs")
    receipt = value.get("receipt")
    exact_receipt_fields = {
        "contractName", "contractVersion", "serviceIdentity", "requestId",
        "operation", "subject", "subjectSha256", "reservationId", "state",
        "revision", "reservedAtUtc", "updatedAtUtc", "uniquenessSubjects",
        "leaseExpiresAtUtc", "priorReservation", "durabilityClass", "exactlyOnce",
        "approval", "abort",
    }
    if not isinstance(receipt, dict) or set(receipt) != exact_receipt_fields:
        raise LedgerError("durable ledger receipt fields are not exact")
    if (
        receipt.get("contractName") != RECEIPT_CONTRACT
        or type(receipt.get("contractVersion")) is not int
        or receipt.get("contractVersion") != 1
        or receipt.get("serviceIdentity") != policy["expected_service_identity"]
        or receipt.get("requestId") != request["requestId"]
        or receipt.get("operation") != request["operation"]
        or receipt.get("priorReservation") != request.get("priorReservation")
        or receipt.get("subject") != request["subject"]
        or receipt.get("subjectSha256") != request["subjectSha256"]
        or not isinstance(receipt.get("reservationId"), str)
        or RESERVATION_ID.fullmatch(receipt["reservationId"]) is None
        or receipt.get("state") not in {"reserved", "committed", "aborted"}
        or type(receipt.get("revision")) is not int or receipt["revision"] <= 0
        or receipt.get("uniquenessSubjects") != UNIQUENESS_SUBJECTS
        or receipt.get("durabilityClass") != "external_durable"
        or receipt.get("exactlyOnce") is not True
    ):
        raise LedgerError("durable ledger receipt authority differs")
    reserved = _timestamp(receipt.get("reservedAtUtc"), "ledger reservation time")
    updated = _timestamp(receipt.get("updatedAtUtc"), "ledger update time")
    lease_expires = _timestamp(receipt.get("leaseExpiresAtUtc"), "ledger lease expiry")
    if (
        lease_expires != reserved + timedelta(seconds=policy["reservation_lease_seconds"])
        or updated < reserved or updated > lease_expires
        or updated > now.replace(microsecond=0) + timedelta(minutes=5)
    ):
        raise LedgerError("durable ledger receipt timestamps are invalid")
    state = receipt["state"]
    approval = receipt.get("approval")
    abort = receipt.get("abort")
    if state == "reserved" and (approval is not None or abort is not None):
        raise LedgerError("reserved ledger receipt contains terminal material")
    if state == "reserved" and lease_expires <= now:
        raise LedgerError("durable ledger reservation lease has expired")
    if state == "committed":
        if not isinstance(approval, dict) or set(approval) != {"sha256", "sizeBytes", "publicJsonBase64"} or abort is not None:
            raise LedgerError("committed ledger receipt is missing exact approval material")
        try:
            approval_bytes = base64.b64decode(approval.get("publicJsonBase64"), validate=True)
        except (binascii.Error, ValueError, TypeError) as error:
            raise LedgerError("committed approval is not strict Base64") from error
        if (
            not approval_bytes or len(approval_bytes) > MAX_APPROVAL_BYTES
            or approval.get("sizeBytes") != len(approval_bytes)
            or approval.get("sha256") != hashlib.sha256(approval_bytes).hexdigest()
        ):
            raise LedgerError("committed approval bytes do not match their binding")
    elif state == "aborted":
        if approval is not None or not isinstance(abort, dict) or set(abort) != {"reasonCode"} or not re.fullmatch(r"[a-z][a-z0-9_]{2,63}", str(abort.get("reasonCode") or "")):
            raise LedgerError("aborted ledger receipt is malformed")
    if value.get("receiptSha256") != canonical_sha256(receipt):
        raise LedgerError("durable ledger receipt digest is invalid")
    signature = value.get("signature")
    if not isinstance(signature, dict) or set(signature) != {"algorithm", "publicKeySpkiSha256", "signatureBase64"} or signature.get("algorithm") != "Ed25519":
        raise LedgerError("durable ledger signature fields are invalid")
    if signature.get("publicKeySpkiSha256") != policy["receipt_public_key_spki_sha256"]:
        raise LedgerError("durable ledger receipt key identity differs")
    try:
        public_der = base64.b64decode(policy["receipt_public_key_spki_der_base64"], validate=True)
        signature_bytes = base64.b64decode(signature.get("signatureBase64"), validate=True)
    except (binascii.Error, ValueError, TypeError) as error:
        raise LedgerError("durable ledger receipt signature is not strict Base64") from error
    if len(signature_bytes) != 64:
        raise LedgerError("durable ledger receipt signature size differs")
    _openssl_verify(public_der, canonical_bytes(receipt), signature_bytes)
    return dict(value)


def _timestamp(value: object, label: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise LedgerError(f"{label} must be a UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise LedgerError(f"{label} must be a UTC timestamp") from error
    if parsed.tzinfo != timezone.utc:
        raise LedgerError(f"{label} must be a UTC timestamp")
    return parsed


class DurableApprovalLedgerClient:
    def __init__(
        self, policy: Mapping[str, Any], environment: Mapping[str, str], *,
        transport: Transport | None = None, sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.policy = validate_ledger_policy(policy, require_configured=True)
        token = environment.get(CREDENTIAL_ENV_NAME)
        if environment is os.environ:
            os.environ.pop(CREDENTIAL_ENV_NAME, None)
        if not isinstance(token, str) or not token or token != token.strip() or len(token) > 4096:
            raise LedgerError("durable ledger environment credential is missing or invalid")
        self._token = token
        self._transport = transport or _https_transport
        self._sleep = sleeper

    def _call(self, request: Mapping[str, Any]) -> dict[str, Any]:
        body = canonical_bytes(request)
        if len(body) > self.policy["maximum_request_bytes"]:
            raise LedgerError("durable ledger request exceeds its byte limit")
        path = self.policy[f"{request['operation']}_path"]
        url = self.policy["base_url"].rstrip("/") + path
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname not in self.policy["allowed_hosts"]:
            raise LedgerError("durable ledger request escaped its reviewed HTTPS identity")
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "User-Agent": "chummer-fleet-preview12-approval-ledger/1",
        }
        last_error: Exception | None = None
        for attempt in range(self.policy["maximum_attempts"]):
            try:
                response = self._transport(url, body, headers, self.policy["timeout_seconds"])
            except (OSError, TimeoutError, socket.timeout, urllib.error.URLError) as error:
                last_error = error
            else:
                if len(response.body) > self.policy["maximum_response_bytes"]:
                    raise LedgerError("durable ledger response is oversized")
                if response.status in TRANSIENT_STATUSES:
                    last_error = LedgerError(f"transient durable ledger HTTP {response.status}")
                elif response.status != 200:
                    raise LedgerError(f"durable ledger rejected {request['operation']} with HTTP {response.status}")
                else:
                    content_type = next((value for key, value in response.headers.items() if key.casefold() == "content-type"), "")
                    content_length = next((value for key, value in response.headers.items() if key.casefold() == "content-length"), None)
                    if content_type.split(";", 1)[0].strip().casefold() != "application/json":
                        raise LedgerError("durable ledger response content type is not JSON")
                    if content_length is not None:
                        try:
                            declared = int(content_length)
                        except ValueError as error:
                            raise LedgerError("durable ledger response Content-Length is invalid") from error
                        if declared != len(response.body) or declared > self.policy["maximum_response_bytes"]:
                            raise LedgerError("durable ledger response length differs or is oversized")
                    value = strict_json_bytes(response.body, "durable ledger response", self.policy["maximum_response_bytes"])
                    return validate_response(value, request=request, policy=self.policy)
            if attempt + 1 < self.policy["maximum_attempts"]:
                self._sleep(0.25 * (2 ** attempt))
        raise LedgerError("durable ledger is unavailable after bounded retries") from last_error

    def reserve(self, subject: Mapping[str, Any]) -> dict[str, Any]:
        reserve_request = _request("reserve", subject)
        try:
            response = self._call(reserve_request)
        except LedgerError as reserve_error:
            if str(reserve_error) != "durable ledger is unavailable after bounded retries":
                raise
            # If every reserve response was lost, first establish through a
            # separately signed, unbound status query that the exact subject
            # exists. Then replay the deterministic reserve request so the
            # durable snapshot remains a signed reserve receipt.
            try:
                observed = self._call(_request("status", subject))
                if observed["receipt"]["state"] not in {
                    "reserved", "committed", "aborted",
                }:
                    raise LedgerError("durable ledger status is not authoritative")
                response = self._call(reserve_request)
            except LedgerError:
                raise reserve_error
        if response["receipt"]["state"] not in {"reserved", "committed"}:
            raise LedgerError("durable ledger subject was previously aborted")
        return response

    def _reservation_binding(
        self, subject: Mapping[str, Any], reservation: Mapping[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        validated = validate_response(
            reservation, request=_request("reserve", subject), policy=self.policy
        )
        receipt = validated["receipt"]
        return validated, {
            "reservationId": receipt["reservationId"],
            "priorRevision": receipt["revision"],
            "reservationReceiptSha256": validated["receiptSha256"],
        }

    @staticmethod
    def _require_continuity(
        prior: Mapping[str, Any], response: Mapping[str, Any], *, transition: bool
    ) -> None:
        before = prior["receipt"]
        after = response["receipt"]
        if after["reservationId"] != before["reservationId"]:
            raise LedgerError("durable ledger reservation identity changed")
        if (
            after["reservedAtUtc"] != before["reservedAtUtc"]
            or after["leaseExpiresAtUtc"] != before["leaseExpiresAtUtc"]
        ):
            raise LedgerError("durable ledger reservation lease identity changed")
        if _timestamp(after["updatedAtUtc"], "ledger update time") > _timestamp(
            before["leaseExpiresAtUtc"], "original ledger lease expiry"
        ):
            raise LedgerError("durable ledger transition exceeded its original lease")
        if after["revision"] < before["revision"] or (
            transition and before["state"] == "reserved"
            and after["revision"] <= before["revision"]
        ):
            raise LedgerError("durable ledger revision is not monotonic")

    def status(
        self, subject: Mapping[str, Any], reservation: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        if reservation is None:
            return self._call(_request("status", subject))
        prior, binding = self._reservation_binding(subject, reservation)
        response = self._call(
            _request("status", subject, prior_reservation=binding)
        )
        self._require_continuity(prior, response, transition=False)
        return response

    def commit(
        self, subject: Mapping[str, Any], approval_bytes: bytes,
        reservation: Mapping[str, Any],
    ) -> dict[str, Any]:
        if not approval_bytes or len(approval_bytes) > MAX_APPROVAL_BYTES:
            raise LedgerError("public approval is not bounded")
        prior, binding = self._reservation_binding(subject, reservation)
        if prior["receipt"]["state"] == "aborted":
            raise LedgerError("durable ledger reservation is already aborted")
        approval = {
            "sha256": hashlib.sha256(approval_bytes).hexdigest(),
            "sizeBytes": len(approval_bytes),
            "publicJsonBase64": base64.b64encode(approval_bytes).decode("ascii"),
        }
        request = _request(
            "commit", subject, approval=approval, prior_reservation=binding
        )
        try:
            response = self._call(request)
        except LedgerError as commit_error:
            # A lost response after a durable commit is ambiguous.  Resolve it
            # through a separately idempotent status operation before failing.
            try:
                response = self.status(subject, reservation)
            except LedgerError:
                raise commit_error
        receipt = response["receipt"]
        self._require_continuity(prior, response, transition=True)
        if receipt["state"] != "committed" or receipt["approval"] != approval:
            raise LedgerError("durable ledger commit did not preserve the exact public approval")
        return response

    def abort(
        self, subject: Mapping[str, Any], reason_code: str,
        reservation: Mapping[str, Any],
    ) -> dict[str, Any]:
        if re.fullmatch(r"[a-z][a-z0-9_]{2,63}", reason_code) is None:
            raise LedgerError("durable ledger abort reason is invalid")
        prior, binding = self._reservation_binding(subject, reservation)
        if prior["receipt"]["state"] == "committed":
            raise LedgerError("durable ledger reservation is already committed")
        response = self._call(
            _request(
                "abort", subject, abort_reason=reason_code,
                prior_reservation=binding,
            )
        )
        self._require_continuity(prior, response, transition=True)
        if response["receipt"]["state"] != "aborted" or response["receipt"]["abort"] != {"reasonCode": reason_code}:
            raise LedgerError("durable ledger abort did not become terminal")
        return response


def load_policy(path: Path) -> tuple[dict[str, Any], str]:
    data, digest = stable_file(path, "approval policy", 256 * 1024)
    value = strict_json_bytes(data, "approval policy", 256 * 1024)
    replay = value.get("replay_protection")
    if not isinstance(replay, dict) or "external_ledger" not in replay:
        raise LedgerError("approval policy has no durable external ledger contract")
    return value, digest


def subject_from_args(args: argparse.Namespace, policy_sha256: str) -> dict[str, Any]:
    def positive(value: str, label: str) -> int:
        if re.fullmatch(r"[1-9][0-9]*", value) is None:
            raise LedgerError(f"{label} must be a canonical positive integer")
        return int(value)
    return make_subject(
        approval_request_nonce=args.approval_request_nonce,
        two_green_artifact_id=positive(args.two_green_artifact_id, "Two-Green artifact ID"),
        two_green_artifact_sha256=args.two_green_artifact_sha256,
        two_green_receipt_sha256=args.two_green_receipt_sha256,
        main_tree=args.main_tree,
        policy_sha256=policy_sha256,
        version_name=args.version_name,
        version_code=positive(args.version_code, "version code"),
    )


def load_reservation_snapshot(
    path: Path, subject: Mapping[str, Any], policy: Mapping[str, Any]
) -> dict[str, Any]:
    data, _ = stable_file(path, "durable reservation snapshot", MAX_LEDGER_RESPONSE_BYTES)
    value = strict_json_bytes(
        data, "durable reservation snapshot", MAX_LEDGER_RESPONSE_BYTES
    )
    response = validate_response(
        value, request=_request("reserve", subject), policy=policy
    )
    if response["receipt"]["state"] not in {"reserved", "committed", "aborted"}:
        raise LedgerError("durable reservation snapshot state is invalid")
    return response


def _subject_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--approval-request-nonce", required=True)
    parser.add_argument("--two-green-artifact-id", required=True)
    parser.add_argument("--two-green-artifact-sha256", required=True)
    parser.add_argument("--two-green-receipt-sha256", required=True)
    parser.add_argument("--main-tree", required=True)
    parser.add_argument("--version-name", required=True)
    parser.add_argument("--version-code", required=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, required=True)
    subparsers = parser.add_subparsers(dest="operation", required=True)
    for operation in ("reserve", "commit", "abort", "status", "cleanup"):
        command = subparsers.add_parser(operation)
        _subject_arguments(command)
        command.add_argument("--receipt-output", type=Path, required=True)
        if operation in {"commit", "abort", "cleanup"}:
            command.add_argument("--reservation-snapshot", type=Path, required=True)
        if operation == "commit":
            command.add_argument("--approval", type=Path, required=True)
            command.add_argument("--committed-approval-output", type=Path, required=True)
        if operation == "abort":
            command.add_argument("--reason-code", required=True)
        if operation == "cleanup":
            command.add_argument("--reason-code", default="workflow_interrupted")
        if operation == "reserve":
            command.add_argument("--committed-approval-output", type=Path)
    args = parser.parse_args(argv)
    policy, policy_sha256 = load_policy(args.policy)
    ledger_policy = validate_ledger_policy(
        policy["replay_protection"]["external_ledger"], require_configured=True
    )
    subject = subject_from_args(args, policy_sha256)
    client = DurableApprovalLedgerClient(ledger_policy, os.environ)
    if args.operation == "reserve":
        response = client.reserve(subject)
        if response["receipt"]["state"] == "committed":
            if args.committed_approval_output is None:
                raise LedgerError("committed reservation requires a recovery output")
            recovered = base64.b64decode(
                response["receipt"]["approval"]["publicJsonBase64"], validate=True
            )
            atomic_write(
                args.committed_approval_output, recovered,
                "recovered committed approval",
            )
    elif args.operation == "status":
        response = client.status(subject)
    else:
        reservation = load_reservation_snapshot(
            args.reservation_snapshot, subject, ledger_policy
        )
        if args.operation == "abort":
            response = client.abort(subject, args.reason_code, reservation)
        elif args.operation == "cleanup":
            status = client.status(subject, reservation)
            response = (
                client.abort(subject, args.reason_code, reservation)
                if status["receipt"]["state"] == "reserved"
                else status
            )
        else:
            approval_bytes, _ = stable_file(
                args.approval, "public approval", MAX_APPROVAL_BYTES
            )
            response = client.commit(subject, approval_bytes, reservation)
            committed = base64.b64decode(
                response["receipt"]["approval"]["publicJsonBase64"], validate=True
            )
            atomic_write(
                args.committed_approval_output, committed, "committed approval"
            )
    atomic_write(
        args.receipt_output, pretty_bytes(response),
        f"ledger {args.operation} receipt",
    )
    print(
        f"preview12_approval_ledger={args.operation} "
        f"state={response['receipt']['state']} "
        f"reservation_id={response['receipt']['reservationId']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
