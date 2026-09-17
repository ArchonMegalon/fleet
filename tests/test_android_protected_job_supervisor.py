"""Real benign child/anonymous pipe/process-group tests, modeled root identity.

Synthetic independently pinned bootstrap code only: no OIDC, HTTP, Docker,
mount, signing, live credential, attester or production bootstrap execution.
"""
import hashlib
import json
import os
from pathlib import Path
import signal
import select
import sys

import pytest

from scripts import android_protected_job_supervisor as owner


BENIGN = '''import argparse, os, sys, time
def main(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--deployment")
    p.add_argument("--deployment-sha256")
    p.add_argument("--owner-release-fd", type=int)
    args = p.parse_args(argv)
    print("protected owner prepared; awaiting owner release", flush=True)
    assert os.read(args.owner_release_fd, 2) == b"1"
    assert os.read(args.owner_release_fd, 1) == b""
    print("protected owner execution returned; inspect retained audit", flush=True)
    return 0
'''


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    monkeypatch.setattr(owner, "OWNER_UID", os.getuid())
    monkeypatch.setattr(owner, "OWNER_GID", os.getgid())
    monkeypatch.setattr(owner, "STOP_GRACE", .1)
    root = tmp_path / "fleet"
    (root / "scripts").mkdir(parents=True, mode=0o700)
    root.chmod(0o700)
    source = root / owner.TARGET
    deployment = tmp_path / "deployment.json"
    def configure(body=BENIGN, **updates):
        if source.exists(): source.chmod(0o600)
        source.write_text(body); source.chmod(0o400)
        value = {"preparation_wait_seconds": 10,
                 "launcher": {"fleet_root": str(root), "code_pins": {
                     owner.TARGET: hashlib.sha256(source.read_bytes()).hexdigest()}}}
        value.update(updates)
        deployment.write_text(json.dumps(value)); deployment.chmod(0o600)
        return hashlib.sha256(deployment.read_bytes()).hexdigest()
    executable = Path(sys.executable).resolve()
    digest = hashlib.sha256(executable.read_bytes()).hexdigest()
    # The test-tool venv has a shared writable ancestor and is intentionally NOT
    # a production-admitted interpreter path. Benign children need stdlib only.
    monkeypatch.setattr(owner.sys, "executable", str(executable))
    processes = []
    original = owner.subprocess.Popen
    def popen(*args, **kwargs):
        child = original(*args, **kwargs); processes.append((child, args, kwargs)); return child
    monkeypatch.setattr(owner.subprocess, "Popen", popen)
    return root, source, deployment, configure, digest, processes


def execute(prepared, body=BENIGN, *, seconds=5, **changes):
    _root, _source, deployment, configure, interpreter, _processes = prepared
    digest = configure(body, **changes)
    return owner.run(deployment, digest, interpreter, seconds)


def test_real_child_pipe_release_and_eof_no_cross_step_fd_or_ambient_credentials(prepared, monkeypatch):
    monkeypatch.setenv("PRIVATE_TEST_SHOULD_NOT_REACH_CHILD", "not-a-real-secret")
    body = BENIGN.replace("args = p.parse_args(argv)",
        'args = p.parse_args(argv)\n    assert "PRIVATE_TEST_SHOULD_NOT_REACH_CHILD" not in os.environ')
    assert execute(prepared, body) == owner.COMPLETE
    child, args, kwargs = prepared[-1][0]
    assert child.returncode == 0 and not Path(f"/proc/{child.pid}").exists()
    assert args[0][1:4] == ["-I", "-B", "-c"] and args[0][4] == owner.CHILD_CODE
    assert kwargs["start_new_session"] and kwargs["close_fds"]
    assert len(kwargs["pass_fds"]) == 1


@pytest.mark.parametrize("outcome", ["ready", "failure", "drift"])
def test_export_schedule_precedes_any_child_or_pipe(prepared, monkeypatch, outcome):
    observed = []
    actual_pipe = owner.os.pipe2
    monkeypatch.setattr(owner.os, "pipe2", lambda flags: observed.append("pipe") or actual_pipe(flags))
    def wait(value, root, deadline, check):
        check()
        assert not prepared[-1] and not observed
        observed.append("export")
        if outcome == "failure":
            raise RuntimeError("PUBLIC synthetic scheduling failure")
        if outcome == "drift":
            prepared[2].write_bytes(b"PUBLIC drift")
        check()
    monkeypatch.setattr(owner, "_wait_for_export", wait)
    if outcome == "ready":
        assert execute(prepared, startup_barrier={"publisher_id": 123}) == owner.COMPLETE
        assert observed[0:2] == ["export", "pipe"] and len(prepared[-1]) == 1
    else:
        with pytest.raises(owner.SupervisorError): execute(prepared, startup_barrier={"publisher_id": 123})
        assert observed == ["export"] and not prepared[-1]


@pytest.mark.parametrize("different_digest", [False, True])
def test_export_observation_still_requires_live_binder(prepared, monkeypatch, different_digest):
    from dataclasses import asdict, replace
    from scripts import android_startup_scheduling as startup
    from scripts import android_workflow_job_binder as binder
    import test_android_workflow_identity as fixtures
    policies = {name: replace(fixtures.policy.__wrapped__(), check_run_id=str(900 + index),
        environment="android-preview12-release-builder" if name == "protected" else name)
        for index, name in enumerate(binder.ROLES)}
    value = {"startup_barrier": {"publisher_id": 123}, "preparation_wait_seconds": 10,
        "launcher": {"code_pins": {}}, "job_policy": asdict(policies["protected"]),
        "role_binding": {"job_names": {name: name for name in binder.ROLES},
                         "templates": {name: asdict(policy) for name, policy in policies.items()}}}
    order = []
    # Interpreter/source admission is modeled here, tested separately below.
    monkeypatch.setattr(owner, "_fleet_imports", lambda *_: None)
    def wait(*args, **kwargs):
        order.append("export")
        return "0" * 64 if different_digest else startup.binding_digest(policies)
    def bind(**kwargs):
        assert order == ["export"] and kwargs["role"] == "protected"
        order.append("binder")
        return policies
    monkeypatch.setattr(startup, "wait_for_stage", wait)
    monkeypatch.setattr(binder, "bind_deployment_roles", bind)
    if different_digest:
        with pytest.raises(owner.SupervisorError): owner._wait_for_export(value, prepared[0], 100, lambda: None)
    else:
        owner._wait_for_export(value, prepared[0], 100, lambda: None)
    assert order == ["export", "binder"]


def test_ambient_startup_namespace_rejected_before_import(prepared):
    # Test process imports real Fleet; the independent descriptor names a
    # different synthetic root. Never import real code on that descriptor.
    pins = {name: "a" * 64 for name in ("scripts/android_startup_scheduling.py", "scripts/android_workflow_job_binder.py")}
    with pytest.raises(owner.SupervisorError): owner._fleet_imports(prepared[0], pins)
    assert not prepared[-1]


@pytest.mark.parametrize("module_absent", [False, True])
@pytest.mark.parametrize("name", ["android_startup_scheduling", "android_workflow_job_binder", "android_artifact_origin"])
def test_parent_package_cannot_override_admitted_startup_module(monkeypatch, module_absent, name):
    from scripts import android_startup_scheduling as startup
    root = Path(owner.__file__).resolve().parents[1]
    pins = {str(Path(module.__file__).relative_to(root)): "a" * 64
            for name, module in tuple(sys.modules.items())
            if (name == "scripts" or name.startswith("scripts."))
            and getattr(module, "__file__", None) and Path(module.__file__).is_relative_to(root)}
    monkeypatch.setattr(sys.modules["scripts"], name, object())
    assert sys.modules["scripts.android_startup_scheduling"] is startup
    if module_absent:
        monkeypatch.delitem(sys.modules, "scripts." + name)
    with pytest.raises(owner.SupervisorError): owner._fleet_imports(root, pins)


def test_cold_isolated_module_invocation_admits_only_exact_namespace():
    import subprocess
    root = Path(owner.__file__).resolve().parents[1]
    code = '''import sys
from pathlib import Path
root = Path(sys.argv[1])
sys.path.insert(0, str(root))
from scripts import android_protected_job_supervisor as owner
names = ("android_startup_scheduling", "android_workflow_job_binder")
assert all("scripts." + name not in sys.modules for name in names)
pins = {"scripts/" + name + ".py": "a" * 64 for name in names}
pins["scripts/android_protected_job_supervisor.py"] = "a" * 64
import scripts
if getattr(scripts, "__file__", None): pins["scripts/__init__.py"] = "a" * 64
owner._fleet_imports(root, pins)
print("exact namespace admitted before lazy imports")
'''
    result = subprocess.run([sys.executable, "-I", "-B", "-c", code, str(root)],
        capture_output=True, timeout=10, env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"})
    assert result.returncode == 0 and result.stderr == b""
    assert result.stdout == b"exact namespace admitted before lazy imports\n"


@pytest.mark.parametrize("body", [
    BENIGN.replace('print("protected owner prepared; awaiting owner release", flush=True)', 'return 0'),
    BENIGN.replace('print("protected owner prepared; awaiting owner release", flush=True)', 'print("unknown PRIVATE_TEST", flush=True)'),
    BENIGN.replace('print("protected owner execution returned; inspect retained audit", flush=True)', 'print("protected owner prepared; awaiting owner release", flush=True)'),
    BENIGN.replace('return 0', 'return 17'),
    BENIGN.replace('print("protected owner execution returned; inspect retained audit", flush=True)', 'print("PRIVATE_TEST", file=sys.stderr, flush=True)'),
    BENIGN.replace('print("protected owner prepared; awaiting owner release", flush=True)', 'print("x" * 5000, flush=True)'),
    BENIGN.replace('print("protected owner execution returned; inspect retained audit", flush=True)', 'print("protected owner execution returned; inspect retained audit", end="", flush=True)'),
    BENIGN.replace('print("protected owner prepared; awaiting owner release", flush=True)', 'print("protected owner execution returned; inspect retained audit", flush=True)'),
])
def test_bad_child_output_and_status_fail_closed_redacted_no_retry(prepared, body):
    with pytest.raises(owner.SupervisorError, match="^" + owner.ERROR + "$"):
        execute(prepared, body)
    assert len(prepared[-1]) == 1
    assert prepared[-1][0][0].returncode is not None


@pytest.mark.parametrize("position", ["before", "after"])
def test_whole_child_deadline_terminates_original_group(prepared, position):
    marker = 'print("protected owner prepared; awaiting owner release", flush=True)' if position == "before" else 'print("protected owner execution returned; inspect retained audit", flush=True)'
    body = BENIGN.replace(marker, "time.sleep(30)\n    " + marker)
    with pytest.raises(owner.SupervisorError): execute(prepared, body, seconds=1)
    child = prepared[-1][0][0]
    assert child.returncode < 0 and not Path(f"/proc/{child.pid}").exists()


@pytest.mark.parametrize("value", [0, -1, True, "10", 1801, None])
def test_pending_opt_in_required_before_spawn(prepared, value):
    with pytest.raises(owner.SupervisorError): execute(prepared, preparation_wait_seconds=value)
    assert prepared[-1] == []


@pytest.mark.parametrize("attack", ["config-pin", "code-pin", "interpreter-pin", "symlink", "mode", "unlisted-import",
                                    "lazy-binder-import", "cache", "duplicate-key"])
def test_program_and_configuration_admission_before_spawn(prepared, attack):
    root, source, deployment, configure, interpreter, processes = prepared
    digest = configure()
    if attack == "config-pin": digest = "0" * 64
    elif attack == "code-pin": source.chmod(0o600); source.write_text(BENIGN + "\n# drift\n")
    elif attack == "interpreter-pin": interpreter = "0" * 64
    elif attack == "symlink":
        target = source.with_suffix(".original"); source.rename(target); source.symlink_to(target)
    elif attack == "mode": deployment.chmod(0o666)
    elif attack == "unlisted-import": digest = configure("from scripts import unadmitted\n" + BENIGN)
    elif attack == "lazy-binder-import": digest = configure(
        BENIGN + "\n\ndef dormant():\n    from scripts import android_workflow_job_binder\n")
    elif attack == "cache": (source.parent / "__pycache__").mkdir()
    else:
        deployment.write_text('{"preparation_wait_seconds":1,"preparation_wait_seconds":2}')
        digest = hashlib.sha256(deployment.read_bytes()).hexdigest()
    with pytest.raises(owner.SupervisorError): owner.run(deployment, digest, interpreter, 5)
    assert processes == []


def test_pre_release_drift_stops_child_and_does_not_write_byte(prepared, monkeypatch):
    original = owner._Pin.recheck
    def changed(item):
        original(item)
        if prepared[-1]: raise OSError("PRIVATE_TEST drift")
    monkeypatch.setattr(owner._Pin, "recheck", changed)
    with pytest.raises(owner.SupervisorError, match="^" + owner.ERROR + "$"): execute(prepared)
    assert prepared[-1][0][0].returncode < 0


def test_short_pipe_write_is_terminal(prepared, monkeypatch):
    monkeypatch.setattr(owner.os, "write", lambda *_: 0)
    with pytest.raises(owner.SupervisorError): execute(prepared)
    assert len(prepared[-1]) == 1 and prepared[-1][0][0].returncode < 0


def test_pid_identity_mismatch_never_signals_foreign_group(monkeypatch):
    class Child: pid = 123
    monkeypatch.setattr(owner, "_process_stamp", lambda _: (123, 2))
    monkeypatch.setattr(owner.os, "killpg", lambda *_: pytest.fail("foreign group signal"))
    with pytest.raises(owner.SupervisorError): owner._stop(Child(), (123, 1), 456)


def test_fragmented_exact_markers_are_accepted(prepared):
    body = BENIGN.replace('print("protected owner prepared; awaiting owner release", flush=True)',
        '[(os.write(1, bytes([b])), time.sleep(.001)) for b in b"protected owner prepared; awaiting owner release\\n"]')
    assert execute(prepared, body) == owner.COMPLETE


def test_successful_leader_exit_still_stops_its_original_remaining_group(prepared, monkeypatch):
    body = BENIGN.replace('args = p.parse_args(argv)', '''args = p.parse_args(argv)
    from pathlib import Path
    kid = os.fork()
    if kid == 0:
        os.close(1); os.close(2); time.sleep(30); os._exit(0)
    Path(args.deployment + ".child").write_text(str(kid))''')
    original, checked = owner._stop, []
    def stopped(child, stamp, pidfd):
        # Observe only the descendant explicitly created by this benign fixture.
        descendant = int(Path(str(prepared[2]) + ".child").read_text())
        fd = os.pidfd_open(descendant)
        try:
            original(child, stamp, pidfd)
            assert select.select([fd], [], [], 1)[0] == [fd]
            checked.append(True)
        finally:
            os.close(fd)
    monkeypatch.setattr(owner, "_stop", stopped)
    assert execute(prepared, body) == owner.COMPLETE and checked == [True]


def test_signal_requests_bounded_cleanup_and_restores_handler(prepared):
    previous = signal.getsignal(signal.SIGTERM)
    body = BENIGN.replace('args = p.parse_args(argv)',
        'args = p.parse_args(argv)\n    os.kill(os.getppid(), 15)\n    time.sleep(30)')
    with pytest.raises(owner.SupervisorError): execute(prepared, body)
    assert prepared[-1][0][0].returncode < 0
    assert signal.getsignal(signal.SIGTERM) == previous


@pytest.mark.parametrize("number", [signal.SIGTERM, signal.SIGINT])
def test_signal_during_spawn_ownership_transfer_still_reaps_child_without_release(prepared, monkeypatch, number):
    original_spawn, original_write = owner.subprocess.Popen, os.write
    writes = []
    previous = signal.getsignal(number)
    def interrupted_spawn(*args, **kwargs):
        child = original_spawn(*args, **kwargs)
        # Real fork/exec already happened; owner.run has not received its Popen.
        os.kill(os.getpid(), number)
        return child
    def written(fd, raw):
        writes.append(raw)
        return original_write(fd, raw)
    monkeypatch.setattr(owner.subprocess, "Popen", interrupted_spawn)
    monkeypatch.setattr(owner.os, "write", written)
    with pytest.raises(owner.SupervisorError, match="^" + owner.ERROR + "$"): execute(prepared)
    child = prepared[-1][0][0]
    assert child.returncode < 0 and not Path(f"/proc/{child.pid}").exists() and writes == []
    assert signal.getsignal(number) == previous and len(prepared[-1]) == 1


def test_cli_never_echoes_raw_input_or_traceback(capsys):
    assert owner.main(["--unknown", "PRIVATE_TEST"]) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == owner.ERROR + "\n"
