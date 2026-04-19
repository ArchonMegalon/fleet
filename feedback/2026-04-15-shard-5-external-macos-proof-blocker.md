# 2026-04-15 shard-5 external macOS proof blocker

## Scope

- Frontier: `1300044932`
- Scope: `Full Chummer5A parity and flagship proof closeout`
- Run: `20260415T013321Z-shard-5`

## Current state

The full-product delivery pass remains fail-closed only on the external macOS desktop proof tuple:

- `avalonia:osx-arm64:macos`

Repo-local readiness, release truth, and the external-proof runbook still agree that `desktop_client` is the sole remaining coverage gap.

## Direct verification

Validated the generated macOS proof lane:

```bash
cd /docker/fleet/.codex-studio/published/external-proof-commands && ./validate-macos-proof.sh
```

Result:

```text
startup-smoke-receipt-stale:/docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json:age_seconds=278253:max_age_seconds=86400
```

Validated whole external-proof closure:

```bash
python3 /docker/fleet/scripts/verify_external_proof_closure.py \
  --support-packets /docker/fleet/.codex-studio/published/SUPPORT_CASE_PACKETS.generated.json \
  --journey-gates /docker/fleet/.codex-studio/published/JOURNEY_GATES.generated.json \
  --release-channel /docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json \
  --external-proof-runbook /docker/fleet/.codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md \
  --external-proof-commands-dir /docker/fleet/.codex-studio/published/external-proof-commands \
  --json
```

Result summary:

- `status=failed`
- `failure_count=23`
- every failure still collapses to the same unresolved host backlog rooted in `avalonia:osx-arm64:macos`

Validated local host capability:

```bash
uname -s && command -v hdiutil || true
```

Result:

```text
Linux
```

This worker cannot produce the required native macOS `hdiutil`-backed startup-smoke receipt.

Materialized a fresh local readiness snapshot without republishing published truth:

```bash
python3 /docker/fleet/scripts/materialize_flagship_product_readiness.py --out /tmp/flagship-readiness-shard5-current.json
```

Result summary:

- `status=fail`
- `ready=7`
- `warning=1`
- `missing=0`
- `warning_keys=[desktop_client]`
- `completion_audit.external_only=true`
- unresolved tuple: `avalonia:osx-arm64:macos`

## Blocker detail

- Current receipt path: `/docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json`
- Receipt timestamp: `2026-04-11T20:19:47.089302+00:00`
- Current published release version: `run-20260414-1836`
- Current published release channel: `docker`
- Repo-local blocker artifact: `/docker/chummercomplete/chummer6-ui/.codex-studio/published/UI_EXTERNAL_HOST_PROOF_BLOCKERS.generated.json`

That blocker artifact still records:

- installer present with expected SHA-256
- public install route acceptable for account-gated access
- receipt stale
- receipt precedes current release publication
- receipt channel mismatch (`preview` vs `docker`)
- receipt version mismatch (`run-20260411-201805` vs `run-20260414-1836`)

## Required next action

Run the generated macOS host lane on a native macOS arm64 host, ingest the resulting bundle, then republish release truth:

```bash
cd /docker/fleet/.codex-studio/published/external-proof-commands
./run-macos-proof-lane.sh
./finalize-external-host-proof.sh
```

Do not mark flagship completion or republish green readiness until that fresh native-host receipt lands and clears `desktop_client` honestly.
