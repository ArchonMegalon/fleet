# Preview12 live signer observation

Status: implementation for independent owner/security review, **not production
admission or activation**. No workflow, trust root, image selection, signing
policy, credential custody, or network permission is changed.

`android_signer_runtime.observe_running_signer(container_id, policy, created,
credential_targets=(...))` fills the live-process observation gap between the
existing CREATED/EXITED Docker observations. It accepts the unchanged
`android_container_runtime.RuntimePolicy` with `process_role="signer"` and its
matching CREATED observation. That profile already requires UID/GID `0:0`,
read-only root, dropped capabilities, no-new-privileges, exact resources,
private namespaces, and network `none`. Selecting that profile grants nothing.

The helper performs only existing bounded Docker GET inspections and bounded
Linux kernel metadata reads. Two bracketed samples bind:

- Exact container/image/configuration, daemon identity, creation/start time,
  running PID, no restart/OOM/paused/dead state, and maximum runtime.
- The actual root-owned PID's start ticks, all UID/GID slots, zero capabilities,
  no-new-privileges, seccomp filter mode, and private PID/mount/network/cgroup
  namespaces. Docker's initial process must be PID 1 in its PID namespace.
- Rootful cgroup-v2 Docker/systemd or Docker/cgroupfs container-ID scope, actual
  CPU ratio, memory maximum, zero swap, PID maximum and process membership.
- Read-only root and kernel mounts, exact declared bind modes and device/inode
  identities, tmpfs mode restrictions, and no unknown, duplicate, propagated,
  or nested mounts beneath the declared roots. Existing standard Docker kernel
  mounts remain the bounded allowlist; every configured READONLY overmount must
  be present and read-only (optional MASKED paths may be absent). Unsupported
  layouts reject.
- Explicit credential-root **metadata only**: declared private root-owned 0700
  directories, without overlapping bind sources or aliased root inodes.

No credential contents or filename inventories are read, and no `/proc` environ,
cmdline, or FD enumeration occurs. The inherited Docker configuration checker
compares the independently admitted non-secret environment; never place secrets
in that policy. Only kernel-provided `/proc/PID/root` and namespace magic links
are followed deliberately; ordinary path-component aliases are rejected.
Permissions must already permit the inspection. Missing kernel fields, denied
reads, unsupported layout, PID reuse or observed drift reject; the helper never
changes permissions or creates/starts/executes/removes a container.

The return value is ordinary local metadata, not a serialized authority
contract or capability. `protected_signer_runtime_verified` is always false.
Two samples do not prove continuous custody, secret absence, authenticated job
execution, durable recovery, or permission to sign. Existing preserved-tree and
transaction checks remain required. In particular, network `none` still cannot
reach the transaction's HTTPS ledger; this helper does not solve or relax that
separate runtime-composition requirement.

## Concrete remaining controller join

Existing executable components already supply these pieces:

1. `android_workflow_identity.authenticate_workflow_origin` authenticates OIDC
   job identity/check-run association and its context with artifact origin;
   `android_workflow_challenge_store.authenticate_and_consume` enforces one-use
   challenge consumption.
2. `android_builder_handoff.run_builder_capture_handoff` owns launch, terminal
   container removal, and the bounded validated seven-file copy, binding its
   container ID and exact manifest/file hashes.
3. `android_artifact_origin.verify_rebuild_handoff_origin` authenticates the
   preserved manifest as the exact attested subject; the unchanged transaction
   and `SignerCredentials` provide the later sign-once and lazy credential seams.

The missing executable join must make the independently admitted controller's
authenticated intended job/transaction actually own that capture invocation and
the emission/attestation of those same captured bytes, with fresh authentication
at action boundaries. Same-run metadata or copied labels do not establish this.
The existing origin policy allows GitHub-hosted execution only; a local Docker
observation does not become a hosted-producer fact by upload. The retained local
first producer and a separately admitted hosted independent rebuilder are
different roles. No second authentication/capture framework or handoff dialect
is needed; neither this observer nor a fabricated provenance boolean supplies
the missing composition.

Tests use modeled daemon/kernel data and synthetic local metadata files only.
They cover actual parser/guard paths and drift/permission failures, not live
Docker qualification, real credentials, signing, or deployment evidence.
