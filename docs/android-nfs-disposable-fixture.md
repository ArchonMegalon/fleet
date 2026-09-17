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

The helper is pinned to:

```
ghcr.io/archonmegalon/chummer-android-recovery-fixture@sha256:fd912e0e4f6744490e6e2559a98f62db6b87f259d51ea3e5b08994996c3d2a1c
sha256:3062be1e90bdb5a481c8b2f12c207412ac2ba33cd3a531de00b3f101784a68e6
```

The first line is the registry digest; the second is the required image config ID.
The package remains private. At implementation time Fleet Actions read access is
still pending; this workflow does not grant access or make the package public.
An unauthorized pull must fail, not substitute a public image or another token.

The job grants only `contents: read` and `packages: read`; GitHub permissions are
job-scoped, not step-scoped. The token is explicitly exposed only to the fixed
pull step. Checkout does not persist credentials. Login uses a fresh private
Docker config; its credential file and directory are removed before the fixture.
The fixture uses a different empty Docker config, an explicit local Unix socket,
and a cleared environment. Neither containers nor public artifacts receive the
token. No installation, image build, registry push, or image archive occurs.

## Supported profile and bounded execution

Before host mutation, the driver records public OS, kernel, runner-image,
Python/tool hashes and versions, selected Docker isolation fields, image identity,
backing filesystem, NFS module availability, and route/subnet observations.
It requires Ubuntu 24.04/x64, Python 3.12, ext4, cgroup v2, enabled AppArmor,
Docker's builtin seccomp, the pinned preloaded image, available NFS tools/module,
`docker stop --timeout`, and an unused fixed fixture subnet/resource namespace.
Incomplete observations or an unsupported profile fail closed. Recording versions
is not proof of an approved environment; the host tools/kernel are not pinned by
the helper image digest. No dynamic package installs or isolation fallbacks exist.

The fixture retains the original narrow AppArmor NFS mount target, private
internal Docker bridge, resource limits, read-only container roots, bounded
tmpfs/output, and fixed capabilities. There are no privileged containers,
host-network containers, published ports, or container Docker-socket mounts.
The default Docker profile may deny Ganesha FSAL operations such as
`open_by_handle_at`; that is a failed experiment with retained evidence, not
permission to broaden the profile. Both controlled stop paths use `--timeout 5`.

The driver has a cooperative 210-second body budget including inventory and a
30-second cleanup budget. Individual commands have deadlines and bounded output.
The entire job has a five-minute timeout including pull, checkout, and evidence
upload, so those budgets can be interrupted. A GitHub job timeout is **not an
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
Failure observations preserve a fixed stage/category, never exception text or
command arguments. Missing evidence, ambiguous resource creation, cleanup errors,
or failed phase assertions are failures, not success receipts or retry authority.
The driver's exclusive output directory prevents adopting an earlier attempt.

Source tests model host commands and admission; local file fsync/rename tests use
temporary synthetic files only. They do not run Docker, mount NFS, load modules,
exercise the hosted kernel, verify private package access, or qualify production.
