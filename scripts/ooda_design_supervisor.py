#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_WORKSPACE_ROOT = Path("/docker/fleet")
DEFAULT_STATE_ROOT = DEFAULT_WORKSPACE_ROOT / "state" / "chummer_design_supervisor"
DEFAULT_MONITOR_ROOT = DEFAULT_WORKSPACE_ROOT / "state" / "design_supervisor_ooda"
DEFAULT_POLL_SECONDS = 300
DEFAULT_DURATION_SECONDS = 8 * 60 * 60
DEFAULT_REPAIR_COOLDOWN_SECONDS = 1800
DEFAULT_STALE_SECONDS = 900
AUTH_ERROR_MARKERS = (
    "auth",
    "token",
    "session",
    "api key",
    "refresh",
    "expired",
    "revoked",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-root", default=str(DEFAULT_WORKSPACE_ROOT))
    parser.add_argument("--state-root", default=str(DEFAULT_STATE_ROOT))
    parser.add_argument("--monitor-root", default=str(DEFAULT_MONITOR_ROOT))
    parser.add_argument("--poll-seconds", type=int, default=DEFAULT_POLL_SECONDS)
    parser.add_argument("--duration-seconds", type=int, default=DEFAULT_DURATION_SECONDS)
    parser.add_argument("--repair-cooldown-seconds", type=int, default=DEFAULT_REPAIR_COOLDOWN_SECONDS)
    parser.add_argument("--stale-seconds", type=int, default=DEFAULT_STALE_SECONDS)
    parser.add_argument("--once", action="store_true")
    return parser.parse_args()


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso_now() -> str:
    return utc_now().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(value: str) -> Optional[dt.datetime]:
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


def log(log_path: Path, message: str) -> None:
    line = f"{iso_now()} {message}"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def run_command(command: list[str], *, cwd: Path, env: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=str(cwd), env=env, capture_output=True, text=True, check=False)


def service_status(workspace_root: Path, service: str) -> str:
    result = run_command(["docker", "compose", "ps", service], cwd=workspace_root)
    combined = " ".join([result.stdout or "", result.stderr or ""]).strip()
    if "Up" in combined:
        return "up"
    if "Exit" in combined or "Exited" in combined:
        return "exited"
    return "unknown"


def restart_service(workspace_root: Path, service: str) -> subprocess.CompletedProcess[str]:
    return run_command(["docker", "compose", "restart", service], cwd=workspace_root)


def source_label(source_key: str) -> str:
    if source_key.startswith("chatgpt_auth_json:") or source_key.startswith("auth_json:"):
        return f"auth.json {source_key.split(':', 1)[1]}"
    if ":env:" in source_key:
        return f"env {source_key.rsplit(':env:', 1)[-1]}"
    return source_key


def should_repair(item: Dict[str, Any], *, now: dt.datetime) -> bool:
    backoff_until = parse_iso(str(item.get("backoff_until") or ""))
    spark_backoff_until = parse_iso(str(item.get("spark_backoff_until") or ""))
    active_until = backoff_until if backoff_until and backoff_until > now else None
    if spark_backoff_until and spark_backoff_until > now and (active_until is None or spark_backoff_until > active_until):
        active_until = spark_backoff_until
    if active_until is None:
        return False
    last_error = str(item.get("last_error") or "").strip().lower()
    return any(marker in last_error for marker in AUTH_ERROR_MARKERS)


def repair_source(workspace_root: Path, item: Dict[str, Any], monitor_state: Dict[str, Any], *, now: dt.datetime) -> tuple[bool, str]:
    source_key = str(item.get("source_key") or "").strip()
    if not source_key:
        return False, "missing source_key"
    repairs = dict(monitor_state.get("repairs") or {})
    previous = parse_iso(str((repairs.get(source_key) or {}).get("attempted_at") or ""))
    cooldown_seconds = int(monitor_state.get("repair_cooldown_seconds") or DEFAULT_REPAIR_COOLDOWN_SECONDS)
    if previous and (now - previous).total_seconds() < cooldown_seconds:
        return False, "repair cooldown active"
    env = os.environ.copy()
    env.update(
        {
            "FLEET_CREDENTIAL_SOURCE_KEY": source_key,
            "FLEET_CREDENTIAL_SOURCE_LABEL": source_label(source_key),
            "FLEET_CREDENTIAL_LAST_ERROR": str(item.get("last_error") or "").strip(),
        }
    )
    completed = run_command(["bash", "scripts/repair_fleet_credential.sh"], cwd=workspace_root, env=env)
    repairs[source_key] = {
        "attempted_at": iso_now(),
        "returncode": completed.returncode,
        "stdout": str(completed.stdout or "").strip()[:800],
        "stderr": str(completed.stderr or "").strip()[:800],
    }
    monitor_state["repairs"] = repairs
    detail = str(completed.stderr or completed.stdout or f"exit {completed.returncode}").strip()
    return completed.returncode == 0, detail


def run_cycle(args: argparse.Namespace, *, log_path: Path, event_path: Path, state_path: Path) -> None:
    workspace_root = Path(args.workspace_root).resolve()
    state_root = Path(args.state_root).resolve()
    monitor_state = read_json(state_path)
    monitor_state["repair_cooldown_seconds"] = int(args.repair_cooldown_seconds)
    now = utc_now()

    state_payload = read_json(state_root / "state.json")
    account_runtime = read_json(state_root / "account_runtime.json")
    controller_state = service_status(workspace_root, "fleet-controller")
    supervisor_state = service_status(workspace_root, "fleet-design-supervisor")
    updated_at = parse_iso(str(state_payload.get("updated_at") or ""))
    stale = updated_at is None or (now - updated_at).total_seconds() > max(60, int(args.stale_seconds))

    append_event(
        event_path,
        {
            "at": iso_now(),
            "observe": {
                "controller": controller_state,
                "supervisor": supervisor_state,
                "updated_at": str(state_payload.get("updated_at") or ""),
                "frontier_ids": state_payload.get("frontier_ids") or [],
                "failure_hint": ((state_payload.get("last_run") or {}).get("failure_hint") or ""),
            },
        },
    )

    if controller_state != "up":
        completed = restart_service(workspace_root, "fleet-controller")
        log(log_path, f"intervene restart fleet-controller rc={completed.returncode}")
    if supervisor_state != "up" or stale:
        completed = restart_service(workspace_root, "fleet-design-supervisor")
        log(log_path, f"intervene restart fleet-design-supervisor rc={completed.returncode} stale={stale}")

    repaired = False
    for item in (account_runtime.get("sources") or {}).values():
        if not isinstance(item, dict) or not should_repair(item, now=now):
            continue
        ok, detail = repair_source(workspace_root, item, monitor_state, now=now)
        repaired = repaired or ok
        log(log_path, f"intervene repair source={item.get('source_key') or ''} ok={ok} detail={detail[:200]}")

    monitor_state["last_cycle_at"] = iso_now()
    monitor_state["last_repair_attempted"] = repaired
    write_json(state_path, monitor_state)


def main() -> int:
    args = parse_args()
    monitor_root = Path(args.monitor_root).resolve()
    monitor_root.mkdir(parents=True, exist_ok=True)
    log_path = monitor_root / "ooda.log"
    event_path = monitor_root / "events.jsonl"
    state_path = monitor_root / "state.json"
    end_time = time.time() + max(1, int(args.duration_seconds))
    while True:
        run_cycle(args, log_path=log_path, event_path=event_path, state_path=state_path)
        if args.once or time.time() >= end_time:
            break
        time.sleep(max(15, int(args.poll_seconds)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
