"""Unsigned/protected configuration boundaries; no runtime or signing proof.

Configuration fixtures are explicit hypothetical admissions, never edits to the
checked-in dormant lock. File/hash and local handoff validation are real. Tests
of tool measurement and preparation model observations/SDK execution, not root
custody, a real build, job authentication, credentials or publication authority.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

import test_android_preview12_external_rebuilder as fixture
from scripts import android_preview12_external_rebuilder as fleet
from test_android_preview12_external_rebuilder import LOCK, protected_file
from test_android_preview12_preserved_handoff import handoff_inputs


def test_release_source_test_capabilities_are_explicit_and_nonpromoting():
    historical = ready_lock()
    fleet._admit_release_test_inputs(historical, None, None, None)
    with pytest.raises(fleet.RebuilderError, match="historical"):
        fleet._admit_release_test_inputs(historical, Path("/explicit"), None, None)
    historical["android_authority"]["build_script"]["sha256"] = "f" * 64
    with pytest.raises(fleet.RebuilderError, match="capability"):
        fleet._admit_release_test_inputs(historical, None, None, None)
    assert len(fleet.REPOSITORIES) == len(fleet.REVISION_VARIABLES) == 8
    assert "chummer5a" not in fleet.REPOSITORIES
    assert json.loads(LOCK.read_bytes())["state"] == "dormant"


@pytest.mark.parametrize("present", [(), (0,), (1,), (2,), (0, 1), (0, 2), (1, 2)])
@pytest.mark.parametrize("build_sha", [
    digest for digest, helper in fleet.RELEASE_TEST_CONSUMERS.items() if helper
])
def test_new_release_source_consumer_never_accepts_missing_or_partial_inputs(tmp_path, present, build_sha):
    lock = ready_lock()
    lock["android_authority"]["build_script"]["sha256"] = build_sha
    paths = tuple(tmp_path / str(index) if index in present else None for index in range(3))
    with pytest.raises(fleet.RebuilderError, match="require explicit"):
        fleet._admit_release_test_inputs(lock, *paths)


def test_checked_in_current_source_consumer_requires_all_three_safe_inputs(tmp_path):
    lock = json.loads(LOCK.read_bytes())
    binding = lock["android_authority"]["build_script"]
    current_build_sha = "4e29b255aae29d30f1b8ddb7fc96947cf851df2c661fa820031bd5db2604f3f6"
    current_capture_sha = "a295c226850edda9ce3a57a3c43690188e271b3059c33dd14abca04f65ef4bcf"
    assert binding["sha256"] == current_build_sha
    assert fleet._release_test_capability(lock) == current_capture_sha
    predecessor_build_sha = "fc8b6e637ba3220e4e9c5ea55c5e4dcca6cb26c196eaa75f6d19e91a87ed3db6"
    assert fleet.RELEASE_TEST_CONSUMERS[predecessor_build_sha] == current_capture_sha
    for present in [(), (0,), (1,), (2,), (0, 1), (0, 2), (1, 2)]:
        paths = tuple(
            (tmp_path / f"missing-{index}") if index in present else None
            for index in range(3)
        )
        for path in paths:
            if path is not None:
                path.mkdir(mode=0o700, exist_ok=True)
        with pytest.raises(fleet.RebuilderError, match="require explicit"):
            fleet._admit_release_test_inputs(lock, *paths)
    safe = tuple(tmp_path / name for name in ("bootstrap", "wheelhouse", "oracle"))
    for path in safe:
        path.mkdir(mode=0o700)
    fleet._admit_release_test_inputs(lock, *safe)


@pytest.mark.parametrize("attack", ["same", "nested", "output", "relative", "symlink", "writable", "file"])
@pytest.mark.parametrize("build_sha", [
    digest for digest, helper in fleet.RELEASE_TEST_CONSUMERS.items() if helper
])
def test_release_source_paths_reject_overlap_or_unsafe_inputs(tmp_path, attack, build_sha):
    lock = ready_lock()
    lock["android_authority"]["build_script"]["sha256"] = build_sha
    paths = [tmp_path / name for name in ("bootstrap", "wheels", "oracle")]
    for path in paths:
        path.mkdir(mode=0o700)
    output = tmp_path / "output"
    if attack == "same":
        paths[1] = paths[0]
    elif attack == "nested":
        paths[1] = paths[0] / "nested"
        paths[1].mkdir()
    elif attack == "output":
        output = paths[2]
    elif attack == "relative":
        paths[0] = Path("relative")
    elif attack == "symlink":
        link = tmp_path / "link"
        link.symlink_to(paths[0], target_is_directory=True)
        paths[0] = link
    elif attack == "writable":
        paths[0].chmod(0o777)
    else:
        paths[0].rmdir()
        paths[0].write_text("not a directory")
    with pytest.raises(fleet.RebuilderError, match="source-test"):
        fleet._admit_release_test_inputs(lock, *paths, output)


def test_release_source_cli_has_three_explicit_nonsecret_inputs(tmp_path):
    args = prepare_arguments(tmp_path, configured())
    argv = ["--lock", str(args.pop("lock_path")), "prepare-rebuild"]
    for name, value in args.items():
        argv += ["--builder-image" if name == "reported_builder_image" else "--" + name.replace("_", "-"), str(value)]
    for name in ("test-bootstrap-dir", "test-wheelhouse", "test-oracle-root"):
        argv += ["--" + name, str(tmp_path / name)]
    parsed = fleet._parser().parse_args(argv)
    assert parsed.test_bootstrap_dir == tmp_path / "test-bootstrap-dir"
    assert parsed.test_wheelhouse == tmp_path / "test-wheelhouse"
    assert parsed.test_oracle_root == tmp_path / "test-oracle-root"


def ready_lock():
    lock = json.loads(fixture.LOCK.read_text())
    # These modeled ready-lock tests exercise historical no-source-test inputs;
    # the checked-in qualified successor is tested separately with explicit feeds.
    lock["android_authority"]["build_script"]["sha256"] = (
        "61ea9fa04338889f78e26de26a90b392c5f16def2a4150a64a94e9d4fadd5ca9"
    )
    lock["state"] = "ready"
    lock["toolchain"].update(builder_image="registry.example.test/team/builder@sha256:" + "a" * 64,
                             signer_image="registry.example.test/team/signer@sha256:" + "b" * 64,
                             installed_closure_receipt_sha256="c" * 64)
    lock["outputs"]["signed_content_handoff_enabled"] = True
    lock["rebuild"]["enabled"] = True
    lock["reservation"].update(configured=True, adapter_sha256="d" * 64, policy_sha256="e" * 64,
                               protocol_source="merged_reviewed_fleet_authority")
    for name in ("key_alias", "keystore_secret", "store_password_secret", "key_password_secret"):
        lock["upload_key"][name] = "TEST_ONLY_SYMBOLIC"
    lock["approval_authority"]["private_key_secret"] = "TEST_ONLY_SYMBOLIC"
    return lock


def validate(module, lock):
    return module.validate_lock(lock, json.dumps(lock).encode(), lock["toolchain"]["builder_image"])


@pytest.mark.parametrize("image", [
    "builder@sha256:" + "a" * 64,
    "registry.example.test/team/builder@sha256:" + "0" * 64,
    "localhost:5000/team/build_worker@sha256:" + "f" * 64,
])
def test_only_explicit_digest_images_pass_synthetic_ready_lock(image):
    module, lock = fixture.load_module(), ready_lock()
    lock["toolchain"]["builder_image"] = image
    assert validate(module, lock) == []
    assert module.validate_lock(lock, json.dumps(lock).encode(), image + "different") == ["reported builder image differs from lock"]


@pytest.mark.parametrize("field", ["builder_image", "signer_image"])
@pytest.mark.parametrize("image", [
    None, 7, True, {}, [], "", "builder:latest", "builder@sha256:qualified",
    "builder:tag@sha256:" + "a" * 64,
    "builder@sha256:" + "A" * 64, "builder@sha256:" + "a" * 63,
    "builder@sha256:" + "a" * 65, "builder@sha256:" + "a" * 64 + "\n",
    "REGISTRY.example.test/builder@sha256:" + "a" * 64,
    "https://registry.example.test/builder@sha256:" + "a" * 64,
    "registry.example.test:99999/builder@sha256:" + "a" * 64,
    "registry.example.test//builder@sha256:" + "a" * 64,
    "builder @sha256:" + "a" * 64,
])
def test_invalid_image_cannot_make_a_ready_lock(field, image):
    module, lock = fixture.load_module(), ready_lock()
    assert validate(module, lock) == []
    lock["toolchain"][field] = image
    errors = validate(module, lock)
    assert len(errors) == 1 and errors[0].startswith("toolchain." + field)


@pytest.mark.parametrize("digest", [None, 9, True, [], "", "receipt", "a" * 63, "A" * 64, "a" * 65, "a" * 64 + "\n", "sha256:" + "a" * 64])
def test_installed_closure_requires_actual_hex_digest(digest):
    module, lock = fixture.load_module(), ready_lock()
    lock["toolchain"]["installed_closure_receipt_sha256"] = digest
    assert validate(module, lock) == ["toolchain.installed_closure_receipt_sha256 is not a lowercase SHA-256"]


def entry_arguments(module, parent, authority, feed, entry):
    if entry == "prepare":
        names = ("lock_path external_request producer_unsigned_aab producer_source_graph producer_sidecar "
                 "two_green_receipt approval package_authority ui_authority_receipt java_tool_observation installed_closure_receipt "
                 "bundletool upload_certificate dotnet_root java_root android_sdk_root output_dir").split()
        return {**{name: parent / name for name in names}, "authority_root": authority,
                "owner_feed": feed, "reported_builder_image": "builder@sha256:" + "a" * 64}
    names = ("workspace two_green_receipt approval package_authority ui_authority_receipt java_tool_observation installed_closure_receipt "
             "bundletool upload_certificate dotnet_root java_root android_sdk_root build_input_root").split()
    return {**{name: parent / name for name in names}, "lock": ready_lock(),
            "authority_root": authority, "owner_feed": feed}


@pytest.mark.parametrize("entry", ["prepare", "direct"])
@pytest.mark.parametrize("attack", ["sibling", "relative-root", "relative-feed", "missing-root", "missing-feed",
                                     "symlink-root", "symlink-feed", "symlink-ancestor", "symlink-cycle", "file-root", "file-feed"])
def test_authority_path_errors_precede_any_staging_clone_or_build(tmp_path, entry, attack):
    module = fixture.load_module()
    authority = tmp_path / "authority"
    authority.mkdir()
    feed = authority / "owner-feed"
    feed.mkdir()
    if attack == "sibling":
        authority = tmp_path / "other-authority"
        authority.mkdir()
    elif attack == "relative-root":
        authority = Path("authority")
    elif attack == "relative-feed":
        feed = Path("owner-feed")
    elif attack == "missing-root":
        authority = tmp_path / "missing"
    elif attack == "missing-feed":
        feed = authority / "missing"
    elif attack == "symlink-cycle":
        authority = tmp_path / "cycle"
        authority.symlink_to(authority, target_is_directory=True)
    elif attack in {"symlink-root", "symlink-feed", "symlink-ancestor"}:
        link = tmp_path / "link"
        link.symlink_to(feed if attack == "symlink-feed" else authority, target_is_directory=True)
        if attack == "symlink-root":
            authority = link
        elif attack == "symlink-feed":
            feed = link
        else:
            authority, feed = link, link / "owner-feed"
    else:
        regular = tmp_path / "regular-file"
        regular.write_bytes(b"not a directory")
        if attack == "file-root":
            authority = regular
        else:
            feed = regular
    before = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*"))
    args = entry_arguments(module, tmp_path, authority, feed, entry)
    function = module.prepare_rebuild_handoff if entry == "prepare" else module._run_independent_rebuild
    with pytest.raises(module.RebuilderError, match="package authority root"):
        function(**args, runner=lambda *_a, **_k: pytest.fail("invalid path reached clone/build runner"))
    assert sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*")) == before


@pytest.mark.parametrize("entry", ["prepare", "direct"])
def test_resolve_cycle_exception_is_fixed_and_precedes_staging(tmp_path, monkeypatch, entry):
    module = fixture.load_module()
    feed = tmp_path / "authority" / "owner-feed"
    feed.mkdir(parents=True)
    args = entry_arguments(module, tmp_path, feed.parent, feed, entry)
    function = module.prepare_rebuild_handoff if entry == "prepare" else module._run_independent_rebuild
    with monkeypatch.context() as context:
        context.setattr(Path, "resolve", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("symlink loop")))
        with pytest.raises(module.RebuilderError, match="canonical existing directories"):
            function(**args, runner=lambda *_a, **_k: pytest.fail("resolution failure reached runner"))
    assert not (tmp_path / "build_input_root").exists()
    assert not (tmp_path / "output_dir").exists()


def test_valid_authority_paths_reach_prepare_lock_before_staging(tmp_path, monkeypatch):
    module = fixture.load_module()
    feed = tmp_path / "authority" / "owner-feed"
    feed.mkdir(parents=True)
    class NextReadOnlyStep(Exception):
        pass
    monkeypatch.setattr(module, "load_lock", lambda *_: (_ for _ in ()).throw(NextReadOnlyStep()))
    with pytest.raises(NextReadOnlyStep):
        module.prepare_rebuild_handoff(**entry_arguments(module, tmp_path, feed.parent, feed, "prepare"),
            runner=lambda *_a, **_k: pytest.fail("sentinel lock must stop before runner"))
    assert not (tmp_path / "output_dir").exists()


def offline_consumer(args, raw=(b'input="$CHUMMER_ANDROID_RELEASE_OFFLINE_NUGET_FEED"\n'
                                b'aar_input="$CHUMMER_ANDROID_RELEASE_OFFLINE_AAR_FEED"\n')):
    script = args["workspace"] / "chummer-android/scripts/build-release.sh"
    script.parent.mkdir(parents=True)
    protected_file(script, raw)
    args["lock"]["android_authority"]["build_script"] = {
        "path": "scripts/build-release.sh", "sha256": hashlib.sha256(raw).hexdigest()}
    return script


@pytest.mark.parametrize("offline", [False, True])
@pytest.mark.parametrize("offline_aar", [False, True])
def test_direct_rebuild_passes_exact_feed_to_existing_android_boundary(tmp_path, monkeypatch, offline, offline_aar):
    module = fixture.load_module()
    feed = tmp_path / "authority" / "owner-feed"
    feed.mkdir(parents=True)
    args = entry_arguments(module, tmp_path, feed.parent, feed, "direct")
    args["workspace"].mkdir()
    expected_offline = {}
    for kind, enabled in (("nuget", offline), ("aar", offline_aar)):
        supplied = tmp_path / f"offline-{kind}"
        supplied.mkdir(mode=0o700)
        variable = f"CHUMMER_ANDROID_RELEASE_OFFLINE_{kind.upper()}_FEED"
        monkeypatch.setenv(variable, "/ambient/must-not-enter-child")
        if enabled:
            args[f"offline_{kind}_feed"] = supplied
            expected_offline[variable] = str(supplied)
    if expected_offline:
        offline_consumer(args)
        # Synthetic shell used only by this modeled NuGet/AAR boundary test.
        # Production capability table remains closed and independently tested.
        monkeypatch.setattr(module, "RELEASE_TEST_CONSUMERS", {
            **module.RELEASE_TEST_CONSUMERS, args["lock"]["android_authority"]["build_script"]["sha256"]: None})
    for name in ("two_green_receipt", "approval", "java_tool_observation", "installed_closure_receipt"):
        fixture.protected_file(args[name], b'{"TEST_ONLY":true}\n')
    graph = json.dumps(fixture.graph(module)).encode()
    fixture.protected_file(tmp_path / "producer-source-graph.json", graph)
    calls = []
    def observe_android_call(argv, **kwargs):
        calls.append(argv)
        assert kwargs["env"]["CHUMMER_INTERNAL_PHONE_BETA_PACKAGE_FEED"] == str(feed)
        assert Path(kwargs["env"]["CHUMMER_INTERNAL_PHONE_BETA_PACKAGE_FEED"]).parent == args["authority_root"]
        assert kwargs["env"]["CHUMMER_ANDROID_RELEASE_PACKAGE_AUTHORITY"] == str(args["package_authority"])
        assert kwargs["env"]["CHUMMER_ANDROID_RELEASE_TOOLCHAIN_AUTHORITY"] == str(args["java_tool_observation"])
        assert str(args["installed_closure_receipt"]) not in kwargs["env"].values()
        assert {key: value for key, value in kwargs["env"].items() if "OFFLINE" in key} == expected_offline
        assert kwargs["env"]["NUGET_PACKAGES"] == str(args["build_input_root"] / "nuget-packages")
        assert kwargs["cwd"] == args["workspace"] / "chummer-android"
        assert kwargs["timeout"] == args["lock"]["limits"]["build_timeout_seconds"]
        assert argv == ["/bin/bash", "-p", str(args["workspace"] / "chummer-android/scripts/build-release.sh")]
        # Orchestration fixture only: no compiler, package validation or build runs.
        outputs = args["build_input_root"] / "artifacts"
        outputs.mkdir()
        fixture.protected_file(outputs / "chummer-android-0.1.0-preview.12-unsigned.aab", b"TEST_ONLY")
        fixture.protected_file(outputs / "chummer-android-0.1.0-preview.12-source-graph.json", graph)
        return subprocess.CompletedProcess(argv, 3)
    module._run_independent_rebuild(**args, runner=observe_android_call)
    assert len(calls) == 1


@pytest.mark.parametrize("entry", ["prepare", "direct"])
@pytest.mark.parametrize("kind", ["NuGet", "AAR"])
@pytest.mark.parametrize("attack", ["empty", "dot", "relative", "missing", "file", "linked", "ancestor-link",
    "cycle", "parent-alias", "unsafe", "oversized", "unowned", "writable", "authority_root", "owner_feed",
    "package_authority", "ui_authority_receipt", "java_tool_observation", "installed_closure_receipt", "dotnet_root", "java_root",
    "android_sdk_root", "generated", "workspace", "ancestor", "root-alias",
    "two_green_receipt", "approval", "bundletool", "upload_certificate"])
def test_offline_feed_rejected_before_any_side_effect(tmp_path, monkeypatch, entry, kind, attack):
    module = fixture.load_module()
    operation = tmp_path / "operation"
    owner = operation / "authority" / "feed"
    owner.mkdir(parents=True)
    args = entry_arguments(module, operation, owner.parent, owner, entry)
    supplied = tmp_path / "offline"
    supplied.mkdir(mode=0o700)
    if attack in {"empty", "dot", "relative", "missing", "oversized"}:
        supplied = {"empty": "", "dot": Path(), "relative": Path("offline"),
                    "missing": tmp_path / "missing", "oversized": Path("/" + "a" * 4096)}[attack]
    elif attack in {"linked", "ancestor-link", "cycle"}:
        link = tmp_path / "link"
        link.symlink_to(link if attack == "cycle" else supplied, target_is_directory=True)
        if attack == "ancestor-link":
            (supplied / "child").mkdir()
            supplied = link / "child"
        else:
            supplied = link
    elif attack == "parent-alias":
        supplied = supplied / ".." / supplied.name
    elif attack in {"file", "unsafe"}:
        supplied = tmp_path / ("file" if attack == "file" else "unsafe;feed")
        supplied.write_bytes(b"input") if attack == "file" else supplied.mkdir()
    elif attack == "unowned":
        original = Path.lstat
        def metadata(path, *a, **k):
            actual = original(path, *a, **k)
            return SimpleNamespace(st_mode=actual.st_mode, st_uid=actual.st_uid + 1) if path == supplied else actual
        monkeypatch.setattr(Path, "lstat", metadata)
    elif attack == "writable":
        supplied.chmod(0o777)
    elif attack == "ancestor":
        supplied = tmp_path
    elif attack == "root-alias":
        args["dotnet_root"].symlink_to(supplied, target_is_directory=True)
    else:
        if attack in {"generated", "workspace"}:
            supplied = (args["output_dir"] / attack if entry == "prepare" else
                        args["workspace"] if attack == "workspace" else args["build_input_root"] / "nuget-packages")
        else:
            supplied = args[attack]
        supplied.mkdir(parents=True, exist_ok=True)
    before = sorted(str(path) for path in tmp_path.rglob("*"))
    function = module.prepare_rebuild_handoff if entry == "prepare" else module._run_independent_rebuild
    with pytest.raises(module.RebuilderError, match=f"offline {kind} feed must"):
        function(**args, **{f"offline_{kind.lower()}_feed": supplied},
                 runner=lambda *a, **k: pytest.fail("invalid offline transport reached runner"))
    assert sorted(str(path) for path in tmp_path.rglob("*")) == before


@pytest.mark.parametrize("entry", ["prepare", "direct"])
@pytest.mark.parametrize("overlap", ["equal", "nuget-parent", "aar-parent"])
def test_optional_feeds_cannot_overlap_each_other(tmp_path, entry, overlap):
    module = fixture.load_module()
    owner = tmp_path / "authority" / "feed"
    owner.mkdir(parents=True)
    args = entry_arguments(module, tmp_path, owner.parent, owner, entry)
    parent = tmp_path / "offline"
    child = parent / "nested"
    child.mkdir(parents=True, mode=0o700)
    nuget, aar = {"equal": (parent, parent), "nuget-parent": (parent, child),
                  "aar-parent": (child, parent)}[overlap]
    before = sorted(tmp_path.rglob("*"))
    function = module.prepare_rebuild_handoff if entry == "prepare" else module._run_independent_rebuild
    with pytest.raises(module.RebuilderError, match="offline AAR feed must"):
        function(**args, offline_nuget_feed=nuget, offline_aar_feed=aar,
                 runner=lambda *a, **k: pytest.fail("overlapping feeds reached runner"))
    assert sorted(tmp_path.rglob("*")) == before


@pytest.mark.parametrize("kind", ["NuGet", "AAR"])
@pytest.mark.parametrize("name", ["lock_path", "external_request", "producer_unsigned_aab",
    "producer_source_graph", "producer_sidecar", "offline_source_manifest"])
def test_prepare_feed_excludes_all_producer_inputs(tmp_path, kind, name):
    module = fixture.load_module()
    owner = tmp_path / "authority" / "feed"
    owner.mkdir(parents=True)
    args = entry_arguments(module, tmp_path, owner.parent, owner, "prepare")
    supplied = tmp_path / "offline"
    supplied.mkdir(mode=0o700)
    args[name] = supplied / "bound-input"
    before = sorted(tmp_path.rglob("*"))
    with pytest.raises(module.RebuilderError, match=f"offline {kind} feed must"):
        module.prepare_rebuild_handoff(**args, **{f"offline_{kind.lower()}_feed": supplied},
            runner=lambda *a, **k: pytest.fail("overlapping producer input reached runner"))
    assert sorted(tmp_path.rglob("*")) == before


@pytest.mark.parametrize("kind", ["NuGet", "AAR"])
@pytest.mark.parametrize("fault", ["older-script", "comment-only", "inline-comment", "single-quoted",
    "escaped-bare", "escaped-quoted", "other-feed", "hash-drift", "path-drift"])
def test_offline_consumer_must_be_capable_and_exactly_bound_before_staging(tmp_path, kind, fault):
    module = fixture.load_module()
    owner = tmp_path / "authority" / "feed"
    owner.mkdir(parents=True)
    supplied = tmp_path / "offline"
    supplied.mkdir(mode=0o700)
    args = entry_arguments(module, tmp_path, owner.parent, owner, "direct")
    variable = f"CHUMMER_ANDROID_RELEASE_OFFLINE_{kind.upper()}_FEED"
    raw_script = {"older-script": "exit 3\n", "comment-only": f'# input="${variable}"\n',
        "inline-comment": f'exit 3 # input="${variable}"\n', "single-quoted": f"input='${variable}'\n",
        "escaped-bare": f'input=\\${variable}\n', "escaped-quoted": f'input="\\${variable}"\n',
        "other-feed": 'input="$CHUMMER_ANDROID_RELEASE_OFFLINE_' + ("AAR" if kind == "NuGet" else "NUGET") + '_FEED"\n'}
    script = offline_consumer(args, raw_script.get(fault, f'input="${variable}"\n').encode())
    if fault == "hash-drift":
        script.write_bytes(script.read_bytes() + b"# changed\n")
    if fault == "path-drift":
        args["lock"]["android_authority"]["build_script"]["path"] = "scripts/other.sh"
    with pytest.raises(module.RebuilderError, match=f"does not support offline {kind}|bytes differ from lock"):
        module._run_independent_rebuild(**args, **{f"offline_{kind.lower()}_feed": supplied},
            runner=lambda *a, **k: pytest.fail("unbound or incapable consumer reached runner"))
    assert not args["build_input_root"].exists()


@pytest.mark.parametrize("kind", ["NuGet", "AAR"])
@pytest.mark.parametrize("expression", ["$VARIABLE", "${VARIABLE}", "${VARIABLE:-}"])
def test_bound_offline_consumer_accepts_ordinary_parameter_expansions(tmp_path, kind, expression):
    module = fixture.load_module()
    args = {"workspace": tmp_path, "lock": ready_lock()}
    expression = expression.replace("VARIABLE", f"CHUMMER_ANDROID_RELEASE_OFFLINE_{kind.upper()}_FEED")
    offline_consumer(args, f'# ignored comment\ninput="{expression}" # trailing comment\n'.encode())
    getattr(module, f"_require_offline_{kind.lower()}_consumer")(args["lock"], tmp_path)


BUILDER = "registry.example/builder@sha256:" + "a" * 64
SIGNER = "registry.example/signer@sha256:" + "b" * 64


def raw(value):
    return (json.dumps(value, sort_keys=True) + "\n").encode()


def configured(*, protected=False):
    value = json.loads(LOCK.read_bytes())
    # Modeled toolchain-input tests intentionally use the historical consumer;
    # current source-test capability requires explicit feeds in its own lane.
    value["android_authority"]["build_script"]["sha256"] = (
        "61ea9fa04338889f78e26de26a90b392c5f16def2a4150a64a94e9d4fadd5ca9"
    )
    value["state"] = "ready"
    value["rebuild"]["enabled"] = True
    value["toolchain"].update(builder_image=BUILDER, installed_closure_receipt_sha256="c" * 64)
    if protected:
        value["toolchain"]["signer_image"] = SIGNER
        value["outputs"]["signed_content_handoff_enabled"] = True
        value["reservation"].update(configured=True, adapter_sha256="d" * 64, policy_sha256="e" * 64,
                                    protocol_source="merged_reviewed_fleet_authority")
        for name in ("key_alias", "keystore_secret", "store_password_secret", "key_password_secret"):
            value["upload_key"][name] = "unit-symbolic-reference"
        value["approval_authority"]["private_key_secret"] = "unit-symbolic-reference"
    return value


def replace_field(value, path, replacement):
    target = value
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = replacement


DOWNSTREAM = [
    (("toolchain", "signer_image"), None, "toolchain.signer_image is not one digest-pinned OCI repository"),
    (("upload_key", "key_alias"), None, "upload_key.key_alias is not configured"),
    (("upload_key", "keystore_secret"), None, "upload_key.keystore_secret is not configured"),
    (("upload_key", "store_password_secret"), None, "upload_key.store_password_secret is not configured"),
    (("upload_key", "key_password_secret"), None, "upload_key.key_password_secret is not configured"),
    (("approval_authority", "private_key_secret"), None, "approval attestation private-key secret is not configured"),
    (("reservation", "configured"), False, "reviewed durable approval-ledger adapter is not configured"),
    (("reservation", "adapter_sha256"), None, "reviewed durable approval-ledger adapter is not configured"),
    (("reservation", "policy_sha256"), None, "reviewed durable approval-ledger adapter is not configured"),
    (("reservation", "protocol_source"), "pending", "reviewed durable approval-ledger adapter is not configured"),
    (("reservation", "policy_path"), "wrong.json", "binary signing must select its separate ledger policy"),
    (("limits", "reservation_timeout_seconds"), None, "limits.reservation_timeout_seconds is invalid"),
    (("outputs", "signed_content_handoff_enabled"), False, "private immutable signed-content handoff is not configured"),
]


@pytest.mark.parametrize("path,replacement,diagnostic", DOWNSTREAM)
def test_unsigned_ignores_only_downstream_activation_while_protected_still_rejects(path, replacement, diagnostic):
    value = configured(protected=True)
    assert fleet.validate_lock(value, raw(value), BUILDER) == []
    replace_field(value, path, replacement)
    before = deepcopy(value)
    assert fleet.validate_unsigned_rebuild_lock(value, raw(value), BUILDER) == []
    assert fleet.validate_lock(value, raw(value), BUILDER) == [diagnostic]
    assert value == before  # No fabricated signer image, credentials or repaired lock.


def test_unsigned_accepts_all_missing_downstream_configuration_without_promoting_it():
    value = configured()
    value["reservation"] = {}
    value["limits"].pop("reservation_timeout_seconds")
    before = deepcopy(value)
    assert fleet.validate_unsigned_rebuild_lock(value, raw(value), BUILDER) == []
    assert fleet.validate_lock(value, raw(value), BUILDER)
    assert value == before and value["toolchain"]["signer_image"] is None
    assert value["outputs"]["publication_authorized"] is False


COMMON = [
    (("contract_name",), "wrong.contract", "external rebuilder lock fields or version are not exact"),
    (("contract_version",), True, "external rebuilder lock fields or version are not exact"),
    (("contract_version",), 1.0, "external rebuilder lock fields or version are not exact"),
    (("release", "version_code"), 13, "Preview12 release identity is not exact"),
    (("release", "package_id"), "other.app", "Preview12 release identity is not exact"),
    (("android_authority", "repository"), "https://example.invalid/repo.git", "qualified Android authority is incomplete"),
    (("android_authority", "commit"), "missing", "qualified Android authority is incomplete"),
    (("android_authority", "tree"), "missing", "qualified Android authority is incomplete"),
    (("android_authority", "build_script", "sha256"), "missing", "Android build_script authority is incomplete"),
    (("android_authority", "build_script", "path"), "../outside", "Android build_script authority is incomplete"),
    (("android_authority", "attestation_consumer", "sha256"), "missing", "Android attestation_consumer authority is incomplete"),
    (("android_authority", "two_green_verifier", "sha256"), "missing", "Android two_green_verifier authority is incomplete"),
    (("android_authority", "source_graph_verifier", "sha256"), "missing", "Android source_graph_verifier authority is incomplete"),
    (("android_authority", "attestation_consumer", "contract_name"), "wrong", "Android attestation consumer contract drifted"),
    (("toolchain", "dotnet", "version"), "wrong", "dotnet closure is not exact"),
    (("toolchain", "dotnet", "tree_sha256"), "missing", "dotnet closure is not exact"),
    (("toolchain", "java", "file_count"), 1, "java closure is not exact"),
    (("toolchain", "java", "size_bytes"), 1, "java closure is not exact"),
    (("toolchain", "android_sdk", "build_tools_version"), "35.0.0", "Android API/build-tools 36 closure is not exact"),
    (("toolchain", "android_sdk", "tree_sha256"), "missing", "Android API/build-tools 36 closure is not exact"),
    (("toolchain", "platform"), "linux/arm64", "external rebuilder platform or bundletool drifted"),
    (("toolchain", "bundletool_sha256"), "0" * 64, "external rebuilder platform or bundletool drifted"),
    (("toolchain", "builder_image"), None, "toolchain.builder_image is not one digest-pinned OCI repository"),
    (("toolchain", "builder_image"), "registry.example:65536/builder@sha256:" + "a" * 64,
     "toolchain.builder_image registry port is invalid"),
    (("toolchain", "installed_closure_receipt_sha256"), None,
     "toolchain.installed_closure_receipt_sha256 is not a lowercase SHA-256"),
    (("approval_authority", "role"), "other", "Android v2 attestation authority is incomplete"),
    (("approval_authority", "scope"), "other", "Android v2 attestation authority is incomplete"),
    (("approval_authority", "rotation_requires_android_merge_and_requalification"), False,
     "Android v2 attestation authority is incomplete"),
    (("approval_authority", "public_key_sha256"), None, "Android v2 attestation authority is incomplete"),
    (("approval_authority", "public_key_spki_sha256"), None, "Android v2 attestation authority is incomplete"),
    (("upload_key", "expected_certificate_sha256"), "0" * 64, "legacy Play upload certificate identity drifted"),
    (("upload_key", "signature_algorithm"), "wrong", "legacy Play upload certificate identity drifted"),
    (("outputs", "android_attestation_contract"), "wrong", "external rebuilder output authority escalates or drifted"),
    (("outputs", "fleet_audit_contract"), "wrong", "external rebuilder output authority escalates or drifted"),
    (("outputs", "signed_content_handoff_required"), False, "external rebuilder output authority escalates or drifted"),
    (("outputs", "publication_authorized"), True, "external rebuilder output authority escalates or drifted"),
    (("outputs", "google_play_upload_authorized"), True, "external rebuilder output authority escalates or drifted"),
    (("state",), "dormant", "external rebuilder lock is dormant"),
    (("rebuild", "enabled"), False, "independent rebuild is disabled or weakened"),
    (("rebuild", "ambient_siblings_allowed"), True, "independent rebuild is disabled or weakened"),
    (("rebuild", "builder_credential_mounts_allowed"), True, "independent rebuild is disabled or weakened"),
    (("rebuild", "builder_runs_in_separate_job"), False, "independent rebuild is disabled or weakened"),
    (("rebuild", "deterministic_unsigned_digest_match_required"), False, "independent rebuild is disabled or weakened"),
    (("rebuild", "full_test_suite_required"), False, "independent rebuild is disabled or weakened"),
    (("limits", "json_bytes"), 0, "limits.json_bytes is invalid"),
    (("limits", "aab_bytes"), True, "limits.aab_bytes is invalid"),
    (("limits", "git_timeout_seconds"), -1, "limits.git_timeout_seconds is invalid"),
    (("limits", "build_timeout_seconds"), 0, "limits.build_timeout_seconds is invalid"),
]


def prepare_arguments(tmp_path, lock):
    tmp_path.chmod(0o700)
    lock_path = protected_file(tmp_path / "selected-lock.json", raw(lock))
    authority = tmp_path / "authority"
    authority.mkdir(mode=0o700)
    feed = authority / "feed"
    feed.mkdir(mode=0o700)
    missing = tmp_path / "not-admitted"
    return dict(lock_path=lock_path, external_request=missing, producer_unsigned_aab=missing,
        producer_source_graph=missing, producer_sidecar=missing, two_green_receipt=missing,
        approval=missing, package_authority=missing, authority_root=authority, owner_feed=feed,
        ui_authority_receipt=missing, java_tool_observation=missing, installed_closure_receipt=missing, bundletool=missing,
        upload_certificate=missing, dotnet_root=missing, java_root=missing, android_sdk_root=missing,
        output_dir=tmp_path / "output", reported_builder_image=BUILDER)


@pytest.mark.parametrize("path,replacement,diagnostic", COMMON)
def test_common_safety_rejected_before_runner_or_stage(tmp_path, monkeypatch, path, replacement, diagnostic):
    value = configured(protected=True)
    replace_field(value, path, replacement)
    assert diagnostic in fleet.validate_unsigned_rebuild_lock(value, raw(value), BUILDER)
    assert diagnostic in fleet.validate_lock(value, raw(value), BUILDER)
    args = prepare_arguments(tmp_path, value)
    def forbidden(*args, **kwargs):
        pytest.fail("invalid configuration reached a stage or runner")
    monkeypatch.setattr(fleet.tempfile, "mkdtemp", forbidden)
    # load_lock has its existing more-specific wrong-contract diagnostic.
    expected = "external rebuilder lock contract is not exact" if path == ("contract_name",) else diagnostic
    with pytest.raises(fleet.RebuilderError, match=expected):
        fleet.prepare_rebuild_handoff(**args, runner=forbidden)
    assert not args["output_dir"].exists()


@pytest.mark.parametrize("change", ["reported-image", "empty-bytes", "oversized-bytes", "extra-field"])
def test_exact_admission_envelope_and_reported_image_remain_required(change):
    value = configured(protected=True)
    selected, content = BUILDER, raw(value)
    if change == "reported-image":
        selected = SIGNER
    elif change == "empty-bytes":
        content = b""
    elif change == "oversized-bytes":
        content = b"x" * (1024 * 1024 + 1)
    else:
        value["unexpected"] = False
    assert fleet.validate_unsigned_rebuild_lock(value, content, selected)
    assert fleet.validate_lock(value, content, selected)


def test_checked_in_dormant_disabled_lock_is_never_activated(tmp_path, monkeypatch):
    original = LOCK.read_bytes()
    value = json.loads(original)
    diagnostics = fleet.validate_unsigned_rebuild_lock(value, original, BUILDER)
    assert "external rebuilder lock is dormant" in diagnostics
    assert "independent rebuild is disabled or weakened" in diagnostics
    args = prepare_arguments(tmp_path, value)
    def forbidden(*args, **kwargs):
        pytest.fail("actual dormant lock reached work")
    monkeypatch.setattr(fleet.tempfile, "mkdtemp", forbidden)
    with pytest.raises(fleet.RebuilderError, match="dormant"):
        fleet.prepare_rebuild_handoff(**args, runner=forbidden)
    assert LOCK.read_bytes() == original and not args["output_dir"].exists()
    assert fleet.contract_check(LOCK)["status"] == "dormant"


@pytest.mark.parametrize("action", ["execute", "reconcile"])
def test_protected_callers_keep_full_gate_before_callbacks_or_outputs(tmp_path, action):
    value = configured()
    lock_path = protected_file(tmp_path / "unsigned-only-lock.json", raw(value))
    def forbidden(*args, **kwargs):
        pytest.fail("unsigned-only configuration reached protected work")
    args = dict(lock_path=lock_path, authenticate_handoff=forbidden, load_consumer=forbidden,
        fleet_root=tmp_path, ledger_environment={}, protected_validation_factory=forbidden,
        output_dir=tmp_path / "protected-output", attempt_id="1" * 64,
        two_green_artifact_id=1, two_green_artifact_sha256="2" * 64)
    with pytest.raises(fleet.RebuilderError, match="signer_image"):
        if action == "execute":
            fleet.execute_protected_signer_transaction(**args, admit_signing_credentials=forbidden, runner=forbidden)
        else:
            fleet.reconcile_protected_signer_transaction(**args)
    assert not args["output_dir"].exists()
    assert fleet.contract_check(lock_path)["status"] == "dormant"


@pytest.fixture
def observations(tmp_path, monkeypatch):
    # Tree/version observations are models. Auxiliary files/hashes are real;
    # no fixture supplies root ownership or authenticated closure proof.
    tmp_path.chmod(0o700)
    lock = configured()
    roots = [tmp_path / name for name in ("dotnet", "java", "sdk")]
    for path in roots:
        path.mkdir(mode=0o700)
    for relative in ("platforms/android-36/android.jar", "build-tools/36.0.0/aapt2"):
        target = roots[2] / relative
        target.parent.mkdir(parents=True)
        target.write_bytes(b"model platform marker")
    bundle = protected_file(tmp_path / "bundletool.jar", b"not a real bundletool")
    receipt = protected_file(tmp_path / "toolchain.json", b'{"unitObservation":true}\n')
    lock["toolchain"]["bundletool_sha256"] = hashlib.sha256(bundle.read_bytes()).hexdigest()
    lock["toolchain"]["installed_closure_receipt_sha256"] = hashlib.sha256(receipt.read_bytes()).hexdigest()
    value = SimpleNamespace(lock=lock, roots=roots, bundle=bundle, receipt=receipt, tree_fault=None,
                            probe_fault=None, calls=[])
    def tree(root, label):
        value.calls.append(label)
        name = ("dotnet", "java", "android_sdk")[roots.index(root)]
        row = lock["toolchain"][name]
        observed = (row["tree_sha256"], row["file_count"], row["size_bytes"])
        if value.tree_fault == name:
            return "0" * 64, observed[1], observed[2]
        return observed
    def probe(runner, command, label):
        value.calls.append(label)
        return "wrong" if value.probe_fault == label else (
            lock["toolchain"]["dotnet"]["version"] if label == "dotnet" else
            'openjdk version "' + lock["toolchain"]["java"]["version"] + '"')
    monkeypatch.setattr(fleet, "_tree_digest", tree)
    monkeypatch.setattr(fleet, "_probe", probe)
    return value


def measure(observations, *, unsigned=True, image=BUILDER):
    method = fleet.verify_unsigned_toolchain if unsigned else fleet.verify_toolchain
    return method(observations.lock, *observations.roots, observations.bundle, observations.receipt, image)


def test_unsigned_toolchain_can_report_null_planned_signer_without_authority(observations):
    closure = measure(observations)
    assert closure["plannedSignerImage"] is None
    assert closure["builderExecutionProvenanceAuthenticated"] is False
    assert closure["protectedSignerRuntimeVerified"] is False
    assert closure["bundletoolSha256"] == hashlib.sha256(observations.bundle.read_bytes()).hexdigest()
    assert closure["installedClosureReceiptSha256"] == hashlib.sha256(observations.receipt.read_bytes()).hexdigest()
    with pytest.raises(fleet.RebuilderError, match="planned protected signer image is absent"):
        measure(observations, unsigned=False)
    with pytest.raises(fleet.RebuilderError, match="planned protected signer image is absent"):
        fleet._bind_auxiliary_toolchain(observations.lock, observations.bundle, observations.receipt, BUILDER)
    before = closure["closureSha256"]
    observations.lock["toolchain"]["signer_image"] = SIGNER
    protected = measure(observations, unsigned=False)
    assert protected == measure(observations) and protected["closureSha256"] != before


@pytest.mark.parametrize("fault", ["dotnet-tree", "java-tree", "sdk-tree", "dotnet-version", "java-version",
                                  "platform", "build-tools", "bundle", "receipt", "builder-image"])
@pytest.mark.parametrize("unsigned", [False, True])
def test_both_toolchain_entrypoints_reject_changed_build_inputs(observations, fault, unsigned):
    observations.lock["toolchain"]["signer_image"] = SIGNER
    image = BUILDER
    if fault.endswith("-tree"):
        observations.tree_fault = {"dotnet-tree": "dotnet", "java-tree": "java", "sdk-tree": "android_sdk"}[fault]
    elif fault.endswith("-version"):
        observations.probe_fault = fault.split("-")[0] if fault == "dotnet-version" else "Java"
    elif fault == "platform":
        (observations.roots[2] / "platforms/android-36/android.jar").unlink()
    elif fault == "build-tools":
        (observations.roots[2] / "build-tools/36.0.0/aapt2").unlink()
    elif fault == "bundle":
        observations.bundle.write_bytes(b"changed bundle")
    elif fault == "receipt":
        observations.receipt.write_bytes(b"changed observation")
    else:
        image = SIGNER
    with pytest.raises(fleet.RebuilderError):
        measure(observations, unsigned=unsigned, image=image)


@pytest.mark.parametrize("offline", [False, True])
@pytest.mark.parametrize("offline_nuget", [False, True])
@pytest.mark.parametrize("offline_aar", [False, True])
def test_prepare_uses_unsigned_paths_and_emits_only_existing_ineligible_handoff(tmp_path, monkeypatch, offline, offline_nuget, offline_aar):
    inputs = tmp_path / "inputs"
    inputs.mkdir(mode=0o700)
    _, _, paths, _ = handoff_inputs(fleet, inputs)
    lock = configured()
    observation = protected_file(tmp_path / "java-observation.json", b'{"TEST_ONLY_observation":true}\n')
    inventory = protected_file(tmp_path / "installed-inventory.json", b'{"TEST_ONLY_inventory":true}\n')
    lock["toolchain"]["installed_closure_receipt_sha256"] = hashlib.sha256(inventory.read_bytes()).hexdigest()
    args = prepare_arguments(tmp_path, lock)
    args.update(java_tool_observation=observation, installed_closure_receipt=inventory)
    if offline_nuget:
        args["offline_nuget_feed"] = tmp_path / "offline-packages"
        args["offline_nuget_feed"].mkdir(mode=0o700)
    if offline_aar:
        args["offline_aar_feed"] = tmp_path / "offline-aars"
        args["offline_aar_feed"].mkdir(mode=0o700)
    args.update(external_request=paths["externalSignerRequest"], producer_unsigned_aab=paths["unsignedAab"],
                producer_source_graph=paths["sourceGraph"], producer_sidecar=paths["buildSidecar"],
                two_green_receipt=paths["twoGreenReceipt"], approval=paths["twoGreenApproval"])
    events = []
    def forbidden(*args, **kwargs):
        pytest.fail("unsigned preparation selected protected validation or a real process")
    monkeypatch.setattr(fleet, "validate_lock", forbidden)
    monkeypatch.setattr(fleet, "verify_toolchain", forbidden)
    actual_unsigned = fleet.validate_unsigned_rebuild_lock
    def validate(*selected):
        events.append("unsigned-configuration")
        return actual_unsigned(*selected)
    monkeypatch.setattr(fleet, "validate_unsigned_rebuild_lock", validate)
    manifest = tmp_path / "source-manifest.json"
    if offline:
        args["offline_source_manifest"] = manifest
    def checkout(graph, workspace, *positional, **kwargs):
        events.append("modeled-checkout")
        assert positional == ((manifest,) if offline else ())
        assert kwargs == ({"timeout": lock["limits"]["git_timeout_seconds"]} if offline else {
            "runner": forbidden, "timeout": lock["limits"]["git_timeout_seconds"]})
        workspace.mkdir(mode=0o700)
    monkeypatch.setattr(fleet, "checkout_source_graph_from_bundles" if offline else "checkout_source_graph", checkout)
    monkeypatch.setattr(fleet, "checkout_source_graph" if offline else "checkout_source_graph_from_bundles", forbidden)
    consumer = SimpleNamespace(VERIFY=SimpleNamespace(verify_release_eligibility=lambda *a, **k: {
        "sourceCommit": lock["android_authority"]["commit"], "sourceTree": lock["android_authority"]["tree"]}),
        _sidecar_claims=lambda *a: {},
        _load_trusted_java_toolchain=lambda path: {
            "observationSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "tools": {"java": args["java_root"] / "bin/java"}, "dotnet": args["dotnet_root"] / "dotnet"})
    monkeypatch.setattr(fleet, "validate_android_consumer", lambda *a: consumer)
    monkeypatch.setattr(fleet, "_require_offline_nuget_consumer", lambda *a: events.append("bound-offline-consumer"))
    monkeypatch.setattr(fleet, "_require_offline_aar_consumer", lambda *a: events.append("bound-offline-aar-consumer"))
    def toolchain(*a, **k):
        events.append("unsigned-toolchain-model")
        assert a[0]["toolchain"]["signer_image"] is None
        assert a[5] == inventory and a[5] != observation
        return {"closureSha256": "f" * 64}
    monkeypatch.setattr(fleet, "verify_unsigned_toolchain", toolchain)
    def rebuild(*a, **k):
        events.append("modeled-unsigned-rebuild")
        # The last positional input is the disposable build-input directory,
        # not the preceding admitted Android SDK root.
        assert a[-1].name == "build-input" and len(a) == 16
        assert a[8:10] == (observation, inventory)
        captured = k.pop("toolchain_inputs")
        captured.assert_exact(inventory, observation)
        assert k == {"runner": forbidden, "offline_nuget_feed": args.get("offline_nuget_feed"),
                     "offline_aar_feed": args.get("offline_aar_feed"), "test_bootstrap_dir": None,
                     "test_wheelhouse": None, "test_oracle_root": None}
        a[-1].mkdir(mode=0o700)
        return paths["unsignedAab"], paths["sourceGraph"]
    monkeypatch.setattr(fleet, "_run_independent_rebuild", rebuild)
    result = fleet.prepare_rebuild_handoff(**args, runner=forbidden)
    assert events == ["unsigned-configuration", "modeled-checkout"] + (["bound-offline-consumer"] if offline_nuget else []) + (
        ["bound-offline-aar-consumer"] if offline_aar else []) + [
        "unsigned-toolchain-model", "modeled-unsigned-rebuild"]
    actual, copied = fleet.validate_local_rebuild_handoff(args["output_dir"], lock)
    assert actual == result and len(list(args["output_dir"].iterdir())) == 7
    assert result["eligibleForProtectedSigner"] is False
    assert result["builderCredentialIsolationAuthority"] == "none_local_preparation_only"
    assert all(result[name] is False for name in ("signingPerformed", "publicationAuthorized", "googlePlayUploadAuthorized"))
    assert copied["unsignedAab"].read_bytes() == paths["unsignedAab"].read_bytes()
    assert result["bindings"]["lockSha256"] == hashlib.sha256(args["lock_path"].read_bytes()).hexdigest()


@pytest.mark.parametrize("manifest", [None, "/absolute/source-manifest.json", "relative-manifest.json"])
@pytest.mark.parametrize("nuget_feed", [None, "/absolute/offline-packages", "relative-packages"])
@pytest.mark.parametrize("aar_feed", [None, "/absolute/offline-aars", "relative-aars"])
def test_prepare_cli_propagates_optional_inputs_without_normalizing_relative_input(tmp_path, monkeypatch, capsys, manifest, nuget_feed, aar_feed):
    args = prepare_arguments(tmp_path, configured())
    argv = ["--lock", str(args["lock_path"]), "prepare-rebuild"]
    for name, value in args.items():
        if name == "lock_path":
            continue
        argv += ["--builder-image" if name == "reported_builder_image" else "--" + name.replace("_", "-"), str(value)]
    if manifest is not None:
        argv += ["--offline-source-manifest", manifest]
    if nuget_feed is not None:
        argv += ["--offline-nuget-feed", nuget_feed]
    if aar_feed is not None:
        argv += ["--offline-aar-feed", aar_feed]
    observed = []
    def prepare(*positional, **kwargs):
        observed.append(kwargs)
        return {"unitFixture": True}
    monkeypatch.setattr(fleet, "prepare_rebuild_handoff", prepare)
    assert fleet.main(argv) == 0
    assert observed == [{"offline_source_manifest": Path(manifest) if manifest is not None else None,
                         "offline_nuget_feed": Path(nuget_feed) if nuget_feed is not None else None,
                         "offline_aar_feed": Path(aar_feed) if aar_feed is not None else None,
                         "test_bootstrap_dir": None, "test_wheelhouse": None, "test_oracle_root": None}]
    assert json.loads(capsys.readouterr().out) == {"unitFixture": True}


@pytest.mark.parametrize("value", ["", "/safe/./feed", "/safe//feed", "/safe/feed/"])
@pytest.mark.parametrize("kind", ["nuget", "aar"])
def test_offline_feed_cli_rejects_aliases_before_path_normalization(value, kind):
    with pytest.raises(fleet.argparse.ArgumentTypeError, match="aliases or be empty"):
        getattr(fleet, f"_offline_{kind}_feed_argument")(value)
