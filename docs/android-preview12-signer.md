# Android Preview12 protected signer groundwork

Fleet owns this signing transaction; the mobile repository owns the unsigned
build recipe. The checked-in lane is intentionally blocked. It cannot enter an
environment, download candidate bytes, read a signing secret, sign, upload to
Play, publish to Registry, or create a GitHub release in its current state.

## Trust split

The workflow has three jobs on separate fresh GitHub-hosted runners:

`workflow_call` is intentionally accepted only when the caller also executes in
`ArchonMegalon/fleet`; mobile hands over IDs and digests through Fleet release
orchestration rather than importing Fleet environment secrets into an app-repo
run. The `job.workflow_*` identity is used to check out and attest the exact
reusable-workflow commit.

1. `contract` checks out the exact Fleet workflow commit and fails unless the
   workflow came from protected Fleet `main`, every toolchain input is locked,
   the final signer OCI digest is locked, and signing was explicitly enabled.
2. `trusted-intake` is reachable only after that check. Its separate
   `android-preview12-intake` environment supplies one credential with read-only
   access to the exact mobile Actions run and artifact APIs. It checks two
   distinct successful runs at the same exact source SHA, the locked workflow
   paths, artifact ID/name/API digest/download digest, candidate digest, and an
   unsigned AAB. It never checks out the mobile repository or executes anything
   from the candidate artifact.
3. `sign-once` downloads only the sanitized intake artifact and runs inside the
   digest selected by the contract job. The image contains the trusted Fleet
   transaction program. It checks exact `Preview12` / version code `12`, checks
   the keystore certificate before mutation, invokes `jarsigner` once, verifies
   the resulting certificate, and emits the signed AAB plus an attestation whose
   publication and upload fields are both `false`.

The one-day GitHub artifacts are private CI evidence, not a public client shelf.
There is deliberately no Play upload job and no job targeting
`android-play-upload`.

## Immutable toolchain closure

`config/release/android-preview12-signer-toolchain.lock.json` pins the amd64
Python and .NET SDK base manifests and every downloaded JDK, Android SDK
platform, Android build-tools, and bundletool input by SHA-256. The transaction
lock pins that build-input manifest by SHA-256. Keeping the final OCI digest in
the separate transaction lock avoids an impossible self-referential image
digest. The Dockerfile downloads only the locked archives, verifies each digest
before extraction, and records the resolved closure in
`/opt/fleet-signer/toolchain-installed.json`.

The image definition can be tested without publishing it:

```bash
docker build --platform linux/amd64 \
  --file containers/android-preview12-signer/Dockerfile \
  --tag fleet-android-preview12-signer:local .
```

Do not put keystores, passwords, broker tokens, or certificate material in the
image, build context, repository, workflow inputs, or artifacts.

## Exact prerequisites before enabling

An authorized operator must complete all of the following in order. None were
created or exercised while this groundwork was implemented.

1. Review and build the linux/amd64 image, publish that non-secret toolchain
   image through an approved container lane, and record its immutable
   `sha256:...` manifest digest in the lock.
2. Record the exact two distinct mobile workflow paths that produce the
   unsigned candidate and independent green verification.
3. Have the upload-key custodian derive and independently verify the SHA-256 of
   the DER upload certificate, identify its RSA or EC key type, then record the
   non-secret fingerprint and matching allowed SHA-256 signature algorithm in
   the lock.
4. Create `android-preview12-intake` in Fleet with required reviewers, protected
   `main` only, no self-approval, and
   `ANDROID_PREVIEW12_CANDIDATE_BROKER_TOKEN`. The token must be independently
   scoped to Actions run/artifact read access for only
   `ArchonMegalon/chummer6-mobile`.
5. Create `android-preview12-signing` in Fleet with required reviewers,
   protected `main` only, no self-approval, and the three upload-key secrets
   named in the workflow. It must not contain Registry, Play, release, package,
   deployment, or repository-write credentials.
6. Set Fleet variable `ANDROID_PREVIEW12_SIGNER_IMAGE` to the exact
   `repository@sha256:digest` recorded in the lock.
7. Add a durable external reservation/receipt store keyed by source SHA,
   artifact ID, candidate digest, certificate digest, and signer image digest
   before claiming replay-proof exactly-once semantics across separate workflow
   runs. The current concurrency key prevents overlap and the code invokes the
   signer once per transaction, but one-day CI retention is not a durable
   cross-run transaction ledger.
8. Only after the preceding receipts are reviewed, change lock state to `ready`
   and signing to enabled in a separately approved protected-path change.

Keep `android-play-upload` absent or disabled. A later Play transaction must be
a separate environment and workflow with its own approval and cannot be added
to this signer transaction.
