#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import yaml

CONTAINER_CONTROLLER_DIR = Path("/app")
HOST_WORKSPACE_ROOT = Path("/docker/fleet")
RUNNING_IN_CONTROLLER_CONTAINER = CONTAINER_CONTROLLER_DIR.joinpath("app.py").exists()

DEFAULT_WORKSPACE_ROOT = HOST_WORKSPACE_ROOT if HOST_WORKSPACE_ROOT.exists() else CONTAINER_CONTROLLER_DIR.parent
DEFAULT_CONTROLLER_DIR = CONTAINER_CONTROLLER_DIR if RUNNING_IN_CONTROLLER_CONTAINER else DEFAULT_WORKSPACE_ROOT / "controller"
DEFAULT_STATE_ROOT = (
    Path("/var/lib/codex-fleet/ooda_keeper")
    if Path("/var/lib/codex-fleet").exists()
    else DEFAULT_WORKSPACE_ROOT / "state" / "fleet_ooda_keeper"
)
DEFAULT_TARGET_ACTIVE = 20
DEFAULT_READY_BACKLOG_FLOOR = 10
DEFAULT_POLL_SECONDS = 10 * 60
DEFAULT_DURATION_SECONDS = 12 * 7 * 24 * 60 * 60
DEFAULT_FAILURE_LOOKBACK_MINUTES = 90
DEFAULT_REPEAT_FAILURE_THRESHOLD = 3
DEFAULT_STALE_LOCAL_REVIEW_MINUTES = 10
DEFAULT_STALE_RUNTIME_HOURS = 6

ACTIVE_RUN_STATUSES = {"starting", "running", "verifying", "healing", "local_review"}
ACTIVE_RUNTIME_TASK_STATES = {"starting", "scheduled", "running", "verifying", "awaiting_review"}
TRANSIENT_AUTO_RETRY_MARKERS = (
    "worker session went stale",
    "without heartbeat or log activity",
    "backend unavailable:",
    "upstream_unavailable:",
    "missing_final_message",
    "nonetype' object has no attribute 'get'",
)
THROTTLED_PROJECT_STATUSES = {
    "review_requested",
    "awaiting_pr",
    "awaiting_review",
    "review_fix_required",
    "review_failed",
    "waiting_dependency",
}
CAPACITY_ERROR_MARKERS = {"capacity", "account", "budget", "runway", "pool", "cooldown", "rate limit"}
ABSOLUTE_ROOT_RE = re.compile(r'^(?P<indent>\s*)ROOT = Path\("(?P<root>/docker/[^"]+)"\)\s*$', re.MULTILINE)
RELEASE_BUILD_DRIFT_RE = re.compile(
    r'CHUMMER_CORE_ENGINE_TEST_FILTER=(?P<filter>parity-m14[23]) dotnet run --project Chummer\.CoreEngine\.Tests/Chummer\.CoreEngine\.Tests\.csproj -m:1 -p:UseSharedCompilation=false'
)
DESIGN_QUEUE_MIRROR_PATH = Path("/docker/chummercomplete/chummer-design/products/chummer/NEXT_90_DAY_QUEUE_STAGING.generated.yaml")
BROAD_SCOPE_PATH_MARKERS = {"src", "tests", "scripts", "docs", "products"}


def _sql_string_set(values: Sequence[str]) -> str:
    return ", ".join("'" + str(value).replace("'", "''") + "'" for value in values)


def default_controller_url(*, running_in_controller_container: Optional[bool] = None) -> str:
    if running_in_controller_container is None:
        running_in_controller_container = RUNNING_IN_CONTROLLER_CONTAINER
    return "http://127.0.0.1:8090" if running_in_controller_container else "http://127.0.0.1:18090"


DEFAULT_CONTROLLER_URL = os.environ.get("FLEET_CONTROLLER_URL", default_controller_url())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-root", default=str(DEFAULT_WORKSPACE_ROOT))
    parser.add_argument("--controller-dir", default=str(DEFAULT_CONTROLLER_DIR))
    parser.add_argument("--state-root", default=str(DEFAULT_STATE_ROOT))
    parser.add_argument("--controller-url", default=DEFAULT_CONTROLLER_URL)
    parser.add_argument("--target-active", type=int, default=DEFAULT_TARGET_ACTIVE)
    parser.add_argument("--ready-backlog-floor", type=int, default=DEFAULT_READY_BACKLOG_FLOOR)
    parser.add_argument("--poll-seconds", type=int, default=DEFAULT_POLL_SECONDS)
    parser.add_argument("--duration-seconds", type=int, default=DEFAULT_DURATION_SECONDS)
    parser.add_argument("--failure-lookback-minutes", type=int, default=DEFAULT_FAILURE_LOOKBACK_MINUTES)
    parser.add_argument("--repeat-failure-threshold", type=int, default=DEFAULT_REPEAT_FAILURE_THRESHOLD)
    parser.add_argument("--stale-local-review-minutes", type=int, default=DEFAULT_STALE_LOCAL_REVIEW_MINUTES)
    parser.add_argument("--stale-runtime-hours", type=int, default=DEFAULT_STALE_RUNTIME_HOURS)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--forever", action="store_true")
    return parser.parse_args()


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso_now() -> str:
    return utc_now().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def iso(value: Optional[dt.datetime]) -> str:
    if value is None:
        return ""
    return value.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(value: Any) -> Optional[dt.datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return dt.datetime.fromisoformat(text)
    except ValueError:
        return None


def fleet_db_path(workspace_root: Path) -> Path:
    return workspace_root / "state" / "fleet.db"


def _path_has_recent_activity(path_text: str, *, cutoff: dt.datetime) -> bool:
    clean = str(path_text or "").strip()
    if not clean:
        return False
    path = Path(clean)
    if not path.exists():
        return False
    try:
        mtime = dt.datetime.fromtimestamp(path.stat().st_mtime, tz=dt.timezone.utc)
    except OSError:
        return False
    return mtime >= cutoff


def prune_stale_runtime_commitments(workspace_root: Path, *, stale_hours: int) -> int:
    db_path = fleet_db_path(workspace_root)
    if not db_path.exists():
        return 0
    now = utc_now()
    cutoff = now - dt.timedelta(hours=max(1, int(stale_hours)))
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT rt.project_id,
                   COALESCE(rt.package_id, '') AS package_id,
                   rt.run_id AS runtime_run_id,
                   rt.task_state,
                   rt.scheduled_at,
                   rt.started_at,
                   rt.updated_at,
                   p.status AS project_status,
                   p.active_run_id,
                   r.id AS run_id,
                   r.status AS run_status,
                   r.started_at AS run_started_at,
                   r.finished_at AS run_finished_at,
                   r.log_path,
                   r.final_message_path
            FROM runtime_tasks rt
            LEFT JOIN projects p ON p.id = rt.project_id
            LEFT JOIN runs r ON r.id = COALESCE(rt.run_id, p.active_run_id)
            WHERE rt.task_state IN ('scheduled', 'running')
            ORDER BY rt.project_id, rt.package_id
            """
        ).fetchall()
        cleared = 0
        for row in rows:
            project_id = str(row["project_id"] or "").strip()
            package_id = str(row["package_id"] or "").strip()
            if not project_id:
                continue
            runtime_run_id = int(row["runtime_run_id"] or 0)
            active_run_id = int(row["active_run_id"] or 0)
            run_finished_at = parse_iso(row["run_finished_at"])
            run_status = str(row["run_status"] or "").strip().lower()
            if runtime_run_id and (run_finished_at is not None or (run_status and run_status not in ACTIVE_RUN_STATUSES)):
                reason = (
                    f"keeper cleared terminal runtime commitment for run {runtime_run_id} "
                    f"status={run_status or 'unknown'}"
                )
                conn.execute(
                    "DELETE FROM runtime_tasks WHERE project_id=? AND COALESCE(package_id,'')=?",
                    (project_id, package_id),
                )
                if active_run_id == runtime_run_id:
                    conn.execute(
                        """
                        UPDATE projects
                        SET active_run_id=NULL,
                            last_error=COALESCE(NULLIF(last_error, ''), ?),
                            updated_at=?
                        WHERE id=?
                        """,
                        (reason, iso(now), project_id),
                    )
                cleared += 1
                continue
            anchors = [
                parse_iso(row["updated_at"]),
                parse_iso(row["started_at"]),
                parse_iso(row["scheduled_at"]),
                parse_iso(row["run_started_at"]),
            ]
            anchor = next((item for item in anchors if item is not None), None)
            if anchor is None or anchor >= cutoff:
                continue
            if _path_has_recent_activity(str(row["log_path"] or ""), cutoff=cutoff):
                continue
            if _path_has_recent_activity(str(row["final_message_path"] or ""), cutoff=cutoff):
                continue
            reason = (
                f"keeper pruned stale runtime commitment after {int((now - anchor).total_seconds())}s "
                "with no run log or final-message activity"
            )
            if row["run_id"]:
                conn.execute(
                    """
                    UPDATE runs
                    SET status='failed',
                        finished_at=COALESCE(finished_at, ?),
                        error_class=COALESCE(error_class, 'orphaned_runtime'),
                        error_message=COALESCE(error_message, ?)
                    WHERE id=?
                    """,
                    (iso(now), reason, int(row["run_id"])),
                )
            conn.execute(
                "DELETE FROM runtime_tasks WHERE project_id=? AND COALESCE(package_id,'')=?",
                (project_id, package_id),
            )
            if row["active_run_id"]:
                conn.execute(
                    """
                    UPDATE projects
                    SET active_run_id=NULL,
                        last_error=COALESCE(last_error, ?),
                        updated_at=?
                    WHERE id=?
                    """,
                    (reason, iso(now), project_id),
                )
            cleared += 1
        if cleared:
            conn.commit()
        return cleared


def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}


def _load_queue_staging_document(path: Path) -> Tuple[Any, List[Dict[str, Any]]]:
    if not path.exists():
        return None, []
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    except Exception:
        return None, []
    if isinstance(payload, list):
        return payload, [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        packages = payload.get("items")
        if packages is None:
            packages = payload.get("packages") or []
        if isinstance(packages, list):
            return payload, [item for item in packages if isinstance(item, dict)]
    return payload, []


def _load_queue_staging(path: Path) -> List[Dict[str, Any]]:
    return _load_queue_staging_document(path)[1]


def _write_queue_staging(path: Path, packages: List[Dict[str, Any]], *, original_document: Any = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = packages
    if isinstance(original_document, dict):
        document = dict(original_document)
        if isinstance(document.get("items"), list):
            document["items"] = packages
        elif isinstance(document.get("packages"), list):
            document["packages"] = packages
        else:
            document = packages
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")


def autoheal_queue_scope_drift(
    app: Any,
    *,
    workspace_root: Path,
    controller_url: str,
    fleet_queue_path: Optional[Path] = None,
    design_queue_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    fleet_queue = fleet_queue_path or (workspace_root / ".codex-studio" / "published" / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml")
    design_queue = design_queue_path or DESIGN_QUEUE_MIRROR_PATH
    fleet_document, fleet_packages = _load_queue_staging_document(fleet_queue)
    _, design_packages = _load_queue_staging_document(design_queue)
    if not fleet_packages or not design_packages:
        return []

    design_by_package = {
        str(item.get("package_id") or "").strip(): item
        for item in design_packages
        if str(item.get("package_id") or "").strip()
    }
    changed: List[Dict[str, Any]] = []
    for item in fleet_packages:
        package_id = str(item.get("package_id") or "").strip()
        if not package_id:
            continue
        mirror = design_by_package.get(package_id)
        if mirror is None:
            continue
        if str(item.get("repo") or "").strip() != str(mirror.get("repo") or "").strip():
            continue
        live_allowed = [str(path).strip() for path in list(item.get("allowed_paths") or []) if str(path).strip()]
        mirror_allowed = [str(path).strip() for path in list(mirror.get("allowed_paths") or []) if str(path).strip()]
        if not live_allowed or not mirror_allowed:
            continue
        if set(mirror_allowed) == set(live_allowed):
            continue
        stale_broad_paths = [path for path in live_allowed if path not in mirror_allowed and path in BROAD_SCOPE_PATH_MARKERS]
        if not stale_broad_paths and not set(mirror_allowed).issubset(set(live_allowed)):
            continue
        if len(mirror_allowed) > len(live_allowed) and not stale_broad_paths:
            continue
        item["allowed_paths"] = mirror_allowed
        changed.append(
            {
                "package_id": package_id,
                "project_id": str(item.get("repo") or "").strip(),
                "old_allowed_paths": live_allowed,
                "new_allowed_paths": mirror_allowed,
                "stale_broad_paths": stale_broad_paths,
            }
        )
    if not changed:
        return []

    _write_queue_staging(fleet_queue, fleet_packages, original_document=fleet_document)
    with app.db() as conn:
        for action in changed:
            package_id = str(action["package_id"])
            allowed = list(action["new_allowed_paths"])
            row = conn.execute(
                "SELECT project_id, task_meta_json FROM work_packages WHERE package_id=?",
                (package_id,),
            ).fetchone()
            if row is None:
                continue
            project_id = str(row["project_id"] or "").strip()
            task_meta = json.loads(str(row["task_meta_json"] or "{}") or "{}")
            task_meta["allowed_paths"] = allowed
            conn.execute(
                "UPDATE work_packages SET allowed_paths_json=?, task_meta_json=? WHERE package_id=?",
                (json.dumps(allowed), json.dumps(task_meta, sort_keys=True), package_id),
            )
            active_rows = conn.execute(
                """
                SELECT claim_value
                FROM scope_claims
                WHERE package_id=?
                  AND claim_type='path'
                  AND claim_state='active'
                """,
                (package_id,),
            ).fetchall()
            active_values = {str(item["claim_value"] or "").strip() for item in active_rows}
            stale_values = [value for value in active_values if value not in allowed]
            if stale_values:
                conn.executemany(
                    """
                    UPDATE scope_claims
                    SET claim_state='released',
                        released_at=?
                    WHERE package_id=?
                      AND claim_type='path'
                      AND claim_value=?
                      AND claim_state='active'
                    """,
                    [(iso_now(), package_id, value) for value in stale_values],
                )
            for value in allowed:
                scope_key = f"path:{value}"
                existing = conn.execute(
                    """
                    SELECT 1
                    FROM scope_claims
                    WHERE package_id=?
                      AND claim_type='path'
                      AND claim_value=?
                    """,
                    (package_id, value),
                ).fetchone()
                if existing:
                    conn.execute(
                        """
                        UPDATE scope_claims
                        SET project_id=?,
                            scope_key=?,
                            claim_state='active',
                            activated_at=COALESCE(activated_at, ?),
                            released_at=NULL
                        WHERE package_id=?
                          AND claim_type='path'
                          AND claim_value=?
                        """,
                        (project_id, scope_key, iso_now(), package_id, value),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO scope_claims(package_id, project_id, claim_type, claim_value, scope_key, claim_state, created_at, activated_at, released_at)
                        VALUES(?, ?, 'path', ?, ?, 'active', ?, ?, NULL)
                        """,
                        (package_id, project_id, value, scope_key, iso_now(), iso_now()),
                    )
    actions: List[Dict[str, Any]] = []
    seen_projects: set[str] = set()
    for action in changed:
        row = None
        with app.db() as conn:
            row = conn.execute(
                "SELECT id AS project_id, status, active_run_id FROM projects WHERE id=(SELECT project_id FROM work_packages WHERE package_id=?)",
                (action["package_id"],),
            ).fetchone()
        project_id = str((row["project_id"] if row else "") or "").strip()
        if not project_id or project_id in seen_projects:
            continue
        seen_projects.add(project_id)
        project_status = str((row["status"] if row else "") or "").strip().lower()
        active_run_id = int((row["active_run_id"] if row else 0) or 0)
        retry_result: Dict[str, Any] = {"ok": True, "skipped": True}
        if project_status not in ACTIVE_RUN_STATUSES and not active_run_id:
            try:
                retry_result = http_post_json(f"{controller_url.rstrip('/')}/api/projects/{project_id}/retry", {})
            except urllib.error.URLError as exc:
                retry_result = {"ok": False, "error": str(exc)}
        actions.append(
            {
                "trigger": "queue_scope_drift",
                "package_id": action["package_id"],
                "project_id": project_id,
                "old_allowed_paths": action["old_allowed_paths"],
                "new_allowed_paths": action["new_allowed_paths"],
                "stale_broad_paths": action["stale_broad_paths"],
                "retry_result": retry_result,
            }
        )
    return actions
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def normalize_worktree_root_literals(worktree_root: Path) -> List[str]:
    changed: List[str] = []
    if not worktree_root.exists():
        return changed
    repo_literal = str(worktree_root)
    targets = [
        worktree_root / "scripts" / "materialize_status_plane.py",
        worktree_root / "scripts" / "verify_status_plane_semantics.py",
    ]
    for path in targets:
        if not path.is_file():
            continue
        try:
            original = path.read_text(encoding="utf-8")
        except OSError:
            continue

        def replace_root(match: re.Match[str]) -> str:
            root = str(match.group("root") or "")
            if root == repo_literal:
                return match.group(0)
            return f'{match.group("indent")}ROOT = Path(__file__).resolve().parents[1]'

        updated = ABSOLUTE_ROOT_RE.sub(replace_root, original)
        if updated == original:
            continue
        path.write_text(updated, encoding="utf-8")
        changed.append(str(path.relative_to(worktree_root)))
    return changed


def normalize_release_receipt_command_strings(repo_root: Path) -> List[str]:
    changed: List[str] = []
    targets = [
        repo_root / "scripts" / "verify-next90-m142-dense-workbench-receipts.py",
        repo_root / "scripts" / "verify-next90-m143-export-print-supplement-rule-environment-receipts.py",
        repo_root / "tests" / "test_next90_m142_dense_workbench_receipts.py",
        repo_root / "tests" / "test_next90_m143_export_print_supplement_rule_environment_receipts.py",
        repo_root / "docs" / "NEXT90_M142_DENSE_WORKBENCH_RECEIPTS.md",
        repo_root / "docs" / "NEXT90_M143_EXPORT_PRINT_SUPPLEMENT_RULE_ENVIRONMENT_RECEIPTS.md",
    ]
    for path in targets:
        if not path.is_file():
            continue
        try:
            original = path.read_text(encoding="utf-8")
        except OSError:
            continue
        updated = RELEASE_BUILD_DRIFT_RE.sub(
            lambda m: (
                f'CHUMMER_CORE_ENGINE_TEST_FILTER={m.group("filter")} '
                'dotnet run --project Chummer.CoreEngine.Tests/Chummer.CoreEngine.Tests.csproj '
                '-c Release -m:1 -p:UseSharedCompilation=false'
            ),
            original,
        )
        if updated == original:
            continue
        path.write_text(updated, encoding="utf-8")
        changed.append(str(path.relative_to(repo_root)))
    return changed


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_event(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def set_host_controller_env_defaults(controller_dir: Path) -> None:
    if RUNNING_IN_CONTROLLER_CONTAINER:
        return
    resolved = controller_dir.resolve()
    workspace_root = resolved.parent if resolved.name == "controller" else DEFAULT_WORKSPACE_ROOT
    state_dir = workspace_root / "state"
    os.environ.setdefault("FLEET_DB_PATH", str(state_dir / "fleet.db"))
    os.environ.setdefault("FLEET_LOG_DIR", str(state_dir / "logs"))
    os.environ.setdefault("FLEET_QUEUE_RECOVERY_DIR", str(state_dir / "queue-recovery"))
    os.environ.setdefault("FLEET_WORKTREE_ROOT", str(state_dir / "worktrees"))
    os.environ.setdefault("FLEET_CONTROLLER_HEARTBEAT_PATH", str(state_dir / "controller-heartbeat.json"))
    os.environ.setdefault("FLEET_CODEX_HOME_ROOT", str(state_dir / "codex-homes"))
    os.environ.setdefault("FLEET_GROUP_ROOT", str(state_dir / "groups"))


def load_controller_app(controller_dir: Path) -> Any:
    resolved = controller_dir.resolve()
    set_host_controller_env_defaults(resolved)
    sys.path.insert(0, str(resolved))
    import app  # type: ignore

    return app


def http_post_json(url: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    data = json.dumps(payload or {}).encode("utf-8")
    request = urllib.request.Request(
        url,
        method="POST",
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def normalize_error_signature(error_class: str, error_message: str) -> str:
    clean_class = str(error_class or "").strip().lower() or "unknown"
    clean_message = str(error_message or "").strip().lower()
    if clean_message.startswith("verify failed with exit"):
        return clean_message
    if clean_class == "verify" and "journey gates contract drift detected" in clean_message:
        return "verify:journey_gates_contract_drift"
    if clean_class == "verify" and "forbidden guide directories still present" in clean_message:
        return "verify:forbidden_guide_directories"
    if clean_class == "verify" and "status_plane.generated.yaml drifted from live readiness/deployment semantics" in clean_message:
        return "verify:status_plane_drift"
    if clean_class == "verify" and "dense workbench receipts" in clean_message:
        return "verify:dense_workbench_receipt_drift"
    if clean_class == "verify" and "export print supplement rule environment receipts" in clean_message:
        return "verify:export_print_receipt_drift"
    if clean_class == "orphaned_runtime":
        if "controller lost coding supervision" in clean_message:
            return "orphaned_runtime:lost_supervision"
        if "run is no longer linked from project.active_run_id" in clean_message:
            return "orphaned_runtime:unlinked_run"
    if clean_class == "review" and "not reviewable" in clean_message:
        return "review:not_reviewable"
    if clean_class == "scope_guard":
        return "scope_guard"
    if clean_class == "package_compile":
        return "package_compile"
    if clean_message:
        return f"{clean_class}:{clean_message}"
    return clean_class


def _run_is_upstream_capacity_failure(row: sqlite3.Row) -> bool:
    error_class = str(row["error_class"] or "").strip().lower()
    error_message = str(row["error_message"] or "").strip().lower()
    if "upstream_unavailable:" in error_message:
        return True
    if error_class not in {"verify", "review", "failed", ""} and error_class != "unknown":
        return False
    final_message_path = str(row["final_message_path"] or "").strip()
    if not final_message_path:
        return False
    path = Path(final_message_path)
    if not path.exists():
        return False
    try:
        final_text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    clean_text = final_text.lower()
    transient_markers = (
        "exact blocker: upstream_unavailable:",
        "error: upstream_unavailable:",
        "exact blocker: missing_final_message",
        "error: missing_final_message",
    )
    return any(marker in clean_text for marker in transient_markers)


def autoheal_worktree_and_receipt_drift(app: Any, *, controller_url: str) -> List[Dict[str, Any]]:
    with app.db() as conn:
        rows = conn.execute(
            """
            SELECT runs.id AS run_id,
                   runs.project_id,
                   COALESCE(runs.package_id, '') AS package_id,
                   COALESCE(runs.error_class, '') AS error_class,
                   COALESCE(runs.error_message, '') AS error_message,
                   COALESCE(runs.log_path, '') AS log_path,
                   COALESCE(wp.worktree_root, '') AS worktree_root,
                   COALESCE(projects.path, '') AS project_path,
                   COALESCE(projects.status, '') AS project_status,
                   projects.active_run_id
            FROM runs
            LEFT JOIN work_packages wp
              ON wp.package_id = runs.package_id
             AND wp.project_id = runs.project_id
            LEFT JOIN projects
              ON projects.id = runs.project_id
            WHERE runs.status='failed'
            ORDER BY runs.finished_at DESC, runs.id DESC
            LIMIT 40
            """
        ).fetchall()
    actions: List[Dict[str, Any]] = []
    seen_projects: set[str] = set()
    for row in rows:
        project_id = str(row["project_id"] or "").strip()
        if not project_id or project_id in seen_projects:
            continue
        seen_projects.add(project_id)
        project_status = str(row["project_status"] or "").strip().lower()
        if project_status in ACTIVE_RUN_STATUSES or row["active_run_id"]:
            continue
        signature = normalize_error_signature(str(row["error_class"] or ""), str(row["error_message"] or ""))
        log_text = ""
        log_path = Path(str(row["log_path"] or "").strip())
        if log_path.exists():
            try:
                log_text = log_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                log_text = ""
        trigger = ""
        changed_paths: List[str] = []
        worktree_root = Path(str(row["worktree_root"] or "").strip()) if str(row["worktree_root"] or "").strip() else None
        project_root = Path(str(row["project_path"] or "").strip()) if str(row["project_path"] or "").strip() else None
        if ("status-plane verification failed" in log_text or signature == "verify:status_plane_drift") and worktree_root is not None:
            changed_paths = normalize_worktree_root_literals(worktree_root)
            trigger = "status_plane_root_leakage"
        elif ("test_next90_m142_dense_workbench_receipts" in log_text or signature == "verify:dense_workbench_receipt_drift") and project_root is not None:
            changed_paths = normalize_release_receipt_command_strings(project_root)
            trigger = "dense_workbench_release_command_drift"
        elif ("test_next90_m143_export_print_supplement_rule_environment_receipts" in log_text or signature == "verify:export_print_receipt_drift") and project_root is not None:
            changed_paths = normalize_release_receipt_command_strings(project_root)
            trigger = "export_print_release_command_drift"
        if not changed_paths:
            continue
        try:
            retry_result = http_post_json(f"{controller_url.rstrip('/')}/api/projects/{project_id}/retry", {})
        except urllib.error.URLError as exc:
            retry_result = {"ok": False, "error": str(exc)}
        actions.append(
            {
                "project_id": project_id,
                "package_id": str(row["package_id"] or ""),
                "run_id": int(row["run_id"] or 0),
                "trigger": trigger,
                "changed_paths": changed_paths,
                "retry_result": retry_result,
            }
        )
    return actions


def repeated_failure_map(app: Any, *, lookback_minutes: int, threshold: int) -> Dict[str, Dict[str, Any]]:
    cutoff = utc_now() - dt.timedelta(minutes=max(1, lookback_minutes))
    blocked: Dict[str, Dict[str, Any]] = {}
    active_keys = active_commitment_keys(app)
    runtime_state_sql = _sql_string_set(sorted(ACTIVE_RUNTIME_TASK_STATES))
    with app.db() as conn:
        active_runtime_rows = conn.execute(
            f"""
            SELECT project_id, COALESCE(package_id, '') AS package_id
            FROM runtime_tasks
            WHERE task_state IN ({runtime_state_sql})
            """
        ).fetchall()
        rows = conn.execute(
            """
            SELECT runs.project_id,
                   COALESCE(runs.package_id, '') AS package_id,
                   COALESCE(runs.error_class, '') AS error_class,
                   COALESCE(runs.error_message, '') AS error_message,
                   runs.finished_at,
                   COALESCE(runs.final_message_path, '') AS final_message_path,
                   COALESCE(wp.status, '') AS package_status,
                   COALESCE(projects.status, '') AS project_status,
                   COALESCE(projects.last_error, '') AS project_last_error,
                   COALESCE(projects.consecutive_failures, 0) AS project_consecutive_failures
            FROM runs
            LEFT JOIN work_packages wp
              ON wp.package_id = runs.package_id
             AND wp.project_id = runs.project_id
            LEFT JOIN projects
              ON projects.id = runs.project_id
            WHERE runs.status IN ('failed', 'review_failed', 'rejected', 'rate_limited')
              AND runs.finished_at IS NOT NULL
              AND runs.finished_at >= ?
            ORDER BY finished_at DESC
            """,
            (iso(cutoff),),
        ).fetchall()
    active_runtime_projects = {
        str(row["project_id"] or "").strip()
        for row in active_runtime_rows
        if str(row["project_id"] or "").strip()
    }
    active_runtime_packages = {
        str(row["package_id"] or "").strip()
        for row in active_runtime_rows
        if str(row["package_id"] or "").strip()
    }
    grouped: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = {}
    for row in rows:
        project_id = str(row["project_id"] or "").strip()
        if not project_id:
            continue
        package_id = str(row["package_id"] or "").strip()
        package_status = str(row["package_status"] or "").strip().lower()
        project_status = str(row["project_status"] or "").strip().lower()
        project_last_error = str(row["project_last_error"] or "").strip()
        project_consecutive_failures = int(row["project_consecutive_failures"] or 0)
        runtime_key = package_id or project_id
        if runtime_key in active_keys:
            continue
        if package_id:
            if package_id in active_runtime_packages or project_id in active_runtime_projects:
                continue
        elif project_id in active_runtime_projects:
            continue
        if package_id and package_status in {"complete", "completed_signed_off", "scaffold_complete", "archived"}:
            continue
        if not package_id and project_status in {"complete", "completed_signed_off", "scaffold_complete"}:
            continue
        if (
            not package_id
            and not project_last_error
            and project_consecutive_failures <= 0
            and project_status not in {"failed", "review_failed", "rejected", "rate_limited"}
        ):
            continue
        if _run_is_upstream_capacity_failure(row):
            continue
        signature = normalize_error_signature(str(row["error_class"] or ""), str(row["error_message"] or ""))
        key = (project_id, package_id, signature)
        grouped.setdefault(key, []).append(
            {
                "finished_at": str(row["finished_at"] or ""),
                "error_class": str(row["error_class"] or ""),
                "error_message": str(row["error_message"] or ""),
            }
        )
    for (project_id, package_id, signature), failures in grouped.items():
        if len(failures) < max(1, threshold):
            continue
        runtime_key = package_id or project_id
        existing = blocked.get(runtime_key)
        if existing and int(existing.get("count") or 0) >= len(failures):
            continue
        blocked[runtime_key] = {
            "runtime_key": runtime_key,
            "project_id": project_id,
            "package_id": package_id,
            "signature": signature,
            "count": len(failures),
            "latest_finished_at": failures[0]["finished_at"],
            "latest_error_class": failures[0]["error_class"],
            "latest_error_message": failures[0]["error_message"],
        }
    return blocked


def persist_planned_launch(app: Any, planned: Any) -> bool:
    project_id = str(planned.project_id or "").strip()
    package_id = str(planned.package_id or planned.candidate.package_id or "").strip()
    runtime_key = package_id or project_id
    if not project_id or app.runtime_task_row(runtime_key):
        return False
    decision = dict(getattr(planned, "decision", {}) or {})
    lane_capacity = dict(decision.get("lane_capacity") or {})
    capacity_summary = dict(lane_capacity.get("capacity_summary") or {})
    lane_capacity_state = str(
        lane_capacity.get("state")
        or capacity_summary.get("state")
        or ""
    ).strip().lower()
    if lane_capacity_state in {"missing", "disabled"}:
        return False
    payload = app.coding_runtime_task_payload(planned)
    app.upsert_runtime_task(
        project_id,
        package_id=package_id or None,
        task_kind="coding",
        task_state="scheduled",
        payload=payload,
        scheduled_at=app.utc_now(),
    )
    if package_id:
        app.activate_work_package_scope_claims(package_id)
        app.update_work_package_runtime(package_id, status="running", runtime_state="scheduled")
    app.save_runtime_task_cache_snapshot()
    return True


def candidate_runtime_key(candidate: Any) -> str:
    package_id = str(getattr(candidate, "package_id", "") or "").strip()
    if package_id:
        return package_id
    project_cfg = getattr(candidate, "project_cfg", {}) or {}
    return str(project_cfg.get("id") or "").strip()


def active_commitment_keys(app: Any) -> set[str]:
    keys: set[str] = set()
    runtime_state_sql = _sql_string_set(sorted(ACTIVE_RUNTIME_TASK_STATES))
    run_status_sql = _sql_string_set(sorted(ACTIVE_RUN_STATUSES))
    with app.db() as conn:
        runtime_rows = conn.execute(
            f"""
            SELECT package_id, project_id
            FROM runtime_tasks
            WHERE task_state IN ({runtime_state_sql})
            ORDER BY project_id, package_id
            """
        ).fetchall()
        run_rows = conn.execute(
            f"""
            SELECT COALESCE(package_id, project_id) AS runtime_key
            FROM runs
            WHERE status IN ({run_status_sql})
              AND finished_at IS NULL
            """
        ).fetchall()
    for row in runtime_rows:
        keys.add(str(row["package_id"] or row["project_id"] or "").strip())
    for row in run_rows:
        keys.add(str(row["runtime_key"] or "").strip())
    keys.discard("")
    return keys


def build_candidates(app: Any, config: Dict[str, Any], repeated_failures: Dict[str, Dict[str, Any]]) -> Tuple[List[Any], Dict[str, int]]:
    now = app.utc_now()
    with app.db() as conn:
        project_rows = conn.execute("SELECT * FROM projects ORDER BY id").fetchall()
    active_projects = {
        str(row["id"] or "").strip()
        for row in project_rows
        if str(row["id"] or "").strip()
        and (bool(row["active_run_id"]) or str(row["status"] or "").strip().lower() in ACTIVE_RUN_STATUSES)
    }
    candidates: List[Any] = []
    status_counts: Dict[str, int] = {}
    for row in project_rows:
        project_id = str(row["id"] or "").strip()
        if not project_id:
            continue
        project_cfg = app.get_project_cfg(config, project_id)
        status_counts[str(row["status"] or "").strip().lower() or "unknown"] = (
            int(status_counts.get(str(row["status"] or "").strip().lower() or "unknown") or 0) + 1
        )
        if app.project_uses_package_scheduler(config, project_id):
            for candidate in app.prepare_work_package_dispatch_candidates(config, project_cfg, row, now):
                runtime_key = candidate_runtime_key(candidate)
                if runtime_key in repeated_failures:
                    continue
                if not candidate.dispatchable or not candidate.slice_name:
                    continue
                candidates.append(candidate)
            continue
        if project_id in active_projects or app.project_has_runtime_task(project_id):
            continue
        candidate = app.prepare_dispatch_candidate(config, project_cfg, row, now)
        if candidate_runtime_key(candidate) in repeated_failures:
            continue
        if candidate.dispatchable and candidate.slice_name and str(candidate.runtime_status or "").strip().lower() not in THROTTLED_PROJECT_STATUSES:
            candidates.append(candidate)
    candidates.sort(
        key=lambda item: (
            app.gate_clearing_priority(item),
            candidate_runtime_key(item),
        )
    )
    return candidates, status_counts


def schedule_to_target(
    app: Any,
    config: Dict[str, Any],
    *,
    target_active: int,
    repeated_failures: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    committed_keys = active_commitment_keys(app)
    deficit = max(0, int(target_active) - len(committed_keys))
    if deficit <= 0:
        return []
    candidates, _ = build_candidates(app, config, repeated_failures)
    reserved_account_counts: Dict[str, int] = {}
    reserved_lane_counts: Dict[str, int] = {}
    reserved_project_counts: Dict[str, int] = {}
    reserved_scope_claims: List[Dict[str, Any]] = []
    launched: List[Dict[str, Any]] = []
    for candidate in candidates:
        if len(committed_keys) + len(launched) >= target_active:
            break
        project_id = str(candidate.project_cfg.get("id") or "").strip()
        runtime_key = candidate_runtime_key(candidate)
        if runtime_key in repeated_failures:
            continue
        if runtime_key in committed_keys:
            continue
        planned = app.plan_candidate_launch(
            config,
            candidate,
            reserved_account_counts=reserved_account_counts,
            reserved_lane_counts=reserved_lane_counts,
            reserved_project_counts=reserved_project_counts,
            reserved_scope_claims=reserved_scope_claims,
        )
        if not planned:
            continue
        if not persist_planned_launch(app, planned):
            continue
        committed_keys.add(runtime_key)
        reserved_project_counts[project_id] = int(reserved_project_counts.get(project_id) or 0) + 1
        reserved_account_counts[planned.account_alias] = int(reserved_account_counts.get(planned.account_alias) or 0) + 1
        target_lane = str((planned.decision.get("quartermaster") or {}).get("target_lane") or "").strip()
        if target_lane:
            reserved_lane_counts[target_lane] = int(reserved_lane_counts.get(target_lane) or 0) + 1
        if planned.candidate.package_row:
            reserved_scope_claims.extend(app.compiled_scope_claims_for_package(planned.candidate.package_row))
        launched.append(
            {
                "project_id": project_id,
                "package_id": str(planned.package_id or ""),
                "slice_name": str(planned.candidate.slice_name or ""),
                "account_alias": str(planned.account_alias or ""),
                "selected_model": str(planned.selected_model or ""),
            }
        )
    return launched


def ready_backlog_count(app: Any, config: Dict[str, Any], repeated_failures: Dict[str, Dict[str, Any]]) -> int:
    candidates, _ = build_candidates(app, config, repeated_failures)
    return len(candidates)


def blocker_summary(app: Any, repeated_failures: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    with app.db() as conn:
        rows = conn.execute(
            "SELECT id, status, current_slice, last_error FROM projects ORDER BY id"
        ).fetchall()
    blockers: List[Dict[str, Any]] = []
    repeated_by_project: Dict[str, List[Dict[str, Any]]] = {}
    for item in repeated_failures.values():
        project_id = str(item.get("project_id") or "").strip()
        if project_id:
            repeated_by_project.setdefault(project_id, []).append(item)
    for row in rows:
        project_id = str(row["id"] or "").strip()
        status = str(row["status"] or "").strip().lower()
        if not project_id or status in {"complete", "completed_signed_off", "scaffold_complete"}:
            continue
        item = {
            "project_id": project_id,
            "status": status,
            "current_slice": str(row["current_slice"] or ""),
            "last_error": str(row["last_error"] or ""),
        }
        if repeated_by_project.get(project_id):
            item["repeat_failures"] = sorted(
                repeated_by_project[project_id],
                key=lambda payload: (-int(payload.get("count") or 0), str(payload.get("runtime_key") or "")),
            )[:3]
        blockers.append(item)
    blockers.sort(key=lambda item: (0 if "repeat_failures" in item else 1, item["status"], item["project_id"]))
    return blockers[:12]


def ready_project_ids(app: Any, repeated_failures: Dict[str, Dict[str, Any]]) -> List[str]:
    active_keys = active_commitment_keys(app)
    with app.db() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT project_id
            FROM work_packages
            WHERE status='ready'
            ORDER BY project_id
            """
        ).fetchall()
    projects: List[str] = []
    for row in rows:
        project_id = str(row["project_id"] or "").strip()
        if not project_id or project_id in active_keys or project_id in repeated_failures:
            continue
        projects.append(project_id)
    return projects


def auto_retry_transient_dispatch_pending_projects(
    app: Any,
    *,
    controller_url: str,
    repeated_failures: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    active_keys = active_commitment_keys(app)
    now = utc_now()
    with app.db() as conn:
        rows = conn.execute(
            """
            SELECT id, status, cooldown_until, last_error, current_slice
            FROM projects
            ORDER BY id
            """
        ).fetchall()
    actions: List[Dict[str, Any]] = []
    for row in rows:
        project_id = str(row["id"] or "").strip()
        if not project_id or project_id in active_keys:
            continue
        if project_id in repeated_failures:
            signature = str((repeated_failures.get(project_id) or {}).get("signature") or "").lower()
            if signature and not any(marker in signature for marker in TRANSIENT_AUTO_RETRY_MARKERS):
                continue
        status = str(row["status"] or "").strip().lower()
        if status not in {"dispatch_pending", "awaiting_account"}:
            continue
        error_text = str(row["last_error"] or "").strip()
        lowered = error_text.lower()
        if not error_text or not any(marker in lowered for marker in TRANSIENT_AUTO_RETRY_MARKERS):
            continue
        cooldown_until = parse_iso(row["cooldown_until"])
        if cooldown_until and cooldown_until > now:
            continue
        try:
            result = http_post_json(f"{controller_url.rstrip('/')}/api/projects/{project_id}/retry", {})
        except urllib.error.URLError as exc:
            actions.append(
                {
                    "project_id": project_id,
                    "action": "retry_failed",
                    "reason": str(exc),
                    "last_error": error_text,
                }
            )
            continue
        actions.append(
            {
                "project_id": project_id,
                "action": "retry_transient_dispatch_pending",
                "last_error": error_text,
                "result": result,
            }
        )
    return actions


def nudge_ready_projects(
    app: Any,
    *,
    controller_url: str,
    repeated_failures: Dict[str, Dict[str, Any]],
    target_active: int,
) -> List[Dict[str, Any]]:
    if len(active_commitment_keys(app)) >= int(target_active):
        return []
    nudged: List[Dict[str, Any]] = []
    for project_id in ready_project_ids(app, repeated_failures):
        if len(active_commitment_keys(app)) >= int(target_active):
            break
        try:
            result = http_post_json(f"{controller_url.rstrip('/')}/api/projects/{project_id}/run-now", {})
        except urllib.error.URLError as exc:
            nudged.append(
                {
                    "project_id": project_id,
                    "action": "run_now_failed",
                    "reason": str(exc),
                }
            )
            continue
        nudged.append(
            {
                "project_id": project_id,
                "action": "run_now",
                "launched": bool(result.get("launched")),
                "result": result,
            }
        )
    return nudged


def anticipate_blockers(
    app: Any,
    repeated_failures: Dict[str, Dict[str, Any]],
    *,
    ready_backlog_after: int,
) -> List[Dict[str, Any]]:
    runtime_state_sql = _sql_string_set(sorted(ACTIVE_RUNTIME_TASK_STATES))
    active_keys = active_commitment_keys(app)
    with app.db() as conn:
        project_rows = conn.execute(
            "SELECT id, status, cooldown_until, last_error, current_slice FROM projects ORDER BY id"
        ).fetchall()
        package_rows = conn.execute(
            """
            SELECT project_id, package_id, status, runtime_state, dependencies_json, latest_run_id
            FROM work_packages
            WHERE status IN ('ready', 'failed', 'waiting_dependency', 'awaiting_review', 'review_fix_required')
            ORDER BY project_id, package_id
            """
        ).fetchall()
        running_runtime_rows = conn.execute(
            f"""
            SELECT project_id, package_id, task_state, run_id
            FROM runtime_tasks
            WHERE task_state IN ({runtime_state_sql})
            """
        ).fetchall()
    blockers: List[Dict[str, Any]] = []
    running_packages = {
        str(row["package_id"] or "").strip()
        for row in running_runtime_rows
        if str(row["package_id"] or "").strip()
    }
    running_projects = {
        str(row["project_id"] or "").strip()
        for row in running_runtime_rows
        if str(row["project_id"] or "").strip()
    }
    if int(ready_backlog_after) <= 0:
        blockers.append(
            {
                "kind": "queue_starvation",
                "summary": "No dispatchable ready backlog remains after this OODA pass.",
                "recommended_action": "materialize new runnable work, clear review holds, or release capacity-gated dispatch_pending projects",
            }
        )
    dependents_by_package: Dict[str, int] = {}
    for row in package_rows:
        dependencies = []
        try:
            dependencies = json.loads(str(row["dependencies_json"] or "[]"))
        except Exception:
            dependencies = []
        for package_id in dependencies:
            clean = str(package_id or "").strip()
            if clean:
                dependents_by_package[clean] = int(dependents_by_package.get(clean) or 0) + 1
    for row in project_rows:
        project_id = str(row["id"] or "").strip()
        status = str(row["status"] or "").strip().lower()
        if not project_id:
            continue
        error_text = str(row["last_error"] or "").strip()
        cooldown_until = parse_iso(row["cooldown_until"])
        lowered = error_text.lower()
        if status in {"dispatch_pending", "awaiting_account"} and error_text and any(
            marker in lowered for marker in CAPACITY_ERROR_MARKERS
        ):
            blockers.append(
                {
                    "kind": "capacity_cooldown",
                    "project_id": project_id,
                    "summary": error_text,
                    "cooldown_until": iso(cooldown_until),
                    "recommended_action": "retry after cooldown expiry or free an eligible account/model lane",
                }
            )
        if status in {"awaiting_review", "review_fix_required"}:
            blockers.append(
                {
                    "kind": "review_gate",
                    "project_id": project_id,
                    "summary": str(row["current_slice"] or "").strip() or status,
                    "recommended_action": "close or clear the current review hold before the queue drains behind it",
                }
            )
    for row in package_rows:
        package_id = str(row["package_id"] or "").strip()
        if str(row["status"] or "").strip().lower() != "failed" or not package_id:
            continue
        project_id = str(row["project_id"] or "").strip()
        if package_id in running_packages or project_id in running_projects:
            continue
        downstream = int(dependents_by_package.get(package_id) or 0)
        if downstream <= 0:
            continue
        blockers.append(
            {
                "kind": "head_of_line_failure",
                "project_id": project_id,
                "package_id": package_id,
                "downstream_waiting_packages": downstream,
                "latest_run_id": int(row["latest_run_id"] or 0) or None,
                "recommended_action": "repair or clear the failed head package before dependent slices starve",
            }
        )
    for item in repeated_failures.values():
        package_id = str(item.get("package_id") or "").strip()
        project_id = str(item.get("project_id") or "").strip()
        runtime_key = package_id or project_id
        if runtime_key in active_keys:
            continue
        if package_id and (package_id in running_packages or project_id in running_projects):
            continue
        if not package_id and project_id in running_projects:
            continue
        blockers.append(
            {
                "kind": "repeat_failure",
                "project_id": project_id,
                "package_id": package_id,
                "signature": str(item.get("signature") or ""),
                "count": int(item.get("count") or 0),
                "recommended_action": "repair the recurring verifier or queue truth before retries consume the lane again",
            }
        )
    priority = {
        "queue_starvation": 0,
        "capacity_cooldown": 1,
        "head_of_line_failure": 2,
        "repeat_failure": 3,
        "review_gate": 4,
    }
    blockers.sort(
        key=lambda item: (
            int(priority.get(str(item.get("kind") or ""), 99)),
            str(item.get("project_id") or ""),
            str(item.get("package_id") or ""),
        )
    )
    return blockers[:12]


def pause_guide_if_feedback_backlog_is_empty(
    app: Any,
    config: Dict[str, Any],
    *,
    controller_url: str,
) -> Optional[Dict[str, Any]]:
    project_cfg = app.get_project_cfg(config, "guide")
    feedback_files = app.selected_feedback_files(config, project_cfg)
    with app.db() as conn:
        row = conn.execute("SELECT status, current_slice, active_run_id FROM projects WHERE id='guide'").fetchone()
    if not row:
        return None
    status = str(row["status"] or "").strip().lower()
    if feedback_files or status not in ACTIVE_RUN_STATUSES:
        return None
    current_slice = str(row["current_slice"] or "")
    if current_slice and not current_slice.lower().startswith("fix feedback"):
        return None
    try:
        result = http_post_json(f"{controller_url.rstrip('/')}/api/projects/guide/pause", {})
    except urllib.error.URLError as exc:
        return {
            "project_id": "guide",
            "action": "pause_failed",
            "reason": str(exc),
        }
    return {
        "project_id": "guide",
        "action": "paused_redundant_feedback_run",
        "result": result,
    }


def _is_synthetic_closeout_finding(row: sqlite3.Row) -> bool:
    external_id = str(row["external_id"] or "").strip().lower()
    body = str(row["body"] or "").strip().lower()
    if external_id != "local-review-closeout":
        return False
    synthetic_markers = (
        "missing_final_message",
        "upstream_unavailable:",
        "expected fix: completed local unblock task",
    )
    return any(marker in body for marker in synthetic_markers)


def release_stale_synthetic_review_holds(
    app: Any,
    *,
    stale_minutes: int,
) -> List[Dict[str, Any]]:
    cutoff = utc_now() - dt.timedelta(minutes=max(1, int(stale_minutes)))
    released: List[Dict[str, Any]] = []
    with app.db() as conn:
        projects = conn.execute(
            """
            SELECT id, status, current_slice, last_run_at, last_error, consecutive_failures,
                   spider_tier, spider_model, spider_reason, updated_at
            FROM projects
            WHERE EXISTS (
                SELECT 1
                FROM pull_requests pr
                WHERE pr.project_id = projects.id
                  AND pr.review_status IN ('local_review', 'review_fix_required')
            )
            ORDER BY id
            """
        ).fetchall()
    for project_row in projects:
        project_id = str(project_row["id"] or "").strip()
        if not project_id:
            continue
        with app.db() as conn:
            pr_rows = conn.execute(
                """
                SELECT id, package_id, pr_number, review_status, review_requested_at, review_completed_at,
                       local_review_last_at, updated_at, review_findings_count, review_blocking_findings_count
                FROM pull_requests
                WHERE project_id=?
                ORDER BY id
                """,
                (project_id,),
            ).fetchall()
        if not pr_rows:
            continue
        review_statuses = {str(pr_row["review_status"] or "").strip().lower() for pr_row in pr_rows}
        project_hold_status = "review_fix_required" if "review_fix_required" in review_statuses else "local_review"
        if project_hold_status not in {"local_review", "review_fix_required"}:
            continue
        aged_at = max(
            (
                parse_iso(pr_row["review_completed_at"])
                or parse_iso(pr_row["local_review_last_at"])
                or parse_iso(pr_row["review_requested_at"])
                or parse_iso(pr_row["updated_at"])
                for pr_row in pr_rows
            ),
            default=None,
        )
        if aged_at is None or aged_at > cutoff:
            continue
        with app.db() as conn:
            finding_rows = conn.execute(
                """
                SELECT project_id, pr_number, external_id, body, blocking, updated_at, created_at
                FROM review_findings
                WHERE project_id=?
                ORDER BY pr_number, id
                """,
                (project_id,),
            ).fetchall()
        if project_hold_status == "local_review":
            has_findings = any(int(pr_row["review_findings_count"] or 0) > 0 or int(pr_row["review_blocking_findings_count"] or 0) > 0 for pr_row in pr_rows)
            if has_findings or finding_rows:
                continue
        elif project_hold_status == "review_fix_required":
            if not finding_rows or any(not _is_synthetic_closeout_finding(row) for row in finding_rows):
                continue
        else:
            continue
        now_text = iso(utc_now())
        with app.db() as conn:
            if finding_rows:
                conn.execute("DELETE FROM review_findings WHERE project_id=?", (project_id,))
            conn.execute(
                """
                UPDATE pull_requests
                SET review_status='clean',
                    review_completed_at=COALESCE(review_completed_at, ?),
                    local_review_last_at=COALESCE(local_review_last_at, ?),
                    review_findings_count=0,
                    review_blocking_findings_count=0,
                    next_retry_at=NULL,
                    updated_at=?
                WHERE project_id=?
                """,
                (now_text, now_text, now_text, project_id),
            )
            conn.execute(
                """
                UPDATE projects
                SET status='ready',
                    active_run_id=NULL,
                    updated_at=?
                WHERE id=?
                """,
                (now_text, project_id),
            )
        released.append(
            {
                "project_id": project_id,
                "project_status": project_hold_status,
                "pr_count": len(pr_rows),
                "finding_count": len(finding_rows),
                "released_at": now_text,
            }
        )
    return released


def release_stale_zero_finding_local_reviews(
    app: Any,
    config: Dict[str, Any],
    *,
    stale_minutes: int,
) -> List[Dict[str, Any]]:
    cutoff = utc_now() - dt.timedelta(minutes=max(1, int(stale_minutes)))
    with app.db() as conn:
        rows = conn.execute(
            """
            SELECT pr.id AS pr_id,
                   pr.project_id,
                   pr.package_id,
                   pr.pr_number,
                   pr.review_status,
                   pr.review_requested_at,
                   pr.review_completed_at,
                   pr.local_review_last_at,
                   wp.status AS package_status,
                   wp.runtime_state AS package_runtime_state,
                   wp.latest_run_id,
                   runs.status AS run_status,
                   runs.verify_exit_code,
                   runs.finished_at AS run_finished_at,
                   runs.error_message
            FROM pull_requests pr
            JOIN work_packages wp
              ON wp.package_id = pr.package_id
             AND wp.project_id = pr.project_id
            LEFT JOIN runs
              ON runs.id = wp.latest_run_id
            WHERE pr.review_status IN ('local_review', 'clean')
              AND pr.review_findings_count = 0
              AND pr.review_blocking_findings_count = 0
              AND wp.status IN ('awaiting_review', 'review_requested', 'local_review')
              AND wp.runtime_state = 'awaiting_review'
            ORDER BY pr.project_id, pr.package_id, pr.id
            """
        ).fetchall()
    released: List[Dict[str, Any]] = []
    for row in rows:
        project_id = str(row["project_id"] or "").strip()
        package_id = str(row["package_id"] or "").strip()
        if not project_id or not package_id:
            continue
        latest_run_id = int(row["latest_run_id"] or 0) or None
        verify_exit_code = row["verify_exit_code"]
        if latest_run_id is None or verify_exit_code != 0:
            continue
        package_status = str(row["package_status"] or "").strip().lower()
        package_runtime_state = str(row["package_runtime_state"] or "").strip().lower()
        if package_status not in {"awaiting_review", "review_requested", "local_review"}:
            continue
        if package_runtime_state != "awaiting_review":
            continue
        aged_at = (
            parse_iso(row["review_completed_at"])
            or parse_iso(row["local_review_last_at"])
            or parse_iso(row["review_requested_at"])
            or parse_iso(row["run_finished_at"])
        )
        if aged_at is None or aged_at > cutoff:
            continue
        with app.db() as conn:
            finding_row = conn.execute(
                """
                SELECT COUNT(1) AS finding_count,
                       MAX(COALESCE(updated_at, created_at)) AS latest_finding_at
                FROM review_findings
                WHERE project_id=? AND pr_number=?
                """,
                (project_id, int(row["pr_number"] or 0)),
            ).fetchone()
        finding_count = int(finding_row["finding_count"] or 0)
        latest_finding_at = parse_iso(finding_row["latest_finding_at"])
        if finding_count and (latest_finding_at is None or latest_finding_at >= aged_at):
            continue
        completed_at = parse_iso(row["run_finished_at"]) or utc_now()
        now_text = iso(utc_now())
        with app.db() as conn:
            if finding_count:
                conn.execute(
                    "DELETE FROM review_findings WHERE project_id=? AND pr_number=?",
                    (project_id, int(row["pr_number"] or 0)),
                )
            conn.execute(
                """
                UPDATE pull_requests
                SET review_status='clean',
                    review_completed_at=COALESCE(review_completed_at, ?),
                    local_review_last_at=COALESCE(local_review_last_at, ?),
                    updated_at=?
                WHERE id=?
                """,
                (now_text, now_text, now_text, int(row["pr_id"] or 0)),
            )
        app.update_work_package_runtime(
            package_id,
            status="complete",
            runtime_state="idle",
            latest_run_id=latest_run_id,
            completed_at=completed_at,
        )
        released.append(
            {
                "project_id": project_id,
                "package_id": package_id,
                "pr_id": int(row["pr_id"] or 0),
                "pr_number": int(row["pr_number"] or 0),
                "latest_run_id": latest_run_id,
                "released_at": now_text,
            }
        )
    if released:
        app.sync_work_packages_to_db(config)
        app.reconcile_stuck_work_package_runtime_links()
        app.save_runtime_task_cache_snapshot()
    return released


def release_orphaned_active_scope_claims(app: Any) -> List[Dict[str, Any]]:
    now_text = iso(utc_now())
    released: List[Dict[str, Any]] = []
    runtime_state_sql = _sql_string_set(sorted(ACTIVE_RUNTIME_TASK_STATES))
    run_status_sql = _sql_string_set(sorted(ACTIVE_RUN_STATUSES))
    with app.db() as conn:
        rows = conn.execute(
            f"""
            SELECT sc.id,
                   sc.package_id,
                   sc.project_id,
                   sc.claim_type,
                   sc.claim_value,
                   wp.status AS package_status,
                   wp.runtime_state AS package_runtime_state,
                   rt.task_state AS runtime_task_state,
                   r.status AS run_status
            FROM scope_claims sc
            LEFT JOIN work_packages wp
              ON wp.package_id = sc.package_id
             AND wp.project_id = sc.project_id
            LEFT JOIN runtime_tasks rt
              ON rt.package_id = sc.package_id
             AND rt.task_state IN ({runtime_state_sql})
            LEFT JOIN runs r
              ON r.package_id = sc.package_id
             AND r.status IN ({run_status_sql})
             AND r.finished_at IS NULL
            WHERE sc.claim_state = 'active'
            ORDER BY sc.project_id, sc.package_id, sc.id
            """
        ).fetchall()
        orphan_ids: List[int] = []
        for row in rows:
            if str(row["runtime_task_state"] or "").strip().lower() in ACTIVE_RUNTIME_TASK_STATES:
                continue
            if str(row["run_status"] or "").strip().lower() in ACTIVE_RUN_STATUSES:
                continue
            package_status = str(row["package_status"] or "").strip().lower()
            package_runtime_state = str(row["package_runtime_state"] or "").strip().lower()
            if package_status not in {"archived", "complete", "completed_signed_off", "scaffold_complete"} and package_runtime_state not in {"", "idle"}:
                continue
            claim_id = int(row["id"])
            orphan_ids.append(claim_id)
            released.append(
                {
                    "scope_claim_id": claim_id,
                    "package_id": str(row["package_id"] or ""),
                    "project_id": str(row["project_id"] or ""),
                    "claim_type": str(row["claim_type"] or ""),
                    "claim_value": str(row["claim_value"] or ""),
                    "released_at": now_text,
                }
            )
        if orphan_ids:
            conn.executemany(
                """
                UPDATE scope_claims
                SET claim_state='released',
                    released_at=?
                WHERE id=?
                """,
                [(now_text, claim_id) for claim_id in orphan_ids],
            )
    return released


def run_once(app: Any, args: argparse.Namespace, state_root: Path) -> Dict[str, Any]:
    workspace_root = Path(str(args.workspace_root or DEFAULT_WORKSPACE_ROOT)).resolve()
    config = app.normalize_config()
    app.sync_config_to_db(config)
    app.sync_work_packages_to_db(config)
    autohealed_drift_actions = autoheal_queue_scope_drift(
        app,
        workspace_root=workspace_root,
        controller_url=str(args.controller_url),
    )
    released_orphan_scope_claims = release_orphaned_active_scope_claims(app)
    pruned_stale_commitment_count = prune_stale_runtime_commitments(
        workspace_root,
        stale_hours=int(args.stale_runtime_hours),
    )
    healed_stale_runtime_count = int(app.reconcile_stale_worker_sessions(config) or 0)
    app.reconcile_stuck_work_package_runtime_links()
    app.save_runtime_task_cache_snapshot()
    app.request_due_group_audits(config)
    app.auto_publish_approved_audit_candidates(config)
    healed_local_reviews = int(app.heal_orphaned_local_reviews(config) or 0)
    released_review_holds = release_stale_zero_finding_local_reviews(
        app,
        config,
        stale_minutes=int(args.stale_local_review_minutes),
    )
    released_review_holds.extend(
        release_stale_synthetic_review_holds(
            app,
            stale_minutes=int(args.stale_local_review_minutes),
        )
    )
    transient_retries = auto_retry_transient_dispatch_pending_projects(
        app,
        controller_url=str(args.controller_url),
        repeated_failures=repeated_failures,
    )
    autohealed_drift_actions.extend(
        autoheal_worktree_and_receipt_drift(
            app,
            controller_url=str(args.controller_url),
        )
    )
    repeated_failures = repeated_failure_map(
        app,
        lookback_minutes=int(args.failure_lookback_minutes),
        threshold=int(args.repeat_failure_threshold),
    )
    ready_before = ready_backlog_count(app, config, repeated_failures)
    guide_pause = pause_guide_if_feedback_backlog_is_empty(app, config, controller_url=str(args.controller_url))
    launched = schedule_to_target(
        app,
        config,
        target_active=int(args.target_active),
        repeated_failures=repeated_failures,
    )
    nudged_ready_projects = nudge_ready_projects(
        app,
        controller_url=str(args.controller_url),
        repeated_failures=repeated_failures,
        target_active=int(args.target_active),
    )
    generated_at = iso_now()
    committed_after = sorted(active_commitment_keys(app))
    ready_after = ready_backlog_count(app, config, repeated_failures)
    blockers = blocker_summary(app, repeated_failures)
    imminent_blockers = anticipate_blockers(app, repeated_failures, ready_backlog_after=ready_after)
    repeated_failure_counts = {
        key: int((value or {}).get("count") or 0)
        for key, value in repeated_failures.items()
    }
    last_action_kind = "observe"
    if launched:
        last_action_kind = "launch"
    elif nudged_ready_projects:
        last_action_kind = "nudge_ready"
    elif autohealed_drift_actions:
        last_action_kind = "autoheal_drift"
    elif transient_retries:
        last_action_kind = "transient_retry"
    elif pruned_stale_commitment_count or healed_stale_runtime_count or healed_local_reviews or released_review_holds or released_orphan_scope_claims:
        last_action_kind = "cleanup"
    elif guide_pause:
        last_action_kind = "guide_pause"
    last_action = {
        "kind": last_action_kind,
        "launch_count": len(launched),
        "ready_nudge_count": len(nudged_ready_projects),
        "pruned_stale_commitment_count": pruned_stale_commitment_count,
        "healed_stale_runtime_count": healed_stale_runtime_count,
        "healed_local_review_count": healed_local_reviews,
        "released_review_hold_count": len(released_review_holds),
        "released_orphan_scope_claim_count": len(released_orphan_scope_claims),
        "transient_retry_count": len(transient_retries),
        "autohealed_drift_action_count": len(autohealed_drift_actions),
        "guide_pause": bool(guide_pause),
    }
    payload = {
        "generated_at": generated_at,
        "updated_at": generated_at,
        "target_active": int(args.target_active),
        "ready_backlog_floor": int(args.ready_backlog_floor),
        "committed_active": len(committed_after),
        "ready_backlog_before": ready_before,
        "ready_backlog_after": ready_after,
        "launched": launched,
        "nudged_ready_projects": nudged_ready_projects,
        "pruned_stale_commitment_count": pruned_stale_commitment_count,
        "healed_stale_runtime_count": healed_stale_runtime_count,
        "healed_local_review_count": healed_local_reviews,
        "released_review_holds": released_review_holds,
        "released_orphan_scope_claims": released_orphan_scope_claims,
        "transient_retries": transient_retries,
        "autohealed_drift_actions": autohealed_drift_actions,
        "guide_pause": guide_pause or {},
        "repeated_failures": repeated_failures,
        "repeated_failure_counts": repeated_failure_counts,
        "top_blockers": blockers,
        "imminent_blockers": imminent_blockers,
        "last_action": last_action,
        "healthy": len(committed_after) >= int(args.target_active) and ready_after >= int(args.ready_backlog_floor),
        "ooda": {
            "observe": {
                "committed_active": len(committed_after),
                "ready_backlog": ready_after,
                "repeated_failure_keys": sorted(repeated_failures.keys()),
                "repeated_failure_projects": sorted({str(item.get("project_id") or "") for item in repeated_failures.values() if str(item.get("project_id") or "")}),
            },
            "orient": {
                "utilization_gap": max(0, int(args.target_active) - len(committed_after)),
                "backlog_gap": max(0, int(args.ready_backlog_floor) - ready_after),
            },
            "decide": {
                "pause_guide": bool(guide_pause),
                "launch_count": len(launched),
                "ready_nudge_count": len(nudged_ready_projects),
                "pruned_stale_commitment_count": pruned_stale_commitment_count,
                "healed_stale_runtime_count": healed_stale_runtime_count,
                "healed_local_review_count": healed_local_reviews,
                "released_review_hold_count": len(released_review_holds),
                "released_orphan_scope_claim_count": len(released_orphan_scope_claims),
            },
            "act": {
                "launched": launched,
                "nudged_ready_projects": nudged_ready_projects,
                "pruned_stale_commitment_count": pruned_stale_commitment_count,
                "healed_stale_runtime_count": healed_stale_runtime_count,
                "healed_local_review_count": healed_local_reviews,
                "released_review_holds": released_review_holds,
                "released_orphan_scope_claims": released_orphan_scope_claims,
                "guide_pause": guide_pause or {},
            },
        },
    }
    write_json(state_root / "state.json", payload)
    append_event(
        state_root / "events.jsonl",
        {
            "generated_at": payload["generated_at"],
            "committed_active": payload["committed_active"],
            "ready_backlog_after": ready_after,
            "launch_count": len(launched),
            "ready_nudge_count": len(nudged_ready_projects),
            "pruned_stale_commitment_count": pruned_stale_commitment_count,
            "healed_stale_runtime_count": healed_stale_runtime_count,
            "healed_local_review_count": healed_local_reviews,
            "released_review_hold_count": len(released_review_holds),
            "released_orphan_scope_claim_count": len(released_orphan_scope_claims),
            "guide_pause": bool(guide_pause),
            "repeat_failure_keys": sorted(repeated_failures.keys()),
            "repeat_failure_projects": sorted({str(item.get("project_id") or "") for item in repeated_failures.values() if str(item.get("project_id") or "")}),
        },
    )
    return payload


def main() -> int:
    args = parse_args()
    controller_dir = Path(args.controller_dir).resolve()
    state_root = Path(args.state_root).resolve()
    state_root.mkdir(parents=True, exist_ok=True)
    app = load_controller_app(controller_dir)

    if args.once:
        payload = run_once(app, args, state_root)
        print(
            json.dumps(
                {
                    "generated_at": payload["generated_at"],
                    "committed_active": payload["committed_active"],
                    "ready_backlog_after": payload["ready_backlog_after"],
                    "launch_count": len(payload["launched"]),
                    "ready_nudge_count": len(payload["nudged_ready_projects"]),
                    "pruned_stale_commitment_count": payload["pruned_stale_commitment_count"],
                    "healed_stale_runtime_count": payload["healed_stale_runtime_count"],
                    "healed_local_review_count": payload["healed_local_review_count"],
                    "released_review_hold_count": len(payload["released_review_holds"]),
                    "released_orphan_scope_claim_count": len(payload["released_orphan_scope_claims"]),
                    "repeat_failure_keys": sorted(payload["repeated_failures"].keys()),
                    "repeat_failure_projects": sorted({str(item.get("project_id") or "") for item in payload["repeated_failures"].values() if str(item.get("project_id") or "")}),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    end_time = None if args.forever else time.time() + max(1, int(args.duration_seconds))
    while True:
        run_once(app, args, state_root)
        if end_time is not None and time.time() >= end_time:
            return 0
        time.sleep(max(5, int(args.poll_seconds)))


if __name__ == "__main__":
    raise SystemExit(main())
