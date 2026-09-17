"""Fixed hosted phases, after independent bootstrap/runtime/input admission.

Execute this independently admitted file as __main__ or the one private
bootstrap identity below, never import it through scripts. Supplied hashes and
root are independently selected authority, not candidate self-hashes. This
caller does not provision a runtime, credential, controller or deployment.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack, contextmanager
import hashlib
import os
from pathlib import Path
import re
import stat
import sys
import types

ERROR = "hosted phase stopped; preserve inputs and reconcile"
COMPLETE = "hosted phase completed"
PHASES = ("capture", "emission-prepare", "emission-submit")
CALLER = "_chummer_hosted_phase_caller"
HELPER = "_chummer_hosted_source_admission"
HELPER_RELATIVE = "scripts/android_hosted_source_admission.py"
HELPER_LIMIT = 2 * 1024**2
_used = False


class PhaseError(RuntimeError):
    """Constant diagnostics; upstream exceptions and private data stay private."""


def _require(value):
    if not value:
        raise PhaseError(ERROR)


def _path(value):
    _require(isinstance(value, Path) and value.is_absolute() and value != Path("/")
             and ".." not in value.parts and "\\" not in str(value)
             and all(32 < ord(char) < 127 for char in str(value)))
    return value


def _stamp(info):
    return tuple(getattr(info, name) for name in ("st_dev", "st_ino", "st_mode", "st_uid",
        "st_gid", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns"))


def _parents(path):
    # Bootstrap-local copy of the existing source gate's public ancestry rule:
    # that gate cannot safely be imported to authenticate its own initial bytes.
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


@contextmanager
def _helper(root, digest):
    """Capture exactly one independently pinned helper before executing it."""
    path = _path(root) / HELPER_RELATIVE
    _require(type(digest) is str and re.fullmatch(r"[0-9a-f]{64}", digest) and HELPER not in sys.modules)
    parents = _parents(path)
    info = path.lstat()
    _require(path.resolve(strict=True) == path and stat.S_ISREG(info.st_mode)
             and info.st_uid in {0, os.getuid()} and info.st_gid in {0, os.getgid()}
             and info.st_nlink == 1 and 0 < info.st_size <= HELPER_LIMIT and not info.st_mode & 0o022)
    stamp = _stamp(info)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    module = None
    try:
        def check():
            _require(_stamp(os.fstat(fd)) == stamp == _stamp(path.lstat())
                     and path.resolve(strict=True) == path and _parents(path) == parents)
            raw = os.pread(fd, info.st_size + 1, 0)
            _require(len(raw) == info.st_size and hashlib.sha256(raw).hexdigest() == digest
                     and _stamp(os.fstat(fd)) == stamp == _stamp(path.lstat()))
            if module is not None:
                _require(sys.modules.get(HELPER) is module and module.__name__ == HELPER
                         and module.__file__ == str(path) and module.__package__ == "")
        check()
        raw = os.pread(fd, info.st_size + 1, 0)
        _require(len(raw) == info.st_size and hashlib.sha256(raw).hexdigest() == digest)
        check()
        module = types.ModuleType(HELPER)
        module.__file__, module.__package__ = str(path), ""
        sys.modules[HELPER] = module
        check()
        exec(compile(raw, str(path), "exec", dont_inherit=True), module.__dict__)
        check()
        yield module, check
        check()
    finally:
        if module is not None and sys.modules.get(HELPER) is module:
            del sys.modules[HELPER]
        os.close(fd)


def run(phase, *, hosted_root, helper_sha256, profile, profile_sha256,
        context, context_sha256, deployment, deployment_sha256, bundle_path=None):
    """One invocation; retain original contracts, effects and no-replay markers."""
    global _used
    try:
        _require(not _used)
        _used = True
        _require(__name__ in {"__main__", CALLER} and phase in PHASES
                 and os.getuid() == os.geteuid() and os.getgid() == os.getegid()
                 and sys.flags.isolated == 1 and sys.dont_write_bytecode and sys.pycache_prefix is None)
        for path in (hosted_root, profile, context, deployment):
            _path(path)
        _require((bundle_path is not None) == (phase == "emission-submit"))
        if bundle_path is not None:
            _path(bundle_path)
        for digest in (helper_sha256, profile_sha256, context_sha256, deployment_sha256):
            _require(type(digest) is str and re.fullmatch(r"[0-9a-f]{64}", digest))
        with _helper(hosted_root, helper_sha256) as (admission, helper_check):
            with admission.admit(profile=profile, profile_sha256=profile_sha256,
                    context=context, context_sha256=context_sha256, hosted_root=hosted_root) as lease:
                helper_check(); lease.recheck()
                modules = lease.import_targets()
                helper_check(); lease.recheck()
                materializer, stager, hosted = (modules[key] for key in ("materializer", "stager", "hosted"))
                with ExitStack() as cleanup:
                    documents = []
                    specs = ((profile, profile_sha256, materializer.MAX_PROFILE, True),
                             (context, context_sha256, materializer.MAX_CONTEXT, True),
                             (deployment, deployment_sha256, hosted.MAX_CONFIG, False))
                    for path, digest, limit, public in specs:
                        item = hosted._Input(path, limit, expected=digest, public=public)
                        cleanup.callback(item.close)
                        documents.append(item)
                    _require(len({item.stamp[:2] for item in documents}) == 3
                             and documents[2].stamp[:2] not in {item.stamp[:2] for item in lease.held})
                    def check():
                        helper_check(); lease.recheck()
                        for item in documents:
                            _require(item.read() == item.raw)
                        helper_check(); lease.recheck()
                    check()
                    role = "capture" if phase == "capture" else "emission"
                    rendered = materializer.render(materializer._json(documents[0].raw),
                                                   materializer._json(documents[1].raw), role)
                    check()
                    _require(rendered == documents[2].raw)
                    if phase != "emission-submit":
                        check()
                        staged = stager.stage(role=role, profile=profile, profile_sha256=profile_sha256,
                            context=context, context_sha256=context_sha256,
                            deployment=deployment, deployment_sha256=deployment_sha256)
                        check()
                        _require(staged == stager.COMPLETE)
                    check()
                    result = hosted.run(phase, deployment, deployment_sha256, bundle_path=bundle_path)
                    check()
                    _require(result == hosted.COMPLETE[phase])
        return COMPLETE
    except BaseException:
        raise PhaseError(ERROR) from None


class _Parser(argparse.ArgumentParser):
    def error(self, _message):
        raise PhaseError(ERROR)


def main(argv=None):
    try:
        parser = _Parser(allow_abbrev=False, add_help=False)
        parser.add_argument("phase", choices=PHASES)
        parser.add_argument("--hosted-root", required=True)
        parser.add_argument("--helper-sha256", required=True)
        for name in ("profile", "context", "deployment"):
            parser.add_argument("--" + name, required=True)
            parser.add_argument("--" + name + "-sha256", required=True)
        parser.add_argument("--bundle")
        args = parser.parse_args(argv)
        print(run(args.phase, hosted_root=Path(args.hosted_root), helper_sha256=args.helper_sha256,
            profile=Path(args.profile), profile_sha256=args.profile_sha256,
            context=Path(args.context), context_sha256=args.context_sha256,
            deployment=Path(args.deployment), deployment_sha256=args.deployment_sha256,
            bundle_path=Path(args.bundle) if args.bundle is not None else None), flush=True)
        return 0
    except BaseException:
        print(ERROR, file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
