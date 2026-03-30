#!/usr/bin/env bash
set -euo pipefail

cd /docker/fleet
exec python3 scripts/chummer_design_supervisor.py loop "$@"
