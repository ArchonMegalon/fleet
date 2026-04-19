Title: Shard 13 audit of hub workspace continuity frontier

Run context:
- run: `20260414T230927Z-shard-13`
- frontier: `2756381468`
- package: `next90-m105-hub-workspace-continuity`
- date: `2026-04-14`

Result:
- The owned hub slice for `workspace_restore:provenance` and `entitlement_sync:conflict_receipts` is already implemented in `chummer.run-services` and passes focused local verification.
- No local code change was warranted in this pass because the repo already carries the required restore provenance receipts, conflict receipts, persistence, projection, and account-surface rendering.

Evidence:
- `Chummer.Run.Api/Services/Community/CampaignSpineService.cs`
  - builds restore provenance receipts with explicit `Surface`, `Authority`, `Proof`, and `RecoveryHint`
  - builds restore conflict receipts for stale/inactive installs, expired/mismatched entitlements, orphan grants, and restore-summary conflicts
- `Chummer.Run.Api/Services/Community/WorkspaceLifecyclePolicyService.cs`
  - preserves stable observation timestamps for restore provenance/conflict receipts across refreshes
- `Chummer.Run.Api/Services/Community/CampaignWorkspaceServerPlaneService.cs`
  - projects restore provenance and conflict receipts onto the workspace server plane with normalized surface classification
- `Chummer.Run.Api/Views/Accounts/Account.cshtml`
  - exposes a dedicated `Restore provenance and conflict receipts` drawer on the selected workspace account surface
- `Chummer.Tests/CampaignSpineRestoreReceiptTests.cs`
  - covers authority-backed provenance emission, stale claim and entitlement conflicts, and store reload persistence
- `tests/RunServicesSmoke/Program.cs`
  - asserts the campaign spine server plane and account workspace detail route preserve restore provenance/conflict receipts, including explicit `workspace_restore` and `entitlement_sync` surfaces

Verification:
- Command:
  - `dotnet test /docker/chummercomplete/chummer.run-services/Chummer.Tests/Chummer.Tests.csproj --filter "CampaignSpineRestoreReceiptTests|WorkspaceLifecyclePolicyServiceTests|CampaignWorkspaceServerPlaneServiceTests"`
- Result:
  - passed on `2026-04-14`
  - `405` passed, `0` failed, `0` skipped for both `net10.0` and `net10.0-windows`

Release truth blocker:
- `FLAGSHIP_PRODUCT_READINESS.generated.json` still reports the only unresolved release-proof gap as the external macOS tuple `avalonia:osx-arm64:macos`.
- This worker run did not change published readiness because the blocker is external-host proof, not a missing local hub implementation.
