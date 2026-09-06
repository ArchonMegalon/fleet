#!/usr/bin/env python3
"""Fail-closed trusted intake and one-shot Android Preview12 signing transaction."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping


HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
FLEET_REPOSITORY = "ArchonMegalon/fleet"
WORKFLOW_REF = (
    "ArchonMegalon/fleet/.github/workflows/android-preview12-signer.yml@refs/heads/main"
)


class SignerError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_lock(path: Path) -> tuple[dict[str, Any], bytes]:
    payload = path.read_bytes()
    lock = json.loads(payload)
    if lock.get("contract_name") != "fleet.android_preview12_signer_transaction.v1":
        raise SignerError("unexpected signer lock contract")
    return lock, payload


def _load_toolchain(path: Path) -> tuple[dict[str, Any], bytes]:
    payload = path.read_bytes()
    lock = json.loads(payload)
    if lock.get("contract_name") != "fleet.android_preview12_toolchain.v1":
        raise SignerError("unexpected toolchain lock contract")
    return lock, payload


def _full_image(lock: Mapping[str, Any]) -> str | None:
    toolchain = lock["toolchain"]
    digest = toolchain.get("image_digest")
    return f"{toolchain['image_repository']}@{digest}" if digest else None


def provisioning_blockers(
    lock: Mapping[str, Any],
    signer_image: str,
    toolchain: Mapping[str, Any],
    toolchain_bytes: bytes,
) -> list[str]:
    blockers: list[str] = []
    if lock.get("state") != "ready":
        blockers.append("lock state is not ready")
    if lock.get("release") != {
        "version_name": "Preview12",
        "version_code": 12,
        "candidate_file_name": "chummer6-preview12.aab",
        "signed_file_name": "chummer6-preview12-signed.aab",
    }:
        blockers.append("release identity is not exact Preview12/code12")
    source = lock.get("source", {})
    if (source.get("repository"), source.get("branch"), source.get("artifact_name")) != (
        "ArchonMegalon/chummer6-mobile",
        "main",
        "android-preview12-unsigned",
    ):
        blockers.append("source repository, branch, or artifact name drifted")
    for field in ("candidate_workflow_path", "verification_workflow_path"):
        value = source.get(field)
        if not isinstance(value, str) or not value.startswith(".github/workflows/"):
            blockers.append(f"source.{field} is not provisioned")
    if source.get("candidate_workflow_path") == source.get("verification_workflow_path"):
        blockers.append("two-green workflow paths must be distinct")
    signing = lock.get("signing", {})
    if signing.get("enabled") is not True:
        blockers.append("signing is disabled")
    if not HEX64.fullmatch(str(signing.get("expected_upload_certificate_sha256") or "")):
        blockers.append("expected upload certificate SHA-256 is not provisioned")
    if signing.get("signature_algorithm") not in ("SHA256withRSA", "SHA256withECDSA"):
        blockers.append("upload key signature algorithm is not provisioned")
    image = _full_image(lock)
    if image is None or not re.fullmatch(r"[^@]+@sha256:[0-9a-f]{64}", image):
        blockers.append("signer OCI digest is not provisioned")
    elif signer_image != image:
        blockers.append("runner signer image does not equal the locked OCI digest")
    toolchain_ref = lock.get("toolchain", {})
    if toolchain_ref.get("lock_path") != "config/release/android-preview12-signer-toolchain.lock.json":
        blockers.append("toolchain lock path drifted")
    if hashlib.sha256(toolchain_bytes).hexdigest() != toolchain_ref.get("lock_sha256"):
        blockers.append("toolchain lock SHA-256 does not match the transaction contract")
    if toolchain.get("platform") != toolchain_ref.get("platform"):
        blockers.append("toolchain platform does not match the transaction contract")
    for entry in [*toolchain.get("base_images", []), *toolchain.get("archives", [])]:
        digest = str(entry.get("digest", entry.get("sha256", ""))).removeprefix("sha256:")
        if not HEX64.fullmatch(digest):
            blockers.append(f"toolchain input {entry.get('name')} has no SHA-256 pin")
    environments = lock.get("environments", {})
    publication = lock.get("publication", {})
    if tuple(environments.get(key) for key in ("intake", "signing", "play_upload")) != (
        "android-preview12-intake",
        "android-preview12-signing",
        "android-play-upload",
    ):
        blockers.append("protected environment names drifted")
    if environments.get("play_upload_enabled") is not False:
        blockers.append("Play upload environment must remain disabled")
    if any(publication.get(key) is not False for key in ("registry_publication", "play_upload", "github_release")):
        blockers.append("publication and upload must remain false")
    return blockers


def preflight(
    args: argparse.Namespace,
    lock: Mapping[str, Any],
    toolchain: Mapping[str, Any],
    toolchain_bytes: bytes,
) -> dict[str, Any]:
    blockers = provisioning_blockers(lock, args.signer_image, toolchain, toolchain_bytes)
    if args.execution_repository != FLEET_REPOSITORY:
        blockers.append("transaction must execute in the canonical Fleet repository")
    if args.execution_ref != "refs/heads/main" or args.execution_ref_protected != "true":
        blockers.append("transaction caller must be protected Fleet main")
    if args.workflow_ref != WORKFLOW_REF:
        blockers.append("workflow must be loaded from Fleet protected main")
    if not HEX40.fullmatch(args.workflow_sha):
        blockers.append("workflow SHA must be an exact commit")
    if blockers:
        raise SignerError("; ".join(blockers))
    if args.github_output:
        with Path(args.github_output).open("a", encoding="utf-8") as output:
            output.write(f"signer_image={_full_image(lock)}\n")
            output.write(f"intake_environment={lock['environments']['intake']}\n")
            output.write(f"signing_environment={lock['environments']['signing']}\n")
    return {
        "ok": True,
        "signer_image": _full_image(lock),
        "intake_environment": lock["environments"]["intake"],
        "signing_environment": lock["environments"]["signing"],
        "publication": False,
        "upload": False,
    }


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):  # noqa: ANN001
        return None


class GitHubClient:
    def __init__(self, token: str):
        if not token:
            raise SignerError("candidate broker credential is missing")
        self.headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "fleet-android-preview12-intake/1",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def get_json(self, url: str) -> dict[str, Any]:
        request = urllib.request.Request(url, headers=self.headers)
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)

    def download_to(self, url: str, output: Path, max_bytes: int) -> None:
        request = urllib.request.Request(url, headers=self.headers)
        opener = urllib.request.build_opener(_NoRedirect())
        try:
            response = opener.open(request, timeout=30)
        except urllib.error.HTTPError as error:
            if error.code not in (301, 302, 303, 307, 308):
                raise
            location = error.headers.get("Location", "")
            parsed = urllib.parse.urlparse(location)
            if parsed.scheme != "https" or not parsed.hostname:
                raise SignerError("artifact broker returned an unsafe redirect") from error
            response = urllib.request.urlopen(
                urllib.request.Request(location, headers={"User-Agent": self.headers["User-Agent"]}),
                timeout=60,
            )
        total = 0
        with response, output.open("wb") as stream:
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > max_bytes:
                    raise SignerError("candidate artifact exceeds locked size limit")
                stream.write(chunk)


def _positive_int(value: str, label: str) -> int:
    if not value.isascii() or not value.isdigit() or int(value) < 1:
        raise SignerError(f"{label} must be a positive integer")
    return int(value)


def _validate_run(run: Mapping[str, Any], *, run_id: int, source: Mapping[str, Any], sha: str, path: str) -> None:
    expected = {
        "id": run_id,
        "head_sha": sha,
        "head_branch": source["branch"],
        "status": "completed",
        "conclusion": "success",
        "path": path,
    }
    for field, value in expected.items():
        if run.get(field) != value:
            raise SignerError(f"green run {run_id} has unexpected {field}")
    if run.get("repository", {}).get("full_name") != source["repository"]:
        raise SignerError(f"green run {run_id} belongs to the wrong repository")


def _safe_candidate(bundle: zipfile.ZipFile, expected_name: str, max_bytes: int) -> zipfile.ZipInfo:
    candidates: list[zipfile.ZipInfo] = []
    seen: set[str] = set()
    for member in bundle.infolist():
        pure = PurePosixPath(member.filename)
        if pure.is_absolute() or ".." in pure.parts or member.filename in seen:
            raise SignerError("unsafe or duplicate candidate artifact member")
        seen.add(member.filename)
        if stat.S_ISLNK(member.external_attr >> 16):
            raise SignerError("candidate artifact contains a symlink")
        if "\\" in member.filename:
            raise SignerError("candidate artifact contains a non-portable path")
        if not member.is_dir() and pure.name == expected_name:
            candidates.append(member)
    if len(candidates) != 1 or candidates[0].file_size > max_bytes:
        raise SignerError("candidate artifact must contain exactly one bounded expected AAB")
    return candidates[0]


def _assert_unsigned_aab(path: Path) -> None:
    try:
        with zipfile.ZipFile(path) as bundle:
            names = [name.upper() for name in bundle.namelist()]
    except zipfile.BadZipFile as error:
        raise SignerError("candidate is not an Android App Bundle ZIP") from error
    signature = re.compile(r"^META-INF/[^/]+\.(SF|RSA|DSA|EC)$")
    if len(names) != len(set(names)) or any(signature.fullmatch(name) for name in names):
        raise SignerError("candidate is already signed or has duplicate members")


def intake(
    args: argparse.Namespace,
    lock: Mapping[str, Any],
    lock_bytes: bytes,
    toolchain: Mapping[str, Any],
    toolchain_bytes: bytes,
    client: GitHubClient,
) -> dict[str, Any]:
    blockers = provisioning_blockers(lock, _full_image(lock) or "", toolchain, toolchain_bytes)
    if blockers:
        raise SignerError("; ".join(blockers))
    source = lock["source"]
    source_sha = args.source_sha.lower()
    artifact_sha = args.artifact_sha256.lower()
    candidate_sha = args.candidate_sha256.lower()
    if not all(HEX40.fullmatch(value) for value in (source_sha,)):
        raise SignerError("source SHA must be an exact commit")
    if not HEX64.fullmatch(artifact_sha) or not HEX64.fullmatch(candidate_sha):
        raise SignerError("artifact and candidate digests must be SHA-256")
    candidate_run_id = _positive_int(args.candidate_run_id, "candidate run ID")
    verification_run_id = _positive_int(args.verification_run_id, "verification run ID")
    artifact_id = _positive_int(args.artifact_id, "artifact ID")
    if candidate_run_id == verification_run_id:
        raise SignerError("two distinct green run IDs are required")
    api = f"https://api.github.com/repos/{source['repository']}"
    candidate_run = client.get_json(f"{api}/actions/runs/{candidate_run_id}")
    verification_run = client.get_json(f"{api}/actions/runs/{verification_run_id}")
    _validate_run(candidate_run, run_id=candidate_run_id, source=source, sha=source_sha, path=source["candidate_workflow_path"])
    _validate_run(verification_run, run_id=verification_run_id, source=source, sha=source_sha, path=source["verification_workflow_path"])
    artifact = client.get_json(f"{api}/actions/artifacts/{artifact_id}")
    expected_digest = f"sha256:{artifact_sha}"
    if artifact.get("id") != artifact_id or artifact.get("name") != source["artifact_name"]:
        raise SignerError("artifact identity does not match the locked contract")
    if artifact.get("expired") is not False or artifact.get("digest") != expected_digest:
        raise SignerError("artifact is expired or its API digest does not match")
    if artifact.get("workflow_run", {}).get("id") != candidate_run_id:
        raise SignerError("artifact was not produced by the candidate green run")
    expected_url = f"{api}/actions/artifacts/{artifact_id}/zip"
    if artifact.get("archive_download_url") != expected_url:
        raise SignerError("artifact download URL does not match the exact source artifact")

    output_dir = Path(args.output_dir)
    if output_dir.exists():
        raise SignerError("intake output already exists")
    with tempfile.TemporaryDirectory(prefix="fleet-intake-") as temporary:
        archive = Path(temporary) / "artifact.zip"
        client.download_to(artifact["archive_download_url"], archive, int(lock["limits"]["artifact_max_bytes"]))
        if _sha256(archive) != artifact_sha:
            raise SignerError("downloaded artifact bytes do not match the exact digest")
        candidate = Path(temporary) / lock["release"]["candidate_file_name"]
        with zipfile.ZipFile(archive) as bundle:
            member = _safe_candidate(bundle, candidate.name, int(lock["limits"]["candidate_max_bytes"]))
            with bundle.open(member) as source_stream, candidate.open("wb") as output:
                shutil.copyfileobj(source_stream, output)
        if _sha256(candidate) != candidate_sha:
            raise SignerError("candidate file digest does not match")
        _assert_unsigned_aab(candidate)
        receipt = {
            "contract_name": "fleet.android_preview12_trusted_intake.v1",
            "source_repository": source["repository"],
            "source_sha": source_sha,
            "candidate_run_id": candidate_run_id,
            "verification_run_id": verification_run_id,
            "artifact_id": artifact_id,
            "artifact_name": artifact["name"],
            "artifact_sha256": artifact_sha,
            "candidate_file": candidate.name,
            "candidate_sha256": candidate_sha,
            "version_name": "Preview12",
            "version_code": 12,
            "signer_contract_sha256": hashlib.sha256(lock_bytes).hexdigest(),
            "publication": False,
            "upload": False,
        }
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=f".{output_dir.name}-", dir=output_dir.parent) as stage_name:
            stage = Path(stage_name)
            shutil.copyfile(candidate, stage / candidate.name)
            (stage / "signer.lock.json").write_bytes(lock_bytes)
            (stage / "intake-attestation.json").write_text(
                json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8"
            )
            os.replace(stage, output_dir)
        return receipt


def _checked(runner: Callable[..., subprocess.CompletedProcess], command: list[str], **kwargs):
    result = runner(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, **kwargs)
    if result.returncode != 0:
        raise SignerError(f"trusted tool failed: {Path(command[0]).name}")
    return result


def _bundle_value(runner, candidate: Path, xpath: str) -> str:
    result = _checked(
        runner,
        ["/opt/jdk/bin/java", "-jar", "/opt/android-sdk/tools/bundletool.jar", "dump", "manifest", f"--bundle={candidate}", f"--xpath={xpath}"],
        text=True,
    )
    return result.stdout.strip()


def _pem_der(payload: str) -> bytes:
    match = re.search(r"-----BEGIN CERTIFICATE-----(.*?)-----END CERTIFICATE-----", payload, re.S)
    if not match:
        raise SignerError("signed bundle did not expose a certificate")
    return base64.b64decode(re.sub(r"\s+", "", match.group(1)), validate=True)


def sign(
    args: argparse.Namespace,
    lock: Mapping[str, Any],
    lock_bytes: bytes,
    toolchain: Mapping[str, Any],
    toolchain_bytes: bytes,
    environ: Mapping[str, str],
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> dict[str, Any]:
    blockers = provisioning_blockers(lock, args.running_image, toolchain, toolchain_bytes)
    if blockers:
        raise SignerError("; ".join(blockers))
    candidate_dir = Path(args.candidate_dir)
    candidate = candidate_dir / lock["release"]["candidate_file_name"]
    receipt = json.loads((candidate_dir / "intake-attestation.json").read_text(encoding="utf-8"))
    if receipt.get("contract_name") != "fleet.android_preview12_trusted_intake.v1":
        raise SignerError("trusted intake attestation is missing")
    if receipt.get("signer_contract_sha256") != hashlib.sha256(lock_bytes).hexdigest():
        raise SignerError("signer contract changed after trusted intake")
    if _sha256(candidate) != receipt.get("candidate_sha256"):
        raise SignerError("candidate changed after trusted intake")
    _assert_unsigned_aab(candidate)
    runtime = {
        "repository": environ.get("GITHUB_REPOSITORY"),
        "workflow_repository": environ.get("FLEET_WORKFLOW_REPOSITORY"),
        "workflow_ref": environ.get("FLEET_WORKFLOW_REF"),
        "workflow_sha": environ.get("FLEET_WORKFLOW_SHA"),
        "runner_environment": environ.get("RUNNER_ENVIRONMENT"),
        "signing_environment": environ.get("FLEET_SIGNING_ENVIRONMENT"),
        "run_id": environ.get("GITHUB_RUN_ID"),
        "run_attempt": environ.get("GITHUB_RUN_ATTEMPT"),
    }
    if (
        runtime["repository"] != FLEET_REPOSITORY
        or runtime["workflow_repository"] != FLEET_REPOSITORY
        or runtime["workflow_ref"] != WORKFLOW_REF
        or not HEX40.fullmatch(str(runtime["workflow_sha"] or ""))
        or runtime["runner_environment"] != "github-hosted"
        or runtime["signing_environment"] != "android-preview12-signing"
        or not str(runtime["run_id"] or "").isdigit()
        or runtime["run_attempt"] != "1"
    ):
        raise SignerError("signing runtime is not the protected Fleet GitHub-hosted lane")
    required = (
        "ANDROID_PREVIEW12_UPLOAD_KEYSTORE_B64",
        "ANDROID_PREVIEW12_KEYSTORE_PASSWORD",
        "ANDROID_PREVIEW12_KEY_PASSWORD",
    )
    if any(not environ.get(name) for name in required):
        raise SignerError("signing material is incomplete")
    try:
        keystore_bytes = base64.b64decode(environ[required[0]], validate=True)
    except (ValueError, binascii.Error) as error:
        raise SignerError("keystore secret is not strict base64") from error

    if _bundle_value(runner, candidate, "/manifest/@android:versionName") != "Preview12":
        raise SignerError("candidate versionName is not Preview12")
    if _bundle_value(runner, candidate, "/manifest/@android:versionCode") != "12":
        raise SignerError("candidate versionCode is not 12")
    output_dir = Path(args.output_dir)
    if output_dir.exists():
        raise SignerError("signed output already exists")
    tool_env = {
        key: environ[key]
        for key in ("HOME", "JAVA_HOME", "LANG", "PATH", "TMPDIR")
        if environ.get(key)
    }
    tool_env["FLEET_STOREPASS"] = environ[required[1]]
    tool_env["FLEET_KEYPASS"] = environ[required[2]]
    tool_env["LC_ALL"] = "C"
    with tempfile.TemporaryDirectory(prefix="fleet-keystore-") as key_temp:
        keystore = Path(key_temp) / "upload.keystore"
        keystore.write_bytes(keystore_bytes)
        keystore.chmod(0o600)
        certificate = _checked(
            runner,
            ["/opt/jdk/bin/keytool", "-exportcert", "-alias", lock["signing"]["key_alias"], "-keystore", str(keystore), "-storepass:env", "FLEET_STOREPASS"],
            env=tool_env,
        ).stdout
        expected_cert = lock["signing"]["expected_upload_certificate_sha256"]
        if hashlib.sha256(certificate).hexdigest() != expected_cert:
            raise SignerError("keystore certificate does not match the expected upload certificate")
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=f".{output_dir.name}-", dir=output_dir.parent) as stage_name:
            stage = Path(stage_name)
            signed = stage / lock["release"]["signed_file_name"]
            shutil.copyfile(candidate, signed)
            _checked(
                runner,
                ["/opt/jdk/bin/jarsigner", "-keystore", str(keystore), "-storepass:env", "FLEET_STOREPASS", "-keypass:env", "FLEET_KEYPASS", "-sigalg", lock["signing"]["signature_algorithm"], "-digestalg", lock["signing"]["digest_algorithm"], str(signed), lock["signing"]["key_alias"]],
                env=tool_env,
            )
            verify = _checked(
                runner,
                ["/opt/jdk/bin/jarsigner", "-verify", "-verbose", "-certs", str(signed)],
                text=True,
                env=tool_env,
            )
            if "jar verified." not in verify.stdout:
                raise SignerError("jarsigner did not verify the signed bundle")
            signed_cert = _checked(
                runner,
                ["/opt/jdk/bin/keytool", "-printcert", "-jarfile", str(signed), "-rfc"],
                text=True,
            ).stdout
            if hashlib.sha256(_pem_der(signed_cert)).hexdigest() != expected_cert:
                raise SignerError("signed bundle certificate does not match the expected upload certificate")
            transaction_id = hashlib.sha256(
                f"{receipt['source_sha']}:{receipt['artifact_id']}:{receipt['candidate_sha256']}:{args.running_image}".encode()
            ).hexdigest()
            attestation = {
                "contract_name": "fleet.android_preview12_signed_attestation.v1",
                "transaction_id": transaction_id,
                "source": receipt,
                "signed_file": signed.name,
                "signed_sha256": _sha256(signed),
                "upload_certificate_sha256": expected_cert,
                "signer_image": args.running_image,
                "signer_contract_sha256": hashlib.sha256(lock_bytes).hexdigest(),
                "toolchain_lock_sha256": hashlib.sha256(toolchain_bytes).hexdigest(),
                "github_runtime": runtime,
                "signing_invocations": 1,
                "publication": False,
                "upload": False,
            }
            (stage / "signed-attestation.json").write_text(
                json.dumps(attestation, sort_keys=True, indent=2) + "\n", encoding="utf-8"
            )
            os.replace(stage, output_dir)
        return attestation


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", required=True, type=Path)
    parser.add_argument("--toolchain-lock", required=True, type=Path)
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser("preflight")
    check.add_argument("--signer-image", default="")
    check.add_argument("--execution-repository", required=True)
    check.add_argument("--execution-ref", required=True)
    check.add_argument("--execution-ref-protected", required=True)
    check.add_argument("--workflow-ref", required=True)
    check.add_argument("--workflow-sha", required=True)
    check.add_argument("--github-output")
    intake_parser = subparsers.add_parser("intake")
    for name in ("source-sha", "candidate-run-id", "verification-run-id", "artifact-id", "artifact-sha256", "candidate-sha256", "output-dir"):
        intake_parser.add_argument(f"--{name}", required=True)
    sign_parser = subparsers.add_parser("sign")
    sign_parser.add_argument("--candidate-dir", required=True)
    sign_parser.add_argument("--output-dir", required=True)
    sign_parser.add_argument("--running-image", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        lock, lock_bytes = _load_lock(args.lock)
        toolchain, toolchain_bytes = _load_toolchain(args.toolchain_lock)
        if args.command == "preflight":
            result = preflight(args, lock, toolchain, toolchain_bytes)
        elif args.command == "intake":
            result = intake(
                args,
                lock,
                lock_bytes,
                toolchain,
                toolchain_bytes,
                GitHubClient(os.environ.get("ANDROID_PREVIEW12_CANDIDATE_BROKER_TOKEN", "")),
            )
        else:
            result = sign(args, lock, lock_bytes, toolchain, toolchain_bytes, os.environ)
    except (OSError, KeyError, ValueError, binascii.Error, json.JSONDecodeError, zipfile.BadZipFile, SignerError) as error:
        print(f"android-preview12-signer: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
