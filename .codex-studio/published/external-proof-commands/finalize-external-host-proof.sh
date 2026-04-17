#!/usr/bin/env bash
set -euo pipefail

cd /docker/fleet/.codex-studio/published/external-proof-commands
./republish-after-host-proof.sh
