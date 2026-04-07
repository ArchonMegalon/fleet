#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE_ROOT="$SCRIPT_DIR/host-proof-bundles/windows"
export BUNDLE_ROOT
rm -rf "$BUNDLE_ROOT"
mkdir -p "$BUNDLE_ROOT"
python3 -c 'import json, os, pathlib; bundle_root=pathlib.Path(os.environ['"'"'BUNDLE_ROOT'"'"']); payload=json.loads('"'"'{"host": "windows", "request_count": 2, "requests": [{"expected_installer_bundle_relative_path": "files/chummer-avalonia-win-x64-installer.exe", "expected_installer_sha256": "529a427c84a36082fe66d09a4547b17bd6c5046d2e4586277c5b7cd0c83ab00f", "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json", "tuple_id": "avalonia:win-x64:windows"}, {"expected_installer_bundle_relative_path": "files/chummer-blazor-desktop-win-x64-installer.exe", "expected_installer_sha256": "bc960d8d8081bd3e661b6f7ac281ee08879a5eeb007d45ec0bdfb9a98f188499", "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-blazor-desktop-win-x64.receipt.json", "tuple_id": "blazor-desktop:win-x64:windows"}], "schema_version": 1}'"'"'); manifest_path=bundle_root / '"'"'external-proof-manifest.json'"'"'; manifest_path.write_text(json.dumps(payload, sort_keys=True, indent=2) + '"'"'\n'"'"', encoding='"'"'utf-8'"'"')'
mkdir -p "$BUNDLE_ROOT/files"
cp -f /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe "$BUNDLE_ROOT/files/chummer-avalonia-win-x64-installer.exe"
mkdir -p "$BUNDLE_ROOT/startup-smoke"
cp -f /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json "$BUNDLE_ROOT/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json"
mkdir -p "$BUNDLE_ROOT/files"
cp -f /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-win-x64-installer.exe "$BUNDLE_ROOT/files/chummer-blazor-desktop-win-x64-installer.exe"
mkdir -p "$BUNDLE_ROOT/startup-smoke"
cp -f /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-blazor-desktop-win-x64.receipt.json "$BUNDLE_ROOT/startup-smoke/startup-smoke-blazor-desktop-win-x64.receipt.json"
tar -czf "$SCRIPT_DIR/windows-proof-bundle.tgz" -C "$BUNDLE_ROOT" .
echo "Wrote $SCRIPT_DIR/windows-proof-bundle.tgz"
