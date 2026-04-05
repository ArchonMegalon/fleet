#!/usr/bin/env bash
set -euo pipefail

cd /docker/chummercomplete/chummer6-ui && test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg
cd /docker/chummercomplete/chummer6-ui && test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json
cd /docker/chummercomplete/chummer6-ui && test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-osx-arm64-installer.dmg
cd /docker/chummercomplete/chummer6-ui && test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-blazor-desktop-osx-arm64.receipt.json
