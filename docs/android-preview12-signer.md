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
the verification receipt and source graph. A broker may report either a newly
created or an already-existing exact reservation; Fleet normalizes both to the
same immutable local evidence, so an exact workflow retry does not require a
second signing slot. Any non-exact or indeterminate result stops. Candidate
tools receive a secret-free environment.

After signing, the same protected job must complete the private content-addressed
handoff. It creates the immutable object at its SHA-256 address with
`If-None-Match: *` and a stable idempotency key. A retry may receive the same
normalized `present` receipt; a different request at the same address is a hard
conflict. If the PUT response is lost, or the server returns `409`/`412`, the
client performs bounded authenticated GETs of both the object and its durable
request receipt. It accepts the retry only when the bytes, address, transaction,
request digest, and every binding are exact; otherwise it fails closed. The
normal path performs the same readbacks. Neither contract nor audit receipt
contains a public or private download URL.

Before certificate verification or upload, the signed AAB is opened without
following symlinks and copied through that one descriptor into a private scratch
file. The scratch file remains open for hashing and upload, and its descriptor,
pathname inode, size, timestamps, and bytes are rechecked across certificate
tools and network operations. Replacing either pathname cannot substitute new
bytes into the handoff.

The handoff request binds all of the following without relying on a filename:

* unsigned candidate artifact and AAB digests;
* Android source commit and complete source-graph digest;
* verification artifact and verification-receipt digests;
* proof-exclusion validator blob and output digests;
* durable reservation request and receipt digests;
* signed AAB digest and byte size plus signed-attestation digest;
* signer contract, exact OCI image, signer execution, and upload-certificate
  digests;
* audited handoff implementation, endpoint-authority, and auth-policy digests.

The bearer accepted by the client must be a signed JWT whose three segments are
strict canonical base64url without whitespace. Its issuer, audience, single
required scope, issued-at/not-before/expiry window, and maximum lifetime match
the lock; `iat` cannot follow `exp`. Lifetime is capped at 15 minutes.
Client-side claim checks are defence in depth; the private handoff service
remains responsible for authenticating the JWT signature and enforcing
create-only scope. Header-construction and HTTP client errors are sanitized
without exception chaining because some runtimes include the raw Authorization
value in those errors. The token, subject, JTI, raw endpoint, and HTTP bodies are
never written to the sanitized audit receipt.

Only sanitized intake uses Actions artifacts. Signed output and the handoff audit
remain runner-local; no signed Actions artifact, Play lane, Registry publication,
GitHub release, or public URL exists. Activation still requires the actual
producer and verifier tuple, OCI digest, audited reservation/handoff services,
upload certificate/algorithm, protected Fleet environments, and least-privilege
short-lived auth. The checked-in lock keeps producer names, image digest,
reservation endpoint, handoff endpoint, issuer/audience/scope, upload certificate,
signing, and signed-content handoff disabled or null. This groundwork does not
create keys, configure environments, deploy services, sign an AAB, or upload it.
