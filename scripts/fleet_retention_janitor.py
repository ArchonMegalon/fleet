#!/usr/bin/env python3
"""Evidence-gated cleanup for Fleet-owned transient run artifacts.

This module intentionally knows about only two managed artifact families:
package worktrees recorded in Fleet's database and run files recorded on the
same package's terminal runs.  Unknown directories, shared caches, Docker,
queue-recovery receipts, Codex homes, and vexp infrastructure are outside its
authority.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import sqlite3
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Sequence


UTC = dt.timezone.utc
ACTIVE_RUN_STATUSES = {"starting", "running", "verifying", "healing", "local_review"}
ACTIVE_RUNTIME_TASK_STATES = {"starting", "scheduled", "running", "verifying", "awaiting_review"}
TERMINAL_PACKAGE_STATUSES = {"archived", "complete", "completed_signed_off", "scaffold_complete"}
VERIFIED_REVIEW_STATUSES = {"accepted", "approved", "clean", "complete", "landed"}
FULL_SHA_RE = re.compile(r"^[0-9a-fA-F]{40,64}$")


@dataclass(frozen=True)
class RetentionPolicy:
    mode: str = "apply"
    interval_hours: int = 6
    worktree_min_age_hours: int = 24
    log_min_age_hours: int = 7 * 24
    keep_run_artifacts_per_package: int = 2
    max_worktrees_per_pass: int = 4
    max_artifacts_per_pass: int = 32
    max_candidates_per_pass: int = 32
    max_receipt_entries: int = 128


def utc_now() -> dt.datetime:
    return dt.datetime.now(UTC)


def iso(value: dt.datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(value: object) -> Optional[dt.datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _path_mentions_vexp(path: Path) -> bool:
    lexical = tuple(part.lower() for part in path.parts)
    resolved = tuple(part.lower() for part in path.resolve(strict=False).parts)
    return ".vexp" in lexical or ".vexp" in resolved


def _managed_path(path: Path, root: Path) -> bool:
    if _path_mentions_vexp(path) or _path_mentions_vexp(root):
        return False
    resolved = path.resolve(strict=False)
    resolved_root = root.resolve(strict=False)
    if resolved == resolved_root:
        return False
    try:
        resolved.relative_to(resolved_root)
    except ValueError:
        return False
    return True


def _process_cwd_uses(path: Path, *, proc_root: Path = Path("/proc")) -> bool:
    target = path.resolve(strict=False)
    try:
        processes = tuple(proc_root.iterdir())
    except OSError:
        return True
    for process in processes:
        if not process.name.isdigit():
            continue
        try:
            cwd = (process / "cwd").resolve(strict=True)
        except (FileNotFoundError, OSError, PermissionError, RuntimeError):
            continue
        if cwd == target:
            return True
        try:
            cwd.relative_to(target)
        except ValueError:
            continue
        return True
    return False


def _git(repo: Path, args: Sequence[str], *, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def _git_ok(repo: Path, args: Sequence[str], *, timeout: int = 60) -> tuple[bool, str]:
    try:
        result = _git(repo, args, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return False, ""
    return result.returncode == 0, str(result.stdout or "").strip()


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (table,),
    ).fetchone()
    return bool(row)


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not _table_exists(conn, table):
        return set()
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _candidate_rows(conn: sqlite3.Connection, *, limit: int) -> list[Dict[str, Any]]:
    required = {
        "projects": {"id", "path", "status", "active_run_id"},
        "work_packages": {
            "package_id",
            "project_id",
            "status",
            "runtime_state",
            "worktree_root",
            "completed_at",
        },
        "pull_requests": {
            "package_id",
            "base_branch",
            "review_status",
            "review_completed_at",
            "landed_at",
            "landed_sha",
            "landing_lane",
            "landing_error",
        },
        "runs": {"id", "project_id", "package_id", "status", "finished_at"},
        "runtime_tasks": {"project_id", "package_id", "task_state"},
    }
    for table, columns in required.items():
        if not columns.issubset(_table_columns(conn, table)):
            raise RuntimeError(f"retention_janitor_schema_missing:{table}")
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT wp.package_id,
               wp.project_id,
               wp.status AS package_status,
               wp.runtime_state,
               wp.worktree_root,
               wp.completed_at,
               p.path AS project_path,
               p.status AS project_status,
               p.active_run_id,
               pr.base_branch,
               pr.review_status,
               pr.review_completed_at,
               pr.landed_at,
               pr.landed_sha,
               pr.landing_lane,
               pr.landing_error,
               EXISTS(
                   SELECT 1 FROM runtime_tasks rt
                   WHERE rt.project_id=wp.project_id
                     AND COALESCE(rt.package_id, '')=wp.package_id
                     AND rt.task_state IN ('starting','scheduled','running','verifying','awaiting_review')
               ) AS has_active_runtime,
               EXISTS(
                   SELECT 1 FROM runs r
                   WHERE r.project_id=wp.project_id
                     AND COALESCE(r.package_id, '')=wp.package_id
                     AND r.status IN ('starting','running','verifying','healing','local_review')
                     AND r.finished_at IS NULL
               ) AS has_active_run
        FROM work_packages wp
        JOIN projects p ON p.id=wp.project_id
        LEFT JOIN pull_requests pr ON pr.package_id=wp.package_id
        WHERE COALESCE(wp.worktree_root, '') != ''
        ORDER BY COALESCE(pr.landed_at, wp.completed_at, '') ASC, wp.package_id ASC
        LIMIT ?
        """,
        (max(1, int(limit)),),
    ).fetchall()
    return [dict(row) for row in rows]


def _authority_gate(row: Dict[str, Any], *, cutoff: dt.datetime) -> str:
    if str(row.get("package_status") or "").strip().lower() not in TERMINAL_PACKAGE_STATUSES:
        return "package_not_terminal"
    if str(row.get("runtime_state") or "").strip().lower() not in {"", "idle"}:
        return "package_runtime_active"
    if str(row.get("project_status") or "").strip().lower() in ACTIVE_RUN_STATUSES:
        return "project_active"
    if int(row.get("active_run_id") or 0):
        return "project_active_run_link"
    if bool(row.get("has_active_runtime")):
        return "runtime_task_active"
    if bool(row.get("has_active_run")):
        return "run_active"
    if str(row.get("review_status") or "").strip().lower() not in VERIFIED_REVIEW_STATUSES:
        return "review_not_verified"
    if parse_iso(row.get("review_completed_at")) is None:
        return "review_receipt_missing"
    landed_at = parse_iso(row.get("landed_at"))
    if landed_at is None:
        return "landing_receipt_missing"
    if landed_at > cutoff:
        return "worktree_grace_period"
    landed_sha = str(row.get("landed_sha") or "").strip()
    if not FULL_SHA_RE.fullmatch(landed_sha):
        return "landing_sha_invalid"
    if not str(row.get("landing_lane") or "").strip():
        return "landing_lane_missing"
    if str(row.get("landing_error") or "").strip():
        return "landing_error_present"
    if not str(row.get("base_branch") or "").strip():
        return "base_branch_missing"
    return ""


def _worktree_record(repo: Path, worktree: Path) -> Optional[Dict[str, str]]:
    ok, output = _git_ok(repo, ["worktree", "list", "--porcelain"])
    if not ok:
        return None
    records: list[Dict[str, str]] = []
    current: Dict[str, str] = {}
    for line in output.splitlines() + [""]:
        if not line.strip():
            if current:
                records.append(current)
            current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value.strip() if value else "1"
    wanted = worktree.resolve(strict=False)
    for record in records:
        raw = str(record.get("worktree") or "").strip()
        if raw and Path(raw).resolve(strict=False) == wanted:
            return record
    return None


def _prepare_local_worktree_proof(repo: Path, worktree: Path, *, base_branch: str) -> tuple[Dict[str, str], str]:
    if not worktree.exists():
        return {}, ""
    if worktree.is_symlink():
        return {}, "worktree_symlink"
    record = _worktree_record(repo, worktree)
    if record is None:
        return {}, "worktree_unregistered"
    if "locked" in record:
        return {}, "worktree_locked"
    if "prunable" in record:
        return {}, "worktree_marked_prunable"
    if _process_cwd_uses(worktree):
        return {}, "worktree_process_active"
    ok, status = _git_ok(worktree, ["status", "--porcelain=v1", "--untracked-files=all"])
    if not ok:
        return {}, "worktree_status_unavailable"
    if status:
        return {}, "worktree_dirty"
    ok, branch = _git_ok(worktree, ["branch", "--show-current"])
    if not ok or not branch:
        return {}, "worktree_branch_missing"
    if branch == base_branch:
        return {}, "worktree_uses_base_branch"
    ok, head_sha = _git_ok(worktree, ["rev-parse", "HEAD"])
    if not ok or not FULL_SHA_RE.fullmatch(head_sha):
        return {}, "worktree_head_invalid"
    record_branch = str(record.get("branch") or "").removeprefix("refs/heads/")
    if record_branch and record_branch != branch:
        return {}, "worktree_branch_registration_mismatch"
    return {"branch": branch, "head_sha": head_sha}, ""


def _fetch_remote_head(repo: Path, base_branch: str, *, token: str) -> tuple[str, str]:
    ok, _ = _git_ok(repo, ["check-ref-format", "--branch", base_branch])
    if not ok:
        return "", "base_branch_invalid"
    temp_ref = f"refs/fleet-retention-janitor/{token}"
    try:
        ok, _ = _git_ok(
            repo,
            [
                "fetch",
                "--quiet",
                "--no-tags",
                "--no-write-fetch-head",
                "origin",
                f"+refs/heads/{base_branch}:{temp_ref}",
            ],
            timeout=120,
        )
        if not ok:
            return "", "remote_fetch_failed"
        ok, remote_sha = _git_ok(repo, ["rev-parse", temp_ref])
        if not ok or not FULL_SHA_RE.fullmatch(remote_sha):
            return "", "remote_head_invalid"
        return remote_sha, ""
    finally:
        _git_ok(repo, ["update-ref", "-d", temp_ref])


def _is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    try:
        result = _git(repo, ["merge-base", "--is-ancestor", ancestor, descendant], timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _eligible_run_artifacts(
    conn: sqlite3.Connection,
    *,
    package_id: str,
    log_root: Path,
    cutoff: dt.datetime,
    keep: int,
    limit: int,
) -> list[Dict[str, Any]]:
    if int(limit) <= 0:
        return []
    columns = _table_columns(conn, "runs")
    required = {"id", "package_id", "status", "finished_at", "log_path", "final_message_path", "prompt_path"}
    if not required.issubset(columns):
        return []
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT id, status, finished_at, log_path, final_message_path, prompt_path
        FROM runs
        WHERE COALESCE(package_id, '')=?
        ORDER BY id DESC
        """,
        (package_id,),
    ).fetchall()
    artifacts: list[Dict[str, Any]] = []
    retained_terminal_runs = 0
    for row in rows:
        status = str(row["status"] or "").strip().lower()
        finished_at = parse_iso(row["finished_at"])
        if status in ACTIVE_RUN_STATUSES or finished_at is None:
            continue
        if retained_terminal_runs < max(0, int(keep)):
            retained_terminal_runs += 1
            continue
        if finished_at > cutoff:
            continue
        for field in ("log_path", "prompt_path", "final_message_path"):
            raw = str(row[field] or "").strip()
            if not raw:
                continue
            path = Path(raw)
            if not _managed_path(path, log_root):
                continue
            if not path.exists() or path.is_symlink() or not path.is_file():
                continue
            try:
                modified_at = dt.datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
            except OSError:
                continue
            if modified_at > cutoff:
                continue
            artifacts.append(
                {
                    "run_id": int(row["id"]),
                    "field": field,
                    "path": path,
                    "bytes": int(path.stat().st_size),
                    "sha256": _file_digest(path),
                }
            )
            if len(artifacts) >= max(0, int(limit)):
                return artifacts
    return artifacts


def _remove_empty_parent(path: Path, *, stop: Path) -> None:
    current = path
    stop_resolved = stop.resolve(strict=False)
    while current.resolve(strict=False) != stop_resolved:
        if not _managed_path(current, stop):
            return
        try:
            current.rmdir()
        except OSError:
            return
        current = current.parent


def _write_latest_receipt(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    previous_sha = ""
    if path.is_file() and not path.is_symlink():
        try:
            previous_sha = _file_digest(path)
        except OSError:
            previous_sha = ""
    if previous_sha:
        payload["previous_receipt_sha256"] = previous_sha
    temp = path.with_name(f".{path.name}.tmp")
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    try:
        if temp.is_symlink() or (temp.exists() and not temp.is_file()):
            raise RuntimeError("retention_receipt_temp_path_unsafe")
        try:
            temp.unlink()
        except FileNotFoundError:
            pass
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(temp, flags, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass


def _recent_receipt_blocks_run(path: Path, *, mode: str, now: dt.datetime, interval_hours: int) -> bool:
    if interval_hours <= 0 or not path.is_file() or path.is_symlink():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return False
    if str(payload.get("mode") or "") != mode:
        return False
    if str(payload.get("status") or "") not in {"applied", "dry_run", "no_candidates"}:
        return False
    generated_at = parse_iso(payload.get("generated_at"))
    return bool(generated_at and generated_at >= now - dt.timedelta(hours=interval_hours))


def _append_bounded(target: list[Dict[str, Any]], item: Dict[str, Any], *, limit: int) -> None:
    if len(target) < max(0, int(limit)):
        target.append(item)


def write_retention_error_receipt(
    state_root: Path,
    *,
    mode: str,
    error: str,
    now: Optional[dt.datetime] = None,
) -> Dict[str, Any]:
    generated_at = (now or utc_now()).astimezone(UTC)
    receipt = {
        "contract_name": "fleet.retention_janitor.receipt",
        "schema_version": 1,
        "generated_at": iso(generated_at),
        "mode": str(mode or "off"),
        "status": "error",
        "error": str(error or "retention_janitor_failed")[:240],
        "summary": {"errors": 1},
        "actions": [],
        "skips": [],
    }
    receipt_path = state_root / "retention-janitor.latest.json"
    if not _path_mentions_vexp(receipt_path):
        _write_latest_receipt(receipt_path, receipt)
    return receipt


def run_retention_janitor(
    app: Any,
    *,
    workspace_root: Path,
    state_root: Path,
    worktree_root: Path,
    log_root: Path,
    policy: RetentionPolicy,
    now: Optional[dt.datetime] = None,
) -> Dict[str, Any]:
    """Run one bounded janitor pass and return its compact receipt."""

    generated_at = (now or utc_now()).astimezone(UTC)
    mode = str(policy.mode or "apply").strip().lower()
    if mode not in {"apply", "dry-run", "off"}:
        mode = "off"
    receipt_path = state_root / "retention-janitor.latest.json"
    if _path_mentions_vexp(receipt_path):
        return {
            "status": "error",
            "mode": mode,
            "generated_at": iso(generated_at),
            "error": "protected_receipt_path",
        }
    if mode == "off":
        return {"status": "off", "mode": "off", "generated_at": iso(generated_at)}
    if _recent_receipt_blocks_run(
        receipt_path,
        mode=mode,
        now=generated_at,
        interval_hours=max(0, int(policy.interval_hours)),
    ):
        return {"status": "deferred", "mode": mode, "generated_at": iso(generated_at)}

    actions: list[Dict[str, Any]] = []
    skips: list[Dict[str, Any]] = []
    summary: Dict[str, int] = {
        "candidates": 0,
        "eligible": 0,
        "worktrees_selected": 0,
        "worktrees_removed": 0,
        "branches_selected": 0,
        "branches_removed": 0,
        "artifact_files_selected": 0,
        "artifact_files_removed": 0,
        "bytes_selected": 0,
        "bytes_reclaimed": 0,
        "skipped": 0,
        "errors": 0,
    }
    policy_payload = {
        "interval_hours": max(0, int(policy.interval_hours)),
        "worktree_min_age_hours": max(1, int(policy.worktree_min_age_hours)),
        "log_min_age_hours": max(1, int(policy.log_min_age_hours)),
        "keep_run_artifacts_per_package": max(0, int(policy.keep_run_artifacts_per_package)),
        "max_worktrees_per_pass": max(0, int(policy.max_worktrees_per_pass)),
        "max_artifacts_per_pass": max(0, int(policy.max_artifacts_per_pass)),
        "max_candidates_per_pass": max(1, int(policy.max_candidates_per_pass)),
    }
    receipt: Dict[str, Any] = {
        "contract_name": "fleet.retention_janitor.receipt",
        "schema_version": 1,
        "generated_at": iso(generated_at),
        "mode": mode,
        "status": "dry_run" if mode == "dry-run" else "applied",
        "policy": policy_payload,
        "summary": summary,
        "actions": actions,
        "skips": skips,
    }

    resolved_workspace = workspace_root.resolve(strict=False)
    if not _managed_path(worktree_root / "managed", resolved_workspace) or _path_mentions_vexp(worktree_root):
        receipt["status"] = "error"
        receipt["error"] = "managed_worktree_root_invalid"
        summary["errors"] += 1
        _write_latest_receipt(receipt_path, receipt)
        return receipt
    if not _managed_path(log_root / "managed", resolved_workspace) or _path_mentions_vexp(log_root):
        receipt["status"] = "error"
        receipt["error"] = "managed_log_root_invalid"
        summary["errors"] += 1
        _write_latest_receipt(receipt_path, receipt)
        return receipt

    with app.db() as conn:
        candidates = _candidate_rows(conn, limit=policy_payload["max_candidates_per_pass"])
    summary["candidates"] = len(candidates)
    if not candidates:
        receipt["status"] = "no_candidates" if mode == "apply" else "dry_run"
        _write_latest_receipt(receipt_path, receipt)
        return receipt

    worktree_cutoff = generated_at - dt.timedelta(hours=policy_payload["worktree_min_age_hours"])
    log_cutoff = generated_at - dt.timedelta(hours=policy_payload["log_min_age_hours"])
    remote_heads: Dict[tuple[str, str], tuple[str, str]] = {}

    for row in candidates:
        package_id = str(row.get("package_id") or "").strip()
        project_id = str(row.get("project_id") or "").strip()
        reason = _authority_gate(row, cutoff=worktree_cutoff)
        if reason:
            summary["skipped"] += 1
            _append_bounded(skips, {"package_id": package_id, "project_id": project_id, "reason": reason}, limit=policy.max_receipt_entries)
            continue
        repo = Path(str(row.get("project_path") or "").strip())
        worktree = Path(str(row.get("worktree_root") or "").strip())
        if _path_mentions_vexp(repo):
            reason = "protected_project_repo"
        elif not repo.is_dir():
            reason = "project_repo_missing"
        elif not _managed_path(worktree, worktree_root):
            reason = "worktree_outside_managed_root"
        else:
            local_proof, reason = _prepare_local_worktree_proof(
                repo,
                worktree,
                base_branch=str(row.get("base_branch") or "").strip(),
            )
        if reason:
            summary["skipped"] += 1
            _append_bounded(skips, {"package_id": package_id, "project_id": project_id, "reason": reason}, limit=policy.max_receipt_entries)
            continue

        base_branch = str(row.get("base_branch") or "").strip()
        cache_key = (str(repo.resolve(strict=False)), base_branch)
        if cache_key not in remote_heads:
            token = hashlib.sha256(f"{cache_key[0]}:{base_branch}".encode("utf-8")).hexdigest()[:20]
            remote_heads[cache_key] = _fetch_remote_head(repo, base_branch, token=token)
        remote_sha, reason = remote_heads[cache_key]
        landed_sha = str(row.get("landed_sha") or "").strip()
        if not reason and not _is_ancestor(repo, landed_sha, remote_sha):
            reason = "landed_sha_not_on_remote_base"
        if not reason and local_proof and not _is_ancestor(repo, local_proof["head_sha"], remote_sha):
            reason = "worktree_head_unpushed"
        if reason:
            summary["skipped"] += 1
            _append_bounded(skips, {"package_id": package_id, "project_id": project_id, "reason": reason}, limit=policy.max_receipt_entries)
            continue

        summary["eligible"] += 1
        package_action: Dict[str, Any] = {
            "package_id": package_id,
            "project_id": project_id,
            "landed_sha": landed_sha,
            "remote_base_sha": remote_sha,
            "worktree": "absent" if not worktree.exists() else ("would_remove" if mode == "dry-run" else "retained"),
            "branch": str(local_proof.get("branch") or ""),
            "artifact_files": [],
        }

        can_remove_worktree = bool(worktree.exists() and local_proof)
        if can_remove_worktree and summary["worktrees_selected"] < policy_payload["max_worktrees_per_pass"]:
            summary["worktrees_selected"] += 1
            summary["branches_selected"] += 1
            if mode == "dry-run":
                package_action["worktree"] = "would_remove"
            else:
                ok, _ = _git_ok(repo, ["worktree", "remove", str(worktree)], timeout=120)
                if not ok:
                    package_action["worktree"] = "remove_failed"
                    summary["errors"] += 1
                    _append_bounded(actions, package_action, limit=policy.max_receipt_entries)
                    continue
                package_action["worktree"] = "removed"
                summary["worktrees_removed"] += 1
                branch = str(local_proof.get("branch") or "")
                ok, _ = _git_ok(repo, ["branch", "-D", "--", branch], timeout=30)
                package_action["branch_removed"] = bool(ok)
                if ok:
                    summary["branches_removed"] += 1
                else:
                    summary["errors"] += 1
                _remove_empty_parent(worktree.parent, stop=worktree_root)
        elif can_remove_worktree:
            package_action["worktree"] = "per_pass_limit"

        with app.db() as conn:
            artifacts = _eligible_run_artifacts(
                conn,
                package_id=package_id,
                log_root=log_root,
                cutoff=log_cutoff,
                keep=policy_payload["keep_run_artifacts_per_package"],
                limit=max(
                    0,
                    policy_payload["max_artifacts_per_pass"] - summary["artifact_files_selected"],
                ),
            )
        for artifact in artifacts:
            if summary["artifact_files_selected"] >= policy_payload["max_artifacts_per_pass"]:
                break
            summary["artifact_files_selected"] += 1
            summary["bytes_selected"] += int(artifact["bytes"])
            public_artifact = {
                "run_id": artifact["run_id"],
                "field": artifact["field"],
                "bytes": artifact["bytes"],
                "sha256": artifact["sha256"],
                "result": "would_remove" if mode == "dry-run" else "retained",
            }
            if mode == "dry-run":
                pass
            else:
                try:
                    artifact["path"].unlink()
                except OSError:
                    public_artifact["result"] = "remove_failed"
                    summary["errors"] += 1
                else:
                    public_artifact["result"] = "removed"
                    summary["artifact_files_removed"] += 1
                    summary["bytes_reclaimed"] += int(artifact["bytes"])
                    with app.db() as conn:
                        try:
                            conn.execute(
                                f"UPDATE runs SET {artifact['field']}=NULL WHERE id=? AND {artifact['field']}=?",
                                (int(artifact["run_id"]), str(artifact["path"])),
                            )
                            conn.commit()
                        except sqlite3.Error:
                            public_artifact["result"] = "removed_db_update_failed"
                            summary["errors"] += 1
                    _remove_empty_parent(artifact["path"].parent, stop=log_root)
            package_action["artifact_files"].append(public_artifact)
        _append_bounded(actions, package_action, limit=policy.max_receipt_entries)

    receipt["details_truncated"] = bool(
        summary["candidates"] > len(actions) + len(skips)
        or len(actions) >= policy.max_receipt_entries
        or len(skips) >= policy.max_receipt_entries
    )
    if summary["errors"]:
        receipt["status"] = "partial_failure"
    _write_latest_receipt(receipt_path, receipt)
    return receipt


__all__ = ["RetentionPolicy", "run_retention_janitor", "write_retention_error_receipt"]
