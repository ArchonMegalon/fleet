# Android Preview12 external rebuilder (dormant)

This lane is non-operational groundwork for an independent Preview12 rebuild
and signer. Checked-in configuration cannot rebuild, sign, hand off, upload, or
publish anything.

The missing production authentication seam is specified for review in
[protected runtime policy proposal](android-preview12-protected-runtime-policy.md).
That proposal is not an approved trust policy or activation evidence.

## Contract boundary

The implementation pins Android commit `0d5c8f0cacfdfbb89288eb0f3906d2fdbab36d0a`,
tree `7d2585c46236f975a7a4d73a591688fd84b4228f`, and its exact consumer bytes.
This dormant consumer rebind does not qualify a builder/signer image or activate
signing. It treats these as different artifacts:

1. Android's non-authoritative external-signer request v1;
2. Android's exact `chummer.android.release-build-attestation/v2`, using the
   Android consumer's canonical and pretty JSON functions;
3. the externally required
   `chummer.android.external-release-signer-attestation/v1` response; and
4. Fleet's separate audit v3.

The v1 external-signer response does not replace Android v2. Fleet audit v3 is
never presented to Android as release authority.

Current helper checks in `test_android_preview12_external_rebuilder.py` and
`test_android_preview12_preserved_validation.py` still read
`CHUMMER_ANDROID_CURRENT_ROOT`; those suites require the exact clean `0d5c8f0c`
checkout pinned by the external lock. The earlier PR70 changed the source-graph verifier
and attestation consumer to admit a bounded sealed anonymous file descriptor;
ordinary path symlink rejection remains. PR71 adds deterministic CI compilation
and portable PDB settings. The current `scripts/build-release.sh` is
`e3b746f73d3a557f12ff93d77888aab6ffc24eca5320a49b56b782bc0836ad0c`.
It verifies captured sidecars from the external release-input root. Its admitted
source-test helper remains
`a295c226850edda9ce3a57a3c43690188e271b3059c33dd14abca04f65ef4bcf`;
the previous build-script capability entry is retained. Current eligibility is
the original Two-Green run `35365960704` artifact `10555893524`, pairing PR72
review `35350168111` attempt 1 and main `35357603833` attempt 1. Its separate
approval-consumer test requires that original receipt, SHA256
`312bbf6478450f973f6b8e2cf804a066e75ba665c7cda66464c30ed6ab9f9528`.
Old run `35219818439` remains historical only. No predecessor receipt or
approval may be relabeled. This is not builder or signer qualification.
The executable source-test capability table now includes the exact PR71 build
script digest above, not only its predecessor. Hosted offline-import regression
also runs the checked-in-lock/input-boundary suite; the exact-checkout test
compares both script and capture-helper bytes when that checkout is supplied.
Unknown scripts and missing/unsafe bootstrap, wheelhouse or oracle inputs remain
rejected. This closes an admission failure before rebuilding, not a byte-equality,
runtime-custody, signing or publication claim.
The lock's historical `approval_authority` field selects the **builder** identity
already trusted by this exact `0d5c` consumer: `fleet-release-builder-2026-09`,
`eng/trusted-release-builders/fleet-release-builder-2026-09.public.pem`, PEM SHA256
`ef44c5b7fcadaf0f115b5f0e0e7b1a65edb322bb002faf980acb654a5db8caaf`, SPKI SHA256
`41b44078d037fafd85b091b967959f77a7a4aa9f160d03749fa49889a8b1b156`.
The public-key selection and protected-environment secret descriptor below do
not activate any gate. They establish no admitted private-key custody or signer
readiness, and do not replace the RSA Play upload identity or
the separate approval key. Android's historical legacy-key compatibility remains
unchanged. Current consumer tests load the actual lock without substituting a
test key and reject mismatched IDs, paths and hashes; a complete stale operational
tuple fails the checked-in public-binding regression.

The new source tree retains Android's sealed-FD handoff fix and PR71's
deterministic compilation settings. PR72 adds build-time AAPT source exclusion
and canonical resource-designer metadata before compilation/linking/AOT. No
finished APK or AAB is rewritten. Whole-AAB equality still requires two real
independent builds; these source changes and wizard qualification do not prove it.
Qualification must come from its new original receipt, not
the historical `8c98` or `840ac` receipts. This lock's changed digest invalidates
old lock-bound rebuild/handoff observations; they cannot be relabeled or reused
for signing. No approval is issued or renewed by this source-only repin, and
the dormant rebuild/signing/publication switches remain unchanged.

The historical `real_v2_consumer` and `current_receipt_consumer` suites instead
read `CHUMMER_ANDROID_HISTORICAL_BUILDER_ROOT`. The latter additionally requires
`CHUMMER_ANDROID_HISTORICAL_BUILDER_TWO_GREEN_RECEIPT`: the unchanged qualified
TwoGreen v3 receipt from hosted workflow `34723623558`, artifact `10306679223`.
The receipt file SHA-256 is
`ce610801b27a7b5942c462ce5d10b2e6a3cb230bf4e29924979e37f706e1119b`;
its canonical eligibility digest is
`5e875d040489714d2d9a7acaf32e4c52a485b8363f73353a8bcbc17d06f73be7`.
It binds review run `34716647057` and later main run `34720323198` for the
same tree and seven SR5 wizard journeys; publication and Play upload remain
unauthorized. The integration calls the actual guarded loader and full Android
`VERIFY.verify_release_eligibility`, substituting only a published RFC test-key
trust pin and a synthetic compatibility approval. No validator is mocked there;
no APK provenance replay, release build, protected approval or custody is claimed.
The existing `real_v2_consumer` tests remain serialization/signature tests with
synthetic artifact and qualification claims, not release qualification.

## Required execution split

`prepare-rebuild` accepts no keystore, password, bearer, or private-key
argument. It checks out the complete source graph, binds the exact
.NET 10.0.111 (9,258 files, 4,276,188,988 bytes), JDK 17.0.20.1 (246 files,
332,109,578 bytes), and Android API/build-tools 36 (11,523 files,
314,037,662 bytes), along with their exact tree digests, the exact bundletool
bytes, the separate installed-closure receipt, and the declared builder image
identity. Downstream signer configuration remains a separate gate.
The SDK111 measurement record's outer execution remains FAILED. A separate
2026-09-16 installed-closure probe observed these same three exact tree/count/size
tuples in the selected builder image and passed its post-fences and cleanup;
it does not rewrite that historical failure or establish runtime custody.
It runs the Android unsigned build and
requires its AAB digest to equal the producer.

Canonical Android promotion leaves the rebuilt AAB, graph and sidecar at
`0444`. Rebuild intake requires those owned, single-link, bounded regular
outputs; writable files and symlink paths are rejected. The graph and sidecar
are descriptor-captured into exclusive `0600` copies below a new `0700`
directory, with identity, digest, sync and readback checks. The originals are
neither chmodded nor replaced. Existing private-input checks stay strict, and
the canonical Android sidecar parser binds both rebuilt digests before handoff.
This copy boundary does not authenticate a workflow, qualify runtime custody,
or turn a failed first-producer wrapper into success. The synthetic tests model
compilation; actual independent rebuild equality remains required.

`prepare-rebuild --retain-mismatch-diagnostics` optionally retains a rejected
independent AAB at the fixed sibling `OUTPUT_DIR.mismatch-diagnostics`. The
original mismatch remains a failure (CLI exit 2), with no verified handoff.
This exclusive `0700` directory contains only `0600` copies of the rejected AAB,
its rebuilt graph and sidecar, and `REBUILD_MISMATCH_DIAGNOSTICS.json`. Copies
are bounded by the existing AAB/JSON limits and a 16 KiB sidecar limit; the
small receipt binds their exact hashes/sizes and records all signing, publishing,
upload and retry authority as false. An existing diagnostic path blocks this
opt-in invocation before rebuilding; it is never overwritten or reused.

The owner must select durable private output storage. Files and directories are
synced and read back before ordinary stage cleanup. If retention fails, the CLI
reports that explicitly and preserves the original `.<OUTPUT_DIR-name>-*`
private stage alongside any partial diagnostics for operator inspection. That
exception can retain build scratch/logs; successful diagnostic capture retains
only the four named files, with no approvals or toolchain observations. Inspect
and retire these diagnostic files explicitly; they grant no rebuild retry or
release authority. These checks assume private owner-controlled custody, not
atomic protection from a concurrent same-UID/root writer. Default behavior and
successful rebuild handoff contents remain unchanged.

### Observed public builder inputs, not activation

The dormant lock selects these existing public builder bytes:

- builder image `ghcr.io/archonmegalon/chummer-android-builder@sha256:5298279ccc96316c546d7bebe00af639e38c22bdac081a980ba10e7dc965e40a`;
- original 2,362-byte `sdk111-tree-measurement.AV1kqHwI/archive-inventory.json`,
  SHA-256 `3a37e627299076065f5881be6e157dd1887f3428dfe2a698ffc8cf4e465ad330`.

The retained public evidence lives below
`/docker/chummercomplete/_completion/chummer-next-wave/android-persistence-owner-20260909.K00qFF/`.
`builder-installed-closure-probe-v2-20260916/execution/RESULTS.json` has SHA-256
`62b43baf2979ed3bceefc01c398d9625d318b2e4a569d870528e4f5a7778b88c`;
its original `observation.json` has SHA-256
`99da464a517d5543ed7cc7e1402dd4ab213de5f6421d4a5b85c0e4845a13bca5`.
The observation binds image config
`sha256:9795253a6f2218f9a757cefaea59ebd8a9d3e056fb6e4d9011b5179b42862be5`
to the repository-qualified digest and inventory above. All originals, including
older failed observations, remain unchanged; no inventory is regenerated or
relabeled for this selection.

This is a public byte selection, not authentication or qualification. The probe
records `builderQualified`, `installedClosureAdmitted`,
`builderExecutionProvenanceAuthenticated` and `protectedSignerRuntimeVerified`
as false. Pinning its inventory does not turn those claims true. The inventory
is not Android's separate Java observation or a protected-runtime attestation.
`state` remains `dormant`, `rebuild.enabled` remains false, reservation remains
unconfigured with a null adapter digest, and
signed-content handoff, publication and Play upload remain disabled. Both
unsigned activation gates and every protected-signing gate still apply. There
is no new runtime authenticator, signer caller or execution in this change.

### Selected signer inputs, not activation

The 2026-09-16 operator readback verified the existing image digest above still
maps to config `9795253a6f2218f9a757cefaea59ebd8a9d3e056fb6e4d9011b5179b42862be5`.
The lock selects that same immutable image for the **separate** signer role;
sharing image bytes does not share jobs, containers, credentials or runtime
authority. Actual signer-profile and PID1 watchdog observations do not establish
authenticated protected-job custody or admit the whole signing transaction.

The protected GitHub environment `android-preview12-release-builder`, ID
`21853652742`, was separately observed with exactly these four secret names.
Only metadata was read for this selection; no values were retrieved:

| Lock field | Selected existing input |
| --- | --- |
| `approval_authority.private_key_secret` | `ANDROID_PREVIEW12_RELEASE_BUILDER_ED25519_PRIVATE_KEY_PKCS8_B64` |
| `upload_key.keystore_secret` | `ANDROID_PREVIEW12_UPLOAD_KEYSTORE_B64` |
| `upload_key.store_password_secret` | `ANDROID_PREVIEW12_KEYSTORE_PASSWORD` |
| `upload_key.key_password_secret` | `ANDROID_PREVIEW12_KEY_PASSWORD` |

`upload_key.key_alias` is `chummer-upload`, matching the retained original
keystore's alias and the unchanged `d9c4...` certificate identity, not the
obsolete native-v3 alias `upload`. A secret name's presence does not verify its
value, SPKI, certificate, availability to a future job, or custody; the existing
reserved transaction must perform its unchanged checks before signing. The
builder key stays in the protected GitHub job, never the ordinary local builder.

These six field selections remove only six missing-input configuration errors.
The four remaining errors are disabled signed-content handoff, dormant state,
disabled independent rebuild, and unconfigured reviewed ledger adapter. Both
owner readiness and signing remain rejected; all publication/upload flags stay
false. A future signing-bound rebuild must consume the **final configured lock**:
this partial lock and its new digest cannot later be relabeled as that authority.

### Separate rebuild inputs

The two mandatory inputs are `--installed-closure-receipt` (Fleet's
lock-digest-bound installed inventory) and `--java-tool-observation` (Android's
canonical `chummer.android.local-unsigned-toolchain-observation/v1` file).
The ambiguous former `--toolchain-authority` option is not accepted; neither
input defaults to the other. Only the observation reaches Android's existing
`CHUMMER_ANDROID_RELEASE_TOOLCHAIN_AUTHORITY` environment variable. The installed
receipt is used only for Fleet's closure check.

Preparation captures both canonical owner-only paths, file identities and byte
digests before staging. Same-path/inode inputs are rejected. Android hashes the
full `dotnet --info` output, including its working-directory-dependent
`global.json` path. The original observation therefore remains an unchanged
historical input; the qualified Android `observe-toolchain` and `verify-toolchain`
commands create and verify a separate canonical observation in the actual staged
Android build directory. Only `dotnet.versionOutputSha256` may differ between
the two observations. Every other field must match with exact JSON types, and
the measured Java/.NET closure must match the lock. No digest is substituted or
version check skipped, and the controller never changes its global cwd.
The build receives that contextual observation. Original and contextual input
snapshots reject changes, including identical-byte file replacement, around
validation and build execution, including failure paths. These are local preparation checks,
not immutable runtime custody. The unchanged seven-file handoff binds the
installed receipt through its lock and toolchain closure, and the observation's
tools through those measured trees; it does **not** transport a new observation
byte digest or an eighth file. Protected validation independently preserves and
revalidates its own separate observation and installed receipt.

The contextual observation follows the existing disposable build-input
lifecycle; these changes do not add durable controller evidence retention.
The future protected controller must preserve its validation closure separately.

The dedicated separate-input tests optionally use
`CHUMMER_ANDROID_CURRENT_ROOT` at the exact checked-in Android lock authority
and its original hosted receipt via `CHUMMER_ANDROID_CURRENT_TWO_GREEN_RECEIPT`
(the older `CURRENT_BUILDER_*` variable names remain aliases, not older pins). Actual-loader
negative tests reject inventory as an observation; preparation tests model SDK
execution and cannot establish an offline build. This plumbing change neither
repins the Android authority or qualifies/activates installed SDK111 custody.
Actual installed closure, admitted immutable image/controller, complete offline source
and package inputs, protected approval and real deterministic rebuild remain
required.

### Offline bundle snapshot lifetime

`checkout_source_graph_from_bundles` still captures and authenticates all eight
complete local bundles before any Git operation. It imports them in descending
authenticated bundle size, retaining canonical repository order for ties. After
each successful unbundle and strict full Git fsck, it removes only that owned
private snapshot and immediately closes its held descriptor, before checking out
that repository. The original transport files are never removed or reread in
place of authenticated snapshots. Final exact graph, ancestry and repository-byte
checks are unchanged.

Held parent, staging-directory and snapshot identities fence retirement. A
replaced entry, changed snapshot or uncertain unlink fails closed; scoped cleanup
preserves unknown entries rather than recursively deleting the staging tree.
Cleanup closes the other held descriptors even if retirement fails. This assumes
the existing private owner-controlled staging custody, not atomic conditional
unlink against a concurrent same-UID or root writer.

This reduces overlapping transport copies and imported Git storage; it does not
establish a new capacity floor. Bundle sizes do not bound Git expansion, checkout
allocation, indexes or build/oracle scratch. Callers still need a filesystem quota
and measured peak with reserve; no signing, deployment or eligibility gate changes.

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
`java_tool_observation`, `installed_closure_receipt`, and exact `dotnet_root`,
`java_root`, `android_sdk_root`.
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
The mandatory `installed_closure_receipt` is a separate preserved file, bound by
`toolchain.installed_closure_receipt_sha256` in the reviewed lock. Its bytes and
file identity are rechecked; it does not replace `java_tool_observation` or
authenticate builder execution or protected signer runtime provenance.
Missing real packages, tools, signed artifacts or validations fail closed.

The pinned 8ea consumer's `sign_android_release_build_attestation.py`
`_trusted_tree_digest` distinguishes symlinks before checking writable mode bits.
A root-owned 0777 link is not rejected merely for its link mode: the actual
`_trusted_tree_link` checks every hop for containment and ownership, rejects
unresolved or excessive-hop links, and requires safe target type and permissions.
Regular files and directories retain the root-owned, non-writable checks.
This is the inspected current consumer behavior, not Fleet substituting its own
hasher or evidence of an operational protected toolchain. Modeled ownership and
read-only flags in temporary tests are not deployment evidence, and no successful
protected release build is claimed by these tests.

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
Draft PR #11. The binary-policy digest is pinned, but the adapter digest remains
null, `configured` remains false, and `protocol_source` remains
`reviewed_fleet_draft_11_pending_merge`, so checked-in code fails closed. The existing adapter
owns reservation, replay rejection, signed receipts, bounded retry, and
lost-response recovery. Exact public external-signer v1 bytes are committed to
a **separate binary-signing ledger**, never PR11's approval-issuance store.

The existing lock selects `config/release/android-preview12-binary-signing-ledger.json`.
That dormant policy reuses the unchanged wire-policy representation and pins the
actual approval-policy bytes for comparison. Loading requires immutable runtime
ancestry and exact hashes for the adapter and both policies. It rejects shared
HTTPS origin, service identity or receipt SPKI, and either receipt key reused
for approval/attestation signing. Public policy pins do not overcome the missing
adapter admission or dormant state. No Android authority pins change here.

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

The existing alias and four protected secret names are selected above, without
embedding or accessing any private value. The current Android v2 owner public
key is unchanged and digest-bound. A future owner-key rotation must first merge and qualify a
new Android consumer, then update this lock in a separate reviewed change.

## Activation blockers

- merge and pin the reviewed Draft #11 ledger adapter and configured policy;
- admit the selected immutable builder/signer image and installed closure in the
  actual distinct runtime roles;
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
- admit actual protected-job custody and validate the selected existing upload
  and Android v2 owner credentials after reservation;
- wire the tested composition callbacks to a real protected owner workflow;
- separately qualify any Android v2 owner-key rotation before updating the
  lock or admitting the rotated key.

Play upload and publication remain false even after those items are complete;
they require their existing separate owner transactions.
