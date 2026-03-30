#!/usr/bin/env bash
set -euo pipefail

cd /docker/fleet

args=()

append_split_flags() {
  local flag="$1"
  local raw="${2:-}"
  local item
  raw="${raw//$'\n'/,}"
  raw="${raw//;/,}"
  IFS=',' read -r -a items <<<"$raw"
  for item in "${items[@]}"; do
    item="${item#"${item%%[![:space:]]*}"}"
    item="${item%"${item##*[![:space:]]}"}"
    if [[ -n "$item" ]]; then
      args+=("$flag" "$item")
    fi
  done
}

if [[ -n "${CHUMMER_DESIGN_SUPERVISOR_STATE_ROOT:-}" ]]; then
  args+=(--state-root "${CHUMMER_DESIGN_SUPERVISOR_STATE_ROOT}")
  if [[ "${CHUMMER_DESIGN_SUPERVISOR_CLEAR_LOCK_ON_BOOT:-0}" == "1" ]]; then
    rm -f "${CHUMMER_DESIGN_SUPERVISOR_STATE_ROOT}/loop.lock"
  fi
fi

append_split_flags --account-owner-id "${CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_OWNER_IDS:-}"
append_split_flags --account-alias "${CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_ALIASES:-}"
append_split_flags --focus-profile "${CHUMMER_DESIGN_SUPERVISOR_FOCUS_PROFILE:-}"
append_split_flags --focus-owner "${CHUMMER_DESIGN_SUPERVISOR_FOCUS_OWNER:-}"
append_split_flags --focus-text "${CHUMMER_DESIGN_SUPERVISOR_FOCUS_TEXT:-}"

exec python3 scripts/chummer_design_supervisor.py loop "${args[@]}" "$@"
