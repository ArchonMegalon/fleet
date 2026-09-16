"""Real subprocess/cwd/fences with a test-only Android CLI double, never an SDK.

The double models --info including global.json's absolute pathname. Production
must use the hash-qualified Android observe/verify CLI; no production digest is
synthesized, and these tests establish no installed-tool or build admission.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from scripts import android_preview12_external_rebuilder as fleet
from test_android_preview12_external_rebuilder import protected_file
import test_android_preview12_rebuild_input_boundaries as boundaries


def info_digest(root):
    return hashlib.sha256(f"global.json file: {root}/global.json\n".encode()).hexdigest()


@pytest.fixture
def context(tmp_path, monkeypatch):
    android = tmp_path / "random-stage/workspace/chummer-android"
    android.mkdir(parents=True, mode=0o700)
    (android / "scripts").mkdir()
    protected_file(android / "global.json", b'{"sdk":{"version":"10.0.110"}}')
    java, dotnet = tmp_path / "jdk", tmp_path / "dotnet"
    claim = {
        "authorityClass": "non_authoritative_local_unsigned_preparation",
        "javaSdkRoot": str(java), "javaVersionOutputSha256": "a" * 64,
        "javaSdkTreeSha256": "b" * 64, "javaSdkTreeFileCount": 1, "javaSdkTreeSizeBytes": 20,
        "dotnetSdkTreeSha256": "c" * 64, "dotnetSdkTreeFileCount": 2, "dotnetSdkTreeSizeBytes": 30,
        "dotnet": {"absolutePath": str(dotnet / "dotnet"), "sha256": "d" * 64,
                   "sizeBytes": 10, "versionOutputSha256": info_digest(tmp_path / "old-cwd")},
        "tools": {"java": {"relativePath": "bin/java", "sha256": "e" * 64, "sizeBytes": 20}},
        "signingAuthorized": False, "publicationAuthorized": False, "androidSdkBound": False,
        "externalSignerMustBindFullJdkDotnetAndroidSdkClosure": True,
    }
    helper = android / "scripts/sign_android_release_build_attestation.py"
    # Executed with the production argv/environment; SDK output is explicitly modeled.
    script = '''import hashlib, json, os, sys
from pathlib import Path
SEED = SEED_VALUE
action = sys.argv[1]
args = dict(zip(sys.argv[2::2], sys.argv[3::2]))
expected = hashlib.sha256(f"global.json file: {Path.cwd()}/global.json\\n".encode()).hexdigest()
if action == "observe-toolchain":
    value = SEED
    value["dotnet"]["versionOutputSha256"] = expected
    output = Path(args["--output"])
    with output.open("xb") as stream:
        stream.write((json.dumps(value, indent=2, sort_keys=True) + "\\n").encode())
    output.chmod(0o600)
else:
    output = Path(args["--authority"])
    value = json.loads(output.read_bytes())
    if value["dotnet"]["versionOutputSha256"] != expected:
        sys.exit(2)
print(json.dumps({"status":"pass", "authorityClass": value["authorityClass"],
    "signingAuthorized":False, "publicationAuthorized":False,
    "observationSha256":hashlib.sha256(output.read_bytes()).hexdigest(),
    "javaSdkRoot":value["javaSdkRoot"], "dotnetPath":value["dotnet"]["absolutePath"]}))
'''.replace("SEED_VALUE", repr(claim))
    protected_file(helper, script.encode())
    original = protected_file(tmp_path / "original.json", fleet._pretty_json(claim))
    inventory = protected_file(tmp_path / "inventory.json", b"{}\n")
    output = tmp_path / "context.json"
    lock = {"android_authority": {"commit": "1" * 40, "attestation_consumer": {
        "path": "scripts/" + helper.name, "sha256": hashlib.sha256(helper.read_bytes()).hexdigest()}},
        "toolchain": {"java": {"tree_sha256": "b" * 64, "file_count": 1, "size_bytes": 20},
                      "dotnet": {"tree_sha256": "c" * 64, "file_count": 2, "size_bytes": 30}}}
    checked, calls = [], []
    monkeypatch.setattr(fleet, "_validate_android_consumer_inputs", lambda root, commit: checked.append((root, commit)))
    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.run(command, **kwargs)
    snapshot = fleet._RebuildToolchainInputs(inventory, original)
    def run(selected=runner):
        return fleet._contextual_rebuild_observation(lock, android, snapshot, dotnet, java, output, runner=selected)
    return SimpleNamespace(**locals())


def test_real_children_observe_and_verify_in_build_cwd_without_global_chdir(context, monkeypatch):
    c = context
    cwd, original_bytes = Path.cwd(), c.original.read_bytes()
    monkeypatch.setattr(os, "chdir", lambda *a: pytest.fail("process-global chdir forbidden"))
    result = c.run()
    assert Path.cwd() == cwd and c.original.read_bytes() == original_bytes
    c.snapshot.assert_exact(c.inventory, c.original)
    result.assert_exact(c.inventory, c.output)
    value = json.loads(c.output.read_bytes())
    assert value["dotnet"]["versionOutputSha256"] == info_digest(c.android)
    assert value["dotnet"]["versionOutputSha256"] != c.claim["dotnet"]["versionOutputSha256"]
    assert [command[5] for command, _ in c.calls] == ["observe-toolchain", "verify-toolchain"]
    for command, kwargs in c.calls:
        assert command[:4] == ["/usr/bin/python3", "-I", "-B", "-S"]
        assert command[4] == str(c.helper) and kwargs["cwd"] == c.android
        assert kwargs["env"] == {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C",
                                 "CHUMMER_RELEASE_REPO_ROOT": str(c.android)}
    assert c.checked == [(c.android, "1" * 40)] * 5


def test_old_observation_really_fails_modeled_canonical_version_check(context):
    c = context
    result = subprocess.run(["/usr/bin/python3", "-I", "-B", "-S", str(c.helper),
                             "verify-toolchain", "--authority", str(c.original)],
                            cwd=c.android, capture_output=True)
    assert result.returncode == 2


@pytest.mark.parametrize("fault", ["bool-int", "int-float", "tool", "java-version", "root", "extra", "version-type"])
def test_only_dotnet_version_output_delta_is_allowed(context, fault):
    c = context
    previous = deepcopy(c.claim)
    if fault == "bool-int": previous["signingAuthorized"] = 0
    elif fault == "int-float": previous["javaSdkTreeFileCount"] = 1.0
    elif fault == "tool": previous["tools"]["java"]["sha256"] = "f" * 64
    elif fault == "java-version": previous["javaVersionOutputSha256"] = "f" * 64
    elif fault == "root": previous["javaSdkRoot"] = "/wrong"
    elif fault == "extra": previous["extra"] = False
    else: previous["dotnet"]["versionOutputSha256"] = 1
    c.original.write_bytes(fleet._pretty_json(previous))
    c.snapshot.bindings = c.snapshot._capture()  # Fixture admission, not production recapture.
    with pytest.raises(fleet.RebuilderError): c.run()


@pytest.mark.parametrize("fault", ["wrong-helper", "closure", "missing-output", "error", "malformed", "wrong-root", "wrong-hash"])
def test_unqualified_failed_or_unbound_observation_is_rejected(context, fault):
    c = context
    if fault == "wrong-helper": c.helper.write_bytes(c.helper.read_bytes() + b"\n")
    if fault == "closure": c.lock["toolchain"]["java"]["file_count"] = True
    def runner(command, **kwargs):
        if fault == "error": return SimpleNamespace(returncode=1, stdout=b"", stderr=b"private diagnostic")
        result = c.runner(command, **kwargs)
        if fault == "missing-output" and command[5] == "observe-toolchain": c.output.unlink()
        if fault == "malformed": result.stdout = b"not json"
        if fault in {"wrong-root", "wrong-hash"} and command[5] == "verify-toolchain":
            value = json.loads(result.stdout)
            value["javaSdkRoot" if fault == "wrong-root" else "observationSha256"] = "/wrong"
            result.stdout = json.dumps(value).encode()
        return result
    with pytest.raises(fleet.RebuilderError): c.run(runner)
    if fault == "wrong-helper": assert not c.calls


@pytest.mark.parametrize("target", ["original", "inventory", "context", "swapped"])
def test_observe_verify_window_rejects_drift_and_swaps(context, target):
    c = context
    def runner(command, **kwargs):
        result = c.runner(command, **kwargs)
        if command[5] == "verify-toolchain":
            if target == "swapped":
                saved = c.original.read_bytes()
                c.original.write_bytes(c.output.read_bytes())
                c.output.write_bytes(saved)
            else:
                path = c.output if target == "context" else getattr(c, target)
                raw = path.read_bytes()
                path.unlink()
                protected_file(path, raw)
        return result
    with pytest.raises(fleet.RebuilderError): c.run(runner)


@pytest.mark.parametrize("target", ["original", "helper", "context"])
@pytest.mark.parametrize("failure", ["exception", "nonzero", "malformed"])
def test_failed_observer_still_fences_original_and_helper(context, failure, target):
    c = context
    def runner(command, **kwargs):
        if target == "context" and command[5] == "observe-toolchain":
            return c.runner(command, **kwargs)
        path = c.output if target == "context" else getattr(c, target)
        path.write_bytes(path.read_bytes() + b" ")
        if failure == "exception": raise subprocess.TimeoutExpired(command, 1)
        return SimpleNamespace(returncode=1 if failure == "nonzero" else 0, stdout=b"invalid")
    with pytest.raises(fleet.RebuilderError, match="qualified bytes" if target == "helper" else "admitted snapshot"):
        c.run(runner)


@pytest.mark.parametrize("target", ["original", "context"])
@pytest.mark.parametrize("failure", [False, True])
def test_build_uses_context_snapshot_and_still_fences_original(tmp_path, monkeypatch, context, target, failure):
    c = context
    owner = tmp_path / "authority/feed"
    owner.mkdir(parents=True)
    args = boundaries.entry_arguments(fleet, tmp_path, owner.parent, owner, "direct")
    args["workspace"].mkdir()
    args.update(java_tool_observation=c.original, installed_closure_receipt=c.inventory)
    for name in ("two_green_receipt", "approval"):
        protected_file(args[name], b'{"TEST_ONLY":true}\n')
    protected_file(tmp_path / "producer-source-graph.json", json.dumps(boundaries.fixture.graph(fleet)).encode())
    contextual = c.run()
    monkeypatch.setattr(fleet, "_contextual_rebuild_observation", lambda *a, **k: contextual)
    called = []
    def runner(command, **kwargs):
        called.append(command)
        assert kwargs["env"]["CHUMMER_ANDROID_RELEASE_TOOLCHAIN_AUTHORITY"] == str(c.output)
        assert kwargs["cwd"] == args["workspace"] / "chummer-android"
        path = c.original if target == "original" else c.output
        path.write_bytes(path.read_bytes() + b" ")
        if failure: raise subprocess.TimeoutExpired(command, 1)
        return SimpleNamespace(returncode=3)
    with pytest.raises(fleet.RebuilderError, match="admitted snapshot"):
        fleet._run_independent_rebuild(**args, runner=runner)
    assert len(called) == 1
