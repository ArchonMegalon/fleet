# PR11 persistent store — dormant service groundwork

`scripts/android_preview12_approval_ledger_store.py` implements persistent
state for the **existing** PR11 request/receipt contract. It does not implement
HTTP, TLS, authentication, authorization, Ed25519 signing, secret storage, a
workflow, a CLI, or deployment activation. Client and policy bytes are unchanged.

## Storage and invocation boundary

An independently reviewed service provisioner explicitly calls
`SQLiteApprovalLedgerStore.create(path, service_identity=..., database_id=...)`
once, in an existing canonical owner-only directory on durable local storage.
The database ID is a separately retained public 64-hex pin, not a credential.
Ordinary construction opens **existing** storage only and requires both pins;
missing, replaced, wrong-identity, non-private and symlinked paths fail closed.
Creation never overwrites an existing database. Failed creation is quarantined,
not silently deleted or retried against fresh empty history.

The service calls `process(request_bytes, now=trusted_utc_clock)` and receives
canonical **unsigned** PR11 receipt bytes after the database transaction commits.
InvalidRequest, Conflict, NotFound and StoreUnavailable are internal outcomes;
a future authenticated transport must map them without leaking internals.
Its signing boundary signs those exact bytes and wraps the existing PR11
response. Persisted reserve-receipt hashes are prepared-for-issue bindings;
this store cannot prove the external signer actually issued a signature.

The required receipt fields `durabilityClass=external_durable` and
`exactlyOnce=true` are unsigned protocol material, not a claim that an external
service is deployed. Exactly-once here means immutable terminal ledger state,
**not** proof that a signer executed once. Multiple authorized callers can
observe one reserved receipt. Protected signer scheduling/credential admission
and the existing sign-once composition remain separate requirements.

## Durable semantics

- SQLite `synchronous=FULL`, DELETE journaling and `BEGIN IMMEDIATE` serialize
  independent request processes on one host. Acknowledgement follows commit.
- Artifact ID and approval nonce are independently UNIQUE across canonical
  subjects. Reserved, committed, aborted and expired rows are never deleted or
  reused; terminal states and original identity/lease columns are immutable.
- Commit/abort require a persisted issued-reserve digest, reservation ID and
  revision. Original revision-one bindings remain usable for exact terminal
  replay after a lost response; fabricated or unrelated bindings do not.
- Committed approval is an exact opaque byte string (up to PR11's 32 KiB cap),
  not a parsed/reformatted JSON value. The existing Android approval validator
  retains semantic/signature responsibility. Status and reserve replay recover
  the exact committed bytes without generating another approval signature.
- The original lease is always 900 seconds. Expiry is terminal `lease_expired`
  at that original deadline, even when observed later; it never creates another
  reservation or signing opportunity. Lazy expiry may be persisted by status.

## Operational prerequisites not supplied by this change

Use one external service's persistent **local** filesystem with real fsync
support and multiple connections/processes on that same host. Do not use NFS,
multi-host shared-file deployment, ephemeral runner databases, or SQLite memory
URIs. Provision storage quota, protected backups and fail-closed disaster recovery.
Restoring an older backup or repointing to a fresh database would lose permanent
uniqueness; an administrator must not do either as automatic recovery. File and
database pins do not defend against a privileged actor replacing the full trust
and storage boundary. Protect the parent directory, database, service identity,
receipt-signing key and clock in the real deployment.

The bootstrap attempt/key-slot store is **not** implemented by this protocol.
Its generation fences must never expire into another attempt, and a database
reservation cannot prove conditional/exclusive custody of a GitHub secret.
Do not repurpose the approval lease as a key-generation or secret-write permit.

Tests use real temporary on-disk databases, separate processes/connections,
restart, unacknowledged commit replay, crash-before-commit recovery and hostile
requests. They do not establish hosted service custody or publication authority.
