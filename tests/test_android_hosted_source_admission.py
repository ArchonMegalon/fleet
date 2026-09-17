"""Cold, disposable import-admission proofs; no profiles, credentials or roles.

Synthetic cases use harmless consumer/dependency sources with import sentinels.
One separate import-only case copies the actual source closure and uses the
caller's existing dependency environment with operational guards. Interpreter
and installed-dependency trust remain external; this is not deployment authority.
All children are isolated; synthetic cases are also site-free, so cached modules
in the surrounding source suite cannot contaminate these checks.
"""
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts/android_hosted_source_admission.py"
ERROR = "hosted source admission stopped; preserve inputs and reconcile"
TARGETS = {"materializer": "android_deployment_materializer", "stager": "android_hosted_input_stager",
           "hosted": "android_hosted_controller_roles"}
DEPENDENCY = "android_workflow_identity"
BARE_FALLBACK = "android_preview12_approval_ledger"

CHILD = r'''
import builtins, importlib, importlib.util, json, os, pathlib, sys, types
p = json.loads(sys.argv[2])
root = pathlib.Path(p['root'])
action = p.get('action', '')
if action.startswith('normal-helper'):
    sys.path.insert(0, str(root))
    admission = importlib.import_module('scripts.android_hosted_source_admission')
else:
    spec = importlib.util.spec_from_file_location('admission_fixture_driver', sys.argv[1])
    admission = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = admission
    spec.loader.exec_module(admission)
if action == 'ambient':
    name = p['ambient']
    sys.modules[name] = None if p.get('none') else types.ModuleType(name)
if action == 'ambient-parent-attribute':
    parent = types.ModuleType('scripts')
    parent.__path__ = [str(root / 'scripts')]
    parent.android_workflow_identity = types.ModuleType('scripts.android_workflow_identity')
    sys.modules['scripts'] = parent
if action == 'normal-helper-poisoned-parent':
    sys.modules['scripts'].android_workflow_identity = types.ModuleType('scripts.android_workflow_identity')
initial_modules = {name for name in sys.modules if name == 'scripts' or name.startswith('scripts.')}
initial_bare = {name: module for name, module in sys.modules.items() if name.startswith('android_')}
initial_meta = list(sys.meta_path)
initial_path = list(sys.path)
initial_trace = sys.gettrace()
guard_proof = {}
if action == 'actual-import':
    forbidden_calls = {'main', 'materialize', 'render', 'stage', 'run', 'capture', 'submit',
                       'emit', 'prepare', 'provision', 'activate', '__init__', '__new__', '__enter__'}
    def fleet_trace(frame, event, argument):
        module = frame.f_globals.get('__name__', '')
        if (event == 'call' and frame.f_code.co_name in forbidden_calls
                and (module.startswith('scripts.') or module.startswith('android_'))):
            raise AssertionError('operational Fleet call disabled in import-only child')
        return fleet_trace
    def operation_audit(event, arguments):
        if (event.startswith(('socket.', 'subprocess.', 'os.exec', 'os.spawn', 'os.posix_spawn', 'os.fork'))
                or event in {'os.system', 'sqlite3.connect'}):
            raise AssertionError('external operation disabled in import-only child')
    sys.addaudithook(operation_audit)
    probes = ['socket.__new__', 'socket.connect', 'socket.bind', 'subprocess.Popen', 'os.exec', 'os.fork']
    for event in probes:
        try:
            sys.audit(event)
        except AssertionError:
            continue
        raise AssertionError('audit guard was not armed')
    synthetic = {'__name__': 'scripts.guard_probe'}
    exec(compile('def run(): return None', str(root / 'scripts' / 'guard_probe.py'), 'exec'), synthetic)
    sys.settrace(fleet_trace)
    try:
        synthetic['run']()
    except AssertionError:
        pass
    else:
        raise AssertionError('Fleet trace guard was not armed')
    # A trace callback exception disarms tracing; restore it after the probe.
    sys.settrace(fleet_trace)
    guard_proof = {'audit_events': probes, 'fleet_trace_armed': sys.gettrace() is fleet_trace}
real_open, real_close = os.open, os.close
live = set()
def opening(*args, **kwargs):
    fd = real_open(*args, **kwargs); live.add(fd); return fd
def closing(fd):
    real_close(fd); live.discard(fd)
os.open, os.close = opening, closing
result = {'status': 'rejected', 'phase': 'admit'}
try:
    with admission.admit(profile=pathlib.Path(p['profile']), profile_sha256=p['profile_sha'],
                         context=pathlib.Path(p['context']), context_sha256=p['context_sha'],
                         hosted_root=root) as lease:
        result['phase'] = 'before-import'
        changed = pathlib.Path(p.get('changed', p['profile']))
        if action == 'mutate-before-import':
            changed.write_bytes(changed.read_bytes() + b' ')
        if action == 'replace-before-import':
            raw = changed.read_bytes(); changed.rename(changed.with_name(changed.name + '.retained'))
            changed.write_bytes(raw); changed.chmod(0o600)
        if action == 'replace-scripts-parent':
            old = root / 'scripts'; saved = root / 'retained-scripts'; old.rename(saved)
            old.mkdir(mode=0o700)
            for source in saved.iterdir():
                (old / source.name).write_bytes(source.read_bytes())
                (old / source.name).chmod(0o644)
        if action in {'captured-only', 'actual-import'}:
            forbidden = set(p['basenames'])
            def guarded(path, *args, **kwargs):
                if not isinstance(path, int) and pathlib.Path(path).name in forbidden:
                    raise AssertionError('source pathname reopened after admission')
                return opening(path, *args, **kwargs)
            os.open = guarded
            original_builtin = builtins.open
            def guarded_builtin(path, *args, **kwargs):
                if not isinstance(path, int) and pathlib.Path(path).name in forbidden:
                    raise AssertionError('source pathname reopened after admission')
                return original_builtin(path, *args, **kwargs)
            builtins.open = guarded_builtin
        if action != 'admit-only':
            if action == 'retry-after-failed-import':
                try:
                    lease.import_targets()
                except admission.AdmissionError:
                    pass
            modules = lease.import_targets()
            result['phase'] = 'after-import'
            result['targets'] = {key: module.__name__ for key, module in modules.items()}
            result['files'] = {key: module.__file__ for key, module in modules.items()}
            result['origins'] = {key: module.__spec__.origin for key, module in modules.items()}
            result['captured_loaders'] = all(module.__loader__ is lease and module.__spec__.loader is lease
                                            for module in modules.values())
            if action == 'second-import':
                lease.import_targets()
            if action == 'mutate-after-import':
                changed.write_bytes(changed.read_bytes() + b' ')
            if action == 'mutate-and-restore':
                raw = changed.read_bytes(); before = changed.stat()
                changed.write_bytes(raw + b' '); changed.write_bytes(raw)
                os.utime(changed, ns=(before.st_atime_ns, before.st_mtime_ns))
            if action == 'poison-binding':
                sys.modules['scripts'].android_workflow_identity = types.ModuleType('foreign_fixture')
        lease.recheck()
        result['phase'] = 'exit'
    result['status'] = 'accepted'
except Exception as error:
    result['error'] = str(error)
    result['error_type'] = type(error).__name__
if action == 'actual-import':
    guard_proof['fleet_trace_still_armed'] = sys.gettrace() is fleet_trace
    sys.settrace(initial_trace)
    result['guard_proof'] = guard_proof
    result['trace_restored'] = sys.gettrace() is initial_trace
result['open_descriptors'] = len(live)
result['new_scripts_modules'] = sorted({name for name in sys.modules if name == 'scripts' or name.startswith('scripts.')} - initial_modules)
result['bare_restored'] = {name: module for name, module in sys.modules.items() if name.startswith('android_')} == initial_bare
result['meta_path_restored'] = sys.meta_path == initial_meta
result['sys_path_restored'] = sys.path == initial_path
print(json.dumps(result, sort_keys=True))
'''


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path, value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    path.write_bytes(raw)
    path.chmod(0o600)
    return sha(raw)


class Packet:
    def __init__(self, root):
        self.root = root
        root.mkdir(mode=0o700)
        self.scripts = root / "scripts"
        self.scripts.mkdir(mode=0o700)
        self.sentinel = root / "import-sentinel.txt"
        self.profile = root / "synthetic-profile.json"
        self.context = root / "synthetic-context.json"
        imports = {
            TARGETS["materializer"]: "from scripts import android_workflow_identity as identity\n",
            TARGETS["stager"]: "from scripts import android_deployment_materializer as materializer\n"
                               "from scripts import android_hosted_controller_roles as hosted\n",
            TARGETS["hosted"]: "from scripts import android_workflow_identity as identity\n",
            DEPENDENCY: "",
        }
        pins = {}
        for name, dependencies in imports.items():
            path = self.scripts / (name + ".py")
            path.write_text(self.source(name, dependencies), encoding="utf-8")
            path.chmod(0o644)
            pins["scripts/" + path.name] = sha(path.read_bytes())
        self.profile_value = {"owner": {"code_pins": dict(pins)}, "capture": {}, "emission": {},
                              "protected": {"launcher": {"code_pins": dict(pins)}}}
        self.context_value = {"fleet_sha": "a" * 40, "workflow_sha": "a" * 40, "ref": "refs/heads/main",
                              "run_id": "77", "run_attempt": "3", "transaction_id": "b" * 64}
        self.rewrite_documents()

    def source(self, name, imports=""):
        return ("from pathlib import Path\n"
                f"with Path({str(self.sentinel)!r}).open('a', encoding='utf-8') as marker:\n"
                f"    marker.write({name!r} + '\\n')\n" + imports +
                "def materialize(*args, **kwargs): raise AssertionError('role action invoked')\n"
                "def stage(*args, **kwargs): raise AssertionError('role action invoked')\n"
                "def run(*args, **kwargs): raise AssertionError('role action invoked')\n")

    def rewrite_documents(self):
        self.profile_sha = write_json(self.profile, self.profile_value)
        self.context_sha = write_json(self.context, self.context_value)

    def pin_source(self, name, source):
        path = self.scripts / (name + ".py")
        path.write_text(source, encoding="utf-8")
        path.chmod(0o644)
        key = "scripts/" + path.name
        digest = sha(path.read_bytes())
        self.profile_value["protected"]["launcher"]["code_pins"][key] = digest
        self.profile_value["owner"]["code_pins"][key] = digest
        self.rewrite_documents()
        return path

    def invoke(self, **options):
        payload = {"root": str(self.root), "profile": str(self.profile), "profile_sha": self.profile_sha,
                   "context": str(self.context), "context_sha": self.context_sha,
                   "basenames": [Path(name).name for name in self.profile_value["protected"]["launcher"]["code_pins"]],
                   **options}
        isolation = ["-I", "-B"] + ([] if options.get("action") == "actual-import" else ["-S"])
        completed = subprocess.run([sys.executable, *isolation, "-c", CHILD, str(HELPER), json.dumps(payload)],
                                   cwd=self.root, env={"PATH": os.defpath, "LANG": "C", "LC_ALL": "C"},
                                   capture_output=True, text=True, timeout=15)
        assert completed.returncode == 0, completed.stderr
        assert completed.stderr == ""
        return json.loads(completed.stdout)

    def markers(self):
        return self.sentinel.read_text().splitlines() if self.sentinel.exists() else []


@pytest.fixture
def packet(tmp_path):
    return Packet(tmp_path / "private-fixture")


def rejected(result, packet, *, no_imports=True):
    assert result["status"] == "rejected", result
    assert result["error_type"] == "AdmissionError", result
    assert result["error"] == ERROR
    assert result["open_descriptors"] == 0
    assert result["new_scripts_modules"] == []
    assert result["bare_restored"]
    assert result["meta_path_restored"] and result["sys_path_restored"]
    if no_imports:
        assert packet.markers() == []


def test_known_bare_fallback_uses_selected_captured_source_and_is_removed(packet):
    packet.pin_source(BARE_FALLBACK, packet.source(BARE_FALLBACK))
    packet.pin_source(TARGETS["materializer"], packet.source(TARGETS["materializer"],
        "import android_preview12_approval_ledger as ledger\n"
        "from scripts import android_workflow_identity as identity\n"))
    result = packet.invoke(action="captured-only")
    assert result["status"] == "accepted", result
    assert sorted(packet.markers()) == sorted([*TARGETS.values(), DEPENDENCY, BARE_FALLBACK])
    assert result["bare_restored"] and result["new_scripts_modules"] == []
    assert result["open_descriptors"] == 0


@pytest.mark.parametrize("action", ["", "captured-only", "normal-helper"])
def test_cold_imports_only_captured_pinned_modules_and_restores_state(packet, action):
    if action == "normal-helper":
        packet.pin_source("android_hosted_source_admission", HELPER.read_text())
    result = packet.invoke(action=action)
    assert result["status"] == "accepted", result
    assert result["targets"] == {key: "scripts." + value for key, value in TARGETS.items()}
    assert result["files"] == {key: str(packet.scripts / (value + ".py")) for key, value in TARGETS.items()}
    assert sorted(packet.markers()) == sorted([*TARGETS.values(), DEPENDENCY])
    assert result["open_descriptors"] == 0 and result["new_scripts_modules"] == []
    assert result["meta_path_restored"] and result["sys_path_restored"]


@pytest.mark.parametrize("field", ["profile", "context", "code"])
def test_changed_raw_bytes_reject_before_any_consumer_import(packet, field):
    path = packet.scripts / (DEPENDENCY + ".py") if field == "code" else getattr(packet, field)
    path.write_bytes(path.read_bytes() + b" ")
    rejected(packet.invoke(), packet)


@pytest.mark.parametrize("field", ["profile_sha", "context_sha"])
@pytest.mark.parametrize("digest", ["0" * 64, "A" * 64, "abc", True])
def test_independent_document_digests_must_be_exact_lowercase_hex(packet, field, digest):
    rejected(packet.invoke(**{field: digest}), packet)


@pytest.mark.parametrize("name", [*TARGETS.values(), DEPENDENCY])
def test_missing_selected_pin_cannot_be_filled_from_owner_union(packet, name):
    del packet.profile_value["protected"]["launcher"]["code_pins"]["scripts/" + name + ".py"]
    packet.rewrite_documents()
    rejected(packet.invoke(), packet)


def test_owner_only_unselected_pin_is_not_read_or_imported(packet):
    packet.profile_value["owner"]["code_pins"]["scripts/owner_only_not_present.py"] = "c" * 64
    packet.rewrite_documents()
    result = packet.invoke()
    assert result["status"] == "accepted", result
    assert len(packet.markers()) == 4


def test_overlapping_owner_pin_conflict_rejects_before_import(packet):
    packet.profile_value["owner"]["code_pins"]["scripts/" + DEPENDENCY + ".py"] = "0" * 64
    packet.rewrite_documents()
    rejected(packet.invoke(), packet)


@pytest.mark.parametrize("literal", ["from scripts import omitted_fixture", "import scripts.omitted_fixture",
                                     "from scripts.omitted_fixture import value", "import android_preview12_approval_ledger",
                                     "import android_workflow_identity"])
def test_unlisted_literal_imports_fail_before_even_first_sentinel(packet, literal):
    packet.pin_source(TARGETS["materializer"], packet.source(TARGETS["materializer"], literal + "\n"))
    rejected(packet.invoke(), packet)


@pytest.mark.parametrize("name", ["scripts", "scripts.android_workflow_identity", "scripts.unknown_fixture",
                                  "android_preview12_approval_ledger", "android_workflow_identity",
                                  "android_deployment_materializer"])
@pytest.mark.parametrize("none", [False, True])
def test_ambient_module_cache_never_supplies_source_authority(packet, name, none):
    rejected(packet.invoke(action="ambient", ambient=name, none=none), packet)


@pytest.mark.parametrize("action", ["ambient-parent-attribute", "normal-helper-poisoned-parent"])
def test_parent_namespace_attributes_cannot_supply_unadmitted_dependencies(packet, action):
    if action.startswith("normal-helper"):
        packet.pin_source("android_hosted_source_admission", HELPER.read_text())
    rejected(packet.invoke(action=action), packet)


@pytest.mark.parametrize("shadow", ["__pycache__", "android_workflow_identity.pyc", "android_workflow_identity",
                                    "__init__.py", "__init__.pyc"])
def test_cache_package_and_namespace_shadows_reject_without_import(packet, shadow):
    path = packet.scripts / shadow
    if shadow in {"__pycache__", "android_workflow_identity"}:
        path.mkdir(mode=0o700)
    else:
        path.write_bytes(b"# synthetic unadmitted shadow\n")
    rejected(packet.invoke(), packet)


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "writable"])
@pytest.mark.parametrize("field", ["profile", "context", "code"])
def test_aliases_links_and_bad_modes_cannot_enter_source_lease(packet, field, kind):
    path = packet.scripts / (DEPENDENCY + ".py") if field == "code" else getattr(packet, field)
    retained = packet.root / (field + ".retained")
    if kind == "symlink":
        path.rename(retained)
        path.symlink_to(retained)
    elif kind == "hardlink":
        os.link(path, retained)
    else:
        path.chmod(0o666)
    rejected(packet.invoke(), packet)


@pytest.mark.parametrize("field", ["profile", "context", "code"])
@pytest.mark.parametrize("action", ["mutate-before-import", "replace-before-import"])
def test_held_fd_and_path_drift_reject_before_import(packet, field, action):
    path = packet.scripts / (DEPENDENCY + ".py") if field == "code" else getattr(packet, field)
    rejected(packet.invoke(action=action, changed=str(path)), packet)


def test_replaced_parent_directory_rejects_before_import(packet):
    rejected(packet.invoke(action="replace-scripts-parent"), packet)


@pytest.mark.parametrize("action", ["mutate-after-import", "mutate-and-restore", "poison-binding", "second-import"])
def test_recheck_rejects_postimport_drift_and_never_retries(packet, action):
    result = packet.invoke(action=action, changed=str(packet.scripts / (DEPENDENCY + ".py")))
    rejected(result, packet, no_imports=False)
    assert sorted(packet.markers()) == sorted([*TARGETS.values(), DEPENDENCY])


def test_failed_import_poisoning_prevents_reexecuting_even_first_source(packet):
    packet.pin_source(TARGETS["materializer"], packet.source(TARGETS["materializer"],
        "raise RuntimeError('synthetic import failure')\n"))
    result = packet.invoke(action="retry-after-failed-import")
    rejected(result, packet, no_imports=False)
    assert packet.markers() == [TARGETS["materializer"]]


@pytest.mark.parametrize("field,value", [("fleet_sha", "c" * 40), ("workflow_sha", "z" * 40),
    ("ref", "main"), ("run_id", "0"), ("run_attempt", "-1"), ("transaction_id", "d" * 63)])
def test_context_shape_is_admitted_before_any_target_import(packet, field, value):
    packet.context_value[field] = value
    packet.rewrite_documents()
    rejected(packet.invoke(), packet)


@pytest.mark.parametrize("field", ["profile", "context"])
def test_duplicate_json_keys_are_rejected_even_with_matching_digest(packet, field):
    path = getattr(packet, field)
    value = packet.profile_value if field == "profile" else packet.context_value
    key = next(iter(value))
    raw = json.dumps(value).encode()[:-1] + b", " + json.dumps(key).encode() + b":null}"
    path.write_bytes(raw)
    rejected(packet.invoke(**{field + "_sha": sha(raw)}), packet)


def test_explicit_hosted_root_does_not_follow_profile_fleet_paths(packet):
    packet.profile_value["owner"]["fleet_root"] = "/synthetic-nonexistent-owner-root"
    packet.profile_value["protected"]["launcher"]["fleet_root"] = "/synthetic-nonexistent-protected-root"
    packet.rewrite_documents()
    result = packet.invoke()
    assert result["status"] == "accepted", result


@pytest.mark.parametrize("kind", ["source-size", "source-count", "unsafe-ancestor", "symlinked-root"])
def test_bounded_inventory_and_trusted_ancestry(packet, kind):
    if kind == "source-size":
        packet.pin_source(DEPENDENCY, "#" * (2 * 1024 * 1024 + 1))
    elif kind == "source-count":
        for index in range(61):
            packet.pin_source("extra_fixture_" + str(index), "VALUE = 1\n")
    elif kind == "unsafe-ancestor":
        packet.root.chmod(0o777)
    else:
        actual = packet.root.with_name("retained-root")
        packet.root.rename(actual)
        packet.root.symlink_to(actual, target_is_directory=True)
    rejected(packet.invoke(), packet)


def actual_source_closure():
    """Read only the fixed current-source closure; never import its modules."""
    queue = ["scripts." + name for name in TARGETS.values()]
    selected = {}
    while queue:
        module = queue.pop()
        relative = module.replace(".", "/") + ".py"
        if relative in selected:
            continue
        raw = (ROOT / relative).read_bytes()
        selected[relative] = raw
        for node in ast.walk(ast.parse(raw, filename=relative)):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                assert not node.level, "Current-source fixture requires an explicit import edge"
                names = (["scripts." + alias.name for alias in node.names]
                         if node.module == "scripts" else [node.module or ""])
            else:
                continue
            for name in names:
                if name == BARE_FALLBACK:
                    queue.append("scripts." + name)
                elif name.startswith("scripts."):
                    queue.append(name)
    return selected


def copy_actual_source_closure(packet):
    sources = actual_source_closure()
    assert 4 < len(sources) <= 64
    assert "scripts/" + BARE_FALLBACK + ".py" in sources
    pins = {}
    for relative, raw in sources.items():
        path = packet.root / relative
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.write_bytes(raw)
        path.chmod(0o644)
        pins[relative] = sha(raw)
    packet.profile_value["owner"]["code_pins"] = dict(pins)
    packet.profile_value["protected"]["launcher"]["code_pins"] = dict(pins)
    packet.rewrite_documents()
    return sources


def test_actual_current_source_closure_is_admitted_without_importing_consumers(packet):
    copy_actual_source_closure(packet)
    result = packet.invoke(action="admit-only")
    assert result["status"] == "accepted", result
    assert "targets" not in result and packet.markers() == []
    assert result["open_descriptors"] == 0 and result["new_scripts_modules"] == []
    assert result["meta_path_restored"] and result["sys_path_restored"]


def test_actual_captured_targets_import_only_under_armed_operational_guards(packet):
    """Uses the caller's existing deps, not deployment or initial trust authority."""
    copy_actual_source_closure(packet)
    result = packet.invoke(action="actual-import")
    assert result["status"] == "accepted", result
    assert result["targets"] == {key: "scripts." + value for key, value in TARGETS.items()}
    expected_paths = {key: str(packet.scripts / (value + ".py")) for key, value in TARGETS.items()}
    assert result["files"] == result["origins"] == expected_paths
    assert result["captured_loaders"] and packet.markers() == []
    assert result["guard_proof"] == {
        "audit_events": ["socket.__new__", "socket.connect", "socket.bind", "subprocess.Popen", "os.exec", "os.fork"],
        "fleet_trace_armed": True, "fleet_trace_still_armed": True,
    }
    assert result["trace_restored"] and result["bare_restored"]
    assert result["open_descriptors"] == 0 and result["new_scripts_modules"] == []
    assert result["meta_path_restored"] and result["sys_path_restored"]
