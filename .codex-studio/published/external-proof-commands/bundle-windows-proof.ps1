$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

bash -lc 'set -euo pipefail
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="${CHUMMER_UI_REPO_ROOT:-/docker/chummercomplete/chummer6-ui}" && export REPO_ROOT && if [ -z "${CHUMMER_UI_REPO_ROOT:-}" ] && [ ! -d "$REPO_ROOT" ]; then for candidate in /docker/chummercomplete/chummer6-ui /docker/chummercomplete/chummer6-ui-finish /docker/chummercomplete/chummer-presentation; do if [ -d "$candidate" ]; then REPO_ROOT="$candidate" && export REPO_ROOT && break; fi; done; fi && DOWNLOADS_ROOT="$REPO_ROOT/Docker/Downloads" && export DOWNLOADS_ROOT
BUNDLE_ROOT="$SCRIPT_DIR/host-proof-bundles/windows"
BUNDLE_ARCHIVE="$SCRIPT_DIR/windows-proof-bundle.tgz"
export BUNDLE_ROOT
export BUNDLE_ARCHIVE
rm -rf "$BUNDLE_ROOT"
mkdir -p "$BUNDLE_ROOT"
rm -f "$BUNDLE_ARCHIVE"
python3 -c ''import json, os, pathlib; bundle_root=pathlib.Path(os.environ[''"''"''BUNDLE_ROOT''"''"'']); payload=json.loads(''"''"''{"host": "windows", "request_count": 1, "requests": [{"expected_installer_bundle_relative_path": "files/chummer-avalonia-win-x64-installer.exe", "expected_installer_sha256": "54966da8ac6f1ca7321b301b025bfb626398f461c78441c132d5c59d9c2bedde", "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json", "tuple_id": "avalonia:win-x64:windows"}], "schema_version": 1}''"''"''); manifest_path=bundle_root / ''"''"''external-proof-manifest.json''"''"''; manifest_path.write_text(json.dumps(payload, sort_keys=True, indent=2) + ''"''"''\n''"''"'', encoding=''"''"''utf-8''"''"'')''
mkdir -p "$BUNDLE_ROOT/files"
cp -f "$DOWNLOADS_ROOT/files/chummer-avalonia-win-x64-installer.exe" "$BUNDLE_ROOT/files/chummer-avalonia-win-x64-installer.exe"
mkdir -p "$BUNDLE_ROOT/startup-smoke"
cp -f "$DOWNLOADS_ROOT/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json" "$BUNDLE_ROOT/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json"
tar -czf "$BUNDLE_ARCHIVE" -C "$BUNDLE_ROOT" .
echo "Wrote $BUNDLE_ARCHIVE"'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
exit 0
