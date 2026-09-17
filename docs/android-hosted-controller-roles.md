# Fixed hosted capture and emission steps

`scripts/android_hosted_controller_roles.py` supplies the missing hosted callers
of the existing `HostedClient`. It does not deploy a workflow/controller, choose
an attester, publish an attestation or establish signing authority. The ordinary
local Docker build is never described as a GitHub-hosted build.

The fixed CLI has three phases:

```text
capture          --deployment PATH --deployment-sha256 SHA256
emission-prepare --deployment PATH --deployment-sha256 SHA256
emission-submit  --deployment PATH --deployment-sha256 SHA256 --bundle ACTION_OUTPUT_PATH
```

These are interface descriptions, not a supplied live configuration. The owner
must admit exact source/import/dependency/interpreter bytes before invoking the
script. The fixed admitted phase caller below keeps source admission ahead of
role imports; do not use cwd/PYTHONPATH or a dynamic command/module factory.
The configuration digest must come independently from protected provisioning,
never from candidate JSON, local claims, a self-hash or chown-as-authentication.

## Held pre-import source admission

`android_hosted_source_admission.admit()` is a stdlib-only, callable source lease,
not a provisioner, runtime attestation or role executor. Its keyword inputs are
`profile`, `profile_sha256`, `context`, `context_sha256`, and an explicitly
selected `hosted_root`. The original four-document profile/context formats are
unchanged. It selects exactly `protected.launcher.code_pins`; overlapping
`owner.code_pins` entries must agree. It never merges the maps or infers the
hosted source root from either role's configured local path. Provisioning must
independently bind that root and select a complete map for the reviewed source.

Before target imports, the lease captures and hashes the two documents and the
bounded Fleet source closure through held no-follow descriptors. It rejects
source aliases, unsafe ancestry/modes, symlinks, bytecode caches, same-stem package
shadows, ambient Fleet namespaces and omitted literal imports, including the
known bare approval-ledger fallback. Its one-shot `import_targets()` returns
only `materializer`, `stager`, and `hosted` modules for the three fixed existing
entrypoints. A scoped loader executes captured bytes, not a reopened pathname;
unknown `scripts` imports fail closed. It checks actual module origins, parent
bindings and loader identities. It does not call any returned role function.

The trusted caller keeps the context open and calls `lease.recheck()` immediately
before and after each existing materializer/stager/role call. The original
consumer parsers still validate full policy; the source gate's preliminary JSON
checks do not replace them. On exit, it closes held descriptors and removes only
the imports it created. Failed imports poison that lease, including caught
failures; partial effects are not rolled back or retried. No files are changed.

Initial admission of this helper/bootstrap, Python, stdlib, installed packages,
`.pth`/site behavior and native libraries must happen **before this API runs**.
`-I -B` and exact source hashes cannot retroactively supply that authority. A cold
fixed bootstrap may load the already-admitted helper outside the `scripts`
namespace; normal package import is also accepted only for the exact pinned
helper and its otherwise empty matching namespace. No arbitrary module/command
selector, new policy document, workflow or deployment authority is provided.

## Fixed phase caller

`android_hosted_phase_caller.py` composes the existing source lease, materializer,
request-input stager and hosted role functions. The caller itself, its initial
Python/stdlib/dependencies and native loaders must already be independently
admitted. Execute those fixed caller bytes with `-I -B` as `__main__`, or load
them under the fixed private `_chummer_hosted_phase_caller` bootstrap identity.
Do **not** import `scripts.android_hosted_phase_caller` first: the resulting
ambient Fleet namespace correctly fails admission. This is not permission to
execute an unverified checkout file or a workflow-input-selected bootstrap.

Its closed interface takes one of `capture`, `emission-prepare`, or
`emission-submit`; `--hosted-root`; independently admitted `--helper-sha256`;
and existing `--profile`, `--context`, `--deployment` paths with their respective
`--*-sha256` values. Only submit takes `--bundle ACTION_OUTPUT_PATH`. The helper
hash binds exactly `HOSTED_ROOT/scripts/android_hosted_source_admission.py`.
The caller captures its bounded bytes through a held no-follow descriptor and
verifies hash/name/parent identity before execution under one fixed private
module name. It never selects arbitrary helper paths or imports it by lookup.
No candidate-computed digest substitutes for independent input selection.

Within the source lease, it holds all three documents and checks that the
retained deployment equals the real materializer's rendered bytes. Capture and
emission-prepare then stage the two explicitly injected request inputs and call
the existing role. Submit cold-re-admits and checks the same deployment but
never materializes, stages, or reads OIDC environment values again; it passes
the actual action bundle path to the original submit function. Fences surround
each call, and the held helper/documents remain checked through completion.
One invocation per process is allowed. Failure keeps existing effects and
original no-replay markers; it never retries, erases files or emits an authority
receipt. Diagnostics are constants. Outer resource/deadline admission remains
necessary, including bounds for filesystem stalls. This adds no live workflow,
controller, bearer delivery, protected credential, private route or recovery
storage. The root protected supervisor remains separate and unchanged.

## Fixed request-input staging

`scripts/android_hosted_input_stager.py` supplies one bounded preparation step,
not a hosted provisioner or role executor. Its closed CLI accepts only `--role
capture|emission`, plus `--profile`, `--context`, `--deployment` and each one's
independently admitted `--*-sha256`. The deployment must equal the actual
`android_deployment_materializer.render()` output byte-for-byte. The existing
configured role bearer must already be delivered; its bytes must match the
admitted owner document's `bearer_sha256` for that exact role. It is not copied.

After public/input/CA alias and custody preflight, the stager reads only
`ACTIONS_ID_TOKEN_REQUEST_URL` and `ACTIONS_ID_TOKEN_REQUEST_TOKEN` from the
explicit job injection. It validates the existing endpoint/ASCII/bounds rules
and distinct bearer/request credential, then exclusively writes those two
configured private files. No directories or credentials are generated. Profile
and context may be non-group/world-writable public files; deployment, existing
bearer and CA files use the caller's existing 0600 custody. All immediate input
and output parents are already current-user 0700 under accepted ancestry.

Both destinations must be fresh and distinct, outside the role attempt and
emission action-output roots. Held input and parent bindings are rechecked
around writes; completed outputs remain held through final readback. Failure
preserves partial files and requires reconciliation, never overwrite, deletion
or automatic retry. The CLI prints only constants, not credential bytes,
private digests or paths. Python zeroization is not claimed. An independently
admitted outer deadline must also cover filesystem stalls.

Interpreter/source/dependency admission still precedes importing this helper.
It does not establish that supplied environment values are genuine GitHub
identity, request an OIDC token, call the owner/client, start a role, or supply
protected signing credentials, storage, private routing or deployment. The
original OIDC/Jobs API/journal authentication remains unchanged. Disposable
tests use the real renderer, writer and `_Input` reader; operational callbacks
are trapped. The source-test CI separately includes this dedicated suite; no
operational workflow is added by this preparation step.

## Actual sequence across hosted steps

1. The capture job calls `capture`. The executable polls only the existing
   `challenge()` pending response until the owner arms capture. It requests
   genuine job OIDC through the existing bounded TLS helper with that exact
   audience, then calls `submit(token)` once and waits for actual capture
   completion. Status is a diagnostic observation, not an authenticated lease.
2. In the **distinct admitted emission job in the same invocation**, call
   `emission-prepare`. It waits for the existing emission challenge, acquires and
   submits genuine OIDC once, then calls `save_manifest()` to retain exactly
   `FLEET_ANDROID_PREVIEW12_REBUILD_HANDOFF.generated.json` with the independently
   expected SHA256. The controller's real session stays alive after this process
   returns; no client capability is serialized.
3. The separately reviewed immutable official attestation action runs as its own
   step in that **same emission job**, using only that exact manifest path as
   `subject-path`, not a glob, digest-only input or automatic subject discovery.
   The selected custom predicate must truthfully describe manifest emission, not
   hosted AAB compilation. Its predicate URI/content and expected source/workflow
   identities must match the independently admitted origin policy. Disable
   registry/storage writes and summary output where intended; ordinary
   attestation publication remains a separately authorized real operation.
4. After the action succeeds, call `emission-submit` with its **actual**
   `bundle-path` output as `--bundle`. A workflow passes this through a quoted
   environment variable/argv, never interpolated into executable shell syntax.
   This phase calls neither `challenge()`, OIDC acquisition nor `submit(token)`;
   it reads no OIDC request URL/credential bytes. It sends the actual bounded
   bundle with `submit_bundle()` once and waits for the original controller's
   complete state. Only the server's unchanged signature/origin/subject/freshness
   checks decide acceptance. A local marker or successful callback cannot do so.

The previously audited candidate is official
[`actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6`](https://github.com/actions/attest/blob/1e69f48acb82d1966a394da916b4c1698aa569d6/action.yml).
Its Node24 action creates a random child of `RUNNER_TEMP`, writes the actual
bundle, and exposes `bundle-path` via action output; see its
[fixed source](https://github.com/actions/attest/blob/1e69f48acb82d1966a394da916b4c1698aa569d6/src/main.ts).
It is not a deployed/policy-selected attester here. No attempt is made to pass
an anonymous file descriptor between GitHub action steps, run its JavaScript
outside the admitted action runtime, or invent a successful emission receipt.

## Owner expectations and custody

The bounded, duplicate-key-rejecting public JSON has these required fields:

- `role`: capture or emission; `job_policy` and `artifact_policy`: all fields of
  the existing dataclasses, JSON arrays for tuple fields. The server owns the
  exact same-run/distinct-job admission. Capture matches shared source/context;
  it need not claim the emission job's reusable workflow identity.
- `base_url`: the existing private HTTPS controller origin; `pins`: public PEM
  `controller_ca` and `oidc_ca`, each with absolute `path` and admitted `sha256`.
- `transport_inputs`: private absolute files `role_bearer`, `oidc_request_url`,
  `oidc_request_credential`, explicitly provisioned for this job. No ambient
  credential discovery, argv tokens or private builder/upload key input exists.
- `attempt_directory`: fresh private role-local path, preserved on failures;
  `attestation_output_root`: the actual admitted runner temporary root for
  emission, null for capture; `deadline_seconds`: 1–10800 per phase, chosen by
  the owner and bounded by independent whole-job supervision.

The optional field `role_binding` contains the exact
reviewed names/templates in [the binder contract](android-workflow-job-binder.md).
The fixed phase selects capture or emission and requires its existing job policy
to match that template before lookup. Discovery is inside the original phase
deadline and retains the separate 20-second transport ceiling. The deployment
is rechecked before private input reads or controller requests. Pending/error
does not permit a retry. Static policies remain supported when the field is absent.
The admitted import closure must include the binder before these steps execute.

With that mode, an independently admitted `startup_barrier: {"publisher_id": ID}`
may additionally enable the fixed GitHub commit-status scheduling observer.
Capture and emission-prepare wait for the exact run/attempt/transaction listener
notice **before** binding the three jobs or reading any private role input.
They then perform the original live lookup and compare its three-check-ID
digest with the notice. Emission-submit does not repeat the startup wait; its
original session, retained manifest and no-replay markers remain authoritative.
See [startup scheduling](android-startup-scheduling.md) for exact transport and
deadline bounds. Public metadata never supplies authenticated job identity,
replaces OIDC, authorizes a protected action, or extends a challenge lifetime.

Emission prepare and submit use the same deployment bytes/digest, same retained
manifest and same private attempt directory. The action output must be a
canonical, single-link, owned regular file below the admitted output root, in a
private 0700 parent; public 0644 action output is accepted, writable-by-others
output is not. Attempt and action-output roots are disjoint. Config/input/CA/
manifest/phase-evidence aliases to role or OIDC credential inodes reject before
those public bytes are read, including file-bind aliases with link count one.
Files are held by no-follow descriptors and rechecked before/after exchanges.

Use the same hosted user for these role steps and the official action, matching
`HostedClient`'s existing private-file ownership rules. This is separate from
the root-only job3 signer bootstrap. Private current-user ownership is necessary
custody, not proof of protected workflow admission; candidate code must never
run in this role process or choose its inputs. No signing secrets are injected
into these roles. Root/local builder key export is neither needed nor allowed.

## Optional protected-success hold

When digest-covered `role_binding` mode is enabled, successful `capture` and
`emission-submit` keep the hosted role alive while observing the exact
already-bound protected check through public run/job metadata. The run must
remain `in_progress`; only that protected job may reach `completed/success`.
`emission-prepare` never waits for this observation. This is metadata
observation, not authentication, signing authority, or a new receipt.

Each hold permits at most eight snapshots (sixteen public reads). Each snapshot
shares one 20-second read deadline and the original phase deadline. After a
validated in-progress snapshot, waits are paced at 30/60/120/240/480/960/960
seconds, with custody/deadline checks in no more than one-second slices and no
extra reads during the wait. Failure, malformed/unknown/queued state, transport
error, or expiry is terminal; errors are not retried and no credentials are
obtained. This does not reserve or guarantee a shared-IP API quota. Static mode
without `role_binding` is unchanged.

## Once-only and expiry boundaries

Exclusive fsynced `started`, `manifest-ready` and `bundle-started` files are
local no-replay diagnostics only, not receipts or portable authority. The first
phase marker precedes any challenge/token/submission; the bundle marker precedes
bundle read/upload. Lost responses, partial writes, directory-fsync failure,
expired identity or process loss require reconciliation; no phase retry, new
challenge, changed transaction or synthesized bundle is authorized.

Only successful `pending` and valid progress states are polled. Network errors
are not retried. Existing server challenge/identity TTLs remain unchanged across
the action step and cannot be extended by a local phase timeout. A slow attester
or transfer can genuinely expire; deployment must qualify that latency. Poll
deadlines/socket checks are not hard bounds on every DNS/filesystem/HTTP-header
stall, so the reviewed job supervisor must impose the final stop deadline.

The live owner/controller, journal custody, role credentials, exact simultaneous
job identities, actual immutable attester/runtime/predicate selection and manual
workflow remain deployment inputs, not artifacts produced by this patch. No
signing lock, ledger policy, environment, key or workflow is activated here.
Errors and successful CLI output are constant non-secret diagnostics; no raw
JWT, exception, response or audit is printed. Python zeroization is not claimed.

Tests exercise real existing client/server methods, temporary SQLite and test-key
RS256 with actual public files. HTTP/OIDC provider, Docker/root custody and the
attester are explicit models; the existing origin subprocess is a noncrypto
stand-in, not evidence of deployed Sigstore or production signing.
