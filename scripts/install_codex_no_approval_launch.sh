#!/usr/bin/env bash
set -euo pipefail

TARGET_USER="${1:-tibor}"
TARGET_HOME="$(eval echo "~${TARGET_USER}")"
BIN_DIR="${TARGET_HOME}/bin"
BASHRC="${TARGET_HOME}/.bashrc"
PROFILE="${TARGET_HOME}/.profile"
DEPLOY_SCRIPT="${TARGET_HOME}/deploy_chummer.sh"
CODEX_DIR="${TARGET_HOME}/.codex"
CODEX_CONFIG="${CODEX_DIR}/config.toml"
REAL_CODEX="/usr/bin/codex"

if [ ! -d "${TARGET_HOME}" ]; then
  echo "Target home does not exist: ${TARGET_HOME}" >&2
  exit 1
fi

mkdir -p "${BIN_DIR}"
mkdir -p "${CODEX_DIR}"

cat >"${BIN_DIR}/codex" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

REAL_CODEX="/usr/bin/codex"

DEFAULT_FLAGS=(-a never -s danger-full-access)

if [ ! -x "${REAL_CODEX}" ]; then
  echo "Missing real codex binary at ${REAL_CODEX}" >&2
  exit 1
fi

is_known_top_level_command() {
  case "${1:-}" in
    exec|review|login|logout|mcp|mcp-server|app-server|completion|sandbox|debug|apply|resume|fork|cloud|features|help)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

inject_fast_prompt() {
  local -a args=("$@")
  local i=0
  local idx=-1

  while [ "${i}" -lt "${#args[@]}" ]; do
    case "${args[$i]}" in
      --)
        i=$((i + 1))
        if [ "${i}" -lt "${#args[@]}" ]; then
          idx="${i}"
        fi
        break
        ;;
      -c|--config|--enable|--disable|-i|--image|-m|--model|--local-provider|-p|--profile|-s|--sandbox|-a|--ask-for-approval|-C|--cd|--add-dir)
        i=$((i + 2))
        ;;
      --oss|--full-auto|--dangerously-bypass-approvals-and-sandbox|--search|--no-alt-screen|-h|--help|-V|--version)
        i=$((i + 1))
        ;;
      -*)
        printf '%s\0' "${args[@]}"
        return
        ;;
      *)
        idx="${i}"
        break
        ;;
    esac
  done

  if [ "${idx}" -lt 0 ]; then
    args+=("/fast")
    printf '%s\0' "${args[@]}"
    return
  fi

  if is_known_top_level_command "${args[$idx]}"; then
    printf '%s\0' "${args[@]}"
    return
  fi

  args[$idx]=$'/fast\n\n'"${args[$idx]}"
  printf '%s\0' "${args[@]}"
}

mapfile -d '' adjusted_args < <(inject_fast_prompt "$@")
exec "${REAL_CODEX}" "${DEFAULT_FLAGS[@]}" "${adjusted_args[@]}"
EOF

chmod +x "${BIN_DIR}/codex"
chown "${TARGET_USER}:${TARGET_USER}" "${BIN_DIR}/codex"

ensure_path_line() {
  local file="$1"
  [ -f "$file" ] || touch "$file"
  if ! grep -Fq 'export PATH="$HOME/bin:$PATH"' "$file"; then
    printf '\nexport PATH="$HOME/bin:$PATH"\n' >>"$file"
  fi
  chown "${TARGET_USER}:${TARGET_USER}" "$file"
}

ensure_path_line "${BASHRC}"
ensure_path_line "${PROFILE}"

python3 - "${CODEX_CONFIG}" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
if path.exists():
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
else:
    lines = []

desired = {
    "approval_policy": '"never"',
    "sandbox_mode": '"danger-full-access"',
}
found = {key: False for key in desired}
out = []
inserted = False
in_root = True

for line in lines:
    stripped = line.strip()
    if stripped.startswith("["):
        if in_root and not inserted:
            for key, value in desired.items():
                if not found[key]:
                    out.append(f"{key} = {value}")
            if any(not found[key] for key in desired):
                out.append("")
            inserted = True
        in_root = False
        out.append(line)
        continue
    if in_root:
        replaced = False
        for key, value in desired.items():
            if stripped.startswith(f"{key}"):
                out.append(f"{key} = {value}")
                found[key] = True
                replaced = True
                break
        if replaced:
            continue
    out.append(line)

if not inserted:
    for key, value in desired.items():
        if not found[key]:
            out.append(f"{key} = {value}")

text = "\n".join(out).rstrip()
path.write_text((text + "\n") if text else "", encoding="utf-8")
PY
chown "${TARGET_USER}:${TARGET_USER}" "${CODEX_CONFIG}"

if [ -f "${DEPLOY_SCRIPT}" ]; then
  python3 - "${DEPLOY_SCRIPT}" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8", errors="ignore")
targets = {
    'codex --agent-file .agent-memory.md': 'codex -a never -s danger-full-access --agent-file .agent-memory.md',
    'codex -a never -s workspace-write --agent-file .agent-memory.md': 'codex -a never -s danger-full-access --agent-file .agent-memory.md',
    'codex -a never -s read-only --agent-file .agent-memory.md': 'codex -a never -s danger-full-access --agent-file .agent-memory.md',
}
updated = text
for old, new in targets.items():
    updated = updated.replace(old, new)
if updated != text:
    path.write_text(updated, encoding="utf-8")
PY
  chown "${TARGET_USER}:${TARGET_USER}" "${DEPLOY_SCRIPT}"
fi

cat <<EOF
Installed:
  ${BIN_DIR}/codex

Patched PATH in:
  ${BASHRC}
  ${PROFILE}

Patched Codex config:
  ${CODEX_CONFIG}

Patched launcher (if present):
  ${DEPLOY_SCRIPT}

Behavior:
  future shell launches of 'codex' will default to:
    -a never -s danger-full-access
    - inject /fast into normal interactive launches

This disables approval prompts for those launches and gives Codex danger-full-access.
EOF
