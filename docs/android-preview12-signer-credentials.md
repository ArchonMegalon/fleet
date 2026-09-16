# Preview12 protected signer credential bridge

`scripts/android_preview12_signer_credentials.py` is a job-local adapter for the
existing `execute_protected_signer_transaction` credential callback. It is not a
workflow, secret provider, custody proof, signer activation, or arbitrary-signing
endpoint. No lock, public key, policy, approval, or transaction gate is changed.

An already admitted protected caller supplies a trusted `read_secret(name)`
callback for **already-injected** secrets. There is no ambient environment
fallback, provider/API access, key generation, export, or credential rotation.
Constructing/entering the bridge does not read secrets. Only the transaction's
post-reservation callback retrieves these four names, once, in this order:

| Transaction field | Existing injected secret |
| --- | --- |
| `ownerPrivateKey` | `ANDROID_PREVIEW12_RELEASE_BUILDER_ED25519_PRIVATE_KEY_PKCS8_B64` |
| `keystore` | `ANDROID_PREVIEW12_UPLOAD_KEYSTORE_B64` |
| `storePassword` | `ANDROID_PREVIEW12_KEYSTORE_PASSWORD` |
| `keyPassword` | `ANDROID_PREVIEW12_KEY_PASSWORD` |

The builder value must be canonical Base64 of the provisioning format: exactly
48 DER bytes with the Ed25519 PKCS8 prefix and 32-byte seed. PEM wrapping retains
those exact DER bytes; it does not replace or generate a key. Keystore transport
is canonical Base64, bounded to 1 MiB decoded. Its PKCS12 format and upload
certificate are still validated by the existing signer. Passwords are nonempty
UTF-8, at most 4096 bytes, with no CR, LF, or NUL; whitespace is not stripped.

## Composition and lifetime

Use a new absent child of a canonical, private, signer-controlled job directory:

```python
with SignerCredentials(job_directory / "signer-credentials", read_injected_secret) as credentials:
    result = execute_protected_signer_transaction(
        # Existing authenticated controller inputs remain required.
        # ...
        admit_signing_credentials=credentials,
    )
```

This fragment illustrates the callback lifetime, not a complete executable
controller. The callback does not independently authenticate its reservation or
provenance arguments; only the existing protected transaction authorizes its
call. Never invoke it as a substitute for that transaction. Existing qualified
Android/builder SPKI, upload certificate, independent rebuild, signed-ledger,
sign-once, and final validation gates remain mandatory. Reconciliation uses
`reconcile_protected_signer_transaction`, which has no credential callback and
must not read or sign with these credentials again.

The parent must exist, be owned by the current UID with mode 0700, and have
canonical nonsymlink ancestors owned by root/current UID without group/other
write. A root-owned sticky `/tmp` is allowed only through a current-UID private
0700 child. Keep signed output and the transaction recovery root disjoint from
the credential child. The child must not exist, even as a dangling symlink.
Creation is exclusive; its four absolute-path outputs are regular, single-link,
owner-only 0600 files under a 0700 directory. Reads, file creation, and cleanup
check held directory descriptors and recorded pathname identities. Reentry and
reuse are rejected without re-reading secrets.

Ordinary partial-admission failures clean bridge-owned files. Context exit
removes only the exact recorded files and empty owned child, never recursively
and never signed output/recovery. Replacement, aliases, unexpected children,
or changed identities fail closed; ambiguous resources are preserved and the
fixed diagnostic reports incomplete cleanup. A failed cleanup is not success
and requires operator inspection before any retry. Provider/decoding/cleanup
exceptions are replaced by fixed diagnostics, not secret values or paths.

This requires an exclusively controlled job directory, not protection against
a hostile same-UID process or administrator. Python memory zeroization, erased
storage blocks, and cleanup after process kill/power loss are not guaranteed.
Caller-owned injected values remain caller-owned; this bridge cannot erase them.

## Evidence boundary and tests

Historical public builder-custody proof does not demonstrate fresh access to all
four secrets. This component neither provisions the missing upload credentials
nor establishes local builder custody or a complete protected caller. Dormant
source configuration remains dormant; no real credential was used to test it.

`tests/test_android_preview12_signer_credentials.py` uses synthetic secrets and a
published RFC8032 vector. It checks strict transport, real OpenSSL public-key
identity preservation/rejection, exclusive paths, partial failures, and fenced
cleanup. Existing modeled transaction fixtures execute the actual transaction
and reconciliation functions to verify reservation-before-provider ordering,
early rejection without provider reads, and recovery without re-reading or
re-signing. Those fixture tests model ledger/authority/signing dependencies;
they are not live signing, live custody, or deployment evidence.
