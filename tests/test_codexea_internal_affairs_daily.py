from __future__ import annotations

import importlib.util
import json
from pathlib import Path


MODULE_PATH = Path("/docker/fleet/scripts/codexea_internal_affairs_daily.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("codexea_internal_affairs_daily", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_compact_fleet_status_keeps_operational_fields() -> None:
    module = _load_module()

    payload = module.compact_fleet_status(
        {
            "updated_at": "2026-05-02T16:13:45Z",
            "active_runs_count": 4,
            "productive_active_runs_count": 1,
            "waiting_active_runs_count": 3,
            "nonproductive_active_runs_count": 0,
            "remaining_open_milestones": 20,
            "allowed_active_shards": 2,
            "last_run_blocker": "",
            "preflight_failure_reason": "",
            "ignored": "value",
        }
    )

    assert payload == {
        "updated_at": "2026-05-02T16:13:45Z",
        "active_runs_count": 4,
        "productive_active_runs_count": 1,
        "waiting_active_runs_count": 3,
        "nonproductive_active_runs_count": 0,
        "remaining_open_milestones": 20,
        "allowed_active_shards": 2,
        "last_run_blocker": "",
        "preflight_failure_reason": "",
    }


def test_current_fleet_snapshot_prefers_fresher_snapshot_and_backfills_missing_fields(tmp_path: Path, monkeypatch) -> None:
    module = _load_module()
    fleet_state = tmp_path / "state.json"
    materialized = tmp_path / "status-live-refresh.materialized.json"
    fleet_state.write_text(
        json.dumps(
            {
                "updated_at": "2026-05-03T09:17:29Z",
                "active_runs_count": 2,
                "productive_active_runs_count": 0,
                "waiting_active_runs_count": 2,
                "remaining_open_milestones": None,
                "allowed_active_shards": 10,
            }
        ),
        encoding="utf-8",
    )
    materialized.write_text(
        json.dumps(
            {
                "updated_at": "2026-05-03T09:17:03Z",
                "active_runs_count": 0,
                "productive_active_runs_count": 0,
                "waiting_active_runs_count": 0,
                "remaining_open_milestones": 2,
                "allowed_active_shards": 20,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "FLEET_STATE", fleet_state)
    monkeypatch.setattr(module, "FLEET_STATE_MATERIALIZED", materialized)

    payload = module.current_fleet_snapshot()

    assert payload["updated_at"] == "2026-05-03T09:17:29Z"
    assert payload["active_runs_count"] == 2
    assert payload["allowed_active_shards"] == 10
    assert payload["remaining_open_milestones"] == 2


def test_record_run_state_preserves_sent_summaries_and_writes_last_run_fields(monkeypatch, tmp_path: Path) -> None:
    module = _load_module()
    state_file = tmp_path / "daily-state.json"
    state_file.write_text(
        json.dumps(
            {
                "sent_summaries": {
                    "2026-05-01": {
                        "message_id": "msg-1",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "STATE_FILE", state_file)
    monkeypatch.setattr(module, "current_fleet_snapshot", lambda: {"updated_at": "2026-05-02T16:13:45Z", "active_runs_count": 4})

    module.record_run_state(
        target_date=module.dt.date(2026, 5, 1),
        dry_run=True,
        summary_status="dry-run summary generated for 2026-05-01",
        watchdog_status="already running pid=123",
    )

    payload = json.loads(state_file.read_text(encoding="utf-8"))
    assert payload["sent_summaries"]["2026-05-01"]["message_id"] == "msg-1"
    assert payload["last_target_date"] == "2026-05-01"
    assert payload["last_dry_run"] is True
    assert payload["last_summary_status"] == "dry-run summary generated for 2026-05-01"
    assert payload["last_watchdog_action"] == "already running pid=123"
    assert payload["last_results"] == [
        "dry-run summary generated for 2026-05-01",
        "already running pid=123",
    ]
    assert payload["last_fleet_status"]["updated_at"] == "2026-05-02T16:13:45Z"
    assert payload["last_fleet_status"]["active_runs_count"] == 4
    assert payload["fleet_snapshot"]["updated_at"] == "2026-05-02T16:13:45Z"
    assert payload["fleet_snapshot"]["active_runs_count"] == 4
    assert payload["last_run_at"]
