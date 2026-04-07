$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

bash -lc 'cd /docker/fleet/.codex-studio/published/external-proof-commands'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc './preflight-windows-proof.sh'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc './capture-windows-proof.sh'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc './validate-windows-proof.sh'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc './bundle-windows-proof.sh'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
exit 0
