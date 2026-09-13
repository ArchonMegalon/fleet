#!/usr/bin/env python3
"""One-time GitHub environment key provisioning; never a release approval.

Private key bytes exist only in the remote process memory. Only sealed ciphertext,
public key metadata, and a domain-separated custody proof may leave this process.
Python does not guarantee zeroization of immutable byte copies.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import stat
import sys

REPOSITORY = "ArchonMegalon/fleet"
REPOSITORY_ID = "1176287728"
ENVIRONMENT = "android-preview12-release-approval"
ENVIRONMENT_ID = "21501373212"
SECRET = "ANDROID_PREVIEW12_RELEASE_APPROVAL_ED25519_PRIVATE_KEY_PKCS8_B64"
WORKFLOW = REPOSITORY + "/.github/workflows/android-release-approver-provision.yml@refs/heads/main"
OUTPUT = "android-release-approver-observation.json"
DOMAIN = b"fleet/android-release-approver/custody-proof/v1\x00"
PUBLIC_FIELDS = {"publicKeySpkiDerBase64", "publicKeySpkiSha256", "publicKeyPem", "publicKeyPemSha256"}
IDENTITY_FIELDS = {"operation", "repository", "repositoryId", "environment", "environmentId", "secretName", "workflowRef", "executionRef",
                   "executionSha", "workflowSha", "runId", "runAttempt", "requestNonce",
                   "recipientKeyId", "recipientPublicKeyBase64", "recipientPublicKeySha256"}


class ProvisionError(Exception):
    """Only fixed, non-sensitive messages are surfaced by the CLI."""


def require(condition, message):
    if not condition:
        raise ProvisionError(message)


def matches(value, pattern):
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None


def b64(raw):
    return base64.b64encode(raw).decode("ascii")


def decode(value, length):
    require(isinstance(value, str) and len(value) == 4 * ((length + 2) // 3), "invalid encoded length")
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, TypeError):
        raise ProvisionError("invalid canonical Base64") from None
    require(len(raw) == length and b64(raw) == value, "invalid canonical Base64")
    return raw


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def identity(mode, nonce, sha, run_id, run_attempt, recipient_id, recipient_key):
    require(mode in {"generate", "prove"}, "invalid operation")
    require(matches(nonce, r"[0-9a-f]{64}") and nonce != "0" * 64, "invalid request nonce")
    require(matches(sha, r"[0-9a-f]{40}") and sha != "0" * 40, "invalid execution SHA")
    require(matches(run_id, r"[1-9][0-9]{0,19}") and run_attempt == "1", "reruns or invalid run identity are forbidden")
    require(matches(recipient_id, r"[1-9][0-9]{0,19}"), "invalid environment public key ID")
    recipient_raw = decode(recipient_key, 32)
    return dict(operation=mode, repository=REPOSITORY, repositoryId=REPOSITORY_ID,
                environment=ENVIRONMENT, environmentId=ENVIRONMENT_ID, secretName=SECRET, workflowRef=WORKFLOW,
                executionRef="refs/heads/main",
                executionSha=sha, workflowSha=sha, runId=run_id, runAttempt=run_attempt,
                requestNonce=nonce, recipientKeyId=recipient_id, recipientPublicKeyBase64=recipient_key,
                recipientPublicKeySha256=hashlib.sha256(recipient_raw).hexdigest())


def execution(environment):
    expected = {
        "GITHUB_ACTIONS": "true", "EXECUTION_REPOSITORY": REPOSITORY,
        "EXECUTION_REPOSITORY_ID": REPOSITORY_ID, "EXECUTION_REF": "refs/heads/main",
        "EXECUTION_REF_PROTECTED": "true", "EXECUTION_EVENT": "workflow_dispatch",
        "WORKFLOW_REPOSITORY": REPOSITORY, "WORKFLOW_REF": WORKFLOW,
        "EXECUTION_ENVIRONMENT": ENVIRONMENT,
    }
    require(all(environment.get(key) == value for key, value in expected.items()), "execution scope is not protected Fleet main")
    sha = environment.get("EXPECTED_EXECUTION_SHA")
    require(environment.get("EXECUTION_SHA") == sha == environment.get("WORKFLOW_SHA"), "workflow source or execution SHA differs")
    result = identity(environment.get("PROVISION_MODE"), environment.get("REQUEST_NONCE"), sha,
                      environment.get("EXECUTION_RUN_ID"), environment.get("EXECUTION_RUN_ATTEMPT"),
                      environment.get("RECIPIENT_KEY_ID"), environment.get("RECIPIENT_PUBLIC_KEY"))
    # Do not even read the secret value until all public context and inputs pass.
    if result["operation"] == "generate":
        require(SECRET not in environment, "generate must not receive an existing secret")
        require(environment.get("EXPECTED_PUBLIC_KEY_SPKI", "") == "", "generate must not specify an existing public key")
    else:
        decode(environment.get("EXPECTED_PUBLIC_KEY_SPKI"), 44)
    return result


def read_json(path):
    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, "duplicate JSON field")
            result[key] = value
        return result
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    with os.fdopen(os.open(path, flags), "rb") as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_size <= 65536, "invalid JSON input size or type")
        raw = stream.read(65537)
    require(len(raw) <= 65536, "oversized JSON input")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ProvisionError("non-finite JSON")))


def snapshot_preflight(environment, context):
    directory = Path(environment.get("RUNNER_TEMP", ""))
    require(directory.is_absolute() and directory.resolve() == directory and directory.is_dir(), "invalid runner temporary directory")
    main = read_json(directory / "approver-main.json")
    require(main.get("name") == "main" and main.get("protected") is True and
            main.get("commit", {}).get("sha") == context["executionSha"], "current main snapshot differs")
    scope = read_json(directory / "approver-environment.json")
    require(scope.get("name") == ENVIRONMENT and str(scope.get("id")) == ENVIRONMENT_ID and
            scope.get("deployment_branch_policy") == {"protected_branches": True, "custom_branch_policies": False} and
            scope.get("can_admins_bypass") is False, "environment protection snapshot differs")
    encryption = read_json(directory / "approver-environment-public-key.json")
    require(encryption.get("key_id") == context["recipientKeyId"] and
            encryption.get("key") == context["recipientPublicKeyBase64"], "authenticated environment encryption key differs")


def public_metadata(key):
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    der = key.public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
    pem = key.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
    require(len(der) == 44, "invalid Ed25519 public key length")
    return {"publicKeySpkiDerBase64": b64(der), "publicKeySpkiSha256": hashlib.sha256(der).hexdigest(),
            "publicKeyPem": pem.decode("ascii"), "publicKeyPemSha256": hashlib.sha256(pem).hexdigest()}


def public_key(value):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.hazmat.primitives.serialization import load_der_public_key
    raw = decode(value, 44)
    key = load_der_public_key(raw)
    require(isinstance(key, Ed25519PublicKey) and public_metadata(key)["publicKeySpkiDerBase64"] == value,
            "expected public key is not canonical Ed25519 SPKI")
    return key


def recipient(value):
    from nacl.bindings import crypto_scalarmult
    from nacl.public import PublicKey, SealedBox
    raw = decode(value, 32)
    # Reject low-order points before generating or reading an approver key.
    crypto_scalarmult(b"\x01" * 32, raw)
    return SealedBox(PublicKey(raw))


def challenge(observation):
    fields = IDENTITY_FIELDS | PUBLIC_FIELDS
    require(observation["operation"] == "prove", "custody challenge requires prove mode")
    return DOMAIN + canonical({key: observation[key] for key in fields})


def validate_observation(observation, expected, expected_public=None):
    require(isinstance(observation, dict), "observation must be an object")
    extra = {"encryptedValue"} if expected["operation"] == "generate" else {"custodyChallengeSha256", "custodySignatureBase64"}
    require(set(observation) == IDENTITY_FIELDS | PUBLIC_FIELDS | extra, "observation schema differs")
    require(all(observation[key] == value for key, value in expected.items()), "observation identity differs")
    key = public_key(observation["publicKeySpkiDerBase64"])
    require(all(observation[key] == value for key, value in public_metadata(key).items()), "public metadata differs")
    if expected_public is not None:
        require(observation["publicKeySpkiDerBase64"] == expected_public, "public key differs from expected generation")
    recipient(observation["recipientPublicKeyBase64"])
    if expected["operation"] == "generate":
        # 48-byte canonical PKCS8 => 64 ASCII Base64 bytes + sealed-box overhead 48.
        decode(observation["encryptedValue"], 112)
    else:
        message = challenge(observation)
        require(observation["custodyChallengeSha256"] == hashlib.sha256(message).hexdigest(), "custody challenge differs")
        key.verify(decode(observation["custodySignatureBase64"], 64), message)


def generate(context):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption
    box = recipient(context["recipientPublicKeyBase64"])
    key = Ed25519PrivateKey.generate()
    private = key.private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption())
    require(len(private) == 48, "invalid canonical private key length")
    encrypted = box.encrypt(base64.b64encode(private))
    result = {**context, **public_metadata(key.public_key()), "encryptedValue": b64(encrypted)}
    del private, key
    validate_observation(result, context)
    return result


def prove(context, environment):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption, load_der_private_key
    expected = environment.get("EXPECTED_PUBLIC_KEY_SPKI")
    public_key(expected)
    recipient(context["recipientPublicKeyBase64"])
    # This is deliberately the first private-value access in the implementation.
    encoded = environment.pop(SECRET, None)
    private = decode(encoded, 48)
    key = load_der_private_key(private, password=None)
    require(isinstance(key, Ed25519PrivateKey) and
            key.private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption()) == private,
            "secret is not canonical Ed25519 PKCS8")
    result = {**context, **public_metadata(key.public_key())}
    require(result["publicKeySpkiDerBase64"] == expected, "injected public key differs")
    message = challenge(result)
    result.update(custodyChallengeSha256=hashlib.sha256(message).hexdigest(),
                  custodySignatureBase64=b64(key.sign(message)))
    del private, encoded, key
    validate_observation(result, context, expected)
    return result


def emit(observation, environment):
    raw = canonical(observation) + b"\n"
    require(len(raw) < 8192, "observation exceeds bound")
    path = Path(environment["RUNNER_TEMP"]) / OUTPUT
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb") as stream:
        stream.write(raw)
    print("Public provisioning observation written; no release approval was produced.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("context", "preflight", "generate", "prove", "verify"))
    parser.add_argument("--observation", type=Path)
    parser.add_argument("--mode", choices=("generate", "prove"))
    parser.add_argument("--nonce")
    parser.add_argument("--execution-sha")
    parser.add_argument("--run-id")
    parser.add_argument("--run-attempt")
    parser.add_argument("--recipient-key-id")
    parser.add_argument("--recipient-public-key")
    parser.add_argument("--public-key-spki")
    args = parser.parse_args(argv)
    try:
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        if args.command == "verify":
            require(args.observation is not None, "observation is required")
            require(args.mode != "prove" or args.public_key_spki is not None, "expected custody public key is required")
            expected = identity(args.mode, args.nonce, args.execution_sha, args.run_id, args.run_attempt,
                                args.recipient_key_id, args.recipient_public_key)
            validate_observation(read_json(args.observation), expected, args.public_key_spki)
            print("Public observation verified; hosted provenance must be checked independently.")
            return 0
        require(all(value is None for key, value in vars(args).items() if key != "command"), "runtime accepts environment inputs only")
        context = execution(os.environ)
        if args.command == "context":
            return 0
        snapshot_preflight(os.environ, context)
        if args.command == "preflight":
            return 0
        require(args.command == context["operation"], "command and dispatch mode differ")
        require("GH_TOKEN" not in os.environ and "GITHUB_TOKEN" not in os.environ,
                "key operation must not receive an API token")
        require(not os.path.lexists(Path(os.environ["RUNNER_TEMP"]) / OUTPUT), "observation destination already exists")
        observation = generate(context) if args.command == "generate" else prove(context, os.environ)
        emit(observation, os.environ)
        return 0
    except Exception:
        # Never print exception values, tracebacks, keys, input data, or environment.
        print("Approver provisioning failed closed; no valid observation was emitted.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
