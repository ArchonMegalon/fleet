# Next Session Handoff

## Mandatory policy

- This file must be rewritten after every important step by default.
- Important steps include implementation batches, validation batches, commits, pushes, live config changes, restarts, audits, blocker discoveries, and ETA/priority changes.
- Writing this handoff is not a stopping condition. After updating it, continue with the next highest-value slice unless truly blocked by an external dependency.
- A missing or stale handoff is a failure state for the main agent and for codexliz-backed lanes.
- Every refresh must include:
  - exact changes
  - exact validations and results
  - exact commits/pushes
  - remaining Chummer5a differences, item by item, with reasons
  - current ETA
  - exact next slice
  - current Fleet truth relevant to that slice
  - exact blocker and external step if blocked

## Current Status (`2026-04-21T05:20:00Z`)

**Flagship Product Readiness**: `fail`
- Ready: 7/8 lanes
- Missing: `desktop_client`

**Current readiness truth**
- Receipt: `/docker/fleet/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json`
- `status=fail`
- `missing_keys=['desktop_client']`
- No other readiness plane is currently missing.
- Continuation and handoff discipline is now explicit host policy in `/docker/fleet/PARITY_COMPLETION_INSTRUCTION.md` and `/docker/fleet/CODEX_HOST_GUIDE.md`.

## What changed in the latest UI parity loop

The owner repo (`/docker/chummercomplete/chummer-presentation`) now has a materially stronger classic-dialog posture:

- shared `tree`, `tabs`, and `image` primitives render in both Avalonia and Blazor
- `Global Settings`, `Master Index`, and `Character Roster` are denser and closer to Chummer5a
- shared utility helpers now default to classic `grid`/`snippet` posture for:
  - source dialogs
  - print/update/link/window utilities
  - action receipts
  - entry editors
  - delete confirmations
- major add/select flows now expose classic `Browse / Details / Notes` sections plus category navigation trees:
  - cyberware
  - gear
  - magic / spells / adept powers / complex forms / matrix programs
  - skills
  - drugs
  - initiation / spirits / critter powers
  - vehicles / vehicle mods
  - qualities / weapons / armor
- the major add/select flows above now also render their right-side detail panes as classic property-style grids with compact note snippets instead of generic summary/detail blocks
- contact add/edit and high-use utility dialogs (`skill_group`, `combat_reload`, `combat_damage_track`, `contact_connection`, `gear_mount`, `magic_bind`) now follow the same compact utility rhythm

Validated in owner repo:

```bash
dotnet test /docker/chummercomplete/chummer-presentation/Chummer.Tests/Chummer.Tests.csproj --filter "FullyQualifiedName~DesktopDialogFactoryTests|FullyQualifiedName~AvaloniaFlagshipUiGateTests|FullyQualifiedName~DesktopShellRulesetCatalogTests|FullyQualifiedName~BlazorShellComponentTests"
```

Result: `92 passed`

```bash
cd /docker/chummercomplete/chummer-presentation
bash scripts/ai/milestones/chummer5a-layout-hard-gate.sh
bash scripts/ai/milestones/classic-dense-workbench-posture-gate.sh
bash scripts/ai/milestones/chummer5a-screenshot-review-gate.sh
bash scripts/ai/milestones/chummer5a-desktop-workflow-parity-check.sh
```

Result: all `PASS`

## What changed in the latest Fleet honesty loop

- Shard-summary truth no longer lets stale persisted `streaming` override a live `waiting_for_model_output` stderr tail.
- Latest Fleet commit: `e81f3329` on `main`.
- Live audit now shows the current truth: all `13` shards are on EA and all `13` are presently `waiting_for_model_output`, so they are alive but not materially progressing right now.

## Remaining real gaps

The remaining work is structural, not just CSS density:

1. `Global Settings`
   - still shared flat persistence under tree chrome
   - needs a real legacy-style settings coordinator with true pane-specific save/apply behavior

2. `Master Index`
   - still a shared tree/detail projection
   - needs a real tree/grid/snippet browser posture with source-selection follow-through and richer snippet/browser coordination

3. `Character Roster`
   - still shared pane orchestration
   - needs real image/tab/tree coordination closer to the legacy utility and better selected-runner follow-through

4. High-use add/edit dialogs
   - visually closer, but still driven by one generic action model
   - need per-form coordinator behavior for live recalculation, exact category coupling, and follow-through actions like `Add & More`

5. Secondary utilities
   - notes/update/print/window helpers are denser, but still not legacy-specific coordinators
   - need utility-specific follow-through instead of generic receipt posture where veteran workflows expect more

6. `SR4` and `SR6`
   - still share some neutral dialog copy
   - need more edition-authored labels and help text

7. Windows proof
   - do not treat Linux similarity as Windows proof
   - once the parity-fixed Windows build is cut, use the prepared Windows proof lane and return the proof bundle
   - Fleet auto-ingests the returned bundle now

## Next OODA loop

1. Observe
   - read `/docker/fleet/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json`
   - read `/docker/fleet/CODEX_HOST_GUIDE.md`
   - read the current owner-repo dialog primitives and tests in `/docker/chummercomplete/chummer-presentation`

2. Orient
   - assume the shell density work is no longer the main gap
   - treat the remaining gap as “generic classic dialog parity” vs “legacy-specific utility form parity”

3. Decide
   - take the next structural surface in this order:
     - `Global Settings` coordinator behavior
     - `Master Index` richer browser/snippet/source follow-through
     - `Character Roster` image/tab/tree follow-through
     - one high-use add/edit flow with true coordinator behavior
     - one secondary utility flow (`notes`, `update`, `print`, `window`)
     - one SR4/SR6 authored-copy slice

4. Act
   - implement the owner-repo slice
   - run the focused UI suite
   - run the four parity gates
   - only then refresh any Fleet-facing receipts or notes

## Windows proof lane

Once the parity-fixed Windows build exists, the honest next release step is:

```bash
cd /docker/fleet/.codex-studio/published/external-proof-commands
bash preflight-windows-proof.sh
bash capture-windows-proof.sh
bash validate-windows-proof.sh
bash bundle-windows-proof.sh
```

Return `windows-proof-bundle.tgz` to the same directory on this host. Fleet rebuilder is already watching for it and will auto-finalize/republish.

## Decision rule

Do not chase broad roadmap work while `desktop_client` is still the only missing lane. Keep pushing the owner-repo parity surfaces and the honest Windows proof closeout until that lane turns green.
