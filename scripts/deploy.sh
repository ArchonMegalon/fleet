#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: bash scripts/deploy.sh <command> [args]

Commands:
  admin-status
      Print the live admin status JSON.
  cockpit-summary
      Print a compact live cockpit summary.
  gateway-cockpit
      Fetch the live cockpit payload through the dashboard gateway.
  gateway-root
      Fetch the root dashboard path headers from inside the gateway container.
  host-root
      Fetch the root dashboard path headers from the host-bound gateway port.
  dashboard-logs
      Print recent fleet-dashboard logs.
  project-status <project> [project...]
      Print compact live project rows from the fleet DB.
  compile-status <project> [project...]
      Print live project lifecycle and compile-health rows from admin status.
  run-status <run_id> [run_id...]
      Print compact live run rows from the fleet DB.
  recent-runs <project> [limit]
      Print recent live run rows for one project from the fleet DB.
  time-vienna
      Print the current Vienna time.
  verify-config
      Parse the split fleet config and fail on invalid YAML/schema loading.
  db-schema <table>
      Print the live SQLite schema for a table.
  verify-python <file> [file...]
      Run python3 -m py_compile on one or more files.
  rebuild <service> [service...]
      Rebuild and restart one or more compose services.
USAGE
}

require_args() {
  if [ "$#" -eq 0 ]; then
    echo "missing arguments" >&2
    exit 1
  fi
}

admin_status() {
  docker exec fleet-admin curl -sS -H 'X-Fleet-Operator-Password: rangersofB5' \
    http://127.0.0.1:8092/api/admin/status
}

case "${1:-}" in
  admin-status)
    admin_status
    ;;
  cockpit-summary)
    admin_status | python3 -c '
import json, sys
data = json.load(sys.stdin)
summary = data.get("summary", {})
cockpit = data.get("cockpit", {})
workers = cockpit.get("workers", [])
projects = data.get("projects", [])
print(json.dumps({
  "fleet_health": data.get("fleet_health"),
  "active_workers": summary.get("active_workers"),
  "open_incidents": summary.get("open_incidents"),
  "approvals_waiting": summary.get("approvals_waiting"),
  "workers": [
    {
      "project_id": worker.get("project_id") or worker.get("id"),
      "status": worker.get("status") or worker.get("phase"),
      "slice": worker.get("current_slice"),
    }
    for worker in workers
  ],
  "project_states": [
    {
      "project_id": project.get("project_id") or project.get("id"),
      "status": project.get("status") or project.get("runtime_status_internal"),
      "runtime_status": project.get("runtime_status"),
      "active_run_id": project.get("active_run_id"),
      "next_action": project.get("next_action"),
      "cooldown_until": project.get("cooldown_until"),
    }
    for project in projects
  ],
}, indent=2))
'
    ;;
  gateway-cockpit)
    docker exec fleet-dashboard wget --header='X-Fleet-Operator-Password: rangersofB5' -qO- http://127.0.0.1:8090/api/cockpit/status | python3 -c '
import json, sys
data = json.load(sys.stdin)
cockpit = data.get("cockpit", {})
summary = cockpit.get("summary", {})
print(json.dumps({
  "fleet_health": summary.get("fleet_health"),
  "active_workers": summary.get("active_workers"),
  "open_incidents": summary.get("open_incidents"),
  "approvals_waiting": summary.get("approvals_waiting"),
  "worker_ids": [worker.get("project_id") for worker in (cockpit.get("workers") or [])],
}, indent=2))
'
    ;;
  gateway-root)
    docker exec fleet-dashboard wget -S -O /dev/null http://127.0.0.1:8090/
    ;;
  host-root)
    curl -sS -D - -o /dev/null http://127.0.0.1:18090/
    ;;
  dashboard-logs)
    docker compose logs --tail="${2:-80}" fleet-dashboard
    ;;
  project-status)
    shift
    require_args "$@"
    docker exec -i fleet-controller python3 - "$@" <<'PY'
import json
import sqlite3
import sys

db = sqlite3.connect("/var/lib/codex-fleet/fleet.db")
db.row_factory = sqlite3.Row
for project_id in sys.argv[1:]:
    row = db.execute(
        """
        select id as project_id, status, active_run_id, current_slice, cooldown_until,
               last_run_at, last_error, spider_tier, spider_model, spider_reason,
               queue_index, queue_json, updated_at
          from projects
         where id = ?
        """,
        (project_id,),
    ).fetchone()
    print(json.dumps(dict(row) if row else {"project_id": project_id, "missing": True}, indent=2))
PY
    ;;
  compile-status)
    shift
    require_args "$@"
    admin_status | python3 -c '
import json, sys
data = json.load(sys.stdin)
targets = set(sys.argv[1:])
rows = []
for project in data.get("projects", []):
    project_id = str(project.get("id") or "")
    if project_id in targets:
        rows.append({
            "project_id": project_id,
            "lifecycle": project.get("lifecycle"),
            "runtime_status": project.get("runtime_status"),
            "compile": project.get("compile"),
            "compile_health": project.get("compile_health"),
        })
print(json.dumps(rows, indent=2))
' "$@"
    ;;
  run-status)
    shift
    require_args "$@"
    docker exec -i fleet-controller python3 - "$@" <<'PY'
import json
import sqlite3
import sys

db = sqlite3.connect("/var/lib/codex-fleet/fleet.db")
db.row_factory = sqlite3.Row
for run_id in sys.argv[1:]:
    row = db.execute(
        """
        select id, project_id, status, started_at, finished_at,
               model, account_alias, slice_name, job_kind, error_class, error_message
          from runs
         where id = ?
        """,
        (run_id,),
    ).fetchone()
    print(json.dumps(dict(row) if row else {"id": run_id, "missing": True}, indent=2))
PY
    ;;
  recent-runs)
    shift
    require_args "$@"
    project_id="$1"
    limit="${2:-10}"
    docker exec -i fleet-controller python3 - "$project_id" "$limit" <<'PY'
import json
import sqlite3
import sys

project_id = sys.argv[1]
limit = int(sys.argv[2])
db = sqlite3.connect("/var/lib/codex-fleet/fleet.db")
db.row_factory = sqlite3.Row
rows = db.execute(
    """
    select id, project_id, status, started_at, finished_at, job_kind, slice_name,
           error_class, error_message, decision_reason
      from runs
     where project_id = ?
     order by id desc
     limit ?
    """,
    (project_id, limit),
).fetchall()
print(json.dumps([dict(row) for row in rows], indent=2))
PY
    ;;
  time-vienna)
    TZ=Europe/Vienna date '+%Y-%m-%d %H:%M:%S %Z'
    ;;
  verify-config)
    python3 - <<'PY'
import pathlib
import sys
import yaml

root = pathlib.Path("/docker/fleet/config")
paths = [root / "fleet.yaml", root / "accounts.yaml", root / "policies.yaml", root / "routing.yaml", root / "groups.yaml"]
projects_dir = root / "projects"
paths.extend(sorted(projects_dir.glob("*.yaml")))
for path in paths:
    with path.open("r", encoding="utf-8") as handle:
        yaml.safe_load(handle)
print("config ok")
PY
    ;;
  db-schema)
    shift
    require_args "$@"
    docker exec -i fleet-controller python3 - "$@" <<'PY'
import json
import sqlite3
import sys

db = sqlite3.connect("/var/lib/codex-fleet/fleet.db")
db.row_factory = sqlite3.Row
for table_name in sys.argv[1:]:
    rows = db.execute(f"PRAGMA table_info({table_name})").fetchall()
    print(json.dumps({
        "table": table_name,
        "columns": [dict(row) for row in rows],
    }, indent=2))
PY
    ;;
  verify-python)
    shift
    require_args "$@"
    python3 -m py_compile "$@"
    ;;
  rebuild)
    shift
    require_args "$@"
    docker compose up -d --build "$@"
    ;;
  ""|-h|--help|help)
    usage
    ;;
  *)
    echo "unknown command: $1" >&2
    usage >&2
    exit 1
    ;;
esac
