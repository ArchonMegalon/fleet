from __future__ import annotations

import contextlib
import datetime as dt
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Iterator


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "fleet_retention_janitor.py"
SPEC = importlib.util.spec_from_file_location("fleet_retention_janitor_under_test", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
janitor = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = janitor
SPEC.loader.exec_module(janitor)


NOW = dt.datetime(2026, 8, 23, 12, 0, tzinfo=dt.timezone.utc)
OLD = "2026-08-20T12:00:00Z"


class FakeApp:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    @contextlib.contextmanager
    def db(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return result.stdout.strip()


def write_old(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    timestamp = (NOW - dt.timedelta(days=3)).timestamp()
    os.utime(path, (timestamp, timestamp))


def seed_runtime(tmp_path: Path, *, worktree_name: str = "pkg-1") -> dict[str, object]:
    workspace = tmp_path / "fleet"
    project = workspace / "repos" / "project"
    remote = workspace / "remotes" / "project.git"
    worktree_root = workspace / "state" / "worktrees"
    worktree = worktree_root / "project" / worktree_name
    log_root = workspace / "state" / "logs"
    state_root = workspace / "state" / "keeper"
    project.mkdir(parents=True)
    remote.parent.mkdir(parents=True)
    git(project, "init", "--initial-branch=main")
    git(project, "config", "user.name", "Fleet Test")
    git(project, "config", "user.email", "fleet@example.invalid")
    (project / "tracked.txt").write_text("landed\n", encoding="utf-8")
    git(project, "add", "tracked.txt")
    git(project, "commit", "-m", "landed")
    subprocess.run(
        ["git", "init", "--bare", "--initial-branch=main", str(remote)],
        text=True,
        capture_output=True,
        check=True,
    )
    git(project, "remote", "add", "origin", str(remote))
    git(project, "push", "-u", "origin", "main")
    landed_sha = git(project, "rev-parse", "HEAD")
    worktree.parent.mkdir(parents=True)
    git(project, "worktree", "add", "-b", "fleet/pkg-1", str(worktree), landed_sha)

    db_path = workspace / "state" / "fleet.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE projects (
            id TEXT PRIMARY KEY,
            path TEXT NOT NULL,
            status TEXT,
            active_run_id INTEGER
        );
        CREATE TABLE work_packages (
            package_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            status TEXT,
            runtime_state TEXT,
            worktree_root TEXT,
            completed_at TEXT
        );
        CREATE TABLE pull_requests (
            package_id TEXT PRIMARY KEY,
            base_branch TEXT,
            review_status TEXT,
            review_completed_at TEXT,
            landed_at TEXT,
            landed_sha TEXT,
            landing_lane TEXT,
            landing_error TEXT
        );
        CREATE TABLE runtime_tasks (
            project_id TEXT,
            package_id TEXT,
            task_state TEXT
        );
        CREATE TABLE runs (
            id INTEGER PRIMARY KEY,
            project_id TEXT,
            package_id TEXT,
            status TEXT,
            finished_at TEXT,
            log_path TEXT,
            prompt_path TEXT,
            final_message_path TEXT
        );
        """
    )
    conn.execute(
        "INSERT INTO projects(id, path, status, active_run_id) VALUES (?,?,?,NULL)",
        ("project", str(project), "dispatch_pending"),
    )
    conn.execute(
        "INSERT INTO work_packages(package_id, project_id, status, runtime_state, worktree_root, completed_at) VALUES (?,?,?,?,?,?)",
        ("pkg-1", "project", "complete", "idle", str(worktree), OLD),
    )
    conn.execute(
        "INSERT INTO pull_requests(package_id, base_branch, review_status, review_completed_at, landed_at, landed_sha, landing_lane, landing_error) VALUES (?,?,?,?,?,?,?,?)",
        ("pkg-1", "main", "clean", OLD, OLD, landed_sha, "jury", ""),
    )
    artifact_paths: dict[int, list[Path]] = {}
    for run_id in (1, 2):
        run_dir = log_root / "project" / "pkg-1"
        paths = [
            run_dir / f"run-{run_id}.jsonl",
            run_dir / f"run-{run_id}.prompt.txt",
            run_dir / f"run-{run_id}.final.txt",
        ]
        for path in paths:
            write_old(path, f"artifact {run_id} {path.suffix}\n")
        artifact_paths[run_id] = paths
        conn.execute(
            "INSERT INTO runs(id, project_id, package_id, status, finished_at, log_path, prompt_path, final_message_path) VALUES (?,?,?,?,?,?,?,?)",
            (run_id, "project", "pkg-1", "completed", OLD, *(str(path) for path in paths)),
        )
    conn.commit()
    conn.close()
    return {
        "workspace": workspace,
        "project": project,
        "remote": remote,
        "worktree_root": worktree_root,
        "worktree": worktree,
        "log_root": log_root,
        "state_root": state_root,
        "db_path": db_path,
        "landed_sha": landed_sha,
        "artifact_paths": artifact_paths,
        "app": FakeApp(db_path),
    }


def run_cleanup(env: dict[str, object], *, mode: str = "apply", **overrides: int):
    policy_args = {
        "mode": mode,
        "interval_hours": 0,
        "worktree_min_age_hours": 1,
        "log_min_age_hours": 1,
        "keep_run_artifacts_per_package": 1,
        "max_worktrees_per_pass": 4,
        "max_artifacts_per_pass": 32,
        "max_candidates_per_pass": 32,
    }
    policy_args.update(overrides)
    return janitor.run_retention_janitor(
        env["app"],
        workspace_root=env["workspace"],
        state_root=env["state_root"],
        worktree_root=env["worktree_root"],
        log_root=env["log_root"],
        policy=janitor.RetentionPolicy(**policy_args),
        now=NOW,
    )


def test_apply_removes_only_remote_verified_worktree_and_old_run_artifacts(tmp_path) -> None:
    env = seed_runtime(tmp_path)
    unknown_checkpoint = env["worktree_root"] / "project" / ".broken-unknown"
    unknown_checkpoint.mkdir(parents=True)
    (unknown_checkpoint / "operator.txt").write_text("unproven\n", encoding="utf-8")
    queue_receipt = env["workspace"] / "state" / "queue-recovery" / "project" / "signed.json"
    queue_receipt.parent.mkdir(parents=True)
    queue_receipt.write_text("{}\n", encoding="utf-8")

    receipt = run_cleanup(env)

    assert receipt["status"] == "applied"
    assert receipt["summary"]["worktrees_selected"] == 1
    assert receipt["summary"]["worktrees_removed"] == 1
    assert receipt["summary"]["branches_removed"] == 1
    assert receipt["summary"]["artifact_files_selected"] == 3
    assert receipt["summary"]["artifact_files_removed"] == 3
    assert receipt["summary"]["bytes_reclaimed"] > 0
    assert not env["worktree"].exists()
    assert unknown_checkpoint.exists()
    assert queue_receipt.exists()
    assert git(env["project"], "branch", "--list", "fleet/pkg-1") == ""
    assert git(env["project"], "for-each-ref", "--format=%(refname)", "refs/fleet-retention-janitor") == ""
    for path in env["artifact_paths"][1]:
        assert not path.exists()
    for path in env["artifact_paths"][2]:
        assert path.exists()
    conn = sqlite3.connect(str(env["db_path"]))
    old = conn.execute(
        "SELECT log_path, prompt_path, final_message_path FROM runs WHERE id=1"
    ).fetchone()
    kept = conn.execute(
        "SELECT log_path, prompt_path, final_message_path FROM runs WHERE id=2"
    ).fetchone()
    conn.close()
    assert old == (None, None, None)
    assert all(kept)
    persisted = json.loads((env["state_root"] / "retention-janitor.latest.json").read_text(encoding="utf-8"))
    assert persisted["summary"] == receipt["summary"]
    assert list(env["state_root"].iterdir()) == [env["state_root"] / "retention-janitor.latest.json"]


def test_dry_run_is_honest_and_mutates_no_managed_target(tmp_path) -> None:
    env = seed_runtime(tmp_path)

    receipt = run_cleanup(env, mode="dry-run")

    assert receipt["status"] == "dry_run"
    assert receipt["summary"]["worktrees_selected"] == 1
    assert receipt["summary"]["worktrees_removed"] == 0
    assert receipt["summary"]["artifact_files_selected"] == 3
    assert receipt["summary"]["artifact_files_removed"] == 0
    assert receipt["summary"]["bytes_selected"] > 0
    assert receipt["summary"]["bytes_reclaimed"] == 0
    assert env["worktree"].exists()
    assert all(path.exists() for path in env["artifact_paths"][1])


def test_dirty_worktree_and_its_logs_are_categorically_excluded(tmp_path) -> None:
    env = seed_runtime(tmp_path)
    (env["worktree"] / "untracked.txt").write_text("operator work\n", encoding="utf-8")

    receipt = run_cleanup(env)

    assert receipt["summary"]["eligible"] == 0
    assert receipt["skips"] == [
        {"package_id": "pkg-1", "project_id": "project", "reason": "worktree_dirty"}
    ]
    assert env["worktree"].exists()
    assert all(path.exists() for path in env["artifact_paths"][1])


def test_clean_but_unpushed_worktree_and_its_logs_are_excluded(tmp_path) -> None:
    env = seed_runtime(tmp_path)
    (env["worktree"] / "local.txt").write_text("not remote\n", encoding="utf-8")
    git(env["worktree"], "add", "local.txt")
    git(env["worktree"], "config", "user.name", "Fleet Test")
    git(env["worktree"], "config", "user.email", "fleet@example.invalid")
    git(env["worktree"], "commit", "-m", "local only")

    receipt = run_cleanup(env)

    assert receipt["skips"][0]["reason"] == "worktree_head_unpushed"
    assert env["worktree"].exists()
    assert all(path.exists() for path in env["artifact_paths"][1])


def test_active_runtime_task_excludes_worktree_and_logs(tmp_path) -> None:
    env = seed_runtime(tmp_path)
    conn = sqlite3.connect(str(env["db_path"]))
    conn.execute(
        "INSERT INTO runtime_tasks(project_id, package_id, task_state) VALUES (?,?,?)",
        ("project", "pkg-1", "verifying"),
    )
    conn.commit()
    conn.close()

    receipt = run_cleanup(env)

    assert receipt["skips"][0]["reason"] == "runtime_task_active"
    assert env["worktree"].exists()
    assert all(path.exists() for path in env["artifact_paths"][1])


def test_process_active_worktree_is_excluded(tmp_path, monkeypatch) -> None:
    env = seed_runtime(tmp_path)
    monkeypatch.setattr(janitor, "_process_cwd_uses", lambda _path: True)

    receipt = run_cleanup(env)

    assert receipt["skips"][0]["reason"] == "worktree_process_active"
    assert env["worktree"].exists()


def test_vexp_path_is_never_touched(tmp_path) -> None:
    env = seed_runtime(tmp_path, worktree_name=".vexp/pkg-1")

    receipt = run_cleanup(env)

    assert receipt["summary"]["eligible"] == 0
    assert receipt["skips"][0]["reason"] == "worktree_outside_managed_root"
    assert env["worktree"].exists()
    assert all(path.exists() for path in env["artifact_paths"][1])


def test_missing_landing_receipt_fails_closed(tmp_path) -> None:
    env = seed_runtime(tmp_path)
    conn = sqlite3.connect(str(env["db_path"]))
    conn.execute("UPDATE pull_requests SET landed_at=NULL, landed_sha='' WHERE package_id='pkg-1'")
    conn.commit()
    conn.close()

    receipt = run_cleanup(env)

    assert receipt["skips"][0]["reason"] == "landing_receipt_missing"
    assert env["worktree"].exists()


def test_unavailable_remote_authority_fails_closed(tmp_path) -> None:
    env = seed_runtime(tmp_path)
    git(env["project"], "remote", "set-url", "origin", str(env["workspace"] / "missing.git"))

    receipt = run_cleanup(env)

    assert receipt["skips"][0]["reason"] == "remote_fetch_failed"
    assert env["worktree"].exists()
    assert all(path.exists() for path in env["artifact_paths"][1])


def test_artifact_cleanup_obeys_exact_per_pass_cap(tmp_path) -> None:
    env = seed_runtime(tmp_path)

    receipt = run_cleanup(env, max_worktrees_per_pass=0, max_artifacts_per_pass=2)

    assert receipt["summary"]["worktrees_selected"] == 0
    assert receipt["summary"]["artifact_files_selected"] == 2
    assert receipt["summary"]["artifact_files_removed"] == 2
    assert env["worktree"].exists()
    assert sum(1 for path in env["artifact_paths"][1] if path.exists()) == 1


def test_vexp_receipt_root_is_rejected_without_writing(tmp_path) -> None:
    env = seed_runtime(tmp_path)
    protected_state = env["workspace"] / ".vexp" / "keeper"

    receipt = janitor.run_retention_janitor(
        env["app"],
        workspace_root=env["workspace"],
        state_root=protected_state,
        worktree_root=env["worktree_root"],
        log_root=env["log_root"],
        policy=janitor.RetentionPolicy(mode="apply", interval_hours=0),
        now=NOW,
    )

    assert receipt["status"] == "error"
    assert receipt["error"] == "protected_receipt_path"
    assert not protected_state.exists()
    assert env["worktree"].exists()


def test_single_latest_receipt_is_atomically_replaced_and_cadence_bounded(tmp_path) -> None:
    env = seed_runtime(tmp_path)
    first = run_cleanup(env, mode="dry-run")
    policy = janitor.RetentionPolicy(
        mode="dry-run",
        interval_hours=6,
        worktree_min_age_hours=1,
        log_min_age_hours=1,
        keep_run_artifacts_per_package=1,
    )

    second = janitor.run_retention_janitor(
        env["app"],
        workspace_root=env["workspace"],
        state_root=env["state_root"],
        worktree_root=env["worktree_root"],
        log_root=env["log_root"],
        policy=policy,
        now=NOW + dt.timedelta(minutes=1),
    )

    assert first["status"] == "dry_run"
    assert second["status"] == "deferred"
    assert list(env["state_root"].iterdir()) == [env["state_root"] / "retention-janitor.latest.json"]


def test_module_has_no_process_or_broad_cache_cleanup_primitives() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "os.kill(" not in source
    assert "shutil.rmtree(" not in source
    assert "docker system prune" not in source
    assert "git\", \"worktree\", \"prune" not in source
