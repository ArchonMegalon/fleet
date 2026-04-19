#!/usr/bin/env python3
from __future__ import annotations

import os
import sqlite3
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def _parse_iso(text: str) -> datetime | None:
    normalized = str(text or "").strip()
    if not normalized:
        return None
    try:
        return datetime.fromisoformat(normalized.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _http_health_ok(url: str, timeout_seconds: float) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(url, timeout=max(float(timeout_seconds), 0.1)) as response:
            body = response.read(64).decode("utf-8", errors="ignore").strip().lower()
            return response.status == 200 and body.startswith("ok"), f"http_status={response.status}"
    except Exception as exc:  # pragma: no cover
        return False, f"http_error={exc}"


def _process_age_seconds() -> float | None:
    try:
        proc_uptime = float(Path("/proc/uptime").read_text(encoding="utf-8").split()[0])
        stat_fields = Path("/proc/1/stat").read_text(encoding="utf-8").split()
        start_ticks = float(stat_fields[21])
        hz = float(os.sysconf("SC_CLK_TCK"))
        return max(0.0, proc_uptime - (start_ticks / hz))
    except Exception:  # pragma: no cover
        return None


def _latest_auditor_run_fresh(path: Path, max_age_seconds: int) -> tuple[bool, str]:
    if not path.exists():
        return False, "auditor_db_missing"
    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT status, started_at, finished_at FROM auditor_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
    except sqlite3.OperationalError as exc:  # pragma: no cover
        return False, f"auditor_db_error={exc}"
    except Exception as exc:  # pragma: no cover
        return False, f"auditor_probe_error={exc}"
    finally:
        if conn is not None:
            conn.close()
    if row is None:
        return False, "auditor_run_missing"
    latest_at = _parse_iso(str(row["finished_at"] or row["started_at"] or ""))
    if latest_at is None:
        return False, "auditor_run_timestamp_invalid"
    age_seconds = max(0.0, (datetime.now(timezone.utc) - latest_at).total_seconds())
    if age_seconds > max_age_seconds:
        return False, f"auditor_run_stale={int(age_seconds)}s"
    return True, f"auditor_run_fresh={int(age_seconds)}s"


def main() -> int:
    health_url = str(os.environ.get("FLEET_AUDITOR_HEALTH_URL", "http://127.0.0.1:8093/health") or "").strip()
    db_path = Path(str(os.environ.get("FLEET_AUDITOR_DB_PATH", "/var/lib/codex-fleet/fleet.db") or "").strip())
    timeout_seconds = float(os.environ.get("FLEET_AUDITOR_HEALTH_TIMEOUT_SECONDS", "3") or "3")
    max_age_seconds = int(os.environ.get("FLEET_AUDITOR_RUN_MAX_AGE_SECONDS", "900") or "900")
    startup_grace_seconds = int(os.environ.get("FLEET_AUDITOR_STARTUP_GRACE_SECONDS", "180") or "180")

    http_ok, http_reason = _http_health_ok(health_url, timeout_seconds)
    if not http_ok:
        print(f"unhealthy ({http_reason})", file=sys.stderr)
        return 1

    run_ok, run_reason = _latest_auditor_run_fresh(db_path, max_age_seconds)
    if run_ok:
        print("ok")
        return 0

    process_age = _process_age_seconds()
    if run_reason == "auditor_run_missing" and process_age is not None and process_age <= startup_grace_seconds:
        print(f"ok ({run_reason}; startup_age={int(process_age)}s)")
        return 0

    print(f"unhealthy ({http_reason}; {run_reason})", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
