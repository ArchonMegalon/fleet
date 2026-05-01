#!/bin/sh
set -eu

default_workspace_root="/docker/fleet"
if [ ! -d "$default_workspace_root" ] && [ -d /workspace ]; then
  default_workspace_root="/workspace"
fi
workspace_root="${FLEET_REBUILD_WORKSPACE_ROOT:-$default_workspace_root}"
compose_file="${FLEET_REBUILD_COMPOSE_FILE:-$workspace_root/docker-compose.yml}"
compose_project_name="${FLEET_COMPOSE_PROJECT_NAME:-fleet}"
state_dir="${FLEET_REBUILD_STATE_DIR:-$workspace_root/state/rebuilder}"
enabled="$(printf '%s' "${FLEET_REBUILD_ENABLED:-true}" | tr '[:upper:]' '[:lower:]')"
target_hour="$(printf '%02d' "${FLEET_REBUILD_HOUR_UTC:-04}")"
target_minute="$(printf '%02d' "${FLEET_REBUILD_MINUTE_UTC:-15}")"
services="${FLEET_REBUILD_SERVICES:-fleet-controller fleet-studio fleet-quartermaster fleet-dashboard}"
granularity="$(printf '%s' "${FLEET_REBUILD_REFRESH_TOKEN_GRANULARITY:-day}" | tr '[:upper:]' '[:lower:]')"
loop_once="$(printf '%s' "${FLEET_REBUILD_LOOP_ONCE:-false}" | tr '[:upper:]' '[:lower:]')"
canary_enabled="$(printf '%s' "${FLEET_REBUILD_CANARY_ENABLED:-true}" | tr '[:upper:]' '[:lower:]')"
canary_services="${FLEET_REBUILD_CANARY_SERVICES:-fleet-controller}"
canary_timeout_seconds="${FLEET_REBUILD_CANARY_TIMEOUT_SECONDS:-180}"
canary_poll_seconds="${FLEET_REBUILD_CANARY_POLL_SECONDS:-5}"
autoheal_enabled="$(printf '%s' "${FLEET_AUTOHEAL_ENABLED:-true}" | tr '[:upper:]' '[:lower:]')"
autoheal_services="${FLEET_AUTOHEAL_SERVICES:-fleet-controller fleet-dashboard fleet-auditor fleet-design-supervisor}"
autoheal_threshold="${FLEET_AUTOHEAL_THRESHOLD:-2}"
autoheal_cooldown_seconds="${FLEET_AUTOHEAL_COOLDOWN_SECONDS:-300}"
autoheal_timeout_seconds="${FLEET_AUTOHEAL_TIMEOUT_SECONDS:-120}"
autoheal_escalate_after_restarts="${FLEET_AUTOHEAL_ESCALATE_AFTER_RESTARTS:-3}"
autoheal_escalate_window_seconds="${FLEET_AUTOHEAL_ESCALATE_WINDOW_SECONDS:-1800}"
external_proof_autoingest_enabled="$(printf '%s' "${FLEET_EXTERNAL_PROOF_AUTOINGEST_ENABLED:-true}" | tr '[:upper:]' '[:lower:]')"
external_proof_commands_dir="${FLEET_EXTERNAL_PROOF_COMMANDS_DIR:-$workspace_root/.codex-studio/published/external-proof-commands}"
external_proof_autoingest_cooldown_seconds="${FLEET_EXTERNAL_PROOF_AUTOINGEST_COOLDOWN_SECONDS:-120}"

mkdir -p "$state_dir"

heartbeat_file="$state_dir/heartbeat.txt"
last_run_file="$state_dir/last_run_utc.txt"
log_file="$state_dir/rebuild.log"
autoheal_state_dir="$state_dir/autoheal"
autoheal_event_log="$autoheal_state_dir/events.jsonl"
external_proof_autoingest_state_dir="$state_dir/external-proof-autoingest"
external_proof_autoingest_status_file="$external_proof_autoingest_state_dir/status.json"
external_proof_autoingest_last_success_fingerprint_file="$external_proof_autoingest_state_dir/last_success_fingerprint.txt"
external_proof_autoingest_last_attempt_fingerprint_file="$external_proof_autoingest_state_dir/last_attempt_fingerprint.txt"
external_proof_autoingest_last_attempt_epoch_file="$external_proof_autoingest_state_dir/last_attempt_epoch"
external_proof_autoingest_last_success_epoch_file="$external_proof_autoingest_state_dir/last_success_epoch"
external_proof_autoingest_last_result_file="$external_proof_autoingest_state_dir/last_result.txt"
external_proof_autoingest_last_detail_file="$external_proof_autoingest_state_dir/last_detail.txt"
mkdir -p "$autoheal_state_dir"
mkdir -p "$external_proof_autoingest_state_dir"

log() {
  printf '%s %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*" | tee -a "$log_file"
}

compose_cmd() {
  docker compose -p "$compose_project_name" -f "$compose_file" "$@"
}

iso_now() {
  date -u +'%Y-%m-%dT%H:%M:%SZ'
}

sanitize_text() {
  printf '%s' "$1" | tr '\n\r' ' ' | sed 's/[[:space:]][[:space:]]*/ /g; s/^ //; s/ $//'
}

json_escape() {
  sanitize_text "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

iso_from_epoch() {
  epoch="$1"
  if [ "${epoch:-0}" -le 0 ] 2>/dev/null; then
    printf '%s' ""
    return 0
  fi
  date -u -d "@$epoch" +'%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || printf '%s' ""
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

service_status_file() {
  printf '%s/%s.status.json\n' "$autoheal_state_dir" "$(service_state_token "$1")"
}

service_total_restart_file() {
  printf '%s/%s.total_restarts\n' "$autoheal_state_dir" "$(service_state_token "$1")"
}

service_total_failure_file() {
  printf '%s/%s.total_failures\n' "$autoheal_state_dir" "$(service_state_token "$1")"
}

service_restart_window_start_file() {
  printf '%s/%s.restart_window_start_epoch\n' "$autoheal_state_dir" "$(service_state_token "$1")"
}

service_restart_window_count_file() {
  printf '%s/%s.restart_window_count\n' "$autoheal_state_dir" "$(service_state_token "$1")"
}

service_last_action_file() {
  printf '%s/%s.last_action.txt\n' "$autoheal_state_dir" "$(service_state_token "$1")"
}

service_last_result_file() {
  printf '%s/%s.last_result.txt\n' "$autoheal_state_dir" "$(service_state_token "$1")"
}

service_last_detail_file() {
  printf '%s/%s.last_detail.txt\n' "$autoheal_state_dir" "$(service_state_token "$1")"
}

service_last_failure_epoch_file() {
  printf '%s/%s.last_failure_epoch\n' "$autoheal_state_dir" "$(service_state_token "$1")"
}

service_last_recovered_epoch_file() {
  printf '%s/%s.last_recovered_epoch\n' "$autoheal_state_dir" "$(service_state_token "$1")"
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

read_text_file() {
  file="$1"
  default_value="$2"
  if [ ! -f "$file" ]; then
    printf '%s\n' "$default_value"
    return 0
  fi
  cat "$file" 2>/dev/null || printf '%s\n' "$default_value"
}

write_text_file() {
  printf '%s\n' "$2" >"$1"
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

set_failure_epoch() {
  printf '%s\n' "$2" >"$(service_last_failure_epoch_file "$1")"
}

set_recovered_epoch() {
  printf '%s\n' "$2" >"$(service_last_recovered_epoch_file "$1")"
}

increment_total_restarts() {
  service="$1"
  current="$(read_int_file "$(service_total_restart_file "$service")" 0)"
  next=$(( current + 1 ))
  printf '%s\n' "$next" >"$(service_total_restart_file "$service")"
  printf '%s\n' "$next"
}

increment_total_failures() {
  service="$1"
  current="$(read_int_file "$(service_total_failure_file "$service")" 0)"
  next=$(( current + 1 ))
  printf '%s\n' "$next" >"$(service_total_failure_file "$service")"
  printf '%s\n' "$next"
}

restart_window_count() {
  service="$1"
  now_epoch="$2"
  window_start="$(read_int_file "$(service_restart_window_start_file "$service")" 0)"
  current="$(read_int_file "$(service_restart_window_count_file "$service")" 0)"
  if [ "$window_start" -le 0 ]; then
    printf '0\n'
    return 0
  fi
  if [ $(( now_epoch - window_start )) -gt "$autoheal_escalate_window_seconds" ]; then
    printf '0\n'
    return 0
  fi
  printf '%s\n' "$current"
}

note_restart_attempt() {
  service="$1"
  now_epoch="$2"
  window_start="$(read_int_file "$(service_restart_window_start_file "$service")" 0)"
  current="$(read_int_file "$(service_restart_window_count_file "$service")" 0)"
  if [ "$window_start" -le 0 ] || [ $(( now_epoch - window_start )) -gt "$autoheal_escalate_window_seconds" ]; then
    window_start="$now_epoch"
    current=0
  fi
  current=$(( current + 1 ))
  printf '%s\n' "$window_start" >"$(service_restart_window_start_file "$service")"
  printf '%s\n' "$current" >"$(service_restart_window_count_file "$service")"
  printf '%s\n' "$current"
}

record_service_note() {
  service="$1"
  action="$2"
  result="$3"
  detail="$4"
  write_text_file "$(service_last_action_file "$service")" "$(sanitize_text "$action")"
  write_text_file "$(service_last_result_file "$service")" "$(sanitize_text "$result")"
  write_text_file "$(service_last_detail_file "$service")" "$(sanitize_text "$detail")"
}

append_autoheal_event() {
  service="$1"
  event_kind="$2"
  status="$3"
  detail="$4"
  failures="$5"
  cooldown_remaining="$6"
  printf '{"at":"%s","service":"%s","event":"%s","status":"%s","detail":"%s","consecutive_failures":%s,"cooldown_remaining_seconds":%s}\n' \
    "$(iso_now)" \
    "$(json_escape "$service")" \
    "$(json_escape "$event_kind")" \
    "$(json_escape "$status")" \
    "$(json_escape "$detail")" \
    "${failures:-0}" \
    "${cooldown_remaining:-0}" >>"$autoheal_event_log"
}

write_service_status() {
  service="$1"
  current_state="$2"
  observed_status="$3"
  consecutive_failures="$4"
  detail="$5"
  cooldown_remaining="$6"
  last_restart_epoch="$(read_int_file "$(service_restart_file "$service")" 0)"
  last_failure_epoch="$(read_int_file "$(service_last_failure_epoch_file "$service")" 0)"
  last_recovered_epoch="$(read_int_file "$(service_last_recovered_epoch_file "$service")" 0)"
  total_restarts="$(read_int_file "$(service_total_restart_file "$service")" 0)"
  total_failures="$(read_int_file "$(service_total_failure_file "$service")" 0)"
  restart_count="$(restart_window_count "$service" "$(date -u +%s)")"
  cooldown_active="false"
  if [ "${cooldown_remaining:-0}" -gt 0 ]; then
    cooldown_active="true"
  fi
  cat >"$(service_status_file "$service")" <<EOF
{
  "generated_at": "$(iso_now)",
  "service": "$(json_escape "$service")",
  "current_state": "$(json_escape "$current_state")",
  "observed_status": "$(json_escape "$observed_status")",
  "consecutive_failures": ${consecutive_failures:-0},
  "threshold": ${autoheal_threshold:-0},
  "cooldown_active": ${cooldown_active},
  "cooldown_remaining_seconds": ${cooldown_remaining:-0},
  "last_action": "$(json_escape "$(read_text_file "$(service_last_action_file "$service")" "")")",
  "last_result": "$(json_escape "$(read_text_file "$(service_last_result_file "$service")" "")")",
  "last_detail": "$(json_escape "$(read_text_file "$(service_last_detail_file "$service")" "$detail")")",
  "last_restart_at": "$(iso_from_epoch "$last_restart_epoch")",
  "last_failure_at": "$(iso_from_epoch "$last_failure_epoch")",
  "last_recovered_at": "$(iso_from_epoch "$last_recovered_epoch")",
  "total_restarts": ${total_restarts},
  "total_failures": ${total_failures},
  "restart_window_count": ${restart_count},
  "restart_window_seconds": ${autoheal_escalate_window_seconds},
  "escalation_threshold": ${autoheal_escalate_after_restarts}
}
EOF
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

restart_cooldown_remaining() {
  service="$1"
  now_epoch="$2"
  last_restart="$(read_int_file "$(service_restart_file "$service")" 0)"
  if [ "$last_restart" -le 0 ]; then
    printf '0\n'
    return 0
  fi
  age=$(( now_epoch - last_restart ))
  remaining=$(( autoheal_cooldown_seconds - age ))
  if [ "$remaining" -lt 0 ]; then
    remaining=0
  fi
  printf '%s\n' "$remaining"
}

external_proof_bundle_count() {
  if [ ! -d "$external_proof_commands_dir" ]; then
    printf '0\n'
    return 0
  fi
  count=0
  for path in "$external_proof_commands_dir"/*-proof-bundle.tgz; do
    [ -f "$path" ] || continue
    case "$path" in
      *-command-pack.tgz) continue ;;
    esac
    if ! external_proof_bundle_has_requests "$path"; then
      continue
    fi
    count=$(( count + 1 ))
  done
  printf '%s\n' "$count"
}

external_proof_bundle_has_requests() {
  path="$1"
  python3 - "$path" <<'PY'
import json
import sys
import tarfile
from pathlib import Path

path = Path(sys.argv[1])
try:
    with tarfile.open(path, "r:gz") as archive:
        for candidate in ("./external-proof-manifest.json", "external-proof-manifest.json"):
            try:
                member = archive.getmember(candidate)
            except KeyError:
                continue
            if not member.isfile():
                continue
            handle = archive.extractfile(member)
            if handle is None:
                continue
            with handle:
                payload = json.load(handle)
            request_count = int((payload or {}).get("request_count") or 0)
            raise SystemExit(0 if request_count > 0 else 1)
except SystemExit as exc:
    raise
except Exception:
    raise SystemExit(0)
raise SystemExit(0)
PY
}

external_proof_bundle_fingerprint() {
  if [ ! -d "$external_proof_commands_dir" ]; then
    printf '\n'
    return 0
  fi
  rows=""
  found=0
  for path in "$external_proof_commands_dir"/*-proof-bundle.tgz; do
    [ -f "$path" ] || continue
    case "$path" in
      *-command-pack.tgz) continue ;;
    esac
    if ! external_proof_bundle_has_requests "$path"; then
      continue
    fi
    found=1
    size="$(wc -c <"$path" | tr -d ' ')"
    mtime="$(date -u -r "$path" +%s 2>/dev/null || stat -c %Y "$path" 2>/dev/null || printf '0')"
    rows="${rows}$(basename "$path")\t${size}\t${mtime}\n"
  done
  if [ "$found" -eq 0 ]; then
    printf '\n'
    return 0
  fi
  printf '%b' "$rows" | LC_ALL=C sort | sha256sum | awk '{print $1}'
}

write_external_proof_status() {
  current_state="$1"
  detail="$2"
  observed_fingerprint="$3"
  observed_bundle_count="$4"
  last_attempt_epoch="$(read_int_file "$external_proof_autoingest_last_attempt_epoch_file" 0)"
  last_success_epoch="$(read_int_file "$external_proof_autoingest_last_success_epoch_file" 0)"
  last_result="$(read_text_file "$external_proof_autoingest_last_result_file" "")"
  cat >"$external_proof_autoingest_status_file" <<EOF
{
  "generated_at": "$(iso_now)",
  "current_state": "$(json_escape "$current_state")",
  "commands_dir": "$(json_escape "$external_proof_commands_dir")",
  "observed_bundle_fingerprint": "$(json_escape "$observed_fingerprint")",
  "observed_bundle_count": ${observed_bundle_count:-0},
  "last_attempt_at": "$(iso_from_epoch "$last_attempt_epoch")",
  "last_success_at": "$(iso_from_epoch "$last_success_epoch")",
  "last_result": "$(json_escape "$last_result")",
  "last_detail": "$(json_escape "$(read_text_file "$external_proof_autoingest_last_detail_file" "$detail")")"
}
EOF
}

recent_external_proof_attempt_within_cooldown() {
  now_epoch="$1"
  last_attempt="$(read_int_file "$external_proof_autoingest_last_attempt_epoch_file" 0)"
  if [ "$last_attempt" -le 0 ]; then
    return 1
  fi
  age=$(( now_epoch - last_attempt ))
  [ "$age" -lt "$external_proof_autoingest_cooldown_seconds" ]
}

external_proof_cooldown_remaining() {
  now_epoch="$1"
  last_attempt="$(read_int_file "$external_proof_autoingest_last_attempt_epoch_file" 0)"
  if [ "$last_attempt" -le 0 ]; then
    printf '0\n'
    return 0
  fi
  age=$(( now_epoch - last_attempt ))
  remaining=$(( external_proof_autoingest_cooldown_seconds - age ))
  if [ "$remaining" -lt 0 ]; then
    remaining=0
  fi
  printf '%s\n' "$remaining"
}

service_health_detail() {
  service="$1"
  detail="$(docker inspect -f '{{if .State.Health}}{{range .State.Health.Log}}{{println .Output}}{{end}}{{else}}{{.State.Status}}{{end}}' "$service" 2>>"$log_file" | tail -n 1 || true)"
  sanitize_text "$detail"
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
  log "starting rebuild for services: $services (refresh_token=rotated)"
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
  observed_status="$2"
  consecutive_failures="$3"
  detail="$4"
  now_epoch="$(date -u +%s)"
  note_restart_attempt "$service" "$now_epoch" >/dev/null
  increment_total_restarts "$service" >/dev/null
  record_service_note "$service" "restart" "starting" "$detail"
  write_service_status "$service" "restarting" "$observed_status" "$consecutive_failures" "$detail" 0
  append_autoheal_event "$service" "restart_started" "$observed_status" "$detail" "$consecutive_failures" 0
  log "autoheal restarting service: $service"
  compose_cmd restart "$service" >>"$log_file" 2>&1 || {
    record_service_note "$service" "restart" "failed" "$detail"
    write_service_status "$service" "restart_failed" "$observed_status" "$consecutive_failures" "$detail" 0
    append_autoheal_event "$service" "restart_failed" "$observed_status" "$detail" "$consecutive_failures" 0
    return 1
  }
  if ! wait_for_service_health "$service" "$autoheal_timeout_seconds"; then
    record_service_note "$service" "restart" "failed" "$detail"
    write_service_status "$service" "restart_failed" "$observed_status" "$consecutive_failures" "$detail" 0
    append_autoheal_event "$service" "restart_failed" "$observed_status" "$detail" "$consecutive_failures" 0
    return 1
  fi
  set_fail_count "$service" 0
  set_restart_epoch "$service" "$now_epoch"
  set_recovered_epoch "$service" "$now_epoch"
  recovered_detail="service recovered after bounded restart"
  record_service_note "$service" "restart" "recovered" "$recovered_detail"
  write_service_status "$service" "recovered" "healthy" 0 "$recovered_detail" 0
  append_autoheal_event "$service" "restart_recovered" "healthy" "$recovered_detail" 0 0
  log "autoheal recovered service: $service"
}

monitor_autoheal() {
  if [ "$autoheal_enabled" != "true" ] && [ "$autoheal_enabled" != "1" ] && [ "$autoheal_enabled" != "yes" ]; then
    return 0
  fi
  now_epoch="$(date -u +%s)"
  for service in $autoheal_services; do
    status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$service" 2>>"$log_file" || true)"
    detail="$(service_health_detail "$service")"
    case "$status" in
      healthy|running)
        set_fail_count "$service" 0
        write_service_status "$service" "healthy" "$status" 0 "$detail" 0
        ;;
      unhealthy|dead|exited)
        count="$(increment_fail_count "$service")"
        increment_total_failures "$service" >/dev/null
        set_failure_epoch "$service" "$now_epoch"
        log "autoheal observed unhealthy service: $service status=$status consecutive_failures=$count"
        record_service_note "$service" "observe" "unhealthy" "$detail"
        append_autoheal_event "$service" "observed_unhealthy" "$status" "$detail" "$count" 0
        if [ "$count" -lt "$autoheal_threshold" ]; then
          write_service_status "$service" "observed_unhealthy" "$status" "$count" "$detail" 0
          continue
        fi
        if recent_restart_within_cooldown "$service" "$now_epoch"; then
          cooldown_remaining="$(restart_cooldown_remaining "$service" "$now_epoch")"
          record_service_note "$service" "cooldown" "waiting" "$detail"
          write_service_status "$service" "cooldown" "$status" "$count" "$detail" "$cooldown_remaining"
          append_autoheal_event "$service" "cooldown_active" "$status" "$detail" "$count" "$cooldown_remaining"
          log "autoheal cooldown active for $service"
          continue
        fi
        current_restart_count="$(restart_window_count "$service" "$now_epoch")"
        if [ "$current_restart_count" -ge "$autoheal_escalate_after_restarts" ]; then
          record_service_note "$service" "escalate" "manual_review_required" "$detail"
          write_service_status "$service" "escalation_required" "$status" "$count" "$detail" 0
          append_autoheal_event "$service" "escalation_required" "$status" "$detail" "$count" 0
          log "autoheal escalation required for $service"
          continue
        fi
        if ! autoheal_service "$service" "$status" "$count" "$detail"; then
          log "autoheal failed for $service"
        fi
        ;;
      *)
        write_service_status "$service" "unknown" "$status" 0 "$detail" 0
        ;;
    esac
  done
}

monitor_external_proof_autoingest() {
  if [ "$external_proof_autoingest_enabled" != "true" ] && [ "$external_proof_autoingest_enabled" != "1" ] && [ "$external_proof_autoingest_enabled" != "yes" ]; then
    write_external_proof_status "disabled" "external proof auto-ingest is disabled" "" 0
    return 0
  fi
  bundle_count="$(external_proof_bundle_count)"
  bundle_fingerprint="$(external_proof_bundle_fingerprint)"
  finalize_script="$external_proof_commands_dir/finalize-external-host-proof.sh"
  if [ ! -d "$external_proof_commands_dir" ]; then
    write_text_file "$external_proof_autoingest_last_result_file" "waiting_for_commands_dir"
    write_text_file "$external_proof_autoingest_last_detail_file" "external proof commands directory is missing"
    write_external_proof_status "waiting_for_commands_dir" "external proof commands directory is missing" "" 0
    return 0
  fi
  if [ "$bundle_count" -le 0 ] || [ -z "$bundle_fingerprint" ]; then
    write_text_file "$external_proof_autoingest_last_result_file" "waiting_for_bundle"
    write_text_file "$external_proof_autoingest_last_detail_file" "waiting for a returned host proof bundle"
    write_external_proof_status "waiting_for_bundle" "waiting for a returned host proof bundle" "$bundle_fingerprint" "$bundle_count"
    return 0
  fi
  last_success_fingerprint="$(read_text_file "$external_proof_autoingest_last_success_fingerprint_file" "")"
  if [ "$bundle_fingerprint" = "$last_success_fingerprint" ]; then
    write_text_file "$external_proof_autoingest_last_result_file" "ingested"
    write_text_file "$external_proof_autoingest_last_detail_file" "host proof bundle already ingested"
    write_external_proof_status "ingested" "host proof bundle already ingested" "$bundle_fingerprint" "$bundle_count"
    return 0
  fi
  now_epoch="$(date -u +%s)"
  last_attempt_fingerprint="$(read_text_file "$external_proof_autoingest_last_attempt_fingerprint_file" "")"
  if [ "$bundle_fingerprint" = "$last_attempt_fingerprint" ] && recent_external_proof_attempt_within_cooldown "$now_epoch"; then
    cooldown_remaining="$(external_proof_cooldown_remaining "$now_epoch")"
    detail="waiting ${cooldown_remaining}s before retrying host proof bundle ingest"
    write_text_file "$external_proof_autoingest_last_result_file" "cooldown"
    write_text_file "$external_proof_autoingest_last_detail_file" "$detail"
    write_external_proof_status "cooldown" "$detail" "$bundle_fingerprint" "$bundle_count"
    return 0
  fi
  if [ ! -x "$finalize_script" ]; then
    write_text_file "$external_proof_autoingest_last_result_file" "blocked"
    write_text_file "$external_proof_autoingest_last_detail_file" "finalize-external-host-proof.sh is missing or not executable"
    write_external_proof_status "blocked" "finalize-external-host-proof.sh is missing or not executable" "$bundle_fingerprint" "$bundle_count"
    return 0
  fi
  write_text_file "$external_proof_autoingest_last_attempt_epoch_file" "$now_epoch"
  write_text_file "$external_proof_autoingest_last_attempt_fingerprint_file" "$bundle_fingerprint"
  write_text_file "$external_proof_autoingest_last_result_file" "ingesting"
  write_text_file "$external_proof_autoingest_last_detail_file" "host proof bundle detected; running finalize-external-host-proof.sh"
  write_external_proof_status "ingesting" "host proof bundle detected; running finalize-external-host-proof.sh" "$bundle_fingerprint" "$bundle_count"
  tmp_output="$external_proof_autoingest_state_dir/last-run.log"
  proof_shell="$(command -v bash 2>/dev/null || true)"
  if [ -z "$proof_shell" ] && [ -x /usr/bin/bash ]; then
    proof_shell="/usr/bin/bash"
  fi
  if [ -z "$proof_shell" ] && [ -x /bin/sh ]; then
    proof_shell="/bin/sh"
  fi
  if [ -z "$proof_shell" ] || [ ! -x "$proof_shell" ]; then
    detail="no shell is available for finalize-external-host-proof.sh"
    write_text_file "$external_proof_autoingest_last_result_file" "failed"
    write_text_file "$external_proof_autoingest_last_detail_file" "$detail"
    write_external_proof_status "failed" "$detail" "$bundle_fingerprint" "$bundle_count"
    log "external proof auto-ingest failed: $detail"
    return 0
  fi
  log "external proof auto-ingest starting"
  if PATH="${PATH:-/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin}" "$proof_shell" "$finalize_script" >"$tmp_output" 2>&1; then
    cat "$tmp_output" >>"$log_file"
    write_text_file "$external_proof_autoingest_last_success_fingerprint_file" "$bundle_fingerprint"
    write_text_file "$external_proof_autoingest_last_success_epoch_file" "$now_epoch"
    write_text_file "$external_proof_autoingest_last_result_file" "ingested"
    write_text_file "$external_proof_autoingest_last_detail_file" "host proof bundle ingested and readiness republished"
    write_external_proof_status "ingested" "host proof bundle ingested and readiness republished" "$bundle_fingerprint" "$bundle_count"
    log "external proof auto-ingest completed"
    return 0
  fi
  cat "$tmp_output" >>"$log_file"
  detail="$(sanitize_text "$(tail -n 5 "$tmp_output" 2>/dev/null || true)")"
  if [ -z "$detail" ]; then
    detail="host proof auto-ingest failed"
  fi
  write_text_file "$external_proof_autoingest_last_result_file" "failed"
  write_text_file "$external_proof_autoingest_last_detail_file" "$detail"
  write_external_proof_status "failed" "$detail" "$bundle_fingerprint" "$bundle_count"
  log "external proof auto-ingest failed: $detail"
  return 0
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
  monitor_external_proof_autoingest
  if [ "$loop_once" = "true" ] || [ "$loop_once" = "1" ] || [ "$loop_once" = "yes" ]; then
    break
  fi
  sleep 30
done
