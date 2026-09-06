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
artifact for the same Two-Green artifact ID.

## Dormant state

The checked-in policy fails before the protected environment: it is not ready,
activation is disabled, environment/key configuration is false, no public-key
digest or human reviewer identity is pinned, and no key or
repository/environment secret is included.

Do not create an approval key in Fleet. A future operator must supply an existing
Ed25519 PKCS#8 private key only as the protected environment secret named by the
policy. It stays in memory, is checked against the reviewed public-key digest,
and is never included in the public JSON or Actions artifact.

## Activation transaction

Activation requires a separate reviewed policy change: provision the
`android-preview12-release-approval` environment for protected branches, require
at least one explicit human `User` reviewer, disallow Team reviewers and
administrator bypass, prevent self-review, add the external key only there,
pin the exact reviewer IDs/logins and the key's SPKI-DER SHA-256, set the two
`configured` flags, `state: ready`, and `activation.enabled: true`, then land
through protected Fleet `main`.

The workflow then rechecks the live environment API response after the GitHub
environment gate, verifies the exact Two-Green workflow run, artifact archive,
receipt digest, current protected Android main commit/tree, evidence freshness,
request nonce, and Preview12 version. A serialized artifact-ledger check permits
only one public approval for each Two-Green artifact ID, after which the
workflow emits one Ed25519-signed public JSON.

The public JSON records that the protected environment gate passed and that its
configured reviewer set matched the reviewed policy. It deliberately does not
claim or identify the individual account that approved that deployment.

## Explicit non-authority

This lane is not the Play upload-key signer, not an AAB verification or signing
lane, and not a publication transaction. A later signing/upload system may use
the public approval as one input, but must independently require its own
protected environment, exact AAB authority, upload-key custody, exactly-once
reservation, Play processing receipt, and physical-install proof.
