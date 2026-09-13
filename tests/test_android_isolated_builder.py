"""Unit lifecycle models, not Docker execution or artifact-emission proof.

Real private journal files and executable pins; modeled daemon, CLI and runtime
observations. No test calls Docker, reads credentials or constructs authority.
"""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import android_artifact_origin as origin
from scripts import android_container_runtime as runtime
from scripts import android_isolated_builder as builder


CID = "c" * 64
IMAGE = "sha256:" + "a" * 64
REFERENCE = "registry.example/fleet/builder@sha256:" + "b" * 64
DAEMON = (10, 20, 30)


@pytest.fixture
def model(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    binary = tmp_path / "docker"
    binary.write_bytes(b"unit model only; never executed\n")
    binary.chmod(0o700)
    pin = origin.PinnedFile(binary, hashlib.sha256(binary.read_bytes()).hexdigest())
    output = tmp_path / "output"
    output.mkdir(mode=0o700)
    policy = runtime.RuntimePolicy(
        IMAGE, REFERENCE, "65534:65534", "/", ("/bin/sh",), ("-c", "exit 0"),
        ("PATH=/usr/bin:/bin",), runtime.ResourceLimits(64 * 1024**2, 250000000, 32),
        binds=(runtime.BindMount(str(output), "/output", False),), maximum_runtime_seconds=60,
    )
    operation = tmp_path / "operation"
    calls = []
    value = SimpleNamespace(policy=policy, pin=pin, operation=operation, calls=calls,
                            fail=None, wrong=None, after=None, binary=binary)
    monkeypatch.setattr(runtime, "_socket_identity", lambda: DAEMON)

    def observation(phase):
        return runtime.RuntimeObservation(CID, IMAGE, "d"*64, "e"*64, "f"*64, phase,
            "2026-09-13T00:00:00Z", "2026-09-13T00:00:01Z", "2026-09-13T00:00:02Z",
            "2026-09-13T00:00:03Z", DAEMON + (123,), "9"*64)

    def created(cid, selected):
        calls.append(("observe-created", cid))
        assert cid == CID and selected is value.policy
        assert json.loads((operation / "container.json").read_bytes())["containerId"] == CID
        if value.fail == "observe-created":
            raise runtime.RuntimeObservationError("PRIVATE diagnostic")
        return observation("created")

    def exited(cid, selected, initial):
        calls.append(("observe-exited", cid))
        assert initial.phase == "created" and selected is value.policy and cid == CID
        if value.fail == "observe-exited":
            raise runtime.RuntimeObservationError("PRIVATE diagnostic")
        return observation("exited")

    def execute(command, directory, timeout, stdout_limit, stderr_limit):
        assert command[:5] == [str(binary), "--config", str(operation / "docker-config"),
                               "--host", "unix:///run/docker.sock"]
        assert directory == operation and (stdout_limit, stderr_limit) == (4096, 65536)
        action = command[5]
        calls.append((action, command[6:]))
        assert (operation / "intent.json").is_file()
        if action == "start":
            assert (operation / "container.json").is_file() and (operation / "created.json").is_file()
        if action == value.fail:
            raise origin.OriginError("PRIVATE diagnostic")
        if value.after is not None:
            value.after(action)
        if action == value.wrong:
            return b"unexpected\n"
        return b"0\n" if action == "wait" else (CID + "\n").encode()

    monkeypatch.setattr(runtime, "observe_created", created)
    monkeypatch.setattr(runtime, "observe_exited", exited)
    monkeypatch.setattr(origin, "_run", execute)
    return value


def run(model):
    return builder.run_builder(model.policy, model.pin, model.operation)


def test_actual_private_journal_orders_one_create_start_wait_and_removal(model):
    result = run(model)
    assert [name for name, _ in model.calls] == [
        "create", "observe-created", "start", "wait", "observe-exited", "rm"]
    assert type(result) is builder.BuilderExecution and result.container_removed
    assert result.created.phase == "created" and result.exited.phase == "exited"
    complete = json.loads((model.operation / "complete.json").read_bytes())
    assert complete["containerRemoved"] and not complete["artifactCapturePerformed"]
    assert not complete["signingPerformed"] and not hasattr(result, "provenance")
    assert model.operation.stat().st_mode & 0o777 == 0o700
    for path in model.operation.iterdir():
        if path.is_file():
            assert path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(builder.BuilderExecutionError, match="admission"):
        run(model)
    assert sum(name == "create" for name, _ in model.calls) == 1


def test_create_options_are_exact_no_shell_and_no_implicit_pull(model):
    model.policy = replace(model.policy, command=("-c", "printf '%s' '$PRIVATE; not-host-shell'"),
        labels=(("test", "two words;not-shell"),),
        tmpfs=(runtime.TmpfsMount("/temporary", "rw,noexec,nosuid,nodev,size=1048576,mode=1777"),))
    run(model)
    args = model.calls[0][1]
    for key, expected in (("--pull", "never"), ("--network", "none"), ("--user", "65534:65534"),
        ("--cap-drop", "ALL"), ("--security-opt", "no-new-privileges"), ("--log-driver", "none"),
        ("--cpus", "0.250000000"), ("--memory", "67108864"), ("--memory-swap", "67108864")):
        assert args[args.index(key) + 1] == expected
    assert args[-3:] == [REFERENCE, *model.policy.command]
    assert "--read-only" in args and "--privileged" not in args and "--rm" not in args
    assert args[args.index("--label") + 1] == "test=two words;not-shell"


@pytest.mark.parametrize("stage", ["create", "observe-created", "start", "wait", "observe-exited", "rm"])
def test_failures_never_replay_create_start_or_claim_completion(model, stage):
    model.fail = stage
    with pytest.raises(builder.BuilderExecutionError) as caught:
        run(model)
    assert "PRIVATE" not in str(caught.value)
    assert not (model.operation / "complete.json").exists()
    failed = json.loads((model.operation / "failed.json").read_bytes())
    assert failed["stage"] == ("remove" if stage == "rm" else stage)
    assert "PRIVATE" not in json.dumps(failed)
    assert not failed["signingPerformed"] and not failed["artifactCapturePerformed"]
    names = [name for name, _ in model.calls]
    assert names.count("create") == 1 and names.count("start") <= 1
    if stage == "create":
        assert failed["containerId"] is None and "stop" not in names
    elif stage == "rm":
        assert names.count("rm") == 1 and "stop" not in names
    else:
        assert names.count("stop") == names.count("rm") == 1
    with pytest.raises(builder.BuilderExecutionError):
        run(model)
    assert [name for name, _ in model.calls] == names


@pytest.mark.parametrize("stage", ["create", "start", "wait", "rm"])
def test_malformed_acknowledgement_is_not_success_or_permission_to_retry(model, stage):
    model.wrong = stage
    with pytest.raises(builder.BuilderExecutionError):
        run(model)
    assert not (model.operation / "complete.json").exists()
    assert sum(name == stage for name, _ in model.calls) == 1


@pytest.mark.parametrize("bad", ["signer", "multi-entrypoint", "detached-output", "overlap", "missing-bind", "bad-pin"])
def test_admission_rejects_before_operation_or_docker_mutation(model, bad):
    if bad == "signer":
        model.policy = replace(model.policy, process_role="signer", user="0:0")
    elif bad == "multi-entrypoint":
        model.policy = replace(model.policy, entrypoint=("/bin/sh", "-e"))
    elif bad == "detached-output":
        model.policy = replace(model.policy, attach_stdout=False, attach_stderr=False)
    elif bad == "overlap":
        model.policy = replace(model.policy, binds=(runtime.BindMount(str(model.operation.parent), "/input", True),))
    elif bad == "missing-bind":
        model.policy = replace(model.policy, binds=(runtime.BindMount(str(model.operation.parent / "missing"), "/input", True),))
    else:
        model.pin = replace(model.pin, sha256="0"*64)
    with pytest.raises(builder.BuilderExecutionError):
        run(model)
    assert model.calls == [] and not model.operation.exists()


@pytest.mark.parametrize("stdout,stderr", [(True, False), (False, True), (True, True)])
def test_each_supported_attachment_policy_has_an_explicit_cli_representation(model, stdout, stderr):
    model.policy = replace(model.policy, attach_stdout=stdout, attach_stderr=stderr)
    run(model)
    args = model.calls[0][1]
    actual = [args[index + 1] for index, item in enumerate(args) if item == "--attach"]
    assert actual == [name for enabled, name in ((stdout, "stdout"), (stderr, "stderr")) if enabled]


@pytest.mark.parametrize("when", ["create", "start", "wait", "rm"])
def test_changed_cli_pin_fails_closed_and_is_not_used_for_cleanup(model, when):
    def change(action):
        if action == when:
            model.binary.write_bytes(b"replacement; must never execute\n")
    model.after = change
    with pytest.raises(builder.BuilderExecutionError):
        run(model)
    assert not (model.operation / "complete.json").exists()
    names = [name for name, _ in model.calls]
    assert names[-1] == when and "stop" not in names


def test_existing_operation_symlink_is_not_followed_or_replaced(model):
    other = model.operation.parent / "other"
    other.mkdir()
    model.operation.symlink_to(other, target_is_directory=True)
    with pytest.raises(builder.BuilderExecutionError):
        run(model)
    assert model.calls == [] and model.operation.is_symlink() and list(other.iterdir()) == []


def test_candidate_changed_output_mode_cannot_veto_own_container_cleanup(model):
    output = Path(model.policy.binds[0].source)
    def change(action):
        if action == "start":
            output.chmod(0o755)
    model.after = change
    with pytest.raises(builder.BuilderExecutionError):
        run(model)
    names = [name for name, _ in model.calls]
    assert names == ["create", "observe-created", "start", "stop", "rm"]
    failed = json.loads((model.operation / "failed.json").read_bytes())
    assert failed["cleanup"] == "stopped-and-removed" and failed["stage"] == "start"
    assert not (model.operation / "complete.json").exists()
