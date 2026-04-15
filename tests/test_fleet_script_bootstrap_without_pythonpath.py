from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = (
    Path("/docker/fleet/scripts/verify_external_proof_closure.py"),
    Path("/docker/fleet/scripts/materialize_external_proof_runbook.py"),
    Path("/docker/fleet/scripts/materialize_journey_gates.py"),
    Path("/docker/fleet/scripts/materialize_status_plane.py"),
    Path("/docker/fleet/scripts/verify_status_plane_semantics.py"),
    Path("/docker/fleet/scripts/materialize_public_progress_report.py"),
    Path("/docker/fleet/scripts/materialize_support_case_packets.py"),
    Path("/docker/fleet/scripts/verify_next90_m102_fleet_reporter_receipts.py"),
    Path("/docker/fleet/scripts/verify_next90_m106_fleet_governor_packet.py"),
    Path("/docker/fleet/scripts/materialize_flagship_product_readiness.py"),
    Path("/docker/fleet/scripts/materialize_proof_orchestration.py"),
    Path("/docker/fleet/scripts/chummer_design_supervisor.py"),
    Path("/docker/fleet/scripts/materialize_package_compile_overlay.py"),
)


def _env_without_pythonpath() -> dict[str, str]:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return env


@pytest.mark.parametrize("script_path", SCRIPTS)
def test_fleet_scripts_launch_help_without_pythonpath(script_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(script_path), "--help"],
        check=False,
        capture_output=True,
        text=True,
        env=_env_without_pythonpath(),
    )

    assert result.returncode == 0
    assert "No module named" not in (result.stderr + result.stdout)
