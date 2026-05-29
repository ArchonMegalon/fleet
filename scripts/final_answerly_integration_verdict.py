#!/usr/bin/env python3
from pathlib import Path
import subprocess

SCRIPT = Path("/docker/fleet/scripts/materialize_answerly_integration_receipts.py")
result = subprocess.run(["python3", str(SCRIPT)], check=False)
print(Path("/docker/chummercomplete/_completion/answerly_integration/FINAL_ANSWERLY_INTEGRATION_VERDICT.md").read_text())
raise SystemExit(result.returncode)
