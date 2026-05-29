#!/bin/sh
set -eu

if ! command -v python3 >/dev/null 2>&1; then echo 'external-proof-python3-missing' >&2; exit 1; fi
if ! command -v curl >/dev/null 2>&1; then echo 'external-proof-curl-missing' >&2; exit 1; fi
if [ -z "${CHUMMER_UI_REPO_ROOT:-}" ] && [ ! -d /docker/chummercomplete/chummer6-ui ] && [ ! -d /docker/chummercomplete/chummer6-ui-finish ] && [ ! -d /docker/chummercomplete/chummer-presentation ]; then echo 'external-proof-ui-repo-root-missing: set CHUMMER_UI_REPO_ROOT if the UI repo is not checked out at /docker/chummercomplete/chummer6-ui, /docker/chummercomplete/chummer6-ui-finish, /docker/chummercomplete/chummer-presentation on the proof host' >&2; exit 1; fi
