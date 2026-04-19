#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import errno
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List


DEFAULT_WORKSPACE_ROOT = Path("/docker/fleet")
DEFAULT_STATE_ROOT = DEFAULT_WORKSPACE_ROOT / "state" / "chummer_design_supervisor"
DEFAULT_MONITOR_BASE = DEFAULT_WORKSPACE_ROOT / "state" / "design_supervisor_ooda"
DEFAULT_DURATION_SECONDS = 12 * 60 * 60
DEFAULT_POLL_SECONDS = 5 * 60
DEFAULT_QUIET_PASSES = 8
DEFAULT_KEEP_OLD_MONITOR_DIRS = 8
DEFAULT_KEEP_AUTH_BACKUPS = 4


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-root", default=str(DEFAULT_WORKSPACE_ROOT))
    parser.add_argument("--state-root", default=str(DEFAULT_STATE_ROOT))
    parser.add_argument("--monitor-base", default=str(DEFAULT_MONITOR_BASE))
    parser.add_argument("--duration-seconds", type=int, default=DEFAULT_DURATION_SECONDS)
    parser.add_argument("--poll-seconds", type=int, default=DEFAULT_POLL_SECONDS)
    parser.add_argument("--quiet-passes", type=int, default=DEFAULT_QUIET_PASSES)
    parser.add_argument(
        "--forever",
        action="store_true",
        help="Run indefinitely; disables duration and quiet-streak stop conditions.",
    )
    parser.add_argument("--current-alias", default="current_12h_quiet")
    parser.add_argument("--once", action="store_true", help="Run a single pass and exit.")
    return parser.parse_args()


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def prune_old_monitor_dirs(monitor_base: Path, *, keep: int, exclude: Path | None = None) -> List[str]:
    removed: List[str] = []
    if keep < 0 or not monitor_base.exists():
        return removed
    candidates = [
        path
        for path in monitor_base.iterdir()
        if path.is_dir() and path != exclude and path.name.startswith(("quietloop_", "launcher_"))
    ]
    candidates.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    for path in candidates[keep:]:
        try:
            subprocess.run(["rm", "-rf", str(path)], check=False)
            removed.append(path.name)
        except Exception:
            continue
    return removed


def prune_auth_backups(*, secrets_dir: Path, keep_per_target: int) -> List[str]:
    removed: List[str] = []
    if keep_per_target < 0 or not secrets_dir.exists():
        return removed
    grouped: Dict[str, List[Path]] = {}
    for path in secrets_dir.glob("*.bak.*"):
        base_name = path.name.split(".bak.", 1)[0]
        grouped.setdefault(base_name, []).append(path)
    for _, paths in grouped.items():
        paths.sort(key=lambda item: item.stat().st_mtime, reverse=True)
        for stale in paths[keep_per_target:]:
            try:
                stale.unlink(missing_ok=True)
                removed.append(stale.name)
            except Exception:
                continue
    return removed


def best_effort_write_json(
    path: Path,
    payload: Dict[str, Any],
    *,
    monitor_base: Path,
    run_root: Path,
    state_root: Path,
) -> tuple[bool, List[str]]:
    cleanup_notes: List[str] = []
    try:
        write_json(path, payload)
        return True, cleanup_notes
    except OSError as exc:
        if exc.errno != errno.ENOSPC:
            raise
    cleanup_notes.extend(prune_old_monitor_dirs(monitor_base, keep=DEFAULT_KEEP_OLD_MONITOR_DIRS, exclude=run_root))
    cleanup_notes.extend(
        prune_auth_backups(
            secrets_dir=state_root.parent.parent / "secrets",
            keep_per_target=DEFAULT_KEEP_AUTH_BACKUPS,
        )
    )
    try:
        write_json(path, payload)
        return True, cleanup_notes
    except OSError as exc:
        if exc.errno != errno.ENOSPC:
            raise
    return False, cleanup_notes


def parse_iso(value: Any) -> str:
    return str(value or "").strip()


def latest_attempts(payload: Dict[str, Any], key: str) -> Dict[str, str]:
    entries = dict(payload.get(key) or {})
    latest: Dict[str, str] = {}
    for name, item in entries.items():
        if not isinstance(item, dict):
            continue
        stamp = parse_iso(item.get("attempted_at"))
        if stamp:
            latest[str(name)] = stamp
    return latest


def classify_findings(before: Dict[str, Any], after: Dict[str, Any]) -> List[str]:
    findings: List[str] = []
    if str(after.get("controller") or "").strip().lower() != "up":
        findings.append(f"controller:{after.get('controller') or 'unknown'}")
    if str(after.get("supervisor") or "").strip().lower() != "up":
        findings.append(f"supervisor:{after.get('supervisor') or 'unknown'}")
    if bool(after.get("aggregate_stale")):
        findings.append("aggregate_stale")
    if bool(after.get("aggregate_timestamp_stale")):
        findings.append("aggregate_timestamp_stale")
    eta_status = str(after.get("eta_status") or "").strip().lower()
    if eta_status == "blocked":
        reason = str(after.get("blocking_reason") or "").strip() or "unknown"
        findings.append(f"eta_blocked:{reason}")
    stale_shards = [str(item).strip() for item in (after.get("stale_shards") or []) if str(item).strip()]
    inactive_shards = [str(item).strip() for item in (after.get("inactive_shards") or []) if str(item).strip()]
    if stale_shards:
        findings.append("stale_shards:" + ",".join(stale_shards))
    if inactive_shards:
        findings.append("inactive_shards:" + ",".join(inactive_shards))

    before_restarts = latest_attempts(before, "service_restarts")
    after_restarts = latest_attempts(after, "service_restarts")
    for service, stamp in sorted(after_restarts.items()):
        if before_restarts.get(service) != stamp:
            findings.append(f"service_restart:{service}")

    before_repairs = latest_attempts(before, "repairs")
    after_repairs = latest_attempts(after, "repairs")
    for source, stamp in sorted(after_repairs.items()):
        if before_repairs.get(source) != stamp:
            findings.append(f"repair:{source}")

    if bool(after.get("last_repair_attempted")):
        findings.append("repair_succeeded")
    return findings


def run_ooda_once(*, workspace_root: Path, state_root: Path, monitor_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "python3",
            "scripts/ooda_design_supervisor.py",
            "--once",
            "--workspace-root",
            str(workspace_root),
            "--state-root",
            str(state_root),
            "--monitor-root",
            str(monitor_root),
        ],
        cwd=str(workspace_root),
        capture_output=True,
        text=True,
        check=False,
    )


def main() -> int:
    args = parse_args()
    workspace_root = Path(args.workspace_root).resolve()
    state_root = Path(args.state_root).resolve()
    monitor_base = Path(args.monitor_base).resolve()
    monitor_base.mkdir(parents=True, exist_ok=True)

    duration_seconds = int(args.duration_seconds)
    run_forever = bool(args.forever) or duration_seconds <= 0
    label_suffix = "forever" if run_forever else "12h"
    run_label = dt.datetime.now(dt.timezone.utc).strftime(f"quietloop_%Y%m%dT%H%M%SZ_{label_suffix}")
    run_root = monitor_base / run_label
    run_root.mkdir(parents=True, exist_ok=True)
    current_link = monitor_base / str(args.current_alias)
    current_link.unlink(missing_ok=True)
    current_link.symlink_to(run_root.name)

    loop_state_path = run_root / "loop_state.json"
    events_path = run_root / "quiet_loop.events.jsonl"
    stdout_log = run_root / "ooda.stdout.log"
    stderr_log = run_root / "ooda.stderr.log"

    end_time = None if run_forever else time.time() + max(1, duration_seconds)
    quiet_streak = 0
    passes = 0

    final_payload: Dict[str, Any] = {}
    try:
        while True:
            before = read_json(run_root / "state.json")
            completed = run_ooda_once(workspace_root=workspace_root, state_root=state_root, monitor_root=run_root)
            after = read_json(run_root / "state.json")
            passes += 1

            if completed.stdout:
                try:
                    with stdout_log.open("a", encoding="utf-8") as handle:
                        handle.write(completed.stdout)
                        if not completed.stdout.endswith("\n"):
                            handle.write("\n")
                except OSError:
                    pass
            if completed.stderr:
                try:
                    with stderr_log.open("a", encoding="utf-8") as handle:
                        handle.write(completed.stderr)
                        if not completed.stderr.endswith("\n"):
                            handle.write("\n")
                except OSError:
                    pass

            findings = classify_findings(before, after)
            if completed.returncode != 0:
                findings.append(f"ooda_rc:{completed.returncode}")
            if findings:
                quiet_streak = 0
            else:
                quiet_streak += 1

            status_payload = {
                "current_alias": str(args.current_alias),
                "last_cycle_at": iso_now(),
                "monitor_root": str(run_root),
                "passes_completed": passes,
                "quiet_streak": quiet_streak,
                "quiet_target": int(args.quiet_passes),
                "stop_reason": "",
                "duration_seconds": 0 if run_forever else duration_seconds,
                "forever": run_forever,
                "poll_seconds": int(args.poll_seconds),
                "once": bool(args.once),
                "latest_findings": findings,
            }
            try:
                append_event(
                    events_path,
                    {
                        "at": iso_now(),
                        "pass": passes,
                        "quiet_streak": quiet_streak,
                        "findings": findings,
                        "ooda_returncode": completed.returncode,
                    },
                )
            except OSError:
                status_payload["latest_findings"] = findings + ["event_log_write_failed"]

            stop_reason = ""
            if args.once:
                stop_reason = "once"
            elif not run_forever and quiet_streak >= max(1, int(args.quiet_passes)):
                stop_reason = f"quiet_streak:{quiet_streak}"
            elif end_time is not None and time.time() >= end_time:
                stop_reason = "duration_elapsed"

            if stop_reason:
                status_payload["stop_reason"] = stop_reason
                final_payload = status_payload
                ok, cleanup_notes = best_effort_write_json(
                    loop_state_path,
                    status_payload,
                    monitor_base=monitor_base,
                    run_root=run_root,
                    state_root=state_root,
                )
                if not ok:
                    final_payload["latest_findings"] = list(final_payload.get("latest_findings") or []) + [
                        "loop_state_write_failed"
                    ]
                if cleanup_notes:
                    final_payload["cleanup_notes"] = cleanup_notes
                break

            ok, cleanup_notes = best_effort_write_json(
                loop_state_path,
                status_payload,
                monitor_base=monitor_base,
                run_root=run_root,
                state_root=state_root,
            )
            if cleanup_notes:
                status_payload["cleanup_notes"] = cleanup_notes
            if not ok:
                final_payload = status_payload
                final_payload["stop_reason"] = "loop_state_write_failed"
                final_payload["latest_findings"] = list(final_payload.get("latest_findings") or []) + [
                    "loop_state_write_failed"
                ]
                break

            time.sleep(max(15, int(args.poll_seconds)))
    except Exception as exc:
        final_payload = {
            "current_alias": str(args.current_alias),
            "last_cycle_at": iso_now(),
            "monitor_root": str(run_root),
            "passes_completed": passes,
            "quiet_streak": quiet_streak,
            "quiet_target": int(args.quiet_passes),
            "stop_reason": f"wrapper_error:{type(exc).__name__}",
            "duration_seconds": 0 if run_forever else duration_seconds,
            "forever": run_forever,
            "poll_seconds": int(args.poll_seconds),
            "once": bool(args.once),
            "latest_findings": [f"wrapper_exception:{exc}"],
        }
        best_effort_write_json(
            loop_state_path,
            final_payload,
            monitor_base=monitor_base,
            run_root=run_root,
            state_root=state_root,
        )
        raise

    if not final_payload:
        final_payload = read_json(loop_state_path)
    else:
        best_effort_write_json(
            loop_state_path,
            final_payload,
            monitor_base=monitor_base,
            run_root=run_root,
            state_root=state_root,
        )
    print(json.dumps(final_payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
