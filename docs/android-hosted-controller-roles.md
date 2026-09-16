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
script. Use an admitted fixed `-I -B -c` import bootstrap which inserts only its
already-admitted absolute Fleet root, not cwd/PYTHONPATH or a dynamic factory.
The configuration digest must come independently from protected provisioning,
never from candidate JSON, local claims, a self-hash or chown-as-authentication.

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

The bounded, duplicate-key-rejecting public JSON has exactly these fields:

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
