"""Cross-repo serialization/signature contract, not release or build evidence.

Run with CHUMMER_ANDROID_388_ROOT pointing to the exact locked Android checkout.
Artifact and qualification fixtures are synthetic; Android's schema, validation,
canonicalization, and cryptographic verification are the real pinned code.
All key material is disposable test-only material in pytest's temporary root.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def real_consumer(tmp_path: Path, monkeypatch, request):
    configured = os.environ.get("CHUMMER_ANDROID_388_ROOT")
    if not configured:
        pytest.skip("requires an explicit exact-locked Android checkout")
    path = ROOT / "scripts/android_preview12_external_rebuilder.py"
    spec = importlib.util.spec_from_file_location("fleet_real_v2_bridge_test", path)
    assert spec and spec.loader
    fleet = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fleet)
    lock, _ = fleet.load_lock(ROOT / "config/release/android-preview12-external-rebuilder.lock.json")
    android = fleet.validate_android_consumer(Path(configured), lock)
    tmp_path.chmod(0o700)
    private_key = tmp_path / "disposable-test-only.private.pem"
    public_key = tmp_path / "disposable-test-only.public.pem"
    # Register before creation so setup failures also remove test keys.
    request.addfinalizer(lambda: private_key.unlink(missing_ok=True))
    request.addfinalizer(lambda: public_key.unlink(missing_ok=True))
    clean_env = {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"}
    subprocess.run(
        ["/usr/bin/openssl", "genpkey", "-algorithm", "ED25519", "-out", str(private_key)],
        check=True, capture_output=True, timeout=20, env=clean_env,
    )
    private_key.chmod(0o600)
    subprocess.run(
        ["/usr/bin/openssl", "pkey", "-in", str(private_key), "-pubout", "-out", str(public_key)],
        check=True, capture_output=True, timeout=20, env=clean_env,
    )
    public_key.chmod(0o600)
    spki = subprocess.run(
        ["/usr/bin/openssl", "pkey", "-in", str(private_key), "-pubout", "-outform", "DER"],
        check=True, capture_output=True, timeout=20, env=clean_env,
    ).stdout
    # Patch trust only inside this freshly loaded test module. No repository
    # public key, lock, real approval, or external signing key is changed.
    monkeypatch.setattr(android, "_fleet_expected_spki_sha256", hashlib.sha256(spki).hexdigest())
    monkeypatch.setattr(android.VERIFY, "RELEASE_APPROVER_PUBLIC_KEY", public_key)
    monkeypatch.setattr(android.VERIFY, "RELEASE_APPROVER_PUBLIC_KEY_SHA256",
                        hashlib.sha256(public_key.read_bytes()).hexdigest())
    digest = "1" * 64
    claims = {
        "sourceCommit": "2" * 40, "sourceTree": "3" * 40,
        "designCommit": "4" * 40, "designTree": "5" * 40,
        "designTreeSha256": digest,
        "aab": {"sha256": digest, "sizeBytes": 1},
        "sourceGraph": {"sha256": digest}, "buildSidecar": {"sha256": digest},
        "twoGreen": {"receiptSha256": digest, "approvalSha256": digest},
        "graph": {
            "releaseIdentity": {"packageId": fleet.PACKAGE_ID,
                                "versionName": fleet.VERSION_NAME, "versionCode": 12},
            "generatedAtUtc": "2026-01-01T00:00:00Z",
        },
    }
    qualification = {"eligibilitySha256": digest,
                     "protectedApproval": {"provenanceReplaySha256": digest}}
    monkeypatch.setattr(android, "_artifact_claims", lambda *_: deepcopy(claims))
    monkeypatch.setattr(android.VERIFY, "verify_release_eligibility",
                        lambda *_args, **_kwargs: deepcopy(qualification))
    validation = {
        "contractName": android.VALIDATION_CONTRACT, "status": "pass",
        "bundletoolSha256": android.EXPECTED_BUNDLETOOL_SHA256,
        "uploadCertificateSha256": android.EXPECTED_UPLOAD_CERTIFICATE_SHA256,
        "toolchainAuthorityClass": "non_authoritative_local_unsigned_preparation",
        "androidSdkBound": False,
        "javaToolSha256": {name: digest for name in ("java", "javac", "jarsigner", "keytool")},
        "validatorSha256": dict(android.VALIDATOR_STARTUP_SHA256),
        "publicationAuthorized": False,
        **{name: digest for name in (
            "uploadCertificateFileSha256", "javaToolAuthoritySha256", "javaVersionOutputSha256",
            "javaSdkTreeSha256", "dotnetSha256", "dotnetVersionOutputSha256", "dotnetSdkTreeSha256",
            "aabValidationOutputSha256", "artifactHygieneOutputSha256", "sourceGraphValidationOutputSha256",
        )},
    }
    artifacts = tuple(tmp_path / name for name in ("fixture.aab", "graph.json", "sidecar", "receipt", "approval"))
    yield fleet, android, private_key, validation, artifacts


def test_real_android_v2_accepts_bridge_bytes_and_rejects_tampering(real_consumer, tmp_path: Path):
    fleet, android, key, validation, artifacts = real_consumer
    output = tmp_path / "TEST_ONLY_android-v2.json"
    value = fleet.android_v2_attestation(
        android, *artifacts, validation, key, output,
        now=datetime.now(UTC), nonce="a" * 64,
    )
    assert set(value) == {
        "contractName", "algorithm", "keyId", "role", "attestationScope",
        "generatedAtUtc", "challengeNonce", "releaseIdentity", "sourceCommit", "sourceTree",
        "designCommit", "designTree", "designTreeSha256", "aab", "sourceGraph", "buildSidecar",
        "twoGreen", "protectedValidation", "signingAuthorized", "publicationAuthorized",
        "googlePlayUploadAuthorized", "signatureBase64",
    }
    assert output.read_bytes() == android._pretty(value)
    assert android.verify(output, *artifacts)["sourceCommit"] == "2" * 40

    # Valid JSON carrying the very same signed values must still use exact
    # Android pretty bytes, not Fleet compact serialization.
    output.write_bytes(json.dumps(value, sort_keys=True).encode())
    with pytest.raises(ValueError, match="exact protected outputs"):
        android.verify(output, *artifacts)

    tampered = deepcopy(value)
    tampered["sourceCommit"] = "6" * 40
    output.write_bytes(android._pretty(tampered))
    with pytest.raises(ValueError, match="signature is invalid"):
        android.verify(output, *artifacts)

    tampered = deepcopy(value)
    tampered["contract_name"] = fleet.FLEET_AUDIT_CONTRACT
    output.write_bytes(android._pretty(tampered))
    with pytest.raises(ValueError, match="fields are not exact"):
        android.verify(output, *artifacts)


@pytest.mark.parametrize("change", [
    {"androidSdkBound": True},
    {"publicationAuthorized": True},
    {"toolchainAuthorityClass": "externally_authoritative"},
    {"proofInstrumentationPresent": True},
    {"validatorSha256": {}},
])
def test_real_android_validation_rejects_escalated_or_incomplete_claims(
    real_consumer, tmp_path: Path, change: dict,
):
    fleet, android, key, validation, artifacts = real_consumer
    output = tmp_path / "must-not-exist.json"
    with pytest.raises(ValueError):
        fleet.android_v2_attestation(android, *artifacts, {**validation, **change}, key, output)
    assert not output.exists()
