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
state_dir="${CHUMMER6_GUIDE_REFRESH_STATE_DIR:-/docker/fleet/state/chummer6-guide-refresh}"
tasks_log="${CHUMMER6_GUIDE_REFRESH_TASKS_LOG:-/docker/fleet/state/chummer6/TASKS_WORK_LOG.md}"
audit_json="${state_dir}/flagship-audit.json"
max_passes="${CHUMMER6_GUIDE_FLAGSHIP_MAX_PASSES:-3}"
onemin_credit_floor="${CHUMMER6_ONEMIN_MIN_TOTAL_CREDITS:-150000000}"

mkdir -p "${state_dir}"

materialize_audit() {
  python3 /docker/fleet/scripts/materialize_chummer6_flagship_queue.py \
    --tasks-log-out "${tasks_log}" \
    --onemin-credit-floor "${onemin_credit_floor}" \
    --json > "${audit_json}"
}

flagship_audit_open() {
  jq -e '.status == "fail"' "${audit_json}" >/dev/null 2>&1
}

onemin_credit_burn_allowed() {
  jq -e '.onemin_credit_burn_allowed == true' "${audit_json}" >/dev/null 2>&1
}

credit_summary() {
  jq -r '"credits=" + ((.onemin_total_remaining_credits // "unknown") | tostring) + " floor=" + ((.onemin_credit_floor // "unknown") | tostring)' "${audit_json}"
}

run_refresh_pass() {
  if [[ "${CHUMMER6_ALLOW_ONEMIN_REFRESH:-0}" == "1" ]] && onemin_credit_burn_allowed; then
    export CHUMMER6_IMAGE_PROVIDER_ORDER="${CHUMMER6_FLAGSHIP_ONEMIN_PROVIDER_ORDER:-onemin,media_factory,magixai,browseract_prompting_systems,browseract_magixai}"
    export CHUMMER6_ONEMIN_MODEL="${CHUMMER6_FLAGSHIP_ONEMIN_MODEL:-gpt-image-1}"
    export CHUMMER6_ONEMIN_IMAGE_QUALITY="${CHUMMER6_FLAGSHIP_ONEMIN_IMAGE_QUALITY:-high}"
    export CHUMMER6_ONEMIN_IMAGE_STYLE="${CHUMMER6_FLAGSHIP_ONEMIN_IMAGE_STYLE:-vivid}"
    export CHUMMER6_PROVIDER_BUSY_RETRIES="${CHUMMER6_FLAGSHIP_PROVIDER_BUSY_RETRIES:-6}"
    export CHUMMER6_PROVIDER_BUSY_DELAY_SECONDS="${CHUMMER6_FLAGSHIP_PROVIDER_BUSY_DELAY_SECONDS:-5}"
    log "1min flagship burn enabled ($(credit_summary))"
  else
    export CHUMMER6_IMAGE_PROVIDER_ORDER="${CHUMMER6_FLAGSHIP_NON_BURN_PROVIDER_ORDER:-magixai,browseract_magixai,browseract_prompting_systems}"
    export CHUMMER6_ENABLE_ONEMIN_PROVIDER="${CHUMMER6_ENABLE_ONEMIN_PROVIDER:-0}"
    export CHUMMER6_MEDIA_FACTORY_ALLOW_ONEMIN_FALLBACK="${CHUMMER6_MEDIA_FACTORY_ALLOW_ONEMIN_FALLBACK:-0}"
    log "1min flagship burn disabled ($(credit_summary)); using non-burn providers: ${CHUMMER6_IMAGE_PROVIDER_ORDER}"
  fi
  if [[ -n "${model}" ]]; then
    python3 /docker/EA/scripts/chummer6_guide_worker.py --model "${model}"
  else
    python3 /docker/EA/scripts/chummer6_guide_worker.py
  fi
  python3 /docker/EA/scripts/chummer6_guide_media_worker.py render-pack --output-dir "${output_dir}"
  python3 /docker/fleet/scripts/finish_chummer6_guide.py
  python3 /docker/fleet/scripts/normalize_chummer6_flagship_outputs.py
}

log "starting chummer6 guide refresh"
python3 /docker/fleet/scripts/materialize_status_plane.py >/dev/null
materialize_audit
if ! flagship_audit_open; then
  log "guide flagship audit already green"
  log "completed chummer6 guide refresh"
  exit 0
fi

pass_index=1
while [[ "${pass_index}" -le "${max_passes}" ]]; do
  log "guide flagship pass ${pass_index}/${max_passes}"
  run_refresh_pass
  materialize_audit
  if ! flagship_audit_open; then
    log "guide flagship audit closed after ${pass_index} pass(es)"
    break
  fi
  pass_index=$((pass_index + 1))
done

if flagship_audit_open; then
  log "guide flagship audit still open after ${max_passes} pass(es)"
fi
log "completed chummer6 guide refresh"
