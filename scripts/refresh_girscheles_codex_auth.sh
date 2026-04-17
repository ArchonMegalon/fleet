#!/usr/bin/env bash
set -euo pipefail

SRC_AUTH="${1:-${HOME}/.codex/auth.json}"
DEST_AUTH="/docker/fleet/secrets/acct-chatgpt-b.auth.json"
KEEP_BACKUPS="${KEEP_BACKUPS:-4}"

if [[ ! -f "${SRC_AUTH}" ]]; then
  echo "Missing Codex auth source: ${SRC_AUTH}" >&2
  exit 1
fi

python3 - "${SRC_AUTH}" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text())
required = {"auth_mode", "tokens"}
missing = sorted(required - set(data))
if missing:
    raise SystemExit(f"Auth file {path} is missing keys: {', '.join(missing)}")
PY

mkdir -p "$(dirname "${DEST_AUTH}")"
if [[ -f "${DEST_AUTH}" ]]; then
  cp "${DEST_AUTH}" "${DEST_AUTH}.bak.$(date -u +%Y%m%dT%H%M%SZ)"
fi
install -m 600 "${SRC_AUTH}" "${DEST_AUTH}"
python3 - "${DEST_AUTH}" "${KEEP_BACKUPS}" <<'PY'
from pathlib import Path
import sys

dest = Path(sys.argv[1])
keep = max(0, int(sys.argv[2]))
backups = sorted(dest.parent.glob(dest.name + ".bak.*"), key=lambda item: item.stat().st_mtime, reverse=True)
for stale in backups[keep:]:
    stale.unlink(missing_ok=True)
PY
echo "the.girscheles auth refreshed at ${DEST_AUTH}"
echo "Fleet controller will ingest it on the next scheduler loop."
