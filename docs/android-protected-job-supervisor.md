# Root host-step supervisor

`scripts/android_protected_job_supervisor.py` is the fixed executable parent of
the existing protected job bootstrap. It runs both sides of one anonymous pipe
in **one root host step** of the approved GitHub-hosted job. No FD crosses GitHub
steps. This source change deploys no workflow, controller, mount or credential.

The closed CLI accepts `--deployment`, `--deployment-sha256`,
`--interpreter-sha256` and `--maximum-seconds` (1–86400). These are owner-admitted
public inputs, not a supplied live configuration. The executable uses its current
interpreter and a fixed isolated `-I -B -c` import of
`scripts.android_protected_job_bootstrap.main`; no command/module factory exists.
An admitted final interpreter symlink preserves a qualified venv; both the link
and the real executable are fenced. The independently expected hash covers the
real interpreter bytes, not the symlink text.

The owner must admit this supervisor, interpreter, standard library, installed
dependencies, dynamic loaders and exact Fleet import closure **before** running
it. The deployment digest is independently selected by protected provisioning,
not calculated from candidate JSON or a self-asserted success receipt. This
supervisor checks the deployment and all existing `launcher.code_pins` before
spawn, rejects omitted literal Fleet imports and cached bytecode, and retains
FD/path identities. These checks do not retroactively authenticate already
executed Python or independently select deployment authority.

## Sequence and remote prerequisite

1. The deployer has already installed the real reachable `PublicCaptureApp` from
   the **completed, still-live** local controller. That owner enables bounded
   preparation wait before serving this attempt, and protected signing checks
   before arming. It may perform its full independent recheck and enable signing
   checks after observing the pending request; preparation is not arm authority.
2. In the same protected host step, run this supervisor as actual UID/GID 0.
   Its deployment must explicitly select `preparation_wait_seconds` in 1–1800;
   the default strict/no-wait mode is not accepted here.
3. The parent creates a root-owned anonymous pipe, spawns exactly one admitted
   bootstrap with only its read end, and waits for the exact constant READY line.
   Only then it writes one byte `1`, closes its writer, and never releases again.
4. The bootstrap performs its existing rechecks, calls the existing pending
   challenge exchange, obtains genuine OIDC only after the local owner arms once,
   and continues through unchanged RS256/Jobs API/SQLite and signer admission.
   The local owner observes preparation as diagnostic timing, not authentication.
5. The parent requires the exact returned marker and exit zero. They report only
   that the child returned; the existing retained audit remains the result.

READY does **not** prove the remote exporter exists or is reachable. No readiness
HTTP probe is added. A network error or missing route is terminal, not pending
and not retryable. Actual orchestration must establish invocation timing before
the pipe is released; this executable cannot discover that authority remotely.

## Required hosted setup

All three distinct live job/check identities must exist in the same workflow
run/attempt before capture. The future manual workflow starts them concurrently,
with no serial `needs` chain that postpones the next identity. Existing capture
and emission CLI phases remain in their own admitted jobs; the real pinned
attestation action stays between emission prepare and submit. Do not reuse the
old native-v3 signer workflow or an artifact-name-based authority shortcut.

The real root host must retain its Docker daemon visibility and mount/PID/time
relationships. Public Fleet/source/tool/authority roots are independently
admitted and read-only. Recovery is one qualified private ext4/xfs/nfs4 parent,
with recovery/outputs/operations on the same filesystem and its independently
admitted current mount-row hash. Requests/responses/socket directories are
private, outside recovery; the fresh intake packet does not preexist. Existing
intake code creates only its own seven-file read-only bind. No nested private
mount namespace may hide these mounts from the host Docker daemon.

The exact signer policy, image/config IDs, Docker/verifier/trust pins and all
existing deployment paths are required. Four signing files remain root-private,
off NFS and outside every runtime bind; this supervisor never opens them. Only
the existing post-reservation launcher reads them. Transport files stay separate.
No ambient credential variables are inherited by the child.

The workflow must additionally enforce an admitted whole-job cgroup CPU/memory/
task limit, no swap, final lifetime and disk budget; container resource policy
does not limit its host supervisor. Production values need actual qualification,
not reuse of small synthetic-test budgets. The monotonic child deadline covers
preparation, release, execution and waiting. SIGTERM/SIGINT trigger bounded
cleanup; SIGKILL and uninterruptible host filesystem stalls require the outer
supervisor. Container lifecycle remains owned by the existing launcher/watchdog,
not by this parent process-group cleanup.

Output is bounded and never relayed raw. Unknown, repeated, incomplete or
out-of-order markers, any stderr, nonzero exit, timeout and short pipe writes
fail closed. The parent fences its original session leader/start ticks, retains
the unreaped child PID through its final group signal and uses a pidfd for exit
observation. Cancellation during spawn is deferred until the original child is
tracked, then cleaned up without pipe release. It never adopts another PID, retries launch, rotates an attempt,
deletes evidence or unmounts anything. Escaped process sessions require the
external job cgroup. Failure requires retained-evidence reconciliation.

Tests use real benign synthetic child programs, pipes and process groups with
root file/process identity explicitly modeled. They do not run the actual
bootstrap, controller, OIDC, network, Docker, SDK, attester or signing path.
