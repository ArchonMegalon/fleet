# Android Preview12 external rebuilder (dormant)

This lane is non-operational groundwork for an independent Preview12 rebuild
and signer. Checked-in configuration cannot rebuild, sign, hand off, upload, or
publish anything.

## Contract boundary

The implementation pins Android commit `7cef6a715867cab8000483b08db9aad2e817f63d`
and its exact consumer bytes. It treats these as different artifacts:

1. Android's non-authoritative external-signer request v1;
2. Android's exact `chummer.android.release-build-attestation/v2`, using the
   Android consumer's canonical and pretty JSON functions;
3. the externally required
   `chummer.android.external-release-signer-attestation/v1` response; and
4. Fleet's separate audit v3.

The v1 external-signer response does not replace Android v2. Fleet audit v3 is
never presented to Android as release authority.

Current consumer tests require `CHUMMER_ANDROID_CURRENT_ROOT` pointing to the
exact clean qualified checkout. The separate original-receipt integration also
requires `CHUMMER_ANDROID_CURRENT_TWO_GREEN_RECEIPT`: the unchanged qualified
TwoGreen v3 receipt. It calls the actual guarded loader and full Android
`VERIFY.verify_release_eligibility`, substituting only a published RFC test-key
trust pin and a synthetic compatibility approval. No validator is mocked there;
no APK provenance replay, release build, protected approval or custody is claimed.
The existing `real_v2_consumer` tests remain serialization/signature tests with
synthetic artifact and qualification claims, not release qualification.

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

Before loading that consumer, Fleet verifies every regular file below its
`scripts/` and `eng/` directories against the exact pinned Git commit's blob
objects, not merely the four direct lock entries or a clean working-tree
status. This includes transitively imported helpers and policy files. Missing,
modified, staged, assume-unchanged, symlinked, extra or ignored bytecode inputs
fail before Python loading. Imported bytecode is not an authority: use a pristine
checkout without `__pycache__`, and the loader suppresses new bytecode writes.
It also rejects any configured `sys.pycache_prefix` before loading: disabling
cache writes does not disable reads from an external bytecode-cache directory.
This includes prefixes supplied programmatically or with Python's `-X` option,
not merely the environment variables excluded by isolated interpreter startup.
The closure is checked again after loading. These checks do not replace the
still-required root-owned immutable filesystem and isolated protected process;
a writable checkout does not acquire signer authority by passing this preflight.

The checked-in module now contains a non-CLI transaction composition that
structurally enforces this order: authenticate and revalidate the immutable
handoff and protected provenance; replay the exact request, source, unsigned
AAB, sidecar, and two-green eligibility; durably reserve; admit credentials;
sign the AAB; create the signed sidecar; run fresh protected validation; emit
Android v2 and external v1; commit the exact external-v1 bytes; and emit Fleet
audit v3. The reservation occurs before any keystore, password, or owner
private-key read. The Android consumer and ledger adapter must be loaded from
root-owned immutable bytes, not from the writable handoff or checkout. The ledger
loader checks every ancestor up to the filesystem root as well as its own files;
a root-owned Fleet directory below a replaceable parent is not protected authority.

After that durable reservation and credential admission, the transaction checks
that the loaded Android consumer and lock agree on the approval public SPKI and
that the admitted owner private key derives that exact public identity. This
happens before AAB signing, so a missing, malformed, or wrong owner key cannot
leave a partially signed AAB. The later detached-attestation key checks remain
in place. Failure still quarantines the reserved attempt; it does not grant
permission to retry signing, rotate trust, or reuse the reservation.

The workflow-owned capability must also bind the attempt ID and exact
two-green artifact ID and digest. Supplying fresh caller values cannot reserve
or sign the same authenticated handoff again.

`PreservedProtectedValidation` is the concrete, key-free consumer/validation
composition for both execute and reconcile. Supply its `load_consumer` method
and the same object as `protected_validation_factory`. Construction requires
explicit `lock_path`, `workspace_root`, `source_graph`, `package_authority`,
`authority_root`, `bundletool`, public `upload_certificate`,
`java_tool_observation`, and exact `dotnet_root`, `java_root`, `android_sdk_root`.
There is no CLI, builder callback, or private-key argument for this composition.

The workspace is an independently retained complete eight-repository checkout
with contained Git storage, not the deleted disposable builder workspace. All
preserved roots and relevant entries must be root-owned, non-group-writable,
canonical and on read-only mounts; nested writable mounts fail closed. Complete
Git-object byte comparison also rejects ignored or assume-unchanged source
drift, using bounded two-pass streaming for Git blobs. Retained repositories
must be fully materialized plain independent clones, not filtered rebuild
checkouts: alternate/shallow/worktree/replacement storage, promisor packs,
active hooks and helper-capable Git configuration are rejected before Git runs.
The package authority and its retained inputs are verified with the real
qualified Android source-graph implementation. Exact consumer ROOT, code and
validator closure, public input hashes, tool roots/trees, and public upload
certificate are checked before credential admission and again around validation.
The transaction additionally binds the same loader, lock bytes, graph digest,
and authenticated Java root before reserving any signing attempt.

The factory invokes Android's actual `_artifact_claims`, current eligibility
verifier, `_protected_validation`, and `_validate_validation_claims`; it never
synthesizes a passing dictionary. `java_tool_observation` is the separate Android
`chummer.android.local-unsigned-toolchain-observation/v1` input, **not** Fleet's
installed-archive inventory or evidence that installed tree pins were observed.
Missing real packages, tools, signed artifacts or validations fail closed.

The qualified 7cef consumer still has its own symlink rejection in
`sign_android_release_build_attestation.py`'s `_trusted_tree_digest`: it checks
mode 022 before the link branch, so an otherwise valid root-owned 0777 internal
link fails. Fleet's repaired hasher does not replace this sealed consumer code.
The focused test executes that actual rejection; any required Android repair
needs its own review and requalification. Modeled read-only flags in temporary
tests are not deployment evidence, and no successful protected release build is
claimed by these tests.

The composition remains dormant: a protected workflow-owned provenance
authenticator, actual preserved mounts/installed toolchain, immutable ledger
adapter, and credential-admission callback are still required. The factory
neither authenticates the workspace provisioner nor proves absence of unrelated
mounts in the surrounding process. Those are protected-runtime responsibilities,
not caller JSON booleans or authority conferred by local filesystem checks.

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
a **separate binary-signing ledger**, never PR11's approval-issuance store.

The existing lock selects `config/release/android-preview12-binary-signing-ledger.json`.
That dormant policy reuses the unchanged wire-policy representation and pins the
actual approval-policy bytes for comparison. Loading requires immutable runtime
ancestry and exact hashes for the adapter and both policies. It rejects shared
HTTPS origin, service identity or receipt SPKI, and either receipt key reused
for approval/attestation signing. Null comparison/adapter/policy pins and dormant
state do not authorize any runtime. No Android authority pins change here.

Both execution and reconciliation require only
`ANDROID_PREVIEW12_BINARY_SIGNING_LEDGER_BEARER_TOKEN`. The loader maps this
signing-only capability into the unchanged client's internal credential slot;
an ambient `ANDROID_PREVIEW12_APPROVAL_LEDGER_BEARER_TOKEN` is rejected before
client construction. Provisioning must ensure genuinely different bearer values,
not merely different secret names. The consumer does not read the other secret
or pretend to prove custody from configuration.

Deploy the existing ledger service with a separate protected database, service
identity, database startup pin and receipt-signing capability. The unchanged
store rejects opening an approval database under a signing service/database
identity; it never resets a database or relaxes permanent artifact/nonce
uniqueness. Database identity is not a wire-receipt field, so actual independent
storage, TLS routing, credentials, backups and protected admission remain
deployment requirements. Changing only a nonce, policy hash or namespace on the
same database is not isolation. A reserve still does not prove exclusive signer
execution; existing protected handoff/recovery admission remains necessary.

Focused integration tests accept `FLEET_PR11_LEDGER_TEST_ROOT` pointing to the
exact reviewed PR11 client/store source. They use real temporary SQLite stores
and published RFC signature fixtures; they do not deploy services or sign AABs.

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
