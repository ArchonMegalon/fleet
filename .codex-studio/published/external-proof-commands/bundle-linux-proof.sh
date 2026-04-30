#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${CHUMMER_UI_REPO_ROOT:-/docker/chummercomplete/chummer6-ui}" && export REPO_ROOT && DOWNLOADS_ROOT="$REPO_ROOT/Docker/Downloads" && export DOWNLOADS_ROOT
BUNDLE_ROOT="$SCRIPT_DIR/host-proof-bundles/linux"
BUNDLE_ARCHIVE="$SCRIPT_DIR/linux-proof-bundle.tgz"
export BUNDLE_ROOT
export BUNDLE_ARCHIVE
rm -rf "$BUNDLE_ROOT"
mkdir -p "$BUNDLE_ROOT"
rm -f "$BUNDLE_ARCHIVE"
python3 -c 'import json, os, pathlib; bundle_root=pathlib.Path(os.environ['"'"'BUNDLE_ROOT'"'"']); payload=json.loads('"'"'{"host": "linux", "request_count": 1, "requests": [{"expected_installer_bundle_relative_path": "files/chummer-avalonia-linux-x64-installer.deb", "expected_installer_sha256": "84d5c3a7065666286c5e3a5feccbc2ee3c04117cf5afaa116c09e1e2d9e44643", "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-linux-x64.receipt.json", "tuple_id": "avalonia:linux-x64:linux"}], "schema_version": 1}'"'"'); manifest_path=bundle_root / '"'"'external-proof-manifest.json'"'"'; manifest_path.write_text(json.dumps(payload, sort_keys=True, indent=2) + '"'"'\n'"'"', encoding='"'"'utf-8'"'"')'
mkdir -p "$BUNDLE_ROOT/files"
cp -f "$DOWNLOADS_ROOT/files/chummer-avalonia-linux-x64-installer.deb" "$BUNDLE_ROOT/files/chummer-avalonia-linux-x64-installer.deb"
mkdir -p "$BUNDLE_ROOT/startup-smoke"
cp -f "$DOWNLOADS_ROOT/startup-smoke/startup-smoke-avalonia-linux-x64.receipt.json" "$BUNDLE_ROOT/startup-smoke/startup-smoke-avalonia-linux-x64.receipt.json"
tar -czf "$BUNDLE_ARCHIVE" -C "$BUNDLE_ROOT" .
echo "Wrote $BUNDLE_ARCHIVE"
