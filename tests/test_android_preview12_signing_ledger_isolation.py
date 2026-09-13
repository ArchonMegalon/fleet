"""Two real PR11 databases/clients; RFC keys only, no custody/deployment claim."""
from __future__ import annotations

import ast
import base64
import hashlib
import importlib
import json
import os
from pathlib import Path
import stat
import subprocess
from types import SimpleNamespace

import pytest

import test_android_preview12_external_rebuilder as fixture
import test_android_preview12_protected_transaction as transaction

PR11_HEAD = "e58651b45d69bbb44215d350947a350f1eaf7bd3"
ADAPTER_SHA = "7881a5ca8b7f1ab6bedcd20a9178ef4d82059e1d0137bd780c160bd88bfbe564"
STORE_SHA = "b34f1f9fa0a2084f2ad84682940923cbfdca268f1ec79f98e395be165159eb29"
# Published RFC 8032 vectors 1 and 2, never production credentials.
SEEDS = [
    bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"),
    bytes.fromhex("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb"),
]
PUBLICS = [bytes.fromhex("302a300506032b6570032100" + key) for key in (
    "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
    "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c",
)]
APPROVAL = b'{"contractName":"chummer.android.two-green-release-approval/v1","testOnly":true}\n'
SIGNING = b'{"contractName":"chummer.android.external-release-signer-attestation/v1","testOnly":true}\n'


@pytest.fixture
def pr11(monkeypatch):
    value = os.environ.get("FLEET_PR11_LEDGER_TEST_ROOT")
    if not value:
        pytest.skip("exact reviewed external PR11 client/store source not supplied")
    root = Path(value).resolve(strict=True)
    assert subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                          check=True, capture_output=True, text=True).stdout.strip() == PR11_HEAD
    for name, expected in (("android_preview12_approval_ledger.py", ADAPTER_SHA),
                           ("android_preview12_approval_ledger_store.py", STORE_SHA)):
        assert hashlib.sha256((root / "scripts" / name).read_bytes()).hexdigest() == expected
    monkeypatch.syspath_prepend(str(root))
    protocol = importlib.import_module("scripts.android_preview12_approval_ledger")
    store = importlib.import_module("scripts.android_preview12_approval_ledger_store")
    assert Path(protocol.__file__).resolve() == root / "scripts/android_preview12_approval_ledger.py"
    assert Path(store.__file__).resolve() == root / "scripts/android_preview12_approval_ledger_store.py"
    return root, protocol, store


def lane_policy(protocol, lane):
    policy = protocol.dormant_ledger_policy()
    host = ["approval.example.test", "signing.example.test"][lane]
    policy.update(configured=True, base_url="https://" + host, allowed_hosts=[host],
                  expected_service_identity=["preview12.approval", "preview12.binary-signing"][lane],
                  receipt_public_key_spki_der_base64=base64.b64encode(PUBLICS[lane]).decode(),
                  receipt_public_key_spki_sha256=hashlib.sha256(PUBLICS[lane]).hexdigest())
    return policy


def sign_response(protocol, receipt, lane):
    key_fd, message_fd = os.memfd_create("RFC-key"), os.memfd_create("public-test-receipt")
    try:
        os.write(key_fd, bytes.fromhex("302e020100300506032b657004220420") + SEEDS[lane])
        os.write(message_fd, protocol.canonical_bytes(receipt))
        os.lseek(key_fd, 0, os.SEEK_SET)
        os.lseek(message_fd, 0, os.SEEK_SET)
        signed = subprocess.run(
            ["/usr/bin/openssl", "pkeyutl", "-sign", "-rawin", "-inkey", f"/proc/self/fd/{key_fd}",
             "-keyform", "DER", "-in", f"/proc/self/fd/{message_fd}"],
            pass_fds=(key_fd, message_fd), check=True, capture_output=True, timeout=10,
        ).stdout
    finally:
        os.close(key_fd)
        os.close(message_fd)
    return {"contractName": protocol.RESPONSE_CONTRACT, "contractVersion": 1,
            "receipt": receipt, "receiptSha256": protocol.canonical_sha256(receipt),
            "signature": {"algorithm": "Ed25519", "publicKeySpkiSha256": hashlib.sha256(PUBLICS[lane]).hexdigest(),
                          "signatureBase64": base64.b64encode(signed).decode()}}


class Lane:
    def __init__(self, parent, protocol, store, lane):
        parent.mkdir(mode=0o700)
        self.protocol, self.store, self.lane = protocol, store, lane
        self.policy = lane_policy(protocol, lane)
        self.path, self.database = parent / "ledger.sqlite3", str(lane + 1) * 64
        self.identity = self.policy["expected_service_identity"]
        store.SQLiteApprovalLedgerStore.create(self.path, service_identity=self.identity, database_id=self.database)
        self.drops = 0

    def open(self):
        return self.store.SQLiteApprovalLedgerStore(self.path, service_identity=self.identity, database_id=self.database)

    def transport(self, url, body, headers, timeout):
        request = json.loads(body)
        assert url == self.policy["base_url"] + self.policy[request["operation"] + "_path"]
        assert headers["Authorization"] == f"Bearer test-lane-{self.lane}"
        try:
            receipt = json.loads(self.open().process(body))
        except self.store.Conflict:
            return self.protocol.HttpResponse(409, {"Content-Type": "application/json"}, b"{}")
        response = self.protocol.pretty_bytes(sign_response(self.protocol, receipt, self.lane))
        if request["operation"] == "commit" and self.drops:
            self.drops -= 1
            raise TimeoutError("test lost commit response")
        return self.protocol.HttpResponse(200, {"Content-Type": "application/json", "Content-Length": str(len(response))}, response)

    def client(self):
        return self.protocol.DurableApprovalLedgerClient(
            self.policy, {self.protocol.CREDENTIAL_ENV_NAME: f"test-lane-{self.lane}"},
            transport=self.transport, sleeper=lambda _: None,
        )


def subject(protocol, policy_sha="5" * 64, nonce="1" * 64):
    return protocol.make_subject(
        approval_request_nonce=nonce, two_green_artifact_id=10139431889,
        two_green_artifact_sha256="2" * 64, two_green_receipt_sha256="3" * 64,
        main_tree="4" * 40, policy_sha256=policy_sha, version_name=protocol.VERSION_NAME, version_code=12,
    )


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value if isinstance(value, bytes) else (json.dumps(value, sort_keys=True) + "\n").encode())
    path.chmod(0o600)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def policy_files(tmp_path, pr11):
    root, protocol, _ = pr11
    module = fixture.load_module()
    runtime = tmp_path / "runtime"
    lock = json.loads(fixture.LOCK.read_text())
    signing = json.loads((fixture.ROOT / module.SIGNING_LEDGER_POLICY_PATH).read_text())
    approval = json.loads((root / module.APPROVAL_LEDGER_POLICY_PATH).read_text())
    approval["state"] = "ready"
    approval["external_ed25519_key"]["configured"] = True
    approval["replay_protection"]["external_ledger"] = lane_policy(protocol, 0)
    signing["state"] = "ready"
    signing["replay_protection"]["external_ledger"] = lane_policy(protocol, 1)
    lock["reservation"]["adapter_sha256"] = write(
        runtime / lock["reservation"]["adapter_path"], (root / lock["reservation"]["adapter_path"]).read_bytes())
    return module, runtime, lock, signing, approval


def seal_policies(module, runtime, lock, signing, approval):
    signing["approval_policy"]["sha256"] = write(runtime / module.APPROVAL_LEDGER_POLICY_PATH, approval)
    lock["reservation"]["policy_sha256"] = write(runtime / module.SIGNING_LEDGER_POLICY_PATH, signing)


def load_modeled_root(module, runtime, lock, environment, monkeypatch):
    # Tests model root-owned metadata only; real bytes, path/ancestry guards,
    # digest validation, adapter import, policy parsing and client are unchanged.
    # The existing ancestry-negative suite separately rejects unsafe parents.
    real_stat = Path.stat
    def root_stat(path, *args, **kwargs):
        result = real_stat(path, *args, **kwargs)
        fields = list(result)
        fields[4] = 0
        fields[0] = stat.S_IFMT(result.st_mode) | (0o755 if stat.S_ISDIR(result.st_mode) else 0o644)
        return os.stat_result(fields)
    with monkeypatch.context() as context:
        context.setattr(Path, "stat", root_stat)
        context.setattr(module, "os", SimpleNamespace(**{**vars(os), "getuid": lambda: 0}))
        return module.load_reviewed_ledger(runtime, lock, environment)


class UnreadCredential(dict):
    def __contains__(self, key):
        pytest.fail("invalid policy reached credential inspection")
    def get(self, key, default=None):
        pytest.fail("invalid policy reached credential read")


MUTATIONS = [
    ("same-origin", lambda s, a, l: s["replay_protection"]["external_ledger"].update(base_url=a["replay_protection"]["external_ledger"]["base_url"], allowed_hosts=a["replay_protection"]["external_ledger"]["allowed_hosts"])),
    ("same-service", lambda s, a, l: s["replay_protection"]["external_ledger"].update(expected_service_identity=a["replay_protection"]["external_ledger"]["expected_service_identity"])),
    ("same-receipt-key", lambda s, a, l: s["replay_protection"]["external_ledger"].update({k: a["replay_protection"]["external_ledger"][k] for k in ("receipt_public_key_spki_der_base64", "receipt_public_key_spki_sha256")})),
    ("shadow-policy", lambda s, a, l: a.update(contract_name="shadow")),
    ("not-ready", lambda s, a, l: a.update(state="dormant")),
    ("numeric-configured", lambda s, a, l: a["external_ed25519_key"].update(configured=1)),
    ("malformed-key", lambda s, a, l: a.update(external_ed25519_key=[])),
    ("malformed-key-bytes", lambda s, a, l: a["external_ed25519_key"].update(public_key_spki_der_base64="garbage")),
    ("key-digest-spoof", lambda s, a, l: a["external_ed25519_key"].update(expected_public_key_spki_sha256="0" * 64)),
    ("malformed-replay", lambda s, a, l: a.update(replay_protection=[])),
    ("malformed-ledger", lambda s, a, l: a["replay_protection"].update(external_ledger=[])),
    ("malformed-attestation", lambda s, a, l: l.update(approval_authority=[])),
    ("numeric-signing-version", lambda s, a, l: s.update(contract_version=True)),
    ("dormant-signing", lambda s, a, l: s.update(state="dormant")),
]


@pytest.mark.parametrize("name,mutate", MUTATIONS, ids=[name for name, _ in MUTATIONS])
def test_pinned_policy_conflicts_fail_before_credential_access(tmp_path, pr11, monkeypatch, name, mutate):
    module, runtime, lock, signing, approval = policy_files(tmp_path, pr11)
    mutate(signing, approval, lock)
    seal_policies(module, runtime, lock, signing, approval)
    with pytest.raises(module.RebuilderError):
        load_modeled_root(module, runtime, lock, UnreadCredential(), monkeypatch)


@pytest.mark.parametrize("lane", [0, 1])
@pytest.mark.parametrize("authority", ["approval", "attestation"])
def test_neither_receipt_key_can_be_a_signing_key(tmp_path, pr11, monkeypatch, lane, authority):
    module, runtime, lock, signing, approval = policy_files(tmp_path, pr11)
    if authority == "approval":
        approval["external_ed25519_key"].update(public_key_spki_der_base64=base64.b64encode(PUBLICS[lane]).decode(),
                                             expected_public_key_spki_sha256=hashlib.sha256(PUBLICS[lane]).hexdigest())
    else:
        lock["approval_authority"]["public_key_spki_sha256"] = hashlib.sha256(PUBLICS[lane]).hexdigest()
    seal_policies(module, runtime, lock, signing, approval)
    with pytest.raises(module.RebuilderError, match="receipt key is reused"):
        load_modeled_root(module, runtime, lock, UnreadCredential(), monkeypatch)


@pytest.mark.parametrize("attack", ["old-path", "comparison-replaced", "comparison-symlink", "approval-wrapper"])
def test_loader_rejects_resealed_old_lane_and_substituted_comparison(tmp_path, pr11, monkeypatch, attack):
    module, runtime, lock, signing, approval = policy_files(tmp_path, pr11)
    seal_policies(module, runtime, lock, signing, approval)
    if attack == "old-path":
        lock["reservation"].update(policy_path=module.APPROVAL_LEDGER_POLICY_PATH,
                                  policy_sha256=signing["approval_policy"]["sha256"])
    elif attack == "comparison-replaced":
        approval["state"] = "changed"
        write(runtime / module.APPROVAL_LEDGER_POLICY_PATH, approval)
    elif attack == "comparison-symlink":
        path = runtime / module.APPROVAL_LEDGER_POLICY_PATH
        path.rename(path.with_suffix(".saved"))
        path.symlink_to(path.with_suffix(".saved"))
    else:
        lock["reservation"]["policy_sha256"] = write(runtime / module.SIGNING_LEDGER_POLICY_PATH, approval)
    with pytest.raises(module.RebuilderError):
        load_modeled_root(module, runtime, lock, UnreadCredential(), monkeypatch)


def test_loader_selects_only_signing_credential_and_policy(tmp_path, pr11, monkeypatch):
    module, runtime, lock, signing, approval = policy_files(tmp_path, pr11)
    seal_policies(module, runtime, lock, signing, approval)
    credential = {module.SIGNING_LEDGER_CREDENTIAL_INPUT: "test-signing-only"}
    ledger, client, digest = load_modeled_root(module, runtime, lock, credential, monkeypatch)
    assert client.policy == signing["replay_protection"]["external_ledger"]
    assert digest == lock["reservation"]["policy_sha256"] != signing["approval_policy"]["sha256"]
    assert client._token == "test-signing-only"
    with pytest.raises(module.RebuilderError, match="approval-ledger credential"):
        load_modeled_root(module, runtime, lock, {**credential, ledger.CREDENTIAL_ENV_NAME: "foreign"}, monkeypatch)
    with pytest.raises(RuntimeError, match="durable ledger environment credential is missing or invalid"):
        load_modeled_root(module, runtime, lock, {}, monkeypatch)


def test_two_real_stores_preserve_approval_and_signing_after_lost_response_and_restart(tmp_path, pr11):
    _, protocol, store = pr11
    module = fixture.load_module()
    a, b = Lane(tmp_path / "approval", protocol, store, 0), Lane(tmp_path / "signing", protocol, store, 1)
    approval_subject = subject(protocol)
    prior_a = a.client().reserve(approval_subject)
    committed_a = a.client().commit(approval_subject, APPROVAL, prior_a)
    signing_subject, prior_b = module.reserve_signing_attempt(
        protocol, b.client(), attempt_id="1" * 64, two_green_artifact_id=10139431889,
        two_green_artifact_sha256="2" * 64, two_green_receipt_sha256="3" * 64,
        main_tree="4" * 40, policy_sha256="6" * 64,
    )
    attestation = tmp_path / "external-v1.json"
    write(attestation, SIGNING)
    b.drops = 3
    committed_b = module.commit_signing_attempt(b.client(), signing_subject, prior_b, attestation)
    assert committed_b["receipt"]["operation"] == "status"
    for lane, value, prior, committed, raw in ((a, approval_subject, prior_a, committed_a, APPROVAL),
                                             (b, signing_subject, prior_b, committed_b, SIGNING)):
        cold = lane.client().status(value, prior)
        assert cold["receipt"]["revision"] == 2 and cold["receipt"]["state"] == "committed"
        assert cold["receipt"]["approval"] == committed["receipt"]["approval"]
        assert base64.b64decode(cold["receipt"]["approval"]["publicJsonBase64"]) == raw
        with pytest.raises(protocol.LedgerError, match="HTTP 409"):
            lane.client().reserve({**value, "approvalRequestNonce": "7" * 64})
    # Same database, different policy subject: immutable artifact collision remains.
    with pytest.raises(protocol.LedgerError, match="HTTP 409"):
        a.client().reserve(signing_subject)
    with pytest.raises(store.StoreUnavailable):
        store.SQLiteApprovalLedgerStore(a.path, service_identity=b.identity, database_id=b.database)
    with pytest.raises(store.StoreUnavailable):
        store.SQLiteApprovalLedgerStore(b.path, service_identity=a.identity, database_id=a.database)
    assert a.client().status(approval_subject, prior_a)["receipt"]["approval"] == committed_a["receipt"]["approval"]
    with pytest.raises(module.RebuilderError, match="already terminal"):
        module.reserve_signing_attempt(protocol, b.client(), attempt_id="1" * 64,
            two_green_artifact_id=10139431889, two_green_artifact_sha256="2" * 64,
            two_green_receipt_sha256="3" * 64, main_tree="4" * 40, policy_sha256="6" * 64)


@pytest.mark.parametrize("operation", ["reserve", "commit", "status"])
def test_cross_lane_signed_response_cannot_reach_actual_transaction_key_callback(tmp_path, pr11, monkeypatch, operation):
    _, protocol, store = pr11
    a = Lane(tmp_path / "approval", protocol, store, 0)
    value = subject(protocol)
    reserve = a.client().reserve(value)
    committed = a.client().commit(value, APPROVAL, reserve)
    response = {"reserve": reserve, "commit": committed, "status": a.client().status(value, reserve)}[operation]
    raw = protocol.pretty_bytes(response)
    protocol.validate_response(response, request=protocol._request("reserve", value), policy=a.policy) if operation == "reserve" else None
    client = protocol.DurableApprovalLedgerClient(lane_policy(protocol, 1),
        {protocol.CREDENTIAL_ENV_NAME: "test-lane-1"}, sleeper=lambda _: None,
        transport=lambda *_: protocol.HttpResponse(200, {"Content-Type": "application/json", "Content-Length": str(len(raw))}, raw))
    module = transaction.load_module()
    events = []
    work = tmp_path / "transaction"
    work.mkdir(mode=0o700)
    lock, lock_raw, lease = transaction.fixture(module, work, events)
    transaction.install_fakes(module, monkeypatch, events, lock, lock_raw)
    monkeypatch.setattr(module, "load_reviewed_ledger", lambda *_: (protocol, client, "6" * 64))
    consumer = transaction.fake_consumer(module, lease, events)
    with pytest.raises(protocol.LedgerError):
        module.execute_protected_signer_transaction(work / "lock.json", lambda *_: lease,
            lambda: consumer, work, {}, lambda *_: pytest.fail("foreign receipt admitted signer credentials"),
            lambda **_: pytest.fail("foreign receipt reached protected signed validation"),
            work / "output", attempt_id="d" * 64, two_green_artifact_id=123, two_green_artifact_sha256="e" * 64)
    assert not {"owner-key-preflight", "sign", "android-v2", "external-v1"}.intersection(events)
    assert a.client().status(value, reserve)["receipt"]["approval"] == committed["receipt"]["approval"]


def test_exact_live_reserve_signed_by_approval_lane_is_rejected_before_keys(tmp_path, pr11, monkeypatch):
    _, protocol, store = pr11
    a = Lane(tmp_path / "approval", protocol, store, 0)
    verified_requests = []

    def foreign_service(url, body, headers, timeout):
        request = protocol.strict_json_bytes(body, "actual signing request", 65536)
        assert request["operation"] == "reserve"
        policy_b = lane_policy(protocol, 1)
        assert url == policy_b["base_url"] + policy_b["reserve_path"]
        assert headers["Authorization"] == "Bearer test-lane-1"
        # A receives the identical live B request, not a different subject/op.
        receipt = json.loads(a.open().process(body))
        response = sign_response(protocol, receipt, 0)
        valid_a = protocol.validate_response(response, request=request, policy=a.policy)
        assert valid_a["receipt"]["subject"] == request["subject"]
        assert valid_a["receipt"]["requestId"] == request["requestId"]
        assert valid_a["receipt"]["state"] == "reserved"
        verified_requests.append(body)
        raw = protocol.pretty_bytes(response)
        return protocol.HttpResponse(200, {"Content-Type": "application/json", "Content-Length": str(len(raw))}, raw)

    client = protocol.DurableApprovalLedgerClient(lane_policy(protocol, 1),
        {protocol.CREDENTIAL_ENV_NAME: "test-lane-1"}, sleeper=lambda _: None, transport=foreign_service)
    module = transaction.load_module()
    events = []
    work = tmp_path / "transaction"
    work.mkdir(mode=0o700)
    lock, lock_raw, lease = transaction.fixture(module, work, events)
    transaction.install_fakes(module, monkeypatch, events, lock, lock_raw)
    monkeypatch.setattr(module, "load_reviewed_ledger", lambda *_: (protocol, client, "6" * 64))
    consumer = transaction.fake_consumer(module, lease, events)
    with pytest.raises(protocol.LedgerError, match="durable ledger receipt authority differs"):
        module.execute_protected_signer_transaction(work / "lock.json", lambda *_: lease,
            lambda: consumer, work, {}, lambda *_: pytest.fail("foreign service admitted credentials"),
            lambda **_: pytest.fail("foreign service reached protected signed validation"),
            work / "output", attempt_id="d" * 64, two_green_artifact_id=123, two_green_artifact_sha256="e" * 64)
    assert len(verified_requests) == 1
    assert not {"owner-key-preflight", "sign", "android-v2", "external-v1"}.intersection(events)


def test_execute_and_reconcile_have_one_shared_signing_policy_loader():
    tree = ast.parse(fixture.SCRIPT.read_text())
    for name in ("execute_protected_signer_transaction", "reconcile_protected_signer_transaction"):
        node = next(item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name == name)
        calls = [item for item in ast.walk(node) if isinstance(item, ast.Call) and isinstance(item.func, ast.Name)
                 and item.func.id == "load_reviewed_ledger"]
        assert len(calls) == 1
    lock = json.loads(fixture.LOCK.read_text())
    policy = json.loads((fixture.ROOT / lock["reservation"]["policy_path"]).read_text())
    assert policy["state"] == "dormant" and policy["approval_policy"]["sha256"] is None
    assert policy["replay_protection"]["external_ledger"]["configured"] is False
    assert lock["reservation"]["adapter_sha256"] is None and lock["reservation"]["policy_sha256"] is None
