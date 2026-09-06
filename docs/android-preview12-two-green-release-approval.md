# Preview12 Two-Green release approval

This is a dormant Fleet-owned approval lane for the exact Android Preview12
Two-Green receipt. It is deliberately separate from the Play AAB signer.

It approves only that the exact Android main tree and Preview12/code12 identity
are backed by the exact successful reviewed and main API-36 Two-Green evidence.

It never accepts, signs, uploads, or publishes an AAB. Its output always keeps
`signingAuthorized`, `publicationAuthorized`, and
`googlePlayUploadAuthorized` false.

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

The final GitHub artifact exposes exactly two public files: the signed approval
and the signed durable commit receipt. The latter binds the same reservation
ID, a monotonic terminal revision, the exact stored approval bytes, and the
prior signed reservation-receipt digest. It is evidence only; it does not grant
signing, upload, processing, distribution, or publication authority.

## Dormant state

The checked-in policy fails before the protected environment: it is not ready,
activation is disabled, environment/key configuration is false, no public-key
digest or human reviewer identity is pinned, and the ledger URL, hostname,
service identity, bearer credential and receipt-verification public key are all
unset. No key or
repository/environment secret is included.

Do not create an approval key in Fleet. A future operator must supply an existing
Ed25519 PKCS#8 private key only as the protected environment secret named by the
policy. It stays in memory, is checked against the reviewed public-key digest,
and is never included in the public JSON or Actions artifact.

## Activation transaction

Activation requires a separate reviewed policy and operations change: deploy
and independently review a durable external ledger that implements the checked
contract, provision its exact HTTPS origin, allowlisted hostname, logical
service identity, Ed25519 receipt public key and environment-only bearer
credential, then provision the
`android-preview12-release-approval` environment for protected branches, require
at least one explicit human `User` reviewer, disallow Team reviewers and
administrator bypass, prevent self-review, add the external key only there,
pin the exact reviewer IDs/logins and the key's SPKI-DER SHA-256, set the two
approval `configured` flags, the ledger `configured` flag and replay authority,
`state: ready`, and `activation.enabled: true`, then land
through protected Fleet `main`. Merely changing the checked-in policy flags
cannot activate the current implementation.

The workflow then rechecks the live environment API response after the GitHub
environment gate, verifies the exact Two-Green workflow run, artifact archive,
receipt digest, current protected Android and Fleet main commit/tree, evidence freshness,
request nonce, Preview12 version, and signed open durable reservation. The
serialized Actions-artifact ledger is only a best-effort duplicate observation
because artifacts can expire or be deleted; it is not replay authority and
cannot substitute for the external ledger.

The public JSON records that the protected environment gate passed and that its
configured reviewer set matched the reviewed policy. It deliberately does not
claim or identify the individual account that approved that deployment.

## Explicit non-authority

This lane is not the Play upload-key signer, not an AAB verification or signing
lane, and not a publication transaction. A later signing/upload system may use
the public approval as one input, but must independently require its own
protected environment, exact AAB authority, upload-key custody, exactly-once
reservation, Play processing receipt, and physical-install proof.
