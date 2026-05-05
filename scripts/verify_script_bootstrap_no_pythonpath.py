#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS = (
    SCRIPT_DIR / "verify_external_proof_closure.py",
    SCRIPT_DIR / "materialize_external_proof_runbook.py",
    SCRIPT_DIR / "verify_next90_m101_fleet_external_proof_lane.py",
    SCRIPT_DIR / "materialize_journey_gates.py",
    SCRIPT_DIR / "materialize_status_plane.py",
    SCRIPT_DIR / "verify_status_plane_semantics.py",
    SCRIPT_DIR / "materialize_public_progress_report.py",
    SCRIPT_DIR / "materialize_support_case_packets.py",
    SCRIPT_DIR / "materialize_proof_orchestration.py",
    SCRIPT_DIR / "verify_next90_m102_fleet_reporter_receipts.py",
    SCRIPT_DIR / "materialize_next90_m111_fleet_install_aware_followthrough.py",
    SCRIPT_DIR / "verify_next90_m111_fleet_install_aware_followthrough.py",
    SCRIPT_DIR / "materialize_next90_m145_fleet_explain_coverage_gate.py",
    SCRIPT_DIR / "verify_next90_m145_fleet_explain_coverage_gate.py",
    SCRIPT_DIR / "verify_next90_m106_fleet_governor_packet.py",
    SCRIPT_DIR / "materialize_flagship_product_readiness.py",
    SCRIPT_DIR / "chummer_design_supervisor.py",
    SCRIPT_DIR / "materialize_package_compile_overlay.py",
)


def _env_without_pythonpath() -> dict[str, str]:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return env


def _main() -> int:
    failures: list[str] = []
    for script_path in SCRIPTS:
        result = subprocess.run(
            [sys.executable, str(script_path), "--help"],
            check=False,
            capture_output=True,
            text=True,
            env=_env_without_pythonpath(),
        )
        combined = (result.stdout or "") + (result.stderr or "")
        if result.returncode != 0:
            failures.append(f"{script_path}: returncode {result.returncode}")
        elif "No module named" in combined:
            failures.append(f"{script_path}: missing module resolution path in output")

    if failures:
        print("pythonpath bootstrap guard failed:", file=sys.stderr)
        for failure in failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    print("pythonpath bootstrap guard passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
