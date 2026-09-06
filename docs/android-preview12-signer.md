# Android Preview12 signer groundwork

Fleet owns signing. `android-preview12-signer.yml` is Fleet-native
`workflow_dispatch`; its reusable verifier is non-secret. The checked-in lock is
red, so its contract job fails before an environment, broker token, ledger,
signing key, candidate download, signature, or upload can be reached.

## What is actually known

The canonical producer is repository ID `1331626697`,
`ArchonMegalon/chummer-android`. Discovery at remote `main`
`eb4d37ee95eee808a4c2269f1d3f3b5631eb3129` found four active workflows, all
recorded with their real Actions ID, path, and Git blob SHA in the transaction
lock. None is a Preview12 producer. Preview9 and an unmerged Preview10 branch
show naming conventions, but they are not Preview12 authority. Therefore the
Preview12 workflow ID/path/blob SHA, source ref/event/attempt, logical artifact
name, exact AAB filename, producer closure digest, and candidate-bound verifier
artifact are null prerequisites rather than guesses.

The future intake validates both run records (including repository and head
repository IDs, event, ref, attempt, workflow ID/path/blob SHA, source SHA, and
green state), both exact artifact IDs/names/archive digests, the AAB digest, and
a producer attestation binding that entire transaction plus the producer
toolchain closure. It checks out no app code and executes no candidate content.

## Secret and output boundaries

The signer image contains a SHA-256-locked JDK, .NET SDK, Android platform and
build-tools, and bundletool closure. Before key access, the signer verifies the
installed-image receipt, sanitized intake, Fleet-native `job.workflow_sha`,
GitHub-hosted runtime, exact Preview12/code12 manifest, and a newly-created
durable ledger reservation. Duplicate or indeterminate reservation outcomes are
terminal. Bundle parsing and signature verification receive a constructed
secret-free environment; the store password reaches only certificate export
and signing, and the key password reaches only the one `jarsigner` invocation.

The sole Actions artifact is one-day sanitized intake/evidence transport. The
signed AAB is never sent through `actions/upload-artifact`. Play upload,
Registry publication, GitHub release, and the Play environment are absent. A
separate future implementation must hand signed bytes to a private store at a
content-addressed SHA-256 endpoint and return a durable receipt; it is not an
Actions evidence upload or a Play upload.

## Prerequisites for a later activation change

An independently reviewed change must supply the actual Preview12 producer and
candidate-bound verifier values above; producer closure receipt; audited
exactly-once broker URL/implementation; upload certificate fingerprint and key
algorithm; published signer image digest (the installed receipt is pinned);
and an audited private content-addressed handoff implementation. Operators must
then separately create reviewer-protected Fleet intake/signing environments and
least-privilege broker, ledger, handoff, and upload-key secrets. Only after all
receipts exist may another protected change set `state` and feature gates ready.

Keep `android-play-upload` disabled. Play delivery remains a later, separately
approved transaction with no credentials or job in this signer workflow.
