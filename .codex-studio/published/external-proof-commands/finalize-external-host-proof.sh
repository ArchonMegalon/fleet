#!/usr/bin/env bash
set -euo pipefail

cd /docker/fleet/.codex-studio/published/external-proof-commands
./validate-windows-proof.sh
./ingest-windows-proof-bundle.sh
./republish-after-host-proof.sh
