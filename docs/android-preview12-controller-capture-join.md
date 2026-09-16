# Authenticated request, capture and emission composition

`scripts/android_controller_capture.py` joins existing primitives without a new
wire contract, deployment, trust root, authority flag or activation. It produces
ordinary local facts, **not** a protected signer capability, custody receipt or
release approval. The canonical seven-file handoff is unchanged. Selection of a
real controller/emitter deployment remains pending independent owner/security
admission; this implementation is not that admission.

## Exact sequence

1. The owner independently admits the controller/import closure, durable
   `SQLiteWorkflowChallengeStore`, exact requesting capture job, distinct later
   emission job, origin policy, Docker policy/tool/lock and preserved namespace.
   The expected manifest hash is an independent input, not selected from the
   candidate or emitter response. Unknown inputs must remain a rejection.
2. The owner issues the capture challenge using the existing store. The session
   compares the full actual stored policy and calls the existing cryptographic
   authentication plus atomic consumption itself. It checks freshness immediately
   before invoking `run_builder_capture_handoff`; there is no supplied build or
   authenticator callback. Existing terminal-container, exact inventory, copied
   bytes, request/source/lock and seven-file checks remain in force.
3. A separately admitted custodian supplies a real `PreservedRebuildHandoff` at
   the preselected canonical path. This module does not mount, copy, chown or
   chmod anything to manufacture read-only custody. Every retained raw file hash
   and the lock must match the just-completed capture. The retained object's
   physical inventory, inode/byte and actual root-owned read-only checks stay in
   force before and after emission and verification.
4. After the potentially long build, the owner issues a fresh challenge for the
   independently admitted **different** emission check-run/job in the same exact
   transaction, source, workflow, run and attempt. Only nonce and challenge times
   may differ from its admitted template. The consumed capture challenge is not
   renewed, lengthened or reused: its permanent job slot remains consumed even
   if the build fails or the process loses its response.
5. The session consumes/authenticates that emission challenge, checks fresh
   authorization and calls the explicitly admitted `emitter(retained, job)` once.
   The emitter returns an existing `PinnedFile` bundle. Before callback execution
   the verifier and public trusted root are independently pinned; afterward the
   real `verify_rebuild_handoff_origin` must accept the exact admitted subject and
   policy. All retained bytes and verifier/trust pins are checked afterward,
   including failure paths; job freshness is required through verification.

### Pre-capture subject availability

The existing `prepare_rebuild_handoff` manifest is deterministic from admitted
producer inputs: fixed contract/status/output names and release identity; exact
lock, external request, original producer source graph, eligibility and approval
file hashes; admitted toolchain closure hash and source commit/tree; and the
request's already-known unsigned AAB hash/size. `require_rebuild_match` rejects a
new rebuild differing from that AAB. The original producer source graph is
copied byte-for-byte, not replaced with the rebuild's newly timestamped graph.
The owner can therefore construct the expected manifest from those admitted
values using the existing `prepare_rebuild_handoff` field layout and `_pretty_json`
serialization, then hash those exact bytes before invoking this independent
rebuild. This module requires that independently admitted digest; it provides no
new preview API and does not construct a prospective success receipt.

The origin subject contains no fresh invocation, container, operation-directory
or timestamp fields. Dynamic `capture-complete.json` is separate operation
evidence, outside the seven-file closure and outside this origin subject. A
future change adding dynamic fields to the subject must revisit this admission
sequence, not substitute a candidate-selected digest or placeholder.

## Boundaries that are not solved by composition

- GitHub authentication identifies the requesting jobs. It does not turn a
  controller's local Docker execution into a GitHub-hosted build. The local
  capture continues to state `authenticatedJob: false`; its builder observation
  and this returned composition are not signer isolation authority.
- The emitter is trusted owner-admitted integration code, not authenticated by
  Python's `callable` check. Existing origin verification binds the manifest to
  the admitted GitHub workflow/run/attempt; its certificate does **not** bind the
  callback to a check-run/job ID or prove a new emission rather than return of
  an existing matching bundle. A real admitted emitter must execute in the
  intended freshly authenticated hosted emission job, emit these exact public
  bytes there, and return its real bundle. No such provider adapter, deployment,
  successful emission receipt or job-attribution proof is invented here.
- The durable owner-controlled journal and controller must survive ephemeral
  hosted jobs. Recreating an empty journal per job or reconstructing a session
  from diagnostic facts would lose the existing replay boundary. An emitted or
  consumed-but-interrupted attempt requires reconciliation, never automatic
  retry, challenge renewal, transaction-ID rotation or fallback to old receipts.
- The origin verifier's `github-hosted` policy still describes hosted emission,
  not local builder provenance. Any future protected caller must separately
  satisfy all existing authenticated origin, preserved toolchain, live runtime,
  independent rebuild, ledger reservation and credential checks. No signer,
  upload credential, protected environment, workflow or source lock is enabled.

## Failure and regression coverage

### Hosted OIDC compatibility and exact policy admission

The production verifier permits only the required alg/kid/typ JWT header plus
optional x5t, validated as a canonical base64url-encoded 20-byte SHA-1 certificate
thumbprint ([RFC 7515 section 4.1.7](https://www.rfc-editor.org/rfc/rfc7515#section-4.1.7)).
That metadata is neither a key selector nor a trust root: the unique kid still
selects the RSA n/e key from the fixed TLS-authenticated GitHub JWKS, and the
complete original JWT must pass real RS256 verification. No header URL, embedded
key, certificate chain, critical extension or algorithm override is admitted.

For a direct job emitting job_workflow_ref/job_workflow_sha, the owner must
explicitly admit both existing policy fields equal to workflow_ref/workflow_sha
before issuing the challenge. A None policy still rejects present claims; an
explicit pair requires both exact signed strings. No automatic fallback,
token-derived policy, absent-environment rule or journal-schema change is added.
Existing independently admitted reusable-workflow policies remain supported.
The protected environment, subject, audience, expiry and replay checks are
unchanged. The journal persists the full exact tuple; changing it cannot renew
the same transaction/run-attempt/check-run slot.

Hosted diagnostic run 35116185741, attempt 1, at protected source
3a83ce15bc2c5f2c45e9c0e3b956915ab291b44a observed exact direct self-reference,
a string OIDC check_run_id, numeric job context, and optional string x5t. Its
public report SHA256 is 1b8914e3c3ab7023b2d54f7c3828047cc20bfdfbe8f168cb3e699d172ca4f0e8.
It explicitly reports signatureVerified=false: it motivates compatibility,
not production cryptographic authentication or protected signer readiness.
The diagnostic recorded x5t's type, not its bytes or canonical encoding.
This implementation validates the standard encoding independently. Job ID and
check-run ID happened to coincide there; the verifier still obtains the former
from the exact-attempt API mapping of the latter, without assuming equality.

### Failure boundaries

Each session latches capture and emission before side effects. Invalid inputs,
authentication failure, callback exception, TTL expiry, drift, verifier failure
or lost response cannot replay that action in the session. Durable consumption
also denies a new session reusing the consumed challenge. Existing operation
evidence, copied inputs and consumed rows are retained; this module performs no
cleanup of them and creates no replacement success receipt.

`tests/test_android_controller_capture.py` uses real SQLite, real synthetic-key
RS256 verification, actual bounded seven-file copying and the existing origin
verification subprocess interface. GitHub HTTP replies, Docker execution,
read-only custody metadata and the subprocess's Sigstore cryptography are
explicitly modeled: these are hostile unit/integration fixtures, not production
attestations. Tests cover independent admission, exact jobs/attempts, stored-policy
drift, all seven capture/retained hashes, session swaps, interrupted consumed
builds, reentry/repeat emission, callback/verifier drift and post-action expiry.
