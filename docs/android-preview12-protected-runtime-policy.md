# Android Preview12 protected runtime policy — review proposal

Status: **DRAFT; not approved policy, deployment authority, or activation evidence.**
This document selects no active workflow, job, image, attestation key, trust root, or credential.
All such choices require separate owner/security review and immutable admission before implementation can promote provenance.
No lock, workflow, output contract, release eligibility rule, or permission changes are authorized here.

## Existing target and boundaries

The target is `scripts/android_preview12_external_rebuilder.py::execute_protected_signer_transaction` and its existing reconciliation path.
Its required `authenticate_handoff(lock, lock_raw)` callback must return the existing in-memory `AuthenticatedRebuildHandoff`; it is not an undefined name or a serialized authority format.
No production authenticator/caller has yet been established by this proposal.
`PreservedRebuildHandoff` supplies retained-byte checks, not job authentication; `PreservedProtectedValidation` supplies protected consumer/tool checks, not complete runtime isolation proof.
Neither GitHub metadata, parsed JWT claims, caller booleans, nor a renamed callback may substitute for authentication.
The separate v3 `android_preview12_signer.py` workflow is not this missing caller.

Bind the exact reviewed `config/release/android-preview12-external-rebuilder.lock.json` and the subsequently qualified Android graph.
Do not adopt the legacy `android-preview12-signer-toolchain.lock.json` (.NET 8/API 35/JDK 21).
The external lock targets .NET 10.0.110/API 36/JDK 17; its image and installed-closure admissions remain unresolved until independently measured and reviewed.
Do not repin that lock to an unqualified Android candidate or treat source changes as preserved image qualification.

## A. Cryptographically authenticated Fleet artifact origin

Reuse reviewed verification mechanics, not another product's authority policy.
`/docker/chummercomplete/scripts/release/verify_native_android_platform_release.py::verify_github_artifact_attestation` is a reference for digest-pinned `gh`, independently pinned Sigstore trust material, isolated verification inputs, and exact verified-statement/certificate comparisons.
Its current policy authenticates an Android API36 receipt, not Fleet's rebuild artifact; calling it unchanged does not establish Fleet authority.
Any extraction/reuse of mechanics and Fleet-specific policy needs review; do not source-copy a new unchecked verifier or silently broaden the Android policy.

Before a Fleet verifier is implemented, the reviewed non-secret admission must fix all of the following, without wildcard or ambient-environment defaults:

| Required binding | Required evidence and limit |
| --- | --- |
| Issuer and verifier trust | Exact OIDC issuer, verifier binary digest, and independent trusted-root bytes/digest; never select roots or issuer policy from the candidate artifact. |
| Repository | Exact Fleet repository URI/identity, owner URI/identity and permitted visibility, checked against authenticated evidence and the independently admitted repository policy. |
| Workflow and source | Exact workflow path/ref/identity and source/workflow commit digests, plus reviewed workflow bytes and allowed trigger; mutable branch names alone are insufficient. |
| Run and attempt | Exact run invocation and run-attempt identity, bound to the verified statement/certificate and the admitted transaction, not merely an API query result. |
| Producer and signer jobs | Exact logical job keys and execution/job identities, connected to that run-attempt by approved workflow semantics plus independently authenticated execution evidence. A GitHub certificate does not automatically contain a job-ID claim. |
| Artifact and subject | Exact artifact ID, name, size, transport digest, attested subject name/digest, predicate type and subject meaning; bound to the retained bytes and admitted run-attempt. |
| Runner posture | Exact allowed runner environment from verified evidence; this is not proof of the actual image, mount topology, credential absence or custody. |

Reject ambiguous/multiple subjects or statements, unsupported predicates, malformed evidence, untrusted chains, stale evidence, and any mismatch under the reviewed freshness policy.
Compare authenticated statement contents with independently acquired transport metadata and exact local bytes; transport metadata alone cannot authenticate the statement.
Reuse existing bounded download/extraction and canonical validation mechanisms; do not introduce a second digest or serialization dialect.
The existing `artifactClosureSha256` field needs an explicitly reviewed subject/closure derivation before implementation: its current shape check does not define authenticated closure semantics.
If available evidence cannot bind a required job/subject fact, stop; do not infer it from environment variables or invent a certificate claim.

## Closed transported inventory

Admit exactly the existing seven handoff files below, with the existing per-file bounds and semantic checks; no extra entries, alternate paths, links, duplicate names, logs, executables, or credential material.
The reviewed lock is a separately preserved input, not an artifact-controlled policy replacement.

```text
FLEET_ANDROID_PREVIEW12_REBUILD_HANDOFF.generated.json
chummer-android-0.1.0-preview.12-unsigned.aab
chummer-android-0.1.0-preview.12-source-graph.json
chummer-android-0.1.0-preview.12-unsigned.aab.sha256
ANDROID_API36_TWO_GREEN_ELIGIBILITY.generated.json
ANDROID_API36_TWO_GREEN_RELEASE_APPROVAL.generated.json
ANDROID_EXTERNAL_SIGNER_REQUEST.generated.json
```

Bind exact source commit/tree, source graph, request, unsigned AAB bytes/size and sidecar, two-green receipt/approval and their artifact identity, lock bytes, and measured toolchain closure through existing validators.
Recheck canonical roots, closed inventory, stable file identity and bytes through `PreservedRebuildHandoff.assert_exact`; detached mappings do not exempt later rechecks.
Two-green eligibility/approval still requires the actual pinned Android consumer and its existing trust policy; a GitHub-success flag is not release approval.

## B. Protected runtime and custody, independently established

GitHub's verified origin establishes who attested which bytes and the authenticated workflow/source/run claims; it does not prove secret isolation, root ownership, read-only mounts, durable recovery or signing authorization.
Workflow source review establishes intended steps and permissions, not that those steps ran inside the claimed custody boundary.
An installed toolchain receipt binds installed bytes; it is not host attestation or proof that unrelated credential mounts were absent.
The owner must select and review an existing independent runtime measurement/attestation mechanism, its trust authority and its exact execution binding before these claims can be established.
Independent means outside candidate control: a protected owner-controlled launcher/provisioner may measure actual jobs, images and mounts and authenticate execution-bound evidence. This does not inherently require TPM hardware or a new attestation service; no such launcher is admitted by this proposal.
The executing builder must not choose its own trust root or attest its own isolation; a signer-local boolean or self-report is insufficient.
No runtime attestation protocol or new output schema is specified or approved here.

Required runtime facts, corroborated by actual protected-runtime checks where applicable:

- Distinct builder and signer jobs/containers, tied to the admitted run-attempt and exact measured image digests; no ambient or floating image aliases.
- Builder has no signing key/password, ledger/signing bearer, signer credential volume, inherited secret environment or equivalent credential access. Review provisioned mounts, identity permissions and job isolation, not just CLI arguments.
- Candidate-controlled build activity ends before credential admission. Never import or execute builder-supplied scripts, callbacks or tools in the credential-bearing signer.
- Signer source, exact Android consumer, Fleet transaction code, reviewed ledger adapter/policy and tool roots are independently admitted, root-owned, immutable and read-only, including nested mounts, Git storage and imported bytes.
- Preserve the existing `_preserved_*` checks, complete tree measurements and installed-closure receipt checks. Bind the measured builder closure to both handoff and toolchain claims before consumer/ledger work; local closure provenance remains false.
- Distinct reviewed approval and binary-signing ledger identities/policies retain their existing signed protocol, scope and replay protections; no substitution of one ledger's bearer, database or authority for another.
- Credentials are admitted only through the existing protected callback after exact validation and successful reservation. Existing source/tool/lease assertions continue across admission and signing.
- Recovery storage is private, durable, preserved and bound to the same admitted transaction/store identity. Its lifecycle survives process loss; fsync, exclusive creation, quarantine and ambiguous-outcome handling retain existing semantics.
- Reconciliation authenticates the same handoff and validates current protected inputs, but never obtains signing credentials or re-signs. Lost responses require authenticated ledger/recovery resolution, not blind retry.

Only after A and B both succeed may the real caller construct `AuthenticatedRebuildHandoff` and supply its live exactness assertion.
Join both results to the same existing attempt ID, lock digest, authenticated artifact closure, two-green artifact ID/digest and recovery-store identity; a matching run-attempt alone cannot authorize a different transaction.
Existing provenance fields must be derived results of those verifiers, never copied from untrusted `true`/`false` claims; no new capability class is needed.
Retain the transaction's type gate, `_validate_authenticated_handoff`, `bind_transaction`, eligibility, reservation and credential-admission ordering in execute and reconcile.
`android_preview12_signer.py::_validate_handoff_bearer` only parses/checks JWT shape and claims; it is not a cryptographic OIDC signature verifier.
Its JIT workload-identity exchange also remains a separately reviewed runtime integration, not a static-token fallback for this caller.

## Hostile-test obligations

| Attack or failure | Required rejection/proof |
| --- | --- |
| Forged/altered bundle, untrusted root, parsed-only JWT | Real cryptographic verifier rejects; no capability, consumer load, ledger reservation or credentials. |
| Wrong repo/owner/workflow/source/trigger/run-attempt/subject | Exact admitted policy rejects, including a valid signature for the wrong identity. |
| Missing or mismatched job/image/runtime evidence | Reject even when GitHub origin is valid; workflow/environment self-claims cannot fill the gap. |
| Extra file, path escape, link, changed bytes or same-byte inode replacement | Closed inventory and preserved checks reject initially and on recheck, including admission-time drift. |
| Writable/foreign nested mount, mutable imported source, wrong installed closure | Actual filesystem/tool checks reject; no modeled custody result is called runtime proof. |
| Builder credential access or candidate code after key admission | Runtime evidence/approved workflow composition rejects; do not infer absence from missing arguments. |
| Raw preserved object, metadata dictionary or `None` from callback | Existing real type gate rejects before privileged callbacks and before recovery/output creation. |
| Substituted approval, replay, lost reservation/commit response or crash | Existing signed ledger and recovery tests preserve idempotency/quarantine; reconciliation never re-signs. |
| Valid origin/runtime evidence from different attempts, locks, closures, two-green artifacts or recovery stores | Reject cross-transaction substitution even within one run; allow only the existing authenticated same-transaction reconciliation. |

Extend existing `tests/test_android_preview12_preserved_handoff.py`, `test_android_preview12_preserved_validation.py` and `test_android_preview12_protected_transaction.py`; label modeled custody explicitly.
Cryptographic tests must include real signed valid/hostile fixtures under test-only roots, without presenting test keys or synthetic runtime evidence as production admission.
Retain qualified-current-Android integration requirements; optional historical-consumer tests do not qualify the current candidate.

## Ordered implementation and activation prerequisites

1. Security/owner review selects the missing Fleet origin policy, subject/closure meaning, job-evidence composition and independent runtime authority. Record exact non-secret admissions; unresolved/null inputs fail closed.
2. Implement and test the real provenance verifier and its caller of the existing transaction using those reviewed inputs. Offline source/tests need no credentials; this proposal alone is insufficient authority to mint capabilities.
3. Obtain non-writer review, merge through normal checks, then qualify immutable builder/signer images and installed closures against the exact admitted source/tools. A source-only pass is not runtime qualification.
4. Separately authorize and provision protected jobs, reviewer controls, runtime evidence, ledger services, JIT identity exchange, credential custody and durable recovery. No provider activation or approval is implied here.
5. Admit the current exact Android graph only after its required two-green qualification and existing release approval; then perform the authorized end-to-end rebuild, protected signing and recovery proof without weakening gates.
6. Treat signed-AAB acceptance, Play upload authorization, Play processing and Internal-track installation evidence as separate subsequent gates. This proposal authorizes none of them.
