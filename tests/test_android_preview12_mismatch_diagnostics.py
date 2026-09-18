"""Real staged-file custody and prepare control flow; SDK/build eligibility is modeled.

The files are synthetic outputs, not a qualified Android build or signing proof.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat

import pytest

from scripts import android_preview12_external_rebuilder as fleet
from test_android_preview12_external_rebuilder import protected_file
from test_android_preview12_separate_toolchain_inputs import modeled_preparation


MISMATCH = "independent unsigned AAB differs from producer"
RECEIPT = "REBUILD_MISMATCH_DIAGNOSTICS.json"


@pytest.fixture
def staged_rebuild(modeled_preparation, monkeypatch):
    case = modeled_preparation
    case.args["retain_mismatch_diagnostics"] = True
    case.diagnostics = case.args["output_dir"].with_name(case.args["output_dir"].name + ".mismatch-diagnostics")
    case.same_bytes = False
    original = fleet._run_independent_rebuild

    def rebuild(*args, **kwargs):
        original(*args, **kwargs)
        build_input = args[-1]
        artifacts, metadata = build_input / "artifacts", build_input / "private-rebuilt-metadata"
        artifacts.mkdir(mode=0o700)
        metadata.mkdir(mode=0o700)
        raw = case.paths["unsignedAab"].read_bytes()
        if not case.same_bytes:
            raw = raw[:-1] + b"!"  # Same length, different digest.
        aab = protected_file(artifacts / case.paths["unsignedAab"].name, raw)
        aab.chmod(0o444)
        graph_value = json.loads(case.paths["sourceGraph"].read_bytes())
        graph_value["generatedAtUtc"] = "2026-09-18T00:00:00Z"
        graph = protected_file(metadata / case.paths["sourceGraph"].name, json.dumps(graph_value).encode())
        sidecar_raw = (f"{hashlib.sha256(raw).hexdigest()}  artifacts/{aab.name}\n"
                       f"{hashlib.sha256(graph.read_bytes()).hexdigest()}  artifacts/{graph.name}\n").encode()
        sidecar = protected_file(metadata / (aab.name + ".sha256"), sidecar_raw)
        protected_file(build_input / "build.stdout", b"TEST_ONLY must not be retained")
        case.stage = build_input.parent
        case.sources = (aab, graph, sidecar)
        case.raw = {path.name: path.read_bytes() for path in case.sources}
        return aab, graph

    monkeypatch.setattr(fleet, "_run_independent_rebuild", rebuild)
    return case


def prepare(case):
    return fleet.prepare_rebuild_handoff(**case.args, runner=case.runner)


def failed(case):
    with pytest.raises(fleet.RebuilderError, match=MISMATCH) as error:
        prepare(case)
    assert str(error.value) == MISMATCH
    assert not case.args["output_dir"].exists()
    return error.value


def test_mismatch_keeps_exact_private_bounded_outputs_without_handoff(staged_rebuild):
    case = staged_rebuild
    error = failed(case)
    assert error.diagnostic_retention == "rejected rebuild diagnostics retained at OUTPUT_DIR.mismatch-diagnostics"
    assert not case.stage.exists()
    assert stat.S_IMODE(case.diagnostics.stat().st_mode) == 0o700
    assert {path.name for path in case.diagnostics.iterdir()} == set(case.raw) | {RECEIPT}
    receipt = json.loads((case.diagnostics / RECEIPT).read_bytes())
    assert receipt["status"] == "independent_unsigned_aab_mismatch" and receipt["diagnosticOnly"] is True
    assert receipt["producer"]["sha256"] == hashlib.sha256(case.paths["unsignedAab"].read_bytes()).hexdigest()
    assert receipt["observed"] == error.observed
    assert receipt["observed"]["sha256"] != receipt["producer"]["sha256"]
    assert case.raw[case.paths["sourceGraph"].name] != case.paths["sourceGraph"].read_bytes()
    assert all(receipt[key] is False for key in (
        "eligibleForProtectedSigner", "retryAuthorized", "signingPerformed",
        "publicationAuthorized", "googlePlayUploadAuthorized"))
    for path in case.diagnostics.iterdir():
        assert stat.S_IMODE(path.stat().st_mode) == 0o600 and path.stat().st_nlink == 1
        if path.name != RECEIPT:
            assert path.read_bytes() == case.raw[path.name]
            assert receipt["files"][path.name] == {
                "sha256": hashlib.sha256(case.raw[path.name]).hexdigest(), "sizeBytes": len(case.raw[path.name])}
    with pytest.raises(fleet.RebuilderError):
        fleet.validate_local_rebuild_handoff(case.diagnostics, json.loads(case.args["lock_path"].read_bytes()))


def test_default_mismatch_behavior_remains_unchanged(staged_rebuild):
    case = staged_rebuild
    case.args.pop("retain_mismatch_diagnostics")
    assert failed(case).diagnostic_retention is None
    assert not case.stage.exists() and not case.diagnostics.exists()


@pytest.mark.parametrize("enabled", [False, True])
def test_matching_rebuild_still_publishes_only_existing_handoff(staged_rebuild, enabled):
    case = staged_rebuild
    case.same_bytes = True
    case.args["retain_mismatch_diagnostics"] = enabled
    value = prepare(case)
    assert value["status"] == "verified" and value["eligibleForProtectedSigner"] is False
    assert not case.stage.exists() and not case.diagnostics.exists()
    assert {path.name for path in case.args["output_dir"].iterdir()} == set(value["outputs"].values()) | {
        "FLEET_ANDROID_PREVIEW12_REBUILD_HANDOFF.generated.json"}


@pytest.mark.parametrize("kind", ["directory", "file", "symlink"])
def test_existing_diagnostics_fail_before_checkout_without_overwrite(staged_rebuild, kind):
    case = staged_rebuild
    if kind == "directory":
        case.diagnostics.mkdir(mode=0o700)
        protected_file(case.diagnostics / "retained", b"existing evidence")
    elif kind == "file":
        protected_file(case.diagnostics, b"existing evidence")
    else:
        case.diagnostics.symlink_to(case.paths["unsignedAab"])
    with pytest.raises(fleet.RebuilderError, match="cannot be overwritten"):
        prepare(case)
    assert case.events == []
    assert case.diagnostics.is_symlink() if kind == "symlink" else (
        (case.diagnostics / "retained" if kind == "directory" else case.diagnostics).read_bytes() == b"existing evidence")


@pytest.mark.parametrize("fault", ["copy", "file-fsync", "directory-fsync", "parent-fsync", "receipt-fsync", "after-fsync"])
def test_retention_failure_keeps_original_candidate_and_same_failure(staged_rebuild, monkeypatch, fault):
    case = staged_rebuild
    original_copy, original_fsync = fleet._copy_canonical_output, fleet.os.fsync
    fired = []

    def copy(*args, **kwargs):
        if fault == "copy":
            fired.append(True)
            raise OSError("TEST_ONLY arbitrary sensitive exception text")
        return original_copy(*args, **kwargs)

    def fsync(descriptor):
        path = Path(f"/proc/self/fd/{descriptor}").resolve()
        selected = {"file-fsync": case.diagnostics / case.paths["unsignedAab"].name,
                    "directory-fsync": case.diagnostics, "parent-fsync": case.diagnostics.parent,
                    "receipt-fsync": case.diagnostics / RECEIPT,
                    "after-fsync": case.diagnostics.parent}.get(fault)
        if path == selected:
            fired.append(True)
            if fault == "after-fsync":
                original_fsync(descriptor)
            raise OSError("TEST_ONLY arbitrary sensitive exception text")
        return original_fsync(descriptor)

    monkeypatch.setattr(fleet, "_copy_canonical_output", copy)
    monkeypatch.setattr(fleet.os, "fsync", fsync)
    error = failed(case)
    assert fired and error.diagnostic_retention == (
        "diagnostic retention incomplete; original private rebuild stage retained")
    assert "sensitive" not in str(error) + error.diagnostic_retention
    for path in case.sources:
        assert path.read_bytes() == case.raw[path.name]
    if fault == "file-fsync":
        assert not (case.diagnostics / case.sources[0].name).exists()  # _write_exclusive removed its partial copy.
    assert (case.stage / "build-input/build.stdout").exists()  # Exceptional whole-stage retention is explicit.


@pytest.mark.parametrize("which", [0, 1, 2])
@pytest.mark.parametrize("attack", ["symlink", "hardlink", "mode", "replace-during-read"])
def test_hostile_custody_during_retention_fails_and_preserves_stage(staged_rebuild, monkeypatch, which, attack):
    case = staged_rebuild
    original = fleet._retain_rebuild_mismatch
    original_read = fleet.os.read
    changed = []

    def retain(*args, **kwargs):
        path = case.sources[which]
        if attack == "symlink":
            path.rename(path.with_suffix(".original"))
            path.symlink_to(path.with_suffix(".original"))
        elif attack == "hardlink":
            path.with_suffix(".alias").hardlink_to(path)
        elif attack == "mode":
            path.chmod(0o644)
        else:
            def read(descriptor, count):
                raw = original_read(descriptor, count)
                if not changed and os.fstat(descriptor).st_ino == path.stat().st_ino:
                    changed.append(True)
                    path.rename(path.with_suffix(".original"))
                    protected_file(path, case.raw[path.name])
                    path.chmod(0o444 if which == 0 else 0o600)
                return raw
            monkeypatch.setattr(fleet.os, "read", read)
        return original(*args, **kwargs)

    monkeypatch.setattr(fleet, "_retain_rebuild_mismatch", retain)
    error = failed(case)
    assert "incomplete" in error.diagnostic_retention and case.stage.is_dir()
    assert case.sources[which].read_bytes() == case.raw[case.sources[which].name]
    assert not (case.diagnostics / RECEIPT).exists()
    if attack == "replace-during-read":
        assert changed


def test_late_destination_tampering_keeps_original_stage(staged_rebuild, monkeypatch):
    case = staged_rebuild
    original = fleet._write_exclusive

    def write(path, raw):
        original(path, raw)
        if path == case.diagnostics / RECEIPT:
            (case.diagnostics / case.sources[1].name).write_bytes(b"changed diagnostic copy")

    monkeypatch.setattr(fleet, "_write_exclusive", write)
    assert "incomplete" in failed(case).diagnostic_retention
    assert all(path.read_bytes() == case.raw[path.name] for path in case.sources)


@pytest.mark.parametrize("attack", ["fixed-directory", "owner-parent", "source-parent", "extra-entry"])
def test_final_custody_fence_rejects_replacement_after_readback(staged_rebuild, monkeypatch, attack):
    case = staged_rebuild
    original = fleet._stable_file_sha256
    retained_stage = []

    def digest(path, metadata, label):
        value = original(path, metadata, label)
        if path == case.diagnostics / RECEIPT and label == "retained mismatch diagnostic":
            if attack == "owner-parent":
                parent = case.stage.parent
                retained = parent.with_name(parent.name + "-retained")
                parent.rename(retained)
                parent.mkdir(mode=0o700)
                shutil.copytree(retained / case.diagnostics.name, case.diagnostics)
                retained_stage.append(retained / case.stage.name)
            elif attack == "extra-entry":
                protected_file(case.diagnostics / "unexpected", b"TEST_ONLY")
            else:
                directory = case.diagnostics if attack == "fixed-directory" else case.sources[1].parent
                retained = directory.with_name(directory.name + "-retained")
                directory.rename(retained)
                shutil.copytree(retained, directory)
        return value

    monkeypatch.setattr(fleet, "_stable_file_sha256", digest)
    assert "incomplete" in failed(case).diagnostic_retention
    stage = retained_stage[0] if retained_stage else case.stage
    assert stage.is_dir()
    for path in case.sources:
        retained = stage / path.relative_to(case.stage)
        assert retained.read_bytes() == case.raw[path.name]


def test_late_target_creation_is_never_overwritten(staged_rebuild, monkeypatch):
    case = staged_rebuild
    original = fleet._retain_rebuild_mismatch
    def retain(*args, **kwargs):
        case.diagnostics.mkdir(mode=0o700)
        protected_file(case.diagnostics / "existing", b"retained evidence")
        return original(*args, **kwargs)
    monkeypatch.setattr(fleet, "_retain_rebuild_mismatch", retain)
    assert "incomplete" in failed(case).diagnostic_retention
    assert (case.diagnostics / "existing").read_bytes() == b"retained evidence"
    assert set(path.name for path in case.diagnostics.iterdir()) == {"existing"}
    assert all(path.read_bytes() == case.raw[path.name] for path in case.sources)


@pytest.mark.parametrize("size", [0, 16 * 1024 + 1])
def test_unbounded_or_empty_metadata_is_not_copied(staged_rebuild, monkeypatch, size):
    case = staged_rebuild
    original = fleet._retain_rebuild_mismatch
    def retain(*args, **kwargs):
        case.sources[2].write_bytes(b"x" * size)
        return original(*args, **kwargs)
    monkeypatch.setattr(fleet, "_retain_rebuild_mismatch", retain)
    assert "incomplete" in failed(case).diagnostic_retention
    assert case.stage.exists() and not (case.diagnostics / RECEIPT).exists()
    assert case.sources[0].read_bytes() == case.raw[case.sources[0].name]


def test_interrupt_during_retention_does_not_delete_original_stage(staged_rebuild, monkeypatch):
    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt
    monkeypatch.setattr(fleet, "_retain_rebuild_mismatch", interrupt)
    with pytest.raises(KeyboardInterrupt):
        prepare(staged_rebuild)
    assert all(path.read_bytes() == staged_rebuild.raw[path.name] for path in staged_rebuild.sources)


def test_cli_passes_opt_in_and_reports_same_failure_without_success(staged_rebuild, monkeypatch, capsys):
    case = staged_rebuild
    original = fleet.prepare_rebuild_handoff
    def prepare_cli(*args, **kwargs):
        assert kwargs["retain_mismatch_diagnostics"] is True
        return original(**case.args, runner=case.runner)
    monkeypatch.setattr(fleet, "prepare_rebuild_handoff", prepare_cli)
    argv = ["--lock", str(case.args["lock_path"]), "prepare-rebuild", "--retain-mismatch-diagnostics"]
    for key, value in case.args.items():
        if key not in {"lock_path", "retain_mismatch_diagnostics"}:
            argv.extend(["--builder-image" if key == "reported_builder_image" else "--" + key.replace("_", "-"), str(value)])
    assert fleet.main(argv) == 2
    output = capsys.readouterr()
    assert output.out == "" and MISMATCH in output.err
    assert "rejected rebuild diagnostics retained" in output.err
