#!/usr/bin/env bash
set -euo pipefail

timestamp() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

log() {
  printf "%s %s\n" "$(timestamp)" "$*"
}

output_dir="${CHUMMER6_GUIDE_REFRESH_OUTPUT_DIR:-/docker/fleet/state/chummer6/ea_media_assets}"
model="${CHUMMER6_GUIDE_REFRESH_MODEL:-}"

log "starting chummer6 guide refresh"
if [[ -n "${model}" ]]; then
  python3 /docker/EA/scripts/chummer6_guide_worker.py --model "${model}"
else
  python3 /docker/EA/scripts/chummer6_guide_worker.py
fi
python3 /docker/EA/scripts/chummer6_guide_media_worker.py render-pack --output-dir "${output_dir}"
python3 /docker/fleet/scripts/finish_chummer6_guide.py
log "completed chummer6 guide refresh"
