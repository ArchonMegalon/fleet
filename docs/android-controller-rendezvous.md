# Fixed-attempt controller rendezvous — source-only

`scripts/android_controller_rendezvous.py` supplies the concrete transport gap
around `ControllerCaptureSession`: a fixed-route ASGI handler, one action worker,
an actual manifest/bundle exchange emitter, and hosted-client exchanges. It
creates no listener, application instance, workflow, credential, TLS key, tunnel,
database, signing capability or release receipt. There is no CLI or deployment
launcher. Constructing the handler is not independent runtime admission.

## Explicit owner inputs and lifecycle

The independently admitted controller opens the **existing**
`SQLiteWorkflowChallengeStore` with its externally retained controller/database
identities. It supplies the exact immutable capture/emission policies,
`OriginPolicy`, independently determined manifest digest, `CaptureInputs`,
preserved destination, verifier/trust pins, and a fresh private attempt directory.
The operation directory remains absent for the existing builder. The separate
attempt directory and fsynced `no-replay` marker are never removed or reused by
this module, including on partial admission failure. That marker is not a receipt
or authentication format. Journal rollback protection and private durable local
storage remain independently admitted host responsibilities.

Two separately admitted, live GitHub-hosted jobs must belong to the same exact
run/attempt, source and transaction and have distinct check-run/job identities.
The controller needs both complete policies before capture; a workflow that
cannot yet identify the emission job must wait, not guess an ID. The capture job
waits for actual capture completion; the emission job remains running through
origin verification. No display name or claimed logical role replaces identity.

Owner-only calls (none are HTTP routes):

1. Construct `ControllerRendezvous(...)` and `RendezvousApp(controller, ...)`.
   No challenge is issued by construction or an HTTP poll.
2. Call `arm_capture()` immediately before the intended job requests its audience.
   The existing store issues a real fresh challenge. A raw OIDC submission is
   queued once; the worker calls the real session's `capture()` and its existing
   cryptographic authentication, atomic consumption and fixed builder capture.
3. After capture completion, the separately admitted root custodian establishes
   the real preserved namespace and constructs `PreservedRebuildHandoff`.
   Call `arm_emission(retained)` only when the intended second job is ready.
   It checks the exact captured closure, actual root-owned/read-only custody and
   all seven retained files before issuing the fresh emission challenge.
4. Emission submission calls real `session.emit()` with this module's concrete
   emitter. Only after fresh authentication does that callback expose exact
   manifest bytes. It accepts one bounded bundle into an exclusive fixed private
   file and returns an existing `PinnedFile` to the existing origin verifier.
   Freshness is checked before/after expensive custody work and before disclosure
   or bundle acceptance. No externally supplied emitter callback exists.
5. `completed()` returns only the existing ordinary `ControllerEmission` facts.
   `close()` stops admission and wakes a waiting emitter; it does not claim that
   a running Python worker or builder was forcibly terminated.

## Existing private authenticated transport pattern

Reuse the ledger service's verified-TLS/exact-Host/bearer pattern, including its
optional exact local TLS proxy-peer handling, not its credentials or authority.
The owner explicitly provides distinct per-attempt capture and emission bearer
SHA256 values plus the independently admitted approval/binary bearer comparison
digests. All four must differ. The server retains only digests, never discovers
secrets in the environment, and compares digests in constant time. Provisioning
must actually deliver each high-entropy role credential only to its intended
reviewed job; different strings alone do not establish that custody. A transport
bearer cannot authenticate a job, issue/renew a challenge or authorize a release.

All routes are POST under `/android-controller/<exact-transaction-id>/`:

| Role | Suffix | Request body | Response meaning |
| --- | --- | --- | --- |
| capture/emission | `challenge` | Empty | Existing audience, or `pending`; never renewal |
| capture/emission | `submit` | Raw bounded OIDC token | `queued-not-authenticated` only |
| capture/emission | `status` | Empty | Ordinary local diagnostic state |
| emission | `manifest` | Empty | Exact retained manifest, or `pending` |
| emission | `bundle` | Actual Sigstore bundle bytes | `received-not-verified` only |

No policy, filesystem path, URL, command, custody flag, archive, key or arbitrary
operation is accepted from HTTP. Headers require exact HTTPS/Host/path, no query,
browser Origin, redirects, duplicate headers, content encoding or alternate
transfer framing. Content-Type is `application/octet-stream`; Content-Length is
mandatory and exact (zero for empty requests). Authentication precedes body reads.
Headers are limited to 32/16 KiB, OIDC bodies to the existing 32 KiB bound, and
bundles/manifests to 8 MiB (the manifest also respects the admitted lock limit).
Responses are fixed bounded diagnostics or the public manifest, with no-store.

Optional proxy mode requires an explicitly admitted exact local socket peer,
actual origin TLS and only the existing bounded X-Forwarded-For/Proto convention.
Forwarded data never becomes identity. Proxy rewriting and infrastructure access
logs must be disabled. Existing local Docker/chummer.run tunnel hosting can carry
this transport, but this module configures or activates none of it.

## Hosted side and concrete attestation step

Construct `HostedClient` with the exact owner-admitted origin, transaction, role,
raw role credential, expected manifest digest and an explicitly admitted
hostname-verifying `SSLContext` with `CERT_REQUIRED`. The caller independently
admits its CA/interpreter/environment closure; the client does not acquire
credentials, consult proxy configuration or follow redirects.

The reviewed hosted workflow calls `challenge()`, obtains genuine GitHub OIDC
for that exact audience using its admitted Actions OIDC facility, and calls
`submit(token)` once. Polling/status is observation, not renewed authentication.
The emission workflow uses `save_manifest(private_directory)` to create only the
canonical manifest basename with exclusive creation and an exact digest check.
It then runs the independently SHA-pinned attestation action with that single
explicit `subject-path` (no glob or automatic subject discovery), and supplies
the action's actual `bundle-path` as a `PinnedFile` to `submit_bundle()` once.
Those are the existing [actions/attest inputs/outputs](https://github.com/actions/attest).
No attestation action, permission, policy or workflow is selected/activated here.
The attestation describes hosted emission of the manifest, not a GitHub-hosted
AAB build. The certificate still does not itself identify the emission job;
the independently admitted exact workflow and private role transport supply that
integration boundary, not an invented claim in a new envelope.

## Bounds, interruption and unresolved authority

Only one capture/emission action can be submitted at a time, and each is latched
before side effects. HTTP has at most two body readers; its ten-second body-read
deadline is **not a hard whole-request deadline**. Admitted synchronous custody
hashing (including the AAB), JSON parsing, writes and fsync run on the ASGI thread
and can block it. No abandoned offload threads or independent progress during that
work are claimed. The action executor remains separate so the waiting emitter
cannot queue its required upload behind itself. Its condition wait releases the
adapter mutex. The emitter does not repeatedly hash the full AAB while idle.

The hosted client bounds response bytes, rejects duplicate/encoded/framed
responses, and uses socket timeouts plus elapsed-time checks while reading. These
are not a hard global handshake/header deadline against a slow peer. An admitted
server/gateway/supervisor must provide connection lifetimes, quotas, clock,
CPU/memory/tasks and final stop bounds. Filesystem stalls and Python thread
termination are not solved by this library. Unit success does not qualify that
deployment or its performance with a real AAB.

Committed-then-failed issuance, duplicate submissions, expired challenges,
partial bundle writes, lost replies and controller loss never automatically
renew or replay an action. Private evidence and journal rows remain. Opening a
fresh adapter on the same directory fails; a new directory cannot renew the
same permanent journal/job slot. The in-memory session cannot be reconstructed
from status or diagnostic files. Interrupted attempts require explicit existing
evidence reconciliation, not a rotated transaction or a new empty journal.

The intended configured signing lock must be independently frozen **before**
the signing-bound independent rebuild. Changing a dormant lock afterward changes
the handoff binding. This adapter does not construct `AuthenticatedRebuildHandoff`
or call `execute_protected_signer_transaction`; that production custody/capability
caller remains separate unfinished work. The actual disposable ledger proof
demonstrated ledger-client recovery, not full protected AAB recovery. No signing,
publication, Play access or release activation follows from this module.

Tests use real temporary SQLite, real synthetic-key RS256 and actual seven-file
capture copying. HTTPS/hosted job replies, Docker, root-owned RO metadata and the
remote attester are modeled; the existing origin subprocess is explicitly a
noncryptographic stand-in. No test is a production token, attestation, deployment,
SDK build, TLS/Cloudflare qualification or signing capability.
