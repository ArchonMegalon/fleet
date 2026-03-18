#!/usr/bin/env bash
set -euo pipefail

weekday="${CHUMMER6_GUIDE_REFRESH_WEEKDAY_UTC:-0}"
hour="${CHUMMER6_GUIDE_REFRESH_HOUR_UTC:-05}"
minute="${CHUMMER6_GUIDE_REFRESH_MINUTE_UTC:-30}"
state_dir="${CHUMMER6_GUIDE_REFRESH_STATE_DIR:-/docker/fleet/state/chummer6-guide-refresh}"
runner="/docker/fleet/scripts/run_chummer6_guide_refresh.sh"
marker="# CHUMMER6_WEEKLY_GUIDE_REFRESH"

mkdir -p "${state_dir}"

cron_cmd="${runner} >> ${state_dir}/cron.log 2>&1"
cron_line="${minute} ${hour} * * ${weekday} ${cron_cmd} ${marker}"

existing="$(crontab -l 2>/dev/null || true)"
filtered="$(printf '%s\n' "${existing}" | grep -v "${marker}" || true)"

{
  printf 'PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\n'
  if [[ -n "${filtered}" ]]; then
    printf '%s\n' "${filtered}"
  fi
  printf '%s\n' "${cron_line}"
} | crontab -

printf '%s\n' "installed weekly Chummer6 guide refresh: weekday=${weekday} hour=${hour} minute=${minute} UTC"
