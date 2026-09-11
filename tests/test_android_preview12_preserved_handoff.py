"""Local byte-retention tests, NOT authenticated custody or release proof.

The shared mount_model fixture models only ownership/read-only mount metadata.
Files, inode changes, inventories, request/graph validation and hashes are real.
No fixture authenticates a workflow, approves a release or invokes a signer.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

import test_android_preview12_external_rebuilder as existing
import test_android_preview12_protected_transaction as transaction
from test_android_preview12_preserved_validation import mount_model, protected


@pytest.fixture
def fleet():
    return existing.load_module()


def raw_json(value):
    return (json.dumps(value, sort_keys=True) + "\n").encode()


def handoff_inputs(fleet, tmp_path):
    # Reuse only public request/graph fixture builders, never the transaction's
    # synthetic authenticated capability or its promoted toolchain booleans.
    tmp_path.chmod(0o700)
    lock_raw = existing.LOCK.read_bytes()
    lock = json.loads(lock_raw)
    lock_path = protected(tmp_path / "lock.json", lock_raw)
    directory = tmp_path / "handoff"
    directory.mkdir(mode=0o700)
    graph_raw = raw_json(transaction.source_graph(fleet, lock))
    unsigned_raw = b"offline unsigned input, not an Android build"
    graph_name = f"chummer-android-{fleet.VERSION_NAME}-source-graph.json"
    aab_name = f"chummer-android-{fleet.VERSION_NAME}-unsigned.aab"
    sidecar_raw = (
        f"{hashlib.sha256(unsigned_raw).hexdigest()}  artifacts/{aab_name}\n"
        f"{hashlib.sha256(graph_raw).hexdigest()}  artifacts/{graph_name}\n"
    ).encode()
    paths = {
        "unsignedAab": protected(directory / aab_name, unsigned_raw),
        "sourceGraph": protected(directory / graph_name, graph_raw),
        "buildSidecar": protected(directory / f"{aab_name}.sha256", sidecar_raw),
        "twoGreenReceipt": protected(directory / "ANDROID_API36_TWO_GREEN_ELIGIBILITY.generated.json",
                                     b'{"eligible":false}\n'),
        "twoGreenApproval": protected(directory / "ANDROID_API36_TWO_GREEN_RELEASE_APPROVAL.generated.json",
                                      b'{"approved":false}\n'),
        "externalSignerRequest": protected(directory / "ANDROID_EXTERNAL_SIGNER_REQUEST.generated.json",
                                           raw_json(transaction.external_request(
                                               fleet, graph_raw, unsigned_raw, sidecar_raw))),
    }
    bindings = {
        "lockSha256": hashlib.sha256(lock_raw).hexdigest(),
        "unsignedAabSizeBytes": len(unsigned_raw),
        "toolchainClosureSha256": "1" * 64,  # Syntax only, not a qualified toolchain.
        "sourceCommit": lock["android_authority"]["commit"],
        "sourceTree": lock["android_authority"]["tree"],
    }
    for field, name in (
        ("requestSha256", "externalSignerRequest"), ("sourceGraphSha256", "sourceGraph"),
        ("unsignedAabSha256", "unsignedAab"), ("twoGreenReceiptSha256", "twoGreenReceipt"),
        ("twoGreenApprovalSha256", "twoGreenApproval"),
    ):
        bindings[field] = hashlib.sha256(paths[name].read_bytes()).hexdigest()
    handoff = {
        "contractName": fleet.REBUILD_HANDOFF_CONTRACT,
        "status": "verified",
        "releaseIdentity": {"packageId": fleet.PACKAGE_ID, "versionName": fleet.VERSION_NAME,
                            "versionCode": fleet.VERSION_CODE},
        "outputs": {name: path.name for name, path in paths.items()},
        "bindings": bindings,
        "builderCredentialIsolationAuthority": "none_local_preparation_only",
        "eligibleForProtectedSigner": False,
        "signingPerformed": False,
        "publicationAuthorized": False,
        "googlePlayUploadAuthorized": False,
    }
    handoff_path = protected(directory / "FLEET_ANDROID_PREVIEW12_REBUILD_HANDOFF.generated.json", raw_json(handoff))
    return lock_path, directory, paths, handoff_path


def rewrite(path, change):
    value = json.loads(path.read_bytes())
    change(value)
    protected(path, raw_json(value))


def refresh_graph_request_bindings(paths, handoff_path):
    graph_raw = paths["sourceGraph"].read_bytes()
    digest = hashlib.sha256(graph_raw).hexdigest()
    def update(request):
        request["sourceGraph"].update(sha256=digest, sizeBytes=len(graph_raw))
        request["expectedExternalSignerOutput"]["mustBindSourceGraphSha256"] = digest
    rewrite(paths["externalSignerRequest"], update)
    rewrite(handoff_path, lambda value: value["bindings"].update(
        sourceGraphSha256=digest,
        requestSha256=hashlib.sha256(paths["externalSignerRequest"].read_bytes()).hexdigest(),
    ))


def test_modeled_custody_retains_local_bytes_without_promoting_authority(fleet, tmp_path, mount_model, monkeypatch):
    lock, directory, paths, handoff = handoff_inputs(fleet, tmp_path)
    def forbidden(*args, **kwargs):
        pytest.fail("retention must not create authenticated capabilities or invoke signing")
    for name in ("AuthenticatedRebuildHandoff", "execute_protected_signer_transaction", "sign_aab"):
        monkeypatch.setattr(fleet, name, forbidden)
    retained = fleet.PreservedRebuildHandoff(lock, directory)
    retained.assert_exact()
    retained.assert_exact()
    assert retained.paths == paths
    assert retained.handoff == json.loads(handoff.read_bytes())
    assert retained.handoff["eligibleForProtectedSigner"] is False
    assert retained.handoff["builderCredentialIsolationAuthority"] == "none_local_preparation_only"
    assert all(retained.handoff[name] is False for name in (
        "signingPerformed", "publicationAuthorized", "googlePlayUploadAuthorized"))
    assert not hasattr(retained, "provenance")
    assert not hasattr(retained, "toolchain")
    # Even in the modeled custody environment, these remain unqualified bytes.
    assert json.loads(paths["twoGreenReceipt"].read_bytes())["eligible"] is False


def test_real_writable_environment_cannot_admit_handoff(fleet, tmp_path):
    # No stat or mount model here: real writable custody must fail closed.
    lock, directory, _, _ = handoff_inputs(fleet, tmp_path)
    assert not os.statvfs(directory).f_flag & os.ST_RDONLY
    with pytest.raises(fleet.RebuilderError):
        fleet.PreservedRebuildHandoff(lock, directory)


@pytest.mark.parametrize("returned_kind", ["preserved", "metadata", "none"])
def test_transaction_rejects_non_authenticated_handoff_before_privileged_work(
    fleet, tmp_path, mount_model, monkeypatch, returned_kind,
):
    lock_path, directory, _, handoff_path = handoff_inputs(fleet, tmp_path)
    lock_raw = lock_path.read_bytes()
    lock = json.loads(lock_raw)
    if returned_kind == "preserved":
        returned = fleet.PreservedRebuildHandoff(lock_path, directory)
        returned.assert_exact()
    elif returned_kind == "metadata":
        returned = json.loads(handoff_path.read_bytes())
    else:
        returned = None
    assert not isinstance(returned, fleet.AuthenticatedRebuildHandoff)
    assert "external rebuilder lock is dormant" in fleet.validate_lock(lock, lock_raw)
    events = []

    def modeled_lock_admission(value, raw):
        # Model only the earlier configuration gate to reach the real return-
        # type boundary. Neither custody nor producer provenance is promoted.
        assert value == lock and raw == lock_raw
        events.append("modeled-lock-admission")
        return []

    def authenticate(value, raw):
        assert value == lock and raw == lock_raw
        events.append("authenticate")
        return returned

    def forbidden(*args, **kwargs):
        pytest.fail("unqualified handoff reached consumer, ledger, credentials or signing")

    monkeypatch.setattr(fleet, "validate_lock", modeled_lock_admission)
    for name in ("load_reviewed_ledger", "reserve_signing_attempt", "sign_aab"):
        monkeypatch.setattr(fleet, name, forbidden)
    output = tmp_path / "must-not-be-signed"
    paths_before = set(tmp_path.rglob("*"))
    with pytest.raises(
        fleet.RebuilderError,
        match="^protected provenance verifier returned no authenticated handoff$",
    ):
        fleet.execute_protected_signer_transaction(
            lock_path, authenticate, forbidden, tmp_path, {}, forbidden,
            forbidden, output, attempt_id="d" * 64,
            two_green_artifact_id=123, two_green_artifact_sha256="e" * 64,
        )
    assert events == ["modeled-lock-admission", "authenticate"]
    assert not output.exists()
    assert set(tmp_path.rglob("*")) == paths_before  # No recovery or output paths.
    assert lock_path.read_bytes() == lock_raw
    if returned_kind == "preserved":
        returned.assert_exact()


@pytest.mark.parametrize("fault", ["extra", "missing", "link", "directory", "relative", "root-link"])
def test_closed_canonical_physical_inventory(fleet, tmp_path, mount_model, fault):
    lock, directory, paths, _ = handoff_inputs(fleet, tmp_path)
    if fault == "extra":
        protected(directory / "unexpected.json", b"{}")
    elif fault == "missing":
        paths["twoGreenApproval"].unlink()
    elif fault == "link":
        target = protected(tmp_path / "outside.json", paths["twoGreenApproval"].read_bytes())
        paths["twoGreenApproval"].unlink()
        paths["twoGreenApproval"].symlink_to(target)
    elif fault == "directory":
        paths["twoGreenApproval"].unlink()
        paths["twoGreenApproval"].mkdir(mode=0o700)
    elif fault == "relative":
        directory = Path("handoff")
    elif fault == "root-link":
        link = tmp_path / "root-link"
        link.symlink_to(directory, target_is_directory=True)
        directory = link
    with pytest.raises(fleet.RebuilderError):
        fleet.PreservedRebuildHandoff(lock, directory)


@pytest.mark.parametrize("fault", ["nested-writable", "foreign-file", "foreign-lock", "writable-mode"])
def test_modeled_root_readonly_is_insufficient_for_unpreserved_inputs(fleet, tmp_path, mount_model, fault):
    lock, directory, paths, _ = handoff_inputs(fleet, tmp_path)
    writable, foreign = mount_model
    if fault == "nested-writable":
        writable.add(paths["unsignedAab"])
    elif fault == "foreign-file":
        foreign.add(paths["sourceGraph"])
    elif fault == "foreign-lock":
        foreign.add(lock)
    else:
        paths["buildSidecar"].chmod(0o622)
    with pytest.raises(fleet.RebuilderError):
        fleet.PreservedRebuildHandoff(lock, directory)


@pytest.mark.parametrize("fault", ["lock", "commit", "tree", "graph-commit", "graph-tree", "sidecar", "request"])
def test_current_lock_source_and_sidecar_bindings_are_real(fleet, tmp_path, mount_model, fault):
    lock, directory, paths, handoff = handoff_inputs(fleet, tmp_path)
    if fault in ("lock", "commit", "tree"):
        key = {"lock": "lockSha256", "commit": "sourceCommit", "tree": "sourceTree"}[fault]
        rewrite(handoff, lambda value: value["bindings"].update({key: "a" * (64 if fault == "lock" else 40)}))
    elif fault.startswith("graph-"):
        key = fault.removeprefix("graph-")
        rewrite(paths["sourceGraph"], lambda value: next(
            row for row in value["repositories"] if row["name"] == "chummer-android").update({key: "a" * 40}))
        refresh_graph_request_bindings(paths, handoff)
    elif fault == "sidecar":
        protected(paths["buildSidecar"], b"different sidecar\n")
    else:
        rewrite(paths["externalSignerRequest"], lambda value: value.update(signingAuthorized=True))
        rewrite(handoff, lambda value: value["bindings"].update(
            requestSha256=hashlib.sha256(paths["externalSignerRequest"].read_bytes()).hexdigest()))
    with pytest.raises(fleet.RebuilderError):
        fleet.PreservedRebuildHandoff(lock, directory)


@pytest.mark.parametrize("name", ["lock", "handoff", "unsignedAab", "sourceGraph", "buildSidecar",
                                 "twoGreenReceipt", "twoGreenApproval", "externalSignerRequest"])
@pytest.mark.parametrize("replacement", [False, True], ids=["changed-bytes", "same-bytes-new-inode"])
def test_every_retained_file_rejects_mutation_and_identical_replacement(fleet, tmp_path, mount_model, name, replacement):
    lock, directory, paths, handoff = handoff_inputs(fleet, tmp_path)
    retained = fleet.PreservedRebuildHandoff(lock, directory)
    path = {"lock": lock, "handoff": handoff, **paths}[name]
    before = path.stat()
    raw = path.read_bytes()
    if replacement:
        new_file = protected(tmp_path / "replacement", raw)
        new_file.replace(path)
        assert path.stat().st_ino != before.st_ino
        assert path.read_bytes() == raw
    else:
        protected(path, raw + b" ")
    with pytest.raises(fleet.RebuilderError):
        retained.assert_exact()


@pytest.mark.parametrize("fault", ["extra", "missing", "link", "writable-mount", "root-replacement"])
def test_lifetime_inventory_and_custody_are_rechecked(fleet, tmp_path, mount_model, fault):
    lock, directory, paths, _ = handoff_inputs(fleet, tmp_path)
    retained = fleet.PreservedRebuildHandoff(lock, directory)
    if fault == "extra":
        protected(directory / "extra")
    elif fault == "missing":
        paths["unsignedAab"].unlink()
    elif fault == "link":
        target = protected(tmp_path / "replacement", paths["unsignedAab"].read_bytes())
        paths["unsignedAab"].unlink()
        paths["unsignedAab"].symlink_to(target)
    elif fault == "writable-mount":
        mount_model[0].add(paths["unsignedAab"])
    else:
        moved = tmp_path / "old-root"
        directory.rename(moved)
        directory.mkdir(mode=0o700)
        for path in moved.iterdir():
            path.rename(directory / path.name)  # Identical file inodes, different root.
    with pytest.raises(fleet.RebuilderError):
        retained.assert_exact()


def test_new_locally_valid_bundle_cannot_replace_admitted_bundle(fleet, tmp_path, mount_model):
    lock, directory, paths, handoff = handoff_inputs(fleet, tmp_path)
    retained = fleet.PreservedRebuildHandoff(lock, directory)
    rewrite(paths["sourceGraph"], lambda value: value.update(generatedAtUtc="2026-09-07T00:00:00Z"))
    refresh_graph_request_bindings(paths, handoff)
    fleet.validate_local_rebuild_handoff(directory, json.loads(lock.read_bytes()))
    with pytest.raises(fleet.RebuilderError):
        retained.assert_exact()


def test_capture_rejects_mutation_during_local_validation(fleet, tmp_path, mount_model, monkeypatch):
    lock, directory, paths, _ = handoff_inputs(fleet, tmp_path)
    original = fleet.validate_local_rebuild_handoff
    def change_after_validation(*args):
        result = original(*args)
        protected(paths["twoGreenApproval"], b'{"approved":false,"changed":true}\n')
        return result
    monkeypatch.setattr(fleet, "validate_local_rebuild_handoff", change_after_validation)
    with pytest.raises(fleet.RebuilderError):
        fleet.PreservedRebuildHandoff(lock, directory)


@pytest.mark.parametrize("when", ["before-load", "after-load"])
def test_constructor_rejects_lock_replacement_between_initial_capture_and_admission(
    fleet, tmp_path, mount_model, monkeypatch, when,
):
    lock, directory, _, _ = handoff_inputs(fleet, tmp_path)
    original = fleet.load_lock
    def replace():
        protected(tmp_path / "replacement-lock", lock.read_bytes()).replace(lock)
    def changed_load(path):
        if when == "before-load":
            replace()
        result = original(path)
        if when == "after-load":
            replace()
        return result
    monkeypatch.setattr(fleet, "load_lock", changed_load)
    with pytest.raises(fleet.RebuilderError, match="lock changed during admission"):
        fleet.PreservedRebuildHandoff(lock, directory)


def test_capture_rejects_same_byte_replacement_during_file_read(fleet, tmp_path, mount_model, monkeypatch):
    lock, directory, paths, _ = handoff_inputs(fleet, tmp_path)
    original = fleet._sha256_file
    def replace_after_read(path, *args, **kwargs):
        result = original(path, *args, **kwargs)
        if path == paths["unsignedAab"]:
            protected(tmp_path / "replacement", path.read_bytes()).replace(path)
        return result
    monkeypatch.setattr(fleet, "_sha256_file", replace_after_read)
    with pytest.raises(fleet.RebuilderError):
        fleet.PreservedRebuildHandoff(lock, directory)


def test_snapshots_are_deeply_detached_and_readonly(fleet, tmp_path, mount_model, monkeypatch):
    lock, directory, paths, _ = handoff_inputs(fleet, tmp_path)
    observed = []
    original = fleet.validate_local_rebuild_handoff
    def retain_validator_result(*args):
        result = original(*args)
        observed.append(result)
        return result
    monkeypatch.setattr(fleet, "validate_local_rebuild_handoff", retain_validator_result)
    retained = fleet.PreservedRebuildHandoff(lock, directory)
    original_handoff, original_paths = observed[0]
    original_handoff["bindings"]["sourceCommit"] = "f" * 40
    original_paths.clear()
    assert retained.handoff["bindings"]["sourceCommit"] != "f" * 40
    assert retained.paths == paths
    with pytest.raises(TypeError):
        retained.handoff["bindings"]["sourceCommit"] = "f" * 40
    with pytest.raises(TypeError):
        retained.paths["unsignedAab"] = tmp_path / "different"
    with pytest.raises(AttributeError):
        retained.handoff = {}
    # The current handoff has nested maps, but future local list snapshots must
    # not accidentally become writable through a read-only outer container.
    mutable = {"items": [{"values": [1, {"flag": False}]}]}
    frozen = fleet.PreservedRebuildHandoff._freeze(mutable)
    mutable["items"][0]["values"][1]["flag"] = True
    assert frozen["items"][0]["values"][1]["flag"] is False
    with pytest.raises(TypeError):
        frozen["items"][0]["values"][1]["flag"] = True
    with pytest.raises(AttributeError):
        frozen["items"].append({})
    retained.assert_exact()
