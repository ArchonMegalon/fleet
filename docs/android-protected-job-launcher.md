# Protected GitHub-job transaction owner

Source implementation, **not deployed or production-admitted**. No workflow,
lock, policy, provider, secret or release permission changes accompany it.
The existing protected GitHub environment `android-preview12-release-builder`
retains the Ed25519 key. Neither the ordinary local build controller nor a remote
signing oracle receives that key. Upload-secret provisioning remains separate.

## Concrete call sequence

The independently admitted protected-job host runs
`android_protected_job_launcher.ProtectedJobLauncher`. Before job3's challenge
is armed, the owner supplies the exact `PublicCaptureClient`, immutable public
configuration, root-owned read-only Fleet/import pins and validation roots,
reviewed Docker `RuntimePolicy`/binary/image, and actual `RecoveryMount`.
Its constructor performs key-free preserved validation. The policy entrypoint
is `/usr/bin/python3`, command initially empty; the launcher supplies the fixed
isolated `-I -B -S` worker bootstrap and hash-bound configuration itself.
The environment is exactly the retained SDK111 public profile; unknown names,
loader/Python injection and credential environment forwarding reject before
intent creation. Inherited OCI labels still require exact owner admission.

The original local controller owner calls
`PublicCaptureExport.enable_protected_job_checks()` **before** `arm()`. Existing
job-owned OIDC acquisition, `client.challenge()`, `begin(token)` and
`receive(packet, lock=..., verifier=..., trusted_root=...)` perform the real
single job3 consumption and closed seven-file intake. The host then calls
`launcher.launch(actual_intake)`, not a dictionary of provenance claims.
The intake's connection must be the exact client admitted before the challenge.

`fresh-check` is distinct from the public transfer echo. It rereads the original
consumed SQLite row and checks exact policy, token/JTI hashes and authenticated
facts against the still-live completed controller/session, then invokes the
existing `_match`. No challenge/token is reissued, consumed twice or renewed.
Its eight-byte request sequence has a twelve-byte response: correlated sequence
plus conservatively rounded remaining validity. The client anchors monotonic
time **before** custody checks and HTTP, subtracting all elapsed time. This is
ephemeral control state, never a reusable authority receipt. Public transfer may
outlive OIDC expiry; protected signing may not.

The host records exclusive durable intent and exact created CID before starting
one network-none, UID0, all-capabilities-dropped, read-only-root signer. It owns
the fixed private AF_UNIX endpoint, verifies actual CREATED/live observations,
SO_PEERCRED host PID/UID/GID, kernel start ticks, pidfd and same time namespace.
The worker sees the outer host peer PID as zero in its private PID namespace;
it does not invent a visible host PID. Socket/root custody remains mandatory.
These samples alone are not continuous proof: the trusted owner controls the
runtime, code, daemon and input writers, and the live fail-stop session supplies
the ongoing constraint. Hostile trusted root is outside that boundary.

The actual PID1 entrypoint constructs `PreservedProtectedValidation`, retained
handoff and measured closure, and invokes the EXISTING execute or reconcile
transaction. The in-memory authenticated handoff is constructed only inside
that concrete session, never from HTTP booleans or an observer dataclass.
All canonical source/tool/eligibility/receipt/attestation validation remains.
Every real transaction-runner command and lazy credential boundary obtains a
fresh owner check, enforcing the conservative deadline immediately before use.
A heartbeat and independent deadline watchdog terminate PID1 on loss/expiry.

## Credentials, ledger and recovery

Execute admits exactly four explicit job-local private regular secret input
files. No environment discovery, provider lookup or credential input is mounted
into the worker. The host validates the real signed reservation in the existing
durable journal before reading a secret, in the fixed one-shot order. Existing
`SignerCredentials` creates transient private Paths in the worker's private
tmpfs only after the transaction's reservation barrier. The worker sets umask
077. Python memory zeroization and surviving SIGKILL cleanup are not claimed.
Reconcile accepts no secret map and has no credential construction/read path.

The unchanged binary ledger bridge gives the signer request-RW/response-RO
private mounts. The job host alone owns the explicit binary bearer and verified
HTTPS transport. It reuses existing four operations, subject, policy separation,
signed responses, reservation and commit recovery. Broker admission is revoked
before blocking container cleanup. Already-sent ambiguous operations are
retained for reconciliation; no queued operation is newly admitted afterward.
Proxy/TLS/host networking custody must be independently admitted in deployment.

One actual persistent parent mount contains `recovery/`, `outputs/` and
`operations/`, and enters the signer through ONE bind. Nested mounts reject.
The exact admitted mountinfo row, private root identity and supported filesystem
are checked; **these metadata checks do not prove physical durability**. Owner
qualification must prove durable backing, authenticated scoped access, UID0
mapping/exclusive custody, fsync and atomic rename, and replacement-host remount
at the same canonical paths. `RUNNER_TEMP`, an ephemeral named volume or a path
hash is not that prerequisite. Keys and SQLite are never placed on this backend.
No backend has been provisioned by this change.

Lost create/start/control replies never authorize another launch. Retain intent,
CID, intake, socket and journal evidence for exact owner cleanup.
Cleanup independently reinspects the exact CID, generated name, image and labels
on the admitted daemon before stop and again before removal. An ambiguous or
foreign identity retains evidence without stopping or deleting that container.
The signed-AAB file/directory fsync barrier precedes sidecar/attestation/commit. Existing partial
post-key evidence stays quarantined; reconcile never re-signs. A missing local
reservation after an ambiguous reserve is not permission to execute again.
Whole original-controller loss cannot be reconstructed from JSON or snapshots.
This caller does not renew expired job3 authority for later reconciliation;
retained bytes alone never authorize a fresh session or another execute.

## Remaining runtime qualifications

No claim is made that transfer and signing fit the original 300-second default
job3 budget. The worker reconstructs preserved validation and measures closure;
the unchanged transaction then performs four additional complete validation
passes, including eight repositories and three tool trees. Pre-staging is not
a cache bypass. Measure this path; expiry fails closed without widening TTL.
Synchronous hashes, filesystem calls and host scheduling are not hard real-time
deadlines; the independent PID1 watchdog and exact runtime must be qualified.

The tests use real RS256/SQLite, strict framing/socketpairs, files and existing
transaction control flow with explicitly modeled TLS, kernel, Docker and signing
boundaries. Ordinary isolated Python subprocesses genuinely exit70 on timeout
or peer loss; this does **not** prove PID1 namespace child termination. A separately
reviewed inert existing-image test must prove that termination, actual socket
peer semantics, mounts, resource limits and owner cleanup before activation.
Production durable-backend admission, exact protected workflow/checkrun/policies,
current qualified Android graph, configured lock frozen BEFORE independent
rebuild, actual source/tool/runtime custody and all four job secrets remain
required. This source does not dispatch a workflow, sign, publish or authorize
Play upload.
