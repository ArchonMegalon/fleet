from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/android_preview12_external_rebuilder.py"
LOCK = ROOT / "config/release/android-preview12-external-rebuilder.lock.json"


def load_module():
    spec = importlib.util.spec_from_file_location("preview12_protected_transaction", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def protected_file(path: Path, raw: bytes) -> Path:
    path.write_bytes(raw)
    path.chmod(0o600)
    return path


def source_graph(module, lock) -> dict:
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
                "commit": lock["android_authority"]["commit"] if name == "chummer-android" else "1" * 40,
                "tree": lock["android_authority"]["tree"] if name == "chummer-android" else "2" * 40,
                "tree_sha256": "3" * 64,
                "repository": repository,
            }
            for name, (role, _relative, repository) in module.REPOSITORIES.items()
        ],
        "generatedAtUtc": "2026-09-06T00:00:00Z",
        "publicationAuthorized": False,
    }


def external_request(module, graph_raw: bytes, unsigned: bytes, sidecar_raw: bytes) -> dict:
    identity = {
        "packageId": module.PACKAGE_ID,
        "versionName": module.VERSION_NAME,
        "versionCode": module.VERSION_CODE,
        "intentAuthority": "explicit_build_input",
        "minimumExclusiveVersionCode": 11,
    }
    unsigned_sha = hashlib.sha256(unsigned).hexdigest()
    graph_sha = hashlib.sha256(graph_raw).hexdigest()
    required = {
        "mustRehashInputs", "mustRebuildAndMatchUnsignedAab", "mustReplayTwoGreenAndSourceGraph",
        "mustBindFullJdkDotnetAndroidSdkClosure", "mustValidatePackageVersionAbiAndProofExclusion",
        "mustVerifyOutputCertificate", "mustEmitDetachedAttestation", "outputMustBindUnsignedAabSha256",
        "outputMustBindSignedAabSha256", "outputMustBindSourceGraphSha256", "outputMustBindReleaseIdentity",
    }
    return {
        "contractName": module.REQUEST_CONTRACT,
        "requestAuthority": "none",
        "releaseIdentity": identity,
        "unsignedAab": {
            "fileName": f"chummer-android-{module.VERSION_NAME}-unsigned.aab",
            "sha256": unsigned_sha,
            "sizeBytes": len(unsigned),
        },
        "sourceGraph": {
            "fileName": f"chummer-android-{module.VERSION_NAME}-source-graph.json",
            "sha256": graph_sha,
            "sizeBytes": len(graph_raw),
        },
        "buildSidecar": {
            "fileName": f"chummer-android-{module.VERSION_NAME}-unsigned.aab.sha256",
            "sha256": hashlib.sha256(sidecar_raw).hexdigest(),
        },
        "expectedUploadCertificateSha256": module.UPLOAD_CERTIFICATE_SHA256,
        "requiredExternalSigner": {
            "implementedByThisRepository": False,
            "inputTransport": "authenticated_descriptor_or_immutable_artifact",
            **{name: True for name in required},
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


def fixture(module, tmp_path: Path, events: list[str]):
    tmp_path.chmod(0o700)
    lock = json.loads(LOCK.read_text())
    graph_raw = (json.dumps(source_graph(module, lock), sort_keys=True) + "\n").encode()
    graph_path = protected_file(tmp_path / f"chummer-android-{module.VERSION_NAME}-source-graph.json", graph_raw)
    unsigned_raw = b"independently-rebuilt-unsigned"
    unsigned = protected_file(tmp_path / f"chummer-android-{module.VERSION_NAME}-unsigned.aab", unsigned_raw)
    sidecar_raw = (
        f"{hashlib.sha256(unsigned_raw).hexdigest()}  artifacts/{unsigned.name}\n"
        f"{hashlib.sha256(graph_raw).hexdigest()}  artifacts/{graph_path.name}\n"
    ).encode()
    request_path = protected_file(
        tmp_path / "ANDROID_EXTERNAL_SIGNER_REQUEST.generated.json",
        (json.dumps(external_request(module, graph_raw, unsigned_raw, sidecar_raw), sort_keys=True) + "\n").encode(),
    )
    paths = {
        "unsignedAab": unsigned,
        "sourceGraph": graph_path,
        "buildSidecar": protected_file(tmp_path / f"{unsigned.name}.sha256", sidecar_raw),
        "twoGreenReceipt": protected_file(
            tmp_path / "ANDROID_API36_TWO_GREEN_ELIGIBILITY.generated.json", b'{"eligible":true}\n'
        ),
        "twoGreenApproval": protected_file(
            tmp_path / "ANDROID_API36_TWO_GREEN_RELEASE_APPROVAL.generated.json", b'{"approved":true}\n'
        ),
        "externalSignerRequest": request_path,
    }
    lock["state"] = "ready"
    lock["toolchain"].update({
        "builder_image": "builder@sha256:qualified",
        "signer_image": "signer@sha256:qualified",
        "installed_closure_receipt_sha256": "5" * 64,
    })
    lock["outputs"]["signed_content_handoff_enabled"] = True
    lock["rebuild"]["enabled"] = True
    lock["reservation"].update({
        "configured": True,
        "adapter_sha256": "6" * 64,
        "policy_sha256": "7" * 64,
        "protocol_source": "merged_reviewed_fleet_authority",
    })
    for name in ("key_alias", "keystore_secret", "store_password_secret", "key_password_secret"):
        lock["upload_key"][name] = f"symbolic-{name}"
    lock["approval_authority"]["private_key_secret"] = "symbolic-owner-key"
    lock_raw = b"qualified-lock-bytes"
    toolchain = {
        "platform": lock["toolchain"]["platform"],
        **{
            name: {
                "treeSha256": lock["toolchain"][name]["tree_sha256"],
                "fileCount": lock["toolchain"][name]["file_count"],
                "sizeBytes": lock["toolchain"][name]["size_bytes"],
            }
            for name in ("dotnet", "java", "android_sdk")
        },
        "bundletoolSha256": lock["toolchain"]["bundletool_sha256"],
        "installedClosureReceiptSha256": lock["toolchain"]["installed_closure_receipt_sha256"],
        "reportedBuilderImage": lock["toolchain"]["builder_image"],
        "plannedSignerImage": lock["toolchain"]["signer_image"],
        "builderExecutionProvenanceAuthenticated": False,
        "protectedSignerRuntimeVerified": False,
    }
    toolchain["builderClosureSha256"] = hashlib.sha256(
        module._canonical_json(toolchain)
    ).hexdigest()
    toolchain["builderExecutionProvenanceAuthenticated"] = True
    toolchain["protectedSignerRuntimeVerified"] = True
    toolchain["closureSha256"] = hashlib.sha256(
        module._canonical_json(toolchain)
    ).hexdigest()
    handoff = {
        "contractName": module.REBUILD_HANDOFF_CONTRACT,
        "releaseIdentity": {
            "packageId": module.PACKAGE_ID,
            "versionName": module.VERSION_NAME,
            "versionCode": module.VERSION_CODE,
        },
        "bindings": {
            "lockSha256": hashlib.sha256(lock_raw).hexdigest(),
            "requestSha256": hashlib.sha256(request_path.read_bytes()).hexdigest(),
            "sourceGraphSha256": hashlib.sha256(graph_raw).hexdigest(),
            "unsignedAabSha256": hashlib.sha256(unsigned_raw).hexdigest(),
            "unsignedAabSizeBytes": len(unsigned_raw),
            "twoGreenReceiptSha256": hashlib.sha256(paths["twoGreenReceipt"].read_bytes()).hexdigest(),
            "twoGreenApprovalSha256": hashlib.sha256(paths["twoGreenApproval"].read_bytes()).hexdigest(),
            "toolchainClosureSha256": toolchain["builderClosureSha256"],
            "sourceCommit": lock["android_authority"]["commit"],
            "sourceTree": lock["android_authority"]["tree"],
        },
    }
    provenance = {
        "authorityClass": "authenticated_immutable_workflow_artifact",
        "lockSha256": hashlib.sha256(lock_raw).hexdigest(),
        "artifactClosureSha256": "a" * 64,
        "builderImage": lock["toolchain"]["builder_image"],
        "signerImage": lock["toolchain"]["signer_image"],
        "builderCredentialMountsPresent": False,
        "builderExecutionProvenanceAuthenticated": True,
        "protectedSignerRuntimeVerified": True,
        "consumerBytesRootOwnedImmutable": True,
        "ledgerAdapterBytesRootOwnedImmutable": True,
        "attemptId": "d" * 64,
        "twoGreenArtifactId": 123,
        "twoGreenArtifactSha256": "e" * 64,
    }
    java_root = tmp_path / "java"
    java_root.mkdir()
    lease = module.AuthenticatedRebuildHandoff(
        handoff, paths, toolchain, provenance, java_root,
        lambda: events.append("assert-exact"),
    )
    return lock, lock_raw, lease


def fake_consumer(module, lease, events):
    def claims(aab, graph, sidecar, receipt, approval):
        graph_value = json.loads(graph.read_text())
        android_row = next(row for row in graph_value["repositories"] if row["name"] == "chummer-android")
        return {
            "sourceCommit": android_row["commit"],
            "sourceTree": android_row["tree"],
            "aab": {"fileName": aab.name, "sha256": hashlib.sha256(aab.read_bytes()).hexdigest(),
                    "sizeBytes": aab.stat().st_size},
            "sourceGraph": {"fileName": graph.name, "sha256": hashlib.sha256(graph.read_bytes()).hexdigest(),
                            "sizeBytes": graph.stat().st_size},
            "buildSidecar": {"fileName": sidecar.name,
                             "sha256": hashlib.sha256(sidecar.read_bytes()).hexdigest()},
            "twoGreen": {"receiptSha256": hashlib.sha256(receipt.read_bytes()).hexdigest(),
                         "approvalSha256": hashlib.sha256(approval.read_bytes()).hexdigest()},
            "graph": graph_value,
        }

    def eligibility(receipt, _approval, **_kwargs):
        return {
            "sourceCommit": lease.handoff["bindings"]["sourceCommit"],
            "sourceTree": lease.handoff["bindings"]["sourceTree"],
            "receiptSha256": hashlib.sha256(receipt.read_bytes()).hexdigest(),
            "eligible": True,
            "internalTestingEligible": True,
            "publicationAuthorized": False,
            "googlePlayUploadAuthorized": False,
        }

    return SimpleNamespace(
        CONTRACT=module.ANDROID_ATTESTATION_CONTRACT,
        ROOT=lease.java_root.parent,
        VERIFY=SimpleNamespace(verify_release_eligibility=eligibility),
        _artifact_claims=claims,
        _validate_validation_claims=lambda value: value,
        verify=lambda *_args: events.append("verify-v2"),
    )


def install_fakes(module, monkeypatch, events, lock, lock_raw):
    monkeypatch.setattr(module, "load_lock", lambda _path: (lock, lock_raw))
    monkeypatch.setattr(module, "validate_lock", lambda *_args: [])
    java = lock["toolchain"]["java"]
    monkeypatch.setattr(
        module, "_tree_digest",
        lambda *_args: (java["tree_sha256"], java["file_count"], java["size_bytes"]),
    )

    class Ledger:
        @staticmethod
        def make_subject(**values):
            return values

    class Client:
        state = "reserved"
        fail_commit_once = False
        commit_calls = 0

        def reserve(self, _subject):
            events.append("reserve")
            return {"receipt": {"state": self.state}}

        def commit(self, _subject, raw, _reservation):
            events.append("commit")
            self.commit_calls += 1
            self.state = "committed"
            response = {
                "receipt": {"state": "committed", "reservationId": "rsv_test",
                            "approval": {"sha256": hashlib.sha256(raw).hexdigest(), "sizeBytes": len(raw)}},
                "receiptSha256": "b" * 64,
                "signature": {"algorithm": "Ed25519"},
            }
            if self.fail_commit_once:
                self.fail_commit_once = False
                raise TimeoutError("simulated lost ledger response")
            return response

        def abort(self, *_args):
            events.append("abort")

    client = Client()
    monkeypatch.setattr(
        module, "load_reviewed_ledger",
        lambda *_args: (events.append("load-ledger") or Ledger, client, "c" * 64),
    )
    monkeypatch.setattr(module, "sign_aab", lambda _unsigned, output, *_args, **_kwargs: (
        events.append("sign"), module._write_exclusive(output, b"signed"),
        {"sha256": hashlib.sha256(b"signed").hexdigest(), "sizeBytes": 6,
         "uploadCertificateSha256": module.UPLOAD_CERTIFICATE_SHA256},
    )[-1])
    sidecar = module.materialize_signed_sidecar
    monkeypatch.setattr(module, "materialize_signed_sidecar", lambda *args, **kwargs: (
        events.append("sidecar"), sidecar(*args, **kwargs)
    )[-1])
    monkeypatch.setattr(module, "android_v2_attestation", lambda *args, **kwargs: (
        events.append("android-v2"),
        module._write_exclusive(args[8], b'{"protectedValidation":{"status":"pass"}}\n'),
        {"protectedValidation": {"status": "pass"}}
    )[-1])
    monkeypatch.setattr(module, "external_signer_attestation", lambda *args, **kwargs: (
        events.append("external-v1"), module._write_exclusive(args[8], b'{"v1":true}\n'), {"v1": True}
    )[-1])
    monkeypatch.setattr(
        module, "validate_external_signer_attestation",
        lambda *_args, **_kwargs: events.append("validate-external-v1") or {"status": "pass"},
    )
    return client


def test_reservation_precedes_key_admission_and_all_signing(tmp_path: Path, monkeypatch) -> None:
    module = load_module()
    events: list[str] = []
    lock, lock_raw, lease = fixture(module, tmp_path, events)
    install_fakes(module, monkeypatch, events, lock, lock_raw)
    consumer = fake_consumer(module, lease, events)

    def credentials(*_args):
        events.append("credentials")
        return {name: tmp_path / name for name in ("keystore", "storePassword", "keyPassword", "ownerPrivateKey")}

    result = module.execute_protected_signer_transaction(
        tmp_path / "lock.json", lambda *_: events.append("authenticate") or lease,
        lambda: events.append("consumer") or consumer, tmp_path, {}, credentials,
        lambda **_: events.append("protected-validation") or {"status": "pass"},
        tmp_path / "output", attempt_id="d" * 64,
        two_green_artifact_id=123, two_green_artifact_sha256="e" * 64,
    )
    assert result["status"] == "verified"
    assert events.index("authenticate") < events.index("reserve") < events.index("credentials") < events.index("sign")
    assert events.index("sign") < events.index("sidecar") < events.index("protected-validation")
    assert events.index("protected-validation") < events.index("android-v2") < events.index("external-v1") < events.index("commit")
    assert "abort" not in events


@pytest.mark.parametrize(
    "failure", ["tampered-provenance", "replayed-reservation", "rejected-reservation"]
)
def test_tamper_or_replay_cannot_read_keys_or_sign(tmp_path: Path, monkeypatch, failure: str) -> None:
    module = load_module()
    events: list[str] = []
    lock, lock_raw, lease = fixture(module, tmp_path, events)
    client = install_fakes(module, monkeypatch, events, lock, lock_raw)
    if failure == "tampered-provenance":
        lease.provenance["lockSha256"] = "0" * 64
    elif failure == "replayed-reservation":
        client.state = "committed"
    else:
        client.state = "aborted"
    with pytest.raises(module.RebuilderError):
        module.execute_protected_signer_transaction(
            tmp_path / "lock.json", lambda *_: events.append("authenticate") or lease,
            lambda: events.append("consumer") or fake_consumer(module, lease, events),
            tmp_path, {}, lambda *_: events.append("credentials") or {},
            lambda **_: events.append("protected-validation") or {}, tmp_path / "blocked",
            attempt_id="d" * 64, two_green_artifact_id=123, two_green_artifact_sha256="e" * 64,
        )
    assert "credentials" not in events
    assert "sign" not in events


@pytest.mark.parametrize(
    "failure", ["attempt-id", "artifact-id", "artifact-sha", "request-bytes", "renamed-source"]
)
def test_authenticated_inputs_are_bound_before_reservation_or_keys(
    tmp_path: Path, monkeypatch, failure: str,
) -> None:
    module = load_module()
    events: list[str] = []
    lock, lock_raw, lease = fixture(module, tmp_path, events)
    install_fakes(module, monkeypatch, events, lock, lock_raw)
    attempt_id, artifact_id, artifact_sha = "d" * 64, 123, "e" * 64
    if failure == "attempt-id":
        attempt_id = "f" * 64
    elif failure == "artifact-id":
        artifact_id = 124
    elif failure == "artifact-sha":
        artifact_sha = "f" * 64
    elif failure == "request-bytes":
        lease.paths["externalSignerRequest"].write_bytes(b"{}\n")
    else:
        renamed = protected_file(tmp_path / "renamed-source-graph.json", lease.paths["sourceGraph"].read_bytes())
        lease.paths["sourceGraph"] = renamed

    with pytest.raises(module.RebuilderError):
        module.execute_protected_signer_transaction(
            tmp_path / "lock.json", lambda *_: events.append("authenticate") or lease,
            lambda: events.append("consumer") or fake_consumer(module, lease, events),
            tmp_path, {}, lambda *_: events.append("credentials") or {},
            lambda **_: {"status": "pass"}, tmp_path / "blocked-input",
            attempt_id=attempt_id, two_green_artifact_id=artifact_id,
            two_green_artifact_sha256=artifact_sha,
        )
    assert "reserve" not in events
    assert "credentials" not in events
    assert "sign" not in events


def test_failure_after_reservation_but_before_key_admission_aborts_and_cleans(
    tmp_path: Path, monkeypatch,
) -> None:
    module = load_module()
    events: list[str] = []
    lock, lock_raw, lease = fixture(module, tmp_path, events)
    install_fakes(module, monkeypatch, events, lock, lock_raw)
    monkeypatch.setattr(
        module, "_recovery_write",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("journal unavailable")),
    )
    output = tmp_path / "aborted-output"
    with pytest.raises(OSError, match="journal unavailable"):
        module.execute_protected_signer_transaction(
            tmp_path / "lock.json", lambda *_: lease,
            lambda: fake_consumer(module, lease, events), tmp_path, {},
            lambda *_: events.append("credentials") or {},
            lambda **_: {"status": "pass"}, output,
            attempt_id="d" * 64, two_green_artifact_id=123,
            two_green_artifact_sha256="e" * 64,
        )
    assert "reserve" in events and "abort" in events
    assert "credentials" not in events and "sign" not in events
    assert not module._recovery_path(output, "d" * 64).exists()


@pytest.mark.parametrize(
    "failure", ["lost-commit-ack", "commit-record", "audit", "audit-write", "promotion", "post-promotion"]
)
def test_recovery_preserves_signed_evidence_and_never_replays_signing(
    tmp_path: Path, monkeypatch, failure: str,
) -> None:
    module = load_module()
    events: list[str] = []
    lock, lock_raw, lease = fixture(module, tmp_path, events)
    client = install_fakes(module, monkeypatch, events, lock, lock_raw)
    consumer = fake_consumer(module, lease, events)
    output = tmp_path / "recovered-output"
    recovery = module._recovery_path(output, "d" * 64)

    if failure == "lost-commit-ack":
        client.fail_commit_once = True
    elif failure == "commit-record":
        original = module._write_or_match
        state = {"failed": False}

        def fail_commit_record(path, *args, **kwargs):
            if path.name == "LEDGER_COMMIT.generated.json" and not state["failed"]:
                state["failed"] = True
                raise OSError("commit record unavailable")
            return original(path, *args, **kwargs)

        monkeypatch.setattr(module, "_write_or_match", fail_commit_record)
    elif failure == "audit":
        original = module.fleet_audit
        state = {"failed": False}

        def fail_audit(*args, **kwargs):
            if not state["failed"]:
                state["failed"] = True
                raise OSError("audit materializer unavailable")
            return original(*args, **kwargs)

        monkeypatch.setattr(module, "fleet_audit", fail_audit)
    elif failure == "audit-write":
        original = module._write_or_match
        state = {"failed": False}

        def fail_audit_write(path, *args, **kwargs):
            if path.name.endswith("AUDIT.v3.json") and not state["failed"]:
                state["failed"] = True
                raise OSError("audit write unavailable")
            return original(path, *args, **kwargs)

        monkeypatch.setattr(module, "_write_or_match", fail_audit_write)
    else:
        original_replace = module.os.replace
        state = {"failed": False}

        def fail_promotion(source, destination):
            if Path(source) == recovery and Path(destination) == output and not state["failed"]:
                state["failed"] = True
                if failure == "post-promotion":
                    original_replace(source, destination)
                raise OSError("promotion interrupted")
            return original_replace(source, destination)

        monkeypatch.setattr(module.os, "replace", fail_promotion)

    def credentials(*_args):
        events.append("credentials")
        return {
            name: tmp_path / name
            for name in ("keystore", "storePassword", "keyPassword", "ownerPrivateKey")
        }

    with pytest.raises((OSError, TimeoutError)):
        module.execute_protected_signer_transaction(
            tmp_path / "lock.json", lambda *_: lease, lambda: consumer,
            tmp_path, {}, credentials, lambda **_: {"status": "pass"}, output,
            attempt_id="d" * 64, two_green_artifact_id=123,
            two_green_artifact_sha256="e" * 64,
        )
    evidence_root = output if output.exists() else recovery
    assert evidence_root.is_dir()
    assert (evidence_root / f"chummer-android-{module.VERSION_NAME}-signed.aab").read_bytes() == b"signed"
    assert events.count("sign") == 1

    result = module.reconcile_protected_signer_transaction(
        tmp_path / "lock.json", lambda *_: lease, lambda: consumer,
        tmp_path, {}, lambda **_: {"status": "pass"}, output,
        attempt_id="d" * 64, two_green_artifact_id=123,
        two_green_artifact_sha256="e" * 64,
    )
    assert result["status"] == "verified"
    assert output.is_dir() and not recovery.exists()
    assert (output / f"chummer-android-{module.VERSION_NAME}-signed.aab").read_bytes() == b"signed"
    assert events.count("sign") == 1
    assert events.count("credentials") == 1
    assert client.commit_calls == 2


def test_recovery_rejects_fresh_validation_drift_without_replaying_signing(
    tmp_path: Path, monkeypatch,
) -> None:
    module = load_module()
    events: list[str] = []
    lock, lock_raw, lease = fixture(module, tmp_path, events)
    install_fakes(module, monkeypatch, events, lock, lock_raw)
    consumer = fake_consumer(module, lease, events)
    original_audit = module.fleet_audit
    state = {"failed": False}

    def fail_audit_once(*args, **kwargs):
        if not state["failed"]:
            state["failed"] = True
            raise OSError("audit unavailable")
        return original_audit(*args, **kwargs)

    monkeypatch.setattr(module, "fleet_audit", fail_audit_once)
    output = tmp_path / "validation-drift-output"
    with pytest.raises(OSError):
        module.execute_protected_signer_transaction(
            tmp_path / "lock.json", lambda *_: lease, lambda: consumer,
            tmp_path, {},
            lambda *_: {
                name: tmp_path / name
                for name in ("keystore", "storePassword", "keyPassword", "ownerPrivateKey")
            },
            lambda **_: {"status": "pass"}, output,
            attempt_id="d" * 64, two_green_artifact_id=123,
            two_green_artifact_sha256="e" * 64,
        )
    with pytest.raises(module.RebuilderError, match="fresh protected validation differs"):
        module.reconcile_protected_signer_transaction(
            tmp_path / "lock.json", lambda *_: lease, lambda: consumer,
            tmp_path, {}, lambda **_: {"status": "changed"}, output,
            attempt_id="d" * 64, two_green_artifact_id=123,
            two_green_artifact_sha256="e" * 64,
        )
    assert events.count("sign") == 1
    assert module._recovery_path(output, "d" * 64).is_dir()


def test_external_v1_validator_binds_claims_and_detached_signature(
    tmp_path: Path,
) -> None:
    module = load_module()
    events: list[str] = []
    lock, _lock_raw, lease = fixture(module, tmp_path, events)
    request = json.loads(lease.paths["externalSignerRequest"].read_text())
    unsigned_raw = lease.paths["unsignedAab"].read_bytes()
    graph_raw = lease.paths["sourceGraph"].read_bytes()
    rebuilt = {"sha256": hashlib.sha256(unsigned_raw).hexdigest(), "sizeBytes": len(unsigned_raw)}
    signed = {
        "sha256": "a" * 64, "sizeBytes": 1234,
        "uploadCertificateSha256": module.UPLOAD_CERTIFICATE_SHA256,
    }
    android_v2 = protected_file(tmp_path / "ANDROID_RELEASE_BUILD_ATTESTATION.v2.json", b'{"v2":true}\n')
    value = {
        "contractName": module.EXTERNAL_SIGNER_ATTESTATION_CONTRACT,
        "algorithm": "ed25519",
        "keyId": lock["approval_authority"]["key_id"],
        "role": lock["approval_authority"]["role"],
        "attestationScope": lock["approval_authority"]["scope"],
        "generatedAtUtc": "2026-09-06T12:00:00Z",
        "challengeNonce": "b" * 64,
        "releaseIdentity": request["releaseIdentity"],
        "unsignedAabSha256": rebuilt["sha256"],
        "signedAabSha256": signed["sha256"],
        "signedAabSizeBytes": signed["sizeBytes"],
        "sourceGraphSha256": hashlib.sha256(graph_raw).hexdigest(),
        "expectedUploadCertificateSha256": module.UPLOAD_CERTIFICATE_SHA256,
        "fullToolchainClosureSha256": lease.toolchain["closureSha256"],
        "androidReleaseBuildAttestation": {
            "contractName": module.ANDROID_ATTESTATION_CONTRACT,
            "sha256": hashlib.sha256(android_v2.read_bytes()).hexdigest(),
        },
        "publicationAuthorized": False,
        "googlePlayUploadAuthorized": False,
        "signatureBase64": base64.b64encode(b"s" * 64).decode(),
    }
    path = protected_file(
        tmp_path / "ANDROID_EXTERNAL_SIGNER_ATTESTATION.v1.json", module._pretty_json(value)
    )
    android = SimpleNamespace(
        VERIFY=SimpleNamespace(
            _verify_ed25519_signature=lambda *_args, **_kwargs: events.append("verify-signature")
        )
    )
    observed = module.validate_external_signer_attestation(
        android, path, request, rebuilt, signed, graph_raw, lease.toolchain,
        android_v2, lock["approval_authority"],
    )
    assert observed == value and events == ["verify-signature"]

    value["signedAabSha256"] = "f" * 64
    path.write_bytes(module._pretty_json(value))
    with pytest.raises(module.RebuilderError, match="claims differ"):
        module.validate_external_signer_attestation(
            android, path, request, rebuilt, signed, graph_raw, lease.toolchain,
            android_v2, lock["approval_authority"],
        )
    assert events == ["verify-signature"]
