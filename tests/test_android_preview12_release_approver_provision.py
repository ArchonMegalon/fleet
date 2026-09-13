"""Real crypto with deterministic PUBLIC TEST KEYS only; no hosted custody claim."""
import base64
import contextlib
from copy import deepcopy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat
from nacl.public import PrivateKey, SealedBox

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("approver_provision_test", ROOT / "scripts/android_preview12_release_approver_provision.py")
P = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P)
# These deterministic bytes are published test vectors, never operational keys.
TEST_KEY = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
TEST_OTHER = Ed25519PrivateKey.from_private_bytes(bytes(range(1, 33)))
TEST_RECIPIENT = PrivateKey(bytes(range(32, 64)))
TEST_PRIVATE = TEST_KEY.private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption())
TEST_ENCODED = P.b64(TEST_PRIVATE)
TEST_PUBLIC = P.public_metadata(TEST_KEY.public_key())["publicKeySpkiDerBase64"]


def environment(directory, mode="generate"):
    result = {
        "GITHUB_ACTIONS": "true", "EXECUTION_REPOSITORY": P.REPOSITORY,
        "EXECUTION_REPOSITORY_ID": P.REPOSITORY_ID, "EXECUTION_REF": "refs/heads/main",
        "EXECUTION_REF_PROTECTED": "true", "EXECUTION_EVENT": "workflow_dispatch",
        "WORKFLOW_REPOSITORY": P.REPOSITORY, "WORKFLOW_REF": P.WORKFLOW,
        "EXECUTION_ENVIRONMENT": P.ENVIRONMENT, "EXPECTED_EXECUTION_SHA": "a" * 40,
        "EXECUTION_SHA": "a" * 40, "WORKFLOW_SHA": "a" * 40,
        "PROVISION_MODE": mode, "REQUEST_NONCE": "b" * 64,
        "EXECUTION_RUN_ID": "1001", "EXECUTION_RUN_ATTEMPT": "1",
        "RECIPIENT_KEY_ID": "123456", "RECIPIENT_PUBLIC_KEY": P.b64(TEST_RECIPIENT.public_key.encode()),
        "EXPECTED_PUBLIC_KEY_SPKI": "" if mode == "generate" else TEST_PUBLIC,
        "RUNNER_TEMP": str(directory),
    }
    if mode == "prove":
        result[P.SECRET] = TEST_ENCODED
    return result


def snapshots(directory, env):
    (directory / "approver-main.json").write_text(json.dumps({"name": "main", "protected": True,
                                                            "commit": {"sha": env["EXECUTION_SHA"]}}))


class PrivateReadGuard(dict):
    def get(self, key, *args):
        if key == P.SECRET:
            raise AssertionError("preflight read private value")
        return super().get(key, *args)

    def pop(self, key, *args):
        if key == P.SECRET:
            raise AssertionError("preflight consumed private value")
        return super().pop(key, *args)


class ProvisionTests(unittest.TestCase):
    def setUp(self):
        # Explicit fixture-only substitution. No test has GitHub's recipient
        # private key and operational generation is never executed locally.
        for name, value in (("RECIPIENT_KEY_ID", "123456"),
                            ("RECIPIENT_PUBLIC_KEY", P.b64(TEST_RECIPIENT.public_key.encode()))):
            pin = patch.object(P, name, value)
            pin.start()
            self.addCleanup(pin.stop)
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.env = environment(self.directory)
        snapshots(self.directory, self.env)

    def generated(self):
        context = P.execution(self.env)
        with patch.object(Ed25519PrivateKey, "generate", return_value=TEST_KEY) as generate:
            result = P.generate(context)
        generate.assert_called_once_with()
        return result

    def invoke(self, command, env=None):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, self.env if env is None else env, clear=True), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = P.main([command])
        return result, stdout.getvalue(), stderr.getvalue()

    def test_sealed_key_round_trip_is_only_decryptable_by_test_recipient(self):
        observation = self.generated()
        encrypted = P.decode(observation["encryptedValue"], 112)
        self.assertEqual(SealedBox(TEST_RECIPIENT).decrypt(encrypted), TEST_ENCODED.encode())
        with self.assertRaises(Exception):
            SealedBox(PrivateKey(bytes(range(64, 96)))).decrypt(encrypted)
        serialized = P.canonical(observation)
        self.assertNotIn(TEST_PRIVATE, serialized)
        self.assertNotIn(TEST_ENCODED.encode(), serialized)
        self.assertEqual(observation["publicKeySpkiDerBase64"], TEST_PUBLIC)
        self.assertEqual(set(observation), P.IDENTITY_FIELDS | P.PUBLIC_FIELDS | {"encryptedValue"})
        P.validate_observation(observation, P.execution(self.env))

    def test_custody_is_independent_and_domain_separated_from_release_approval(self):
        generated = self.generated()
        proof_env = environment(self.directory, "prove")
        proof_env["EXECUTION_RUN_ID"] = "1002"
        context = P.execution(proof_env)
        proof = P.prove(context, proof_env)
        self.assertNotIn(P.SECRET, proof_env)
        self.assertEqual(proof["publicKeySpkiDerBase64"], generated["publicKeySpkiDerBase64"])
        P.validate_observation(proof, context, TEST_PUBLIC)
        signature = P.decode(proof["custodySignatureBase64"], 64)
        TEST_KEY.public_key().verify(signature, P.challenge(proof))
        for wrong_message in (P.challenge(proof)[len(P.DOMAIN):], P.canonical({
                "contractName": "chummer.android.two-green-release-approval/v1", "approved": True})):
            with self.assertRaises(InvalidSignature):
                TEST_KEY.public_key().verify(signature, wrong_message)
        self.assertNotIn("encryptedValue", proof)
        self.assertNotIn(TEST_ENCODED.encode(), P.canonical(proof))

    def test_each_execution_scope_rejection_precedes_private_value_access(self):
        valid = environment(self.directory, "prove")
        P.execution(PrivateReadGuard(valid))
        fields = ("GITHUB_ACTIONS", "EXECUTION_REPOSITORY", "EXECUTION_REPOSITORY_ID", "EXECUTION_REF",
                  "EXECUTION_REF_PROTECTED", "EXECUTION_EVENT", "WORKFLOW_REPOSITORY", "WORKFLOW_REF",
                  "EXECUTION_ENVIRONMENT", "EXPECTED_EXECUTION_SHA", "EXECUTION_SHA", "WORKFLOW_SHA")
        for field in fields:
            for bad in (None, "", "false", "refs/pull/1/merge", "$(id)\n"):
                with self.subTest(field=field, bad=bad), self.assertRaises(P.ProvisionError):
                    P.execution(PrivateReadGuard({**valid, field: bad}))

    def test_request_inputs_are_bounded_before_private_access(self):
        cases = {
            "PROVISION_MODE": ["", "approve", "generate; id", "prove\n"],
            "REQUEST_NONCE": ["", "0" * 64, "B" * 64, "b" * 63, "b" * 65, "b" * 64 + "\n"],
            "EXECUTION_RUN_ID": ["0", "01", "-1", "1; id", "1" * 21],
            "EXECUTION_RUN_ATTEMPT": ["0", "2", "01", "1\n"],
            "RECIPIENT_KEY_ID": ["", "0", "01", "../other", "1" * 21],
            "RECIPIENT_PUBLIC_KEY": ["", "A" * 43, "A" * 45, P.b64(b"x" * 31), P.b64(b"x" * 33)],
            "EXPECTED_PUBLIC_KEY_SPKI": ["", "A" * 59, "A" * 61, TEST_PUBLIC + "\n"],
        }
        valid = environment(self.directory, "prove")
        for field, values in cases.items():
            for bad in values:
                with self.subTest(field=field, bad=bad), self.assertRaises(P.ProvisionError):
                    P.execution(PrivateReadGuard({**valid, field: bad}))

    def test_generate_rejects_any_existing_secret_without_reading_it(self):
        with self.assertRaises(P.ProvisionError):
            P.execution(PrivateReadGuard({**self.env, P.SECRET: ""}))
        with self.assertRaises(P.ProvisionError):
            P.execution({**self.env, "EXPECTED_PUBLIC_KEY_SPKI": TEST_PUBLIC})

    def test_recipient_low_order_point_precedes_key_generation(self):
        for bad in (b"\0" * 32, b"\x01" + b"\0" * 31):
            context = {**P.execution(self.env), "recipientPublicKeyBase64": P.b64(bad)}
            with patch.object(Ed25519PrivateKey, "generate", side_effect=AssertionError("generated too early")) as generate:
                with self.assertRaises(Exception):
                    P.generate(context)
                generate.assert_not_called()

    def test_wrong_public_key_and_malformed_secret_emit_nothing_sensitive(self):
        valid = environment(self.directory, "prove")
        for private in (None, "", TEST_ENCODED + "\n", P.b64(b"x" * 48), P.b64(TEST_PRIVATE + b"\0"), "SENSITIVE-TEST-SENTINEL"):
            with self.subTest(private_length=len(private or "")):
                selected = {**valid, P.SECRET: private or ""}
                result, out, err = self.invoke("prove", selected)
                self.assertEqual(result, 1)
                self.assertEqual(out, "")
                self.assertEqual(err, "Approver provisioning failed closed; no valid observation was emitted.\n")
                self.assertFalse((self.directory / P.OUTPUT).exists())
        wrong = {**valid, "EXPECTED_PUBLIC_KEY_SPKI": P.public_metadata(TEST_OTHER.public_key())["publicKeySpkiDerBase64"]}
        self.assertEqual(self.invoke("prove", wrong)[0], 1)

    def test_invalid_spki_type_precedes_private_access(self):
        # X25519 has the same DER length, but must never become an Ed25519 key.
        from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
        from cryptography.hazmat.primitives.serialization import PublicFormat
        raw = X25519PrivateKey.from_private_bytes(bytes(range(32))).public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
        selected = PrivateReadGuard({**environment(self.directory, "prove"), "EXPECTED_PUBLIC_KEY_SPKI": P.b64(raw)})
        with self.assertRaises(P.ProvisionError):
            P.prove(P.execution(selected), selected)

    def test_closed_schema_identity_and_all_public_bindings_reject_tamper(self):
        observation = self.generated()
        expected = P.execution(self.env)
        for field in observation:
            for change in ("remove", "alter"):
                altered = deepcopy(observation)
                if change == "remove":
                    del altered[field]
                else:
                    altered[field] = "changed"
                with self.subTest(field=field, change=change), self.assertRaises(Exception):
                    P.validate_observation(altered, expected)
        for field in ("privateKey", "signingAuthorized", "googlePlayUploadAuthorized", "activationEnabled", "approval"):
            with self.subTest(extra=field), self.assertRaises(P.ProvisionError):
                P.validate_observation({**observation, field: True}, expected)

    def test_ciphertext_and_signature_lengths_and_proof_binding(self):
        observation = self.generated()
        for length in (0, 48, 111, 113, 8192):
            with self.subTest(cipher_length=length), self.assertRaises(P.ProvisionError):
                P.validate_observation({**observation, "encryptedValue": P.b64(b"x" * length)}, P.execution(self.env))
        selected = environment(self.directory, "prove")
        context = P.execution(selected)
        proof = P.prove(context, selected)
        for field in proof:
            bad = {**proof, field: "changed"}
            with self.subTest(field=field), self.assertRaises(Exception):
                P.validate_observation(bad, context, TEST_PUBLIC)
        for length in (0, 63, 65):
            with self.subTest(signature_length=length), self.assertRaises(P.ProvisionError):
                P.validate_observation({**proof, "custodySignatureBase64": P.b64(b"x" * length)}, context, TEST_PUBLIC)
        with self.assertRaises(P.ProvisionError):
            P.validate_observation(proof, {**context, "requestNonce": "c" * 64}, TEST_PUBLIC)
        with self.assertRaises(P.ProvisionError):
            P.validate_observation(proof, {**context, "runId": "1003"}, TEST_PUBLIC)

    def test_snapshots_fail_closed_before_generation_or_private_read(self):
        cases = [("approver-main.json", "protected", False), ("approver-main.json", "name", "other"),
                 ("approver-main.json", "commit", {"sha": "c" * 40})]
        for filename, key, value in cases:
            snapshots(self.directory, self.env)
            path = self.directory / filename
            data = json.loads(path.read_text())
            data[key] = value
            path.write_text(json.dumps(data))
            with self.subTest(filename=filename, key=key), patch.object(P, "generate", side_effect=AssertionError("key access")) as generate:
                self.assertEqual(self.invoke("generate")[0], 1)
                generate.assert_not_called()
            with self.subTest(prove_filename=filename, key=key), patch.object(P, "prove", side_effect=AssertionError("private read")) as prove:
                self.assertEqual(self.invoke("prove", environment(self.directory, "prove"))[0], 1)
                prove.assert_not_called()

    def test_json_bounds_duplicates_symlink_and_fifo_rejected(self):
        path = self.directory / "input.json"
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b"x" * 65537):
            path.write_bytes(raw)
            with self.assertRaises(Exception):
                P.read_json(path)
        path.unlink()
        path.symlink_to(self.directory / "approver-main.json")
        with self.assertRaises(OSError):
            P.read_json(path)
        path.unlink()
        os.mkfifo(path)
        with self.assertRaises(P.ProvisionError):
            P.read_json(path)

    def test_runtime_writes_one_public_file_and_never_overwrites(self):
        with patch.object(Ed25519PrivateKey, "generate", return_value=TEST_KEY):
            code, out, err = self.invoke("generate")
        self.assertEqual((code, err), (0, ""))
        output = self.directory / P.OUTPUT
        first = output.read_bytes()
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        self.assertNotIn(TEST_ENCODED, out)
        self.assertNotIn(TEST_ENCODED.encode(), first)
        with patch.object(Ed25519PrivateKey, "generate", return_value=TEST_OTHER) as second:
            self.assertEqual(self.invoke("generate")[0], 1)
            second.assert_not_called()
        self.assertEqual(output.read_bytes(), first)
        self.assertEqual({p.name for p in self.directory.iterdir()}, {P.OUTPUT, "approver-main.json"})

    def test_runtime_command_cannot_switch_dispatch_mode(self):
        with patch.object(P, "prove", side_effect=AssertionError("private read")) as prove:
            self.assertEqual(self.invoke("prove")[0], 1)
            prove.assert_not_called()

    def test_api_token_is_not_admitted_to_key_operation(self):
        for mode in ("generate", "prove"):
            for token in ("GH_TOKEN", "GITHUB_TOKEN"):
                with self.subTest(mode=mode, token=token), patch.object(P, mode, side_effect=AssertionError("key access")) as operation:
                    self.assertEqual(self.invoke(mode, {**environment(self.directory, mode), token: "TEST-TOKEN"})[0], 1)
                    operation.assert_not_called()

    def test_controller_cli_verifies_exact_public_observation(self):
        observation = self.generated()
        path = self.directory / P.OUTPUT
        path.write_bytes(P.canonical(observation))
        argv = ["verify", "--observation", str(path), "--mode", "generate", "--nonce", self.env["REQUEST_NONCE"],
                "--execution-sha", self.env["EXECUTION_SHA"], "--run-id", self.env["EXECUTION_RUN_ID"],
                "--run-attempt", "1", "--recipient-key-id", self.env["RECIPIENT_KEY_ID"],
                "--recipient-public-key", self.env["RECIPIENT_PUBLIC_KEY"]]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(P.main(argv), 0)
        bad = list(argv)
        bad[bad.index("--nonce") + 1] = "c" * 64
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(P.main(bad), 1)

    def test_workflow_scope_secret_isolation_pins_and_no_input_interpolation(self):
        raw = (ROOT / ".github/workflows/android-release-approver-provision.yml").read_text()
        verify = raw.split("  verify:\n", 1)[1].split("  generate:\n", 1)[0]
        generate = raw.split("  generate:\n", 1)[1].split("  prove:\n", 1)[0]
        prove = raw.split("  prove:\n", 1)[1]
        self.assertIn("  pull_request:\n", raw)
        self.assertIn("  push:\n    branches: [main]", raw)
        self.assertIn("github.event_name == 'pull_request' || github.event_name == 'push'", verify)
        self.assertNotIn("environment:", verify)
        self.assertNotIn("secrets.", verify)
        self.assertNotIn("gh api", verify)
        self.assertIn("-m unittest discover -s tests -p test_android_preview12_release_approver_provision.py -v", verify)
        self.assertNotIn("secrets.", generate)
        self.assertEqual(raw.count("${{ secrets."), 1)
        self.assertIn("${{ secrets." + P.SECRET + " }}", prove)
        self.assertEqual(raw.count("environment: " + P.ENVIRONMENT), 2)
        self.assertEqual(raw.count("github.ref_protected && github.event_name == 'workflow_dispatch'"), 2)
        self.assertEqual(raw.count("github.repository_id == '" + P.REPOSITORY_ID + "'"), 2)
        self.assertEqual(raw.count("persist-credentials: false"), 3)
        self.assertEqual(raw.count("actions/checkout@11d5960a326750d5838078e36cf38b85af677262"), 3)
        self.assertEqual(raw.count("actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02"), 2)
        self.assertEqual(raw.count("--only-binary=:all: --require-hashes --no-deps"), 3)
        self.assertEqual(raw.count("path: ${{ runner.temp }}/" + P.OUTPUT), 2)
        self.assertEqual(raw.count("retention-days: 1"), 2)
        self.assertNotIn("/environments/", raw)
        self.assertNotIn("approver-environment", raw)
        self.assertNotIn("deployments: read", raw)
        self.assertEqual(raw.count("repos/ArchonMegalon/fleet/branches/main >"), 4)
        self.assertEqual(raw.count("Checking authenticated Fleet main before dependency installation"), 2)
        self.assertEqual(raw.count("Checking authenticated Fleet main after dependency installation"), 2)
        self.assertIn("github.event_name == 'workflow_dispatch' && 'android-preview12-release-approval-key-provision'", raw)
        self.assertIn("format('android-release-approver-verify-{0}', github.ref)", raw)
        for namespace in ("repository", "ref", "sha"):
            self.assertEqual(raw.count("${{ job.workflow_" + namespace + " }}"), 4)
        self.assertNotIn("id-token:", raw)
        self.assertNotIn(": write", raw)
        self.assertNotIn("set -x", raw)
        self.assertLess(prove.index("-m pip"), prove.index("${{ secrets."))
        secret_step = prove.split("${{ secrets.", 1)[1].split("- uses: actions/upload-artifact", 1)[0]
        self.assertNotIn("gh api", secret_step)
        self.assertNotIn("-m pip", secret_step)
        for block in raw.split("run: |\n")[1:]:
            run_lines = []
            for line in block.splitlines():
                if line and not line.startswith("          "):
                    break
                run_lines.append(line)
            self.assertNotIn("${{", "\n".join(run_lines))


class ProductionPinTests(unittest.TestCase):
    """Read-only tests of the real public pin; no fixture patch of its constants."""

    def test_unpatched_public_pin_is_exact_and_admits_only_public_context(self):
        self.assertEqual(P.RECIPIENT_KEY_ID, "3380204578043523366")
        self.assertEqual(P.RECIPIENT_PUBLIC_KEY, "KehADg5PaYNI/6mRiXvHp3Nwk2h+F55K0cMJWv/Dcz8=")
        selected = {**environment(Path("/tmp")), "RECIPIENT_KEY_ID": P.RECIPIENT_KEY_ID,
                    "RECIPIENT_PUBLIC_KEY": P.RECIPIENT_PUBLIC_KEY}
        with patch.object(Ed25519PrivateKey, "generate", side_effect=AssertionError("operational generation forbidden")) as generate:
            context = P.execution(selected)
            self.assertEqual(context["recipientKeyId"], P.RECIPIENT_KEY_ID)
            self.assertEqual(context["recipientPublicKeyBase64"], P.RECIPIENT_PUBLIC_KEY)
            generate.assert_not_called()

    def test_unpatched_pin_rejects_each_override_before_key_access(self):
        for mode in ("generate", "prove"):
            original = {**environment(Path("/tmp"), mode), "RECIPIENT_KEY_ID": P.RECIPIENT_KEY_ID,
                        "RECIPIENT_PUBLIC_KEY": P.RECIPIENT_PUBLIC_KEY}
            cases = ({"RECIPIENT_KEY_ID": "123456"},
                     {"RECIPIENT_PUBLIC_KEY": P.b64(TEST_RECIPIENT.public_key.encode())},
                     {"RECIPIENT_KEY_ID": "123456", "RECIPIENT_PUBLIC_KEY": P.b64(TEST_RECIPIENT.public_key.encode())})
            for change in cases:
                with self.subTest(mode=mode, fields=sorted(change)), self.assertRaises(P.ProvisionError):
                    P.execution(PrivateReadGuard({**original, **change}))
            context = P.execution(PrivateReadGuard(original))
            forged = {**context, "recipientKeyId": "123456", "recipientPublicKeyBase64": P.b64(TEST_RECIPIENT.public_key.encode())}
            with patch.object(Ed25519PrivateKey, "generate", side_effect=AssertionError("operational generation forbidden")) as generate:
                with self.assertRaises(P.ProvisionError):
                    P.generate(forged) if mode == "generate" else P.prove(forged, PrivateReadGuard(original))
                generate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
