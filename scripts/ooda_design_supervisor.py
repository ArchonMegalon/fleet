#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_WORKSPACE_ROOT = Path("/docker/fleet")
DEFAULT_STATE_ROOT = DEFAULT_WORKSPACE_ROOT / "state" / "chummer_design_supervisor"
DEFAULT_MONITOR_ROOT = DEFAULT_WORKSPACE_ROOT / "state" / "design_supervisor_ooda"
DEFAULT_POLL_SECONDS = 300
DEFAULT_DURATION_SECONDS = 8 * 60 * 60
DEFAULT_REPAIR_COOLDOWN_SECONDS = 1800
DEFAULT_SERVICE_RESTART_COOLDOWN_SECONDS = 1800
DEFAULT_STALE_SECONDS = 900
DOCKER_SOCKET_PATH = "/var/run/docker.sock"
DOCKER_API_VERSION = "v1.44"
SERVICE_CONTAINER_NAMES = {
    "fleet-controller": "fleet-controller",
    "fleet-design-supervisor": "fleet-design-supervisor",
}
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


def freshest_updated_at(
    aggregate_updated_at: Optional[dt.datetime],
    shard_payloads: List[Dict[str, Any]],
) -> Optional[dt.datetime]:
    freshest = aggregate_updated_at
    for shard_payload in shard_payloads:
        shard_state = dict(shard_payload.get("state") or {})
        shard_updated_at = parse_iso(str(shard_state.get("updated_at") or ""))
        if shard_updated_at is None:
            continue
        if freshest is None or shard_updated_at > freshest:
            freshest = shard_updated_at
    return freshest


def parse_supervisor_status_text(text: str) -> Dict[str, Any]:
    fields: Dict[str, str] = {}
    shards: List[Dict[str, Any]] = []
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line or ": " not in line:
            continue
        key, value = line.split(": ", 1)
        if key.startswith("shard."):
            tokens = [token for token in value.split() if "=" in token]
            parts = dict(token.split("=", 1) for token in tokens)
            active_run_value = str(parts.get("active_run") or "").strip().lower()
            shards.append(
                {
                    "name": key.split(".", 1)[1],
                    "updated_at": str(parts.get("updated_at") or ""),
                    "mode": str(parts.get("mode") or ""),
                    "active_run": active_run_value not in {"", "none"},
                }
            )
            continue
        fields[key] = value.strip()
    return {"fields": fields, "shards": shards}


def read_supervisor_status(workspace_root: Path) -> Dict[str, Any]:
    completed = run_command(
        ["python3", "scripts/chummer_design_supervisor.py", "status"],
        cwd=workspace_root,
    )
    if completed.returncode != 0:
        return {}
    stdout = str(completed.stdout or "").strip()
    if not stdout:
        return {}
    return parse_supervisor_status_text(stdout)


def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def shard_state_roots(state_root: Path) -> List[Path]:
    if not state_root.exists() or not state_root.is_dir():
        return []
    roots: List[Path] = []
    for candidate in sorted(state_root.iterdir()):
        if candidate.is_dir() and candidate.name.startswith("shard-") and (candidate / "state.json").exists():
            roots.append(candidate)
    return roots


def observed_shard_state(
    shard_payload: Dict[str, Any],
    *,
    supervisor_shards: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    name = str(shard_payload.get("name") or "unknown")
    raw_state = dict(shard_payload.get("state") or {})
    supervisor_state = dict(supervisor_shards.get(name) or {})
    active_run = bool(raw_state.get("active_run")) or bool(supervisor_state.get("active_run"))
    return {
        "name": name,
        "updated_at": str(supervisor_state.get("updated_at") or raw_state.get("updated_at") or ""),
        "mode": str(supervisor_state.get("mode") or raw_state.get("mode") or ""),
        "active_run": active_run,
    }


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
    try:
        return subprocess.run(command, cwd=str(cwd), env=env, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        missing = str(exc.filename or command[0] if command else "command")
        return subprocess.CompletedProcess(
            command,
            127,
            stdout="",
            stderr=f"{missing}: not found",
        )


def compose_command(workspace_root: Path, *args: str) -> list[str]:
    docker_bin = shutil.which("docker")
    if docker_bin:
        probe = run_command([docker_bin, "compose", "version"], cwd=workspace_root)
        if probe.returncode == 0:
            return [docker_bin, "compose", *args]
    docker_compose_bin = shutil.which("docker-compose")
    if docker_compose_bin:
        return [docker_compose_bin, *args]
    return [docker_bin or "docker", "compose", *args]


def service_container_name(service: str) -> str:
    return SERVICE_CONTAINER_NAMES.get(service, service)


def docker_socket_request(workspace_root: Path, method: str, path: str) -> Optional[subprocess.CompletedProcess[str]]:
    curl_bin = shutil.which("curl")
    if not curl_bin or not Path(DOCKER_SOCKET_PATH).exists():
        return None
    return run_command(
        [
            curl_bin,
            "--silent",
            "--show-error",
            "--fail",
            "--unix-socket",
            DOCKER_SOCKET_PATH,
            "-X",
            method.upper(),
            f"http://localhost/{DOCKER_API_VERSION}{path}",
        ],
        cwd=workspace_root,
    )


def docker_inspect_state(workspace_root: Path, service: str) -> Optional[Dict[str, Any]]:
    socket_result = docker_socket_request(
        workspace_root,
        "GET",
        f"/containers/{service_container_name(service)}/json",
    )
    if socket_result and socket_result.returncode == 0:
        try:
            payload = json.loads(str(socket_result.stdout or "").strip())
            return dict(payload.get("State") or {})
        except json.JSONDecodeError:
            return None
    docker_bin = shutil.which("docker")
    if not docker_bin:
        return None
    result = run_command(
        [docker_bin, "inspect", "--format", "{{json .State}}", service_container_name(service)],
        cwd=workspace_root,
    )
    if result.returncode != 0:
        return None
    try:
        return json.loads(str(result.stdout or "").strip())
    except json.JSONDecodeError:
        return None


def service_status(workspace_root: Path, service: str) -> str:
    docker_state = docker_inspect_state(workspace_root, service)
    if docker_state:
        status = str(docker_state.get("Status") or "").strip().lower()
        if status == "restarting":
            return "restarting"
        if status == "running":
            return "up"
        if status in {"exited", "dead"}:
            return "exited"
        if status:
            return status
    result = run_command(compose_command(workspace_root, "ps", service), cwd=workspace_root)
    combined = " ".join([result.stdout or "", result.stderr or ""]).strip()
    if "Restarting" in combined:
        return "restarting"
    if "Up" in combined:
        return "up"
    if "Exit" in combined or "Exited" in combined:
        return "exited"
    return "unknown"


def restart_service(workspace_root: Path, service: str) -> subprocess.CompletedProcess[str]:
    socket_result = docker_socket_request(
        workspace_root,
        "POST",
        f"/containers/{service_container_name(service)}/restart",
    )
    if socket_result and socket_result.returncode == 0:
        return socket_result
    docker_bin = shutil.which("docker")
    if docker_bin and docker_inspect_state(workspace_root, service):
        return run_command([docker_bin, "restart", service_container_name(service)], cwd=workspace_root)
    return run_command(compose_command(workspace_root, "restart", service), cwd=workspace_root)


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


def _path_recent_enough(path_value: str, *, now: dt.datetime, threshold_seconds: int) -> bool:
    path_text = str(path_value or "").strip()
    if not path_text:
        return False
    path = Path(path_text)
    if not path.exists():
        return False
    try:
        modified_at = dt.datetime.fromtimestamp(path.stat().st_mtime, tz=dt.timezone.utc)
    except Exception:
        return False
    return (now - modified_at).total_seconds() <= max(60, int(threshold_seconds))


def shard_active_run_still_healthy(shard_state: Dict[str, Any], *, now: dt.datetime, stale_seconds: int) -> bool:
    active_run = dict(shard_state.get("active_run") or {})
    if not active_run:
        return False
    watchdog_seconds = float(active_run.get("watchdog_timeout_seconds") or 0.0)
    started_at = parse_iso(str(active_run.get("started_at") or ""))
    if started_at is not None and watchdog_seconds > 0:
        grace_seconds = max(300, int(stale_seconds))
        if (now - started_at).total_seconds() <= watchdog_seconds + grace_seconds:
            return True
    for key in ("stderr_path", "stdout_path", "last_message_path"):
        if _path_recent_enough(str(active_run.get(key) or ""), now=now, threshold_seconds=stale_seconds):
            return True
    return False


def service_restart_allowed(service: str, monitor_state: Dict[str, Any], *, now: dt.datetime) -> bool:
    restarts = dict(monitor_state.get("service_restarts") or {})
    previous = parse_iso(str((restarts.get(service) or {}).get("attempted_at") or ""))
    cooldown_seconds = int(
        monitor_state.get("service_restart_cooldown_seconds") or DEFAULT_SERVICE_RESTART_COOLDOWN_SECONDS
    )
    if previous and (now - previous).total_seconds() < cooldown_seconds:
        return False
    return True


def record_service_restart(
    service: str,
    completed: subprocess.CompletedProcess[str],
    monitor_state: Dict[str, Any],
) -> None:
    restarts = dict(monitor_state.get("service_restarts") or {})
    restarts[service] = {
        "attempted_at": iso_now(),
        "returncode": completed.returncode,
        "stdout": str(completed.stdout or "").strip()[:800],
        "stderr": str(completed.stderr or "").strip()[:800],
    }
    monitor_state["service_restarts"] = restarts


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
    if not str(monitor_state.get("started_at") or "").strip():
        monitor_state["started_at"] = iso_now()
    monitor_state["repair_cooldown_seconds"] = int(args.repair_cooldown_seconds)
    monitor_state["service_restart_cooldown_seconds"] = int(DEFAULT_SERVICE_RESTART_COOLDOWN_SECONDS)
    now = utc_now()

    state_payload = read_json(state_root / "state.json")
    account_runtime = read_json(state_root / "account_runtime.json")
    supervisor_status = read_supervisor_status(workspace_root)
    supervisor_fields = dict(supervisor_status.get("fields") or {})
    supervisor_shards = {
        str(item.get("name") or "unknown"): dict(item)
        for item in (supervisor_status.get("shards") or [])
        if isinstance(item, dict)
    }
    shard_payloads = [
        {
            "name": shard_root.name,
            "path": str(shard_root),
            "state": read_json(shard_root / "state.json"),
        }
        for shard_root in shard_state_roots(state_root)
    ]
    previous_controller_state = str(monitor_state.get("controller") or "").strip().lower()
    previous_supervisor_state = str(monitor_state.get("supervisor") or "").strip().lower()
    controller_state = service_status(workspace_root, "fleet-controller")
    supervisor_state = service_status(workspace_root, "fleet-design-supervisor")
    if controller_state == "unknown" and previous_controller_state in {"up", "restarting", "exited"}:
        controller_state = previous_controller_state
    if supervisor_state == "unknown" and previous_supervisor_state in {"up", "restarting", "exited"}:
        supervisor_state = previous_supervisor_state
    observed_shards = [
        observed_shard_state(item, supervisor_shards=supervisor_shards)
        for item in shard_payloads
    ]
    frontier_ids = state_payload.get("frontier_ids") or []
    supervisor_mode = str(supervisor_fields.get("mode") or state_payload.get("mode") or "").strip().lower()
    all_shards_complete_or_idle = bool(observed_shards) and all(
        str(item.get("mode") or "").strip().lower() in {"complete", "idle"} and not bool(item.get("active_run"))
        for item in observed_shards
    )
    steady_complete_quiet = (
        not frontier_ids
        and supervisor_mode in {"flagship_product", "complete", "idle"}
        and all_shards_complete_or_idle
    )
    updated_at = freshest_updated_at(
        parse_iso(str(supervisor_fields.get("updated_at") or state_payload.get("updated_at") or "")),
        [{"state": {"updated_at": item.get("updated_at") or ""}} for item in observed_shards],
    )
    aggregate_timestamp_stale = updated_at is None or (now - updated_at).total_seconds() > max(60, int(args.stale_seconds))
    stale_shards: List[str] = []
    inactive_shards: List[str] = []
    for shard_payload, observed in zip(shard_payloads, observed_shards):
        shard_state = dict(shard_payload.get("state") or {})
        shard_updated_at = parse_iso(str(observed.get("updated_at") or shard_state.get("updated_at") or ""))
        active_run_healthy = shard_active_run_still_healthy(
            shard_state,
            now=now,
            stale_seconds=int(args.stale_seconds),
        )
        if (
            not active_run_healthy
            and (shard_updated_at is None or (now - shard_updated_at).total_seconds() > max(60, int(args.stale_seconds)))
        ):
            stale_shards.append(str(observed.get("name") or shard_payload.get("name") or "unknown"))
        shard_mode = str(observed.get("mode") or "").strip().lower()
        if shard_mode not in {"complete", "idle"} and not bool(observed.get("active_run")):
            inactive_shards.append(str(observed.get("name") or shard_payload.get("name") or "unknown"))
    stale = (
        aggregate_timestamp_stale
        and (not shard_payloads or len(stale_shards) == len(shard_payloads))
        and not steady_complete_quiet
    )

    append_event(
        event_path,
        {
            "at": iso_now(),
            "observe": {
                "controller": controller_state,
                "supervisor": supervisor_state,
                "updated_at": updated_at.replace(microsecond=0).isoformat().replace("+00:00", "Z") if updated_at else "",
                "aggregate_stale": stale,
                "aggregate_timestamp_stale": aggregate_timestamp_stale,
                "frontier_ids": frontier_ids,
                "failure_hint": ((state_payload.get("last_run") or {}).get("failure_hint") or ""),
                "stale_shards": stale_shards,
                "inactive_shards": inactive_shards,
                "shard_count": len(shard_payloads),
                "steady_complete_quiet": steady_complete_quiet,
            },
        },
    )

    if controller_state in {"exited", "unknown"} and service_restart_allowed("fleet-controller", monitor_state, now=now):
        completed = restart_service(workspace_root, "fleet-controller")
        record_service_restart("fleet-controller", completed, monitor_state)
        log(log_path, f"intervene restart fleet-controller rc={completed.returncode}")
    if (
        (supervisor_state in {"exited", "unknown"} or stale or stale_shards or inactive_shards)
        and service_restart_allowed("fleet-design-supervisor", monitor_state, now=now)
    ):
        completed = restart_service(workspace_root, "fleet-design-supervisor")
        record_service_restart("fleet-design-supervisor", completed, monitor_state)
        log(
            log_path,
            "intervene restart fleet-design-supervisor "
            f"rc={completed.returncode} stale={stale} "
            f"stale_shards={','.join(stale_shards) or 'none'} "
            f"inactive_shards={','.join(inactive_shards) or 'none'}",
        )

    repaired = False
    for item in (account_runtime.get("sources") or {}).values():
        if not isinstance(item, dict) or not should_repair(item, now=now):
            continue
        ok, detail = repair_source(workspace_root, item, monitor_state, now=now)
        repaired = repaired or ok
        log(log_path, f"intervene repair source={item.get('source_key') or ''} ok={ok} detail={detail[:200]}")

    monitor_state["last_cycle_at"] = iso_now()
    monitor_state["last_repair_attempted"] = repaired
    monitor_state["controller"] = controller_state
    monitor_state["supervisor"] = supervisor_state
    monitor_state["updated_at"] = updated_at.replace(microsecond=0).isoformat().replace("+00:00", "Z") if updated_at else ""
    monitor_state["aggregate_stale"] = stale
    monitor_state["aggregate_timestamp_stale"] = aggregate_timestamp_stale
    monitor_state["frontier_ids"] = frontier_ids
    monitor_state["supervisor_reported_mode"] = str(supervisor_fields.get("mode") or "")
    monitor_state["supervisor_reported_updated_at"] = str(supervisor_fields.get("updated_at") or "")
    monitor_state["steady_complete_quiet"] = steady_complete_quiet
    monitor_state["shards"] = observed_shards
    monitor_state["last_observed_shards"] = observed_shards
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
