# External Proof Runbook

- generated_at: 2026-05-29T09:34:21Z
- unresolved_request_count: 2
- unresolved_hosts: macos, windows
- plan_generated_at: 2026-05-29T09:32:50Z
- release_channel_generated_at: 2026-05-29T08:34:38Z
- capture_deadline_hours: 24
- capture_deadline_utc: 2026-05-30T08:34:38Z

## Prerequisites

- Run each host section on the matching native host (`macos` on macOS, `windows` on Windows).
- Provide signed-in download credentials before capture when public routes are account-gated.
- Supported auth inputs: `CHUMMER_EXTERNAL_PROOF_AUTH_HEADER`, `CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER`, `CHUMMER_EXTERNAL_PROOF_COOKIE_JAR`.
- Set `CHUMMER_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD=1` only when install routes are intentionally guest-readable.
- Optional base URL override: `CHUMMER_EXTERNAL_PROOF_BASE_URL` (default `${CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}`).

## Generated Command Files

- commands_dir: `/docker/fleet/.codex-studio/published/external-proof-commands`
- command_bundle_sha256: `a09d7c1ee6492c3bc319c0c52b358f8948e7d57e6042b25624ab40157a2861d2`
- command_bundle_file_count: 30
- host `linux`
  preflight_script: `/docker/fleet/.codex-studio/published/external-proof-commands/preflight-linux-proof.sh`
  capture_script: `/docker/fleet/.codex-studio/published/external-proof-commands/capture-linux-proof.sh`
  validation_script: `/docker/fleet/.codex-studio/published/external-proof-commands/validate-linux-proof.sh`
  bundle_script: `/docker/fleet/.codex-studio/published/external-proof-commands/bundle-linux-proof.sh`
  ingest_script: `/docker/fleet/.codex-studio/published/external-proof-commands/ingest-linux-proof-bundle.sh`
  host_lane_script: `/docker/fleet/.codex-studio/published/external-proof-commands/run-linux-proof-lane.sh`
  prepare_command_pack_script: `/docker/fleet/.codex-studio/published/external-proof-commands/prepare-linux-proof-command-pack.sh`
  command_pack_path: `/docker/fleet/.codex-studio/published/external-proof-commands/linux-proof-command-pack.tgz`
  command_pack_sha256_path: `/docker/fleet/.codex-studio/published/external-proof-commands/linux-proof-command-pack.tgz.sha256`
  command_pack_sha256: `f2e0a8ccf9e9401cbfa70d6e21f32721016ebefdcefe49452d5c21d20fc9abb4`
- host `macos`
  preflight_script: `/docker/fleet/.codex-studio/published/external-proof-commands/preflight-macos-proof.sh`
  capture_script: `/docker/fleet/.codex-studio/published/external-proof-commands/capture-macos-proof.sh`
  validation_script: `/docker/fleet/.codex-studio/published/external-proof-commands/validate-macos-proof.sh`
  bundle_script: `/docker/fleet/.codex-studio/published/external-proof-commands/bundle-macos-proof.sh`
  ingest_script: `/docker/fleet/.codex-studio/published/external-proof-commands/ingest-macos-proof-bundle.sh`
  host_lane_script: `/docker/fleet/.codex-studio/published/external-proof-commands/run-macos-proof-lane.sh`
  prepare_command_pack_script: `/docker/fleet/.codex-studio/published/external-proof-commands/prepare-macos-proof-command-pack.sh`
  command_pack_path: `/docker/fleet/.codex-studio/published/external-proof-commands/macos-proof-command-pack.tgz`
  command_pack_sha256_path: `/docker/fleet/.codex-studio/published/external-proof-commands/macos-proof-command-pack.tgz.sha256`
  command_pack_sha256: `62aad50b50f5571e0d01f5c5f8fe44aa7cab93d88dbfa44cd8e398ec7d763974`
- host `windows`
  preflight_script: `/docker/fleet/.codex-studio/published/external-proof-commands/preflight-windows-proof.sh`
  capture_script: `/docker/fleet/.codex-studio/published/external-proof-commands/capture-windows-proof.sh`
  validation_script: `/docker/fleet/.codex-studio/published/external-proof-commands/validate-windows-proof.sh`
  bundle_script: `/docker/fleet/.codex-studio/published/external-proof-commands/bundle-windows-proof.sh`
  ingest_script: `/docker/fleet/.codex-studio/published/external-proof-commands/ingest-windows-proof-bundle.sh`
  host_lane_script: `/docker/fleet/.codex-studio/published/external-proof-commands/run-windows-proof-lane.sh`
  prepare_command_pack_script: `/docker/fleet/.codex-studio/published/external-proof-commands/prepare-windows-proof-command-pack.sh`
  command_pack_path: `/docker/fleet/.codex-studio/published/external-proof-commands/windows-proof-command-pack.tgz`
  command_pack_sha256_path: `/docker/fleet/.codex-studio/published/external-proof-commands/windows-proof-command-pack.tgz.sha256`
  command_pack_sha256: `bc9654a1ced7787b6ecc7771df6b7c8cb61236790365904ef496f02efeb820e4`
  preflight_powershell: `/docker/fleet/.codex-studio/published/external-proof-commands/preflight-windows-proof.ps1`
  capture_powershell: `/docker/fleet/.codex-studio/published/external-proof-commands/capture-windows-proof.ps1`
  validation_powershell: `/docker/fleet/.codex-studio/published/external-proof-commands/validate-windows-proof.ps1`
  bundle_powershell: `/docker/fleet/.codex-studio/published/external-proof-commands/bundle-windows-proof.ps1`
  ingest_powershell: `/docker/fleet/.codex-studio/published/external-proof-commands/ingest-windows-proof-bundle.ps1`
  host_lane_powershell: `/docker/fleet/.codex-studio/published/external-proof-commands/run-windows-proof-lane.ps1`
  prepare_command_pack_powershell: `/docker/fleet/.codex-studio/published/external-proof-commands/prepare-windows-proof-command-pack.ps1`
- post_capture_script: `/docker/fleet/.codex-studio/published/external-proof-commands/republish-after-host-proof.sh`
- finalize_script: `/docker/fleet/.codex-studio/published/external-proof-commands/finalize-external-host-proof.sh`

## Host: macos

- shell_hint: Run commands in a POSIX shell (bash/zsh) on the required host.
- platform_hint: macOS proofs require `hdiutil` on the proof host.
- request_count: 1
- tuples: avalonia:osx-arm64:macos
- cached_bundle_status: `stale_directory`
- cached_bundle_detail: `manifest_mismatch:/docker/fleet/.codex-studio/published/external-proof-commands/host-proof-bundles/macos/external-proof-manifest.json`
- cached_bundle_archive_path: `/docker/fleet/.codex-studio/published/external-proof-commands/macos-proof-bundle.tgz`
- cached_bundle_directory_path: `/docker/fleet/.codex-studio/published/external-proof-commands/host-proof-bundles/macos`
- command_pack_path: `/docker/fleet/.codex-studio/published/external-proof-commands/macos-proof-command-pack.tgz`
- command_pack_present: `true`
- command_pack_sha256_path: `/docker/fleet/.codex-studio/published/external-proof-commands/macos-proof-command-pack.tgz.sha256`
- command_pack_sha256: `62aad50b50f5571e0d01f5c5f8fe44aa7cab93d88dbfa44cd8e398ec7d763974`

### Command Pack Verification

Transfer the command pack, its SHA sidecar, and the retained prepare script to the native proof host. The prepare script verifies the archive and unpacks it into the target directory.
After unpacking, use `README.md` and `proof-host.env.example` in the extracted folder as the host-local checklist before you run the lane.

```bash
bash prepare-macos-proof-command-pack.sh macos-proof-command-pack.tgz macos-proof-command-pack.tgz.sha256
```

### Requested Tuples

- `avalonia:osx-arm64:macos`
  required_proofs: `promoted_installer_artifact, startup_smoke_receipt`
  artifact_id: `avalonia-osx-arm64-installer`
  installer_file: `chummer-avalonia-osx-arm64-installer.dmg`
  installer_relative_path: `files/chummer-avalonia-osx-arm64-installer.dmg`
  installer_sha256: `c82393b1bcff3897faf2ea9255e8775ccc1cefa512b3e16a7cb06e52ba48b07e`
  public_route: `/downloads/install/avalonia-osx-arm64-installer`
  startup_smoke_receipt: `startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json`
  local_installer_state: `present_sha256_mismatch`
  local_installer_path: `/docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg`
  local_startup_smoke_receipt_state: `stale`
  local_startup_smoke_receipt_path: `/docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json`
  local_startup_smoke_receipt_recorded_at: `2026-05-18T22:12:25.078057+00:00`
  local_startup_smoke_receipt_age_seconds: `904825`
  capture_deadline_utc: `2026-05-30T08:34:38Z`
  capture_deadline_state: `pending`
  commands:
    - `REPO_ROOT="${CHUMMER_UI_REPO_ROOT:-/docker/chummercomplete/chummer6-ui}" && export REPO_ROOT && if [ -z "${CHUMMER_UI_REPO_ROOT:-}" ] && [ ! -d "$REPO_ROOT" ]; then for candidate in /docker/chummercomplete/chummer6-ui /docker/chummercomplete/chummer6-ui-finish /docker/chummercomplete/chummer-presentation; do if [ -d "$candidate" ]; then REPO_ROOT="$candidate" && export REPO_ROOT && break; fi; done; fi && DOWNLOADS_ROOT="$REPO_ROOT/Docker/Downloads" && export DOWNLOADS_ROOT && INSTALLER_PATH="$DOWNLOADS_ROOT/files/chummer-avalonia-osx-arm64-installer.dmg" && export INSTALLER_PATH && cd "$REPO_ROOT" && mkdir -p "$(dirname "$INSTALLER_PATH")" && python3 -c 'import hashlib, os, pathlib; p=pathlib.Path(os.environ['"'"'INSTALLER_PATH'"'"']); expected='"'"'c82393b1bcff3897faf2ea9255e8775ccc1cefa512b3e16a7cb06e52ba48b07e'"'"'; import sys; sys.exit(0) if (not p.is_file()) else None; digest=hashlib.sha256(p.read_bytes()).hexdigest().lower(); sys.exit(0) if digest==expected else print(f'"'"'installer-preflight-sha256-mismatch:{p}:digest={digest}:expected={expected}'"'"') or p.unlink()' && if [ ! -s "$INSTALLER_PATH" ]; then if [ -z "${CHUMMER_EXTERNAL_PROOF_AUTH_HEADER:-}" ] && [ -z "${CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER:-}" ] && [ -z "${CHUMMER_EXTERNAL_PROOF_COOKIE_JAR:-}" ] && [ "${CHUMMER_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD:-0}" != "1" ]; then echo 'external-proof-auth-missing: set CHUMMER_EXTERNAL_PROOF_AUTH_HEADER, CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER, or CHUMMER_EXTERNAL_PROOF_COOKIE_JAR (or set CHUMMER_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD=1 to bypass)' >&2; exit 1; fi; set -- curl -fL --retry 3 --retry-delay 2; if [ -n "${CHUMMER_EXTERNAL_PROOF_AUTH_HEADER:-}" ]; then set -- "$@" -H "${CHUMMER_EXTERNAL_PROOF_AUTH_HEADER:-}"; fi; if [ -n "${CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER:-}" ]; then set -- "$@" -H "Cookie: ${CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER:-}"; fi; if [ -n "${CHUMMER_EXTERNAL_PROOF_COOKIE_JAR:-}" ]; then set -- "$@" --cookie "${CHUMMER_EXTERNAL_PROOF_COOKIE_JAR:-}"; fi; set -- "$@" "${CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}/downloads/install/avalonia-osx-arm64-installer" -o "$INSTALLER_PATH"; "$@"; fi; python3 -c 'import os, pathlib, sys; p=pathlib.Path(os.environ['"'"'INSTALLER_PATH'"'"']); expected_magic='"'"''"'"'; sys.exit(f'"'"'installer-download-missing:{p}'"'"') if (not p.is_file()) else None; probe=p.read_bytes()[:8192]; probe_text=probe.decode('"'"'latin-1'"'"', errors='"'"'ignore'"'"').lower(); auth_header_set=bool(str(os.environ.get('"'"'CHUMMER_EXTERNAL_PROOF_AUTH_HEADER'"'"','"'"''"'"')).strip()); cookie_header_set=bool(str(os.environ.get('"'"'CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER'"'"','"'"''"'"')).strip()); cookie_jar_set=bool(str(os.environ.get('"'"'CHUMMER_EXTERNAL_PROOF_COOKIE_JAR'"'"','"'"''"'"')).strip()); html_like=('"'"'<!doctype html'"'"' in probe_text) or ('"'"'<html'"'"' in probe_text) or ('"'"'<head'"'"' in probe_text); sys.exit(f'"'"'installer-download-html-response:{p}:auth_header_set={auth_header_set}:cookie_header_set={cookie_header_set}:cookie_jar_set={cookie_jar_set}:hint=signed-in-download-route-required-or-missing-auth'"'"') if html_like else None; sys.exit(0) if (not expected_magic or probe.startswith(expected_magic.encode('"'"'latin-1'"'"'))) else sys.exit(f'"'"'installer-download-signature-mismatch:{p}:expected_magic={expected_magic}:auth_header_set={auth_header_set}:cookie_header_set={cookie_header_set}:cookie_jar_set={cookie_jar_set}:hint=unexpected-binary-format-or-route-response'"'"')'; python3 -c 'import hashlib, os, pathlib, sys; p=pathlib.Path(os.environ['"'"'INSTALLER_PATH'"'"']); expected='"'"'c82393b1bcff3897faf2ea9255e8775ccc1cefa512b3e16a7cb06e52ba48b07e'"'"'; sys.exit(f'"'"'installer-download-missing:{p}'"'"') if (not p.is_file()) else None; digest=hashlib.sha256(p.read_bytes()).hexdigest().lower(); auth_header_set=bool(str(os.environ.get('"'"'CHUMMER_EXTERNAL_PROOF_AUTH_HEADER'"'"','"'"''"'"')).strip()); cookie_header_set=bool(str(os.environ.get('"'"'CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER'"'"','"'"''"'"')).strip()); cookie_jar_set=bool(str(os.environ.get('"'"'CHUMMER_EXTERNAL_PROOF_COOKIE_JAR'"'"','"'"''"'"')).strip()); sys.exit(0) if digest==expected else sys.exit(f'"'"'installer-postdownload-sha256-mismatch:{p}:digest={digest}:expected={expected}:auth_header_set={auth_header_set}:cookie_header_set={cookie_header_set}:cookie_jar_set={cookie_jar_set}:hint=signed-in-download-route-required-or-bytes-drift'"'"')'`
    - `REPO_ROOT="${CHUMMER_UI_REPO_ROOT:-/docker/chummercomplete/chummer6-ui}" && export REPO_ROOT && INSTALLER_PATH="$REPO_ROOT/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg" && STARTUP_SMOKE_DIR="$REPO_ROOT/Docker/Downloads/startup-smoke" && cd "$REPO_ROOT" && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=macos-host CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=macOS ./scripts/run-desktop-startup-smoke.sh "$INSTALLER_PATH" avalonia osx-arm64 Chummer.Avalonia "$STARTUP_SMOKE_DIR" run-20260518-220935`
    - `REPO_ROOT="${CHUMMER_UI_REPO_ROOT:-/docker/chummercomplete/chummer6-ui}" && export REPO_ROOT && cd "$REPO_ROOT" && ./scripts/generate-releases-manifest.sh`

### Commands (Host Consolidated)

```bash
REPO_ROOT="${CHUMMER_UI_REPO_ROOT:-/docker/chummercomplete/chummer6-ui}" && export REPO_ROOT && if [ -z "${CHUMMER_UI_REPO_ROOT:-}" ] && [ ! -d "$REPO_ROOT" ]; then for candidate in /docker/chummercomplete/chummer6-ui /docker/chummercomplete/chummer6-ui-finish /docker/chummercomplete/chummer-presentation; do if [ -d "$candidate" ]; then REPO_ROOT="$candidate" && export REPO_ROOT && break; fi; done; fi && DOWNLOADS_ROOT="$REPO_ROOT/Docker/Downloads" && export DOWNLOADS_ROOT && INSTALLER_PATH="$DOWNLOADS_ROOT/files/chummer-avalonia-osx-arm64-installer.dmg" && export INSTALLER_PATH && cd "$REPO_ROOT" && mkdir -p "$(dirname "$INSTALLER_PATH")" && python3 -c 'import hashlib, os, pathlib; p=pathlib.Path(os.environ['"'"'INSTALLER_PATH'"'"']); expected='"'"'c82393b1bcff3897faf2ea9255e8775ccc1cefa512b3e16a7cb06e52ba48b07e'"'"'; import sys; sys.exit(0) if (not p.is_file()) else None; digest=hashlib.sha256(p.read_bytes()).hexdigest().lower(); sys.exit(0) if digest==expected else print(f'"'"'installer-preflight-sha256-mismatch:{p}:digest={digest}:expected={expected}'"'"') or p.unlink()' && if [ ! -s "$INSTALLER_PATH" ]; then if [ -z "${CHUMMER_EXTERNAL_PROOF_AUTH_HEADER:-}" ] && [ -z "${CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER:-}" ] && [ -z "${CHUMMER_EXTERNAL_PROOF_COOKIE_JAR:-}" ] && [ "${CHUMMER_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD:-0}" != "1" ]; then echo 'external-proof-auth-missing: set CHUMMER_EXTERNAL_PROOF_AUTH_HEADER, CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER, or CHUMMER_EXTERNAL_PROOF_COOKIE_JAR (or set CHUMMER_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD=1 to bypass)' >&2; exit 1; fi; set -- curl -fL --retry 3 --retry-delay 2; if [ -n "${CHUMMER_EXTERNAL_PROOF_AUTH_HEADER:-}" ]; then set -- "$@" -H "${CHUMMER_EXTERNAL_PROOF_AUTH_HEADER:-}"; fi; if [ -n "${CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER:-}" ]; then set -- "$@" -H "Cookie: ${CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER:-}"; fi; if [ -n "${CHUMMER_EXTERNAL_PROOF_COOKIE_JAR:-}" ]; then set -- "$@" --cookie "${CHUMMER_EXTERNAL_PROOF_COOKIE_JAR:-}"; fi; set -- "$@" "${CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}/downloads/install/avalonia-osx-arm64-installer" -o "$INSTALLER_PATH"; "$@"; fi; python3 -c 'import os, pathlib, sys; p=pathlib.Path(os.environ['"'"'INSTALLER_PATH'"'"']); expected_magic='"'"''"'"'; sys.exit(f'"'"'installer-download-missing:{p}'"'"') if (not p.is_file()) else None; probe=p.read_bytes()[:8192]; probe_text=probe.decode('"'"'latin-1'"'"', errors='"'"'ignore'"'"').lower(); auth_header_set=bool(str(os.environ.get('"'"'CHUMMER_EXTERNAL_PROOF_AUTH_HEADER'"'"','"'"''"'"')).strip()); cookie_header_set=bool(str(os.environ.get('"'"'CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER'"'"','"'"''"'"')).strip()); cookie_jar_set=bool(str(os.environ.get('"'"'CHUMMER_EXTERNAL_PROOF_COOKIE_JAR'"'"','"'"''"'"')).strip()); html_like=('"'"'<!doctype html'"'"' in probe_text) or ('"'"'<html'"'"' in probe_text) or ('"'"'<head'"'"' in probe_text); sys.exit(f'"'"'installer-download-html-response:{p}:auth_header_set={auth_header_set}:cookie_header_set={cookie_header_set}:cookie_jar_set={cookie_jar_set}:hint=signed-in-download-route-required-or-missing-auth'"'"') if html_like else None; sys.exit(0) if (not expected_magic or probe.startswith(expected_magic.encode('"'"'latin-1'"'"'))) else sys.exit(f'"'"'installer-download-signature-mismatch:{p}:expected_magic={expected_magic}:auth_header_set={auth_header_set}:cookie_header_set={cookie_header_set}:cookie_jar_set={cookie_jar_set}:hint=unexpected-binary-format-or-route-response'"'"')'; python3 -c 'import hashlib, os, pathlib, sys; p=pathlib.Path(os.environ['"'"'INSTALLER_PATH'"'"']); expected='"'"'c82393b1bcff3897faf2ea9255e8775ccc1cefa512b3e16a7cb06e52ba48b07e'"'"'; sys.exit(f'"'"'installer-download-missing:{p}'"'"') if (not p.is_file()) else None; digest=hashlib.sha256(p.read_bytes()).hexdigest().lower(); auth_header_set=bool(str(os.environ.get('"'"'CHUMMER_EXTERNAL_PROOF_AUTH_HEADER'"'"','"'"''"'"')).strip()); cookie_header_set=bool(str(os.environ.get('"'"'CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER'"'"','"'"''"'"')).strip()); cookie_jar_set=bool(str(os.environ.get('"'"'CHUMMER_EXTERNAL_PROOF_COOKIE_JAR'"'"','"'"''"'"')).strip()); sys.exit(0) if digest==expected else sys.exit(f'"'"'installer-postdownload-sha256-mismatch:{p}:digest={digest}:expected={expected}:auth_header_set={auth_header_set}:cookie_header_set={cookie_header_set}:cookie_jar_set={cookie_jar_set}:hint=signed-in-download-route-required-or-bytes-drift'"'"')'
REPO_ROOT="${CHUMMER_UI_REPO_ROOT:-/docker/chummercomplete/chummer6-ui}" && export REPO_ROOT && INSTALLER_PATH="$REPO_ROOT/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg" && STARTUP_SMOKE_DIR="$REPO_ROOT/Docker/Downloads/startup-smoke" && cd "$REPO_ROOT" && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=macos-host CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=macOS ./scripts/run-desktop-startup-smoke.sh "$INSTALLER_PATH" avalonia osx-arm64 Chummer.Avalonia "$STARTUP_SMOKE_DIR" run-20260518-220935
REPO_ROOT="${CHUMMER_UI_REPO_ROOT:-/docker/chummercomplete/chummer6-ui}" && export REPO_ROOT && cd "$REPO_ROOT" && ./scripts/generate-releases-manifest.sh
```

### Commands (Host Preflight)

```bash
if ! command -v python3 >/dev/null 2>&1; then echo 'external-proof-python3-missing' >&2; exit 1; fi
if ! command -v curl >/dev/null 2>&1; then echo 'external-proof-curl-missing' >&2; exit 1; fi
if [ -z "${CHUMMER_UI_REPO_ROOT:-}" ] && [ ! -d /docker/chummercomplete/chummer6-ui ] && [ ! -d /docker/chummercomplete/chummer6-ui-finish ] && [ ! -d /docker/chummercomplete/chummer-presentation ]; then echo 'external-proof-ui-repo-root-missing: set CHUMMER_UI_REPO_ROOT if the UI repo is not checked out at /docker/chummercomplete/chummer6-ui, /docker/chummercomplete/chummer6-ui-finish, /docker/chummercomplete/chummer-presentation on the proof host' >&2; exit 1; fi
if ! command -v hdiutil >/dev/null 2>&1; then echo 'external-proof-macos-host-missing-hdiutil' >&2; echo 'Hint: run this lane on a macOS host (install xcode tools if needed) rather than Linux.' >&2; exit 1; fi
if [ -z "${CHUMMER_EXTERNAL_PROOF_AUTH_HEADER:-}" ] && [ -z "${CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER:-}" ] && [ -z "${CHUMMER_EXTERNAL_PROOF_COOKIE_JAR:-}" ] && [ "${CHUMMER_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD:-0}" != "1" ]; then echo 'external-proof-auth-missing: set CHUMMER_EXTERNAL_PROOF_AUTH_HEADER, CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER, or CHUMMER_EXTERNAL_PROOF_COOKIE_JAR (or set CHUMMER_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD=1 to bypass)' >&2; exit 1; fi
```

### Commands (Host Validation)

```bash
REPO_ROOT="${CHUMMER_UI_REPO_ROOT:-/docker/chummercomplete/chummer6-ui}" && export REPO_ROOT && if [ -z "${CHUMMER_UI_REPO_ROOT:-}" ] && [ ! -d "$REPO_ROOT" ]; then for candidate in /docker/chummercomplete/chummer6-ui /docker/chummercomplete/chummer6-ui-finish /docker/chummercomplete/chummer-presentation; do if [ -d "$candidate" ]; then REPO_ROOT="$candidate" && export REPO_ROOT && break; fi; done; fi && DOWNLOADS_ROOT="$REPO_ROOT/Docker/Downloads" && export DOWNLOADS_ROOT && INSTALLER_PATH="$DOWNLOADS_ROOT/files/chummer-avalonia-osx-arm64-installer.dmg" && export INSTALLER_PATH && cd "$REPO_ROOT" && test -s "$INSTALLER_PATH"
REPO_ROOT="${CHUMMER_UI_REPO_ROOT:-/docker/chummercomplete/chummer6-ui}" && export REPO_ROOT && if [ -z "${CHUMMER_UI_REPO_ROOT:-}" ] && [ ! -d "$REPO_ROOT" ]; then for candidate in /docker/chummercomplete/chummer6-ui /docker/chummercomplete/chummer6-ui-finish /docker/chummercomplete/chummer-presentation; do if [ -d "$candidate" ]; then REPO_ROOT="$candidate" && export REPO_ROOT && break; fi; done; fi && DOWNLOADS_ROOT="$REPO_ROOT/Docker/Downloads" && export DOWNLOADS_ROOT && INSTALLER_PATH="$DOWNLOADS_ROOT/files/chummer-avalonia-osx-arm64-installer.dmg" && export INSTALLER_PATH && cd "$REPO_ROOT" && python3 -c 'import hashlib, os, pathlib, sys; p=pathlib.Path(os.environ['"'"'INSTALLER_PATH'"'"']); expected='"'"'c82393b1bcff3897faf2ea9255e8775ccc1cefa512b3e16a7cb06e52ba48b07e'"'"'; digest=hashlib.sha256(p.read_bytes()).hexdigest().lower(); sys.exit(0) if digest==expected else sys.exit(f'"'"'installer-contract-mismatch:{p}:digest={digest}:expected={expected}'"'"')'
REPO_ROOT="${CHUMMER_UI_REPO_ROOT:-/docker/chummercomplete/chummer6-ui}" && export REPO_ROOT && if [ -z "${CHUMMER_UI_REPO_ROOT:-}" ] && [ ! -d "$REPO_ROOT" ]; then for candidate in /docker/chummercomplete/chummer6-ui /docker/chummercomplete/chummer6-ui-finish /docker/chummercomplete/chummer-presentation; do if [ -d "$candidate" ]; then REPO_ROOT="$candidate" && export REPO_ROOT && break; fi; done; fi && DOWNLOADS_ROOT="$REPO_ROOT/Docker/Downloads" && export DOWNLOADS_ROOT && RECEIPT_PATH="$DOWNLOADS_ROOT/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json" && export RECEIPT_PATH && cd "$REPO_ROOT" && test -s "$RECEIPT_PATH"
REPO_ROOT="${CHUMMER_UI_REPO_ROOT:-/docker/chummercomplete/chummer6-ui}" && export REPO_ROOT && if [ -z "${CHUMMER_UI_REPO_ROOT:-}" ] && [ ! -d "$REPO_ROOT" ]; then for candidate in /docker/chummercomplete/chummer6-ui /docker/chummercomplete/chummer6-ui-finish /docker/chummercomplete/chummer-presentation; do if [ -d "$candidate" ]; then REPO_ROOT="$candidate" && export REPO_ROOT && break; fi; done; fi && DOWNLOADS_ROOT="$REPO_ROOT/Docker/Downloads" && export DOWNLOADS_ROOT && RECEIPT_PATH="$DOWNLOADS_ROOT/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json" && export RECEIPT_PATH && cd "$REPO_ROOT" && python3 -c 'import datetime as dt, json, os, pathlib, sys; p=pathlib.Path(os.environ['"'"'RECEIPT_PATH'"'"']); max_age_seconds=604800; max_future_skew_seconds=300; payload=json.loads(p.read_text(encoding='"'"'utf-8'"'"')); payload=payload if isinstance(payload, dict) else {}; raw=next((str(payload.get(key) or '"'"''"'"').strip() for key in ('"'"'recordedAtUtc'"'"','"'"'completedAtUtc'"'"','"'"'generatedAt'"'"','"'"'generated_at'"'"','"'"'startedAtUtc'"'"') if str(payload.get(key) or '"'"''"'"').strip()), '"'"''"'"'); sys.exit(f'"'"'startup-smoke-receipt-timestamp-missing:{p}'"'"') if not raw else None; raw = raw[:-1] + '"'"'+00:00'"'"' if raw.endswith('"'"'Z'"'"') else raw; parsed=dt.datetime.fromisoformat(raw); parsed=parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=dt.timezone.utc); parsed=parsed.astimezone(dt.timezone.utc); now=dt.datetime.now(dt.timezone.utc); age_seconds=int((now-parsed).total_seconds()); sys.exit(f'"'"'startup-smoke-receipt-future-skew:{p}:age_seconds={age_seconds}:max_future_skew_seconds={max_future_skew_seconds}'"'"') if age_seconds < -max_future_skew_seconds else None; age_seconds = 0 if age_seconds < 0 else age_seconds; sys.exit(0) if age_seconds <= max_age_seconds else sys.exit(f'"'"'startup-smoke-receipt-stale:{p}:age_seconds={age_seconds}:max_age_seconds={max_age_seconds}'"'"')'
REPO_ROOT="${CHUMMER_UI_REPO_ROOT:-/docker/chummercomplete/chummer6-ui}" && export REPO_ROOT && if [ -z "${CHUMMER_UI_REPO_ROOT:-}" ] && [ ! -d "$REPO_ROOT" ]; then for candidate in /docker/chummercomplete/chummer6-ui /docker/chummercomplete/chummer6-ui-finish /docker/chummercomplete/chummer-presentation; do if [ -d "$candidate" ]; then REPO_ROOT="$candidate" && export REPO_ROOT && break; fi; done; fi && DOWNLOADS_ROOT="$REPO_ROOT/Docker/Downloads" && export DOWNLOADS_ROOT && RECEIPT_PATH="$DOWNLOADS_ROOT/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json" && export RECEIPT_PATH && cd "$REPO_ROOT" && python3 -c 'import json, os, pathlib, sys; p=pathlib.Path(os.environ['"'"'RECEIPT_PATH'"'"']); contract=json.loads('"'"'{"head_id": "avalonia", "host_class_contains": "macos", "platform": "macos", "ready_checkpoint": "pre_ui_event_loop", "rid": "osx-arm64", "status_any_of": ["pass", "passed", "ready"]}'"'"'); payload=json.loads(p.read_text(encoding='"'"'utf-8'"'"')); payload=payload if isinstance(payload, dict) else {}; status=str(payload.get('"'"'status'"'"') or '"'"''"'"').strip().lower(); expected_statuses=[str(token).strip().lower() for token in (contract.get('"'"'status_any_of'"'"') or []) if str(token).strip()]; head_id=str(payload.get('"'"'headId'"'"') or '"'"''"'"').strip().lower(); platform=str(payload.get('"'"'platform'"'"') or '"'"''"'"').strip().lower(); rid=str(payload.get('"'"'rid'"'"') or '"'"''"'"').strip().lower(); ready_checkpoint=str(payload.get('"'"'readyCheckpoint'"'"') or '"'"''"'"').strip().lower(); host_class=str(payload.get('"'"'hostClass'"'"') or '"'"''"'"').strip().lower(); expected_head=str(contract.get('"'"'head_id'"'"') or '"'"''"'"').strip().lower(); expected_platform=str(contract.get('"'"'platform'"'"') or '"'"''"'"').strip().lower(); expected_rid=str(contract.get('"'"'rid'"'"') or '"'"''"'"').strip().lower(); expected_ready=str(contract.get('"'"'ready_checkpoint'"'"') or '"'"''"'"').strip().lower(); expected_host_contains=str(contract.get('"'"'host_class_contains'"'"') or '"'"''"'"').strip().lower(); sys.exit(0) if ((not expected_statuses or status in expected_statuses) and (not expected_head or head_id == expected_head) and (not expected_platform or platform == expected_platform) and (not expected_rid or rid == expected_rid) and (not expected_ready or ready_checkpoint == expected_ready) and (not expected_host_contains or expected_host_contains in host_class)) else sys.exit(f'"'"'receipt-contract-mismatch:{p}:status={status}:head={head_id}:platform={platform}:rid={rid}:ready={ready_checkpoint}:host_class={host_class}:contract={contract}'"'"')'
REPO_ROOT="${CHUMMER_UI_REPO_ROOT:-/docker/chummercomplete/chummer6-ui}" && export REPO_ROOT && if [ -z "${CHUMMER_UI_REPO_ROOT:-}" ] && [ ! -d "$REPO_ROOT" ]; then for candidate in /docker/chummercomplete/chummer6-ui /docker/chummercomplete/chummer6-ui-finish /docker/chummercomplete/chummer-presentation; do if [ -d "$candidate" ]; then REPO_ROOT="$candidate" && export REPO_ROOT && break; fi; done; fi && DOWNLOADS_ROOT="$REPO_ROOT/Docker/Downloads" && export DOWNLOADS_ROOT && RELEASE_CHANNEL_PATH="$DOWNLOADS_ROOT/RELEASE_CHANNEL.generated.json" && export RELEASE_CHANNEL_PATH && cd "$REPO_ROOT" && python3 -c 'import json, os, pathlib, sys; p=pathlib.Path(os.environ['"'"'RELEASE_CHANNEL_PATH'"'"']); tuple_id='"'"'avalonia:osx-arm64:macos'"'"'; expected_artifact='"'"'avalonia-osx-arm64-installer'"'"'; expected_route='"'"'/downloads/install/avalonia-osx-arm64-installer'"'"'; payload=json.loads(p.read_text(encoding='"'"'utf-8'"'"')); coverage=payload.get('"'"'desktopTupleCoverage'"'"') if isinstance(payload, dict) else {}; coverage=coverage if isinstance(coverage, dict) else {}; rows=coverage.get('"'"'externalProofRequests'"'"') if isinstance(coverage, dict) else []; rows=rows if isinstance(rows, list) else []; row=next((item for item in rows if isinstance(item, dict) and str(item.get('"'"'tupleId'"'"') or item.get('"'"'tuple_id'"'"') or '"'"''"'"').strip()==tuple_id), None); sys.exit(f'"'"'release-channel-contract-mismatch:{tuple_id}:missing-external-proof-row'"'"') if row is None else None; artifact=str(row.get('"'"'expectedArtifactId'"'"') or row.get('"'"'expected_artifact_id'"'"') or '"'"''"'"').strip(); route=str(row.get('"'"'expectedPublicInstallRoute'"'"') or row.get('"'"'expected_public_install_route'"'"') or '"'"''"'"').strip(); artifact_ok=(not expected_artifact) or artifact==expected_artifact; route_ok=(not expected_route) or route==expected_route; sys.exit(0) if artifact_ok and route_ok else sys.exit(f'"'"'release-channel-contract-mismatch:{tuple_id}:artifact={artifact}:expected_artifact={expected_artifact}:route={route}:expected_route={expected_route}'"'"')'
```

### Commands (Host Bundle)

```bash
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
```

### Commands (Host Ingest)

```bash
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
DEFAULT_BUNDLE_ARCHIVE="$SCRIPT_DIR/macos-proof-bundle.tgz"
DEFAULT_BUNDLE_DIR="$SCRIPT_DIR/host-proof-bundles/macos"
BUNDLE_INPUT="${1:-}"
if [ -n "$BUNDLE_INPUT" ] && [ -f "$BUNDLE_INPUT" ]; then
  BUNDLE_ARCHIVE="$BUNDLE_INPUT"
  BUNDLE_DIR="$DEFAULT_BUNDLE_DIR"
elif [ -n "$BUNDLE_INPUT" ] && [ -d "$BUNDLE_INPUT" ]; then
  BUNDLE_ARCHIVE="$DEFAULT_BUNDLE_ARCHIVE"
  BUNDLE_DIR="$BUNDLE_INPUT"
else
  BUNDLE_ARCHIVE="$DEFAULT_BUNDLE_ARCHIVE"
  BUNDLE_DIR="$DEFAULT_BUNDLE_DIR"
fi
export BUNDLE_ARCHIVE
export BUNDLE_DIR
TARGET_ROOT=/docker/chummercomplete/chummer.run-services/Chummer.Portal/downloads
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
        if member.isdir():
            continue
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
python3 -c 'import os, json, pathlib; manifest_path=pathlib.Path(os.environ['"'"'TARGET_ROOT'"'"']) / '"'"'external-proof-manifest.json'"'"'; expected=json.loads('"'"'{"host": "macos", "request_count": 1, "requests": [{"expected_installer_bundle_relative_path": "files/chummer-avalonia-osx-arm64-installer.dmg", "expected_installer_sha256": "c82393b1bcff3897faf2ea9255e8775ccc1cefa512b3e16a7cb06e52ba48b07e", "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json", "tuple_id": "avalonia:osx-arm64:macos"}], "schema_version": 1}'"'"'); assert manifest_path.is_file(), '"'"'external-proof-bundle-manifest-missing:'"'"' + str(manifest_path); payload=json.loads(manifest_path.read_text(encoding='"'"'utf-8'"'"')); assert payload == expected, '"'"'external-proof-bundle-manifest-mismatch:'"'"' + str(manifest_path) + '"'"':expected='"'"' + json.dumps(expected, sort_keys=True) + '"'"':actual='"'"' + json.dumps(payload, sort_keys=True)'
test -s "$TARGET_ROOT/files/chummer-avalonia-osx-arm64-installer.dmg"
test -s "$TARGET_ROOT/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json"
python3 -c 'import hashlib, os, pathlib; target_root=pathlib.Path(os.environ['"'"'TARGET_ROOT'"'"']); tuple_id='"'"'avalonia:osx-arm64:macos'"'"'; relative='"'"'files/chummer-avalonia-osx-arm64-installer.dmg'"'"'; expected='"'"'c82393b1bcff3897faf2ea9255e8775ccc1cefa512b3e16a7cb06e52ba48b07e'"'"'; path=target_root / relative; assert path.is_file(), f'"'"'external-proof-bundle-installer-missing:{tuple_id}:{path}'"'"'; digest=hashlib.sha256(path.read_bytes()).hexdigest().lower(); assert digest==expected, f'"'"'installer-contract-mismatch:{tuple_id}:{path}:digest={digest}:expected={expected}'"'"''
python3 -c 'import datetime as dt, json, os, pathlib; target_root=pathlib.Path(os.environ['"'"'TARGET_ROOT'"'"']); relative='"'"'startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json'"'"'; max_age_seconds=604800; max_future_skew_seconds=300; path=target_root / relative; assert path.is_file(), '"'"'external-proof-bundle-receipt-missing:'"'"' + str(path); payload=json.loads(path.read_text(encoding='"'"'utf-8'"'"')); payload=payload if isinstance(payload, dict) else {}; raw=next((str(payload.get(key) or '"'"''"'"').strip() for key in ('"'"'recordedAtUtc'"'"','"'"'completedAtUtc'"'"','"'"'generatedAt'"'"','"'"'generated_at'"'"','"'"'startedAtUtc'"'"') if str(payload.get(key) or '"'"''"'"').strip()), '"'"''"'"'); assert raw, '"'"'startup-smoke-receipt-timestamp-missing:'"'"' + str(path); raw = raw[:-1] + '"'"'+00:00'"'"' if raw.endswith('"'"'Z'"'"') else raw; parsed=dt.datetime.fromisoformat(raw); parsed=parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=dt.timezone.utc); parsed=parsed.astimezone(dt.timezone.utc); now=dt.datetime.now(dt.timezone.utc); age_seconds=int((now-parsed).total_seconds()); assert age_seconds >= -max_future_skew_seconds, '"'"'startup-smoke-receipt-future-skew:'"'"' + str(path) + f'"'"':age_seconds={age_seconds}:max_future_skew_seconds={max_future_skew_seconds}'"'"'; age_seconds = 0 if age_seconds < 0 else age_seconds; assert age_seconds <= max_age_seconds, '"'"'startup-smoke-receipt-stale:'"'"' + str(path) + f'"'"':age_seconds={age_seconds}:max_age_seconds={max_age_seconds}'"'"''
python3 -c 'import json, os, pathlib; target_root=pathlib.Path(os.environ['"'"'TARGET_ROOT'"'"']); tuple_id='"'"'avalonia:osx-arm64:macos'"'"'; relative='"'"'startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json'"'"'; contract=json.loads('"'"'{"head_id": "avalonia", "host_class_contains": "macos", "platform": "macos", "ready_checkpoint": "pre_ui_event_loop", "rid": "osx-arm64", "status_any_of": ["pass", "passed", "ready"]}'"'"'); path=target_root / relative; assert path.is_file(), f'"'"'external-proof-bundle-receipt-missing:{tuple_id}:{path}'"'"'; payload=json.loads(path.read_text(encoding='"'"'utf-8'"'"')); payload=payload if isinstance(payload, dict) else {}; status=str(payload.get('"'"'status'"'"') or '"'"''"'"').strip().lower(); expected_statuses=[str(token).strip().lower() for token in (contract.get('"'"'status_any_of'"'"') or []) if str(token).strip()]; head_id=str(payload.get('"'"'headId'"'"') or '"'"''"'"').strip().lower(); platform=str(payload.get('"'"'platform'"'"') or '"'"''"'"').strip().lower(); rid=str(payload.get('"'"'rid'"'"') or '"'"''"'"').strip().lower(); ready_checkpoint=str(payload.get('"'"'readyCheckpoint'"'"') or '"'"''"'"').strip().lower(); host_class=str(payload.get('"'"'hostClass'"'"') or '"'"''"'"').strip().lower(); expected_head=str(contract.get('"'"'head_id'"'"') or '"'"''"'"').strip().lower(); expected_platform=str(contract.get('"'"'platform'"'"') or '"'"''"'"').strip().lower(); expected_rid=str(contract.get('"'"'rid'"'"') or '"'"''"'"').strip().lower(); expected_ready=str(contract.get('"'"'ready_checkpoint'"'"') or '"'"''"'"').strip().lower(); expected_host_contains=str(contract.get('"'"'host_class_contains'"'"') or '"'"''"'"').strip().lower(); assert ((not expected_statuses or status in expected_statuses) and (not expected_head or head_id == expected_head) and (not expected_platform or platform == expected_platform) and (not expected_rid or rid == expected_rid) and (not expected_ready or ready_checkpoint == expected_ready) and (not expected_host_contains or expected_host_contains in host_class), f'"'"'receipt-contract-mismatch:{tuple_id}:{path}:status={status}:head={head_id}:platform={platform}:rid={rid}:ready={ready_checkpoint}:host_class={host_class}:contract={contract}'"'"')'
echo "Host proof bundle ingest complete: $BUNDLE_ARCHIVE"
```

### Commands (Host Lane)

```bash
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$SCRIPT_DIR"
if [ -f "$SCRIPT_DIR/proof-host.env" ]; then
  set -a
  . "$SCRIPT_DIR/proof-host.env"
  set +a
fi
./preflight-macos-proof.sh
./capture-macos-proof.sh
./validate-macos-proof.sh
./bundle-macos-proof.sh
if [ "${CHUMMER_EXTERNAL_PROOF_AUTO_FINALIZE:-0}" = "1" ]; then
  if [ -x "$SCRIPT_DIR/finalize-external-host-proof.sh" ] && [ -d /docker/fleet ] && [ -d /docker/chummercomplete ]; then
    "$SCRIPT_DIR/finalize-external-host-proof.sh"
  else
    echo 'external-proof-auto-finalize-blocked: finalize-external-host-proof.sh requires the shared /docker/fleet and /docker/chummercomplete workspace on this host. Either mount the shared workspace or unset CHUMMER_EXTERNAL_PROOF_AUTO_FINALIZE and return the proof bundle for manual ingest.' >&2
    exit 1
  fi
fi
```

Set `CHUMMER_EXTERNAL_PROOF_AUTO_FINALIZE=1` to make the retained host-lane script ingest and republish automatically when the shared `/docker/fleet` and `/docker/chummercomplete` workspace is mounted on the proof host.

## Host: windows

- shell_hint: Run canonical commands in Git Bash (or WSL bash). PowerShell wrappers are provided below when you need to stay in PowerShell.
- platform_hint: Windows proofs require `powershell.exe` or `pwsh` on the proof host.
- request_count: 1
- tuples: avalonia:win-x64:windows
- cached_bundle_status: `stale_directory`
- cached_bundle_detail: `manifest_mismatch:/docker/fleet/.codex-studio/published/external-proof-commands/host-proof-bundles/windows/external-proof-manifest.json`
- cached_bundle_archive_path: `/docker/fleet/.codex-studio/published/external-proof-commands/windows-proof-bundle.tgz`
- cached_bundle_directory_path: `/docker/fleet/.codex-studio/published/external-proof-commands/host-proof-bundles/windows`
- command_pack_path: `/docker/fleet/.codex-studio/published/external-proof-commands/windows-proof-command-pack.tgz`
- command_pack_present: `true`
- command_pack_sha256_path: `/docker/fleet/.codex-studio/published/external-proof-commands/windows-proof-command-pack.tgz.sha256`
- command_pack_sha256: `bc9654a1ced7787b6ecc7771df6b7c8cb61236790365904ef496f02efeb820e4`

### Command Pack Verification

Transfer the command pack, its SHA sidecar, and the retained prepare script to the native proof host. The prepare script verifies the archive and unpacks it into the target directory.
After unpacking, use `README.md` and `proof-host.env.example` in the extracted folder as the host-local checklist before you run the lane.

```bash
bash prepare-windows-proof-command-pack.sh windows-proof-command-pack.tgz windows-proof-command-pack.tgz.sha256
```

```powershell
& .\prepare-windows-proof-command-pack.ps1 windows-proof-command-pack.tgz windows-proof-command-pack.tgz.sha256
```

### Requested Tuples

- `avalonia:win-x64:windows`
  required_proofs: `promoted_installer_artifact, startup_smoke_receipt`
  artifact_id: `avalonia-win-x64-installer`
  installer_file: `chummer-avalonia-win-x64-installer.exe`
  installer_relative_path: `files/chummer-avalonia-win-x64-installer.exe`
  installer_sha256: `54966da8ac6f1ca7321b301b025bfb626398f461c78441c132d5c59d9c2bedde`
  public_route: `/downloads/install/avalonia-win-x64-installer`
  startup_smoke_receipt: `startup-smoke/startup-smoke-avalonia-win-x64.receipt.json`
  local_installer_state: `present_sha256_match`
  local_installer_path: `/docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe`
  local_startup_smoke_receipt_state: `stale`
  local_startup_smoke_receipt_path: `/docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json`
  local_startup_smoke_receipt_recorded_at: `2026-05-21T19:52:05.2855129+00:00`
  local_startup_smoke_receipt_age_seconds: `654045`
  capture_deadline_utc: `2026-05-30T08:34:38Z`
  capture_deadline_state: `pending`
  commands:
    - `REPO_ROOT="${CHUMMER_UI_REPO_ROOT:-/docker/chummercomplete/chummer6-ui}" && export REPO_ROOT && if [ -z "${CHUMMER_UI_REPO_ROOT:-}" ] && [ ! -d "$REPO_ROOT" ]; then for candidate in /docker/chummercomplete/chummer6-ui /docker/chummercomplete/chummer6-ui-finish /docker/chummercomplete/chummer-presentation; do if [ -d "$candidate" ]; then REPO_ROOT="$candidate" && export REPO_ROOT && break; fi; done; fi && DOWNLOADS_ROOT="$REPO_ROOT/Docker/Downloads" && export DOWNLOADS_ROOT && INSTALLER_PATH="$DOWNLOADS_ROOT/files/chummer-avalonia-win-x64-installer.exe" && export INSTALLER_PATH && cd "$REPO_ROOT" && mkdir -p "$(dirname "$INSTALLER_PATH")" && python3 -c 'import hashlib, os, pathlib; p=pathlib.Path(os.environ['"'"'INSTALLER_PATH'"'"']); expected='"'"'54966da8ac6f1ca7321b301b025bfb626398f461c78441c132d5c59d9c2bedde'"'"'; import sys; sys.exit(0) if (not p.is_file()) else None; digest=hashlib.sha256(p.read_bytes()).hexdigest().lower(); sys.exit(0) if digest==expected else print(f'"'"'installer-preflight-sha256-mismatch:{p}:digest={digest}:expected={expected}'"'"') or p.unlink()' && if [ ! -s "$INSTALLER_PATH" ]; then if [ -z "${CHUMMER_EXTERNAL_PROOF_AUTH_HEADER:-}" ] && [ -z "${CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER:-}" ] && [ -z "${CHUMMER_EXTERNAL_PROOF_COOKIE_JAR:-}" ] && [ "${CHUMMER_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD:-0}" != "1" ]; then echo 'external-proof-auth-missing: set CHUMMER_EXTERNAL_PROOF_AUTH_HEADER, CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER, or CHUMMER_EXTERNAL_PROOF_COOKIE_JAR (or set CHUMMER_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD=1 to bypass)' >&2; exit 1; fi; set -- curl -fL --retry 3 --retry-delay 2; if [ -n "${CHUMMER_EXTERNAL_PROOF_AUTH_HEADER:-}" ]; then set -- "$@" -H "${CHUMMER_EXTERNAL_PROOF_AUTH_HEADER:-}"; fi; if [ -n "${CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER:-}" ]; then set -- "$@" -H "Cookie: ${CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER:-}"; fi; if [ -n "${CHUMMER_EXTERNAL_PROOF_COOKIE_JAR:-}" ]; then set -- "$@" --cookie "${CHUMMER_EXTERNAL_PROOF_COOKIE_JAR:-}"; fi; set -- "$@" "${CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}/downloads/install/avalonia-win-x64-installer" -o "$INSTALLER_PATH"; "$@"; fi; python3 -c 'import os, pathlib, sys; p=pathlib.Path(os.environ['"'"'INSTALLER_PATH'"'"']); expected_magic='"'"'MZ'"'"'; sys.exit(f'"'"'installer-download-missing:{p}'"'"') if (not p.is_file()) else None; probe=p.read_bytes()[:8192]; probe_text=probe.decode('"'"'latin-1'"'"', errors='"'"'ignore'"'"').lower(); auth_header_set=bool(str(os.environ.get('"'"'CHUMMER_EXTERNAL_PROOF_AUTH_HEADER'"'"','"'"''"'"')).strip()); cookie_header_set=bool(str(os.environ.get('"'"'CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER'"'"','"'"''"'"')).strip()); cookie_jar_set=bool(str(os.environ.get('"'"'CHUMMER_EXTERNAL_PROOF_COOKIE_JAR'"'"','"'"''"'"')).strip()); html_like=('"'"'<!doctype html'"'"' in probe_text) or ('"'"'<html'"'"' in probe_text) or ('"'"'<head'"'"' in probe_text); sys.exit(f'"'"'installer-download-html-response:{p}:auth_header_set={auth_header_set}:cookie_header_set={cookie_header_set}:cookie_jar_set={cookie_jar_set}:hint=signed-in-download-route-required-or-missing-auth'"'"') if html_like else None; sys.exit(0) if (not expected_magic or probe.startswith(expected_magic.encode('"'"'latin-1'"'"'))) else sys.exit(f'"'"'installer-download-signature-mismatch:{p}:expected_magic={expected_magic}:auth_header_set={auth_header_set}:cookie_header_set={cookie_header_set}:cookie_jar_set={cookie_jar_set}:hint=unexpected-binary-format-or-route-response'"'"')'; python3 -c 'import hashlib, os, pathlib, sys; p=pathlib.Path(os.environ['"'"'INSTALLER_PATH'"'"']); expected='"'"'54966da8ac6f1ca7321b301b025bfb626398f461c78441c132d5c59d9c2bedde'"'"'; sys.exit(f'"'"'installer-download-missing:{p}'"'"') if (not p.is_file()) else None; digest=hashlib.sha256(p.read_bytes()).hexdigest().lower(); auth_header_set=bool(str(os.environ.get('"'"'CHUMMER_EXTERNAL_PROOF_AUTH_HEADER'"'"','"'"''"'"')).strip()); cookie_header_set=bool(str(os.environ.get('"'"'CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER'"'"','"'"''"'"')).strip()); cookie_jar_set=bool(str(os.environ.get('"'"'CHUMMER_EXTERNAL_PROOF_COOKIE_JAR'"'"','"'"''"'"')).strip()); sys.exit(0) if digest==expected else sys.exit(f'"'"'installer-postdownload-sha256-mismatch:{p}:digest={digest}:expected={expected}:auth_header_set={auth_header_set}:cookie_header_set={cookie_header_set}:cookie_jar_set={cookie_jar_set}:hint=signed-in-download-route-required-or-bytes-drift'"'"')'`
    - `REPO_ROOT="${CHUMMER_UI_REPO_ROOT:-/docker/chummercomplete/chummer6-ui}" && export REPO_ROOT && INSTALLER_PATH="$REPO_ROOT/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe" && STARTUP_SMOKE_DIR="$REPO_ROOT/Docker/Downloads/startup-smoke" && cd "$REPO_ROOT" && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=Windows ./scripts/run-desktop-startup-smoke.sh "$INSTALLER_PATH" avalonia win-x64 Chummer.Avalonia.exe "$STARTUP_SMOKE_DIR" run-20260518-220935`
    - `REPO_ROOT="${CHUMMER_UI_REPO_ROOT:-/docker/chummercomplete/chummer6-ui}" && export REPO_ROOT && cd "$REPO_ROOT" && ./scripts/generate-releases-manifest.sh`

### Commands (Host Consolidated)

```bash
REPO_ROOT="${CHUMMER_UI_REPO_ROOT:-/docker/chummercomplete/chummer6-ui}" && export REPO_ROOT && if [ -z "${CHUMMER_UI_REPO_ROOT:-}" ] && [ ! -d "$REPO_ROOT" ]; then for candidate in /docker/chummercomplete/chummer6-ui /docker/chummercomplete/chummer6-ui-finish /docker/chummercomplete/chummer-presentation; do if [ -d "$candidate" ]; then REPO_ROOT="$candidate" && export REPO_ROOT && break; fi; done; fi && DOWNLOADS_ROOT="$REPO_ROOT/Docker/Downloads" && export DOWNLOADS_ROOT && INSTALLER_PATH="$DOWNLOADS_ROOT/files/chummer-avalonia-win-x64-installer.exe" && export INSTALLER_PATH && cd "$REPO_ROOT" && mkdir -p "$(dirname "$INSTALLER_PATH")" && python3 -c 'import hashlib, os, pathlib; p=pathlib.Path(os.environ['"'"'INSTALLER_PATH'"'"']); expected='"'"'54966da8ac6f1ca7321b301b025bfb626398f461c78441c132d5c59d9c2bedde'"'"'; import sys; sys.exit(0) if (not p.is_file()) else None; digest=hashlib.sha256(p.read_bytes()).hexdigest().lower(); sys.exit(0) if digest==expected else print(f'"'"'installer-preflight-sha256-mismatch:{p}:digest={digest}:expected={expected}'"'"') or p.unlink()' && if [ ! -s "$INSTALLER_PATH" ]; then if [ -z "${CHUMMER_EXTERNAL_PROOF_AUTH_HEADER:-}" ] && [ -z "${CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER:-}" ] && [ -z "${CHUMMER_EXTERNAL_PROOF_COOKIE_JAR:-}" ] && [ "${CHUMMER_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD:-0}" != "1" ]; then echo 'external-proof-auth-missing: set CHUMMER_EXTERNAL_PROOF_AUTH_HEADER, CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER, or CHUMMER_EXTERNAL_PROOF_COOKIE_JAR (or set CHUMMER_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD=1 to bypass)' >&2; exit 1; fi; set -- curl -fL --retry 3 --retry-delay 2; if [ -n "${CHUMMER_EXTERNAL_PROOF_AUTH_HEADER:-}" ]; then set -- "$@" -H "${CHUMMER_EXTERNAL_PROOF_AUTH_HEADER:-}"; fi; if [ -n "${CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER:-}" ]; then set -- "$@" -H "Cookie: ${CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER:-}"; fi; if [ -n "${CHUMMER_EXTERNAL_PROOF_COOKIE_JAR:-}" ]; then set -- "$@" --cookie "${CHUMMER_EXTERNAL_PROOF_COOKIE_JAR:-}"; fi; set -- "$@" "${CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}/downloads/install/avalonia-win-x64-installer" -o "$INSTALLER_PATH"; "$@"; fi; python3 -c 'import os, pathlib, sys; p=pathlib.Path(os.environ['"'"'INSTALLER_PATH'"'"']); expected_magic='"'"'MZ'"'"'; sys.exit(f'"'"'installer-download-missing:{p}'"'"') if (not p.is_file()) else None; probe=p.read_bytes()[:8192]; probe_text=probe.decode('"'"'latin-1'"'"', errors='"'"'ignore'"'"').lower(); auth_header_set=bool(str(os.environ.get('"'"'CHUMMER_EXTERNAL_PROOF_AUTH_HEADER'"'"','"'"''"'"')).strip()); cookie_header_set=bool(str(os.environ.get('"'"'CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER'"'"','"'"''"'"')).strip()); cookie_jar_set=bool(str(os.environ.get('"'"'CHUMMER_EXTERNAL_PROOF_COOKIE_JAR'"'"','"'"''"'"')).strip()); html_like=('"'"'<!doctype html'"'"' in probe_text) or ('"'"'<html'"'"' in probe_text) or ('"'"'<head'"'"' in probe_text); sys.exit(f'"'"'installer-download-html-response:{p}:auth_header_set={auth_header_set}:cookie_header_set={cookie_header_set}:cookie_jar_set={cookie_jar_set}:hint=signed-in-download-route-required-or-missing-auth'"'"') if html_like else None; sys.exit(0) if (not expected_magic or probe.startswith(expected_magic.encode('"'"'latin-1'"'"'))) else sys.exit(f'"'"'installer-download-signature-mismatch:{p}:expected_magic={expected_magic}:auth_header_set={auth_header_set}:cookie_header_set={cookie_header_set}:cookie_jar_set={cookie_jar_set}:hint=unexpected-binary-format-or-route-response'"'"')'; python3 -c 'import hashlib, os, pathlib, sys; p=pathlib.Path(os.environ['"'"'INSTALLER_PATH'"'"']); expected='"'"'54966da8ac6f1ca7321b301b025bfb626398f461c78441c132d5c59d9c2bedde'"'"'; sys.exit(f'"'"'installer-download-missing:{p}'"'"') if (not p.is_file()) else None; digest=hashlib.sha256(p.read_bytes()).hexdigest().lower(); auth_header_set=bool(str(os.environ.get('"'"'CHUMMER_EXTERNAL_PROOF_AUTH_HEADER'"'"','"'"''"'"')).strip()); cookie_header_set=bool(str(os.environ.get('"'"'CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER'"'"','"'"''"'"')).strip()); cookie_jar_set=bool(str(os.environ.get('"'"'CHUMMER_EXTERNAL_PROOF_COOKIE_JAR'"'"','"'"''"'"')).strip()); sys.exit(0) if digest==expected else sys.exit(f'"'"'installer-postdownload-sha256-mismatch:{p}:digest={digest}:expected={expected}:auth_header_set={auth_header_set}:cookie_header_set={cookie_header_set}:cookie_jar_set={cookie_jar_set}:hint=signed-in-download-route-required-or-bytes-drift'"'"')'
REPO_ROOT="${CHUMMER_UI_REPO_ROOT:-/docker/chummercomplete/chummer6-ui}" && export REPO_ROOT && INSTALLER_PATH="$REPO_ROOT/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe" && STARTUP_SMOKE_DIR="$REPO_ROOT/Docker/Downloads/startup-smoke" && cd "$REPO_ROOT" && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=Windows ./scripts/run-desktop-startup-smoke.sh "$INSTALLER_PATH" avalonia win-x64 Chummer.Avalonia.exe "$STARTUP_SMOKE_DIR" run-20260518-220935
REPO_ROOT="${CHUMMER_UI_REPO_ROOT:-/docker/chummercomplete/chummer6-ui}" && export REPO_ROOT && cd "$REPO_ROOT" && ./scripts/generate-releases-manifest.sh
```

### Commands (Host Preflight)

```bash
if ! command -v python3 >/dev/null 2>&1; then echo 'external-proof-python3-missing' >&2; exit 1; fi
if ! command -v curl >/dev/null 2>&1; then echo 'external-proof-curl-missing' >&2; exit 1; fi
if [ -z "${CHUMMER_UI_REPO_ROOT:-}" ] && [ ! -d /docker/chummercomplete/chummer6-ui ] && [ ! -d /docker/chummercomplete/chummer6-ui-finish ] && [ ! -d /docker/chummercomplete/chummer-presentation ]; then echo 'external-proof-ui-repo-root-missing: set CHUMMER_UI_REPO_ROOT if the UI repo is not checked out at /docker/chummercomplete/chummer6-ui, /docker/chummercomplete/chummer6-ui-finish, /docker/chummercomplete/chummer-presentation on the proof host' >&2; exit 1; fi
if ! command -v powershell.exe >/dev/null 2>&1 && ! command -v pwsh >/dev/null 2>&1; then echo 'external-proof-powershell-missing' >&2; echo 'Hint: run this lane on a Windows host (Git Bash wrapper is supported for bash commands). ' >&2; exit 1; fi
if ! command -v bash >/dev/null 2>&1; then echo 'external-proof-bash-missing' >&2; echo 'Hint: install Git Bash or run the lane from WSL so the generated shell commands can execute.' >&2; exit 1; fi
if [ -z "${CHUMMER_EXTERNAL_PROOF_AUTH_HEADER:-}" ] && [ -z "${CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER:-}" ] && [ -z "${CHUMMER_EXTERNAL_PROOF_COOKIE_JAR:-}" ] && [ "${CHUMMER_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD:-0}" != "1" ]; then echo 'external-proof-auth-missing: set CHUMMER_EXTERNAL_PROOF_AUTH_HEADER, CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER, or CHUMMER_EXTERNAL_PROOF_COOKIE_JAR (or set CHUMMER_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD=1 to bypass)' >&2; exit 1; fi
```

### Commands (Host Validation)

```bash
REPO_ROOT="${CHUMMER_UI_REPO_ROOT:-/docker/chummercomplete/chummer6-ui}" && export REPO_ROOT && if [ -z "${CHUMMER_UI_REPO_ROOT:-}" ] && [ ! -d "$REPO_ROOT" ]; then for candidate in /docker/chummercomplete/chummer6-ui /docker/chummercomplete/chummer6-ui-finish /docker/chummercomplete/chummer-presentation; do if [ -d "$candidate" ]; then REPO_ROOT="$candidate" && export REPO_ROOT && break; fi; done; fi && DOWNLOADS_ROOT="$REPO_ROOT/Docker/Downloads" && export DOWNLOADS_ROOT && INSTALLER_PATH="$DOWNLOADS_ROOT/files/chummer-avalonia-win-x64-installer.exe" && export INSTALLER_PATH && cd "$REPO_ROOT" && test -s "$INSTALLER_PATH"
REPO_ROOT="${CHUMMER_UI_REPO_ROOT:-/docker/chummercomplete/chummer6-ui}" && export REPO_ROOT && if [ -z "${CHUMMER_UI_REPO_ROOT:-}" ] && [ ! -d "$REPO_ROOT" ]; then for candidate in /docker/chummercomplete/chummer6-ui /docker/chummercomplete/chummer6-ui-finish /docker/chummercomplete/chummer-presentation; do if [ -d "$candidate" ]; then REPO_ROOT="$candidate" && export REPO_ROOT && break; fi; done; fi && DOWNLOADS_ROOT="$REPO_ROOT/Docker/Downloads" && export DOWNLOADS_ROOT && INSTALLER_PATH="$DOWNLOADS_ROOT/files/chummer-avalonia-win-x64-installer.exe" && export INSTALLER_PATH && cd "$REPO_ROOT" && python3 -c 'import hashlib, os, pathlib, sys; p=pathlib.Path(os.environ['"'"'INSTALLER_PATH'"'"']); expected='"'"'54966da8ac6f1ca7321b301b025bfb626398f461c78441c132d5c59d9c2bedde'"'"'; digest=hashlib.sha256(p.read_bytes()).hexdigest().lower(); sys.exit(0) if digest==expected else sys.exit(f'"'"'installer-contract-mismatch:{p}:digest={digest}:expected={expected}'"'"')'
REPO_ROOT="${CHUMMER_UI_REPO_ROOT:-/docker/chummercomplete/chummer6-ui}" && export REPO_ROOT && if [ -z "${CHUMMER_UI_REPO_ROOT:-}" ] && [ ! -d "$REPO_ROOT" ]; then for candidate in /docker/chummercomplete/chummer6-ui /docker/chummercomplete/chummer6-ui-finish /docker/chummercomplete/chummer-presentation; do if [ -d "$candidate" ]; then REPO_ROOT="$candidate" && export REPO_ROOT && break; fi; done; fi && DOWNLOADS_ROOT="$REPO_ROOT/Docker/Downloads" && export DOWNLOADS_ROOT && RECEIPT_PATH="$DOWNLOADS_ROOT/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json" && export RECEIPT_PATH && cd "$REPO_ROOT" && test -s "$RECEIPT_PATH"
REPO_ROOT="${CHUMMER_UI_REPO_ROOT:-/docker/chummercomplete/chummer6-ui}" && export REPO_ROOT && if [ -z "${CHUMMER_UI_REPO_ROOT:-}" ] && [ ! -d "$REPO_ROOT" ]; then for candidate in /docker/chummercomplete/chummer6-ui /docker/chummercomplete/chummer6-ui-finish /docker/chummercomplete/chummer-presentation; do if [ -d "$candidate" ]; then REPO_ROOT="$candidate" && export REPO_ROOT && break; fi; done; fi && DOWNLOADS_ROOT="$REPO_ROOT/Docker/Downloads" && export DOWNLOADS_ROOT && RECEIPT_PATH="$DOWNLOADS_ROOT/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json" && export RECEIPT_PATH && cd "$REPO_ROOT" && python3 -c 'import datetime as dt, json, os, pathlib, sys; p=pathlib.Path(os.environ['"'"'RECEIPT_PATH'"'"']); max_age_seconds=604800; max_future_skew_seconds=300; payload=json.loads(p.read_text(encoding='"'"'utf-8'"'"')); payload=payload if isinstance(payload, dict) else {}; raw=next((str(payload.get(key) or '"'"''"'"').strip() for key in ('"'"'recordedAtUtc'"'"','"'"'completedAtUtc'"'"','"'"'generatedAt'"'"','"'"'generated_at'"'"','"'"'startedAtUtc'"'"') if str(payload.get(key) or '"'"''"'"').strip()), '"'"''"'"'); sys.exit(f'"'"'startup-smoke-receipt-timestamp-missing:{p}'"'"') if not raw else None; raw = raw[:-1] + '"'"'+00:00'"'"' if raw.endswith('"'"'Z'"'"') else raw; parsed=dt.datetime.fromisoformat(raw); parsed=parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=dt.timezone.utc); parsed=parsed.astimezone(dt.timezone.utc); now=dt.datetime.now(dt.timezone.utc); age_seconds=int((now-parsed).total_seconds()); sys.exit(f'"'"'startup-smoke-receipt-future-skew:{p}:age_seconds={age_seconds}:max_future_skew_seconds={max_future_skew_seconds}'"'"') if age_seconds < -max_future_skew_seconds else None; age_seconds = 0 if age_seconds < 0 else age_seconds; sys.exit(0) if age_seconds <= max_age_seconds else sys.exit(f'"'"'startup-smoke-receipt-stale:{p}:age_seconds={age_seconds}:max_age_seconds={max_age_seconds}'"'"')'
REPO_ROOT="${CHUMMER_UI_REPO_ROOT:-/docker/chummercomplete/chummer6-ui}" && export REPO_ROOT && if [ -z "${CHUMMER_UI_REPO_ROOT:-}" ] && [ ! -d "$REPO_ROOT" ]; then for candidate in /docker/chummercomplete/chummer6-ui /docker/chummercomplete/chummer6-ui-finish /docker/chummercomplete/chummer-presentation; do if [ -d "$candidate" ]; then REPO_ROOT="$candidate" && export REPO_ROOT && break; fi; done; fi && DOWNLOADS_ROOT="$REPO_ROOT/Docker/Downloads" && export DOWNLOADS_ROOT && RECEIPT_PATH="$DOWNLOADS_ROOT/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json" && export RECEIPT_PATH && cd "$REPO_ROOT" && python3 -c 'import json, os, pathlib, sys; p=pathlib.Path(os.environ['"'"'RECEIPT_PATH'"'"']); contract=json.loads('"'"'{"head_id": "avalonia", "host_class_contains": "windows", "platform": "windows", "ready_checkpoint": "pre_ui_event_loop", "rid": "win-x64", "status_any_of": ["pass", "passed", "ready"]}'"'"'); payload=json.loads(p.read_text(encoding='"'"'utf-8'"'"')); payload=payload if isinstance(payload, dict) else {}; status=str(payload.get('"'"'status'"'"') or '"'"''"'"').strip().lower(); expected_statuses=[str(token).strip().lower() for token in (contract.get('"'"'status_any_of'"'"') or []) if str(token).strip()]; head_id=str(payload.get('"'"'headId'"'"') or '"'"''"'"').strip().lower(); platform=str(payload.get('"'"'platform'"'"') or '"'"''"'"').strip().lower(); rid=str(payload.get('"'"'rid'"'"') or '"'"''"'"').strip().lower(); ready_checkpoint=str(payload.get('"'"'readyCheckpoint'"'"') or '"'"''"'"').strip().lower(); host_class=str(payload.get('"'"'hostClass'"'"') or '"'"''"'"').strip().lower(); expected_head=str(contract.get('"'"'head_id'"'"') or '"'"''"'"').strip().lower(); expected_platform=str(contract.get('"'"'platform'"'"') or '"'"''"'"').strip().lower(); expected_rid=str(contract.get('"'"'rid'"'"') or '"'"''"'"').strip().lower(); expected_ready=str(contract.get('"'"'ready_checkpoint'"'"') or '"'"''"'"').strip().lower(); expected_host_contains=str(contract.get('"'"'host_class_contains'"'"') or '"'"''"'"').strip().lower(); sys.exit(0) if ((not expected_statuses or status in expected_statuses) and (not expected_head or head_id == expected_head) and (not expected_platform or platform == expected_platform) and (not expected_rid or rid == expected_rid) and (not expected_ready or ready_checkpoint == expected_ready) and (not expected_host_contains or expected_host_contains in host_class)) else sys.exit(f'"'"'receipt-contract-mismatch:{p}:status={status}:head={head_id}:platform={platform}:rid={rid}:ready={ready_checkpoint}:host_class={host_class}:contract={contract}'"'"')'
REPO_ROOT="${CHUMMER_UI_REPO_ROOT:-/docker/chummercomplete/chummer6-ui}" && export REPO_ROOT && if [ -z "${CHUMMER_UI_REPO_ROOT:-}" ] && [ ! -d "$REPO_ROOT" ]; then for candidate in /docker/chummercomplete/chummer6-ui /docker/chummercomplete/chummer6-ui-finish /docker/chummercomplete/chummer-presentation; do if [ -d "$candidate" ]; then REPO_ROOT="$candidate" && export REPO_ROOT && break; fi; done; fi && DOWNLOADS_ROOT="$REPO_ROOT/Docker/Downloads" && export DOWNLOADS_ROOT && RELEASE_CHANNEL_PATH="$DOWNLOADS_ROOT/RELEASE_CHANNEL.generated.json" && export RELEASE_CHANNEL_PATH && cd "$REPO_ROOT" && python3 -c 'import json, os, pathlib, sys; p=pathlib.Path(os.environ['"'"'RELEASE_CHANNEL_PATH'"'"']); tuple_id='"'"'avalonia:win-x64:windows'"'"'; expected_artifact='"'"'avalonia-win-x64-installer'"'"'; expected_route='"'"'/downloads/install/avalonia-win-x64-installer'"'"'; payload=json.loads(p.read_text(encoding='"'"'utf-8'"'"')); coverage=payload.get('"'"'desktopTupleCoverage'"'"') if isinstance(payload, dict) else {}; coverage=coverage if isinstance(coverage, dict) else {}; rows=coverage.get('"'"'externalProofRequests'"'"') if isinstance(coverage, dict) else []; rows=rows if isinstance(rows, list) else []; row=next((item for item in rows if isinstance(item, dict) and str(item.get('"'"'tupleId'"'"') or item.get('"'"'tuple_id'"'"') or '"'"''"'"').strip()==tuple_id), None); sys.exit(f'"'"'release-channel-contract-mismatch:{tuple_id}:missing-external-proof-row'"'"') if row is None else None; artifact=str(row.get('"'"'expectedArtifactId'"'"') or row.get('"'"'expected_artifact_id'"'"') or '"'"''"'"').strip(); route=str(row.get('"'"'expectedPublicInstallRoute'"'"') or row.get('"'"'expected_public_install_route'"'"') or '"'"''"'"').strip(); artifact_ok=(not expected_artifact) or artifact==expected_artifact; route_ok=(not expected_route) or route==expected_route; sys.exit(0) if artifact_ok and route_ok else sys.exit(f'"'"'release-channel-contract-mismatch:{tuple_id}:artifact={artifact}:expected_artifact={expected_artifact}:route={route}:expected_route={expected_route}'"'"')'
```

### Commands (Host Bundle)

```bash
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="${CHUMMER_UI_REPO_ROOT:-/docker/chummercomplete/chummer6-ui}" && export REPO_ROOT && if [ -z "${CHUMMER_UI_REPO_ROOT:-}" ] && [ ! -d "$REPO_ROOT" ]; then for candidate in /docker/chummercomplete/chummer6-ui /docker/chummercomplete/chummer6-ui-finish /docker/chummercomplete/chummer-presentation; do if [ -d "$candidate" ]; then REPO_ROOT="$candidate" && export REPO_ROOT && break; fi; done; fi && DOWNLOADS_ROOT="$REPO_ROOT/Docker/Downloads" && export DOWNLOADS_ROOT
BUNDLE_ROOT="$SCRIPT_DIR/host-proof-bundles/windows"
BUNDLE_ARCHIVE="$SCRIPT_DIR/windows-proof-bundle.tgz"
export BUNDLE_ROOT
export BUNDLE_ARCHIVE
rm -rf "$BUNDLE_ROOT"
mkdir -p "$BUNDLE_ROOT"
rm -f "$BUNDLE_ARCHIVE"
python3 -c 'import json, os, pathlib; bundle_root=pathlib.Path(os.environ['"'"'BUNDLE_ROOT'"'"']); payload=json.loads('"'"'{"host": "windows", "request_count": 1, "requests": [{"expected_installer_bundle_relative_path": "files/chummer-avalonia-win-x64-installer.exe", "expected_installer_sha256": "54966da8ac6f1ca7321b301b025bfb626398f461c78441c132d5c59d9c2bedde", "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json", "tuple_id": "avalonia:win-x64:windows"}], "schema_version": 1}'"'"'); manifest_path=bundle_root / '"'"'external-proof-manifest.json'"'"'; manifest_path.write_text(json.dumps(payload, sort_keys=True, indent=2) + '"'"'\n'"'"', encoding='"'"'utf-8'"'"')'
mkdir -p "$BUNDLE_ROOT/files"
cp -f "$DOWNLOADS_ROOT/files/chummer-avalonia-win-x64-installer.exe" "$BUNDLE_ROOT/files/chummer-avalonia-win-x64-installer.exe"
mkdir -p "$BUNDLE_ROOT/startup-smoke"
cp -f "$DOWNLOADS_ROOT/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json" "$BUNDLE_ROOT/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json"
tar -czf "$BUNDLE_ARCHIVE" -C "$BUNDLE_ROOT" .
echo "Wrote $BUNDLE_ARCHIVE"
```

### Commands (Host Ingest)

```bash
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
DEFAULT_BUNDLE_ARCHIVE="$SCRIPT_DIR/windows-proof-bundle.tgz"
DEFAULT_BUNDLE_DIR="$SCRIPT_DIR/host-proof-bundles/windows"
BUNDLE_INPUT="${1:-}"
if [ -n "$BUNDLE_INPUT" ] && [ -f "$BUNDLE_INPUT" ]; then
  BUNDLE_ARCHIVE="$BUNDLE_INPUT"
  BUNDLE_DIR="$DEFAULT_BUNDLE_DIR"
elif [ -n "$BUNDLE_INPUT" ] && [ -d "$BUNDLE_INPUT" ]; then
  BUNDLE_ARCHIVE="$DEFAULT_BUNDLE_ARCHIVE"
  BUNDLE_DIR="$BUNDLE_INPUT"
else
  BUNDLE_ARCHIVE="$DEFAULT_BUNDLE_ARCHIVE"
  BUNDLE_DIR="$DEFAULT_BUNDLE_DIR"
fi
export BUNDLE_ARCHIVE
export BUNDLE_DIR
TARGET_ROOT=/docker/chummercomplete/chummer.run-services/Chummer.Portal/downloads
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
        if member.isdir():
            continue
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
python3 -c 'import os, json, pathlib; manifest_path=pathlib.Path(os.environ['"'"'TARGET_ROOT'"'"']) / '"'"'external-proof-manifest.json'"'"'; expected=json.loads('"'"'{"host": "windows", "request_count": 1, "requests": [{"expected_installer_bundle_relative_path": "files/chummer-avalonia-win-x64-installer.exe", "expected_installer_sha256": "54966da8ac6f1ca7321b301b025bfb626398f461c78441c132d5c59d9c2bedde", "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json", "tuple_id": "avalonia:win-x64:windows"}], "schema_version": 1}'"'"'); assert manifest_path.is_file(), '"'"'external-proof-bundle-manifest-missing:'"'"' + str(manifest_path); payload=json.loads(manifest_path.read_text(encoding='"'"'utf-8'"'"')); assert payload == expected, '"'"'external-proof-bundle-manifest-mismatch:'"'"' + str(manifest_path) + '"'"':expected='"'"' + json.dumps(expected, sort_keys=True) + '"'"':actual='"'"' + json.dumps(payload, sort_keys=True)'
test -s "$TARGET_ROOT/files/chummer-avalonia-win-x64-installer.exe"
test -s "$TARGET_ROOT/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json"
python3 -c 'import hashlib, os, pathlib; target_root=pathlib.Path(os.environ['"'"'TARGET_ROOT'"'"']); tuple_id='"'"'avalonia:win-x64:windows'"'"'; relative='"'"'files/chummer-avalonia-win-x64-installer.exe'"'"'; expected='"'"'54966da8ac6f1ca7321b301b025bfb626398f461c78441c132d5c59d9c2bedde'"'"'; path=target_root / relative; assert path.is_file(), f'"'"'external-proof-bundle-installer-missing:{tuple_id}:{path}'"'"'; digest=hashlib.sha256(path.read_bytes()).hexdigest().lower(); assert digest==expected, f'"'"'installer-contract-mismatch:{tuple_id}:{path}:digest={digest}:expected={expected}'"'"''
python3 -c 'import datetime as dt, json, os, pathlib; target_root=pathlib.Path(os.environ['"'"'TARGET_ROOT'"'"']); relative='"'"'startup-smoke/startup-smoke-avalonia-win-x64.receipt.json'"'"'; max_age_seconds=604800; max_future_skew_seconds=300; path=target_root / relative; assert path.is_file(), '"'"'external-proof-bundle-receipt-missing:'"'"' + str(path); payload=json.loads(path.read_text(encoding='"'"'utf-8'"'"')); payload=payload if isinstance(payload, dict) else {}; raw=next((str(payload.get(key) or '"'"''"'"').strip() for key in ('"'"'recordedAtUtc'"'"','"'"'completedAtUtc'"'"','"'"'generatedAt'"'"','"'"'generated_at'"'"','"'"'startedAtUtc'"'"') if str(payload.get(key) or '"'"''"'"').strip()), '"'"''"'"'); assert raw, '"'"'startup-smoke-receipt-timestamp-missing:'"'"' + str(path); raw = raw[:-1] + '"'"'+00:00'"'"' if raw.endswith('"'"'Z'"'"') else raw; parsed=dt.datetime.fromisoformat(raw); parsed=parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=dt.timezone.utc); parsed=parsed.astimezone(dt.timezone.utc); now=dt.datetime.now(dt.timezone.utc); age_seconds=int((now-parsed).total_seconds()); assert age_seconds >= -max_future_skew_seconds, '"'"'startup-smoke-receipt-future-skew:'"'"' + str(path) + f'"'"':age_seconds={age_seconds}:max_future_skew_seconds={max_future_skew_seconds}'"'"'; age_seconds = 0 if age_seconds < 0 else age_seconds; assert age_seconds <= max_age_seconds, '"'"'startup-smoke-receipt-stale:'"'"' + str(path) + f'"'"':age_seconds={age_seconds}:max_age_seconds={max_age_seconds}'"'"''
python3 -c 'import json, os, pathlib; target_root=pathlib.Path(os.environ['"'"'TARGET_ROOT'"'"']); tuple_id='"'"'avalonia:win-x64:windows'"'"'; relative='"'"'startup-smoke/startup-smoke-avalonia-win-x64.receipt.json'"'"'; contract=json.loads('"'"'{"head_id": "avalonia", "host_class_contains": "windows", "platform": "windows", "ready_checkpoint": "pre_ui_event_loop", "rid": "win-x64", "status_any_of": ["pass", "passed", "ready"]}'"'"'); path=target_root / relative; assert path.is_file(), f'"'"'external-proof-bundle-receipt-missing:{tuple_id}:{path}'"'"'; payload=json.loads(path.read_text(encoding='"'"'utf-8'"'"')); payload=payload if isinstance(payload, dict) else {}; status=str(payload.get('"'"'status'"'"') or '"'"''"'"').strip().lower(); expected_statuses=[str(token).strip().lower() for token in (contract.get('"'"'status_any_of'"'"') or []) if str(token).strip()]; head_id=str(payload.get('"'"'headId'"'"') or '"'"''"'"').strip().lower(); platform=str(payload.get('"'"'platform'"'"') or '"'"''"'"').strip().lower(); rid=str(payload.get('"'"'rid'"'"') or '"'"''"'"').strip().lower(); ready_checkpoint=str(payload.get('"'"'readyCheckpoint'"'"') or '"'"''"'"').strip().lower(); host_class=str(payload.get('"'"'hostClass'"'"') or '"'"''"'"').strip().lower(); expected_head=str(contract.get('"'"'head_id'"'"') or '"'"''"'"').strip().lower(); expected_platform=str(contract.get('"'"'platform'"'"') or '"'"''"'"').strip().lower(); expected_rid=str(contract.get('"'"'rid'"'"') or '"'"''"'"').strip().lower(); expected_ready=str(contract.get('"'"'ready_checkpoint'"'"') or '"'"''"'"').strip().lower(); expected_host_contains=str(contract.get('"'"'host_class_contains'"'"') or '"'"''"'"').strip().lower(); assert ((not expected_statuses or status in expected_statuses) and (not expected_head or head_id == expected_head) and (not expected_platform or platform == expected_platform) and (not expected_rid or rid == expected_rid) and (not expected_ready or ready_checkpoint == expected_ready) and (not expected_host_contains or expected_host_contains in host_class), f'"'"'receipt-contract-mismatch:{tuple_id}:{path}:status={status}:head={head_id}:platform={platform}:rid={rid}:ready={ready_checkpoint}:host_class={host_class}:contract={contract}'"'"')'
echo "Host proof bundle ingest complete: $BUNDLE_ARCHIVE"
```

### Commands (Host Lane)

```bash
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$SCRIPT_DIR"
if [ -f "$SCRIPT_DIR/proof-host.env" ]; then
  set -a
  . "$SCRIPT_DIR/proof-host.env"
  set +a
fi
./preflight-windows-proof.sh
./capture-windows-proof.sh
./validate-windows-proof.sh
./bundle-windows-proof.sh
if [ "${CHUMMER_EXTERNAL_PROOF_AUTO_FINALIZE:-0}" = "1" ]; then
  if [ -x "$SCRIPT_DIR/finalize-external-host-proof.sh" ] && [ -d /docker/fleet ] && [ -d /docker/chummercomplete ]; then
    "$SCRIPT_DIR/finalize-external-host-proof.sh"
  else
    echo 'external-proof-auto-finalize-blocked: finalize-external-host-proof.sh requires the shared /docker/fleet and /docker/chummercomplete workspace on this host. Either mount the shared workspace or unset CHUMMER_EXTERNAL_PROOF_AUTO_FINALIZE and return the proof bundle for manual ingest.' >&2
    exit 1
  fi
fi
```

Set `CHUMMER_EXTERNAL_PROOF_AUTO_FINALIZE=1` to make the retained host-lane script ingest and republish automatically when the shared `/docker/fleet` and `/docker/chummercomplete` workspace is mounted on the proof host.

### Commands (PowerShell Preflight Wrappers)

```powershell
bash -lc 'set -euo pipefail
if ! command -v python3 >/dev/null 2>&1; then echo ''external-proof-python3-missing'' >&2; exit 1; fi
if ! command -v curl >/dev/null 2>&1; then echo ''external-proof-curl-missing'' >&2; exit 1; fi
if [ -z "${CHUMMER_UI_REPO_ROOT:-}" ] && [ ! -d /docker/chummercomplete/chummer6-ui ] && [ ! -d /docker/chummercomplete/chummer6-ui-finish ] && [ ! -d /docker/chummercomplete/chummer-presentation ]; then echo ''external-proof-ui-repo-root-missing: set CHUMMER_UI_REPO_ROOT if the UI repo is not checked out at /docker/chummercomplete/chummer6-ui, /docker/chummercomplete/chummer6-ui-finish, /docker/chummercomplete/chummer-presentation on the proof host'' >&2; exit 1; fi
if ! command -v powershell.exe >/dev/null 2>&1 && ! command -v pwsh >/dev/null 2>&1; then echo ''external-proof-powershell-missing'' >&2; echo ''Hint: run this lane on a Windows host (Git Bash wrapper is supported for bash commands). '' >&2; exit 1; fi
if ! command -v bash >/dev/null 2>&1; then echo ''external-proof-bash-missing'' >&2; echo ''Hint: install Git Bash or run the lane from WSL so the generated shell commands can execute.'' >&2; exit 1; fi
if [ -z "${CHUMMER_EXTERNAL_PROOF_AUTH_HEADER:-}" ] && [ -z "${CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER:-}" ] && [ -z "${CHUMMER_EXTERNAL_PROOF_COOKIE_JAR:-}" ] && [ "${CHUMMER_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD:-0}" != "1" ]; then echo ''external-proof-auth-missing: set CHUMMER_EXTERNAL_PROOF_AUTH_HEADER, CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER, or CHUMMER_EXTERNAL_PROOF_COOKIE_JAR (or set CHUMMER_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD=1 to bypass)'' >&2; exit 1; fi'
```

### Commands (PowerShell Wrappers)

```powershell
bash -lc 'set -euo pipefail
REPO_ROOT="${CHUMMER_UI_REPO_ROOT:-/docker/chummercomplete/chummer6-ui}" && export REPO_ROOT && if [ -z "${CHUMMER_UI_REPO_ROOT:-}" ] && [ ! -d "$REPO_ROOT" ]; then for candidate in /docker/chummercomplete/chummer6-ui /docker/chummercomplete/chummer6-ui-finish /docker/chummercomplete/chummer-presentation; do if [ -d "$candidate" ]; then REPO_ROOT="$candidate" && export REPO_ROOT && break; fi; done; fi && DOWNLOADS_ROOT="$REPO_ROOT/Docker/Downloads" && export DOWNLOADS_ROOT && INSTALLER_PATH="$DOWNLOADS_ROOT/files/chummer-avalonia-win-x64-installer.exe" && export INSTALLER_PATH && cd "$REPO_ROOT" && mkdir -p "$(dirname "$INSTALLER_PATH")" && python3 -c ''import hashlib, os, pathlib; p=pathlib.Path(os.environ[''"''"''INSTALLER_PATH''"''"'']); expected=''"''"''54966da8ac6f1ca7321b301b025bfb626398f461c78441c132d5c59d9c2bedde''"''"''; import sys; sys.exit(0) if (not p.is_file()) else None; digest=hashlib.sha256(p.read_bytes()).hexdigest().lower(); sys.exit(0) if digest==expected else print(f''"''"''installer-preflight-sha256-mismatch:{p}:digest={digest}:expected={expected}''"''"'') or p.unlink()'' && if [ ! -s "$INSTALLER_PATH" ]; then if [ -z "${CHUMMER_EXTERNAL_PROOF_AUTH_HEADER:-}" ] && [ -z "${CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER:-}" ] && [ -z "${CHUMMER_EXTERNAL_PROOF_COOKIE_JAR:-}" ] && [ "${CHUMMER_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD:-0}" != "1" ]; then echo ''external-proof-auth-missing: set CHUMMER_EXTERNAL_PROOF_AUTH_HEADER, CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER, or CHUMMER_EXTERNAL_PROOF_COOKIE_JAR (or set CHUMMER_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD=1 to bypass)'' >&2; exit 1; fi; set -- curl -fL --retry 3 --retry-delay 2; if [ -n "${CHUMMER_EXTERNAL_PROOF_AUTH_HEADER:-}" ]; then set -- "$@" -H "${CHUMMER_EXTERNAL_PROOF_AUTH_HEADER:-}"; fi; if [ -n "${CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER:-}" ]; then set -- "$@" -H "Cookie: ${CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER:-}"; fi; if [ -n "${CHUMMER_EXTERNAL_PROOF_COOKIE_JAR:-}" ]; then set -- "$@" --cookie "${CHUMMER_EXTERNAL_PROOF_COOKIE_JAR:-}"; fi; set -- "$@" "${CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}/downloads/install/avalonia-win-x64-installer" -o "$INSTALLER_PATH"; "$@"; fi; python3 -c ''import os, pathlib, sys; p=pathlib.Path(os.environ[''"''"''INSTALLER_PATH''"''"'']); expected_magic=''"''"''MZ''"''"''; sys.exit(f''"''"''installer-download-missing:{p}''"''"'') if (not p.is_file()) else None; probe=p.read_bytes()[:8192]; probe_text=probe.decode(''"''"''latin-1''"''"'', errors=''"''"''ignore''"''"'').lower(); auth_header_set=bool(str(os.environ.get(''"''"''CHUMMER_EXTERNAL_PROOF_AUTH_HEADER''"''"'',''"''"''''"''"'')).strip()); cookie_header_set=bool(str(os.environ.get(''"''"''CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER''"''"'',''"''"''''"''"'')).strip()); cookie_jar_set=bool(str(os.environ.get(''"''"''CHUMMER_EXTERNAL_PROOF_COOKIE_JAR''"''"'',''"''"''''"''"'')).strip()); html_like=(''"''"''<!doctype html''"''"'' in probe_text) or (''"''"''<html''"''"'' in probe_text) or (''"''"''<head''"''"'' in probe_text); sys.exit(f''"''"''installer-download-html-response:{p}:auth_header_set={auth_header_set}:cookie_header_set={cookie_header_set}:cookie_jar_set={cookie_jar_set}:hint=signed-in-download-route-required-or-missing-auth''"''"'') if html_like else None; sys.exit(0) if (not expected_magic or probe.startswith(expected_magic.encode(''"''"''latin-1''"''"''))) else sys.exit(f''"''"''installer-download-signature-mismatch:{p}:expected_magic={expected_magic}:auth_header_set={auth_header_set}:cookie_header_set={cookie_header_set}:cookie_jar_set={cookie_jar_set}:hint=unexpected-binary-format-or-route-response''"''"'')''; python3 -c ''import hashlib, os, pathlib, sys; p=pathlib.Path(os.environ[''"''"''INSTALLER_PATH''"''"'']); expected=''"''"''54966da8ac6f1ca7321b301b025bfb626398f461c78441c132d5c59d9c2bedde''"''"''; sys.exit(f''"''"''installer-download-missing:{p}''"''"'') if (not p.is_file()) else None; digest=hashlib.sha256(p.read_bytes()).hexdigest().lower(); auth_header_set=bool(str(os.environ.get(''"''"''CHUMMER_EXTERNAL_PROOF_AUTH_HEADER''"''"'',''"''"''''"''"'')).strip()); cookie_header_set=bool(str(os.environ.get(''"''"''CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER''"''"'',''"''"''''"''"'')).strip()); cookie_jar_set=bool(str(os.environ.get(''"''"''CHUMMER_EXTERNAL_PROOF_COOKIE_JAR''"''"'',''"''"''''"''"'')).strip()); sys.exit(0) if digest==expected else sys.exit(f''"''"''installer-postdownload-sha256-mismatch:{p}:digest={digest}:expected={expected}:auth_header_set={auth_header_set}:cookie_header_set={cookie_header_set}:cookie_jar_set={cookie_jar_set}:hint=signed-in-download-route-required-or-bytes-drift''"''"'')''
REPO_ROOT="${CHUMMER_UI_REPO_ROOT:-/docker/chummercomplete/chummer6-ui}" && export REPO_ROOT && INSTALLER_PATH="$REPO_ROOT/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe" && STARTUP_SMOKE_DIR="$REPO_ROOT/Docker/Downloads/startup-smoke" && cd "$REPO_ROOT" && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=Windows ./scripts/run-desktop-startup-smoke.sh "$INSTALLER_PATH" avalonia win-x64 Chummer.Avalonia.exe "$STARTUP_SMOKE_DIR" run-20260518-220935
REPO_ROOT="${CHUMMER_UI_REPO_ROOT:-/docker/chummercomplete/chummer6-ui}" && export REPO_ROOT && cd "$REPO_ROOT" && ./scripts/generate-releases-manifest.sh'
```

### Commands (PowerShell Validation Wrappers)

```powershell
bash -lc 'set -euo pipefail
REPO_ROOT="${CHUMMER_UI_REPO_ROOT:-/docker/chummercomplete/chummer6-ui}" && export REPO_ROOT && if [ -z "${CHUMMER_UI_REPO_ROOT:-}" ] && [ ! -d "$REPO_ROOT" ]; then for candidate in /docker/chummercomplete/chummer6-ui /docker/chummercomplete/chummer6-ui-finish /docker/chummercomplete/chummer-presentation; do if [ -d "$candidate" ]; then REPO_ROOT="$candidate" && export REPO_ROOT && break; fi; done; fi && DOWNLOADS_ROOT="$REPO_ROOT/Docker/Downloads" && export DOWNLOADS_ROOT && INSTALLER_PATH="$DOWNLOADS_ROOT/files/chummer-avalonia-win-x64-installer.exe" && export INSTALLER_PATH && cd "$REPO_ROOT" && test -s "$INSTALLER_PATH"
REPO_ROOT="${CHUMMER_UI_REPO_ROOT:-/docker/chummercomplete/chummer6-ui}" && export REPO_ROOT && if [ -z "${CHUMMER_UI_REPO_ROOT:-}" ] && [ ! -d "$REPO_ROOT" ]; then for candidate in /docker/chummercomplete/chummer6-ui /docker/chummercomplete/chummer6-ui-finish /docker/chummercomplete/chummer-presentation; do if [ -d "$candidate" ]; then REPO_ROOT="$candidate" && export REPO_ROOT && break; fi; done; fi && DOWNLOADS_ROOT="$REPO_ROOT/Docker/Downloads" && export DOWNLOADS_ROOT && INSTALLER_PATH="$DOWNLOADS_ROOT/files/chummer-avalonia-win-x64-installer.exe" && export INSTALLER_PATH && cd "$REPO_ROOT" && python3 -c ''import hashlib, os, pathlib, sys; p=pathlib.Path(os.environ[''"''"''INSTALLER_PATH''"''"'']); expected=''"''"''54966da8ac6f1ca7321b301b025bfb626398f461c78441c132d5c59d9c2bedde''"''"''; digest=hashlib.sha256(p.read_bytes()).hexdigest().lower(); sys.exit(0) if digest==expected else sys.exit(f''"''"''installer-contract-mismatch:{p}:digest={digest}:expected={expected}''"''"'')''
REPO_ROOT="${CHUMMER_UI_REPO_ROOT:-/docker/chummercomplete/chummer6-ui}" && export REPO_ROOT && if [ -z "${CHUMMER_UI_REPO_ROOT:-}" ] && [ ! -d "$REPO_ROOT" ]; then for candidate in /docker/chummercomplete/chummer6-ui /docker/chummercomplete/chummer6-ui-finish /docker/chummercomplete/chummer-presentation; do if [ -d "$candidate" ]; then REPO_ROOT="$candidate" && export REPO_ROOT && break; fi; done; fi && DOWNLOADS_ROOT="$REPO_ROOT/Docker/Downloads" && export DOWNLOADS_ROOT && RECEIPT_PATH="$DOWNLOADS_ROOT/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json" && export RECEIPT_PATH && cd "$REPO_ROOT" && test -s "$RECEIPT_PATH"
REPO_ROOT="${CHUMMER_UI_REPO_ROOT:-/docker/chummercomplete/chummer6-ui}" && export REPO_ROOT && if [ -z "${CHUMMER_UI_REPO_ROOT:-}" ] && [ ! -d "$REPO_ROOT" ]; then for candidate in /docker/chummercomplete/chummer6-ui /docker/chummercomplete/chummer6-ui-finish /docker/chummercomplete/chummer-presentation; do if [ -d "$candidate" ]; then REPO_ROOT="$candidate" && export REPO_ROOT && break; fi; done; fi && DOWNLOADS_ROOT="$REPO_ROOT/Docker/Downloads" && export DOWNLOADS_ROOT && RECEIPT_PATH="$DOWNLOADS_ROOT/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json" && export RECEIPT_PATH && cd "$REPO_ROOT" && python3 -c ''import datetime as dt, json, os, pathlib, sys; p=pathlib.Path(os.environ[''"''"''RECEIPT_PATH''"''"'']); max_age_seconds=604800; max_future_skew_seconds=300; payload=json.loads(p.read_text(encoding=''"''"''utf-8''"''"'')); payload=payload if isinstance(payload, dict) else {}; raw=next((str(payload.get(key) or ''"''"''''"''"'').strip() for key in (''"''"''recordedAtUtc''"''"'',''"''"''completedAtUtc''"''"'',''"''"''generatedAt''"''"'',''"''"''generated_at''"''"'',''"''"''startedAtUtc''"''"'') if str(payload.get(key) or ''"''"''''"''"'').strip()), ''"''"''''"''"''); sys.exit(f''"''"''startup-smoke-receipt-timestamp-missing:{p}''"''"'') if not raw else None; raw = raw[:-1] + ''"''"''+00:00''"''"'' if raw.endswith(''"''"''Z''"''"'') else raw; parsed=dt.datetime.fromisoformat(raw); parsed=parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=dt.timezone.utc); parsed=parsed.astimezone(dt.timezone.utc); now=dt.datetime.now(dt.timezone.utc); age_seconds=int((now-parsed).total_seconds()); sys.exit(f''"''"''startup-smoke-receipt-future-skew:{p}:age_seconds={age_seconds}:max_future_skew_seconds={max_future_skew_seconds}''"''"'') if age_seconds < -max_future_skew_seconds else None; age_seconds = 0 if age_seconds < 0 else age_seconds; sys.exit(0) if age_seconds <= max_age_seconds else sys.exit(f''"''"''startup-smoke-receipt-stale:{p}:age_seconds={age_seconds}:max_age_seconds={max_age_seconds}''"''"'')''
REPO_ROOT="${CHUMMER_UI_REPO_ROOT:-/docker/chummercomplete/chummer6-ui}" && export REPO_ROOT && if [ -z "${CHUMMER_UI_REPO_ROOT:-}" ] && [ ! -d "$REPO_ROOT" ]; then for candidate in /docker/chummercomplete/chummer6-ui /docker/chummercomplete/chummer6-ui-finish /docker/chummercomplete/chummer-presentation; do if [ -d "$candidate" ]; then REPO_ROOT="$candidate" && export REPO_ROOT && break; fi; done; fi && DOWNLOADS_ROOT="$REPO_ROOT/Docker/Downloads" && export DOWNLOADS_ROOT && RECEIPT_PATH="$DOWNLOADS_ROOT/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json" && export RECEIPT_PATH && cd "$REPO_ROOT" && python3 -c ''import json, os, pathlib, sys; p=pathlib.Path(os.environ[''"''"''RECEIPT_PATH''"''"'']); contract=json.loads(''"''"''{"head_id": "avalonia", "host_class_contains": "windows", "platform": "windows", "ready_checkpoint": "pre_ui_event_loop", "rid": "win-x64", "status_any_of": ["pass", "passed", "ready"]}''"''"''); payload=json.loads(p.read_text(encoding=''"''"''utf-8''"''"'')); payload=payload if isinstance(payload, dict) else {}; status=str(payload.get(''"''"''status''"''"'') or ''"''"''''"''"'').strip().lower(); expected_statuses=[str(token).strip().lower() for token in (contract.get(''"''"''status_any_of''"''"'') or []) if str(token).strip()]; head_id=str(payload.get(''"''"''headId''"''"'') or ''"''"''''"''"'').strip().lower(); platform=str(payload.get(''"''"''platform''"''"'') or ''"''"''''"''"'').strip().lower(); rid=str(payload.get(''"''"''rid''"''"'') or ''"''"''''"''"'').strip().lower(); ready_checkpoint=str(payload.get(''"''"''readyCheckpoint''"''"'') or ''"''"''''"''"'').strip().lower(); host_class=str(payload.get(''"''"''hostClass''"''"'') or ''"''"''''"''"'').strip().lower(); expected_head=str(contract.get(''"''"''head_id''"''"'') or ''"''"''''"''"'').strip().lower(); expected_platform=str(contract.get(''"''"''platform''"''"'') or ''"''"''''"''"'').strip().lower(); expected_rid=str(contract.get(''"''"''rid''"''"'') or ''"''"''''"''"'').strip().lower(); expected_ready=str(contract.get(''"''"''ready_checkpoint''"''"'') or ''"''"''''"''"'').strip().lower(); expected_host_contains=str(contract.get(''"''"''host_class_contains''"''"'') or ''"''"''''"''"'').strip().lower(); sys.exit(0) if ((not expected_statuses or status in expected_statuses) and (not expected_head or head_id == expected_head) and (not expected_platform or platform == expected_platform) and (not expected_rid or rid == expected_rid) and (not expected_ready or ready_checkpoint == expected_ready) and (not expected_host_contains or expected_host_contains in host_class)) else sys.exit(f''"''"''receipt-contract-mismatch:{p}:status={status}:head={head_id}:platform={platform}:rid={rid}:ready={ready_checkpoint}:host_class={host_class}:contract={contract}''"''"'')''
REPO_ROOT="${CHUMMER_UI_REPO_ROOT:-/docker/chummercomplete/chummer6-ui}" && export REPO_ROOT && if [ -z "${CHUMMER_UI_REPO_ROOT:-}" ] && [ ! -d "$REPO_ROOT" ]; then for candidate in /docker/chummercomplete/chummer6-ui /docker/chummercomplete/chummer6-ui-finish /docker/chummercomplete/chummer-presentation; do if [ -d "$candidate" ]; then REPO_ROOT="$candidate" && export REPO_ROOT && break; fi; done; fi && DOWNLOADS_ROOT="$REPO_ROOT/Docker/Downloads" && export DOWNLOADS_ROOT && RELEASE_CHANNEL_PATH="$DOWNLOADS_ROOT/RELEASE_CHANNEL.generated.json" && export RELEASE_CHANNEL_PATH && cd "$REPO_ROOT" && python3 -c ''import json, os, pathlib, sys; p=pathlib.Path(os.environ[''"''"''RELEASE_CHANNEL_PATH''"''"'']); tuple_id=''"''"''avalonia:win-x64:windows''"''"''; expected_artifact=''"''"''avalonia-win-x64-installer''"''"''; expected_route=''"''"''/downloads/install/avalonia-win-x64-installer''"''"''; payload=json.loads(p.read_text(encoding=''"''"''utf-8''"''"'')); coverage=payload.get(''"''"''desktopTupleCoverage''"''"'') if isinstance(payload, dict) else {}; coverage=coverage if isinstance(coverage, dict) else {}; rows=coverage.get(''"''"''externalProofRequests''"''"'') if isinstance(coverage, dict) else []; rows=rows if isinstance(rows, list) else []; row=next((item for item in rows if isinstance(item, dict) and str(item.get(''"''"''tupleId''"''"'') or item.get(''"''"''tuple_id''"''"'') or ''"''"''''"''"'').strip()==tuple_id), None); sys.exit(f''"''"''release-channel-contract-mismatch:{tuple_id}:missing-external-proof-row''"''"'') if row is None else None; artifact=str(row.get(''"''"''expectedArtifactId''"''"'') or row.get(''"''"''expected_artifact_id''"''"'') or ''"''"''''"''"'').strip(); route=str(row.get(''"''"''expectedPublicInstallRoute''"''"'') or row.get(''"''"''expected_public_install_route''"''"'') or ''"''"''''"''"'').strip(); artifact_ok=(not expected_artifact) or artifact==expected_artifact; route_ok=(not expected_route) or route==expected_route; sys.exit(0) if artifact_ok and route_ok else sys.exit(f''"''"''release-channel-contract-mismatch:{tuple_id}:artifact={artifact}:expected_artifact={expected_artifact}:route={route}:expected_route={expected_route}''"''"'')'''
```

### Commands (PowerShell Bundle Wrappers)

```powershell
bash -lc 'set -euo pipefail
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="${CHUMMER_UI_REPO_ROOT:-/docker/chummercomplete/chummer6-ui}" && export REPO_ROOT && if [ -z "${CHUMMER_UI_REPO_ROOT:-}" ] && [ ! -d "$REPO_ROOT" ]; then for candidate in /docker/chummercomplete/chummer6-ui /docker/chummercomplete/chummer6-ui-finish /docker/chummercomplete/chummer-presentation; do if [ -d "$candidate" ]; then REPO_ROOT="$candidate" && export REPO_ROOT && break; fi; done; fi && DOWNLOADS_ROOT="$REPO_ROOT/Docker/Downloads" && export DOWNLOADS_ROOT
BUNDLE_ROOT="$SCRIPT_DIR/host-proof-bundles/windows"
BUNDLE_ARCHIVE="$SCRIPT_DIR/windows-proof-bundle.tgz"
export BUNDLE_ROOT
export BUNDLE_ARCHIVE
rm -rf "$BUNDLE_ROOT"
mkdir -p "$BUNDLE_ROOT"
rm -f "$BUNDLE_ARCHIVE"
python3 -c ''import json, os, pathlib; bundle_root=pathlib.Path(os.environ[''"''"''BUNDLE_ROOT''"''"'']); payload=json.loads(''"''"''{"host": "windows", "request_count": 1, "requests": [{"expected_installer_bundle_relative_path": "files/chummer-avalonia-win-x64-installer.exe", "expected_installer_sha256": "54966da8ac6f1ca7321b301b025bfb626398f461c78441c132d5c59d9c2bedde", "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json", "tuple_id": "avalonia:win-x64:windows"}], "schema_version": 1}''"''"''); manifest_path=bundle_root / ''"''"''external-proof-manifest.json''"''"''; manifest_path.write_text(json.dumps(payload, sort_keys=True, indent=2) + ''"''"''\n''"''"'', encoding=''"''"''utf-8''"''"'')''
mkdir -p "$BUNDLE_ROOT/files"
cp -f "$DOWNLOADS_ROOT/files/chummer-avalonia-win-x64-installer.exe" "$BUNDLE_ROOT/files/chummer-avalonia-win-x64-installer.exe"
mkdir -p "$BUNDLE_ROOT/startup-smoke"
cp -f "$DOWNLOADS_ROOT/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json" "$BUNDLE_ROOT/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json"
tar -czf "$BUNDLE_ARCHIVE" -C "$BUNDLE_ROOT" .
echo "Wrote $BUNDLE_ARCHIVE"'
```

### Commands (PowerShell Ingest Wrappers)

```powershell
bash -lc 'set -euo pipefail
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
DEFAULT_BUNDLE_ARCHIVE="$SCRIPT_DIR/windows-proof-bundle.tgz"
DEFAULT_BUNDLE_DIR="$SCRIPT_DIR/host-proof-bundles/windows"
BUNDLE_INPUT="${1:-}"
if [ -n "$BUNDLE_INPUT" ] && [ -f "$BUNDLE_INPUT" ]; then
BUNDLE_ARCHIVE="$BUNDLE_INPUT"
BUNDLE_DIR="$DEFAULT_BUNDLE_DIR"
elif [ -n "$BUNDLE_INPUT" ] && [ -d "$BUNDLE_INPUT" ]; then
BUNDLE_ARCHIVE="$DEFAULT_BUNDLE_ARCHIVE"
BUNDLE_DIR="$BUNDLE_INPUT"
else
BUNDLE_ARCHIVE="$DEFAULT_BUNDLE_ARCHIVE"
BUNDLE_DIR="$DEFAULT_BUNDLE_DIR"
fi
export BUNDLE_ARCHIVE
export BUNDLE_DIR
TARGET_ROOT=/docker/chummercomplete/chummer.run-services/Chummer.Portal/downloads
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
        if member.isdir():
            continue
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
python3 -c ''import os, json, pathlib; manifest_path=pathlib.Path(os.environ[''"''"''TARGET_ROOT''"''"'']) / ''"''"''external-proof-manifest.json''"''"''; expected=json.loads(''"''"''{"host": "windows", "request_count": 1, "requests": [{"expected_installer_bundle_relative_path": "files/chummer-avalonia-win-x64-installer.exe", "expected_installer_sha256": "54966da8ac6f1ca7321b301b025bfb626398f461c78441c132d5c59d9c2bedde", "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json", "tuple_id": "avalonia:win-x64:windows"}], "schema_version": 1}''"''"''); assert manifest_path.is_file(), ''"''"''external-proof-bundle-manifest-missing:''"''"'' + str(manifest_path); payload=json.loads(manifest_path.read_text(encoding=''"''"''utf-8''"''"'')); assert payload == expected, ''"''"''external-proof-bundle-manifest-mismatch:''"''"'' + str(manifest_path) + ''"''"'':expected=''"''"'' + json.dumps(expected, sort_keys=True) + ''"''"'':actual=''"''"'' + json.dumps(payload, sort_keys=True)''
test -s "$TARGET_ROOT/files/chummer-avalonia-win-x64-installer.exe"
test -s "$TARGET_ROOT/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json"
python3 -c ''import hashlib, os, pathlib; target_root=pathlib.Path(os.environ[''"''"''TARGET_ROOT''"''"'']); tuple_id=''"''"''avalonia:win-x64:windows''"''"''; relative=''"''"''files/chummer-avalonia-win-x64-installer.exe''"''"''; expected=''"''"''54966da8ac6f1ca7321b301b025bfb626398f461c78441c132d5c59d9c2bedde''"''"''; path=target_root / relative; assert path.is_file(), f''"''"''external-proof-bundle-installer-missing:{tuple_id}:{path}''"''"''; digest=hashlib.sha256(path.read_bytes()).hexdigest().lower(); assert digest==expected, f''"''"''installer-contract-mismatch:{tuple_id}:{path}:digest={digest}:expected={expected}''"''"''''
python3 -c ''import datetime as dt, json, os, pathlib; target_root=pathlib.Path(os.environ[''"''"''TARGET_ROOT''"''"'']); relative=''"''"''startup-smoke/startup-smoke-avalonia-win-x64.receipt.json''"''"''; max_age_seconds=604800; max_future_skew_seconds=300; path=target_root / relative; assert path.is_file(), ''"''"''external-proof-bundle-receipt-missing:''"''"'' + str(path); payload=json.loads(path.read_text(encoding=''"''"''utf-8''"''"'')); payload=payload if isinstance(payload, dict) else {}; raw=next((str(payload.get(key) or ''"''"''''"''"'').strip() for key in (''"''"''recordedAtUtc''"''"'',''"''"''completedAtUtc''"''"'',''"''"''generatedAt''"''"'',''"''"''generated_at''"''"'',''"''"''startedAtUtc''"''"'') if str(payload.get(key) or ''"''"''''"''"'').strip()), ''"''"''''"''"''); assert raw, ''"''"''startup-smoke-receipt-timestamp-missing:''"''"'' + str(path); raw = raw[:-1] + ''"''"''+00:00''"''"'' if raw.endswith(''"''"''Z''"''"'') else raw; parsed=dt.datetime.fromisoformat(raw); parsed=parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=dt.timezone.utc); parsed=parsed.astimezone(dt.timezone.utc); now=dt.datetime.now(dt.timezone.utc); age_seconds=int((now-parsed).total_seconds()); assert age_seconds >= -max_future_skew_seconds, ''"''"''startup-smoke-receipt-future-skew:''"''"'' + str(path) + f''"''"'':age_seconds={age_seconds}:max_future_skew_seconds={max_future_skew_seconds}''"''"''; age_seconds = 0 if age_seconds < 0 else age_seconds; assert age_seconds <= max_age_seconds, ''"''"''startup-smoke-receipt-stale:''"''"'' + str(path) + f''"''"'':age_seconds={age_seconds}:max_age_seconds={max_age_seconds}''"''"''''
python3 -c ''import json, os, pathlib; target_root=pathlib.Path(os.environ[''"''"''TARGET_ROOT''"''"'']); tuple_id=''"''"''avalonia:win-x64:windows''"''"''; relative=''"''"''startup-smoke/startup-smoke-avalonia-win-x64.receipt.json''"''"''; contract=json.loads(''"''"''{"head_id": "avalonia", "host_class_contains": "windows", "platform": "windows", "ready_checkpoint": "pre_ui_event_loop", "rid": "win-x64", "status_any_of": ["pass", "passed", "ready"]}''"''"''); path=target_root / relative; assert path.is_file(), f''"''"''external-proof-bundle-receipt-missing:{tuple_id}:{path}''"''"''; payload=json.loads(path.read_text(encoding=''"''"''utf-8''"''"'')); payload=payload if isinstance(payload, dict) else {}; status=str(payload.get(''"''"''status''"''"'') or ''"''"''''"''"'').strip().lower(); expected_statuses=[str(token).strip().lower() for token in (contract.get(''"''"''status_any_of''"''"'') or []) if str(token).strip()]; head_id=str(payload.get(''"''"''headId''"''"'') or ''"''"''''"''"'').strip().lower(); platform=str(payload.get(''"''"''platform''"''"'') or ''"''"''''"''"'').strip().lower(); rid=str(payload.get(''"''"''rid''"''"'') or ''"''"''''"''"'').strip().lower(); ready_checkpoint=str(payload.get(''"''"''readyCheckpoint''"''"'') or ''"''"''''"''"'').strip().lower(); host_class=str(payload.get(''"''"''hostClass''"''"'') or ''"''"''''"''"'').strip().lower(); expected_head=str(contract.get(''"''"''head_id''"''"'') or ''"''"''''"''"'').strip().lower(); expected_platform=str(contract.get(''"''"''platform''"''"'') or ''"''"''''"''"'').strip().lower(); expected_rid=str(contract.get(''"''"''rid''"''"'') or ''"''"''''"''"'').strip().lower(); expected_ready=str(contract.get(''"''"''ready_checkpoint''"''"'') or ''"''"''''"''"'').strip().lower(); expected_host_contains=str(contract.get(''"''"''host_class_contains''"''"'') or ''"''"''''"''"'').strip().lower(); assert ((not expected_statuses or status in expected_statuses) and (not expected_head or head_id == expected_head) and (not expected_platform or platform == expected_platform) and (not expected_rid or rid == expected_rid) and (not expected_ready or ready_checkpoint == expected_ready) and (not expected_host_contains or expected_host_contains in host_class), f''"''"''receipt-contract-mismatch:{tuple_id}:{path}:status={status}:head={head_id}:platform={platform}:rid={rid}:ready={ready_checkpoint}:host_class={host_class}:contract={contract}''"''"'')''
echo "Host proof bundle ingest complete: $BUNDLE_ARCHIVE"'
```

### Commands (PowerShell Host Lane Wrappers)

```powershell
bash -lc 'set -euo pipefail
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$SCRIPT_DIR"
if [ -f "$SCRIPT_DIR/proof-host.env" ]; then
set -a
. "$SCRIPT_DIR/proof-host.env"
set +a
fi
./preflight-windows-proof.sh
./capture-windows-proof.sh
./validate-windows-proof.sh
./bundle-windows-proof.sh
if [ "${CHUMMER_EXTERNAL_PROOF_AUTO_FINALIZE:-0}" = "1" ]; then
if [ -x "$SCRIPT_DIR/finalize-external-host-proof.sh" ] && [ -d /docker/fleet ] && [ -d /docker/chummercomplete ]; then
"$SCRIPT_DIR/finalize-external-host-proof.sh"
else
echo ''external-proof-auto-finalize-blocked: finalize-external-host-proof.sh requires the shared /docker/fleet and /docker/chummercomplete workspace on this host. Either mount the shared workspace or unset CHUMMER_EXTERNAL_PROOF_AUTO_FINALIZE and return the proof bundle for manual ingest.'' >&2
exit 1
fi
fi'
```

Set `$env:CHUMMER_EXTERNAL_PROOF_AUTO_FINALIZE = '1'` before the PowerShell host lane to trigger the same shared-workspace finalize path.

## After Host Proof Capture

Run these commands after macOS/Windows proofs land to validate receipts, ingest bundles, and republish release truth.

```bash
/docker/fleet/.codex-studio/published/external-proof-commands/finalize-external-host-proof.sh
```

```bash
cd /docker/chummercomplete/chummer-hub-registry && python3 scripts/materialize_public_release_channel.py --manifest /docker/chummercomplete/chummer.run-services/Chummer.Portal/downloads/RELEASE_CHANNEL.generated.json --downloads-dir /docker/chummercomplete/chummer.run-services/Chummer.Portal/downloads/files --startup-smoke-dir /docker/chummercomplete/chummer.run-services/Chummer.Portal/downloads/startup-smoke --channel docker --version unpublished --published-at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" --output .codex-studio/published/RELEASE_CHANNEL.generated.json
cd /docker/chummercomplete/chummer-hub-registry && python3 scripts/verify_public_release_channel.py /docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json
cd /docker/fleet && python3 scripts/materialize_status_plane.py --out .codex-studio/published/STATUS_PLANE.generated.yaml
cd /docker/fleet && python3 scripts/verify_status_plane_semantics.py --status-plane .codex-studio/published/STATUS_PLANE.generated.yaml
cd /docker/fleet && python3 scripts/materialize_public_progress_report.py --out .codex-studio/published/PROGRESS_REPORT.generated.json --html-out /docker/chummercomplete/chummer-design/products/chummer/PROGRESS_REPORT.generated.html --history-out .codex-studio/published/PROGRESS_HISTORY.generated.json --preview-out /docker/chummercomplete/chummer-design/products/chummer/PROGRESS_REPORT.generated.json
cd /docker/fleet && python3 scripts/materialize_support_case_packets.py --out .codex-studio/published/SUPPORT_CASE_PACKETS.generated.json --release-channel /docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json
cd /docker/fleet && python3 scripts/materialize_journey_gates.py --out .codex-studio/published/JOURNEY_GATES.generated.json --status-plane .codex-studio/published/STATUS_PLANE.generated.yaml --progress-report .codex-studio/published/PROGRESS_REPORT.generated.json --progress-history .codex-studio/published/PROGRESS_HISTORY.generated.json --support-packets .codex-studio/published/SUPPORT_CASE_PACKETS.generated.json
cd /docker/fleet && python3 scripts/materialize_external_proof_runbook.py --support-packets .codex-studio/published/SUPPORT_CASE_PACKETS.generated.json --journey-gates /docker/fleet/.codex-studio/published/JOURNEY_GATES.generated.json --release-channel /docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json --out .codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md
cd /docker/fleet && python3 scripts/verify_external_proof_closure.py --support-packets .codex-studio/published/SUPPORT_CASE_PACKETS.generated.json --journey-gates .codex-studio/published/JOURNEY_GATES.generated.json --release-channel /docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json --external-proof-runbook .codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md --external-proof-commands-dir .codex-studio/published/external-proof-commands
cd /docker/fleet && python3 scripts/materialize_flagship_product_readiness.py --out .codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json --mirror-out /docker/fleet/state/chummer_design_supervisor/artifacts/FLAGSHIP_PRODUCT_READINESS.generated.json
cd /docker/chummercomplete/chummer-design && python3 scripts/ai/materialize_weekly_product_pulse_snapshot.py --out products/chummer/WEEKLY_PRODUCT_PULSE.generated.json
```
