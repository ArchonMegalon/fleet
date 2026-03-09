import datetime as dt
import html
import json
import os
import pathlib
import sqlite3
from typing import Any, Dict, List, Optional

import yaml
from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse

UTC = dt.timezone.utc
APP_PORT = int(os.environ.get("APP_PORT", "8092"))
APP_TITLE = "Codex Fleet Admin"
CONFIG_PATH = pathlib.Path(os.environ.get("FLEET_CONFIG_PATH", "/app/config/fleet.yaml"))
ACCOUNTS_PATH = pathlib.Path(os.environ.get("FLEET_ACCOUNTS_PATH", "/app/config/accounts.yaml"))
DB_PATH = pathlib.Path(os.environ.get("FLEET_DB_PATH", "/var/lib/codex-fleet/fleet.db"))
DOCKER_ROOT = pathlib.Path("/docker")
STUDIO_PUBLISHED_DIR = ".codex-studio/published"

app = FastAPI(title=APP_TITLE)


def utc_now() -> dt.datetime:
    return dt.datetime.now(UTC)


def iso(ts: Optional[dt.datetime]) -> Optional[str]:
    return ts.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z") if ts else None


def parse_iso(value: Optional[str]) -> Optional[dt.datetime]:
    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        return dt.datetime.fromisoformat(value).astimezone(UTC)
    except ValueError:
        return None


def load_yaml(path: pathlib.Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def save_yaml(path: pathlib.Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False)
    tmp_path.replace(path)


def normalize_config() -> Dict[str, Any]:
    fleet = load_yaml(CONFIG_PATH)
    accounts_cfg = load_yaml(ACCOUNTS_PATH)
    fleet.setdefault("policies", {})
    fleet.setdefault("spider", {})
    fleet.setdefault("projects", [])
    fleet["accounts"] = accounts_cfg.get("accounts", {}) or {}
    for project in fleet["projects"]:
        project.setdefault("enabled", True)
        project.setdefault("feedback_dir", "feedback")
        project.setdefault("state_file", ".agent-state.json")
        project.setdefault("verify_cmd", "")
        project.setdefault("design_doc", "")
        project.setdefault("accounts", [])
        project.setdefault("queue", [])
        project.setdefault("queue_sources", [])
        project.setdefault("runner", {})
        project["runner"].setdefault("sandbox", "workspace-write")
        project["runner"].setdefault("approval_policy", "never")
        project["runner"].setdefault("exec_timeout_seconds", 5400)
        project["runner"].setdefault("verify_timeout_seconds", 1800)
        project["runner"].setdefault("config_overrides", [])
    return fleet


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def project_cfg(config: Dict[str, Any], project_id: str) -> Dict[str, Any]:
    for project in config.get("projects", []):
        if project.get("id") == project_id:
            return project
    raise KeyError(project_id)


def project_runtime_rows() -> Dict[str, Dict[str, Any]]:
    if not DB_PATH.exists():
        return {}
    with db() as conn:
        rows = conn.execute("SELECT * FROM projects ORDER BY id").fetchall()
    return {row["id"]: dict(row) for row in rows}


def effective_runtime_status(
    *,
    stored_status: Optional[str],
    queue_len: int,
    queue_index: int,
    enabled: bool,
    active_run_id: Optional[int],
) -> str:
    status = str(stored_status or "").strip() or "idle"
    if not enabled:
        return "paused"
    if int(queue_index) >= int(queue_len):
        if status in {"starting", "running", "verifying"} and active_run_id:
            return status
        return "complete"
    if status in {"complete", "paused"}:
        return "idle"
    return status


def recent_runs(limit: int = 20) -> List[Dict[str, Any]]:
    if not DB_PATH.exists():
        return []
    with db() as conn:
        rows = conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(row) for row in rows]


def split_items(raw: str) -> List[str]:
    values: List[str] = []
    for line in raw.replace(",", "\n").splitlines():
        value = line.strip()
        if value:
            values.append(value)
    return values


def validate_repo_path(repo_path: str) -> pathlib.Path:
    path = pathlib.Path(repo_path).expanduser()
    if not path.is_absolute():
        raise HTTPException(400, "repo path must be absolute")
    try:
        path.relative_to(DOCKER_ROOT)
    except ValueError as exc:
        raise HTTPException(400, "repo path must live under /docker") from exc
    if not path.exists() or not path.is_dir():
        raise HTTPException(400, "repo path is not visible inside the fleet containers")
    return path


def resolve_optional_repo_file(repo_root: pathlib.Path, raw_value: str) -> str:
    value = raw_value.strip()
    if not value:
        return ""
    path = pathlib.Path(value)
    if path.is_absolute():
        return str(path)
    return str(repo_root / path)


def bootstrap_repo_ai_files(repo_root: pathlib.Path, feedback_dir: str, state_file: str) -> None:
    feedback_path = repo_root / feedback_dir
    feedback_path.mkdir(parents=True, exist_ok=True)
    applied_log = feedback_path / ".applied.log"
    applied_log.touch(exist_ok=True)

    studio_published = repo_root / STUDIO_PUBLISHED_DIR
    studio_published.mkdir(parents=True, exist_ok=True)

    scripts_ai = repo_root / "scripts/ai"
    scripts_ai.mkdir(parents=True, exist_ok=True)

    agent_memory = repo_root / ".agent-memory.md"
    if not agent_memory.exists():
        agent_memory.write_text(
            "# Repo-local agent memory\n\n- Keep repo-specific workflow notes here.\n",
            encoding="utf-8",
        )

    state_path = repo_root / state_file
    if not state_path.exists():
        state_path.write_text("{}\n", encoding="utf-8")

    verify_script = scripts_ai / "verify.sh"
    if not verify_script.exists():
        verify_script.write_text(
            "#!/usr/bin/env bash\nset -euo pipefail\n# TODO: replace with repo verification commands.\n",
            encoding="utf-8",
        )
        verify_script.chmod(0o755)


def save_fleet_config(config: Dict[str, Any]) -> None:
    data = dict(config)
    data.pop("accounts", None)
    save_yaml(CONFIG_PATH, data)


def set_project_enabled(project_id: str, enabled: bool) -> None:
    config = normalize_config()
    project = project_cfg(config, project_id)
    project["enabled"] = bool(enabled)
    save_fleet_config(config)


def update_project_runtime(project_id: str, *, status: Optional[str] = None, clear_cooldown: bool = False, reset_failures: bool = False) -> None:
    if not DB_PATH.exists():
        return
    fields: List[str] = []
    values: List[Any] = []
    if status is not None:
        fields.append("status=?")
        values.append(status)
    if clear_cooldown:
        fields.append("cooldown_until=NULL")
    if reset_failures:
        fields.extend(["consecutive_failures=0", "last_error=NULL"])
    if not fields:
        return
    fields.append("updated_at=?")
    values.append(iso(utc_now()))
    values.append(project_id)
    with db() as conn:
        conn.execute(f"UPDATE projects SET {', '.join(fields)} WHERE id=?", values)


def studio_published_files(repo_root: pathlib.Path) -> List[str]:
    published_dir = repo_root / STUDIO_PUBLISHED_DIR
    if not published_dir.exists() or not published_dir.is_dir():
        return []
    return sorted(child.name for child in published_dir.iterdir() if child.is_file())


def merged_projects() -> List[Dict[str, Any]]:
    config = normalize_config()
    runtime = project_runtime_rows()
    items: List[Dict[str, Any]] = []
    for project in config.get("projects", []):
        row = dict(project)
        runtime_row = runtime.get(project["id"], {})
        row["queue_index"] = int(runtime_row.get("queue_index") or 0)
        queue_items = json.loads(runtime_row.get("queue_json") or "[]") if runtime_row.get("queue_json") else list(project.get("queue") or [])
        row["runtime_status"] = effective_runtime_status(
            stored_status=runtime_row.get("status"),
            queue_len=len(queue_items),
            queue_index=row["queue_index"],
            enabled=bool(project.get("enabled", True)),
            active_run_id=runtime_row.get("active_run_id"),
        )
        row["queue_len"] = len(queue_items)
        row["current_slice"] = queue_items[row["queue_index"]] if row["queue_index"] < len(queue_items) else None
        row["last_error"] = runtime_row.get("last_error")
        row["cooldown_until"] = runtime_row.get("cooldown_until")
        row["consecutive_failures"] = runtime_row.get("consecutive_failures", 0)
        row["published_files"] = studio_published_files(pathlib.Path(project["path"]))
        items.append(row)
    return items


def admin_status_payload() -> Dict[str, Any]:
    config = normalize_config()
    return {
        "config": {
            "policies": config.get("policies", {}),
            "spider": config.get("spider", {}),
            "projects": merged_projects(),
            "accounts": config.get("accounts", {}),
        },
        "recent_runs": recent_runs(),
        "generated_at": iso(utc_now()),
    }


@app.get("/health", response_class=PlainTextResponse)
def health() -> str:
    return "ok"


@app.get("/api/admin/status")
def api_admin_status() -> Dict[str, Any]:
    return admin_status_payload()


@app.post("/api/admin/projects/add")
def api_admin_add_project(
    project_id: str = Form(...),
    repo_path: str = Form(...),
    design_doc: str = Form(""),
    verify_cmd: str = Form(""),
    feedback_dir: str = Form("feedback"),
    state_file: str = Form(".agent-state.json"),
    account_aliases: str = Form(""),
    queue_items: str = Form(""),
    bootstrap_files: Optional[str] = Form(None),
) -> RedirectResponse:
    config = normalize_config()
    if any(project.get("id") == project_id for project in config.get("projects", [])):
        raise HTTPException(400, f"project id already exists: {project_id}")

    repo_root = validate_repo_path(repo_path)
    accounts = split_items(account_aliases)
    queue = split_items(queue_items)
    project = {
        "id": project_id.strip(),
        "path": str(repo_root),
        "design_doc": resolve_optional_repo_file(repo_root, design_doc),
        "verify_cmd": verify_cmd.strip(),
        "feedback_dir": feedback_dir.strip() or "feedback",
        "state_file": state_file.strip() or ".agent-state.json",
        "enabled": True,
        "accounts": accounts,
        "runner": {
            "sandbox": "workspace-write",
            "approval_policy": "never",
            "exec_timeout_seconds": 5400,
            "verify_timeout_seconds": 1800,
            "config_overrides": [],
        },
        "queue": queue,
    }
    if bootstrap_files:
        bootstrap_repo_ai_files(repo_root, project["feedback_dir"], project["state_file"])

    config.setdefault("projects", []).append(project)
    save_fleet_config(config)
    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/projects/{project_id}/pause")
def api_admin_pause_project(project_id: str) -> RedirectResponse:
    set_project_enabled(project_id, False)
    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/projects/{project_id}/resume")
def api_admin_resume_project(project_id: str) -> RedirectResponse:
    set_project_enabled(project_id, True)
    update_project_runtime(project_id, status="idle", clear_cooldown=True)
    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/projects/{project_id}/clear-cooldown")
def api_admin_clear_cooldown(project_id: str) -> RedirectResponse:
    update_project_runtime(project_id, clear_cooldown=True)
    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/projects/{project_id}/retry")
def api_admin_retry_project(project_id: str) -> RedirectResponse:
    update_project_runtime(project_id, status="idle", clear_cooldown=True, reset_failures=True)
    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/projects/{project_id}/run-now")
def api_admin_run_now(project_id: str) -> RedirectResponse:
    update_project_runtime(project_id, status="idle", clear_cooldown=True, reset_failures=True)
    return RedirectResponse("/admin", status_code=303)


@app.get("/admin", response_class=HTMLResponse)
@app.get("/admin/", response_class=HTMLResponse)
def admin_dashboard() -> str:
    status = admin_status_payload()
    projects = status["config"]["projects"]
    accounts = status["config"]["accounts"]
    spider = status["config"]["spider"] or {}
    runs = status["recent_runs"]

    def td(value: Any) -> str:
        return html.escape("" if value is None else str(value))

    project_rows: List[str] = []
    for project in projects:
        actions: List[str] = []
        if project.get("enabled", True):
            actions.append(
                f'<form method="post" action="/api/admin/projects/{project["id"]}/pause"><button type="submit">Pause</button></form>'
            )
        else:
            actions.append(
                f'<form method="post" action="/api/admin/projects/{project["id"]}/resume"><button type="submit">Resume</button></form>'
            )
        actions.append(
            f'<form method="post" action="/api/admin/projects/{project["id"]}/run-now"><button type="submit">Run Now</button></form>'
        )
        actions.append(
            f'<form method="post" action="/api/admin/projects/{project["id"]}/retry"><button type="submit">Retry</button></form>'
        )
        actions.append(
            f'<form method="post" action="/api/admin/projects/{project["id"]}/clear-cooldown"><button type="submit">Clear Cooldown</button></form>'
        )
        project_rows.append(
            f"""
            <tr>
              <td>{td(project.get('id'))}</td>
              <td>{'yes' if project.get('enabled', True) else 'no'}</td>
              <td>{td(project.get('runtime_status'))}</td>
              <td>{td(project.get('path'))}</td>
              <td>{td(project.get('queue_index'))} / {td(project.get('queue_len'))}</td>
              <td>{td(project.get('current_slice'))}</td>
              <td>{td(', '.join(project.get('accounts') or []))}</td>
              <td>{td(project.get('design_doc'))}</td>
              <td>{td(project.get('verify_cmd'))}</td>
              <td>{td(project.get('cooldown_until'))}</td>
              <td>{td(project.get('last_error'))}</td>
              <td>{td(', '.join(project.get('published_files') or []))}</td>
              <td><div class="actions">{''.join(actions)}</div></td>
            </tr>
            """
        )

    account_rows: List[str] = []
    for alias, account in sorted(accounts.items()):
        account_rows.append(
            f"""
            <tr>
              <td>{td(alias)}</td>
              <td>{td(account.get('auth_kind'))}</td>
              <td>{td(', '.join(account.get('allowed_models') or []))}</td>
              <td>{td(account.get('daily_budget_usd'))}</td>
              <td>{td(account.get('monthly_budget_usd'))}</td>
              <td>{td(account.get('max_parallel_runs'))}</td>
            </tr>
            """
        )

    tier_rows: List[str] = []
    for tier, details in (spider.get("tier_preferences") or {}).items():
        tier_rows.append(
            f"""
            <tr>
              <td>{td(tier)}</td>
              <td>{td(', '.join(details.get('models') or []))}</td>
              <td>{td(details.get('reasoning_effort'))}</td>
              <td>{td(details.get('estimated_output_tokens'))}</td>
            </tr>
            """
        )

    price_rows: List[str] = []
    for model, pricing in (spider.get("price_table") or {}).items():
        price_rows.append(
            f"""
            <tr>
              <td>{td(model)}</td>
              <td>{td(pricing.get('input'))}</td>
              <td>{td(pricing.get('cached_input'))}</td>
              <td>{td(pricing.get('output'))}</td>
            </tr>
            """
        )

    run_rows: List[str] = []
    for run in runs[:20]:
        run_rows.append(
            f"""
            <tr>
              <td>{td(run.get('id'))}</td>
              <td>{td(run.get('project_id'))}</td>
              <td>{td(run.get('status'))}</td>
              <td>{td(run.get('slice_name'))}</td>
              <td>{td(run.get('model'))}</td>
              <td>{td(run.get('started_at'))}</td>
              <td>{td(run.get('finished_at'))}</td>
              <td><a href="/api/logs/{run['id']}">log</a></td>
              <td><a href="/api/final/{run['id']}">final</a></td>
            </tr>
            """
        )

    return f"""
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8" />
        <meta http-equiv="refresh" content="15" />
        <title>{APP_TITLE}</title>
        <style>
          body {{ font-family: Arial, sans-serif; margin: 24px; }}
          table {{ border-collapse: collapse; width: 100%; margin-bottom: 24px; }}
          th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; vertical-align: top; }}
          th {{ background: #f4f4f4; }}
          code {{ background: #f4f4f4; padding: 2px 4px; }}
          .muted {{ color: #555; }}
          .actions form {{ display: inline-block; margin: 0 6px 6px 0; }}
          .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 24px; }}
          .panel {{ border: 1px solid #ccc; padding: 16px; }}
          input[type=text], textarea {{ width: 100%; box-sizing: border-box; }}
          textarea {{ min-height: 120px; }}
          label {{ display: block; margin: 12px 0 4px; font-weight: 600; }}
        </style>
      </head>
      <body>
        <h1>{APP_TITLE}</h1>
        <p><a href="/">Open Fleet Dashboard</a> · <a href="/studio">Open Studio</a></p>
        <p><strong>Desired state:</strong> YAML in <code>{td(str(CONFIG_PATH))}</code>. <strong>Runtime state:</strong> SQLite in <code>{td(str(DB_PATH))}</code>.</p>
        <p class="muted">Config changes are picked up automatically by the controller on the next scheduler loop. Pause/Resume edits desired state; Retry/Clear Cooldown/Run Now edit runtime state.</p>

        <div class="grid">
          <div class="panel">
            <h2>Add Project</h2>
            <form method="post" action="/api/admin/projects/add">
              <label for="project_id">Project ID</label>
              <input id="project_id" name="project_id" type="text" placeholder="photos" required />

              <label for="repo_path">Repo Path</label>
              <input id="repo_path" name="repo_path" type="text" placeholder="/docker/photos" required />

              <label for="design_doc">Design Doc</label>
              <input id="design_doc" name="design_doc" type="text" placeholder="docs/design.md or /docker/photos/docs/design.md" />

              <label for="verify_cmd">Verify Command</label>
              <input id="verify_cmd" name="verify_cmd" type="text" placeholder="./scripts/ai/verify.sh" />

              <label for="account_aliases">Account Aliases</label>
              <textarea id="account_aliases" name="account_aliases" placeholder="acct-photos-a&#10;acct-studio-a&#10;acct-shared-b"></textarea>

              <label for="queue_items">Initial Queue</label>
              <textarea id="queue_items" name="queue_items" placeholder="Inspect repository state and bootstrap repo-local AI files&#10;Compile recovery&#10;Contract hardening"></textarea>

              <label for="feedback_dir">Feedback Dir</label>
              <input id="feedback_dir" name="feedback_dir" type="text" value="feedback" />

              <label for="state_file">State File</label>
              <input id="state_file" name="state_file" type="text" value=".agent-state.json" />

              <label><input name="bootstrap_files" type="checkbox" value="1" checked /> Bootstrap repo-local AI files</label>
              <p><button type="submit">Add Project</button></p>
            </form>
          </div>

          <div class="panel">
            <h2>Routing Policy</h2>
            <p><strong>Scheduler interval:</strong> {td(status['config']['policies'].get('scheduler_interval_seconds'))}s</p>
            <p><strong>Max parallel runs:</strong> {td(status['config']['policies'].get('max_parallel_runs'))}</p>
            <p><strong>Token alliance window:</strong> {td(spider.get('token_alliance_window_hours'))}h</p>
          </div>
        </div>

        <h2>Projects</h2>
        <table>
          <thead>
            <tr>
              <th>ID</th><th>Enabled</th><th>Runtime Status</th><th>Path</th><th>Progress</th><th>Current Slice</th><th>Accounts</th><th>Design Doc</th><th>Verify</th><th>Cooldown</th><th>Last Error</th><th>Published Studio Files</th><th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {''.join(project_rows) or '<tr><td colspan="13">No projects configured.</td></tr>'}
          </tbody>
        </table>

        <h2>Accounts</h2>
        <table>
          <thead>
            <tr>
              <th>Alias</th><th>Auth</th><th>Allowed Models</th><th>Day Budget</th><th>Month Budget</th><th>Parallel</th>
            </tr>
          </thead>
          <tbody>
            {''.join(account_rows) or '<tr><td colspan="6">No accounts configured.</td></tr>'}
          </tbody>
        </table>

        <h2>Tier Preferences</h2>
        <table>
          <thead>
            <tr>
              <th>Tier</th><th>Models</th><th>Reasoning</th><th>Estimated Output Tokens</th>
            </tr>
          </thead>
          <tbody>
            {''.join(tier_rows) or '<tr><td colspan="4">No tier preferences configured.</td></tr>'}
          </tbody>
        </table>

        <h2>Price Table</h2>
        <table>
          <thead>
            <tr>
              <th>Model</th><th>Input</th><th>Cached Input</th><th>Output</th>
            </tr>
          </thead>
          <tbody>
            {''.join(price_rows) or '<tr><td colspan="4">No pricing configured.</td></tr>'}
          </tbody>
        </table>

        <h2>Recent Runs</h2>
        <table>
          <thead>
            <tr>
              <th>ID</th><th>Project</th><th>Status</th><th>Slice</th><th>Model</th><th>Started</th><th>Finished</th><th>Log</th><th>Final</th>
            </tr>
          </thead>
          <tbody>
            {''.join(run_rows) or '<tr><td colspan="9">No runs yet.</td></tr>'}
          </tbody>
        </table>
      </body>
    </html>
    """
