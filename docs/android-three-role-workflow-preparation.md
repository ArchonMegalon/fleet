# Three-role workflow preparation: not an operational workflow

This document records the existing executable seams, not a deployable GitHub
workflow. The separate `android-role-source-tests.yml` runs only source unit
tests on ordinary pull requests and main pushes. No operational role workflow
or profile is admitted, and no owner, listener, credential, storage, attestation
or signing operation is started. The offline tests exercise real parsers/materialization/job discovery;
their synthetic example repository, jobs and resource paths are not live inputs.

## The remaining provisioning boundary

`android_deployment_materializer.materialize()` accepts an independently admitted
four-document profile and invocation context, checks their exact byte digests,
and writes one existing role document exclusively as 0600. It does not establish
where those admissions came from or provision the interpreter, source closure,
root-owned files, credentials, private route or durable recovery mount. A
candidate profile plus its own SHA256 cannot supply that missing authority.

There is no complete reviewed hosted provisioning entrypoint to invoke here. Adding a
made-up `provision` command, an arbitrary bootstrap/command input, a synthetic
active profile or a successful placeholder job would hide this gap. The
existing owner/bootstrap custody checks must remain unchanged. The fixed
`android_hosted_input_stager.py` now stages only the two explicitly injected
OIDC request values into fresh files at admitted paths, after checking the exact
rendered deployment and already-delivered role bearer. It does not supply
source/interpreter/profile admission, role-bearer delivery, protected credentials,
private routing or durable storage. See the
[materializer](android-deployment-materializer.md),
[hosted roles](android-hosted-controller-roles.md), and
[protected supervisor](android-protected-job-supervisor.md) contracts.

## Fixed source wiring after independent provisioning exists

The dedicated workflow must be manual-only (`workflow_dispatch`), on its
reviewed Fleet ref, with three distinctly named concurrently scheduled
GitHub-hosted jobs. Do not add `needs` dependencies between capture, emission
and protected jobs or use the old serial/native-v3 signer path. The exact names
become the admitted `role_binding.job_names`, not identity inferred from API
rows. The protected job uses `android-preview12-release-builder`; capture and
emission use their separately reviewed protected environments.

Before any role module is imported, independent provisioning must admit its
fixed interpreter/import/dependency closure and applicable public/private file
custody. Only then may the existing materializer render one role using
`--profile`, `--profile-sha256`, `--context`, `--context-sha256`, `--role` and
`--output`. That output digest binds bytes, not a new grant of authority.
No shell command or Python bootstrap is selected by a workflow input.

The post-admission entrypoints are already implemented:

| Concurrent job | Fixed sequence within that job |
| --- | --- |
| Capture | `android_hosted_controller_roles.main`: `capture --deployment PATH --deployment-sha256 ADMITTED_SHA` |
| Emission | Same CLI: `emission-prepare`; official pinned attestation action; `emission-submit --deployment PATH --deployment-sha256 ADMITTED_SHA --bundle ACTION_OUTPUT_PATH` |
| Protected | `android_protected_job_supervisor.main`: `--deployment PATH --deployment-sha256 ADMITTED_SHA --interpreter-sha256 ADMITTED_INTERPRETER_SHA --maximum-seconds ADMITTED_BOUND` |

These are interfaces, not runnable commands with supplied deployment values.
Emission prepare/submit use the same admitted document, digest, user and attempt
directory. The supervisor owns the one child/anonymous-pipe handshake within a
single protected step; no descriptor is carried between action steps.

The previously reviewed official attester is
`actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6`. Its independently
selected `subject-path` is the one exact retained
`FLEET_ANDROID_PREVIEW12_REBUILD_HANDOFF.generated.json`, never an AAB, glob or
caller-provided digest. Its custom predicate must describe hosted emission of
that manifest, not claim that the local Android compilation was GitHub-hosted.
Predicate URI/content and workflow identities must match the admitted origin
policy. Selection and actual attestation publication still need review; the
action pin alone does not authorize publication or qualify its runtime.

Pass the real action output through an environment variable and quote its
single argv value, as in this non-operational fragment:

```yaml
env:
  ATTESTATION_BUNDLE_PATH: ${{ steps.attest.outputs.bundle-path }}
```

The fixed admitted caller then passes `--bundle "$ATTESTATION_BUNDLE_PATH"`.
Do not interpolate that expression into shell code, rediscover bundle files,
fabricate a bundle or retry submission after an uncertain response. No role
uses secret expressions in executable shell, prints private inputs, or gains
GHCR/package write permission for this flow. Review only the permissions needed
for the selected OIDC/attestation operation; do not inherit fork/package-write
settings from an unrelated workflow.

With existing `role_binding`/`startup_barrier` enabled, all three jobs first
remain in progress while the owner publishes the admitted listener notice.
Capture/emission bind actual check IDs and execute the original OIDC protocol.
The owner publishes export readiness only after actual handoff installation;
the protected supervisor waits for it and still performs original admission.
Capture and emission-submit hold for the bound protected job's success. Notices
and discovered check IDs are scheduling/expectation data, not authentication.

## Inputs that cannot be invented by source wiring

The complete profile must supply all existing fields; these are particularly
important at the still-unimplemented provisioning boundary:

- All roles: independently admitted profile/deployment digests; exact same
  controller `base_url`; aligned job/artifact policies and `role_binding`;
  optional identical `startup_barrier.publisher_id` from actual admission.
- Owner: `fleet_root`, complete `code_pins`, lock/Docker/verifier/trusted-root/
  TLS pins, journal identities/path, five bearer digests, private TLS key path,
  attempt/operation/custody directories, actual builder runtime policy and
  whole-operation limits. Optional status publishing needs its admitted private
  `status_write_token`; public scheduling metadata cannot replace it.
- Hosted capture/emission: controller/OIDC CA pins, private `role_bearer`,
  `oidc_request_url`, `oidc_request_credential` files and fresh role-local attempt
  paths. Emission additionally admits the real `attestation_output_root` and
  action runtime/output custody; that runner temporary root is not signer
  recovery storage.
- Protected: launcher validation/tool/source/handoff paths, lock/code pins,
  Docker/verifier/trusted-root/intake/OIDC CA pins, real `persistent.parent` and
  `persistent.mount_row_sha256`, separately delivered secret/transport paths,
  signer runtime policy, interpreter digest, actual host cgroup/disk/deadline
  admission and fresh recovery/output directories. Durable recovery needs real
  private mount/replacement-host evidence, not a fabricated row or local-only
  `RUNNER_TEMP`. This document establishes no private route or WARP consent.

Exact public source, lock, tool, CA and image bytes can be prepared and reviewed
offline. The candidate ready lock must be frozen before the genuine independent
rebuild and bound by both owner/protected profiles and the resulting handoff;
its prepared state is not deployment or signing authority. Original public
snapshots and dormant repository policy must not be silently replaced.

The invocation context uses **the future Fleet workflow commit** for both
`fleet_sha` and `workflow_sha`, not the Android commit or the earlier base-code
commit. Profile source identities/import pins must be explicitly rebound for
that reviewed source. Actual `run_id`, `run_attempt`, transaction identity,
three job check IDs, OIDC challenges/tokens, startup notices and action output
come from the real admitted invocation. The materializer preserves expected
manifest digest, predicate, role subjects/environments, recovery/resource/code
pins and all credential paths; it does not discover or authenticate them.

## Offline verification scope

`tests/test_android_three_role_preparation.py` composes the real materializer,
all four consumer parsers and real public Jobs API validators. It verifies
preserved authority fields, changed-byte rejection, matching Fleet/workflow
context, three concurrently running roles and rejection before private input
use when hosted custody is absent. Public metadata is a fixture; no genuine
OIDC, attestation, Docker, network, listener or signing operation occurs.
Existing dependency version checks remain active. These tests are preparation
evidence only, not a substitute for the missing provisioning implementation.

The source-test CI runs seven suites: these composition tests plus materializer,
adversarial materializer, hosted-role, job-binder, supervisor and hosted-input
stager tests on Ubuntu 24.04/Python 3.12, without path filters. It uses a fresh non-system-site
venv and ten hash-pinned binary wheels in
`tests/android-role-source-requirements.txt`, with dependency resolution
disabled and `pip check` required. No FastAPI/Uvicorn/optional server extras
are installed: the server import is inside the uncalled owner `run()` path.
The five-minute job has only read-only repository permission, pinned checkout
with persisted credentials disabled, no protected environment or artifact
upload, and no dispatch/activation route. Public wheel download is installation
of test dependencies only; the seven suites do not contact live providers.
