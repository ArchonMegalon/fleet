#!/usr/bin/env bash
set -euo pipefail

workspace_root="${OODA_WORKSPACE_ROOT:-/docker/fleet}"
cd "$workspace_root"

state_root="${OODA_MONITOR_STATE_ROOT:-/docker/fleet/state/design_supervisor_ooda}"
supervisor_state_root="${OODA_SUPERVISOR_STATE_ROOT:-${workspace_root}/state/chummer_design_supervisor}"
duration_seconds="${OODA_DURATION_SECONDS:-28800}"
poll_seconds="${OODA_POLL_SECONDS:-300}"
stale_seconds="${OODA_STALE_SECONDS:-900}"
foreground_mode="$(printf '%s' "${OODA_FOREGROUND_MODE:-0}" | tr '[:upper:]' '[:lower:]')"

if [[ ! "$duration_seconds" =~ ^[0-9]+$ ]] || [[ "$duration_seconds" -le 0 ]]; then
  echo "invalid OODA_DURATION_SECONDS: $duration_seconds" >&2
  exit 1
fi
if [[ ! "$poll_seconds" =~ ^[0-9]+$ ]] || [[ "$poll_seconds" -le 0 ]]; then
  echo "invalid OODA_POLL_SECONDS: $poll_seconds" >&2
  exit 1
fi
if [[ ! "$stale_seconds" =~ ^[0-9]+$ ]] || [[ "$stale_seconds" -le 0 ]]; then
  echo "invalid OODA_STALE_SECONDS: $stale_seconds" >&2
  exit 1
fi

duration_label="${OODA_DURATION_LABEL:-}"
if [[ -z "$duration_label" ]]; then
  if (( duration_seconds % 3600 == 0 )); then
    duration_label="$((duration_seconds / 3600))h"
  else
    duration_label="${duration_seconds}s"
  fi
fi

current_alias="${OODA_CURRENT_ALIAS:-current_${duration_label}}"
timestamp="$(date -u +'%Y%m%dT%H%M%SZ')"
monitor_root="${state_root}/overwatch_${timestamp}_${duration_label}"
mkdir -p "$monitor_root"

current_link="${state_root}/${current_alias}"
if [[ -L "$current_link" ]]; then
  old_target="$(readlink -f "$current_link" || true)"
  if [[ -n "$old_target" && -d "$old_target" ]]; then
    while IFS= read -r pid; do
      [[ -n "$pid" ]] || continue
      kill "$pid" 2>/dev/null || true
    done < <(pgrep -f "python3 .*ooda_design_supervisor.py.*--monitor-root ${old_target}" || true)
  fi
fi

ln -sfn "$(basename "$monitor_root")" "$current_link"
ln -sfn "${current_alias}/state.json" "${state_root}/state.json"

if [[ "$foreground_mode" == "1" || "$foreground_mode" == "true" || "$foreground_mode" == "yes" ]]; then
  exec python3 scripts/ooda_design_supervisor.py \
    --workspace-root "$workspace_root" \
    --state-root "$supervisor_state_root" \
    --monitor-root "$monitor_root" \
    --duration-seconds "$duration_seconds" \
    --poll-seconds "$poll_seconds" \
    --stale-seconds "$stale_seconds" \
    "$@"
fi

setsid -f python3 scripts/ooda_design_supervisor.py \
  --workspace-root "$workspace_root" \
  --state-root "$supervisor_state_root" \
  --monitor-root "$monitor_root" \
  --duration-seconds "$duration_seconds" \
  --poll-seconds "$poll_seconds" \
  --stale-seconds "$stale_seconds" \
  "$@" \
  >"$monitor_root/launcher.stdout.log" \
  2>"$monitor_root/launcher.stderr.log" \
  < /dev/null

sleep 1
pid="$(pgrep -n -f "python3 .*ooda_design_supervisor.py.*--monitor-root ${monitor_root}" || true)"
if [[ -z "$pid" ]] || ! kill -0 "$pid" 2>/dev/null; then
  echo "ooda watcher failed to stay up; inspect $monitor_root/launcher.stderr.log" >&2
  exit 1
fi

echo "$pid" >"$monitor_root/ooda.pid"

printf 'pid=%s\nmonitor_root=%s\ncurrent_alias=%s\n' "$pid" "$monitor_root" "$current_alias"
