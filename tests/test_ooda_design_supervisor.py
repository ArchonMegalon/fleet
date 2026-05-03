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


def test_run_command_returns_timeout_completed_process(monkeypatch, tmp_path: Path) -> None:
    def fake_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs.get("timeout", 0))

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    completed = module.run_command(
        ["python3", "scripts/chummer_design_supervisor.py", "status"],
        cwd=tmp_path,
        timeout_seconds=5,
    )

    assert completed.returncode == 124
    assert "timeout after 5s" in completed.stderr


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


def test_supervisor_restart_needed_ignores_small_inactive_minority() -> None:
    assert (
        module.supervisor_restart_needed(
            supervisor_state="up",
            aggregate_stale=False,
            stale_shards=[],
            inactive_shards=["shard-11", "shard-12"],
            shard_count=13,
        )
        is False
    )


def test_supervisor_restart_needed_restarts_when_inactive_quorum_is_down() -> None:
    assert (
        module.supervisor_restart_needed(
            supervisor_state="up",
            aggregate_stale=False,
            stale_shards=[],
            inactive_shards=[f"shard-{index}" for index in range(1, 8)],
            shard_count=13,
        )
        is True
    )


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
                "remaining_open_milestones": 6,
            },
        }
    )

    assert payload == {
        "status": "tracked",
        "eta_human": "5.6d-2w",
        "summary": "6 milestones remain.",
        "remaining_open_milestones": 6,
    }
    assert module.remaining_open_milestones_from_state({}, payload) == 6


def test_remaining_open_milestones_from_state_prefers_explicit_open_ids_over_stale_successor_wave_count() -> None:
    payload = {
        "successor_wave_remaining_open_milestones": 37,
        "open_milestone_ids": [101, 102, 103, 104],
        "frontier_ids": [101, 102, 103, 104],
    }

    assert module.remaining_open_milestones_from_state(payload, {}) == 4


def test_path_recent_enough_resolves_container_local_state_mount(
    monkeypatch,
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "fleet"
    artifact = workspace_root / "state" / "chummer_design_supervisor" / "shard-1" / "runs" / "run-1" / "worker.stderr.log"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text("hello\n", encoding="utf-8")
    monkeypatch.setattr(module, "DEFAULT_WORKSPACE_ROOT", workspace_root)

    now = dt.datetime.fromtimestamp(artifact.stat().st_mtime, tz=dt.timezone.utc) + dt.timedelta(seconds=5)

    assert (
        module._path_recent_enough(
            "/var/lib/codex-fleet/chummer_design_supervisor/shard-1/runs/run-1/worker.stderr.log",
            now=now,
            threshold_seconds=60,
        )
        is True
    )


def test_shard_active_run_still_healthy_accepts_container_local_output_paths(
    monkeypatch,
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "fleet"
    artifact = workspace_root / "state" / "chummer_design_supervisor" / "shard-1" / "runs" / "run-1" / "worker.stdout.log"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text("progress\n", encoding="utf-8")
    monkeypatch.setattr(module, "DEFAULT_WORKSPACE_ROOT", workspace_root)
    now = dt.datetime.fromtimestamp(artifact.stat().st_mtime, tz=dt.timezone.utc) + dt.timedelta(seconds=5)

    shard_state = {
        "active_run": {
            "started_at": "2026-05-03T10:00:00Z",
            "watchdog_timeout_seconds": 0.0,
            "stdout_path": "/var/lib/codex-fleet/chummer_design_supervisor/shard-1/runs/run-1/worker.stdout.log",
        }
    }

    assert module.shard_active_run_still_healthy(shard_state, now=now, stale_seconds=60) is True


def test_merge_richer_runtime_fields_prefers_more_productive_split_when_active_run_count_matches() -> None:
    payload = {
        "updated_at": "2026-05-03T10:20:30Z",
        "active_runs_count": 14,
        "productive_active_runs_count": 0,
        "waiting_active_runs_count": 14,
    }
    candidate = {
        "updated_at": "2026-05-03T10:20:25Z",
        "active_runs_count": 14,
        "productive_active_runs_count": 3,
        "waiting_active_runs_count": 11,
        "progress_evidence_counts": {"repo_work_detected": 3, "worker_output_only": 11},
    }

    merged = module.merge_richer_runtime_fields(payload, candidate)

    assert merged["productive_active_runs_count"] == 3
    assert merged["waiting_active_runs_count"] == 11
    assert merged["progress_evidence_counts"] == {"repo_work_detected": 3, "worker_output_only": 11}


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


def test_run_cycle_prefers_active_shards_manifest_for_live_active_count(
    monkeypatch,
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    state_root = tmp_path / "state" / "chummer_design_supervisor"
    state_root.mkdir(parents=True)
    (state_root / "state.json").write_text(
        json.dumps(
            {
                "updated_at": "2026-04-01T04:48:34Z",
                "mode": "flagship_product",
                "active_runs_count": 6,
                "provider_capacity_summary": {
                    "allowed_active_shards": 9,
                    "configured_shard_count": 13,
                    "ready_slots": 10,
                    "hard_max_active_requests": 8,
                    "estimated_remaining_credits_total": 44198385,
                    "reason": "live provider capacity caps shard dispatch at 9/13",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (state_root / "active_shards.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-04-01T04:48:40Z",
                "active_run_count": 9,
                "active_shards": [
                    {
                        "name": "shard-1",
                        "shard_id": "shard-1",
                        "active_run_id": "run-1",
                        "active_run_progress_state": "streaming",
                        "active_run_progress_evidence": "repo_work_detected",
                        "active_run_worker_last_output_at": "2026-04-01T04:48:39Z",
                        "selected_account_alias": "acct-chatgpt-b",
                        "selected_model": "gpt-5.4",
                    },
                    {
                        "name": "shard-7",
                        "shard_id": "shard-7",
                        "active_run_id": "run-7",
                        "active_run_progress_state": "running_silent",
                        "active_run_progress_evidence": "worker_output_only",
                        "active_run_worker_last_output_at": "2026-04-01T04:48:38Z",
                        "selected_account_alias": "lane:core",
                        "selected_model": "qwen3-coder-next:q8_0",
                    },
                    {
                        "name": "shard-10",
                        "shard_id": "shard-10",
                    },
                ],
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
                stdout="updated_at: 2026-04-01T04:48:34Z\nmode: flagship_product\n",
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
    assert payload["active_runs_count"] == 2
    assert payload["active_shards_count"] == 2
    assert payload["allowed_active_shards"] == 9
    assert payload["provider_ready_slots"] == 10
    assert payload["provider_hard_max_active_requests"] == 8
    assert payload["provider_capacity_summary"]["estimated_remaining_credits_total"] == 44198385
    assert payload["provider_capacity_summary"]["ready_slots"] == 10
    assert [item["shard_id"] for item in payload["active_shards"]] == ["shard-1", "shard-7"]
    assert payload["active_shards"][0]["progress_evidence"] == "repo_work_detected"
    assert payload["active_shards"][1]["selected_model"] == "qwen3-coder-next:q8_0"


def test_run_cycle_preserves_zero_provider_ready_slots(
    monkeypatch,
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    state_root = tmp_path / "state" / "chummer_design_supervisor"
    state_root.mkdir(parents=True)
    (state_root / "state.json").write_text(
        json.dumps(
            {
                "updated_at": "2026-04-01T04:48:34Z",
                "mode": "flagship_product",
                "active_runs_count": 1,
                "productive_active_runs_count": 0,
                "waiting_active_runs_count": 1,
                "allowed_active_shards": 10,
                "provider_ready_slots": 0,
                "provider_hard_max_active_requests": 20,
                "dispatch_reason": "live provider capacity caps shard dispatch at 10/20",
                "remaining_open_milestones": 20,
                "eta": {
                    "status": "tracked",
                    "eta_human": "11h-1.1d",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (state_root / "active_shards.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-04-01T04:48:40Z",
                "active_run_count": 1,
                "active_shards": [
                    {
                        "name": "shard-1",
                        "shard_id": "shard-1",
                        "active_run_id": "run-1",
                        "active_run_progress_state": "running_silent",
                        "active_run_progress_evidence": "worker_output_only",
                    }
                ],
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
                stdout="updated_at: 2026-04-01T04:48:34Z\nmode: flagship_product\n",
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

    monkeypatch.setattr(module, "utc_now", lambda: dt.datetime(2026, 4, 1, 5, 20, tzinfo=dt.timezone.utc))
    monkeypatch.setattr(module, "run_command", fake_run_command)

    module.run_cycle(args, log_path=log_path, event_path=event_path, state_path=state_path)

    payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert payload["provider_ready_slots"] == 0
    assert payload["productive_active_runs_count"] == 0
    assert payload["waiting_active_runs_count"] == 1


def test_run_cycle_prefers_richer_existing_materialized_runtime_fields(
    monkeypatch,
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    state_root = tmp_path / "state" / "chummer_design_supervisor"
    state_root.mkdir(parents=True)
    (state_root / "state.json").write_text(
        json.dumps(
            {
                "updated_at": "2026-04-01T04:48:34Z",
                "mode": "flagship_product",
                "active_runs_count": 0,
                "productive_active_runs_count": 0,
                "waiting_active_runs_count": 0,
                "remaining_open_milestones": 19,
                "eta": {
                    "status": "tracked",
                    "eta_human": "11h-1.1d",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (state_root / "active_shards.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-04-01T04:48:40Z",
                "active_run_count": 0,
                "active_shards": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    module.materialized_status_path(state_root).write_text(
        json.dumps(
            {
                "updated_at": "2026-04-01T05:18:00Z",
                "allowed_active_shards": 14,
                "provider_ready_slots": 14,
                "provider_hard_max_active_requests": 20,
                "active_runs_count": 11,
                "productive_active_runs_count": 5,
                "waiting_active_runs_count": 6,
                "remaining_open_milestones": 18,
                "dispatch_reason": "live provider capacity caps shard dispatch at 14/20",
                "provider_capacity_summary": {
                    "allowed_active_shards": 14,
                    "ready_slots": 14,
                    "hard_max_active_requests": 20,
                    "reason": "live provider capacity caps shard dispatch at 14/20",
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
                stdout="updated_at: 2026-04-01T04:48:34Z\nmode: flagship_product\n",
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

    monkeypatch.setattr(module, "utc_now", lambda: dt.datetime(2026, 4, 1, 5, 20, tzinfo=dt.timezone.utc))
    monkeypatch.setattr(module, "run_command", fake_run_command)

    module.run_cycle(args, log_path=log_path, event_path=event_path, state_path=state_path)

    payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert payload["allowed_active_shards"] == 14
    assert payload["provider_ready_slots"] == 14
    assert payload["provider_hard_max_active_requests"] == 20
    assert payload["active_runs_count"] == 11
    assert payload["productive_active_runs_count"] == 5
    assert payload["waiting_active_runs_count"] == 6
    assert payload["dispatch_reason"] == "live provider capacity caps shard dispatch at 14/20"


def test_refresh_materialized_status_snapshot_replaces_stale_blocked_snapshot(
    monkeypatch,
    tmp_path: Path,
) -> None:
    state_root = tmp_path / "state" / "chummer_design_supervisor"
    state_root.mkdir(parents=True)
    (state_root / "status-live-refresh.materialized.json").write_text(
        json.dumps(
            {
                "updated_at": "2026-03-31T04:00:00Z",
                "eta_status": "blocked",
                "active_runs_count": 1,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "iso_now", lambda: "2026-04-01T05:20:00Z")

    module.refresh_materialized_status_snapshot(
        state_root,
        state_payload={
            "updated_at": "2026-04-01T05:19:00Z",
            "mode": "successor_wave",
            "successor_wave_eta": {
                "status": "tracked",
                "eta_human": "5.6d-2w",
                "summary": "27 open milestones remain.",
                "remaining_open_milestones": 27,
                "remaining_in_progress_milestones": 13,
                "remaining_not_started_milestones": 14,
            },
        },
        active_shards_payload={
            "configured_shard_count": 13,
            "active_shards": [
                {
                    "name": "shard-1",
                    "active_run_id": "run-1",
                    "active_run_progress_evidence": "repo_work_detected",
                },
                {
                    "name": "shard-2",
                    "active_run_id": "run-2",
                    "active_run_progress_evidence": "worker_output_only",
                },
            ],
        },
        observed_shards=[
            {
                "name": "shard-1",
                "shard_id": "shard-1",
                "active_run_id": "run-1",
                "active_frontier_ids": [109],
                "open_milestone_ids": [109],
                "active_run_progress_state": "streaming",
                "active_run_worker_pid": "1234",
                "active_run_worker_last_output_at": "2026-04-01T05:19:50Z",
            },
            {
                "name": "shard-2",
                "shard_id": "shard-2",
                "active_run_id": "run-2",
                "active_frontier_ids": [114],
                "open_milestone_ids": [114],
                "active_run_progress_state": "streaming",
                "active_run_worker_pid": "2345",
                "active_run_worker_last_output_at": "2026-04-01T05:19:55Z",
            },
        ],
    )

    payload = json.loads((state_root / "status-live-refresh.materialized.json").read_text(encoding="utf-8"))

    assert payload["contract_name"] == "fleet.chummer_design_supervisor.status_live_refresh_materialized"
    assert payload["updated_at"] == "2026-04-01T05:20:00Z"
    assert payload["eta_status"] == "tracked"
    assert payload["remaining_open_milestones"] == 27
    assert payload["remaining_in_progress_milestones"] == 13
    assert payload["remaining_not_started_milestones"] == 14
    assert payload["configured_shard_count"] == 13
    assert payload["active_runs_count"] == 2
    assert payload["productive_active_runs_count"] == 1
    assert payload["waiting_active_runs_count"] == 0
    assert payload["nonproductive_active_runs_count"] == 1
    assert [item["run_id"] for item in payload["active_runs"]] == ["run-1", "run-2"]


def test_refresh_materialized_status_snapshot_classifies_waiting_runs_separately(
    monkeypatch,
    tmp_path: Path,
) -> None:
    state_root = tmp_path / "state" / "chummer_design_supervisor"
    state_root.mkdir(parents=True)
    monkeypatch.setattr(module, "iso_now", lambda: "2026-04-01T05:30:00Z")

    module.refresh_materialized_status_snapshot(
        state_root,
        state_payload={"updated_at": "2026-04-01T05:29:00Z"},
        active_shards_payload={
            "configured_shard_count": 3,
            "active_shards": [
                {
                    "name": "shard-1",
                    "active_run_id": "run-1",
                    "active_run_progress_evidence": "repo_work_detected",
                },
                {
                    "name": "shard-2",
                    "active_run_id": "run-2",
                    "active_run_progress_evidence": "worker_output_only",
                },
                {
                    "name": "shard-3",
                    "active_run_id": "run-3",
                    "active_run_progress_evidence": "read_only_repo_probe",
                },
            ],
        },
        observed_shards=[
            {
                "name": "shard-1",
                "shard_id": "shard-1",
                "active_run_id": "run-1",
                "active_run_progress_state": "streaming",
            },
            {
                "name": "shard-2",
                "shard_id": "shard-2",
                "active_run_id": "run-2",
                "active_run_progress_state": "container_scoped",
            },
            {
                "name": "shard-3",
                "shard_id": "shard-3",
                "active_run_id": "run-3",
                "active_run_progress_state": "waiting_for_model_output",
            },
        ],
    )

    payload = json.loads((state_root / "status-live-refresh.materialized.json").read_text(encoding="utf-8"))

    assert payload["active_runs_count"] == 3
    assert payload["productive_active_runs_count"] == 1
    assert payload["waiting_active_runs_count"] == 2
    assert payload["nonproductive_active_runs_count"] == 0


def test_refresh_materialized_status_snapshot_promotes_richer_persisted_dispatch_capacity(
    monkeypatch,
    tmp_path: Path,
) -> None:
    state_root = tmp_path / "state" / "chummer_design_supervisor"
    state_root.mkdir(parents=True)
    (state_root / "state.json").write_text(
        json.dumps(
            {
                "updated_at": "2026-05-03T10:14:00Z",
                "allowed_active_shards": 19,
                "provider_ready_slots": 1,
                "dispatch_reason": "live provider capacity caps shard dispatch at 19/20 (billing-backed degraded slot override)",
                "provider_capacity_summary": {"allowed_active_shards": 19, "ready_slots": 1},
                "host_memory_pressure": {"allowed_active_shards": 20},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "iso_now", lambda: "2026-05-03T10:15:00Z")

    module.refresh_materialized_status_snapshot(
        state_root,
        state_payload={
            "updated_at": "2026-05-03T10:14:30Z",
            "allowed_active_shards": 1,
            "provider_ready_slots": 1,
            "dispatch_reason": "live provider capacity caps shard dispatch at 1/20",
        },
        active_shards_payload={"configured_shard_count": 20, "active_shards": []},
        observed_shards=[],
    )

    payload = json.loads((state_root / "status-live-refresh.materialized.json").read_text(encoding="utf-8"))

    assert payload["allowed_active_shards"] == 19
    assert payload["provider_ready_slots"] == 1
    assert "billing-backed degraded slot override" in payload["dispatch_reason"]
    assert payload["provider_capacity_summary"]["allowed_active_shards"] == 19
    assert payload["host_memory_pressure"]["allowed_active_shards"] == 20


def test_refresh_materialized_status_snapshot_promotes_richer_persisted_provider_truth_when_shard_ceiling_matches(
    monkeypatch,
    tmp_path: Path,
) -> None:
    state_root = tmp_path / "state" / "chummer_design_supervisor"
    state_root.mkdir(parents=True)
    (state_root / "state.json").write_text(
        json.dumps(
            {
                "updated_at": "2026-05-03T10:25:00Z",
                "allowed_active_shards": 4,
                "provider_ready_slots": 4,
                "provider_hard_max_active_requests": 20,
                "dispatch_reason": "live provider capacity caps shard dispatch at 4/20 (billing-backed degraded slot override)",
                "provider_capacity_summary": {
                    "allowed_active_shards": 4,
                    "ready_slots": 4,
                    "hard_max_active_requests": 20,
                },
                "host_memory_pressure": {"allowed_active_shards": 20},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "iso_now", lambda: "2026-05-03T10:26:00Z")

    module.refresh_materialized_status_snapshot(
        state_root,
        state_payload={
            "updated_at": "2026-05-03T10:25:30Z",
            "allowed_active_shards": 4,
            "provider_ready_slots": 2,
            "provider_hard_max_active_requests": 13,
            "dispatch_reason": "live provider capacity caps shard dispatch at 4/20",
        },
        active_shards_payload={"configured_shard_count": 20, "active_shards": []},
        observed_shards=[],
    )

    payload = json.loads((state_root / "status-live-refresh.materialized.json").read_text(encoding="utf-8"))

    assert payload["allowed_active_shards"] == 4
    assert payload["provider_ready_slots"] == 4
    assert payload["provider_hard_max_active_requests"] == 20
    assert "billing-backed degraded slot override" in payload["dispatch_reason"]


def test_refresh_materialized_status_snapshot_prefers_persisted_provider_cap_over_host_memory_only_sample(
    monkeypatch,
    tmp_path: Path,
) -> None:
    state_root = tmp_path / "state" / "chummer_design_supervisor"
    state_root.mkdir(parents=True)
    (state_root / "state.json").write_text(
        json.dumps(
            {
                "updated_at": "2026-05-03T12:40:00Z",
                "allowed_active_shards": 10,
                "provider_ready_slots": 0,
                "provider_hard_max_active_requests": 20,
                "dispatch_reason": "live provider capacity caps shard dispatch at 10/20 (recent provider-health probe failure forces EA canary dispatch)",
                "provider_capacity_summary": {
                    "allowed_active_shards": 10,
                    "ready_slots": 0,
                    "hard_max_active_requests": 20,
                },
                "provider_health_snapshot_status": "local_override",
                "host_memory_pressure": {"allowed_active_shards": 20},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "iso_now", lambda: "2026-05-03T12:41:00Z")

    module.refresh_materialized_status_snapshot(
        state_root,
        state_payload={
            "updated_at": "2026-05-03T12:40:30Z",
            "allowed_active_shards": 20,
            "dispatch_reason": "host memory headroom is healthy for the configured shard set",
        },
        active_shards_payload={"configured_shard_count": 20, "active_shards": []},
        observed_shards=[],
    )

    payload = json.loads((state_root / "status-live-refresh.materialized.json").read_text(encoding="utf-8"))

    assert payload["allowed_active_shards"] == 10
    assert payload["provider_hard_max_active_requests"] == 20
    assert "provider capacity caps shard dispatch at 10/20" in payload["dispatch_reason"]


def test_refresh_materialized_status_snapshot_prefers_lower_persisted_remaining_open_milestones(
    monkeypatch,
    tmp_path: Path,
) -> None:
    state_root = tmp_path / "state" / "chummer_design_supervisor"
    state_root.mkdir(parents=True)
    (state_root / "state.json").write_text(
        json.dumps(
            {
                "updated_at": "2026-05-03T10:20:00Z",
                "remaining_open_milestones": 18,
                "remaining_in_progress_milestones": 18,
                "remaining_not_started_milestones": 0,
                "eta": {
                    "status": "tracked",
                    "eta_human": "10h-1.1d",
                    "summary": "18 open milestones remain (18 in progress, 0 not started).",
                    "remaining_open_milestones": 18,
                    "remaining_in_progress_milestones": 18,
                    "remaining_not_started_milestones": 0,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "iso_now", lambda: "2026-05-03T10:21:00Z")

    module.refresh_materialized_status_snapshot(
        state_root,
        state_payload={
            "updated_at": "2026-05-03T10:19:30Z",
            "remaining_open_milestones": 37,
            "eta": {
                "status": "tracked",
                "eta_human": "later",
                "summary": "37 open milestones remain.",
                "remaining_open_milestones": 37,
                "remaining_in_progress_milestones": 37,
                "remaining_not_started_milestones": 0,
            },
        },
        active_shards_payload={"configured_shard_count": 20, "active_shards": []},
        observed_shards=[],
    )

    payload = json.loads((state_root / "status-live-refresh.materialized.json").read_text(encoding="utf-8"))

    assert payload["remaining_open_milestones"] == 18
    assert payload["remaining_in_progress_milestones"] == 18
    assert payload["eta"]["remaining_open_milestones"] == 18
    assert payload["eta_human"] == "10h-1.1d"


def test_refresh_materialized_status_snapshot_does_not_let_older_persisted_remaining_open_override_newer_state(
    monkeypatch,
    tmp_path: Path,
) -> None:
    state_root = tmp_path / "state" / "chummer_design_supervisor"
    state_root.mkdir(parents=True)
    (state_root / "state.json").write_text(
        json.dumps(
            {
                "updated_at": "2026-05-03T10:20:00Z",
                "remaining_open_milestones": 4,
                "remaining_in_progress_milestones": 4,
                "remaining_not_started_milestones": 0,
                "eta": {
                    "status": "tracked",
                    "eta_human": "later",
                    "summary": "4 open milestones remain.",
                    "remaining_open_milestones": 4,
                    "remaining_in_progress_milestones": 4,
                    "remaining_not_started_milestones": 0,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "iso_now", lambda: "2026-05-03T10:21:00Z")

    module.refresh_materialized_status_snapshot(
        state_root,
        state_payload={
            "updated_at": "2026-05-03T10:20:30Z",
            "remaining_open_milestones": 18,
            "remaining_in_progress_milestones": 18,
            "remaining_not_started_milestones": 0,
            "eta": {
                "status": "tracked",
                "eta_human": "10h-1.1d",
                "summary": "18 open milestones remain.",
                "remaining_open_milestones": 18,
                "remaining_in_progress_milestones": 18,
                "remaining_not_started_milestones": 0,
            },
        },
        active_shards_payload={"configured_shard_count": 20, "active_shards": []},
        observed_shards=[],
    )

    payload = json.loads((state_root / "status-live-refresh.materialized.json").read_text(encoding="utf-8"))

    assert payload["remaining_open_milestones"] == 18
    assert payload["remaining_in_progress_milestones"] == 18
    assert payload["eta"]["remaining_open_milestones"] == 18
    assert payload["eta_human"] == "10h-1.1d"


def test_refresh_materialized_status_snapshot_prefers_explicit_open_ids_over_stale_successor_wave_remaining(
    monkeypatch,
    tmp_path: Path,
) -> None:
    state_root = tmp_path / "state" / "chummer_design_supervisor"
    state_root.mkdir(parents=True)
    monkeypatch.setattr(module, "iso_now", lambda: "2026-05-03T10:21:00Z")

    module.refresh_materialized_status_snapshot(
        state_root,
        state_payload={
            "updated_at": "2026-05-03T10:20:30Z",
            "successor_wave_remaining_open_milestones": 37,
            "open_milestone_ids": [101, 102, 103, 104],
            "frontier_ids": [101, 102, 103, 104],
        },
        active_shards_payload={"configured_shard_count": 20, "active_shards": []},
        observed_shards=[],
    )

    payload = json.loads((state_root / "status-live-refresh.materialized.json").read_text(encoding="utf-8"))

    assert payload["remaining_open_milestones"] == 4


def test_refresh_materialized_status_snapshot_preserves_richer_state_productive_split(
    monkeypatch,
    tmp_path: Path,
) -> None:
    state_root = tmp_path / "state" / "chummer_design_supervisor"
    state_root.mkdir(parents=True)
    monkeypatch.setattr(module, "iso_now", lambda: "2026-05-03T10:21:00Z")

    module.refresh_materialized_status_snapshot(
        state_root,
        state_payload={
            "updated_at": "2026-05-03T10:20:30Z",
            "active_runs_count": 14,
            "productive_active_runs_count": 3,
            "waiting_active_runs_count": 11,
            "progress_evidence_counts": {"repo_work_detected": 3, "worker_output_only": 11},
        },
        active_shards_payload={"configured_shard_count": 20, "active_shards": []},
        observed_shards=[],
    )

    payload = json.loads((state_root / "status-live-refresh.materialized.json").read_text(encoding="utf-8"))

    assert payload["active_runs_count"] == 14
    assert payload["productive_active_runs_count"] == 3
    assert payload["waiting_active_runs_count"] == 11
    assert payload["progress_evidence_counts"] == {"repo_work_detected": 3, "worker_output_only": 11}


def test_refresh_materialized_status_snapshot_preserves_persisted_active_run_counts_when_observed_list_is_empty(
    monkeypatch,
    tmp_path: Path,
) -> None:
    state_root = tmp_path / "state" / "chummer_design_supervisor"
    state_root.mkdir(parents=True)
    (state_root / "state.json").write_text(
        json.dumps(
            {
                "updated_at": "2026-05-03T10:22:00Z",
                "active_run_count": 10,
                "active_runs_count": 10,
                "productive_active_runs_count": 0,
                "waiting_active_runs_count": 10,
                "nonproductive_active_runs_count": 0,
                "progress_evidence_counts": {"wait_only": 10},
                "active_runs": [{"run_id": "run-1"}],
                "shards": [{"name": "shard-1", "active_run_id": "run-1"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "iso_now", lambda: "2026-05-03T10:23:00Z")

    module.refresh_materialized_status_snapshot(
        state_root,
        state_payload={"updated_at": "2026-05-03T10:22:30Z"},
        active_shards_payload={"configured_shard_count": 20, "active_shards": []},
        observed_shards=[],
    )

    payload = json.loads((state_root / "status-live-refresh.materialized.json").read_text(encoding="utf-8"))

    assert payload["active_run_count"] == 10
    assert payload["active_runs_count"] == 10
    assert payload["waiting_active_runs_count"] == 10
    assert payload["progress_evidence_counts"] == {"wait_only": 10}
    assert payload["active_runs"] == [{"run_id": "run-1"}]


def test_refresh_materialized_status_snapshot_includes_manifest_only_active_runs(
    monkeypatch,
    tmp_path: Path,
) -> None:
    state_root = tmp_path / "state" / "chummer_design_supervisor"
    state_root.mkdir(parents=True)
    monkeypatch.setattr(module, "iso_now", lambda: "2026-05-03T10:30:00Z")

    module.refresh_materialized_status_snapshot(
        state_root,
        state_payload={"updated_at": "2026-05-03T10:29:00Z"},
        active_shards_payload={
            "configured_shard_count": 20,
            "active_run_count": 2,
            "active_shards": [
                {
                    "name": "shard-1",
                    "shard_id": "shard-1",
                    "active_run_id": "run-1",
                    "active_run_progress_state": "waiting_for_model_output",
                    "active_run_progress_evidence": "repo_work_detected",
                },
                {
                    "name": "shard-2",
                    "shard_id": "shard-2",
                    "active_run_id": "run-2",
                    "active_run_progress_state": "waiting_for_model_output",
                    "active_run_progress_evidence": "wait_only",
                },
            ],
        },
        observed_shards=[
            {
                "name": "shard-1",
                "shard_id": "shard-1",
                "active_run_id": "",
                "active_run_progress_state": "idle_claimed_frontier_without_active_run",
            }
        ],
    )

    payload = json.loads((state_root / "status-live-refresh.materialized.json").read_text(encoding="utf-8"))

    assert payload["active_runs_count"] == 2
    assert payload["productive_active_runs_count"] == 1
    assert payload["waiting_active_runs_count"] == 1
    assert [item["run_id"] for item in payload["active_runs"]] == ["run-1", "run-2"]


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
