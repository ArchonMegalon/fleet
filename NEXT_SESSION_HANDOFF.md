# Next Session Handoff

## What changed
- Tightened `Character Roster` so it now uses the configured roster path instead of a pure placeholder posture.
- Added roster watch-folder tree content, saved-runner entries, actual watch-folder status, and denser roster commands.
- Added a deterministic portrait source placeholder path so Avalonia and Blazor now expose the same roster portrait contract.
- Fixed Fleet shard honesty again: stale `streaming` no longer survives when a shard has a worker PID and run paths but zero output timestamps and zero output artifacts.
- Restarted `fleet-design-supervisor` so the new Fleet honesty logic is live.

## Exact files changed
- `/docker/chummercomplete/chummer-presentation/Chummer.Presentation/Overview/DesktopDialogFactory.cs`
- `/docker/chummercomplete/chummer-presentation/Chummer.Tests/Presentation/DesktopDialogFactoryTests.cs`
- `/docker/fleet/scripts/chummer_design_supervisor.py`
- `/docker/fleet/tests/test_chummer_design_supervisor.py`

## Exact validations run and results
- `dotnet test /docker/chummercomplete/chummer-presentation/Chummer.Tests/Chummer.Tests.csproj --filter 'FullyQualifiedName~DesktopDialogFactoryTests' --nologo`
  - Result: `50 passed`
- `dotnet test /docker/chummercomplete/chummer-presentation/Chummer.Tests/Chummer.Tests.csproj --filter 'FullyQualifiedName~DesktopDialogFactoryTests|FullyQualifiedName~AvaloniaFlagshipUiGateTests|FullyQualifiedName~DesktopShellRulesetCatalogTests|FullyQualifiedName~BlazorShellComponentTests|FullyQualifiedName~DialogCoordinatorTests|FullyQualifiedName~DesktopPreferenceRuntimeTests|FullyQualifiedName~CharacterOverviewPresenterTests|FullyQualifiedName~DualHeadAcceptanceTests|FullyQualifiedName~RulesetUiDirectiveCatalogTests' --nologo`
  - Result: `231 passed`
- `bash /docker/chummercomplete/chummer-presentation/scripts/ai/milestones/chummer5a-layout-hard-gate.sh`
  - Result: `PASS`
- `bash /docker/chummercomplete/chummer-presentation/scripts/ai/milestones/classic-dense-workbench-posture-gate.sh`
  - Result: `PASS`
- `bash /docker/chummercomplete/chummer-presentation/scripts/ai/milestones/chummer5a-screenshot-review-gate.sh`
  - Result: `PASS`
- `bash /docker/chummercomplete/chummer-presentation/scripts/ai/milestones/chummer5a-desktop-workflow-parity-check.sh`
  - Result: `PASS`
- `pytest -q /docker/fleet/tests/test_chummer_design_supervisor.py -k 'preserves_waiting_for_model_output or waiting_tail_overrides_stale_streaming_progress or marks_missing_output_artifacts_instead_of_streaming or waiting_overrides_stale_streaming_without_output_evidence'`
  - Result: `4 passed`

## Exact commits and pushes
- `chummer6-ui`
  - Commit: `3bd37458`
  - Message: `Tighten roster watch and portrait posture`
  - Pushed to:
    - `origin/main`
    - `origin/safe-push-fix-windows-installer-payload-20260401`
- `fleet`
  - Commit: `9470ff55`
  - Message: `Mark silent shards waiting without output evidence`
  - Pushed to:
    - `origin/main`

## What still differs from Chummer5a, item by item, and why
- `Character Roster`
  - Closer now, but still not a true legacy roster coordinator.
  - Reason: there is still no real mugshot/image pipeline and no actual live watch-folder/file-watcher behavior; the portrait and watch folder are still deterministic placeholders over shared dialog state.
- `Master Index`
  - Closer now, but still not a fully interactive legacy browser.
  - Reason: snippet/result posture is better, but source switching, result activation, and page-open follow-through still ride the shared dialog model instead of a dedicated stateful coordinator.
- High-use add/select dialogs
  - Closer now, but still not exact Chummer5a selectors.
  - Reason: category/result posture and `Add & More` are tighter, but the dialogs still lack exact legacy category-tree coupling and fuller per-form coordinator behavior.
- Edit/remove utility dialogs
  - Denser now, but still not fully identical.
  - Reason: they still run on shared dialog primitives instead of dedicated per-form legacy coordinators.
- `Blazor`
  - Still not pixel-identical.
  - Reason: browser font metrics, focus semantics, and menu behavior differ from desktop.
- `SR4` / `SR6`
  - Still partially neutral in dialog wording.
  - Reason: not every dialog title, label, and message is authored per edition yet.

## Current ETA
- Remaining roster true coordinator follow-through: `0.5–1 working day`
- Remaining `Master Index` dedicated coordinator follow-through: `0.25–0.5 working day`
- Remaining selector and utility coordinator parity: `0.5–1 working day`
- Remaining SR4/SR6 authored wording beyond the shell layer: `0.5 working day`
- Honest `98%+` parity claim across Avalonia + Blazor + SR4/SR5/SR6 wording: `1.0–2.0 working days`

## Live Fleet truth relevant to the next slice
- Before the latest fix, all `13` active shard state files claimed `streaming` while exposing:
  - no `active_run_worker_first_output_at`
  - no `active_run_worker_last_output_at`
  - no `latest_stdout_at`
  - no `latest_stderr_at`
  - no output artifact paths that actually existed
- `shard-13` was on EA, not `code.girschele.com`, using `acct-ea-core-01`.
- After applying `9470ff55` and restarting `fleet-design-supervisor`, the aggregate board is temporarily repopulating from zero:
  - current `active_run_count = 0`
  - top-level shard entries are blank while the supervisor repopulates state
- So the honest live statement right now is:
  - the previous board overstated progress
  - the new honesty logic is live
  - the aggregate board needs a fresh post-restart sample before any positive shard-progress claim is credible

## Real blocker and exact external step if blocked
- No host-local blocker for ongoing UI parity work.
- The broader product still has the previously known external Windows-proof blocker for honest Windows green status, but that does not block the current UI parity slices.

## Exact next slice to work on
1. Author SR4/SR6 dialog wording beyond the shell layer in `Chummer.Presentation/Rulesets/RulesetUiDirectiveCatalog.cs` and the highest-use dialog factories that still read neutral.
2. Re-run the focused parity suite and the four parity gates.
3. Commit and push the green slice immediately.
4. Re-sample Fleet shard truth after the supervisor repopulates.
5. Start next working slice.
