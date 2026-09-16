# Binary ledger bridge: source-only composition

This adapter does not deploy or admit a controller, alter current policy JSON,
enable signing, or claim release provenance. The existing four ledger operations,
HTTPS service, signed receipts, uniqueness, journal and reconciliation remain the
authority. Local exchange files are neither a ledger nor a new receipt dialect.

## Explicit binary-only custody

The reviewed source variant
`owner_admitted_binary_ledger_controller_only` is accepted only by explicit
binary-lane validation. Default policy validation, the ordinary client, the
approval service/server and the comparison approval policy reject it. A string
does not establish custody: immutable controller/image/code admission, actual
mount/network observation, separate approval/binary database, origin, bearer and
receipt-key custody remain owner requirements. No current policy or pin changes.

`load_reviewed_ledger(..., bridge_transport=...)` still checks immutable ancestry,
adapter and both policy hashes, wrapper and cross-lane separation. This mode
rejects either approval or binary bearer in the supplied signer environment and
requires an explicit callback. The old mode rejects a bridge callback. Execution
and reconciliation accept `ledger_bridge_transport` and pass it through this
same loader; there is no ambient fallback or fake token.

## Minimal owner composition

1. Independently admit the immutable binary policy, its comparison approval
   policy and exact one transaction subject. Bind `policy_sha256` to the actual
   outer binary policy bytes, not just its nested wire policy. The subject
   includes the attempt nonce, artifact identity/digests, source tree and policy.
2. Provision two **fresh empty, distinct private directories**. Construct both
   `ControllerBroker` and `SignerTransport` before publishing the first request.
   Each receives the same admitted policy, subject and policy digest. Broker gets
   only the binary bearer and verified HTTPS transport, never signing keys.
3. Mount requests RW and responses RO into the network-none signer as separate
   explicitly admitted binds. Do not put these in immutable source, credential,
   handoff or recovery directories. The controller has the corresponding local
   endpoints and calls `serve_once()` from its bounded supervised worker loop.
4. Supply the signer transport to the existing execute/reconcile function via
   `ledger_bridge_transport`. The signer verifies the actual service's signed
   responses with the unchanged client, including reservation/lease/revision
   continuity and exact public committed bytes. Reserve and durable journaling
   still precede credential admission. No candidate code is introduced.

Both endpoints require the **same real UID** (`os.getuid()`), directory mode 0700 and file
mode 0600. The current UID0, ALL-capabilities-dropped signer therefore requires a
separately admitted UID0 broker process/container, with network and ledger bearer
but no signing keys. A UID1000 host controller cannot directly operate these
boxes. This source does not provision that root process, weaken permissions or
grant ptrace/capabilities. Different-UID sharing is not implemented. The signer
must actually have response RO/request RW mounts; these Python classes cannot
prove mount isolation or protection against an admitted host administrator.

The broker derives the exact HTTPS origin/path and authorization header from
its admitted policy, not IPC. No caller URL/header enters the exchange. Only the
canonical existing wire request for the one exact subject and four operations
is accepted. TLS verification/no-redirect uses the existing transport. Its
process environment, proxy settings, DNS/TLS routing and egress restrictions
must be independently controlled; callback tests do not establish them.

## Bounds and failure behavior

Each session allows at most 64 exchanges. Each body is an owner-only, stable,
single-link regular file, published without replacement before an exclusive
zero-byte readiness marker. Readers ignore incomplete bodies and reject unsafe
ready files. Independent random exchange names plus the complete request-byte
digest bind responses; the existing signed request/receipt bindings remain
mandatory. Request, response, directory-entry and polling time bounds are fixed.
Responses expose only bounded status, content type/length and raw body bytes.
These transport fields carry no release authority of their own.

The broker attempts each published request at most once. An ambiguous HTTPS
failure produces no invented response; the signer times out and the existing
client performs its bounded retry/status/commit replay. A controller supervisor
must bound worker lifetime and decide whether to continue after a rejected
exchange; `serve_once()` does not create a background service. No callback can
promise a hostile custom transport terminates; production uses the admitted
bounded HTTPS implementation and supervisor.

Controller/process loss requires a fresh mailbox pair for the **same** durable
subject and journal. Never reopen old boxes as a ledger or rerun a consumed
signing operation. Use reconciliation without credentials after the existing
attested/commit-intent fence; pre-attestation quarantine remains non-reconcilable.
Retain or remove exchange files only under an explicit owner retention policy;
the adapter never cleans journals, resets databases or deletes mailbox evidence.

Tests use private temporary files, modeled HTTPS and existing public RFC receipt
fixtures. They exercise the actual hash-bound loader, client signature/replay
checks and execute/reconcile bridge forwarding. Signing and Android qualification
in transaction fixtures remain modeled. No Docker, mounted endpoint isolation,
production credentials, deployment or live release admission is claimed.
