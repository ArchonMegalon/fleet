#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE_ROOT="$SCRIPT_DIR/host-proof-bundles/macos"
export BUNDLE_ROOT
rm -rf "$BUNDLE_ROOT"
mkdir -p "$BUNDLE_ROOT"
python3 -c 'import json, os, pathlib; bundle_root=pathlib.Path(os.environ['"'"'BUNDLE_ROOT'"'"']); payload=json.loads('"'"'{"host": "macos", "request_count": 2, "requests": [{"expected_installer_bundle_relative_path": "files/chummer-avalonia-osx-arm64-installer.dmg", "expected_installer_sha256": "086e7c0f2c55da5a3932c324f54b3bd98fabe6dc7715553406c3c9a74f24f89a", "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json", "tuple_id": "avalonia:osx-arm64:macos"}, {"expected_installer_bundle_relative_path": "files/chummer-blazor-desktop-osx-arm64-installer.dmg", "expected_installer_sha256": "19af740fb995ee5dff0c5c7a4e601159d8779ce08b4ce47ae3b0db7f796cd581", "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-blazor-desktop-osx-arm64.receipt.json", "tuple_id": "blazor-desktop:osx-arm64:macos"}], "schema_version": 1}'"'"'); manifest_path=bundle_root / '"'"'external-proof-manifest.json'"'"'; manifest_path.write_text(json.dumps(payload, sort_keys=True, indent=2) + '"'"'\n'"'"', encoding='"'"'utf-8'"'"')'
mkdir -p "$BUNDLE_ROOT/files"
cp -f /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg "$BUNDLE_ROOT/files/chummer-avalonia-osx-arm64-installer.dmg"
mkdir -p "$BUNDLE_ROOT/startup-smoke"
cp -f /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json "$BUNDLE_ROOT/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json"
mkdir -p "$BUNDLE_ROOT/files"
cp -f /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-osx-arm64-installer.dmg "$BUNDLE_ROOT/files/chummer-blazor-desktop-osx-arm64-installer.dmg"
mkdir -p "$BUNDLE_ROOT/startup-smoke"
cp -f /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-blazor-desktop-osx-arm64.receipt.json "$BUNDLE_ROOT/startup-smoke/startup-smoke-blazor-desktop-osx-arm64.receipt.json"
tar -czf "$SCRIPT_DIR/macos-proof-bundle.tgz" -C "$BUNDLE_ROOT" .
echo "Wrote $SCRIPT_DIR/macos-proof-bundle.tgz"
