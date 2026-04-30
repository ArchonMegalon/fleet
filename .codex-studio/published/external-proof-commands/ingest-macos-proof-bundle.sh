#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE_ARCHIVE="$SCRIPT_DIR/macos-proof-bundle.tgz"
BUNDLE_DIR="$SCRIPT_DIR/host-proof-bundles/macos"
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
  python3 -c 'import os, pathlib, shutil, tarfile
bundle=pathlib.Path(os.environ['"'"'BUNDLE_ARCHIVE'"'"'])
target_root=pathlib.Path(os.environ['"'"'TARGET_ROOT'"'"'])
target_root.mkdir(parents=True, exist_ok=True)
target_root_resolved=target_root.resolve()
bad=[]
copied=[]
with tarfile.open(bundle, '"'"'r:gz'"'"') as archive:
    for member in archive.getmembers():
        pure=pathlib.PurePosixPath(member.name)
        parts=tuple(part for part in pure.parts if part not in ('"'"''"'"', '"'"'.'"'"'))
        if member.name.startswith('"'"'/'"'"') or '"'"'..'"'"' in parts or not member.isfile():
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
        with source, destination.open('"'"'wb'"'"') as handle:
            shutil.copyfileobj(source, handle)
        copied.append('"'"'/'"'"'.join(parts))
assert not bad, '"'"'external-proof-bundle-member-unsafe:'"'"' + '"'"','"'"'.join(sorted(set(bad)))
assert copied, '"'"'external-proof-bundle-empty:'"'"' + str(bundle)'
fi
python3 -c 'import os, json, pathlib; manifest_path=pathlib.Path(os.environ['"'"'TARGET_ROOT'"'"']) / '"'"'external-proof-manifest.json'"'"'; expected=json.loads('"'"'{"host": "macos", "request_count": 1, "requests": [{"expected_installer_bundle_relative_path": "files/chummer-avalonia-osx-arm64-installer.dmg", "expected_installer_sha256": "ca6c25f0cdaf48bddfe83e3e983ff87b8763d973e671100165248c9edcd044bd", "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json", "tuple_id": "avalonia:osx-arm64:macos"}], "schema_version": 1}'"'"'); assert manifest_path.is_file(), '"'"'external-proof-bundle-manifest-missing:'"'"' + str(manifest_path); payload=json.loads(manifest_path.read_text(encoding='"'"'utf-8'"'"')); assert payload == expected, '"'"'external-proof-bundle-manifest-mismatch:'"'"' + str(manifest_path) + '"'"':expected='"'"' + json.dumps(expected, sort_keys=True) + '"'"':actual='"'"' + json.dumps(payload, sort_keys=True)'
test -s "$TARGET_ROOT/files/chummer-avalonia-osx-arm64-installer.dmg"
test -s "$TARGET_ROOT/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json"
python3 -c 'import hashlib, os, pathlib; target_root=pathlib.Path(os.environ['"'"'TARGET_ROOT'"'"']); tuple_id='"'"'avalonia:osx-arm64:macos'"'"'; relative='"'"'files/chummer-avalonia-osx-arm64-installer.dmg'"'"'; expected='"'"'ca6c25f0cdaf48bddfe83e3e983ff87b8763d973e671100165248c9edcd044bd'"'"'; path=target_root / relative; assert path.is_file(), f'"'"'external-proof-bundle-installer-missing:{tuple_id}:{path}'"'"'; digest=hashlib.sha256(path.read_bytes()).hexdigest().lower(); assert digest==expected, f'"'"'installer-contract-mismatch:{tuple_id}:{path}:digest={digest}:expected={expected}'"'"''
python3 -c 'import datetime as dt, json, os, pathlib; target_root=pathlib.Path(os.environ['"'"'TARGET_ROOT'"'"']); relative='"'"'startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json'"'"'; max_age_seconds=604800; max_future_skew_seconds=300; path=target_root / relative; assert path.is_file(), '"'"'external-proof-bundle-receipt-missing:'"'"' + str(path); payload=json.loads(path.read_text(encoding='"'"'utf-8'"'"')); payload=payload if isinstance(payload, dict) else {}; raw=next((str(payload.get(key) or '"'"''"'"').strip() for key in ('"'"'recordedAtUtc'"'"','"'"'completedAtUtc'"'"','"'"'generatedAt'"'"','"'"'generated_at'"'"','"'"'startedAtUtc'"'"') if str(payload.get(key) or '"'"''"'"').strip()), '"'"''"'"'); assert raw, '"'"'startup-smoke-receipt-timestamp-missing:'"'"' + str(path); raw = raw[:-1] + '"'"'+00:00'"'"' if raw.endswith('"'"'Z'"'"') else raw; parsed=dt.datetime.fromisoformat(raw); parsed=parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=dt.timezone.utc); parsed=parsed.astimezone(dt.timezone.utc); now=dt.datetime.now(dt.timezone.utc); age_seconds=int((now-parsed).total_seconds()); assert age_seconds >= -max_future_skew_seconds, '"'"'startup-smoke-receipt-future-skew:'"'"' + str(path) + f'"'"':age_seconds={age_seconds}:max_future_skew_seconds={max_future_skew_seconds}'"'"'; age_seconds = 0 if age_seconds < 0 else age_seconds; assert age_seconds <= max_age_seconds, '"'"'startup-smoke-receipt-stale:'"'"' + str(path) + f'"'"':age_seconds={age_seconds}:max_age_seconds={max_age_seconds}'"'"''
python3 -c 'import json, os, pathlib; target_root=pathlib.Path(os.environ['"'"'TARGET_ROOT'"'"']); tuple_id='"'"'avalonia:osx-arm64:macos'"'"'; relative='"'"'startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json'"'"'; contract=json.loads('"'"'{"head_id": "avalonia", "host_class_contains": "macos", "platform": "macos", "ready_checkpoint": "pre_ui_event_loop", "rid": "osx-arm64", "status_any_of": ["pass", "passed", "ready"]}'"'"'); path=target_root / relative; assert path.is_file(), f'"'"'external-proof-bundle-receipt-missing:{tuple_id}:{path}'"'"'; payload=json.loads(path.read_text(encoding='"'"'utf-8'"'"')); payload=payload if isinstance(payload, dict) else {}; status=str(payload.get('"'"'status'"'"') or '"'"''"'"').strip().lower(); expected_statuses=[str(token).strip().lower() for token in (contract.get('"'"'status_any_of'"'"') or []) if str(token).strip()]; head_id=str(payload.get('"'"'headId'"'"') or '"'"''"'"').strip().lower(); platform=str(payload.get('"'"'platform'"'"') or '"'"''"'"').strip().lower(); rid=str(payload.get('"'"'rid'"'"') or '"'"''"'"').strip().lower(); ready_checkpoint=str(payload.get('"'"'readyCheckpoint'"'"') or '"'"''"'"').strip().lower(); host_class=str(payload.get('"'"'hostClass'"'"') or '"'"''"'"').strip().lower(); expected_head=str(contract.get('"'"'head_id'"'"') or '"'"''"'"').strip().lower(); expected_platform=str(contract.get('"'"'platform'"'"') or '"'"''"'"').strip().lower(); expected_rid=str(contract.get('"'"'rid'"'"') or '"'"''"'"').strip().lower(); expected_ready=str(contract.get('"'"'ready_checkpoint'"'"') or '"'"''"'"').strip().lower(); expected_host_contains=str(contract.get('"'"'host_class_contains'"'"') or '"'"''"'"').strip().lower(); assert ((not expected_statuses or status in expected_statuses) and (not expected_head or head_id == expected_head) and (not expected_platform or platform == expected_platform) and (not expected_rid or rid == expected_rid) and (not expected_ready or ready_checkpoint == expected_ready) and (not expected_host_contains or expected_host_contains in host_class), f'"'"'receipt-contract-mismatch:{tuple_id}:{path}:status={status}:head={head_id}:platform={platform}:rid={rid}:ready={ready_checkpoint}:host_class={host_class}:contract={contract}'"'"')'
echo "Host proof bundle ingest complete: $BUNDLE_ARCHIVE"
