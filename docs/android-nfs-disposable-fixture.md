# Disposable hosted NFS fixture

This manual lane runs the existing BKpapg6L synthetic fixture on one disposable
GitHub-hosted Ubuntu 24.04 x64 VM. It is a backend feasibility experiment, not a
production recovery service, release approval, signing operation, or provisioning
transport. No release gates or locks are changed. Do not run it on the shared
Chummer host or any VM containing production data.

## Before dispatch

The operator must independently review the exact Fleet main commit, confirm the
disposable-VM scope, and pass that commit as `expected_execution_sha`. The workflow
also requires protected Fleet main and checks both the workflow and checkout SHA.
Those checks and the driver's environment checks are accident guards, not remote
attestation of the runner or independent approval of its kernel/tool closure.

The operator rejected any possible fork access to the private recovery-fixture
package. **Do not grant Fleet package access or supply a token workaround.** The
private image remains private and is not an input to this workflow. A separate
local helper is prepared from this pinned public MCR base:

```
mcr.microsoft.com/dotnet/runtime-deps:10.0.10-noble-amd64@sha256:e6508f4bfffe893467e70c54b68a2d28b93fc5d1a69f3de0a3ce69d131ca274e
sha256:9993b46fc643b59f3c9ea5859acfc1b8b6c3859cfe7b5586cfc24455a0ab6dd7
```

The first line is the base manifest; the second is its required config ID. The
reviewed recipe adds 52 fixed public Ubuntu archives (13,482,674 bytes), validates
every size/hash, and installs offline in the original reviewed order. Downloads
reject redirects/proxies and have a 120-second wall-clock alarm. The build runs
network-none with a checked 1 GiB/no-swap/half-CPU cgroup. Recipe hashes are pinned
in the preparation script; the resulting local image ID/rootfs and source hashes
are recorded as same-job observations, not independent release authority.

The job grants only `contents: read`, with no `packages` permission or explicit
token input. Checkout does not persist credentials. The pinned public MCR pull
uses a fresh empty Docker configuration and a cleared environment, with no login.
The fixture uses a different empty Docker configuration, an explicit local Unix
socket and a cleared environment. It starts only the receipt's immutable image
ID. No private package pull, registry push or image archive is permitted.

## Supported profile and bounded execution

Before host mutation, the driver records public OS, kernel, runner-image,
Python/tool hashes and versions, selected Docker isolation fields, image identity,
backing filesystem, NFS module availability, and route/subnet observations.
It requires Ubuntu 24.04/x64, Python 3.12, ext4, cgroup v2, enabled AppArmor,
Docker's builtin seccomp, the exact locally prepared image, available NFS tools/module,
`docker stop --timeout`, and an unused fixed fixture subnet/resource namespace.
Incomplete observations or an unsupported profile fail closed. Recording versions
is not proof of an approved environment; the host tools/kernel are not pinned by
the helper image digest. Package installation is confined to the separate
offline image-preparation step; no dynamic installation or isolation fallback
exists in the fixture itself.

The fixture retains the original narrow AppArmor NFS mount target, private
internal Docker bridge, resource limits, read-only container roots, bounded
tmpfs/output, and fixed capabilities. There are no privileged containers,
host-network containers, published ports, or container Docker-socket mounts.
The default Docker profile may deny Ganesha FSAL operations such as
`open_by_handle_at`; that is a failed experiment with retained evidence, not
permission to broaden the profile. Both controlled stop paths use `--timeout 5`.

The driver has a cooperative 210-second body budget including inventory and a
30-second cleanup budget. Individual commands have deadlines and bounded output.
Preparation has a separate ten-minute limit; the entire job has a fifteen-minute
timeout including checkout and evidence upload, so those budgets can still be
interrupted. Preparation failures retain bounded, JSON-escaped public command
output in the job log; the four-file artifact allowlist is unchanged.
A GitHub job timeout is **not an
independently verified VM destruction guarantee**. Hard NFS I/O can remain stuck
through cancellation and prevent cleanup or evidence upload. Do not claim a clean
host when cleanup is unresolved; retain the failed run and obtain actual VM
termination evidence separately if required.

## What a successful exercise observes

Client A mounts native hard NFSv4.1 with AUTH_SYS, exercises exclusive creation,
final-inode fsync, parent-directory fsync and rename, and deliberately exits 47
after an unacknowledged synthetic record. The server is stopped and restarted
with the same export/state. A new client container and mount reads the exact
records without replay. This is one VM and kernel: not independent-host failover,
power-loss durability, a genuine network partition, authenticated production
storage, or independent-client lock contention. AUTH_SYS is confined to this
isolated synthetic network and is not production authentication.

Only `HOST_INVENTORY.json`, `INTENT.json`, `OBSERVATIONS.json`, and bounded
`SERVER_LOG.json` are eligible for the one-day public artifact. No export, state,
source staging directory, credentials, or private package bytes are uploaded.
Fixture failure observations preserve a fixed stage/category, never exception text or
command arguments. `SERVER_LOG.json` additionally retains only the verified server
identity, bounded status/exit/OOM fields, and a bounded Docker `State.Error` prefix;
if log capture is unavailable it records a fixed marker and empty log. Driver
exception text is never retained. Missing evidence, ambiguous resource creation, cleanup errors,
or failed phase assertions are failures, not success receipts or retry authority.
The driver's exclusive output directory prevents adopting an earlier attempt.

For an unexpected exit from the fixed public-only client start/attach command,
`OBSERVATIONS.json` additionally retains `clientCommandFailures`: the rechecked
owned container identity/state, CLI exit code, and separate stdout/stderr prefixes
of at most 8192 characters each with explicit truncation flags. This output is
JSON-escaped; driver exception strings and output from other failed commands
remain excluded. Container-identity drift refuses diagnostic retention. Clients
still have Docker logging disabled. These diagnostics never satisfy client events
or success, and the original failure is re-raised before bounded cleanup. A CLI
exit code is not substituted for the container's actual exit or persistence proof.

Source tests model host commands and admission; local file fsync/rename tests use
temporary synthetic files only. Preparation-bound tests use in-memory responses
and tiny local Python child processes. They do not download archives, run Docker,
mount NFS, load modules, exercise the hosted kernel or qualify production.
See [the recipe notes](../tests/fixtures/android_nfs_recovery/README.md).
