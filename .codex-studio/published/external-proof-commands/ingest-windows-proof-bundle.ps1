$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

bash -lc 'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'BUNDLE_ARCHIVE="$SCRIPT_DIR/windows-proof-bundle.tgz"'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'TARGET_ROOT=/docker/chummercomplete/chummer6-ui/Docker/Downloads'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'if [ ! -s "$BUNDLE_ARCHIVE" ]; then'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'echo "Missing host proof bundle: $BUNDLE_ARCHIVE"'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'exit 1'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'fi'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'python3 -c ''import pathlib, tarfile; bundle=pathlib.Path(__import__(''"''"''os''"''"'').environ[''"''"''BUNDLE_ARCHIVE''"''"'']); bad=[]; with tarfile.open(bundle, ''"''"''r:gz''"''"'') as t:   for member in t.getmembers():     parts=pathlib.PurePosixPath(member.name).parts;     if member.name.startswith(''"''"''/''"''"'') or ''"''"''..''"''"'' in parts:       bad.append(member.name); if bad:   raise SystemExit(''"''"''external-proof-bundle-path-unsafe:''"''"'' + ''"''"'',''"''"''.join(sorted(set(bad))))'''
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'mkdir -p "$TARGET_ROOT"'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'tar -xzf "$BUNDLE_ARCHIVE" -C "$TARGET_ROOT"'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'test -s ''$TARGET_ROOT/files/chummer-avalonia-win-x64-installer.exe'''
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'test -s ''$TARGET_ROOT/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json'''
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'test -s ''$TARGET_ROOT/files/chummer-blazor-desktop-win-x64-installer.exe'''
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'test -s ''$TARGET_ROOT/startup-smoke/startup-smoke-blazor-desktop-win-x64.receipt.json'''
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'echo "Host proof bundle ingest complete: $BUNDLE_ARCHIVE"'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
exit 0
