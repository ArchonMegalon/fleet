#!/usr/bin/env bash
set -euo pipefail

CODEX_DIR="${HOME}/.codex"
CONFIG="${CODEX_DIR}/config.toml"
RULES="${CODEX_DIR}/rules/default.rules"

mkdir -p "${CODEX_DIR}/rules"
touch "${CONFIG}" "${RULES}"

timestamp="$(date +%Y%m%d%H%M%S)"

backup_if_missing() {
  local source="$1"
  local backup="$2"
  if [ -e "${source}" ] && [ ! -e "${backup}" ]; then
    cp "${source}" "${backup}"
  fi
}

backup_if_missing "${CONFIG}" "${CONFIG}.bak.${timestamp}"
backup_if_missing "${RULES}" "${RULES}.bak.${timestamp}"

ensure_project_trusted() {
  local path="$1"
  local block="[projects.\"${path}\"]"

  if ! grep -Fq "${block}" "${CONFIG}"; then
    printf '\n%s\ntrust_level = "trusted"\n' "${block}" >>"${CONFIG}"
    return
  fi

  python3 - "$CONFIG" "$path" <<'PY'
from pathlib import Path
import sys

config_path = Path(sys.argv[1])
target = sys.argv[2]
block = f'[projects."{target}"]'
lines = config_path.read_text(encoding="utf-8", errors="ignore").splitlines()

out = []
inside = False
saw_trust = False

for line in lines:
    stripped = line.strip()
    if stripped.startswith("[projects.") and stripped == block:
        inside = True
        saw_trust = False
        out.append(line)
        continue
    if inside and stripped.startswith("[") and stripped != block:
        if not saw_trust:
            out.append('trust_level = "trusted"')
        inside = False
    if inside and stripped.startswith("trust_level"):
        out.append('trust_level = "trusted"')
        saw_trust = True
        continue
    out.append(line)

if inside and not saw_trust:
    out.append('trust_level = "trusted"')

config_path.write_text("\n".join(out) + "\n", encoding="utf-8")
PY
}

ensure_rule() {
  local rule="$1"
  grep -Fqx "$rule" "${RULES}" || printf '%s\n' "$rule" >>"${RULES}"
}

ensure_project_trusted "/docker/fleet"
ensure_project_trusted "/docker/EA"
ensure_project_trusted "/docker/chummercomplete/Chummer6"
ensure_project_trusted "/docker"

ensure_rule 'prefix_rule(pattern=["bash", "scripts/deploy.sh"], decision="allow")'
ensure_rule 'prefix_rule(pattern=["bash", "/docker/fleet/scripts/deploy.sh"], decision="allow")'
ensure_rule 'prefix_rule(pattern=["/bin/bash", "-lc", "bash scripts/deploy.sh"], decision="allow")'
ensure_rule 'prefix_rule(pattern=["git", "-C", "/docker/fleet"], decision="allow")'
ensure_rule 'prefix_rule(pattern=["git", "-C", "/docker/EA"], decision="allow")'
ensure_rule 'prefix_rule(pattern=["git", "-C", "/docker/chummercomplete/Chummer6"], decision="allow")'

cat <<EOF
Updated:
  ${CONFIG}
  ${RULES}

This does not fully disable escalation globally.
It makes wrapper-based work much less interactive on this machine.
EOF
