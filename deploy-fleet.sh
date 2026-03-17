#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="/opt/codex-fleet"
HOST_DASHBOARD_PORT="18090"
NETWORK_NAME="codex-fleet-net"
FORCE=0

usage() {
  cat <<USAGE
Usage: $0 [--install-dir /opt/codex-fleet] [--host-port 18090] [--network-name codex-fleet-net] [--force]

This installs the Codex Fleet Studio bundle, which includes:
- fleet controller / spider scheduler
- Studio design layer at /studio
- reverse-proxy dashboard entrypoint on port 8090 inside Docker
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --install-dir)
      INSTALL_DIR="$2"
      shift 2
      ;;
    --host-port)
      HOST_DASHBOARD_PORT="$2"
      shift 2
      ;;
    --network-name)
      NETWORK_NAME="$2"
      shift 2
      ;;
    --force)
      FORCE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

command -v docker >/dev/null || { echo "docker not found" >&2; exit 1; }
if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  echo "docker compose not found" >&2
  exit 1
fi

BUNDLE_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ -n "${SUDO_USER:-}" ] && id "$SUDO_USER" >/dev/null 2>&1; then
  OWNER_UID="$(id -u "$SUDO_USER")"
  OWNER_GID="$(id -g "$SUDO_USER")"
else
  OWNER_UID="$(id -u)"
  OWNER_GID="$(id -g)"
fi

mkdir -p \
  "$INSTALL_DIR/controller" \
  "$INSTALL_DIR/studio" \
  "$INSTALL_DIR/admin" \
  "$INSTALL_DIR/auditor" \
  "$INSTALL_DIR/gateway/static" \
  "$INSTALL_DIR/scripts" \
  "$INSTALL_DIR/config/projects" \
  "$INSTALL_DIR/secrets" \
  "$INSTALL_DIR/state"

file_mode() {
  local src="$1"
  if [ -x "$src" ]; then
    printf '%s' "0755"
  else
    printf '%s' "0644"
  fi
}

copy_bundle_file() {
  local src="$1"
  local dest="$2"
  mkdir -p "$(dirname "$dest")"
  install -m "$(file_mode "$src")" "$src" "$dest"
}

copy_mutable_file() {
  local src="$1"
  local dest="$2"
  local mode="${3:-$(file_mode "$src")}"
  mkdir -p "$(dirname "$dest")"
  if [ -e "$dest" ] && [ "$FORCE" -ne 1 ]; then
    return 0
  fi
  install -m "$mode" "$src" "$dest"
}

copy_tree() {
  local src_root="$1"
  local dest_root="$2"
  shift 2
  local rel src dest skip pattern
  while IFS= read -r -d '' src; do
    rel="${src#"$src_root"/}"
    skip=0
    for pattern in "$@"; do
      if [[ "$rel" == $pattern ]]; then
        skip=1
        break
      fi
    done
    if [ "$skip" -eq 1 ]; then
      continue
    fi
    dest="$dest_root/$rel"
    copy_bundle_file "$src" "$dest"
  done < <(find "$src_root" -type f ! -path '*/__pycache__/*' ! -name '*.pyc' -print0)
}

wait_for_container_health() {
  local container_name="$1"
  local timeout_seconds="${2:-180}"
  local deadline=$((SECONDS + timeout_seconds))
  local status=""
  while [ "$SECONDS" -lt "$deadline" ]; do
    status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container_name" 2>/dev/null || true)"
    case "$status" in
      healthy)
        return 0
        ;;
      exited|dead|unhealthy)
        break
        ;;
    esac
    sleep 2
  done
  echo "Container $container_name did not become healthy (last status: ${status:-missing})." >&2
  return 1
}

wait_for_http() {
  local url="$1"
  local timeout_seconds="${2:-120}"
  python3 - "$url" "$timeout_seconds" <<'PY'
import sys
import time
import urllib.request

url = sys.argv[1]
timeout_seconds = int(sys.argv[2])
deadline = time.time() + timeout_seconds
last_error = "no response"
while time.time() < deadline:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            if 200 <= int(response.status) < 300:
                sys.exit(0)
            last_error = f"status {response.status}"
    except Exception as exc:  # pragma: no cover - shell smoke helper
        last_error = str(exc)
    time.sleep(2)
print(f"{url} did not become ready within {timeout_seconds}s: {last_error}", file=sys.stderr)
sys.exit(1)
PY
}

run_post_deploy_smoke_checks() {
  local dashboard_url="http://127.0.0.1:$HOST_DASHBOARD_PORT"
  local container
  echo "Waiting for Fleet services to report healthy..."
  for container in \
    fleet-controller \
    fleet-studio \
    fleet-admin \
    fleet-auditor \
    fleet-dashboard \
    fleet-rebuilder
  do
    wait_for_container_health "$container" 180
  done
  echo "Running dashboard smoke checks..."
  wait_for_http "$dashboard_url/health" 120
  wait_for_http "$dashboard_url/api/status" 120
}

copy_bundle_file "$BUNDLE_DIR/docker-compose.yml" "$INSTALL_DIR/docker-compose.yml"
copy_tree "$BUNDLE_DIR/controller" "$INSTALL_DIR/controller"
copy_tree "$BUNDLE_DIR/studio" "$INSTALL_DIR/studio"
copy_tree "$BUNDLE_DIR/admin" "$INSTALL_DIR/admin"
copy_tree "$BUNDLE_DIR/auditor" "$INSTALL_DIR/auditor"
copy_tree "$BUNDLE_DIR/gateway" "$INSTALL_DIR/gateway"
copy_tree "$BUNDLE_DIR/scripts" "$INSTALL_DIR/scripts"
copy_tree "$BUNDLE_DIR/config" "$INSTALL_DIR/config" "accounts.yaml"
copy_mutable_file "$BUNDLE_DIR/config/accounts.yaml.example" "$INSTALL_DIR/config/accounts.yaml"
copy_bundle_file "$BUNDLE_DIR/config/accounts.yaml.example" "$INSTALL_DIR/config/accounts.yaml.example"
copy_mutable_file "$BUNDLE_DIR/runtime.ea.env" "$INSTALL_DIR/runtime.ea.env"
copy_bundle_file "$BUNDLE_DIR/runtime.ea.env" "$INSTALL_DIR/runtime.ea.env.example"
copy_bundle_file "$BUNDLE_DIR/runtime.env.example" "$INSTALL_DIR/runtime.env.example"
if [ ! -e "$INSTALL_DIR/runtime.env" ]; then
  install -m 0600 /dev/null "$INSTALL_DIR/runtime.env"
fi
copy_bundle_file "$BUNDLE_DIR/README.md" "$INSTALL_DIR/README.md"

cat > "$INSTALL_DIR/.env" <<ENVEOF
LOCAL_UID=$OWNER_UID
LOCAL_GID=$OWNER_GID
HOST_DASHBOARD_PORT=$HOST_DASHBOARD_PORT
FLEET_NETWORK_NAME=$NETWORK_NAME
ENVEOF

chown -R "$OWNER_UID:$OWNER_GID" \
  "$INSTALL_DIR/state" \
  "$INSTALL_DIR/secrets" \
  "$INSTALL_DIR/config" \
  "$INSTALL_DIR/.env" \
  "$INSTALL_DIR/runtime.env" \
  "$INSTALL_DIR/runtime.env.example" \
  "$INSTALL_DIR/runtime.ea.env" \
  "$INSTALL_DIR/runtime.ea.env.example" \
  "$INSTALL_DIR/README.md" \
  "$INSTALL_DIR/controller" \
  "$INSTALL_DIR/studio" \
  "$INSTALL_DIR/admin" \
  "$INSTALL_DIR/auditor" \
  "$INSTALL_DIR/gateway" \
  "$INSTALL_DIR/scripts" || true

echo "Install dir: $INSTALL_DIR"
echo "Building and starting stack..."
cd "$INSTALL_DIR"
"${COMPOSE[@]}" up -d --build

if ! run_post_deploy_smoke_checks; then
  echo >&2
  echo "Fleet deploy smoke checks failed. Current compose status:" >&2
  "${COMPOSE[@]}" ps >&2 || true
  echo >&2
  echo "Recent compose logs:" >&2
  "${COMPOSE[@]}" logs --tail=120 >&2 || true
  exit 1
fi

echo
echo "Dashboard host URL: http://127.0.0.1:$HOST_DASHBOARD_PORT"
echo "Studio URL: http://127.0.0.1:$HOST_DASHBOARD_PORT/studio"
echo "Docker network for cloudflared: $NETWORK_NAME"
echo "Cloudflare origin target from another container on that network: http://fleet-dashboard:8090"
echo
echo "If your cloudflared container is already running, connect it once:"
echo "  docker network connect $NETWORK_NAME <cloudflared-container>"
echo
echo "Next steps:"
echo "  1. Put API keys/auth.json files into $INSTALL_DIR/secrets/ or add env vars to $INSTALL_DIR/runtime.env"
echo "  2. Edit $INSTALL_DIR/config/accounts.yaml to map account aliases to api_key_file, api_key_env, or auth_json_file"
echo "  3. Open $HOST_DASHBOARD_PORT/studio and create a design session"
echo "  4. Publish approved artifacts so coding workers read .codex-studio/published/* on their next slice"
echo "  5. Restart after config changes: cd $INSTALL_DIR && ${COMPOSE[*]} up -d --build"
