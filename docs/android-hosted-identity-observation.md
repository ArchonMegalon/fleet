# Hosted identity compatibility observation — diagnostic only

The manual-only android-hosted-identity-observation.yml workflow answers whether
an actual Fleet hosted job receives check_run_id as a JSON string or number,
whether it equals job.check_run_id, and how that exact check run maps to the
distinct job ID in the exact run-attempt Jobs API. It neither imports nor changes
the production workflow identity verifier. No production challenge is issued.

Preparation is not execution approval. After normal review and merge, a separately
authorized single dispatch supplies the exact current protected Fleet main commit
as expected_execution_sha. Only attempt one, the fixed Fleet repository and
protected main are accepted. The helper checks fresh main before requesting the
token; an old dispatch must fail, never silently follow newer source. No signing
environment, release secret, key, Docker, SDK, tunnel or controller is involved.

The standard-library helper obtains the hosted runner OIDC response directly over
verified HTTPS with a fixed diagnostic audience derived from the run/attempt/check
run. This audience is distinct from urn:chummer:fleet:workflow-job:... . The raw
JWT is decoded in memory **without signature verification**; output explicitly
says signatureVerified: false and diagnostic_only_not_authority. Direct issuer
transport plus hosted execution evidence supports this compatibility observation,
not cryptographic job authentication, release eligibility or signer readiness.

The ephemeral runner request credential is sent only to the runner-provided HTTPS
.actions.githubusercontent.com endpoint. The ephemeral GitHub job token is sent
only to fixed Fleet branch and exact-attempt API URLs. There are no proxies,
redirects or retries; HTTP bodies are bounded, each request has a 15-second timeout,
and the helper has a 60-second wall deadline inside a three-minute job. Public API
and token comparisons must pass before producing any output file. The diagnostic
accepts only canonical positive integer strings or integers for check_run_id;
this observation does not normalize or broaden production JWT admission.
The documented optional x5t JWT header is accepted only by this diagnostic;
known header names (alg, kid, typ, optional x5t) and JSON types are recorded,
never header values or arbitrary names. Unknown names or malformed types fail.
Additional bounded OIDC response metadata is discarded, following the official
toolkit's response.value selection rather than assuming a closed response schema.

Only an exclusive 0600 file under the canonical runner temporary directory is
uploaded, with one-day retention. Its closed public inventory is classification,
the explicit false signature-verification flag, exact repository/source/workflow/
run/attempt identifiers, OIDC/context check-run values and JSON types, whitelisted
JWT header names/types, matched API job/check-run IDs and comparison result.
JWTs, header values, subjects, JTIs, token hashes, request
headers/URLs/query strings, arbitrary claims, response bodies and exception text
are never persisted or logged. Failures print one constant line and do not upload
an artifact. No Python-memory zeroization claim is made. Enable neither shell
tracing nor third-party credential/token debugging around this observation.

Actual execution effects, if later authorized: one hosted Ubuntu 24.04 job; pinned
checkout; one protected-main GET; one OIDC token request; two exact-attempt API
GETs; and one small public diagnostic artifact upload. Permissions are only
contents/read, actions/read and id-token/write. Attestation publication, signing,
release approval, production journal/controller and account mutation are absent.

The one-job workflow does not establish when future dependent jobs receive their
check-run IDs or demonstrate simultaneous-job scheduling. Those are separate
deployment observations; this result must not be stretched into that evidence.

Primary references: [OIDC claims and token requests](https://docs.github.com/en/actions/reference/security/oidc),
[job context](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts#job-context),
[exact-attempt Jobs API](https://docs.github.com/en/rest/actions/workflow-jobs#list-jobs-for-a-workflow-run-attempt),
[documented JWT header](https://docs.github.com/en/actions/concepts/security/openid-connect#understanding-the-oidc-token),
[official token retrieval](https://github.com/actions/toolkit/blob/main/packages/core/src/oidc-utils.ts),
[hosted OIDC domains](https://docs.github.com/en/actions/reference/runners/github-hosted-runners#communication-requirements-for-github-hosted-runners).
Focused tests use fabricated unsigned diagnostic tokens and modeled HTTP only;
they never claim genuine hosted evidence or execute the workflow.
