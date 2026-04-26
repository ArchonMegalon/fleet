$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

bash -lc 'set -euo pipefail
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
python3 -c ''import os, pathlib, shutil
bundle_dir=pathlib.Path(os.environ[''"''"''BUNDLE_DIR''"''"''])
target_root=pathlib.Path(os.environ[''"''"''TARGET_ROOT''"''"''])
bad=[]
copied=[]
for source in sorted(bundle_dir.rglob(''"''"''*''"''"'')):
    if source.is_dir():
        continue
    relative=source.relative_to(bundle_dir)
    if source.is_symlink() or any(part in (''"''"''..''"''"'', ''"''"''''"''"'') for part in relative.parts):
        bad.append(str(relative))
        continue
    destination=target_root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    copied.append(str(relative))
assert not bad, ''"''"''external-proof-bundle-path-unsafe:''"''"'' + ''"''"'',''"''"''.join(sorted(set(bad)))
assert copied, ''"''"''external-proof-bundle-empty:''"''"'' + str(bundle_dir)''
else
python3 -c ''import os, pathlib, shutil, tarfile
bundle=pathlib.Path(os.environ[''"''"''BUNDLE_ARCHIVE''"''"''])
target_root=pathlib.Path(os.environ[''"''"''TARGET_ROOT''"''"''])
target_root.mkdir(parents=True, exist_ok=True)
target_root_resolved=target_root.resolve()
bad=[]
copied=[]
with tarfile.open(bundle, ''"''"''r:gz''"''"'') as archive:
    for member in archive.getmembers():
        pure=pathlib.PurePosixPath(member.name)
        parts=tuple(part for part in pure.parts if part not in (''"''"''''"''"'', ''"''"''.''"''"''))
        if member.name.startswith(''"''"''/''"''"'') or ''"''"''..''"''"'' in parts or not member.isfile():
            bad.append(member.name)
            continue
        destination=target_root.joinpath(*parts)
        destination_parent=destination.parent.resolve()
        if target_root_resolved != destination_parent and target_root_resolved not in destination_parent.parents:
            bad.append(member.name)
            continue
        source=archive.extractfile(member)
        if source is None:
            bad.append(member.name)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        with source, destination.open(''"''"''wb''"''"'') as handle:
            shutil.copyfileobj(source, handle)
        copied.append(''"''"''/''"''"''.join(parts))
assert not bad, ''"''"''external-proof-bundle-member-unsafe:''"''"'' + ''"''"'',''"''"''.join(sorted(set(bad)))
assert copied, ''"''"''external-proof-bundle-empty:''"''"'' + str(bundle)''
fi
python3 -c ''import os, json, pathlib; manifest_path=pathlib.Path(os.environ[''"''"''TARGET_ROOT''"''"'']) / ''"''"''external-proof-manifest.json''"''"''; expected=json.loads(''"''"''{"host": "windows", "request_count": 0, "requests": [], "schema_version": 1}''"''"''); assert manifest_path.is_file(), ''"''"''external-proof-bundle-manifest-missing:''"''"'' + str(manifest_path); payload=json.loads(manifest_path.read_text(encoding=''"''"''utf-8''"''"'')); assert payload == expected, ''"''"''external-proof-bundle-manifest-mismatch:''"''"'' + str(manifest_path) + ''"''"'':expected=''"''"'' + json.dumps(expected, sort_keys=True) + ''"''"'':actual=''"''"'' + json.dumps(payload, sort_keys=True)''
echo ''No expected host proof files were queued for ingest.'''
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
exit 0
