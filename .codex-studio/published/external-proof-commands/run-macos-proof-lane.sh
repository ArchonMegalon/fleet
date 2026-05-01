#!/bin/sh
set -eu

cd /docker/fleet/.codex-studio/published/external-proof-commands
./preflight-macos-proof.sh
./capture-macos-proof.sh
./validate-macos-proof.sh
./bundle-macos-proof.sh
