$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

bash -lc 'if ! command -v python3 >/dev/null 2>&1; then echo ''external-proof-python3-missing'' >&2; exit 1; fi'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'if ! command -v curl >/dev/null 2>&1; then echo ''external-proof-curl-missing'' >&2; exit 1; fi'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'if ! command -v powershell.exe >/dev/null 2>&1 && ! command -v pwsh >/dev/null 2>&1; then echo ''external-proof-powershell-missing'' >&2; echo ''Hint: run this lane on a Windows host (Git Bash wrapper is supported for bash commands). '' >&2; exit 1; fi'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
exit 0
