"""Real PR11 client/signature compatibility over the persistent store.

Only the existing public RFC test key signs these TEST responses. This bridge
is neither a deployed HTTPS service nor protected release-signing evidence.
"""
import base64
import importlib.util
import json
from pathlib import Path

import pytest

from scripts import android_preview12_approval_ledger as protocol
from scripts.android_preview12_approval_ledger_store import (
    Conflict, InvalidRequest, NotFound, SQLiteApprovalLedgerStore,
)


_spec = importlib.util.spec_from_file_location(
    "existing_ledger_test_fixture", Path(__file__).with_name("test_android_preview12_approval_ledger.py")
)
fixture = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fixture)
SERVICE = "chummer.preview12.approval-ledger"
DATABASE = "b" * 64
APPROVAL = b'{"testOnly":true,"publicationAuthorized":false}\n'


class PersistentTestTransport:
    def __init__(self, parent):
        parent.mkdir(mode=0o700)
        self.path = parent / "approvals.sqlite3"
        SQLiteApprovalLedgerStore.create(self.path, service_identity=SERVICE, database_id=DATABASE)
        self.drops = {"reserve": 0, "commit": 0}
        self.operations = []

    def __call__(self, url, body, headers, timeout):
        request = protocol.strict_json_bytes(body, "test request", 65536)
        operation = request["operation"]
        policy = fixture.active_ledger_policy()
        assert url == policy["base_url"] + policy[operation + "_path"]
        assert headers["Authorization"] == "Bearer public-test-token"
        assert b"public-test-token" not in body and timeout == 10
        self.operations.append(operation)
        # Every request opens the actual persistent database anew; no in-memory
        # ledger/state double can make recovery pass.
        store = SQLiteApprovalLedgerStore(self.path, service_identity=SERVICE, database_id=DATABASE)
        try:
            receipt = json.loads(store.process(body))
        except (Conflict, InvalidRequest, NotFound) as error:
            status = {Conflict: 409, InvalidRequest: 400, NotFound: 404}[type(error)]
            return protocol.HttpResponse(status, {"Content-Type": "application/json"}, b"{}")
        signed = protocol.pretty_bytes(fixture.sign(receipt))
        if self.drops.get(operation, 0):
            self.drops[operation] -= 1
            raise TimeoutError("test response lost after persistent transaction")
        return protocol.HttpResponse(
            200, {"Content-Type": "application/json", "Content-Length": str(len(signed))}, signed
        )

    def client(self):
        return protocol.DurableApprovalLedgerClient(
            fixture.active_ledger_policy(),
            {protocol.CREDENTIAL_ENV_NAME: "public-test-token"},
            transport=self, sleeper=lambda _: None,
        )


def test_real_signed_protocol_preserves_exact_commit_after_reopening(tmp_path):
    transport = PersistentTestTransport(tmp_path / "ledger")
    subject = fixture.subject()
    reserve = transport.client().reserve(subject)
    commit = transport.client().commit(subject, APPROVAL, reserve)
    recovered = transport.client().reserve(subject)
    assert reserve["receipt"]["revision"] == 1
    assert commit["receipt"]["revision"] == recovered["receipt"]["revision"] == 2
    assert recovered["receipt"]["state"] == "committed"
    assert recovered["receipt"]["reservationId"] == reserve["receipt"]["reservationId"]
    assert recovered["receipt"]["approval"] == commit["receipt"]["approval"]
    assert base64.b64decode(recovered["receipt"]["approval"]["publicJsonBase64"]) == APPROVAL
    assert transport.client().commit(subject, APPROVAL, reserve) == commit


def test_real_client_recovers_after_all_reserve_responses_are_lost(tmp_path):
    transport = PersistentTestTransport(tmp_path / "ledger")
    transport.drops["reserve"] = 3
    subject = fixture.subject()
    reserve = transport.client().reserve(subject)
    assert transport.operations == ["reserve", "reserve", "reserve", "status", "reserve"]
    assert reserve["receipt"]["revision"] == 1
    assert transport.client().reserve(subject) == reserve


def test_real_client_recovers_after_all_commit_responses_are_lost(tmp_path):
    transport = PersistentTestTransport(tmp_path / "ledger")
    subject = fixture.subject()
    reserve = transport.client().reserve(subject)
    transport.drops["commit"] = 3
    recovered = transport.client().commit(subject, APPROVAL, reserve)
    assert transport.operations == ["reserve", "commit", "commit", "commit", "status"]
    assert recovered["receipt"]["operation"] == "status"
    assert recovered["receipt"]["state"] == "committed"
    assert recovered["receipt"]["revision"] == 2
    assert base64.b64decode(recovered["receipt"]["approval"]["publicJsonBase64"]) == APPROVAL


@pytest.mark.parametrize("changes", [
    {"approval_request_nonce": "6" * 64},  # Same artifact, new nonce.
    {"two_green_artifact_id": 9989938591},  # Same nonce, new artifact.
])
def test_real_client_cannot_reuse_either_terminal_uniqueness_subject(tmp_path, changes):
    transport = PersistentTestTransport(tmp_path / "ledger")
    subject = fixture.subject()
    reserve = transport.client().reserve(subject)
    transport.client().commit(subject, APPROVAL, reserve)
    with pytest.raises(protocol.LedgerError, match="HTTP 409"):
        transport.client().reserve(fixture.subject(**changes))
    assert transport.client().reserve(subject)["receipt"]["state"] == "committed"


def test_real_signed_abort_is_permanent_and_cannot_be_committed(tmp_path):
    transport = PersistentTestTransport(tmp_path / "ledger")
    subject = fixture.subject()
    reserve = transport.client().reserve(subject)
    aborted = transport.client().abort(subject, "workflow_interrupted", reserve)
    assert aborted["receipt"]["state"] == "aborted"
    assert transport.client().abort(subject, "workflow_interrupted", reserve) == aborted
    with pytest.raises(protocol.LedgerError, match="previously aborted"):
        transport.client().reserve(subject)
    with pytest.raises(protocol.LedgerError):
        transport.client().commit(subject, APPROVAL, reserve)
    assert transport.client().status(subject, reserve)["receipt"]["state"] == "aborted"
