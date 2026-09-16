"""Private-file IPC and real client validation; no network/deployed authority.

Receipts use the existing PUBLIC RFC fixture, never production signing keys.
Directory ownership uses the test real UID, not a claim of production UID0 custody.
"""
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
from types import SimpleNamespace

import pytest

from scripts import android_preview12_approval_ledger as ledger
from scripts import android_preview12_ledger_bridge as bridge


def load_fixture(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fixture = load_fixture('test_android_preview12_approval_ledger')


def policy():
    value = fixture.active_ledger_policy()
    value['credential_source'] = ledger.BINARY_CONTROLLER_CREDENTIAL_SOURCE
    return value


def directories(tmp_path):
    paths = tmp_path / 'requests', tmp_path / 'responses'
    for path in paths:
        path.mkdir(mode=0o700)
    return paths


def pair(tmp_path, upstream=None):
    paths = directories(tmp_path)
    upstream = upstream or fixture.FakeLedger()
    args = dict(policy=policy(), subject=fixture.subject(), policy_sha256='5' * 64)
    broker = bridge.ControllerBroker(*paths, **args, bearer='test-token', https_transport=upstream)
    transport = bridge.SignerTransport(*paths, **args, sleeper=lambda _: broker.serve_once())
    client = ledger.DurableApprovalLedgerClient.for_binary_bridge(policy(), transport=transport, sleeper=lambda _: None)
    return paths, broker, transport, client, upstream


def test_real_client_all_operations_exact_bytes_no_signer_token(tmp_path, monkeypatch):
    monkeypatch.setenv(ledger.CREDENTIAL_ENV_NAME, 'ambient-approval-must-not-be-read')
    paths, broker, transport, client, upstream = pair(tmp_path)
    assert client._token is None
    prior = client.reserve(fixture.subject())
    assert client.status(fixture.subject(), prior)['receipt']['state'] == 'reserved'
    public = b'{"publicExternalV1Fixture":true}\n'
    committed = client.commit(fixture.subject(), public, prior)
    assert base64.b64decode(committed['receipt']['approval']['publicJsonBase64']) == public
    assert {json.loads(body)['operation'] for _, _, body in upstream.requests} == {'reserve', 'status', 'commit'}
    assert not broker.serve_once()
    for directory in paths:
        for path in directory.iterdir():
            assert path.stat().st_nlink == 1 and path.stat().st_mode & 0o777 == 0o600
            assert b'test-token' not in path.read_bytes()
            assert b'Authorization' not in path.read_bytes()
    other = tmp_path / 'abort'
    other.mkdir(mode=0o700)
    _, _, _, second, _ = pair(other)
    reserved = second.reserve(fixture.subject())
    assert second.abort(fixture.subject(), 'protected_signer_failed', reserved)['receipt']['state'] == 'aborted'


@pytest.mark.parametrize('operation', ['reserve', 'status', 'commit', 'abort'])
def test_no_caller_url_headers_or_subject_drift(tmp_path, operation):
    _, broker, transport, _, upstream = pair(tmp_path)
    raw = ledger.canonical_bytes({**ledger._request(operation, fixture.subject()),
                                 'url': 'https://wrong.invalid', 'headers': {'Authorization': 'bad'}})
    with pytest.raises(bridge.BridgeError):
        transport(raw, 10)
    raw = ledger.canonical_bytes(ledger._request('reserve', fixture.subject(approval_request_nonce='a' * 64)))
    with pytest.raises(bridge.BridgeError):
        transport(raw, 10)
    assert upstream.requests == [] and not broker.serve_once()


@pytest.mark.parametrize('mutation', ['bool', 'policy', 'extra', 'noncanonical'])
def test_strict_request_binding_on_both_sides(tmp_path, mutation):
    paths, broker, transport, _, upstream = pair(tmp_path)
    request = ledger._request('reserve', fixture.subject())
    if mutation == 'bool':
        request['contractVersion'] = True
    elif mutation == 'policy':
        request = ledger._request('reserve', fixture.subject(policy_sha256='9' * 64))
    elif mutation == 'extra':
        request['subject']['unexpected'] = 'x'
    raw = json.dumps(request).encode() if mutation == 'noncanonical' else ledger.canonical_bytes(request)
    with pytest.raises(bridge.BridgeError):
        transport(raw, 10)
    bridge._Directory(paths[0]).publish('a' * 32, raw)
    with pytest.raises(bridge.BridgeError):
        broker.serve_once()
    assert upstream.requests == []


@pytest.mark.parametrize('attack', ['symlink', 'hardlink', 'fifo', 'directory', 'mode', 'oversize'])
def test_unsafe_ready_requests_never_reach_https(tmp_path, attack):
    paths, broker, _, _, upstream = pair(tmp_path)
    directory = bridge._Directory(paths[0])
    key = 'a' * 32
    raw = ledger.canonical_bytes(ledger._request('reserve', fixture.subject()))
    directory.publish(key, raw)
    target = paths[0] / (key + '.body')
    if attack in ('symlink', 'fifo', 'directory'):
        target.unlink()
        if attack == 'symlink':
            target.symlink_to('/dev/null')
        elif attack == 'fifo':
            os.mkfifo(target, 0o600)
        else:
            target.mkdir(mode=0o700)
    elif attack == 'hardlink':
        os.link(target, tmp_path / 'alias')
    elif attack == 'mode':
        target.chmod(0o644)
    else:
        target.write_bytes(b'x' * 65537)
    with pytest.raises(bridge.BridgeError):
        broker.serve_once()
    assert upstream.requests == []


def test_atomic_marker_and_no_replacement(tmp_path):
    paths, broker, _, _, upstream = pair(tmp_path)
    raw = ledger.canonical_bytes(ledger._request('reserve', fixture.subject()))
    body = paths[0] / ('a' * 32 + '.body')
    body.write_bytes(raw)
    body.chmod(0o600)
    assert broker.serve_once() is False  # A complete body without publication marker is not ready.
    with pytest.raises(FileExistsError):
        bridge._Directory(paths[0]).publish('a' * 32, b'changed')
    assert body.read_bytes() == raw and upstream.requests == []


@pytest.mark.parametrize('attack', ['hash', 'status-bool', 'headers', 'oversize', 'stale'])
def test_response_correlation_bounds_and_timeout(tmp_path, attack):
    paths = directories(tmp_path)
    now = [0]
    def respond(_):
        keys = sorted(name[:-6] for name in os.listdir(paths[0]) if name.endswith('.ready'))
        key = keys[-1]
        raw = bridge._Directory(paths[0]).receive(key, 65536)
        value = {'requestSha256': hashlib.sha256(raw).hexdigest(), 'status': 200,
                 'headers': {'content-type': 'application/json'}, 'bodyBase64': 'e30='}
        if attack == 'hash':
            value['requestSha256'] = '0' * 64
        elif attack == 'status-bool':
            value['status'] = True
        elif attack == 'headers':
            value['headers']['location'] = 'https://bad.invalid'
        elif attack == 'oversize':
            value['bodyBase64'] = base64.b64encode(b'x' * 262145).decode()
        elif attack == 'stale':
            key = 'f' * 32
        bridge._Directory(paths[1]).publish(key, ledger.canonical_bytes(value))
        now[0] = 11 if attack == 'stale' else 1
    transport = bridge.SignerTransport(*paths, policy=policy(), subject=fixture.subject(),
        policy_sha256='5' * 64, sleeper=respond, clock=lambda: now[0])
    with pytest.raises(TimeoutError if attack == 'stale' else bridge.BridgeError):
        transport(ledger.canonical_bytes(ledger._request('reserve', fixture.subject())), 10)


@pytest.mark.parametrize('attack', ['forged-signature', 'swapped-response'])
def test_actual_client_still_checks_signed_receipts(tmp_path, attack):
    upstream = fixture.FakeLedger()
    def change(url, raw, headers, timeout):
        response = upstream(url, raw, headers, timeout)
        value = json.loads(response.body)
        if attack == 'forged-signature':
            value['signature']['signatureBase64'] = base64.b64encode(b'x' * 64).decode()
        else:
            value['receipt']['operation'] = 'status'
        body = ledger.canonical_bytes(value)
        return ledger.HttpResponse(200, {'content-type': 'application/json', 'content-length': str(len(body))}, body)
    _, _, _, client, _ = pair(tmp_path, change)
    with pytest.raises(ledger.LedgerError):
        client.reserve(fixture.subject())


def test_policy_variant_explicit_only_and_snapshots(tmp_path):
    local = policy()
    assert ledger.validate_ledger_policy(local, require_configured=True, binary_signing=True) == local
    for invalid in (False, 1, None):
        with pytest.raises(ledger.LedgerError):
            ledger.validate_ledger_policy(local, require_configured=True, binary_signing=invalid)
    with pytest.raises(ledger.LedgerError):
        ledger.DurableApprovalLedgerClient(local, {ledger.CREDENTIAL_ENV_NAME: 'fake'})
    with pytest.raises(ledger.LedgerError):
        ledger.DurableApprovalLedgerClient.for_binary_bridge(fixture.active_ledger_policy(), transport=lambda *_: None)
    dormant = ledger.dormant_ledger_policy()
    dormant['credential_source'] = ledger.BINARY_CONTROLLER_CREDENTIAL_SOURCE
    with pytest.raises(ledger.LedgerError):
        ledger.validate_ledger_policy(dormant, require_configured=False, binary_signing=True)
    paths = directories(tmp_path)
    bound = bridge.SignerTransport(*paths, policy=local, subject=fixture.subject(), policy_sha256='5' * 64)
    local['allowed_hosts'][0] = 'changed.invalid'
    assert bound.binding.policy['allowed_hosts'] == ['ledger.example.test']


@pytest.mark.parametrize('attack', ['same-directory', 'not-private', 'owner', 'swapped-directory', 'too-many'])
def test_endpoint_custody_and_session_bounds(tmp_path, monkeypatch, attack):
    paths, broker, transport, _, upstream = pair(tmp_path)
    if attack == 'same-directory':
        with pytest.raises(bridge.BridgeError):
            bridge.SignerTransport(paths[0], paths[0], policy=policy(), subject=fixture.subject(), policy_sha256='5' * 64)
        return
    if attack == 'not-private':
        paths[0].chmod(0o755)
    elif attack == 'owner':
        monkeypatch.setattr(bridge.os, 'getuid', lambda: 99999)
    elif attack == 'swapped-directory':
        paths[0].rename(tmp_path / 'old')
        paths[0].mkdir(mode=0o700)
    else:
        transport._count = bridge.MAX_EXCHANGES
    with pytest.raises(bridge.BridgeError):
        transport(ledger.canonical_bytes(ledger._request('reserve', fixture.subject())), 10)
    assert upstream.requests == []


@pytest.mark.parametrize('lost', ['reserve', 'commit'])
def test_real_client_lost_response_replay_and_fresh_session(tmp_path, lost):
    paths = directories(tmp_path)
    upstream = fixture.FakeLedger()
    setattr(upstream, 'drop_' + lost + '_responses', 3)
    args = dict(policy=policy(), subject=fixture.subject(), policy_sha256='5' * 64)
    broker = bridge.ControllerBroker(*paths, **args, bearer='test-token', https_transport=upstream)
    now = [0]
    def tick(_):
        now[0] += 1
        try:
            broker.serve_once()
        except bridge.BridgeError:
            pass  # Model controller remaining alive after a lost upstream reply.
    transport = bridge.SignerTransport(*paths, **args, sleeper=tick, clock=lambda: now[0])
    client = ledger.DurableApprovalLedgerClient.for_binary_bridge(policy(), transport=transport, sleeper=lambda _: None)
    prior = client.reserve(fixture.subject())
    committed = client.commit(fixture.subject(), b'{"public":true}\n', prior)
    assert committed['receipt']['state'] == 'committed'
    if lost == 'commit':
        assert committed['receipt']['operation'] == 'status'
    assert len(upstream.records) == 1
    restart = tmp_path / 'new-session'
    restart.mkdir(mode=0o700)
    _, _, _, replay, _ = pair(restart, upstream)
    recovered = replay.commit(fixture.subject(), b'{"public":true}\n', prior)
    assert recovered['receipt']['reservationId'] == committed['receipt']['reservationId']
    assert recovered['receipt']['approval'] == committed['receipt']['approval']


def configured_runtime(tmp_path):
    isolation = load_fixture('test_android_preview12_signing_ledger_isolation')
    root = Path(__file__).resolve().parents[1]
    module, runtime, lock, signing, approval = isolation.policy_files(tmp_path, (root, ledger, None))
    approval['replay_protection']['external_ledger'] = isolation.lane_policy(ledger, 1)
    signing['replay_protection']['external_ledger'] = policy()
    isolation.seal_policies(module, runtime, lock, signing, approval)
    return module, runtime, lock, signing, approval


def modeled_root_load(monkeypatch, loader, module, runtime, lock, environment, **kwargs):
    # Same existing metadata model as the isolation suite. Actual adapter bytes,
    # hashes, wrapper/separation validation, client and receipt verification run.
    real_stat = Path.stat
    def root_stat(path, *args, **options):
        result = real_stat(path, *args, **options)
        fields = list(result)
        fields[4] = 0
        fields[0] = stat.S_IFMT(result.st_mode) | (0o755 if stat.S_ISDIR(result.st_mode) else 0o644)
        return os.stat_result(fields)
    with monkeypatch.context() as patch:
        patch.setattr(Path, 'stat', root_stat)
        patch.setattr(module, 'os', SimpleNamespace(**{**vars(os), 'getuid': lambda: 0}))
        return loader(runtime, lock, environment, **kwargs)


def test_actual_hash_bound_loader_uses_credential_free_bridge(tmp_path, monkeypatch):
    module, runtime, lock, signing, _ = configured_runtime(tmp_path)
    digest = lock['reservation']['policy_sha256']
    subject = fixture.subject(policy_sha256=digest)
    paths = directories(tmp_path)
    args = dict(policy=policy(), subject=subject, policy_sha256=digest)
    upstream = fixture.FakeLedger()
    broker = bridge.ControllerBroker(*paths, **args, bearer='test-token', https_transport=upstream)
    transport = bridge.SignerTransport(*paths, **args, sleeper=lambda _: broker.serve_once())
    actual, client, selected = modeled_root_load(monkeypatch, module.load_reviewed_ledger,
        module, runtime, lock, {}, bridge_transport=transport)
    assert selected == digest and client._token is None
    assert client.reserve(subject)['receipt']['state'] == 'reserved'


@pytest.mark.parametrize('attack', ['missing-bridge', 'approval-token', 'binary-token', 'approval-variant',
                                  'shared-origin', 'shared-service', 'shared-key', 'adapter-swap'])
def test_actual_loader_fails_before_bridge_use(tmp_path, monkeypatch, attack):
    module, runtime, lock, signing, approval = configured_runtime(tmp_path)
    isolation = load_fixture('test_android_preview12_signing_ledger_isolation')
    environment, kwargs = {}, {'bridge_transport': lambda *_: pytest.fail('bridge used before admission')}
    if attack == 'missing-bridge':
        kwargs = {}
    elif attack == 'approval-token':
        environment[ledger.CREDENTIAL_ENV_NAME] = 'not-read'
    elif attack == 'binary-token':
        environment[module.SIGNING_LEDGER_CREDENTIAL_INPUT] = 'not-read'
    elif attack == 'approval-variant':
        approval['replay_protection']['external_ledger']['credential_source'] = ledger.BINARY_CONTROLLER_CREDENTIAL_SOURCE
    elif attack.startswith('shared-'):
        field = {'shared-origin': 'base_url', 'shared-service': 'expected_service_identity',
                 'shared-key': 'receipt_public_key_spki_sha256'}[attack]
        first, second = signing['replay_protection']['external_ledger'], approval['replay_protection']['external_ledger']
        first[field] = second[field]
        if attack == 'shared-origin':
            first['allowed_hosts'] = second['allowed_hosts']
        if attack == 'shared-key':
            first['receipt_public_key_spki_der_base64'] = second['receipt_public_key_spki_der_base64']
    isolation.seal_policies(module, runtime, lock, signing, approval)
    if attack == 'adapter-swap':
        with (runtime / lock['reservation']['adapter_path']).open('ab') as stream:
            stream.write(b'\n# changed\n')
    with pytest.raises(module.RebuilderError):
        modeled_root_load(monkeypatch, module.load_reviewed_ledger, module, runtime, lock, environment, **kwargs)


@pytest.mark.parametrize('flow', ['before-credentials', 'reconcile'])
def test_real_execute_and_reconcile_loader_bridge(tmp_path, monkeypatch, flow):
    transaction = load_fixture('test_android_preview12_protected_transaction')
    module, runtime, ledger_lock, _, _ = configured_runtime(tmp_path)
    events = []
    work = tmp_path / 'transaction'
    work.mkdir(mode=0o700)
    lock, lock_raw, lease = transaction.fixture(module, work, events)
    lock['reservation'] = ledger_lock['reservation']
    original_loader = module.load_reviewed_ledger
    transaction.install_fakes(module, monkeypatch, events, lock, lock_raw)
    subject = ledger.make_subject(approval_request_nonce='d' * 64, two_green_artifact_id=123,
        two_green_artifact_sha256='e' * 64,
        two_green_receipt_sha256=lease.handoff['bindings']['twoGreenReceiptSha256'],
        main_tree=lease.handoff['bindings']['sourceTree'],
        policy_sha256=ledger_lock['reservation']['policy_sha256'],
        version_name=ledger.VERSION_NAME, version_code=ledger.VERSION_CODE)
    paths = directories(tmp_path)
    args = dict(policy=policy(), subject=subject, policy_sha256=subject['policySha256'])
    upstream = fixture.FakeLedger()
    broker = bridge.ControllerBroker(*paths, **args, bearer='test-token', https_transport=upstream)
    transport = bridge.SignerTransport(*paths, **args, sleeper=lambda _: broker.serve_once())
    monkeypatch.setattr(module, 'load_reviewed_ledger', lambda root, checked, environment, **kwargs:
        modeled_root_load(monkeypatch, original_loader, module, root, checked, environment, **kwargs))
    def credential_stop(reservation, _provenance):
        assert reservation['receipt']['state'] == 'reserved'
        events.append('real-ledger-before-credentials')
        if flow == 'before-credentials':
            raise RuntimeError('test stops before any credential or signing')
        return {name: work / name for name in ('keystore', 'storePassword', 'keyPassword', 'ownerPrivateKey')}
    original_write = module._write_or_match
    fail_once = [flow == 'reconcile']
    def lost_commit_record(path, *positional, **keyword):
        if path.name == 'LEDGER_COMMIT.generated.json' and fail_once[0]:
            fail_once[0] = False
            raise OSError('test lost commit record')
        return original_write(path, *positional, **keyword)
    monkeypatch.setattr(module, '_write_or_match', lost_commit_record)
    with pytest.raises((RuntimeError, OSError), match='test (stops|lost commit)'):
        module.execute_protected_signer_transaction(work / 'lock.json', lambda *_: lease,
            lambda: transaction.fake_consumer(module, lease, events), runtime, {}, credential_stop,
            lambda **_: {'status': 'pass'}, work / 'output', attempt_id='d' * 64,
            two_green_artifact_id=123, two_green_artifact_sha256='e' * 64,
            ledger_bridge_transport=transport)
    assert 'real-ledger-before-credentials' in events
    if flow == 'before-credentials':
        assert not {'sign', 'owner-key-preflight', 'android-v2', 'external-v1'}.intersection(events)
    else:
        # Signing/Android functions are the existing MODEL stubs. Ledger loader,
        # file bridge, public RFC receipt verification and recovery are real.
        restart = tmp_path / 'fresh-controller'
        restart.mkdir(mode=0o700)
        new_paths = directories(restart)
        new_broker = bridge.ControllerBroker(*new_paths, **args, bearer='test-token', https_transport=upstream)
        new_transport = bridge.SignerTransport(*new_paths, **args, sleeper=lambda _: new_broker.serve_once())
        result = module.reconcile_protected_signer_transaction(work / 'lock.json', lambda *_: lease,
            lambda: transaction.fake_consumer(module, lease, events), runtime, {}, lambda **_: {'status': 'pass'},
            work / 'output', attempt_id='d' * 64, two_green_artifact_id=123,
            two_green_artifact_sha256='e' * 64, ledger_bridge_transport=new_transport)
        assert result['status'] == 'verified'
        assert events.count('sign') == events.count('real-ledger-before-credentials') == 1
