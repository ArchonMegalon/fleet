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

The checked-in module now contains a non-CLI transaction composition that
structurally enforces this order: authenticate and revalidate the immutable
handoff and protected provenance; replay the exact request, source, unsigned
AAB, sidecar, and two-green eligibility; durably reserve; admit credentials;
sign the AAB; create the signed sidecar; run fresh protected validation; emit
Android v2 and external v1; commit the exact external-v1 bytes; and emit Fleet
audit v3. The reservation occurs before any keystore, password, or owner
private-key read. The Android consumer and ledger adapter must be loaded from
root-owned immutable bytes, not from the writable handoff or checkout.

The workflow-owned capability must also bind the attempt ID and exact
two-green artifact ID and digest. Supplying fresh caller values cannot reserve
or sign the same authenticated handoff again.

The composition is still dormant because Fleet does not yet provide the
protected workflow-owned provenance authenticator, immutable root-owned
consumer/adapter loader, or credential-admission callback. Those are capability
inputs rather than CLI flags, and caller-supplied JSON booleans are not accepted
as authority.

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

After credential admission, signed bytes and their attestations remain in a
deterministic owner-only recovery store until promotion succeeds. The store is
authenticated as part of the handoff and its attempt journal is independent of
the requested output path, so changing a destination cannot create a second
signing opportunity for an already reserved attempt. An
exclusive reservation record, attested-byte record, and commit-intent record
bind that recovery transaction. Failures after a commit acknowledgement, a
lost commit acknowledgement, Fleet-audit materialization, audit persistence,
or directory promotion retain the signed AAB and sidecars. The separate
reconciliation function accepts no credential callback and never signs: it
revalidates current handoff and two-green semantics, reruns protected
validation, verifies Android v2 and external v1 with the pinned public key,
and replays the exact commit through Draft #11's signed ledger adapter before
finishing audit and promotion. A local ledger-response file can never replace
that service-authenticated replay.

Draft #11 may legitimately return a signed `status` response after a lost
commit acknowledgement and a different signed `commit` response on later
reconciliation. Fleet revalidates both envelopes with the reviewed adapter,
requires the same reservation and exact external-v1 approval bytes, preserves
each response under its content digest, and keeps the first authenticated
response as the stable audit binding. It never requires unrelated request IDs
or signatures to be byte-identical.

If failure occurs after key admission but before complete v2/v1 evidence is
journaled, the private bytes are retained with an explicit `quarantined`,
`verified = false`, `reconciliationEligible = false` marker for operator
diagnosis and explicit abort. Quarantined bytes cannot enter ordinary
reconciliation or promotion; the code does not silently delete them or attempt
a second signature.
The future owner workflow must provide durable private recovery storage and
authenticate that storage as part of its signer-runtime provenance.

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
- provide durable owner-only signer recovery storage and bind it to the exact
  protected job/image/attempt rather than trusting caller-authored files;
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
- wire the tested composition callbacks to a real protected owner workflow;
- separately qualify any Android v2 owner-key rotation before updating the
  lock or admitting the rotated key.

Play upload and publication remain false even after those items are complete;
they require their existing separate owner transactions.
