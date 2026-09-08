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
    unsigned = {"contractName": module.ANDROID_ATTESTATION_CONTRACT, "challengeNonce": "a" * 64}
    fake = SimpleNamespace(
        ROOT=tmp_path,
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
    value = os.environ.get("CHUMMER_ANDROID_388_ROOT")
    if not value:
        pytest.skip("exact Android consumer checkout not supplied")
    monkeypatch.setattr(module.sys, "dont_write_bytecode", prior_bytecode_posture)
    monkeypatch.setenv("CHUMMER_RELEASE_REPO_ROOT", "caller-posture-must-be-restored")
    consumer = module.validate_android_consumer(Path(value), json.loads(LOCK.read_text()))
    assert consumer.CONTRACT == module.ANDROID_ATTESTATION_CONTRACT
    assert consumer._pretty({"b": 2, "a": 1}) == b'{\n  "a": 1,\n  "b": 2\n}\n'
    assert module.sys.dont_write_bytecode is prior_bytecode_posture
    assert os.environ["CHUMMER_RELEASE_REPO_ROOT"] == "caller-posture-must-be-restored"
    module._validate_android_consumer_inputs(Path(value), json.loads(LOCK.read_text())["android_authority"]["commit"])


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
    value = os.environ.get("CHUMMER_ANDROID_388_ROOT")
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
