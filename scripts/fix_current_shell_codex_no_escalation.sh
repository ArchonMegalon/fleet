#!/usr/bin/env bash
set -euo pipefail

TARGET_USER="${1:-${SUDO_USER:-${USER:-tibor}}}"
TARGET_HOME="$(eval echo "~${TARGET_USER}")"
INSTALLER="/docker/fleet/scripts/install_codex_no_approval_launch.sh"
WRAPPER="${TARGET_HOME}/bin/codex"
BASHRC="${TARGET_HOME}/.bashrc"

if [ ! -d "${TARGET_HOME}" ]; then
  echo "Target home does not exist: ${TARGET_HOME}" >&2
  exit 1
fi

if [ ! -x "${INSTALLER}" ]; then
  echo "Missing installer: ${INSTALLER}" >&2
  exit 1
fi

bash "${INSTALLER}" "${TARGET_USER}" >/dev/null

if [ ! -x "${WRAPPER}" ]; then
  echo "Missing wrapper after install: ${WRAPPER}" >&2
  exit 1
fi

if [ -n "${BASH_VERSION:-}" ]; then
  export PATH="${TARGET_HOME}/bin:${PATH}"

  codex() {
    "${WRAPPER}" "$@"
  }

  hash -r 2>/dev/null || true

  if [ -n "${TMUX:-}" ] && command -v tmux >/dev/null 2>&1; then
    tmux set-environment -g PATH "${PATH}" || true
  fi
fi

resolved="$(command -v codex || true)"

cat <<EOF
Codex no-escalation defaults refreshed for ${TARGET_USER}.

Wrapper:
  ${WRAPPER}

Resolved codex:
  ${resolved}

Config:
  ${TARGET_HOME}/.codex/config.toml

If you ran this with:
  source /docker/fleet/scripts/fix_current_shell_codex_no_escalation.sh
then the current shell is already refreshed.

If you ran it as a normal script:
  bash /docker/fleet/scripts/fix_current_shell_codex_no_escalation.sh
then start a fresh login shell now:
  exec bash -l

If tmux panes still use stale PATH, restart tmux or open a new tmux session.
EOF
