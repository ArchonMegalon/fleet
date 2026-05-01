#!/bin/sh
set -eu

cd /docker/fleet/.codex-studio/published/external-proof-commands
./preflight-windows-proof.sh
./capture-windows-proof.sh
./validate-windows-proof.sh
./bundle-windows-proof.sh
