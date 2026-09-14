"""Explicit source-bound integration lane: never discovered by default pytest.

Run with CHUMMER_ANDROID_RELEASE_TEST_RUNNER_ROOT set to reviewed Android source.
No SDK/build/pip/container/signing operations; real tiny Git/data captures only.
"""
import hashlib
import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import android_preview12_external_rebuilder as fleet
import test_android_preview12_external_rebuilder as fixture
from test_android_preview12_external_rebuilder import protected_file
from test_android_preview12_rebuild_input_boundaries import ready_lock, entry_arguments


def _tiny_git(root, repository):
    fleet._offline_git(["init", "--quiet", "--template=", str(root)], timeout=30)
    fleet._offline_git(["-C", str(root), "remote", "add", "origin", repository], timeout=30)


def _tiny_commit(root):
    fleet._offline_git(["-C", str(root), "add", "."], timeout=30)
    fleet._offline_git(["-C", str(root), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                       "commit", "--quiet", "-m", "source-only fixture"], timeout=30)
    return fleet._offline_git(["-C", str(root), "rev-parse", "HEAD"], timeout=30)


@pytest.fixture
def offline_source_case(tmp_path):
    """Actual reviewed Android capture code; inert data, no pip/build/container.

    The explicit-source lane is mandatory for reviewing this integration. It is
    separate from portable Fleet tests; never discover a sibling automatically.
    """
    configured_root = os.environ.get("CHUMMER_ANDROID_RELEASE_TEST_RUNNER_ROOT")
    if not configured_root:
        pytest.fail("explicit reviewed Android source required for exact capture integration")
    reviewed = Path(configured_root)
    workspace = tmp_path / "workspace"
    workspace.mkdir(mode=0o700)
    android, oracle = workspace / "chummer-android", tmp_path / "oracle-input"
    android.mkdir(mode=0o700)
    oracle.mkdir(mode=0o700)
    _tiny_git(oracle, fleet.TEST_ORACLE_REPOSITORY)
    for relative in ("Chummer", "Plugins/ChummerHub.Client/UI", "Translator", "CrashHandler", "ChummerDataViewer"):
        directory = oracle / relative
        directory.mkdir(parents=True, mode=0o700)
        protected_file(directory / "fixture.txt", b"source-test oracle\n")
    oracle_commit = _tiny_commit(oracle)
    _tiny_git(android, fleet.REPOSITORIES["chummer-android"][2])
    for relative in ("scripts/build-release.sh", "scripts/run_release_source_tests.py"):
        destination = android / relative
        destination.parent.mkdir(exist_ok=True, mode=0o700)
        protected_file(destination, (reviewed / relative).read_bytes())
    bootstrap, wheels = tmp_path / "bootstrap-input", tmp_path / "wheel-input"
    bootstrap.mkdir(mode=0o700)
    wheels.mkdir(mode=0o700)
    bootstrap_lock = json.loads((reviewed / "eng/release-test-bootstrap.lock.json").read_bytes())
    for row in bootstrap_lock["artifacts"]:
        raw = ("inert fixture: " + row["fileName"]).encode()
        protected_file(bootstrap / row["fileName"], raw)
        row.update(sizeBytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    requirements = []
    for index in range(11):
        raw = f"inert wheel {index}".encode()
        protected_file(wheels / f"test{index}-1.0-py3-none-any.whl", raw)
        requirements.append(f"test{index}==1.0 --hash=sha256:{hashlib.sha256(raw).hexdigest()}")
    for relative, raw in {
        "eng/release-test-bootstrap.lock.json": json.dumps(bootstrap_lock).encode(),
        "tests/requirements-ci.txt": ("\n".join(requirements) + "\n").encode(),
        ".github/workflows/api36-editing-e2e.yml":
            f"repository: ArchonMegalon/chummer5a\n  ref: {oracle_commit}\n".encode(),
    }.items():
        destination = android / relative
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        protected_file(destination, raw)
    commit = _tiny_commit(android)
    lock = ready_lock()
    lock["android_authority"].update(commit=commit)
    digest = hashlib.sha256((android / "scripts/build-release.sh").read_bytes()).hexdigest()
    assert fleet.RELEASE_TEST_CONSUMERS[digest] == hashlib.sha256((android / "scripts/run_release_source_tests.py").read_bytes()).hexdigest()
    lock["android_authority"]["build_script"]["sha256"] = digest
    scratch = tmp_path / "scratch"
    scratch.mkdir(mode=0o700)
    return SimpleNamespace(lock=lock, workspace=workspace, android=android, bootstrap=bootstrap,
                           wheels=wheels, oracle=oracle, scratch=scratch, commit=oracle_commit)


@pytest.mark.parametrize("failure", [False, True])
@pytest.mark.parametrize("packed", [False, True])
def test_actual_source_capture_stages_only_test_data_and_cleans_on_exit(offline_source_case, failure, packed):
    case = offline_source_case
    if packed:
        fleet._offline_git(["-C", str(case.oracle), "repack", "-ad"], timeout=30)
    context = fleet._staged_release_test_inputs(case.lock, case.workspace, case.scratch,
                                               case.bootstrap, case.wheels, case.oracle)
    def exercise():
        with context as environment:
            assert set(environment) == {"CHUMMER_ANDROID_RELEASE_TEST_BOOTSTRAP_DIR", "CHUMMER_ANDROID_RELEASE_TEST_WHEELHOUSE"}
            staged = case.workspace / "chummer5a"
            assert fleet._offline_git(["-C", str(staged), "rev-parse", "HEAD"], timeout=30) == case.commit
            assert (staged / ".git").is_dir() and not (staged / ".git").is_symlink()
            assert not (staged / ".git/objects/info/packs").exists()
            assert len(list(Path(environment["CHUMMER_ANDROID_RELEASE_TEST_WHEELHOUSE"]).iterdir())) == 11
            assert set(fleet.REPOSITORIES) == set(fleet.REVISION_VARIABLES)
            if failure:
                raise RuntimeError("modeled child failure")
    if failure:
        with pytest.raises(RuntimeError, match="modeled child"):
            exercise()
    else:
        exercise()
    assert not (case.workspace / "chummer5a").exists()
    assert list(case.scratch.iterdir()) == []
    assert (case.oracle / "Chummer/fixture.txt").read_bytes() == b"source-test oracle\n"


def test_test_snapshot_cleanup_is_attempted_even_when_oracle_cleanup_raises(offline_source_case, monkeypatch):
    case = offline_source_case
    remove = fleet._remove_owned_directory
    calls = []
    def cleanup(path, identity):
        calls.append(path)
        remove(path, identity)
        if path == case.workspace / "chummer5a":
            raise fleet.RebuilderError("modeled cleanup failure")
    monkeypatch.setattr(fleet, "_remove_owned_directory", cleanup)
    with pytest.raises(fleet.RebuilderError, match="modeled cleanup"):
        with fleet._staged_release_test_inputs(case.lock, case.workspace, case.scratch,
                                               case.bootstrap, case.wheels, case.oracle):
            pass
    assert len(calls) == 2 and calls[0] == case.workspace / "chummer5a"
    assert list(case.scratch.iterdir()) == []


def test_partial_object_copy_is_cleaned_and_never_reaches_child(offline_source_case, monkeypatch):
    case = offline_source_case
    copy = fleet._copy_offline_input
    def interrupted(*args):
        copy(*args)
        raise fleet.RebuilderError("modeled interrupted object copy")
    monkeypatch.setattr(fleet, "_copy_offline_input", interrupted)
    with pytest.raises(fleet.RebuilderError, match="interrupted object copy"):
        with fleet._staged_release_test_inputs(case.lock, case.workspace, case.scratch,
                                               case.bootstrap, case.wheels, case.oracle):
            pytest.fail("incomplete oracle reached child")
    assert not (case.workspace / "chummer5a").exists()
    assert list(case.scratch.iterdir()) == []


def test_yielded_build_timeout_keeps_its_category_and_still_cleans(offline_source_case):
    case = offline_source_case
    timeout = subprocess.TimeoutExpired(["modeled-build"], 30)
    with pytest.raises(subprocess.TimeoutExpired) as failure:
        with fleet._staged_release_test_inputs(case.lock, case.workspace, case.scratch,
                                               case.bootstrap, case.wheels, case.oracle):
            raise timeout
    assert failure.value is timeout
    assert list(case.scratch.iterdir()) == []
    assert not (case.workspace / "chummer5a").exists()


@pytest.mark.parametrize("attack", ["wheel", "missing-wheel", "extra-bootstrap", "fifo", "helper", "workflow", "requirements",
                                     "oracle-symlink", "object-symlink", "hardlink", "config", "alternate", "gitfile",
                                     "dirty", "assume-unchanged", "wrong-head", "unreachable-loose", "unreachable-packed",
                                     "unknown-object-info"])
def test_actual_release_test_input_attacks_fail_before_child(offline_source_case, attack):
    case = offline_source_case
    if attack == "wheel":
        next(case.wheels.iterdir()).write_bytes(b"changed")
    elif attack == "missing-wheel":
        next(case.wheels.iterdir()).unlink()
    elif attack == "extra-bootstrap":
        (case.bootstrap / "extra").write_bytes(b"extra")
    elif attack == "fifo":
        target = case.bootstrap / "get-pip.py"
        target.unlink()
        os.mkfifo(target)
    elif attack in {"helper", "workflow", "requirements"}:
        relative = {"helper": "scripts/run_release_source_tests.py", "workflow": ".github/workflows/api36-editing-e2e.yml",
                    "requirements": "tests/requirements-ci.txt"}[attack]
        target = case.android / relative
        target.write_bytes(target.read_bytes() + b"\n# drift\n")
    elif attack in {"oracle-symlink", "object-symlink"}:
        target = case.oracle / ("Chummer/fixture.txt" if attack == "oracle-symlink" else ".git/objects/link")
        if target.exists():
            target.unlink()
        target.symlink_to(case.bootstrap / "get-pip.py")
    elif attack == "hardlink":
        os.link(case.oracle / "Chummer/fixture.txt", case.oracle / "extra")
    elif attack == "config":
        with (case.oracle / ".git/config").open("a") as output:
            output.write("\n[core]\n hooksPath = /arbitrary\n")
    elif attack == "alternate":
        directory = case.oracle / ".git/objects/info"
        directory.mkdir(exist_ok=True)
        (directory / "alternates").write_text("/arbitrary\n")
    elif attack == "unknown-object-info":
        directory = case.oracle / ".git/objects/info"
        directory.mkdir(exist_ok=True)
        (directory / "unrelated-metadata").write_text("never copied or trusted\n")
    elif attack == "gitfile":
        (case.oracle / ".git").rename(case.oracle / "git-original")
        (case.oracle / ".git").write_text("gitdir: /arbitrary\n")
    elif attack in {"dirty", "assume-unchanged"}:
        if attack == "assume-unchanged":
            fleet._offline_git(["-C", str(case.oracle), "update-index", "--assume-unchanged", "Chummer/fixture.txt"], timeout=30)
        (case.oracle / "Chummer/fixture.txt").write_bytes(b"changed")
    elif attack.startswith("unreachable-"):
        extra = case.scratch / "unrelated-source.txt"
        protected_file(extra, b"unrelated object must not enter the build")
        blob = fleet._offline_git(["-C", str(case.oracle), "hash-object", "-w", str(extra)], timeout=30)
        extra.unlink()
        if attack == "unreachable-packed":
            fleet._offline_git(["-C", str(case.oracle), "update-ref", "refs/test/unrelated", blob], timeout=30)
            fleet._offline_git(["-C", str(case.oracle), "repack", "-ad"], timeout=30)
            fleet._offline_git(["-C", str(case.oracle), "update-ref", "-d", "refs/test/unrelated"], timeout=30)
    else:
        (case.oracle / "Chummer/fixture.txt").write_bytes(b"different committed source")
        _tiny_commit(case.oracle)
    with pytest.raises(fleet.RebuilderError):
        with fleet._staged_release_test_inputs(case.lock, case.workspace, case.scratch,
                                               case.bootstrap, case.wheels, case.oracle):
            pytest.fail("unsafe inputs reached child boundary")
    assert list(case.scratch.iterdir()) == []
    assert not (case.workspace / "chummer5a").exists()


def test_default_preserved_git_authority_still_rejects_oracle(offline_source_case):
    with pytest.raises(fleet.RebuilderError, match="helper-free"):
        fleet._preserved_git_storage(offline_source_case.oracle)


@pytest.mark.parametrize("failure", [False, True])
def test_actual_new_inputs_reach_clean_child_environment_only(offline_source_case, tmp_path, monkeypatch, failure):
    case = offline_source_case
    owner = tmp_path / "authority/feed"
    owner.mkdir(parents=True)
    args = entry_arguments(fleet, tmp_path, owner.parent, owner, "direct")
    args.update(lock=case.lock, workspace=case.workspace, test_bootstrap_dir=case.bootstrap,
                test_wheelhouse=case.wheels, test_oracle_root=case.oracle)
    for name in ("two_green_receipt", "approval", "java_tool_observation", "installed_closure_receipt"):
        protected_file(args[name], b'{"TEST_ONLY":true}\n')
    protected_file(tmp_path / "producer-source-graph.json", json.dumps(fixture.graph(fleet)).encode())
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "must-not-propagate")
    monkeypatch.setenv("PYTHONPATH", "/must-not-propagate")
    calls = []
    def child(command, **options):
        calls.append(command)
        environment = options["env"]
        assert "AWS_SECRET_ACCESS_KEY" not in environment and "PYTHONPATH" not in environment
        assert environment["CHUMMER_DOTNET"] == str(args["dotnet_root"] / "dotnet")
        assert Path(environment["CHUMMER_ANDROID_RELEASE_TEST_WHEELHOUSE"]).is_relative_to(args["build_input_root"])
        assert (case.workspace / "chummer5a/Chummer/fixture.txt").is_file()
        if failure:
            raise RuntimeError("modeled build failure")
        artifacts = args["build_input_root"] / "artifacts"
        artifacts.mkdir(mode=0o700)
        protected_file(artifacts / f"chummer-android-{fleet.VERSION_NAME}-unsigned.aab", b"fixture-not-an-aab")
        protected_file(artifacts / f"chummer-android-{fleet.VERSION_NAME}-source-graph.json", b"{}")
        return SimpleNamespace(returncode=3)
    if failure:
        with pytest.raises(RuntimeError, match="modeled build failure"):
            fleet._run_independent_rebuild(**args, runner=child)
    else:
        fleet._run_independent_rebuild(**args, runner=child)
    assert len(calls) == 1
    assert not (case.workspace / "chummer5a").exists()
    assert not list(args["build_input_root"].glob(".release-test-inputs-*"))
