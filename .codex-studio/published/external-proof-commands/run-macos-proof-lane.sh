#!/bin/sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$SCRIPT_DIR"
if [ -f "$SCRIPT_DIR/proof-host.env" ]; then
  set -a
  . "$SCRIPT_DIR/proof-host.env"
  set +a
fi
./preflight-macos-proof.sh
./capture-macos-proof.sh
./validate-macos-proof.sh
./bundle-macos-proof.sh
if [ "${CHUMMER_EXTERNAL_PROOF_AUTO_FINALIZE:-0}" = "1" ]; then
  if [ -x "$SCRIPT_DIR/finalize-external-host-proof.sh" ] && [ -d /docker/fleet ] && [ -d /docker/chummercomplete ]; then
    "$SCRIPT_DIR/finalize-external-host-proof.sh"
  else
    echo 'external-proof-auto-finalize-blocked: finalize-external-host-proof.sh requires the shared /docker/fleet and /docker/chummercomplete workspace on this host. Either mount the shared workspace or unset CHUMMER_EXTERNAL_PROOF_AUTO_FINALIZE and return the proof bundle for manual ingest.' >&2
    exit 1
  fi
fi
