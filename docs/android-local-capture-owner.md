# Fixed local capture owner

Source implementation only: not deployed, qualified, or a signing permission.
This is the local Docker-owner executable joining existing capture, retained
read-only custody, genuine hosted emission and protected public intake. It
does not run the protected signer or receive any of its four signing secrets.
There is no new wire contract, workflow dispatch, journal provisioning, arm
endpoint, upload action, factory/plugin loader or serialized capability.

## Invocation and independent admission

The admitted local supervisor invokes the fixed module with only
`--deployment /absolute/private/document.json --deployment-sha256 EXACT_SHA256`.
For an isolated invocation, use an independently pinned interpreter with `-I -B`
and a fixed `-c` bootstrap that inserts only the independently admitted Fleet
root and imports `scripts.android_local_capture_owner.main`. No ambient
`PYTHONPATH` or candidate-selected import path is permitted.

The interpreter, dependencies, bootstrap and all pre-validation imports must be
authenticated by protected provisioning **before invocation**. The descriptor
digest comes from that same independent admission, never from an artifact or
adjacent candidate sidecar. Root ownership and the later `code_pins` check are
necessary file controls, not retroactive authentication of code already run.
No sample live descriptor or deployment approval accompanies this source.

The executable requires UID/GID0 in its admitted local owner boundary. The
intended all-local infrastructure remains Docker: a reviewed owner container
needs its actual mount namespace/privileges and restricted Docker-daemon access
admitted separately. This change does not grant privileges or deploy a bare-host
root service. Builder execution remains the separate nonroot existing runtime.

## Closed owner document

The fields below are required; unknown fields, null pins, missing readiness inputs and
the checked-in dormant lock reject before any challenge or TLS-key read.

| Fields | Existing expectation type/purpose |
| --- | --- |
| `fleet_root`, `code_pins` | Root-owned read-only admitted Fleet/import closure, including this executable and its serving imports |
| `pins` | Exact `path`/`sha256` pairs for `lock`, `docker`, `verifier`, `trusted_root`, `tls_certificate` |
| `journal` | Existing `path`, `controller_id`, `database_id`; constructor opens original history, never creates a replacement |
| `capture_policy`, `emission_policy`, `protected_job_policy` | Exact existing `WorkflowJobPolicy` fields, three distinct check runs in one transaction/run/attempt; job3 selects `android-preview12-release-builder` |
| `artifact_policy` | Existing `OriginPolicy`; exact deterministic seven-file manifest subject, admitted separately before capture |
| `runtime_policy` | Existing builder `RuntimePolicy`, including fixed executable command, image, resources, mounts and nonroot user |
| `operation_directory`, `attempt_directory`, `custody_packet` | Distinct initially absent private roots, disjoint from every builder bind and private owner input |
| `output_bind_target`, `handoff_child_name` | Existing exact capture output selection; no arbitrary source-directory import |
| `base_url`, `bearer_sha256` | Admitted HTTPS origin and five distinct capture/emission/intake/approval/binary credential digests; no raw role secrets |
| `tls` | Canonical `bind_address`, private local `key_file`, explicit `trusted_proxy_addresses`; certificate pin above |
| `limits` | Whole-lifecycle `whole_seconds` (1–21600) and shorter `preparation_wait_seconds` (1–1800) |

The only additional optional field is `role_binding`, using the exact admitted
three-role names/templates described in [the binder contract](android-workflow-job-binder.md).
The existing three policies must equal those templates before lookup. Discovery
can replace only their check IDs and occurs before controller construction. The
held deployment and code closure are rechecked afterward. Its at-most20-second
lookup consumes the existing whole-lifecycle budget, never extending it. Without
this field the original static-policy path remains unchanged.

Certificate/role credential selection and actual network/proxy custody remain
independent deployment inputs. Only the explicitly selected local TLS key is
read to serve HTTPS. It is held/fenced and loaded through sealed descriptors;
signing keys and ledger receipt keys are never discovered or read here.
The listener reuses pinned Uvicorn0.34.2/H11 mechanics, TLS1.2 minimum, one worker,
16 connections, disabled access/proxy logging and exact existing ASGI checks.
It never invokes the ledger server's `prepare()` or mounts its database/keys.

## Executed sequence

1. Construct the real `ControllerRendezvous` from admitted policies/pins and the
   original SQLite store. After the TLS listener starts, arm capture once.
2. The genuine hosted capture job supplies its existing OIDC challenge response.
   The real session verifies RS256/Jobs API identity and consumes the journal
   slot before running the existing isolated builder/capture operation.
3. After successful builder removal, obtain the actual live capture object.
   Copy only its seven exact files into fresh `custody_packet/files`, preserving
   the original `captured-handoff` and operation receipts. Recheck bounded bytes,
   inode metadata and digests, finalize0400 files and fsync. `ReadOnlyIntake`
   creates the real private `ro,nosuid,nodev,noexec` bind at `preserved`.
4. Construct the actual `PreservedRebuildHandoff`, recheck capture equality and
   arm emission. Existing hosted emission authenticates once, obtains the exact
   manifest and returns the actual attestation bundle for existing verification.
5. From the same completed, still-live rendezvous construct `PublicCaptureExport`,
   enable bounded preparation wait and install the existing intake ASGI app.
6. Its pending observation is **only scheduling information**. The owner then
   rechecks independent input/code/tool/custody admission, enables original
   protected-job freshness checks and arms job3 once. Actual job3 authentication
   still uses genuine OIDC, exact Jobs API identity and the original SQLite slot.

All three real job/check IDs must exist before owner construction. Independent
workflow provisioning must withhold capture/emission role starts until the
listener is installed, and withhold the hosted job3 supervisor's pipe release
until the export endpoint is installed. The constant listener diagnostics are
not authentication or release receipts. The actual deployment barrier remains
to be admitted; do not substitute blind delays, HTTP-error retries or new routes.

## Failure and operational bounds

No action is replayed after an uncertain failure. Idle polls check metadata,
state and mount identity; full hashing remains at transitions/arm and existing
session use boundaries. The original token TTL is neither extended nor renewed.
On detected drift the executable revokes new HTTP admission before graceful
shutdown. Already executing foreign callbacks are not claimed cancelled.
It stops adapters, joins the worker, then unmounts only its owned exact mount;
original captures, partial copies, journals and attempt evidence are retained.

The admitted outer process/container supervisor must bound the entire lifetime
and cleanup: synchronous hashing, syscalls, server shutdown and thread/executor
joins are not Python hard deadlines. Cleanup uncertainty forbids automatic retry.
Exit0 on an orderly listener stop is **not signing completion**; only the existing
protected transaction's actual retained receipts can establish its outcome.

Tests use real files, SQLite/test-key RS256 and existing capture/ASGI/validation
methods, with explicit modeled root/mount/Docker/GitHub/listener boundaries and
the existing non-cryptographic attester stand-in. They do not qualify deployment.
