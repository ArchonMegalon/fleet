#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE_ROOT="$SCRIPT_DIR/host-proof-bundles/linux"
rm -rf "$BUNDLE_ROOT"
mkdir -p "$BUNDLE_ROOT"
mkdir -p '$BUNDLE_ROOT/files'
cp -f /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-linux-x64-installer.deb '$BUNDLE_ROOT/files/chummer-blazor-desktop-linux-x64-installer.deb'
mkdir -p '$BUNDLE_ROOT/startup-smoke'
cp -f /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-blazor-desktop-linux-x64.receipt.json '$BUNDLE_ROOT/startup-smoke/startup-smoke-blazor-desktop-linux-x64.receipt.json'
tar -czf "$SCRIPT_DIR/linux-proof-bundle.tgz" -C "$BUNDLE_ROOT" .
echo "Wrote $SCRIPT_DIR/linux-proof-bundle.tgz"
