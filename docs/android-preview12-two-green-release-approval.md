# Preview12 Two-Green release approval

This is a source-configured Fleet-owned approval lane for the exact Android
Preview12 Two-Green receipt. The reviewed READY policy is source-qualified, not
runtime-verified by its presence. It is separate from the Play AAB signer.

It approves only that the exact Android main tree and Preview12/code12 identity
are backed by the exact successful reviewed and main API-36 Two-Green evidence.

It never accepts, signs, uploads, or publishes an AAB. Its primary output is
the exact `chummer.android.two-green-release-approval/v1` contract consumed by
the bound Android `9cbe9136a786bf5c8dee233e77656678c838c481` release
verifier at tree `46322c4789f8de397e043ba29ed93e0186ff9cc7`. Public-key
compatibility, hosted consumer qualification and issuer activation are separate
claims. It always keeps
`signingAuthorized`, `publicationAuthorized`, and
`googlePlayUploadAuthorized` false.

Fleet emits an exact compact object: `fleet-release-approver-2026-09`, role
`android_internal_release_approver`, scope
`android_internal_release_preparation`, Ed25519 over sorted compact UTF-8 JSON
without a trailing newline, and no extra fields. The approval binds the raw
Two-Green receipt digest and eligibility digest, source commit/tree,
Preview12/code12, dependency graph, environment policy, challenge nonce,
expiry, the qualified provenance-validator digest, and Fleet's adapter audit
receipt digest (the existing `provenanceReplaySha256` field).

The current input is the exact Two-Green v3 wizard-only receipt, with all seven
journeys, the qualified workflow/environment/gate/policy bindings, and the exact
canonical dependency graph. The historical Android `388425ace` fixture remains
only a public-key and approval-v1 byte-shape fixture; it is not current evidence.
The existing workflow audits authenticated hosted Two-Green artifact metadata
and bytes. It does **not** run Android's local source/archive provenance replay;
pinning that validator's hash does not mean it was executed by Fleet.

Every request also binds a fresh 256-bit approval nonce, a live protected
Android `main` commit/tree snapshot, and one exact Two-Green artifact. The
lane rejects evidence older than 24 hours and refuses a second public approval
artifact for the same Two-Green artifact ID. A signed external ledger receipt
is now mandatory authority; the GitHub artifact search remains diagnostic only.

## Durable exactly-once ledger

The ledger subject is canonical and binds all of:

```text
Two-Green GitHub artifact ID
approval request nonce (exactly 256 bits, lowercase hex)
Two-Green artifact archive SHA-256
Two-Green receipt SHA-256
Android main tree
exact approval-policy SHA-256
package/version name/version code
```

Both the artifact ID and request nonce are independent uniqueness subjects.
The external service contract must durably enforce those uniqueness constraints
under concurrent requests. Its `reserve`, `status`, `commit`, and `abort`
operations are idempotent by deterministic request IDs. Only an open `reserved`
receipt permits a new approval to be signed. `commit` atomically stores the
exact public approval bytes; `abort` is terminal and is rejected after commit.

Every response is bounded strict JSON and contains a canonical receipt signed
by the service's reviewed Ed25519 key. The client additionally requires the
reviewed HTTPS origin, the exact hostname allowlist, the exact logical service
identity, normal platform TLS verification, and an environment-only bearer
credential. Redirects, unknown fields, duplicate JSON keys, non-finite values,
wrong content type/length, signature drift, service drift, subject drift, and
unavailability all fail closed.

The workflow reserves before invoking the approval signer and commits before
uploading the public JSON. If a commit response is lost after the server made
the durable change, the client reconciles through `status`. If a later workflow
run encounters the committed subject, it restores the exact public approval
bytes from the signed durable receipt instead of signing a second approval.
If every initial reserve response is lost, the client performs a signed unbound
status lookup and then replays the deterministic reserve request to obtain a
signed reserve snapshot. A separate `always()` cleanup step performs a
status-aware, idempotent abort after an ordinary later-step failure or
cancellation. Runner loss cannot guarantee local cleanup, so every
reservation also has an exact 15-minute service-enforced lease; the service
must terminally abort an uncommitted reservation when that lease expires. No
approval artifact is uploaded unless the exact bytes returned by commit equal
the locally verified approval.

The signer and ledger credentials are never placed in the same workflow step.
Reserve, commit, and cleanup steps receive only the ledger bearer credential;
the approval step receives only the Ed25519 approval key. This prevents the
unrelated credential from entering the same parent-shell environment. The
ledger receipt-signing key is independently held by the external service and
must be distinct from the approval-signing key.

Cross-repository Android evidence fetches use a third, separately named
protected-environment credential:
`ANDROID_PREVIEW12_CROSS_REPO_ACTIONS_READ_TOKEN`. Fleet's default
`GITHUB_TOKEN` is never used as a fallback for Android. The credential must be
either a fine-grained PAT or GitHub App installation token scoped only to
`ArchonMegalon/chummer-android` with `Actions: read`, `Contents: read`, and
`Metadata: read`. Its step fetches only Android repository/run/artifact/branch/
commit authority. A separate Fleet-only step uses the normal Fleet token for
Fleet environment, branch, commit, and diagnostic artifact observations. The
cross-repository credential is absent from signer and ledger steps, is never
printed or persisted, and malformed or missing values fail before network
access.

The final GitHub artifact exposes the Android-compatible signed approval, the
separate Fleet audit receipt when this run performed the signing operation, and
the signed durable commit receipt. A recovery run restores the exact previously
committed Android approval and does not invent a replacement Fleet audit
receipt. The durable receipt binds the same reservation
ID, a monotonic terminal revision, the exact stored approval bytes, and the
prior signed reservation-receipt digest. It is evidence only; it does not grant
signing, upload, processing, distribution, or publication authority.

## Source-configured state

The checked-in policy selects the existing closed READY shape: its environment,
cross-repository reader, approval key, ledger and replay bindings are configured,
and the source activation flag is enabled. This is a public configuration
transaction, not evidence of authenticated operability, continuous health or a
completed approval. All runtime gates remain mandatory. The unchanged dormant
template remains supported and tested to reject before credential access.

The ledger origin is `https://chummer.run`, service identity
`fleet-preview12-approval-ledger-20260914`, with receipt SPKI SHA256
`6bff5bfb80dbdb3892a7a9ef7f149baf6a3ad711ea4623621d5baf74079e55b2`.
Only its reviewed public verification key is included; the four paths, request
limits, lease and retry bounds are unchanged. Android's exact consumer and
public approver remain pinned. No private key, bearer value or repository/
environment secret is included.

The connector is ephemeral: it exists only during a root-supervised workflow
window and is removed afterward. The public ledger route is not continuously
available or continuously healthy. Before dispatch, root must bind fresh
environment/runtime/configuration evidence and independently confirm the exact
owned connector, protected origin/TLS and environment configuration. The first
authenticated mutation is the actual protected workflow reservation: its signed
service identity must validate before approver-key use. No dummy reservation or
authenticated health/status probe substitutes for that transaction.

Supervise the connector within its fixed lease. On normal completion, confirm
terminal workflow/ledger disposition, then perform connector-first cleanup.
Lease expiry, EOF or error always triggers connector-first cleanup even when the
workflow disposition remains ambiguous; the connector is never extended merely
to wait for a cleanup job. If owned connector absence is unresolved, preserve
the NFT boundary and token custody. Conditional configuration rollback requires
actual owned-process absence. A policy file cannot replace these execution checks.

The fixed existing public approver is
`eng/trusted-release-approvers/fleet-release-approver-2026-09.public.pem`, PEM
SHA256 `0ccffb5997e10dea7531894e00a2376f8da309a8e50da00199ffc3073de85dcb`,
SPKI SHA256 `b0afed082c23ee1af1c828dde5b28ffa4061ceaa71d1bab4c11927ff142f43a3`.
Android admits this identity only for preparation approval. The separate
`fleet-release-builder-2026-09` identity cannot approve. Fleet exposes no key
selection or partly refreshed profile: key ID, role, scope, public bytes, exact
consumer and output posture are admitted together before credentials or signing.
Old consumer/new key combinations and stale evidence hashes fail closed.

This source transaction does not generate, retrieve or configure a private key.
An independently approved execution may supply the existing key only through the
protected environment secret named by the policy. Its derived public key must
match the reviewed pin. Any future identity change requires a separate reviewed
requalification of both Android and Fleet; changing Fleet alone cannot confer
consumer trust.

## Activation transaction

The prepared READY policy requires independent non-writer review and protected
Fleet main landing before use. Root must separately recheck the actual ledger
and `android-preview12-release-approval` environment, including current secret
availability without exposing values, protected branches, administrator bypass
disabled and exactly its branch-policy protection rule. Prior provisioning
metadata is not a fresh execution or authenticated-service receipt.
The owner's zero-manual-review policy requires no reviewer rule or identities;
reintroduced reviewer rules fail closed. Keep credentials only in their existing
separate protected-environment slots and retain Android's exact public-key and
consumer-contract pins. Source READY flags alone do not authorize a dispatch,
prove authenticated ingress or establish a continuously running connector.

The workflow then rechecks the live environment API response after the GitHub
environment gate, verifies the exact Two-Green workflow run, artifact archive,
receipt digest, current protected Android and Fleet main commit/tree, evidence freshness,
request nonce, Preview12 version, and signed open durable reservation. The
serialized Actions-artifact ledger is only a best-effort duplicate observation
because artifacts can expire or be deleted; it is not replay authority and
cannot substitute for the external ledger.

The separate Fleet audit JSON records that the exact environment's automated
branch/no-bypass checks passed. It reports zero reviewer counts, an empty
reviewer list, no pinned human reviewer set, no self-review requirement, and
`humanEnvironmentReviewRequired: false`. `protectedEnvironmentGatePassed`
does not mean a human approved anything. Its
canonical SHA-256 is signed into the Android approval as
`provenanceReplaySha256`. It does not claim a human approval or record an
approval actor.

Local current-consumer tests require `CHUMMER_ANDROID_CURRENT_ROOT` at the exact
commit above, with clean source and exact file digests; matching only the tree is
insufficient. They verify the actual protected public tuple before substituting
published RFC 8032 bytes for the already admitted approval-only identity in the
test process. They exercise the actual signature consumer and graph normalizer,
and prove synthetic CI metadata does not qualify as full eligibility.
`CHUMMER_ANDROID_CURRENT_TWO_GREEN_RECEIPT` supplies the separately pinned
original hosted receipt for full consumer interoperability. These tests grant
no operational approval, establish no protected custody, and perform no local
APK/archive provenance replay.

The current original qualification receipt is from Two-Green run `35032475683`, artifact
`10421743956`, pairing PR `65` review `35019359374` and main `35026224346`. Its exact
26,383-byte JSON SHA256 is
`986131d9b0d487efcd4d1044260337ae65d0429f095910b7c8aad66a0d18e4b1`;
the 26,597-byte artifact archive SHA256 is
`21bda71bb846acd77958eb22dd79a27d6a817a189b2ad3b3c50441792368d274`;
the canonical dependency graph SHA256 is
`b4f0e957bf8ab7544a55b934a204cb5283a0fb73f671daaa0ca2db13d737e574`.
The exact workflow hash is
`a1c19279957f0a0e53ca715119c339a628718e8e219f76527c528075f757fee3`.
The P0 source, workflow, consumer verifier,
provenance materializer, environment, wizard-gate, Two-Green-policy and public-key
bytes were remeasured from exact source and remain unchanged from `e0d997b`.
The dependency source tuples are unchanged apart from the Android tree.
The previous `e0d997b`/`f816035` qualification, like `d4e9116`/`301180a`, is
historical and is rejected as current input. Rebinding does not bypass freshness
or current protected-main checks: advancing Android main requires a separately
reviewed qualification, and this receipt cannot be silently reused for it.
Original hosted evidence stays external; tests never rewrite it or historical fixtures.

The optional builder suites still bind their historical source and original
receipt. They now use `CHUMMER_ANDROID_HISTORICAL_BUILDER_ROOT` and
`CHUMMER_ANDROID_HISTORICAL_BUILDER_TWO_GREEN_RECEIPT`; their historical fixtures
and exact commit checks are unchanged. They are not current Android builder
qualification, and skipping them does not establish it.

## Explicit non-authority

This lane is not the Play upload-key signer, not an AAB verification or signing
lane, and not a publication transaction. A later signing/upload system may use
the public approval as one input, but must independently require its own
protected environment, exact AAB authority, upload-key custody, exactly-once
reservation, Play processing receipt, and physical-install proof.
