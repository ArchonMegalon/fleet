#!/bin/sh
set -eu

if ! command -v python3 >/dev/null 2>&1; then echo 'external-proof-python3-missing' >&2; exit 1; fi
if ! command -v curl >/dev/null 2>&1; then echo 'external-proof-curl-missing' >&2; exit 1; fi
if [ -z "${CHUMMER_UI_REPO_ROOT:-}" ] && [ ! -d /docker/chummercomplete/chummer6-ui ]; then echo 'external-proof-ui-repo-root-missing: set CHUMMER_UI_REPO_ROOT to the chummer6-ui checkout root on the proof host' >&2; exit 1; fi
if ! command -v powershell.exe >/dev/null 2>&1 && ! command -v pwsh >/dev/null 2>&1; then echo 'external-proof-powershell-missing' >&2; echo 'Hint: run this lane on a Windows host (Git Bash wrapper is supported for bash commands). ' >&2; exit 1; fi
if ! command -v bash >/dev/null 2>&1; then echo 'external-proof-bash-missing' >&2; echo 'Hint: install Git Bash or run the lane from WSL so the generated shell commands can execute.' >&2; exit 1; fi
