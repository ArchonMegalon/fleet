from __future__ import annotations

import importlib.util
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock


MODULE_PATH = Path("/docker/fleet/scripts/healthcheck_auditor.py")


def load_module():
    spec = importlib.util.spec_from_file_location("test_healthcheck_auditor", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HealthcheckAuditorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def _write_db(self, root: str, *, finished_at: datetime | None = None) -> Path:
        db_path = Path(root) / "fleet.db"
        conn = sqlite3.connect(db_path)
        conn.execute(
            """
            CREATE TABLE auditor_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                finding_count INTEGER NOT NULL DEFAULT 0,
                candidate_count INTEGER NOT NULL DEFAULT 0,
                error_message TEXT
            )
            """
        )
        if finished_at is not None:
            started_at = finished_at - timedelta(seconds=30)
            conn.execute(
                """
                INSERT INTO auditor_runs(status, started_at, finished_at, finding_count, candidate_count, error_message)
                VALUES(?, ?, ?, 0, 0, NULL)
                """,
                (
                    "succeeded",
                    started_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    finished_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                ),
            )
        conn.commit()
        conn.close()
        return db_path

    def test_fresh_http_and_recent_auditor_run_are_healthy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = self._write_db(tmpdir, finished_at=datetime.now(timezone.utc))
            env = {
                "FLEET_AUDITOR_DB_PATH": str(db_path),
                "FLEET_AUDITOR_RUN_MAX_AGE_SECONDS": "900",
            }
            with mock.patch.object(self.module, "_http_health_ok", return_value=(True, "http_status=200")):
                with mock.patch.dict(os.environ, env, clear=False):
                    self.assertEqual(self.module.main(), 0)

    def test_missing_run_is_allowed_during_startup_grace(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = self._write_db(tmpdir)
            env = {
                "FLEET_AUDITOR_DB_PATH": str(db_path),
                "FLEET_AUDITOR_STARTUP_GRACE_SECONDS": "180",
            }
            with mock.patch.object(self.module, "_http_health_ok", return_value=(True, "http_status=200")):
                with mock.patch.object(self.module, "_process_age_seconds", return_value=30.0):
                    with mock.patch.dict(os.environ, env, clear=False):
                        self.assertEqual(self.module.main(), 0)

    def test_stale_run_after_startup_grace_is_unhealthy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            stale_finished = datetime.now(timezone.utc) - timedelta(seconds=2000)
            db_path = self._write_db(tmpdir, finished_at=stale_finished)
            env = {
                "FLEET_AUDITOR_DB_PATH": str(db_path),
                "FLEET_AUDITOR_RUN_MAX_AGE_SECONDS": "900",
            }
            with mock.patch.object(self.module, "_http_health_ok", return_value=(True, "http_status=200")):
                with mock.patch.object(self.module, "_process_age_seconds", return_value=600.0):
                    with mock.patch.dict(os.environ, env, clear=False):
                        self.assertEqual(self.module.main(), 1)


if __name__ == "__main__":
    unittest.main()
