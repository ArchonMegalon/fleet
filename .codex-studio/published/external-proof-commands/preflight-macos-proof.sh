#!/usr/bin/env bash
set -euo pipefail

if ! command -v python3 >/dev/null 2>&1; then echo 'external-proof-python3-missing' >&2; exit 1; fi
if ! command -v curl >/dev/null 2>&1; then echo 'external-proof-curl-missing' >&2; exit 1; fi
if ! command -v hdiutil >/dev/null 2>&1; then echo 'external-proof-macos-host-missing-hdiutil' >&2; echo 'Hint: run this lane on a macOS host (install xcode tools if needed) rather than Linux.' >&2; exit 1; fi
if [ -z "${CHUMMER_EXTERNAL_PROOF_AUTH_HEADER:-}" ] && [ -z "${CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER:-}" ] && [ -z "${CHUMMER_EXTERNAL_PROOF_COOKIE_JAR:-}" ] && [ "${CHUMMER_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD:-0}" != "1" ]; then echo 'external-proof-auth-missing: set CHUMMER_EXTERNAL_PROOF_AUTH_HEADER, CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER, or CHUMMER_EXTERNAL_PROOF_COOKIE_JAR (or set CHUMMER_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD=1 to bypass)' >&2; exit 1; fi
