"""Separate preparation inputs: real file guards, modeled build, optional exact Android.

No installed SDK, operational approval, runtime custody or compilation is modeled
as proven. Exact-current tests use the actual guarded Android loader; the original
receipt test uses published RFC test trust, not an operational signing key.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import android_preview12_external_rebuilder as fleet
import test_android_preview12_rebuild_input_boundaries as boundaries
from test_android_preview12_external_rebuilder import LOCK, protected_file
from test_android_preview12_preserved_handoff import handoff_inputs


def tool_inputs(parent):
    inventory = protected_file(parent / "archive-inventory.json", json.dumps({
        "contract_name": "fleet.android_preview12_installed_toolchain.v1",
        "lock_sha256": "a" * 64, "base_images": [], "archives": [],
    }).encode())  # Schema fixture, not a measured installed inventory.
    observation = protected_file(parent / "observation.json", b'{"TEST_ONLY_observation":true}\n')
    return inventory, observation


@pytest.mark.parametrize("missing", ["java-tool-observation", "installed-closure-receipt", "legacy-only"])
def test_cli_requires_both_distinct_inputs_without_legacy_fallback(tmp_path, missing):
    args = boundaries.prepare_arguments(tmp_path, boundaries.configured())
    argv = ["--lock", str(args.pop("lock_path")), "prepare-rebuild"]
    for name, path in args.items():
        option = name.replace("_", "-")
        if option == missing or (missing == "legacy-only" and option in {
                "java-tool-observation", "installed-closure-receipt"}):
            continue
        argv += ["--builder-image" if name == "reported_builder_image" else "--" + option, str(path)]
    if missing == "legacy-only":
        argv += ["--toolchain-authority", str(tmp_path / "ambiguous.json")]
    with pytest.raises(SystemExit) as error:
        fleet._parser().parse_args(argv)
    assert error.value.code == 2


def change(path, kind):
    if kind == "bytes":
        path.write_bytes(path.read_bytes() + b" ")
    elif kind == "replace":
        original = path.with_suffix(".original")
        path.rename(original)
        protected_file(path, original.read_bytes())
    elif kind == "mode":
        path.chmod(0o644)
    else:
        path.unlink()


@pytest.mark.parametrize("which", [0, 1])
@pytest.mark.parametrize("kind", ["bytes", "replace", "mode", "missing"])
def test_both_inputs_reject_drift_and_same_byte_replacement(tmp_path, which, kind):
    paths = tool_inputs(tmp_path)
    snapshot = fleet._RebuildToolchainInputs(*paths)
    change(paths[which], kind)
    with pytest.raises(fleet.RebuilderError):
        snapshot.assert_exact(*paths)


@pytest.mark.parametrize("kind", ["same-path", "hardlink", "symlink", "relative", "swapped-paths"])
def test_inputs_cannot_alias_or_change_roles(tmp_path, kind):
    inventory, observation = tool_inputs(tmp_path)
    snapshot = fleet._RebuildToolchainInputs(inventory, observation)
    if kind == "swapped-paths":
        with pytest.raises(fleet.RebuilderError, match="admitted snapshot"):
            snapshot.assert_exact(observation, inventory)
        return
    if kind in {"hardlink", "symlink"}:
        observation.unlink()
        if kind == "hardlink":
            observation.hardlink_to(inventory)
        else:
            observation.symlink_to(inventory)
    elif kind == "same-path":
        observation = inventory
    else:
        observation = Path("observation.json")
    with pytest.raises(fleet.RebuilderError):
        fleet._RebuildToolchainInputs(inventory, observation)


@pytest.fixture
def modeled_preparation(tmp_path, monkeypatch):
    """Only preparation control flow is real; no SDK/build result is certified."""
    inputs = tmp_path / "inputs"
    inputs.mkdir(mode=0o700)
    _, _, paths, _ = handoff_inputs(fleet, inputs)
    inventory, observation = tool_inputs(tmp_path)
    lock = boundaries.configured()
    lock["toolchain"]["installed_closure_receipt_sha256"] = hashlib.sha256(inventory.read_bytes()).hexdigest()
    args = boundaries.prepare_arguments(tmp_path, lock)
    args.update(java_tool_observation=observation, installed_closure_receipt=inventory,
        external_request=paths["externalSignerRequest"], producer_unsigned_aab=paths["unsignedAab"],
        producer_source_graph=paths["sourceGraph"], producer_sidecar=paths["buildSidecar"],
        two_green_receipt=paths["twoGreenReceipt"], approval=paths["twoGreenApproval"])
    events = []
    def forbidden(*args, **kwargs):
        pytest.fail("modeled preparation reached a real process or protected work")
    def checkout(graph, workspace, **kwargs):
        events.append("checkout")
        workspace.mkdir(mode=0o700)
    consumer = SimpleNamespace(VERIFY=SimpleNamespace(verify_release_eligibility=lambda *a, **k: {
        "sourceCommit": lock["android_authority"]["commit"], "sourceTree": lock["android_authority"]["tree"]}),
        _sidecar_claims=lambda *a: {}, _load_trusted_java_toolchain=lambda path: {
            "observationSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "tools": {"java": args["java_root"] / "bin/java"}, "dotnet": args["dotnet_root"] / "dotnet"})
    def measure(*a, **kwargs):
        assert a[5] == inventory
        events.append("measure-model")
        return {"closureSha256": "f" * 64}
    def rebuild(*a, **kwargs):
        kwargs["toolchain_inputs"].assert_exact(inventory, observation)
        assert a[8:10] == (observation, inventory)
        events.append("rebuild-model")
        a[-1].mkdir(mode=0o700)
        return paths["unsignedAab"], paths["sourceGraph"]
    monkeypatch.setattr(fleet, "checkout_source_graph", checkout)
    monkeypatch.setattr(fleet, "validate_android_consumer", lambda *a: consumer)
    monkeypatch.setattr(fleet, "verify_unsigned_toolchain", measure)
    monkeypatch.setattr(fleet, "_run_independent_rebuild", rebuild)
    monkeypatch.setattr(fleet, "validate_lock", forbidden)
    return SimpleNamespace(args=args, paths=paths, consumer=consumer, events=events,
                           inventory=inventory, observation=observation, runner=forbidden)


@pytest.mark.parametrize("which", ["inventory", "observation"])
@pytest.mark.parametrize("kind", ["bytes", "replace"])
@pytest.mark.parametrize("phase", ["checkout", "measurement", "eligibility", "sidecar", "build", "publish"])
def test_input_drift_never_publishes_handoff(modeled_preparation, monkeypatch, which, kind, phase):
    case = modeled_preparation
    target = getattr(case, which)
    obj, name = {
        "checkout": (fleet, "checkout_source_graph"),
        "measurement": (fleet, "verify_unsigned_toolchain"),
        "eligibility": (case.consumer.VERIFY, "verify_release_eligibility"),
        "sidecar": (case.consumer, "_sidecar_claims"),
        "build": (fleet, "_run_independent_rebuild"),
        "publish": (fleet.shutil, "rmtree"),
    }[phase]
    original = getattr(obj, name)
    changed = False
    def drift(*args, **kwargs):
        nonlocal changed
        value = original(*args, **kwargs)
        if not changed:
            change(target, kind)
            changed = True
        return value
    monkeypatch.setattr(obj, name, drift)
    with pytest.raises(fleet.RebuilderError, match="admitted snapshot"):
        fleet.prepare_rebuild_handoff(**case.args, runner=case.runner)
    assert not case.args["output_dir"].exists()
    assert not list(case.args["output_dir"].parent.glob(".output-*"))
    if phase not in {"build", "publish"}:
        assert "rebuild-model" not in case.events


@pytest.mark.parametrize("fault", ["missing-inventory", "missing-observation", "swapped", "stale-inventory"])
def test_wrong_or_missing_inputs_fail_before_checkout(modeled_preparation, fault):
    case = modeled_preparation
    if fault.startswith("missing-"):
        getattr(case, fault.removeprefix("missing-")).unlink()
    elif fault == "swapped":
        case.args.update(installed_closure_receipt=case.observation, java_tool_observation=case.inventory)
    else:
        case.inventory.write_bytes(b"changed installed receipt")
    with pytest.raises(fleet.RebuilderError):
        fleet.prepare_rebuild_handoff(**case.args, runner=case.runner)
    assert case.events == [] and not case.args["output_dir"].exists()


@pytest.mark.parametrize("fault", ["digest", "java", "dotnet", "missing-digest"])
def test_android_observation_must_match_captured_bytes_and_tool_roots(modeled_preparation, fault):
    case = modeled_preparation
    original = case.consumer._load_trusted_java_toolchain
    def load(path):
        value = original(path)
        if fault == "digest":
            value["observationSha256"] = "0" * 64
        elif fault == "missing-digest":
            value.pop("observationSha256")
        elif fault == "java":
            value["tools"]["java"] = Path("/different/bin/java")
        else:
            value["dotnet"] = Path("/different/dotnet")
        return value
    case.consumer._load_trusted_java_toolchain = load
    with pytest.raises((fleet.RebuilderError, KeyError)):
        fleet.prepare_rebuild_handoff(**case.args, runner=case.runner)
    assert "rebuild-model" not in case.events and not case.args["output_dir"].exists()


@pytest.mark.parametrize("which", ["installed_closure_receipt", "java_tool_observation"])
@pytest.mark.parametrize("phase", ["before-runner", "during-runner"])
def test_real_child_boundary_rechecks_both_inputs(tmp_path, monkeypatch, which, phase):
    owner = tmp_path / "authority/feed"
    owner.mkdir(parents=True)
    args = boundaries.entry_arguments(fleet, tmp_path, owner.parent, owner, "direct")
    args["workspace"].mkdir()
    for name in ("two_green_receipt", "approval", "java_tool_observation", "installed_closure_receipt"):
        protected_file(args[name], b'{"TEST_ONLY":true}\n')
    protected_file(tmp_path / "producer-source-graph.json", json.dumps(boundaries.fixture.graph(fleet)).encode())
    calls = []
    if phase == "before-runner":
        original = fleet._copy_protected
        def copy(*values):
            original(*values)
            if not calls:
                change(args[which], "replace")
                calls.append("replace")
        monkeypatch.setattr(fleet, "_copy_protected", copy)
    def runner(*a, **k):
        calls.append("runner")
        change(args[which], "replace")
        return SimpleNamespace(returncode=3)
    with pytest.raises(fleet.RebuilderError, match="admitted snapshot"):
        fleet._run_independent_rebuild(**args, runner=runner)
    assert ("runner" in calls) == (phase == "during-runner")


@pytest.fixture
def exact_current_android():
    configured = os.environ.get("CHUMMER_ANDROID_CURRENT_BUILDER_ROOT")
    if not configured:
        pytest.skip("exact current d4e Android source required; not installed SDK qualification")
    root = Path(configured)
    lock = deepcopy(json.loads(LOCK.read_bytes()))
    authority = lock["android_authority"]
    authority.update(commit="d4e9116d5bcdf12a51dec6490bf47b97ed143134",
                     tree="301180a95bb313f77b6c695ac8b88624603de933")
    for name, digest in {
        "build_script": "499f7cf4ccea659239c1fdc6e7c0a1b18c7280cc1983f699bbbbc30019546daa",
        "attestation_consumer": "6b784367cd58348f77243ac497efd67e73c6d53828241c5a47b4a0ff6255f655",
        "two_green_verifier": "3217d44a653c21e604de6383b7b200e36749865c5e343fd1c1983be7261ee07c",
        "source_graph_verifier": "c15f60db34f6becfe60ddfd749da1b50d457cf5777232e26a7513bdc068d983e",
    }.items():
        authority[name]["sha256"] = digest
    # Public-only test binding; production lock and every readiness flag stay dormant.
    lock["approval_authority"].update(key_id="fleet-release-builder-2026-09",
        public_key_path="eng/trusted-release-builders/fleet-release-builder-2026-09.public.pem",
        public_key_sha256="ef44c5b7fcadaf0f115b5f0e0e7b1a65edb322bb002faf980acb654a5db8caaf",
        public_key_spki_sha256="41b44078d037fafd85b091b967959f77a7a4aa9f160d03749fa49889a8b1b156")
    original = LOCK.read_bytes()
    android = fleet.validate_android_consumer(root, lock)  # Exact HEAD, origin and full scripts/eng blob guards.
    yield android
    fleet._validate_android_consumer_inputs(root, authority["commit"])
    assert LOCK.read_bytes() == original


def test_actual_current_android_rejects_inventory_as_observation(exact_current_android, tmp_path):
    inventory, observation = tool_inputs(tmp_path)
    captured = fleet._RebuildToolchainInputs(observation, inventory)  # Swapped roles, distinct files.
    with pytest.raises(ValueError, match="fields are not exact"):
        captured.validate_observation(exact_current_android, Path("/opt/dotnet"), Path("/opt/jdk"))


def test_original_receipt_passes_actual_current_builder_guarded_loader(exact_current_android, tmp_path, monkeypatch):
    from test_android_preview12_current_consumer import ORIGINAL_RECEIPT_SHA256, synthetic_approval, verify_full
    supplied = os.environ.get("CHUMMER_ANDROID_CURRENT_BUILDER_TWO_GREEN_RECEIPT")
    if not supplied:
        pytest.skip("original current hosted receipt required; no operational approval is inferred")
    path = Path(supplied)
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == ORIGINAL_RECEIPT_SHA256
    verifier = exact_current_android.VERIFY
    signed, now = synthetic_approval(tmp_path, monkeypatch, raw, json.loads(raw), verifier)
    result = verify_full(verifier, exact_current_android.ROOT, path, signed, now)
    assert result["receiptSha256"] == ORIGINAL_RECEIPT_SHA256
    assert result["sourceCommit"] == "d4e9116d5bcdf12a51dec6490bf47b97ed143134"
    assert result["publicationAuthorized"] is False and result["googlePlayUploadAuthorized"] is False
    assert path.read_bytes() == raw
