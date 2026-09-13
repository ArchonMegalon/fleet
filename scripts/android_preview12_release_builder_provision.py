#!/usr/bin/env python3
"""Remote-only builder-key provisioning, not build attestation or release authority.

Reuse the reviewed approver's pure crypto/parsing primitives, never its runtime
dispatch or its identity. Private material stays in remote process memory; Python
does not guarantee zeroization. Only ciphertext and public custody proofs leave.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import resource
import stat
import sys
import types

SHARED_SHA256 = "caa02022657d79c5566007bb5405c8c5ac2bb809aef4ff75b4453f4b9f3fc8df"


def _shared_helpers():
    path = Path(__file__).resolve().with_name("android_preview12_release_approver_provision.py")
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > 32768:
            raise ValueError("shared helper source is not admitted")
        raw = stream.read(32769)
    if len(raw) > 32768 or hashlib.sha256(raw).hexdigest() != SHARED_SHA256:
        raise ValueError("shared helper source differs from pin")
    module = types.ModuleType("fleet_builder_provision_shared_primitives")
    module.__file__ = os.fspath(path)
    # Execute only these exact hash-bound bytes, not a timestamp-valid .pyc.
    exec(compile(raw, os.fspath(path), "exec"), module.__dict__)
    return module


try:
    _SHARED = _shared_helpers()
except Exception:
    raise SystemExit("Builder provisioning failed closed: shared helpers unavailable.") from None

ProvisionError = _SHARED.ProvisionError
require, matches = _SHARED.require, _SHARED.matches
b64, decode, canonical = _SHARED.b64, _SHARED.decode, _SHARED.canonical
read_json, public_metadata = _SHARED.read_json, _SHARED.public_metadata
public_key, recipient = _SHARED.public_key, _SHARED.recipient
PUBLIC_FIELDS = _SHARED.PUBLIC_FIELDS
IDENTITY_FIELDS = _SHARED.IDENTITY_FIELDS | {"role"}
REPOSITORY, REPOSITORY_ID = "ArchonMegalon/fleet", "1176287728"
ENVIRONMENT, ENVIRONMENT_ID = "android-preview12-release-builder", "21853652742"
# Authenticated operator readback 2026-09-13; the numeric recipient ID alone is
# NOT destination identity (GitHub returned the same ID for the approver).
RECIPIENT_KEY_ID = "3380204578043523366"
RECIPIENT_PUBLIC_KEY = "ar5WmLUgUHPZK8TCcLavSeiSUIZraJvEBRkN3qoHOyg="
SECRET = "ANDROID_PREVIEW12_RELEASE_BUILDER_ED25519_PRIVATE_KEY_PKCS8_B64"
ROLE = "android_internal_release_builder"
WORKFLOW = REPOSITORY + "/.github/workflows/android-release-builder-provision.yml@refs/heads/main"
OUTPUT = "android-release-builder-observation.json"
DOMAIN = b"fleet/android-release-builder/custody-proof/v1\x00"
APPROVER_SPKI_SHA256 = "b0afed082c23ee1af1c828dde5b28ffa4061ceaa71d1bab4c11927ff142f43a3"
FORBIDDEN_KEY_DIGESTS = frozenset({APPROVER_SPKI_SHA256,
    "c46a4e9a224c8c77a4038bca83f7d9ed66146318d8b5c2c9fc81cd19fdd18ea7"})


def admit_recipient(key_id, key):
    require(matches(key_id, r"[1-9][0-9]{0,19}"), "invalid environment public key ID")
    raw = decode(key, 32)
    require(key_id == RECIPIENT_KEY_ID and key == RECIPIENT_PUBLIC_KEY,
            "recipient differs from reviewed builder destination")
    return raw


def identity(mode, nonce, sha, run_id, run_attempt, recipient_id, recipient_key):
    require(mode in {"generate", "prove"}, "invalid operation")
    require(matches(nonce, r"[0-9a-f]{64}") and nonce != "0" * 64, "invalid request nonce")
    require(matches(sha, r"[0-9a-f]{40}") and sha != "0" * 40, "invalid execution SHA")
    require(matches(run_id, r"[1-9][0-9]{0,19}") and run_attempt == "1", "reruns or invalid run identity are forbidden")
    raw = admit_recipient(recipient_id, recipient_key)
    return dict(operation=mode, repository=REPOSITORY, repositoryId=REPOSITORY_ID,
                environment=ENVIRONMENT, environmentId=ENVIRONMENT_ID, secretName=SECRET,
                workflowRef=WORKFLOW, executionRef="refs/heads/main", executionSha=sha, workflowSha=sha,
                runId=run_id, runAttempt=run_attempt, requestNonce=nonce, recipientKeyId=recipient_id,
                recipientPublicKeyBase64=recipient_key, recipientPublicKeySha256=hashlib.sha256(raw).hexdigest(), role=ROLE)


def _context(context):
    require(isinstance(context, dict) and set(context) == IDENTITY_FIELDS, "builder context schema differs")
    exact = identity(context["operation"], context["requestNonce"], context["executionSha"], context["runId"],
                     context["runAttempt"], context["recipientKeyId"], context["recipientPublicKeyBase64"])
    require(context == exact, "builder context identity differs")


def builder_public(value):
    key = public_key(value)
    require(public_metadata(key)["publicKeySpkiSha256"] not in FORBIDDEN_KEY_DIGESTS,
            "approval or historical shared key cannot become the new builder key")
    return key


def execution(environment):
    expected = {"GITHUB_ACTIONS": "true", "EXECUTION_REPOSITORY": REPOSITORY,
                "EXECUTION_REPOSITORY_ID": REPOSITORY_ID, "EXECUTION_REF": "refs/heads/main",
                "EXECUTION_REF_PROTECTED": "true", "EXECUTION_EVENT": "workflow_dispatch",
                "WORKFLOW_REPOSITORY": REPOSITORY, "WORKFLOW_REF": WORKFLOW, "EXECUTION_ENVIRONMENT": ENVIRONMENT}
    require(all(environment.get(key) == value for key, value in expected.items()), "execution scope is not protected Fleet main")
    sha = environment.get("EXPECTED_EXECUTION_SHA")
    require(environment.get("EXECUTION_SHA") == sha == environment.get("WORKFLOW_SHA"), "workflow source or execution SHA differs")
    result = identity(environment.get("PROVISION_MODE"), environment.get("REQUEST_NONCE"), sha,
                      environment.get("EXECUTION_RUN_ID"), environment.get("EXECUTION_RUN_ATTEMPT"),
                      environment.get("RECIPIENT_KEY_ID"), environment.get("RECIPIENT_PUBLIC_KEY"))
    require(_SHARED.SECRET not in environment, "builder provisioning must not receive an approver secret")
    if result["operation"] == "generate":
        require(SECRET not in environment, "generate must not receive an existing builder secret")
        require(environment.get("EXPECTED_PUBLIC_KEY_SPKI", "") == "", "generate must not specify an existing key")
    else:
        # Length/canonical bytes and forbidden pins need no optional crypto deps;
        # full Ed25519 type validation runs after hashed dependency installation.
        raw = decode(environment.get("EXPECTED_PUBLIC_KEY_SPKI"), 44)
        require(raw.startswith(bytes.fromhex("302a300506032b6570032100")) and
                hashlib.sha256(raw).hexdigest() not in FORBIDDEN_KEY_DIGESTS, "expected builder public key is not admitted")
    return result


def main_preflight(environment, context):
    directory = Path(environment.get("RUNNER_TEMP", ""))
    require(directory.is_absolute() and directory.resolve() == directory and directory.is_dir(), "invalid runner temporary directory")
    main = read_json(directory / "builder-main.json")
    require(main.get("name") == "main" and main.get("protected") is True and
            main.get("commit", {}).get("sha") == context["executionSha"], "current main snapshot differs")


def challenge(observation):
    require(observation["operation"] == "prove", "custody challenge requires prove mode")
    _context({key: observation[key] for key in IDENTITY_FIELDS})
    return DOMAIN + canonical({key: observation[key] for key in IDENTITY_FIELDS | PUBLIC_FIELDS})


def validate_observation(observation, expected, expected_public=None):
    _context(expected)
    require(isinstance(observation, dict), "observation must be an object")
    extra = {"encryptedValue"} if expected["operation"] == "generate" else {"custodyChallengeSha256", "custodySignatureBase64"}
    require(set(observation) == IDENTITY_FIELDS | PUBLIC_FIELDS | extra, "observation schema differs")
    require(all(observation[key] == value for key, value in expected.items()), "observation identity differs")
    key = builder_public(observation["publicKeySpkiDerBase64"])
    require(all(observation[key] == value for key, value in public_metadata(key).items()), "public metadata differs")
    if expected_public is not None:
        builder_public(expected_public)
        require(observation["publicKeySpkiDerBase64"] == expected_public, "public key differs from expected generation")
    recipient(observation["recipientPublicKeyBase64"])
    if expected["operation"] == "generate":
        decode(observation["encryptedValue"], 112)
    else:
        message = challenge(observation)
        require(observation["custodyChallengeSha256"] == hashlib.sha256(message).hexdigest(), "custody challenge differs")
        key.verify(decode(observation["custodySignatureBase64"], 64), message)


def generate(context):
    _context(context)
    require(context["operation"] == "generate", "operation differs")
    box = recipient(context["recipientPublicKeyBase64"])
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption
    key = Ed25519PrivateKey.generate()
    metadata = public_metadata(key.public_key())
    builder_public(metadata["publicKeySpkiDerBase64"])
    private = key.private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption())
    require(len(private) == 48, "invalid canonical private key length")
    result = {**context, **metadata, "encryptedValue": b64(box.encrypt(b64(private).encode("ascii")))}
    del private, key
    validate_observation(result, context)
    return result


def prove(context, environment):
    _context(context)
    require(context["operation"] == "prove" and _SHARED.SECRET not in environment, "builder proof role differs")
    expected = environment.get("EXPECTED_PUBLIC_KEY_SPKI")
    builder_public(expected)
    recipient(context["recipientPublicKeyBase64"])
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption, load_der_private_key
    # First private-value access, after exact public role/destination validation.
    encoded = environment.pop(SECRET, None)
    private = decode(encoded, 48)
    key = load_der_private_key(private, password=None)
    require(isinstance(key, Ed25519PrivateKey) and
            key.private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption()) == private, "secret is not canonical Ed25519 PKCS8")
    result = {**context, **public_metadata(key.public_key())}
    require(result["publicKeySpkiDerBase64"] == expected, "injected public key differs")
    message = challenge(result)
    result.update(custodyChallengeSha256=hashlib.sha256(message).hexdigest(), custodySignatureBase64=b64(key.sign(message)))
    del private, encoded, key
    validate_observation(result, context, expected)
    return result


def emit(observation, environment):
    raw = canonical(observation) + b"\n"
    require(len(raw) < 8192, "observation exceeds bound")
    path = Path(environment["RUNNER_TEMP"]) / OUTPUT
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb") as stream:
        stream.write(raw)
    print("Public builder custody observation written; no build attestation was produced.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("context", "preflight", "generate", "prove", "verify"))
    parser.add_argument("--observation", type=Path)
    parser.add_argument("--mode", choices=("generate", "prove"))
    for name in ("nonce", "execution-sha", "run-id", "run-attempt", "recipient-key-id", "recipient-public-key", "public-key-spki"):
        parser.add_argument("--" + name)
    args = parser.parse_args(argv)
    try:
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        if args.command == "verify":
            require(args.observation is not None, "observation is required")
            require(args.mode != "prove" or args.public_key_spki is not None, "expected custody public key is required")
            expected = identity(args.mode, args.nonce, args.execution_sha, args.run_id, args.run_attempt,
                                args.recipient_key_id, args.recipient_public_key)
            validate_observation(read_json(args.observation), expected, args.public_key_spki)
            print("Public builder observation verified; hosted provenance must be checked independently.")
            return 0
        require(all(value is None for key, value in vars(args).items() if key != "command"), "runtime accepts environment inputs only")
        context = execution(os.environ)
        if args.command == "context":
            return 0
        main_preflight(os.environ, context)
        if args.command == "preflight":
            return 0
        require(args.command == context["operation"], "command and dispatch mode differ")
        require("GH_TOKEN" not in os.environ and "GITHUB_TOKEN" not in os.environ, "key operation must not receive an API token")
        require(not os.path.lexists(Path(os.environ["RUNNER_TEMP"]) / OUTPUT), "observation destination already exists")
        observation = generate(context) if args.command == "generate" else prove(context, os.environ)
        emit(observation, os.environ)
        return 0
    except Exception:
        print("Builder provisioning failed closed; no valid observation was emitted.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
