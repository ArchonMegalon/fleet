# External Proof Runbook

- generated_at: 2026-04-05T05:09:38Z
- unresolved_request_count: 4
- unresolved_hosts: macos, windows
- plan_generated_at: 2026-04-05T05:04:40Z
- release_channel_generated_at: 2026-04-05T04:10:31Z
- capture_deadline_hours: 24
- capture_deadline_utc: 2026-04-06T04:10:31Z

## Generated Command Files

- commands_dir: `/docker/fleet/.codex-studio/published/external-proof-commands`
- host `macos`
  capture_script: `/docker/fleet/.codex-studio/published/external-proof-commands/capture-macos-proof.sh`
  validation_script: `/docker/fleet/.codex-studio/published/external-proof-commands/validate-macos-proof.sh`
  bundle_script: `/docker/fleet/.codex-studio/published/external-proof-commands/bundle-macos-proof.sh`
  ingest_script: `/docker/fleet/.codex-studio/published/external-proof-commands/ingest-macos-proof-bundle.sh`
- host `windows`
  capture_script: `/docker/fleet/.codex-studio/published/external-proof-commands/capture-windows-proof.sh`
  validation_script: `/docker/fleet/.codex-studio/published/external-proof-commands/validate-windows-proof.sh`
  bundle_script: `/docker/fleet/.codex-studio/published/external-proof-commands/bundle-windows-proof.sh`
  ingest_script: `/docker/fleet/.codex-studio/published/external-proof-commands/ingest-windows-proof-bundle.sh`
  capture_powershell: `/docker/fleet/.codex-studio/published/external-proof-commands/capture-windows-proof.ps1`
  validation_powershell: `/docker/fleet/.codex-studio/published/external-proof-commands/validate-windows-proof.ps1`
  bundle_powershell: `/docker/fleet/.codex-studio/published/external-proof-commands/bundle-windows-proof.ps1`
  ingest_powershell: `/docker/fleet/.codex-studio/published/external-proof-commands/ingest-windows-proof-bundle.ps1`
- post_capture_script: `/docker/fleet/.codex-studio/published/external-proof-commands/republish-after-host-proof.sh`

## Host: macos

- shell_hint: Run commands in a POSIX shell (bash/zsh) on the required host.
- request_count: 2
- tuples: avalonia:osx-arm64:macos, blazor-desktop:osx-arm64:macos

### Requested Tuples

- `avalonia:osx-arm64:macos`
  required_proofs: `promoted_installer_artifact, startup_smoke_receipt`
  artifact_id: `avalonia-osx-arm64-installer`
  installer_file: `chummer-avalonia-osx-arm64-installer.dmg`
  installer_relative_path: `files/chummer-avalonia-osx-arm64-installer.dmg`
  installer_sha256: `086e7c0f2c55da5a3932c324f54b3bd98fabe6dc7715553406c3c9a74f24f89a`
  public_route: `/downloads/install/avalonia-osx-arm64-installer`
  startup_smoke_receipt: `startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json`
  capture_deadline_utc: `2026-04-06T04:10:31Z`
  capture_deadline_state: `pending`
  commands:
    - `cd /docker/chummercomplete/chummer6-ui && mkdir -p /docker/chummercomplete/chummer6-ui/Docker/Downloads/files && python3 -c 'import hashlib, pathlib; p=pathlib.Path('"'"'/docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg'"'"'); expected='"'"'086e7c0f2c55da5a3932c324f54b3bd98fabe6dc7715553406c3c9a74f24f89a'"'"'; import sys; sys.exit(0) if (not p.is_file()) else None; digest=hashlib.sha256(p.read_bytes()).hexdigest().lower(); sys.exit(0) if digest==expected else print(f'"'"'installer-preflight-sha256-mismatch:{p}:digest={digest}:expected={expected}'"'"') or p.unlink()' && if [ ! -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg ]; then curl -fL --retry 3 --retry-delay 2 "${CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}/downloads/install/avalonia-osx-arm64-installer" -o /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg; fi`
    - `cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=macos-host CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=macOS ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg avalonia osx-arm64 Chummer.Avalonia /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke`
    - `cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh`
- `blazor-desktop:osx-arm64:macos`
  required_proofs: `promoted_installer_artifact, startup_smoke_receipt`
  artifact_id: `blazor-desktop-osx-arm64-installer`
  installer_file: `chummer-blazor-desktop-osx-arm64-installer.dmg`
  installer_relative_path: `files/chummer-blazor-desktop-osx-arm64-installer.dmg`
  installer_sha256: `19af740fb995ee5dff0c5c7a4e601159d8779ce08b4ce47ae3b0db7f796cd581`
  public_route: `/downloads/install/blazor-desktop-osx-arm64-installer`
  startup_smoke_receipt: `startup-smoke/startup-smoke-blazor-desktop-osx-arm64.receipt.json`
  capture_deadline_utc: `2026-04-06T04:10:31Z`
  capture_deadline_state: `pending`
  commands:
    - `cd /docker/chummercomplete/chummer6-ui && mkdir -p /docker/chummercomplete/chummer6-ui/Docker/Downloads/files && python3 -c 'import hashlib, pathlib; p=pathlib.Path('"'"'/docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-osx-arm64-installer.dmg'"'"'); expected='"'"'19af740fb995ee5dff0c5c7a4e601159d8779ce08b4ce47ae3b0db7f796cd581'"'"'; import sys; sys.exit(0) if (not p.is_file()) else None; digest=hashlib.sha256(p.read_bytes()).hexdigest().lower(); sys.exit(0) if digest==expected else print(f'"'"'installer-preflight-sha256-mismatch:{p}:digest={digest}:expected={expected}'"'"') or p.unlink()' && if [ ! -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-osx-arm64-installer.dmg ]; then curl -fL --retry 3 --retry-delay 2 "${CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}/downloads/install/blazor-desktop-osx-arm64-installer" -o /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-osx-arm64-installer.dmg; fi`
    - `cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=macos-host CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=macOS ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-osx-arm64-installer.dmg blazor-desktop osx-arm64 Chummer.Blazor.Desktop /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke`
    - `cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh`

### Commands (Host Consolidated)

```bash
cd /docker/chummercomplete/chummer6-ui && mkdir -p /docker/chummercomplete/chummer6-ui/Docker/Downloads/files && python3 -c 'import hashlib, pathlib; p=pathlib.Path('"'"'/docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg'"'"'); expected='"'"'086e7c0f2c55da5a3932c324f54b3bd98fabe6dc7715553406c3c9a74f24f89a'"'"'; import sys; sys.exit(0) if (not p.is_file()) else None; digest=hashlib.sha256(p.read_bytes()).hexdigest().lower(); sys.exit(0) if digest==expected else print(f'"'"'installer-preflight-sha256-mismatch:{p}:digest={digest}:expected={expected}'"'"') or p.unlink()' && if [ ! -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg ]; then curl -fL --retry 3 --retry-delay 2 "${CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}/downloads/install/avalonia-osx-arm64-installer" -o /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg; fi
cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=macos-host CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=macOS ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg avalonia osx-arm64 Chummer.Avalonia /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke
cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh
cd /docker/chummercomplete/chummer6-ui && mkdir -p /docker/chummercomplete/chummer6-ui/Docker/Downloads/files && python3 -c 'import hashlib, pathlib; p=pathlib.Path('"'"'/docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-osx-arm64-installer.dmg'"'"'); expected='"'"'19af740fb995ee5dff0c5c7a4e601159d8779ce08b4ce47ae3b0db7f796cd581'"'"'; import sys; sys.exit(0) if (not p.is_file()) else None; digest=hashlib.sha256(p.read_bytes()).hexdigest().lower(); sys.exit(0) if digest==expected else print(f'"'"'installer-preflight-sha256-mismatch:{p}:digest={digest}:expected={expected}'"'"') or p.unlink()' && if [ ! -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-osx-arm64-installer.dmg ]; then curl -fL --retry 3 --retry-delay 2 "${CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}/downloads/install/blazor-desktop-osx-arm64-installer" -o /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-osx-arm64-installer.dmg; fi
cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=macos-host CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=macOS ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-osx-arm64-installer.dmg blazor-desktop osx-arm64 Chummer.Blazor.Desktop /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke
```

### Commands (Host Validation)

```bash
cd /docker/chummercomplete/chummer6-ui && test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg
cd /docker/chummercomplete/chummer6-ui && python3 -c 'import hashlib, pathlib, sys; p=pathlib.Path('"'"'/docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg'"'"'); expected='"'"'086e7c0f2c55da5a3932c324f54b3bd98fabe6dc7715553406c3c9a74f24f89a'"'"'; digest=hashlib.sha256(p.read_bytes()).hexdigest().lower(); sys.exit(0) if digest==expected else sys.exit(f'"'"'installer-contract-mismatch:{p}:digest={digest}:expected={expected}'"'"')'
cd /docker/chummercomplete/chummer6-ui && test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json
cd /docker/chummercomplete/chummer6-ui && python3 -c 'import json, pathlib, sys; p=pathlib.Path('"'"'/docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json'"'"'); contract=json.loads('"'"'{"head_id": "avalonia", "host_class_contains": "macos", "platform": "macos", "ready_checkpoint": "pre_ui_event_loop", "rid": "osx-arm64", "status_any_of": ["pass", "passed", "ready"]}'"'"'); payload=json.loads(p.read_text(encoding='"'"'utf-8'"'"')); payload=payload if isinstance(payload, dict) else {}; status=str(payload.get('"'"'status'"'"') or '"'"''"'"').strip().lower(); expected_statuses=[str(token).strip().lower() for token in (contract.get('"'"'status_any_of'"'"') or []) if str(token).strip()]; head_id=str(payload.get('"'"'headId'"'"') or '"'"''"'"').strip().lower(); platform=str(payload.get('"'"'platform'"'"') or '"'"''"'"').strip().lower(); rid=str(payload.get('"'"'rid'"'"') or '"'"''"'"').strip().lower(); ready_checkpoint=str(payload.get('"'"'readyCheckpoint'"'"') or '"'"''"'"').strip().lower(); host_class=str(payload.get('"'"'hostClass'"'"') or '"'"''"'"').strip().lower(); expected_head=str(contract.get('"'"'head_id'"'"') or '"'"''"'"').strip().lower(); expected_platform=str(contract.get('"'"'platform'"'"') or '"'"''"'"').strip().lower(); expected_rid=str(contract.get('"'"'rid'"'"') or '"'"''"'"').strip().lower(); expected_ready=str(contract.get('"'"'ready_checkpoint'"'"') or '"'"''"'"').strip().lower(); expected_host_contains=str(contract.get('"'"'host_class_contains'"'"') or '"'"''"'"').strip().lower(); sys.exit(0) if ((not expected_statuses or status in expected_statuses) and (not expected_head or head_id == expected_head) and (not expected_platform or platform == expected_platform) and (not expected_rid or rid == expected_rid) and (not expected_ready or ready_checkpoint == expected_ready) and (not expected_host_contains or expected_host_contains in host_class)) else sys.exit(f'"'"'receipt-contract-mismatch:{p}:status={status}:head={head_id}:platform={platform}:rid={rid}:ready={ready_checkpoint}:host_class={host_class}:contract={contract}'"'"')'
cd /docker/chummercomplete/chummer6-ui && python3 -c 'import json, pathlib, sys; p=pathlib.Path('"'"'/docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json'"'"'); tuple_id='"'"'avalonia:osx-arm64:macos'"'"'; expected_artifact='"'"'avalonia-osx-arm64-installer'"'"'; expected_route='"'"'/downloads/install/avalonia-osx-arm64-installer'"'"'; payload=json.loads(p.read_text(encoding='"'"'utf-8'"'"')); coverage=payload.get('"'"'desktopTupleCoverage'"'"') if isinstance(payload, dict) else {}; coverage=coverage if isinstance(coverage, dict) else {}; rows=coverage.get('"'"'externalProofRequests'"'"') if isinstance(coverage, dict) else []; rows=rows if isinstance(rows, list) else []; row=next((item for item in rows if isinstance(item, dict) and str(item.get('"'"'tupleId'"'"') or item.get('"'"'tuple_id'"'"') or '"'"''"'"').strip()==tuple_id), None); sys.exit(f'"'"'release-channel-contract-mismatch:{tuple_id}:missing-external-proof-row'"'"') if row is None else None; artifact=str(row.get('"'"'expectedArtifactId'"'"') or row.get('"'"'expected_artifact_id'"'"') or '"'"''"'"').strip(); route=str(row.get('"'"'expectedPublicInstallRoute'"'"') or row.get('"'"'expected_public_install_route'"'"') or '"'"''"'"').strip(); artifact_ok=(not expected_artifact) or artifact==expected_artifact; route_ok=(not expected_route) or route==expected_route; sys.exit(0) if artifact_ok and route_ok else sys.exit(f'"'"'release-channel-contract-mismatch:{tuple_id}:artifact={artifact}:expected_artifact={expected_artifact}:route={route}:expected_route={expected_route}'"'"')'
cd /docker/chummercomplete/chummer6-ui && test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-osx-arm64-installer.dmg
cd /docker/chummercomplete/chummer6-ui && python3 -c 'import hashlib, pathlib, sys; p=pathlib.Path('"'"'/docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-osx-arm64-installer.dmg'"'"'); expected='"'"'19af740fb995ee5dff0c5c7a4e601159d8779ce08b4ce47ae3b0db7f796cd581'"'"'; digest=hashlib.sha256(p.read_bytes()).hexdigest().lower(); sys.exit(0) if digest==expected else sys.exit(f'"'"'installer-contract-mismatch:{p}:digest={digest}:expected={expected}'"'"')'
cd /docker/chummercomplete/chummer6-ui && test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-blazor-desktop-osx-arm64.receipt.json
cd /docker/chummercomplete/chummer6-ui && python3 -c 'import json, pathlib, sys; p=pathlib.Path('"'"'/docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-blazor-desktop-osx-arm64.receipt.json'"'"'); contract=json.loads('"'"'{"head_id": "blazor-desktop", "host_class_contains": "macos", "platform": "macos", "ready_checkpoint": "pre_ui_event_loop", "rid": "osx-arm64", "status_any_of": ["pass", "passed", "ready"]}'"'"'); payload=json.loads(p.read_text(encoding='"'"'utf-8'"'"')); payload=payload if isinstance(payload, dict) else {}; status=str(payload.get('"'"'status'"'"') or '"'"''"'"').strip().lower(); expected_statuses=[str(token).strip().lower() for token in (contract.get('"'"'status_any_of'"'"') or []) if str(token).strip()]; head_id=str(payload.get('"'"'headId'"'"') or '"'"''"'"').strip().lower(); platform=str(payload.get('"'"'platform'"'"') or '"'"''"'"').strip().lower(); rid=str(payload.get('"'"'rid'"'"') or '"'"''"'"').strip().lower(); ready_checkpoint=str(payload.get('"'"'readyCheckpoint'"'"') or '"'"''"'"').strip().lower(); host_class=str(payload.get('"'"'hostClass'"'"') or '"'"''"'"').strip().lower(); expected_head=str(contract.get('"'"'head_id'"'"') or '"'"''"'"').strip().lower(); expected_platform=str(contract.get('"'"'platform'"'"') or '"'"''"'"').strip().lower(); expected_rid=str(contract.get('"'"'rid'"'"') or '"'"''"'"').strip().lower(); expected_ready=str(contract.get('"'"'ready_checkpoint'"'"') or '"'"''"'"').strip().lower(); expected_host_contains=str(contract.get('"'"'host_class_contains'"'"') or '"'"''"'"').strip().lower(); sys.exit(0) if ((not expected_statuses or status in expected_statuses) and (not expected_head or head_id == expected_head) and (not expected_platform or platform == expected_platform) and (not expected_rid or rid == expected_rid) and (not expected_ready or ready_checkpoint == expected_ready) and (not expected_host_contains or expected_host_contains in host_class)) else sys.exit(f'"'"'receipt-contract-mismatch:{p}:status={status}:head={head_id}:platform={platform}:rid={rid}:ready={ready_checkpoint}:host_class={host_class}:contract={contract}'"'"')'
cd /docker/chummercomplete/chummer6-ui && python3 -c 'import json, pathlib, sys; p=pathlib.Path('"'"'/docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json'"'"'); tuple_id='"'"'blazor-desktop:osx-arm64:macos'"'"'; expected_artifact='"'"'blazor-desktop-osx-arm64-installer'"'"'; expected_route='"'"'/downloads/install/blazor-desktop-osx-arm64-installer'"'"'; payload=json.loads(p.read_text(encoding='"'"'utf-8'"'"')); coverage=payload.get('"'"'desktopTupleCoverage'"'"') if isinstance(payload, dict) else {}; coverage=coverage if isinstance(coverage, dict) else {}; rows=coverage.get('"'"'externalProofRequests'"'"') if isinstance(coverage, dict) else []; rows=rows if isinstance(rows, list) else []; row=next((item for item in rows if isinstance(item, dict) and str(item.get('"'"'tupleId'"'"') or item.get('"'"'tuple_id'"'"') or '"'"''"'"').strip()==tuple_id), None); sys.exit(f'"'"'release-channel-contract-mismatch:{tuple_id}:missing-external-proof-row'"'"') if row is None else None; artifact=str(row.get('"'"'expectedArtifactId'"'"') or row.get('"'"'expected_artifact_id'"'"') or '"'"''"'"').strip(); route=str(row.get('"'"'expectedPublicInstallRoute'"'"') or row.get('"'"'expected_public_install_route'"'"') or '"'"''"'"').strip(); artifact_ok=(not expected_artifact) or artifact==expected_artifact; route_ok=(not expected_route) or route==expected_route; sys.exit(0) if artifact_ok and route_ok else sys.exit(f'"'"'release-channel-contract-mismatch:{tuple_id}:artifact={artifact}:expected_artifact={expected_artifact}:route={route}:expected_route={expected_route}'"'"')'
```

### Commands (Host Bundle)

```bash
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
```

### Commands (Host Ingest)

```bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE_ARCHIVE="$SCRIPT_DIR/macos-proof-bundle.tgz"
TARGET_ROOT=/docker/chummercomplete/chummer6-ui/Docker/Downloads
if [ ! -s "$BUNDLE_ARCHIVE" ]; then
  echo "Missing host proof bundle: $BUNDLE_ARCHIVE"
  exit 1
fi
python3 -c 'import pathlib, tarfile; bundle=pathlib.Path(__import__('"'"'os'"'"').environ['"'"'BUNDLE_ARCHIVE'"'"']); bad=[]; with tarfile.open(bundle, '"'"'r:gz'"'"') as t:   for member in t.getmembers():     parts=pathlib.PurePosixPath(member.name).parts;     if member.name.startswith('"'"'/'"'"') or '"'"'..'"'"' in parts:       bad.append(member.name); if bad:   raise SystemExit('"'"'external-proof-bundle-path-unsafe:'"'"' + '"'"','"'"'.join(sorted(set(bad))))'
mkdir -p "$TARGET_ROOT"
tar -xzf "$BUNDLE_ARCHIVE" -C "$TARGET_ROOT"
test -s '$TARGET_ROOT/files/chummer-avalonia-osx-arm64-installer.dmg'
test -s '$TARGET_ROOT/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json'
test -s '$TARGET_ROOT/files/chummer-blazor-desktop-osx-arm64-installer.dmg'
test -s '$TARGET_ROOT/startup-smoke/startup-smoke-blazor-desktop-osx-arm64.receipt.json'
echo "Host proof bundle ingest complete: $BUNDLE_ARCHIVE"
```

## Host: windows

- shell_hint: Run canonical commands in Git Bash (or WSL bash). PowerShell wrappers are provided below when you need to stay in PowerShell.
- request_count: 2
- tuples: avalonia:win-x64:windows, blazor-desktop:win-x64:windows

### Requested Tuples

- `avalonia:win-x64:windows`
  required_proofs: `promoted_installer_artifact, startup_smoke_receipt`
  artifact_id: `avalonia-win-x64-installer`
  installer_file: `chummer-avalonia-win-x64-installer.exe`
  installer_relative_path: `files/chummer-avalonia-win-x64-installer.exe`
  installer_sha256: `529a427c84a36082fe66d09a4547b17bd6c5046d2e4586277c5b7cd0c83ab00f`
  public_route: `/downloads/install/avalonia-win-x64-installer`
  startup_smoke_receipt: `startup-smoke/startup-smoke-avalonia-win-x64.receipt.json`
  capture_deadline_utc: `2026-04-06T04:10:31Z`
  capture_deadline_state: `pending`
  commands:
    - `cd /docker/chummercomplete/chummer6-ui && mkdir -p /docker/chummercomplete/chummer6-ui/Docker/Downloads/files && python3 -c 'import hashlib, pathlib; p=pathlib.Path('"'"'/docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe'"'"'); expected='"'"'529a427c84a36082fe66d09a4547b17bd6c5046d2e4586277c5b7cd0c83ab00f'"'"'; import sys; sys.exit(0) if (not p.is_file()) else None; digest=hashlib.sha256(p.read_bytes()).hexdigest().lower(); sys.exit(0) if digest==expected else print(f'"'"'installer-preflight-sha256-mismatch:{p}:digest={digest}:expected={expected}'"'"') or p.unlink()' && if [ ! -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe ]; then curl -fL --retry 3 --retry-delay 2 "${CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}/downloads/install/avalonia-win-x64-installer" -o /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe; fi`
    - `cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=Windows ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe avalonia win-x64 Chummer.Avalonia.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke`
    - `cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh`
- `blazor-desktop:win-x64:windows`
  required_proofs: `promoted_installer_artifact, startup_smoke_receipt`
  artifact_id: `blazor-desktop-win-x64-installer`
  installer_file: `chummer-blazor-desktop-win-x64-installer.exe`
  installer_relative_path: `files/chummer-blazor-desktop-win-x64-installer.exe`
  installer_sha256: `bc960d8d8081bd3e661b6f7ac281ee08879a5eeb007d45ec0bdfb9a98f188499`
  public_route: `/downloads/install/blazor-desktop-win-x64-installer`
  startup_smoke_receipt: `startup-smoke/startup-smoke-blazor-desktop-win-x64.receipt.json`
  capture_deadline_utc: `2026-04-06T04:10:31Z`
  capture_deadline_state: `pending`
  commands:
    - `cd /docker/chummercomplete/chummer6-ui && mkdir -p /docker/chummercomplete/chummer6-ui/Docker/Downloads/files && python3 -c 'import hashlib, pathlib; p=pathlib.Path('"'"'/docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-win-x64-installer.exe'"'"'); expected='"'"'bc960d8d8081bd3e661b6f7ac281ee08879a5eeb007d45ec0bdfb9a98f188499'"'"'; import sys; sys.exit(0) if (not p.is_file()) else None; digest=hashlib.sha256(p.read_bytes()).hexdigest().lower(); sys.exit(0) if digest==expected else print(f'"'"'installer-preflight-sha256-mismatch:{p}:digest={digest}:expected={expected}'"'"') or p.unlink()' && if [ ! -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-win-x64-installer.exe ]; then curl -fL --retry 3 --retry-delay 2 "${CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}/downloads/install/blazor-desktop-win-x64-installer" -o /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-win-x64-installer.exe; fi`
    - `cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=Windows ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-win-x64-installer.exe blazor-desktop win-x64 Chummer.Blazor.Desktop.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke`
    - `cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh`

### Commands (Host Consolidated)

```bash
cd /docker/chummercomplete/chummer6-ui && mkdir -p /docker/chummercomplete/chummer6-ui/Docker/Downloads/files && python3 -c 'import hashlib, pathlib; p=pathlib.Path('"'"'/docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe'"'"'); expected='"'"'529a427c84a36082fe66d09a4547b17bd6c5046d2e4586277c5b7cd0c83ab00f'"'"'; import sys; sys.exit(0) if (not p.is_file()) else None; digest=hashlib.sha256(p.read_bytes()).hexdigest().lower(); sys.exit(0) if digest==expected else print(f'"'"'installer-preflight-sha256-mismatch:{p}:digest={digest}:expected={expected}'"'"') or p.unlink()' && if [ ! -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe ]; then curl -fL --retry 3 --retry-delay 2 "${CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}/downloads/install/avalonia-win-x64-installer" -o /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe; fi
cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=Windows ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe avalonia win-x64 Chummer.Avalonia.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke
cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh
cd /docker/chummercomplete/chummer6-ui && mkdir -p /docker/chummercomplete/chummer6-ui/Docker/Downloads/files && python3 -c 'import hashlib, pathlib; p=pathlib.Path('"'"'/docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-win-x64-installer.exe'"'"'); expected='"'"'bc960d8d8081bd3e661b6f7ac281ee08879a5eeb007d45ec0bdfb9a98f188499'"'"'; import sys; sys.exit(0) if (not p.is_file()) else None; digest=hashlib.sha256(p.read_bytes()).hexdigest().lower(); sys.exit(0) if digest==expected else print(f'"'"'installer-preflight-sha256-mismatch:{p}:digest={digest}:expected={expected}'"'"') or p.unlink()' && if [ ! -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-win-x64-installer.exe ]; then curl -fL --retry 3 --retry-delay 2 "${CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}/downloads/install/blazor-desktop-win-x64-installer" -o /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-win-x64-installer.exe; fi
cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=Windows ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-win-x64-installer.exe blazor-desktop win-x64 Chummer.Blazor.Desktop.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke
```

### Commands (Host Validation)

```bash
cd /docker/chummercomplete/chummer6-ui && test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe
cd /docker/chummercomplete/chummer6-ui && python3 -c 'import hashlib, pathlib, sys; p=pathlib.Path('"'"'/docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe'"'"'); expected='"'"'529a427c84a36082fe66d09a4547b17bd6c5046d2e4586277c5b7cd0c83ab00f'"'"'; digest=hashlib.sha256(p.read_bytes()).hexdigest().lower(); sys.exit(0) if digest==expected else sys.exit(f'"'"'installer-contract-mismatch:{p}:digest={digest}:expected={expected}'"'"')'
cd /docker/chummercomplete/chummer6-ui && test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json
cd /docker/chummercomplete/chummer6-ui && python3 -c 'import json, pathlib, sys; p=pathlib.Path('"'"'/docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json'"'"'); contract=json.loads('"'"'{"head_id": "avalonia", "host_class_contains": "windows", "platform": "windows", "ready_checkpoint": "pre_ui_event_loop", "rid": "win-x64", "status_any_of": ["pass", "passed", "ready"]}'"'"'); payload=json.loads(p.read_text(encoding='"'"'utf-8'"'"')); payload=payload if isinstance(payload, dict) else {}; status=str(payload.get('"'"'status'"'"') or '"'"''"'"').strip().lower(); expected_statuses=[str(token).strip().lower() for token in (contract.get('"'"'status_any_of'"'"') or []) if str(token).strip()]; head_id=str(payload.get('"'"'headId'"'"') or '"'"''"'"').strip().lower(); platform=str(payload.get('"'"'platform'"'"') or '"'"''"'"').strip().lower(); rid=str(payload.get('"'"'rid'"'"') or '"'"''"'"').strip().lower(); ready_checkpoint=str(payload.get('"'"'readyCheckpoint'"'"') or '"'"''"'"').strip().lower(); host_class=str(payload.get('"'"'hostClass'"'"') or '"'"''"'"').strip().lower(); expected_head=str(contract.get('"'"'head_id'"'"') or '"'"''"'"').strip().lower(); expected_platform=str(contract.get('"'"'platform'"'"') or '"'"''"'"').strip().lower(); expected_rid=str(contract.get('"'"'rid'"'"') or '"'"''"'"').strip().lower(); expected_ready=str(contract.get('"'"'ready_checkpoint'"'"') or '"'"''"'"').strip().lower(); expected_host_contains=str(contract.get('"'"'host_class_contains'"'"') or '"'"''"'"').strip().lower(); sys.exit(0) if ((not expected_statuses or status in expected_statuses) and (not expected_head or head_id == expected_head) and (not expected_platform or platform == expected_platform) and (not expected_rid or rid == expected_rid) and (not expected_ready or ready_checkpoint == expected_ready) and (not expected_host_contains or expected_host_contains in host_class)) else sys.exit(f'"'"'receipt-contract-mismatch:{p}:status={status}:head={head_id}:platform={platform}:rid={rid}:ready={ready_checkpoint}:host_class={host_class}:contract={contract}'"'"')'
cd /docker/chummercomplete/chummer6-ui && python3 -c 'import json, pathlib, sys; p=pathlib.Path('"'"'/docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json'"'"'); tuple_id='"'"'avalonia:win-x64:windows'"'"'; expected_artifact='"'"'avalonia-win-x64-installer'"'"'; expected_route='"'"'/downloads/install/avalonia-win-x64-installer'"'"'; payload=json.loads(p.read_text(encoding='"'"'utf-8'"'"')); coverage=payload.get('"'"'desktopTupleCoverage'"'"') if isinstance(payload, dict) else {}; coverage=coverage if isinstance(coverage, dict) else {}; rows=coverage.get('"'"'externalProofRequests'"'"') if isinstance(coverage, dict) else []; rows=rows if isinstance(rows, list) else []; row=next((item for item in rows if isinstance(item, dict) and str(item.get('"'"'tupleId'"'"') or item.get('"'"'tuple_id'"'"') or '"'"''"'"').strip()==tuple_id), None); sys.exit(f'"'"'release-channel-contract-mismatch:{tuple_id}:missing-external-proof-row'"'"') if row is None else None; artifact=str(row.get('"'"'expectedArtifactId'"'"') or row.get('"'"'expected_artifact_id'"'"') or '"'"''"'"').strip(); route=str(row.get('"'"'expectedPublicInstallRoute'"'"') or row.get('"'"'expected_public_install_route'"'"') or '"'"''"'"').strip(); artifact_ok=(not expected_artifact) or artifact==expected_artifact; route_ok=(not expected_route) or route==expected_route; sys.exit(0) if artifact_ok and route_ok else sys.exit(f'"'"'release-channel-contract-mismatch:{tuple_id}:artifact={artifact}:expected_artifact={expected_artifact}:route={route}:expected_route={expected_route}'"'"')'
cd /docker/chummercomplete/chummer6-ui && test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-win-x64-installer.exe
cd /docker/chummercomplete/chummer6-ui && python3 -c 'import hashlib, pathlib, sys; p=pathlib.Path('"'"'/docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-win-x64-installer.exe'"'"'); expected='"'"'bc960d8d8081bd3e661b6f7ac281ee08879a5eeb007d45ec0bdfb9a98f188499'"'"'; digest=hashlib.sha256(p.read_bytes()).hexdigest().lower(); sys.exit(0) if digest==expected else sys.exit(f'"'"'installer-contract-mismatch:{p}:digest={digest}:expected={expected}'"'"')'
cd /docker/chummercomplete/chummer6-ui && test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-blazor-desktop-win-x64.receipt.json
cd /docker/chummercomplete/chummer6-ui && python3 -c 'import json, pathlib, sys; p=pathlib.Path('"'"'/docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-blazor-desktop-win-x64.receipt.json'"'"'); contract=json.loads('"'"'{"head_id": "blazor-desktop", "host_class_contains": "windows", "platform": "windows", "ready_checkpoint": "pre_ui_event_loop", "rid": "win-x64", "status_any_of": ["pass", "passed", "ready"]}'"'"'); payload=json.loads(p.read_text(encoding='"'"'utf-8'"'"')); payload=payload if isinstance(payload, dict) else {}; status=str(payload.get('"'"'status'"'"') or '"'"''"'"').strip().lower(); expected_statuses=[str(token).strip().lower() for token in (contract.get('"'"'status_any_of'"'"') or []) if str(token).strip()]; head_id=str(payload.get('"'"'headId'"'"') or '"'"''"'"').strip().lower(); platform=str(payload.get('"'"'platform'"'"') or '"'"''"'"').strip().lower(); rid=str(payload.get('"'"'rid'"'"') or '"'"''"'"').strip().lower(); ready_checkpoint=str(payload.get('"'"'readyCheckpoint'"'"') or '"'"''"'"').strip().lower(); host_class=str(payload.get('"'"'hostClass'"'"') or '"'"''"'"').strip().lower(); expected_head=str(contract.get('"'"'head_id'"'"') or '"'"''"'"').strip().lower(); expected_platform=str(contract.get('"'"'platform'"'"') or '"'"''"'"').strip().lower(); expected_rid=str(contract.get('"'"'rid'"'"') or '"'"''"'"').strip().lower(); expected_ready=str(contract.get('"'"'ready_checkpoint'"'"') or '"'"''"'"').strip().lower(); expected_host_contains=str(contract.get('"'"'host_class_contains'"'"') or '"'"''"'"').strip().lower(); sys.exit(0) if ((not expected_statuses or status in expected_statuses) and (not expected_head or head_id == expected_head) and (not expected_platform or platform == expected_platform) and (not expected_rid or rid == expected_rid) and (not expected_ready or ready_checkpoint == expected_ready) and (not expected_host_contains or expected_host_contains in host_class)) else sys.exit(f'"'"'receipt-contract-mismatch:{p}:status={status}:head={head_id}:platform={platform}:rid={rid}:ready={ready_checkpoint}:host_class={host_class}:contract={contract}'"'"')'
cd /docker/chummercomplete/chummer6-ui && python3 -c 'import json, pathlib, sys; p=pathlib.Path('"'"'/docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json'"'"'); tuple_id='"'"'blazor-desktop:win-x64:windows'"'"'; expected_artifact='"'"'blazor-desktop-win-x64-installer'"'"'; expected_route='"'"'/downloads/install/blazor-desktop-win-x64-installer'"'"'; payload=json.loads(p.read_text(encoding='"'"'utf-8'"'"')); coverage=payload.get('"'"'desktopTupleCoverage'"'"') if isinstance(payload, dict) else {}; coverage=coverage if isinstance(coverage, dict) else {}; rows=coverage.get('"'"'externalProofRequests'"'"') if isinstance(coverage, dict) else []; rows=rows if isinstance(rows, list) else []; row=next((item for item in rows if isinstance(item, dict) and str(item.get('"'"'tupleId'"'"') or item.get('"'"'tuple_id'"'"') or '"'"''"'"').strip()==tuple_id), None); sys.exit(f'"'"'release-channel-contract-mismatch:{tuple_id}:missing-external-proof-row'"'"') if row is None else None; artifact=str(row.get('"'"'expectedArtifactId'"'"') or row.get('"'"'expected_artifact_id'"'"') or '"'"''"'"').strip(); route=str(row.get('"'"'expectedPublicInstallRoute'"'"') or row.get('"'"'expected_public_install_route'"'"') or '"'"''"'"').strip(); artifact_ok=(not expected_artifact) or artifact==expected_artifact; route_ok=(not expected_route) or route==expected_route; sys.exit(0) if artifact_ok and route_ok else sys.exit(f'"'"'release-channel-contract-mismatch:{tuple_id}:artifact={artifact}:expected_artifact={expected_artifact}:route={route}:expected_route={expected_route}'"'"')'
```

### Commands (Host Bundle)

```bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE_ROOT="$SCRIPT_DIR/host-proof-bundles/windows"
rm -rf "$BUNDLE_ROOT"
mkdir -p "$BUNDLE_ROOT"
mkdir -p '$BUNDLE_ROOT/files'
cp -f /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe '$BUNDLE_ROOT/files/chummer-avalonia-win-x64-installer.exe'
mkdir -p '$BUNDLE_ROOT/startup-smoke'
cp -f /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json '$BUNDLE_ROOT/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json'
mkdir -p '$BUNDLE_ROOT/files'
cp -f /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-win-x64-installer.exe '$BUNDLE_ROOT/files/chummer-blazor-desktop-win-x64-installer.exe'
mkdir -p '$BUNDLE_ROOT/startup-smoke'
cp -f /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-blazor-desktop-win-x64.receipt.json '$BUNDLE_ROOT/startup-smoke/startup-smoke-blazor-desktop-win-x64.receipt.json'
tar -czf "$SCRIPT_DIR/windows-proof-bundle.tgz" -C "$BUNDLE_ROOT" .
echo "Wrote $SCRIPT_DIR/windows-proof-bundle.tgz"
```

### Commands (Host Ingest)

```bash
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
```

### Commands (PowerShell Wrappers)

```powershell
bash -lc 'cd /docker/chummercomplete/chummer6-ui && mkdir -p /docker/chummercomplete/chummer6-ui/Docker/Downloads/files && python3 -c ''import hashlib, pathlib; p=pathlib.Path(''"''"''/docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe''"''"''); expected=''"''"''529a427c84a36082fe66d09a4547b17bd6c5046d2e4586277c5b7cd0c83ab00f''"''"''; import sys; sys.exit(0) if (not p.is_file()) else None; digest=hashlib.sha256(p.read_bytes()).hexdigest().lower(); sys.exit(0) if digest==expected else print(f''"''"''installer-preflight-sha256-mismatch:{p}:digest={digest}:expected={expected}''"''"'') or p.unlink()'' && if [ ! -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe ]; then curl -fL --retry 3 --retry-delay 2 "${CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}/downloads/install/avalonia-win-x64-installer" -o /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe; fi'
bash -lc 'cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=Windows ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe avalonia win-x64 Chummer.Avalonia.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke'
bash -lc 'cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh'
bash -lc 'cd /docker/chummercomplete/chummer6-ui && mkdir -p /docker/chummercomplete/chummer6-ui/Docker/Downloads/files && python3 -c ''import hashlib, pathlib; p=pathlib.Path(''"''"''/docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-win-x64-installer.exe''"''"''); expected=''"''"''bc960d8d8081bd3e661b6f7ac281ee08879a5eeb007d45ec0bdfb9a98f188499''"''"''; import sys; sys.exit(0) if (not p.is_file()) else None; digest=hashlib.sha256(p.read_bytes()).hexdigest().lower(); sys.exit(0) if digest==expected else print(f''"''"''installer-preflight-sha256-mismatch:{p}:digest={digest}:expected={expected}''"''"'') or p.unlink()'' && if [ ! -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-win-x64-installer.exe ]; then curl -fL --retry 3 --retry-delay 2 "${CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}/downloads/install/blazor-desktop-win-x64-installer" -o /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-win-x64-installer.exe; fi'
bash -lc 'cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=Windows ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-win-x64-installer.exe blazor-desktop win-x64 Chummer.Blazor.Desktop.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke'
```

### Commands (PowerShell Validation Wrappers)

```powershell
bash -lc 'cd /docker/chummercomplete/chummer6-ui && test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe'
bash -lc 'cd /docker/chummercomplete/chummer6-ui && python3 -c ''import hashlib, pathlib, sys; p=pathlib.Path(''"''"''/docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe''"''"''); expected=''"''"''529a427c84a36082fe66d09a4547b17bd6c5046d2e4586277c5b7cd0c83ab00f''"''"''; digest=hashlib.sha256(p.read_bytes()).hexdigest().lower(); sys.exit(0) if digest==expected else sys.exit(f''"''"''installer-contract-mismatch:{p}:digest={digest}:expected={expected}''"''"'')'''
bash -lc 'cd /docker/chummercomplete/chummer6-ui && test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json'
bash -lc 'cd /docker/chummercomplete/chummer6-ui && python3 -c ''import json, pathlib, sys; p=pathlib.Path(''"''"''/docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json''"''"''); contract=json.loads(''"''"''{"head_id": "avalonia", "host_class_contains": "windows", "platform": "windows", "ready_checkpoint": "pre_ui_event_loop", "rid": "win-x64", "status_any_of": ["pass", "passed", "ready"]}''"''"''); payload=json.loads(p.read_text(encoding=''"''"''utf-8''"''"'')); payload=payload if isinstance(payload, dict) else {}; status=str(payload.get(''"''"''status''"''"'') or ''"''"''''"''"'').strip().lower(); expected_statuses=[str(token).strip().lower() for token in (contract.get(''"''"''status_any_of''"''"'') or []) if str(token).strip()]; head_id=str(payload.get(''"''"''headId''"''"'') or ''"''"''''"''"'').strip().lower(); platform=str(payload.get(''"''"''platform''"''"'') or ''"''"''''"''"'').strip().lower(); rid=str(payload.get(''"''"''rid''"''"'') or ''"''"''''"''"'').strip().lower(); ready_checkpoint=str(payload.get(''"''"''readyCheckpoint''"''"'') or ''"''"''''"''"'').strip().lower(); host_class=str(payload.get(''"''"''hostClass''"''"'') or ''"''"''''"''"'').strip().lower(); expected_head=str(contract.get(''"''"''head_id''"''"'') or ''"''"''''"''"'').strip().lower(); expected_platform=str(contract.get(''"''"''platform''"''"'') or ''"''"''''"''"'').strip().lower(); expected_rid=str(contract.get(''"''"''rid''"''"'') or ''"''"''''"''"'').strip().lower(); expected_ready=str(contract.get(''"''"''ready_checkpoint''"''"'') or ''"''"''''"''"'').strip().lower(); expected_host_contains=str(contract.get(''"''"''host_class_contains''"''"'') or ''"''"''''"''"'').strip().lower(); sys.exit(0) if ((not expected_statuses or status in expected_statuses) and (not expected_head or head_id == expected_head) and (not expected_platform or platform == expected_platform) and (not expected_rid or rid == expected_rid) and (not expected_ready or ready_checkpoint == expected_ready) and (not expected_host_contains or expected_host_contains in host_class)) else sys.exit(f''"''"''receipt-contract-mismatch:{p}:status={status}:head={head_id}:platform={platform}:rid={rid}:ready={ready_checkpoint}:host_class={host_class}:contract={contract}''"''"'')'''
bash -lc 'cd /docker/chummercomplete/chummer6-ui && python3 -c ''import json, pathlib, sys; p=pathlib.Path(''"''"''/docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json''"''"''); tuple_id=''"''"''avalonia:win-x64:windows''"''"''; expected_artifact=''"''"''avalonia-win-x64-installer''"''"''; expected_route=''"''"''/downloads/install/avalonia-win-x64-installer''"''"''; payload=json.loads(p.read_text(encoding=''"''"''utf-8''"''"'')); coverage=payload.get(''"''"''desktopTupleCoverage''"''"'') if isinstance(payload, dict) else {}; coverage=coverage if isinstance(coverage, dict) else {}; rows=coverage.get(''"''"''externalProofRequests''"''"'') if isinstance(coverage, dict) else []; rows=rows if isinstance(rows, list) else []; row=next((item for item in rows if isinstance(item, dict) and str(item.get(''"''"''tupleId''"''"'') or item.get(''"''"''tuple_id''"''"'') or ''"''"''''"''"'').strip()==tuple_id), None); sys.exit(f''"''"''release-channel-contract-mismatch:{tuple_id}:missing-external-proof-row''"''"'') if row is None else None; artifact=str(row.get(''"''"''expectedArtifactId''"''"'') or row.get(''"''"''expected_artifact_id''"''"'') or ''"''"''''"''"'').strip(); route=str(row.get(''"''"''expectedPublicInstallRoute''"''"'') or row.get(''"''"''expected_public_install_route''"''"'') or ''"''"''''"''"'').strip(); artifact_ok=(not expected_artifact) or artifact==expected_artifact; route_ok=(not expected_route) or route==expected_route; sys.exit(0) if artifact_ok and route_ok else sys.exit(f''"''"''release-channel-contract-mismatch:{tuple_id}:artifact={artifact}:expected_artifact={expected_artifact}:route={route}:expected_route={expected_route}''"''"'')'''
bash -lc 'cd /docker/chummercomplete/chummer6-ui && test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-win-x64-installer.exe'
bash -lc 'cd /docker/chummercomplete/chummer6-ui && python3 -c ''import hashlib, pathlib, sys; p=pathlib.Path(''"''"''/docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-win-x64-installer.exe''"''"''); expected=''"''"''bc960d8d8081bd3e661b6f7ac281ee08879a5eeb007d45ec0bdfb9a98f188499''"''"''; digest=hashlib.sha256(p.read_bytes()).hexdigest().lower(); sys.exit(0) if digest==expected else sys.exit(f''"''"''installer-contract-mismatch:{p}:digest={digest}:expected={expected}''"''"'')'''
bash -lc 'cd /docker/chummercomplete/chummer6-ui && test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-blazor-desktop-win-x64.receipt.json'
bash -lc 'cd /docker/chummercomplete/chummer6-ui && python3 -c ''import json, pathlib, sys; p=pathlib.Path(''"''"''/docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-blazor-desktop-win-x64.receipt.json''"''"''); contract=json.loads(''"''"''{"head_id": "blazor-desktop", "host_class_contains": "windows", "platform": "windows", "ready_checkpoint": "pre_ui_event_loop", "rid": "win-x64", "status_any_of": ["pass", "passed", "ready"]}''"''"''); payload=json.loads(p.read_text(encoding=''"''"''utf-8''"''"'')); payload=payload if isinstance(payload, dict) else {}; status=str(payload.get(''"''"''status''"''"'') or ''"''"''''"''"'').strip().lower(); expected_statuses=[str(token).strip().lower() for token in (contract.get(''"''"''status_any_of''"''"'') or []) if str(token).strip()]; head_id=str(payload.get(''"''"''headId''"''"'') or ''"''"''''"''"'').strip().lower(); platform=str(payload.get(''"''"''platform''"''"'') or ''"''"''''"''"'').strip().lower(); rid=str(payload.get(''"''"''rid''"''"'') or ''"''"''''"''"'').strip().lower(); ready_checkpoint=str(payload.get(''"''"''readyCheckpoint''"''"'') or ''"''"''''"''"'').strip().lower(); host_class=str(payload.get(''"''"''hostClass''"''"'') or ''"''"''''"''"'').strip().lower(); expected_head=str(contract.get(''"''"''head_id''"''"'') or ''"''"''''"''"'').strip().lower(); expected_platform=str(contract.get(''"''"''platform''"''"'') or ''"''"''''"''"'').strip().lower(); expected_rid=str(contract.get(''"''"''rid''"''"'') or ''"''"''''"''"'').strip().lower(); expected_ready=str(contract.get(''"''"''ready_checkpoint''"''"'') or ''"''"''''"''"'').strip().lower(); expected_host_contains=str(contract.get(''"''"''host_class_contains''"''"'') or ''"''"''''"''"'').strip().lower(); sys.exit(0) if ((not expected_statuses or status in expected_statuses) and (not expected_head or head_id == expected_head) and (not expected_platform or platform == expected_platform) and (not expected_rid or rid == expected_rid) and (not expected_ready or ready_checkpoint == expected_ready) and (not expected_host_contains or expected_host_contains in host_class)) else sys.exit(f''"''"''receipt-contract-mismatch:{p}:status={status}:head={head_id}:platform={platform}:rid={rid}:ready={ready_checkpoint}:host_class={host_class}:contract={contract}''"''"'')'''
bash -lc 'cd /docker/chummercomplete/chummer6-ui && python3 -c ''import json, pathlib, sys; p=pathlib.Path(''"''"''/docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json''"''"''); tuple_id=''"''"''blazor-desktop:win-x64:windows''"''"''; expected_artifact=''"''"''blazor-desktop-win-x64-installer''"''"''; expected_route=''"''"''/downloads/install/blazor-desktop-win-x64-installer''"''"''; payload=json.loads(p.read_text(encoding=''"''"''utf-8''"''"'')); coverage=payload.get(''"''"''desktopTupleCoverage''"''"'') if isinstance(payload, dict) else {}; coverage=coverage if isinstance(coverage, dict) else {}; rows=coverage.get(''"''"''externalProofRequests''"''"'') if isinstance(coverage, dict) else []; rows=rows if isinstance(rows, list) else []; row=next((item for item in rows if isinstance(item, dict) and str(item.get(''"''"''tupleId''"''"'') or item.get(''"''"''tuple_id''"''"'') or ''"''"''''"''"'').strip()==tuple_id), None); sys.exit(f''"''"''release-channel-contract-mismatch:{tuple_id}:missing-external-proof-row''"''"'') if row is None else None; artifact=str(row.get(''"''"''expectedArtifactId''"''"'') or row.get(''"''"''expected_artifact_id''"''"'') or ''"''"''''"''"'').strip(); route=str(row.get(''"''"''expectedPublicInstallRoute''"''"'') or row.get(''"''"''expected_public_install_route''"''"'') or ''"''"''''"''"'').strip(); artifact_ok=(not expected_artifact) or artifact==expected_artifact; route_ok=(not expected_route) or route==expected_route; sys.exit(0) if artifact_ok and route_ok else sys.exit(f''"''"''release-channel-contract-mismatch:{tuple_id}:artifact={artifact}:expected_artifact={expected_artifact}:route={route}:expected_route={expected_route}''"''"'')'''
```

### Commands (PowerShell Bundle Wrappers)

```powershell
bash -lc 'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"'
bash -lc 'BUNDLE_ROOT="$SCRIPT_DIR/host-proof-bundles/windows"'
bash -lc 'rm -rf "$BUNDLE_ROOT"'
bash -lc 'mkdir -p "$BUNDLE_ROOT"'
bash -lc 'mkdir -p ''$BUNDLE_ROOT/files'''
bash -lc 'cp -f /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe ''$BUNDLE_ROOT/files/chummer-avalonia-win-x64-installer.exe'''
bash -lc 'mkdir -p ''$BUNDLE_ROOT/startup-smoke'''
bash -lc 'cp -f /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json ''$BUNDLE_ROOT/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json'''
bash -lc 'mkdir -p ''$BUNDLE_ROOT/files'''
bash -lc 'cp -f /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-win-x64-installer.exe ''$BUNDLE_ROOT/files/chummer-blazor-desktop-win-x64-installer.exe'''
bash -lc 'mkdir -p ''$BUNDLE_ROOT/startup-smoke'''
bash -lc 'cp -f /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-blazor-desktop-win-x64.receipt.json ''$BUNDLE_ROOT/startup-smoke/startup-smoke-blazor-desktop-win-x64.receipt.json'''
bash -lc 'tar -czf "$SCRIPT_DIR/windows-proof-bundle.tgz" -C "$BUNDLE_ROOT" .'
bash -lc 'echo "Wrote $SCRIPT_DIR/windows-proof-bundle.tgz"'
```

### Commands (PowerShell Ingest Wrappers)

```powershell
bash -lc 'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"'
bash -lc 'BUNDLE_ARCHIVE="$SCRIPT_DIR/windows-proof-bundle.tgz"'
bash -lc 'TARGET_ROOT=/docker/chummercomplete/chummer6-ui/Docker/Downloads'
bash -lc 'if [ ! -s "$BUNDLE_ARCHIVE" ]; then'
bash -lc 'echo "Missing host proof bundle: $BUNDLE_ARCHIVE"'
bash -lc 'exit 1'
bash -lc 'fi'
bash -lc 'python3 -c ''import pathlib, tarfile; bundle=pathlib.Path(__import__(''"''"''os''"''"'').environ[''"''"''BUNDLE_ARCHIVE''"''"'']); bad=[]; with tarfile.open(bundle, ''"''"''r:gz''"''"'') as t:   for member in t.getmembers():     parts=pathlib.PurePosixPath(member.name).parts;     if member.name.startswith(''"''"''/''"''"'') or ''"''"''..''"''"'' in parts:       bad.append(member.name); if bad:   raise SystemExit(''"''"''external-proof-bundle-path-unsafe:''"''"'' + ''"''"'',''"''"''.join(sorted(set(bad))))'''
bash -lc 'mkdir -p "$TARGET_ROOT"'
bash -lc 'tar -xzf "$BUNDLE_ARCHIVE" -C "$TARGET_ROOT"'
bash -lc 'test -s ''$TARGET_ROOT/files/chummer-avalonia-win-x64-installer.exe'''
bash -lc 'test -s ''$TARGET_ROOT/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json'''
bash -lc 'test -s ''$TARGET_ROOT/files/chummer-blazor-desktop-win-x64-installer.exe'''
bash -lc 'test -s ''$TARGET_ROOT/startup-smoke/startup-smoke-blazor-desktop-win-x64.receipt.json'''
bash -lc 'echo "Host proof bundle ingest complete: $BUNDLE_ARCHIVE"'
```

## After Host Proof Capture

Run these commands after macOS/Windows proofs land to ingest receipts and republish release truth.

```bash
cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh
cd /docker/chummercomplete/chummer-hub-registry && python3 scripts/materialize_public_release_channel.py --manifest /docker/chummercomplete/chummer6-ui/Docker/Downloads/RELEASE_CHANNEL.generated.json --downloads-dir /docker/chummercomplete/chummer6-ui/Docker/Downloads/files --startup-smoke-dir /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke --proof /docker/chummercomplete/chummer6-ui/.codex-studio/published/UI_LOCAL_RELEASE_PROOF.generated.json --ui-localization-release-gate /docker/chummercomplete/chummer6-ui/.codex-studio/published/UI_LOCALIZATION_RELEASE_GATE.generated.json --channel docker --version unpublished --published-at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" --output .codex-studio/published/RELEASE_CHANNEL.generated.json
cd /docker/chummercomplete/chummer-hub-registry && python3 scripts/verify_public_release_channel.py .codex-studio/published/RELEASE_CHANNEL.generated.json
cd /docker/fleet && python3 scripts/materialize_status_plane.py --out .codex-studio/published/STATUS_PLANE.generated.yaml
cd /docker/fleet && python3 scripts/verify_status_plane_semantics.py --status-plane .codex-studio/published/STATUS_PLANE.generated.yaml
cd /docker/fleet && python3 scripts/materialize_public_progress_report.py --out .codex-studio/published/PROGRESS_REPORT.generated.json --html-out /docker/chummercomplete/chummer-design/products/chummer/PROGRESS_REPORT.generated.html --history-out .codex-studio/published/PROGRESS_HISTORY.generated.json --preview-out /docker/chummercomplete/chummer-design/products/chummer/PROGRESS_REPORT.generated.json
cd /docker/fleet && python3 scripts/materialize_support_case_packets.py --out .codex-studio/published/SUPPORT_CASE_PACKETS.generated.json --release-channel /docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json
cd /docker/fleet && python3 scripts/materialize_journey_gates.py --out .codex-studio/published/JOURNEY_GATES.generated.json --status-plane .codex-studio/published/STATUS_PLANE.generated.yaml --progress-report .codex-studio/published/PROGRESS_REPORT.generated.json --progress-history .codex-studio/published/PROGRESS_HISTORY.generated.json --support-packets .codex-studio/published/SUPPORT_CASE_PACKETS.generated.json
cd /docker/fleet && python3 scripts/materialize_external_proof_runbook.py --support-packets .codex-studio/published/SUPPORT_CASE_PACKETS.generated.json --out .codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md
cd /docker/fleet && python3 scripts/verify_external_proof_closure.py --support-packets .codex-studio/published/SUPPORT_CASE_PACKETS.generated.json --journey-gates .codex-studio/published/JOURNEY_GATES.generated.json --release-channel /docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json --external-proof-runbook .codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md --external-proof-commands-dir .codex-studio/published/external-proof-commands
cd /docker/fleet && python3 scripts/materialize_flagship_product_readiness.py --out .codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json
cd /docker/chummercomplete/chummer-design && python3 scripts/ai/materialize_weekly_product_pulse_snapshot.py --out products/chummer/WEEKLY_PRODUCT_PULSE.generated.json
cd /docker/fleet && python3 scripts/chummer_design_supervisor.py status >/dev/null
```
