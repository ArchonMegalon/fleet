$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

bash -lc 'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'REPO_ROOT="${CHUMMER_UI_REPO_ROOT:-/docker/chummercomplete/chummer6-ui}" && export REPO_ROOT && DOWNLOADS_ROOT="$REPO_ROOT/Docker/Downloads" && export DOWNLOADS_ROOT'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'BUNDLE_ROOT="$SCRIPT_DIR/host-proof-bundles/windows"'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'BUNDLE_ARCHIVE="$SCRIPT_DIR/windows-proof-bundle.tgz"'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'export BUNDLE_ROOT'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'export BUNDLE_ARCHIVE'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'rm -rf "$BUNDLE_ROOT"'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'mkdir -p "$BUNDLE_ROOT"'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'rm -f "$BUNDLE_ARCHIVE"'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'python3 -c ''import json, os, pathlib; bundle_root=pathlib.Path(os.environ[''"''"''BUNDLE_ROOT''"''"'']); payload=json.loads(''"''"''{"host": "windows", "request_count": 0, "requests": [], "schema_version": 1}''"''"''); manifest_path=bundle_root / ''"''"''external-proof-manifest.json''"''"''; manifest_path.write_text(json.dumps(payload, sort_keys=True, indent=2) + ''"''"''\n''"''"'', encoding=''"''"''utf-8''"''"'')'''
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'echo ''No host proof files were queued for bundling.'''
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'tar -czf "$BUNDLE_ARCHIVE" -C "$BUNDLE_ROOT" .'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'echo "Wrote $BUNDLE_ARCHIVE"'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
exit 0
