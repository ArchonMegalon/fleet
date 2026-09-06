# Android Preview12 external rebuilder (dormant)

This lane is non-operational groundwork for an independent Preview12 rebuild
and signer. Checked-in configuration cannot rebuild, sign, hand off, upload, or
publish anything.

## Contract boundary

The implementation pins Android commit `388425aceac266e06265e4c0c73a4058b052d316`
and its exact consumer bytes. It treats these as different artifacts:

1. Android's non-authoritative external-signer request v1;
2. Android's exact `chummer.android.release-build-attestation/v2`, using the
   Android consumer's canonical and pretty JSON functions;
3. the externally required
   `chummer.android.external-release-signer-attestation/v1` response; and
4. Fleet's separate audit v3.

The v1 external-signer response does not replace Android v2. Fleet audit v3 is
never presented to Android as release authority.

## Required execution split

`prepare-rebuild` accepts no keystore, password, bearer, or private-key
argument. It checks out the complete source graph, binds the exact
.NET 10.0.110, JDK 17.0.20.1, Android API/build-tools 36 closures, the exact
bundletool bytes, the installed toolchain-authority receipt, and the declared
builder/signer image identities. It runs the Android unsigned build and
requires its AAB digest to equal the producer.

Its local handoff explicitly says:

```text
builderCredentialIsolationAuthority = none_local_preparation_only
eligibleForProtectedSigner = false
```

Local JSON and digest checks cannot prove job isolation. A future activation
must run the builder in a separate job/container with no signing credential
mounts, then bind the transferred bytes to exact workflow/artifact provenance.
The protected signer must use a root-owned pinned Android consumer and must not
execute builder-controlled code after keys become available.

The checked-in helpers are not a protected signer transaction. A later owner
workflow must structurally enforce this order: durable reservation; immutable
handoff capture and revalidation; credential admission; AAB signing; signed
sidecar creation; fresh protected validation; Android v2 attestation; external
v1 response; ledger commit; and separate Fleet audit. The reservation must
happen before any keystore, password, or owner private-key read. The Android
consumer and ledger adapter must be loaded from root-owned immutable bytes,
not from the writable handoff or checkout.

The resulting local toolchain object deliberately records both
`builderExecutionProvenanceAuthenticated = false` and
`protectedSignerRuntimeVerified = false`. Merely supplying a matching image
name, toolchain receipt, or rewritten digest cannot change either claim. The
external-signer attestation helper refuses to sign while either is false.

## Replay and lost responses

This lane does not introduce another HTTP or reservation protocol. It pins and
loads the signed, no-redirect durable Approval Ledger adapter reviewed in Fleet
Draft PR #11. Its adapter and policy digests remain null, and its policy source
remains `pending_merge`, so checked-in code fails closed. The existing adapter
owns reservation, replay rejection, signed receipts, bounded retry, and
lost-response recovery. Exact public external-signer v1 bytes are committed to
that ledger.

## Keys and rotation

No secret or key exists in this change. The only upload identity recorded is
the old Play upload certificate SHA-256:

```text
d9c4b635121544d5522abf1ec2dfda3c1938aab93d6726bb93c9871ec9ed1d15
```

Key aliases and secret references are null. The current Android v2 owner public
key is digest-bound. A future owner-key rotation must first merge and qualify a
new Android consumer, then update this lock in a separate reviewed change.

## Activation blockers

- merge and pin the reviewed Draft #11 ledger adapter and configured policy;
- supply immutable builder and signer images plus an installed-closure receipt;
- prove the builder job has no signer credential mounts;
- add authenticated immutable artifact provenance between jobs;
- bind the protected signer runtime and its root-owned Android consumer to that
  provenance before producing full-toolchain or Android-v2 authority;
- produce the signed-AAB two-line sidecar inside the protected signer
  transaction and pass it to the exact Android v2 consumer;
- generate fresh `protectedValidation` inside the protected signer rather than
  trusting a caller-supplied or deleted builder-workspace projection;
- make protected consumption revalidate the current lock, sidecar, source,
  two-green semantics, and authenticated execution provenance;
- configure a private immutable signed-content handoff with readback;
- configure protected secret descriptors for the recovered old upload key and
  the qualified Android v2 owner key;
- review and test the protected workflow composition.

Play upload and publication remain false even after those items are complete;
they require their existing separate owner transactions.
