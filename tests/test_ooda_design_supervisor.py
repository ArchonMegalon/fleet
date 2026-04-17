from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
from pathlib import Path

from scripts import ooda_design_supervisor as module


def _now() -> dt.datetime:
    return dt.datetime(2026, 4, 1, 5, 20, 0, tzinfo=dt.timezone.utc)


def test_shard_active_run_still_healthy_while_within_watchdog() -> None:
    now = _now()
    shard_state = {
        "updated_at": "2026-04-01T04:48:34Z",
        "active_run": {
            "started_at": "2026-04-01T04:48:34Z",
            "watchdog_timeout_seconds": 21600.0,
        },
    }

    assert module.shard_active_run_still_healthy(shard_state, now=now, stale_seconds=900) is True


def test_service_status_detects_restarting(monkeypatch) -> None:
    monkeypatch.setattr(module.shutil, "which", lambda name: None)
    completed = subprocess.CompletedProcess(
        ["docker", "compose", "ps", "fleet-controller"],
        0,
        stdout="fleet-controller Restarting (3) 59 seconds ago\n",
        stderr="",
    )

    monkeypatch.setattr(module, "run_command", lambda *args, **kwargs: completed)

    assert module.service_status(Path("/docker/fleet"), "fleet-controller") == "restarting"


def test_service_status_prefers_docker_socket(monkeypatch) -> None:
    monkeypatch.setattr(module.shutil, "which", lambda name: "/usr/bin/curl" if name == "curl" else None)
    monkeypatch.setattr(module.Path, "exists", lambda self: str(self) == module.DOCKER_SOCKET_PATH)

    def fake_run_command(command, *, cwd, env=None):  # type: ignore[no-untyped-def]
        if command[:7] == [
            "/usr/bin/curl",
            "--silent",
            "--show-error",
            "--fail",
            "--unix-socket",
            module.DOCKER_SOCKET_PATH,
            "-X",
        ]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout='{"State": {"Status": "running"}}\n',
                stderr="",
            )
        raise AssertionError(command)

    monkeypatch.setattr(module, "run_command", fake_run_command)

    assert module.service_status(Path("/docker/fleet"), "fleet-controller") == "up"


def test_compose_command_falls_back_to_docker_compose(monkeypatch) -> None:
    monkeypatch.setattr(module.shutil, "which", lambda name: None if name == "docker" else "/usr/bin/docker-compose")

    command = module.compose_command(Path("/docker/fleet"), "ps", "fleet-controller")

    assert command == ["/usr/bin/docker-compose", "ps", "fleet-controller"]


def test_compose_command_falls_back_to_docker_when_tools_missing(monkeypatch) -> None:
    monkeypatch.setattr(module.shutil, "which", lambda _name: None)

    command = module.compose_command(Path("/docker/fleet"), "ps", "fleet-controller")

    assert command == ["docker", "compose", "ps", "fleet-controller"]


def test_restart_service_prefers_docker_socket_restart(monkeypatch) -> None:
    monkeypatch.setattr(module.shutil, "which", lambda name: "/usr/bin/curl" if name == "curl" else None)
    monkeypatch.setattr(module.Path, "exists", lambda self: str(self) == module.DOCKER_SOCKET_PATH)

    def fake_run_command(command, *, cwd, env=None):  # type: ignore[no-untyped-def]
        if command[:7] == [
            "/usr/bin/curl",
            "--silent",
            "--show-error",
            "--fail",
            "--unix-socket",
            module.DOCKER_SOCKET_PATH,
            "-X",
        ]:
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        raise AssertionError(command)

    monkeypatch.setattr(module, "run_command", fake_run_command)

    completed = module.restart_service(Path("/docker/fleet"), "fleet-controller")

    assert completed.returncode == 0
    assert completed.stdout == ""


def test_service_restart_allowed_respects_cooldown() -> None:
    now = _now()
    monitor_state = {
        "service_restart_cooldown_seconds": 1800,
        "service_restarts": {
            "fleet-design-supervisor": {
                "attempted_at": "2026-04-01T05:10:00Z",
            }
        },
    }

    assert module.service_restart_allowed("fleet-design-supervisor", monitor_state, now=now) is False


def test_freshest_updated_at_prefers_live_shard_timestamp() -> None:
    aggregate = module.parse_iso("2026-03-31T07:58:10Z")
    shard_payloads = [
        {"state": {"updated_at": "2026-04-01T05:18:38Z"}},
        {"state": {"updated_at": "2026-04-01T05:18:32Z"}},
    ]

    freshest = module.freshest_updated_at(aggregate, shard_payloads)

    assert freshest == module.parse_iso("2026-04-01T05:18:38Z")


def test_eta_payload_from_state_prefers_successor_wave_eta_when_primary_eta_missing() -> None:
    payload = module.eta_payload_from_state(
        {
            "mode": "successor_wave",
            "successor_wave_eta": {
                "status": "tracked",
                "eta_human": "5.6d-2w",
                "summary": "6 milestones remain.",
            },
        }
    )

    assert payload == {
        "status": "tracked",
        "eta_human": "5.6d-2w",
        "summary": "6 milestones remain.",
    }


def test_parse_supervisor_status_text_extracts_effective_shard_modes() -> None:
    payload = module.parse_supervisor_status_text(
        "\n".join(
            [
                "updated_at: 2026-04-01T08:36:20Z",
                "mode: flagship_product",
                "shard.shard-1: updated_at=2026-04-01T08:36:14Z mode=flagship_product open=none frontier=1 active_run=20260401T083614Z",
                "shard.shard-2: updated_at=2026-04-01T08:36:17Z mode=idle open=none frontier=none active_run=none",
            ]
        )
    )

    assert payload["fields"]["mode"] == "flagship_product"
    assert payload["fields"]["updated_at"] == "2026-04-01T08:36:20Z"
    assert payload["shards"] == [
        {
            "name": "shard-1",
            "updated_at": "2026-04-01T08:36:14Z",
            "mode": "flagship_product",
            "active_run": True,
        },
        {
            "name": "shard-2",
            "updated_at": "2026-04-01T08:36:17Z",
            "mode": "idle",
            "active_run": False,
        },
    ]


def test_observed_shard_state_prefers_supervisor_report_over_raw_mode() -> None:
    observed = module.observed_shard_state(
        {
            "name": "shard-1",
            "state": {
                "updated_at": "2026-04-01T08:36:14Z",
                "mode": "completion_review",
                "active_run": {"run_id": "raw-run"},
            },
        },
        supervisor_shards={
            "shard-1": {
                "updated_at": "2026-04-01T08:36:14Z",
                "mode": "flagship_product",
                "active_run": True,
            }
        },
    )

    assert observed["name"] == "shard-1"
    assert observed["updated_at"] == "2026-04-01T08:36:14Z"
    assert observed["mode"] == "flagship_product"
    assert observed["active_run"] is True


def test_run_cycle_does_not_mark_healthy_long_run_as_aggregate_stale(
    monkeypatch,
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    state_root = tmp_path / "state" / "chummer_design_supervisor"
    shard_root = state_root / "shard-1"
    shard_root.mkdir(parents=True)
    (state_root / "state.json").write_text(
        json.dumps({"updated_at": "2026-04-01T04:48:34Z"}) + "\n",
        encoding="utf-8",
    )
    (shard_root / "state.json").write_text(
        json.dumps(
            {
                "updated_at": "2026-04-01T04:48:34Z",
                "mode": "completion_review",
                "active_run": {
                    "started_at": "2026-04-01T04:48:34Z",
                    "watchdog_timeout_seconds": 21600.0,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    log_path = tmp_path / "monitor" / "ooda.log"
    event_path = tmp_path / "monitor" / "events.jsonl"
    state_path = tmp_path / "monitor" / "state.json"
    args = argparse.Namespace(
        workspace_root=str(workspace_root),
        state_root=str(state_root),
        monitor_root=str(tmp_path / "monitor"),
        poll_seconds=300,
        duration_seconds=28800,
        repair_cooldown_seconds=1800,
        stale_seconds=900,
        once=True,
    )

    def fake_run_command(command, *, cwd, env=None):  # type: ignore[no-untyped-def]
        if command[:3] == ["python3", "scripts/chummer_design_supervisor.py", "status"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=(
                    "updated_at: 2026-04-01T04:48:34Z\n"
                    "mode: flagship_product\n"
                    "shard.shard-1: updated_at=2026-04-01T04:48:34Z "
                    "mode=flagship_product open=none frontier=1 active_run=20260401T044834Z\n"
                ),
                stderr="",
            )
        if command[:7] == [
            "/usr/bin/curl",
            "--silent",
            "--show-error",
            "--fail",
            "--unix-socket",
            module.DOCKER_SOCKET_PATH,
            "-X",
        ]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout='{"State": {"Status": "running"}}\n',
                stderr="",
            )
        if command[-2:] == ["compose", "version"]:
            return subprocess.CompletedProcess(command, 0, stdout="Docker Compose version v2.0.0\n", stderr="")
        if command[-3:] == ["compose", "ps", "fleet-controller"] or command[-3:] == ["compose", "ps", "fleet-design-supervisor"]:
            return subprocess.CompletedProcess(command, 0, stdout="service Up\n", stderr="")
        raise AssertionError(command)

    monkeypatch.setattr(module, "utc_now", _now)
    monkeypatch.setattr(module, "run_command", fake_run_command)

    module.run_cycle(args, log_path=log_path, event_path=event_path, state_path=state_path)

    payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert payload["aggregate_stale"] is False
    assert payload["aggregate_timestamp_stale"] is True
    assert payload["updated_at"] == "2026-04-01T04:48:34Z"
    assert payload["frontier_ids"] == []
    assert payload["supervisor_reported_mode"] == "flagship_product"
    assert payload["shards"][0]["mode"] == "flagship_product"
    assert payload["last_observed_shards"][0]["mode"] == "flagship_product"


def test_run_cycle_keeps_last_known_service_status_when_probes_unavailable(
    monkeypatch,
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    state_root = tmp_path / "state" / "chummer_design_supervisor"
    shard_root = state_root / "shard-1"
    shard_root.mkdir(parents=True)
    (state_root / "state.json").write_text(
        json.dumps({"updated_at": "2026-04-01T04:48:34Z", "mode": "complete", "frontier_ids": []}) + "\n",
        encoding="utf-8",
    )
    (shard_root / "state.json").write_text(
        json.dumps(
            {
                "updated_at": "2026-04-01T04:48:34Z",
                "mode": "complete",
                "active_run": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    log_path = tmp_path / "monitor" / "ooda.log"
    event_path = tmp_path / "monitor" / "events.jsonl"
    state_path = tmp_path / "monitor" / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps({"controller": "up", "supervisor": "up"}) + "\n",
        encoding="utf-8",
    )
    args = argparse.Namespace(
        workspace_root=str(workspace_root),
        state_root=str(state_root),
        monitor_root=str(tmp_path / "monitor"),
        poll_seconds=300,
        duration_seconds=28800,
        repair_cooldown_seconds=1800,
        stale_seconds=900,
        once=True,
    )

    def fake_run_command(command, *, cwd, env=None):  # type: ignore[no-untyped-def]
        if command[:3] == ["python3", "scripts/chummer_design_supervisor.py", "status"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=(
                    "updated_at: 2026-04-01T04:48:34Z\n"
                    "mode: complete\n"
                    "shard.shard-1: updated_at=2026-04-01T04:48:34Z mode=complete open=none frontier=none active_run=none\n"
                ),
                stderr="",
            )
        if command[-3:] == ["compose", "ps", "fleet-controller"] or command[-3:] == [
            "compose",
            "ps",
            "fleet-design-supervisor",
        ]:
            return subprocess.CompletedProcess(command, 127, stdout="", stderr="docker: not found")
        if command[-3:] == ["compose", "restart", "fleet-design-supervisor"]:
            return subprocess.CompletedProcess(command, 127, stdout="", stderr="docker: not found")
        raise AssertionError(command)

    monkeypatch.setattr(module, "utc_now", _now)
    monkeypatch.setattr(module, "run_command", fake_run_command)
    monkeypatch.setattr(module.shutil, "which", lambda _name: None)

    module.run_cycle(args, log_path=log_path, event_path=event_path, state_path=state_path)

    payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert payload["controller"] == "up"
    assert payload["supervisor"] == "up"


def test_run_cycle_treats_complete_idle_snapshot_as_non_stale(
    monkeypatch,
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    state_root = tmp_path / "state" / "chummer_design_supervisor"
    shard_root = state_root / "shard-1"
    shard_root.mkdir(parents=True)
    (state_root / "state.json").write_text(
        json.dumps(
            {
                "updated_at": "2026-04-01T04:00:00Z",
                "mode": "complete",
                "frontier_ids": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (shard_root / "state.json").write_text(
        json.dumps(
            {
                "updated_at": "2026-04-01T04:00:00Z",
                "mode": "complete",
                "active_run": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    log_path = tmp_path / "monitor" / "ooda.log"
    event_path = tmp_path / "monitor" / "events.jsonl"
    state_path = tmp_path / "monitor" / "state.json"
    args = argparse.Namespace(
        workspace_root=str(workspace_root),
        state_root=str(state_root),
        monitor_root=str(tmp_path / "monitor"),
        poll_seconds=300,
        duration_seconds=28800,
        repair_cooldown_seconds=1800,
        stale_seconds=900,
        once=True,
    )

    def fake_run_command(command, *, cwd, env=None):  # type: ignore[no-untyped-def]
        if command[:3] == ["python3", "scripts/chummer_design_supervisor.py", "status"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=(
                    "updated_at: 2026-04-01T04:00:00Z\n"
                    "mode: complete\n"
                    "shard.shard-1: updated_at=2026-04-01T04:00:00Z "
                    "mode=complete open=none frontier=none active_run=none\n"
                ),
                stderr="",
            )
        if command[:7] == [
            "/usr/bin/curl",
            "--silent",
            "--show-error",
            "--fail",
            "--unix-socket",
            module.DOCKER_SOCKET_PATH,
            "-X",
        ]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout='{"State": {"Status": "running"}}\n',
                stderr="",
            )
        if command[-2:] == ["compose", "version"]:
            return subprocess.CompletedProcess(command, 0, stdout="Docker Compose version v2.0.0\n", stderr="")
        if command[-3:] == ["compose", "ps", "fleet-controller"] or command[-3:] == ["compose", "ps", "fleet-design-supervisor"]:
            return subprocess.CompletedProcess(command, 0, stdout="service Up\n", stderr="")
        if command[-3:] == ["compose", "restart", "fleet-design-supervisor"]:
            return subprocess.CompletedProcess(command, 0, stdout="restarted\n", stderr="")
        raise AssertionError(command)

    monkeypatch.setattr(module, "utc_now", _now)
    monkeypatch.setattr(module, "run_command", fake_run_command)

    module.run_cycle(args, log_path=log_path, event_path=event_path, state_path=state_path)

    payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert payload["aggregate_stale"] is False
    assert payload["aggregate_timestamp_stale"] is True
    assert payload["steady_complete_quiet"] is True


def test_run_cycle_persists_structured_eta_payload_for_successor_wave(
    monkeypatch,
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    state_root = tmp_path / "state" / "chummer_design_supervisor"
    shard_root = state_root / "shard-1"
    shard_root.mkdir(parents=True)
    (state_root / "state.json").write_text(
        json.dumps(
            {
                "updated_at": "2026-04-01T04:48:34Z",
                "mode": "successor_wave",
                "active_runs_count": 6,
                "eta_status": "tracked",
                "successor_wave_eta": {
                    "status": "tracked",
                    "eta_human": "5.6d-2w",
                    "summary": "6 next-wave milestones remain.",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (shard_root / "state.json").write_text(
        json.dumps(
            {
                "updated_at": "2026-04-01T04:48:34Z",
                "mode": "successor_wave",
                "active_run": {
                    "started_at": "2026-04-01T04:48:34Z",
                    "watchdog_timeout_seconds": 21600.0,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    log_path = tmp_path / "monitor" / "ooda.log"
    event_path = tmp_path / "monitor" / "events.jsonl"
    state_path = tmp_path / "monitor" / "state.json"
    args = argparse.Namespace(
        workspace_root=str(workspace_root),
        state_root=str(state_root),
        monitor_root=str(tmp_path / "monitor"),
        poll_seconds=300,
        duration_seconds=28800,
        repair_cooldown_seconds=1800,
        stale_seconds=900,
        once=True,
    )

    def fake_run_command(command, *, cwd, env=None):  # type: ignore[no-untyped-def]
        if command[:3] == ["python3", "scripts/chummer_design_supervisor.py", "status"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=(
                    "updated_at: 2026-04-01T04:48:34Z\n"
                    "mode: successor_wave\n"
                    "shard.shard-1: updated_at=2026-04-01T04:48:34Z "
                    "mode=successor_wave open=none frontier=1 active_run=20260401T044834Z\n"
                ),
                stderr="",
            )
        if command[:7] == [
            "/usr/bin/curl",
            "--silent",
            "--show-error",
            "--fail",
            "--unix-socket",
            module.DOCKER_SOCKET_PATH,
            "-X",
        ]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout='{"State": {"Status": "running"}}\n',
                stderr="",
            )
        if command[-2:] == ["compose", "version"]:
            return subprocess.CompletedProcess(command, 0, stdout="Docker Compose version v2.0.0\n", stderr="")
        if command[-3:] == ["compose", "ps", "fleet-controller"] or command[-3:] == ["compose", "ps", "fleet-design-supervisor"]:
            return subprocess.CompletedProcess(command, 0, stdout="service Up\n", stderr="")
        raise AssertionError(command)

    monkeypatch.setattr(module, "utc_now", _now)
    monkeypatch.setattr(module, "run_command", fake_run_command)

    module.run_cycle(args, log_path=log_path, event_path=event_path, state_path=state_path)

    payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert payload["eta"]["status"] == "tracked"
    assert payload["eta"]["eta_human"] == "5.6d-2w"
    assert payload["eta_human"] == "5.6d-2w"
    assert payload["eta_status"] == "tracked"


def test_run_cycle_treats_flagship_product_quiet_snapshot_as_non_stale(
    monkeypatch,
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    state_root = tmp_path / "state" / "chummer_design_supervisor"
    shard_root = state_root / "shard-1"
    shard_root.mkdir(parents=True)
    (state_root / "state.json").write_text(
        json.dumps(
            {
                "updated_at": "2026-04-01T04:00:00Z",
                "mode": "flagship_product",
                "frontier_ids": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (shard_root / "state.json").write_text(
        json.dumps(
            {
                "updated_at": "2026-04-01T04:00:00Z",
                "mode": "complete",
                "active_run": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    log_path = tmp_path / "monitor" / "ooda.log"
    event_path = tmp_path / "monitor" / "events.jsonl"
    state_path = tmp_path / "monitor" / "state.json"
    args = argparse.Namespace(
        workspace_root=str(workspace_root),
        state_root=str(state_root),
        monitor_root=str(tmp_path / "monitor"),
        poll_seconds=300,
        duration_seconds=28800,
        repair_cooldown_seconds=1800,
        stale_seconds=900,
        once=True,
    )

    def fake_run_command(command, *, cwd, env=None):  # type: ignore[no-untyped-def]
        if command[:3] == ["python3", "scripts/chummer_design_supervisor.py", "status"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=(
                    "updated_at: 2026-04-01T04:00:00Z\n"
                    "mode: flagship_product\n"
                    "shard.shard-1: updated_at=2026-04-01T04:00:00Z "
                    "mode=complete open=none frontier=none active_run=none\n"
                ),
                stderr="",
            )
        if command[:7] == [
            "/usr/bin/curl",
            "--silent",
            "--show-error",
            "--fail",
            "--unix-socket",
            module.DOCKER_SOCKET_PATH,
            "-X",
        ]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout='{"State": {"Status": "running"}}\n',
                stderr="",
            )
        if command[-2:] == ["compose", "version"]:
            return subprocess.CompletedProcess(command, 0, stdout="Docker Compose version v2.0.0\n", stderr="")
        if command[-3:] == ["compose", "ps", "fleet-controller"] or command[-3:] == ["compose", "ps", "fleet-design-supervisor"]:
            return subprocess.CompletedProcess(command, 0, stdout="service Up\n", stderr="")
        if command[-3:] == ["compose", "restart", "fleet-design-supervisor"]:
            return subprocess.CompletedProcess(command, 0, stdout="restarted\n", stderr="")
        raise AssertionError(command)

    monkeypatch.setattr(module, "utc_now", _now)
    monkeypatch.setattr(module, "run_command", fake_run_command)

    module.run_cycle(args, log_path=log_path, event_path=event_path, state_path=state_path)

    payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert payload["aggregate_stale"] is False
    assert payload["aggregate_timestamp_stale"] is True
    assert payload["steady_complete_quiet"] is True
