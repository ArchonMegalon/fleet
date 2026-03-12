#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path


EA_APP_ROOT = Path("/docker/EA/ea")
if str(EA_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(EA_APP_ROOT))

from app.domain.models import TaskContract, now_utc_iso  # noqa: E402
from app.services.ltd_inventory_api import extract_inventory_output_json  # noqa: E402
from app.services.ltd_inventory_markdown import update_discovery_tracking_table  # noqa: E402
from app.services.planner import PlannerService  # noqa: E402
from app.services.provider_registry import ProviderRegistryService  # noqa: E402
from app.services.skills import SkillCatalogService  # noqa: E402
from app.services.task_contracts import TaskContractService  # noqa: E402
from app.repositories.task_contracts import InMemoryTaskContractRepository  # noqa: E402
from app.settings import get_settings, resolve_runtime_profile, validate_startup_settings  # noqa: E402


ENV_KEYS = (
    "EA_RUNTIME_MODE",
    "EA_STORAGE_BACKEND",
    "EA_LEDGER_BACKEND",
    "DATABASE_URL",
    "EA_API_TOKEN",
    "EA_DEFAULT_PRINCIPAL_ID",
)


def clear_env() -> None:
    for key in ENV_KEYS:
        os.environ.pop(key, None)


def verify_runtime_profile() -> None:
    clear_env()
    settings = get_settings()
    profile = resolve_runtime_profile(settings)
    assert profile.storage_backend == "memory"
    assert profile.durability == "ephemeral"

    clear_env()
    os.environ["DATABASE_URL"] = "postgresql://example.invalid/ea"
    settings = get_settings()
    profile = resolve_runtime_profile(settings)
    assert profile.storage_backend == "postgres"
    assert profile.durability == "durable"

    clear_env()
    os.environ["EA_RUNTIME_MODE"] = "prod"
    os.environ["EA_API_TOKEN"] = "secret-token"
    try:
        validate_startup_settings(get_settings())
    except RuntimeError as exc:
        assert "DATABASE_URL" in str(exc)
    else:
        raise AssertionError("prod startup validation should require DATABASE_URL")


def verify_planner_edge_case() -> None:
    contracts = TaskContractService(InMemoryTaskContractRepository())
    contracts.upsert_contract(
        task_key="artifact_memory_dispatch",
        deliverable_type="rewrite_note",
        default_risk_class="low",
        default_approval_class="none",
        allowed_tools=("artifact_repository", "connector.dispatch"),
        memory_write_policy="reviewed_only",
        budget_policy_json={
            "class": "low",
            "workflow_template": "artifact_then_memory_candidate",
            "post_artifact_packs": ["dispatch", "memory_candidate"],
        },
    )
    planner = PlannerService(contracts)
    _, plan = planner.build_plan(
        task_key="artifact_memory_dispatch",
        principal_id="exec-1",
        goal="exercise edge case",
    )
    step_keys = [step.step_key for step in plan.steps]
    assert step_keys == [
        "step_input_prepare",
        "step_policy_evaluate",
        "step_artifact_save",
        "step_connector_dispatch",
        "step_memory_candidate_stage",
    ]


def verify_ltd_inventory_additivity() -> None:
    payload = extract_inventory_output_json(
        {
            "status": "completed",
            "next_action": "download_artifact",
            "output_json": {
                "services_json": [
                    {
                        "service_name": "MarkupGo",
                        "account_email": "ops@example.com",
                    }
                ]
            },
        }
    )
    assert payload["services_json"][0]["service_name"] == "MarkupGo"

    markdown = """# LTDs

## Discovery Tracking

| Service | Account / Email | Discovery Status | Verification Source | Last Verified | Notes |
|---|---|---|---|---|---|
| `BrowserAct` |  | `runtime_ready` | `browseract.extract_account_inventory` |  | waiting |

## Attention Items
"""
    updated = update_discovery_tracking_table(
        markdown,
        {
            "services_json": [
                {
                    "service_name": "UnknownService",
                    "account_email": "",
                    "discovery_status": "missing",
                    "verification_source": "missing",
                    "last_verified_at": "2026-03-07T12:02:00Z",
                    "missing_fields": ["tier", "account_email"],
                }
            ]
        },
    )
    assert "UnknownService" in updated
    assert "Missing fields: tier, account_email" in updated


def verify_provider_registry() -> None:
    registry = ProviderRegistryService()
    contract = TaskContract(
        task_key="inventory_refresh",
        deliverable_type="inventory",
        default_risk_class="low",
        default_approval_class="none",
        allowed_tools=("browseract.extract_account_inventory", "artifact_repository"),
        evidence_requirements=(),
        memory_write_policy="none",
        budget_policy_json={"class": "low"},
        updated_at=now_utc_iso(),
    )
    skill = SkillCatalogService(TaskContractService(InMemoryTaskContractRepository())).contract_to_skill(contract)
    bindings = registry.bindings_for_skill(skill)
    keys = {binding.provider_key for binding in bindings}
    assert "browseract" in keys
    assert "artifact_repository" in keys


def main() -> None:
    verify_runtime_profile()
    verify_planner_edge_case()
    verify_ltd_inventory_additivity()
    verify_provider_registry()


if __name__ == "__main__":
    main()
