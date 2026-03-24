from __future__ import annotations

from pathlib import Path

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
