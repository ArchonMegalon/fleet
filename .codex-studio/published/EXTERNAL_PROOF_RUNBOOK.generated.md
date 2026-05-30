# External Proof Runbook

- generated_at: 2026-05-29T23:34:37Z
- unresolved_request_count: 0
- unresolved_hosts: (none)
- plan_generated_at: 2026-05-29T23:33:10Z
- release_channel_generated_at: 2026-05-29T20:14:22Z
- capture_deadline_hours: 24
- capture_deadline_utc: 2026-05-30T20:14:22Z

## Prerequisites

- Run each host section on the matching native host (`macos` on macOS, `windows` on Windows).
- Provide signed-in download credentials before capture when public routes are account-gated.
- Supported auth inputs: `CHUMMER_EXTERNAL_PROOF_AUTH_HEADER`, `CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER`, `CHUMMER_EXTERNAL_PROOF_COOKIE_JAR`.
- Set `CHUMMER_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD=1` only when install routes are intentionally guest-readable.
- Optional base URL override: `CHUMMER_EXTERNAL_PROOF_BASE_URL` (default `${CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}`).

## Generated Command Files

- commands_dir: `/docker/fleet/.codex-studio/published/external-proof-commands`
- command_bundle_sha256: `d095b63bdb5c10063788e8bac7201cf5ed60d69ced95be3d2028bc3b638c723e`
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
  command_pack_sha256: `c500608bea46c88abeedd95e3c34d8bec6d111a361b50f6d57bde818fbb53644`
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
  command_pack_sha256: `03ad820f4813954711e40717790d82e21f83f0975d758ae7fa3f9395c4eba170`
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
  command_pack_sha256: `36c0bebbe3bcca3f06643cefb85357258707e2c0b11d1fd563ac3427306b8072`
  preflight_powershell: `/docker/fleet/.codex-studio/published/external-proof-commands/preflight-windows-proof.ps1`
  capture_powershell: `/docker/fleet/.codex-studio/published/external-proof-commands/capture-windows-proof.ps1`
  validation_powershell: `/docker/fleet/.codex-studio/published/external-proof-commands/validate-windows-proof.ps1`
  bundle_powershell: `/docker/fleet/.codex-studio/published/external-proof-commands/bundle-windows-proof.ps1`
  ingest_powershell: `/docker/fleet/.codex-studio/published/external-proof-commands/ingest-windows-proof-bundle.ps1`
  host_lane_powershell: `/docker/fleet/.codex-studio/published/external-proof-commands/run-windows-proof-lane.ps1`
  prepare_command_pack_powershell: `/docker/fleet/.codex-studio/published/external-proof-commands/prepare-windows-proof-command-pack.ps1`
- post_capture_script: `/docker/fleet/.codex-studio/published/external-proof-commands/republish-after-host-proof.sh`
- finalize_script: `/docker/fleet/.codex-studio/published/external-proof-commands/finalize-external-host-proof.sh`

## Retained Host Lanes

These command bundles stay materialized even with zero backlog so native-host proof capture can resume without rebuilding the lane.

### Host: linux

- shell_hint: Run commands in a POSIX shell (bash/zsh) on the required host.
- request_count: 0
- tuples: (none)
- host_lane_script: `/docker/fleet/.codex-studio/published/external-proof-commands/run-linux-proof-lane.sh`
- prepare_command_pack_script: `/docker/fleet/.codex-studio/published/external-proof-commands/prepare-linux-proof-command-pack.sh`
- retained_bundle_archive_path: `/docker/fleet/.codex-studio/published/external-proof-commands/linux-proof-bundle.tgz`
- retained_bundle_archive_present: `true`
- retained_bundle_directory_path: `/docker/fleet/.codex-studio/published/external-proof-commands/host-proof-bundles/linux`
- retained_bundle_directory_present: `true`
- command_pack_path: `/docker/fleet/.codex-studio/published/external-proof-commands/linux-proof-command-pack.tgz`
- command_pack_present: `true`
- command_pack_sha256_path: `/docker/fleet/.codex-studio/published/external-proof-commands/linux-proof-command-pack.tgz.sha256`
- command_pack_sha256: `c500608bea46c88abeedd95e3c34d8bec6d111a361b50f6d57bde818fbb53644`

### Host: macos

- shell_hint: Run commands in a POSIX shell (bash/zsh) on the required host.
- platform_hint: macOS proofs require `hdiutil` on the proof host.
- request_count: 0
- tuples: (none)
- host_lane_script: `/docker/fleet/.codex-studio/published/external-proof-commands/run-macos-proof-lane.sh`
- prepare_command_pack_script: `/docker/fleet/.codex-studio/published/external-proof-commands/prepare-macos-proof-command-pack.sh`
- retained_bundle_archive_path: `/docker/fleet/.codex-studio/published/external-proof-commands/macos-proof-bundle.tgz`
- retained_bundle_archive_present: `true`
- retained_bundle_directory_path: `/docker/fleet/.codex-studio/published/external-proof-commands/host-proof-bundles/macos`
- retained_bundle_directory_present: `true`
- command_pack_path: `/docker/fleet/.codex-studio/published/external-proof-commands/macos-proof-command-pack.tgz`
- command_pack_present: `true`
- command_pack_sha256_path: `/docker/fleet/.codex-studio/published/external-proof-commands/macos-proof-command-pack.tgz.sha256`
- command_pack_sha256: `03ad820f4813954711e40717790d82e21f83f0975d758ae7fa3f9395c4eba170`

### Host: windows

- shell_hint: Run canonical commands in Git Bash (or WSL bash). PowerShell wrappers are provided below when you need to stay in PowerShell.
- platform_hint: Windows proofs require `powershell.exe` or `pwsh` on the proof host.
- request_count: 0
- tuples: (none)
- host_lane_script: `/docker/fleet/.codex-studio/published/external-proof-commands/run-windows-proof-lane.sh`
- prepare_command_pack_script: `/docker/fleet/.codex-studio/published/external-proof-commands/prepare-windows-proof-command-pack.sh`
- host_lane_powershell: `/docker/fleet/.codex-studio/published/external-proof-commands/run-windows-proof-lane.ps1`
- prepare_command_pack_powershell: `/docker/fleet/.codex-studio/published/external-proof-commands/prepare-windows-proof-command-pack.ps1`
- retained_bundle_archive_path: `/docker/fleet/.codex-studio/published/external-proof-commands/windows-proof-bundle.tgz`
- retained_bundle_archive_present: `true`
- retained_bundle_directory_path: `/docker/fleet/.codex-studio/published/external-proof-commands/host-proof-bundles/windows`
- retained_bundle_directory_present: `true`
- command_pack_path: `/docker/fleet/.codex-studio/published/external-proof-commands/windows-proof-command-pack.tgz`
- command_pack_present: `true`
- command_pack_sha256_path: `/docker/fleet/.codex-studio/published/external-proof-commands/windows-proof-command-pack.tgz.sha256`
- command_pack_sha256: `36c0bebbe3bcca3f06643cefb85357258707e2c0b11d1fd563ac3427306b8072`

## Resume Commands

Use these exact retained entrypoints to reopen native-host capture without rebuilding the command bundle.

### Resume Host Lane: linux

```bash
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$SCRIPT_DIR"
if [ -f "$SCRIPT_DIR/proof-host.env" ]; then
  set -a
  . "$SCRIPT_DIR/proof-host.env"
  set +a
fi
./preflight-linux-proof.sh
./capture-linux-proof.sh
./validate-linux-proof.sh
./bundle-linux-proof.sh
if [ "${CHUMMER_EXTERNAL_PROOF_AUTO_FINALIZE:-0}" = "1" ]; then
  if [ -x "$SCRIPT_DIR/finalize-external-host-proof.sh" ] && [ -d /docker/fleet ] && [ -d /docker/chummercomplete ]; then
    "$SCRIPT_DIR/finalize-external-host-proof.sh"
  else
    echo 'external-proof-auto-finalize-blocked: finalize-external-host-proof.sh requires the shared /docker/fleet and /docker/chummercomplete workspace on this host. Either mount the shared workspace or unset CHUMMER_EXTERNAL_PROOF_AUTO_FINALIZE and return the proof bundle for manual ingest.' >&2
    exit 1
  fi
fi
```

### Resume Host Lane: macos

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

### Resume Host Lane: windows

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

### Resume Host Lane (PowerShell): windows

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

## After Host Proof Capture

Run these retained commands after a host lane succeeds to validate receipts, ingest bundles, and republish release truth.

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

No unresolved external-proof requests are currently queued.
