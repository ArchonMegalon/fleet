# Protected job3 entrypoint

`scripts/android_protected_job_entrypoint.py` implements the real network/intake/
launch composition. It is **not deployed** and does not activate a workflow,
configure a dormant lock or make an ordinary local process a protected job.

The independently admitted root owner **inside the protected GitHub-hosted job**
calls `ProtectedJobEntrypoint` with an actual, already constructed
`ProtectedJobLauncher`, pinned origin verifier/trusted root and its admitted
OIDC TLS context (`CERT_REQUIRED`, hostname checking, minimum TLS1.2). The
launcher's existing constructor must have completed its full key-free input
validation. Missing or changed code, lock, roots, mount, tools or packet admission
reject before this entrypoint requests a challenge or token. This module never
reads the four signing-secret files; the unchanged launcher/transaction do so
only after their signed reservation barrier.

Before the local controller owner arms the original job3 challenge, prepare the
launcher, all public source/tool roots, durable mount and this entrypoint. The
same live `PublicCaptureExport` must have called
`enable_protected_job_checks()` before `arm()`. The bootstrap then invokes:

```python
# These are actual owner-admitted objects, not request dictionaries or fixtures.
entry = ProtectedJobEntrypoint(
    owned_launcher,
    verifier=pinned_origin_verifier,
    trusted_root=pinned_sigstore_root,
    oidc_tls_context=admitted_oidc_tls,
)
# Owner coordination arms the original challenge only after preparation.
audit = entry.run(
    oidc_request_url=job_injected_request_url,
    oidc_request_credential=job_injected_request_credential,
)
```

The two request inputs are explicitly passed from this hosted job's
`ACTIONS_ID_TOKEN_REQUEST_URL` and `ACTIONS_ID_TOKEN_REQUEST_TOKEN`. No ambient
environment lookup, raw-token argument, injected token-provider callback,
factory import or serialized capability is accepted. Neither the URL nor token
is emitted, persisted, put in a child argv/environment or used as provenance.
The same invocation must contain the two distinct admitted hosted capture and
emission jobs. Jobs1/2 already use `ControllerRendezvous` and `HostedClient`;
there is no new controller or signing protocol here.

Execution performs one challenge request, one direct GitHub OIDC HTTPS GET with
that audience, `begin(token)`, the existing seven-file `receive(...)`, and
`ProtectedJobLauncher.launch(actual_intake)`. Token syntax is bounded locally;
the existing server's RS256/JWKS/exact Jobs API/SQLite consume remains the only
workflow authentication. Neither locally decoded claims nor diagnostic identity
observations are substituted. The raw launcher audit is returned unchanged.

The endpoint is HTTPS on the existing GitHub Actions issuer-request host family;
the injected URL must not already contain an audience. No proxies, redirects,
retries, renewal or resume. Response headers/bytes and elapsed socket operations
are bounded between socket calls. The15s check is not a hard whole-request
deadline: DNS, kernel scheduling and trickled header/chunk-trailer parsing can
exceed it. The root owner must supervise the entire operation. Extra provider JSON metadata
is discarded. Both fixed-length and chunked/EOF JSON responses are supported.
All public errors are one constant without upstream exception text. Python
memory zeroization and traceback-local confidentiality are not claimed; the
owner must not enable traceback-local dumping or debug HTTP logging.

The first attempt is latched before network, with a shared-client latch before
the challenge. No mutex is held across launcher execution, so its ledger broker
and heartbeat can call the same client. Any ambiguous failure closes the client
and forbids replay; a lost consume/launch response never authorizes a new attempt.
No intake mount, tombstone, signed output, operation or recovery record is
automatically deleted. `entry.captured` retains the successful intake object for
the existing explicit exact-owner cleanup; partial receive evidence also remains.
This entrypoint is execute-only; it neither adds nor changes reconciliation.

## Exact production wiring still missing

There is no safe generic JSON-to-owner bootstrap in the project. This change
deliberately does **not** invent one or call an arbitrary operator-selected
module. A reviewed hosted-owner bootstrap still must construct the existing
launcher/client from actual deployment admission and call the entrypoint above.
That bootstrap belongs in the protected GitHub-runner host step, not the isolated
worker or the ordinary local build controller. Its manual workflow must admit
the exact Fleet/workflow/run/attempt/check-run, select
`android-preview12-release-builder`, grant `id-token: write`, prepare root-owned
read-only code/source/tool inputs, and coordinate the still-live local controller
through the existing private TLS role transport. The older native-v3
`android-preview12-signer.yml` does not currently call this path.

This remains blocked on the real endpoint/role credentials, admitted hosted
runtime, qualified persistent local-infrastructure backend, configured immutable
lock frozen before independent rebuild, genuine capture/emission and all four
protected job secrets. Builder-key custody remains in the existing GitHub
environment; nothing exports it to the ordinary host. Preparation/testing here
does not obtain any of those values, dispatch, sign, attest, publish or upload.

Focused tests use synthetic credentials and real existing test-key RS256,
SQLite and public intake bytes. HTTPS, root/mount/source admission and final
launcher execution are explicitly modeled. They cover once-only composition,
wrong signed job/run/attempt/claims, malformed/late/oversized responses,
configuration drift, lost replies, expiry and retained partial evidence. Passing
them is source regression evidence, not a deployment or successful-signing claim.
