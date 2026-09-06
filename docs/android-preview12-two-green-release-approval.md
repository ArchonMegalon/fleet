# Preview12 Two-Green release approval

This is a dormant Fleet-owned approval lane for the exact Android Preview12
Two-Green receipt. It is deliberately separate from the Play AAB signer.

It approves only that the exact Android main tree and Preview12/code12 identity
are backed by the exact successful reviewed and main API-36 Two-Green evidence.

It never accepts, signs, uploads, or publishes an AAB. Its output always keeps
`signingAuthorized`, `publicationAuthorized`, and
`googlePlayUploadAuthorized` false.

## Dormant state

The checked-in policy fails before the protected environment: it is not ready,
activation is disabled, environment/key configuration is false, no public-key
digest is pinned, and no key or repository/environment secret is included.

Do not create an approval key in Fleet. A future operator must supply an existing
Ed25519 PKCS#8 private key only as the protected environment secret named by the
policy. It stays in memory, is checked against the reviewed public-key digest,
and is never included in the public JSON or Actions artifact.

## Activation transaction

Activation requires a separate reviewed policy change: provision the
`android-preview12-release-approval` environment for protected branches, require
at least one human reviewer, prevent self-review, add the external key only
there, pin its SPKI-DER SHA-256, set the two `configured` flags, `state: ready`,
and `activation.enabled: true`, then land through protected Fleet `main`.

The workflow then rechecks the live environment API response after the GitHub
environment gate, verifies the exact Two-Green workflow run, artifact archive,
receipt digest, Android main commit/tree, and Preview12 version, and emits one
Ed25519-signed public JSON.

## Explicit non-authority

This lane is not the Play upload-key signer, not an AAB verification or signing
lane, and not a publication transaction. A later signing/upload system may use
the public approval as one input, but must independently require its own
protected environment, exact AAB authority, upload-key custody, exactly-once
reservation, Play processing receipt, and physical-install proof.
