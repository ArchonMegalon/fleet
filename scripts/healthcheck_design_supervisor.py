#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


UTC = timezone.utc
DEFAULT_STATE_ROOT = Path("/var/lib/codex-fleet/chummer_design_supervisor")
LOOP_PATTERN = "python3 scripts/chummer_design_supervisor.py loop"


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


def _loop_process_running() -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            ["pgrep", "-f", LOOP_PATTERN],
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception as exc:  # pragma: no cover
        return False, f"pgrep_error={exc}"

    pids = [line.strip() for line in str(completed.stdout or "").splitlines() if line.strip()]
    if completed.returncode != 0 or not pids:
        return False, "loop_process_missing"
    return True, f"loop_pids={','.join(pids[:4])}"


def main() -> int:
    state_root = Path(
        str(os.environ.get("CHUMMER_DESIGN_SUPERVISOR_STATE_ROOT") or DEFAULT_STATE_ROOT).strip()
        or str(DEFAULT_STATE_ROOT)
    )
    max_age_seconds = int(os.environ.get("CHUMMER_DESIGN_SUPERVISOR_HEALTH_MAX_AGE_SECONDS", "900") or "900")

    loop_ok, loop_reason = _loop_process_running()
    state_ok, state_reason = _fresh_state_ok(state_root, max_age_seconds)
    if loop_ok and state_ok:
        print(f"ok ({loop_reason}; {state_reason})")
        return 0

    print(f"unhealthy ({loop_reason}; {state_reason})", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
