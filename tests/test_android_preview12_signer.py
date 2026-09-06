from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import io
import json
import subprocess
import zipfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/android_preview12_signer.py"
LOCK = ROOT / "config/release/android-preview12-signer.lock.json"
TOOLCHAIN = ROOT / "config/release/android-preview12-signer-toolchain.lock.json"


def _load_module():
    spec = importlib.util.spec_from_file_location("android_preview12_signer", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


signer = _load_module()


def _ready_lock(tmp_path: Path, certificate: bytes = b"upload-certificate"):
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    lock["state"] = "ready"
    lock["source"]["candidate_workflow_path"] = ".github/workflows/android-preview12-candidate.yml"
    lock["source"]["verification_workflow_path"] = ".github/workflows/android-preview12-verify.yml"
    lock["signing"]["enabled"] = True
    lock["signing"]["signature_algorithm"] = "SHA256withRSA"
    lock["signing"]["expected_upload_certificate_sha256"] = hashlib.sha256(certificate).hexdigest()
    lock["toolchain"]["image_digest"] = "sha256:" + "1" * 64
    path = tmp_path / "ready-lock.json"
    payload = json.dumps(lock, sort_keys=True).encode()
    path.write_bytes(payload)
    return lock, payload, path


def _toolchain():
    return signer._load_toolchain(TOOLCHAIN)


def _aab_bytes() -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as bundle:
        bundle.writestr("base/manifest/AndroidManifest.xml", b"compiled-manifest")
        bundle.writestr("BundleConfig.pb", b"config")
    return output.getvalue()


def _artifact_bytes(candidate: bytes) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as bundle:
        bundle.writestr("chummer6-preview12.aab", candidate)
    return output.getvalue()


def _intake_args(tmp_path: Path, artifact: bytes, candidate: bytes):
    return argparse.Namespace(
        source_sha="a" * 40,
        candidate_run_id="101",
        verification_run_id="102",
        artifact_id="201",
        artifact_sha256=hashlib.sha256(artifact).hexdigest(),
        candidate_sha256=hashlib.sha256(candidate).hexdigest(),
        output_dir=str(tmp_path / "trusted-intake"),
    )


class FakeGitHubClient:
    def __init__(self, responses: dict[str, dict], artifact: bytes):
        self.responses = responses
        self.artifact = artifact
        self.downloads = 0

    def get_json(self, url: str):
        return self.responses[url]

    def download_to(self, url: str, output: Path, max_bytes: int):
        assert url == "https://api.github.com/repos/ArchonMegalon/chummer6-mobile/actions/artifacts/201/zip"
        assert len(self.artifact) <= max_bytes
        self.downloads += 1
        output.write_bytes(self.artifact)


def _green_run(run_id: int, workflow_path: str) -> dict:
    return {
        "id": run_id,
        "head_sha": "a" * 40,
        "head_branch": "main",
        "status": "completed",
        "conclusion": "success",
        "path": workflow_path,
        "repository": {"full_name": "ArchonMegalon/chummer6-mobile"},
    }


def _responses(args, lock) -> dict[str, dict]:
    api = "https://api.github.com/repos/ArchonMegalon/chummer6-mobile"
    return {
        f"{api}/actions/runs/101": _green_run(101, lock["source"]["candidate_workflow_path"]),
        f"{api}/actions/runs/102": _green_run(102, lock["source"]["verification_workflow_path"]),
        f"{api}/actions/artifacts/201": {
            "id": 201,
            "name": "android-preview12-unsigned",
            "expired": False,
            "digest": "sha256:" + args.artifact_sha256,
            "workflow_run": {"id": 101},
            "archive_download_url": f"{api}/actions/artifacts/201/zip",
        },
    }


def test_checked_in_lock_fails_closed_without_creating_output(tmp_path: Path) -> None:
    lock, _ = signer._load_lock(LOCK)
    toolchain, toolchain_bytes = _toolchain()
    github_output = tmp_path / "github-output"
    args = argparse.Namespace(
        signer_image="",
        execution_repository="ArchonMegalon/fleet",
        execution_ref="refs/heads/main",
        execution_ref_protected="true",
        workflow_ref=signer.WORKFLOW_REF,
        workflow_sha="b" * 40,
        github_output=str(github_output),
    )
    with pytest.raises(signer.SignerError) as failure:
        signer.preflight(args, lock, toolchain, toolchain_bytes)
    message = str(failure.value)
    assert "signer OCI digest is not provisioned" in message
    assert "signing is disabled" in message
    assert "expected upload certificate" in message
    assert "signature algorithm" in message
    assert not github_output.exists()


def test_intake_requires_two_exact_green_runs_before_download_or_mutation(tmp_path: Path) -> None:
    lock, lock_bytes, _ = _ready_lock(tmp_path)
    toolchain, toolchain_bytes = _toolchain()
    candidate = _aab_bytes()
    artifact = _artifact_bytes(candidate)
    args = _intake_args(tmp_path, artifact, candidate)
    responses = _responses(args, lock)
    responses[next(key for key in responses if key.endswith("runs/102"))]["conclusion"] = "failure"
    client = FakeGitHubClient(responses, artifact)
    with pytest.raises(signer.SignerError, match="unexpected conclusion"):
        signer.intake(args, lock, lock_bytes, toolchain, toolchain_bytes, client)
    assert client.downloads == 0
    assert not Path(args.output_dir).exists()


def test_missing_broker_credential_fails_before_intake_mutation(tmp_path: Path) -> None:
    with pytest.raises(signer.SignerError, match="credential is missing"):
        signer.GitHubClient("")
    assert list(tmp_path.iterdir()) == []


def test_intake_binds_exact_run_artifact_and_candidate_digests(tmp_path: Path) -> None:
    lock, lock_bytes, _ = _ready_lock(tmp_path)
    toolchain, toolchain_bytes = _toolchain()
    candidate = _aab_bytes()
    artifact = _artifact_bytes(candidate)
    args = _intake_args(tmp_path, artifact, candidate)
    client = FakeGitHubClient(_responses(args, lock), artifact)
    receipt = signer.intake(args, lock, lock_bytes, toolchain, toolchain_bytes, client)
    output = Path(args.output_dir)
    assert client.downloads == 1
    assert (output / "chummer6-preview12.aab").read_bytes() == candidate
    assert receipt["source_sha"] == "a" * 40
    assert receipt["candidate_run_id"] == 101
    assert receipt["verification_run_id"] == 102
    assert receipt["artifact_id"] == 201
    assert receipt["publication"] is False and receipt["upload"] is False


def _write_intake(path: Path, candidate: bytes, lock_bytes: bytes) -> None:
    path.mkdir()
    (path / "chummer6-preview12.aab").write_bytes(candidate)
    receipt = {
        "contract_name": "fleet.android_preview12_trusted_intake.v1",
        "source_sha": "a" * 40,
        "artifact_id": 201,
        "candidate_sha256": hashlib.sha256(candidate).hexdigest(),
        "signer_contract_sha256": hashlib.sha256(lock_bytes).hexdigest(),
    }
    (path / "intake-attestation.json").write_text(json.dumps(receipt), encoding="utf-8")


def _github_runtime() -> dict[str, str]:
    return {
        "GITHUB_REPOSITORY": "ArchonMegalon/fleet",
        "FLEET_WORKFLOW_REPOSITORY": "ArchonMegalon/fleet",
        "FLEET_WORKFLOW_REF": signer.WORKFLOW_REF,
        "FLEET_WORKFLOW_SHA": "b" * 40,
        "RUNNER_ENVIRONMENT": "github-hosted",
        "FLEET_SIGNING_ENVIRONMENT": "android-preview12-signing",
        "GITHUB_RUN_ID": "301",
        "GITHUB_RUN_ATTEMPT": "1",
    }


def test_missing_signing_material_cannot_mutate_candidate_or_output(tmp_path: Path) -> None:
    lock, lock_bytes, _ = _ready_lock(tmp_path)
    toolchain, toolchain_bytes = _toolchain()
    candidate = _aab_bytes()
    intake_dir = tmp_path / "intake"
    _write_intake(intake_dir, candidate, lock_bytes)
    output = tmp_path / "signed"
    args = argparse.Namespace(
        candidate_dir=str(intake_dir), output_dir=str(output), running_image=signer._full_image(lock)
    )
    with pytest.raises(signer.SignerError, match="signing material is incomplete"):
        signer.sign(args, lock, lock_bytes, toolchain, toolchain_bytes, _github_runtime())
    assert (intake_dir / "chummer6-preview12.aab").read_bytes() == candidate
    assert not output.exists()


def test_non_github_hosted_runtime_cannot_reach_signing_material(tmp_path: Path) -> None:
    lock, lock_bytes, _ = _ready_lock(tmp_path)
    toolchain, toolchain_bytes = _toolchain()
    candidate = _aab_bytes()
    intake_dir = tmp_path / "intake"
    _write_intake(intake_dir, candidate, lock_bytes)
    output = tmp_path / "signed"
    args = argparse.Namespace(
        candidate_dir=str(intake_dir), output_dir=str(output), running_image=signer._full_image(lock)
    )
    runtime = _github_runtime()
    runtime["RUNNER_ENVIRONMENT"] = "self-hosted"
    with pytest.raises(signer.SignerError, match="not the protected Fleet GitHub-hosted lane"):
        signer.sign(args, lock, lock_bytes, toolchain, toolchain_bytes, runtime)
    assert (intake_dir / "chummer6-preview12.aab").read_bytes() == candidate
    assert not output.exists()


def test_success_path_invokes_jarsigner_once_and_emits_non_upload_attestation(tmp_path: Path) -> None:
    certificate = b"expected-upload-cert"
    lock, lock_bytes, _ = _ready_lock(tmp_path, certificate)
    toolchain, toolchain_bytes = _toolchain()
    candidate = _aab_bytes()
    intake_dir = tmp_path / "intake"
    _write_intake(intake_dir, candidate, lock_bytes)
    calls: list[list[str]] = []
    pem = "-----BEGIN CERTIFICATE-----\n" + base64.b64encode(certificate).decode() + "\n-----END CERTIFICATE-----\n"

    def runner(command, **kwargs):
        calls.append(command)
        if command[0].endswith("java"):
            stdout = "Preview12\n" if "versionName" in command[-1] else "12\n"
        elif command[0].endswith("keytool") and "-exportcert" in command:
            stdout = certificate
        elif command[0].endswith("keytool"):
            stdout = pem
        elif command[0].endswith("jarsigner") and "-verify" in command:
            stdout = "jar verified.\n"
        else:
            stdout = "" if kwargs.get("text") else b""
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    output = tmp_path / "signed"
    args = argparse.Namespace(
        candidate_dir=str(intake_dir), output_dir=str(output), running_image=signer._full_image(lock)
    )
    environ = {
        "ANDROID_PREVIEW12_UPLOAD_KEYSTORE_B64": base64.b64encode(b"keystore").decode(),
        "ANDROID_PREVIEW12_KEYSTORE_PASSWORD": "store-password",
        "ANDROID_PREVIEW12_KEY_PASSWORD": "key-password",
        **_github_runtime(),
    }
    attestation = signer.sign(
        args, lock, lock_bytes, toolchain, toolchain_bytes, environ, runner
    )
    sign_calls = [call for call in calls if call[0].endswith("jarsigner") and "-verify" not in call]
    assert len(sign_calls) == 1
    assert attestation["signing_invocations"] == 1
    assert attestation["publication"] is False and attestation["upload"] is False
    assert (output / "chummer6-preview12-signed.aab").exists()
    assert json.loads((output / "signed-attestation.json").read_text())["transaction_id"]


def test_toolchain_and_workflow_are_immutable_and_play_upload_is_absent() -> None:
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    toolchain = json.loads(TOOLCHAIN.read_text(encoding="utf-8"))
    dockerfile = (ROOT / "containers/android-preview12-signer/Dockerfile").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/android-preview12-signer.yml").read_text(encoding="utf-8")
    assert lock["release"]["version_name"] == "Preview12"
    assert lock["release"]["version_code"] == 12
    assert hashlib.sha256(TOOLCHAIN.read_bytes()).hexdigest() == lock["toolchain"]["lock_sha256"]
    assert "image_digest" not in toolchain
    assert "android-preview12-signer.lock.json" not in dockerfile
    for image in toolchain["base_images"]:
        assert signer.HEX64.fullmatch(image["digest"].removeprefix("sha256:"))
        assert f"{image['reference']}@{image['digest']}" in dockerfile
    for archive in toolchain["archives"]:
        assert signer.HEX64.fullmatch(archive["sha256"])
        assert "latest" not in archive["url"]
    for action_sha in (
        "11d5960a326750d5838078e36cf38b85af677262",
        "ea165f8d65b6e75b540449e92b4886f43607fa02",
        "d3f86a106a0bac45b974a628896c90dbdf5c8093",
    ):
        assert action_sha in workflow
    assert "repository: ArchonMegalon/fleet" in workflow
    assert "repository: ArchonMegalon/chummer6-mobile" not in workflow
    assert workflow.count("actions/checkout@") == 2
    assert "environment: ${{ needs.contract.outputs.intake_environment }}" in workflow
    assert "environment: ${{ needs.contract.outputs.signing_environment }}" in workflow
    assert "needs: contract" in workflow
    assert "environment: android-play-upload" not in workflow
    assert "contents: write" not in workflow
    assert "packages: write" not in workflow
    assert '--source-sha "${{ inputs.source_sha }}"' not in workflow
