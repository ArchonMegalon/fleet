#!/usr/bin/env bash
set -euo pipefail

status_path="${CODEXEA_INTERNAL_AFFAIRS_STATUS_PATH:-/docker/fleet/state/chummer_design_supervisor/status-live-refresh.materialized.json}"
watch_root="${CODEXEA_INTERNAL_AFFAIRS_WATCH_ROOT:-/tmp/codexea-internal-affairs-watch}"
interval_seconds="${CODEXEA_INTERNAL_AFFAIRS_INTERVAL_SECONDS:-300}"
run_command="${CODEXEA_INTERNAL_AFFAIRS_COMMAND:-}"

mkdir -p "$watch_root"

while true; do
  healthy_enough="$(
    python3 - "$status_path" "$watch_root/last-health.json" <<'PY'
import json
import sys
from pathlib import Path

status_path = Path(sys.argv[1])
health_path = Path(sys.argv[2])
try:
    payload = json.loads(status_path.read_text(encoding="utf-8"))
except Exception:
    payload = {}

active = int(payload.get("active_runs_count") or payload.get("active_run_count") or 0)
productive = int(payload.get("productive_active_runs_count") or 0)
waiting = int(payload.get("waiting_active_runs_count") or 0)
remaining_open = int(payload.get("remaining_open_milestones") or 0)
healthy_enough_for_internal_affairs = (
    active == 0
    or (remaining_open > 0 and productive >= 1 and active == productive)
)
health_path.write_text(
    json.dumps(
        {
            "healthy_enough_for_internal_affairs": healthy_enough_for_internal_affairs,
            "active_runs_count": active,
            "productive_active_runs_count": productive,
            "waiting_active_runs_count": waiting,
            "remaining_open_milestones": remaining_open,
        },
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)
print("1" if healthy_enough_for_internal_affairs else "0")
PY
  )"

  if [[ "${healthy_enough}" != "1" ]]; then
    printf '%s\n' "fleet-health loop still owns active remediation; deferring internal-affairs patch cycle"
    sleep "$interval_seconds"
    continue
  fi

  if [[ -n "$run_command" ]]; then
    bash -lc "$run_command"
  else
    printf '%s\n' "internal-affairs watchdog healthy; no command configured"
  fi

  sleep "$interval_seconds"
done
