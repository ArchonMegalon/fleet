#!/bin/sh
set -eu

cd /docker/fleet/.codex-studio/published/external-proof-commands
./validate-linux-proof.sh
./ingest-linux-proof-bundle.sh
./validate-macos-proof.sh
./ingest-macos-proof-bundle.sh
./validate-windows-proof.sh
./ingest-windows-proof-bundle.sh
./republish-after-host-proof.sh
