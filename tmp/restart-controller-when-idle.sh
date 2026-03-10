#!/usr/bin/env bash
set -euo pipefail

ROOT="/docker/fleet"
DB="/docker/fleet/state/fleet.db"
LOG="/tmp/fleet-controller-idle-restart.log"

cd "$ROOT"

while true; do
  active="$(sqlite3 "$DB" "select count(*) from runs where status in ('starting','running','verifying');")"
  if [ "${active:-0}" = "0" ]; then
    {
      date -u +"%Y-%m-%dT%H:%M:%SZ controller restart starting"
      docker compose up -d --build fleet-controller
      sleep 5
      docker exec fleet-admin curl -sS -X POST http://127.0.0.1:8092/api/admin/groups/solo-ea/audit-now >/dev/null || true
      date -u +"%Y-%m-%dT%H:%M:%SZ controller restart finished"
    } >>"$LOG" 2>&1
    exit 0
  fi
  sleep 20
done
