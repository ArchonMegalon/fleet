#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="${ROOT}/scripts/codex-shims"
TARGET_USER="${1:-${SUDO_USER:-$(id -un)}}"
TARGET_HOME="$(eval echo "~${TARGET_USER}")"
USER_BIN_DIR="${TARGET_HOME}/bin"
USER_LOCAL_BIN_DIR="${TARGET_HOME}/.local/bin"
PROMPTS_DIR="${TARGET_HOME}/.codex/prompts"
CODEX_HOME_DIR="${TARGET_HOME}/.codex"
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
install_if_writable 0755 "${SOURCE_DIR}/codexaudit" "${USER_LOCAL_BIN_DIR}/codexaudit"
install_if_writable 0755 "${SOURCE_DIR}/codexea-watchdog" "${USER_LOCAL_BIN_DIR}/codexea-watchdog"
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

configure_ea_mcp_server() {
  local codex_cmd="${USER_BIN_DIR}/codex"
  local bridge_script="${ROOT}/scripts/ea_mcp_bridge.py"
  local principal_id="${TARGET_USER}-codex-ea"
  local shell_cmd

  if [ ! -x "${codex_cmd}" ]; then
    return 0
  fi
  if [ ! -f "${bridge_script}" ]; then
    return 0
  fi

  shell_cmd="$(cat <<EOF
set -euo pipefail
export HOME='${TARGET_HOME}'
'${codex_cmd}' mcp remove ea-mcp >/dev/null 2>&1 || true
'${codex_cmd}' mcp add ea-mcp \
  --env EA_MCP_BASE_URL=http://127.0.0.1:8090 \
  --env EA_MCP_API_TOKEN= \
  --env EA_MCP_PRINCIPAL_ID=${principal_id} \
  --env EA_MCP_TIMEOUT_SECONDS=120 \
  --env EA_MCP_MODEL=gemini-2.5-flash \
  -- python3 '${bridge_script}'
EOF
)"

  if [ "$(id -un)" = "${TARGET_USER}" ]; then
    bash -lc "${shell_cmd}"
  else
    su - "${TARGET_USER}" -c "${shell_cmd}"
  fi
}

configure_ea_mcp_server

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

EA MCP server:
  ea-mcp configured for ${TARGET_USER} via ${ROOT}/scripts/ea_mcp_bridge.py

Next shell launch will pick them up automatically.
EOF

if [ "${#SKIPPED_PATHS[@]}" -gt 0 ]; then
  printf '\nSkipped unwritable targets:\n'
  printf '  %s\n' "${SKIPPED_PATHS[@]}"
fi
