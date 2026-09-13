# Separate protected Android builder-key custody

This is remote-only Ed25519 provisioning, not an independent rebuild, build
attestation, Android trust rotation, AAB signing, or release activation. The
existing RSA Play upload identity and every Android/Fleet authority lock remain
unchanged. Do not mount this key, the approval key, or ledger credentials in the
candidate build container.

## Fixed destination and separation

The source-reviewed destination is Fleet `ArchonMegalon/fleet` (1176287728),
environment `android-preview12-release-builder` (21853652742), secret
`ANDROID_PREVIEW12_RELEASE_BUILDER_ED25519_PRIVATE_KEY_PKCS8_B64`.
The operator authenticated the environment, protected-branches-only policy,
disabled administrator bypass, and empty secret inventory on 2026-09-13.
Manual reviewers are not required; automated source/provenance/custody gates
remain. This source pin does not claim a fresh runner-side environment read.

The recipient key ID is `3380204578043523366`; its public Base64 bytes are
`ar5WmLUgUHPZK8TCcLavSeiSUIZraJvEBRkN3qoHOyg=`. GitHub returned the SAME numeric
key ID for the approver's DIFFERENT recipient bytes: both fields and the exact
destination must match. No caller-selected destination/profile is supported.
Recipient rotation requires a separately reviewed source update, not fallback.

The active approver SPKI SHA256
`b0afed082c23ee1af1c828dde5b28ffa4061ceaa71d1bab4c11927ff142f43a3`
and historical shared SPKI `c46a4e9a224c8c77a4038bca83f7d9ed66146318d8b5c2c9fc81cd19fdd18ea7`
are rejected. Expected-public rejection precedes private-value access; generated
public metadata is checked before ciphertext emission. Approval-secret injection
is rejected even if its value is empty. A role label is not runtime authority.

The helper reuses only pure bounded crypto/JSON functions from the unchanged
approver helper. It reads at most 32769 bytes, requires reviewed SHA256
`caa02022657d79c5566007bb5405c8c5ac2bb809aef4ff75b4453f4b9f3fc8df`, and executes
those same captured source bytes under a non-main name, never cached bytecode.
It does not call the approver's generation/proof/dispatch or change its globals.
The approver workflow, original 19 tests, observation schema and proof domain
remain unchanged. Builder PR/main verification runs those tests plus the new
builder tests using the existing hash-locked wheels; no test creates an
operational private key or claims hosted custody.

## Generate, import once, and independently prove

Use workflow `android-release-builder-provision.yml` only after its exact source
has passed hosted verification and merged through normal protected-main checks.
Both runtime jobs require the fixed repository, protected main, matching current
main/workflow SHA, `workflow_dispatch`, and run attempt one. No automatic retry
or rerun is permitted. Dispatch inputs are the existing provisioning inputs:
`mode`, `request_nonce`, `expected_execution_sha`, `recipient_key_id`,
`recipient_public_key`, and `expected_public_key_spki` (empty for generation).

Follow the existing [operator transport procedure](android-release-approver-provision.md)
with these exact builder-only workflow, destination, secret and artifact names.
Re-read the environment ID/name/URL, protection posture, recipient ID AND bytes,
and empty exact secret slot before dispatch and immediately before import.
Generation has no secret injection. Only canonical PKCS8 Base64 sealed directly
to GitHub's public recipient is exported; no plaintext key file or key argument
is created. Python/hosted runner memory is the boundary, not HSM custody or
guaranteed byte zeroization. Core dumps are disabled. Key steps receive no API
token and perform no network/subprocess action; dependency installation finishes
before secret injection, with authenticated current-main checks on both sides.

Select the exact successful generate run/attempt/job and artifact
`android-release-builder-generate-RUNID-1`, never merely the latest run. Require
the authenticated repository, workflow source, event, run/attempt, artifact ID,
archive digest and bounded single-file inventory before using its ciphertext.
The only member is `android-release-builder-observation.json` (under 8192 bytes);
compressed transport must remain at most 65536 bytes. Public artifact retention
is one day. Sealed boxes authenticate neither sender nor hosted execution.

Local public-only verification uses the existing CLI shape:

```text
python -I -B scripts/android_preview12_release_builder_provision.py verify
  --observation <captured-json> --mode <generate-or-prove>
  --nonce <matching-64-hex-nonce> --execution-sha <exact-run-source>
  --run-id <exact-run-id> --run-attempt 1
  --recipient-key-id 3380204578043523366
  --recipient-public-key ar5WmLUgUHPZK8TCcLavSeiSUIZraJvEBRkN3qoHOyg=
  [--public-key-spki <exact-generated-SPKI-required-for-prove>]
```

Operator import is one PUT of `{key_id, encrypted_value}` to the exact builder
environment secret endpoint. GitHub PUT is create-or-update, NOT atomic CAS.
Only observed HTTP 201 confirms creation; 204 or an uncertain acknowledgment is
not accepted creation. Preserve evidence and reconcile with independent custody
proof rather than regenerate/retry/overwrite. Concurrency does not exclude an
administrator or another writer; require one coordinated operator.

The separate `prove` dispatch injects ONLY the builder secret into its key step,
with the generated nonce and exact generated public SPKI. Bind its own current
source/run/attempt/job and `android-release-builder-prove-RUNID-1` artifact before
public verification. Its signature covers the fixed builder role/destination and
public fields, prefixed by `fleet/android-release-builder/custody-proof/v1` plus
NUL. It accepts no arbitrary message, AAB, or release-approval payload. Approval
artifacts/domains cannot substitute, even if nonce and numeric recipient ID match.

A successful observation proves the specific hosted job received the expected
key only after independent provenance replay. It does not replace Android's
reviewed builder-public-trust change and fresh qualification, Fleet's separate
qualified-consumer/lock update, authenticated independent rebuild, immutable
toolchain/runtime admission, binary-signing ledger reservation, or durable
sign-once recovery. All later signing/publication decisions stay separate.
