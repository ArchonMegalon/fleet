#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: bash scripts/deploy.sh <command> [args]

Commands:
  admin-status
      Print the live admin status JSON.
  cockpit-summary
      Print a compact live cockpit summary.
  chummer-portal
      Probe the local Chummer portal landing and key routed health endpoints.
  build-chummer-windows-downloads
      Build Windows desktop artifact(s) for the local Chummer portal and publish them into /downloads.
  build-chummer-desktop-downloads
      Build and publish the default desktop matrix (Windows x64 and macOS ARM64) into /downloads.
  build-chummer-desktop-windows-downloads
      Build and publish both Avalonia and Blazor Windows desktop artifacts into /downloads.
  build-chummer-avalonia-windows-downloads
      Build and publish only the Avalonia Windows desktop artifact into /downloads.
  build-chummer-desktop-macos-arm64-downloads
      Build and publish both Avalonia and Blazor macOS ARM64 desktop artifacts into /downloads.
  build-chummer-avalonia-macos-arm64-downloads
      Build and publish only the Avalonia macOS ARM64 desktop artifact into /downloads.
  patch-chummer-portal-downloads-ui
      Patch the Chummer portal downloads page to expose platform and app-type selectors.
  verify-chummer-portal-downloads-ui
      Verify the live Chummer portal downloads page exposes platform and type selectors.
  rebuild-chummer-portal
      Rebuild and restart the Chummer portal container, then verify the downloads page.
  patch-and-rebuild-chummer-portal-downloads-ui
      Patch the Chummer portal downloads UI, rebuild the portal, and verify the live page.
  patch-chummer-desktop-source
      Patch the real Chummer desktop source tree with the desktop-safe coach client fallback.
  patch-and-build-chummer-windows-downloads
      Patch the real Chummer desktop source tree, then rebuild and republish the Windows desktop download.
  gateway-cockpit
      Fetch the live cockpit payload through the dashboard gateway.
  smoke-fleet-dashboard
      Run a browser smoke test against the live Fleet dashboard login and bridge hydration path.
  gateway-root
      Fetch the root dashboard path headers from inside the gateway container.
  host-root
      Fetch the root dashboard path headers from the host-bound gateway port.
  dashboard-logs
      Print recent fleet-dashboard logs.
  project-status <project> [project...]
      Print compact live project rows from the fleet DB.
  compile-status <project> [project...]
      Print live project lifecycle and compile-health rows from admin status.
  run-status <run_id> [run_id...]
      Print compact live run rows from the fleet DB.
  recent-runs <project> [limit]
      Print recent live run rows for one project from the fleet DB.
  time-vienna
      Print the current Vienna time.
  verify-config
      Parse the split fleet config and fail on invalid YAML/schema loading.
  db-schema <table>
      Print the live SQLite schema for a table.
  verify-python <file> [file...]
      Run python3 -m py_compile on one or more files.
  inject-chummer-public-repo-audit
      Publish the latest scoped Chummer public-repo audit feedback into group and repo feedback lanes.
  inject-chummer-design-dropin-pack
      Publish the latest Chummer design drop-in canon pack into design and group feedback lanes.
  inject-ea-main-branch-audit
      Publish the latest EA main-branch hardening audit into repo and group feedback lanes.
  inject-fleet-public-audit
      Publish the latest Fleet public architecture audit follow-up into repo feedback.
  rebuild <service> [service...]
      Rebuild and restart one or more compose services.
USAGE
}

require_args() {
  if [ "$#" -eq 0 ]; then
    echo "missing arguments" >&2
    exit 1
  fi
}

operator_password() {
  if [ -n "${FLEET_OPERATOR_PASSWORD:-}" ]; then
    printf '%s' "${FLEET_OPERATOR_PASSWORD}"
    return 0
  fi
  if [ -f /docker/fleet/runtime.env ]; then
    sed -n 's/^FLEET_OPERATOR_PASSWORD=//p' /docker/fleet/runtime.env | tail -n 1
    return 0
  fi
  echo "FLEET_OPERATOR_PASSWORD is not set and /docker/fleet/runtime.env is missing" >&2
  exit 1
}

admin_status() {
  docker exec fleet-admin curl -sS -H "X-Fleet-Operator-Password: $(operator_password)" \
    http://127.0.0.1:8092/api/admin/status
}

patch_chummer_desktop_coach_client() {
  local source_root="$1"
  local desktop_program="$source_root/Chummer.Blazor.Desktop/Program.cs"
  local desktop_client="$source_root/Chummer.Blazor.Desktop/DesktopWorkbenchCoachApiClient.cs"

  if [[ ! -f "$desktop_program" ]]; then
    echo "desktop startup file not found: $desktop_program" >&2
    exit 1
  fi

  if ! grep -q "using Chummer.Blazor;" "$desktop_program"; then
    python3 - "$desktop_program" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
needle = "using Chummer.Presentation;\n"
replacement = "using Chummer.Blazor;\nusing Chummer.Presentation;\n"
if needle not in text:
    raise SystemExit(f"needle not found in {path}")
path.write_text(text.replace(needle, replacement, 1), encoding="utf-8")
PY
  fi

  if ! grep -q "DesktopWorkbenchCoachApiClient" "$desktop_program"; then
    python3 - "$desktop_program" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
needle = '        appBuilder.Services.AddSingleton<Chummer.Blazor.CharacterOverviewStateBridge>();\n'
replacement = needle + '        appBuilder.Services.AddSingleton<IWorkbenchCoachApiClient, DesktopWorkbenchCoachApiClient>();\n'
if needle not in text:
    raise SystemExit(f"needle not found in {path}")
path.write_text(text.replace(needle, replacement, 1), encoding="utf-8")
PY
  fi

  if [[ ! -f "$desktop_client" ]]; then
    cat >"$desktop_client" <<'EOF'
using Chummer.Blazor;
using Chummer.Contracts.AI;

namespace Chummer.Blazor.Desktop;

internal sealed class DesktopWorkbenchCoachApiClient : IWorkbenchCoachApiClient
{
    private static readonly AiNotImplementedReceipt Receipt = new(
        Error: "coach_sidecar_unavailable",
        Operation: "workbench_coach_desktop",
        Message: "Coach sidecar is not configured in the desktop runtime yet.",
        RouteType: AiRouteTypes.Coach);

    public Task<WorkbenchCoachApiCallResult<AiGatewayStatusProjection>> GetStatusAsync(CancellationToken ct = default)
        => Task.FromResult(WorkbenchCoachApiCallResult<AiGatewayStatusProjection>.FromNotImplemented(501, Receipt));

    public Task<WorkbenchCoachApiCallResult<AiProviderHealthProjection[]>> ListProviderHealthAsync(string? routeType = null, CancellationToken ct = default)
        => Task.FromResult(WorkbenchCoachApiCallResult<AiProviderHealthProjection[]>.FromNotImplemented(501, Receipt with { RouteType = routeType ?? AiRouteTypes.Coach }));

    public Task<WorkbenchCoachApiCallResult<AiConversationAuditCatalogPage>> ListConversationAuditsAsync(
        string routeType,
        string? runtimeFingerprint = null,
        int maxCount = 3,
        CancellationToken ct = default)
        => Task.FromResult(WorkbenchCoachApiCallResult<AiConversationAuditCatalogPage>.FromNotImplemented(501, Receipt with { RouteType = routeType ?? AiRouteTypes.Coach }));
}
EOF
  fi
}

build_chummer_windows_downloads() {
  local repo_root="${CHUMMER_PORTAL_REPO_ROOT:-/docker/chummer5a}"
  local build_root="${CHUMMER_DESKTOP_BUILD_ROOT:-/tmp/chummer5a-desktop-build}"
  local source_root="${CHUMMER_DESKTOP_SOURCE_ROOT:-$build_root/src}"
  local rids_csv="${CHUMMER_DESKTOP_RIDS:-${CHUMMER_DESKTOP_RID:-win-x64}}"
  local apps_csv="${CHUMMER_DESKTOP_APPS:-blazor-desktop}"
  local dist_dir="${CHUMMER_DESKTOP_DIST_DIR:-$build_root/dist}"
  local deploy_dir="${CHUMMER_DOWNLOADS_DEPLOY_DIR:-$repo_root/Docker/Downloads}"
  local live_verify_target="${CHUMMER_DOWNLOADS_VERIFY_URL:-http://127.0.0.1:8091}"
  local release_stamp="${CHUMMER_RELEASE_STAMP:-$(date -u +%Y%m%d-%H%M%S)}"
  local release_version="${CHUMMER_RELEASE_VERSION:-Chummer 6 local ${release_stamp}}"
  local release_channel="${CHUMMER_RELEASE_CHANNEL:-preview}"
  local release_published_at
  release_published_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

  if [[ ! -d "$repo_root" ]]; then
    echo "Chummer repo root not found: $repo_root" >&2
    exit 1
  fi

  rm -rf "$build_root"
  mkdir -p "$source_root" "$dist_dir/files" "$build_root/dotnet-home" "$build_root/nuget-packages"
  rm -f "$dist_dir/files"/chummer-6-*.zip "$dist_dir/files"/chummer-6-*.tar.gz "$dist_dir/releases.json"

  echo "== stage writable source tree =="
  rsync -a --delete \
    --exclude ".git/" \
    --exclude ".env" \
    --exclude ".tmp/" \
    --exclude "Chummer.Tests/" \
    "$repo_root"/ "$source_root"/
  find "$source_root" -type d \( -name .git -o -name bin -o -name obj -o -name dist -o -name out \) -prune -exec rm -rf {} +

  echo "== inject desktop coach fallback =="
  patch_chummer_desktop_coach_client "$source_root"

  pushd "$source_root" >/dev/null
  IFS=',' read -r -a requested_rids <<<"$rids_csv"
  IFS=',' read -r -a requested_apps <<<"$apps_csv"
  for rid in "${requested_rids[@]}"; do
    rid="$(echo "$rid" | xargs)"
    [[ -n "$rid" ]] || continue

    for app in "${requested_apps[@]}"; do
      app="$(echo "$app" | xargs)"
      [[ -n "$app" ]] || continue

      local project=""
      local archive_slug=""
      case "$app" in
        avalonia)
          project="Chummer.Avalonia/Chummer.Avalonia.csproj"
          archive_slug="avalonia"
          ;;
        blazor-desktop)
          project="Chummer.Blazor.Desktop/Chummer.Blazor.Desktop.csproj"
          archive_slug="blazor"
          ;;
        *)
          echo "Unsupported desktop app '$app'. Supported values: avalonia, blazor-desktop" >&2
          exit 1
          ;;
      esac

      local out_dir="$build_root/output/$archive_slug/$rid/publish"
      local archive_path="$dist_dir/files/chummer-6-$archive_slug-$rid-$release_stamp.zip"
      rm -rf "$(dirname "$out_dir")"

      echo "== restore $project =="
      DOTNET_CLI_HOME="$build_root/dotnet-home" \
      NUGET_PACKAGES="$build_root/nuget-packages" \
      dotnet restore "$project" \
        -p:RestorePackagesPath="$build_root/nuget-packages"

      echo "== publish $project ($rid) =="
      DOTNET_CLI_HOME="$build_root/dotnet-home" \
      NUGET_PACKAGES="$build_root/nuget-packages" \
      dotnet publish "$project" \
        -c Release \
        -r "$rid" \
        --self-contained true \
        -p:PublishSingleFile=true \
        -p:PublishTrimmed=false \
        -p:IncludeNativeLibrariesForSelfExtract=true \
        -p:RestorePackagesPath="$build_root/nuget-packages" \
        -o "$out_dir"

      echo "== package $archive_path =="
      python3 - "$archive_path" "$out_dir" <<'PY'
import os
import sys
import zipfile
from pathlib import Path

archive_path = Path(sys.argv[1])
source_dir = Path(sys.argv[2])
archive_path.parent.mkdir(parents=True, exist_ok=True)

with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    for path in sorted(source_dir.rglob("*")):
        if path.is_file():
            zf.write(path, path.relative_to(source_dir))
print(f"wrote {archive_path}")
PY
    done
  done
  popd >/dev/null

  echo "== generate local releases manifest =="
  python3 - "$dist_dir/files" "$dist_dir/releases.json" "$release_version" "$release_channel" "$release_published_at" <<'PY'
import hashlib
import json
import re
import sys
from pathlib import Path

downloads_dir = Path(sys.argv[1])
manifest_path = Path(sys.argv[2])
version = sys.argv[3]
channel = sys.argv[4]
published_at = sys.argv[5]

pattern = re.compile(r"^chummer-6-(?P<app>avalonia|blazor)-(?P<rid>.+)-(?P<stamp>\d{8}-\d{6})\.zip$")
app_labels = {
    "avalonia": "Chummer 6 Avalonia",
    "blazor": "Chummer 6 Blazor",
}
platform_names = {
    "win-x64": "Windows x64",
    "win-arm64": "Windows ARM64",
    "linux-x64": "Linux x64",
    "linux-arm64": "Linux ARM64",
    "osx-arm64": "macOS ARM64",
    "osx-x64": "macOS x64",
}
downloads = []

for artifact in sorted(downloads_dir.iterdir()):
    if not artifact.is_file():
        continue
    match = pattern.match(artifact.name)
    if not match:
        continue
    app = match.group("app")
    rid = match.group("rid")
    stamp = match.group("stamp")
    downloads.append(
        {
            "id": f"{app}-{rid}-{stamp}",
            "platform": f"{app_labels.get(app, app)} {platform_names.get(rid, rid)}",
            "url": f"/downloads/files/{artifact.name}",
            "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
            "sizeBytes": artifact.stat().st_size,
        }
    )

manifest = {
    "version": version if downloads else "unpublished",
    "channel": channel,
    "publishedAt": published_at,
    "downloads": downloads,
}
manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(f"wrote {manifest_path} with {len(downloads)} download entry(ies)")
PY

  echo "== publish into portal downloads directory =="
  mkdir -p "$deploy_dir/files"
  find "$deploy_dir/files" -maxdepth 1 -type f \( -name "chummer-6-*.zip" -o -name "chummer-6-*.tar.gz" \) -delete
  cp "$dist_dir"/releases.json "$deploy_dir"/releases.json
  find "$dist_dir/files" -maxdepth 1 -type f \( -name "chummer-6-*.zip" -o -name "chummer-6-*.tar.gz" \) -exec cp {} "$deploy_dir/files/" \;

  echo "== verify deployed downloads manifest =="
  CHUMMER_PORTAL_DOWNLOADS_REQUIRE_PUBLISHED_VERSION=true \
  CHUMMER_PORTAL_DOWNLOADS_VERIFY_LINKS=false \
  bash "$repo_root/scripts/verify-releases-manifest.sh" "$deploy_dir/releases.json"

  echo "== verify live portal downloads =="
  CHUMMER_PORTAL_DOWNLOADS_REQUIRE_PUBLISHED_VERSION=true \
  CHUMMER_PORTAL_DOWNLOADS_VERIFY_LINKS=true \
  bash "$repo_root/scripts/verify-releases-manifest.sh" "$live_verify_target"
}

patch_chummer_portal_downloads_ui() {
  local repo_root="${CHUMMER_PORTAL_REPO_ROOT:-/docker/chummer5a}"
  local target="$repo_root/Chummer.Portal/PortalPageBuilder.cs"
  if [[ ! -f "$target" ]]; then
    echo "Portal page builder not found: $target" >&2
    exit 1
  fi
  python3 "$repo_root/../fleet/scripts/chummer_portal_downloads_ui_patch.py" "$target"
  echo "== verify patched portal page builder =="
  rg -n "download-platform|download-type|All platforms|All types" "$target"
}

rebuild_chummer_portal() {
  local repo_root="${CHUMMER_PORTAL_REPO_ROOT:-/docker/chummer5a}"
  local compose_file="$repo_root/docker-compose.yml"
  if [[ ! -f "$compose_file" ]]; then
    echo "Chummer portal compose file not found: $compose_file" >&2
    exit 1
  fi

  echo "== rebuild chummer-portal =="
  docker compose -f "$compose_file" build chummer-portal
  echo "== restart chummer-portal =="
  docker compose -f "$compose_file" up -d chummer-portal
  verify_chummer_portal_downloads_ui
}

verify_chummer_portal_downloads_ui() {
  echo "== verify live downloads html =="
  python3 - <<'PY'
import time
import sys
import urllib.request

needles = ["download-platform", "download-type", "All platforms", "All types"]
last_error = None
for _attempt in range(12):
    try:
        html = urllib.request.urlopen("http://127.0.0.1:8091/downloads/", timeout=20).read().decode("utf-8", errors="replace")
        missing = [needle for needle in needles if needle not in html]
        if missing:
            raise RuntimeError(f"missing downloads UI markers: {', '.join(missing)}")
        print("verified downloads UI markers:", ", ".join(needles))
        raise SystemExit(0)
    except Exception as exc:
        last_error = exc
        time.sleep(2)
raise SystemExit(str(last_error) if last_error else "downloads UI verification failed")
PY
}

smoke_fleet_dashboard() {
  local compose_file="${CHUMMER_PORTAL_REPO_ROOT:-/docker/chummer5a}/docker-compose.yml"
  local dashboard_url="${FLEET_DASHBOARD_SMOKE_URL:-http://fleet-dashboard:8090}"
  local dashboard_network="${FLEET_DASHBOARD_SMOKE_NETWORK:-codex-fleet-net}"
  local password
  password="$(operator_password)"

  if [[ ! -f "$compose_file" ]]; then
    echo "Chummer compose file not found: $compose_file" >&2
    exit 1
  fi

  echo "== build playwright smoke image =="
  docker compose -f "$compose_file" --profile test --profile portal build chummer-playwright-portal >/dev/null

  FLEET_DASHBOARD_SMOKE_URL="$dashboard_url" \
  FLEET_DASHBOARD_SMOKE_NETWORK="$dashboard_network" \
  FLEET_OPERATOR_PASSWORD="$password" \
  docker run --rm -i \
    --network "$dashboard_network" \
    -e FLEET_DASHBOARD_SMOKE_URL \
    -e FLEET_OPERATOR_PASSWORD \
    chummer-playwright:local node - <<'NODE'
'use strict';

const { chromium } = require('playwright');

const baseUrl = String(process.env.FLEET_DASHBOARD_SMOKE_URL || 'https://fleet.girschele.com').replace(/\/+$/, '');
const password = String(process.env.FLEET_OPERATOR_PASSWORD || '');

if (!password) {
  throw new Error('FLEET_OPERATOR_PASSWORD is required for smoke_fleet_dashboard');
}

const errors = [];
const requestLog = [];
let cockpitStatusSeen = false;
let cockpitStatusOk = false;
let cockpitPayloadSummary = null;

const failOnTextPatterns = [
  /Bridge script failed to load/i,
  /Bridge load failed/i,
  /Bridge assets did not finish loading/i,
];

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ ignoreHTTPSErrors: true });

  page.on('console', (msg) => {
    const type = msg.type();
    const text = msg.text();
    console.log(`console:${type}: ${text}`);
    if (type === 'error') {
      errors.push(`console error: ${text}`);
    }
  });
  page.on('pageerror', (error) => {
    const message = error && (error.stack || error.message) ? (error.stack || error.message) : String(error);
    console.log(`pageerror: ${message}`);
    errors.push(`pageerror: ${message}`);
  });
  page.on('requestfailed', (request) => {
    const message = request.failure() && request.failure().errorText ? request.failure().errorText : 'request failed';
    const url = request.url();
    console.log(`requestfailed: ${url} :: ${message}`);
    requestLog.push({ url, failure: message });
    errors.push(`requestfailed: ${url} :: ${message}`);
  });
  page.on('response', async (response) => {
    const url = response.url();
    if (!url.includes('/api/cockpit/status')) {
      return;
    }
    cockpitStatusSeen = true;
    console.log(`cockpit-response: ${response.status()} ${url}`);
    if (response.ok()) {
      cockpitStatusOk = true;
      try {
        const payload = await response.json();
        cockpitPayloadSummary = payload && payload.cockpit && payload.cockpit.summary ? payload.cockpit.summary : null;
      } catch (error) {
        errors.push(`cockpit json parse failed: ${error instanceof Error ? error.message : String(error)}`);
      }
    } else {
      errors.push(`cockpit status not ok: ${response.status()}`);
    }
  });

  try {
    await page.goto(`${baseUrl}/admin/login?next=%2Fdashboard%2F`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.fill('#password', password);
    await Promise.all([
      page.waitForURL((url) => url.pathname === '/dashboard/' || url.pathname === '/dashboard', { timeout: 30000 }),
      page.locator('button[type="submit"]').click(),
    ]);

    await page.waitForLoadState('networkidle', { timeout: 30000 }).catch(() => {});
    await page.waitForFunction(() => window.__fleetBridgeReady === true, null, { timeout: 30000 });

    const recommendedAction = (await page.locator('#recommended-action').textContent()) || '';
    const postureState = (await page.locator('#posture-state').textContent()) || '';
    const operatorCards = await page.locator('#operator-grid .operator-card, #operator-grid .empty').count();

    console.log(`recommended-action: ${recommendedAction}`);
    console.log(`posture-state: ${postureState}`);
    console.log(`operator-cards: ${operatorCards}`);
    if (cockpitPayloadSummary) {
      console.log(`cockpit-summary: ${JSON.stringify(cockpitPayloadSummary)}`);
    }

    if (!cockpitStatusSeen) {
      errors.push('cockpit status was never requested');
    }
    if (!cockpitStatusOk) {
      errors.push('cockpit status never returned 200');
    }
    if (postureState.trim() === '...') {
      errors.push('posture state never hydrated');
    }
    if (operatorCards < 1) {
      errors.push('operator cards did not render');
    }
    if (failOnTextPatterns.some((pattern) => pattern.test(recommendedAction))) {
      errors.push(`dashboard error banner still present: ${recommendedAction}`);
    }
    if (requestLog.some((entry) => /bridge\.(js|css)/.test(entry.url))) {
      errors.push('bridge asset request failed');
    }

    if (errors.length) {
      throw new Error(errors.join('\n'));
    }

    console.log('fleet dashboard smoke completed');
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error instanceof Error ? error.stack || error.message : error);
  process.exit(1);
});
NODE
}

patch_chummer_desktop_source() {
  local repo_root="${CHUMMER_PORTAL_REPO_ROOT:-/docker/chummer5a}"
  local patch_root="${CHUMMER_DESKTOP_SOURCE_PATCH_ROOT:-/tmp/chummer-desktop-source-patch}"

  if [[ ! -d "$repo_root" ]]; then
    echo "Chummer repo root not found: $repo_root" >&2
    exit 1
  fi

  echo "== patch desktop coach fallback in source repo =="
  rm -rf "$patch_root"
  mkdir -p "$patch_root/Chummer.Blazor.Desktop"
  cp "$repo_root/Chummer.Blazor.Desktop/Program.cs" "$patch_root/Chummer.Blazor.Desktop/Program.cs"
  patch_chummer_desktop_coach_client "$patch_root"
  docker run --rm \
    -v "$repo_root:/work" \
    -v "$patch_root:/patch:ro" \
    --entrypoint sh \
    nginx:1.27-alpine \
    -c 'cp /patch/Chummer.Blazor.Desktop/Program.cs /work/Chummer.Blazor.Desktop/Program.cs && chmod 0644 /work/Chummer.Blazor.Desktop/Program.cs && cp /patch/Chummer.Blazor.Desktop/DesktopWorkbenchCoachApiClient.cs /work/Chummer.Blazor.Desktop/DesktopWorkbenchCoachApiClient.cs && chmod 0644 /work/Chummer.Blazor.Desktop/DesktopWorkbenchCoachApiClient.cs'

  echo "== verify patched source files =="
  sed -n '1,80p' "$repo_root/Chummer.Blazor.Desktop/Program.cs"
  sed -n '1,120p' "$repo_root/Chummer.Blazor.Desktop/DesktopWorkbenchCoachApiClient.cs"
}

case "${1:-}" in
  admin-status)
    admin_status
    ;;
  chummer-portal)
    python3 - <<'PY'
import json
import urllib.error
import urllib.request

targets = [
    ("landing", "http://127.0.0.1:8091/"),
    ("api_health", "http://127.0.0.1:8091/api/health"),
    ("hub_health", "http://127.0.0.1:8091/hub/health"),
    ("session_health", "http://127.0.0.1:8091/session/health"),
    ("coach_health", "http://127.0.0.1:8091/coach/health"),
    ("avalonia_health", "http://127.0.0.1:8091/avalonia/health"),
    ("docs", "http://127.0.0.1:8091/docs/"),
    ("downloads", "http://127.0.0.1:8091/downloads/"),
]

results = []
for name, url in targets:
    try:
        with urllib.request.urlopen(url, timeout=8) as response:
            body = response.read(240).decode("utf-8", errors="replace")
            results.append(
                {
                    "target": name,
                    "url": url,
                    "status": response.status,
                    "content_type": response.headers.get("Content-Type"),
                    "preview": " ".join(body.split())[:160],
                }
            )
    except urllib.error.HTTPError as exc:
        body = exc.read(240).decode("utf-8", errors="replace")
        results.append(
            {
                "target": name,
                "url": url,
                "status": exc.code,
                "content_type": exc.headers.get("Content-Type"),
                "preview": " ".join(body.split())[:160],
            }
        )
    except Exception as exc:  # noqa: BLE001
        results.append(
            {
                "target": name,
                "url": url,
                "error": str(exc),
            }
        )

print(json.dumps(results, indent=2))
PY
    ;;
  build-chummer-windows-downloads)
    build_chummer_windows_downloads
    ;;
  build-chummer-desktop-downloads)
    CHUMMER_DESKTOP_RIDS="win-x64,osx-arm64" CHUMMER_DESKTOP_APPS="avalonia,blazor-desktop" build_chummer_windows_downloads
    ;;
  build-chummer-desktop-windows-downloads)
    CHUMMER_DESKTOP_APPS="avalonia,blazor-desktop" build_chummer_windows_downloads
    ;;
  build-chummer-avalonia-windows-downloads)
    CHUMMER_DESKTOP_APPS="avalonia" build_chummer_windows_downloads
    ;;
  build-chummer-desktop-macos-arm64-downloads)
    CHUMMER_DESKTOP_RIDS="osx-arm64" CHUMMER_DESKTOP_APPS="avalonia,blazor-desktop" build_chummer_windows_downloads
    ;;
  build-chummer-avalonia-macos-arm64-downloads)
    CHUMMER_DESKTOP_RIDS="osx-arm64" CHUMMER_DESKTOP_APPS="avalonia" build_chummer_windows_downloads
    ;;
  patch-chummer-portal-downloads-ui)
    patch_chummer_portal_downloads_ui
    ;;
  verify-chummer-portal-downloads-ui)
    verify_chummer_portal_downloads_ui
    ;;
  rebuild-chummer-portal)
    rebuild_chummer_portal
    ;;
  patch-and-rebuild-chummer-portal-downloads-ui)
    patch_chummer_portal_downloads_ui
    rebuild_chummer_portal
    ;;
  patch-chummer-desktop-source)
    patch_chummer_desktop_source
    ;;
  patch-and-build-chummer-windows-downloads)
    patch_chummer_desktop_source
    build_chummer_windows_downloads
    ;;
  cockpit-summary)
    admin_status | python3 -c '
import json, sys
data = json.load(sys.stdin)
summary = data.get("summary", {})
cockpit = data.get("cockpit", {})
workers = cockpit.get("workers", [])
projects = data.get("projects", [])
print(json.dumps({
  "fleet_health": data.get("fleet_health"),
  "active_workers": summary.get("active_workers"),
  "open_incidents": summary.get("open_incidents"),
  "approvals_waiting": summary.get("approvals_waiting"),
  "workers": [
    {
      "project_id": worker.get("project_id") or worker.get("id"),
      "status": worker.get("status") or worker.get("phase"),
      "slice": worker.get("current_slice"),
    }
    for worker in workers
  ],
  "project_states": [
    {
      "project_id": project.get("project_id") or project.get("id"),
      "status": project.get("status") or project.get("runtime_status_internal"),
      "runtime_status": project.get("runtime_status"),
      "active_run_id": project.get("active_run_id"),
      "next_action": project.get("next_action"),
      "cooldown_until": project.get("cooldown_until"),
    }
    for project in projects
  ],
}, indent=2))
'
    ;;
  gateway-cockpit)
    docker exec fleet-dashboard wget --header="X-Fleet-Operator-Password: $(operator_password)" -qO- http://127.0.0.1:8090/api/cockpit/status | python3 -c '
import json, sys
data = json.load(sys.stdin)
cockpit = data.get("cockpit", {})
summary = cockpit.get("summary", {})
print(json.dumps({
  "fleet_health": summary.get("fleet_health"),
  "active_workers": summary.get("active_workers"),
  "open_incidents": summary.get("open_incidents"),
  "approvals_waiting": summary.get("approvals_waiting"),
  "worker_ids": [worker.get("project_id") for worker in (cockpit.get("workers") or [])],
}, indent=2))
'
    ;;
  smoke-fleet-dashboard)
    smoke_fleet_dashboard
    ;;
  gateway-root)
    docker exec fleet-dashboard wget -S -O /dev/null http://127.0.0.1:8090/
    ;;
  host-root)
    curl -sS -D - -o /dev/null http://127.0.0.1:18090/
    ;;
  dashboard-logs)
    docker compose logs --tail="${2:-80}" fleet-dashboard
    ;;
  project-status)
    shift
    require_args "$@"
    docker exec -i fleet-controller python3 - "$@" <<'PY'
import json
import sqlite3
import sys

db = sqlite3.connect("/var/lib/codex-fleet/fleet.db")
db.row_factory = sqlite3.Row
for project_id in sys.argv[1:]:
    row = db.execute(
        """
        select id as project_id, status, active_run_id, current_slice, cooldown_until,
               last_run_at, last_error, spider_tier, spider_model, spider_reason,
               queue_index, queue_json, updated_at
          from projects
         where id = ?
        """,
        (project_id,),
    ).fetchone()
    print(json.dumps(dict(row) if row else {"project_id": project_id, "missing": True}, indent=2))
PY
    ;;
  compile-status)
    shift
    require_args "$@"
    admin_status | python3 -c '
import json, sys
data = json.load(sys.stdin)
targets = set(sys.argv[1:])
rows = []
for project in data.get("projects", []):
    project_id = str(project.get("id") or "")
    if project_id in targets:
        rows.append({
            "project_id": project_id,
            "lifecycle": project.get("lifecycle"),
            "runtime_status": project.get("runtime_status"),
            "compile": project.get("compile"),
            "compile_health": project.get("compile_health"),
        })
print(json.dumps(rows, indent=2))
' "$@"
    ;;
  run-status)
    shift
    require_args "$@"
    docker exec -i fleet-controller python3 - "$@" <<'PY'
import json
import sqlite3
import sys

db = sqlite3.connect("/var/lib/codex-fleet/fleet.db")
db.row_factory = sqlite3.Row
for run_id in sys.argv[1:]:
    row = db.execute(
        """
        select id, project_id, status, started_at, finished_at,
               model, account_alias, slice_name, job_kind, error_class, error_message
          from runs
         where id = ?
        """,
        (run_id,),
    ).fetchone()
    print(json.dumps(dict(row) if row else {"id": run_id, "missing": True}, indent=2))
PY
    ;;
  recent-runs)
    shift
    require_args "$@"
    project_id="$1"
    limit="${2:-10}"
    docker exec -i fleet-controller python3 - "$project_id" "$limit" <<'PY'
import json
import sqlite3
import sys

project_id = sys.argv[1]
limit = int(sys.argv[2])
db = sqlite3.connect("/var/lib/codex-fleet/fleet.db")
db.row_factory = sqlite3.Row
rows = db.execute(
    """
    select id, project_id, status, started_at, finished_at, job_kind, slice_name,
           error_class, error_message, decision_reason
      from runs
     where project_id = ?
     order by id desc
     limit ?
    """,
    (project_id, limit),
).fetchall()
print(json.dumps([dict(row) for row in rows], indent=2))
PY
    ;;
  time-vienna)
    TZ=Europe/Vienna date '+%Y-%m-%d %H:%M:%S %Z'
    ;;
  verify-config)
    python3 - <<'PY'
import pathlib
import sys
import yaml

root = pathlib.Path("/docker/fleet/config")
paths = [root / "fleet.yaml", root / "accounts.yaml", root / "policies.yaml", root / "routing.yaml", root / "groups.yaml"]
projects_dir = root / "projects"
paths.extend(sorted(projects_dir.glob("*.yaml")))
for path in paths:
    with path.open("r", encoding="utf-8") as handle:
        yaml.safe_load(handle)
print("config ok")
PY
    ;;
  db-schema)
    shift
    require_args "$@"
    docker exec -i fleet-controller python3 - "$@" <<'PY'
import json
import sqlite3
import sys

db = sqlite3.connect("/var/lib/codex-fleet/fleet.db")
db.row_factory = sqlite3.Row
for table_name in sys.argv[1:]:
    rows = db.execute(f"PRAGMA table_info({table_name})").fetchall()
    print(json.dumps({
        "table": table_name,
        "columns": [dict(row) for row in rows],
    }, indent=2))
PY
    ;;
  verify-python)
    shift
    require_args "$@"
    python3 -m py_compile "$@"
    ;;
  inject-chummer-public-repo-audit)
    python3 /docker/fleet/scripts/chummer_public_repo_audit_inject.py
    ;;
  inject-chummer-design-dropin-pack)
    python3 /docker/fleet/scripts/chummer_design_dropin_pack_inject.py
    ;;
  inject-ea-main-branch-audit)
    python3 /docker/fleet/scripts/ea_main_branch_audit_inject.py
    ;;
  inject-fleet-public-audit)
    python3 /docker/fleet/scripts/fleet_public_audit_inject.py
    ;;
  rebuild)
    shift
    require_args "$@"
    docker compose up -d --build "$@"
    ;;
  ""|-h|--help|help)
    usage
    ;;
  *)
    echo "unknown command: $1" >&2
    usage >&2
    exit 1
    ;;
esac
