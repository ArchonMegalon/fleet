from __future__ import annotations

import contextlib
import importlib.util
import os
import sqlite3
from pathlib import Path


MODULE_PATH = Path("/docker/fleet/scripts/fleet_ooda_keeper.py")
SPEC = importlib.util.spec_from_file_location("fleet_ooda_keeper", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
keeper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(keeper)


class FakeApp:
    def __init__(self, conn: sqlite3.Connection, *, uses_package_scheduler: bool = True) -> None:
        self._conn = conn
        self._uses_package_scheduler = uses_package_scheduler
        self.updated_packages = []
        self.synced = False
        self.reconciled = False
        self.snapshotted = False

    @contextlib.contextmanager
    def db(self):
        yield self._conn

    def project_uses_package_scheduler(self, _config, _project_id: str) -> bool:
        return self._uses_package_scheduler

    def update_work_package_runtime(
        self,
        package_id: str,
        *,
        status: str,
        runtime_state: str,
        latest_run_id: int | None,
        completed_at: object,
    ) -> None:
        self.updated_packages.append(
            {
                "package_id": package_id,
                "status": status,
                "runtime_state": runtime_state,
                "latest_run_id": latest_run_id,
                "completed_at": completed_at,
            }
        )
        self._conn.execute(
            """
            UPDATE work_packages
            SET status=?, runtime_state=?, latest_run_id=?, completed_at=?
            WHERE package_id=?
            """,
            (status, runtime_state, latest_run_id, str(completed_at), package_id),
        )

    def sync_work_packages_to_db(self, _config) -> None:
        self.synced = True

    def reconcile_stuck_work_package_runtime_links(self) -> None:
        self.reconciled = True

    def save_runtime_task_cache_snapshot(self) -> None:
        self.snapshotted = True


def test_set_host_controller_env_defaults_points_host_import_at_state_db(monkeypatch, tmp_path) -> None:
    keys = [
        "FLEET_DB_PATH",
        "FLEET_LOG_DIR",
        "FLEET_QUEUE_RECOVERY_DIR",
        "FLEET_WORKTREE_ROOT",
        "FLEET_CONTROLLER_HEARTBEAT_PATH",
        "FLEET_CODEX_HOME_ROOT",
        "FLEET_GROUP_ROOT",
    ]
    for key in keys:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(keeper, "RUNNING_IN_CONTROLLER_CONTAINER", False)

    keeper.set_host_controller_env_defaults(tmp_path / "controller")

    assert Path(os.environ["FLEET_DB_PATH"]) == tmp_path / "state" / "fleet.db"
    assert Path(os.environ["FLEET_LOG_DIR"]) == tmp_path / "state" / "logs"
    assert Path(os.environ["FLEET_QUEUE_RECOVERY_DIR"]) == tmp_path / "state" / "queue-recovery"
    assert Path(os.environ["FLEET_WORKTREE_ROOT"]) == tmp_path / "state" / "worktrees"
    assert Path(os.environ["FLEET_CONTROLLER_HEARTBEAT_PATH"]) == tmp_path / "state" / "controller-heartbeat.json"
    assert Path(os.environ["FLEET_CODEX_HOME_ROOT"]) == tmp_path / "state" / "codex-homes"
    assert Path(os.environ["FLEET_GROUP_ROOT"]) == tmp_path / "state" / "groups"


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
            latest_run_id INTEGER,
            completed_at TEXT
        );
        CREATE TABLE pull_requests (
            id INTEGER PRIMARY KEY,
            package_id TEXT,
            project_id TEXT,
            pr_number INTEGER,
            review_status TEXT,
            review_findings_count INTEGER,
            review_blocking_findings_count INTEGER,
            review_requested_at TEXT,
            review_completed_at TEXT,
            local_review_last_at TEXT,
            updated_at TEXT
        );
        CREATE TABLE runs (
            id INTEGER PRIMARY KEY,
            status TEXT,
            verify_exit_code INTEGER,
            finished_at TEXT,
            error_message TEXT
        );
        CREATE TABLE review_findings (
            id INTEGER PRIMARY KEY,
            project_id TEXT,
            pr_number INTEGER,
            updated_at TEXT,
            created_at TEXT
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


def test_release_stale_zero_finding_local_reviews_ignores_old_findings_rows() -> None:
    conn = _seed_db()
    conn.execute(
        "INSERT INTO work_packages(package_id, project_id, status, runtime_state, dependencies_json, latest_run_id, completed_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("audit-task-11710", "mobile", "awaiting_review", "awaiting_review", "[]", 34143, None),
    )
    conn.execute(
        """
        INSERT INTO pull_requests(
            id, package_id, project_id, pr_number, review_status,
            review_findings_count, review_blocking_findings_count,
            review_requested_at, review_completed_at, local_review_last_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            1,
            "audit-task-11710",
            "mobile",
            0,
            "local_review",
            0,
            0,
            None,
            None,
            None,
            "2026-04-22T13:27:37Z",
        ),
    )
    conn.execute(
        "INSERT INTO runs(id, status, verify_exit_code, finished_at, error_message) VALUES (?, ?, ?, ?, ?)",
        (34143, "awaiting_review", 0, "2026-04-22T13:27:37Z", None),
    )
    conn.execute(
        "INSERT INTO review_findings(id, project_id, pr_number, updated_at, created_at) VALUES (?, ?, ?, ?, ?)",
        (889, "mobile", 0, "2026-03-14T00:26:02Z", "2026-03-14T00:03:43Z"),
    )
    app = FakeApp(conn)

    released = keeper.release_stale_zero_finding_local_reviews(
        app,
        {},
        stale_minutes=30,
    )

    assert [item["package_id"] for item in released] == ["audit-task-11710"]
    assert app.updated_packages[0]["status"] == "complete"
    assert conn.execute("SELECT COUNT(1) FROM review_findings WHERE project_id='mobile' AND pr_number=0").fetchone()[0] == 0


def test_release_stale_zero_finding_local_reviews_does_not_require_scheduler_flag() -> None:
    conn = _seed_db()
    conn.execute(
        "INSERT INTO work_packages(package_id, project_id, status, runtime_state, dependencies_json, latest_run_id, completed_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("media-factory-0008", "media-factory", "awaiting_review", "awaiting_review", "[]", 34343, None),
    )
    conn.execute(
        """
        INSERT INTO pull_requests(
            id, package_id, project_id, pr_number, review_status,
            review_findings_count, review_blocking_findings_count,
            review_requested_at, review_completed_at, local_review_last_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            1,
            "media-factory-0008",
            "media-factory",
            0,
            "local_review",
            0,
            0,
            None,
            None,
            "2026-04-22T17:36:55Z",
            "2026-04-22T17:36:55Z",
        ),
    )
    conn.execute(
        "INSERT INTO runs(id, status, verify_exit_code, finished_at, error_message) VALUES (?, ?, ?, ?, ?)",
        (34343, "awaiting_review", 0, "2026-04-22T17:36:55Z", None),
    )
    app = FakeApp(conn, uses_package_scheduler=False)

    released = keeper.release_stale_zero_finding_local_reviews(
        app,
        {},
        stale_minutes=30,
    )

    assert [item["package_id"] for item in released] == ["media-factory-0008"]
    assert app.updated_packages[0]["status"] == "complete"
