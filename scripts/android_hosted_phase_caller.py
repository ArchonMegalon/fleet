"""Fixed hosted phases, after independent bootstrap/runtime/input admission.

Execute this independently admitted file as __main__ or the one private
bootstrap identity below, never import it through scripts. Supplied hashes and
root are independently selected authority, not candidate self-hashes. This
caller does not provision a runtime or controller. Its explicit prepare-inputs
mode creates only hosted role-local paths, a rendered deployment and an already
injected bearer; neither its returned digest nor those files grant authority.
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


def prepare_inputs(role, *, hosted_root, helper_sha256, profile, profile_sha256,
                   context, context_sha256, job_root, deployment, environment=None):
    """Create one fresh hosted input tree; never request OIDC or execute a role."""
    global _used
    try:
        _require(not _used)
        _used = True
        _require(__name__ in {"__main__", CALLER} and role in {"capture", "emission"}
                 and os.getuid() == os.geteuid() and os.getgid() == os.getegid()
                 and sys.flags.isolated == 1 and sys.dont_write_bytecode and sys.pycache_prefix is None)
        for path in (hosted_root, profile, context, job_root, deployment):
            _path(path)
        for digest in (helper_sha256, profile_sha256, context_sha256):
            _require(type(digest) is str and re.fullmatch(r"[0-9a-f]{64}", digest))
        _require(not os.path.lexists(job_root))
        with _helper(hosted_root, helper_sha256) as (admission, helper_check):
            with admission.admit(profile=profile, profile_sha256=profile_sha256,
                    context=context, context_sha256=context_sha256, hosted_root=hosted_root) as lease:
                helper_check(); lease.recheck()
                modules = lease.import_targets()
                materializer, stager, hosted = (modules[key] for key in ("materializer", "stager", "hosted"))
                with ExitStack() as cleanup:
                    held, directories, created = [], {}, set()
                    def hold(path, digest, limit, public=False):
                        item = hosted._Input(path, limit, expected=digest, public=public)
                        cleanup.callback(item.close); held.append(item)
                        return item
                    documents = (hold(profile, profile_sha256, materializer.MAX_PROFILE, True),
                                 hold(context, context_sha256, materializer.MAX_CONTEXT, True))
                    helper_check(); lease.recheck()
                    rendered = materializer.render(materializer._json(documents[0].raw),
                                                   materializer._json(documents[1].raw), role)
                    phase = "capture" if role == "capture" else "emission-prepare"
                    value, _, _, pins, inputs, attempt = hosted._document(rendered, phase)
                    leaves = [deployment, *inputs.values(), attempt]
                    _require(all(path != job_root and path.is_relative_to(job_root) for path in leaves)
                             and all(not a.is_relative_to(b) and not b.is_relative_to(a)
                                     for i, a in enumerate(leaves) for b in leaves[i+1:]))
                    outside = [profile, context, hosted_root, *(pin.path for pin in pins.values())]
                    action_root = value["attestation_output_root"]
                    if action_root is not None:
                        outside.append(Path(action_root))
                    _require(all(not path.is_relative_to(job_root) and not job_root.is_relative_to(path)
                                 for path in outside))
                    needed = {job_root}
                    for path in leaves:
                        relative = path.relative_to(job_root)
                        _require(len(relative.parts) <= 8)
                        for parent in path.parents:
                            if parent == job_root:
                                break
                            needed.add(parent)
                    _require(len(needed) <= 32 and not set(leaves) & needed)
                    parent_chain = _parents(job_root)
                    _require(parent_chain[-1][3:] == (os.getuid(), os.getgid())
                             and stat.S_IMODE(parent_chain[-1][2]) == 0o700)
                    parent_fd = os.open(job_root.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
                    cleanup.callback(os.close, parent_fd)
                    directory_stamp = lambda info: (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid)
                    _require(directory_stamp(os.fstat(parent_fd)) == parent_chain[-1])
                    _require(directory_stamp(hosted_root.lstat())[:2] not in {row[:2] for row in parent_chain})
                    action = None
                    if action_root is not None:
                        action_root = Path(action_root)
                        action_chain = _parents(action_root / "unused")
                        fd = os.open(action_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
                        cleanup.callback(os.close, fd)
                        stamp = directory_stamp(os.fstat(fd))
                        _require(stamp == action_chain[-1] and stamp[:2] not in {row[:2] for row in parent_chain})
                        action = (fd, stamp, action_chain)
                    for pin in pins.values():
                        hold(pin.path, pin.sha256, 1024**2)
                    _require(len({item.stamp[:2] for item in held}) == len(held))
                    def check():
                        helper_check(); lease.recheck()
                        for item in held:
                            _require(item.read() == item.raw)
                        _require(_parents(job_root) == parent_chain
                                 and directory_stamp(os.fstat(parent_fd)) == parent_chain[-1])
                        if not directories:
                            _require(not os.path.lexists(job_root))
                        for path, (fd, stamp) in directories.items():
                            _require(path.resolve(strict=True) == path
                                     and directory_stamp(path.lstat()) == stamp == directory_stamp(os.fstat(fd)))
                            expected = {p.name for p in (*directories, *created) if p.parent == path}
                            with os.scandir(fd) as entries:
                                actual = set()
                                for entry in entries:
                                    _require(entry.name in expected and entry.name not in actual)
                                    actual.add(entry.name)
                            _require(actual == expected)
                        _require(all(path in created or not os.path.lexists(path) for path in leaves))
                        if action is not None:
                            fd, stamp, chain = action
                            _require(_parents(action_root / "unused") == chain
                                     and directory_stamp(os.fstat(fd)) == stamp == directory_stamp(action_root.lstat()))
                        helper_check(); lease.recheck()
                    check()
                    for path in sorted(needed, key=lambda p: (len(p.parts), str(p))):
                        check()
                        base_fd = parent_fd if path == job_root else directories[path.parent][0]
                        os.mkdir(path.name, 0o700, dir_fd=base_fd)
                        fd = os.open(path.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=base_fd)
                        cleanup.callback(os.close, fd)
                        stamp = directory_stamp(os.fstat(fd))
                        _require(stamp[3:] == (os.getuid(), os.getgid()) and stat.S_IMODE(stamp[2]) == 0o700)
                        directories[path] = (fd, stamp)
                        check(); os.fsync(fd); os.fsync(base_fd); check()
                    digest = materializer.materialize(profile, profile_sha256, context, context_sha256, deployment, role)
                    created.add(deployment)
                    output = hold(deployment, digest, hosted.MAX_CONFIG)
                    _require(output.raw == rendered and digest == hashlib.sha256(rendered).hexdigest())
                    check()
                    selected_environment = os.environ if environment is None else environment
                    class BearerEnvironment:
                        def get(self, name):
                            _require(name == "ANDROID_PREVIEW12_ROLE_BEARER")
                            check()
                            raw = selected_environment.get(name)
                            check()
                            return raw
                    result = stager.deliver_role_bearer(role=role, profile=profile, profile_sha256=profile_sha256,
                        context=context, context_sha256=context_sha256, deployment=deployment,
                        deployment_sha256=digest, environment=BearerEnvironment())
                    created.add(inputs["role_bearer"])
                    bearer = hold(inputs["role_bearer"],
                                  materializer._json(documents[0].raw)["owner"]["bearer_sha256"][role],
                                  hosted.INPUT_LIMITS["role_bearer"])
                    _require(result == stager.BEARER_COMPLETE
                             and len({item.stamp[:2] for item in held}) == len(held))
                    check()
                return digest
    except BaseException:
        raise PhaseError(ERROR) from None


class _Parser(argparse.ArgumentParser):
    def error(self, _message):
        raise PhaseError(ERROR)


def main(argv=None):
    try:
        parser = _Parser(allow_abbrev=False, add_help=False)
        parser.add_argument("phase", choices=(*PHASES, "prepare-inputs"))
        parser.add_argument("--hosted-root", required=True)
        parser.add_argument("--helper-sha256", required=True)
        for name in ("profile", "context"):
            parser.add_argument("--" + name, required=True)
            parser.add_argument("--" + name + "-sha256", required=True)
        parser.add_argument("--bundle")
        parser.add_argument("--deployment", required=True)
        parser.add_argument("--deployment-sha256")
        parser.add_argument("--role", choices=("capture", "emission"))
        parser.add_argument("--job-root")
        args = parser.parse_args(argv)
        if args.phase == "prepare-inputs":
            _require(args.role is not None and args.job_root is not None
                     and args.deployment_sha256 is None and args.bundle is None)
            print(prepare_inputs(args.role, hosted_root=Path(args.hosted_root),
                helper_sha256=args.helper_sha256, profile=Path(args.profile), profile_sha256=args.profile_sha256,
                context=Path(args.context), context_sha256=args.context_sha256,
                job_root=Path(args.job_root), deployment=Path(args.deployment)), flush=True)
            return 0
        _require(args.role is None and args.job_root is None and args.deployment_sha256 is not None)
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
