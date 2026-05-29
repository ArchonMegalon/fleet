#!/usr/bin/env python3
from pathlib import Path
import subprocess

SCRIPT = Path("/docker/fleet/scripts/materialize_rafter_pixefy_completion.py")
VERDICT = Path("/docker/chummercomplete/_completion/RAFTER_PIXEFY_QA_STACK_VERDICT.md")

result = subprocess.run(["python3", str(SCRIPT)], check=False)
print(VERDICT.read_text(encoding="utf-8").strip())
raise SystemExit(result.returncode)
