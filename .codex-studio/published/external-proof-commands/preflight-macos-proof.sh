#!/usr/bin/env bash
set -euo pipefail

if ! command -v python3 >/dev/null 2>&1; then echo 'external-proof-python3-missing' >&2; exit 1; fi
if ! command -v curl >/dev/null 2>&1; then echo 'external-proof-curl-missing' >&2; exit 1; fi
if ! command -v hdiutil >/dev/null 2>&1; then echo 'external-proof-macos-host-missing-hdiutil' >&2; echo 'Hint: run this lane on a macOS host (install xcode tools if needed) rather than Linux.' >&2; exit 1; fi
