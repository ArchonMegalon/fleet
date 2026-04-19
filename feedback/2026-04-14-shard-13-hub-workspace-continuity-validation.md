Title: Shard 13 validation of hub workspace continuity frontier

Run context:
- run: `20260414T231318Z-shard-13`
- frontier: `2756381468`
- package: `next90-m105-hub-workspace-continuity`
- date: `2026-04-14`

Result:
- The owned hub slice for `workspace_restore:provenance` and `entitlement_sync:conflict_receipts` is already present on the live `chummer.run-services` checkout and remains green under focused local verification.
- No code edit was required in this worker pass because the implementation, projection, persistence, and account-surface rendering for restore provenance and conflict receipts are already landed.

Evidence:
- `Chummer.Run.Api/Services/Community/CampaignSpineService.cs`
  - emits restore provenance receipts with `Surface`, `Authority`, `Proof`, and `RecoveryHint`
  - emits restore conflict receipts for inactive claims, stale claims, expired entitlements, status mismatches, orphan grants, missing grants, missing artifact receipts, and mixed rule-environment posture
- `Chummer.Run.Api/Services/Community/WorkspaceLifecyclePolicyService.cs`
  - preserves stable observation timestamps for unchanged restore provenance and conflict receipts
- `Chummer.Run.Api/Services/Community/CampaignWorkspaceServerPlaneService.cs`
  - projects restore receipts onto the workspace server plane with normalized `workspace_restore` and `entitlement_sync` surface classification
- `Chummer.Run.Api/Views/Accounts/Account.cshtml`
  - keeps the `Restore provenance and conflict receipts` drawer visible on the selected workspace surface
- `Chummer.Tests/CampaignSpineRestoreReceiptTests.cs`
  - covers authority-backed provenance, stale/inactive continuity conflicts, and reload persistence
- `Chummer.Tests/WorkspaceLifecyclePolicyServiceTests.cs`
  - covers stable observation timestamps across unchanged refreshes
- `Chummer.Tests/CampaignWorkspaceServerPlaneServiceTests.cs`
  - covers receipt projection surface normalization

Verification:
- Command:
  - `dotnet test /docker/chummercomplete/chummer.run-services/Chummer.Tests/Chummer.Tests.csproj --filter "CampaignSpineRestoreReceiptTests|WorkspaceLifecyclePolicyServiceTests|CampaignWorkspaceServerPlaneServiceTests"`
- Result:
  - passed on `2026-04-14`
  - `405` passed, `0` failed, `0` skipped on `net10.0`
  - `405` passed, `0` failed, `0` skipped on `net10.0-windows`

Release truth blocker:
- `/docker/fleet/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json` still reports the only unresolved flagship blocker as external host proof for `avalonia:osx-arm64:macos`.
- This worker pass did not refresh readiness truth because no new local repo state changed and the remaining blocker is still the missing macOS proof lane.
