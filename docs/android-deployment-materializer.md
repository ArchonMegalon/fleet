# Android deployment materializer

`android_deployment_materializer.py` is a source-only renderer for the four
already-defined deployment documents: `owner`, `capture`, `emission`, and
`protected`.  Its input profile is an independently admitted public template
set; its output is exactly one existing role document selected by `--role`,
not a new envelope or release receipt.  The profile and invocation context
must be admitted by the caller before this helper runs.  A supplied digest is
only checked against those admitted bytes; hashing arbitrary input does not
grant authority.

The fixed context contains the Fleet/workflow SHA, ref, run ID/attempt, and
one transaction ID.  Rendering changes only the existing invocation fields,
role-binding copies, and the protected launcher attempt/output path.  Check
IDs, subjects, role names, environment, reusable-workflow identity, manifest,
TLS/publisher/trust/resource/image/recovery/code pins, and secret/transport
paths remain profile-controlled.  In direct-workflow profiles the signer
commit follows the admitted workflow SHA; reusable-workflow identity fields
are never inferred or replaced.  Owner and protected lock pins must agree.

Emission preparation and submission therefore consume the same rendered bytes
and context.  The helper performs no credential reads, network requests,
mounts, constructors, signing, or deployment.  It writes only a new 0600
output beneath an existing owner-only directory, with exclusive creation,
descriptor/readback checks, and preserved partial evidence on uncertainty.
