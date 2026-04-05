#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE_ROOT="$SCRIPT_DIR/host-proof-bundles/macos"
rm -rf "$BUNDLE_ROOT"
mkdir -p "$BUNDLE_ROOT"
mkdir -p '$BUNDLE_ROOT/files'
cp -f /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg '$BUNDLE_ROOT/files/chummer-avalonia-osx-arm64-installer.dmg'
mkdir -p '$BUNDLE_ROOT/startup-smoke'
cp -f /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json '$BUNDLE_ROOT/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json'
mkdir -p '$BUNDLE_ROOT/files'
cp -f /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-osx-arm64-installer.dmg '$BUNDLE_ROOT/files/chummer-blazor-desktop-osx-arm64-installer.dmg'
mkdir -p '$BUNDLE_ROOT/startup-smoke'
cp -f /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-blazor-desktop-osx-arm64.receipt.json '$BUNDLE_ROOT/startup-smoke/startup-smoke-blazor-desktop-osx-arm64.receipt.json'
tar -czf "$SCRIPT_DIR/macos-proof-bundle.tgz" -C "$BUNDLE_ROOT" .
echo "Wrote $SCRIPT_DIR/macos-proof-bundle.tgz"
