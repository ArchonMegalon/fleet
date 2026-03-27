#!/bin/sh
set -eu

compose_file="${FLEET_REBUILD_COMPOSE_FILE:-/workspace/docker-compose.yml}"
compose_project_name="${FLEET_COMPOSE_PROJECT_NAME:-fleet}"
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
autoheal_enabled="$(printf '%s' "${FLEET_AUTOHEAL_ENABLED:-true}" | tr '[:upper:]' '[:lower:]')"
autoheal_services="${FLEET_AUTOHEAL_SERVICES:-fleet-controller fleet-dashboard}"
autoheal_threshold="${FLEET_AUTOHEAL_THRESHOLD:-2}"
autoheal_cooldown_seconds="${FLEET_AUTOHEAL_COOLDOWN_SECONDS:-300}"
autoheal_timeout_seconds="${FLEET_AUTOHEAL_TIMEOUT_SECONDS:-120}"

mkdir -p "$state_dir"

heartbeat_file="$state_dir/heartbeat.txt"
last_run_file="$state_dir/last_run_utc.txt"
log_file="$state_dir/rebuild.log"
autoheal_state_dir="$state_dir/autoheal"
mkdir -p "$autoheal_state_dir"

log() {
  printf '%s %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*" | tee -a "$log_file"
}

compose_cmd() {
  docker compose -p "$compose_project_name" -f "$compose_file" "$@"
}

service_state_token() {
  printf '%s' "$1" | tr '/: ' '___'
}

service_fail_file() {
  printf '%s/%s.failcount\n' "$autoheal_state_dir" "$(service_state_token "$1")"
}

service_restart_file() {
  printf '%s/%s.last_restart_epoch\n' "$autoheal_state_dir" "$(service_state_token "$1")"
}

read_int_file() {
  file="$1"
  default_value="$2"
  if [ ! -f "$file" ]; then
    printf '%s\n' "$default_value"
    return 0
  fi
  value="$(cat "$file" 2>/dev/null || true)"
  case "$value" in
    ''|*[!0-9]*)
      printf '%s\n' "$default_value"
      ;;
    *)
      printf '%s\n' "$value"
      ;;
  esac
}

set_fail_count() {
  printf '%s\n' "$2" >"$(service_fail_file "$1")"
}

increment_fail_count() {
  service="$1"
  current="$(read_int_file "$(service_fail_file "$service")" 0)"
  next=$(( current + 1 ))
  set_fail_count "$service" "$next"
  printf '%s\n' "$next"
}

set_restart_epoch() {
  printf '%s\n' "$2" >"$(service_restart_file "$1")"
}

recent_restart_within_cooldown() {
  service="$1"
  now_epoch="$2"
  last_restart="$(read_int_file "$(service_restart_file "$service")" 0)"
  if [ "$last_restart" -le 0 ]; then
    return 1
  fi
  age=$(( now_epoch - last_restart ))
  [ "$age" -lt "$autoheal_cooldown_seconds" ]
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
  compose_cmd up -d --build --force-recreate $set_services >>"$log_file" 2>&1
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

autoheal_service() {
  service="$1"
  log "autoheal restarting service: $service"
  compose_cmd restart "$service" >>"$log_file" 2>&1 || return 1
  wait_for_service_health "$service" "$autoheal_timeout_seconds" || return 1
  set_fail_count "$service" 0
  set_restart_epoch "$service" "$(date -u +%s)"
  log "autoheal recovered service: $service"
}

monitor_autoheal() {
  if [ "$autoheal_enabled" != "true" ] && [ "$autoheal_enabled" != "1" ] && [ "$autoheal_enabled" != "yes" ]; then
    return 0
  fi
  now_epoch="$(date -u +%s)"
  for service in $autoheal_services; do
    status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$service" 2>>"$log_file" || true)"
    case "$status" in
      healthy|running)
        set_fail_count "$service" 0
        ;;
      unhealthy|dead|exited)
        count="$(increment_fail_count "$service")"
        log "autoheal observed unhealthy service: $service status=$status consecutive_failures=$count"
        if [ "$count" -lt "$autoheal_threshold" ]; then
          continue
        fi
        if recent_restart_within_cooldown "$service" "$now_epoch"; then
          log "autoheal cooldown active for $service"
          continue
        fi
        if ! autoheal_service "$service"; then
          log "autoheal failed for $service"
        fi
        ;;
      *)
        ;;
    esac
  done
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
  monitor_autoheal
  sleep 30
done
