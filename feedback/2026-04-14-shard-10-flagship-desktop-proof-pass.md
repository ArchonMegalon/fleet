# 2026-04-14 shard-10 flagship desktop proof pass

## Scope

- Frontier: `4087117301`
- Slice: `desktop_release_train:avalonia`, `flagship_route_truth:desktop`
- Owner focus: `chummer6-ui`, `chummer6-design`

## Verified state

The current full-product frontier is still fail-closed only on external macOS host proof for the promoted Avalonia desktop tuple:

- tuple: `avalonia:osx-arm64:macos`
- readiness path: `/docker/fleet/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json`
- runbook path: `/docker/fleet/.codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md`
- ui blocker path: `/docker/chummercomplete/chummer6-ui/.codex-studio/published/UI_EXTERNAL_HOST_PROOF_BLOCKERS.generated.json`
- release channel path: `/docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json`

Repo-local truth remains aligned with the canonical desktop flagship bar:

- primary desktop head is still `Chummer.Avalonia`
- published truth still refuses to promote while the required macOS tuple is unresolved
- local feedback/crash/autofix routing remains ready with `total_local_blocker_count=0`

## Command results

Validated the current external-proof lane directly:

```bash
cd /docker/fleet/.codex-studio/published/external-proof-commands && ./validate-macos-proof.sh
```

Result:

```text
startup-smoke-receipt-stale:/docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json:age_seconds=270780:max_age_seconds=86400
```

Validated full external-proof closure:

```bash
python3 /docker/fleet/scripts/verify_external_proof_closure.py \
  --support-packets /docker/fleet/.codex-studio/published/SUPPORT_CASE_PACKETS.generated.json \
  --journey-gates /docker/fleet/.codex-studio/published/JOURNEY_GATES.generated.json \
  --release-channel /docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json \
  --external-proof-runbook /docker/fleet/.codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md \
  --external-proof-commands-dir /docker/fleet/.codex-studio/published/external-proof-commands \
  --json
```

Result: fail-closed only on the same unresolved macOS tuple and its dependent support/journey rows.

Fresh local synthesis confirms the published readiness shape has not drifted:

```bash
python3 /docker/fleet/scripts/materialize_flagship_product_readiness.py --out /tmp/flagship-readiness-current.json
```

Result summary:

- `status=fail`
- `ready=7`
- `warning=1`
- `missing=0`
- `warning_keys=[desktop_client]`
- `completion_audit.external_only=true`
- unresolved tuple: `avalonia:osx-arm64:macos`

## Current blocker detail

`/docker/chummercomplete/chummer6-ui/.codex-studio/published/UI_EXTERNAL_HOST_PROOF_BLOCKERS.generated.json` is current and shows:

- installer present and sha256 matches expected
- public install route probe is acceptable for an account-required download (`403` challenge accepted)
- startup smoke receipt is present but stale
- receipt predates current release publication
- receipt channel mismatch: actual `preview`, expected `docker`
- receipt version mismatch: actual `run-20260411-201805`, expected `run-20260414-1836`

## Required follow-through

Run the generated macOS lane on a native macOS host, then ingest and republish:

```bash
cd /docker/fleet/.codex-studio/published/external-proof-commands
./run-macos-proof-lane.sh
./finalize-external-host-proof.sh
```

Do not mark the frontier complete until the republished readiness artifact clears `desktop_client` without weakening the desktop flagship bar.
