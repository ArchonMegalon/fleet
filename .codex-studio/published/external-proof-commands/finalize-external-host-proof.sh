#!/bin/sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$SCRIPT_DIR"
BUNDLE_INPUT="${1:-}"
./validate-macos-proof.sh
./ingest-macos-proof-bundle.sh "$BUNDLE_INPUT"
./validate-windows-proof.sh
./ingest-windows-proof-bundle.sh "$BUNDLE_INPUT"
./republish-after-host-proof.sh
