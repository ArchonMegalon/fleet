#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="${ROOT}/scripts/codex-shims"
TARGET_USER="${1:-${SUDO_USER:-$(id -un)}}"
TARGET_HOME="$(eval echo "~${TARGET_USER}")"
USER_BIN_DIR="${TARGET_HOME}/bin"
USER_LOCAL_BIN_DIR="${TARGET_HOME}/.local/bin"
PROMPTS_DIR="${TARGET_HOME}/.codex/prompts"
PROFILE_FILE="${TARGET_HOME}/.profile"
USER_BASHRC="${TARGET_HOME}/.bashrc"

if [ ! -d "${TARGET_HOME}" ]; then
  echo "Target home does not exist: ${TARGET_HOME}" >&2
  exit 1
fi

mkdir -p "${USER_BIN_DIR}" "${USER_LOCAL_BIN_DIR}" "${PROMPTS_DIR}"

install -m 0755 "${SOURCE_DIR}/codex" "${USER_BIN_DIR}/codex"
install -m 0755 "${SOURCE_DIR}/codexea" "${USER_LOCAL_BIN_DIR}/codexea"
install -m 0644 "${SOURCE_DIR}/ea_interactive_bootstrap.md" "${PROMPTS_DIR}/ea_interactive_bootstrap.md"

ensure_path_line() {
  local file="$1"
  [ -f "${file}" ] || touch "${file}"
  if ! grep -Fq 'export PATH="$HOME/.local/bin:$HOME/bin:$PATH"' "${file}"; then
    printf '\nexport PATH="$HOME/.local/bin:$HOME/bin:$PATH"\n' >>"${file}"
  fi
}

ensure_path_line "${PROFILE_FILE}"
ensure_path_line "${USER_BASHRC}"

chown "${TARGET_USER}:${TARGET_USER}" \
  "${USER_BIN_DIR}/codex" \
  "${USER_LOCAL_BIN_DIR}/codexea" \
  "${PROMPTS_DIR}/ea_interactive_bootstrap.md" \
  "${PROFILE_FILE}" \
  "${USER_BASHRC}"

cat <<EOF
Installed Codex shims for ${TARGET_USER}:
  ${USER_BIN_DIR}/codex
  ${USER_LOCAL_BIN_DIR}/codexea
  ${PROMPTS_DIR}/ea_interactive_bootstrap.md

Shell PATH ensured in:
  ${PROFILE_FILE}
  ${USER_BASHRC}

Next shell launch will pick them up automatically.
EOF
