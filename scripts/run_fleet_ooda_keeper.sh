#!/usr/bin/env bash
set -euo pipefail

if [ -f /app/app.py ]; then
  cd /docker/fleet
  exec python3 scripts/fleet_ooda_keeper.py "$@"
fi

exec docker exec fleet-controller python3 /docker/fleet/scripts/fleet_ooda_keeper.py \
  --controller-dir /app \
  --state-root /var/lib/codex-fleet/ooda_keeper \
  --controller-url http://127.0.0.1:8090 \
  "$@"
