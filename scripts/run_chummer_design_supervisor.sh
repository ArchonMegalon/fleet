#!/usr/bin/env bash
set -euo pipefail

cd /docker/fleet

worker_bin_effective="${CHUMMER_DESIGN_SUPERVISOR_WORKER_BIN:-}"
worker_lane_effective="${CHUMMER_DESIGN_SUPERVISOR_WORKER_LANE:-}"
if [[ -n "$worker_lane_effective" ]] && [[ "${worker_bin_effective##*/}" == "codexea" ]]; then
  case "$worker_lane_effective" in
    core|jury|survival)
      : "${CODEXEA_STREAM_IDLE_TIMEOUT_MS:=${CHUMMER_DESIGN_SUPERVISOR_STREAM_IDLE_TIMEOUT_MS:-900000}}"
      : "${CODEXEA_STREAM_MAX_RETRIES:=${CHUMMER_DESIGN_SUPERVISOR_STREAM_MAX_RETRIES:-8}}"
      export CODEXEA_STREAM_IDLE_TIMEOUT_MS CODEXEA_STREAM_MAX_RETRIES
      ;;
  esac
fi

common_args=()
state_root_base="${CHUMMER_DESIGN_SUPERVISOR_STATE_ROOT:-}"
parallel_shards_raw="${CHUMMER_DESIGN_SUPERVISOR_PARALLEL_SHARDS:-1}"
shard_owner_groups_raw="${CHUMMER_DESIGN_SUPERVISOR_SHARD_OWNER_GROUPS:-}"
clear_lock_on_boot="${CHUMMER_DESIGN_SUPERVISOR_CLEAR_LOCK_ON_BOOT:-0}"

if [[ ! "$parallel_shards_raw" =~ ^[0-9]+$ ]]; then
  parallel_shards_raw=1
fi
parallel_shards=$(( parallel_shards_raw < 1 ? 1 : parallel_shards_raw ))

shard_owner_groups_raw="${shard_owner_groups_raw//$'\n'/;}"
IFS=';' read -r -a shard_owner_groups <<<"$shard_owner_groups_raw"

append_split_flags() {
  local -n dest="$1"
  local flag="$2"
  local raw="${3:-}"
  local item
  raw="${raw//$'\n'/,}"
  raw="${raw//;/,}"
  IFS=',' read -r -a items <<<"$raw"
  for item in "${items[@]}"; do
    item="${item#"${item%%[![:space:]]*}"}"
    item="${item%"${item##*[![:space:]]}"}"
    if [[ -n "$item" ]]; then
      dest+=("$flag" "$item")
    fi
  done
}

build_loop_args() {
  local -n dest="$1"
  local shard_index="$2"
  local shard_group="${3:-}"
  local shard_state_root=""
  dest=("${common_args[@]}")
  if [[ -n "$state_root_base" ]]; then
    shard_state_root="$state_root_base"
    if (( parallel_shards > 1 )); then
      shard_state_root="${state_root_base}/shard-${shard_index}"
      mkdir -p "$shard_state_root"
    fi
    dest+=(--state-root "$shard_state_root")
    if [[ "$clear_lock_on_boot" == "1" ]]; then
      rm -f "$shard_state_root/loop.lock"
    fi
  fi
  if [[ -n "$shard_group" ]]; then
    append_split_flags "$1" --focus-owner "$shard_group"
  fi
}

append_split_flags common_args --account-owner-id "${CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_OWNER_IDS:-}"
append_split_flags common_args --account-alias "${CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_ALIASES:-}"
append_split_flags common_args --focus-profile "${CHUMMER_DESIGN_SUPERVISOR_FOCUS_PROFILE:-}"
append_split_flags common_args --focus-owner "${CHUMMER_DESIGN_SUPERVISOR_FOCUS_OWNER:-}"
append_split_flags common_args --focus-text "${CHUMMER_DESIGN_SUPERVISOR_FOCUS_TEXT:-}"

if (( parallel_shards <= 1 )); then
  args=()
  build_loop_args args 1 "${shard_owner_groups[0]:-}"
  exec python3 scripts/chummer_design_supervisor.py loop "${args[@]}" "$@"
fi

pids=()
cleanup() {
  trap - EXIT TERM INT
  local pid
  for pid in "${pids[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait || true
}
trap cleanup EXIT TERM INT

for ((shard_index = 1; shard_index <= parallel_shards; shard_index++)); do
  shard_args=()
  build_loop_args shard_args "$shard_index" "${shard_owner_groups[$((shard_index - 1))]:-}"
  python3 scripts/chummer_design_supervisor.py loop "${shard_args[@]}" "$@" &
  pids+=("$!")
done

wait -n "${pids[@]}"
status=$?
cleanup
exit "$status"
