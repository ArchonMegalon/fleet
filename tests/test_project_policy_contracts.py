from __future__ import annotations

from pathlib import Path
import os
import subprocess

import yaml


PROJECTS_DIR = Path("/docker/fleet/config/projects")


def _load_project(project_id: str) -> dict:
    payload = yaml.safe_load((PROJECTS_DIR / f"{project_id}.yaml").read_text(encoding="utf-8")) or {}
    assert isinstance(payload, dict)
    return payload


def test_bounded_repos_are_controlled_participant_canaries_while_fleet_stays_operator_only() -> None:
    core = _load_project("core")
    hub = _load_project("hub")
    fleet = _load_project("fleet")

    assert core["participant_burst"]["enabled"] is True
    assert core["participant_burst"]["allow_chatgpt_accounts"] is True
    assert core["participant_burst"]["eligible_task_classes"] == ["bounded_fix", "multi_file_impl"]
    assert core["review"]["mode"] == "github"

    assert hub["participant_burst"]["enabled"] is True
    assert hub["participant_burst"]["allow_chatgpt_accounts"] is True
    assert hub["participant_burst"]["eligible_task_classes"] == ["bounded_fix", "multi_file_impl"]
    assert hub["review"]["mode"] == "github"

    assert fleet["account_policy"]["allow_chatgpt_accounts"] is False
    assert fleet["account_policy"]["emergency_chatgpt_fallback_accounts"] == ["acct-chatgpt-archon"]
    assert fleet["review"]["mode"] == "local"


def test_fleet_supervisor_contract_carries_shard_routing_and_proof_paths() -> None:
    fleet = _load_project("fleet")
    contract = fleet["supervisor_contract"]
    runtime = contract["runtime_policy"]
    restart_safe = contract["restart_safe_runtime"]
    resource_policy = contract["resource_policy"]
    topology = contract["shard_topology"]
    shards = topology["configured_shards"]

    assert contract["schema_version"] == 1
    assert runtime["source_of_record"] == "config/projects/fleet.yaml"
    assert runtime["restart_safe"] is True
    assert runtime["state_root"] == "/docker/fleet/state/chummer_design_supervisor"
    assert runtime["clear_lock_on_boot"] is True
    assert runtime["shard_count"] == 13
    assert runtime["dynamic_account_routing"] == "auto"
    assert runtime["worker_bin"].endswith("/scripts/codex-shims/codexea")
    assert runtime["worker_lane"] == "core"
    assert runtime["worker_model"] == "ea-coder-hard-batch"
    assert runtime["resource_policy"]["operating_profile"] == "standard"
    assert restart_safe["canonical_config_surface"].endswith("config/projects/fleet.yaml")
    assert restart_safe["documented_at"].endswith("docs/restart-safe-runtime-configuration.md")
    assert restart_safe["launcher_defaults"]["parallel_shards"] == 13
    assert restart_safe["launcher_defaults"]["state_root"].endswith("chummer_design_supervisor")
    assert restart_safe["launcher_defaults"]["clear_lock_on_boot"] is True
    assert resource_policy["default_operating_profile"] == "standard"
    assert set(resource_policy["operating_profiles"]) == {"maintenance", "standard", "burst"}
    assert resource_policy["operating_profiles"]["standard"]["max_active_shards"] == 13
    assert resource_policy["operating_profiles"]["standard"]["memory_dispatch_reserve_gib"] == 2.0
    assert runtime["queue_posture"]["source"] == "WORKLIST.md"
    assert fleet["queue_sources"][0]["path"] == "WORKLIST.md"
    assert any(item["package_id"] == "fleet-postclient-restart-safe-config" for item in fleet["queue"])
    assert topology["primary_probe_shard"] == "shard-1"
    assert len(shards) == 13
    assert {shard["name"] for shard in shards} == {f"shard-{index}" for index in range(1, 14)}
    assert all(shard["focus_owner"] for shard in shards)
    assert all(shard["focus_text"] for shard in shards)
    assert shards[0]["focus_profile"] == ["top_flagship_grade", "whole_project_frontier"]
    assert "desktop_client" in contract["focus_profiles"]
    assert contract["proof_paths"]["completion_review_frontier"].endswith(
        "/COMPLETION_REVIEW_FRONTIER.generated.yaml"
    )


def test_launcher_hydrates_shard_focus_defaults_from_project_contract() -> None:
    launcher = Path("/docker/fleet/scripts/run_chummer_design_supervisor.sh").read_text(encoding="utf-8")

    assert "CHUMMER_DESIGN_SUPERVISOR_PROJECT_CONFIG" in launcher
    assert "load_project_runtime_contract_defaults" in launcher
    assert "project_contract_shard_owner_groups" in launcher
    assert "project_contract_shard_focus_profile_groups" in launcher
    assert "project_contract_shard_focus_text_groups" in launcher
    assert "project_contract_parallel_shards" in launcher
    assert "project_contract_operating_profile" in launcher
    assert "project_contract_memory_dispatch_reserve_gib" in launcher
    assert "project_contract_memory_dispatch_warning_available_percent" in launcher
    assert "CHUMMER_DESIGN_SUPERVISOR_PRINT_RUNTIME_POLICY" in launcher


def test_launcher_cold_restart_policy_is_reproducible_from_project_contract() -> None:
    env = {
        "PATH": os.environ.get("PATH", ""),
        "CHUMMER_DESIGN_SUPERVISOR_PRINT_RUNTIME_POLICY": "1",
        "CHUMMER_DESIGN_SUPERVISOR_PROJECT_CONFIG": "/docker/fleet/config/projects/fleet.yaml",
    }

    result = subprocess.run(
        ["bash", "/docker/fleet/scripts/run_chummer_design_supervisor.sh"],
        check=True,
        text=True,
        capture_output=True,
        env=env,
    )
    lines = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)

    assert lines["project_config"] == "/docker/fleet/config/projects/fleet.yaml"
    assert lines["state_root"] == "/docker/fleet/state/chummer_design_supervisor"
    assert lines["parallel_shards"] == "13"
    assert lines["clear_lock_on_boot"] == "1"
    assert lines["health_max_age_seconds"] == "900"
    assert lines["operating_profile"] == "standard"
    assert lines["memory_dispatch_reserve_gib"] == "2.0"
    assert lines["memory_dispatch_shard_budget_gib"] == "0.28"
    assert lines["memory_dispatch_warning_available_percent"] == "10.0"
    assert lines["memory_dispatch_critical_available_percent"] == "6.0"
    assert lines["memory_dispatch_warning_swap_used_percent"] == "75.0"
    assert lines["memory_dispatch_critical_swap_used_percent"] == "90.0"
    assert lines["memory_dispatch_parked_poll_seconds"] == "300"
    assert lines["dynamic_account_routing"] == "auto"
    assert lines["prefer_full_ea_lanes"] == "1"
    assert lines["worker_bin"] == "/docker/fleet/scripts/codex-shims/codexea"
    assert lines["worker_lane"] == "core"
    assert lines["worker_model"] == "ea-coder-hard-batch"
    assert lines["fallback_lanes"] == "core_rescue"
    assert "fleet,chummer6-design,chummer6-ui" in lines["shard_owner_groups"]


def test_fleet_restart_safe_runtime_contract_is_documented() -> None:
    fleet = _load_project("fleet")
    restart_safe = fleet["supervisor_contract"]["restart_safe_runtime"]
    documented_at = Path(restart_safe["documented_at"])

    assert restart_safe["canonical_config_surface"] == "/docker/fleet/config/projects/fleet.yaml"
    assert documented_at.is_file()
    document = documented_at.read_text(encoding="utf-8")
    assert "state/chummer_design_supervisor/active_shards.json" in document
    assert "/docker/fleet/state/chummer_design_supervisor" in document
    assert "stale completion receipts remain visible" in document
    assert restart_safe["cold_restart_validation"]["command"].startswith(
        "docker compose -f /docker/fleet/docker-compose.yml up -d --force-recreate"
    )
    assert "repo_backlog_audit has no active WL-305 queue item after this closeout." in restart_safe[
        "cold_restart_validation"
    ]["expected"]
