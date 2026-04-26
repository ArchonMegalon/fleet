#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


UTC = timezone.utc
DEFAULT_WORKSPACE_ROOT = Path(os.environ.get("FLEET_WORKSPACE_ROOT", "/docker/fleet"))
DEFAULT_STATE_ROOT = DEFAULT_WORKSPACE_ROOT / "state" / "chummer_design_supervisor"
LOOP_PATTERN = "python3 scripts/chummer_design_supervisor.py loop"
SUPERVISOR_SERVICE = "fleet-design-supervisor"
DEFAULT_WATCHDOG_SHARD = "shard-1"
DEFAULT_WATCHDOG_MAX_SILENT_SECONDS = 900


def _parse_iso(text: str) -> datetime | None:
    normalized = str(text or "").strip()
    if not normalized:
        return None
    try:
        return datetime.fromisoformat(normalized.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _mapping_copy(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _runtime_env_candidates() -> tuple[Path, ...]:
    return (
        DEFAULT_WORKSPACE_ROOT / "runtime.env",
        DEFAULT_WORKSPACE_ROOT / "runtime.ea.env",
        DEFAULT_WORKSPACE_ROOT / ".env",
    )


def _runtime_env_value(name: str, default: str = "") -> str:
    direct = str(os.environ.get(name, "") or "").strip()
    if direct:
        return direct
    for candidate in _runtime_env_candidates():
        if not candidate.is_file():
            continue
        try:
            lines = candidate.read_text(encoding="utf-8-sig", errors="ignore").splitlines()
        except OSError:
            continue
        for raw_line in lines:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[7:].strip()
            key, value = line.split("=", 1)
            if key.strip() != name:
                continue
            resolved = value.strip().strip("'").strip('"')
            if resolved:
                return resolved
    return default


def _env_int(name: str, default: int) -> int:
    raw_value = str(_runtime_env_value(name, str(default)) or "").strip()
    try:
        return int(raw_value)
    except ValueError:
        return default


def _discover_state_paths(state_root: Path) -> list[Path]:
    paths: list[Path] = []
    root_state = state_root / "state.json"
    if root_state.is_file():
        paths.append(root_state)

    active_shards_path = state_root / "active_shards.json"
    active_shard_names: list[str] = []
    if active_shards_path.is_file():
        payload = _read_json(active_shards_path)
        for item in payload.get("active_shards") or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if name:
                active_shard_names.append(name)

    if active_shard_names:
        for name in active_shard_names:
            candidate = state_root / name / "state.json"
            if candidate.is_file():
                paths.append(candidate)
    else:
        paths.extend(sorted(state_root.glob("shard-*/state.json")))

    deduped: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(path)
    return deduped


def _state_signal_times(path: Path) -> list[datetime]:
    payload = _read_json(path)
    signals: list[datetime] = []
    for key in (
        "updated_at",
        "worker_last_output_at",
        "worker_first_output_at",
        "active_run_worker_last_output_at",
        "active_run_worker_first_output_at",
    ):
        stamp = _parse_iso(str(payload.get(key) or ""))
        if stamp is not None:
            signals.append(stamp)

    active_run = payload.get("active_run")
    if isinstance(active_run, dict):
        for key in ("started_at", "worker_first_output_at", "worker_last_output_at", "completed_at"):
            stamp = _parse_iso(str(active_run.get(key) or ""))
            if stamp is not None:
                signals.append(stamp)

    if not signals:
        try:
            signals.append(datetime.fromtimestamp(path.stat().st_mtime, tz=UTC))
        except OSError:
            return []
    return signals


def _fresh_state_ok(state_root: Path, max_age_seconds: int) -> tuple[bool, str]:
    state_paths = _discover_state_paths(state_root)
    if not state_paths:
        return False, "state_missing"

    now = datetime.now(UTC)
    fresh_states = 0
    freshest_age_seconds: float | None = None
    invalid_states = 0
    for path in state_paths:
        signals = _state_signal_times(path)
        if not signals:
            invalid_states += 1
            continue
        newest_signal = max(signals)
        age_seconds = max(0.0, (now - newest_signal).total_seconds())
        if freshest_age_seconds is None or age_seconds < freshest_age_seconds:
            freshest_age_seconds = age_seconds
        if age_seconds <= max_age_seconds:
            fresh_states += 1

    if freshest_age_seconds is None:
        return False, f"state_invalid={invalid_states}/{len(state_paths)}"
    if fresh_states <= 0:
        return False, f"state_stale freshest={int(freshest_age_seconds)}s"
    return True, f"state_fresh={fresh_states}/{len(state_paths)} freshest={int(freshest_age_seconds)}s"


def _watchdog_shard_payload(state_root: Path, shard_name: str) -> tuple[dict[str, Any], Path | None]:
    normalized_name = str(shard_name or "").strip()
    if not normalized_name:
        return {}, None

    active_shards_path = state_root / "active_shards.json"
    if active_shards_path.is_file():
        active_shards = _read_json(active_shards_path).get("active_shards") or []
        for item in active_shards:
            if not isinstance(item, dict):
                continue
            candidate_name = str(item.get("name") or item.get("shard_id") or item.get("shard_token") or "").strip()
            if candidate_name == normalized_name:
                return dict(item), active_shards_path

    shard_state_path = state_root / normalized_name / "state.json"
    if shard_state_path.is_file():
        return _read_json(shard_state_path), shard_state_path
    return {}, None


def _watchdog_output_time(payload: dict[str, Any]) -> datetime | None:
    active_run = _mapping_copy(payload.get("active_run"))
    for key in (
        "active_run_worker_last_output_at",
        "worker_last_output_at",
        "active_run_output_updated_at",
        "active_run_worker_first_output_at",
    ):
        stamp = _parse_iso(str(payload.get(key) or ""))
        if stamp is not None:
            return stamp
    for key in ("worker_last_output_at", "worker_first_output_at"):
        stamp = _parse_iso(str(active_run.get(key) or ""))
        if stamp is not None:
            return stamp
    return None


def _watchdog_started_at(payload: dict[str, Any], source_path: Path | None) -> datetime | None:
    active_run = _mapping_copy(payload.get("active_run"))
    for key in ("active_run_started_at", "updated_at"):
        stamp = _parse_iso(str(payload.get(key) or ""))
        if stamp is not None:
            return stamp
    stamp = _parse_iso(str(active_run.get("started_at") or ""))
    if stamp is not None:
        return stamp
    if source_path is None:
        return None
    try:
        return datetime.fromtimestamp(source_path.stat().st_mtime, tz=UTC)
    except OSError:
        return None


def _watchdog_state_ok(
    state_root: Path,
    shard_name: str,
    max_silent_seconds: int,
    startup_grace_seconds: int,
) -> tuple[bool, str]:
    normalized_name = str(shard_name or "").strip()
    if not normalized_name or max_silent_seconds <= 0:
        return True, "watchdog_disabled"

    payload, source_path = _watchdog_shard_payload(state_root, normalized_name)
    if not payload:
        return False, f"watchdog_missing shard={normalized_name}"

    active_run = _mapping_copy(payload.get("active_run"))
    active_run_id = str(payload.get("active_run_id") or active_run.get("run_id") or "").strip()
    progress_state = str(payload.get("active_run_progress_state") or active_run.get("progress_state") or "").strip()
    if not active_run_id:
        return True, f"watchdog_idle shard={normalized_name}"
    if progress_state in {"completed", "complete", "succeeded", "failed", "idle"}:
        return True, f"watchdog_transition shard={normalized_name} progress={progress_state}"

    now = datetime.now(UTC)
    last_output_at = _watchdog_output_time(payload)
    if last_output_at is not None:
        silence_seconds = max(0.0, (now - last_output_at).total_seconds())
        if silence_seconds > max_silent_seconds:
            return False, (
                f"watchdog_stalled shard={normalized_name} silence={int(silence_seconds)}s "
                f"progress={progress_state or 'unknown'}"
            )
        return True, (
            f"watchdog_ok shard={normalized_name} silence={int(silence_seconds)}s "
            f"progress={progress_state or 'unknown'}"
        )

    started_at = _watchdog_started_at(payload, source_path)
    if started_at is None:
        return False, f"watchdog_no_timestamps shard={normalized_name}"

    startup_age_seconds = max(0.0, (now - started_at).total_seconds())
    if startup_age_seconds <= startup_grace_seconds:
        return True, f"watchdog_starting shard={normalized_name} age={int(startup_age_seconds)}s"
    return False, (
        f"watchdog_no_output shard={normalized_name} age={int(startup_age_seconds)}s "
        f"progress={progress_state or 'unknown'}"
    )


def _loop_process_running() -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            ["pgrep", "-f", LOOP_PATTERN],
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
        )
    except Exception as exc:  # pragma: no cover
        return False, f"pgrep_error={exc}"

    pids = [line.strip() for line in str(completed.stdout or "").splitlines() if line.strip()]
    if completed.returncode != 0 or not pids:
        return _container_loop_process_running()
    return True, f"loop_pids={','.join(pids[:4])}"


def _container_loop_process_running() -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            ["docker", "compose", "exec", "-T", SUPERVISOR_SERVICE, "pgrep", "-f", LOOP_PATTERN],
            cwd=str(DEFAULT_WORKSPACE_ROOT),
            check=False,
            capture_output=True,
            text=True,
            timeout=12,
        )
    except FileNotFoundError:
        return False, "loop_process_missing"
    except subprocess.TimeoutExpired:
        return False, "loop_process_missing container_probe_timeout"
    except Exception as exc:  # pragma: no cover
        return False, f"loop_process_missing container_probe_error={exc}"

    pids = [line.strip() for line in str(completed.stdout or "").splitlines() if line.strip()]
    if completed.returncode != 0 or not pids:
        stderr = str(completed.stderr or "").strip().splitlines()
        suffix = f" container_probe_stderr={stderr[-1][:180]}" if stderr else ""
        return False, f"loop_process_missing{suffix}"
    return True, f"loop_container_pids={','.join(pids[:4])}"


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Healthcheck the Chummer design supervisor loop.")
    parser.add_argument("--json", action="store_true", help="Render machine-readable health details.")
    args, _unknown = parser.parse_known_args(argv)
    return args


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    state_root = Path(
        str(os.environ.get("CHUMMER_DESIGN_SUPERVISOR_STATE_ROOT") or DEFAULT_STATE_ROOT).strip()
        or str(DEFAULT_STATE_ROOT)
    )
    max_age_seconds = _env_int("CHUMMER_DESIGN_SUPERVISOR_HEALTH_MAX_AGE_SECONDS", 900)
    watchdog_shard = str(
        os.environ.get("CHUMMER_DESIGN_SUPERVISOR_WATCHDOG_SHARD", DEFAULT_WATCHDOG_SHARD) or ""
    ).strip()
    watchdog_max_silent_seconds = _env_int(
        "CHUMMER_DESIGN_SUPERVISOR_WATCHDOG_MAX_SILENT_SECONDS",
        DEFAULT_WATCHDOG_MAX_SILENT_SECONDS,
    )
    watchdog_startup_grace_seconds = _env_int("CHUMMER_DESIGN_SUPERVISOR_WATCHDOG_STARTUP_GRACE_SECONDS", 900)

    loop_ok, loop_reason = _loop_process_running()
    state_ok, state_reason = _fresh_state_ok(state_root, max_age_seconds)
    watchdog_ok, watchdog_reason = _watchdog_state_ok(
        state_root,
        watchdog_shard,
        watchdog_max_silent_seconds,
        watchdog_startup_grace_seconds,
    )

    ok = loop_ok and state_ok and watchdog_ok
    if args.json:
        print(
            json.dumps(
                {
                    "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                    "ok": ok,
                    "status": "ok" if ok else "unhealthy",
                    "state_root": str(state_root),
                    "max_age_seconds": max_age_seconds,
                    "loop_ok": loop_ok,
                    "loop_reason": loop_reason,
                    "state_ok": state_ok,
                    "state_reason": state_reason,
                    "watchdog_ok": watchdog_ok,
                    "watchdog_reason": watchdog_reason,
                    "watchdog_shard": watchdog_shard,
                    "watchdog_max_silent_seconds": watchdog_max_silent_seconds,
                    "watchdog_startup_grace_seconds": watchdog_startup_grace_seconds,
                },
                sort_keys=True,
            )
        )
        return 0 if ok else 1

    if ok:
        print(f"ok ({loop_reason}; {state_reason}; {watchdog_reason})")
        return 0

    print(f"unhealthy ({loop_reason}; {state_reason}; {watchdog_reason})", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
