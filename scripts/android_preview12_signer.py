#!/usr/bin/env python3
"""Trusted Preview12 intake, durable reservation, and one-shot signer."""
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
ANDROID_REPOSITORY = "ArchonMegalon/chummer-android"
VERIFIER_REF = f"{FLEET_REPOSITORY}/.github/workflows/android-preview12-verifier.yml@refs/heads/main"
SIGNER_REF = f"{FLEET_REPOSITORY}/.github/workflows/android-preview12-signer.yml@refs/heads/main"


class SignerError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _load(path: Path, contract: str) -> tuple[dict[str, Any], bytes]:
    payload = path.read_bytes()
    value = json.loads(payload)
    if value.get("contract_name") != contract:
        raise SignerError(f"unexpected {contract} contract")
    return value, payload


def _load_lock(path: Path):
    return _load(path, "fleet.android_preview12_signer_transaction.v2")


def _load_toolchain(path: Path):
    return _load(path, "fleet.android_preview12_toolchain.v1")


def _full_image(lock: Mapping[str, Any]) -> str | None:
    value = lock["toolchain"]
    return f"{value['image_repository']}@{value['image_digest']}" if value.get("image_digest") else None


def _positive(value: Any, label: str) -> int:
    text = str(value)
    if not text.isascii() or not text.isdigit() or int(text) < 1:
        raise SignerError(f"{label} must be a positive integer")
    return int(text)


def provisioning_blockers(lock, signer_image: str, toolchain, toolchain_bytes: bytes) -> list[str]:
    failures: list[str] = []
    if lock.get("state") != "ready":
        failures.append("lock state is not ready")
    release = lock.get("release", {})
    if (release.get("version_name"), release.get("version_code")) != ("Preview12", 12):
        failures.append("release identity is not exact Preview12/code12")
    for field in ("candidate_file_name", "signed_file_name"):
        if not isinstance(release.get(field), str) or not release[field].endswith(".aab"):
            failures.append(f"release.{field} is not provisioned")
    source = lock.get("source", {})
    if (source.get("repository"), source.get("repository_id")) != (ANDROID_REPOSITORY, 1331626697):
        failures.append("canonical Android source repository drifted")
    if not str(source.get("source_ref") or "").startswith("refs/heads/"):
        failures.append("source.source_ref is not provisioned")
    if source.get("discovery_receipt", {}).get("preview12_workflow_found") is not True:
        failures.append("canonical repository discovery found no Preview12 producer")
    for kind in ("candidate", "verification"):
        spec = source.get(kind, {})
        for field in ("workflow_id", "run_attempt"):
            if not isinstance(spec.get(field), int) or spec[field] < 1:
                failures.append(f"source.{kind}.{field} is not provisioned")
        for field in ("workflow_path", "artifact_name"):
            if not isinstance(spec.get(field), str) or not spec[field]:
                failures.append(f"source.{kind}.{field} is not provisioned")
        for field in ("workflow_blob_sha",):
            if not HEX40.fullmatch(str(spec.get(field) or "")):
                failures.append(f"source.{kind}.{field} is not provisioned")
        if spec.get("event") not in ("push", "workflow_dispatch"):
            failures.append(f"source.{kind}.event is not provisioned")
    if source.get("candidate", {}).get("workflow_id") == source.get("verification", {}).get("workflow_id"):
        failures.append("candidate and verification workflows must be distinct")
    candidate = source.get("candidate", {})
    verification = source.get("verification", {})
    if not HEX64.fullmatch(str(candidate.get("producer_toolchain_closure_sha256") or "")):
        failures.append("producer toolchain closure is not provisioned")
    if not isinstance(verification.get("receipt_file_name"), str):
        failures.append("verification receipt file name is not provisioned")
    reservation = lock.get("reservation", {})
    if reservation.get("enabled") is not True:
        failures.append("durable exactly-once reservation is disabled")
    if not str(reservation.get("broker_url") or "").startswith("https://"):
        failures.append("reservation broker URL is not provisioned")
    if not HEX64.fullmatch(str(reservation.get("audited_implementation_sha256") or "")):
        failures.append("reservation implementation audit is not provisioned")
    signing = lock.get("signing", {})
    if signing.get("enabled") is not True:
        failures.append("signing is disabled")
    if signing.get("signature_algorithm") not in ("SHA256withRSA", "SHA256withECDSA"):
        failures.append("upload-key signature algorithm is not provisioned")
    if not HEX64.fullmatch(str(signing.get("expected_upload_certificate_sha256") or "")):
        failures.append("expected upload certificate SHA-256 is not provisioned")
    tool = lock.get("toolchain", {})
    image = _full_image(lock)
    if not image or not re.fullmatch(r"[^@]+@sha256:[0-9a-f]{64}", image):
        failures.append("signer OCI digest is not provisioned")
    elif signer_image != image:
        failures.append("runner signer image does not equal locked OCI digest")
    if hashlib.sha256(toolchain_bytes).hexdigest() != tool.get("lock_sha256"):
        failures.append("toolchain lock SHA-256 mismatch")
    if not HEX64.fullmatch(str(tool.get("installed_receipt_sha256") or "")):
        failures.append("installed signer receipt SHA-256 is not provisioned")
    if toolchain.get("platform") != tool.get("platform"):
        failures.append("toolchain platform drifted")
    for item in [*toolchain.get("base_images", []), *toolchain.get("archives", [])]:
        digest = str(item.get("digest", item.get("sha256", ""))).removeprefix("sha256:")
        if not HEX64.fullmatch(digest):
            failures.append(f"toolchain input {item.get('name')} is not SHA-256 locked")
    handoff = lock.get("signed_content_handoff", {})
    if handoff.get("enabled") is not True:
        failures.append("private signed-content handoff is disabled")
    if not str(handoff.get("private_content_addressed_endpoint") or "").startswith("https://"):
        failures.append("private signed-content handoff endpoint is not provisioned")
    if not HEX64.fullmatch(str(handoff.get("audited_implementation_sha256") or "")):
        failures.append("private signed-content handoff implementation is not provisioned")
    envs, publication = lock.get("environments", {}), lock.get("publication", {})
    if tuple(envs.get(k) for k in ("intake", "signing", "play_upload")) != (
        "android-preview12-intake", "android-preview12-signing", "android-play-upload"
    ):
        failures.append("protected environment names drifted")
    if envs.get("play_upload_enabled") is not False:
        failures.append("Play upload environment must remain disabled")
    if publication.get("intake_actions_artifact_is_private_ci_evidence") is not True:
        failures.append("intake Actions artifact must remain private CI evidence")
    for key in ("signed_aab_actions_artifact", "registry_publication", "play_upload", "github_release"):
        if publication.get(key) is not False:
            failures.append(f"publication.{key} must remain false")
    return failures


def preflight(args, lock, toolchain, toolchain_bytes: bytes) -> dict[str, Any]:
    failures = provisioning_blockers(lock, args.signer_image, toolchain, toolchain_bytes)
    expected = {
        "execution_repository": FLEET_REPOSITORY,
        "execution_ref": "refs/heads/main",
        "execution_ref_protected": "true",
        "execution_event": "workflow_dispatch",
        "workflow_repository": FLEET_REPOSITORY,
        "workflow_ref": VERIFIER_REF,
    }
    for field, value in expected.items():
        if getattr(args, field) != value:
            failures.append(f"{field} is not the protected Fleet verifier value")
    if not HEX40.fullmatch(args.execution_sha) or args.workflow_sha != args.execution_sha:
        failures.append("job_workflow_sha is not the exact Fleet execution SHA")
    if failures:
        raise SignerError("; ".join(failures))
    values = {
        "signer_image": _full_image(lock),
        "intake_environment": lock["environments"]["intake"],
        "signing_environment": lock["environments"]["signing"],
    }
    if args.github_output:
        with Path(args.github_output).open("a", encoding="utf-8") as output:
            for key, value in values.items():
                output.write(f"{key}={value}\n")
    return {"ok": True, **values, "play_upload_performed": False, "publication_performed": False}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):  # noqa: ANN001
        return None


class GitHubClient:
    def __init__(self, token: str):
        if not token:
            raise SignerError("candidate broker credential is missing")
        self.headers = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}",
                        "User-Agent": "fleet-preview12-intake/2", "X-GitHub-Api-Version": "2022-11-28"}

    def get_json(self, url: str) -> dict[str, Any]:
        with urllib.request.urlopen(urllib.request.Request(url, headers=self.headers), timeout=30) as response:
            return json.load(response)

    def download_to(self, url: str, output: Path, limit: int) -> None:
        request = urllib.request.Request(url, headers=self.headers)
        try:
            response = urllib.request.build_opener(_NoRedirect()).open(request, timeout=30)
        except urllib.error.HTTPError as error:
            if error.code not in (301, 302, 303, 307, 308):
                raise
            location = error.headers.get("Location", "")
            parsed = urllib.parse.urlparse(location)
            if parsed.scheme != "https" or not parsed.hostname:
                raise SignerError("artifact broker returned an unsafe redirect") from error
            response = urllib.request.urlopen(urllib.request.Request(location, headers={"User-Agent": self.headers["User-Agent"]}), timeout=60)
        total = 0
        with response, output.open("wb") as stream:
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > limit:
                    raise SignerError("artifact exceeds locked size limit")
                stream.write(chunk)


class ReservationClient:
    def __init__(self, url: str, token: str):
        if not token:
            raise SignerError("reservation broker credential is missing")
        self.url, self.token = url, token

    def reserve(self, request_value: Mapping[str, Any]) -> dict[str, Any]:
        transaction = str(request_value["transaction_id"])
        request = urllib.request.Request(self.url, data=_json_bytes(request_value), method="POST", headers={
            "Authorization": f"Bearer {self.token}", "Content-Type": "application/json",
            "Idempotency-Key": transaction, "User-Agent": "fleet-preview12-reservation/1"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            raise SignerError("reservation outcome is indeterminate") from error


def _validate_run(run, run_id: int, source, source_sha: str, spec) -> None:
    expected = {"id": run_id, "run_attempt": spec["run_attempt"], "event": spec["event"],
                "head_sha": source_sha, "head_branch": source["source_ref"].removeprefix("refs/heads/"),
                "workflow_id": spec["workflow_id"], "path": spec["workflow_path"],
                "status": "completed", "conclusion": "success"}
    for field, value in expected.items():
        if run.get(field) != value:
            raise SignerError(f"run {run_id} has unexpected {field}")
    for field in ("repository", "head_repository"):
        repo = run.get(field) or {}
        if (repo.get("id"), repo.get("full_name")) != (source["repository_id"], source["repository"]):
            raise SignerError(f"run {run_id} has unexpected {field}")


def _validate_workflow_blob(client, api: str, spec, source_sha: str) -> None:
    path = urllib.parse.quote(spec["workflow_path"], safe="/")
    value = client.get_json(f"{api}/contents/{path}?ref={source_sha}")
    if (value.get("path"), value.get("sha")) != (spec["workflow_path"], spec["workflow_blob_sha"]):
        raise SignerError("workflow path/blob SHA does not match the run commit")


def _validate_artifact(value, artifact_id: int, run_id: int, name: str, digest: str, api: str) -> str:
    expected_url = f"{api}/actions/artifacts/{artifact_id}/zip"
    if (value.get("id"), value.get("name"), value.get("expired"), value.get("digest")) != (
        artifact_id, name, False, f"sha256:{digest}"):
        raise SignerError("artifact identity/digest does not match the locked contract")
    if value.get("workflow_run", {}).get("id") != run_id or value.get("archive_download_url") != expected_url:
        raise SignerError("artifact is not bound to the exact workflow run")
    return expected_url


def _safe_member(bundle: zipfile.ZipFile, expected: str, limit: int) -> zipfile.ZipInfo:
    matches, seen = [], set()
    for member in bundle.infolist():
        pure = PurePosixPath(member.filename)
        if pure.is_absolute() or ".." in pure.parts or member.filename in seen or "\\" in member.filename:
            raise SignerError("unsafe or duplicate artifact member")
        seen.add(member.filename)
        if stat.S_ISLNK(member.external_attr >> 16):
            raise SignerError("artifact contains a symlink")
        if not member.is_dir() and member.filename == expected:
            matches.append(member)
    if len(matches) != 1 or matches[0].file_size > limit:
        raise SignerError("artifact lacks exactly one bounded expected file")
    return matches[0]


def _extract(archive: Path, expected: str, output: Path, limit: int) -> None:
    with zipfile.ZipFile(archive) as bundle:
        member = _safe_member(bundle, expected, limit)
        with bundle.open(member) as source, output.open("wb") as target:
            shutil.copyfileobj(source, target)


def _assert_unsigned_aab(path: Path) -> None:
    try:
        with zipfile.ZipFile(path) as bundle:
            names = [name.upper() for name in bundle.namelist()]
    except zipfile.BadZipFile as error:
        raise SignerError("candidate is not an Android App Bundle ZIP") from error
    signature = re.compile(r"^META-INF/[^/]+\.(SF|RSA|DSA|EC)$")
    if len(names) != len(set(names)) or any(signature.fullmatch(name) for name in names):
        raise SignerError("candidate is already signed or has duplicate members")


def _producer_receipt_expected(lock, args, source_sha: str, digests: Mapping[str, str]) -> dict[str, Any]:
    source, candidate, verification = lock["source"], lock["source"]["candidate"], lock["source"]["verification"]
    return {
        "contract_name": "chummer_android.preview12_signer_eligibility.v1", "eligible": True,
        "source_repository": source["repository"], "source_repository_id": source["repository_id"],
        "source_ref": source["source_ref"], "source_sha": source_sha,
        "candidate": {"run_id": int(args.candidate_run_id), "run_attempt": candidate["run_attempt"],
            "workflow_id": candidate["workflow_id"], "workflow_path": candidate["workflow_path"],
            "workflow_blob_sha": candidate["workflow_blob_sha"], "artifact_id": int(args.candidate_artifact_id),
            "artifact_name": candidate["artifact_name"], "artifact_sha256": digests["candidate_artifact"],
            "aab_file_name": lock["release"]["candidate_file_name"], "aab_sha256": digests["candidate_aab"],
            "producer_toolchain_closure_sha256": candidate["producer_toolchain_closure_sha256"]},
        "verification": {"run_id": int(args.verification_run_id), "run_attempt": verification["run_attempt"],
            "workflow_id": verification["workflow_id"], "workflow_path": verification["workflow_path"],
            "workflow_blob_sha": verification["workflow_blob_sha"], "artifact_id": int(args.verification_artifact_id),
            "artifact_name": verification["artifact_name"]},
        "publication_authorized": False, "play_upload_authorized": False,
    }


def intake(args, lock, lock_bytes: bytes, toolchain, toolchain_bytes: bytes, client) -> dict[str, Any]:
    failures = provisioning_blockers(lock, _full_image(lock) or "", toolchain, toolchain_bytes)
    if failures:
        raise SignerError("; ".join(failures))
    source_sha = args.source_sha.lower()
    digests = {key: getattr(args, f"{key}_sha256").lower() for key in (
        "candidate_artifact", "candidate_aab", "verification_artifact", "verification_receipt")}
    if not HEX40.fullmatch(source_sha) or any(not HEX64.fullmatch(value) for value in digests.values()):
        raise SignerError("source and artifact inputs require exact SHA-1/SHA-256 digests")
    ids = {key: _positive(getattr(args, key), key) for key in (
        "candidate_run_id", "candidate_artifact_id", "verification_run_id", "verification_artifact_id")}
    if ids["candidate_run_id"] == ids["verification_run_id"]:
        raise SignerError("candidate and verification run IDs must be distinct")
    source, api = lock["source"], f"https://api.github.com/repos/{ANDROID_REPOSITORY}"
    for kind in ("candidate", "verification"):
        run_id = ids[f"{kind}_run_id"]
        _validate_run(client.get_json(f"{api}/actions/runs/{run_id}"), run_id, source, source_sha, source[kind])
        _validate_workflow_blob(client, api, source[kind], source_sha)
    artifact_urls = {}
    for kind in ("candidate", "verification"):
        artifact_id, run_id = ids[f"{kind}_artifact_id"], ids[f"{kind}_run_id"]
        artifact_urls[kind] = _validate_artifact(
            client.get_json(f"{api}/actions/artifacts/{artifact_id}"), artifact_id, run_id,
            source[kind]["artifact_name"], digests[f"{kind}_artifact"], api)
    output_dir = Path(args.output_dir)
    if output_dir.exists():
        raise SignerError("intake output already exists")
    with tempfile.TemporaryDirectory(prefix="fleet-intake-") as temporary:
        temporary_path = Path(temporary)
        archives = {kind: temporary_path / f"{kind}.zip" for kind in ("candidate", "verification")}
        for kind in archives:
            client.download_to(artifact_urls[kind], archives[kind], int(lock["limits"]["artifact_max_bytes"]))
            if _sha256(archives[kind]) != digests[f"{kind}_artifact"]:
                raise SignerError(f"downloaded {kind} artifact digest mismatch")
        candidate = temporary_path / lock["release"]["candidate_file_name"]
        verification_receipt = temporary_path / source["verification"]["receipt_file_name"]
        _extract(archives["candidate"], candidate.name, candidate, int(lock["limits"]["candidate_max_bytes"]))
        _extract(archives["verification"], verification_receipt.name, verification_receipt, 1024 * 1024)
        if _sha256(candidate) != digests["candidate_aab"] or _sha256(verification_receipt) != digests["verification_receipt"]:
            raise SignerError("candidate or producer verification receipt digest mismatch")
        _assert_unsigned_aab(candidate)
        producer_receipt = json.loads(verification_receipt.read_text(encoding="utf-8"))
        if producer_receipt != _producer_receipt_expected(lock, args, source_sha, digests):
            raise SignerError("producer verification receipt does not bind the exact candidate transaction")
        receipt = {"contract_name": "fleet.android_preview12_trusted_intake.v2", "producer": producer_receipt,
            "verification_artifact_sha256": digests["verification_artifact"],
            "verification_receipt_sha256": digests["verification_receipt"],
            "signer_contract_sha256": hashlib.sha256(lock_bytes).hexdigest(),
            "ci_transport_role": "private_actions_artifact_sanitized_intake", "signed_aab_actions_artifact_uploaded": False,
            "play_upload_performed": False, "publication_performed": False}
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=f".{output_dir.name}-", dir=output_dir.parent) as stage_name:
            stage = Path(stage_name)
            shutil.copyfile(candidate, stage / candidate.name)
            (stage / "signer.lock.json").write_bytes(lock_bytes)
            (stage / "intake-attestation.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
            os.replace(stage, output_dir)
    return receipt


def _installed_receipt(path: Path, lock, toolchain, toolchain_bytes: bytes) -> None:
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != lock["toolchain"]["installed_receipt_sha256"]:
        raise SignerError("installed signer receipt digest mismatch")
    actual = json.loads(payload)
    expected = {"contract_name": "fleet.android_preview12_installed_toolchain.v1",
        "lock_sha256": hashlib.sha256(toolchain_bytes).hexdigest(), "base_images": toolchain["base_images"],
        "archives": [{key: item[key] for key in ("name", "version", "url", "sha256")} for item in toolchain["archives"]]}
    if actual != expected:
        raise SignerError("installed signer receipt does not match the full toolchain closure")


def _intake_receipt(path: Path, lock_bytes: bytes, candidate: Path) -> dict[str, Any]:
    receipt = json.loads((path / "intake-attestation.json").read_text())
    if receipt.get("contract_name") != "fleet.android_preview12_trusted_intake.v2":
        raise SignerError("trusted intake attestation is missing")
    if receipt.get("signer_contract_sha256") != hashlib.sha256(lock_bytes).hexdigest():
        raise SignerError("signer contract changed after trusted intake")
    expected = receipt.get("producer", {}).get("candidate", {}).get("aab_sha256")
    if not candidate.is_file() or _sha256(candidate) != expected:
        raise SignerError("candidate changed after trusted intake")
    _assert_unsigned_aab(candidate)
    return receipt


def _runtime(environ: Mapping[str, str]) -> dict[str, str | None]:
    value = {"repository": environ.get("GITHUB_REPOSITORY"), "event": environ.get("GITHUB_EVENT_NAME"),
        "sha": environ.get("GITHUB_SHA"), "workflow_repository": environ.get("FLEET_WORKFLOW_REPOSITORY"),
        "workflow_ref": environ.get("FLEET_WORKFLOW_REF"), "workflow_sha": environ.get("FLEET_WORKFLOW_SHA"),
        "runner_environment": environ.get("RUNNER_ENVIRONMENT"),
        "signing_environment": environ.get("FLEET_SIGNING_ENVIRONMENT"), "run_id": environ.get("GITHUB_RUN_ID"),
        "run_attempt": environ.get("GITHUB_RUN_ATTEMPT")}
    if (value["repository"], value["event"], value["workflow_repository"], value["workflow_ref"],
        value["runner_environment"], value["signing_environment"], value["run_attempt"]) != (
        FLEET_REPOSITORY, "workflow_dispatch", FLEET_REPOSITORY, SIGNER_REF, "github-hosted",
        "android-preview12-signing", "1") or not HEX40.fullmatch(str(value["sha"] or "")) \
            or value["workflow_sha"] != value["sha"] or not str(value["run_id"] or "").isdigit():
        raise SignerError("runtime is not the Fleet-native protected GitHub-hosted signer")
    return value


def _transaction(lock, lock_bytes: bytes, intake_receipt, image: str) -> tuple[str, dict[str, Any]]:
    candidate = intake_receipt["producer"]["candidate"]
    bindings = {"source_sha": intake_receipt["producer"]["source_sha"], "candidate_run_id": candidate["run_id"],
        "candidate_artifact_id": candidate["artifact_id"], "candidate_artifact_sha256": candidate["artifact_sha256"],
        "candidate_aab_sha256": candidate["aab_sha256"], "upload_certificate_sha256": lock["signing"]["expected_upload_certificate_sha256"],
        "signer_image": image, "signer_contract_sha256": hashlib.sha256(lock_bytes).hexdigest()}
    return hashlib.sha256(_json_bytes(bindings)).hexdigest(), bindings


def reserve(args, lock, lock_bytes, toolchain, toolchain_bytes, environ, client) -> dict[str, Any]:
    failures = provisioning_blockers(lock, args.running_image, toolchain, toolchain_bytes)
    if failures:
        raise SignerError("; ".join(failures))
    candidate_dir = Path(args.candidate_dir)
    receipt = _intake_receipt(candidate_dir, lock_bytes, candidate_dir / lock["release"]["candidate_file_name"])
    _installed_receipt(Path(args.installed_toolchain_receipt), lock, toolchain, toolchain_bytes)
    _runtime(environ)
    transaction_id, bindings = _transaction(lock, lock_bytes, receipt, args.running_image)
    request_value = {"contract_name": "fleet.android_preview12_reservation_request.v1",
                     "transaction_id": transaction_id, "bindings": bindings}
    response = client.reserve(request_value)
    expected = {"contract_name": "fleet.android_preview12_reservation.v1", "decision": "reserved",
        "created": True, "durable": True, "transaction_id": transaction_id,
        "request_sha256": hashlib.sha256(_json_bytes(request_value)).hexdigest(), "bindings": bindings}
    if response != expected:
        decision = response.get("decision", "indeterminate") if isinstance(response, dict) else "indeterminate"
        raise SignerError(f"reservation rejected: {decision}")
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(response, sort_keys=True, indent=2) + "\n")
    return response


def _checked(runner: Callable[..., subprocess.CompletedProcess], command: list[str], **kwargs):
    result = runner(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, **kwargs)
    if result.returncode:
        raise SignerError(f"trusted tool failed: {Path(command[0]).name}")
    return result


def _tool_env(home: str) -> dict[str, str]:
    return {"HOME": home, "TMPDIR": home, "JAVA_HOME": "/opt/jdk", "PATH": "/opt/jdk/bin:/usr/bin:/bin",
            "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TZ": "UTC"}


def _bundle_value(runner, candidate: Path, xpath: str, env) -> str:
    result = _checked(runner, ["/opt/jdk/bin/java", "-jar", "/opt/android-sdk/tools/bundletool.jar", "dump",
        "manifest", f"--bundle={candidate}", f"--xpath={xpath}"], text=True, env=env)
    return result.stdout.strip()


def _pem_der(payload: str) -> bytes:
    match = re.search(r"-----BEGIN CERTIFICATE-----(.*?)-----END CERTIFICATE-----", payload, re.S)
    if not match:
        raise SignerError("signed bundle did not expose a certificate")
    return base64.b64decode(re.sub(r"\s+", "", match.group(1)), validate=True)


def sign(args, lock, lock_bytes, toolchain, toolchain_bytes, environ,
         runner: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> dict[str, Any]:
    failures = provisioning_blockers(lock, args.running_image, toolchain, toolchain_bytes)
    if failures:
        raise SignerError("; ".join(failures))
    candidate_dir = Path(args.candidate_dir)
    candidate = candidate_dir / lock["release"]["candidate_file_name"]
    intake_receipt = _intake_receipt(candidate_dir, lock_bytes, candidate)
    _installed_receipt(Path(args.installed_toolchain_receipt), lock, toolchain, toolchain_bytes)
    runtime = _runtime(environ)
    transaction_id, bindings = _transaction(lock, lock_bytes, intake_receipt, args.running_image)
    reservation = json.loads(Path(args.reservation_receipt).read_text())
    reservation_request = {"contract_name": "fleet.android_preview12_reservation_request.v1",
                           "transaction_id": transaction_id, "bindings": bindings}
    if reservation != {"contract_name": "fleet.android_preview12_reservation.v1", "decision": "reserved",
        "created": True, "durable": True, "transaction_id": transaction_id,
        "request_sha256": hashlib.sha256(_json_bytes(reservation_request)).hexdigest(), "bindings": bindings}:
        raise SignerError("durable reservation receipt is missing or does not bind this transaction")
    output_dir = Path(args.output_dir)
    if output_dir.exists():
        raise SignerError("signed output already exists")
    with tempfile.TemporaryDirectory(prefix="fleet-secret-free-") as scratch:
        clean_env = _tool_env(scratch)
        if _bundle_value(runner, candidate, "/manifest/@android:versionName", clean_env) != "Preview12" \
                or _bundle_value(runner, candidate, "/manifest/@android:versionCode", clean_env) != "12":
            raise SignerError("candidate manifest is not exact Preview12/code12")
        names = ("ANDROID_PREVIEW12_UPLOAD_KEYSTORE_B64", "ANDROID_PREVIEW12_KEYSTORE_PASSWORD",
                 "ANDROID_PREVIEW12_KEY_PASSWORD")
        if any(not environ.get(name) for name in names):
            raise SignerError("signing material is incomplete")
        try:
            keystore_bytes = base64.b64decode(environ[names[0]], validate=True)
        except (ValueError, binascii.Error) as error:
            raise SignerError("keystore secret is not strict base64") from error
        with tempfile.TemporaryDirectory(prefix="fleet-keystore-") as key_temp:
            keystore = Path(key_temp) / "upload.keystore"
            keystore.write_bytes(keystore_bytes)
            keystore.chmod(0o600)
            cert_env = {**clean_env, "FLEET_STOREPASS": environ[names[1]]}
            certificate = _checked(runner, ["/opt/jdk/bin/keytool", "-exportcert", "-alias",
                lock["signing"]["key_alias"], "-keystore", str(keystore), "-storepass:env", "FLEET_STOREPASS"],
                env=cert_env).stdout
            expected_cert = lock["signing"]["expected_upload_certificate_sha256"]
            if hashlib.sha256(certificate).hexdigest() != expected_cert:
                raise SignerError("keystore certificate does not match the expected upload certificate")
            output_dir.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix=f".{output_dir.name}-", dir=output_dir.parent) as stage_name:
                stage, signed = Path(stage_name), Path(stage_name) / lock["release"]["signed_file_name"]
                shutil.copyfile(candidate, signed)
                sign_env = {**cert_env, "FLEET_KEYPASS": environ[names[2]]}
                _checked(runner, ["/opt/jdk/bin/jarsigner", "-keystore", str(keystore), "-storepass:env",
                    "FLEET_STOREPASS", "-keypass:env", "FLEET_KEYPASS", "-sigalg",
                    lock["signing"]["signature_algorithm"], "-digestalg", lock["signing"]["digest_algorithm"],
                    str(signed), lock["signing"]["key_alias"]], env=sign_env)
                verify = _checked(runner, ["/opt/jdk/bin/jarsigner", "-verify", "-verbose", "-certs", str(signed)],
                                  text=True, env=clean_env)
                if "jar verified." not in verify.stdout:
                    raise SignerError("jarsigner did not verify the signed bundle")
                pem = _checked(runner, ["/opt/jdk/bin/keytool", "-printcert", "-jarfile", str(signed), "-rfc"],
                               text=True, env=clean_env).stdout
                if hashlib.sha256(_pem_der(pem)).hexdigest() != expected_cert:
                    raise SignerError("signed bundle certificate does not match expected upload certificate")
                attestation = {"contract_name": "fleet.android_preview12_signed_attestation.v2",
                    "transaction_id": transaction_id, "bindings": bindings, "signed_file": signed.name,
                    "signed_sha256": _sha256(signed), "github_runtime": runtime, "signing_invocations": 1,
                    "ci_evidence_actions_artifact_uploaded": False, "signed_content_handoff_performed": False,
                    "play_upload_performed": False, "publication_performed": False}
                (stage / "signed-attestation.json").write_text(json.dumps(attestation, sort_keys=True, indent=2) + "\n")
                os.replace(stage, output_dir)
    return attestation


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", required=True, type=Path)
    parser.add_argument("--toolchain-lock", required=True, type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("preflight")
    for name in ("signer-image", "execution-repository", "execution-ref", "execution-ref-protected",
                 "execution-event", "execution-sha", "workflow-repository", "workflow-ref", "workflow-sha"):
        check.add_argument(f"--{name}", required=True)
    check.add_argument("--github-output")
    intake_parser = commands.add_parser("intake")
    for name in ("source-sha", "candidate-run-id", "candidate-artifact-id", "candidate-artifact-sha256",
                 "candidate-aab-sha256", "verification-run-id", "verification-artifact-id",
                 "verification-artifact-sha256", "verification-receipt-sha256", "output-dir"):
        intake_parser.add_argument(f"--{name}", required=True)
    reserve_parser = commands.add_parser("reserve")
    for name in ("candidate-dir", "installed-toolchain-receipt", "running-image", "output"):
        reserve_parser.add_argument(f"--{name}", required=True)
    sign_parser = commands.add_parser("sign")
    for name in ("candidate-dir", "installed-toolchain-receipt", "reservation-receipt", "output-dir", "running-image"):
        sign_parser.add_argument(f"--{name}", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        lock, lock_bytes = _load_lock(args.lock)
        toolchain, toolchain_bytes = _load_toolchain(args.toolchain_lock)
        if args.command == "preflight":
            value = preflight(args, lock, toolchain, toolchain_bytes)
        elif args.command == "intake":
            value = intake(args, lock, lock_bytes, toolchain, toolchain_bytes,
                GitHubClient(os.environ.get("ANDROID_PREVIEW12_CANDIDATE_BROKER_TOKEN", "")))
        elif args.command == "reserve":
            value = reserve(args, lock, lock_bytes, toolchain, toolchain_bytes, os.environ,
                ReservationClient(lock["reservation"]["broker_url"], os.environ.get("ANDROID_PREVIEW12_LEDGER_TOKEN", "")))
        else:
            value = sign(args, lock, lock_bytes, toolchain, toolchain_bytes, os.environ)
    except (OSError, KeyError, TypeError, ValueError, binascii.Error, json.JSONDecodeError, zipfile.BadZipFile, SignerError) as error:
        print(f"android-preview12-signer: {error}", file=sys.stderr)
        return 2
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
