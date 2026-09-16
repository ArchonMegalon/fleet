# Protected-job public intake — first A implementation slice

`scripts/android_protected_capture_intake.py` implements the actual public
transport dependency between the completed local controller and a separately
admitted protected GitHub job. It supplies a fixed ASGI server, concrete HTTPS
client, bounded file transfer, actual root-only read-only bind establishment and
existing origin verification. It creates no listener, GitHub job, Docker
container, credential, signature or signing capability. No workflow, lock,
ledger protocol, policy activation or key custody changes are included.

The production caller of `execute_protected_signer_transaction` and
`reconcile_protected_signer_transaction` remains **pending the second slice**:
the protected-job owner launcher, exact live signer lifecycle and PID-bound
worker. This intake is not a substitute for that caller or its runtime proof.

## Concrete sequence

1. The independently admitted local root controller constructs
   `PublicCaptureExport(completed_rendezvous, ...)` from its actual completed,
   still-live `ControllerRendezvous`. A detached `ControllerEmission`, receipt,
   dictionary or candidate boolean is rejected. The original session, complete
   seven-file retained bytes, lock and verified origin bundle stay fenced.
2. The owner provides an exact **third**, distinct, live GitHub-hosted job policy
   in the same source/workflow/run/attempt/transaction. The intended protected
   environment is an explicit independently reviewed policy input. Its fresh
   private bearer must differ from both existing role bearers and independently
   supplied approval/binary comparison digests. These comparisons are not
   provisioning or a credential-custody proof.
3. Owner-only `arm()` issues a fresh challenge through the actual existing
   SQLite challenge store. Neither HTTP polling nor object reconstruction can
   issue, renew or reset it. The client obtains its audience with `challenge()`;
   the admitted GitHub job obtains genuine OIDC and calls `begin(token)` once.
   The server performs real RS256 authentication and atomic consumption through
   the existing session/store. The acknowledgement grants public transfer only.
4. `PublicCaptureClient.receive(...)` exclusively creates a new private packet,
   streams the seven canonical files in sorted order using at most 1 MiB per
   response, and writes each file exclusively with no symlink following. An
   exact-multiple file ends with a zero-length final chunk. Out-of-order or
   duplicate chunks stop the export; lost replies never authorize resumption.
   The origin bundle is separate public verification material outside the
   closed seven-file directory. The lock, verifier and trust roots are
   independently pinned caller inputs, never downloaded replacement policy.
5. The protected-job **root host**, not the cap-drop signer, establishes one
   real private bind mount of its own newly created seven-file directory.
   `ReadOnlyIntake` requires root/private canonical ancestry, regular single-link
   0400 files and a private source directory. It requests and rechecks
   read-only/nosuid/nodev/noexec/private mount posture, exact mount ID and inode
   identities. `PreservedRebuildHandoff` performs its unchanged full inventory,
   byte, inode, nested read-only and semantic checks. The existing actual origin
   verifier validates the independently expected manifest subject and policy.
6. `CapturedPublicIntake.assert_exact()` combines current local custody with
   correlated checks against the actual still-live source session. It returns
   no serialized provenance, promoted toolchain flags or `AuthenticatedRebuildHandoff`.

The raw fixed routes are POST under
`/android-protected-capture/<admitted-transaction>/`: `challenge`, `submit`,
`check`, `bundle`, and each precomputed `file/<canonical-name>/<chunk-number>`.
There are no caller URLs, paths, commands, arbitrary ranges or upload routes.
The original rendezvous HTTP framing/TLS/exact Host/bearer implementation is
shared privately; its original capture/emission roles are unchanged. Only the
new check request carries an eight-byte sequence; its echoed response is
ephemeral correlation, never an authority receipt. TLS/CA/runtime admission and
the optional exact trusted proxy configuration remain owner responsibilities.

## Lifetime, failure and custody

The strict default remains unchanged: an unarmed `challenge` request stops the
exporter. A local owner may explicitly call
`enable_preparation_wait(maximum_seconds)` once, with an integer 1–1800. Its
fixed monotonic deadline starts at that call, not at each poll. Before arm, the
existing authenticated empty `challenge` route then returns exactly
`200 pending\n`, at most 1,801 times. No new route is added. This records only a
per-export preparation diagnostic; `preparation_observed()` lets the same local
owner inspect it. It is not authenticated job identity, signing authority, a
remote arm command or a durable receipt. It never calls the challenge store.

For this opt-in mode, the owner must see a pending request before independently
calling `enable_protected_job_checks()` and `arm()`. Arm rechecks full custody
and the original preparation deadline before and after store issuance. Expiry,
drift, close, repeated enabling or arm failure stops the export; an issue that
committed before failure remains in the original journal and is not reissued.
After arm, the original fresh audience replaces pending permanently. The
preparation timer never changes challenge, token, transfer or signing TTLs.

Only `client.challenge(preparation_wait_seconds=N)` with integer 1–1800 accepts
pending. Its independent fixed monotonic deadline is checked before and after
each request; it waits at most one second between successful pending responses,
with the same 1,801-request cap. Zero/omission stays strict. Unknown bodies,
404/other status, network errors, lost replies and late audience replies stop
the client without a retry. Neither side renews a session. These are cooperative
call-boundary limits: the owner still needs a whole-process deadline for blocked
DNS, headers, transport or filesystem work. This option does not deploy a
listener or establish private transport or job supervision.

OIDC freshness is required through initial admission. It is not replayed or
renewed while an already admitted transfer runs. A separately admitted monotonic
session limit (default 1,800 seconds, maximum 7,200) and idle limit (default 60,
maximum 120 seconds) apply afterward, with at most 4,096 continuation checks.
These limits do not claim that old job identity is fresh signer authorization.
The second-slice launcher must establish its own required execution admission.
Monotonic and idle checks are cooperative at call boundaries, not a hard
watchdog: synchronous hashing, fsync or an ASGI stall can delay enforcement.
Live public-transfer acknowledgements alone are never signing admission.

Source/controller loss, drift, expiry, an incorrect response, lost reply or
out-of-order operation permanently poison that local client/export. A new
export cannot renew the journal's permanent consumed job slot. Whole-controller
loss cannot reconstruct the in-memory authority from diagnostic files. A future
PID1 worker needs an independent watchdog/fail-stop mechanism: this synchronous
intake API does not claim to kill an executing signer or monitor continuously.

Packets, partial bytes, tombstones and ambiguous mounts are retained on failure.
No recursive cleanup or reuse occurs. The owner may explicitly close a known
`ReadOnlyIntake`; unmount requires the exact original mount ID and inode and
uses neither force nor lazy unmount. A crash between mount creation and identity
capture requires explicit owned-target inspection, not assumed successful cleanup.

Only the transfer is chunk-bounded. Existing canonical validators can allocate
their permitted complete AAB (up to 512 MiB); synchronous hashing/fsync and
origin verification can block the ASGI worker. The existing ten-second HTTP
body/socket checks are not hard deadlines over filesystem stalls or slow
handshake/headers. Deployment needs independently admitted CPU/memory/tasks,
connection/deadline limits and supervision. No resource/TLS/Docker qualification
is inferred from these unit tests.

The successor must keep all four lazy signing-secret reads inside the approved
protected GitHub job, after reservation; ordinary local orchestration never
receives them. It must provision genuine durable recovery/output custody on one
filesystem, not assume `RUNNER_TEMP` is durable. Actual signer/image/lock, public
validation roots, upload-secret provisioning, protected-job transport and
runtime admission remain unactivated inputs. The configured signing lock must
be frozen before its signing-bound independent rebuild.

Tests exercise real client/server composition, SQLite consumption, test-key
RS256, bounded file transfer and existing validators. HTTPS/GitHub replies,
Docker and root/RO syscalls are modeled; the existing origin subprocess stand-in
is noncryptographic. Tests are not production authentication, mounts, a real
AAB recovery proof, signing, publication or Play authorization.
