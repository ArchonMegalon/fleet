#!/usr/bin/env python3
from pathlib import Path
import json
import subprocess

SCRIPT = Path("/docker/fleet/scripts/materialize_answerly_integration_receipts.py")
subprocess.run(["python3", str(SCRIPT)], check=False)
payload = json.loads(Path("/docker/chummercomplete/_completion/answerly_integration/ANSWERLY_DESIGN_BOUNDARY.generated.json").read_text())
raise SystemExit(0 if payload.get("status") == "pass" else 1)
