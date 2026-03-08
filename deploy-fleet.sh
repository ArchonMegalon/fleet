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

mkdir -p "$INSTALL_DIR/controller" "$INSTALL_DIR/studio" "$INSTALL_DIR/gateway" "$INSTALL_DIR/config" "$INSTALL_DIR/secrets" "$INSTALL_DIR/state"

copy_file() {
  local src="$1"
  local dest="$2"
  if [ -e "$dest" ] && [ "$FORCE" -ne 1 ]; then
    return 0
  fi
  install -m 0644 "$src" "$dest"
}

copy_file "$BUNDLE_DIR/docker-compose.yml" "$INSTALL_DIR/docker-compose.yml"
copy_file "$BUNDLE_DIR/controller/Dockerfile" "$INSTALL_DIR/controller/Dockerfile"
copy_file "$BUNDLE_DIR/controller/requirements.txt" "$INSTALL_DIR/controller/requirements.txt"
copy_file "$BUNDLE_DIR/controller/app.py" "$INSTALL_DIR/controller/app.py"
copy_file "$BUNDLE_DIR/studio/Dockerfile" "$INSTALL_DIR/studio/Dockerfile"
copy_file "$BUNDLE_DIR/studio/requirements.txt" "$INSTALL_DIR/studio/requirements.txt"
copy_file "$BUNDLE_DIR/studio/app.py" "$INSTALL_DIR/studio/app.py"
copy_file "$BUNDLE_DIR/gateway/nginx.conf" "$INSTALL_DIR/gateway/nginx.conf"
copy_file "$BUNDLE_DIR/config/fleet.yaml" "$INSTALL_DIR/config/fleet.yaml"
if [ ! -e "$INSTALL_DIR/config/accounts.yaml" ] || [ "$FORCE" -eq 1 ]; then
  install -m 0644 "$BUNDLE_DIR/config/accounts.yaml.example" "$INSTALL_DIR/config/accounts.yaml"
fi
install -m 0644 "$BUNDLE_DIR/config/accounts.yaml.example" "$INSTALL_DIR/config/accounts.yaml.example"
install -m 0644 "$BUNDLE_DIR/runtime.env.example" "$INSTALL_DIR/runtime.env.example"
if [ ! -e "$INSTALL_DIR/runtime.env" ]; then
  install -m 0600 /dev/null "$INSTALL_DIR/runtime.env"
fi
install -m 0644 "$BUNDLE_DIR/README.md" "$INSTALL_DIR/README.md"

cat > "$INSTALL_DIR/.env" <<ENVEOF
LOCAL_UID=$OWNER_UID
LOCAL_GID=$OWNER_GID
HOST_DASHBOARD_PORT=$HOST_DASHBOARD_PORT
FLEET_NETWORK_NAME=$NETWORK_NAME
ENVEOF

chown -R "$OWNER_UID:$OWNER_GID" "$INSTALL_DIR/state" "$INSTALL_DIR/secrets" "$INSTALL_DIR/config" "$INSTALL_DIR/.env" "$INSTALL_DIR/runtime.env" "$INSTALL_DIR/runtime.env.example" "$INSTALL_DIR/README.md" "$INSTALL_DIR/controller" "$INSTALL_DIR/studio" "$INSTALL_DIR/gateway" || true

echo "Install dir: $INSTALL_DIR"
echo "Building and starting stack..."
cd "$INSTALL_DIR"
"${COMPOSE[@]}" up -d --build

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
