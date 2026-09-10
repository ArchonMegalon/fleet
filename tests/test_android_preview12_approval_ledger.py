from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import threading

import pytest


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "config/release/android-preview12-two-green-release-approval.json"
from scripts import android_preview12_approval_ledger as ledger

TEST_SEED = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
TEST_PRIVATE_DER = bytes.fromhex("302e020100300506032b657004220420") + TEST_SEED


def openssl(arguments: list[str], *, pass_fds: tuple[int, ...] = ()) -> bytes:
    result = subprocess.run(
        ["/usr/bin/openssl", *arguments], capture_output=True, check=False,
        timeout=10, env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
        pass_fds=pass_fds,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def public_key() -> bytes:
    descriptor = os.memfd_create("ledger-test-key")
    try:
        os.write(descriptor, TEST_PRIVATE_DER)
        os.lseek(descriptor, 0, os.SEEK_SET)
        return openssl(
            ["pkey", "-inform", "DER", "-in", f"/proc/self/fd/{descriptor}",
             "-pubout", "-outform", "DER"],
            pass_fds=(descriptor,),
        )
    finally:
        os.close(descriptor)


PUBLIC_DER = public_key()


def active_ledger_policy() -> dict:
    value = ledger.dormant_ledger_policy()
    value.update({
        "configured": True,
        "base_url": "https://ledger.example.test",
        "allowed_hosts": ["ledger.example.test"],
        "expected_service_identity": "chummer.preview12.approval-ledger",
        "receipt_public_key_spki_der_base64": base64.b64encode(PUBLIC_DER).decode(),
        "receipt_public_key_spki_sha256": hashlib.sha256(PUBLIC_DER).hexdigest(),
    })
    return value


def subject(**changes: object) -> dict:
    values = {
        "approval_request_nonce": "1" * 64,
        "two_green_artifact_id": 9989938590,
        "two_green_artifact_sha256": "2" * 64,
        "two_green_receipt_sha256": "3" * 64,
        "main_tree": "4" * 40,
        "policy_sha256": "5" * 64,
        "version_name": ledger.VERSION_NAME,
        "version_code": ledger.VERSION_CODE,
    }
    values.update(changes)
    return ledger.make_subject(**values)


def sign(statement: dict) -> dict:
    key_fd = os.memfd_create("ledger-test-private")
    message_fd = os.memfd_create("ledger-test-message")
    try:
        os.write(key_fd, TEST_PRIVATE_DER)
        os.lseek(key_fd, 0, os.SEEK_SET)
        os.write(message_fd, ledger.canonical_bytes(statement))
        os.lseek(message_fd, 0, os.SEEK_SET)
        signature = openssl(
            ["pkeyutl", "-sign", "-rawin", "-inkey", f"/proc/self/fd/{key_fd}",
             "-keyform", "DER", "-in", f"/proc/self/fd/{message_fd}"],
            pass_fds=(key_fd, message_fd),
        )
    finally:
        os.close(key_fd)
        os.close(message_fd)
    return {
        "contractName": ledger.RESPONSE_CONTRACT,
        "contractVersion": 1,
        "receipt": statement,
        "receiptSha256": ledger.canonical_sha256(statement),
        "signature": {
            "algorithm": "Ed25519",
            "publicKeySpkiSha256": hashlib.sha256(PUBLIC_DER).hexdigest(),
            "signatureBase64": base64.b64encode(signature).decode(),
        },
    }


class FakeLedger:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.records: dict[str, dict] = {}
        self.artifacts: dict[int, str] = {}
        self.nonces: dict[str, str] = {}
        self.drop_reserve_responses = 0
        self.drop_commit_responses = 0
        self.requests: list[tuple[str, dict[str, str], bytes]] = []

    def _response(self, request: dict, record: dict) -> ledger.HttpResponse:
        statement = {
            "contractName": ledger.RECEIPT_CONTRACT,
            "contractVersion": 1,
            "serviceIdentity": "chummer.preview12.approval-ledger",
            "requestId": request["requestId"],
            "operation": request["operation"],
            "subject": request["subject"],
            "subjectSha256": request["subjectSha256"],
            "reservationId": record["reservationId"],
            "state": record["state"],
            "revision": record["revision"],
            "reservedAtUtc": record["reservedAtUtc"],
            "updatedAtUtc": record["updatedAtUtc"],
            "leaseExpiresAtUtc": record["leaseExpiresAtUtc"],
            "priorReservation": request.get("priorReservation"),
            "uniquenessSubjects": ledger.UNIQUENESS_SUBJECTS,
            "durabilityClass": "external_durable",
            "exactlyOnce": True,
            "approval": record.get("approval"),
            "abort": record.get("abort"),
        }
        body = ledger.pretty_bytes(sign(statement))
        if request["operation"] == "reserve":
            record["reservationBindings"].add(
                (record["revision"], ledger.canonical_sha256(statement))
            )
        return ledger.HttpResponse(
            200, {"Content-Type": "application/json", "Content-Length": str(len(body))}, body
        )

    def __call__(self, url: str, body: bytes, headers: dict[str, str], timeout: int) -> ledger.HttpResponse:
        request = ledger.strict_json_bytes(body, "test request", 65536)
        assert url.startswith("https://ledger.example.test/")
        assert headers["Authorization"] == "Bearer test-token"
        assert b"test-token" not in body
        assert timeout == 10
        with self.lock:
            self.requests.append((url, dict(headers), body))
            subject_sha = request["subjectSha256"]
            subject_value = request["subject"]
            operation = request["operation"]
            record = self.records.get(subject_sha)
            artifact = subject_value["twoGreenArtifactId"]
            nonce = subject_value["approvalRequestNonce"]
            if operation == "reserve":
                conflict = (
                    artifact in self.artifacts and self.artifacts[artifact] != subject_sha
                ) or (nonce in self.nonces and self.nonces[nonce] != subject_sha)
                if conflict:
                    return ledger.HttpResponse(409, {"Content-Type": "application/json"}, b"{}")
                if record is None:
                    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
                    record = {
                        "reservationId": "rsv_" + subject_sha[:24],
                        "state": "reserved",
                        "revision": 1,
                        "reservedAtUtc": now,
                        "updatedAtUtc": now,
                        "leaseExpiresAtUtc": (
                            datetime.now(timezone.utc).replace(microsecond=0)
                            + timedelta(seconds=900)
                        ).isoformat().replace("+00:00", "Z"),
                        "reservationBindings": set(),
                        "approval": None,
                        "abort": None,
                    }
                    self.records[subject_sha] = record
                    self.artifacts[artifact] = subject_sha
                    self.nonces[nonce] = subject_sha
            elif record is None:
                return ledger.HttpResponse(404, {"Content-Type": "application/json"}, b"{}")
            else:
                prior = request.get("priorReservation")
                if prior is not None and (
                    prior.get("reservationId") != record["reservationId"]
                    or (prior.get("priorRevision"), prior.get("reservationReceiptSha256"))
                    not in record["reservationBindings"]
                ):
                    return ledger.HttpResponse(409, {"Content-Type": "application/json"}, b"{}")
            if operation == "commit":
                if record["state"] == "aborted":
                    return ledger.HttpResponse(409, {"Content-Type": "application/json"}, b"{}")
                incoming = request["approval"]
                if record["state"] == "committed" and record["approval"] != incoming:
                    return ledger.HttpResponse(409, {"Content-Type": "application/json"}, b"{}")
                if record["state"] == "reserved":
                    record.update(
                        state="committed", revision=2, approval=incoming,
                        updatedAtUtc=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    )
                if self.drop_commit_responses:
                    self.drop_commit_responses -= 1
                    raise TimeoutError("response lost after durable commit")
            elif operation == "reserve" and self.drop_reserve_responses:
                self.drop_reserve_responses -= 1
                raise TimeoutError("response lost after durable reserve")
            elif operation == "abort":
                if record["state"] == "committed":
                    return ledger.HttpResponse(409, {"Content-Type": "application/json"}, b"{}")
                reason = {"reasonCode": request["abortReason"]}
                if record["state"] == "aborted" and record["abort"] != reason:
                    return ledger.HttpResponse(409, {"Content-Type": "application/json"}, b"{}")
                if record["state"] == "reserved":
                    record.update(
                        state="aborted", revision=2, abort=reason,
                        updatedAtUtc=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    )
            return self._response(request, record)


def client(fake: FakeLedger, **environment: str) -> ledger.DurableApprovalLedgerClient:
    return ledger.DurableApprovalLedgerClient(
        active_ledger_policy(), {ledger.CREDENTIAL_ENV_NAME: "test-token", **environment},
        transport=fake, sleeper=lambda _: None,
    )


def test_checked_in_ledger_is_dormant_and_contains_no_endpoint_credential_or_key():
    policy = json.loads(POLICY.read_text())
    value = policy["replay_protection"]["external_ledger"]
    assert ledger.validate_ledger_policy(value, require_configured=False) == ledger.dormant_ledger_policy()
    assert value["configured"] is False
    assert value["base_url"] is None
    assert value["allowed_hosts"] == []
    assert value["expected_service_identity"] is None
    assert value["receipt_public_key_spki_der_base64"] is None
    assert ledger.CREDENTIAL_ENV_NAME not in POLICY.read_text().split('"credential_env_name"', 1)[0]


@pytest.mark.parametrize("change", [
    {"base_url": "http://ledger.example.test"},
    {"base_url": "https://evil.example.test"},
    {"allowed_hosts": ["evil.example.test"]},
    {"base_url": "https://user@ledger.example.test"},
    {"base_url": "https://ledger.example.test/path"},
    {"base_url": "https://LEDGER.example.test"},
    {"expected_service_identity": "not valid!"},
    {"receipt_public_key_spki_sha256": "0" * 64},
])
def test_policy_rejects_non_https_unallowlisted_or_wrong_service_authority(change):
    policy = active_ledger_policy()
    policy.update(change)
    with pytest.raises(ledger.LedgerError):
        ledger.validate_ledger_policy(policy, require_configured=True)


def test_missing_environment_credential_fails_before_any_request():
    fake = FakeLedger()
    with pytest.raises(ledger.LedgerError, match="credential"):
        ledger.DurableApprovalLedgerClient(active_ledger_policy(), {}, transport=fake)
    assert fake.requests == []


def test_subject_binds_artifact_nonce_two_green_tree_policy_and_version():
    value = subject()
    assert value == {
        "contractName": ledger.SUBJECT_CONTRACT,
        "contractVersion": 1,
        "approvalRequestNonce": "1" * 64,
        "twoGreenArtifactId": 9989938590,
        "twoGreenArtifactSha256": "2" * 64,
        "twoGreenReceiptSha256": "3" * 64,
        "mainTree": "4" * 40,
        "policySha256": "5" * 64,
        "release": {
            "packageId": ledger.PACKAGE_ID,
            "versionName": ledger.VERSION_NAME,
            "versionCode": ledger.VERSION_CODE,
        },
    }


def test_concurrent_identical_reservations_are_exactly_once_and_idempotent():
    fake = FakeLedger()
    instance = client(fake)
    with ThreadPoolExecutor(max_workers=16) as pool:
        responses = list(pool.map(lambda _: instance.reserve(subject()), range(64)))
    assert {item["receipt"]["reservationId"] for item in responses} == {
        "rsv_" + ledger.canonical_sha256(subject())[:24]
    }
    assert len(fake.records) == 1
    assert all(item["receipt"]["state"] == "reserved" for item in responses)


@pytest.mark.parametrize("changed", [
    {"approval_request_nonce": "6" * 64},
    {"two_green_artifact_id": 9989938591},
])
def test_artifact_and_nonce_are_independently_unique(changed):
    fake = FakeLedger()
    instance = client(fake)
    instance.reserve(subject())
    with pytest.raises(ledger.LedgerError, match="HTTP 409"):
        instance.reserve(subject(**changed))


def test_commit_lost_response_is_reconciled_by_status_and_restores_exact_bytes():
    fake = FakeLedger()
    instance = client(fake)
    reserved = instance.reserve(subject())
    approval = b'{"public":"approval"}\n'
    fake.drop_commit_responses = 3
    committed = instance.commit(subject(), approval, reserved)
    assert committed["receipt"]["operation"] == "status"
    stored = base64.b64decode(committed["receipt"]["approval"]["publicJsonBase64"], validate=True)
    assert stored == approval
    assert fake.records[ledger.canonical_sha256(subject())]["state"] == "committed"


def test_reserve_lost_responses_are_reconciled_before_returning_signed_reserve_snapshot():
    fake = FakeLedger()
    fake.drop_reserve_responses = 3
    reserved = client(fake).reserve(subject())
    assert reserved["receipt"]["operation"] == "reserve"
    assert reserved["receipt"]["state"] == "reserved"
    operations = [
        ledger.strict_json_bytes(body, "request", 65536)["operation"]
        for _, _, body in fake.requests
    ]
    assert operations == ["reserve", "reserve", "reserve", "status", "reserve"]
    assert len(fake.records) == 1


def test_transient_reserve_is_bounded_and_unavailability_fails_closed():
    calls = 0

    def unavailable(*_):
        nonlocal calls
        calls += 1
        raise TimeoutError("offline")

    instance = ledger.DurableApprovalLedgerClient(
        active_ledger_policy(), {ledger.CREDENTIAL_ENV_NAME: "test-token"},
        transport=unavailable, sleeper=lambda _: None,
    )
    with pytest.raises(ledger.LedgerError, match="bounded retries"):
        instance.reserve(subject())
    assert calls == 6


def test_status_is_read_only_and_returns_the_current_signed_revision():
    fake = FakeLedger()
    instance = client(fake)
    reserved = instance.reserve(subject())
    status = instance.status(subject(), reserved)
    assert status["receipt"]["operation"] == "status"
    assert status["receipt"]["reservationId"] == reserved["receipt"]["reservationId"]
    assert status["receipt"]["revision"] == 1
    assert status["receipt"]["state"] == "reserved"


@pytest.mark.parametrize("field,value,match", [
    ("reservationId", "rsv_zzzzzzzzzzzzzzzz", "identity changed"),
    ("revision", 1, "not monotonic"),
])
def test_terminal_receipt_must_continue_exact_reservation_and_revision(field, value, match):
    fake = FakeLedger()
    reserved = client(fake).reserve(subject())

    def hostile(url, body, headers, timeout):
        response = fake(url, body, headers, timeout)
        request = ledger.strict_json_bytes(body, "request", 65536)
        if request["operation"] == "commit" and response.status == 200:
            payload = json.loads(response.body)
            payload["receipt"][field] = value
            payload = sign(payload["receipt"])
            return ledger.HttpResponse(
                200, {"Content-Type": "application/json"}, ledger.pretty_bytes(payload)
            )
        return response

    instance = ledger.DurableApprovalLedgerClient(
        active_ledger_policy(), {ledger.CREDENTIAL_ENV_NAME: "test-token"},
        transport=hostile, sleeper=lambda _: None,
    )
    with pytest.raises(ledger.LedgerError, match=match):
        instance.commit(subject(), b"approval", reserved)


def test_terminal_receipt_cannot_replace_original_reservation_lease_window():
    fake = FakeLedger()
    reserved = client(fake).reserve(subject())

    def hostile(url, body, headers, timeout):
        response = fake(url, body, headers, timeout)
        request = ledger.strict_json_bytes(body, "request", 65536)
        if request["operation"] == "commit" and response.status == 200:
            payload = json.loads(response.body)
            original = datetime.fromisoformat(
                reserved["receipt"]["reservedAtUtc"][:-1] + "+00:00"
            )
            shifted = original - timedelta(seconds=60)
            payload["receipt"]["reservedAtUtc"] = shifted.isoformat().replace("+00:00", "Z")
            payload["receipt"]["leaseExpiresAtUtc"] = (
                shifted + timedelta(seconds=900)
            ).isoformat().replace("+00:00", "Z")
            payload = sign(payload["receipt"])
            return ledger.HttpResponse(
                200, {"Content-Type": "application/json"}, ledger.pretty_bytes(payload)
            )
        return response

    instance = ledger.DurableApprovalLedgerClient(
        active_ledger_policy(), {ledger.CREDENTIAL_ENV_NAME: "test-token"},
        transport=hostile, sleeper=lambda _: None,
    )
    with pytest.raises(ledger.LedgerError, match="lease identity changed"):
        instance.commit(subject(), b"approval", reserved)


def test_terminal_request_binds_reservation_id_revision_and_signed_receipt_digest():
    fake = FakeLedger()
    instance = client(fake)
    reserved = instance.reserve(subject())
    instance.commit(subject(), b"approval", reserved)
    commit_request = ledger.strict_json_bytes(fake.requests[-1][2], "commit request", 65536)
    assert commit_request["operation"] == "commit"
    assert commit_request["priorReservation"] == {
        "reservationId": reserved["receipt"]["reservationId"],
        "priorRevision": reserved["receipt"]["revision"],
        "reservationReceiptSha256": reserved["receiptSha256"],
    }


def test_approval_size_limit_fits_request_envelope_and_rejects_one_byte_over():
    fake = FakeLedger()
    instance = client(fake)
    reserved = instance.reserve(subject())
    result = instance.commit(subject(), b"a" * ledger.MAX_APPROVAL_BYTES, reserved)
    assert result["receipt"]["state"] == "committed"
    commit_body = next(body for url, _, body in fake.requests if url.endswith("/commit"))
    assert len(commit_body) <= active_ledger_policy()["maximum_request_bytes"]

    another = subject(
        approval_request_nonce="7" * 64, two_green_artifact_id=9989938592
    )
    other_reservation = instance.reserve(another)
    with pytest.raises(ledger.LedgerError, match="bounded"):
        instance.commit(
            another, b"a" * (ledger.MAX_APPROVAL_BYTES + 1), other_reservation
        )


def test_abort_is_idempotent_and_commit_after_abort_fails_closed():
    fake = FakeLedger()
    instance = client(fake)
    reserved = instance.reserve(subject())
    first = instance.abort(subject(), "approval_validation_failed", reserved)
    second = instance.abort(subject(), "approval_validation_failed", reserved)
    assert first["receipt"]["reservationId"] == second["receipt"]["reservationId"]
    with pytest.raises(ledger.LedgerError):
        instance.commit(subject(), b"approval", reserved)


def test_status_aware_cleanup_aborts_only_an_open_reservation():
    fake = FakeLedger()
    instance = client(fake)
    reserved = instance.reserve(subject())
    status = instance.status(subject(), reserved)
    cleaned = instance.abort(subject(), "workflow_interrupted", reserved) if status["receipt"]["state"] == "reserved" else status
    assert cleaned["receipt"]["state"] == "aborted"

    committed_subject = subject(
        approval_request_nonce="8" * 64, two_green_artifact_id=9989938593
    )
    committed_reservation = instance.reserve(committed_subject)
    instance.commit(committed_subject, b"approval", committed_reservation)
    terminal = instance.status(committed_subject, committed_reservation)
    cleaned = instance.abort(committed_subject, "workflow_interrupted", committed_reservation) if terminal["receipt"]["state"] == "reserved" else terminal
    assert cleaned["receipt"]["state"] == "committed"


def test_symlink_inputs_and_outputs_fail_without_following(tmp_path: Path):
    policy_target = tmp_path / "policy.json"
    policy_target.write_bytes(POLICY.read_bytes())
    policy_link = tmp_path / "policy-link.json"
    policy_link.symlink_to(policy_target)
    with pytest.raises(ledger.LedgerError, match="non-symlink"):
        ledger.load_policy(policy_link.absolute())

    output_target = tmp_path / "target.json"
    output_target.write_text("unchanged")
    output_link = tmp_path / "receipt.json"
    output_link.symlink_to(output_target)
    with pytest.raises(ledger.LedgerError, match="non-symlink"):
        ledger.atomic_write(output_link.absolute(), b"changed", "receipt")
    assert output_target.read_text() == "unchanged"


def test_html_transient_response_retries_before_strict_success_validation():
    fake = FakeLedger()
    calls = 0

    def transient(url, body, headers, timeout):
        nonlocal calls
        calls += 1
        if calls < 3:
            return ledger.HttpResponse(
                503, {"Content-Type": "text/html"}, b"temporarily unavailable"
            )
        return fake(url, body, headers, timeout)

    instance = ledger.DurableApprovalLedgerClient(
        active_ledger_policy(), {ledger.CREDENTIAL_ENV_NAME: "test-token"},
        transport=transient, sleeper=lambda _: None,
    )
    assert instance.reserve(subject())["receipt"]["state"] == "reserved"
    assert calls == 3


@pytest.mark.parametrize("mutation,match", [
    (lambda response: response.__class__(200, {"Content-Type": "text/plain"}, response.body), "content type"),
    (lambda response: response.__class__(302, {"Content-Type": "application/json"}, response.body), "HTTP 302"),
    (lambda response: response.__class__(200, {"Content-Type": "application/json", "Content-Length": "1"}, response.body), "length"),
    (lambda response: response.__class__(200, {"Content-Type": "application/json"}, b'{"a":1,"a":2}'), "duplicate JSON"),
    (lambda response: response.__class__(200, {"Content-Type": "application/json"}, b'{"value":NaN}'), "non-finite"),
    (lambda response: response.__class__(200, {"Content-Type": "application/json"}, b"x" * 262145), "oversized"),
])
def test_transport_rejects_content_type_redirect_length_and_duplicate_json(mutation, match):
    fake = FakeLedger()

    def hostile(url, body, headers, timeout):
        return mutation(fake(url, body, headers, timeout))

    instance = ledger.DurableApprovalLedgerClient(
        active_ledger_policy(), {ledger.CREDENTIAL_ENV_NAME: "test-token"},
        transport=hostile, sleeper=lambda _: None,
    )
    with pytest.raises(ledger.LedgerError, match=match):
        instance.reserve(subject())


def test_signed_response_rejects_service_subject_and_signature_tampering():
    fake = FakeLedger()
    good = fake(
        "https://ledger.example.test/v1/preview12-approval-reservations/reserve",
        ledger.canonical_bytes(ledger._request("reserve", subject())),
        {"Authorization": "Bearer test-token"}, 10,
    )
    for mutate in (
        lambda value: value["receipt"].update(serviceIdentity="evil.service"),
        lambda value: value["receipt"]["subject"].update(mainTree="f" * 40),
        lambda value: value["signature"].update(signatureBase64=base64.b64encode(b"0" * 64).decode()),
    ):
        value = json.loads(good.body)
        mutate(value)
        response = ledger.HttpResponse(200, {"Content-Type": "application/json"}, ledger.pretty_bytes(value))
        instance = ledger.DurableApprovalLedgerClient(
            active_ledger_policy(), {ledger.CREDENTIAL_ENV_NAME: "test-token"},
            transport=lambda *_: response, sleeper=lambda _: None,
        )
        with pytest.raises(ledger.LedgerError):
            instance.reserve(subject())


@pytest.mark.parametrize("target", ["response", "receipt"])
def test_signed_response_rejects_boolean_contract_versions(target):
    fake = FakeLedger()

    def hostile(url, body, headers, timeout):
        response = fake(url, body, headers, timeout)
        value = json.loads(response.body)
        if target == "response":
            value["contractVersion"] = True
        else:
            value["receipt"]["contractVersion"] = True
            value = sign(value["receipt"])
        return ledger.HttpResponse(
            200, {"Content-Type": "application/json"}, ledger.pretty_bytes(value)
        )

    with pytest.raises(ledger.LedgerError, match="contract|authority"):
        ledger.DurableApprovalLedgerClient(
            active_ledger_policy(), {ledger.CREDENTIAL_ENV_NAME: "test-token"},
            transport=hostile, sleeper=lambda _: None,
        ).reserve(subject())


@pytest.mark.parametrize("configured", [0, 1])
def test_policy_rejects_integer_configured_posture(configured):
    policy = active_ledger_policy()
    policy["configured"] = configured
    with pytest.raises(ledger.LedgerError, match="configured posture"):
        ledger.validate_ledger_policy(policy, require_configured=True)
