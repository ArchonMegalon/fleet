#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE_ARCHIVE="$SCRIPT_DIR/windows-proof-bundle.tgz"
BUNDLE_DIR="$SCRIPT_DIR/host-proof-bundles/windows"
export BUNDLE_ARCHIVE
export BUNDLE_DIR
TARGET_ROOT=/docker/chummercomplete/chummer6-ui/Docker/Downloads
export TARGET_ROOT
mkdir -p "$TARGET_ROOT"
if [ ! -s "$BUNDLE_ARCHIVE" ]; then
  if [ ! -d "$BUNDLE_DIR" ]; then
    echo "Missing host proof bundle: $BUNDLE_ARCHIVE or $BUNDLE_DIR"
    exit 1
  fi
fi
if [ ! -s "$BUNDLE_ARCHIVE" ]; then
  python3 -c 'import os, pathlib, shutil
bundle_dir=pathlib.Path(os.environ['"'"'BUNDLE_DIR'"'"'])
target_root=pathlib.Path(os.environ['"'"'TARGET_ROOT'"'"'])
bad=[]
copied=[]
for source in sorted(bundle_dir.rglob('"'"'*'"'"')):
    if source.is_dir():
        continue
    relative=source.relative_to(bundle_dir)
    if source.is_symlink() or any(part in ('"'"'..'"'"', '"'"''"'"') for part in relative.parts):
        bad.append(str(relative))
        continue
    destination=target_root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    copied.append(str(relative))
assert not bad, '"'"'external-proof-bundle-path-unsafe:'"'"' + '"'"','"'"'.join(sorted(set(bad)))
assert copied, '"'"'external-proof-bundle-empty:'"'"' + str(bundle_dir)'
else
  python3 -c 'import os, pathlib, tarfile; bundle=pathlib.Path(os.environ['"'"'BUNDLE_ARCHIVE'"'"']); members=tarfile.open(bundle, '"'"'r:gz'"'"').getmembers(); bad=[member.name for member in members if member.name.startswith('"'"'/'"'"') or '"'"'..'"'"' in pathlib.PurePosixPath(member.name).parts]; assert not any('"'"'..'"'"' in parts for parts in [pathlib.PurePosixPath(member.name).parts for member in members]), '"'"'external-proof-bundle-path-unsafe:'"'"' + '"'"','"'"'.join(sorted(set(bad)))'
  tar -xzf "$BUNDLE_ARCHIVE" -C "$TARGET_ROOT"
fi
python3 -c 'import os, json, pathlib; manifest_path=pathlib.Path(os.environ['"'"'TARGET_ROOT'"'"']) / '"'"'external-proof-manifest.json'"'"'; expected=json.loads('"'"'{"host": "windows", "request_count": 0, "requests": [], "schema_version": 1}'"'"'); assert manifest_path.is_file(), '"'"'external-proof-bundle-manifest-missing:'"'"' + str(manifest_path); payload=json.loads(manifest_path.read_text(encoding='"'"'utf-8'"'"')); assert payload == expected, '"'"'external-proof-bundle-manifest-mismatch:'"'"' + str(manifest_path) + '"'"':expected='"'"' + json.dumps(expected, sort_keys=True) + '"'"':actual='"'"' + json.dumps(payload, sort_keys=True)'
echo 'No expected host proof files were queued for ingest.'
