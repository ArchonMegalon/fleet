#!/usr/bin/env bash
set -euo pipefail

cd /docker/chummercomplete/chummer6-ui && test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe
cd /docker/chummercomplete/chummer6-ui && test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json
cd /docker/chummercomplete/chummer6-ui && test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-win-x64-installer.exe
cd /docker/chummercomplete/chummer6-ui && test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-blazor-desktop-win-x64.receipt.json
