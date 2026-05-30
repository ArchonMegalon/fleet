# Pixefy Provider Gate

Pixefy is an auxiliary Fleet responsive visual QA gate. It captures public-route visual evidence only and never owns product truth, release truth, or media rendering truth.

The provider verifier is fail-closed. Without a local verification export and screenshot evidence it writes `pilot`/`unverified` evidence and exits non-zero.

Expected local config path:

```text
providers/pixefy/local/pixefy_provider_verification.local.json
```

Screenshots should contain only public route evidence. Do not store private runner sheets, campaign data, browser sessions, or credentials.
