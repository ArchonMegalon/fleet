$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

bash -lc 'cd /docker/chummercomplete/chummer6-ui && mkdir -p /docker/chummercomplete/chummer6-ui/Docker/Downloads/files && if [ ! -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe ]; then curl -fL --retry 3 --retry-delay 2 "${CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}/downloads/install/avalonia-win-x64-installer" -o /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe; fi'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=Windows ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe avalonia win-x64 Chummer.Avalonia.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'cd /docker/chummercomplete/chummer6-ui && mkdir -p /docker/chummercomplete/chummer6-ui/Docker/Downloads/files && if [ ! -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-win-x64-installer.exe ]; then curl -fL --retry 3 --retry-delay 2 "${CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}/downloads/install/blazor-desktop-win-x64-installer" -o /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-win-x64-installer.exe; fi'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=Windows ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-win-x64-installer.exe blazor-desktop win-x64 Chummer.Blazor.Desktop.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
exit 0
