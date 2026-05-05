from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


SCRIPT = Path("/docker/fleet/scripts/materialize_next90_m142_fleet_route_local_proof_closeout_gates.py")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _workflow_pack_payload() -> dict:
    return {
        "workflow_maps": [
            {
                "id": "build_explain_publish",
                "compare_artifacts": [
                    "workflow:build_explain_publish",
                    "baseline:first_launch_workbench_or_restore",
                    "baseline:menu_tools_settings_masterindex_roster",
                ],
            }
        ],
        "families": [
            {
                "id": "dense_builder_and_career_workflows",
                "compare_artifacts": ["oracle:tabs", "oracle:workspace_actions", "workflow:build_explain_publish"],
            },
            {
                "id": "dice_initiative_and_table_utilities",
                "compare_artifacts": ["menu:dice_roller", "workflow:initiative"],
            },
            {
                "id": "identity_contacts_lifestyles_history",
                "compare_artifacts": ["workflow:contacts", "workflow:lifestyles", "workflow:notes"],
            },
        ],
    }


def _registry() -> dict:
    return {"milestones": [{"id": 142, "work_tasks": [{"id": "142.5", "owner": "fleet"}]}]}


def _queue_item() -> dict:
    return {
        "title": "Fail closeout when any route in this milestone closes on family prose, stale captures, or missing task-speed and runtime receipts.",
        "task": "Fail closeout when any route in this milestone closes on family prose, stale captures, or missing task-speed and runtime receipts.",
        "package_id": "next90-m142-fleet-fail-closeout-when-any-route-in-this-milestone-closes-on-family-prose",
        "milestone_id": 142,
        "work_task_id": "142.5",
        "frontier_id": 7414599441,
        "wave": "W22P",
        "repo": "fleet",
        "allowed_paths": ["scripts", "tests", ".codex-studio", "feedback"],
        "owned_surfaces": ["fail_closeout_when_any_route_in_this_milestone_closes_on:fleet"],
    }


def _parity_rows(*, direct: bool) -> list[dict]:
    runtime_suffixes = {
        "dense": [
            "/tmp/SECTION_HOST_RULESET_PARITY.generated.json",
            "/tmp/CHUMMER5A_SCREENSHOT_REVIEW_GATE.generated.json",
        ],
        "dice": [
            "/tmp/GENERATED_DIALOG_ELEMENT_PARITY.generated.json",
            "/tmp/NEXT90_M121_UI_GM_RUNBOARD_ROUTE.generated.json",
            "/tmp/NEXT90_M142_DENSE_WORKBENCH_RECEIPTS.md",
        ],
        "identity": [
            "/tmp/SECTION_HOST_RULESET_PARITY.generated.json",
            "/tmp/NEXT90_M142_DENSE_WORKBENCH_RECEIPTS.md",
        ],
    }
    broad = [
        "/tmp/veteran_workflow_packs.yaml",
        "/tmp/DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json",
        "/tmp/DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json",
    ]
    reason_prefix = "All declared compare artifacts for this Chummer5A family are directly backed by current parity proof:"
    return [
        {
            "id": "family:dense_builder_and_career_workflows",
            "label": "Dense Builder And Career Workflows",
            "visual_parity": "yes",
            "behavioral_parity": "yes",
            "present_in_chummer5a": "yes",
            "present_in_chummer6": "yes",
            "removable_if_not_in_chummer5a": "no",
            "reason": "Route-local dense proof is cited." if direct else f"{reason_prefix} ['oracle:tabs', 'oracle:workspace_actions', 'workflow:build_explain_publish'].",
            "evidence": runtime_suffixes["dense"] if direct else broad,
        },
        {
            "id": "family:dice_initiative_and_table_utilities",
            "label": "Dice Initiative And Table Utilities",
            "visual_parity": "yes",
            "behavioral_parity": "yes",
            "present_in_chummer5a": "yes",
            "present_in_chummer6": "yes",
            "removable_if_not_in_chummer5a": "no",
            "reason": "Route-local dice and initiative proof is cited." if direct else f"{reason_prefix} ['menu:dice_roller', 'workflow:initiative'].",
            "evidence": runtime_suffixes["dice"] if direct else broad,
        },
        {
            "id": "family:identity_contacts_lifestyles_history",
            "label": "Identity Contacts Lifestyles History",
            "visual_parity": "yes",
            "behavioral_parity": "yes",
            "present_in_chummer5a": "yes",
            "present_in_chummer6": "yes",
            "removable_if_not_in_chummer5a": "no",
            "reason": "Route-local contacts, lifestyles, and notes proof is cited." if direct else f"{reason_prefix} ['workflow:contacts', 'workflow:lifestyles', 'workflow:notes'].",
            "evidence": runtime_suffixes["identity"] if direct else broad,
        },
    ]


def _fixture_tree(tmp_path: Path, *, direct: bool) -> dict[str, Path]:
    registry = tmp_path / "registry.yaml"
    fleet_queue = tmp_path / "fleet_queue.yaml"
    design_queue = tmp_path / "design_queue.yaml"
    guide = tmp_path / "guide.md"
    workflow_pack = tmp_path / "workflow_pack.yaml"
    parity_audit = tmp_path / "parity_audit.json"
    visual_gate = tmp_path / "visual_gate.json"
    workflow_gate = tmp_path / "workflow_gate.json"
    screenshot_gate = tmp_path / "screenshot_gate.json"
    dense_gate = tmp_path / "dense_gate.json"
    veteran_gate = tmp_path / "veteran_gate.json"
    ui_release = tmp_path / "ui_release.json"
    dialog_parity = tmp_path / "dialog_parity.json"
    section_host = tmp_path / "section_host.json"
    gm_runboard = tmp_path / "gm_runboard.json"
    core_doc = tmp_path / "core_doc.md"

    _write_yaml(registry, _registry())
    _write_yaml(fleet_queue, {"items": [_queue_item()]})
    _write_yaml(design_queue, {"items": [_queue_item()]})
    _write_text(
        guide,
        "## Wave 22P - close human-tested parity proof and desktop executable trust before successor breadth\n"
        "### 142. Direct parity proof for dense workbench, dice utilities, and identity or lifestyle workflows\n"
        "Exit: dense builder/career, dice/initiative, and identity/contacts/lifestyles/history families all flip to direct `yes/yes` parity with current route-local proof and dense-workbench captures.\n",
    )
    _write_yaml(workflow_pack, _workflow_pack_payload())
    rows = _parity_rows(direct=direct)
    _write_json(parity_audit, {"generated_at": "2026-05-05T12:00:00Z", "rows": rows, "elements": rows})
    _write_json(
        visual_gate,
        {
            "generated_at": "2026-05-05T12:00:00Z",
            "status": "pass",
            "screenshots": ["05-dense-section-light.png", "06-dense-section-dark.png", "10-contacts-section-light.png", "11-diary-dialog-light.png"],
            "evidence": {"legacy_dense_builder_rhythm": "pass", "legacy_contacts_workflow_rhythm": "pass"},
            "maybe": "dice_roller" if direct else "",
        },
    )
    _write_json(
        workflow_gate,
        {
            "generated_at": "2026-05-05T12:00:00Z",
            "status": "pass",
            "workflowFamilyIds": ["qualities-contacts-identities-notes-calendar-expenses-lifestyles-sources"],
        },
    )
    _write_json(
        screenshot_gate,
        {
            "generated_at": "2026-05-05T12:00:00Z",
            "status": "pass",
            "reviewJobs": {"dense_builder": {"screenshots": ["05-dense-section-light.png", "06-dense-section-dark.png"], "evidenceKeys": ["legacy_dense_builder_rhythm"]}},
        },
    )
    _write_json(
        dense_gate,
        {
            "generated_at": "2026-05-05T12:00:00Z",
            "status": "pass",
            "evidence": {"tests": ["Character_creation_preserves_familiar_dense_builder_rhythm", "Runtime_backed_toolstrip_preserves_flat_classic_toolbar_posture"]},
        },
    )
    _write_json(
        veteran_gate,
        {
            "generated_at": "2026-05-05T12:00:00Z",
            "status": "pass",
            "taskTimeEvidence": {"save": {"tests": ["save"]}},
        },
    )
    _write_json(
        ui_release,
        {
            "generated_at": "2026-05-05T12:00:00Z",
            "status": "pass",
            "proofs": {"dense": {"tokens": ["workflow:build_explain_publish"] if direct else []}},
            "screenshots": ["10-contacts-section-light.png", "11-diary-dialog-light.png"],
        },
    )
    _write_json(
        dialog_parity,
        {
            "generated_at": "2026-05-05T12:00:00Z",
            "status": "pass",
            "evidence": {"rebuildableDialogIdsFound": ["dialog.dice_roller"], "commandIdsFound": ["dice_roller"]},
        },
    )
    _write_json(
        section_host,
        {
            "generated_at": "2026-05-05T12:00:00Z",
            "status": "pass",
            "evidence": {
                "expectedTabIds": ["tab-info", "tab-skills", "tab-qualities", "tab-combat", "tab-gear", "tab-contacts", "tab-notes"],
                "expectedWorkspaceActionIds": ["tab-info.summary", "tab-skills.skills", "tab-gear.inventory", "tab-contacts.contacts", "tab-notes.metadata"],
            },
        },
    )
    _write_json(
        gm_runboard,
        {
            "generatedAt": "2026-05-05T12:00:00Z",
            "status": "pass",
            "evidence": {"surface": "gm_runboard", "summary": ["Initiative lane:", "ResolveRunboardInitiativeSummary"]},
        },
    )
    _write_text(
        core_doc,
        "SessionActionBudgetDeterministicReceipt\nWorkspaceWorkflowDeterministicReceipt\n"
        + ("workflow:lifestyles\n" if direct else ""),
    )
    return {
        "registry": registry,
        "fleet_queue": fleet_queue,
        "design_queue": design_queue,
        "guide": guide,
        "workflow_pack": workflow_pack,
        "parity_audit": parity_audit,
        "visual_gate": visual_gate,
        "workflow_gate": workflow_gate,
        "screenshot_gate": screenshot_gate,
        "dense_gate": dense_gate,
        "veteran_gate": veteran_gate,
        "ui_release": ui_release,
        "dialog_parity": dialog_parity,
        "section_host": section_host,
        "gm_runboard": gm_runboard,
        "core_doc": core_doc,
    }


class MaterializeNext90M142FleetRouteLocalProofCloseoutGatesTest(unittest.TestCase):
    def test_materializer_emits_passing_gate_when_rows_cite_route_local_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path, direct=True)
            artifact = tmp_path / "artifact.json"
            markdown = tmp_path / "artifact.md"
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--output", str(artifact),
                    "--markdown-output", str(markdown),
                    "--successor-registry", str(fixture["registry"]),
                    "--fleet-queue-staging", str(fixture["fleet_queue"]),
                    "--design-queue-staging", str(fixture["design_queue"]),
                    "--next90-guide", str(fixture["guide"]),
                    "--workflow-pack", str(fixture["workflow_pack"]),
                    "--parity-audit", str(fixture["parity_audit"]),
                    "--desktop-visual-familiarity-gate", str(fixture["visual_gate"]),
                    "--desktop-workflow-execution-gate", str(fixture["workflow_gate"]),
                    "--screenshot-review-gate", str(fixture["screenshot_gate"]),
                    "--classic-dense-workbench-gate", str(fixture["dense_gate"]),
                    "--veteran-task-time-gate", str(fixture["veteran_gate"]),
                    "--ui-flagship-release-gate", str(fixture["ui_release"]),
                    "--generated-dialog-parity", str(fixture["dialog_parity"]),
                    "--section-host-ruleset-parity", str(fixture["section_host"]),
                    "--gm-runboard-route", str(fixture["gm_runboard"]),
                    "--core-dense-receipts-doc", str(fixture["core_doc"]),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            payload = json.loads(artifact.read_text(encoding="utf-8"))
            assert payload["status"] == "pass"
            assert payload["monitor_summary"]["route_local_proof_closeout_status"] == "pass"
            assert payload["package_closeout"]["ready"] is True

    def test_materializer_blocks_when_rows_still_close_on_family_prose_and_broad_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path, direct=False)
            artifact = tmp_path / "artifact.json"
            markdown = tmp_path / "artifact.md"
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--output", str(artifact),
                    "--markdown-output", str(markdown),
                    "--successor-registry", str(fixture["registry"]),
                    "--fleet-queue-staging", str(fixture["fleet_queue"]),
                    "--design-queue-staging", str(fixture["design_queue"]),
                    "--next90-guide", str(fixture["guide"]),
                    "--workflow-pack", str(fixture["workflow_pack"]),
                    "--parity-audit", str(fixture["parity_audit"]),
                    "--desktop-visual-familiarity-gate", str(fixture["visual_gate"]),
                    "--desktop-workflow-execution-gate", str(fixture["workflow_gate"]),
                    "--screenshot-review-gate", str(fixture["screenshot_gate"]),
                    "--classic-dense-workbench-gate", str(fixture["dense_gate"]),
                    "--veteran-task-time-gate", str(fixture["veteran_gate"]),
                    "--ui-flagship-release-gate", str(fixture["ui_release"]),
                    "--generated-dialog-parity", str(fixture["dialog_parity"]),
                    "--section-host-ruleset-parity", str(fixture["section_host"]),
                    "--gm-runboard-route", str(fixture["gm_runboard"]),
                    "--core-dense-receipts-doc", str(fixture["core_doc"]),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            payload = json.loads(artifact.read_text(encoding="utf-8"))
            assert payload["status"] == "pass"
            assert payload["monitor_summary"]["route_local_proof_closeout_status"] == "blocked"
            assert any("family prose" in item or "route-local receipts" in item for item in payload["monitor_summary"]["runtime_blockers"])

    def test_materializer_accepts_live_workflow_pack_family_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path, direct=True)
            artifact = tmp_path / "artifact.json"
            markdown = tmp_path / "artifact.md"
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--output", str(artifact),
                    "--markdown-output", str(markdown),
                    "--successor-registry", str(fixture["registry"]),
                    "--fleet-queue-staging", str(fixture["fleet_queue"]),
                    "--design-queue-staging", str(fixture["design_queue"]),
                    "--next90-guide", str(fixture["guide"]),
                    "--workflow-pack", str(fixture["workflow_pack"]),
                    "--parity-audit", str(fixture["parity_audit"]),
                    "--desktop-visual-familiarity-gate", str(fixture["visual_gate"]),
                    "--desktop-workflow-execution-gate", str(fixture["workflow_gate"]),
                    "--screenshot-review-gate", str(fixture["screenshot_gate"]),
                    "--classic-dense-workbench-gate", str(fixture["dense_gate"]),
                    "--veteran-task-time-gate", str(fixture["veteran_gate"]),
                    "--ui-flagship-release-gate", str(fixture["ui_release"]),
                    "--generated-dialog-parity", str(fixture["dialog_parity"]),
                    "--section-host-ruleset-parity", str(fixture["section_host"]),
                    "--gm-runboard-route", str(fixture["gm_runboard"]),
                    "--core-dense-receipts-doc", str(fixture["core_doc"]),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            payload = json.loads(artifact.read_text(encoding="utf-8"))
            assert payload["canonical_monitors"]["workflow_pack_contract"]["state"] == "pass"


if __name__ == "__main__":
    unittest.main()
