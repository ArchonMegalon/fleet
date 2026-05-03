from __future__ import annotations

import importlib.util
import json
from pathlib import Path


MODULE_PATH = Path("/docker/fleet/scripts/fleet_ooda_timer_guard.py")
SPEC = importlib.util.spec_from_file_location("fleet_ooda_timer_guard", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


def _capacity(*, state: str, configured_slots: int, ready_slots: int, remaining: float | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "state": state,
        "configured_slots": configured_slots,
        "ready_slots": ready_slots,
    }
    if remaining is not None:
        payload["remaining_percent_of_max"] = remaining
    return payload


def test_rewrite_env_defaults_updates_known_keys_and_preserves_unrelated_lines() -> None:
    updated, changed = guard.rewrite_env_defaults(
        "UNCHANGED=yes\nCHUMMER_DESIGN_SUPERVISOR_FALLBACK_LANES=core\n# comment\n",
        {
            "CHUMMER_DESIGN_SUPERVISOR_FALLBACK_LANES": "core_rescue,survival,repair",
            "CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_FALLBACK_LANES": "core_rescue,survival,repair",
        },
    )

    assert changed == [
        "CHUMMER_DESIGN_SUPERVISOR_FALLBACK_LANES",
        "CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_FALLBACK_LANES",
    ]
    assert "UNCHANGED=yes" in updated
    assert "# comment" in updated
    assert "CHUMMER_DESIGN_SUPERVISOR_FALLBACK_LANES=core_rescue,survival,repair" in updated
    assert "CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_FALLBACK_LANES=core_rescue,survival,repair" in updated


def test_fleet_runtime_defaults_include_operator_principal_for_ea_status_calls() -> None:
    assert guard.FLEET_RUNTIME_DEFAULTS["EA_MCP_PRINCIPAL_ID"] == "codex-fleet"
    assert guard.FLEET_RUNTIME_DEFAULTS["EA_PRINCIPAL_ID"] == "codex-fleet"
    assert guard.FLEET_RUNTIME_DEFAULTS["CHUMMER_DESIGN_SUPERVISOR_EA_PROVIDER_HEALTH_PRINCIPAL_ID"] == "codex-fleet"
    assert guard.EA_RUNTIME_DEFAULTS["EA_RESPONSES_HARD_MAX_ACTIVE_REQUESTS"] == "20"


def test_load_status_reports_timeout_without_crashing(monkeypatch, tmp_path: Path) -> None:
    def fake_run(*_args, **kwargs):
        raise guard.subprocess.TimeoutExpired(
            cmd=kwargs.get("args", "status"),
            timeout=kwargs.get("timeout", 45),
            output="partial status",
            stderr="slow status",
        )

    monkeypatch.setattr(guard.subprocess, "run", fake_run)

    result = guard.load_status(tmp_path, timeout=1)

    assert result["ok"] is False
    assert result["returncode"] == 124
    assert result["timed_out"] is True
    assert "slow status" in result["stderr_tail"]


def test_load_status_with_lane_health_only_live_refreshes_when_missing(monkeypatch, tmp_path: Path) -> None:
    calls: list[bool] = []

    def fake_load_status(_workspace_root: Path, *, timeout: int, live_refresh: bool = False):
        calls.append(live_refresh)
        if live_refresh:
            return {
                "ok": True,
                "payload": {
                    "worker_lane_health": {"routable_lanes": ["core"]},
                },
            }
        return {"ok": True, "payload": {"active_runs_count": 13}}

    monkeypatch.setattr(guard, "load_status", fake_load_status)

    result = guard.load_status_with_lane_health(tmp_path, timeout=45)

    assert result["ok"] is True
    assert result["payload"]["worker_lane_health"]["routable_lanes"] == ["core"]
    assert calls == [False, True]


def test_main_refreshes_status_after_keeper_before_blocking(monkeypatch, tmp_path: Path, capsys) -> None:
    statuses = [
        {
            "ok": True,
            "payload": {
                "active_runs_count": 1,
                "allowed_active_shards": 13,
                "worker_lane_health": {"routable_lanes": ["core"]},
            },
        },
        {
            "ok": True,
            "payload": {
                "active_runs_count": 13,
                "allowed_active_shards": 13,
                "worker_lane_health": {"routable_lanes": ["core", "core_rescue", "survival"]},
            },
        },
    ]

    monkeypatch.setattr(guard, "fetch_provider_health_with_retries", lambda *_args, **_kwargs: {"ok": True, "payload": {}})
    monkeypatch.setattr(
        guard,
        "assess_provider_health_payload",
        lambda _payload: {"status": "pass", "problems": [], "warnings": [], "provider_count": 4, "lane_count": 9},
    )
    monkeypatch.setattr(guard, "load_status", lambda *_args, **_kwargs: statuses.pop(0))
    monkeypatch.setattr(guard.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        guard,
        "run_command",
        lambda argv, **_kwargs: {"argv": argv, "returncode": 0},
    )

    rc = guard.main(
        [
            "--once",
            "--workspace-root",
            str(tmp_path / "fleet"),
            "--ea-root",
            str(tmp_path / "ea"),
            "--target-active",
            "13",
            "--minimum-active",
            "8",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["status"] == "pass"
    assert payload["blockers"] == []
    assert payload["fleet_summary"]["active_runs_count"] == 13
    assert payload["fleet_status_fetch_after_keeper"][0]["ok"] is True


def test_main_clears_provider_cache_without_recreating_supervisor(monkeypatch, tmp_path: Path, capsys) -> None:
    statuses = [
        {
            "ok": True,
            "payload": {
                "active_runs_count": 13,
                "allowed_active_shards": 13,
                "worker_lane_health": {
                    "reason": "using cached provider-health after transient failure",
                    "routable_lanes": [],
                },
            },
        },
        {
            "ok": True,
            "payload": {
                "active_runs_count": 13,
                "allowed_active_shards": 13,
                "worker_lane_health": {
                    "reason": "using fresh provider-health",
                    "routable_lanes": ["core", "core_rescue"],
                },
            },
        },
    ]

    monkeypatch.setattr(
        guard,
        "ensure_env_defaults",
        lambda path, defaults, *, dry_run: {"path": str(path), "changed": False, "changed_keys": []},
    )
    monkeypatch.setattr(guard, "load_env", lambda _path: dict(guard.FLEET_RUNTIME_DEFAULTS))
    monkeypatch.setattr(guard, "fetch_provider_health_with_retries", lambda *_args, **_kwargs: {"ok": True, "payload": {}})
    monkeypatch.setattr(
        guard,
        "assess_provider_health_payload",
        lambda _payload: {"status": "pass", "problems": [], "warnings": [], "provider_count": 4, "lane_count": 9},
    )
    monkeypatch.setattr(guard, "load_status", lambda *_args, **_kwargs: statuses.pop(0))
    monkeypatch.setattr(guard, "provider_cache_paths", lambda *_args, **_kwargs: [tmp_path / "cache.json"])
    monkeypatch.setattr(
        guard,
        "remove_provider_cache",
        lambda *_args, **_kwargs: {"changed": True, "removed_paths": [str(tmp_path / "cache.json")]},
    )

    commands: list[list[str]] = []
    monkeypatch.setattr(
        guard,
        "run_command",
        lambda argv, **_kwargs: commands.append(list(argv)) or {"argv": argv, "returncode": 0},
    )

    rc = guard.main(
        [
            "--once",
            "--workspace-root",
            str(tmp_path / "fleet"),
            "--ea-root",
            str(tmp_path / "ea"),
            "--target-active",
            "13",
            "--minimum-active",
            "8",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["status"] == "pass"
    assert payload["actions"][0]["changed"] is True
    assert commands == []


def test_provider_health_assessment_rejects_ready_provider_with_zero_ready_slots() -> None:
    result = guard.assess_provider_health_payload(
        {
            "provider_registry": {
                "providers": [
                    {
                        "provider_key": "onemin",
                        "primary_state": "ready",
                        "slot_pool": _capacity(state="ready", configured_slots=1, ready_slots=0),
                    }
                ],
                "lanes": [
                    {
                        "profile": "survival",
                        "primary_state": "ready",
                        "primary_provider_key": "browseract",
                        "slot_pool": _capacity(state="ready", configured_slots=1, ready_slots=1),
                        "providers": [
                            {
                                "provider_key": "browseract",
                                "primary_state": "ready",
                                "slot_pool": _capacity(state="ready", configured_slots=1, ready_slots=1),
                            }
                        ],
                    }
                ],
            }
        }
    )

    assert result["status"] == "fail"
    assert "ready_provider_has_zero_ready_slots" in {problem["code"] for problem in result["problems"]}


def test_provider_health_assessment_accepts_survival_browseract_with_degraded_core() -> None:
    result = guard.assess_provider_health_payload(
        {
            "provider_registry": {
                "providers": [
                    {
                        "provider_key": "browseract",
                        "primary_state": "ready",
                        "slot_pool": _capacity(state="ready", configured_slots=1, ready_slots=1),
                    },
                    {
                        "provider_key": "onemin",
                        "primary_state": "unavailable",
                        "slot_pool": _capacity(state="unavailable", configured_slots=1, ready_slots=0, remaining=0.0),
                    },
                ],
                "lanes": [
                    {
                        "profile": "core",
                        "primary_state": "degraded",
                        "primary_provider_key": "onemin",
                        "slot_pool": _capacity(state="degraded", configured_slots=1, ready_slots=0, remaining=0.0),
                    },
                    {
                        "profile": "survival",
                        "primary_state": "ready",
                        "primary_provider_key": "browseract",
                        "slot_pool": _capacity(state="ready", configured_slots=1, ready_slots=1),
                        "providers": [
                            {
                                "provider_key": "browseract",
                                "primary_state": "ready",
                                "slot_pool": _capacity(state="ready", configured_slots=1, ready_slots=1),
                            }
                        ],
                    },
                ],
            }
        }
    )

    assert result["status"] == "pass"
    assert result["problems"] == []


def test_provider_health_assessment_rejects_ready_low_credit_core_with_ready_slots() -> None:
    result = guard.assess_provider_health_payload(
        {
            "provider_registry": {
                "providers": [
                    {
                        "provider_key": "onemin",
                        "primary_state": "ready",
                        "slot_pool": _capacity(state="ready", configured_slots=3, ready_slots=2, remaining=0.05),
                    },
                    {
                        "provider_key": "browseract",
                        "primary_state": "ready",
                        "slot_pool": _capacity(state="ready", configured_slots=1, ready_slots=1),
                    },
                ],
                "lanes": [
                    {
                        "profile": "core",
                        "primary_state": "ready",
                        "primary_provider_key": "onemin",
                        "slot_pool": _capacity(state="ready", configured_slots=3, ready_slots=2, remaining=0.05),
                    },
                    {
                        "profile": "survival",
                        "primary_state": "ready",
                        "primary_provider_key": "browseract",
                        "slot_pool": _capacity(state="ready", configured_slots=1, ready_slots=1),
                        "providers": [
                            {
                                "provider_key": "browseract",
                                "primary_state": "ready",
                                "slot_pool": _capacity(state="ready", configured_slots=1, ready_slots=1),
                            }
                        ],
                    },
                ],
            }
        }
    )

    assert result["status"] == "fail"
    assert "low_capacity_core_lane_marked_ready" in {problem["code"] for problem in result["problems"]}


def test_provider_health_assessment_rejects_survival_without_ready_browseract() -> None:
    result = guard.assess_provider_health_payload(
        {
            "provider_registry": {
                "providers": [
                    {
                        "provider_key": "onemin",
                        "primary_state": "ready",
                        "slot_pool": _capacity(state="ready", configured_slots=1, ready_slots=1),
                    }
                ],
                "lanes": [
                    {
                        "profile": "survival",
                        "primary_state": "ready",
                        "primary_provider_key": "onemin",
                        "slot_pool": _capacity(state="ready", configured_slots=1, ready_slots=1),
                        "providers": [
                            {
                                "provider_key": "onemin",
                                "primary_state": "ready",
                                "slot_pool": _capacity(state="ready", configured_slots=1, ready_slots=1),
                            }
                        ],
                    }
                ],
            }
        }
    )

    assert result["status"] == "fail"
    assert "survival_not_backed_by_ready_browseract" in {problem["code"] for problem in result["problems"]}
