"""Fixed root host-step supervisor; no credentials, activation or action retry.

The caller admits this interpreter/dependency closure before executing this file.
The already-installed exporter must support the explicitly selected pending mode.
READY and the anonymous pipe sequence local execution, never remote authority.
Optional public startup metadata delays child creation; it never releases the
pipe or replaces the child's independent authentication and custody checks.
"""
from __future__ import annotations

import argparse
import ast
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import select
import signal
import stat
import subprocess
import sys
import time

ERROR = "protected host supervision stopped; reconcile retained evidence"
COMPLETE = "protected host child returned; inspect retained audit"
READY = b"protected owner prepared; awaiting owner release"
RETURNED = b"protected owner execution returned; inspect retained audit"
OWNER_UID = OWNER_GID = 0
MAX_OUTPUT = 4096
STOP_GRACE = 1.0
TARGET = "scripts/android_protected_job_bootstrap.py"
CHILD_CODE = ("import sys;sys.path.insert(0,sys.argv[1]);"
              "from scripts.android_protected_job_bootstrap import main;"
              "raise SystemExit(main(sys.argv[2:]))")


class SupervisorError(RuntimeError):
    """Only a constant reaches the caller; upstream details stay private."""


def require(value):
    if not value:
        raise SupervisorError(ERROR)


def _path(value):
    require(type(value) is str and value.startswith("/") and "\\" not in value
            and all(32 < ord(c) < 127 for c in value)
            and str(Path(value)) == value and ".." not in Path(value).parts)
    return Path(value)


def _stamp(info):
    return tuple(getattr(info, name) for name in ("st_dev", "st_ino", "st_mode", "st_uid",
        "st_gid", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns"))


def _parents(path):
    require(path.is_absolute() and path.parent.resolve(strict=True) == path.parent)
    chain = [*reversed(path.parent.parents), path.parent]
    result = []
    for index, part in enumerate(chain):
        info = part.lstat()
        require(stat.S_ISDIR(info.st_mode) and info.st_uid in {0, OWNER_UID}
                and info.st_gid in {0, OWNER_GID})
        if info.st_mode & 0o022:
            require(part == Path("/tmp") and info.st_uid == 0
                    and stat.S_IMODE(info.st_mode) == 0o1777 and index + 1 < len(chain))
            child = chain[index + 1].lstat()
            require(child.st_uid == OWNER_UID and child.st_gid == OWNER_GID
                    and stat.S_IMODE(child.st_mode) == 0o700)
        result.append((info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid))
    return tuple(result)


class _Pin:
    def __init__(self, path, digest, limit, *, private=False, executable=False):
        require(type(digest) is str and re.fullmatch("[0-9a-f]{64}", digest))
        self.path, self.parents = path, _parents(path)
        info = path.lstat()
        require(path.resolve(strict=True) == path and stat.S_ISREG(info.st_mode)
                and info.st_uid in {0, OWNER_UID} and info.st_gid in {0, OWNER_GID}
                and info.st_nlink == 1 and 0 < info.st_size <= limit
                and not info.st_mode & 0o022 and (not executable or info.st_mode & 0o111)
                and (not private or stat.S_IMODE(info.st_mode) in {0o400, 0o600}))
        self.stamp = _stamp(info)
        self.fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
        try:
            self.recheck()
            self.raw = os.pread(self.fd, limit + 1, 0)
            self.recheck()
            require(len(self.raw) == info.st_size and hashlib.sha256(self.raw).hexdigest() == digest)
        except BaseException:
            self.close()
            raise

    def recheck(self):
        require(_stamp(os.fstat(self.fd)) == self.stamp == _stamp(self.path.lstat())
                and self.path.resolve(strict=True) == self.path and _parents(self.path) == self.parents)

    def close(self):
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1


def _json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result)
            result[key] = value
        return result
    def invalid(_):
        raise SupervisorError(ERROR)
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=invalid)
    require(type(value) is dict)
    return value


def _code(root, pins, hold):
    require(type(pins) is dict and 1 <= len(pins) <= 64 and TARGET in pins)
    files, absent = {}, []
    for relative, digest in pins.items():
        require(type(relative) is str and re.fullmatch(r"scripts/(?:[A-Za-z_]\w*/)*[A-Za-z_]\w*\.py", relative))
        path = root / relative
        files[relative] = hold(path, digest, 2 * 1024**2)
        for directory in (path.parent, *path.parent.parents):
            if directory == root:
                break
            cache = directory / "__pycache__"
            require(not os.path.lexists(cache))
            absent.append(cache)
            init = directory / "__init__.py"
            if os.path.lexists(init):
                require(str(init.relative_to(root)) in pins)
            else:
                absent.append(init)
        require(not os.path.lexists(path.with_suffix(".pyc")))
        absent.append(path.with_suffix(".pyc"))
    # Reject omitted literal Fleet imports BEFORE executing the pinned bootstrap.
    # Dynamic loaders and non-Fleet dependencies still require prior owner admission.
    for relative, item in files.items():
        for node in ast.walk(ast.parse(item.raw, filename=relative)):
            modules = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names if alias.name.startswith("scripts.")]
            elif isinstance(node, ast.ImportFrom):
                require(not node.level)  # Existing admitted closure uses absolute imports.
                if node.module == "scripts":
                    modules = ["scripts." + alias.name for alias in node.names]
                elif node.module and node.module.startswith("scripts."):
                    modules = [node.module]
            for module in modules:
                require(module.replace(".", "/") + ".py" in files)
    return absent


def _process_stamp(pid):
    with open(f"/proc/{pid}/stat", "rb") as stream:
        raw = stream.read(8193)
    require(len(raw) <= 8192 and raw.startswith(str(pid).encode() + b" ("))
    fields = raw.rsplit(b") ", 1)[1].split()
    require(len(fields) >= 20 and int(fields[2]) == pid and int(fields[3]) == pid)
    return pid, int(fields[19])  # Own unreaped session leader + kernel start ticks.


def _stop(child, stamp, pidfd):
    # Never poll()/wait() before the last group signal: an unreaped child keeps
    # its PID reserved even if it is already a zombie. No foreign PID adoption.
    require(_process_stamp(child.pid) == stamp)
    os.killpg(child.pid, signal.SIGTERM)
    select.select([pidfd], [], [], STOP_GRACE)
    require(_process_stamp(child.pid) == stamp)
    os.killpg(child.pid, signal.SIGKILL)


def _interrupted(_number, _frame):
    raise SupervisorError(ERROR)


def _fleet_imports(root, pins):
    """Reject ambient Fleet namespaces before any optional startup import."""
    require({"scripts/android_startup_scheduling.py", "scripts/android_workflow_job_binder.py"} <= set(pins))
    namespace = sys.modules.get("scripts")
    require(namespace is not None and list(getattr(namespace, "__path__", ())) == [str(root / "scripts")])
    missing = object()
    for relative in pins:
        name = relative.removesuffix(".py").replace("/", ".").removesuffix(".__init__")
        if name == "scripts":
            continue
        parent_name, child = name.rsplit(".", 1)
        loaded = sys.modules.get(name, missing)
        attribute = getattr(sys.modules.get(parent_name), child, missing)
        require((loaded is missing and attribute is missing)
                or (loaded is not missing and loaded is attribute))
    for name, module in tuple(sys.modules.items()):
        if name != "scripts" and not name.startswith("scripts."):
            continue
        path = getattr(module, "__file__", None)
        if name == "scripts" and path is None:
            continue  # One exact namespace path above, no arbitrary search path.
        if name != "scripts":
            parent_name, child_name = name.rsplit(".", 1)
            require(getattr(sys.modules.get(parent_name), child_name, None) is module)
        expected = name.replace(".", "/") + ".py"
        if expected not in pins:
            expected = name.replace(".", "/") + "/__init__.py"
        require(type(path) is str and expected in pins and Path(path) == root / expected
                and Path(path).resolve(strict=True) == Path(path))


def _wait_for_export(value, root, deadline, check):
    pins = value["launcher"]["code_pins"]
    _fleet_imports(root, pins)
    from scripts import android_startup_scheduling as startup
    from scripts import android_workflow_job_binder as binder
    require(sys.modules.get("scripts.android_startup_scheduling") is startup
            and sys.modules.get("scripts.android_workflow_job_binder") is binder)
    _fleet_imports(root, pins)
    check()
    startup.validate_deployment(value)
    observed = startup.wait_for_stage(value, "export", deadline=deadline, recheck=check)
    check()
    # A publication never supplies job identity. Resolve independently before
    # creating a private child; its original binding/auth still runs as well.
    bound = binder.bind_deployment_roles(binding=value["role_binding"],
        current_policies={"protected": binder.identity.WorkflowJobPolicy(**value["job_policy"])},
        role="protected", deadline=deadline)
    check()
    require(startup.binding_digest(bound) == observed)
    _fleet_imports(root, pins)
    check()


def run(deployment, digest, interpreter_sha256, maximum_seconds):
    child = None
    read_fd = write_fd = pidfd = None
    stamp = None
    handlers = {}
    spawning = cancelled = False
    def interrupted(number, frame):
        nonlocal cancelled
        if spawning:
            cancelled = True  # Popen must transfer ownership before unwinding.
        else:
            _interrupted(number, frame)
    try:
        require(os.getuid() == os.geteuid() == OWNER_UID and os.getgid() == os.getegid() == OWNER_GID
                and signal.getsignal(signal.SIGCHLD) == signal.SIG_DFL
                and type(maximum_seconds) is int and 1 <= maximum_seconds <= 86400)
        deadline = time.monotonic() + maximum_seconds
        for number in (signal.SIGTERM, signal.SIGINT):
            handlers[number] = signal.signal(number, interrupted)
        with ExitStack() as cleanup:
            snapshots = []
            def hold(*args, **kwargs):
                value = _Pin(*args, **kwargs)
                cleanup.callback(value.close); snapshots.append(value)
                return value
            source = hold(deployment, digest, 256 * 1024, private=True)
            value = _json(source.raw)
            require(type(value.get("preparation_wait_seconds")) is int
                    and 1 <= value["preparation_wait_seconds"] <= 1800)
            config = value["launcher"]
            require(type(config) is dict)
            root = _path(config["fleet_root"])
            absent = _code(root, config["code_pins"], hold)
            executable = _path(sys.executable)
            executable_parents, executable_stamp = _parents(executable), _stamp(executable.lstat())
            require(executable_stamp[3] in {0, OWNER_UID} and executable_stamp[4] in {0, OWNER_GID})
            # Preserve a qualified venv's executable path, including a final
            # root-owned symlink; hash the real interpreter, fence both identities.
            interpreter_target = executable.resolve(strict=True)
            hold(interpreter_target, interpreter_sha256, 128 * 1024**2, executable=True)
            def check():
                require(time.monotonic() < deadline and _parents(executable) == executable_parents
                        and _stamp(executable.lstat()) == executable_stamp
                        and executable.resolve(strict=True) == interpreter_target
                        and not any(os.path.lexists(path) for path in absent))
                for item in snapshots:
                    item.recheck()
            check()
            if "startup_barrier" in value:
                _wait_for_export(value, root, deadline, check)
            read_fd, write_fd = os.pipe2(os.O_CLOEXEC)
            spawning = True
            child = subprocess.Popen([str(executable), "-I", "-B", "-c", CHILD_CODE, str(root),
                "--deployment", str(deployment), "--deployment-sha256", digest,
                "--owner-release-fd", str(read_fd)], stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True,
                pass_fds=(read_fd,), start_new_session=True, bufsize=0,
                env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"})
            cleanup.callback(child.stdout.close)
            cleanup.callback(child.stderr.close)
            spawning = False
            require(not cancelled)  # finally can now identify/stop the owned child.
            os.close(read_fd); read_fd = None
            pidfd = os.pidfd_open(child.pid)
            stamp = _process_stamp(child.pid)
            ready = returned = False
            total, buffered = 0, b""
            with selectors.DefaultSelector() as selector:
                for stream in (child.stdout, child.stderr):
                    os.set_blocking(stream.fileno(), False)
                    selector.register(stream, selectors.EVENT_READ)
                while selector.get_map():
                    check()
                    events = selector.select(max(0, deadline - time.monotonic()))
                    require(events and time.monotonic() < deadline)
                    for key, _ in events:
                        chunk = os.read(key.fileobj.fileno(), MAX_OUTPUT + 1)
                        if not chunk:
                            selector.unregister(key.fileobj)
                            continue
                        total += len(chunk)
                        require(total <= MAX_OUTPUT and key.fileobj is child.stdout)
                        buffered += chunk
                        while b"\n" in buffered:
                            line, buffered = buffered.split(b"\n", 1)
                            if line == READY and not ready and not returned:
                                check()
                                require(_process_stamp(child.pid) == stamp)
                                ready = True
                                require(os.write(write_fd, b"1") == 1)
                                os.close(write_fd); write_fd = None
                            elif line == RETURNED and ready and not returned:
                                returned = True
                            else:
                                raise SupervisorError(ERROR)
            require(ready and returned and not buffered)
            check()
            require(select.select([pidfd], [], [], max(0, deadline - time.monotonic()))[0] == [pidfd])
            require(time.monotonic() < deadline)
            _stop(child, stamp, pidfd)
            status = child.wait(timeout=STOP_GRACE)
            child = None
            require(status == 0)
            return COMPLETE
    except BaseException:
        raise SupervisorError(ERROR) from None
    finally:
        failed = False
        for number in handlers:
            signal.signal(number, signal.SIG_IGN)
        if child is not None:
            try:
                if stamp is None:
                    stamp = _process_stamp(child.pid)
                if pidfd is None:
                    pidfd = os.pidfd_open(child.pid)
                _stop(child, stamp, pidfd)
            except BaseException:
                failed = True
            try:
                child.wait(timeout=STOP_GRACE)
            except BaseException:
                failed = True
        for fd in (read_fd, write_fd, pidfd):
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    failed = True
        for number, handler in handlers.items():
            signal.signal(number, handler)
        if failed:
            raise SupervisorError(ERROR) from None


class _Parser(argparse.ArgumentParser):
    def error(self, _message):
        raise SupervisorError(ERROR)


def main(argv=None):
    try:
        parser = _Parser(allow_abbrev=False, add_help=False)
        parser.add_argument("--deployment", required=True)
        parser.add_argument("--deployment-sha256", required=True)
        parser.add_argument("--interpreter-sha256", required=True)
        parser.add_argument("--maximum-seconds", required=True, type=int)
        args = parser.parse_args(argv)
        print(run(_path(args.deployment), args.deployment_sha256, args.interpreter_sha256,
                  args.maximum_seconds), flush=True)
        return 0
    except BaseException:
        print(ERROR, file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
