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

INSTALLED_PATHS=()
SKIPPED_PATHS=()

install_if_writable() {
  local mode="$1"
  local source="$2"
  local target="$3"
  local parent
  parent="$(dirname "${target}")"
  if [ ! -e "${target}" ] && [ ! -w "${parent}" ]; then
    SKIPPED_PATHS+=("${target} (parent not writable)")
    return 0
  fi
  if [ -e "${target}" ] && [ ! -w "${parent}" ]; then
    if [ -w "${target}" ]; then
      cp "${source}" "${target}"
      chmod "${mode}" "${target}"
      INSTALLED_PATHS+=("${target}")
      return 0
    fi
    SKIPPED_PATHS+=("${target} (target not writable)")
    return 0
  fi
  install -m "${mode}" "${source}" "${target}"
  INSTALLED_PATHS+=("${target}")
}

install_if_writable 0755 "${SOURCE_DIR}/codex" "${USER_BIN_DIR}/codex"
install_if_writable 0755 "${SOURCE_DIR}/codexea" "${USER_LOCAL_BIN_DIR}/codexea"
install_if_writable 0755 "${SOURCE_DIR}/codexsurvival" "${USER_LOCAL_BIN_DIR}/codexsurvival"
install_if_writable 0644 "${SOURCE_DIR}/ea_interactive_bootstrap.md" "${PROMPTS_DIR}/ea_interactive_bootstrap.md"
install_if_writable 0644 "${SOURCE_DIR}/ea_survival_bootstrap.md" "${PROMPTS_DIR}/ea_survival_bootstrap.md"

ensure_path_line() {
  local file="$1"
  [ -f "${file}" ] || touch "${file}"
  if ! grep -Fq 'export PATH="$HOME/.local/bin:$HOME/bin:$PATH"' "${file}"; then
    printf '\nexport PATH="$HOME/.local/bin:$HOME/bin:$PATH"\n' >>"${file}"
  fi
}

ensure_path_line "${PROFILE_FILE}"
ensure_path_line "${USER_BASHRC}"

if [ "${#INSTALLED_PATHS[@]}" -gt 0 ]; then
  chown "${TARGET_USER}:${TARGET_USER}" \
    "${INSTALLED_PATHS[@]}" \
    "${PROFILE_FILE}" \
    "${USER_BASHRC}"
else
  chown "${TARGET_USER}:${TARGET_USER}" \
    "${PROFILE_FILE}" \
    "${USER_BASHRC}"
fi

cat <<EOF
Installed Codex shims for ${TARGET_USER}:
$(printf '  %s\n' "${INSTALLED_PATHS[@]}")

Shell PATH ensured in:
  ${PROFILE_FILE}
  ${USER_BASHRC}

Next shell launch will pick them up automatically.
EOF

if [ "${#SKIPPED_PATHS[@]}" -gt 0 ]; then
  printf '\nSkipped unwritable targets:\n'
  printf '  %s\n' "${SKIPPED_PATHS[@]}"
fi
