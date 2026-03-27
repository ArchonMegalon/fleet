from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import time
from pathlib import Path


SCRIPT = Path("/docker/fleet/scripts/rebuild-loop.sh")


FAKE_DOCKER = """#!/usr/bin/env python3
from __future__ import annotations
import os
import sys
from pathlib import Path

state_dir = Path(os.environ["FAKE_DOCKER_STATE_DIR"])
state_dir.mkdir(parents=True, exist_ok=True)
args = sys.argv[1:]

def current_status(service: str) -> str:
    env_key = "FAKE_STATUS_" + service.replace("-", "_").upper()
    default = os.environ.get(env_key, "healthy")
    if service == "fleet-controller" and (state_dir / f"{service}.restarted").exists():
        return "healthy"
    return default

if not args:
    raise SystemExit(1)

if args[0] == "inspect":
    template = ""
    if "-f" in args:
        template = args[args.index("-f") + 1]
    service = args[-1]
    status = current_status(service)
    if "State.Health.Log" in template:
        sys.stdout.write("ok\\n" if status == "healthy" else "timed out\\n")
    else:
        sys.stdout.write(status)
    raise SystemExit(0)

if args[0] == "compose":
    filtered = []
    skip = False
    for arg in args[1:]:
        if skip:
            skip = False
            continue
        if arg in {"-p", "-f"}:
            skip = True
            continue
        filtered.append(arg)
    with (state_dir / "calls.log").open("a", encoding="utf-8") as handle:
        handle.write(" ".join(filtered) + "\\n")
    if filtered and filtered[0] == "restart":
        for service in filtered[1:]:
            (state_dir / f"{service}.restarted").write_text("1", encoding="utf-8")
    raise SystemExit(0)

raise SystemExit(0)
"""


def _write_fake_docker(root: Path) -> Path:
    bin_dir = root / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    docker_path = bin_dir / "docker"
    docker_path.write_text(FAKE_DOCKER, encoding="utf-8")
    docker_path.chmod(docker_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return docker_path


def _run_loop(tmp_path: Path, *, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    _write_fake_docker(tmp_path)
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{tmp_path / 'bin'}:{env.get('PATH', '')}",
            "FAKE_DOCKER_STATE_DIR": str(tmp_path / "fake-docker"),
            "FAKE_STATUS_FLEET_CONTROLLER": "unhealthy",
            "FLEET_REBUILD_ENABLED": "false",
            "FLEET_AUTOHEAL_ENABLED": "true",
            "FLEET_AUTOHEAL_SERVICES": "fleet-controller",
            "FLEET_AUTOHEAL_THRESHOLD": "1",
            "FLEET_AUTOHEAL_COOLDOWN_SECONDS": "0",
            "FLEET_AUTOHEAL_TIMEOUT_SECONDS": "5",
            "FLEET_REBUILD_LOOP_ONCE": "true",
            "FLEET_REBUILD_STATE_DIR": str(tmp_path / "state" / "rebuilder"),
            "FLEET_COMPOSE_PROJECT_NAME": "fleet",
        }
    )
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=str(tmp_path),
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )


def test_rebuild_loop_autoheal_recovers_unhealthy_controller(tmp_path: Path) -> None:
    result = _run_loop(tmp_path)
    assert result.returncode == 0, result.stderr

    status_path = tmp_path / "state" / "rebuilder" / "autoheal" / "fleet-controller.status.json"
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    assert payload["current_state"] == "recovered"
    assert payload["total_restarts"] == 1
    assert payload["last_result"] == "recovered"

    events = [
        json.loads(line)
        for line in (tmp_path / "state" / "rebuilder" / "autoheal" / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [event["event"] for event in events][-2:] == ["restart_started", "restart_recovered"]

    calls_log = (tmp_path / "fake-docker" / "calls.log").read_text(encoding="utf-8")
    assert "restart fleet-controller" in calls_log


def test_rebuild_loop_autoheal_escalates_after_recent_restart_budget_is_exhausted(tmp_path: Path) -> None:
    autoheal_dir = tmp_path / "state" / "rebuilder" / "autoheal"
    autoheal_dir.mkdir(parents=True, exist_ok=True)
    now_epoch = int(time.time())
    (autoheal_dir / "fleet-controller.restart_window_start_epoch").write_text(str(now_epoch), encoding="utf-8")
    (autoheal_dir / "fleet-controller.restart_window_count").write_text("1", encoding="utf-8")

    result = _run_loop(
        tmp_path,
        extra_env={
            "FLEET_AUTOHEAL_ESCALATE_AFTER_RESTARTS": "1",
            "FLEET_AUTOHEAL_ESCALATE_WINDOW_SECONDS": "1800",
        },
    )
    assert result.returncode == 0, result.stderr

    status_path = autoheal_dir / "fleet-controller.status.json"
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    assert payload["current_state"] == "escalation_required"
    assert payload["total_restarts"] == 0

    events = [
        json.loads(line)
        for line in (autoheal_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert events[-1]["event"] == "escalation_required"

    calls_log_path = tmp_path / "fake-docker" / "calls.log"
    calls_log = calls_log_path.read_text(encoding="utf-8") if calls_log_path.is_file() else ""
    assert "restart fleet-controller" not in calls_log
