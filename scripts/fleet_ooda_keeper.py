#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


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
DEFAULT_CONTROLLER_URL = "http://127.0.0.1:8090" if RUNNING_IN_CONTROLLER_CONTAINER else "http://127.0.0.1:18090"
DEFAULT_TARGET_ACTIVE = 13
DEFAULT_READY_BACKLOG_FLOOR = 10
DEFAULT_POLL_SECONDS = 10 * 60
DEFAULT_DURATION_SECONDS = 12 * 7 * 24 * 60 * 60
DEFAULT_FAILURE_LOOKBACK_MINUTES = 90
DEFAULT_REPEAT_FAILURE_THRESHOLD = 3
DEFAULT_STALE_LOCAL_REVIEW_MINUTES = 10

ACTIVE_RUN_STATUSES = {"starting", "running", "verifying", "healing", "local_review"}
ACTIVE_RUNTIME_TASK_STATES = {"scheduled", "running"}
THROTTLED_PROJECT_STATUSES = {
    "review_requested",
    "awaiting_pr",
    "awaiting_review",
    "review_fix_required",
    "review_failed",
    "waiting_dependency",
}
CAPACITY_ERROR_MARKERS = {"capacity", "account", "budget", "runway", "pool", "cooldown", "rate limit"}


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


def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_event(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def load_controller_app(controller_dir: Path) -> Any:
    resolved = controller_dir.resolve()
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


def repeated_failure_map(app: Any, *, lookback_minutes: int, threshold: int) -> Dict[str, Dict[str, Any]]:
    cutoff = utc_now() - dt.timedelta(minutes=max(1, lookback_minutes))
    blocked: Dict[str, Dict[str, Any]] = {}
    active_keys = active_commitment_keys(app)
    with app.db() as conn:
        rows = conn.execute(
            """
            SELECT runs.project_id,
                   COALESCE(runs.package_id, '') AS package_id,
                   COALESCE(runs.error_class, '') AS error_class,
                   COALESCE(runs.error_message, '') AS error_message,
                   runs.finished_at,
                   COALESCE(wp.status, '') AS package_status,
                   COALESCE(projects.status, '') AS project_status
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
    grouped: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = {}
    for row in rows:
        project_id = str(row["project_id"] or "").strip()
        if not project_id:
            continue
        package_id = str(row["package_id"] or "").strip()
        package_status = str(row["package_status"] or "").strip().lower()
        project_status = str(row["project_status"] or "").strip().lower()
        runtime_key = package_id or project_id
        if runtime_key in active_keys:
            continue
        if package_id and package_status in {"complete", "completed_signed_off", "scaffold_complete", "archived"}:
            continue
        if not package_id and project_status in {"complete", "completed_signed_off", "scaffold_complete"}:
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
    with app.db() as conn:
        runtime_rows = conn.execute(
            """
            SELECT package_id, project_id
            FROM runtime_tasks
            WHERE task_state IN ('scheduled', 'running')
            ORDER BY project_id, package_id
            """
        ).fetchall()
        run_rows = conn.execute(
            """
            SELECT COALESCE(package_id, project_id) AS runtime_key
            FROM runs
            WHERE status IN ('starting', 'running', 'verifying', 'healing', 'local_review')
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
    blockers: List[Dict[str, Any]] = []
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
        downstream = int(dependents_by_package.get(package_id) or 0)
        if downstream <= 0:
            continue
        blockers.append(
            {
                "kind": "head_of_line_failure",
                "project_id": str(row["project_id"] or "").strip(),
                "package_id": package_id,
                "downstream_waiting_packages": downstream,
                "latest_run_id": int(row["latest_run_id"] or 0) or None,
                "recommended_action": "repair or clear the failed head package before dependent slices starve",
            }
        )
    for item in repeated_failures.values():
        blockers.append(
            {
                "kind": "repeat_failure",
                "project_id": str(item.get("project_id") or ""),
                "package_id": str(item.get("package_id") or ""),
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
        if not app.project_uses_package_scheduler(config, project_id):
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
            finding_count = int(
                conn.execute(
                    "SELECT COUNT(1) FROM review_findings WHERE project_id=? AND pr_number=?",
                    (project_id, int(row["pr_number"] or 0)),
                ).fetchone()[0]
                or 0
            )
        if finding_count:
            continue
        completed_at = parse_iso(row["run_finished_at"]) or utc_now()
        now_text = iso(utc_now())
        with app.db() as conn:
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


def run_once(app: Any, args: argparse.Namespace, state_root: Path) -> Dict[str, Any]:
    config = app.normalize_config()
    app.sync_config_to_db(config)
    app.sync_work_packages_to_db(config)
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
    committed_after = sorted(active_commitment_keys(app))
    ready_after = ready_backlog_count(app, config, repeated_failures)
    blockers = blocker_summary(app, repeated_failures)
    imminent_blockers = anticipate_blockers(app, repeated_failures, ready_backlog_after=ready_after)
    payload = {
        "generated_at": iso_now(),
        "target_active": int(args.target_active),
        "ready_backlog_floor": int(args.ready_backlog_floor),
        "committed_active": len(committed_after),
        "ready_backlog_before": ready_before,
        "ready_backlog_after": ready_after,
        "launched": launched,
        "nudged_ready_projects": nudged_ready_projects,
        "healed_local_review_count": healed_local_reviews,
        "released_review_holds": released_review_holds,
        "guide_pause": guide_pause or {},
        "repeated_failures": repeated_failures,
        "top_blockers": blockers,
        "imminent_blockers": imminent_blockers,
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
                "healed_local_review_count": healed_local_reviews,
                "released_review_hold_count": len(released_review_holds),
            },
            "act": {
                "launched": launched,
                "nudged_ready_projects": nudged_ready_projects,
                "healed_local_review_count": healed_local_reviews,
                "released_review_holds": released_review_holds,
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
            "healed_local_review_count": healed_local_reviews,
            "released_review_hold_count": len(released_review_holds),
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
                    "healed_local_review_count": payload["healed_local_review_count"],
                    "released_review_hold_count": len(payload["released_review_holds"]),
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
