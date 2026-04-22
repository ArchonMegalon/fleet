from __future__ import annotations

import contextlib
import importlib.util
import sqlite3
from pathlib import Path


MODULE_PATH = Path("/docker/fleet/scripts/fleet_ooda_keeper.py")
SPEC = importlib.util.spec_from_file_location("fleet_ooda_keeper", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
keeper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(keeper)


class FakeApp:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    @contextlib.contextmanager
    def db(self):
        yield self._conn


def _seed_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE projects (
            id TEXT PRIMARY KEY,
            status TEXT,
            cooldown_until TEXT,
            last_error TEXT,
            current_slice TEXT
        );
        CREATE TABLE work_packages (
            package_id TEXT PRIMARY KEY,
            project_id TEXT,
            status TEXT,
            runtime_state TEXT,
            dependencies_json TEXT,
            latest_run_id INTEGER
        );
        """
    )
    return conn


def test_ready_project_ids_excludes_active_and_repeat_failure_projects(monkeypatch) -> None:
    conn = _seed_db()
    conn.executemany(
        "INSERT INTO work_packages(package_id, project_id, status, runtime_state, dependencies_json, latest_run_id) VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("design-1", "design", "ready", "idle", "[]", None),
            ("fleet-1", "fleet", "ready", "idle", "[]", None),
            ("media-1", "media-factory", "ready", "idle", "[]", None),
        ],
    )
    app = FakeApp(conn)
    monkeypatch.setattr(keeper, "active_commitment_keys", lambda _app: {"design"})

    result = keeper.ready_project_ids(app, {"fleet": {"project_id": "fleet"}})

    assert result == ["media-factory"]


def test_nudge_ready_projects_stops_when_target_is_already_met(monkeypatch) -> None:
    conn = _seed_db()
    conn.execute(
        "INSERT INTO work_packages(package_id, project_id, status, runtime_state, dependencies_json, latest_run_id) VALUES (?, ?, ?, ?, ?, ?)",
        ("media-1", "media-factory", "ready", "idle", "[]", None),
    )
    app = FakeApp(conn)
    monkeypatch.setattr(keeper, "active_commitment_keys", lambda _app: {"a", "b", "c"})

    result = keeper.nudge_ready_projects(
        app,
        controller_url="http://127.0.0.1:8090",
        repeated_failures={},
        target_active=3,
    )

    assert result == []


def test_anticipate_blockers_reports_capacity_and_head_of_line_failure() -> None:
    conn = _seed_db()
    conn.executemany(
        "INSERT INTO projects(id, status, cooldown_until, last_error, current_slice) VALUES (?, ?, ?, ?, ?)",
        [
            (
                "fleet",
                "awaiting_account",
                "2026-04-22T14:30:00Z",
                "no eligible account/model after auth, pool state, allowlist, or budget filtering (acct-ea-core-01: state=cooldown)",
                "Compile booster-ready work packages from queue truth",
            ),
            (
                "ui-kit",
                "awaiting_review",
                None,
                "",
                "Review shared token and shell chrome boundary split",
            ),
        ],
    )
    conn.executemany(
        "INSERT INTO work_packages(package_id, project_id, status, runtime_state, dependencies_json, latest_run_id) VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("design-0009", "design", "failed", "idle", "[]", 34172),
            ("design-0010", "design", "waiting_dependency", "idle", '["design-0009"]', None),
        ],
    )
    app = FakeApp(conn)

    result = keeper.anticipate_blockers(
        app,
        {"design-0009": {"project_id": "design", "package_id": "design-0009", "signature": "verify failed with exit 1", "count": 4}},
        ready_backlog_after=0,
    )

    kinds = [item["kind"] for item in result]
    assert "queue_starvation" in kinds
    assert "capacity_cooldown" in kinds
    assert "head_of_line_failure" in kinds
    assert "review_gate" in kinds
    assert "repeat_failure" in kinds
