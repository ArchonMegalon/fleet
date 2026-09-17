"""Disposable cold caller checks; no deployment, custody or operational calls.

The actual closure cases use the existing caller-supplied dependency runtime.
Initial caller/interpreter/dependency trust is external, not established here.
Real held admission and inputs surround safe render/stage/run doubles installed
only after captured imports return. Synthetic cases remain site-free.
"""
import ast
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
HELPER = ROOT / "scripts/android_hosted_source_admission.py"
ERROR = "hosted phase stopped; preserve inputs and reconcile"
COMPLETE = "hosted phase completed"
TARGETS = ("android_deployment_materializer", "android_hosted_input_stager", "android_hosted_controller_roles")
HELPER_NAME = "_chummer_hosted_source_admission"
PRIVATE = "SYNTHETIC_PRIVATE_FAILURE_DO_NOT_PRINT"

CHILD = r'''
import contextlib, importlib.util, io, json, os, pathlib, sys, types
p = json.loads(sys.argv[2]); root = pathlib.Path(p['root']); action = p.get('action', '')
events, imports, guard_hits = [], [], []
helper_execs = 0
helper_path = root / 'scripts' / 'android_hosted_source_admission.py'
live, fd_paths = set(), {}
real_open, real_close, real_pread = os.open, os.close, os.pread
changed_once = False
def mutate(path):
    path.write_bytes(path.read_bytes() + b' ')
def opening(path, *args, **kwargs):
    fd = real_open(path, *args, **kwargs); live.add(fd); fd_paths[fd] = str(path); return fd
def closing(fd):
    real_close(fd); live.discard(fd); fd_paths.pop(fd, None)
def reading(fd, *args):
    global changed_once
    raw = real_pread(fd, *args)
    if not changed_once and fd_paths.get(fd) == str(helper_path) and action.startswith('helper-read-'):
        changed_once = True
        if action == 'helper-read-mutate':
            mutate(helper_path)
        elif action == 'helper-read-replace':
            helper_path.rename(helper_path.with_suffix('.retained')); helper_path.write_bytes(raw)
            helper_path.chmod(0o644)
        elif action == 'helper-read-parent':
            old = root / 'scripts'; saved = root / 'retained-scripts'; old.rename(saved); old.mkdir(mode=0o700)
            for source in saved.iterdir():
                (old / source.name).write_bytes(source.read_bytes()); (old / source.name).chmod(0o644)
    return raw
os.open, os.close, os.pread = opening, closing, reading
def audited(event, arguments):
    if (event.startswith(('socket.', 'subprocess.', 'os.exec', 'os.spawn', 'os.posix_spawn', 'os.fork'))
            or event in {'os.system', 'sqlite3.connect'}):
        guard_hits.append(event)
        raise AssertionError('external operation forbidden in caller test')
sys.addaudithook(audited)
for event in ('socket.__new__', 'subprocess.Popen', 'sqlite3.connect'):
    try:
        sys.audit(event)
    except AssertionError:
        pass
    else:
        raise AssertionError('audit guard missing')
guard_hits.clear()
class NoEnvironment(dict):
    def forbidden(self, *args, **kwargs):
        events.append(['environment-read']); raise AssertionError('submit environment access')
    __getitem__ = get = __iter__ = __contains__ = keys = items = values = forbidden
class NoOIDCEnvironment(dict):
    def __getitem__(self, key):
        if key.startswith('ACTIONS_ID_TOKEN_REQUEST_'):
            events.append(['environment-read']); raise AssertionError('submit OIDC environment access')
        return super().__getitem__(key)
    def get(self, key, default=None):
        try: return self[key]
        except KeyError: return default
if p['phase'] == 'emission-submit':
    os.environ = NoOIDCEnvironment(os.environ)
def install_doubles(modules):
    imports.extend((key, module.__name__, module.__file__, module.__spec__.origin)
                   for key, module in modules.items())
    def render(profile, context, role):
        events.append(['render', role])
        assert isinstance(profile, dict) and isinstance(context, dict)
        if action == 'render-failure':
            raise RuntimeError(p['private'])
        return (b'wrong synthetic deployment' if action == 'render-mismatch' else p['deployment_raw'].encode())
    def stage(**kwargs):
        events.append(['stage', kwargs['role']])
        assert p['phase'] != 'emission-submit'
        for key in ('profile', 'context', 'deployment'):
            assert kwargs[key] == pathlib.Path(p[key]) and kwargs[key + '_sha256'] == p[key + '_sha256']
        (root / 'stage-effect').write_bytes(b'synthetic staged effect')
        if action.startswith('after-stage-'):
            mutate(pathlib.Path(p[action.removeprefix('after-stage-')]))
        if action == 'stage-failure':
            raise RuntimeError(p['private'])
        return 'incorrect synthetic completion' if action == 'stage-wrong-completion' else modules['stager'].COMPLETE
    def run(phase, deployment, deployment_sha256, *, bundle_path=None):
        events.append(['run', phase, None if bundle_path is None else str(bundle_path)])
        assert deployment == pathlib.Path(p['deployment']) and deployment_sha256 == p['deployment_sha256']
        (root / 'run-effect').write_bytes(b'synthetic run effect')
        if action.startswith('after-run-'):
            mutate(pathlib.Path(p[action.removeprefix('after-run-')]))
        if action == 'run-failure':
            raise RuntimeError(p['private'])
        return 'incorrect synthetic completion' if action == 'run-wrong-completion' else modules['hosted'].COMPLETE[phase]
    if not p.get('real_render'):
        modules['materializer'].render = render
    modules['stager'].stage = stage
    modules['hosted'].run = run
    if p['phase'] == 'emission-submit':
        os.environ = NoEnvironment()
    if action == 'foreign-helper-module':
        foreign = types.ModuleType('_chummer_hosted_source_admission'); foreign.synthetic_foreign = True
        sys.modules[foreign.__name__] = foreign
    elif action.startswith('after-import-'):
        mutate(pathlib.Path(p[action.removeprefix('after-import-')]))
def traced(frame, event, argument):
    global helper_execs
    name = frame.f_globals.get('__name__', '')
    if event == 'call' and name == '_chummer_hosted_source_admission' and frame.f_code.co_name == '<module>':
        helper_execs += 1
    if (event == 'call' and (name.startswith('scripts.') or name.startswith('android_'))
            and frame.f_code.co_filename != sys.argv[1]
            and frame.f_code.co_name in {'main', 'materialize', 'render', 'stage', 'run', 'capture', 'submit'}):
        if p.get('real_render') and name == 'scripts.android_deployment_materializer' and frame.f_code.co_name == 'render':
            events.append(['render', frame.f_locals['role']])
        else:
            raise AssertionError('real operational entrypoint forbidden')
    if event == 'return' and name == '_chummer_hosted_source_admission':
        if frame.f_code.co_name == 'import_targets' and isinstance(argument, dict):
            install_doubles(argument)
        if frame.f_code.co_name == '<module>' and action == 'after-helper-exec':
            mutate(helper_path)
    return traced
probe = {'__name__': 'scripts.synthetic_guard_probe'}
exec('def run(): return None', probe)
sys.settrace(traced)
try:
    probe['run']()
except AssertionError:
    pass
else:
    raise AssertionError('operational trace guard missing')
sys.settrace(traced)
if action == 'ambient':
    sys.modules[p['ambient']] = types.ModuleType(p['ambient'])
initial_modules = {name: module for name, module in sys.modules.items()
                   if name == 'scripts' or name.startswith(('scripts.', 'android_', '_chummer_hosted_source_admission'))}
initial_path, initial_meta = list(sys.path), list(sys.meta_path)
result = {'status': 'rejected'}
captured_out, captured_err = io.StringIO(), io.StringIO()
try:
    with contextlib.redirect_stdout(captured_out), contextlib.redirect_stderr(captured_err):
        spec = importlib.util.spec_from_file_location(p.get('caller_name', '_chummer_hosted_phase_caller'), sys.argv[1])
        caller = importlib.util.module_from_spec(spec); sys.modules[spec.name] = caller; spec.loader.exec_module(caller)
        if spec.name == 'scripts' or spec.name.startswith(('scripts.', 'android_', '_chummer_hosted_source_admission')):
            initial_modules[spec.name] = caller  # The caller must not delete its own rejected import alias.
        kwargs = {key: pathlib.Path(p[key]) for key in ('hosted_root', 'profile', 'context', 'deployment')}
        kwargs.update({key: p[key] for key in ('helper_sha256', 'profile_sha256', 'context_sha256', 'deployment_sha256')})
        kwargs['bundle_path'] = pathlib.Path(p['bundle']) if p.get('bundle') is not None else None
        if p.get('cli'):
            argv = [p['phase']]
            for key in ('hosted_root', 'helper_sha256', 'profile', 'profile_sha256', 'context', 'context_sha256',
                        'deployment', 'deployment_sha256'):
                argv.extend(['--' + key.replace('_', '-'), p[key]])
            if p.get('bundle') is not None:
                argv.extend(['--bundle', p['bundle']])
            argv.extend(p.get('extra_args', []))
            result['exit_code'] = caller.main(argv)
        else:
            result['return'] = caller.run(p['phase'], **kwargs)
        result['status'] = 'accepted'
except Exception as error:
    result['error'], result['error_type'] = str(error), type(error).__name__
if p.get('retry'):
    before_retry = list(events)
    try:
        caller.run(p['phase'], **kwargs)
    except Exception as error:
        result['retry_error'], result['retry_type'] = str(error), type(error).__name__
    result['retry_unchanged'] = before_retry == events
result.update(events=events, imports=imports, helper_execs=helper_execs, open_descriptors=len(live),
              stdout=captured_out.getvalue(), stderr=captured_err.getvalue(), guard_hits=guard_hits,
              trace_armed=sys.gettrace() is traced, sys_path_restored=sys.path == initial_path,
              meta_path_restored=sys.meta_path == initial_meta,
              foreign_helper_retained=getattr(sys.modules.get('_chummer_hosted_source_admission'), 'synthetic_foreign', False),
              modules_restored={name: module for name, module in sys.modules.items()
                  if name == 'scripts' or name.startswith(('scripts.', 'android_', '_chummer_hosted_source_admission'))}
                  == initial_modules)
sys.settrace(None)
print(json.dumps(result, sort_keys=True))
'''


SYNTHETIC_INPUT = '''
import hashlib, os
class _Input:
    def __init__(self, path, limit, *, expected=None, public=False):
        self.path = path; self.fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW); self.limit = limit
        self.stamp = self._stamp(os.fstat(self.fd)); self.expected = expected
        try:
            self.raw = self.read()
        except BaseException:
            self.close(); raise
    @staticmethod
    def _stamp(info):
        return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    def recheck(self):
        assert self._stamp(os.fstat(self.fd)) == self.stamp == self._stamp(self.path.stat())
    def read(self):
        self.recheck(); raw = os.pread(self.fd, self.limit + 1, 0); self.recheck()
        assert self.expected is None or hashlib.sha256(raw).hexdigest() == self.expected
        return raw
    def close(self):
        if self.fd >= 0: os.close(self.fd); self.fd = -1
MAX_CONFIG = 131072
COMPLETE = {'capture': 'synthetic capture complete', 'emission-prepare': 'synthetic prepare complete',
            'emission-submit': 'synthetic submit complete'}
def run(*args, **kwargs): raise AssertionError('real synthetic role entrypoint')
'''


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path, value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    path.write_bytes(raw); path.chmod(0o600)
    return digest(raw)


def current_sources():
    queue, selected = ["scripts." + name for name in TARGETS], {}
    while queue:
        module = queue.pop(); relative = module.replace(".", "/") + ".py"
        if relative in selected:
            continue
        raw = (ROOT / relative).read_bytes(); selected[relative] = raw
        for node in ast.walk(ast.parse(raw)):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                assert not node.level
                names = (["scripts." + alias.name for alias in node.names]
                         if node.module == "scripts" else [node.module or ""])
            else:
                continue
            queue.extend("scripts." + name if name == "android_preview12_approval_ledger" else name
                         for name in names if name.startswith("scripts.") or name == "android_preview12_approval_ledger")
    return selected


class Packet:
    def __init__(self, root, *, actual=False):
        self.root, self.actual = root, actual
        root.mkdir(mode=0o700); (root / "scripts").mkdir(mode=0o700)
        self.helper = root / "scripts/android_hosted_source_admission.py"
        self.helper.write_bytes(HELPER.read_bytes()); self.helper.chmod(0o644)
        sources = current_sources() if actual else {
            "scripts/android_deployment_materializer.py": b"import json\nMAX_PROFILE=2097152\nMAX_CONTEXT=16384\n_json=json.loads\ndef render(*args): raise AssertionError('real render')\ndef materialize(*args): raise AssertionError('materialize forbidden')\n",
            "scripts/android_hosted_input_stager.py": b"COMPLETE='synthetic staged'\ndef stage(**kwargs): raise AssertionError('real stage')\n",
            "scripts/android_hosted_controller_roles.py": SYNTHETIC_INPUT.encode(),
        }
        pins = {}
        for name, raw in sources.items():
            path = root / name; path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            path.write_bytes(raw); path.chmod(0o644); pins[name] = digest(raw)
        self.profile = root / "profile.json"; self.context = root / "context.json"; self.deployment = root / "deployment.json"
        self.profile_value = {"owner": {"code_pins": dict(pins)}, "capture": {}, "emission": {},
                              "protected": {"launcher": {"code_pins": dict(pins)}}}
        self.context_value = {"fleet_sha": "a" * 40, "workflow_sha": "a" * 40, "ref": "refs/heads/main",
                              "run_id": "77", "run_attempt": "3", "transaction_id": "b" * 64}
        self.payload = {"root": str(root), "hosted_root": str(root), "profile": str(self.profile),
                        "context": str(self.context), "deployment": str(self.deployment), "helper": str(self.helper),
                        "helper_sha256": digest(self.helper.read_bytes()), "private": PRIVATE,
                        "profile_sha256": write_json(self.profile, self.profile_value),
                        "context_sha256": write_json(self.context, self.context_value),
                        "deployment_sha256": write_json(self.deployment, {"synthetic": "deployment"})}
        self.payload["deployment_raw"] = self.deployment.read_text()
        (root / "retained-actual-bundle.json").write_bytes(b'{"synthetic":"retained bundle"}\n')

    def invoke(self, phase="capture", **options):
        payload = {**self.payload, "phase": phase, **options}
        if phase == "emission-submit" and "bundle" not in options:
            payload["bundle"] = str(self.root / "retained-actual-bundle.json")
        flags = ["-I", "-B"] + ([] if self.actual else ["-S"])
        completed = subprocess.run([sys.executable, *flags, "-c", CHILD, str(CALLER), json.dumps(payload)],
            cwd=self.root, env={"PATH": os.defpath, "LANG": "C", "LC_ALL": "C"},
            capture_output=True, text=True, timeout=20)
        assert completed.returncode == 0, completed.stderr
        assert completed.stderr == ""
        return json.loads(completed.stdout)


@pytest.fixture
def packet(tmp_path):
    return Packet(tmp_path / "private-fixture")


def clean(result, *, foreign=False):
    assert result["open_descriptors"] == 0, result
    assert result["modules_restored"] is not foreign, result
    assert result["foreign_helper_retained"] is foreign, result
    assert result["meta_path_restored"] and result["sys_path_restored"], result
    assert result["guard_hits"] == [] and result["trace_armed"], result


def rejected(result, *, no_imports=False, before_helper=False, foreign=False):
    assert result["status"] == "rejected", result
    assert result["error_type"] == "PhaseError" and result["error"] == ERROR, result
    assert result["stdout"] == result["stderr"] == ""
    assert PRIVATE not in str(result)
    clean(result, foreign=foreign)
    if no_imports:
        assert result["imports"] == [] and result["events"] == []
    if before_helper:
        assert result["helper_execs"] == 0


@pytest.mark.parametrize("phase", ["capture", "emission-prepare", "emission-submit"])
@pytest.mark.parametrize("actual", [False, True])
def test_fixed_phases_use_retained_admission_then_only_expected_calls(tmp_path, phase, actual):
    packet = Packet(tmp_path / "private-fixture", actual=actual)
    result = packet.invoke(phase, retry=True)
    assert result["status"] == "accepted" and result["return"] == COMPLETE, result
    role = "capture" if phase == "capture" else "emission"
    expected = [["render", role]]
    if phase != "emission-submit":
        expected.append(["stage", role])
    expected.append(["run", phase, str(packet.root / "retained-actual-bundle.json") if phase == "emission-submit" else None])
    assert result["events"] == expected
    assert {name for _, name, _, _ in result["imports"]} == {"scripts." + name for name in TARGETS}
    for _, name, path, origin in result["imports"]:
        assert path == origin == str(packet.root / (name.replace(".", "/") + ".py"))
    assert result["helper_execs"] == 1 and result["retry_unchanged"]
    assert result["retry_type"] == "PhaseError" and result["retry_error"] == ERROR
    assert result["stdout"] == result["stderr"] == ""
    assert (packet.root / "retained-actual-bundle.json").read_bytes() == b'{"synthetic":"retained bundle"}\n'
    clean(result)


def test_existing_profile_fixture_real_render_matches_held_deployment_in_cold_child(tmp_path):
    """Real pure rendering/input custody; operational stage/run remain doubles."""
    packet = Packet(tmp_path / "private-fixture", actual=True)
    fixture_path = ROOT / "tests/test_android_deployment_materializer.py"
    spec = importlib.util.spec_from_file_location("_phase_materializer_fixture", fixture_path)
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    profile, context = fixture._profile(packet.root), fixture._context()
    pins = packet.profile_value["owner"]["code_pins"]
    profile["owner"]["code_pins"] = dict(pins)
    profile["protected"]["launcher"]["code_pins"] = dict(pins)
    raw = fixture.materializer.render(profile, context, "emission")
    packet.payload["profile_sha256"] = write_json(packet.profile, profile)
    packet.payload["context_sha256"] = write_json(packet.context, context)
    packet.deployment.write_bytes(raw)
    packet.payload.update(deployment_raw=raw.decode(), deployment_sha256=digest(raw))
    result = packet.invoke("emission-prepare", real_render=True)
    assert result["status"] == "accepted" and result["return"] == COMPLETE, result
    assert result["events"] == [["render", "emission"], ["stage", "emission"], ["run", "emission-prepare", None]]
    assert packet.deployment.read_bytes() == raw and result["helper_execs"] == 1
    assert result["stdout"] == result["stderr"] == ""
    clean(result)


@pytest.mark.parametrize("kind", ["digest", "bytes", "symlink", "hardlink", "writable", "helper-read-mutate",
                                  "helper-read-replace", "helper-read-parent"])
def test_helper_bytes_and_binding_are_checked_before_execution(packet, kind):
    options = {}
    if kind == "digest": options["helper_sha256"] = "0" * 64
    elif kind == "bytes": packet.helper.write_bytes(packet.helper.read_bytes() + b"\nraise RuntimeError('unadmitted helper')\n")
    elif kind == "symlink":
        retained = packet.root / "retained-helper"; packet.helper.rename(retained); packet.helper.symlink_to(retained)
    elif kind == "hardlink": os.link(packet.helper, packet.root / "retained-helper")
    elif kind == "writable": packet.helper.chmod(0o666)
    else: options["action"] = kind
    rejected(packet.invoke(**options), no_imports=True, before_helper=True)


def test_package_cache_rejects_before_targets_import(packet):
    (packet.root / "scripts/__pycache__").mkdir(mode=0o700)
    rejected(packet.invoke(), no_imports=True)


def test_unselected_helper_bytecode_never_supplies_executable_authority(packet):
    (packet.root / "scripts/android_hosted_source_admission.pyc").write_bytes(b"synthetic invalid cache")
    result = packet.invoke()
    assert result["status"] == "accepted" and result["return"] == COMPLETE, result
    assert result["helper_execs"] == 1 and len(result["imports"]) == 3
    clean(result)


def test_foreign_helper_module_replacement_is_rejected_but_not_erased(packet):
    result = packet.invoke(action="foreign-helper-module")
    rejected(result, foreign=True)
    assert result["events"] == []


@pytest.mark.parametrize("ambient", [HELPER_NAME, "scripts", "scripts.android_hosted_controller_roles",
                                    "android_preview12_approval_ledger"])
def test_ambient_imports_cannot_supply_source_authority(packet, ambient):
    rejected(packet.invoke(action="ambient", ambient=ambient), no_imports=True,
             before_helper=ambient == HELPER_NAME)


@pytest.mark.parametrize("name", ["arbitrary_caller", "scripts.android_hosted_phase_caller"])
def test_caller_must_have_fixed_private_identity(packet, name):
    rejected(packet.invoke(caller_name=name), no_imports=True, before_helper=True)


@pytest.mark.parametrize("phase,bundle", [("other", None), ("capture", "/synthetic-bundle"),
    ("emission-prepare", "/synthetic-bundle"), ("emission-submit", None)])
def test_phase_and_bundle_shape_fail_before_loading_helper(packet, phase, bundle):
    rejected(packet.invoke(phase, bundle=bundle), no_imports=True, before_helper=True)


@pytest.mark.parametrize("document", ["profile", "context", "deployment"])
def test_stale_document_digest_rejects_before_operations(packet, document):
    path = getattr(packet, document); path.write_bytes(path.read_bytes() + b" ")
    result = packet.invoke(); rejected(result)
    assert result["events"] == []


@pytest.mark.parametrize("action", ["render-mismatch", "render-failure", "after-helper-exec",
    "after-import-profile", "after-import-context", "after-import-deployment", "after-import-helper"])
def test_preoperation_drift_and_render_failure_prevent_stage_and_run(packet, action):
    result = packet.invoke(action=action); rejected(result)
    assert all(event[0] == "render" for event in result["events"])
    assert not (packet.root / "stage-effect").exists() and not (packet.root / "run-effect").exists()


@pytest.mark.parametrize("action", ["stage-failure", "stage-wrong-completion", "after-stage-profile", "after-stage-context",
                                   "after-stage-deployment", "after-stage-helper"])
def test_staging_failure_or_drift_preserves_partial_effect_without_run_or_retry(packet, action):
    result = packet.invoke(action=action, retry=True); rejected(result)
    assert result["events"] == [["render", "capture"], ["stage", "capture"]]
    assert (packet.root / "stage-effect").read_bytes() == b"synthetic staged effect"
    assert not (packet.root / "run-effect").exists()
    assert result["retry_error"] == ERROR and result["retry_unchanged"]


@pytest.mark.parametrize("action", ["run-failure", "run-wrong-completion", "after-run-profile", "after-run-context",
                                   "after-run-deployment", "after-run-helper"])
def test_run_failure_or_final_drift_preserves_both_effects_without_retry(packet, action):
    result = packet.invoke(action=action, retry=True); rejected(result)
    assert [event[0] for event in result["events"]] == ["render", "stage", "run"]
    assert (packet.root / "stage-effect").read_bytes() == b"synthetic staged effect"
    assert (packet.root / "run-effect").read_bytes() == b"synthetic run effect"
    assert result["retry_error"] == ERROR and result["retry_unchanged"]


@pytest.mark.parametrize("extra", [[], ["--unknown", PRIVATE], ["--help"], ["--profile-sha256", "invalid"]])
def test_cli_has_fixed_flags_and_constant_diagnostics(packet, extra):
    result = packet.invoke(cli=True, extra_args=extra)
    assert result["status"] == "accepted", result
    assert result["exit_code"] == (0 if not extra else 1)
    assert result["stdout"] == (COMPLETE + "\n" if not extra else "")
    assert result["stderr"] == ("" if not extra else ERROR + "\n")
    assert PRIVATE not in result["stdout"] + result["stderr"]
    clean(result)
