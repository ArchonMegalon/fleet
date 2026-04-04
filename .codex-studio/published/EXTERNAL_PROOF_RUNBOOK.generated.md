# External Proof Runbook

- generated_at: 2026-04-04T23:50:10Z
- unresolved_request_count: 4
- unresolved_hosts: macos, windows

## Host: macos

- request_count: 2
- tuples: avalonia:osx-arm64:macos, blazor-desktop:osx-arm64:macos

### Requested Tuples

- `avalonia:osx-arm64:macos`
  required_proofs: `promoted_installer_artifact, startup_smoke_receipt`
  artifact_id: `avalonia-osx-arm64-installer`
  installer_file: `chummer-avalonia-osx-arm64-installer.dmg`
  public_route: `/downloads/install/avalonia-osx-arm64-installer`
  startup_smoke_receipt: `startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json`
- `blazor-desktop:osx-arm64:macos`
  required_proofs: `promoted_installer_artifact, startup_smoke_receipt`
  artifact_id: `blazor-desktop-osx-arm64-installer`
  installer_file: `chummer-blazor-desktop-osx-arm64-installer.dmg`
  public_route: `/downloads/install/blazor-desktop-osx-arm64-installer`
  startup_smoke_receipt: `startup-smoke/startup-smoke-blazor-desktop-osx-arm64.receipt.json`

### Commands

```bash
cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=macos-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg avalonia osx-arm64 Chummer.Avalonia /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke
cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh
cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=macos-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-osx-arm64-installer.dmg blazor-desktop osx-arm64 Chummer.Blazor.Desktop /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke
```

## Host: windows

- request_count: 2
- tuples: avalonia:win-x64:windows, blazor-desktop:win-x64:windows

### Requested Tuples

- `avalonia:win-x64:windows`
  required_proofs: `promoted_installer_artifact, startup_smoke_receipt`
  artifact_id: `avalonia-win-x64-installer`
  installer_file: `chummer-avalonia-win-x64-installer.exe`
  public_route: `/downloads/install/avalonia-win-x64-installer`
  startup_smoke_receipt: `startup-smoke/startup-smoke-avalonia-win-x64.receipt.json`
- `blazor-desktop:win-x64:windows`
  required_proofs: `promoted_installer_artifact, startup_smoke_receipt`
  artifact_id: `blazor-desktop-win-x64-installer`
  installer_file: `chummer-blazor-desktop-win-x64-installer.exe`
  public_route: `/downloads/install/blazor-desktop-win-x64-installer`
  startup_smoke_receipt: `startup-smoke/startup-smoke-blazor-desktop-win-x64.receipt.json`

### Commands

```bash
cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe avalonia win-x64 Chummer.Avalonia.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke
cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh
cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-win-x64-installer.exe blazor-desktop win-x64 Chummer.Blazor.Desktop.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke
```
