#!/bin/sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="${CHUMMER_UI_REPO_ROOT:-/docker/chummercomplete/chummer6-ui}" && export REPO_ROOT && if [ -z "${CHUMMER_UI_REPO_ROOT:-}" ] && [ ! -d "$REPO_ROOT" ]; then for candidate in /docker/chummercomplete/chummer6-ui /docker/chummercomplete/chummer6-ui-finish /docker/chummercomplete/chummer-presentation; do if [ -d "$candidate" ]; then REPO_ROOT="$candidate" && export REPO_ROOT && break; fi; done; fi && DOWNLOADS_ROOT="$REPO_ROOT/Docker/Downloads" && export DOWNLOADS_ROOT
BUNDLE_ROOT="$SCRIPT_DIR/host-proof-bundles/macos"
BUNDLE_ARCHIVE="$SCRIPT_DIR/macos-proof-bundle.tgz"
export BUNDLE_ROOT
export BUNDLE_ARCHIVE
rm -rf "$BUNDLE_ROOT"
mkdir -p "$BUNDLE_ROOT"
rm -f "$BUNDLE_ARCHIVE"
python3 -c 'import json, os, pathlib; bundle_root=pathlib.Path(os.environ['"'"'BUNDLE_ROOT'"'"']); payload=json.loads('"'"'{"host": "macos", "request_count": 1, "requests": [{"expected_installer_bundle_relative_path": "files/chummer-avalonia-osx-arm64-installer.dmg", "expected_installer_sha256": "c82393b1bcff3897faf2ea9255e8775ccc1cefa512b3e16a7cb06e52ba48b07e", "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json", "tuple_id": "avalonia:osx-arm64:macos"}], "schema_version": 1}'"'"'); manifest_path=bundle_root / '"'"'external-proof-manifest.json'"'"'; manifest_path.write_text(json.dumps(payload, sort_keys=True, indent=2) + '"'"'\n'"'"', encoding='"'"'utf-8'"'"')'
mkdir -p "$BUNDLE_ROOT/files"
cp -f "$DOWNLOADS_ROOT/files/chummer-avalonia-osx-arm64-installer.dmg" "$BUNDLE_ROOT/files/chummer-avalonia-osx-arm64-installer.dmg"
mkdir -p "$BUNDLE_ROOT/startup-smoke"
cp -f "$DOWNLOADS_ROOT/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json" "$BUNDLE_ROOT/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json"
tar -czf "$BUNDLE_ARCHIVE" -C "$BUNDLE_ROOT" .
echo "Wrote $BUNDLE_ARCHIVE"
