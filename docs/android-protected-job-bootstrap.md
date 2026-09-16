# Hosted owner bootstrap

`scripts/android_protected_job_bootstrap.py` is an executable composition of the
existing `RecoveryMount`, `PublicCaptureClient`, `ProtectedJobLauncher` and
`ProtectedJobEntrypoint`. It loads expected inputs, calls their real constructors,
then executes the original one-shot job3 path. It is not deployed or activated.
No existing workflow invokes it yet; no workflow/provisioner currently supplies
an admitted deployment digest. A source test is not a hosted execution receipt.

## Admission before Python starts

The protected workflow/provisioner must independently admit the interpreter,
installed dependencies, exact Fleet commit and every imported source byte
**before** executing this module. Root ownership, copying/chowning a candidate
file, a self-computed hash, or successful parsing does not establish authenticity.
The deployment SHA must come from that independently reviewed protected owner,
not from candidate artifacts, request JSON, decoded JWTs or the deployment file
itself. The runtime `code_pins` check is a drift fence, not retroactive admission
of code that has already executed during imports.

Invocation belongs on the actual root GitHub-hosted runner in the already
approved `android-preview12-release-builder` environment, not on the ordinary
local controller, not inside the signer container and not in a candidate shell.
An admitted fixed host step invokes a pinned interpreter with `-I -B`, a fixed
`-c` import bootstrap that inserts **only its already-admitted absolute Fleet
root** into `sys.path`, then imports
`scripts.android_protected_job_bootstrap.main`. This is the same fixed import
placement used for the existing worker, without relying on `PYTHONPATH`, cwd,
user site packages or an operator-selected module/factory. The interpreter's
system dependency paths must also be admitted; `-I` does not qualify them.

Only these CLI arguments are accepted:

```text
--deployment <owner-local absolute public expectations file>
--deployment-sha256 <independently admitted SHA256>
--owner-release-fd <inherited anonymous read-pipe FD, at least 3>
```

This documents the interface, not a runnable deployment/sample live config.
The real fixed host step and its independently pinned invocation/configuration
remain deployment prerequisites. No credentials occur in argv or public JSON.

## Expected inputs, never serialized capabilities

The bounded duplicate-key-rejecting JSON contains exactly:

- `launcher`: the existing launcher configuration fields, execute-only, including
  its exact validation paths and imported Fleet `code_pins`.
- `job_policy`, `artifact_policy`, `runtime_policy`: all fields of the existing
  `WorkflowJobPolicy`, `OriginPolicy`, `RuntimePolicy` dataclasses. Their existing
  nested resource/bind/tmpfs policies are constructed normally. JSON arrays map
  to the documented tuple fields; there is no policy inference or fallback.
- `pins`: exact `{path, sha256}` for `lock`, `docker`, `verifier`, `trusted_root`,
  `intake_ca`, `oidc_ca`. Each CA is a public PEM trust bundle; no ambient CA
  discovery or disabled verification. Existing hostname/certificate/TLS1.2+
  checks remain. Docker and verifier still undergo existing executable checks.
- `persistent`: the real fixed parent path and independently admitted current
  `mount_row_sha256`; `operation_directory`: its fresh exclusive operation path.
- `secret_inputs`: paths for exactly the existing four signing-secret names.
- `transport_inputs`: owner-local file paths `intake_bearer`, `binary_bearer`,
  `oidc_request_url`, `oidc_request_credential`; `base_url`: admitted private TLS
  controller origin; `release_wait_seconds`: bounded 1–1800 local wait.

Dynamic repository/workflow/run/attempt/check-run/environment/transaction/subject
expectations must agree with the **same live** controller and its two distinct
capture/emission jobs. A decoded token or candidate cannot choose these values.
Template challenge fields remain ordinary constructor inputs: only the existing
controller's SQLite store generates the real nonce/times. Bootstrap never issues,
renews or substitutes a challenge or reconstructs an authenticated handoff.

Real root-owned source/tool/authority/code roots, immutable lock, Docker daemon
and image, origin verifier, TLS roots and qualified persistent storage must
already exist. `RecoveryMount` observes the actual mount, not a durability flag.
Its row digest does not qualify physical stable storage, fsync/rename/remount,
private UID mapping or exclusive custody. The source lock remains dormant until
separately admitted configuration exists; this executable does not null-fill or
change it. Current dormant inputs reject before challenge or transport reads.

## Credential and sequencing boundaries

Deployment and private inputs must be canonical root-owned, regular, single-link,
0400/0600 files under immutable root-owned ancestry. Existing launcher admission
additionally requires the four signing files to be 0600 in private 0700 parents,
off NFS. Public executable pins may retain executable modes. Private aliases,
aliases to pinned public files, all six configured validation files (including
distinct-path same-inode file-bind aliases with link count one), and private paths
under **any** runtime bind or derived public/IPC/recovery root reject before
transport reads. Held public/transport FDs and path metadata are checked again
after the owner wait. The four signing files are never opened by this module;
only the existing signed-reservation barrier in the launcher may read them.

Expensive source/tool validation and all constructors finish first. The CLI then
prints the single constant `protected owner prepared; awaiting owner release`.
The owner supervisor, which exclusively holds the anonymous pipe's write end,
coordinates the existing local controller's `enable_protected_job_checks()` and
single `arm()`, **then** sends exactly one byte `1` and closes its write end.
The root-owned read-only anonymous pipe is identity-fenced and boundedly waited.
It is local sequencing only, not an authentication/capability receipt. Do not
prebuffer the byte. No new HTTP readiness endpoint, polling or second challenge
exists: requesting an unarmed challenge fails and closes the existing exporter.

After release, drift fences run and the real entrypoint acquires the genuine
job-injected OIDC token, consumes the original RS256/Jobs-API/SQLite admission,
receives the actual seven-file intake and launches the existing isolated signer.
No signing-file contents are transported to the ordinary local controller.
The existing strict original-facts TTL, root peer/PID/pidfd watchdog, source,
ledger, approval, reservation, attestation and recovery checks are unchanged.
Preparation must finish before arming; hashing/transfer/signing after arming
still consume the original short TTL. No timeout widening, retry or renewal.

The owner must supervise the **whole** host process and retain the actual audit,
operation, recovery and intake evidence. This CLI's pipe wait and existing socket
timeouts are not a hard whole-job deadline. It emits only closed ready/returned/
stopped markers, never raw audit/exception/token data; no traceback-local debug
dumping. Python zeroization is not claimed. Failure closes the live client but
never deletes signed outputs, mounts, intents or recovery. Restart/replay is not
authorized; reconcile through the existing owner recovery path instead.

Focused tests use synthetic files and modeled root/runtime/public-validation
boundaries. They exercise actual policy parsing, file descriptor/path fences,
anonymous pipes, fixed constructor wiring, read ordering and error redaction.
No test invokes a hosted job, real network, signer, mount, Docker or SDK.
