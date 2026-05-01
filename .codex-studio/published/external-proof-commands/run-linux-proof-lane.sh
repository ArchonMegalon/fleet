#!/bin/sh
set -eu

cd /docker/fleet/.codex-studio/published/external-proof-commands
./preflight-linux-proof.sh
./capture-linux-proof.sh
./validate-linux-proof.sh
./bundle-linux-proof.sh
