"""Deterministic PUBLIC TEST KEYS only; no operational generation or hosted proof."""
import base64
import builtins
import contextlib
from copy import deepcopy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat
from nacl.public import PrivateKey, SealedBox

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("builder_provision_test", ROOT / "scripts/android_preview12_release_builder_provision.py")
P = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P)
TEST_KEY = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
TEST_OTHER = Ed25519PrivateKey.from_private_bytes(bytes(range(1, 33)))
TEST_RECIPIENT = PrivateKey(bytes(range(32, 64)))
TEST_PRIVATE = TEST_KEY.private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption())
TEST_ENCODED = P.b64(TEST_PRIVATE)
TEST_PUBLIC = P.public_metadata(TEST_KEY.public_key())["publicKeySpkiDerBase64"]
APPROVER_PUBLIC = "MCowBQYDK2VwAyEAfQlc4wil/fVVadQd7QwlJhaEdVoovi6pkR6AICaeAZ0="
HISTORICAL_PUBLIC = "MCowBQYDK2VwAyEAB105wcYguHU3a/phMkbbRjhZ+Qhj8cdDTAvw/7t14sk="


def environment(directory, mode="generate"):
    result = {"GITHUB_ACTIONS": "true", "EXECUTION_REPOSITORY": P.REPOSITORY,
              "EXECUTION_REPOSITORY_ID": P.REPOSITORY_ID, "EXECUTION_REF": "refs/heads/main",
              "EXECUTION_REF_PROTECTED": "true", "EXECUTION_EVENT": "workflow_dispatch",
              "WORKFLOW_REPOSITORY": P.REPOSITORY, "WORKFLOW_REF": P.WORKFLOW,
              "EXECUTION_ENVIRONMENT": P.ENVIRONMENT, "EXPECTED_EXECUTION_SHA": "a" * 40,
              "EXECUTION_SHA": "a" * 40, "WORKFLOW_SHA": "a" * 40, "PROVISION_MODE": mode,
              "REQUEST_NONCE": "b" * 64, "EXECUTION_RUN_ID": "1001", "EXECUTION_RUN_ATTEMPT": "1",
              "RECIPIENT_KEY_ID": P.RECIPIENT_KEY_ID, "RECIPIENT_PUBLIC_KEY": P.RECIPIENT_PUBLIC_KEY,
              "EXPECTED_PUBLIC_KEY_SPKI": "" if mode == "generate" else TEST_PUBLIC,
              "RUNNER_TEMP": str(directory)}
    if mode == "prove":
        result[P.SECRET] = TEST_ENCODED
    return result


class PrivateReadGuard(dict):
    def get(self, key, *args):
        if key in (P.SECRET, P._SHARED.SECRET):
            raise AssertionError("private value read before admission")
        return super().get(key, *args)

    def pop(self, key, *args):
        if key in (P.SECRET, P._SHARED.SECRET):
            raise AssertionError("private value consumed before admission")
        return super().pop(key, *args)


class BuilderTests(unittest.TestCase):
    def setUp(self):
        # Fixture recipient only; never possess GitHub's recipient private key.
        for name, value in (("RECIPIENT_KEY_ID", "123456"),
                            ("RECIPIENT_PUBLIC_KEY", P.b64(TEST_RECIPIENT.public_key.encode()))):
            replacement = patch.object(P, name, value)
            replacement.start()
            self.addCleanup(replacement.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.env = environment(self.directory)
        self.snapshot()

    def snapshot(self):
        (self.directory / "builder-main.json").write_text(json.dumps(
            {"name": "main", "protected": True, "commit": {"sha": self.env["EXECUTION_SHA"]}}))

    def generated(self):
        context = P.execution(self.env)
        with patch.object(Ed25519PrivateKey, "generate", return_value=TEST_KEY) as generated:
            observation = P.generate(context)
        generated.assert_called_once_with()
        return observation

    def proof(self):
        selected = environment(self.directory, "prove")
        selected["EXECUTION_RUN_ID"] = "1002"
        context = P.execution(selected)
        result = P.prove(context, selected)
        self.assertNotIn(P.SECRET, selected)
        return result, context

    def invoke(self, command, env=None):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, self.env if env is None else env, clear=True), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = P.main([command])
        return status, stdout.getvalue(), stderr.getvalue()

    def test_only_fixture_recipient_can_decrypt_and_no_private_bytes_exported(self):
        observation = self.generated()
        encrypted = P.decode(observation["encryptedValue"], 112)
        self.assertEqual(SealedBox(TEST_RECIPIENT).decrypt(encrypted), TEST_ENCODED.encode())
        with self.assertRaises(Exception):
            SealedBox(PrivateKey(bytes(range(64, 96)))).decrypt(encrypted)
        self.assertNotIn(TEST_PRIVATE, P.canonical(observation))
        self.assertNotIn(TEST_ENCODED.encode(), P.canonical(observation))
        self.assertEqual(observation["role"], "android_internal_release_builder")
        P.validate_observation(observation, P.execution(self.env))

    def test_custody_proof_uses_actual_signature_and_distinct_domain(self):
        proof, context = self.proof()
        P.validate_observation(proof, context, TEST_PUBLIC)
        signature = P.decode(proof["custodySignatureBase64"], 64)
        message = P.challenge(proof)
        TEST_KEY.public_key().verify(signature, message)
        for other in (message[len(P.DOMAIN):], P._SHARED.DOMAIN + message[len(P.DOMAIN):],
                      b'{"contractName":"chummer.android.release-build-attestation/v2"}'):
            with self.subTest(domain=other[:40]), self.assertRaises(InvalidSignature):
                TEST_KEY.public_key().verify(signature, other)
        self.assertNotIn("encryptedValue", proof)
        self.assertNotIn(TEST_ENCODED.encode(), P.canonical(proof))

    def test_valid_approver_artifact_cannot_cross_into_builder(self):
        old = P._SHARED
        expected = old.identity("prove", "b" * 64, "a" * 40, "1002", "1", old.RECIPIENT_KEY_ID, old.RECIPIENT_PUBLIC_KEY)
        observation = {**expected, **P.public_metadata(TEST_KEY.public_key())}
        message = old.challenge(observation)
        observation.update(custodyChallengeSha256=hashlib.sha256(message).hexdigest(),
                           custodySignatureBase64=P.b64(TEST_KEY.sign(message)))
        old.validate_observation(observation, expected, TEST_PUBLIC)
        with self.assertRaises(P.ProvisionError):
            P.validate_observation(observation, P.execution(environment(self.directory, "prove")), TEST_PUBLIC)
        proof, context = self.proof()
        with self.assertRaises(old.ProvisionError):
            old.validate_observation(proof, expected, TEST_PUBLIC)
        # Re-labeling the same data cannot transfer a signature across domains.
        wrong_message = old.DOMAIN + P.challenge(proof)[len(P.DOMAIN):]
        proof.update(custodyChallengeSha256=hashlib.sha256(P.challenge(proof)).hexdigest(),
                     custodySignatureBase64=P.b64(TEST_KEY.sign(wrong_message)))
        with self.assertRaises(InvalidSignature):
            P.validate_observation(proof, context, TEST_PUBLIC)

    def test_all_public_scope_guards_precede_private_access(self):
        valid = environment(self.directory, "prove")
        P.execution(PrivateReadGuard(valid))
        for field in ("GITHUB_ACTIONS", "EXECUTION_REPOSITORY", "EXECUTION_REPOSITORY_ID", "EXECUTION_REF",
                      "EXECUTION_REF_PROTECTED", "EXECUTION_EVENT", "WORKFLOW_REPOSITORY", "WORKFLOW_REF",
                      "EXECUTION_ENVIRONMENT", "EXPECTED_EXECUTION_SHA", "EXECUTION_SHA", "WORKFLOW_SHA"):
            for bad in (None, "", "false", "refs/pull/1/merge", "$(id)\n"):
                with self.subTest(field=field, bad=bad), self.assertRaises(P.ProvisionError):
                    P.execution(PrivateReadGuard({**valid, field: bad}))

    def test_malformed_inputs_precede_private_access(self):
        cases = {"PROVISION_MODE": ["", "approve", "generate;id", "prove\n"],
                 "REQUEST_NONCE": ["", "0" * 64, "B" * 64, "b" * 63, "b" * 65],
                 "EXECUTION_RUN_ID": ["0", "01", "-1", "1" * 21],
                 "EXECUTION_RUN_ATTEMPT": ["0", "2", "01", "1\n"],
                 "RECIPIENT_KEY_ID": ["", "0", "01", "1" * 21],
                 "RECIPIENT_PUBLIC_KEY": ["", "A" * 43, "A" * 45],
                 "EXPECTED_PUBLIC_KEY_SPKI": ["", "A" * 59, "A" * 61, TEST_PUBLIC + "\n", P.b64(b"x" * 44)]}
        valid = environment(self.directory, "prove")
        for field, values in cases.items():
            for bad in values:
                with self.subTest(field=field, bad=bad), self.assertRaises(P.ProvisionError):
                    P.execution(PrivateReadGuard({**valid, field: bad}))

    def test_denied_expected_keys_rejected_before_private_access(self):
        for public in (APPROVER_PUBLIC, HISTORICAL_PUBLIC):
            selected = PrivateReadGuard({**environment(self.directory, "prove"), "EXPECTED_PUBLIC_KEY_SPKI": public})
            with self.subTest(public=public), self.assertRaises(P.ProvisionError):
                P.execution(selected)
            with self.assertRaises(P.ProvisionError):
                P.prove(P.execution(environment(self.directory, "prove")), selected)

    def test_generated_or_observed_key_cannot_be_approver_substitution(self):
        digest = hashlib.sha256(P.decode(TEST_PUBLIC, 44)).hexdigest()
        with patch.object(P, "FORBIDDEN_KEY_DIGESTS", frozenset({digest})), \
                patch.object(Ed25519PrivateKey, "generate", return_value=TEST_KEY):
            with self.assertRaises(P.ProvisionError):
                P.generate(P.execution(self.env))
        observation = self.generated()
        for public in (APPROVER_PUBLIC, HISTORICAL_PUBLIC):
            changed = {**observation, **P.public_metadata(P.public_key(public))}
            with self.subTest(public=public), self.assertRaises(P.ProvisionError):
                P.validate_observation(changed, P.execution(self.env))

    def test_context_cannot_override_role_destination_or_execution(self):
        for mode in ("generate", "prove"):
            context = P.execution(environment(self.directory, mode))
            for field in P.IDENTITY_FIELDS:
                with self.subTest(mode=mode, field=field), \
                        patch.object(Ed25519PrivateKey, "generate", side_effect=AssertionError("generation too early")):
                    with self.assertRaises(P.ProvisionError):
                        bad = {**context, field: "other"}
                        P.generate(bad) if mode == "generate" else P.prove(bad, PrivateReadGuard(environment(self.directory, mode)))

    def test_low_order_recipient_rejected_before_generation(self):
        for raw in (b"\0" * 32, b"\x01" + b"\0" * 31):
            with patch.object(P, "RECIPIENT_PUBLIC_KEY", P.b64(raw)), \
                    patch.object(Ed25519PrivateKey, "generate", side_effect=AssertionError("generation too early")) as generate:
                with self.assertRaises(Exception):
                    P.generate(P.execution(environment(self.directory)))
                generate.assert_not_called()

    def test_other_role_secret_or_existing_generation_secret_rejected_unread(self):
        for mode in ("generate", "prove"):
            with self.subTest(mode=mode), self.assertRaises(P.ProvisionError):
                P.execution(PrivateReadGuard({**environment(self.directory, mode), P._SHARED.SECRET: ""}))
        with self.assertRaises(P.ProvisionError):
            P.execution(PrivateReadGuard({**self.env, P.SECRET: ""}))
        with self.assertRaises(P.ProvisionError):
            P.execution({**self.env, "EXPECTED_PUBLIC_KEY_SPKI": TEST_PUBLIC})

    def test_invalid_private_value_or_wrong_key_emits_fixed_failure_only(self):
        wrong = TEST_OTHER.private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption())
        for encoded in ("", "SENSITIVE-TEST-SENTINEL", TEST_ENCODED + "\n", P.b64(b"x" * 48), P.b64(wrong)):
            with self.subTest(length=len(encoded)):
                status, out, err = self.invoke("prove", {**environment(self.directory, "prove"), P.SECRET: encoded})
                self.assertEqual((status, out, err), (1, "", "Builder provisioning failed closed; no valid observation was emitted.\n"))
                self.assertFalse((self.directory / P.OUTPUT).exists())

    def test_actual_cli_prove_rejects_malformed_fixture_secret_without_observation(self):
        # Real process/CLI, but synthetic GitHub context, public fixture SPKI,
        # and malformed sentinel secret only. NEVER operational generation.
        selected = environment(self.directory, "prove")
        selected.update(RECIPIENT_KEY_ID="3380204578043523366",
                        RECIPIENT_PUBLIC_KEY="ar5WmLUgUHPZK8TCcLavSeiSUIZraJvEBRkN3qoHOyg=")
        selected[P.SECRET] = "MALFORMED-PUBLIC-TEST-SENTINEL"
        completed = subprocess.run(
            [sys.executable, "-I", "-B", os.fspath(ROOT / "scripts/android_preview12_release_builder_provision.py"), "prove"],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C", **selected}, timeout=10,
        )
        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout, b"")
        self.assertEqual(completed.stderr, b"Builder provisioning failed closed; no valid observation was emitted.\n")
        self.assertFalse((self.directory / P.OUTPUT).exists())

    def test_every_observation_field_and_cryptographic_length_is_bound(self):
        generated = self.generated()
        proof, proof_context = self.proof()
        for observation, context in ((generated, P.execution(self.env)), (proof, proof_context)):
            for field in observation:
                for action in ("remove", "alter"):
                    changed = deepcopy(observation)
                    if action == "remove":
                        del changed[field]
                    else:
                        changed[field] = "changed"
                    with self.subTest(field=field, action=action), self.assertRaises(Exception):
                        P.validate_observation(changed, context)
            for field in ("privateKey", "signingAuthorized", "activationEnabled", "approval", "publicationAuthorized"):
                with self.subTest(extra=field), self.assertRaises(P.ProvisionError):
                    P.validate_observation({**observation, field: True}, context)
        for length in (0, 48, 111, 113, 8192):
            with self.subTest(ciphertext=length), self.assertRaises(P.ProvisionError):
                P.validate_observation({**generated, "encryptedValue": P.b64(b"x" * length)}, P.execution(self.env))
        for length in (0, 63, 65):
            with self.subTest(signature=length), self.assertRaises(P.ProvisionError):
                P.validate_observation({**proof, "custodySignatureBase64": P.b64(b"x" * length)}, proof_context)

    def test_preflight_main_scope_and_runtime_modes_fail_before_key_operations(self):
        path = self.directory / "builder-main.json"
        for change in ({"name": "other"}, {"protected": False}, {"commit": {"sha": "c" * 40}}):
            for mode in ("generate", "prove"):
                self.snapshot()
                path.write_text(json.dumps({**json.loads(path.read_text()), **change}))
                with self.subTest(mode=mode, change=change), patch.object(P, mode, side_effect=AssertionError("private access")) as operation:
                    self.assertEqual(self.invoke(mode, environment(self.directory, mode))[0], 1)
                    operation.assert_not_called()
        self.snapshot()
        with patch.object(P, "prove", side_effect=AssertionError("private access")) as operation:
            self.assertEqual(self.invoke("prove")[0], 1)
            operation.assert_not_called()

    def test_context_and_preflight_need_no_crypto_dependency_import(self):
        original = builtins.__import__
        def no_crypto(name, *args, **kwargs):
            if name.split(".")[0] in {"cryptography", "nacl"}:
                raise AssertionError("optional dependency imported during public preflight")
            return original(name, *args, **kwargs)
        for mode in ("generate", "prove"):
            for command in ("context", "preflight"):
                with self.subTest(mode=mode, command=command), patch("builtins.__import__", side_effect=no_crypto):
                    self.assertEqual(self.invoke(command, environment(self.directory, mode))[0], 0)

    def test_no_api_token_reaches_key_operation(self):
        for mode in ("generate", "prove"):
            for token in ("GH_TOKEN", "GITHUB_TOKEN"):
                with self.subTest(mode=mode, token=token), patch.object(P, mode, side_effect=AssertionError("private access")) as operation:
                    self.assertEqual(self.invoke(mode, {**environment(self.directory, mode), token: "TEST-TOKEN"})[0], 1)
                    operation.assert_not_called()

    def test_only_one_exclusive_bounded_public_file_is_written(self):
        with patch.object(Ed25519PrivateKey, "generate", return_value=TEST_KEY):
            self.assertEqual(self.invoke("generate")[0], 0)
        path = self.directory / P.OUTPUT
        raw = path.read_bytes()
        self.assertLess(len(raw), 8192)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertNotIn(TEST_ENCODED.encode(), raw)
        with patch.object(Ed25519PrivateKey, "generate", side_effect=AssertionError("second generation")) as generate:
            self.assertEqual(self.invoke("generate")[0], 1)
            generate.assert_not_called()
        self.assertEqual(path.read_bytes(), raw)
        self.assertEqual({p.name for p in self.directory.iterdir()}, {"builder-main.json", P.OUTPUT})

    def test_bounded_json_rejects_duplicate_nonfinite_symlink_fifo(self):
        path = self.directory / "input.json"
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b"x" * 65537):
            path.write_bytes(raw)
            with self.assertRaises(Exception):
                P.read_json(path)
        path.unlink()
        path.symlink_to(self.directory / "builder-main.json")
        with self.assertRaises(OSError):
            P.read_json(path)
        path.unlink()
        os.mkfifo(path)
        with self.assertRaises(P.ProvisionError):
            P.read_json(path)

    def test_public_controller_cli_and_proof_expected_key_requirement(self):
        observation = self.generated()
        path = self.directory / P.OUTPUT
        path.write_bytes(P.canonical(observation))
        argv = ["verify", "--observation", str(path), "--mode", "generate", "--nonce", self.env["REQUEST_NONCE"],
                "--execution-sha", self.env["EXECUTION_SHA"], "--run-id", "1001", "--run-attempt", "1",
                "--recipient-key-id", P.RECIPIENT_KEY_ID, "--recipient-public-key", P.RECIPIENT_PUBLIC_KEY]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(P.main(argv), 0)
        for change in (("--nonce", "c" * 64), ("--mode", "prove"), ("--run-attempt", "2")):
            bad = list(argv)
            bad[bad.index(change[0]) + 1] = change[1]
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(P.main(bad), 1)


class SourceBindingTests(unittest.TestCase):
    def test_real_destination_and_approver_deny_pins_are_exact(self):
        self.assertEqual((P.ENVIRONMENT, P.ENVIRONMENT_ID), ("android-preview12-release-builder", "21853652742"))
        self.assertEqual(P.RECIPIENT_KEY_ID, "3380204578043523366")
        self.assertEqual(P.RECIPIENT_PUBLIC_KEY, "ar5WmLUgUHPZK8TCcLavSeiSUIZraJvEBRkN3qoHOyg=")
        self.assertEqual(P.RECIPIENT_KEY_ID, P._SHARED.RECIPIENT_KEY_ID)
        self.assertNotEqual(P.RECIPIENT_PUBLIC_KEY, P._SHARED.RECIPIENT_PUBLIC_KEY)
        self.assertEqual(P.APPROVER_SPKI_SHA256, hashlib.sha256(base64.b64decode(APPROVER_PUBLIC)).hexdigest())
        for mode in ("generate", "prove"):
            good = PrivateReadGuard(environment(Path("/tmp"), mode))
            with patch.object(Ed25519PrivateKey, "generate", side_effect=AssertionError("operational generation forbidden")) as generate:
                P.execution(good)
                for change in ({"RECIPIENT_PUBLIC_KEY": P._SHARED.RECIPIENT_PUBLIC_KEY},
                               {"EXECUTION_ENVIRONMENT": P._SHARED.ENVIRONMENT}, {"WORKFLOW_REF": P._SHARED.WORKFLOW}):
                    with self.subTest(mode=mode, change=change), self.assertRaises(P.ProvisionError):
                        P.execution(PrivateReadGuard({**good, **change}))
                generate.assert_not_called()

    def test_original_approver_source_workflow_tests_dependencies_unchanged(self):
        files = {"scripts/android_preview12_release_approver_provision.py": P.SHARED_SHA256,
                 "tests/test_android_preview12_release_approver_provision.py": "8dcc99085be4063d06ff24f83131a12926606efd5563a82a9557a7398826bca1",
                 ".github/workflows/android-release-approver-provision.yml": "15a744edfcbd9b736295ce977b6923cbd8ee41d6011dab7426b91b44cd99331f",
                 "config/release/android-release-approver-provision.requirements.txt": "5ce531992e0cb662cb8bd742d9c9904c98b9a7c4803d48efdfcd803775c756f0"}
        for name, expected in files.items():
            self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), expected, name)
        for name in ("b64", "decode", "canonical", "read_json", "public_key", "public_metadata", "recipient"):
            self.assertIs(getattr(P, name), getattr(P._SHARED, name))
        self.assertNotEqual(P._SHARED.DOMAIN, P.DOMAIN)
        with patch.object(P, "SHARED_SHA256", "0" * 64), self.assertRaises(ValueError):
            P._shared_helpers()

    def test_workflow_fixed_destination_secret_step_and_original_tests(self):
        raw = (ROOT / ".github/workflows/android-release-builder-provision.yml").read_text()
        verify = raw.split("  verify:\n", 1)[1].split("  generate:\n", 1)[0]
        generate = raw.split("  generate:\n", 1)[1].split("  prove:\n", 1)[0]
        prove = raw.split("  prove:\n", 1)[1]
        self.assertNotIn("environment:", verify)
        self.assertNotIn("secrets.", verify + generate)
        self.assertNotIn("gh api", verify)
        for test in ("approver", "builder"):
            self.assertIn("-m unittest discover -s tests -p test_android_preview12_release_" + test + "_provision.py -v", verify)
        self.assertEqual(raw.count("${{ secrets."), 1)
        self.assertIn("${{ secrets." + P.SECRET + " }}", prove)
        self.assertNotIn(P._SHARED.SECRET, raw)
        self.assertEqual(raw.count("environment: " + P.ENVIRONMENT), 2)
        self.assertEqual(raw.count("github.ref_protected && github.event_name == 'workflow_dispatch'"), 2)
        self.assertEqual(raw.count("github.repository_id == '" + P.REPOSITORY_ID + "'"), 2)
        self.assertEqual(raw.count("persist-credentials: false"), 3)
        self.assertEqual(raw.count("actions/checkout@11d5960a326750d5838078e36cf38b85af677262"), 3)
        self.assertEqual(raw.count("actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02"), 2)
        self.assertEqual(raw.count("--only-binary=:all: --require-hashes --no-deps"), 3)
        self.assertEqual(raw.count("repos/ArchonMegalon/fleet/branches/main >"), 4)
        self.assertEqual(raw.count("path: ${{ runner.temp }}/" + P.OUTPUT), 2)
        self.assertEqual(raw.count("retention-days: 1"), 2)
        for forbidden in ("id-token:", ": write", "set -x", "deployments: read", "/environments/", "--force"):
            self.assertNotIn(forbidden, raw)
        self.assertLess(prove.index("-m pip"), prove.index("${{ secrets."))
        secret_step = prove.split("${{ secrets.", 1)[1].split("- uses: actions/upload-artifact", 1)[0]
        self.assertNotIn("gh api", secret_step)
        self.assertNotIn("-m pip", secret_step)
        for block in raw.split("run: |\n")[1:]:
            lines = []
            for line in block.splitlines():
                if line and not line.startswith("          "):
                    break
                lines.append(line)
            self.assertNotIn("${{", "\n".join(lines))


if __name__ == "__main__":
    unittest.main()
