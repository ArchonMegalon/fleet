#!/bin/sh
set -eu

compose_file="${FLEET_REBUILD_COMPOSE_FILE:-/workspace/docker-compose.yml}"
state_dir="${FLEET_REBUILD_STATE_DIR:-/workspace/state/rebuilder}"
enabled="$(printf '%s' "${FLEET_REBUILD_ENABLED:-true}" | tr '[:upper:]' '[:lower:]')"
target_hour="$(printf '%02d' "${FLEET_REBUILD_HOUR_UTC:-04}")"
target_minute="$(printf '%02d' "${FLEET_REBUILD_MINUTE_UTC:-15}")"
services="${FLEET_REBUILD_SERVICES:-fleet-controller fleet-studio fleet-quartermaster fleet-dashboard}"
granularity="$(printf '%s' "${FLEET_REBUILD_REFRESH_TOKEN_GRANULARITY:-day}" | tr '[:upper:]' '[:lower:]')"
canary_enabled="$(printf '%s' "${FLEET_REBUILD_CANARY_ENABLED:-true}" | tr '[:upper:]' '[:lower:]')"
canary_services="${FLEET_REBUILD_CANARY_SERVICES:-fleet-controller}"
canary_timeout_seconds="${FLEET_REBUILD_CANARY_TIMEOUT_SECONDS:-180}"
canary_poll_seconds="${FLEET_REBUILD_CANARY_POLL_SECONDS:-5}"

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
  if ! rebuild_with_canary "$services"; then
    log "rebuild failed"
    return 1
  fi
  printf '%s\n' "$current_day" >"$last_run_file"
  log "rebuild completed successfully"
}

wait_for_service_health() {
  service="$1"
  timeout_seconds="$2"
  deadline=$(( $(date -u +%s) + timeout_seconds ))
  while [ "$(date -u +%s)" -lt "$deadline" ]; do
    status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$service" 2>>"$log_file" || true)"
    if [ "$status" = "healthy" ] || [ "$status" = "running" ]; then
      log "service healthy: $service ($status)"
      return 0
    fi
    if [ "$status" = "unhealthy" ] || [ "$status" = "dead" ] || [ "$status" = "exited" ]; then
      log "service failed health: $service ($status)"
      return 1
    fi
    sleep "$canary_poll_seconds"
  done
  log "service health timed out: $service"
  return 1
}

rebuild_service_set() {
  set_services="$1"
  if [ -z "$set_services" ]; then
    return 0
  fi
  docker compose -f "$compose_file" up -d --build --force-recreate $set_services >>"$log_file" 2>&1
}

wait_for_service_set() {
  set_services="$1"
  if [ -z "$set_services" ]; then
    return 0
  fi
  for service in $set_services; do
    wait_for_service_health "$service" "$canary_timeout_seconds" || return 1
  done
}

filter_remaining_services() {
  all_services="$1"
  chosen="$2"
  remaining=""
  for service in $all_services; do
    case " $chosen " in
      *" $service "*) ;;
      *) remaining="$remaining $service" ;;
    esac
  done
  printf '%s\n' "$(printf '%s' "$remaining" | xargs)"
}

rebuild_with_canary() {
  all_services="$1"
  if [ -z "$all_services" ]; then
    return 0
  fi
  if [ "$canary_enabled" = "true" ] || [ "$canary_enabled" = "1" ] || [ "$canary_enabled" = "yes" ]; then
    chosen_canary=""
    for service in $canary_services; do
      case " $all_services " in
        *" $service "*) chosen_canary="$chosen_canary $service" ;;
      esac
    done
    chosen_canary="$(printf '%s' "$chosen_canary" | xargs)"
    if [ -n "$chosen_canary" ]; then
      remaining_services="$(filter_remaining_services "$all_services" "$chosen_canary")"
      log "starting canary rebuild for services: $chosen_canary"
      rebuild_service_set "$chosen_canary" || return 1
      wait_for_service_set "$chosen_canary" || return 1
      if [ -n "$remaining_services" ]; then
        log "canary passed; rebuilding remaining services: $remaining_services"
        rebuild_service_set "$remaining_services" || return 1
        wait_for_service_set "$remaining_services" || return 1
      fi
      return 0
    fi
  fi
  rebuild_service_set "$all_services" || return 1
  wait_for_service_set "$all_services" || return 1
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
