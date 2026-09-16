"""Binary receipt-server admission only: public keys and disposable fixtures.

No listener, provider, real credential, builder-key custody or signer readiness.
The original server suite retains the approval-lane and real TLS qualifications.
"""
from dataclasses import replace
import base64
import hashlib
import json
import os
from pathlib import Path

import pytest

import test_android_preview12_approval_ledger_server as existing
from scripts import android_preview12_approval_ledger as protocol
from scripts import android_preview12_approval_ledger_server as launcher
from scripts import android_preview12_approval_ledger_store as persistence

certificates = existing.certificates
launch = existing.launch
BINARY_ID = 'd' * 64
BINARY_SERVICE = 'chummer.preview12.binary-signing-ledger'
TOKEN = b'public-distinct-binary-test-token'
TOKEN_DIGEST = hashlib.sha256(TOKEN).hexdigest()
PRIVATE_FIELDS = ('receipt_key_file', 'tls_key_file')


def write_policy(path, value):
    return existing.private_write(Path(path), protocol.pretty_bytes(value))


def reseal(policy, approval, config):
    write_policy(config.comparison_approval_policy, approval)
    policy['approval_policy']['sha256'] = hashlib.sha256(
        Path(config.comparison_approval_policy).read_bytes()).hexdigest()
    write_policy(config.policy, policy)


@pytest.fixture
def binary(launch):
    root, approval, approval_config = launch
    approval['state'] = 'ready'
    approval['external_ed25519_key']['configured'] = True
    comparison_ledger = approval['replay_protection']['external_ledger']
    comparison_ledger.update(
        base_url='https://approval.example.test', allowed_hosts=['approval.example.test'],
        receipt_public_key_spki_der_base64=base64.b64encode(existing.OTHER_PUBLIC_DER).decode(),
        receipt_public_key_spki_sha256=hashlib.sha256(existing.OTHER_PUBLIC_DER).hexdigest())
    policy = json.loads((existing.ROOT / 'config/release/android-preview12-binary-signing-ledger.json').read_bytes())
    policy['state'] = 'ready'
    policy['replay_protection']['external_ledger'] = existing.fixture.active_ledger_policy()
    policy['replay_protection']['external_ledger']['expected_service_identity'] = BINARY_SERVICE
    database = root / 'binary.sqlite3'
    persistence.SQLiteApprovalLedgerStore.create(database, service_identity=BINARY_SERVICE, database_id=BINARY_ID)
    config = replace(approval_config,
        policy=str(root / 'binary-policy.json'), database=str(database), database_id=BINARY_ID,
        bearer_sha256_file=existing.private_write(root / 'binary-bearer.sha256', TOKEN_DIGEST.encode()),
        ledger_lane='binary-signing', comparison_approval_policy=approval_config.policy,
        comparison_approval_bearer_sha256_file=approval_config.bearer_sha256_file)
    reseal(policy, approval, config)
    return root, policy, approval, config, approval_config


def reject_before_store_and_keys(config, monkeypatch, *, no_digest=False):
    forbidden = {getattr(config, name) for name in PRIVATE_FIELDS}
    if no_digest:
        forbidden.update((config.bearer_sha256_file, config.comparison_approval_bearer_sha256_file))
    attempted, stores = [], []
    original_hold = launcher._HeldFile
    original_store = persistence.SQLiteApprovalLedgerStore
    before = Path(config.database).read_bytes()

    def tracked_hold(value, limit):
        if value in forbidden:
            attempted.append(value)
        return original_hold(value, limit)

    def tracked_store(*args, **kwargs):
        stores.append(True)
        return original_store(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(launcher, '_HeldFile', tracked_hold)
        patch.setattr(persistence, 'SQLiteApprovalLedgerStore', tracked_store)
        existing.reject(config)
    assert attempted == [] and stores == []
    assert Path(config.database).read_bytes() == before


def test_binary_startup_composes_existing_store_protocol_tls_without_running(binary):
    _, policy, _, config, approval_config = binary
    before = {path: Path(path).read_bytes() for path in (config.database, approval_config.database)}
    with launcher.prepare(config) as prepared:
        assert prepared.config.loaded and prepared.config.is_ssl and prepared.config.port == 443
        assert prepared.config.proxy_headers is False and prepared.config.workers == 1
        assert not prepared.server.started
        assert {held.path for held in prepared._files} >= {
            Path(config.policy), Path(config.comparison_approval_policy),
            Path(config.bearer_sha256_file), Path(config.comparison_approval_bearer_sha256_file)}
        # The original receipt implementation derives the selected RFC key.
        assert prepared.sign_receipt(protocol.canonical_bytes({'testOnly': True})) == base64.b64decode(
            existing.fixture.sign({'testOnly': True})['signature']['signatureBase64'])
    assert all(Path(path).read_bytes() == raw for path, raw in before.items())
    assert policy['credential_input'] == 'ANDROID_PREVIEW12_BINARY_SIGNING_LEDGER_BEARER_TOKEN'


@pytest.mark.parametrize('field,value', [
    ('ledger_lane', 'unknown'), ('ledger_lane', True),
    ('comparison_approval_policy', None), ('comparison_approval_policy', ''),
    ('comparison_approval_bearer_sha256_file', None), ('comparison_approval_bearer_sha256_file', ''),
])
def test_binary_requires_explicit_complete_launch_arguments(binary, monkeypatch, field, value):
    reject_before_store_and_keys(replace(binary[3], **{field: value}), monkeypatch, no_digest=True)


@pytest.mark.parametrize('field', ('comparison_approval_policy', 'comparison_approval_bearer_sha256_file'))
def test_default_approval_rejects_stray_binary_options(launch, monkeypatch, field):
    config = replace(launch[2], **{field: launch[2].policy})
    existing.reject_before_credentials(config, monkeypatch)


def test_binary_policy_cannot_silently_select_binary_lane(binary, monkeypatch):
    config = replace(binary[3], ledger_lane='approval', comparison_approval_policy=None,
                     comparison_approval_bearer_sha256_file=None)
    reject_before_store_and_keys(config, monkeypatch, no_digest=True)


@pytest.mark.parametrize('defect', ('dormant', 'not-configured', 'approval-wrapper', 'wrong-credential',
                                 'wrong-binding-path', 'extra-wrapper', 'wrong-digest', 'changed-comparison'))
def test_wrong_binary_policy_or_comparison_fails_before_credentials(binary, monkeypatch, defect):
    _, policy, approval, config, _ = binary
    if defect == 'dormant':
        policy['state'] = 'dormant'
    elif defect == 'not-configured':
        policy['replay_protection']['external_ledger'] = protocol.dormant_ledger_policy()
    elif defect == 'approval-wrapper':
        policy = approval
    elif defect == 'wrong-credential':
        policy['credential_input'] = protocol.CREDENTIAL_ENV_NAME
    elif defect == 'wrong-binding-path':
        policy['approval_policy']['path'] = 'other-policy.json'
    elif defect == 'extra-wrapper':
        policy['unknown'] = True
    elif defect == 'wrong-digest':
        policy['approval_policy']['sha256'] = '0' * 64
    elif defect == 'changed-comparison':
        Path(config.comparison_approval_policy).write_bytes(
            Path(config.comparison_approval_policy).read_bytes() + b'\n')
    write_policy(config.policy, policy)
    reject_before_store_and_keys(config, monkeypatch, no_digest=True)


@pytest.mark.parametrize('defect', ('same-origin', 'same-service', 'same-receipt', 'binary-is-approver',
                                 'comparison-is-approver', 'wrong-approver', 'dormant-comparison',
                                 'comparison-key-unconfigured', 'comparison-version-bool', 'shadow-comparison'))
def test_policy_role_and_origin_separation_is_byte_bound(binary, monkeypatch, defect):
    _, policy, approval, config, _ = binary
    selected = policy['replay_protection']['external_ledger']
    compared = approval['replay_protection']['external_ledger']
    approver = approval['external_ed25519_key']
    if defect == 'same-origin':
        selected.update(base_url=compared['base_url'], allowed_hosts=compared['allowed_hosts'])
    elif defect == 'same-service':
        selected['expected_service_identity'] = compared['expected_service_identity']
    elif defect == 'same-receipt':
        for name in ('receipt_public_key_spki_der_base64', 'receipt_public_key_spki_sha256'):
            selected[name] = compared[name]
    elif defect in ('binary-is-approver', 'comparison-is-approver'):
        target = selected if defect == 'binary-is-approver' else compared
        target['receipt_public_key_spki_der_base64'] = approver['public_key_spki_der_base64']
        target['receipt_public_key_spki_sha256'] = approver['expected_public_key_spki_sha256']
    elif defect == 'wrong-approver':
        approver['key_id'] = 'local-release-builder-2026'
    elif defect == 'dormant-comparison':
        approval['state'] = 'dormant'
    elif defect == 'comparison-key-unconfigured':
        approver['configured'] = False
    elif defect == 'comparison-version-bool':
        approval['contract_version'] = True
    else:
        approval['contract_name'] = 'shadow'
    reseal(policy, approval, config)
    reject_before_store_and_keys(config, monkeypatch, no_digest=True)


@pytest.mark.parametrize('defect', ('same', 'same-with-lf', 'alias', 'hardlink', 'invalid', 'uppercase', 'extra-lf'))
def test_bearer_comparison_rejects_reuse_and_unsafe_digest_before_store(binary, monkeypatch, defect):
    config = binary[3]
    path = Path(config.comparison_approval_bearer_sha256_file)
    if defect == 'alias':
        config = replace(config, comparison_approval_bearer_sha256_file=config.bearer_sha256_file)
    elif defect == 'hardlink':
        path.unlink()
        os.link(config.bearer_sha256_file, path)
    else:
        raw = {'same': TOKEN_DIGEST.encode(), 'same-with-lf': TOKEN_DIGEST.encode() + b'\n',
               'invalid': b'bad', 'uppercase': b'A' * 64, 'extra-lf': b'0' * 64 + b'\n\n'}[defect]
        path.write_bytes(raw)
    reject_before_store_and_keys(config, monkeypatch)


@pytest.mark.parametrize('field', ('comparison_approval_policy', 'comparison_approval_bearer_sha256_file'))
@pytest.mark.parametrize('defect', ('missing', 'symlink', 'hardlink', 'nonprivate'))
def test_comparison_files_have_original_private_custody_rules(binary, monkeypatch, field, defect):
    config = binary[3]
    path = Path(getattr(config, field))
    if defect == 'missing':
        path.unlink()
    elif defect == 'symlink':
        path.rename(path.with_suffix('.saved'))
        path.symlink_to(path.with_suffix('.saved'))
    elif defect == 'hardlink':
        os.link(path, path.with_suffix('.linked'))
    else:
        path.chmod(0o640)
    reject_before_store_and_keys(config, monkeypatch)


@pytest.mark.parametrize('field', ('policy', 'comparison_approval_policy', 'bearer_sha256_file',
                                 'comparison_approval_bearer_sha256_file'))
def test_all_four_held_files_are_reasserted_before_database_open(binary, monkeypatch, field):
    config = binary[3]
    original = launcher.PreparedServer._hold

    def replace_after_last_hold(prepared, value, limit):
        held = original(prepared, value, limit)
        if value == config.comparison_approval_bearer_sha256_file:
            path = Path(getattr(config, field))
            replacement = path.with_suffix('.replacement')
            existing.private_write(replacement, path.read_bytes())
            replacement.replace(path)
        return held

    monkeypatch.setattr(launcher.PreparedServer, '_hold', replace_after_last_hold)
    reject_before_store_and_keys(config, monkeypatch)


@pytest.mark.parametrize('field', ('comparison_approval_policy', 'comparison_approval_bearer_sha256_file'))
def test_comparison_file_replacement_after_prepare_revokes_signing_and_http(binary, field, monkeypatch):
    config = binary[3]
    before = Path(config.database).read_bytes()
    with launcher.prepare(config) as prepared:
        path = Path(getattr(config, field))
        replacement = path.with_suffix('.replacement')
        existing.private_write(replacement, path.read_bytes())
        replacement.replace(path)
        with pytest.raises(launcher.LaunchError):
            prepared.sign_receipt(b'{"testOnly":true}')
        processed = []
        monkeypatch.setattr(persistence.SQLiteApprovalLedgerStore, 'process',
                            lambda *args, **kwargs: processed.append(True))
        body = existing.service_fixture.raw_request()
        headers = existing.service_fixture.headers(body, authorization='Bearer ' + TOKEN.decode())
        status, raw, _ = existing.service_fixture.invoke(prepared.app, body=body, raw_headers=headers)
        assert (status, raw) == (503, b'{"error":"service_unavailable"}')
        assert processed == []
    assert Path(config.database).read_bytes() == before


@pytest.mark.parametrize('defect', ('approval-database-with-own-id', 'wrong-id', 'missing'))
def test_selected_service_and_database_identity_are_open_only(binary, monkeypatch, defect):
    _, _, _, config, approval_config = binary
    if defect == 'approval-database-with-own-id':
        config = replace(config, database=approval_config.database, database_id=approval_config.database_id)
    elif defect == 'wrong-id':
        config = replace(config, database_id='e' * 64)
    else:
        Path(config.database).unlink()
    before = Path(config.database).read_bytes() if defect != 'missing' else None
    attempts = []
    original = launcher._HeldFile

    def track(value, limit):
        if value in (config.receipt_key_file, config.tls_key_file):
            attempts.append(value)
        return original(value, limit)

    monkeypatch.setattr(launcher, '_HeldFile', track)
    existing.reject(config)
    assert attempts == []
    assert (Path(config.database).read_bytes() if Path(config.database).exists() else None) == before


@pytest.mark.parametrize('index', (2, 3), ids=('selected-receipt', 'comparison-receipt'))
def test_tls_key_cannot_reuse_either_receipt_role(binary, certificates, monkeypatch, index):
    config = binary[3]
    existing.private_write(Path(config.tls_cert_file), certificates[index][0])
    attempts = []
    original = launcher._HeldFile

    def track(value, limit):
        if value == config.tls_key_file:
            attempts.append(value)
        return original(value, limit)

    monkeypatch.setattr(launcher, '_HeldFile', track)
    existing.reject(config)
    assert attempts == []


def test_cli_carries_only_explicit_binary_files(binary, monkeypatch, capsys):
    config = binary[3]
    fields = ('policy', 'database', 'database_id', *existing.CREDENTIALS, 'bind_address',
              'ledger_lane', 'comparison_approval_policy', 'comparison_approval_bearer_sha256_file')
    arguments = [item for field in fields for item in ('--' + field.replace('_', '-'), getattr(config, field))]
    observed = []

    def capture(options):
        observed.append(options)
        raise launcher.LaunchError('test: no server run')

    monkeypatch.setattr(launcher, 'prepare', capture)
    assert launcher.main(arguments) == 1 and observed == [config]
    assert capsys.readouterr().err == 'ledger_server=unavailable\n'
