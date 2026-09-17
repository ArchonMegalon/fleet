# Android startup scheduling (not release authority)

This optional source implementation sequences three concurrent hosted roles
and the separately admitted local owner. It is not a workflow deployment,
credential grant, readiness receipt, authentication mechanism or signing
permission. The existing serial signer workflow remains outside this mode.

Digest-covered deployments opt in using `startup_barrier` with one positive
numeric GitHub `publisher_id`, alongside the existing `role_binding`. Only the
local owner also receives an explicit private `status_write_token` path. Its
status-write permission must be independently admitted; no ambient GitHub
credential or authentication fallback is used. Hosted reads are public.

## Fixed two-stage sequence

1. Start the three distinct hosted jobs. Capture/emission-prepare wait for the
   listener notice; the protected supervisor waits for the export notice.
2. Independent provisioning admits all three live role IDs and starts the local
   owner. After actual TLS startup and capture arming it posts `listener` once.
3. Capture/emission independently bind the three live jobs, compare the notice's
   ID digest, and continue their original OIDC/journal/controller paths.
4. After verified capture and emission, the owner installs the actual intake
   app with its bounded preparation wait and posts `export` once.
5. The protected supervisor independently binds/compares the jobs before making
   a private child. The existing anonymous-pipe/READY sequence, child binding,
   signed identity and protected transaction checks remain unchanged.

The context contains only the stage and a canonical digest of repository,
workflow SHA, run ID, attempt and transaction ID. The description carries only
the ordered capture/emission/protected check-ID digest. Challenge nonces,
bearers, signing keys and deployment files are never published. Notices are
ordinary public scheduling data, never authenticated job facts.

## Observation and failure bounds

The observer reads only the exact full-SHA GitHub statuses endpoint, first page
of at most 100 rows, using GitHub's [commit-status API](https://docs.github.com/en/rest/commits/statuses).
It accepts only the newest matching context, exact publisher,
run/attempt target and well-formed identifiers/timestamps. Malformed, failed,
ambiguous, truncated, redirected or transport-error responses stop the attempt;
an older success is never substituted for a newer rejection.

Only valid pending/absence observations permit waiting. Listener observation
is capped at eight reads with ten-second waits. Export is capped at sixteen
reads with paced waits of 30/60/120/240/480 then at most 900 seconds, also capped
by half the configured preparation window. Every read has at most 20 seconds
within the original phase deadline. During waits, local custody/deadline checks
run in slices no longer than one second; they make no extra API requests.
The wait figures exclude request duration. These caps neither reserve nor
guarantee shared-IP quota and never extend token or challenge lifetimes.

Owner publication is one bounded fixed-endpoint POST per actual stage, latched
before I/O. Failed or lost replies are not retried. A notice cannot release a
pipe directly, bypass a live job lookup, authenticate a controller session,
replay a mutation or create a release receipt. If a later endpoint fails despite
the notice, the original client fails closed.

This adds no controller routes and changes no Play publication state. Source
tests model GitHub transport and privileged deployment; they do not constitute
live listener, attestation, external signer or Play evidence.
