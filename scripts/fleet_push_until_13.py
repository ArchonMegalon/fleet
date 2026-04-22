#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def active_runtime_count(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS count FROM runtime_tasks WHERE task_state='running'"
    ).fetchone()
    return int(row["count"] or 0)


def ready_projects(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        """
        SELECT DISTINCT project_id
        FROM work_packages
        WHERE status='ready'
        ORDER BY project_id
        """
    ).fetchall()
    return [str(row["project_id"]) for row in rows]


def trigger_run_now(controller_url: str, project_id: str) -> dict[str, object]:
    req = urllib.request.Request(
        f"{controller_url.rstrip('/')}/api/projects/{project_id}/run-now",
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        payload = response.read().decode("utf-8")
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return {"raw": payload}


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggressively trigger ready fleet projects until target live runtime count is reached.")
    parser.add_argument("--db", default="/docker/fleet/state/fleet.db")
    parser.add_argument("--controller-url", default="http://127.0.0.1:8090")
    parser.add_argument("--target-active", type=int, default=13)
    parser.add_argument("--poll-seconds", type=int, default=30)
    parser.add_argument("--max-idle-passes", type=int, default=0, help="0 means run forever until target is reached.")
    args = parser.parse_args()

    db_path = Path(args.db).resolve()
    idle_passes = 0

    while True:
        try:
            with connect(db_path) as conn:
                active = active_runtime_count(conn)
                ready = ready_projects(conn)
        except sqlite3.Error as exc:
            print(f"{utc_now()} db_error={exc}", flush=True)
            time.sleep(max(5, args.poll_seconds))
            continue

        print(f"{utc_now()} active={active} ready_projects={ready}", flush=True)

        if active >= args.target_active:
            print(f"{utc_now()} target_reached={args.target_active}", flush=True)
            return 0

        launched_any = False
        for project_id in ready:
            try:
                result = trigger_run_now(args.controller_url, project_id)
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                print(f"{utc_now()} project={project_id} trigger_error={exc}", flush=True)
                continue
            launched_any = launched_any or bool(result.get("launched"))
            print(f"{utc_now()} project={project_id} result={json.dumps(result, sort_keys=True)}", flush=True)

        if launched_any or ready:
            idle_passes = 0
        else:
            idle_passes += 1
            if args.max_idle_passes > 0 and idle_passes >= args.max_idle_passes:
                print(f"{utc_now()} stopping_after_idle_passes={idle_passes}", flush=True)
                return 0

        time.sleep(max(5, args.poll_seconds))


if __name__ == "__main__":
    raise SystemExit(main())
