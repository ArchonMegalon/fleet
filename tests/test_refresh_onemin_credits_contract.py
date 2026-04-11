from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path


SCRIPT = Path("/docker/chummercomplete/chummer-presentation/scripts/ai/refresh_onemin_credits.py")


def test_refresh_onemin_credits_updates_history_and_runtime_aggregate(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    runtime_root = tmp_path / "runtime"
    history_path = tmp_path / "onemin_credit_history.csv"
    latest_filename = "onemin_aggregate_latest.json"
    bin_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "sum_free_credits": 123456789,
        "sum_max_credits": 262550000,
        "percent_remaining": 47.02,
        "slot_count": 59,
        "owner_mapped_slot_count": 49,
        "basis_summary": "actual_billing_usage_page x54, observed_error x5",
        "status_basis": "actual_or_observed_or_estimated_else_unknown_unprobed",
        "current_pace_burn_credits_per_hour": 111111.0,
        "avg_daily_burn_credits_7d": 2222222.0,
        "used_precomputed_aggregate": True,
        "slots": [{"free_credits": 123456789, "max_credits": 262550000}],
        "probe": {"slots": [{"estimated_remaining_credits": 123450000, "estimated_credit_basis": "actual_billing_usage_page"}]},
    }
    codexea_path = bin_dir / "codexea"
    codexea_path.write_text(
        "#!/usr/bin/env python3\n"
        "import json\n"
        f"print(json.dumps({payload!r}))\n",
        encoding="utf-8",
    )
    codexea_path.chmod(codexea_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    env["ONEMIN_CREDIT_HISTORY_PATH"] = str(history_path)
    env["ONEMIN_AGGREGATE_RUNTIME_ROOT"] = str(runtime_root)
    env["ONEMIN_AGGREGATE_LATEST_FILENAME"] = latest_filename

    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    body = json.loads(result.stdout)
    assert body["free_credits"] == 123456789
    assert body["history_path"] == str(history_path)
    assert body["aggregate_latest_path"] == str(runtime_root / latest_filename)

    latest_payload = json.loads((runtime_root / latest_filename).read_text(encoding="utf-8"))
    assert latest_payload["sum_free_credits"] == 123456789
    assert latest_payload["refresh_mode"] == "billing_full_refresh"
    assert latest_payload["history_path"] == str(history_path)
    assert latest_payload["recorded_at_utc"] == body["recorded_at_utc"]

    archive_path = Path(body["aggregate_archive_path"])
    assert archive_path.exists()
    assert archive_path.parent == runtime_root
    assert archive_path.name.startswith("onemin_aggregate_billing_full_refresh_")

    history_lines = history_path.read_text(encoding="utf-8").splitlines()
    assert len(history_lines) == 2
    assert "free_credits" in history_lines[0]
    assert "123456789" in history_lines[1]


def test_refresh_onemin_credits_runtime_aggregate_uses_normalized_fallback_totals(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    runtime_root = tmp_path / "runtime"
    history_path = tmp_path / "onemin_credit_history.csv"
    latest_filename = "onemin_aggregate_latest.json"
    bin_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "sum_free_credits": 0,
        "sum_max_credits": 262550000,
        "slot_count": 59,
        "owner_mapped_slot_count": 49,
        "basis_summary": "profiles_fallback x59",
        "status_basis": "profiles_fallback",
        "used_precomputed_aggregate": True,
        "slots": [{"free_credits": None, "max_credits": 262550000}],
        "sum_probe_estimated_credits": 987654,
        "probe": {"slots": [{"estimated_remaining_credits": 987654, "estimated_credit_basis": "profiles_fallback"}]},
    }
    codexea_path = bin_dir / "codexea"
    codexea_path.write_text(
        "#!/usr/bin/env python3\n"
        "import json\n"
        f"print(json.dumps({payload!r}))\n",
        encoding="utf-8",
    )
    codexea_path.chmod(codexea_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    env["ONEMIN_CREDIT_HISTORY_PATH"] = str(history_path)
    env["ONEMIN_AGGREGATE_RUNTIME_ROOT"] = str(runtime_root)
    env["ONEMIN_AGGREGATE_LATEST_FILENAME"] = latest_filename

    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    body = json.loads(result.stdout)
    assert body["free_credits"] == 987654

    latest_payload = json.loads((runtime_root / latest_filename).read_text(encoding="utf-8"))
    assert latest_payload["sum_free_credits"] == 987654
    assert latest_payload["free_credits"] == 987654
    assert latest_payload["total_remaining_credits"] == 987654
    assert latest_payload["remaining_credits"] == 987654
    assert latest_payload["basis_summary"] == "profiles_fallback x59"
