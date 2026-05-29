#!/usr/bin/env python3
from pathlib import Path
import json
import subprocess

SCRIPT = Path("/docker/fleet/scripts/materialize_rafter_pixefy_completion.py")
ARTIFACT = Path("/docker/chummercomplete/_completion/rafter/RAFTER_SECURITY_GOLD_GATE.generated.json")

subprocess.run(["python3", str(SCRIPT)], check=False)
payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
raise SystemExit(0 if payload.get("status") == "pass" else 1)
