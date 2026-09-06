# Android Preview12 signer groundwork

Fleet owns signing. Its secret signer is Fleet-native `workflow_dispatch`; the
independent reusable verifier accepts only canonical `chummer-android` source
SHA/ref plus an exact full-SHA Fleet workflow pin. Both validate and hash every
run/artifact/digest input. The checked-in red lock blocks environments/secrets.
The only accepted release identity is package `com.myexternalbrain.chummer`,
version `0.1.0-preview.12`, code `12`, minimum SDK `24`, and target SDK `36`.

Android main discovery at `eb4d37ee95eee808a4c2269f1d3f3b5631eb3129`
recorded all real workflow IDs/paths/blob SHAs but found no Preview12 producer.
Preview12 names remain null rather than borrowing Preview9/10 guesses. Future
intake verifies exact run metadata, artifacts, AAB, attestation, producer
toolchain closure, the v3 source graph, and a candidate/source-bound proof-
exclusion result from the exact pinned Android validator. JSON contracts and
HTTP bodies are read through explicit byte ceilings and duplicate keys fail.

Before key access the signer verifies installed toolchain, Fleet job SHA,
GitHub-hosted runtime, package/version/code/SDK manifest identity, source graph,
proof exclusion, and a new durable reservation. The reservation transaction
binds both candidate and verification run/artifact/digest authorities, including
the verification receipt and source graph. Duplicate or indeterminate results
stop. Candidate tools receive a secret-free environment.
Only sanitized intake uses Actions artifacts. Signed output, Play, Registry, and
GitHub release remain absent. Activation still requires the actual producer and
verifier tuple, OCI digest, audited ledger/private SHA-addressed handoff, upload
certificate/algorithm, protected Fleet environments, and least-privilege secrets.
The checked-in publication posture additionally keeps signing and signed-content
handoff false; this groundwork neither creates nor activates those services.
