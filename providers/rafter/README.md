# Rafter Provider Gate

Rafter is an auxiliary Fleet security/proof gate. It may produce evidence for release decisions, but it does not own product truth, release truth, roadmap truth, publishing, or deployment.

The provider verifier is fail-closed. Without a local verification export it writes `pilot`/`unverified` evidence and exits non-zero.

Expected local config path:

```text
providers/rafter/local/rafter_provider_verification.local.json
```

This local file must not be committed. It should contain only account/capability metadata and redacted export references, never credentials or raw secret values.
