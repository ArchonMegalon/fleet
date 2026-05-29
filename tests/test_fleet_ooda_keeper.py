from __future__ import annotations

import contextlib
import importlib.util
import os
import sqlite3
from pathlib import Path

import yaml

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
        self.synced_projects = []

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

    def reconcile_finished_run_links(self) -> int:
        self.reconciled = True
        with self._conn:
            self._conn.execute(
                """
                UPDATE projects
                SET status='dispatch_pending',
                    active_run_id=NULL
                WHERE active_run_id IS NOT NULL
                """
            )
        return 1

    def sync_project_progress_from_packages(self, project_id: str) -> None:
        self.synced_projects.append(project_id)
        with self._conn:
            self._conn.execute(
                """
                UPDATE projects
                SET status='running'
                WHERE id=?
                """,
                (project_id,),
            )

    def project_has_live_runtime_commitment(self, project_id: str, active_run_id: int | None) -> bool:
        row = self._conn.execute(
            """
            SELECT 1
            FROM runtime_tasks
            WHERE project_id=?
              AND task_state IN ('starting', 'scheduled', 'running', 'verifying', 'awaiting_review')
            LIMIT 1
            """,
            (project_id,),
        ).fetchone()
        if row:
            return True
        if not active_run_id:
            return False
        run = self._conn.execute(
            "SELECT status, finished_at FROM runs WHERE id=?",
            (active_run_id,),
        ).fetchone()
        return bool(run and str(run["status"] or "") in keeper.ACTIVE_RUN_STATUSES and not str(run["finished_at"] or ""))


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


def test_default_controller_url_uses_host_dashboard_port_by_default() -> None:
    assert keeper.default_controller_url(running_in_controller_container=False) == "http://127.0.0.1:18090"


def test_default_controller_url_keeps_controller_container_port() -> None:
    assert keeper.default_controller_url(running_in_controller_container=True) == "http://127.0.0.1:8090"


def _seed_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE projects (
            id TEXT PRIMARY KEY,
            status TEXT,
            active_run_id INTEGER,
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
            project_id TEXT,
            package_id TEXT,
            status TEXT,
            started_at TEXT,
            verify_exit_code INTEGER,
            finished_at TEXT,
            error_message TEXT,
            error_class TEXT,
            log_path TEXT,
            final_message_path TEXT
        );
        CREATE TABLE runtime_tasks (
            package_id TEXT,
            project_id TEXT,
            task_kind TEXT,
            task_state TEXT,
            payload_json TEXT,
            run_id INTEGER,
            scheduled_at TEXT,
            started_at TEXT,
            updated_at TEXT
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


def test_prune_stale_runtime_commitments_clears_terminal_rows_without_waiting(tmp_path) -> None:
    db_path = tmp_path / "state" / "fleet.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE projects (
            id TEXT PRIMARY KEY,
            status TEXT,
            active_run_id INTEGER,
            updated_at TEXT,
            last_error TEXT
        );
        CREATE TABLE runs (
            id INTEGER PRIMARY KEY,
            project_id TEXT,
            package_id TEXT,
            status TEXT,
            started_at TEXT,
            finished_at TEXT,
            error_class TEXT,
            error_message TEXT,
            log_path TEXT,
            final_message_path TEXT
        );
        CREATE TABLE runtime_tasks (
            package_id TEXT,
            project_id TEXT,
            task_kind TEXT,
            task_state TEXT,
            payload_json TEXT,
            run_id INTEGER,
            scheduled_at TEXT,
            started_at TEXT,
            updated_at TEXT
        );
        """
    )
    now = keeper.iso_now()
    finished = keeper.iso(keeper.utc_now() - keeper.dt.timedelta(minutes=2))
    conn.execute(
        "INSERT INTO projects(id, status, active_run_id, updated_at, last_error) VALUES ('core', 'dispatch_pending', 41, ?, '')",
        (now,),
    )
    conn.execute(
        """
        INSERT INTO runs(id, project_id, package_id, status, started_at, finished_at, error_class, error_message, log_path, final_message_path)
        VALUES (41, 'core', '', 'abandoned', ?, ?, '', 'runtime task cancelled', '', '')
        """,
        (finished, finished),
    )
    conn.execute(
        """
        INSERT INTO runtime_tasks(package_id, project_id, task_kind, task_state, payload_json, run_id, scheduled_at, started_at, updated_at)
        VALUES ('', 'core', 'coding', 'running', '{}', 41, ?, ?, ?)
        """,
        (finished, finished, now),
    )
    conn.commit()
    conn.close()

    cleared = keeper.prune_stale_runtime_commitments(tmp_path, stale_hours=6)

    assert cleared == 1
    conn = sqlite3.connect(str(db_path))
    row = conn.execute("SELECT COUNT(*) FROM runtime_tasks").fetchone()
    project = conn.execute("SELECT active_run_id FROM projects WHERE id='core'").fetchone()
    conn.close()
    assert row[0] == 0
    assert project[0] is None


def test_autoheal_queue_scope_drift_narrows_live_queue_and_scope_claims(tmp_path, monkeypatch) -> None:
    fleet_queue = tmp_path / ".codex-studio" / "published" / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    design_queue = tmp_path / "design" / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    fleet_queue.parent.mkdir(parents=True, exist_ok=True)
    design_queue.parent.mkdir(parents=True, exist_ok=True)
    fleet_queue.write_text(
        yaml.safe_dump(
            {
                "items": [
                    {
                        "package_id": "next90-m146-ui-kit-package-release-truth",
                        "repo": "chummer6-ui-kit",
                        "allowed_paths": ["src", "tests", "scripts", ".codex-studio"],
                        "owned_surfaces": [
                            "ui_kit_package_release_truth:ui_kit",
                            "downstream_consumption_proof:ui_kit",
                        ],
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    design_queue.write_text(
        yaml.safe_dump(
            {
                "items": [
                    {
                        "package_id": "next90-m146-ui-kit-package-release-truth",
                        "repo": "chummer6-ui-kit",
                        "allowed_paths": [".codex-studio", "feedback"],
                        "owned_surfaces": [
                            "ui_kit_package_release_truth:ui_kit",
                            "downstream_consumption_proof:ui_kit",
                        ],
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE projects (
            id TEXT PRIMARY KEY,
            status TEXT,
            active_run_id INTEGER
        );
        CREATE TABLE work_packages (
            package_id TEXT PRIMARY KEY,
            project_id TEXT,
            task_meta_json TEXT,
            allowed_paths_json TEXT
        );
        CREATE TABLE scope_claims (
            package_id TEXT,
            project_id TEXT,
            claim_type TEXT,
            claim_value TEXT,
            scope_key TEXT,
            claim_state TEXT,
            created_at TEXT,
            activated_at TEXT,
            released_at TEXT,
            UNIQUE(package_id, claim_type, claim_value)
        );
        """
    )
    conn.execute("INSERT INTO projects(id, status, active_run_id) VALUES ('ui-kit', 'dispatch_pending', NULL)")
    conn.execute(
        """
        INSERT INTO work_packages(package_id, project_id, task_meta_json, allowed_paths_json)
        VALUES (?, 'ui-kit', ?, ?)
        """,
        (
            "next90-m146-ui-kit-package-release-truth",
            '{"allowed_paths":["src","tests","scripts",".codex-studio"]}',
            '["src","tests","scripts",".codex-studio"]',
        ),
    )
    for value in ("src", "tests", "scripts", ".codex-studio"):
        conn.execute(
            """
            INSERT INTO scope_claims(package_id, project_id, claim_type, claim_value, scope_key, claim_state, created_at, activated_at, released_at)
            VALUES ('next90-m146-ui-kit-package-release-truth', 'ui-kit', 'path', ?, ?, 'active', '', '', NULL)
            """,
            (value, f"path:{value}"),
        )
    app = FakeApp(conn)
    monkeypatch.setattr(keeper, "http_post_json", lambda _url, _payload=None: {"ok": True})

    actions = keeper.autoheal_queue_scope_drift(
        app,
        workspace_root=tmp_path,
        controller_url="http://127.0.0.1:18090",
        fleet_queue_path=fleet_queue,
        design_queue_path=design_queue,
    )

    assert len(actions) == 1
    assert actions[0]["package_id"] == "next90-m146-ui-kit-package-release-truth"
    queue_payload = yaml.safe_load(fleet_queue.read_text(encoding="utf-8"))
    assert queue_payload["items"][0]["allowed_paths"] == [".codex-studio", "feedback"]
    package_row = conn.execute(
        "SELECT allowed_paths_json FROM work_packages WHERE package_id='next90-m146-ui-kit-package-release-truth'"
    ).fetchone()
    assert package_row[0] == '[".codex-studio", "feedback"]'
    active_claims = [
        row[0]
        for row in conn.execute(
            """
            SELECT claim_value
            FROM scope_claims
            WHERE package_id='next90-m146-ui-kit-package-release-truth'
              AND claim_type='path'
              AND claim_state='active'
            ORDER BY claim_value
            """
        ).fetchall()
    ]
    assert active_claims == [".codex-studio", "feedback"]


def test_autoheal_projection_drift_clears_stale_active_project_links() -> None:
    conn = _seed_db()
    now = keeper.iso_now()
    conn.execute(
        """
        INSERT INTO projects(id, status, cooldown_until, last_error, current_slice)
        VALUES ('core', 'running', NULL, '', 'slice')
        """
    )
    conn.execute(
        """
        INSERT INTO runs(id, project_id, package_id, status, started_at, verify_exit_code, finished_at, error_message, error_class, log_path, final_message_path)
        VALUES (34126, 'core', '', 'awaiting_review', ?, NULL, ?, '', '', '', '')
        """,
        (now, now),
    )
    conn.execute("UPDATE projects SET active_run_id=34126 WHERE id='core'")
    app = FakeApp(conn)

    actions = keeper.autoheal_projection_drift(app)

    row = conn.execute("SELECT status, active_run_id FROM projects WHERE id='core'").fetchone()
    assert any(action["trigger"] == "projection_drift_stale_active" for action in actions)
    assert app.reconciled is True
    assert app.snapshotted is True
    assert str(row["status"]) == "dispatch_pending"
    assert row["active_run_id"] is None


def test_autoheal_projection_drift_resyncs_stale_inactive_project_rows() -> None:
    conn = _seed_db()
    now = keeper.iso_now()
    conn.execute(
        """
        INSERT INTO projects(id, status, cooldown_until, last_error, current_slice)
        VALUES ('ui-kit', 'waiting_capacity', NULL, '', 'slice')
        """
    )
    conn.execute(
        """
        INSERT INTO runs(id, project_id, package_id, status, started_at, verify_exit_code, finished_at, error_message, error_class, log_path, final_message_path)
        VALUES (537, 'ui-kit', 'pkg-ui-kit', 'running', ?, NULL, NULL, '', '', '', '')
        """,
        (now,),
    )
    conn.execute("UPDATE projects SET active_run_id=537 WHERE id='ui-kit'")
    conn.execute(
        """
        INSERT INTO runtime_tasks(package_id, project_id, task_kind, task_state, payload_json, run_id, scheduled_at, started_at, updated_at)
        VALUES('pkg-ui-kit', 'ui-kit', 'coding', 'running', '{}', 537, ?, ?, ?)
        """,
        (now, now, now),
    )
    app = FakeApp(conn)

    actions = keeper.autoheal_projection_drift(app)

    row = conn.execute("SELECT status FROM projects WHERE id='ui-kit'").fetchone()
    assert any(action["trigger"] == "projection_drift_stale_inactive" for action in actions)
    assert app.synced_projects == ["ui-kit"]
    assert app.snapshotted is True
    assert str(row["status"]) == "running"


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


def test_auto_retry_transient_dispatch_pending_projects_retries_stale_worker_rows(monkeypatch) -> None:
    conn = _seed_db()
    conn.executemany(
        "INSERT INTO projects(id, status, cooldown_until, last_error, current_slice) VALUES (?, ?, ?, ?, ?)",
        [
            (
                "core",
                "dispatch_pending",
                None,
                "worker session went stale after 2177s without heartbeat or log activity",
                "Core slice",
            ),
            (
                "design",
                "dispatch_pending",
                None,
                "verify failed with exit 1",
                "Design slice",
            ),
            (
                "fleet",
                "running",
                None,
                "worker session went stale after 10s without heartbeat or log activity",
                "Fleet slice",
            ),
        ],
    )
    app = FakeApp(conn)
    retried: list[str] = []

    def _fake_post(url: str, _payload=None):
        retried.append(url.rsplit("/", 2)[-2])
        return {"ok": True}

    monkeypatch.setattr(keeper, "http_post_json", _fake_post)
    monkeypatch.setattr(keeper, "active_commitment_keys", lambda _app: {"fleet"})

    result = keeper.auto_retry_transient_dispatch_pending_projects(
        app,
        controller_url="http://127.0.0.1:18090",
        repeated_failures={},
    )

    assert retried == ["core"]
    assert len(result) == 1
    assert result[0]["project_id"] == "core"
    assert result[0]["action"] == "retry_transient_dispatch_pending"


def test_auto_retry_transient_dispatch_pending_projects_respects_cooldown_and_non_transient_repeat_failure(monkeypatch) -> None:
    conn = _seed_db()
    conn.executemany(
        "INSERT INTO projects(id, status, cooldown_until, last_error, current_slice) VALUES (?, ?, ?, ?, ?)",
        [
            (
                "media-factory",
                "dispatch_pending",
                "2999-01-01T00:00:00Z",
                "worker session went stale after 2201s without heartbeat or log activity",
                "Media slice",
            ),
            (
                "ui",
                "dispatch_pending",
                None,
                "worker session went stale after 2200s without heartbeat or log activity",
                "UI slice",
            ),
        ],
    )
    app = FakeApp(conn)
    monkeypatch.setattr(keeper, "http_post_json", lambda *_args, **_kwargs: {"ok": True})

    result = keeper.auto_retry_transient_dispatch_pending_projects(
        app,
        controller_url="http://127.0.0.1:18090",
        repeated_failures={
            "ui": {
                "project_id": "ui",
                "signature": "verify failed with exit 1",
                "count": 5,
            }
        },
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


def test_anticipate_blockers_ignores_failed_head_package_once_it_is_rerunning() -> None:
    conn = _seed_db()
    conn.execute(
        "INSERT INTO projects(id, status, cooldown_until, last_error, current_slice) VALUES (?, ?, ?, ?, ?)",
        ("ui-kit", "running", None, "", "Regenerate package release truth"),
    )
    conn.executemany(
        "INSERT INTO work_packages(package_id, project_id, status, runtime_state, dependencies_json, latest_run_id) VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("ui-kit-0001", "ui-kit", "failed", "idle", "[]", 48731),
            ("ui-kit-0002", "ui-kit", "waiting_dependency", "idle", '[\"ui-kit-0001\"]', None),
        ],
    )
    conn.execute(
        """
        INSERT INTO runtime_tasks(package_id, project_id, task_kind, task_state, payload_json, run_id, scheduled_at, started_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "ui-kit-0001",
            "ui-kit",
            "coding",
            "running",
            "{}",
            48751,
            "2026-05-22T18:38:20Z",
            "2026-05-22T18:38:20Z",
            "2026-05-22T18:38:20Z",
        ),
    )
    app = FakeApp(conn)

    result = keeper.anticipate_blockers(app, {}, ready_backlog_after=3)

    kinds = [item["kind"] for item in result]
    assert "head_of_line_failure" not in kinds


def test_anticipate_blockers_ignores_repeat_failure_once_package_is_rerunning() -> None:
    conn = _seed_db()
    conn.execute(
        "INSERT INTO projects(id, status, cooldown_until, last_error, current_slice) VALUES (?, ?, ?, ?, ?)",
        ("design", "running", None, "", "Canonical release truth"),
    )
    conn.execute(
        """
        INSERT INTO runtime_tasks(package_id, project_id, task_kind, task_state, payload_json, run_id, scheduled_at, started_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "next90-m146-design-canonical-release-truth-recovery",
            "design",
            "coding",
            "running",
            "{}",
            48850,
            "2026-05-22T20:22:34Z",
            "2026-05-22T20:22:34Z",
            "2026-05-22T20:22:34Z",
        ),
    )
    app = FakeApp(conn)

    result = keeper.anticipate_blockers(
        app,
        {
            "next90-m146-design-canonical-release-truth-recovery": {
                "project_id": "design",
                "package_id": "next90-m146-design-canonical-release-truth-recovery",
                "signature": "provider_unavailable:backend unavailable: tool_shim_planner_timeout:74s",
                "count": 10,
            }
        },
        ready_backlog_after=3,
    )

    kinds = [item["kind"] for item in result]
    assert "repeat_failure" not in kinds


def test_repeated_failure_map_ignores_package_once_it_is_verifying_again() -> None:
    conn = _seed_db()
    conn.execute("ALTER TABLE projects ADD COLUMN consecutive_failures INTEGER DEFAULT 0")
    conn.execute(
        "INSERT INTO projects(id, status, cooldown_until, last_error, current_slice) VALUES (?, ?, ?, ?, ?)",
        ("hub-registry", "running", None, "", "Registry release truth"),
    )
    conn.executemany(
        """
        INSERT INTO runs(project_id, package_id, status, error_class, error_message, finished_at, final_message_path)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                "hub-registry",
                "next90-m146-registry-release-channel-truth-recovery",
                "rejected",
                "provider_unavailable",
                "backend unavailable: tool_shim_planner_timeout:74s",
                "2026-05-22T18:00:00Z",
                "",
            ),
            (
                "hub-registry",
                "next90-m146-registry-release-channel-truth-recovery",
                "rejected",
                "provider_unavailable",
                "backend unavailable: tool_shim_planner_timeout:74s",
                "2026-05-22T18:05:00Z",
                "",
            ),
            (
                "hub-registry",
                "next90-m146-registry-release-channel-truth-recovery",
                "rejected",
                "provider_unavailable",
                "backend unavailable: tool_shim_planner_timeout:74s",
                "2026-05-22T18:10:00Z",
                "",
            ),
        ],
    )
    conn.execute(
        """
        INSERT INTO runtime_tasks(package_id, project_id, task_kind, task_state, payload_json, run_id, scheduled_at, started_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "next90-m146-registry-release-channel-truth-recovery",
            "hub-registry",
            "coding",
            "verifying",
            "{}",
            48810,
            "2026-05-22T18:12:00Z",
            "2026-05-22T18:12:00Z",
            "2026-05-22T18:12:00Z",
        ),
    )
    app = FakeApp(conn)

    result = keeper.repeated_failure_map(app, lookback_minutes=240, threshold=3)

    assert result == {}


def test_active_commitment_keys_include_verifying_runtime_tasks() -> None:
    conn = _seed_db()
    conn.execute(
        "INSERT INTO projects(id, status, cooldown_until, last_error, current_slice) VALUES (?, ?, ?, ?, ?)",
        ("fleet", "verifying", None, "", "Release recovery"),
    )
    conn.execute(
        """
        INSERT INTO runtime_tasks(package_id, project_id, task_kind, task_state, payload_json, run_id, scheduled_at, started_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "next90-m146-fleet-release-recovery-gate-stack",
            "fleet",
            "coding",
            "verifying",
            "{}",
            48833,
            "2026-05-22T20:05:00Z",
            "2026-05-22T20:05:00Z",
            "2026-05-22T20:05:00Z",
        ),
    )
    app = FakeApp(conn)

    keys = keeper.active_commitment_keys(app)

    assert "next90-m146-fleet-release-recovery-gate-stack" in keys
    assert "fleet" not in keeper.ready_project_ids(app, {})


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


def test_persist_planned_launch_rejects_missing_lane_capacity_state() -> None:
    class FakePersistApp:
        def runtime_task_row(self, _runtime_key: str):
            return None

        def coding_runtime_task_payload(self, _planned):
            raise AssertionError("payload generation should not run for missing lane capacity")

        def upsert_runtime_task(self, *args, **kwargs):
            raise AssertionError("runtime task should not be persisted for missing lane capacity")

        def activate_work_package_scope_claims(self, _package_id: str) -> None:
            raise AssertionError("scope claims should not activate for missing lane capacity")

        def update_work_package_runtime(self, *args, **kwargs) -> None:
            raise AssertionError("package runtime should not update for missing lane capacity")

        def save_runtime_task_cache_snapshot(self) -> None:
            raise AssertionError("snapshot should not save for missing lane capacity")

        def utc_now(self) -> str:
            return "2026-05-19T13:37:59Z"

    class Candidate:
        package_id = "design"

    class Planned:
        project_id = "design"
        package_id = "design"
        candidate = Candidate()
        decision = {"lane_capacity": {"capacity_summary": {"state": "missing"}}}

    assert keeper.persist_planned_launch(FakePersistApp(), Planned()) is False
