#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE_ARCHIVE="$SCRIPT_DIR/windows-proof-bundle.tgz"
TARGET_ROOT=/docker/chummercomplete/chummer6-ui/Docker/Downloads
if [ ! -s "$BUNDLE_ARCHIVE" ]; then
  echo "Missing host proof bundle: $BUNDLE_ARCHIVE"
  exit 1
fi
python3 -c 'import pathlib, tarfile; bundle=pathlib.Path(__import__('"'"'os'"'"').environ['"'"'BUNDLE_ARCHIVE'"'"']); bad=[]; with tarfile.open(bundle, '"'"'r:gz'"'"') as t:   for member in t.getmembers():     parts=pathlib.PurePosixPath(member.name).parts;     if member.name.startswith('"'"'/'"'"') or '"'"'..'"'"' in parts:       bad.append(member.name); if bad:   raise SystemExit('"'"'external-proof-bundle-path-unsafe:'"'"' + '"'"','"'"'.join(sorted(set(bad))))'
mkdir -p "$TARGET_ROOT"
tar -xzf "$BUNDLE_ARCHIVE" -C "$TARGET_ROOT"
test -s '$TARGET_ROOT/files/chummer-avalonia-win-x64-installer.exe'
test -s '$TARGET_ROOT/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json'
test -s '$TARGET_ROOT/files/chummer-blazor-desktop-win-x64-installer.exe'
test -s '$TARGET_ROOT/startup-smoke/startup-smoke-blazor-desktop-win-x64.receipt.json'
echo "Host proof bundle ingest complete: $BUNDLE_ARCHIVE"
