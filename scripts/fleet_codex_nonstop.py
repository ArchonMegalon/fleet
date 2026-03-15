#!/usr/bin/env python3
"""Keep one project continuously cycling coding work in Fleet."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import time
import urllib.request
from typing import Any, Dict, Optional


DEFAULT_FLEET_URL = "http://127.0.0.1:18090"
ACTIVE_RUN_STATES = {"starting", "running", "verifying", "healing", "local_review"}
REVIEW_HOLD_STATES = {"review_requested", "awaiting_pr"}
NO_WORK_STATES = {"complete", "source_backlog_open", "scaffold_complete", "completed_signed_off"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", help="Fleet project id to keep dispatching continuously.")
    parser.add_argument(
        "--fleet-url",
        default=DEFAULT_FLEET_URL,
        help=f"Fleet controller URL (default: {DEFAULT_FLEET_URL}).",
    )
    parser.add_argument(
        "--tick-seconds",
        type=float,
        default=8.0,
        help="Sleep between status polls, in seconds.",
    )
    parser.add_argument(
        "--attempt-seconds",
        type=float,
        default=3.0,
        help="Wait after triggering run-now before the next status check.",
    )
    parser.add_argument(
        "--max-idle-ticks",
        type=int,
        default=0,
        help="Stop after N consecutive non-active ticks. 0 means indefinite.",
    )
    parser.add_argument(
        "--stop-on-review",
        action="store_true",
        help="Stop when project status becomes review_requested.",
    )
    parser.add_argument(
        "--include-signoff",
        action="store_true",
        help="Continue even when project is in signoff_only.",
    )
    parser.add_argument(
        "--include-review",
        action="store_true",
        help="Attempt dispatch even while the project is review-held.",
    )
    parser.add_argument(
        "--no-retry-on-errors",
        action="store_true",
        help="Stop on first API error instead of retrying.",
    )
    parser.add_argument(
        "--api-token",
        default=os.environ.get("FLEET_API_TOKEN", "").strip(),
        help="Optional Bearer token for Fleet API calls.",
    )
    parser.add_argument(
        "--max-api-errors",
        type=int,
        default=8,
        help="Consecutive API errors before stop (0 = never).",
    )
    return parser.parse_args()


def _parse_iso(value: Optional[str]) -> Optional[dt.datetime]:
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return dt.datetime.fromisoformat(raw)
    except ValueError:
        return None


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _has_active_break(now: Optional[dt.datetime], cooldown_until: Optional[str]) -> bool:
    parsed = _parse_iso(cooldown_until)
    if not parsed:
        return False
    return parsed.astimezone(dt.timezone.utc) > (now or _utc_now())


def _status_is_active(state: str) -> bool:
    return str(state or "").strip().lower() in ACTIVE_RUN_STATES


def _status_is_review_hold(state: str) -> bool:
    return str(state or "").strip().lower() in REVIEW_HOLD_STATES


def _status_is_done(state: str) -> bool:
    return str(state or "").strip().lower() in NO_WORK_STATES


def _request(method: str, url: str, payload: Optional[Dict[str, Any]] = None, token: str = "") -> Dict[str, Any]:
    data = None
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"{url}", method=method, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def _fetch_status(base_url: str, token: str) -> Dict[str, Any]:
    return _request("GET", f"{base_url.rstrip('/')}/api/status", token=token)


def _find_project(status_data: Dict[str, Any], project_id: str) -> Optional[Dict[str, Any]]:
    for project in status_data.get("projects", []):
        if str(project.get("id")) == str(project_id):
            return project
    return None


def _run_now(base_url: str, project_id: str, token: str) -> None:
    _request("POST", f"{base_url.rstrip('/')}/api/projects/{project_id}/run-now", {}, token)


def _log(project_id: str, status: str, backend: str, brain: str, run_alias: str) -> None:
    print(
        f"[fleet] {project_id} status={status} "
        f"active_alias={run_alias or 'None'} backend={backend or 'unknown'} brain={brain or 'unknown'}",
        flush=True,
    )


def main() -> None:
    args = parse_args()
    if args.tick_seconds <= 0:
        raise SystemExit("--tick-seconds must be greater than 0")

    base_url = args.fleet_url.rstrip("/")
    idle_ticks = 0
    api_error_count = 0

    while True:
        try:
            status_data = _fetch_status(base_url, args.api_token)
            api_error_count = 0
        except Exception as exc:  # pragma: no cover - network guard
            api_error_count += 1
            print(f"[fleet] status fetch failed ({api_error_count}): {exc}", flush=True)
            if args.no_retry_on_errors:
                return
            if args.max_api_errors and api_error_count >= max(1, args.max_api_errors):
                print(f"[fleet] stopping after {api_error_count} consecutive API errors", flush=True)
                return
            backoff = min(30, args.tick_seconds * 2) * max(1, min(api_error_count, 3))
            time.sleep(backoff)
            continue

        project = _find_project(status_data, args.project)
        if not project:
            print(f"[fleet] project not found: {args.project}", flush=True)
            return

        runtime_status = str(project.get("status") or project.get("runtime_status") or "").strip().lower()
        cooldown_until = str(project.get("cooldown_until") or "").strip() or None
        active_run = str(project.get("active_run_id") or "")
        run_alias = str(project.get("active_run_account_alias") or "")
        run_backend = str(project.get("active_run_account_backend") or "")
        run_brain = str(project.get("active_run_brain") or "")
        _log(args.project, runtime_status, run_backend, run_brain, run_alias)

        now = _utc_now()
        in_break = active_run or _status_is_active(runtime_status)
        if in_break:
            idle_ticks = 0
        else:
            idle_ticks += 1

        if args.stop_on_review and runtime_status == "review_requested":
            print("[fleet] stopping on review_requested", flush=True)
            return

        if runtime_status == "signoff_only" and not args.include_signoff:
            print("[fleet] stopping on signoff_only", flush=True)
            return

        if _status_is_done(runtime_status):
            print("[fleet] project has no remaining queue work; stopping", flush=True)
            return

        if _has_active_break(now, cooldown_until):
            cooldown_msg = str(project.get("cooldown_until") or "unknown")
            print(f"[fleet] waiting on cooldown until {cooldown_msg}", flush=True)
            time.sleep(args.tick_seconds)
            continue

        if _status_is_review_hold(runtime_status) and not args.include_review:
            print("[fleet] waiting on review hold", flush=True)
            time.sleep(args.tick_seconds)
            continue

        if args.max_idle_ticks and idle_ticks >= args.max_idle_ticks and not active_run:
            print(f"[fleet] stopping after {idle_ticks} idle ticks", flush=True)
            return

        if not in_break:
            try:
                _run_now(base_url, args.project, args.api_token)
                print("[fleet] run-now dispatched", flush=True)
                idle_ticks = 0
            except Exception as exc:
                print(f"[fleet] run-now failed: {exc}", flush=True)
            time.sleep(max(0.0, args.attempt_seconds))

        time.sleep(max(1.0, args.tick_seconds))


if __name__ == "__main__":
    main()
