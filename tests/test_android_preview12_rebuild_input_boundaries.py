"""Local path/lock admission tests, not image or release-build authority."""
import json
from pathlib import Path
import subprocess

import pytest

import test_android_preview12_external_rebuilder as fixture


def ready_lock():
    lock = json.loads(fixture.LOCK.read_text())
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
                 "two_green_receipt approval package_authority ui_authority_receipt toolchain_authority "
                 "bundletool upload_certificate dotnet_root java_root android_sdk_root output_dir").split()
        return {**{name: parent / name for name in names}, "authority_root": authority,
                "owner_feed": feed, "reported_builder_image": "builder@sha256:" + "a" * 64}
    names = ("workspace two_green_receipt approval package_authority ui_authority_receipt toolchain_authority "
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


def test_direct_rebuild_passes_exact_feed_to_existing_android_boundary(tmp_path):
    module = fixture.load_module()
    feed = tmp_path / "authority" / "owner-feed"
    feed.mkdir(parents=True)
    args = entry_arguments(module, tmp_path, feed.parent, feed, "direct")
    args["workspace"].mkdir()
    for name in ("two_green_receipt", "approval"):
        fixture.protected_file(args[name], b'{"TEST_ONLY":true}\n')
    graph = json.dumps(fixture.graph(module)).encode()
    fixture.protected_file(tmp_path / "producer-source-graph.json", graph)
    calls = []
    def observe_android_call(argv, **kwargs):
        calls.append(argv)
        assert kwargs["env"]["CHUMMER_INTERNAL_PHONE_BETA_PACKAGE_FEED"] == str(feed)
        assert Path(kwargs["env"]["CHUMMER_INTERNAL_PHONE_BETA_PACKAGE_FEED"]).parent == args["authority_root"]
        assert kwargs["env"]["CHUMMER_ANDROID_RELEASE_PACKAGE_AUTHORITY"] == str(args["package_authority"])
        assert argv == ["/bin/bash", "-p", str(args["workspace"] / "chummer-android/scripts/build-release.sh")]
        # Orchestration fixture only: no compiler, package validation or build runs.
        outputs = args["build_input_root"] / "artifacts"
        outputs.mkdir()
        fixture.protected_file(outputs / "chummer-android-0.1.0-preview.12-unsigned.aab", b"TEST_ONLY")
        fixture.protected_file(outputs / "chummer-android-0.1.0-preview.12-source-graph.json", graph)
        return subprocess.CompletedProcess(argv, 3)
    module._run_independent_rebuild(**args, runner=observe_android_call)
    assert len(calls) == 1
