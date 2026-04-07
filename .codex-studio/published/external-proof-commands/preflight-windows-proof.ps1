$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

bash -lc 'if ! command -v python3 >/dev/null 2>&1; then echo ''external-proof-python3-missing'' >&2; exit 1; fi'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'if ! command -v curl >/dev/null 2>&1; then echo ''external-proof-curl-missing'' >&2; exit 1; fi'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'if ! command -v powershell.exe >/dev/null 2>&1 && ! command -v pwsh >/dev/null 2>&1; then echo ''external-proof-powershell-missing'' >&2; echo ''Hint: run this lane on a Windows host (Git Bash wrapper is supported for bash commands). '' >&2; exit 1; fi'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bash -lc 'if [ -z "${CHUMMER_EXTERNAL_PROOF_AUTH_HEADER:-}" ] && [ -z "${CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER:-}" ] && [ -z "${CHUMMER_EXTERNAL_PROOF_COOKIE_JAR:-}" ] && [ "${CHUMMER_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD:-0}" != "1" ]; then echo ''external-proof-auth-missing: set CHUMMER_EXTERNAL_PROOF_AUTH_HEADER, CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER, or CHUMMER_EXTERNAL_PROOF_COOKIE_JAR (or set CHUMMER_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD=1 to bypass)'' >&2; exit 1; fi'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
exit 0
