"""Held, fixed-target Fleet admission; not interpreter or deployment authority.

The initial bootstrap, this file, interpreter, stdlib, installed dependencies
and native loaders must already be independently admitted. Profile/context
digests and the hosted root come from that caller, never from a candidate's
self-hash. This module imports only stdlib and never calls a role or client.
"""
from __future__ import annotations

import ast
from contextlib import contextmanager
import hashlib
import importlib
import importlib.abc
import importlib.machinery
import json
import os
from pathlib import Path
import re
import stat
import sys

ERROR = "hosted source admission stopped; preserve inputs and reconcile"
TARGETS = {
    "materializer": "scripts.android_deployment_materializer",
    "stager": "scripts.android_hosted_input_stager",
    "hosted": "scripts.android_hosted_controller_roles",
}
SELF = "scripts.android_hosted_source_admission"
BARE = {"android_preview12_approval_ledger": "scripts.android_preview12_approval_ledger"}
PROFILE_FIELDS = {"owner", "capture", "emission", "protected"}
CONTEXT_FIELDS = {"fleet_sha", "workflow_sha", "ref", "run_id", "run_attempt", "transaction_id"}
SOURCE_LIMIT = 2 * 1024**2


class AdmissionError(RuntimeError):
    """Constant diagnostics only; no upstream bytes, private paths or hashes."""


def _require(value):
    if not value:
        raise AdmissionError(ERROR)


def _path(value):
    _require(isinstance(value, Path) and value.is_absolute() and value != Path("/")
             and ".." not in value.parts and "\\" not in str(value)
             and all(32 < ord(c) < 127 for c in str(value)))
    return value


def _stamp(info):
    return tuple(getattr(info, name) for name in ("st_dev", "st_ino", "st_mode", "st_uid",
        "st_gid", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns"))


def _parents(path):
    # Same ancestry rule as the supervisor, with the hosted user rather than
    # protected root custody. Directory child creation does not change binding.
    _require(path.parent.resolve(strict=True) == path.parent)
    chain = [*reversed(path.parent.parents), path.parent]
    result = []
    for index, part in enumerate(chain):
        info = part.lstat()
        _require(stat.S_ISDIR(info.st_mode) and info.st_uid in {0, os.getuid()}
                 and info.st_gid in {0, os.getgid()})
        if info.st_mode & 0o022:
            _require(part == Path("/tmp") and info.st_uid == 0
                     and stat.S_IMODE(info.st_mode) == 0o1777 and index + 1 < len(chain))
            child = chain[index + 1].lstat()
            _require(child.st_uid == os.getuid() and child.st_gid == os.getgid()
                     and stat.S_IMODE(child.st_mode) == 0o700)
        result.append((info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid))
    return tuple(result)


class _Pin:
    """Supervisor-style held no-follow capture, including byte rechecks."""
    def __init__(self, path, digest, limit):
        self.fd = -1
        self.path, self.limit = _path(path), limit
        _require(type(digest) is str and re.fullmatch(r"[0-9a-f]{64}", digest))
        self.digest, self.parents = digest, _parents(path)
        info = path.lstat()
        _require(path.resolve(strict=True) == path and stat.S_ISREG(info.st_mode)
                 and info.st_uid in {0, os.getuid()} and info.st_gid in {0, os.getgid()}
                 and info.st_nlink == 1 and 0 < info.st_size <= limit and not info.st_mode & 0o022)
        self.stamp = _stamp(info)
        try:
            self.fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
            self.recheck()
            self.raw = os.pread(self.fd, info.st_size + 1, 0)
            _require(len(self.raw) == info.st_size and hashlib.sha256(self.raw).hexdigest() == digest)
            self.recheck()
        except BaseException:
            self.close()
            raise

    def recheck(self):
        _require(self.fd >= 0 and _stamp(os.fstat(self.fd)) == self.stamp == _stamp(self.path.lstat())
                 and self.path.resolve(strict=True) == self.path and _parents(self.path) == self.parents)
        raw = os.pread(self.fd, self.stamp[6] + 1, 0)
        _require(len(raw) == self.stamp[6] and hashlib.sha256(raw).hexdigest() == self.digest
                 and _stamp(os.fstat(self.fd)) == self.stamp == _stamp(self.path.lstat()))

    def close(self):
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1


def _json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result)
            result[key] = value
        return result
    def invalid(_):
        raise AdmissionError(ERROR)
    result = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
    _require(type(result) is dict)
    return result


def _pins(value):
    _require(type(value) is dict and 1 <= len(value) <= 64)
    for name, digest in value.items():
        _require(type(name) is str
                 and re.fullmatch(r"scripts/(?:[A-Za-z_]\w*/)*[A-Za-z_]\w*\.py", name)
                 and type(digest) is str and re.fullmatch(r"[0-9a-f]{64}", digest))
    return value


def _module_name(relative):
    return relative.removesuffix(".py").replace("/", ".").removesuffix(".__init__")


def _fleet_name(name):
    # Bare android_* names are reserved for Fleet here, not an ambient runtime
    # fallback. Only the one known, explicitly pinned alias is executable.
    return name == "scripts" or name.startswith("scripts.") or name.startswith("android_")


def _module_stamp(module):
    spec = getattr(module, "__spec__", None)
    return (getattr(module, "__file__", None), getattr(module, "__loader__", None),
            spec, getattr(spec, "origin", None), getattr(spec, "loader", None),
            tuple(getattr(module, "__path__", ())))


class _Admission(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def __init__(self):
        self.files, self.modules, self.namespaces, self.owned, self.initial = {}, {}, {}, {}, {}
        self.held, self.absent = [], set()
        self.installed = self.attempted = self.closed = self.failed = False

    def _hold(self, path, digest, limit):
        item = _Pin(path, digest, limit)
        self.held.append(item)
        return item

    def prepare(self, profile, profile_sha256, context, context_sha256, hosted_root):
        _require(os.getuid() == os.geteuid() and os.getgid() == os.getegid()
                 and sys.flags.isolated == 1 and sys.dont_write_bytecode and sys.pycache_prefix is None)
        self.root = _path(hosted_root)
        profile_pin = self._hold(profile, profile_sha256, SOURCE_LIMIT)
        context_pin = self._hold(context, context_sha256, 16 * 1024)
        value, invocation = _json(profile_pin.raw), _json(context_pin.raw)
        _require(set(value) == PROFILE_FIELDS and all(type(v) is dict for v in value.values())
                 and set(invocation) == CONTEXT_FIELDS)
        for key, length in (("fleet_sha", 40), ("workflow_sha", 40), ("transaction_id", 64)):
            _require(type(invocation[key]) is str and re.fullmatch("[0-9a-f]{" + str(length) + "}", invocation[key]))
        ref = invocation["ref"]
        # Match the existing context syntax, including tags; authorization and
        # profile alignment still belong to the original consumer parsers.
        _require(invocation["fleet_sha"] == invocation["workflow_sha"]
                 and type(ref) is str and 0 < len(ref) <= 2048
                 and re.fullmatch(r"refs/(heads|tags)/[A-Za-z0-9._/-]+", ref)
                 and not any(part in {"", ".", ".."} for part in ref.split("/"))
                 and ".." not in ref and not ref.endswith(".lock"))
        for key in ("run_id", "run_attempt"):
            _require(type(invocation[key]) is str and re.fullmatch(r"[1-9][0-9]{0,19}", invocation[key]))
        # One fixed existing map, never an inferred owner root or merged union.
        owner = _pins(value["owner"]["code_pins"])
        selected = _pins(value["protected"]["launcher"]["code_pins"])
        _require(all(owner[name] == selected[name] for name in owner.keys() & selected.keys()))
        _require({name.replace(".", "/") + ".py" for name in TARGETS.values()} <= selected.keys())
        for relative, digest in selected.items():
            path = self.root / relative
            item = self._hold(path, digest, SOURCE_LIMIT)
            self.files[relative] = item
            name = _module_name(relative)
            _require(name not in self.modules)
            self.modules[name] = item
            if path.name != "__init__.py":
                self.absent.add(path.with_suffix(""))  # Same-stem package wins ordinary import lookup.
            self.absent.add(path.with_suffix(".pyc"))
            for directory in (path.parent, *path.parent.parents):
                if directory == self.root:
                    break
                self.absent.add(directory / "__pycache__")
                self.absent.add(directory / "__init__.pyc")
                init = directory / "__init__.py"
                if os.path.lexists(init):
                    _require(str(init.relative_to(self.root)) in selected)
                else:
                    self.absent.add(init)
                    self.namespaces[str(directory.relative_to(self.root)).replace("/", ".")] = directory
        _require(len({item.stamp[:2] for item in self.held}) == len(self.held))
        for relative, item in self.files.items():
            for node in ast.walk(ast.parse(item.raw, filename=relative)):
                imports = []
                if isinstance(node, ast.Import):
                    imports = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    _require(not node.level)
                    imports = (["scripts." + alias.name for alias in node.names]
                               if node.module == "scripts" else [node.module or ""])
                for name in imports:
                    if name in BARE:
                        _require(BARE[name] in self.modules)
                    elif name == "scripts" or name.startswith("scripts."):
                        _require(name in self.modules or name in self.namespaces)
                    elif name.startswith("android_"):
                        raise AdmissionError(ERROR)
        self._initial_namespace()
        self.path_before, self.finders_before = tuple(sys.path), tuple(sys.meta_path)
        self._fence()

    def _initial_namespace(self):
        for name, module in tuple(sys.modules.items()):
            if not _fleet_name(name):
                continue
            if name == SELF:
                _require(getattr(module, "__dict__", None) is globals() and name in self.modules
                         and Path(module.__file__) == self.modules[name].path)
            elif name == "scripts":
                _require(SELF in sys.modules and getattr(sys.modules[SELF], "__dict__", None) is globals()
                         and list(getattr(module, "__path__", ())) == [str(self.root / "scripts")]
                         and getattr(module, "__file__", None) is None
                         and set(vars(module)) <= {"__name__", "__doc__", "__package__", "__loader__",
                             "__spec__", "__file__", "__path__", "android_hosted_source_admission"})
            else:
                raise AdmissionError(ERROR)
            self.initial[name] = (module, _module_stamp(module))
        if SELF in self.initial:
            _require("scripts" in self.initial
                     and getattr(self.initial["scripts"][0], "android_hosted_source_admission", None)
                     is self.initial[SELF][0])

    def _fence(self):
        _require(not self.closed and not self.failed and tuple(sys.path) == self.path_before)
        expected = (self, *self.finders_before) if self.installed else self.finders_before
        _require(tuple(sys.meta_path) == expected and not any(os.path.lexists(path) for path in self.absent))
        for item in self.held:
            item.recheck()

    def _bindings(self):
        expected = set(self.initial) | set(self.owned)
        actual = {name for name in sys.modules if _fleet_name(name)}
        _require(actual == expected)
        for name, (module, stamp) in self.initial.items():
            _require(sys.modules.get(name) is module and _module_stamp(module) == stamp)
        for name, module in self.owned.items():
            item = self.modules.get(BARE.get(name, name))
            spec = module.__spec__
            _require(sys.modules.get(name) is module and module.__loader__ is self and spec.loader is self
                     and spec.name == name and module.__name__ == name)
            if item is None:
                _require(getattr(module, "__file__", None) is None and spec.origin is None
                         and list(module.__path__) == [str(self.namespaces[name])])
            else:
                _require(module.__file__ == str(item.path) and spec.origin == str(item.path))
                if item.path.name == "__init__.py":
                    _require(list(module.__path__) == list(spec.submodule_search_locations)
                             == [str(item.path.parent)])
                else:
                    _require(not hasattr(module, "__path__") and spec.submodule_search_locations is None)
        for name in expected:
            if "." in name:
                parent, child = name.rsplit(".", 1)
                _require(getattr(sys.modules.get(parent), child, None) is sys.modules[name])
        # Reject package attributes shadowing a not-yet-imported admitted child.
        missing = object()
        for name in self.modules.keys() | self.namespaces.keys():
            if "." in name and name not in sys.modules:
                parent, child = name.rsplit(".", 1)
                _require(getattr(sys.modules.get(parent), child, missing) is missing)

    def recheck(self):
        try:
            self._fence()
            self._bindings()
        except BaseException:
            self.failed = True
            raise AdmissionError(ERROR) from None

    def find_spec(self, fullname, path=None, target=None):
        if not _fleet_name(fullname):
            return None  # Already independently admitted standard/external runtime.
        try:
            self._fence()
            name = BARE.get(fullname, fullname)
            _require(name in self.modules or name in self.namespaces)
            item = self.modules.get(name)
            package = item is None or item.path.name == "__init__.py"
            spec = importlib.machinery.ModuleSpec(fullname, self,
                origin=str(item.path) if item else None, is_package=package)
            if item:
                spec.has_location = True
            if package:
                spec.submodule_search_locations = [str(item.path.parent if item else self.namespaces[name])]
            return spec
        except BaseException:
            self.failed = True
            raise AdmissionError(ERROR) from None

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        try:
            self._fence()
            name = module.__spec__.name
            _require(name not in self.owned and name not in self.initial)
            self.owned[name] = module
            item = self.modules.get(BARE.get(name, name))
            if item is not None:
                exec(compile(item.raw, str(item.path), "exec", dont_inherit=True), module.__dict__)
            self._fence()
        except BaseException:
            self.failed = True
            raise AdmissionError(ERROR) from None

    def import_targets(self):
        """Import only the three fixed targets from captured, already pinned bytes."""
        try:
            _require(not self.attempted)
            self.attempted = True
            self.recheck()
            sys.meta_path.insert(0, self)
            self.installed = True
            result = {label: importlib.import_module(name) for label, name in TARGETS.items()}
            self.recheck()
            return result
        except BaseException:
            self.failed = True
            raise AdmissionError(ERROR) from None

    def close(self):
        # Only remove entries this lease created, never erase another actor's
        # replacement or any file. A failed import remains a failed attempt.
        failed = False
        try:
            for name, module in sorted(self.owned.items(), key=lambda item: item[0].count("."), reverse=True):
                if "." in name:
                    parent, child = name.rsplit(".", 1)
                    parent_module = sys.modules.get(parent)
                    if getattr(parent_module, child, None) is module:
                        delattr(parent_module, child)
                if sys.modules.get(name) is module:
                    del sys.modules[name]
        except BaseException:
            failed = True
        sys.meta_path[:] = [finder for finder in sys.meta_path if finder is not self]
        for item in reversed(self.held):
            try:
                item.close()
            except BaseException:
                failed = True
        self.closed = True
        _require(not failed)


@contextmanager
def admit(*, profile, profile_sha256, context, context_sha256, hosted_root):
    """Hold admitted existing documents/source through caller-owned fixed calls.

    Use import_targets() once; call recheck() immediately around each existing
    materializer/stager/role call. Full consumer policy parsing remains there.
    Leaving the context removes only this lease's imports and closes its FDs.
    Initial Python/dependency trust and genuine deployment admission are NOT
    established here. No operational call, credential read or file write occurs.
    """
    lease = _Admission()
    try:
        lease.prepare(profile, profile_sha256, context, context_sha256, hosted_root)
        yield lease
        lease.recheck()
    except BaseException:
        raise AdmissionError(ERROR) from None
    finally:
        lease.close()
