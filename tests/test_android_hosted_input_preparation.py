"""Cold real-source preparation on synthetic files; no runtime or live authority.

The caller/dependency runtime is the test runner's separately supplied runtime.
Every child blocks network, subprocess, SQLite and operational role entrypoints.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
CALLER = ROOT / "scripts/android_hosted_phase_caller.py"
ERROR = "hosted phase stopped; preserve inputs and reconcile"
TOKEN = "SYNTHETIC_ONLY_CAPTURE_OR_EMISSION_BEARER"


def load_fixture(name):
    spec = importlib.util.spec_from_file_location("_prepare_fixture_" + name, ROOT / "tests" / (name + ".py"))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path, value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    path.write_bytes(raw); path.chmod(0o600)
    return digest(raw)


CHILD = r'''
import importlib.util, json, os, pathlib, sys
p = json.loads(sys.argv[2]); root = pathlib.Path(p['hosted_root']); action = p.get('action', '')
events, reads, violations, live = [], [], [], set()
real_open, real_close, real_sync = os.open, os.close, os.fsync
changed = False
def opening(*args, **kwargs):
    fd = real_open(*args, **kwargs); live.add(fd); return fd
def closing(fd):
    real_close(fd); live.discard(fd)
def sync(fd):
    global changed
    real_sync(fd)
    named = os.readlink('/proc/self/fd/' + str(fd))
    if action == 'unexpected-file' and named == p['job_root'] and not changed:
        changed = True
        (pathlib.Path(p['job_root']) / 'unknown').write_bytes(b'preserve unknown')
    match = ((action == 'directory-fsync' and named == p['job_root'])
             or (action == 'deployment-fsync' and named == p['deployment'])
             or (action == 'bearer-fsync' and named == p['bearer_path']))
    if match and not changed:
        changed = True; raise OSError('synthetic sensitive exception must not print')
os.open, os.close, os.fsync = opening, closing, sync
def audit(event, arguments):
    if event.startswith(('socket.', 'subprocess.', 'os.exec', 'os.spawn', 'os.posix_spawn', 'os.fork')) or event in {'os.system', 'sqlite3.connect'}:
        violations.append(event); raise AssertionError('external operation forbidden')
sys.addaudithook(audit)
for event in ('socket.__new__', 'subprocess.Popen', 'sqlite3.connect'):
    try: sys.audit(event)
    except AssertionError: pass
    else: raise AssertionError('audit guard missing')
violations.clear()
def trace(frame, event, argument):
    if event == 'call' and frame.f_globals.get('__name__', '').startswith(('scripts.', 'android_')):
        name = frame.f_code.co_name
        if name in {'run', 'main', '_request_token', 'capture', 'submit'} or (name == 'stage' and action != 'consume'):
            violations.append(name); raise AssertionError('operational role call forbidden')
        if name in {'render', 'materialize', 'deliver_role_bearer', 'stage'}:
            events.append(name)
    return trace
sys.settrace(trace)
class Injection:
    def get(self, name):
        reads.append(name)
        assert name == 'ANDROID_PREVIEW12_ROLE_BEARER'
        if action == 'environment-profile-drift':
            path = pathlib.Path(p['profile']); path.write_bytes(path.read_bytes() + b' ')
        if action == 'environment-code-drift':
            path = root / 'scripts/android_workflow_identity.py'; path.write_bytes(path.read_bytes() + b' ')
        if action == 'environment-parent-replace':
            path = pathlib.Path(p['job_root']); path.rename(path.with_name('retained-parent')); path.mkdir(mode=0o700)
        return 'wrong-synthetic-bearer' if action == 'wrong-bearer' else p['token']
initial_modules = {name for name in sys.modules if name == 'scripts' or name.startswith(('scripts.', 'android_'))}
initial_path, initial_meta = list(sys.path), list(sys.meta_path)
spec = importlib.util.spec_from_file_location('_chummer_hosted_phase_caller', sys.argv[1])
caller = importlib.util.module_from_spec(spec); spec.loader.exec_module(caller)
arguments = {key: pathlib.Path(p[key]) for key in ('hosted_root', 'profile', 'context', 'job_root', 'deployment')}
arguments.update({key: p[key] for key in ('helper_sha256', 'profile_sha256', 'context_sha256')})
result = {}
try:
    value = caller.prepare_inputs(p['role'], **arguments, environment=Injection())
    result.update(status='accepted', digest=value)
    if action == 'consume':
        with caller._helper(arguments['hosted_root'], arguments['helper_sha256']) as (admission, check):
            with admission.admit(profile=arguments['profile'], profile_sha256=arguments['profile_sha256'],
                    context=arguments['context'], context_sha256=arguments['context_sha256'],
                    hosted_root=arguments['hosted_root']) as lease:
                modules = lease.import_targets(); check(); lease.recheck()
                staged = modules['stager'].stage(role=p['role'], profile=arguments['profile'],
                    profile_sha256=arguments['profile_sha256'], context=arguments['context'],
                    context_sha256=arguments['context_sha256'], deployment=arguments['deployment'],
                    deployment_sha256=value, environment={
                        'ACTIONS_ID_TOKEN_REQUEST_URL': 'https://vstoken.actions.githubusercontent.com/path?x=1',
                        'ACTIONS_ID_TOKEN_REQUEST_TOKEN': 'SYNTHETIC_DISTINCT_REQUEST_TOKEN'})
                assert staged == modules['stager'].COMPLETE
                profile = json.loads(arguments['profile'].read_bytes())
                for path in profile[p['role']]['transport_inputs'].values():
                    item = modules['hosted']._Input(pathlib.Path(path), 16384)
                    try: assert item.read()
                    finally: item.close()
                check(); lease.recheck()
except caller.PhaseError as error:
    result.update(status='rejected', error=str(error))
if p.get('retry'):
    before = list(reads)
    try: caller.prepare_inputs(p['role'], **arguments, environment=Injection())
    except caller.PhaseError as error: result['retry_error'] = str(error)
    else: raise AssertionError('same-process retry accepted')
    assert reads == before
result.update(reads=reads, events=events, violations=violations, fds=len(live),
              modules_restored=initial_modules == {name for name in sys.modules if name == 'scripts' or name.startswith(('scripts.', 'android_'))},
              helper_absent=caller.HELPER not in sys.modules,
              path_restored=initial_path == sys.path, meta_restored=initial_meta == sys.meta_path,
              trace_armed=sys.gettrace() is trace)
print(json.dumps(result))
'''


class Packet:
    def __init__(self, tmp_path, role):
        self.root = tmp_path / "private"; self.root.mkdir(mode=0o700)
        self.source = self.root / "source"; self.source.mkdir(mode=0o700)
        sources = load_fixture("test_android_hosted_phase_caller").current_sources()
        self.pins = {}
        for name, raw in sources.items():
            path = self.source / name; path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            path.write_bytes(raw); path.chmod(0o644); self.pins[name] = digest(raw)
        helper = self.source / "scripts/android_hosted_source_admission.py"
        helper.write_bytes((ROOT / "scripts/android_hosted_source_admission.py").read_bytes()); helper.chmod(0o644)
        fixture = load_fixture("test_android_deployment_materializer")
        self.profile_value, self.context_value = fixture._profile(self.root), fixture._context()
        self.profile_value['owner']['code_pins'] = dict(self.pins)
        self.profile_value['protected']['launcher']['code_pins'] = dict(self.pins)
        parent = self.root / 'jobs'; parent.mkdir(mode=0o700)
        for selected in ('capture', 'emission'):
            job = parent / selected; document = self.profile_value[selected]
            document['transport_inputs'] = {name: str(job / 'transport' / name)
                for name in ('role_bearer', 'oidc_request_url', 'oidc_request_credential')}
            document['attempt_directory'] = str(job / 'attempts' / 'attempt')
            self.profile_value['owner']['bearer_sha256'][selected] = digest(TOKEN.encode())
            for name, pin in document['pins'].items():
                path = Path(pin['path']); raw = ('SYNTHETIC_CA_' + name).encode()
                path.write_bytes(raw); path.chmod(0o600); pin['sha256'] = digest(raw)
        # Owner admission requires distinct role digests, even across separate jobs.
        other = 'emission' if role == 'capture' else 'capture'
        self.profile_value['owner']['bearer_sha256'][other] = digest(b'OTHER_SYNTHETIC_ROLE')
        self.job = parent / role; self.deployment = self.job / 'documents' / 'deployment.json'
        self.profile, self.context = self.root / 'profile.json', self.root / 'context.json'
        self.payload = dict(role=role, token=TOKEN, hosted_root=str(self.source), helper_sha256=digest(helper.read_bytes()),
            profile=str(self.profile), context=str(self.context), job_root=str(self.job), deployment=str(self.deployment),
            bearer_path=self.profile_value[role]['transport_inputs']['role_bearer'])
        self.seal()
        self.expected = fixture.materializer.render(self.profile_value, self.context_value, role)

    def seal(self):
        self.payload['profile_sha256'] = write_json(self.profile, self.profile_value)
        self.payload['context_sha256'] = write_json(self.context, self.context_value)

    def invoke(self, **options):
        result = subprocess.run([sys.executable, '-I', '-B', '-c', CHILD, str(CALLER), json.dumps({**self.payload, **options})],
            env={'PATH': os.defpath, 'LANG': 'C', 'LC_ALL': 'C'}, cwd=self.root, capture_output=True, text=True, timeout=25)
        assert result.returncode == 0, result.stderr
        assert result.stderr == '' and TOKEN not in result.stdout
        value = json.loads(result.stdout)
        assert value['fds'] == 0 and value['modules_restored'] and value['helper_absent']
        assert value['path_restored'] and value['meta_restored'] and value['trace_armed']
        assert value['violations'] == []
        return value


@pytest.fixture(params=['capture', 'emission'])
def packet(tmp_path, request):
    return Packet(tmp_path, request.param)


def rejected(result, *, reads=0):
    assert result['status'] == 'rejected' and result['error'] == ERROR
    assert len(result['reads']) == reads


def test_real_preparation_creates_only_private_deployment_and_bearer(packet):
    result = packet.invoke(retry=True)
    assert result['status'] == 'accepted' and result['digest'] == digest(packet.expected)
    assert result['retry_error'] == ERROR
    assert result['reads'] == ['ANDROID_PREVIEW12_ROLE_BEARER']
    assert result['events'].count('materialize') == result['events'].count('deliver_role_bearer') == 1
    assert 'stage' not in result['events'] and packet.deployment.read_bytes() == packet.expected
    assert Path(packet.payload['bearer_path']).read_bytes() == TOKEN.encode()
    document = packet.profile_value[packet.payload['role']]
    assert not Path(document['attempt_directory']).exists()
    assert all(not Path(document['transport_inputs'][name]).exists() for name in ('oidc_request_url', 'oidc_request_credential'))
    for path in (packet.job, *packet.job.rglob('*')):
        assert path.stat().st_uid == os.getuid() and path.stat().st_gid == os.getgid()
        assert path.stat().st_mode & 0o777 == (0o700 if path.is_dir() else 0o600)
    before = {str(path): path.read_bytes() for path in packet.job.rglob('*') if path.is_file()}
    rejected(packet.invoke())  # New process cannot reprovision emission or capture.
    assert before == {str(path): path.read_bytes() for path in packet.job.rglob('*') if path.is_file()}


def test_prepared_bearer_and_deployment_feed_unchanged_real_stager(packet):
    result = packet.invoke(action='consume')
    assert result['status'] == 'accepted' and result['events'].count('stage') == 1
    document = packet.profile_value[packet.payload['role']]
    assert not Path(document['attempt_directory']).exists()
    assert Path(document['transport_inputs']['oidc_request_credential']).read_bytes() == b'SYNTHETIC_DISTINCT_REQUEST_TOKEN'


@pytest.mark.parametrize('attack', ['existing', 'symlink', 'parent-mode', 'profile-hash', 'helper-hash', 'source-bytes',
                                   'profile-policy', 'context', 'ca-bytes', 'ca-mode', 'deployment-alias', 'outside-input', 'action-root'])
def test_public_or_path_rejection_precedes_bearer_access(tmp_path, attack):
    packet = Packet(tmp_path, 'emission' if attack == 'action-root' else 'capture')
    if attack == 'existing': packet.job.mkdir(mode=0o700)
    elif attack == 'symlink': packet.job.symlink_to(packet.root, target_is_directory=True)
    elif attack == 'parent-mode': packet.job.parent.chmod(0o755)
    elif attack == 'profile-hash': packet.payload['profile_sha256'] = '0'*64
    elif attack == 'helper-hash': packet.payload['helper_sha256'] = '0'*64
    elif attack == 'source-bytes':
        path = packet.source / 'scripts/android_workflow_identity.py'; path.write_bytes(path.read_bytes() + b' ')
    elif attack == 'profile-policy': packet.profile_value['capture']['job_policy']['repository'] = 'other/repo'; packet.seal()
    elif attack == 'context': packet.context_value['workflow_sha'] = '0'*40; packet.seal()
    elif attack in ('ca-bytes', 'ca-mode'):
        path = Path(packet.profile_value['capture']['pins']['controller_ca']['path'])
        if attack == 'ca-bytes': path.write_bytes(b'changed')
        else: path.chmod(0o644)
    elif attack == 'deployment-alias': packet.payload['deployment'] = packet.payload['bearer_path']
    elif attack == 'action-root': packet.profile_value['emission']['attestation_output_root'] = str(packet.job.parent); packet.seal()
    else: packet.profile_value['capture']['transport_inputs']['oidc_request_url'] = str(packet.root/'outside'); packet.seal()
    rejected(packet.invoke())
    if attack not in ('existing', 'symlink'): assert not packet.job.exists()


@pytest.mark.parametrize('action', ['directory-fsync', 'unexpected-file', 'deployment-fsync', 'bearer-fsync', 'wrong-bearer',
                                  'environment-profile-drift', 'environment-code-drift', 'environment-parent-replace'])
def test_partial_failures_preserve_effects_and_cannot_be_replayed(tmp_path, action):
    packet = Packet(tmp_path, 'emission')
    reads = 0 if action in ('directory-fsync', 'unexpected-file', 'deployment-fsync') else 1
    rejected(packet.invoke(action=action, retry=True), reads=reads)
    assert packet.job.exists()
    if action == 'environment-parent-replace':
        assert (packet.job.parent/'retained-parent/documents/deployment.json').read_bytes() == packet.expected
    elif action not in ('directory-fsync', 'unexpected-file'): assert packet.deployment.read_bytes() == packet.expected
    if action == 'unexpected-file': assert (packet.job/'unknown').read_bytes() == b'preserve unknown'
    if action == 'bearer-fsync': assert Path(packet.payload['bearer_path']).read_bytes() == TOKEN.encode()
    elif action != 'environment-parent-replace': assert not Path(packet.payload['bearer_path']).exists()
    rejected(packet.invoke())


@pytest.mark.parametrize('role', ['protected', 'owner', 'emission-submit'])
def test_no_other_role_or_submit_reprovisioning(tmp_path, role):
    packet = Packet(tmp_path, 'capture'); rejected(packet.invoke(role=role))
    assert not packet.job.exists()


@pytest.mark.parametrize('extra', [
    ['--bearer', TOKEN], ['--bundle', '/synthetic/bundle'], ['--deployment-sha256', 'a'*64],
    ['--role', 'emission-submit'], ['--command', 'arbitrary'],
])
def test_closed_preparation_cli_rejects_secret_command_or_submit_inputs(tmp_path, extra):
    packet = Packet(tmp_path, 'capture')
    args = ['prepare-inputs', '--role', 'capture', '--job-root', str(packet.job)]
    for name in ('hosted_root', 'helper_sha256', 'profile', 'profile_sha256', 'context', 'context_sha256', 'deployment'):
        args += ['--'+name.replace('_', '-'), packet.payload[name]]
    result = subprocess.run([sys.executable, '-I', '-B', str(CALLER), *args, *extra],
        env={'PATH': os.defpath, 'LANG': 'C'}, capture_output=True, text=True, timeout=5)
    assert result.returncode == 1 and result.stdout == '' and result.stderr == ERROR+'\n'
    assert TOKEN not in result.stderr and not packet.job.exists()
