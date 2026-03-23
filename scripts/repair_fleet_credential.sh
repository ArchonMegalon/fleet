#!/usr/bin/env bash
set -euo pipefail

FLEET_RUNTIME_ENV_PATH="${FLEET_RUNTIME_ENV_PATH:-/docker/fleet/runtime.env}"
FLEET_OPENAI_REPAIR_ENV_PATHS="${FLEET_OPENAI_REPAIR_ENV_PATHS:-/docker/.env:/docker/fleet/.env:/docker/EA/.env:/docker/chummer5a/.env:/docker/chummer5a/.env.providers}"
FLEET_OPENAI_VALIDATION_URL="${FLEET_OPENAI_VALIDATION_URL:-https://api.openai.com/v1/models}"
FLEET_OPENAI_BROWSERACT_REPAIR_COMMAND="${FLEET_OPENAI_BROWSERACT_REPAIR_COMMAND:-}"
FLEET_CHATGPT_AUTH_REPAIR_COMMAND="${FLEET_CHATGPT_AUTH_REPAIR_COMMAND:-}"

log() {
  printf '%s\n' "$*" >&2
}

extract_target_path_and_key() {
  python3 - <<'PY'
import os
import re

label = str(os.environ.get("FLEET_CREDENTIAL_SOURCE_LABEL") or "").strip()
source_key = str(os.environ.get("FLEET_CREDENTIAL_SOURCE_KEY") or "").strip()
runtime_env = str(os.environ.get("FLEET_RUNTIME_ENV_PATH") or "/docker/fleet/runtime.env").strip()

path = ""
key = ""

match = re.match(r"^local env file (.+)::([A-Za-z0-9_]+)$", label)
if match:
    path = match.group(1).strip()
    key = match.group(2).strip()
else:
    match = re.match(r"^(?:container )?env ([A-Za-z0-9_]+)$", label)
    if match:
        path = runtime_env
        key = match.group(1).strip()
    elif ":env:" in source_key:
        path = runtime_env
        key = source_key.rsplit(":env:", 1)[-1].strip()

print(path)
print(key)
PY
}

read_env_key() {
  local path="$1"
  local key="$2"
  python3 - "$path" "$key" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
key = sys.argv[2]
if not path.exists():
    raise SystemExit(1)
for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    current_key, value = line.split("=", 1)
    if current_key.strip() != key:
        continue
    cleaned = value.strip().strip("'").strip('"')
    if cleaned:
        print(cleaned)
        raise SystemExit(0)
raise SystemExit(1)
PY
}

write_env_key() {
  local path="$1"
  local key="$2"
  local value="$3"
  python3 - "$path" "$key" "$value" <<'PY'
from pathlib import Path
import re
import sys

path = Path(sys.argv[1])
key = sys.argv[2]
value = sys.argv[3]
path.parent.mkdir(parents=True, exist_ok=True)
text = path.read_text(encoding="utf-8") if path.exists() else ""
line = f"{key}={value}"
pattern = re.compile(rf"(?m)^{re.escape(key)}=.*$")
if pattern.search(text):
    text = pattern.sub(line, text, count=1)
else:
    if text and not text.endswith("\n"):
        text += "\n"
    text += line + "\n"
path.write_text(text, encoding="utf-8")
PY
}

validate_openai_key() {
  local candidate="$1"
  local http_code
  local body_file
  body_file="$(mktemp)"
  http_code="$(curl -sS -o "$body_file" -w '%{http_code}' "$FLEET_OPENAI_VALIDATION_URL" -H "Authorization: Bearer $candidate" || true)"
  if [[ "$http_code" == "200" ]]; then
    rm -f "$body_file"
    return 0
  fi
  log "OpenAI key validation failed with HTTP ${http_code:-curl_error}"
  if [[ -s "$body_file" ]]; then
    head -c 400 "$body_file" >&2 || true
    printf '\n' >&2
  fi
  rm -f "$body_file"
  return 1
}

collect_openai_candidates() {
  local target_path="$1"
  local current_key="$2"
  python3 - "$target_path" "$current_key" "$FLEET_OPENAI_REPAIR_ENV_PATHS" <<'PY'
from pathlib import Path
import os
import re
import sys

target_path = str(sys.argv[1] or "").strip()
current_key = str(sys.argv[2] or "").strip()
extra_paths_raw = str(sys.argv[3] or "").strip()

paths = []
if target_path:
    paths.append(Path(target_path))
for raw in re.split(r"[:,;\n\r]+", extra_paths_raw):
    candidate = raw.strip()
    if candidate:
        paths.append(Path(candidate))

seen_paths = set()
ordered_paths = []
for path in paths:
    key = str(path)
    if key in seen_paths:
        continue
    seen_paths.add(key)
    ordered_paths.append(path)

seen_values = set()
for path in ordered_paths:
    if not path.exists():
        continue
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        continue
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        env_key, value = line.split("=", 1)
        clean_key = env_key.strip()
        if not clean_key.startswith("OPENAI_API_KEY"):
            continue
        clean_value = value.strip().strip("'").strip('"')
        if not clean_value:
            continue
        token = clean_value
        if token in seen_values:
            continue
        seen_values.add(token)
        print(f"{path}\t{clean_key}\t{token}")
PY
}

maybe_repair_chatgpt_auth() {
  local label="${FLEET_CREDENTIAL_SOURCE_LABEL:-}"
  if [[ "$label" != auth.json* ]]; then
    return 1
  fi
  local auth_path="${label#auth.json }"
  if [[ -n "$FLEET_CHATGPT_AUTH_REPAIR_COMMAND" ]]; then
    log "Running configured ChatGPT auth repair command for ${auth_path}"
    export FLEET_CHATGPT_AUTH_SOURCE="$auth_path"
    eval "$FLEET_CHATGPT_AUTH_REPAIR_COMMAND"
    return 0
  fi
  if [[ "$auth_path" == "/run/secrets/chatgpt.auth.json" || "$auth_path" == "/docker/fleet/secrets/chatgpt.auth.json" ]]; then
    log "Running default shared ChatGPT auth refresh helper"
    bash /docker/fleet/scripts/refresh_shared_codex_auth.sh
    return 0
  fi
  if [[ "$auth_path" == "/run/secrets/acct-chatgpt-archon.auth.json" || "$auth_path" == "/docker/fleet/secrets/acct-chatgpt-archon.auth.json" ]]; then
    log "Running default Archon auth refresh helper"
    bash /docker/fleet/scripts/refresh_archon_codex_auth.sh
    return 0
  fi
  return 1
}

main() {
  if maybe_repair_chatgpt_auth; then
    log "ChatGPT auth repair command completed"
    return 0
  fi

  local parsed
  mapfile -t parsed < <(extract_target_path_and_key)
  local target_path="${parsed[0]:-}"
  local target_key="${parsed[1]:-}"
  if [[ -z "$target_key" ]]; then
    log "No env-backed credential target could be derived from source label '${FLEET_CREDENTIAL_SOURCE_LABEL:-}'"
    return 1
  fi
  if [[ -z "$target_path" ]]; then
    target_path="$FLEET_RUNTIME_ENV_PATH"
  fi
  if [[ "$target_key" != "OPENAI_API_KEY" ]]; then
    log "No generic repair strategy exists yet for env key ${target_key}"
    return 1
  fi

  local current_value=""
  if current_value="$(read_env_key "$target_path" "$target_key" 2>/dev/null)"; then
    log "Current ${target_key} is present in ${target_path}"
  else
    current_value=""
    log "Current ${target_key} is missing in ${target_path}"
  fi

  local candidate_path
  local candidate_key
  local candidate_value
  while IFS=$'\t' read -r candidate_path candidate_key candidate_value; do
    [[ -n "$candidate_value" ]] || continue
    if [[ "$candidate_value" == "$current_value" ]]; then
      continue
    fi
    log "Validating candidate ${candidate_key} from ${candidate_path}"
    if validate_openai_key "$candidate_value"; then
      write_env_key "$target_path" "$target_key" "$candidate_value"
      log "Promoted ${candidate_key} from ${candidate_path} into ${target_path}:${target_key}"
      return 0
    fi
  done < <(collect_openai_candidates "$target_path" "$target_key")

  if [[ -n "$FLEET_OPENAI_BROWSERACT_REPAIR_COMMAND" ]]; then
    log "Running configured BrowserAct/OpenAI repair command"
    eval "$FLEET_OPENAI_BROWSERACT_REPAIR_COMMAND"
    if current_value="$(read_env_key "$target_path" "$target_key" 2>/dev/null)"; then
      if validate_openai_key "$current_value"; then
        log "BrowserAct/OpenAI repair command restored a valid ${target_key}"
        return 0
      fi
    fi
  fi

  log "No working replacement ${target_key} was found"
  return 1
}

main "$@"
