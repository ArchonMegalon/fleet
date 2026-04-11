#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE_ROOT="$SCRIPT_DIR/host-proof-bundles/linux"
export BUNDLE_ROOT
rm -rf "$BUNDLE_ROOT"
mkdir -p "$BUNDLE_ROOT"
python3 -c 'import json, os, pathlib; bundle_root=pathlib.Path(os.environ['"'"'BUNDLE_ROOT'"'"']); payload=json.loads('"'"'{"host": "linux", "request_count": 2, "requests": [{"expected_installer_bundle_relative_path": "files/chummer-avalonia-linux-x64-installer.deb", "expected_installer_sha256": "", "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-linux-x64.receipt.json", "tuple_id": "avalonia:linux-x64:linux"}, {"expected_installer_bundle_relative_path": "files/chummer-blazor-desktop-linux-x64-installer.deb", "expected_installer_sha256": "", "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-blazor-desktop-linux-x64.receipt.json", "tuple_id": "blazor-desktop:linux-x64:linux"}], "schema_version": 1}'"'"'); manifest_path=bundle_root / '"'"'external-proof-manifest.json'"'"'; manifest_path.write_text(json.dumps(payload, sort_keys=True, indent=2) + '"'"'\n'"'"', encoding='"'"'utf-8'"'"')'
mkdir -p "$BUNDLE_ROOT/files"
cp -f /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-linux-x64-installer.deb "$BUNDLE_ROOT/files/chummer-avalonia-linux-x64-installer.deb"
mkdir -p "$BUNDLE_ROOT/startup-smoke"
cp -f /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-linux-x64.receipt.json "$BUNDLE_ROOT/startup-smoke/startup-smoke-avalonia-linux-x64.receipt.json"
mkdir -p "$BUNDLE_ROOT/files"
cp -f /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-linux-x64-installer.deb "$BUNDLE_ROOT/files/chummer-blazor-desktop-linux-x64-installer.deb"
mkdir -p "$BUNDLE_ROOT/startup-smoke"
cp -f /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-blazor-desktop-linux-x64.receipt.json "$BUNDLE_ROOT/startup-smoke/startup-smoke-blazor-desktop-linux-x64.receipt.json"
tar -czf "$SCRIPT_DIR/linux-proof-bundle.tgz" -C "$BUNDLE_ROOT" .
echo "Wrote $SCRIPT_DIR/linux-proof-bundle.tgz"
