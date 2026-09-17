from __future__ import annotations

import base64
from copy import deepcopy
from datetime import UTC, datetime
import hashlib
import importlib.util
import json
import marshal
import os
from pathlib import Path
import stat
import struct
import subprocess
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/android_preview12_external_rebuilder.py"
LOCK = ROOT / "config/release/android-preview12-external-rebuilder.lock.json"


def load_module():
    spec = importlib.util.spec_from_file_location("android_preview12_external_rebuilder", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def protected_file(path: Path, raw: bytes) -> Path:
    path.write_bytes(raw)
    path.chmod(0o600)
    return path


def graph(module) -> dict:
    return {
        "contractName": module.SOURCE_GRAPH_CONTRACT,
        "releaseIdentity": {
            "packageId": module.PACKAGE_ID,
            "versionName": module.VERSION_NAME,
            "versionCode": module.VERSION_CODE,
            "intentAuthority": "explicit_build_input",
            "minimumExclusiveVersionCode": 11,
        },
        "repositories": [
            {
                "name": name,
                "role": role,
                "commit": "1" * 40,
                "tree": "2" * 40,
                "tree_sha256": "3" * 64,
                "repository": repository,
            }
            for name, (role, _relative, repository) in module.REPOSITORIES.items()
        ],
        "generatedAtUtc": "2026-09-06T00:00:00Z",
        "publicationAuthorized": False,
    }


def request(module, graph_raw: bytes, unsigned: bytes = b"unsigned") -> dict:
    unsigned_sha = hashlib.sha256(unsigned).hexdigest()
    graph_sha = hashlib.sha256(graph_raw).hexdigest()
    identity = {
        "packageId": module.PACKAGE_ID,
        "versionName": module.VERSION_NAME,
        "versionCode": module.VERSION_CODE,
        "intentAuthority": "explicit_build_input",
        "minimumExclusiveVersionCode": 11,
    }
    required_true = {
        "mustRehashInputs", "mustRebuildAndMatchUnsignedAab", "mustReplayTwoGreenAndSourceGraph",
        "mustBindFullJdkDotnetAndroidSdkClosure", "mustValidatePackageVersionAbiAndProofExclusion",
        "mustVerifyOutputCertificate", "mustEmitDetachedAttestation", "outputMustBindUnsignedAabSha256",
        "outputMustBindSignedAabSha256", "outputMustBindSourceGraphSha256", "outputMustBindReleaseIdentity",
    }
    return {
        "contractName": module.REQUEST_CONTRACT,
        "requestAuthority": "none",
        "releaseIdentity": identity,
        "unsignedAab": {"fileName": f"chummer-android-{module.VERSION_NAME}-unsigned.aab",
                        "sha256": unsigned_sha, "sizeBytes": len(unsigned)},
        "sourceGraph": {"fileName": f"chummer-android-{module.VERSION_NAME}-source-graph.json",
                        "sha256": graph_sha,
                        "sizeBytes": len(graph_raw)},
        "buildSidecar": {"fileName": f"chummer-android-{module.VERSION_NAME}-unsigned.aab.sha256",
                         "sha256": "4" * 64},
        "expectedUploadCertificateSha256": module.UPLOAD_CERTIFICATE_SHA256,
        "requiredExternalSigner": {
            "implementedByThisRepository": False,
            "inputTransport": "authenticated_descriptor_or_immutable_artifact",
            **{name: True for name in required_true},
        },
        "expectedExternalSignerOutput": {
            "contractName": module.EXTERNAL_SIGNER_ATTESTATION_CONTRACT,
            "mustContainDetachedAuthoritySignature": True,
            "mustBindUnsignedAabSha256": unsigned_sha,
            "mustBindSourceGraphSha256": graph_sha,
            "mustBindExpectedUploadCertificateSha256": module.UPLOAD_CERTIFICATE_SHA256,
            "mustBindReleaseIdentity": identity,
            "mustReportSignedAabSha256": True,
            "mustReportFullToolchainClosureSha256": True,
            "publicationAuthorized": False,
            "googlePlayUploadAuthorized": False,
        },
        "signingAuthorized": False,
        "publicationAuthorized": False,
        "googlePlayUploadAuthorized": False,
    }


def test_checked_in_contract_is_dormant_and_prepare_parser_has_no_secret_argument() -> None:
    module = load_module()
    result = module.contract_check(LOCK)
    assert result["status"] == "dormant"
    assert result["signing_performed"] is False
    assert result["google_play_upload_performed"] is False


def synthetic_ready_lock() -> dict:
    lock = json.loads(LOCK.read_text())
    lock["state"] = "ready"
    lock["toolchain"].update(
        builder_image="registry.example.test/team/builder@sha256:" + "a" * 64,
        signer_image="registry.example.test/team/signer@sha256:" + "b" * 64,
        installed_closure_receipt_sha256="c" * 64,
    )
    lock["outputs"]["signed_content_handoff_enabled"] = True
    lock["rebuild"]["enabled"] = True
    lock["reservation"].update(
        configured=True, adapter_sha256="d" * 64, policy_sha256="e" * 64,
        protocol_source="merged_reviewed_fleet_authority",
    )
    for name in ("key_alias", "keystore_secret", "store_password_secret", "key_password_secret"):
        lock["upload_key"][name] = "TEST_ONLY_SYMBOLIC"
    lock["approval_authority"]["private_key_secret"] = "TEST_ONLY_SYMBOLIC"
    return lock


EXPECTED_SDK111_MEASUREMENTS = {
    "dotnet": ("10.0.111", "b35e0cd83e7ca5ac595d712fb9185f9357b123f8c15afad5c285750c284f3dd1", 9258, 4276188988),
    "java": ("17.0.20.1", "85d610b3ad706cd4de8d36d3c8c6fc91000814f5c3f84fefde5ab401c836806a", 246, 332109578),
    "android_sdk": (36, "36.0.0", "54de1ef5b7d26c7a442cbc51078c105d31ac4b73f58469404c3e04d7c7a55e09", 11523, 314037662),
}
OBSERVED_BUILDER_IMAGE = (
    "ghcr.io/archonmegalon/chummer-android-builder@sha256:"
    "5298279ccc96316c546d7bebe00af639e38c22bdac081a980ba10e7dc965e40a"
)
OBSERVED_INSTALLED_INVENTORY_SHA256 = "3a37e627299076065f5881be6e157dd1887f3428dfe2a698ffc8cf4e465ad330"
CURRENT_BUILDER_PUBLIC_BINDING = {
    "key_id": "fleet-release-builder-2026-09",
    "role": "android_internal_release_builder",
    "scope": "android_internal_release_artifact_binding",
    "public_key_path": "eng/trusted-release-builders/fleet-release-builder-2026-09.public.pem",
    "public_key_sha256": "ef44c5b7fcadaf0f115b5f0e0e7b1a65edb322bb002faf980acb654a5db8caaf",
    "public_key_spki_sha256": "41b44078d037fafd85b091b967959f77a7a4aa9f160d03749fa49889a8b1b156",
    "private_key_secret": "ANDROID_PREVIEW12_RELEASE_BUILDER_ED25519_PRIVATE_KEY_PKCS8_B64",
    "rotation_requires_android_merge_and_requalification": True,
}
CURRENT_UPLOAD_BINDINGS = {
    "key_alias": "chummer-upload",
    "keystore_secret": "ANDROID_PREVIEW12_UPLOAD_KEYSTORE_B64",
    "store_password_secret": "ANDROID_PREVIEW12_KEYSTORE_PASSWORD",
    "key_password_secret": "ANDROID_PREVIEW12_KEY_PASSWORD",
}
REMAINING_SIGNER_BLOCKERS = [
    "private immutable signed-content handoff is not configured",
    "external rebuilder lock is dormant",
    "independent rebuild is disabled or weakened",
    "reviewed durable approval-ledger adapter is not configured",
]


def test_checked_in_builder_public_binding_is_current_without_credential_activation() -> None:
    module = load_module()
    lock, raw = module.load_lock(LOCK)
    assert lock["approval_authority"] == CURRENT_BUILDER_PUBLIC_BINDING
    assert lock["android_authority"]["commit"] == "5732c7803c934a6eeb02ab8dbe474e5ea9703755"
    assert lock["android_authority"]["tree"] == "103ff9fe1f4feba5d6134376191fcd9b03472351"
    assert lock["state"] == "dormant" and lock["rebuild"]["enabled"] is False
    assert lock["reservation"]["configured"] is False
    assert lock["toolchain"]["signer_image"] == OBSERVED_BUILDER_IMAGE
    assert all(lock["outputs"][name] is False for name in (
        "signed_content_handoff_enabled", "publication_authorized", "google_play_upload_authorized",
    ))
    assert module.validate_lock(lock, raw) == REMAINING_SIGNER_BLOCKERS
    assert module.validate_unsigned_rebuild_lock(lock, raw) == [
        "external rebuilder lock is dormant", "independent rebuild is disabled or weakened",
    ]


def test_sdk111_toolchain_tuple_is_exact_and_checked_in_lock_stays_unusable() -> None:
    module = load_module()
    lock, raw = module.load_lock(LOCK)
    errors = module.validate_unsigned_rebuild_lock(lock, raw)
    assert errors == ["external rebuilder lock is dormant", "independent rebuild is disabled or weakened"]
    assert lock["toolchain"]["builder_image"] == OBSERVED_BUILDER_IMAGE
    assert lock["toolchain"]["installed_closure_receipt_sha256"] == OBSERVED_INSTALLED_INVENTORY_SHA256

    ready = synthetic_ready_lock()
    assert (ready["toolchain"]["dotnet"]["version"], ready["toolchain"]["dotnet"]["tree_sha256"],
            ready["toolchain"]["dotnet"]["file_count"], ready["toolchain"]["dotnet"]["size_bytes"]) == EXPECTED_SDK111_MEASUREMENTS["dotnet"]
    assert (ready["toolchain"]["java"]["version"], ready["toolchain"]["java"]["tree_sha256"],
            ready["toolchain"]["java"]["file_count"], ready["toolchain"]["java"]["size_bytes"]) == EXPECTED_SDK111_MEASUREMENTS["java"]
    assert (ready["toolchain"]["android_sdk"]["api_level"], ready["toolchain"]["android_sdk"]["build_tools_version"],
            ready["toolchain"]["android_sdk"]["tree_sha256"], ready["toolchain"]["android_sdk"]["file_count"],
            ready["toolchain"]["android_sdk"]["size_bytes"]) == EXPECTED_SDK111_MEASUREMENTS["android_sdk"]
    original = deepcopy(ready)
    assert module.validate_lock(ready, json.dumps(ready).encode(), ready["toolchain"]["builder_image"]) == []
    assert ready == original


def test_observed_public_pins_remove_only_two_configuration_blockers() -> None:
    module = load_module()
    lock, raw = module.load_lock(LOCK)
    original = deepcopy(lock)
    unpinned = deepcopy(lock)
    unpinned["toolchain"].update(builder_image=None, installed_closure_receipt_sha256=None)
    remaining = module.validate_lock(lock, raw)
    before = module.validate_lock(unpinned, json.dumps(unpinned).encode())
    assert [error for error in before if error not in remaining] == [
        "toolchain.builder_image is not one digest-pinned OCI repository",
        "toolchain.installed_closure_receipt_sha256 is not a lowercase SHA-256",
    ]
    assert remaining == [error for error in before if error in remaining]
    assert lock["state"] == "dormant" and lock["rebuild"]["enabled"] is False
    assert lock["toolchain"]["signer_image"] == OBSERVED_BUILDER_IMAGE
    assert lock["reservation"]["configured"] is False
    assert lock["reservation"]["adapter_sha256"] is None
    assert lock["approval_authority"] == CURRENT_BUILDER_PUBLIC_BINDING
    assert {name: lock["upload_key"][name] for name in CURRENT_UPLOAD_BINDINGS} == CURRENT_UPLOAD_BINDINGS
    assert all(lock["outputs"][name] is False for name in (
        "signed_content_handoff_enabled", "publication_authorized", "google_play_upload_authorized",
    ))
    result = module.contract_check(LOCK)
    assert result["status"] == "dormant"
    assert result["blockers"] == remaining
    assert all(result[name] is False for name in (
        "signing_performed", "publication_performed", "google_play_upload_performed",
    ))
    assert lock == original


SELECTED_SIGNER_INPUTS = [
    ("toolchain", "signer_image", OBSERVED_BUILDER_IMAGE,
     "toolchain.signer_image is not one digest-pinned OCI repository"),
    *[("upload_key", name, value, f"upload_key.{name} is not configured")
      for name, value in CURRENT_UPLOAD_BINDINGS.items()],
    ("approval_authority", "private_key_secret", CURRENT_BUILDER_PUBLIC_BINDING["private_key_secret"],
     "approval attestation private-key secret is not configured"),
]


def test_selected_signer_inputs_remove_only_six_missing_input_blockers() -> None:
    module = load_module()
    lock, raw = module.load_lock(LOCK)
    original = deepcopy(lock)
    unselected = deepcopy(lock)
    for row, field, value, _error in SELECTED_SIGNER_INPUTS:
        assert lock[row][field] == value
        unselected[row][field] = None
    remaining = module.validate_lock(lock, raw)
    before = module.validate_lock(unselected, json.dumps(unselected).encode())
    assert remaining == REMAINING_SIGNER_BLOCKERS
    assert before == remaining + [item[3] for item in SELECTED_SIGNER_INPUTS]
    assert lock["reservation"]["configured"] is False
    assert lock["reservation"]["adapter_sha256"] is None
    assert lock["state"] == "dormant" and lock["rebuild"]["enabled"] is False
    assert all(lock["outputs"][name] is False for name in (
        "signed_content_handoff_enabled", "publication_authorized", "google_play_upload_authorized",
    ))
    result = module.contract_check(LOCK)
    assert result["status"] == "dormant" and result["blockers"] == remaining
    assert all(result[name] is False for name in (
        "signing_performed", "publication_performed", "google_play_upload_performed",
    ))
    assert lock == original


@pytest.mark.parametrize(("row", "field", "value", "error"), SELECTED_SIGNER_INPUTS)
def test_each_selected_signer_input_remains_required(row, field, value, error) -> None:
    module = load_module()
    lock, _ = module.load_lock(LOCK)
    assert lock[row][field] == value
    lock[row][field] = None
    assert module.validate_lock(lock, json.dumps(lock).encode()) == REMAINING_SIGNER_BLOCKERS + [error]


@pytest.mark.parametrize(("field", "value"), [
    ("builder_runs_in_separate_job", False), ("builder_credential_mounts_allowed", True),
])
def test_same_image_selection_never_relaxes_builder_isolation(field, value) -> None:
    module = load_module()
    lock = synthetic_ready_lock()
    lock["toolchain"]["signer_image"] = lock["toolchain"]["builder_image"]
    # This checks configuration compatibility only, not authenticated runtime.
    assert module.validate_lock(lock, json.dumps(lock).encode()) == []
    lock["rebuild"][field] = value
    assert module.validate_lock(lock, json.dumps(lock).encode()) == [
        "independent rebuild is disabled or weakened",
    ]


@pytest.mark.parametrize(("state", "enabled", "expected"), [
    ("dormant", False, ["external rebuilder lock is dormant", "independent rebuild is disabled or weakened"]),
    ("ready", False, ["independent rebuild is disabled or weakened"]),
    ("dormant", True, ["external rebuilder lock is dormant"]),
])
def test_observed_public_pins_cannot_bypass_unsigned_activation(state, enabled, expected) -> None:
    module = load_module()
    lock, _ = module.load_lock(LOCK)
    lock["state"], lock["rebuild"]["enabled"] = state, enabled
    assert module.validate_unsigned_rebuild_lock(
        lock, json.dumps(lock).encode(), OBSERVED_BUILDER_IMAGE,
    ) == expected


def test_observed_public_builder_pin_rejects_a_different_reported_image() -> None:
    module = load_module()
    lock, raw = module.load_lock(LOCK)
    assert module.validate_unsigned_rebuild_lock(lock, raw, "builder@sha256:" + "0" * 64) == [
        "external rebuilder lock is dormant", "independent rebuild is disabled or weakened",
        "reported builder image differs from lock",
    ]


@pytest.mark.parametrize(("row", "field", "value"), [
    (row, "file_count", value)
    for row, count in (("dotnet", 9258), ("java", 246), ("android_sdk", 11523))
    for value in (float(count), True, str(count), count - 1, count + 1)
] + [
    (row, "size_bytes", value)
    for row, size in (("dotnet", 4276188988), ("java", 332109578), ("android_sdk", 314037662))
    for value in (float(size), True, str(size), size - 1, size + 1)
] + [
    (row, "tree_sha256", int("5" * 64))
    for row in ("dotnet", "java", "android_sdk")
] + [
    ("dotnet", "version", "10.0.110"),
    ("dotnet", "file_count", 8899),
    ("java", "file_count", 454),
    ("android_sdk", "file_count", 11670),
    ("dotnet", "version", 10.0),
    ("dotnet", "version", True),
    ("java", "version", 17.0201),
    ("java", "version", None),
    ("android_sdk", "api_level", 36.0),
    ("android_sdk", "api_level", True),
    ("android_sdk", "api_level", "36"),
    ("android_sdk", "build_tools_version", 36.0),
    ("android_sdk", "build_tools_version", True),
    ("android_sdk", "build_tools_version", None),
    ("java", "tree_sha256", True),
    ("android_sdk", "tree_sha256", ["5" * 64]),
])
def test_sdk111_toolchain_tuple_drift_fails_closed(row, field, value) -> None:
    module = load_module()
    lock = synthetic_ready_lock()
    lock["toolchain"][row][field] = value
    errors = module.validate_lock(lock, json.dumps(lock).encode(), lock["toolchain"]["builder_image"])
    assert any("closure is not exact" in error for error in errors)


def test_prepare_parser_help_contains_no_signing_secret(monkeypatch, capsys) -> None:
    module = load_module()
    with pytest.raises(SystemExit) as stopped:
        module._parser().parse_args(["--lock", str(LOCK), "prepare-rebuild", "--help"])
    assert stopped.value.code == 0
    help_text = capsys.readouterr().out.lower()
    assert all(word not in help_text for word in ("keystore", "password", "private-key", "token"))


def test_request_is_closed_world_and_binds_old_upload_identity(tmp_path: Path) -> None:
    module = load_module()
    tmp_path.chmod(0o700)
    graph_raw = (json.dumps(graph(module), sort_keys=True) + "\n").encode()
    graph_path = protected_file(tmp_path / "graph.json", graph_raw)
    value = request(module, graph_raw)
    request_path = protected_file(tmp_path / "request.json", (json.dumps(value) + "\n").encode())
    parsed, parsed_graph = module.validate_external_request(request_path, graph_path)
    assert parsed["expectedUploadCertificateSha256"] == module.UPLOAD_CERTIFICATE_SHA256
    assert parsed_graph["releaseIdentity"]["versionCode"] == 12

    for mutate in (
        lambda item: item["requiredExternalSigner"].update(extra=True),
        lambda item: item["expectedExternalSignerOutput"].update(extra=True),
        lambda item: item.update(expectedUploadCertificateSha256="0" * 64),
    ):
        hostile = deepcopy(value)
        mutate(hostile)
        hostile_path = protected_file(tmp_path / f"hostile-{len(list(tmp_path.iterdir()))}.json",
                                      json.dumps(hostile).encode())
        with pytest.raises(module.RebuilderError):
            module.validate_external_request(hostile_path, graph_path)


def test_source_graph_rejects_stale_release_and_repository_authority() -> None:
    module = load_module()
    stale_release = graph(module)
    stale_release["releaseIdentity"]["versionCode"] = 11
    with pytest.raises(module.RebuilderError, match="not Preview12"):
        module.validate_source_graph(stale_release)

    stale_repository = graph(module)
    stale_repository["repositories"][0]["commit"] = "f" * 39
    with pytest.raises(module.RebuilderError, match="40-character"):
        module.validate_source_graph(stale_repository)


def test_online_checkout_is_full_history_unfiltered_and_cleans_up_on_failure(tmp_path: Path) -> None:
    module = load_module()
    origin = tmp_path / "origin"
    origin.mkdir()
    git_environment = {
        "PATH": "/usr/bin:/bin",
        "LANG": "C",
        "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_ASKPASS": "/bin/false",
    }

    def git(*args: str, check: bool = True):
        return subprocess.run(
            ["/usr/bin/git", "-c", "core.hooksPath=/dev/null", "-c", "init.templateDir=",
             "-c", "commit.gpgSign=false", *args],
            check=check, capture_output=True, text=True, env=git_environment,
        )

    git("init", "--quiet", str(origin))
    git("-C", str(origin), "config", "user.name", "fixture")
    git("-C", str(origin), "config", "user.email", "fixture@example.invalid")
    (origin / "ancestor-only.txt").write_text("ancestor\n")
    git("-C", str(origin), "add", ".")
    git("-C", str(origin), "commit", "--quiet", "-m", "ancestor")
    ancestor = git("-C", str(origin), "rev-parse", "HEAD").stdout.strip()
    (origin / "ancestor-only.txt").unlink()
    (origin / "head-only.txt").write_text("head\n")
    git("-C", str(origin), "add", ".")
    git("-C", str(origin), "commit", "--quiet", "-m", "head")
    head = git("-C", str(origin), "rev-parse", "HEAD").stdout.strip()
    tree = git("-C", str(origin), "rev-parse", "HEAD^{tree}").stdout.strip()
    listing = git("-C", str(origin), "ls-tree", "-r", "-z", "--full-tree", "HEAD").stdout.encode()
    local_url = str(origin)
    monkeypatch_repositories = {
        name: (role, relative, local_url)
        for name, (role, relative, _repository) in module.REPOSITORIES.items()
    }
    module.REPOSITORIES = monkeypatch_repositories
    value = graph(module)
    for row in value["repositories"]:
        row.update(commit=head, tree=tree, tree_sha256=hashlib.sha256(listing).hexdigest())
    calls = []

    def controlled(command, **kwargs):
        calls.append(list(command))
        cleaned = []
        index = 0
        while index < len(command):
            if command[index:index + 2] in (["-c", "protocol.allow=never"], ["-c", "protocol.https.allow=always"]):
                index += 2
            else:
                cleaned.append(command[index])
                index += 1
        return subprocess.run(cleaned, **kwargs)

    roots = module.checkout_source_graph(value, tmp_path / "checkout", runner=controlled, timeout=30)
    assert len(roots) == len(module.REPOSITORIES) == 8
    fetches = [command for command in calls if "fetch" in command]
    assert len(fetches) == 8
    assert all(not any("filter" in arg or "depth" in arg for arg in command) for command in fetches)
    for root in roots.values():
        module._preserved_git_storage(root, local_url)
        assert git("-C", str(root), "cat-file", "-e", f"{ancestor}:ancestor-only.txt").returncode == 0
        assert git("-C", str(root), "show", f"{ancestor}:ancestor-only.txt").stdout == "ancestor\n"
        assert git("-C", str(root), "cat-file", "-e", f"{head}:ancestor-only.txt", check=False).returncode != 0
    failed = tmp_path / "failed-checkout"

    def fail_checkout(command, **kwargs):
        if "checkout" in command:
            return subprocess.CompletedProcess(command, 1, "", "")
        return controlled(command, **kwargs)

    with pytest.raises(module.RebuilderError):
        module.checkout_source_graph(value, failed, runner=fail_checkout, timeout=30)
    assert not failed.exists()


def test_duplicate_json_key_and_symlink_fail_closed(tmp_path: Path) -> None:
    module = load_module()
    tmp_path.chmod(0o700)
    duplicate = protected_file(tmp_path / "duplicate.json", b'{"contract_name":"a","contract_name":"b"}')
    with pytest.raises(module.RebuilderError, match="duplicate"):
        module._json_file(duplicate, "duplicate", 1024, owner_only=True)
    link = tmp_path / "link.json"
    link.symlink_to(duplicate)
    with pytest.raises(module.RebuilderError):
        module._json_file(link.absolute(), "symlink", 1024)


def test_rebuild_mismatch_and_stale_toolchain_fail_closed(tmp_path: Path, monkeypatch) -> None:
    module = load_module()
    tmp_path.chmod(0o700)
    candidate = protected_file(tmp_path / "candidate.aab", b"different")
    with pytest.raises(module.RebuilderError, match="differs"):
        module.require_rebuild_match(candidate, {"unsignedAab": {"sha256": "0" * 64, "sizeBytes": 9}}, 1024)

    lock = json.loads(LOCK.read_text())
    roots = [tmp_path / name for name in ("dotnet", "java", "sdk")]
    for root in roots:
        root.mkdir()
    monkeypatch.setattr(module, "_tree_digest", lambda _root, _label: ("0" * 64, 1, 1))
    with pytest.raises(module.RebuilderError, match="differs from lock"):
        module.verify_toolchain(
            lock, *roots, tmp_path / "bundletool.jar", tmp_path / "toolchain.json", "builder@sha256:test"
        )


def test_auxiliary_toolchain_binds_bundletool_receipt_and_both_images(tmp_path: Path) -> None:
    module = load_module()
    tmp_path.chmod(0o700)
    bundletool = protected_file(tmp_path / "bundletool.jar", b"bundletool")
    receipt = protected_file(tmp_path / "toolchain-authority.json", b'{"authority":true}\n')
    lock = json.loads(LOCK.read_text())
    lock["toolchain"].update({
        "bundletool_sha256": hashlib.sha256(bundletool.read_bytes()).hexdigest(),
        "installed_closure_receipt_sha256": hashlib.sha256(receipt.read_bytes()).hexdigest(),
        "builder_image": "builder@sha256:qualified",
        "signer_image": "signer@sha256:qualified",
    })
    bound = module._bind_auxiliary_toolchain(
        lock, bundletool, receipt, "builder@sha256:qualified"
    )
    assert bound == {
        "bundletoolSha256": hashlib.sha256(bundletool.read_bytes()).hexdigest(),
        "installedClosureReceiptSha256": hashlib.sha256(receipt.read_bytes()).hexdigest(),
        "reportedBuilderImage": "builder@sha256:qualified",
        "plannedSignerImage": "signer@sha256:qualified",
        "builderExecutionProvenanceAuthenticated": False,
        "protectedSignerRuntimeVerified": False,
    }
    stale = protected_file(tmp_path / "stale-bundletool.jar", b"stale")
    with pytest.raises(module.RebuilderError, match="bundletool differs"):
        module._bind_auxiliary_toolchain(lock, stale, receipt, "builder@sha256:qualified")
    with pytest.raises(module.RebuilderError, match="builder image differs"):
        module._bind_auxiliary_toolchain(lock, bundletool, receipt, "builder@sha256:wrong")


def test_android_v2_uses_consumer_pretty_bytes_and_rejects_proof_contamination(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_module()
    tmp_path.chmod(0o700)
    files = [protected_file(tmp_path / name, name.encode()) for name in
             ("signed.aab", "graph.json", "sidecar", "receipt.json", "approval.json", "owner.key")]
    signed, graph_path, sidecar, receipt, approval, owner_key = files
    unsigned = {"contractName": module.ANDROID_ATTESTATION_CONTRACT, "challengeNonce": "a" * 64,
                "keyId": module.BUILDER_KEY_IDS[0]}
    fake = SimpleNamespace(
        ROOT=tmp_path,
        _fleet_builder_key_id=module.BUILDER_KEY_IDS[0],
        _fleet_builder_selection="qualified-legacy",  # Modeled loader result, not custody.
        _fleet_expected_spki_sha256="b" * 64,
        _artifact_claims=lambda *_: {"graph": {"releaseIdentity": {
            "packageId": module.PACKAGE_ID, "versionName": module.VERSION_NAME, "versionCode": 12
        }}},
        VERIFY=SimpleNamespace(
            verify_release_eligibility=lambda *_args, **_kwargs: {"eligible": True},
            _canonical_json_bytes=lambda value: module._canonical_json(value),
        ),
        _validate_validation_claims=lambda value: value,
        _unsigned=lambda *_: dict(unsigned),
        _pretty=lambda value: module._pretty_json(value),
        verify=lambda path, *_: json.loads(path.read_text()),
    )
    monkeypatch.setattr(module, "_owner_key_matches", lambda *_: None)
    runner = lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, b"x" * 64, b"")
    output = tmp_path / "attestation.json"
    value = module.android_v2_attestation(
        fake, signed, graph_path, sidecar, receipt, approval, {"status": "pass"}, owner_key, output,
        runner=runner, now=datetime(2026, 9, 6, tzinfo=UTC), nonce="c" * 64,
    )
    assert output.read_bytes() == module._pretty_json(value)
    assert output.read_bytes().endswith(b"\n") and not output.read_bytes().endswith(b"\n\n")

    fake._validate_validation_claims = lambda _value: (_ for _ in ()).throw(ValueError("proof contamination"))
    with pytest.raises(ValueError, match="proof contamination"):
        module.android_v2_attestation(
            fake, signed, graph_path, sidecar, receipt, approval, {"proof": True}, owner_key,
            tmp_path / "rejected.json", runner=runner,
        )
    assert not (tmp_path / "rejected.json").exists()


def test_external_v1_is_separate_from_android_v2_and_redacts_tool_failure(tmp_path: Path, monkeypatch) -> None:
    module = load_module()
    tmp_path.chmod(0o700)
    graph_raw = b'{"graph":true}\n'
    v2 = protected_file(tmp_path / "v2.json", b'{"contractName":"chummer.android.release-build-attestation/v2"}\n')
    key = protected_file(tmp_path / "owner.key", b"placeholder-not-a-real-key")
    req = request(module, graph_raw)
    rebuilt = {"sha256": req["unsignedAab"]["sha256"], "sizeBytes": req["unsignedAab"]["sizeBytes"]}
    signed = {"sha256": "5" * 64, "sizeBytes": 42,
              "uploadCertificateSha256": module.UPLOAD_CERTIFICATE_SHA256}
    monkeypatch.setattr(module, "_owner_key_matches", lambda *_: None)
    runner = lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, b"s" * 64, b"")
    output = tmp_path / "external-v1.json"
    protected_toolchain = {
        "closureSha256": "6" * 64,
        "builderExecutionProvenanceAuthenticated": True,
        "protectedSignerRuntimeVerified": True,
    }
    value = module.external_signer_attestation(
        req, rebuilt, signed, graph_raw, protected_toolchain, v2, key,
        {"key_id": "future-qualified-key", "role": "android_internal_release_builder",
         "scope": "android_internal_release_artifact_binding", "public_key_spki_sha256": "7" * 64},
        output, runner=runner, now=datetime(2026, 9, 6, tzinfo=UTC), nonce="8" * 64,
    )
    assert value["contractName"] == module.EXTERNAL_SIGNER_ATTESTATION_CONTRACT
    assert value["androidReleaseBuildAttestation"]["contractName"] == module.ANDROID_ATTESTATION_CONTRACT
    assert value["keyId"] == "future-qualified-key"
    assert output.read_bytes() == module._pretty_json(value)
    assert value["publicationAuthorized"] is False

    with pytest.raises(module.RebuilderError, match="runtime provenance"):
        module.external_signer_attestation(
            req, rebuilt, signed, graph_raw,
            {**protected_toolchain, "protectedSignerRuntimeVerified": False}, v2, key,
            {"key_id": "future-qualified-key", "role": "android_internal_release_builder",
             "scope": "android_internal_release_artifact_binding", "public_key_spki_sha256": "7" * 64},
            tmp_path / "blocked.json", runner=runner,
        )

    failed = lambda *_args, **_kwargs: subprocess.CompletedProcess([], 1, b"", b"password=leak")
    with pytest.raises(module.RebuilderError) as error:
        module._checked(failed, ["/trusted/tool"], env={}, label="safe label")
    assert "leak" not in str(error.value)


def test_reviewed_ledger_replay_and_lost_response_are_delegated_without_new_protocol() -> None:
    module = load_module()

    class Ledger:
        @staticmethod
        def make_subject(**values):
            return {"contractName": "fleet.android_preview12_approval_ledger_subject.v1", **values}

    class Client:
        def __init__(self, state="reserved"):
            self.state = state

        def reserve(self, subject):
            return {"receipt": {"state": self.state, "subject": subject}}

    subject, reservation = module.reserve_signing_attempt(
        Ledger, Client(), attempt_id="a" * 64, two_green_artifact_id=123,
        two_green_artifact_sha256="b" * 64, two_green_receipt_sha256="c" * 64,
        main_tree="d" * 40, policy_sha256="e" * 64,
    )
    assert reservation["receipt"]["state"] == "reserved"
    assert subject["approval_request_nonce"] == "a" * 64
    with pytest.raises(module.RebuilderError, match="already terminal"):
        module.reserve_signing_attempt(
            Ledger, Client("committed"), attempt_id="a" * 64, two_green_artifact_id=123,
            two_green_artifact_sha256="b" * 64, two_green_receipt_sha256="c" * 64,
            main_tree="d" * 40, policy_sha256="e" * 64,
        )


def test_exact_ledger_commit_accepts_recovered_bytes_and_rejects_mismatch(tmp_path: Path) -> None:
    module = load_module()
    tmp_path.chmod(0o700)
    attestation = protected_file(tmp_path / "external-v1.json", b'{"public":true}\n')
    raw = attestation.read_bytes()

    class RecoveredClient:
        def __init__(self, digest: str):
            self.digest = digest

        def commit(self, _subject, payload, _reservation):
            assert payload == raw
            return {"receipt": {"state": "committed", "approval": {
                "sha256": self.digest, "sizeBytes": len(payload),
                "publicJsonBase64": base64.b64encode(payload).decode("ascii"),
            }}}

    committed = module.commit_signing_attempt(
        RecoveredClient(hashlib.sha256(raw).hexdigest()), {"subject": True},
        {"receipt": {"state": "reserved"}}, attestation,
    )
    assert committed["receipt"]["state"] == "committed"
    with pytest.raises(module.RebuilderError, match="did not commit exact"):
        module.commit_signing_attempt(
            RecoveredClient("0" * 64), {"subject": True},
            {"receipt": {"state": "reserved"}}, attestation,
        )


def test_fleet_audit_rejects_secret_bearing_nested_output(tmp_path: Path) -> None:
    module = load_module()
    tmp_path.chmod(0o700)
    android = protected_file(tmp_path / "android-v2.json", b'{"public":true}\n')
    external = protected_file(tmp_path / "external-v1.json", b'{"public":true}\n')
    lock = json.loads(LOCK.read_text())
    with pytest.raises(module.RebuilderError, match="forbidden secret-bearing"):
        module.fleet_audit(
            lock,
            b"lock",
            b"request",
            b"graph",
            {"sha256": "a" * 64, "sizeBytes": 1, "producerMatch": True},
            {"sha256": "b" * 64, "accessToken": "must-not-escape"},
            {"closureSha256": "c" * 64},
            {
                "receipt": {"state": "committed", "reservationId": "reservation"},
                "receiptSha256": "d" * 64,
                "signature": {"keyId": "ledger"},
            },
            android,
            external,
        )


@pytest.mark.parametrize("prior_bytecode_posture", [False, True])
def test_real_android_v2_consumer_binding_when_exact_checkout_is_available(
    monkeypatch, prior_bytecode_posture: bool,
) -> None:
    module = load_module()
    value = os.environ.get("CHUMMER_ANDROID_CURRENT_ROOT")
    if not value:
        pytest.skip("exact Android consumer checkout not supplied")
    monkeypatch.setattr(module.sys, "dont_write_bytecode", prior_bytecode_posture)
    monkeypatch.setenv("CHUMMER_RELEASE_REPO_ROOT", "caller-posture-must-be-restored")
    # Use the actual checked-in lock and exact consumer. No synthetic key/path
    # override or historical approval default may conceal a stale public pin.
    lock, _ = module.load_lock(LOCK)
    original = deepcopy(lock)
    assert lock["approval_authority"] == CURRENT_BUILDER_PUBLIC_BINDING
    consumer = module.validate_android_consumer(Path(value), lock)
    assert consumer.CONTRACT == module.ANDROID_ATTESTATION_CONTRACT
    assert module._android_builder_selection(consumer) == ("fleet-release-builder-2026-09", True)
    assert consumer._fleet_expected_spki_sha256 == CURRENT_BUILDER_PUBLIC_BINDING["public_key_spki_sha256"]
    assert consumer.VERIFY._release_builder_key("fleet-release-builder-2026-09") == (
        Path(value) / CURRENT_BUILDER_PUBLIC_BINDING["public_key_path"],
        CURRENT_BUILDER_PUBLIC_BINDING["public_key_sha256"],
    )
    assert lock == original
    assert consumer._pretty({"b": 2, "a": 1}) == b'{\n  "a": 1,\n  "b": 2\n}\n'
    assert module.sys.dont_write_bytecode is prior_bytecode_posture
    assert os.environ["CHUMMER_RELEASE_REPO_ROOT"] == "caller-posture-must-be-restored"
    module._validate_android_consumer_inputs(Path(value), json.loads(LOCK.read_text())["android_authority"]["commit"])


@pytest.mark.parametrize("field,value", [
    ("key_id", "local-release-builder-2026"),
    ("key_id", "fleet-release-approver-2026-09"),
    ("key_id", "unregistered-builder"),
    ("public_key_path", "eng/trusted-release-approvers/local-release-builder-2026.public.pem"),
    ("public_key_path", "eng/trusted-release-approvers/fleet-release-approver-2026-09.public.pem"),
    ("public_key_path", "eng/trusted-release-builders/unregistered-builder.public.pem"),
    ("public_key_sha256", "ed1fbe95fc7713bfc6d9d0fea21726c1ba3193533fc2d5523e054ad8fb86184c"),
    ("public_key_sha256", "0" * 64),
    ("public_key_spki_sha256", "c46a4e9a224c8c77a4038bca83f7d9ed66146318d8b5c2c9fc81cd19fdd18ea7"),
    ("public_key_spki_sha256", "0" * 64),
])
def test_real_current_consumer_rejects_stale_or_unregistered_builder_substitutions(field, value):
    configured = os.environ.get("CHUMMER_ANDROID_CURRENT_ROOT")
    if not configured:
        pytest.skip("exact Android consumer checkout not supplied")
    module = load_module()
    lock, _ = module.load_lock(LOCK)
    assert lock["approval_authority"] == CURRENT_BUILDER_PUBLIC_BINDING
    lock["approval_authority"][field] = value
    # Historical complete tuples remain valid for their historical receipts.
    # They cannot be mixed with this current operational selection, and the
    # checked-in-lock assertion above prevents silently reverting the full tuple.
    with pytest.raises(module.RebuilderError, match="builder"):
        module.validate_android_consumer(Path(configured), lock)


# Public RFC 8032 vector 1; these fixtures exercise transport/crypto only, never
# a qualified Android graph, operational private key, or protected-job custody.
RFC_BUILDER_SEED = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
RFC_BUILDER_SPKI = bytes.fromhex(
    "302a300506032b6570032100d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"
)


def synthetic_builder(module, root, key_id=None):
    lock = json.loads(LOCK.read_text())
    key_id = key_id or module.BUILDER_KEY_IDS[1]
    path = root / "eng" / "trusted-release-builders" / (key_id + ".public.pem")
    path.parent.mkdir(parents=True)
    raw = b"-----BEGIN PUBLIC KEY-----\n" + base64.b64encode(RFC_BUILDER_SPKI) + b"\n-----END PUBLIC KEY-----\n"
    protected_file(path, raw)
    lock["approval_authority"].update(
        key_id=key_id, public_key_path=path.relative_to(root).as_posix(),
        public_key_sha256=hashlib.sha256(raw).hexdigest(),
        public_key_spki_sha256=hashlib.sha256(RFC_BUILDER_SPKI).hexdigest(),
    )
    authority = lock["approval_authority"]
    consumer = SimpleNamespace(
        CONTRACT=module.ANDROID_ATTESTATION_CONTRACT,
        EXPECTED_UPLOAD_CERTIFICATE_SHA256=module.UPLOAD_CERTIFICATE_SHA256,
        VERIFY=SimpleNamespace(
            RELEASE_APPROVER_KEY_ID="unrelated-approval-key",
            _release_builder_key=lambda selected: (path, authority["public_key_sha256"])
            if selected == key_id else (_ for _ in ()).throw(ValueError("unknown fixture key")),
        ),
    )
    return lock, consumer, path


@pytest.mark.parametrize("key_id", ["local-release-builder-2026", "fleet-release-builder-2026-09"])
def test_finite_builder_consumer_loads_qualified_fixture_bytes_not_approval_default(tmp_path, key_id):
    module = load_module()
    root = tmp_path / "synthetic-consumer"
    lock, _consumer, public_key = synthetic_builder(module, root, key_id)
    (root / "scripts").mkdir()
    source = (
        "import os\nfrom pathlib import Path\nfrom types import SimpleNamespace\n"
        f"CONTRACT = {module.ANDROID_ATTESTATION_CONTRACT!r}\n"
        f"EXPECTED_UPLOAD_CERTIFICATE_SHA256 = {module.UPLOAD_CERTIFICATE_SHA256!r}\n"
        "ROOT = Path(os.environ['CHUMMER_RELEASE_REPO_ROOT'])\n"
        f"KEY_ID = {key_id!r}\n"
        "def builder(key_id):\n"
        "    if key_id != KEY_ID: raise ValueError('unknown fixture key')\n"
        f"    return (ROOT / {public_key.relative_to(root).as_posix()!r}, "
        f"{lock['approval_authority']['public_key_sha256']!r})\n"
        "VERIFY = SimpleNamespace(RELEASE_APPROVER_KEY_ID='not-the-builder', _release_builder_key=builder)\n"
    ).encode()
    for name in ("build_script", "attestation_consumer", "two_green_verifier", "source_graph_verifier"):
        binding = lock["android_authority"][name]
        raw = source if name == "attestation_consumer" else b"# synthetic non-executable fixture\n"
        protected_file(root / binding["path"], raw)
        binding["sha256"] = hashlib.sha256(raw).hexdigest()

    def git(*args):
        return module._git(subprocess.run, ["-C", str(root), *args], timeout=30)

    git("init", "--quiet")
    git("remote", "add", "origin", lock["android_authority"]["repository"])
    git("add", ".")
    git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
        "-c", "commit.gpgSign=false", "commit", "--quiet", "-m", "Synthetic builder API")
    lock["android_authority"].update(commit=git("rev-parse", "HEAD"), tree=git("rev-parse", "HEAD^{tree}"))
    consumer = module.validate_android_consumer(root, lock)
    assert module._android_builder_selection(consumer, lock["approval_authority"]) == (key_id, True)
    assert consumer._fleet_expected_spki_sha256 == hashlib.sha256(RFC_BUILDER_SPKI).hexdigest()
    assert consumer.VERIFY.RELEASE_APPROVER_KEY_ID == "not-the-builder"
    assert json.loads(LOCK.read_text())["state"] == "dormant"


@pytest.mark.parametrize("key_id", [None, True, [], {}, "unknown", "fleet-release-approver-2026-09"])
def test_unknown_builder_rejected_before_selector_or_public_file_read(tmp_path, monkeypatch, key_id):
    module = load_module()
    lock, consumer, _path = synthetic_builder(module, tmp_path)
    lock["approval_authority"]["key_id"] = key_id
    consumer.VERIFY._release_builder_key = lambda *_: pytest.fail("unknown ID reached Android selector")
    monkeypatch.setattr(module, "_stable_bytes", lambda *_: pytest.fail("unknown ID read public bytes"))
    with pytest.raises(module.RebuilderError, match="key ID is not supported"):
        module._bind_android_builder(consumer, tmp_path, lock)
    assert not hasattr(consumer, "_fleet_builder_key_id")


@pytest.mark.parametrize("attack", [
    "missing", "not-callable", "raises-typeerror", "tuple-shape", "string-path",
    "other-path", "other-digest", "spki", "pem", "symlink", "role", "scope",
])
def test_builder_selector_and_public_binding_fail_closed(tmp_path, attack):
    module = load_module()
    lock, consumer, path = synthetic_builder(module, tmp_path)
    authority = lock["approval_authority"]
    calls = []
    if attack == "missing":
        del consumer.VERIFY._release_builder_key
    elif attack == "not-callable":
        consumer.VERIFY._release_builder_key = None
    elif attack == "raises-typeerror":
        def reject(*args):
            calls.append(args)
            raise TypeError("private exception text must not escape")
        consumer.VERIFY._release_builder_key = reject
    elif attack in ("tuple-shape", "string-path", "other-path", "other-digest"):
        selected = {
            "tuple-shape": [path, authority["public_key_sha256"]],
            "string-path": (str(path), authority["public_key_sha256"]),
            "other-path": (path.with_name("other.pem"), authority["public_key_sha256"]),
            "other-digest": (path, "0" * 64),
        }[attack]
        consumer.VERIFY._release_builder_key = lambda _: selected
    elif attack == "spki":
        authority["public_key_spki_sha256"] = "0" * 64
    elif attack == "pem":
        path.write_bytes(b"-----BEGIN PUBLIC KEY-----\n!!!!\n-----END PUBLIC KEY-----\n")
        authority["public_key_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    elif attack == "symlink":
        saved = path.with_suffix(".saved")
        path.rename(saved)
        path.symlink_to(saved)
    else:
        authority[attack] = "approval-only"
    with pytest.raises(module.RebuilderError) as error:
        module._bind_android_builder(consumer, tmp_path, lock)
    assert "private exception" not in str(error.value)
    assert not hasattr(consumer, "_fleet_builder_key_id")
    if attack == "raises-typeerror":
        assert calls == [(module.BUILDER_KEY_IDS[1],)]  # No default-key retry.


@pytest.mark.parametrize("field", ["commit", "tree", "path", "sha256", "key_id", "public_key_path", "public_key_sha256", "public_key_spki_sha256"])
def test_legacy_compatibility_requires_exact_historical_binding_before_read(tmp_path, monkeypatch, field):
    module = load_module()
    lock = json.loads(LOCK.read_text())
    if field in ("commit", "tree"):
        lock["android_authority"][field] = "0" * 40
    elif field in ("path", "sha256"):
        lock["android_authority"]["attestation_consumer"][field] = "changed"
    else:
        lock["approval_authority"][field] = "changed"
    consumer = SimpleNamespace(VERIFY=SimpleNamespace(RELEASE_APPROVER_KEY_ID=module.BUILDER_KEY_IDS[0]))
    monkeypatch.setattr(module, "_stable_bytes", lambda *_: pytest.fail("unqualified legacy read public key"))
    with pytest.raises(module.RebuilderError):
        module._bind_android_builder(consumer, tmp_path, lock)


def test_explicit_builder_v2_and_external_v1_use_real_rfc_signatures_without_approval_fallback(tmp_path):
    module = load_module()
    tmp_path.chmod(0o700)
    lock, consumer, public_key = synthetic_builder(module, tmp_path)
    module._bind_android_builder(consumer, tmp_path, lock)
    authority = lock["approval_authority"]
    pkcs8 = bytes.fromhex("302e020100300506032b657004220420") + RFC_BUILDER_SEED
    key = protected_file(tmp_path / "RFC8032-test-only.key", b"-----BEGIN PRIVATE KEY-----\n" +
                         base64.b64encode(pkcs8) + b"\n-----END PRIVATE KEY-----\n")
    files = [protected_file(tmp_path / name, name.encode()) for name in
             ("signed.aab", "graph.json", "sidecar", "receipt.json", "approval.json")]
    signed_aab, graph_path, sidecar, receipt, approval = files
    calls = []

    def verify_signature(unsigned, signature, *, label, builder_key_id):
        # Deliberately minimal synthetic consumer, with actual RFC Ed25519 crypto.
        assert builder_key_id == authority["key_id"] == unsigned["keyId"]
        calls.append((label, builder_key_id))
        message = protected_file(tmp_path / "verify-payload", module._canonical_json(unsigned))
        sig = protected_file(tmp_path / "verify-signature", base64.b64decode(signature, validate=True))
        result = subprocess.run(["/usr/bin/openssl", "pkeyutl", "-verify", "-pubin", "-inkey", str(public_key),
                                 "-rawin", "-in", str(message), "-sigfile", str(sig)],
                                capture_output=True, timeout=10, env={"PATH": "/usr/bin:/bin"})
        if result.returncode:
            raise ValueError("fixture signature rejected")

    def verify_v2(path, *_):
        value = json.loads(path.read_bytes())
        signature = value.pop("signatureBase64")
        verify_signature(value, signature, label="Android v2 fixture", builder_key_id=value["keyId"])

    def unsigned(_claims, _qualification, _validation, generated, nonce, *, key_id):
        return {"contractName": module.ANDROID_ATTESTATION_CONTRACT, "keyId": key_id,
                "generatedAtUtc": generated, "challengeNonce": nonce, "testOnly": True}

    consumer.ROOT = tmp_path
    consumer._artifact_claims = lambda *_: {"graph": {"releaseIdentity": {"versionName": module.VERSION_NAME, "versionCode": 12}}}
    consumer.VERIFY.verify_release_eligibility = lambda *_args, **_kwargs: {"testOnly": True}
    consumer.VERIFY._canonical_json_bytes = module._canonical_json
    consumer.VERIFY._verify_ed25519_signature = verify_signature
    consumer._validate_validation_claims = lambda value: value
    consumer._unsigned, consumer._pretty, consumer.verify = unsigned, module._pretty_json, verify_v2
    v2 = tmp_path / "v2.json"
    module.android_v2_attestation(consumer, signed_aab, graph_path, sidecar, receipt, approval, {}, key, v2)
    graph_raw = graph_path.read_bytes()
    req = request(module, graph_raw)
    rebuilt = {"sha256": req["unsignedAab"]["sha256"], "sizeBytes": req["unsignedAab"]["sizeBytes"]}
    signed = {"sha256": hashlib.sha256(signed_aab.read_bytes()).hexdigest(), "sizeBytes": signed_aab.stat().st_size,
              "uploadCertificateSha256": module.UPLOAD_CERTIFICATE_SHA256}
    toolchain = {"builderExecutionProvenanceAuthenticated": True, "protectedSignerRuntimeVerified": True,
                 "closureSha256": "a" * 64}  # Explicitly modeled, not an execution receipt.
    v1 = tmp_path / "v1.json"
    module.external_signer_attestation(req, rebuilt, signed, graph_raw, toolchain, v2, key, authority, v1)
    module.validate_external_signer_attestation(consumer, v1, req, rebuilt, signed, graph_raw, toolchain, v2, authority)
    assert calls == [("Android v2 fixture", authority["key_id"]), ("external signer v1", authority["key_id"])]
    value = json.loads(v1.read_bytes())
    value["signatureBase64"] = base64.b64encode(bytes(64)).decode()
    v1.write_bytes(module._pretty_json(value))
    with pytest.raises(module.RebuilderError, match="detached signature is invalid"):
        module.validate_external_signer_attestation(consumer, v1, req, rebuilt, signed, graph_raw, toolchain, v2, authority)
    assert len(calls) == 3  # A failing explicit verification is never retried.


@pytest.mark.parametrize("attack", ["wrong-returned-id", "old-call-signature"])
def test_explicit_v2_materializer_cannot_downgrade_or_retry_before_private_key(tmp_path, monkeypatch, attack):
    module = load_module()
    lock, consumer, _ = synthetic_builder(module, tmp_path)
    module._bind_android_builder(consumer, tmp_path, lock)
    consumer.ROOT = tmp_path
    consumer._artifact_claims = lambda *_: {"graph": {"releaseIdentity": {"versionName": module.VERSION_NAME, "versionCode": 12}}}
    consumer.VERIFY.verify_release_eligibility = lambda *_args, **_kwargs: {}
    consumer._validate_validation_claims = lambda value: value
    calls = []
    def wrong_id(*args, **kwargs):
        calls.append(kwargs)
        return {"contractName": module.ANDROID_ATTESTATION_CONTRACT, "keyId": module.BUILDER_KEY_IDS[0]}
    def old_signature(*args):
        pytest.fail("explicit v2 incorrectly retried the old signature")
    consumer._unsigned = wrong_id if attack == "wrong-returned-id" else old_signature
    monkeypatch.setattr(module, "_owner_key_matches", lambda *_: pytest.fail("invalid selector reached private key"))
    with pytest.raises(module.RebuilderError if attack == "wrong-returned-id" else TypeError):
        module.android_v2_attestation(consumer, *(tmp_path / name for name in
            ("aab", "graph", "sidecar", "receipt", "approval")), {}, tmp_path / "private", tmp_path / "out")
    assert calls == ([{"key_id": module.BUILDER_KEY_IDS[1]}] if attack == "wrong-returned-id" else [])
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("tamper", [
    "helper", "staged-helper", "assume-unchanged-helper", "helper-symlink",
    "ignored-bytecode", "untracked-module", "eng-policy", "missing-helper",
])
def test_consumer_rejects_unpinned_import_inputs_before_loading(
    tmp_path: Path, monkeypatch, tamper: str,
) -> None:
    module = load_module()
    root = tmp_path / "consumer"
    root.mkdir()
    scripts = root / "scripts"
    scripts.mkdir()
    (root / "eng").mkdir()
    lock = json.loads(LOCK.read_text())
    authority = lock["android_authority"]
    for name in ("build_script", "attestation_consumer", "two_green_verifier", "source_graph_verifier"):
        binding = authority[name]
        raw = b"# trusted test fixture, never executed\n"
        (root / binding["path"]).write_bytes(raw)
        binding["sha256"] = hashlib.sha256(raw).hexdigest()
    helper = scripts / "verify_release_private_key_hygiene.py"
    helper.write_bytes(b"# transitive helper\n")
    policy = root / "eng" / "api36-proof-environment-authority.json"
    policy.write_bytes(b'{}\n')
    (root / ".gitignore").write_text("__pycache__/\n")

    def git(*args):
        return module._git(subprocess.run, ["-C", str(root), *args], timeout=30)

    git("init", "--quiet")
    git("remote", "add", "origin", authority["repository"])
    git("add", ".")
    git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
        "-c", "commit.gpgSign=false", "commit", "--quiet", "-m", "Test consumer")
    authority["commit"] = git("rev-parse", "HEAD")
    authority["tree"] = git("rev-parse", "HEAD^{tree}")
    if tamper == "assume-unchanged-helper":
        git("update-index", "--assume-unchanged", "scripts/verify_release_private_key_hygiene.py")
    if tamper in ("helper", "staged-helper", "assume-unchanged-helper"):
        helper.write_bytes(b"raise RuntimeError('untrusted helper must not execute')\n")
        if tamper == "staged-helper":
            git("add", str(helper))
    elif tamper == "helper-symlink":
        # Even a symlink to the correct bytes is not the committed regular file.
        target = tmp_path / "helper-copy.py"
        target.write_bytes(helper.read_bytes())
        helper.unlink()
        helper.symlink_to(target)
    elif tamper == "ignored-bytecode":
        cache = scripts / "__pycache__"
        cache.mkdir()
        (cache / "verify_release_private_key_hygiene.cpython-312.pyc").write_bytes(b"untrusted cache")
    elif tamper == "untracked-module":
        (scripts / "unreviewed.py").write_bytes(b"# must not enter import path\n")
    elif tamper == "eng-policy":
        policy.write_bytes(b'{"changed":true}\n')
    elif tamper == "missing-helper":
        helper.unlink()

    def reject_import(*args, **kwargs):
        pytest.fail("unverified Android code reached the Python loader")

    monkeypatch.setattr(module.importlib.util, "spec_from_file_location", reject_import)
    with pytest.raises(module.RebuilderError, match="consumer (input|closure)"):
        module.validate_android_consumer(root, lock)


@pytest.mark.parametrize("cached_input", ["consumer", "transitive-helper"])
def test_consumer_rejects_external_bytecode_cache_before_execution(
    tmp_path: Path, monkeypatch, cached_input: str,
) -> None:
    module = load_module()
    root = tmp_path / "consumer"
    (root / "scripts").mkdir(parents=True)
    (root / "eng").mkdir()
    lock = json.loads(LOCK.read_text())
    authority = lock["android_authority"]
    for name in ("build_script", "attestation_consumer", "two_green_verifier", "source_graph_verifier"):
        (root / authority[name]["path"]).write_bytes(b"# qualified synthetic input\n")
    helper = root / "scripts" / "verify_release_private_key_hygiene.py"
    helper.write_bytes(b"# qualified synthetic transitive helper\n")
    consumer = root / authority["attestation_consumer"]["path"]
    consumer.write_text(
        "import importlib.util\n"
        f"spec = importlib.util.spec_from_file_location('fixture_helper', {str(helper)!r})\n"
        "helper = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(helper)\n"
        "raise AssertionError('fixture source must not execute with an external cache')\n"
    )
    for name in ("build_script", "attestation_consumer", "two_green_verifier", "source_graph_verifier"):
        binding = authority[name]
        binding["sha256"] = hashlib.sha256((root / binding["path"]).read_bytes()).hexdigest()

    def git(*args):
        return module._git(subprocess.run, ["-C", str(root), *args], timeout=30)

    git("init", "--quiet")
    git("remote", "add", "origin", authority["repository"])
    git("add", ".")
    git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
        "-c", "commit.gpgSign=false", "commit", "--quiet", "-m", "Test consumer")
    authority["commit"] = git("rev-parse", "HEAD")
    authority["tree"] = git("rev-parse", "HEAD^{tree}")
    external_cache = tmp_path / "outside-cache"
    monkeypatch.setattr(module.sys, "pycache_prefix", str(external_cache))
    monkeypatch.setattr(module.sys, "dont_write_bytecode", True)
    target = consumer if cached_input == "consumer" else helper
    cache = Path(importlib.util.cache_from_source(str(target)))
    assert cache.is_relative_to(external_cache) and not cache.is_relative_to(root)
    cache.parent.mkdir(parents=True)
    metadata = target.stat()
    # Valid timestamp-mode cache for the unchanged Git-bound source. Only its
    # marshalled code differs; no real signing input or credential is involved.
    poisoned = compile("raise RuntimeError('poisoned external bytecode executed')\n", str(target), "exec")
    header = importlib.util.MAGIC_NUMBER + struct.pack(
        "<III", 0, int(metadata.st_mtime) & 0xffffffff, metadata.st_size & 0xffffffff
    )
    cache.write_bytes(header + marshal.dumps(poisoned))
    module._validate_android_consumer_inputs(root, authority["commit"])
    observed_error = None
    try:
        module.validate_android_consumer(root, lock)
    except Exception as error:
        observed_error = error
    assert isinstance(observed_error, module.RebuilderError), (
        f"protected loader observed {type(observed_error).__name__}: {observed_error}"
    )
    assert "bytecode cache" in str(observed_error)
    assert module.sys.pycache_prefix == str(external_cache)
    assert module.sys.dont_write_bytecode is True
    assert git("status", "--porcelain") == ""


def test_signed_sidecar_is_accepted_by_real_android_consumer_when_available(tmp_path: Path) -> None:
    module = load_module()
    value = os.environ.get("CHUMMER_ANDROID_CURRENT_ROOT")
    if not value:
        pytest.skip("exact Android consumer checkout not supplied")
    tmp_path.chmod(0o700)
    consumer = module.validate_android_consumer(Path(value), json.loads(LOCK.read_text()))
    signed = protected_file(tmp_path / "preview12-signed.aab", b"signed-bytes")
    graph_path = protected_file(tmp_path / "preview12-source-graph.json", b'{"source":true}\n')
    sidecar = tmp_path / "preview12-signed.aab.sha256"
    raw = module.materialize_signed_sidecar(signed, graph_path, sidecar, 1024)
    claims = consumer._sidecar_claims(sidecar, signed, graph_path)
    assert claims["rawSha256"] == hashlib.sha256(raw).hexdigest()
    assert claims[f"artifacts/{signed.name}"] == hashlib.sha256(signed.read_bytes()).hexdigest()


@pytest.mark.parametrize("ancestor_kind", ["trusted-parent", "writable-parent", "nonroot-parent"])
def test_reviewed_ledger_checks_full_runtime_ancestry_before_loading(
    tmp_path: Path, monkeypatch, ancestor_kind: str,
) -> None:
    module = load_module()
    root = tmp_path / "replaceable-parent" / "fleet"
    root.mkdir(parents=True)
    lock = json.loads(LOCK.read_text())
    adapter = root / lock["reservation"]["adapter_path"]
    policy = root / lock["reservation"]["policy_path"]
    for path in (adapter, policy):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"test-only, must not be loaded")
    real_stat = Path.stat

    def observed_stat(path, *args, **kwargs):
        actual = real_stat(path, *args, **kwargs)
        # Model a root-owned runtime underneath an unsafe ancestor. No real
        # ownership or permission change is required on the execution host.
        fields = list(actual)
        fields[4] = 0
        fields[0] = stat.S_IFMT(actual.st_mode) | (0o755 if stat.S_ISDIR(actual.st_mode) else 0o644)
        if path == root.parent:
            if ancestor_kind == "writable-parent":
                fields[0] |= 0o020
            elif ancestor_kind == "nonroot-parent":
                fields[4] = 1001
        return os.stat_result(fields)

    monkeypatch.setattr(Path, "stat", observed_stat)

    class ExpectedReadReached(Exception):
        pass

    def reject_read(*args, **kwargs):
        if ancestor_kind == "trusted-parent":
            raise ExpectedReadReached
        pytest.fail("replaceable protected runtime reached ledger byte loading")

    monkeypatch.setattr(module, "_stable_bytes", reject_read)
    if ancestor_kind == "trusted-parent":
        with pytest.raises(ExpectedReadReached):
            module.load_reviewed_ledger(root, lock, {})
        return
    with pytest.raises(module.RebuilderError, match="ancestry is not immutable root-owned"):
        module.load_reviewed_ledger(root, lock, {})
