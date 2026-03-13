#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: bash scripts/launch_codex_no_escalation.sh [--print-cmd] [workdir] [-- codex args...]

Launch a new Codex session with:
  -a never
  -s danger-full-access

Examples:
  bash scripts/launch_codex_no_escalation.sh
  bash scripts/launch_codex_no_escalation.sh /docker/fleet
  bash scripts/launch_codex_no_escalation.sh --print-cmd /docker/fleet
  bash scripts/launch_codex_no_escalation.sh /docker/fleet -- --model gpt-5.4
EOF
}

print_cmd=0
workdir="/docker/fleet"

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
  usage
  exit 0
fi

if [ "${1:-}" = "--print-cmd" ]; then
  print_cmd=1
  shift
fi

if [ "${1:-}" != "" ] && [ "${1:-}" != "--" ]; then
  workdir="$1"
  shift
fi

if [ "${1:-}" = "--" ]; then
  shift
fi

codex_bin="${CODEX_BIN:-codex}"
codex_home_dir="${CODEX_HOME:-${HOME}/.codex}"

resolved_codex="$(command -v "${codex_bin}" || true)"
if [ -z "${resolved_codex}" ]; then
  echo "Missing codex binary on PATH: ${codex_bin}" >&2
  exit 1
fi

if [ ! -d "${workdir}" ]; then
  echo "Missing workdir: ${workdir}" >&2
  exit 1
fi

has_flag() {
  local needle="$1"
  shift
  local arg
  for arg in "$@"; do
    if [ "${arg}" = "${needle}" ]; then
      return 0
    fi
  done
  return 1
}

cmd=(
  env
  "CODEX_HOME=${codex_home_dir}"
  "HOME=${HOME}"
  "${resolved_codex}"
  -C
  "${workdir}"
)

if ! has_flag "-a" "$@" && ! has_flag "--ask-for-approval" "$@" && ! has_flag "--dangerously-bypass-approvals-and-sandbox" "$@"; then
  cmd+=(-a never)
fi

if ! has_flag "-s" "$@" && ! has_flag "--sandbox" "$@" && ! has_flag "--dangerously-bypass-approvals-and-sandbox" "$@"; then
  cmd+=(-s danger-full-access)
fi

if [ "$#" -gt 0 ]; then
  cmd+=("$@")
fi

if [ "${print_cmd}" -eq 1 ]; then
  printf '%q ' "${cmd[@]}"
  printf '\n'
  exit 0
fi

cd "${workdir}"
exec "${cmd[@]}"
