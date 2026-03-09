#!/bin/sh
set -eu

compose_file="${FLEET_REBUILD_COMPOSE_FILE:-/workspace/docker-compose.yml}"
state_dir="${FLEET_REBUILD_STATE_DIR:-/workspace/state/rebuilder}"
enabled="$(printf '%s' "${FLEET_REBUILD_ENABLED:-true}" | tr '[:upper:]' '[:lower:]')"
target_hour="$(printf '%02d' "${FLEET_REBUILD_HOUR_UTC:-04}")"
target_minute="$(printf '%02d' "${FLEET_REBUILD_MINUTE_UTC:-15}")"
services="${FLEET_REBUILD_SERVICES:-fleet-controller fleet-studio fleet-dashboard}"
granularity="$(printf '%s' "${FLEET_REBUILD_REFRESH_TOKEN_GRANULARITY:-day}" | tr '[:upper:]' '[:lower:]')"

mkdir -p "$state_dir"

heartbeat_file="$state_dir/heartbeat.txt"
last_run_file="$state_dir/last_run_utc.txt"
log_file="$state_dir/rebuild.log"

log() {
  printf '%s %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*" | tee -a "$log_file"
}

refresh_token() {
  case "$granularity" in
    hour)
      date -u +'%Y-%m-%dT%H'
      ;;
    minute)
      date -u +'%Y-%m-%dT%H:%M'
      ;;
    *)
      date -u +'%Y-%m-%d'
      ;;
  esac
}

run_rebuild() {
  current_day="$(date -u +'%Y-%m-%d')"
  export CODEX_NPM_REFRESH_TOKEN
  CODEX_NPM_REFRESH_TOKEN="$(refresh_token)"
  log "starting rebuild for services: $services (refresh_token=$CODEX_NPM_REFRESH_TOKEN)"
  if docker compose -f "$compose_file" up -d --build --force-recreate $services >>"$log_file" 2>&1; then
    printf '%s\n' "$current_day" >"$last_run_file"
    log "rebuild completed successfully"
  else
    log "rebuild failed"
  fi
}

while :; do
  date -u +'%Y-%m-%dT%H:%M:%SZ' >"$heartbeat_file"
  if [ "$enabled" = "true" ] || [ "$enabled" = "1" ] || [ "$enabled" = "yes" ]; then
    current_day="$(date -u +'%Y-%m-%d')"
    current_hour="$(date -u +'%H')"
    current_minute="$(date -u +'%M')"
    last_run_day=""
    if [ -f "$last_run_file" ]; then
      last_run_day="$(cat "$last_run_file" 2>/dev/null || true)"
    fi
    if [ "$current_hour" = "$target_hour" ] && [ "$current_minute" = "$target_minute" ] && [ "$last_run_day" != "$current_day" ]; then
      run_rebuild
    fi
  fi
  sleep 30
done
