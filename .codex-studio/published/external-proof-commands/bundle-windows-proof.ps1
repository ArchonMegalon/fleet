$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

bash -lc 'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'BUNDLE_ROOT="$SCRIPT_DIR/host-proof-bundles/windows"'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'rm -rf "$BUNDLE_ROOT"'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'mkdir -p "$BUNDLE_ROOT"'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'mkdir -p ''$BUNDLE_ROOT/files'''
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'cp -f /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe ''$BUNDLE_ROOT/files/chummer-avalonia-win-x64-installer.exe'''
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'mkdir -p ''$BUNDLE_ROOT/startup-smoke'''
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'cp -f /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json ''$BUNDLE_ROOT/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json'''
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'mkdir -p ''$BUNDLE_ROOT/files'''
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'cp -f /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-win-x64-installer.exe ''$BUNDLE_ROOT/files/chummer-blazor-desktop-win-x64-installer.exe'''
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'mkdir -p ''$BUNDLE_ROOT/startup-smoke'''
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'cp -f /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-blazor-desktop-win-x64.receipt.json ''$BUNDLE_ROOT/startup-smoke/startup-smoke-blazor-desktop-win-x64.receipt.json'''
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'tar -czf "$SCRIPT_DIR/windows-proof-bundle.tgz" -C "$BUNDLE_ROOT" .'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'echo "Wrote $SCRIPT_DIR/windows-proof-bundle.tgz"'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
exit 0
