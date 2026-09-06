#!/usr/bin/env python3
"""Trusted Preview12 intake, durable reservation, and one-shot signer."""
from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping

HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
FLEET_REPOSITORY = "ArchonMegalon/fleet"
ANDROID_REPOSITORY = "ArchonMegalon/chummer-android"
PACKAGE_ID = "com.myexternalbrain.chummer"
VERSION_NAME = "0.1.0-preview.12"
VERSION_CODE = 12
MINIMUM_SDK = 24
TARGET_SDK = 36
SOURCE_GRAPH_CONTRACT = "chummer.android.release-source-graph/v3"
PROOF_EXCLUSION_CONTRACT = "chummer.android.release-aab-proof-exclusion/v1"
HANDOFF_REQUEST_CONTRACT = "fleet.android_preview12_signed_content_handoff_request.v1"
HANDOFF_RECEIPT_CONTRACT = "fleet.android_preview12_signed_content_handoff_receipt.v1"
HANDOFF_AUDIT_CONTRACT = "fleet.android_preview12_signed_content_handoff_audit.v1"
RESERVATION_EVIDENCE_CONTRACT = "fleet.android_preview12_reservation_evidence.v3"
SOURCE_REPOSITORIES = {
    "chummer-android": ("app", "https://github.com/ArchonMegalon/chummer-android.git"),
    "chummer6-core": ("runtime", "https://github.com/ArchonMegalon/chummer6-core.git"),
    "chummer6-design": ("validation", "https://github.com/ArchonMegalon/chummer6-design.git"),
    "chummer6-hub": ("contracts_and_validation", "https://github.com/ArchonMegalon/chummer6-hub.git"),
    "chummer6-hub-registry": ("contracts", "https://github.com/ArchonMegalon/chummer6-hub-registry.git"),
    "chummer6-media-factory": ("contracts", "https://github.com/ArchonMegalon/chummer6-media-factory.git"),
    "chummer6-ui": ("runtime", "https://github.com/ArchonMegalon/chummer6-ui.git"),
    "chummer6-ui-kit": ("runtime", "https://github.com/ArchonMegalon/chummer6-ui-kit.git"),
}
VERIFIER_PATH = f"{FLEET_REPOSITORY}/.github/workflows/android-preview12-verifier.yml"
SIGNER_REF = f"{FLEET_REPOSITORY}/.github/workflows/android-preview12-signer.yml@refs/heads/main"
class SignerError(RuntimeError):
    pass
def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SignerError(f"duplicate JSON key: {key}")
        result[key] = value
    return result
def _json_object(payload: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8", errors="strict"),
            object_pairs_hook=_object_without_duplicates,
            parse_constant=lambda token: (_ for _ in ()).throw(SignerError(f"non-finite JSON value: {token}")))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SignerError(f"{label} is not strict UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise SignerError(f"{label} must contain one JSON object")
    return value
def _bounded_file_bytes(path: Path, label: str, limit: int) -> bytes:
    if limit < 1:
        raise SignerError(f"{label} has an invalid size limit")
    with path.open("rb") as stream:
        payload = stream.read(limit + 1)
    if len(payload) > limit:
        raise SignerError(f"{label} exceeds the locked size limit")
    return payload
def _bounded_response_bytes(response, label: str, limit: int) -> bytes:
    declared = response.headers.get("Content-Length") if getattr(response, "headers", None) else None
    if declared is not None:
        if not declared.isascii() or not declared.isdigit():
            raise SignerError(f"{label} has an invalid Content-Length")
        if int(declared) > limit:
            raise SignerError(f"{label} exceeds the locked size limit")
    payload = response.read(limit + 1)
    if len(payload) > limit:
        raise SignerError(f"{label} exceeds the locked size limit")
    if declared is not None and len(payload) != int(declared):
        raise SignerError(f"{label} body length differs from Content-Length")
    return payload
def _load(path: Path, contract: str) -> tuple[dict[str, Any], bytes]:
    payload = _bounded_file_bytes(path, contract, 1024 * 1024)
    value = _json_object(payload, contract)
    if value.get("contract_name") != contract:
        raise SignerError(f"unexpected {contract} contract")
    return value, payload
def _load_lock(path: Path):
    return _load(path, "fleet.android_preview12_signer_transaction.v3")
def _load_toolchain(path: Path):
    return _load(path, "fleet.android_preview12_toolchain.v1")
def _full_image(lock: Mapping[str, Any]) -> str | None:
    value = lock["toolchain"]
    return f"{value['image_repository']}@{value['image_digest']}" if value.get("image_digest") else None
def _positive(value: Any, label: str) -> int:
    text = str(value)
    if not text.isascii() or not text.isdigit() or int(text) < 1:
        raise SignerError(f"{label} must be a positive integer")
    return int(text)
def _plain_file_name(value: Any, suffix: str) -> bool:
    return isinstance(value, str) and value.endswith(suffix) and PurePosixPath(value).name == value \
        and "\\" not in value and value not in ("", ".", "..")
def provisioning_blockers(lock, signer_image: str, toolchain, toolchain_bytes: bytes,
                          producer_only: bool = False) -> list[str]:
    failures: list[str] = []
    if lock.get("state") != "ready":
        failures.append("lock state is not ready")
    release = lock.get("release", {})
    identity = (release.get("package_id"), release.get("version_name"), release.get("version_code"),
                release.get("minimum_sdk"), release.get("target_sdk"))
    if identity != (PACKAGE_ID, VERSION_NAME, VERSION_CODE, MINIMUM_SDK, TARGET_SDK):
        failures.append("release identity is not exact com.myexternalbrain.chummer/0.1.0-preview.12/code12/API24-36")
    for field in ("candidate_file_name", "signed_file_name"):
        if not _plain_file_name(release.get(field), ".aab"):
            failures.append(f"release.{field} is not provisioned")
    if not _plain_file_name(release.get("source_graph_file_name"), "-source-graph.json"):
        failures.append("release.source_graph_file_name is not provisioned")
    source = lock.get("source", {})
    if (source.get("repository"), source.get("repository_id")) != (ANDROID_REPOSITORY, 1331626697):
        failures.append("canonical Android source repository drifted")
    if not str(source.get("source_ref") or "").startswith("refs/heads/"):
        failures.append("source.source_ref is not provisioned")
    if source.get("discovery_receipt", {}).get("preview12_workflow_found") is not True:
        failures.append("canonical repository discovery found no Preview12 producer")
    for kind in ("candidate", "verification"):
        spec = source.get(kind, {})
        for field in ("workflow_id", "run_attempt"):
            if not isinstance(spec.get(field), int) or spec[field] < 1:
                failures.append(f"source.{kind}.{field} is not provisioned")
        for field in ("workflow_path", "artifact_name"):
            if not isinstance(spec.get(field), str) or not spec[field]:
                failures.append(f"source.{kind}.{field} is not provisioned")
        for field in ("workflow_blob_sha",):
            if not HEX40.fullmatch(str(spec.get(field) or "")):
                failures.append(f"source.{kind}.{field} is not provisioned")
        if spec.get("event") not in ("push", "workflow_dispatch"):
            failures.append(f"source.{kind}.event is not provisioned")
    if source.get("candidate", {}).get("workflow_id") == source.get("verification", {}).get("workflow_id"):
        failures.append("candidate and verification workflows must be distinct")
    candidate = source.get("candidate", {})
    verification = source.get("verification", {})
    if not HEX64.fullmatch(str(candidate.get("producer_toolchain_closure_sha256") or "")):
        failures.append("producer toolchain closure is not provisioned")
    for field in ("receipt_file_name", "proof_exclusion_validator_path"):
        if not isinstance(verification.get(field), str) or not verification[field]:
            failures.append(f"verification {field} is not provisioned")
    receipt_name = verification.get("receipt_file_name")
    if receipt_name is not None and not _plain_file_name(receipt_name, ".json"):
        failures.append("verification receipt file name is unsafe")
    validator_path = str(verification.get("proof_exclusion_validator_path") or "")
    validator_parts = PurePosixPath(validator_path)
    if validator_path and (validator_parts.is_absolute() or ".." in validator_parts.parts
                           or "\\" in validator_path or not validator_path.startswith("scripts/")
                           or not validator_path.endswith(".py")):
        failures.append("verification proof-exclusion validator path is unsafe")
    if not HEX40.fullmatch(str(verification.get("proof_exclusion_validator_blob_sha") or "")):
        failures.append("verification proof-exclusion validator blob SHA is not provisioned")
    limits = lock.get("limits", {})
    for key in ("artifact_max_bytes", "candidate_max_bytes", "source_graph_max_bytes",
                "verification_receipt_max_bytes", "api_json_max_bytes", "reservation_json_max_bytes",
                "handoff_content_max_bytes", "handoff_json_max_bytes", "handoff_metadata_max_bytes"):
        if type(limits.get(key)) is not int or limits[key] < 1:
            failures.append(f"limits.{key} is not provisioned")
    if (type(limits.get("handoff_content_max_bytes")) is int
            and type(limits.get("candidate_max_bytes")) is int
            and limits["handoff_content_max_bytes"] > limits["candidate_max_bytes"]) \
            or (type(limits.get("handoff_json_max_bytes")) is int
                and type(limits.get("api_json_max_bytes")) is int
                and limits["handoff_json_max_bytes"] > limits["api_json_max_bytes"]) \
            or (type(limits.get("handoff_metadata_max_bytes")) is int
                and limits["handoff_metadata_max_bytes"] > 16 * 1024):
        failures.append("private signed-content handoff size ceilings exceed the trusted bounds")
    if producer_only:
        return failures
    reservation = lock.get("reservation", {})
    if reservation.get("enabled") is not True:
        failures.append("durable exactly-once reservation is disabled")
    if not str(reservation.get("broker_url") or "").startswith("https://"):
        failures.append("reservation broker URL is not provisioned")
    if not HEX64.fullmatch(str(reservation.get("audited_implementation_sha256") or "")):
        failures.append("reservation implementation audit is not provisioned")
    signing = lock.get("signing", {})
    if signing.get("enabled") is not True:
        failures.append("signing is disabled")
    if signing.get("signature_algorithm") not in ("SHA256withRSA", "SHA256withECDSA"):
        failures.append("upload-key signature algorithm is not provisioned")
    if not HEX64.fullmatch(str(signing.get("expected_upload_certificate_sha256") or "")):
        failures.append("expected upload certificate SHA-256 is not provisioned")
    tool = lock.get("toolchain", {})
    image = _full_image(lock)
    if not image or not re.fullmatch(r"[^@]+@sha256:[0-9a-f]{64}", image):
        failures.append("signer OCI digest is not provisioned")
    elif signer_image != image:
        failures.append("runner signer image does not equal locked OCI digest")
    if hashlib.sha256(toolchain_bytes).hexdigest() != tool.get("lock_sha256"):
        failures.append("toolchain lock SHA-256 mismatch")
    if not HEX64.fullmatch(str(tool.get("installed_receipt_sha256") or "")):
        failures.append("installed signer receipt SHA-256 is not provisioned")
    if toolchain.get("platform") != tool.get("platform"):
        failures.append("toolchain platform drifted")
    for item in [*toolchain.get("base_images", []), *toolchain.get("archives", [])]:
        digest = str(item.get("digest", item.get("sha256", ""))).removeprefix("sha256:")
        if not HEX64.fullmatch(digest):
            failures.append(f"toolchain input {item.get('name')} is not SHA-256 locked")
    handoff = lock.get("signed_content_handoff", {})
    if handoff.get("enabled") is not True:
        failures.append("private signed-content handoff is disabled")
    endpoint = str(handoff.get("private_content_addressed_endpoint") or "")
    parsed_endpoint = urllib.parse.urlparse(endpoint)
    if parsed_endpoint.scheme != "https" or not parsed_endpoint.hostname or parsed_endpoint.username \
            or parsed_endpoint.password or parsed_endpoint.query or parsed_endpoint.fragment or endpoint.endswith("/"):
        failures.append("private signed-content handoff endpoint is not provisioned")
    if not HEX64.fullmatch(str(handoff.get("audited_implementation_sha256") or "")):
        failures.append("private signed-content handoff implementation is not provisioned")
    if handoff.get("visibility") != "private_authenticated_only" \
            or handoff.get("immutability") != "create_if_absent" \
            or handoff.get("public_url_forbidden") is not True \
            or handoff.get("request_contract") != HANDOFF_REQUEST_CONTRACT \
            or handoff.get("receipt_contract") != HANDOFF_RECEIPT_CONTRACT:
        failures.append("private signed-content handoff posture is not exact")
    auth = handoff.get("auth", {})
    if auth.get("token_type") != "jwt_bearer" or auth.get("server_signature_validation_required") is not True \
            or auth.get("issuance_mode") != "jit_workload_identity_exchange" \
            or auth.get("jit_per_job_required") is not True or auth.get("static_secret_forbidden") is not True \
            or not HEX64.fullmatch(str(auth.get("audited_issuer_integration_sha256") or "")) \
            or not str(auth.get("issuer") or "").startswith("https://") \
            or not isinstance(auth.get("audience"), str) or not auth.get("audience") \
            or not isinstance(auth.get("scope"), str) or not re.fullmatch(r"[A-Za-z0-9:._/-]{1,200}", auth["scope"]) \
            or type(auth.get("max_ttl_seconds")) is not int or not 1 <= auth["max_ttl_seconds"] <= 900:
        failures.append("private signed-content handoff short-lived auth is not provisioned")
    envs, publication = lock.get("environments", {}), lock.get("publication", {})
    if tuple(envs.get(k) for k in ("intake", "signing", "play_upload")) != (
        "android-preview12-intake", "android-preview12-signing", "android-play-upload"
    ):
        failures.append("protected environment names drifted")
    if envs.get("play_upload_enabled") is not False:
        failures.append("Play upload environment must remain disabled")
    if publication.get("intake_actions_artifact_is_private_ci_evidence") is not True:
        failures.append("intake Actions artifact must remain private CI evidence")
    for key in ("signing", "signed_content_handoff", "signed_aab_actions_artifact", "registry_publication",
                "play_upload", "github_release"):
        if publication.get(key) is not False:
            failures.append(f"publication.{key} must remain false")
    return failures


INPUT_FIELDS = ("source_sha", "candidate_run_id", "candidate_artifact_id", "candidate_artifact_sha256",
                "candidate_aab_sha256", "verification_run_id", "verification_artifact_id",
                "verification_artifact_sha256", "verification_receipt_sha256")
def _validated_inputs(args) -> tuple[dict[str, Any], str]:
    values = {field: getattr(args, field) for field in INPUT_FIELDS}
    values["source_sha"] = values["source_sha"].lower()
    if not HEX40.fullmatch(values["source_sha"]):
        raise SignerError("source_sha must be an exact commit")
    for field in ("candidate_run_id", "candidate_artifact_id", "verification_run_id", "verification_artifact_id"):
        values[field] = _positive(values[field], field)
    for field in ("candidate_artifact_sha256", "candidate_aab_sha256", "verification_artifact_sha256",
                  "verification_receipt_sha256"):
        values[field] = values[field].lower()
        if not HEX64.fullmatch(values[field]):
            raise SignerError(f"{field} must be an exact SHA-256")
    if values["candidate_run_id"] == values["verification_run_id"]:
        raise SignerError("candidate and verification run IDs must be distinct")
    if values["candidate_artifact_id"] == values["verification_artifact_id"]:
        raise SignerError("candidate and verification artifact IDs must be distinct")
    return values, hashlib.sha256(_json_bytes(values)).hexdigest()
def _emit_preflight(lock, transaction_sha: str, github_output: str | None, signer: bool) -> dict[str, Any]:
    values = {"transaction_inputs_sha256": transaction_sha}
    if signer:
        values.update(signer_image=_full_image(lock), intake_environment=lock["environments"]["intake"],
                      signing_environment=lock["environments"]["signing"])
    if github_output:
        with Path(github_output).open("a", encoding="utf-8") as output:
            for key, value in values.items():
                output.write(f"{key}={value}\n")
    return {"ok": True, **values, "play_upload_performed": False, "publication_performed": False}
def reusable_preflight(args, lock, toolchain, toolchain_bytes: bytes) -> dict[str, Any]:
    inputs, transaction_sha = _validated_inputs(args)
    failures = provisioning_blockers(lock, "", toolchain, toolchain_bytes, producer_only=True)
    source = lock.get("source", {})
    expected = {"caller_repository": ANDROID_REPOSITORY, "caller_repository_id": str(source.get("repository_id")),
                "caller_ref": source.get("source_ref"), "caller_sha": inputs["source_sha"],
                "workflow_repository": FLEET_REPOSITORY, "workflow_ref": f"{VERIFIER_PATH}@{args.fleet_verifier_sha}",
                "workflow_sha": args.fleet_verifier_sha}
    for field, value in expected.items():
        if getattr(args, field) != value:
            failures.append(f"{field} is not the canonical reusable-verifier value")
    if not HEX40.fullmatch(args.fleet_verifier_sha):
        failures.append("caller did not pin an exact Fleet verifier commit")
    if failures:
        raise SignerError("; ".join(failures))
    return _emit_preflight(lock, transaction_sha, args.github_output, False)
def dispatch_preflight(args, lock, toolchain, toolchain_bytes: bytes) -> dict[str, Any]:
    _, transaction_sha = _validated_inputs(args)
    failures = provisioning_blockers(lock, args.signer_image, toolchain, toolchain_bytes)
    expected = {
        "execution_repository": FLEET_REPOSITORY,
        "execution_ref": "refs/heads/main",
        "execution_ref_protected": "true",
        "execution_event": "workflow_dispatch",
        "workflow_repository": FLEET_REPOSITORY,
        "workflow_ref": SIGNER_REF,
    }
    for field, value in expected.items():
        if getattr(args, field) != value:
            failures.append(f"{field} is not the protected Fleet signer value")
    if not HEX40.fullmatch(args.execution_sha) or args.workflow_sha != args.execution_sha:
        failures.append("job_workflow_sha is not the exact Fleet execution SHA")
    if failures:
        raise SignerError("; ".join(failures))
    return _emit_preflight(lock, transaction_sha, args.github_output, True)
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):  # noqa: ANN001
        return None


def _authorization_value(token: str, label: str) -> str:
    if not token or len(token) > 16 * 1024 or not token.isascii() \
            or any(ord(character) < 0x21 or ord(character) > 0x7e for character in token):
        raise SignerError(f"{label} credential is missing or invalid")
    return f"Bearer {token}"


class GitHubClient:
    def __init__(self, token: str, json_limit: int = 1024 * 1024):
        if not token:
            raise SignerError("candidate broker credential is missing")
        if json_limit < 1:
            raise SignerError("GitHub JSON limit is invalid")
        self.json_limit = json_limit
        self.headers = {"Accept": "application/vnd.github+json",
                        "Authorization": _authorization_value(token, "candidate broker"),
                        "User-Agent": "fleet-preview12-intake/2", "X-GitHub-Api-Version": "2022-11-28"}

    def get_json(self, url: str) -> dict[str, Any]:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=self.headers), timeout=30) as response:
                return _json_object(_bounded_response_bytes(response, "GitHub API response", self.json_limit),
                                    "GitHub API response")
        except (TypeError, ValueError):
            raise SignerError("candidate broker request was rejected locally") from None

    def download_to(self, url: str, output: Path, limit: int) -> None:
        try:
            request = urllib.request.Request(url, headers=self.headers)
            response = urllib.request.build_opener(_NoRedirect()).open(request, timeout=30)
        except (TypeError, ValueError):
            raise SignerError("candidate broker request was rejected locally") from None
        except urllib.error.HTTPError as error:
            if error.code not in (301, 302, 303, 307, 308):
                raise
            location = error.headers.get("Location", "")
            parsed = urllib.parse.urlparse(location)
            if parsed.scheme != "https" or not parsed.hostname:
                raise SignerError("artifact broker returned an unsafe redirect") from error
            try:
                response = urllib.request.urlopen(urllib.request.Request(
                    location, headers={"User-Agent": self.headers["User-Agent"]}), timeout=60)
            except (TypeError, ValueError):
                raise SignerError("artifact broker request was rejected locally") from None
        total = 0
        with response, output.open("wb") as stream:
            declared = response.headers.get("Content-Length") if getattr(response, "headers", None) else None
            if declared is not None and (not declared.isascii() or not declared.isdigit() or int(declared) > limit):
                raise SignerError("artifact has an invalid or oversized Content-Length")
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > limit:
                    raise SignerError("artifact exceeds locked size limit")
                stream.write(chunk)
            if declared is not None and total != int(declared):
                raise SignerError("artifact body length differs from Content-Length")
class ReservationClient:
    def __init__(self, url: str, token: str, json_limit: int = 256 * 1024):
        if not token:
            raise SignerError("reservation broker credential is missing")
        if json_limit < 1:
            raise SignerError("reservation JSON limit is invalid")
        self.url, self.token, self.json_limit = url, token, json_limit
        self.authorization = _authorization_value(token, "reservation broker")

    def reserve(self, request_value: Mapping[str, Any]) -> dict[str, Any]:
        transaction = str(request_value["transaction_id"])
        try:
            request = urllib.request.Request(self.url, data=_json_bytes(request_value), method="POST", headers={
                "Authorization": self.authorization, "Content-Type": "application/json",
                "Idempotency-Key": transaction, "User-Agent": "fleet-preview12-reservation/1"})
            with urllib.request.urlopen(request, timeout=30) as response:
                return _json_object(_bounded_response_bytes(response, "reservation response", self.json_limit),
                                    "reservation response")
        except (TypeError, ValueError):
            raise SignerError("reservation broker request was rejected locally") from None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, SignerError) as error:
            raise SignerError("reservation outcome is indeterminate") from error


def _base64url_bytes(segment: str, label: str, limit: int = 16 * 1024) -> bytes:
    if not segment or len(segment) > limit * 2 or not re.fullmatch(r"[A-Za-z0-9_-]+", segment):
        raise SignerError(f"handoff bearer {label} is invalid")
    try:
        payload = base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))
    except (ValueError, binascii.Error) as error:
        raise SignerError(f"handoff bearer {label} is invalid") from error
    if not payload or len(payload) > limit:
        raise SignerError(f"handoff bearer {label} exceeds the locked size limit")
    if base64.urlsafe_b64encode(payload).decode().rstrip("=") != segment:
        raise SignerError(f"handoff bearer {label} is not canonical base64url")
    return payload


def _base64url_json(segment: str, label: str, limit: int = 16 * 1024) -> dict[str, Any]:
    payload = _base64url_bytes(segment, label, limit)
    return _json_object(payload, f"handoff bearer {label}")


def _validate_handoff_bearer(token: str, auth: Mapping[str, Any], now: int | None = None) -> dict[str, str | int]:
    if not token or len(token) > 16 * 1024:
        raise SignerError("handoff bearer is missing or oversized")
    parts = token.split(".")
    if len(parts) != 3 or not parts[2]:
        raise SignerError("handoff bearer is not a signed JWT")
    header = _base64url_json(parts[0], "header")
    claims = _base64url_json(parts[1], "claims")
    _base64url_bytes(parts[2], "signature")
    if header.get("typ") not in (None, "JWT") or header.get("alg") not in ("RS256", "ES256", "EdDSA"):
        raise SignerError("handoff bearer algorithm is not allowed")
    current = int(time.time()) if now is None else now
    issued, expires = claims.get("iat"), claims.get("exp")
    if type(issued) is not int or type(expires) is not int or issued >= expires \
            or issued > current + 30 or expires <= current:
        raise SignerError("handoff bearer lifetime is invalid")
    maximum = auth.get("max_ttl_seconds")
    if type(maximum) is not int or maximum < 1 or maximum > 900 or expires - issued > maximum:
        raise SignerError("handoff bearer lifetime exceeds the locked maximum")
    not_before = claims.get("nbf", issued)
    if type(not_before) is not int or not_before >= expires or not_before > current + 30:
        raise SignerError("handoff bearer is not active")
    audience = claims.get("aud")
    audiences = [audience] if isinstance(audience, str) else audience
    scopes = str(claims.get("scope") or "").split()
    expected = (auth.get("issuer"), auth.get("audience"), auth.get("scope"))
    if claims.get("iss") != expected[0] or audiences != [expected[1]] or scopes != [expected[2]]:
        raise SignerError("handoff bearer authority is not exact")
    if not isinstance(claims.get("sub"), str) or not claims["sub"] \
            or not isinstance(claims.get("jti"), str) or not claims["jti"]:
        raise SignerError("handoff bearer identity is incomplete")
    return {"issuer": expected[0], "audience": expected[1], "scope": expected[2],
            "subject_sha256": hashlib.sha256(claims["sub"].encode()).hexdigest(),
            "jti_sha256": hashlib.sha256(claims["jti"].encode()).hexdigest(), "expires_at": expires}


class _PinnedSignedContent:
    """Private scratch copy whose single open descriptor is the handoff byte authority."""

    def __init__(self, source: Path, expected_sha256: str, expected_size: int, limit: int):
        if not HEX64.fullmatch(expected_sha256) or expected_size < 1 or expected_size > limit:
            raise SignerError("private handoff signed content does not match its address")
        self._temp = tempfile.TemporaryDirectory(prefix="fleet-handoff-pinned-")
        self.path = Path(self._temp.name) / "signed-content.aab"
        source_flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        source_fd = None
        try:
            source_fd = os.open(source, source_flags)
            before = os.fstat(source_fd)
            if not stat.S_ISREG(before.st_mode) or before.st_size != expected_size:
                raise SignerError("private handoff signed content does not match its address")
            output_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
            output_fd = os.open(self.path, output_flags, 0o600)
            digest, total = hashlib.sha256(), 0
            try:
                while chunk := os.read(source_fd, 1024 * 1024):
                    total += len(chunk)
                    if total > limit:
                        raise SignerError("signed content exceeds the locked handoff size limit")
                    digest.update(chunk)
                    view = memoryview(chunk)
                    while view:
                        written = os.write(output_fd, view)
                        if written < 1:
                            raise SignerError("private handoff scratch copy did not make progress")
                        view = view[written:]
                os.fsync(output_fd)
            finally:
                os.close(output_fd)
            after = os.fstat(source_fd)
            identity = lambda value: (value.st_dev, value.st_ino, value.st_size,
                value.st_mtime_ns, value.st_ctime_ns)
            if identity(before) != identity(after) or total != expected_size or digest.hexdigest() != expected_sha256:
                raise SignerError("signed content changed while being pinned for private handoff")
        except Exception:
            self._temp.cleanup()
            raise
        finally:
            if source_fd is not None:
                os.close(source_fd)
        try:
            self._stream = self.path.open("rb", buffering=0)
            self._identity = self._stat_identity(os.fstat(self._stream.fileno()))
            self.expected_sha256, self.expected_size, self.limit = expected_sha256, expected_size, limit
            self.assert_exact()
        except Exception:
            stream = getattr(self, "_stream", None)
            if stream is not None:
                stream.close()
            self._temp.cleanup()
            raise

    @staticmethod
    def _stat_identity(value) -> tuple[int, int, int, int, int]:
        return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns

    def assert_identity(self) -> None:
        descriptor = os.fstat(self._stream.fileno())
        try:
            pathname = os.lstat(self.path)
        except FileNotFoundError:
            raise SignerError("pinned signed content path disappeared during private handoff") from None
        if not stat.S_ISREG(pathname.st_mode) or self._stat_identity(descriptor) != self._identity \
                or self._stat_identity(pathname) != self._identity:
            raise SignerError("pinned signed content identity changed during private handoff")

    def assert_exact(self) -> None:
        self.assert_identity()
        self._stream.seek(0)
        digest, total = hashlib.sha256(), 0
        while chunk := self._stream.read(1024 * 1024):
            total += len(chunk)
            if total > self.limit:
                raise SignerError("signed content exceeds the locked handoff size limit")
            digest.update(chunk)
        self._stream.seek(0)
        self.assert_identity()
        if total != self.expected_size or digest.hexdigest() != self.expected_sha256:
            raise SignerError("pinned signed content bytes changed during private handoff")

    def read(self, size: int) -> bytes:
        return self._stream.read(size)

    def rewind(self) -> None:
        self.assert_identity()
        self._stream.seek(0)

    def close(self) -> None:
        if not self._stream.closed:
            self._stream.close()
        self._temp.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class _StreamingFileBody:
    def __init__(self, content: _PinnedSignedContent, limit: int):
        self.content, self.limit = content, limit
        self.total = 0
        self.digest = hashlib.sha256()
        self.finished = False

    def __iter__(self):
        self.content.rewind()
        while chunk := self.content.read(1024 * 1024):
            self.total += len(chunk)
            if self.total > self.limit:
                raise SignerError("signed content exceeds the locked handoff size limit")
            self.digest.update(chunk)
            yield chunk
        self.finished = True

    def assert_exact(self, expected_size: int, expected_sha256: str) -> None:
        if not self.finished or self.total != expected_size or self.digest.hexdigest() != expected_sha256:
            raise SignerError("signed content changed during private handoff")
        self.content.assert_exact()


class _HandoffReconcileRequired(Exception):
    def __init__(self, conflict: bool):
        super().__init__("private handoff create requires authenticated reconciliation")
        self.conflict = conflict


class SignedContentHandoffClient:
    def __init__(self, endpoint: str, token: str, auth: Mapping[str, Any], json_limit: int,
                 content_limit: int, metadata_limit: int, opener=None, now: int | None = None):
        parsed = urllib.parse.urlparse(endpoint)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password \
                or parsed.query or parsed.fragment or endpoint.endswith("/"):
            raise SignerError("private signed-content handoff endpoint is invalid")
        self.endpoint = endpoint
        self.json_limit, self.content_limit, self.metadata_limit = json_limit, content_limit, metadata_limit
        if min(json_limit, content_limit, metadata_limit) < 1 or metadata_limit > 16 * 1024:
            raise SignerError("private signed-content handoff limits are invalid")
        self.auth_audit = _validate_handoff_bearer(token, auth, now)
        self.authorization = _authorization_value(token, "handoff bearer")
        self.opener = opener or urllib.request.build_opener(_NoRedirect())

    @staticmethod
    def _request(url: str, *, headers: Mapping[str, str], method: str, data=None) -> urllib.request.Request:
        try:
            return urllib.request.Request(url, data=data, method=method, headers=dict(headers))
        except (TypeError, ValueError):
            raise SignerError("private signed-content request was rejected locally") from None

    def _open(self, request: urllib.request.Request, label: str, reconcile_create: bool = False):
        try:
            response = self.opener.open(request, timeout=60)
        except urllib.error.HTTPError as error:
            error.close()
            if reconcile_create and error.code in (409, 412):
                raise _HandoffReconcileRequired(True) from None
            raise SignerError(f"private signed-content {label} outcome is indeterminate") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            if reconcile_create:
                raise _HandoffReconcileRequired(False) from None
            raise SignerError(f"private signed-content {label} outcome is indeterminate") from None
        except (TypeError, ValueError):
            # http.client may echo an invalid Authorization value in ValueError. Never chain or render it.
            raise SignerError("private signed-content request was rejected locally") from None
        if getattr(response, "headers", {}).get("Location"):
            response.close()
            raise SignerError("private signed-content handoff attempted a redirect")
        return response

    @staticmethod
    def _status(response) -> int:
        value = getattr(response, "status", None)
        if value is None and hasattr(response, "getcode"):
            value = response.getcode()
        return int(value or 200)

    def _headers(self, request_sha256: str, metadata: bytes | None = None) -> dict[str, str]:
        headers = {"Authorization": self.authorization, "Accept": "application/json",
            "Idempotency-Key": request_sha256, "User-Agent": "fleet-preview12-private-handoff/1"}
        if metadata is not None:
            encoded = base64.urlsafe_b64encode(metadata).decode().rstrip("=")
            if len(encoded) > self.metadata_limit:
                raise SignerError("private handoff metadata exceeds the locked size limit")
            headers["X-Chummer-Handoff-Request"] = encoded
            headers["X-Chummer-Handoff-Request-Sha256"] = request_sha256
        return headers

    def _read_json(self, response, label: str) -> dict[str, Any]:
        with response:
            return _json_object(_bounded_response_bytes(response, label, self.json_limit), label)

    def _verify_readbacks(self, object_url: str, receipt_url: str, request_sha256: str,
                          expected_receipt: Mapping[str, Any], size: int, digest: str) -> None:
        readback = self._open(self._request(object_url, headers={**self._headers(request_sha256),
            "Accept": "application/vnd.android.aab"}, method="GET"), "content readback")
        if self._status(readback) != 200:
            readback.close()
            raise SignerError("private signed-content readback response is not successful")
        declared = readback.headers.get("Content-Length") if getattr(readback, "headers", None) else None
        if declared is not None and (not declared.isascii() or not declared.isdigit() or int(declared) != size):
            readback.close()
            raise SignerError("private signed-content readback length is not exact")
        total, actual = 0, hashlib.sha256()
        with readback:
            while chunk := readback.read(1024 * 1024):
                total += len(chunk)
                if total > self.content_limit:
                    raise SignerError("private signed-content readback exceeds the locked size limit")
                actual.update(chunk)
        if total != size or actual.hexdigest() != digest:
            raise SignerError("private signed-content readback digest is not exact")
        receipt_readback = self._open(self._request(receipt_url,
            headers=self._headers(request_sha256), method="GET"), "receipt readback")
        if self._status(receipt_readback) != 200 \
                or self._read_json(receipt_readback, "private signed-content receipt readback") != expected_receipt:
            raise SignerError("private signed-content receipt readback is not exact")

    def _create_and_verify_pinned(self, request_value: Mapping[str, Any],
                                  signed: _PinnedSignedContent) -> tuple[dict[str, Any], dict[str, Any]]:
        _validate_handoff_request(request_value)
        metadata = _json_bytes(request_value)
        request_sha256 = hashlib.sha256(metadata).hexdigest()
        content = request_value["content_address"]
        digest, size = str(content["sha256"]), int(content["size_bytes"])
        if not HEX64.fullmatch(digest) or size < 1 or size > self.content_limit \
                or signed.expected_size != size or signed.expected_sha256 != digest:
            raise SignerError("private handoff signed content does not match its address")
        signed.assert_exact()
        object_url = f"{self.endpoint}/objects/sha256/{digest}"
        body = _StreamingFileBody(signed, self.content_limit)
        headers = {**self._headers(request_sha256, metadata), "Content-Type": "application/vnd.android.aab",
            "Content-Length": str(size), "Digest": "sha-256=" + base64.b64encode(bytes.fromhex(digest)).decode(),
            "If-None-Match": "*"}
        expected_receipt = _handoff_service_receipt(request_value, request_sha256)
        receipt_url = f"{self.endpoint}/receipts/sha256/{request_sha256}"
        reconciled = False
        try:
            create = self._request(object_url, data=body, method="PUT", headers=headers)
            response = self._open(create, "create", reconcile_create=True)
            if self._status(response) not in (200, 201):
                response.close()
                raise SignerError("private signed-content create response is not successful")
            remote_receipt = self._read_json(response, "private signed-content create receipt")
            body.assert_exact(size, digest)
            if remote_receipt != expected_receipt:
                raise SignerError("private signed-content create receipt is not exact")
        except _HandoffReconcileRequired as reconcile:
            try:
                self._verify_readbacks(object_url, receipt_url, request_sha256, expected_receipt, size, digest)
                reconciled = True
            except SignerError:
                if reconcile.conflict:
                    raise SignerError(
                        "private signed-content handoff rejected a conflicting immutable object") from None
                raise SignerError("private signed-content create outcome is indeterminate") from None
        signed.assert_exact()
        if not reconciled:
            self._verify_readbacks(object_url, receipt_url, request_sha256, expected_receipt, size, digest)
        return expected_receipt, self.auth_audit

    def create_and_verify(self, request_value: Mapping[str, Any], signed: Path | _PinnedSignedContent) \
            -> tuple[dict[str, Any], dict[str, Any]]:
        _validate_handoff_request(request_value)
        content = request_value["content_address"]
        if isinstance(signed, _PinnedSignedContent):
            return self._create_and_verify_pinned(request_value, signed)
        with _PinnedSignedContent(Path(signed), str(content["sha256"]), int(content["size_bytes"]),
                                  self.content_limit) as pinned:
            return self._create_and_verify_pinned(request_value, pinned)
def _validate_run(run, run_id: int, source, source_sha: str, spec) -> None:
    expected = {"id": run_id, "run_attempt": spec["run_attempt"], "event": spec["event"],
                "head_sha": source_sha, "head_branch": source["source_ref"].removeprefix("refs/heads/"),
                "workflow_id": spec["workflow_id"], "path": spec["workflow_path"],
                "status": "completed", "conclusion": "success"}
    for field, value in expected.items():
        if run.get(field) != value:
            raise SignerError(f"run {run_id} has unexpected {field}")
    for field in ("repository", "head_repository"):
        repo = run.get(field) or {}
        if (repo.get("id"), repo.get("full_name")) != (source["repository_id"], source["repository"]):
            raise SignerError(f"run {run_id} has unexpected {field}")
def _validate_workflow_blob(client, api: str, spec, source_sha: str) -> None:
    path = urllib.parse.quote(spec["workflow_path"], safe="/")
    value = client.get_json(f"{api}/contents/{path}?ref={source_sha}")
    if (value.get("path"), value.get("sha")) != (spec["workflow_path"], spec["workflow_blob_sha"]):
        raise SignerError("workflow path/blob SHA does not match the run commit")
def _validate_source_blob(client, api: str, path: str, blob_sha: str, source_sha: str, label: str) -> None:
    value = client.get_json(f"{api}/contents/{urllib.parse.quote(path, safe='/')}?ref={source_sha}")
    if (value.get("path"), value.get("sha")) != (path, blob_sha):
        raise SignerError(f"{label} path/blob SHA does not match the run commit")
def _validate_artifact(value, artifact_id: int, run_id: int, name: str, digest: str, api: str) -> str:
    expected_url = f"{api}/actions/artifacts/{artifact_id}/zip"
    if (value.get("id"), value.get("name"), value.get("expired"), value.get("digest")) != (
        artifact_id, name, False, f"sha256:{digest}"):
        raise SignerError("artifact identity/digest does not match the locked contract")
    if value.get("workflow_run", {}).get("id") != run_id or value.get("archive_download_url") != expected_url:
        raise SignerError("artifact is not bound to the exact workflow run")
    return expected_url
def _safe_member(bundle: zipfile.ZipFile, expected: str, limit: int) -> zipfile.ZipInfo:
    matches, seen = [], set()
    for member in bundle.infolist():
        pure = PurePosixPath(member.filename)
        if pure.is_absolute() or ".." in pure.parts or member.filename in seen or "\\" in member.filename:
            raise SignerError("unsafe or duplicate artifact member")
        seen.add(member.filename)
        if stat.S_ISLNK(member.external_attr >> 16):
            raise SignerError("artifact contains a symlink")
        if not member.is_dir() and member.filename == expected:
            matches.append(member)
    if len(matches) != 1 or matches[0].file_size > limit:
        raise SignerError("artifact lacks exactly one bounded expected file")
    return matches[0]
def _extract(archive: Path, expected: str, output: Path, limit: int) -> None:
    with zipfile.ZipFile(archive) as bundle:
        member = _safe_member(bundle, expected, limit)
        with bundle.open(member) as source, output.open("wb") as target:
            shutil.copyfileobj(source, target)
def _assert_unsigned_aab(path: Path) -> None:
    try:
        with zipfile.ZipFile(path) as bundle:
            names = [name.upper() for name in bundle.namelist()]
    except zipfile.BadZipFile as error:
        raise SignerError("candidate is not an Android App Bundle ZIP") from error
    signature = re.compile(r"^META-INF/[^/]+\.(SF|RSA|DSA|EC)$")
    if len(names) != len(set(names)) or any(signature.fullmatch(name) for name in names):
        raise SignerError("candidate is already signed or has duplicate members")
def _validate_source_graph(value: dict[str, Any], raw: bytes, lock, source_sha: str,
                           expected_sha256: str) -> None:
    expected_fields = {"contractName", "generatedAtUtc", "authorityState", "publicationAuthorized",
        "releaseIdentity", "generator", "repositories", "packagePins", "ownerPackagePins",
        "dependencyClosure", "presentationSource", "doesNotAssert"}
    if set(value) != expected_fields or value.get("contractName") != SOURCE_GRAPH_CONTRACT \
            or value.get("authorityState") != "local_review_required" \
            or value.get("publicationAuthorized") is not False:
        raise SignerError("release source graph contract/posture is not exact")
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise SignerError("release source graph digest is not exact")
    release = lock["release"]
    if value.get("releaseIdentity") != {"packageId": PACKAGE_ID, "versionName": VERSION_NAME,
            "versionCode": VERSION_CODE, "intentAuthority": "explicit_build_input",
            "minimumExclusiveVersionCode": 11}:
        raise SignerError("release source graph identity is not exact Preview12")
    rows = value.get("repositories")
    if not isinstance(rows, list) or len(rows) != len(SOURCE_REPOSITORIES):
        raise SignerError("release source graph repository inventory is not exact")
    by_name: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"name", "role", "commit", "tree", "tree_sha256", "repository"}:
            raise SignerError("release source graph repository binding is not exact")
        name = row.get("name")
        if name not in SOURCE_REPOSITORIES or name in by_name:
            raise SignerError("release source graph repository inventory is ambiguous")
        role, repository = SOURCE_REPOSITORIES[name]
        if row.get("role") != role or row.get("repository") != repository \
                or not HEX40.fullmatch(str(row.get("commit") or "")) \
                or not HEX40.fullmatch(str(row.get("tree") or "")) \
                or not HEX64.fullmatch(str(row.get("tree_sha256") or "")):
            raise SignerError(f"release source graph repository authority differs: {name}")
        by_name[name] = row
    if set(by_name) != set(SOURCE_REPOSITORIES) or by_name["chummer-android"]["commit"] != source_sha:
        raise SignerError("release source graph does not bind the exact Android source")
    generator = value.get("generator")
    if not isinstance(generator, dict) or set(generator) != {"path", "sha256", "size_bytes"} \
            or not isinstance(generator.get("path"), str) \
            or PurePosixPath(generator["path"]).is_absolute() or ".." in PurePosixPath(generator["path"]).parts \
            or "\\" in generator["path"] or not generator["path"].startswith("scripts/") \
            or not HEX64.fullmatch(str(generator.get("sha256") or "")) \
            or type(generator.get("size_bytes")) is not int or generator["size_bytes"] < 1:
        raise SignerError("release source graph generator authority is not exact")
    for label in ("packagePins", "ownerPackagePins"):
        rows = value.get(label)
        if not isinstance(rows, list) or not rows:
            raise SignerError("release source graph package closure is absent")
        identities: set[str] = set()
        for row in rows:
            package_id = row.get("package_id") if isinstance(row, dict) else None
            if not isinstance(package_id, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,200}", package_id) \
                    or package_id in identities:
                raise SignerError(f"release source graph {label} is malformed or ambiguous")
            identities.add(package_id)
    closure = value.get("dependencyClosure")
    if not isinstance(closure, list) or not closure:
        raise SignerError("release source graph package closure is absent")
    closure_identities: set[str] = set()
    for row in closure:
        package_id = row.get("package_id") if isinstance(row, dict) else None
        dependencies = row.get("dependencies") if isinstance(row, dict) else None
        if not isinstance(package_id, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,200}", package_id) \
                or package_id in closure_identities or not isinstance(dependencies, list) \
                or any(not isinstance(item, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,200}", item)
                       for item in dependencies) or len(dependencies) != len(set(dependencies)):
            raise SignerError("release source graph dependency closure is malformed or ambiguous")
        closure_identities.add(package_id)
    presentation = value.get("presentationSource")
    if not isinstance(presentation, dict) or presentation.get("repository") != "chummer6-ui":
        raise SignerError("release source graph presentation authority is not exact")
    exclusions = value.get("doesNotAssert")
    if not isinstance(exclusions, list) or any(not isinstance(item, str) or not item for item in exclusions) \
            or len(exclusions) != len(set(exclusions)) \
            or not {"google_play_upload", "tester_installation"}.issubset(exclusions):
        raise SignerError("release source graph non-claims are not exact")
    if not isinstance(release.get("source_graph_file_name"), str):
        raise SignerError("release source graph file name is unavailable")
def _validate_proof_exclusion(value: Any, lock, candidate_sha256: str, source_graph_sha256: str) -> str:
    verification = lock["source"]["verification"]
    expected_fields = {"contract_name", "status", "candidate_aab_sha256", "source_graph_sha256",
        "validator_path", "validator_blob_sha", "validation_output_sha256", "publication_authorized"}
    if not isinstance(value, dict) or set(value) != expected_fields \
            or value.get("contract_name") != PROOF_EXCLUSION_CONTRACT or value.get("status") != "pass" \
            or value.get("candidate_aab_sha256") != candidate_sha256 \
            or value.get("source_graph_sha256") != source_graph_sha256 \
            or value.get("validator_path") != verification["proof_exclusion_validator_path"] \
            or value.get("validator_blob_sha") != verification["proof_exclusion_validator_blob_sha"] \
            or value.get("publication_authorized") is not False:
        raise SignerError("proof-exclusion authority does not bind the exact candidate and source graph")
    output_digest = str(value.get("validation_output_sha256") or "")
    if not HEX64.fullmatch(output_digest):
        raise SignerError("proof-exclusion validation output digest is invalid")
    return output_digest
def _producer_receipt_expected(lock, args, source_sha: str, digests: Mapping[str, str]) -> dict[str, Any]:
    source, candidate, verification = lock["source"], lock["source"]["candidate"], lock["source"]["verification"]
    return {
        "contract_name": "chummer_android.preview12_signer_eligibility.v2", "eligible": True,
        "source_repository": source["repository"], "source_repository_id": source["repository_id"],
        "source_ref": source["source_ref"], "source_sha": source_sha,
        "release_identity": {"package_id": PACKAGE_ID, "version_name": VERSION_NAME, "version_code": VERSION_CODE,
            "minimum_sdk": MINIMUM_SDK, "target_sdk": TARGET_SDK},
        "candidate": {"run_id": int(args.candidate_run_id), "run_attempt": candidate["run_attempt"],
            "workflow_id": candidate["workflow_id"], "workflow_path": candidate["workflow_path"],
            "workflow_blob_sha": candidate["workflow_blob_sha"], "artifact_id": int(args.candidate_artifact_id),
            "artifact_name": candidate["artifact_name"], "artifact_sha256": digests["candidate_artifact"],
            "aab_file_name": lock["release"]["candidate_file_name"], "aab_sha256": digests["candidate_aab"],
            "producer_toolchain_closure_sha256": candidate["producer_toolchain_closure_sha256"]},
        "verification": {"run_id": int(args.verification_run_id), "run_attempt": verification["run_attempt"],
            "workflow_id": verification["workflow_id"], "workflow_path": verification["workflow_path"],
            "workflow_blob_sha": verification["workflow_blob_sha"], "artifact_id": int(args.verification_artifact_id),
            "artifact_name": verification["artifact_name"]},
        "source_graph": {"contract_name": SOURCE_GRAPH_CONTRACT,
            "file_name": lock["release"]["source_graph_file_name"], "sha256": digests["source_graph"],
            "android_source_sha": source_sha, "publication_authorized": False},
        "proof_exclusion": {"contract_name": PROOF_EXCLUSION_CONTRACT, "status": "pass",
            "candidate_aab_sha256": digests["candidate_aab"], "source_graph_sha256": digests["source_graph"],
            "validator_path": verification["proof_exclusion_validator_path"],
            "validator_blob_sha": verification["proof_exclusion_validator_blob_sha"],
            "validation_output_sha256": digests["proof_validation_output"], "publication_authorized": False},
        "publication_authorized": False, "play_upload_authorized": False,
    }
def intake(args, lock, lock_bytes: bytes, toolchain, toolchain_bytes: bytes, client) -> dict[str, Any]:
    failures = provisioning_blockers(lock, _full_image(lock) or "", toolchain, toolchain_bytes)
    if failures:
        raise SignerError("; ".join(failures))
    source_sha = args.source_sha.lower()
    digests = {key: getattr(args, f"{key}_sha256").lower() for key in (
        "candidate_artifact", "candidate_aab", "verification_artifact", "verification_receipt")}
    if not HEX40.fullmatch(source_sha) or any(not HEX64.fullmatch(value) for value in digests.values()):
        raise SignerError("source and artifact inputs require exact SHA-1/SHA-256 digests")
    ids = {key: _positive(getattr(args, key), key) for key in (
        "candidate_run_id", "candidate_artifact_id", "verification_run_id", "verification_artifact_id")}
    if ids["candidate_run_id"] == ids["verification_run_id"]:
        raise SignerError("candidate and verification run IDs must be distinct")
    source, api = lock["source"], f"https://api.github.com/repos/{ANDROID_REPOSITORY}"
    for kind in ("candidate", "verification"):
        run_id = ids[f"{kind}_run_id"]
        _validate_run(client.get_json(f"{api}/actions/runs/{run_id}"), run_id, source, source_sha, source[kind])
        _validate_workflow_blob(client, api, source[kind], source_sha)
    verification_spec = source["verification"]
    _validate_source_blob(client, api, verification_spec["proof_exclusion_validator_path"],
                          verification_spec["proof_exclusion_validator_blob_sha"], source_sha,
                          "proof-exclusion validator")
    artifact_urls = {}
    for kind in ("candidate", "verification"):
        artifact_id, run_id = ids[f"{kind}_artifact_id"], ids[f"{kind}_run_id"]
        artifact_urls[kind] = _validate_artifact(
            client.get_json(f"{api}/actions/artifacts/{artifact_id}"), artifact_id, run_id,
            source[kind]["artifact_name"], digests[f"{kind}_artifact"], api)
    output_dir = Path(args.output_dir)
    if output_dir.exists():
        raise SignerError("intake output already exists")
    with tempfile.TemporaryDirectory(prefix="fleet-intake-") as temporary:
        temporary_path = Path(temporary)
        archives = {kind: temporary_path / f"{kind}.zip" for kind in ("candidate", "verification")}
        for kind in archives:
            client.download_to(artifact_urls[kind], archives[kind], int(lock["limits"]["artifact_max_bytes"]))
            if _sha256(archives[kind]) != digests[f"{kind}_artifact"]:
                raise SignerError(f"downloaded {kind} artifact digest mismatch")
        candidate = temporary_path / lock["release"]["candidate_file_name"]
        verification_receipt = temporary_path / source["verification"]["receipt_file_name"]
        source_graph = temporary_path / lock["release"]["source_graph_file_name"]
        _extract(archives["candidate"], candidate.name, candidate, int(lock["limits"]["candidate_max_bytes"]))
        _extract(archives["verification"], verification_receipt.name, verification_receipt,
                 int(lock["limits"]["verification_receipt_max_bytes"]))
        _extract(archives["verification"], source_graph.name, source_graph,
                 int(lock["limits"]["source_graph_max_bytes"]))
        if _sha256(candidate) != digests["candidate_aab"] or _sha256(verification_receipt) != digests["verification_receipt"]:
            raise SignerError("candidate or producer verification receipt digest mismatch")
        _assert_unsigned_aab(candidate)
        receipt_bytes = _bounded_file_bytes(verification_receipt, "producer verification receipt",
                                            int(lock["limits"]["verification_receipt_max_bytes"]))
        producer_receipt = _json_object(receipt_bytes, "producer verification receipt")
        graph_bytes = _bounded_file_bytes(source_graph, "release source graph",
                                          int(lock["limits"]["source_graph_max_bytes"]))
        graph_value = _json_object(graph_bytes, "release source graph")
        graph_claim = producer_receipt.get("source_graph")
        if not isinstance(graph_claim, dict) or set(graph_claim) != {
                "contract_name", "file_name", "sha256", "android_source_sha", "publication_authorized"}:
            raise SignerError("producer receipt source-graph binding is not exact")
        graph_sha = str(graph_claim.get("sha256") or "")
        if not HEX64.fullmatch(graph_sha) or graph_claim != {
                "contract_name": SOURCE_GRAPH_CONTRACT, "file_name": source_graph.name, "sha256": graph_sha,
                "android_source_sha": source_sha, "publication_authorized": False}:
            raise SignerError("producer receipt source-graph authority is invalid")
        _validate_source_graph(graph_value, graph_bytes, lock, source_sha, graph_sha)
        proof_output = _validate_proof_exclusion(producer_receipt.get("proof_exclusion"), lock,
                                                 digests["candidate_aab"], graph_sha)
        expected_digests = {**digests, "source_graph": graph_sha, "proof_validation_output": proof_output}
        if producer_receipt != _producer_receipt_expected(lock, args, source_sha, expected_digests):
            raise SignerError("producer verification receipt does not bind the exact candidate transaction")
        receipt = {"contract_name": "fleet.android_preview12_trusted_intake.v3", "producer": producer_receipt,
            "verification_artifact_sha256": digests["verification_artifact"],
            "verification_receipt_sha256": digests["verification_receipt"],
            "signer_contract_sha256": hashlib.sha256(lock_bytes).hexdigest(),
            "ci_transport_role": "private_actions_artifact_sanitized_intake", "signed_aab_actions_artifact_uploaded": False,
            "play_upload_performed": False, "publication_performed": False}
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=f".{output_dir.name}-", dir=output_dir.parent) as stage_name:
            stage = Path(stage_name)
            shutil.copyfile(candidate, stage / candidate.name)
            shutil.copyfile(source_graph, stage / source_graph.name)
            (stage / "signer.lock.json").write_bytes(lock_bytes)
            (stage / "intake-attestation.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
            os.replace(stage, output_dir)
    return receipt
def _installed_receipt(path: Path, lock, toolchain, toolchain_bytes: bytes) -> None:
    payload = _bounded_file_bytes(path, "installed signer receipt", 1024 * 1024)
    if hashlib.sha256(payload).hexdigest() != lock["toolchain"]["installed_receipt_sha256"]:
        raise SignerError("installed signer receipt digest mismatch")
    actual = _json_object(payload, "installed signer receipt")
    expected = {"contract_name": "fleet.android_preview12_installed_toolchain.v1",
        "lock_sha256": hashlib.sha256(toolchain_bytes).hexdigest(), "base_images": toolchain["base_images"],
        "archives": [{key: item[key] for key in ("name", "version", "url", "sha256")} for item in toolchain["archives"]]}
    if actual != expected:
        raise SignerError("installed signer receipt does not match the full toolchain closure")
def _intake_receipt(path: Path, lock_bytes: bytes, candidate: Path) -> dict[str, Any]:
    lock = _json_object(lock_bytes, "signer contract")
    receipt = _json_object(_bounded_file_bytes(path / "intake-attestation.json", "trusted intake attestation",
                                               int(lock["limits"]["verification_receipt_max_bytes"])),
                           "trusted intake attestation")
    if set(receipt) != {"contract_name", "producer", "verification_artifact_sha256",
            "verification_receipt_sha256", "signer_contract_sha256", "ci_transport_role",
            "signed_aab_actions_artifact_uploaded", "play_upload_performed", "publication_performed"} \
            or receipt.get("contract_name") != "fleet.android_preview12_trusted_intake.v3" \
            or receipt.get("ci_transport_role") != "private_actions_artifact_sanitized_intake" \
            or any(receipt.get(field) is not False for field in (
                "signed_aab_actions_artifact_uploaded", "play_upload_performed", "publication_performed")):
        raise SignerError("trusted intake attestation is missing")
    if receipt.get("signer_contract_sha256") != hashlib.sha256(lock_bytes).hexdigest():
        raise SignerError("signer contract changed after trusted intake")
    expected = receipt.get("producer", {}).get("candidate", {}).get("aab_sha256")
    if not candidate.is_file() or _sha256(candidate) != expected:
        raise SignerError("candidate changed after trusted intake")
    for field in ("verification_artifact_sha256", "verification_receipt_sha256"):
        if not HEX64.fullmatch(str(receipt.get(field) or "")):
            raise SignerError(f"trusted intake {field} is invalid")
    _assert_unsigned_aab(candidate)
    producer = receipt.get("producer")
    if not isinstance(producer, dict):
        raise SignerError("trusted intake producer receipt is invalid")
    source_sha = str(producer.get("source_sha") or "")
    if not HEX40.fullmatch(source_sha):
        raise SignerError("trusted intake Android source is invalid")
    graph_claim = producer.get("source_graph")
    if not isinstance(graph_claim, dict):
        raise SignerError("trusted intake source graph is missing")
    graph_path = path / lock["release"]["source_graph_file_name"]
    graph_bytes = _bounded_file_bytes(graph_path, "trusted intake source graph",
                                      int(lock["limits"]["source_graph_max_bytes"]))
    graph_sha = str(graph_claim.get("sha256") or "")
    _validate_source_graph(_json_object(graph_bytes, "trusted intake source graph"), graph_bytes,
                           lock, source_sha, graph_sha)
    proof_output = _validate_proof_exclusion(producer.get("proof_exclusion"), lock, expected, graph_sha)
    candidate_claim = producer.get("candidate")
    verification_claim = producer.get("verification")
    if not isinstance(candidate_claim, dict) or not isinstance(verification_claim, dict):
        raise SignerError("trusted intake run/artifact authority is missing")
    expected_args = argparse.Namespace(candidate_run_id=candidate_claim.get("run_id"),
        candidate_artifact_id=candidate_claim.get("artifact_id"),
        verification_run_id=verification_claim.get("run_id"),
        verification_artifact_id=verification_claim.get("artifact_id"))
    digests = {"candidate_artifact": candidate_claim.get("artifact_sha256"),
        "candidate_aab": expected, "verification_artifact": receipt["verification_artifact_sha256"],
        "verification_receipt": receipt["verification_receipt_sha256"], "source_graph": graph_sha,
        "proof_validation_output": proof_output}
    if producer != _producer_receipt_expected(lock, expected_args, source_sha, digests):
        raise SignerError("trusted intake producer authority changed after sanitization")
    return receipt
def _runtime(environ: Mapping[str, str]) -> dict[str, str | None]:
    value = {"repository": environ.get("GITHUB_REPOSITORY"), "event": environ.get("GITHUB_EVENT_NAME"),
        "sha": environ.get("GITHUB_SHA"), "workflow_repository": environ.get("FLEET_WORKFLOW_REPOSITORY"),
        "workflow_ref": environ.get("FLEET_WORKFLOW_REF"), "workflow_sha": environ.get("FLEET_WORKFLOW_SHA"),
        "runner_environment": environ.get("RUNNER_ENVIRONMENT"),
        "signing_environment": environ.get("FLEET_SIGNING_ENVIRONMENT"), "run_id": environ.get("GITHUB_RUN_ID"),
        "run_attempt": environ.get("GITHUB_RUN_ATTEMPT")}
    if (value["repository"], value["event"], value["workflow_repository"], value["workflow_ref"],
        value["runner_environment"], value["signing_environment"], value["run_attempt"]) != (
        FLEET_REPOSITORY, "workflow_dispatch", FLEET_REPOSITORY, SIGNER_REF, "github-hosted",
        "android-preview12-signing", "1") or not HEX40.fullmatch(str(value["sha"] or "")) \
            or value["workflow_sha"] != value["sha"] or not str(value["run_id"] or "").isdigit():
        raise SignerError("runtime is not the Fleet-native protected GitHub-hosted signer")
    return value
def _transaction(lock, lock_bytes: bytes, intake_receipt, image: str) -> tuple[str, dict[str, Any]]:
    candidate = intake_receipt["producer"]["candidate"]
    verification = intake_receipt["producer"]["verification"]
    source_graph = intake_receipt["producer"]["source_graph"]
    proof_exclusion = intake_receipt["producer"]["proof_exclusion"]
    bindings = {"source_sha": intake_receipt["producer"]["source_sha"], "candidate_run_id": candidate["run_id"],
        "candidate_artifact_id": candidate["artifact_id"], "candidate_artifact_sha256": candidate["artifact_sha256"],
        "candidate_aab_sha256": candidate["aab_sha256"], "verification_run_id": verification["run_id"],
        "verification_artifact_id": verification["artifact_id"],
        "verification_artifact_sha256": intake_receipt["verification_artifact_sha256"],
        "verification_receipt_sha256": intake_receipt["verification_receipt_sha256"],
        "source_graph_sha256": source_graph["sha256"],
        "proof_exclusion_validator_blob_sha": proof_exclusion["validator_blob_sha"],
        "proof_exclusion_validation_output_sha256": proof_exclusion["validation_output_sha256"],
        "package_id": PACKAGE_ID, "version_name": VERSION_NAME, "version_code": VERSION_CODE,
        "minimum_sdk": MINIMUM_SDK, "target_sdk": TARGET_SDK,
        "upload_certificate_sha256": lock["signing"]["expected_upload_certificate_sha256"],
        "signer_image": image, "signer_contract_sha256": hashlib.sha256(lock_bytes).hexdigest()}
    return hashlib.sha256(_json_bytes(bindings)).hexdigest(), bindings
def reserve(args, lock, lock_bytes, toolchain, toolchain_bytes, environ, client) -> dict[str, Any]:
    failures = provisioning_blockers(lock, args.running_image, toolchain, toolchain_bytes)
    if failures:
        raise SignerError("; ".join(failures))
    candidate_dir = Path(args.candidate_dir)
    receipt = _intake_receipt(candidate_dir, lock_bytes, candidate_dir / lock["release"]["candidate_file_name"])
    _installed_receipt(Path(args.installed_toolchain_receipt), lock, toolchain, toolchain_bytes)
    _runtime(environ)
    transaction_id, bindings = _transaction(lock, lock_bytes, receipt, args.running_image)
    request_value = {"contract_name": "fleet.android_preview12_reservation_request.v2",
                     "transaction_id": transaction_id, "bindings": bindings}
    response = client.reserve(request_value)
    expected = {"contract_name": "fleet.android_preview12_reservation.v2", "decision": "reserved",
        "created": True, "durable": True, "transaction_id": transaction_id,
        "request_sha256": hashlib.sha256(_json_bytes(request_value)).hexdigest(), "bindings": bindings}
    if response == {**expected, "created": False}:
        raise SignerError("reservation already exists; sign-once policy forbids key access")
    if response != expected:
        decision = response.get("decision", "indeterminate") if isinstance(response, dict) else "indeterminate"
        raise SignerError(f"reservation rejected: {decision}")
    evidence = {"contract_name": RESERVATION_EVIDENCE_CONTRACT, "state": "reserved", "durable": True,
        "transaction_id": transaction_id, "request_sha256": expected["request_sha256"], "bindings": bindings}
    output = Path(args.output)
    _write_idempotent_receipt(output, evidence, int(lock["limits"]["reservation_json_max_bytes"]))
    return evidence
def _checked(runner: Callable[..., subprocess.CompletedProcess], command: list[str], **kwargs):
    result = runner(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, **kwargs)
    if result.returncode:
        raise SignerError(f"trusted tool failed: {Path(command[0]).name}")
    return result
def _tool_env(home: str) -> dict[str, str]:
    return {"HOME": home, "TMPDIR": home, "JAVA_HOME": "/opt/jdk", "PATH": "/opt/jdk/bin:/usr/bin:/bin",
            "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TZ": "UTC"}
def _bundle_value(runner, candidate: Path, xpath: str, env) -> str:
    result = _checked(runner, ["/opt/jdk/bin/java", "-jar", "/opt/android-sdk/tools/bundletool.jar", "dump",
        "manifest", f"--bundle={candidate}", f"--xpath={xpath}"], text=True, env=env)
    return result.stdout.strip()
def _validate_candidate_manifest(runner, candidate: Path, env) -> None:
    expected = {
        "/manifest/@package": PACKAGE_ID,
        "/manifest/@android:versionName": VERSION_NAME,
        "/manifest/@android:versionCode": str(VERSION_CODE),
        "/manifest/uses-sdk/@android:minSdkVersion": str(MINIMUM_SDK),
        "/manifest/uses-sdk/@android:targetSdkVersion": str(TARGET_SDK),
    }
    for xpath, value in expected.items():
        if _bundle_value(runner, candidate, xpath, env) != value:
            raise SignerError(f"candidate manifest is not exact for {xpath}")
def _pin_candidate(candidate: Path, output: Path, expected_sha256: str, limit: int) -> None:
    digest = hashlib.sha256()
    total = 0
    with candidate.open("rb") as source, output.open("xb") as target:
        while chunk := source.read(1024 * 1024):
            total += len(chunk)
            if total > limit:
                raise SignerError("candidate exceeds locked size limit while pinning")
            digest.update(chunk)
            target.write(chunk)
    if digest.hexdigest() != expected_sha256:
        raise SignerError("candidate changed before secret-free manifest validation")
    _assert_unsigned_aab(output)
def _pem_der(payload: str) -> bytes:
    match = re.search(r"-----BEGIN CERTIFICATE-----(.*?)-----END CERTIFICATE-----", payload, re.S)
    if not match:
        raise SignerError("signed bundle did not expose a certificate")
    return base64.b64decode(re.sub(r"\s+", "", match.group(1)), validate=True)


def _reservation_receipt(path: Path, lock, transaction_id: str, bindings: Mapping[str, Any]) \
        -> tuple[dict[str, Any], bytes]:
    raw = _bounded_file_bytes(path, "durable reservation receipt",
                              int(lock["limits"]["reservation_json_max_bytes"]))
    value = _json_object(raw, "durable reservation receipt")
    request = {"contract_name": "fleet.android_preview12_reservation_request.v2",
               "transaction_id": transaction_id, "bindings": bindings}
    expected = {"contract_name": RESERVATION_EVIDENCE_CONTRACT, "state": "reserved",
        "durable": True, "transaction_id": transaction_id,
        "request_sha256": hashlib.sha256(_json_bytes(request)).hexdigest(), "bindings": bindings}
    if value != expected:
        raise SignerError("durable reservation receipt is missing or does not bind this transaction")
    return value, raw


def _validate_handoff_request(value: Mapping[str, Any]) -> None:
    expected_fields = {"contract_name", "transaction_id", "content_address", "bindings", "visibility",
        "immutability", "public_url", "publication_authorized", "play_upload_authorized"}
    if not isinstance(value, Mapping) or set(value) != expected_fields \
            or value.get("contract_name") != HANDOFF_REQUEST_CONTRACT \
            or not HEX64.fullmatch(str(value.get("transaction_id") or "")) \
            or value.get("visibility") != "private_authenticated_only" \
            or value.get("immutability") != "create_if_absent" or value.get("public_url") is not None \
            or value.get("publication_authorized") is not False or value.get("play_upload_authorized") is not False:
        raise SignerError("private signed-content handoff request posture is not exact")
    content, bindings = value.get("content_address"), value.get("bindings")
    if not isinstance(content, dict) or set(content) != {"algorithm", "sha256", "size_bytes"} \
            or content.get("algorithm") != "sha256" or not HEX64.fullmatch(str(content.get("sha256") or "")) \
            or type(content.get("size_bytes")) is not int or content["size_bytes"] < 1 \
            or not isinstance(bindings, dict):
        raise SignerError("private signed-content handoff address is not exact")
    digest_fields = {"candidate_artifact_sha256", "candidate_aab_sha256", "verification_artifact_sha256",
        "verification_receipt_sha256", "source_graph_sha256",
        "proof_exclusion_validation_output_sha256", "upload_certificate_sha256", "signer_contract_sha256",
        "reservation_request_sha256", "reservation_receipt_sha256", "signed_attestation_sha256",
        "signed_aab_sha256", "handoff_implementation_sha256", "handoff_endpoint_authority_sha256",
        "handoff_auth_policy_sha256"}
    if any(not HEX64.fullmatch(str(bindings.get(field) or "")) for field in digest_fields) \
            or not HEX40.fullmatch(str(bindings.get("source_sha") or "")) \
            or not HEX40.fullmatch(str(bindings.get("proof_exclusion_validator_blob_sha") or "")) \
            or not HEX40.fullmatch(str(bindings.get("signer_execution_sha") or "")) \
            or bindings.get("signed_aab_sha256") != content["sha256"] \
            or bindings.get("signed_aab_size_bytes") != content["size_bytes"] \
            or bindings.get("package_id") != PACKAGE_ID or bindings.get("version_name") != VERSION_NAME \
            or bindings.get("version_code") != VERSION_CODE or bindings.get("minimum_sdk") != MINIMUM_SDK \
            or bindings.get("target_sdk") != TARGET_SDK \
            or not re.fullmatch(r"[^@]+@sha256:[0-9a-f]{64}", str(bindings.get("signer_image") or "")):
        raise SignerError("private signed-content handoff bindings are not exact")
    for field in ("candidate_run_id", "candidate_artifact_id", "verification_run_id",
                  "verification_artifact_id"):
        if type(bindings.get(field)) is not int or bindings[field] < 1:
            raise SignerError("private signed-content handoff run/artifact identity is not exact")
    if not isinstance(bindings.get("signer_run_id"), str) or not bindings["signer_run_id"].isdigit():
        raise SignerError("private signed-content handoff signer run is not exact")


def _handoff_service_receipt(request_value: Mapping[str, Any], request_sha256: str) -> dict[str, Any]:
    return {"contract_name": HANDOFF_RECEIPT_CONTRACT, "state": "present", "durable": True,
        "visibility": "private_authenticated_only", "immutability": "create_if_absent",
        "request_sha256": request_sha256, "transaction_id": request_value["transaction_id"],
        "content_address": request_value["content_address"], "bindings": request_value["bindings"],
        "public_url": None, "publication_authorized": False, "play_upload_authorized": False}


def _signed_attestation(raw: bytes, value: Mapping[str, Any], transaction_id: str, bindings: Mapping[str, Any],
                        reservation_sha256: str, runtime: Mapping[str, Any], signed_name: str,
                        signed_sha256: str, signed_size: int) -> dict[str, Any]:
    expected = {"contract_name": "fleet.android_preview12_signed_attestation.v3",
        "transaction_id": transaction_id, "bindings": bindings, "signed_file": signed_name,
        "signed_sha256": signed_sha256, "signed_size_bytes": signed_size,
        "reservation_receipt_sha256": reservation_sha256, "github_runtime": runtime,
        "signing_invocations": 1, "ci_evidence_actions_artifact_uploaded": False,
        "signed_content_handoff_performed": False, "play_upload_performed": False,
        "publication_performed": False}
    if value != expected:
        raise SignerError("signed attestation is missing or does not bind the exact signed content")
    return dict(value)


def _write_idempotent_receipt(path: Path, value: Mapping[str, Any], limit: int) -> None:
    payload = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
    if len(payload) > limit:
        raise SignerError("sanitized handoff audit exceeds the locked size limit")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(payload)
    except FileExistsError:
        if _bounded_file_bytes(path, "existing handoff audit", limit) != payload:
            raise SignerError("existing handoff audit conflicts with this immutable transaction")


def handoff(args, lock, lock_bytes, toolchain, toolchain_bytes, environ, client=None,
            runner: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> dict[str, Any]:
    failures = provisioning_blockers(lock, args.running_image, toolchain, toolchain_bytes)
    if failures:
        raise SignerError("; ".join(failures))
    candidate_dir, signed_dir = Path(args.candidate_dir), Path(args.signed_dir)
    candidate = candidate_dir / lock["release"]["candidate_file_name"]
    intake_receipt = _intake_receipt(candidate_dir, lock_bytes, candidate)
    _installed_receipt(Path(args.installed_toolchain_receipt), lock, toolchain, toolchain_bytes)
    runtime = _runtime(environ)
    transaction_id, transaction_bindings = _transaction(lock, lock_bytes, intake_receipt, args.running_image)
    reservation, reservation_raw = _reservation_receipt(
        Path(args.reservation_receipt), lock, transaction_id, transaction_bindings)
    signed = signed_dir / lock["release"]["signed_file_name"]
    reservation_sha256 = hashlib.sha256(reservation_raw).hexdigest()
    attestation_path = signed_dir / "signed-attestation.json"
    attestation_raw = _bounded_file_bytes(attestation_path, "signed attestation",
                                          int(lock["limits"]["handoff_json_max_bytes"]))
    attestation_claim = _json_object(attestation_raw, "signed attestation")
    claimed_sha, claimed_size = attestation_claim.get("signed_sha256"), attestation_claim.get("signed_size_bytes")
    if not HEX64.fullmatch(str(claimed_sha or "")) or type(claimed_size) is not int:
        raise SignerError("signed attestation has an invalid content address")
    handoff_limit = int(lock["limits"]["handoff_content_max_bytes"])
    with _PinnedSignedContent(signed, str(claimed_sha), claimed_size, handoff_limit) as pinned:
        attestation = _signed_attestation(attestation_raw, attestation_claim, transaction_id, transaction_bindings,
            reservation_sha256, runtime, signed.name, pinned.expected_sha256, pinned.expected_size)
        clean_env = _tool_env(tempfile.mkdtemp(prefix="fleet-handoff-verify-"))
        try:
            verify = _checked(runner, ["/opt/jdk/bin/jarsigner", "-verify", "-verbose", "-certs",
                              str(pinned.path)], text=True, env=clean_env)
            if "jar verified." not in verify.stdout:
                raise SignerError("jarsigner did not verify the handoff bundle")
            pinned.assert_exact()
            pem = _checked(runner, ["/opt/jdk/bin/keytool", "-printcert", "-jarfile", str(pinned.path), "-rfc"],
                           text=True, env=clean_env).stdout
            pinned.assert_exact()
            if hashlib.sha256(_pem_der(pem)).hexdigest() != lock["signing"]["expected_upload_certificate_sha256"]:
                raise SignerError("handoff bundle certificate does not match expected upload certificate")
        finally:
            shutil.rmtree(clean_env["HOME"], ignore_errors=True)
        signed_sha256, signed_size = pinned.expected_sha256, pinned.expected_size
        handoff_spec = lock["signed_content_handoff"]
        endpoint_authority_sha256 = hashlib.sha256(
            handoff_spec["private_content_addressed_endpoint"].encode()).hexdigest()
        bindings = {**transaction_bindings, "reservation_request_sha256": reservation["request_sha256"],
            "reservation_receipt_sha256": reservation_sha256,
            "signed_attestation_sha256": hashlib.sha256(attestation_raw).hexdigest(),
            "signed_aab_sha256": signed_sha256, "signed_aab_size_bytes": signed_size,
            "signer_execution_sha": runtime["sha"], "signer_run_id": runtime["run_id"],
            "handoff_implementation_sha256": handoff_spec["audited_implementation_sha256"],
            "handoff_endpoint_authority_sha256": endpoint_authority_sha256,
            "handoff_auth_policy_sha256": hashlib.sha256(_json_bytes(handoff_spec["auth"])).hexdigest()}
        request_value = {"contract_name": HANDOFF_REQUEST_CONTRACT, "transaction_id": transaction_id,
            "content_address": {"algorithm": "sha256", "sha256": signed_sha256, "size_bytes": signed_size},
            "bindings": bindings, "visibility": "private_authenticated_only", "immutability": "create_if_absent",
            "public_url": None, "publication_authorized": False, "play_upload_authorized": False}
        if client is None:
            client = SignedContentHandoffClient(handoff_spec["private_content_addressed_endpoint"],
                environ.get("ANDROID_PREVIEW12_HANDOFF_ACCESS_TOKEN", ""), handoff_spec["auth"],
                int(lock["limits"]["handoff_json_max_bytes"]), handoff_limit,
                int(lock["limits"]["handoff_metadata_max_bytes"]))
        service_receipt, auth_audit = client.create_and_verify(request_value, pinned)
        pinned.assert_exact()
    request_sha256 = hashlib.sha256(_json_bytes(request_value)).hexdigest()
    if service_receipt != _handoff_service_receipt(request_value, request_sha256):
        raise SignerError("private signed-content service receipt changed after readback")
    audit = {"contract_name": HANDOFF_AUDIT_CONTRACT, "status": "verified",
        "transaction_id": transaction_id, "request_sha256": request_sha256,
        "service_receipt_sha256": hashlib.sha256(_json_bytes(service_receipt)).hexdigest(),
        "content_address": request_value["content_address"], "bindings": bindings,
        "endpoint_authority_sha256": endpoint_authority_sha256,
        "auth_context_sha256": hashlib.sha256(_json_bytes(auth_audit)).hexdigest(),
        "durable_readback_verified": True, "private_authenticated_only": True,
        "public_url": None, "signed_aab_actions_artifact_uploaded": False,
        "play_upload_performed": False, "publication_performed": False}
    _write_idempotent_receipt(Path(args.output), audit, int(lock["limits"]["handoff_json_max_bytes"]))
    return audit


def sign(args, lock, lock_bytes, toolchain, toolchain_bytes, environ,
         runner: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> dict[str, Any]:
    failures = provisioning_blockers(lock, args.running_image, toolchain, toolchain_bytes)
    if failures:
        raise SignerError("; ".join(failures))
    candidate_dir = Path(args.candidate_dir)
    candidate = candidate_dir / lock["release"]["candidate_file_name"]
    intake_receipt = _intake_receipt(candidate_dir, lock_bytes, candidate)
    _installed_receipt(Path(args.installed_toolchain_receipt), lock, toolchain, toolchain_bytes)
    runtime = _runtime(environ)
    transaction_id, bindings = _transaction(lock, lock_bytes, intake_receipt, args.running_image)
    _, reservation_raw = _reservation_receipt(Path(args.reservation_receipt), lock, transaction_id, bindings)
    output_dir = Path(args.output_dir)
    if output_dir.exists():
        raise SignerError("signed output already exists")
    with tempfile.TemporaryDirectory(prefix="fleet-secret-free-") as scratch:
        clean_env = _tool_env(scratch)
        pinned_candidate = Path(scratch) / candidate.name
        expected_candidate_sha256 = intake_receipt["producer"]["candidate"]["aab_sha256"]
        _pin_candidate(candidate, pinned_candidate, expected_candidate_sha256,
                       int(lock["limits"]["candidate_max_bytes"]))
        _validate_candidate_manifest(runner, pinned_candidate, clean_env)
        names = ("ANDROID_PREVIEW12_UPLOAD_KEYSTORE_B64", "ANDROID_PREVIEW12_KEYSTORE_PASSWORD",
                 "ANDROID_PREVIEW12_KEY_PASSWORD")
        if any(not environ.get(name) for name in names):
            raise SignerError("signing material is incomplete")
        try:
            keystore_bytes = base64.b64decode(environ[names[0]], validate=True)
        except (ValueError, binascii.Error) as error:
            raise SignerError("keystore secret is not strict base64") from error
        with tempfile.TemporaryDirectory(prefix="fleet-keystore-") as key_temp:
            keystore = Path(key_temp) / "upload.keystore"
            keystore.write_bytes(keystore_bytes)
            keystore.chmod(0o600)
            cert_env = {**clean_env, "FLEET_STOREPASS": environ[names[1]]}
            certificate = _checked(runner, ["/opt/jdk/bin/keytool", "-exportcert", "-alias",
                lock["signing"]["key_alias"], "-keystore", str(keystore), "-storepass:env", "FLEET_STOREPASS"],
                env=cert_env).stdout
            expected_cert = lock["signing"]["expected_upload_certificate_sha256"]
            if hashlib.sha256(certificate).hexdigest() != expected_cert:
                raise SignerError("keystore certificate does not match the expected upload certificate")
            output_dir.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix=f".{output_dir.name}-", dir=output_dir.parent) as stage_name:
                stage, signed = Path(stage_name), Path(stage_name) / lock["release"]["signed_file_name"]
                shutil.copyfile(pinned_candidate, signed)
                sign_env = {**cert_env, "FLEET_KEYPASS": environ[names[2]]}
                _checked(runner, ["/opt/jdk/bin/jarsigner", "-keystore", str(keystore), "-storepass:env",
                    "FLEET_STOREPASS", "-keypass:env", "FLEET_KEYPASS", "-sigalg",
                    lock["signing"]["signature_algorithm"], "-digestalg", lock["signing"]["digest_algorithm"],
                    str(signed), lock["signing"]["key_alias"]], env=sign_env)
                verify = _checked(runner, ["/opt/jdk/bin/jarsigner", "-verify", "-verbose", "-certs", str(signed)],
                                  text=True, env=clean_env)
                if "jar verified." not in verify.stdout:
                    raise SignerError("jarsigner did not verify the signed bundle")
                pem = _checked(runner, ["/opt/jdk/bin/keytool", "-printcert", "-jarfile", str(signed), "-rfc"],
                               text=True, env=clean_env).stdout
                if hashlib.sha256(_pem_der(pem)).hexdigest() != expected_cert:
                    raise SignerError("signed bundle certificate does not match expected upload certificate")
                attestation = {"contract_name": "fleet.android_preview12_signed_attestation.v3",
                    "transaction_id": transaction_id, "bindings": bindings, "signed_file": signed.name,
                    "signed_sha256": _sha256(signed), "signed_size_bytes": signed.stat().st_size,
                    "reservation_receipt_sha256": hashlib.sha256(reservation_raw).hexdigest(),
                    "github_runtime": runtime, "signing_invocations": 1,
                    "ci_evidence_actions_artifact_uploaded": False, "signed_content_handoff_performed": False,
                    "play_upload_performed": False, "publication_performed": False}
                (stage / "signed-attestation.json").write_text(json.dumps(attestation, sort_keys=True, indent=2) + "\n")
                os.replace(stage, output_dir)
    return attestation
def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", required=True, type=Path)
    parser.add_argument("--toolchain-lock", required=True, type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    reusable = commands.add_parser("reusable-preflight")
    for name in ("caller-repository", "caller-repository-id", "caller-ref", "caller-sha", "fleet-verifier-sha", "workflow-repository",
                 "workflow-ref", "workflow-sha", *[field.replace("_", "-") for field in INPUT_FIELDS]):
        reusable.add_argument(f"--{name}", required=True)
    reusable.add_argument("--github-output")
    dispatch = commands.add_parser("dispatch-preflight")
    for name in ("signer-image", "execution-repository", "execution-ref", "execution-ref-protected",
                 "execution-event", "execution-sha", "workflow-repository", "workflow-ref", "workflow-sha",
                 *[field.replace("_", "-") for field in INPUT_FIELDS]):
        dispatch.add_argument(f"--{name}", required=True)
    dispatch.add_argument("--github-output")
    intake_parser = commands.add_parser("intake")
    for name in ("source-sha", "candidate-run-id", "candidate-artifact-id", "candidate-artifact-sha256",
                 "candidate-aab-sha256", "verification-run-id", "verification-artifact-id",
                 "verification-artifact-sha256", "verification-receipt-sha256", "output-dir"):
        intake_parser.add_argument(f"--{name}", required=True)
    reserve_parser = commands.add_parser("reserve")
    for name in ("candidate-dir", "installed-toolchain-receipt", "running-image", "output"):
        reserve_parser.add_argument(f"--{name}", required=True)
    sign_parser = commands.add_parser("sign")
    for name in ("candidate-dir", "installed-toolchain-receipt", "reservation-receipt", "output-dir", "running-image"):
        sign_parser.add_argument(f"--{name}", required=True)
    handoff_parser = commands.add_parser("handoff")
    for name in ("candidate-dir", "signed-dir", "installed-toolchain-receipt", "reservation-receipt",
                 "running-image", "output"):
        handoff_parser.add_argument(f"--{name}", required=True)
    return parser
def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        lock, lock_bytes = _load_lock(args.lock)
        toolchain, toolchain_bytes = _load_toolchain(args.toolchain_lock)
        if args.command == "reusable-preflight":
            value = reusable_preflight(args, lock, toolchain, toolchain_bytes)
        elif args.command == "dispatch-preflight":
            value = dispatch_preflight(args, lock, toolchain, toolchain_bytes)
        elif args.command == "intake":
            value = intake(args, lock, lock_bytes, toolchain, toolchain_bytes,
                GitHubClient(os.environ.get("ANDROID_PREVIEW12_CANDIDATE_BROKER_TOKEN", ""),
                             int(lock["limits"]["api_json_max_bytes"])))
        elif args.command == "reserve":
            value = reserve(args, lock, lock_bytes, toolchain, toolchain_bytes, os.environ,
                ReservationClient(lock["reservation"]["broker_url"],
                                  os.environ.get("ANDROID_PREVIEW12_LEDGER_TOKEN", ""),
                                  int(lock["limits"]["reservation_json_max_bytes"])))
        elif args.command == "sign":
            value = sign(args, lock, lock_bytes, toolchain, toolchain_bytes, os.environ)
        else:
            value = handoff(args, lock, lock_bytes, toolchain, toolchain_bytes, os.environ)
    except (OSError, KeyError, TypeError, ValueError, binascii.Error, json.JSONDecodeError, zipfile.BadZipFile, SignerError) as error:
        print(f"android-preview12-signer: {error}", file=sys.stderr)
        return 2
    print(json.dumps(value, sort_keys=True))
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
