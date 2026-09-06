from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import io
import json
import subprocess
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/android_preview12_signer.py"
LOCK = ROOT / "config/release/android-preview12-signer.lock.json"
TOOLCHAIN = ROOT / "config/release/android-preview12-signer-toolchain.lock.json"
spec = importlib.util.spec_from_file_location("android_preview12_signer", SCRIPT)
assert spec and spec.loader
signer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(signer)


def _installed_bytes(toolchain, toolchain_bytes: bytes) -> bytes:
    value = {"contract_name": "fleet.android_preview12_installed_toolchain.v1",
        "lock_sha256": hashlib.sha256(toolchain_bytes).hexdigest(), "base_images": toolchain["base_images"],
        "archives": [{key: item[key] for key in ("name", "version", "url", "sha256")} for item in toolchain["archives"]]}
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def _ready(tmp_path: Path, certificate: bytes = b"certificate"):
    lock = json.loads(LOCK.read_text())
    toolchain, toolchain_bytes = signer._load_toolchain(TOOLCHAIN)
    lock["state"] = "ready"
    lock["release"].update(candidate_file_name="chummer-android-0.1.0-preview.12-unsigned.aab",
                           signed_file_name="chummer-android-0.1.0-preview.12-signed.aab",
                           source_graph_file_name="chummer-android-0.1.0-preview.12-source-graph.json")
    source = lock["source"]
    source["source_ref"] = "refs/heads/release/preview12"
    source["discovery_receipt"]["preview12_workflow_found"] = True
    source["candidate"].update(workflow_id=401, workflow_path=".github/workflows/preview12-aab.yml",
        workflow_blob_sha="c" * 40, event="push", run_attempt=1,
        artifact_name="chummer-android-preview12-arm64-unsigned-101-1",
        producer_toolchain_closure_sha256="e" * 64)
    source["verification"].update(workflow_id=402, workflow_path=".github/workflows/preview12-verify.yml",
        workflow_blob_sha="d" * 40, event="workflow_dispatch", run_attempt=1,
        artifact_name="chummer-android-preview12-verification-102-1", receipt_file_name="eligibility.json",
        proof_exclusion_validator_path="scripts/verify_release_aab_excludes_api36_proof.py",
        proof_exclusion_validator_blob_sha="8" * 40)
    lock["reservation"].update(enabled=True, broker_url="https://ledger.example.test/v1/reserve",
                                audited_implementation_sha256="f" * 64)
    lock["signing"].update(enabled=True, signature_algorithm="SHA256withRSA",
        expected_upload_certificate_sha256=hashlib.sha256(certificate).hexdigest())
    lock["toolchain"].update(image_digest="sha256:" + "1" * 64,
        installed_receipt_sha256=hashlib.sha256(_installed_bytes(toolchain, toolchain_bytes)).hexdigest())
    lock["signed_content_handoff"].update(enabled=True,
        private_content_addressed_endpoint="https://handoff.example.test/sha256",
        audited_implementation_sha256="2" * 64)
    lock_bytes = (json.dumps(lock, sort_keys=True) + "\n").encode()
    lock_path = tmp_path / "lock.json"
    lock_path.write_bytes(lock_bytes)
    installed = tmp_path / "installed.json"
    installed.write_bytes(_installed_bytes(toolchain, toolchain_bytes))
    return lock, lock_bytes, toolchain, toolchain_bytes, installed


def _aab() -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as bundle:
        bundle.writestr("base/manifest/AndroidManifest.xml", b"compiled")
        bundle.writestr("BundleConfig.pb", b"config")
    return output.getvalue()


def _zip(name: str, payload: bytes) -> bytes:
    return _zip_members({name: payload})


def _zip_members(values: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as bundle:
        for name, payload in values.items():
            bundle.writestr(name, payload)
    return output.getvalue()


def _source_graph() -> bytes:
    repositories = [
        {"name": name, "role": role, "commit": "a" * 40 if name == "chummer-android" else f"{index + 2:x}" * 40,
         "tree": f"{(index + 10) % 16:x}" * 40, "tree_sha256": str(index + 1) * 64,
         "repository": repository}
        for index, (name, (role, repository)) in enumerate(signer.SOURCE_REPOSITORIES.items())
    ]
    value = {"contractName": signer.SOURCE_GRAPH_CONTRACT, "generatedAtUtc": "2026-09-06T12:00:00Z",
        "authorityState": "local_review_required", "publicationAuthorized": False,
        "releaseIdentity": {"packageId": signer.PACKAGE_ID, "versionName": signer.VERSION_NAME,
            "versionCode": signer.VERSION_CODE, "intentAuthority": "explicit_build_input",
            "minimumExclusiveVersionCode": 11},
        "generator": {"path": "scripts/verify_release_source_graph.py", "sha256": "7" * 64, "size_bytes": 1},
        "repositories": repositories, "packagePins": [{"package_id": "Chummer.Application"}],
        "ownerPackagePins": [{"package_id": "Chummer.Run.Contracts"}],
        "dependencyClosure": [{"package_id": "Chummer.Run.Contracts", "dependencies": ["Chummer.Play.Contracts"]}],
        "presentationSource": {"repository": "chummer6-ui"},
        "doesNotAssert": ["google_play_upload", "tester_installation"]}
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def _args(tmp_path, candidate_archive, candidate, verification_archive, verification_receipt):
    return argparse.Namespace(source_sha="a" * 40, candidate_run_id="101", candidate_artifact_id="201",
        candidate_artifact_sha256=hashlib.sha256(candidate_archive).hexdigest(),
        candidate_aab_sha256=hashlib.sha256(candidate).hexdigest(), verification_run_id="102",
        verification_artifact_id="202", verification_artifact_sha256=hashlib.sha256(verification_archive).hexdigest(),
        verification_receipt_sha256=hashlib.sha256(verification_receipt).hexdigest(),
        output_dir=str(tmp_path / "intake"))


def _run(run_id: int, source, spec):
    return {"id": run_id, "run_attempt": 1, "event": spec["event"], "head_sha": "a" * 40,
        "head_branch": "release/preview12", "workflow_id": spec["workflow_id"], "path": spec["workflow_path"],
        "status": "completed", "conclusion": "success",
        "repository": {"id": 1331626697, "full_name": signer.ANDROID_REPOSITORY},
        "head_repository": {"id": 1331626697, "full_name": signer.ANDROID_REPOSITORY}}


def _producer_receipt(lock, args, graph: bytes):
    digests = {"candidate_artifact": args.candidate_artifact_sha256, "candidate_aab": args.candidate_aab_sha256,
        "verification_artifact": args.verification_artifact_sha256,
        "verification_receipt": args.verification_receipt_sha256,
        "source_graph": hashlib.sha256(graph).hexdigest(), "proof_validation_output": "9" * 64}
    return signer._producer_receipt_expected(lock, args, args.source_sha, digests)


class FakeGitHub:
    def __init__(self, values, downloads):
        self.values, self.downloads, self.download_count = values, downloads, 0

    def get_json(self, url):
        return self.values[url]

    def download_to(self, url, output, limit):
        payload = self.downloads[url]
        assert len(payload) <= limit
        self.download_count += 1
        output.write_bytes(payload)


def _case(tmp_path, mutate=None):
    lock, lock_bytes, toolchain, toolchain_bytes, installed = _ready(tmp_path)
    candidate = _aab()
    graph = _source_graph()
    placeholder = b"{}"
    args0 = _args(tmp_path, _zip(lock["release"]["candidate_file_name"], candidate), candidate,
                  _zip_members({"eligibility.json": placeholder,
                                lock["release"]["source_graph_file_name"]: graph}), placeholder)
    receipt = (json.dumps(_producer_receipt(lock, args0, graph), sort_keys=True, indent=2) + "\n").encode()
    candidate_archive = _zip(lock["release"]["candidate_file_name"], candidate)
    verification_archive = _zip_members({"eligibility.json": receipt,
                                          lock["release"]["source_graph_file_name"]: graph})
    args = _args(tmp_path, candidate_archive, candidate, verification_archive, receipt)
    receipt = (json.dumps(_producer_receipt(lock, args, graph), sort_keys=True, indent=2) + "\n").encode()
    verification_archive = _zip_members({"eligibility.json": receipt,
                                          lock["release"]["source_graph_file_name"]: graph})
    args = _args(tmp_path, candidate_archive, candidate, verification_archive, receipt)
    # The receipt intentionally does not bind its own archive or file digest, so this converges after one rebuild.
    api = f"https://api.github.com/repos/{signer.ANDROID_REPOSITORY}"
    values = {}
    for kind, run_id in (("candidate", 101), ("verification", 102)):
        values[f"{api}/actions/runs/{run_id}"] = _run(run_id, lock["source"], lock["source"][kind])
        path = lock["source"][kind]["workflow_path"]
        values[f"{api}/contents/{path}?ref={'a' * 40}"] = {"path": path, "sha": lock["source"][kind]["workflow_blob_sha"]}
    proof_path = lock["source"]["verification"]["proof_exclusion_validator_path"]
    values[f"{api}/contents/{proof_path}?ref={'a' * 40}"] = {
        "path": proof_path, "sha": lock["source"]["verification"]["proof_exclusion_validator_blob_sha"]}
    for kind, artifact_id, run_id, digest in (("candidate", 201, 101, args.candidate_artifact_sha256),
                                               ("verification", 202, 102, args.verification_artifact_sha256)):
        url = f"{api}/actions/artifacts/{artifact_id}/zip"
        values[f"{api}/actions/artifacts/{artifact_id}"] = {"id": artifact_id,
            "name": lock["source"][kind]["artifact_name"], "expired": False, "digest": f"sha256:{digest}",
            "workflow_run": {"id": run_id}, "archive_download_url": url}
    if mutate:
        mutate(values, args, receipt)
    downloads = {f"{api}/actions/artifacts/201/zip": candidate_archive,
                 f"{api}/actions/artifacts/202/zip": verification_archive}
    return lock, lock_bytes, toolchain, toolchain_bytes, installed, args, candidate, FakeGitHub(values, downloads)


def _runtime():
    return {"GITHUB_REPOSITORY": signer.FLEET_REPOSITORY, "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_SHA": "b" * 40, "FLEET_WORKFLOW_REPOSITORY": signer.FLEET_REPOSITORY,
        "FLEET_WORKFLOW_REF": signer.SIGNER_REF, "FLEET_WORKFLOW_SHA": "b" * 40,
        "RUNNER_ENVIRONMENT": "github-hosted", "FLEET_SIGNING_ENVIRONMENT": "android-preview12-signing",
        "GITHUB_RUN_ID": "301", "GITHUB_RUN_ATTEMPT": "1"}


def _preflight_inputs():
    return {"source_sha": "a" * 40, "candidate_run_id": "101", "candidate_artifact_id": "201",
        "candidate_artifact_sha256": "3" * 64, "candidate_aab_sha256": "4" * 64,
        "verification_run_id": "102", "verification_artifact_id": "202",
        "verification_artifact_sha256": "5" * 64, "verification_receipt_sha256": "6" * 64}


def _reusable_args(**changes):
    values = {**_preflight_inputs(), "caller_repository": signer.ANDROID_REPOSITORY,
        "caller_repository_id": "1331626697", "caller_ref": "refs/heads/release/preview12",
        "caller_sha": "a" * 40, "workflow_repository": signer.FLEET_REPOSITORY,
        "fleet_verifier_sha": "f" * 40, "workflow_ref": f"{signer.VERIFIER_PATH}@{'f' * 40}",
        "workflow_sha": "f" * 40, "github_output": None}
    values.update(changes)
    return argparse.Namespace(**values)


def _dispatch_args(image: str, **changes):
    values = {**_preflight_inputs(), "signer_image": image, "execution_repository": signer.FLEET_REPOSITORY,
        "execution_ref": "refs/heads/main", "execution_ref_protected": "true", "execution_event": "workflow_dispatch",
        "execution_sha": "b" * 40, "workflow_repository": signer.FLEET_REPOSITORY,
        "workflow_ref": signer.SIGNER_REF, "workflow_sha": "b" * 40, "github_output": None}
    values.update(changes)
    return argparse.Namespace(**values)


def test_checked_in_contract_is_red_and_uses_canonical_source(tmp_path):
    lock, _ = signer._load_lock(LOCK)
    toolchain, toolchain_bytes = signer._load_toolchain(TOOLCHAIN)
    assert hashlib.sha256(toolchain_bytes).hexdigest() == lock["toolchain"]["lock_sha256"]
    assert hashlib.sha256(_installed_bytes(toolchain, toolchain_bytes)).hexdigest() == lock["toolchain"]["installed_receipt_sha256"]
    args = _dispatch_args("")
    args.github_output = str(tmp_path / "output")
    with pytest.raises(signer.SignerError) as error:
        signer.dispatch_preflight(args, lock, toolchain, toolchain_bytes)
    message = str(error.value)
    assert lock["source"]["repository"] == "ArchonMegalon/chummer-android"
    assert lock["release"] == {"package_id": signer.PACKAGE_ID, "version_name": signer.VERSION_NAME,
        "version_code": signer.VERSION_CODE, "minimum_sdk": signer.MINIMUM_SDK,
        "target_sdk": signer.TARGET_SDK, "candidate_file_name": None, "signed_file_name": None,
        "source_graph_file_name": None}
    assert lock["publication"]["signing"] is False
    assert lock["publication"]["signed_content_handoff"] is False
    assert "found no Preview12 producer" in message and "artifact_name is not provisioned" in message
    assert "reservation is disabled" in message and "signed-content handoff is disabled" in message
    assert not Path(args.github_output).exists()
    with pytest.raises(signer.SignerError, match="lock state is not ready"):
        signer.reusable_preflight(_reusable_args(), lock, toolchain, toolchain_bytes)


def test_provisioned_android_reusable_and_fleet_dispatch_preflights_pass_separately(tmp_path):
    lock, _, toolchain, toolchain_bytes, _ = _ready(tmp_path)
    reusable = signer.reusable_preflight(_reusable_args(), lock, toolchain, toolchain_bytes)
    dispatch = signer.dispatch_preflight(_dispatch_args(signer._full_image(lock)), lock, toolchain, toolchain_bytes)
    assert reusable["transaction_inputs_sha256"] == dispatch["transaction_inputs_sha256"]
    assert reusable.get("signer_image") is None and dispatch["signer_image"] == signer._full_image(lock)


@pytest.mark.parametrize("field,value", [("caller_repository", "fork/android"), ("caller_sha", "b" * 40),
    ("caller_ref", "refs/heads/main"), ("workflow_repository", "fork/fleet"),
    ("workflow_ref", signer.SIGNER_REF), ("workflow_sha", "c" * 40), ("fleet_verifier_sha", "c" * 40)])
def test_reusable_verifier_rejects_context_substitutions(tmp_path, field, value):
    lock, _, toolchain, toolchain_bytes, _ = _ready(tmp_path)
    with pytest.raises(signer.SignerError, match="canonical reusable-verifier|exact Fleet commit"):
        signer.reusable_preflight(_reusable_args(**{field: value}), lock, toolchain, toolchain_bytes)


@pytest.mark.parametrize("field,value", [("execution_repository", signer.ANDROID_REPOSITORY),
    ("execution_ref", "refs/heads/release/preview12"), ("workflow_ref", f"{signer.VERIFIER_PATH}@{'f' * 40}"),
    ("workflow_sha", "c" * 40)])
def test_fleet_dispatch_rejects_repo_ref_or_workflow_sha_substitution(tmp_path, field, value):
    lock, _, toolchain, toolchain_bytes, _ = _ready(tmp_path)
    with pytest.raises(signer.SignerError, match="protected Fleet signer|exact Fleet execution SHA"):
        signer.dispatch_preflight(_dispatch_args(signer._full_image(lock), **{field: value}), lock, toolchain, toolchain_bytes)


@pytest.mark.parametrize("field,value", [("event", "pull_request_target"), ("run_attempt", 99),
    ("workflow_id", 999), ("head_branch", "main"), ("head_repository", {"id": 1, "full_name": "fork/repo"})])
def test_hostile_verification_run_rejected_before_download_or_mutation(tmp_path, field, value):
    def mutate(values, args, receipt):
        run = next(item for url, item in values.items() if url.endswith("runs/102"))
        run[field] = value
    lock, lock_bytes, toolchain, toolchain_bytes, _, args, _, client = _case(tmp_path, mutate)
    with pytest.raises(signer.SignerError, match="run 102 has unexpected"):
        signer.intake(args, lock, lock_bytes, toolchain, toolchain_bytes, client)
    assert client.download_count == 0 and not Path(args.output_dir).exists()


def test_logical_artifact_name_is_exact_and_rejected_before_download(tmp_path):
    def mutate(values, args, receipt):
        next(item for url, item in values.items() if url.endswith("artifacts/201"))["name"] = "lookalike"
    lock, lock_bytes, toolchain, toolchain_bytes, _, args, _, client = _case(tmp_path, mutate)
    with pytest.raises(signer.SignerError, match="artifact identity/digest"):
        signer.intake(args, lock, lock_bytes, toolchain, toolchain_bytes, client)
    assert client.download_count == 0 and not Path(args.output_dir).exists()


def test_proof_exclusion_validator_blob_is_authenticated_before_download(tmp_path):
    def mutate(values, args, receipt):
        row = next(item for url, item in values.items() if "verify_release_aab_excludes" in url)
        row["sha"] = "0" * 40
    lock, lock_bytes, toolchain, toolchain_bytes, _, args, _, client = _case(tmp_path, mutate)
    with pytest.raises(signer.SignerError, match="proof-exclusion validator path/blob SHA"):
        signer.intake(args, lock, lock_bytes, toolchain, toolchain_bytes, client)
    assert client.download_count == 0 and not Path(args.output_dir).exists()


def test_intake_requires_candidate_bound_producer_attestation(tmp_path):
    lock, lock_bytes, toolchain, toolchain_bytes, _, args, _, client = _case(tmp_path)
    verification_url = next(url for url in client.downloads if url.endswith("202/zip"))
    with zipfile.ZipFile(io.BytesIO(client.downloads[verification_url])) as original:
        bad = json.loads(original.read("eligibility.json"))
        graph = original.read(lock["release"]["source_graph_file_name"])
    bad["candidate"]["artifact_id"] = 999
    bad_bytes = (json.dumps(bad, sort_keys=True, indent=2) + "\n").encode()
    archive = _zip_members({"eligibility.json": bad_bytes,
                            lock["release"]["source_graph_file_name"]: graph})
    client.downloads[verification_url] = archive
    artifact_meta = next(item for url, item in client.values.items() if url.endswith("artifacts/202"))
    args.verification_artifact_sha256 = hashlib.sha256(archive).hexdigest()
    args.verification_receipt_sha256 = hashlib.sha256(bad_bytes).hexdigest()
    artifact_meta["digest"] = "sha256:" + args.verification_artifact_sha256
    with pytest.raises(signer.SignerError, match="does not bind the exact candidate"):
        signer.intake(args, lock, lock_bytes, toolchain, toolchain_bytes, client)
    assert not Path(args.output_dir).exists()


def test_exact_intake_succeeds_with_both_artifacts(tmp_path):
    lock, lock_bytes, toolchain, toolchain_bytes, _, args, candidate, client = _case(tmp_path)
    receipt = signer.intake(args, lock, lock_bytes, toolchain, toolchain_bytes, client)
    assert client.download_count == 2
    assert (Path(args.output_dir) / lock["release"]["candidate_file_name"]).read_bytes() == candidate
    assert receipt["producer"]["candidate"]["artifact_id"] == 201
    assert receipt["signed_aab_actions_artifact_uploaded"] is False


def _write_intake(path, lock, lock_bytes, candidate):
    path.mkdir()
    (path / lock["release"]["candidate_file_name"]).write_bytes(candidate)
    graph = _source_graph()
    (path / lock["release"]["source_graph_file_name"]).write_bytes(graph)
    args = argparse.Namespace(source_sha="a" * 40, candidate_run_id="101", candidate_artifact_id="201",
        candidate_artifact_sha256="3" * 64, candidate_aab_sha256=hashlib.sha256(candidate).hexdigest(),
        verification_run_id="102", verification_artifact_id="202", verification_artifact_sha256="5" * 64,
        verification_receipt_sha256="6" * 64)
    producer = _producer_receipt(lock, args, graph)
    value = {"contract_name": "fleet.android_preview12_trusted_intake.v3", "producer": producer,
        "verification_artifact_sha256": args.verification_artifact_sha256,
        "verification_receipt_sha256": args.verification_receipt_sha256,
        "signer_contract_sha256": hashlib.sha256(lock_bytes).hexdigest(),
        "ci_transport_role": "private_actions_artifact_sanitized_intake",
        "signed_aab_actions_artifact_uploaded": False, "play_upload_performed": False,
        "publication_performed": False}
    (path / "intake-attestation.json").write_text(json.dumps(value))
    return value


def _reserve_args(tmp_path, installed, image):
    return argparse.Namespace(candidate_dir=str(tmp_path / "intake"), installed_toolchain_receipt=str(installed),
                              running_image=image, output=str(tmp_path / "reservation.json"))


@pytest.mark.parametrize("decision", ["duplicate", "indeterminate"])
def test_duplicate_or_indeterminate_reservation_rejects_without_output(tmp_path, decision):
    lock, lock_bytes, toolchain, toolchain_bytes, installed = _ready(tmp_path)
    _write_intake(tmp_path / "intake", lock, lock_bytes, _aab())
    class Client:
        def reserve(self, request):
            return {"decision": decision}
    args = _reserve_args(tmp_path, installed, signer._full_image(lock))
    with pytest.raises(signer.SignerError, match=f"reservation rejected: {decision}"):
        signer.reserve(args, lock, lock_bytes, toolchain, toolchain_bytes, _runtime(), Client())
    assert not Path(args.output).exists()


def _reservation(lock, lock_bytes, intake, image):
    transaction, bindings = signer._transaction(lock, lock_bytes, intake, image)
    request = {"contract_name": "fleet.android_preview12_reservation_request.v2",
               "transaction_id": transaction, "bindings": bindings}
    return {"contract_name": "fleet.android_preview12_reservation.v2", "decision": "reserved", "created": True,
        "durable": True, "transaction_id": transaction,
        "request_sha256": hashlib.sha256(signer._json_bytes(request)).hexdigest(), "bindings": bindings}


def test_transaction_binds_verification_source_graph_proof_and_release_identity(tmp_path):
    lock, lock_bytes, _, _, _ = _ready(tmp_path)
    intake = _write_intake(tmp_path / "intake", lock, lock_bytes, _aab())
    transaction, bindings = signer._transaction(lock, lock_bytes, intake, signer._full_image(lock))
    assert signer.HEX64.fullmatch(transaction)
    assert bindings["verification_run_id"] == 102
    assert bindings["verification_artifact_id"] == 202
    assert bindings["verification_artifact_sha256"] == "5" * 64
    assert bindings["verification_receipt_sha256"] == "6" * 64
    assert bindings["source_graph_sha256"] == intake["producer"]["source_graph"]["sha256"]
    assert bindings["proof_exclusion_validation_output_sha256"] == "9" * 64
    assert (bindings["package_id"], bindings["version_name"], bindings["version_code"],
            bindings["minimum_sdk"], bindings["target_sdk"]) == (
                signer.PACKAGE_ID, signer.VERSION_NAME, signer.VERSION_CODE,
                signer.MINIMUM_SDK, signer.TARGET_SDK)
    changed = json.loads(json.dumps(intake))
    changed["verification_receipt_sha256"] = "7" * 64
    assert signer._transaction(lock, lock_bytes, changed, signer._full_image(lock))[0] != transaction


def test_installed_toolchain_receipt_rejected_before_candidate_tools_or_key_access(tmp_path):
    lock, lock_bytes, toolchain, toolchain_bytes, installed = _ready(tmp_path)
    intake = _write_intake(tmp_path / "intake", lock, lock_bytes, _aab())
    reservation = tmp_path / "reservation.json"
    reservation.write_text(json.dumps(_reservation(lock, lock_bytes, intake, signer._full_image(lock))))
    installed.write_text("{}")
    calls = []
    args = argparse.Namespace(candidate_dir=str(tmp_path / "intake"), installed_toolchain_receipt=str(installed),
        reservation_receipt=str(reservation), output_dir=str(tmp_path / "signed"), running_image=signer._full_image(lock))
    with pytest.raises(signer.SignerError, match="installed signer receipt digest mismatch"):
        signer.sign(args, lock, lock_bytes, toolchain, toolchain_bytes, _runtime(), lambda c, **k: calls.append(c))
    assert calls == [] and not Path(args.output_dir).exists()


def _rewrite_intake_graph(path: Path, lock, mutate) -> dict:
    graph_path = path / lock["release"]["source_graph_file_name"]
    graph = json.loads(graph_path.read_text())
    mutate(graph)
    graph_bytes = (json.dumps(graph, sort_keys=True, indent=2) + "\n").encode()
    graph_path.write_bytes(graph_bytes)
    intake_path = path / "intake-attestation.json"
    intake = json.loads(intake_path.read_text())
    digest = hashlib.sha256(graph_bytes).hexdigest()
    intake["producer"]["source_graph"]["sha256"] = digest
    intake["producer"]["proof_exclusion"]["source_graph_sha256"] = digest
    intake_path.write_text(json.dumps(intake))
    return intake


@pytest.mark.parametrize("mutation,error", [
    (lambda graph: graph["releaseIdentity"].update(packageId="org.attacker.lookalike"), "source graph identity"),
    (lambda graph: next(row for row in graph["repositories"] if row["name"] == "chummer-android")
        .update(commit="b" * 40), "exact Android source"),
])
def test_hostile_source_graph_is_rejected_before_candidate_tools_or_key_access(tmp_path, mutation, error):
    lock, lock_bytes, toolchain, toolchain_bytes, installed = _ready(tmp_path)
    intake = _write_intake(tmp_path / "intake", lock, lock_bytes, _aab())
    intake = _rewrite_intake_graph(tmp_path / "intake", lock, mutation)
    reservation = tmp_path / "reservation.json"
    reservation.write_text(json.dumps(_reservation(lock, lock_bytes, intake, signer._full_image(lock))))
    calls = []
    args = argparse.Namespace(candidate_dir=str(tmp_path / "intake"), installed_toolchain_receipt=str(installed),
        reservation_receipt=str(reservation), output_dir=str(tmp_path / "signed"), running_image=signer._full_image(lock))
    with pytest.raises(signer.SignerError, match=error):
        signer.sign(args, lock, lock_bytes, toolchain, toolchain_bytes, _runtime(),
                    lambda command, **kwargs: calls.append(command))
    assert calls == [] and not Path(args.output_dir).exists()


@pytest.mark.parametrize("field,value", [("status", "fail"), ("validator_blob_sha", "0" * 40),
                                           ("candidate_aab_sha256", "0" * 64)])
def test_hostile_proof_exclusion_claim_is_rejected_before_key_access(tmp_path, field, value):
    lock, lock_bytes, toolchain, toolchain_bytes, installed = _ready(tmp_path)
    intake = _write_intake(tmp_path / "intake", lock, lock_bytes, _aab())
    intake["producer"]["proof_exclusion"][field] = value
    (tmp_path / "intake" / "intake-attestation.json").write_text(json.dumps(intake))
    reservation = tmp_path / "reservation.json"
    reservation.write_text(json.dumps(_reservation(lock, lock_bytes, intake, signer._full_image(lock))))
    calls = []
    args = argparse.Namespace(candidate_dir=str(tmp_path / "intake"), installed_toolchain_receipt=str(installed),
        reservation_receipt=str(reservation), output_dir=str(tmp_path / "signed"), running_image=signer._full_image(lock))
    with pytest.raises(signer.SignerError, match="proof-exclusion authority"):
        signer.sign(args, lock, lock_bytes, toolchain, toolchain_bytes, _runtime(),
                    lambda command, **kwargs: calls.append(command))
    assert calls == [] and not Path(args.output_dir).exists()


@pytest.mark.parametrize("bad_xpath", ["/manifest/@package", "/manifest/@android:versionName",
    "/manifest/@android:versionCode", "/manifest/uses-sdk/@android:minSdkVersion",
    "/manifest/uses-sdk/@android:targetSdkVersion"])
def test_hostile_manifest_identity_is_rejected_before_key_access(tmp_path, bad_xpath):
    lock, lock_bytes, toolchain, toolchain_bytes, installed = _ready(tmp_path)
    intake = _write_intake(tmp_path / "intake", lock, lock_bytes, _aab())
    reservation = tmp_path / "reservation.json"
    reservation.write_text(json.dumps(_reservation(lock, lock_bytes, intake, signer._full_image(lock))))
    calls = []
    expected = {"/manifest/@package": signer.PACKAGE_ID,
        "/manifest/@android:versionName": signer.VERSION_NAME,
        "/manifest/@android:versionCode": str(signer.VERSION_CODE),
        "/manifest/uses-sdk/@android:minSdkVersion": str(signer.MINIMUM_SDK),
        "/manifest/uses-sdk/@android:targetSdkVersion": str(signer.TARGET_SDK)}
    def runner(command, **kwargs):
        calls.append(command)
        xpath = command[-1].removeprefix("--xpath=")
        return subprocess.CompletedProcess(command, 0,
            stdout=("hostile" if xpath == bad_xpath else expected[xpath]) + "\n", stderr="")
    args = argparse.Namespace(candidate_dir=str(tmp_path / "intake"), installed_toolchain_receipt=str(installed),
        reservation_receipt=str(reservation), output_dir=str(tmp_path / "signed"), running_image=signer._full_image(lock))
    environ = {**_runtime(), "ANDROID_PREVIEW12_UPLOAD_KEYSTORE_B64": base64.b64encode(b"key").decode(),
        "ANDROID_PREVIEW12_KEYSTORE_PASSWORD": "store-secret", "ANDROID_PREVIEW12_KEY_PASSWORD": "key-secret"}
    with pytest.raises(signer.SignerError, match="candidate manifest is not exact"):
        signer.sign(args, lock, lock_bytes, toolchain, toolchain_bytes, environ, runner)
    assert calls and all(Path(command[0]).name == "java" for command in calls)
    assert not Path(args.output_dir).exists()


def test_oversized_trusted_intake_is_rejected_before_key_access(tmp_path):
    lock, lock_bytes, toolchain, toolchain_bytes, installed = _ready(tmp_path)
    _write_intake(tmp_path / "intake", lock, lock_bytes, _aab())
    limit = lock["limits"]["verification_receipt_max_bytes"]
    (tmp_path / "intake" / "intake-attestation.json").write_bytes(b" " * (limit + 1))
    calls = []
    args = argparse.Namespace(candidate_dir=str(tmp_path / "intake"), installed_toolchain_receipt=str(installed),
        reservation_receipt=str(tmp_path / "reservation.json"), output_dir=str(tmp_path / "signed"),
        running_image=signer._full_image(lock))
    with pytest.raises(signer.SignerError, match="exceeds the locked size limit"):
        signer.sign(args, lock, lock_bytes, toolchain, toolchain_bytes, _runtime(),
                    lambda command, **kwargs: calls.append(command))
    assert calls == [] and not Path(args.output_dir).exists()


def test_secret_free_parsing_precedes_key_access_and_password_env_is_minimal(tmp_path):
    certificate = b"certificate"
    lock, lock_bytes, toolchain, toolchain_bytes, installed = _ready(tmp_path, certificate)
    intake = _write_intake(tmp_path / "intake", lock, lock_bytes, _aab())
    reservation = tmp_path / "reservation.json"
    reservation.write_text(json.dumps(_reservation(lock, lock_bytes, intake, signer._full_image(lock))))
    calls = []
    pem = "-----BEGIN CERTIFICATE-----\n" + base64.b64encode(certificate).decode() + "\n-----END CERTIFICATE-----\n"
    def runner(command, **kwargs):
        calls.append((command, kwargs.get("env", {})))
        if command[0].endswith("java"):
            xpath = command[-1].removeprefix("--xpath=")
            stdout = {"/manifest/@package": signer.PACKAGE_ID,
                "/manifest/@android:versionName": signer.VERSION_NAME,
                "/manifest/@android:versionCode": str(signer.VERSION_CODE),
                "/manifest/uses-sdk/@android:minSdkVersion": str(signer.MINIMUM_SDK),
                "/manifest/uses-sdk/@android:targetSdkVersion": str(signer.TARGET_SDK)}[xpath] + "\n"
        elif command[0].endswith("keytool") and "-exportcert" in command:
            stdout = certificate
        elif command[0].endswith("keytool"):
            stdout = pem
        elif command[0].endswith("jarsigner") and "-verify" in command:
            stdout = "jar verified.\n"
        else:
            stdout = "" if kwargs.get("text") else b""
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")
    args = argparse.Namespace(candidate_dir=str(tmp_path / "intake"), installed_toolchain_receipt=str(installed),
        reservation_receipt=str(reservation), output_dir=str(tmp_path / "signed"), running_image=signer._full_image(lock))
    environ = {**_runtime(), "ANDROID_PREVIEW12_UPLOAD_KEYSTORE_B64": base64.b64encode(b"key").decode(),
        "ANDROID_PREVIEW12_KEYSTORE_PASSWORD": "store-secret", "ANDROID_PREVIEW12_KEY_PASSWORD": "key-secret",
        "UNTRUSTED_PARENT_ENV": "must-not-pass"}
    value = signer.sign(args, lock, lock_bytes, toolchain, toolchain_bytes, environ, runner)
    assert [Path(call[0][0]).name for call in calls[:5]] == ["java"] * 5
    assert all("UNTRUSTED_PARENT_ENV" not in env for _, env in calls)
    assert all("FLEET_STOREPASS" not in env and "FLEET_KEYPASS" not in env for _, env in calls[:5])
    export_env = next(env for cmd, env in calls if "-exportcert" in cmd)
    sign_env = next(env for cmd, env in calls if Path(cmd[0]).name == "jarsigner" and "-verify" not in cmd)
    verify_env = next(env for cmd, env in calls if "-verify" in cmd)
    assert export_env["FLEET_STOREPASS"] == "store-secret" and "FLEET_KEYPASS" not in export_env
    assert sign_env["FLEET_STOREPASS"] == "store-secret" and sign_env["FLEET_KEYPASS"] == "key-secret"
    assert "FLEET_STOREPASS" not in verify_env and value["signing_invocations"] == 1
    assert value["signed_content_handoff_performed"] is False


class _HttpResponse(io.BytesIO):
    def __init__(self, payload: bytes, headers: dict[str, str] | None = None):
        super().__init__(payload)
        self.headers = headers or {}
        self.read_calls = 0

    def read(self, *args, **kwargs):
        self.read_calls += 1
        return super().read(*args, **kwargs)


def test_github_json_body_is_bounded_and_duplicate_keys_fail_closed(monkeypatch):
    responses = iter((_HttpResponse(b"{" + b" " * 64), _HttpResponse(b'{"id":1,"id":2}')))
    monkeypatch.setattr(urllib.request, "urlopen", lambda *args, **kwargs: next(responses))
    client = signer.GitHubClient("opaque", json_limit=32)
    with pytest.raises(signer.SignerError, match="exceeds the locked size limit"):
        client.get_json("https://api.github.test/oversized")
    with pytest.raises(signer.SignerError, match="duplicate JSON key"):
        client.get_json("https://api.github.test/duplicate")


def test_reservation_response_body_is_bounded_before_json_materialization(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen",
        lambda *args, **kwargs: _HttpResponse(b"{" + b" " * 64))
    client = signer.ReservationClient("https://ledger.example.test/reserve", "opaque", json_limit=32)
    with pytest.raises(signer.SignerError, match="reservation outcome is indeterminate"):
        client.reserve({"transaction_id": "a" * 64})


def test_declared_oversized_api_body_is_rejected_without_reading(monkeypatch):
    response = _HttpResponse(b"{}", {"Content-Length": "1048577"})
    monkeypatch.setattr(urllib.request, "urlopen", lambda *args, **kwargs: response)
    with pytest.raises(signer.SignerError, match="exceeds the locked size limit"):
        signer.GitHubClient("opaque", json_limit=1024 * 1024).get_json("https://api.github.test/declared")
    assert response.read_calls == 0


def test_workflow_topology_has_no_signed_actions_artifact_or_play_lane():
    signer_flow = (ROOT / ".github/workflows/android-preview12-signer.yml").read_text()
    verifier_flow = (ROOT / ".github/workflows/android-preview12-verifier.yml").read_text()
    assert "workflow_call:" not in signer_flow and "workflow_dispatch:" in signer_flow
    assert "workflow_call:" in verifier_flow and "secrets." not in verifier_flow
    for field in signer.INPUT_FIELDS:
        assert f"${{{{ inputs.{field} }}}}" in verifier_flow
        assert f"--{field.replace('_', '-')}" in verifier_flow
    assert "${{ inputs.fleet_verifier_sha }}" in verifier_flow and "--fleet-verifier-sha" in verifier_flow
    assert signer_flow.count("actions/upload-artifact@") == 1
    assert "uses: ./.github/workflows/android-preview12-verifier.yml" not in signer_flow
    assert "path: trusted-intake" in signer_flow and "path: signed-output" not in signer_flow
    assert signer.ANDROID_REPOSITORY in (ROOT / "config/release/android-preview12-signer.lock.json").read_text()
    assert "environment: android-play-upload" not in signer_flow
    assert "contents: write" not in signer_flow + verifier_flow
