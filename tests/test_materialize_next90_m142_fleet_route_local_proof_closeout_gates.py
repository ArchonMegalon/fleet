from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


SCRIPT = Path("/docker/fleet/scripts/materialize_next90_m142_fleet_route_local_proof_closeout_gates.py")
QUEUE_PROOF = [
    "/docker/fleet/scripts/materialize_next90_m142_fleet_route_local_proof_closeout_gates.py",
    "/docker/fleet/scripts/verify_next90_m142_fleet_route_local_proof_closeout_gates.py",
    "/docker/fleet/tests/test_materialize_next90_m142_fleet_route_local_proof_closeout_gates.py",
    "/docker/fleet/tests/test_verify_next90_m142_fleet_route_local_proof_closeout_gates.py",
    "/docker/fleet/.codex-studio/published/NEXT90_M142_FLEET_ROUTE_LOCAL_PROOF_CLOSEOUT_GATES.generated.json",
    "/docker/fleet/.codex-studio/published/NEXT90_M142_FLEET_ROUTE_LOCAL_PROOF_CLOSEOUT_GATES.generated.md",
    "/docker/fleet/feedback/2026-05-05-next90-m142-fleet-route-local-proof-closeout.md",
]
REGISTRY_EVIDENCE = [
    "/docker/fleet/scripts/materialize_next90_m142_fleet_route_local_proof_closeout_gates.py and /docker/fleet/scripts/verify_next90_m142_fleet_route_local_proof_closeout_gates.py now fail closed when milestone 142 family rows rely on family prose, stale captures, or reopened canonical closeout metadata instead of route-local proof receipts.",
    "/docker/fleet/tests/test_materialize_next90_m142_fleet_route_local_proof_closeout_gates.py and /docker/fleet/tests/test_verify_next90_m142_fleet_route_local_proof_closeout_gates.py now cover direct route-local evidence requirements plus the canonical closeout metadata so stale or reopened rows break the gate.",
    "/docker/fleet/.codex-studio/published/NEXT90_M142_FLEET_ROUTE_LOCAL_PROOF_CLOSEOUT_GATES.generated.json and /docker/fleet/.codex-studio/published/NEXT90_M142_FLEET_ROUTE_LOCAL_PROOF_CLOSEOUT_GATES.generated.md record the current pass state for dense builder/career, dice/initiative, and identity/contacts/lifestyles/history against route-local receipts and dense-workbench proof surfaces.",
    "python3 scripts/materialize_next90_m142_fleet_route_local_proof_closeout_gates.py, python3 scripts/verify_next90_m142_fleet_route_local_proof_closeout_gates.py --json, and python3 -m unittest tests.test_materialize_next90_m142_fleet_route_local_proof_closeout_gates tests.test_verify_next90_m142_fleet_route_local_proof_closeout_gates all exit 0.",
]


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


def _registry(*, closeout_complete: bool) -> dict:
    row = {
        "id": "142.5",
        "owner": "fleet",
        "title": "Fail closeout when any route in this milestone closes on family prose, stale captures, or missing task-speed and runtime receipts.",
    }
    if closeout_complete:
        row["status"] = "complete"
        row["evidence"] = list(REGISTRY_EVIDENCE)
    return {"milestones": [{"id": 142, "work_tasks": [row]}]}


def _queue_item(*, closeout_complete: bool) -> dict:
    row = {
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
    if closeout_complete:
        row["status"] = "complete"
        row["completion_action"] = "verify_closed_package_only"
        row["landed_commit"] = "unlanded"
        row["do_not_reopen_reason"] = (
            "M142 fleet route-local proof closeout gate is complete; future shards must verify the repo-local gate scripts, "
            "generated proof artifacts, and canonical queue/registry mirrors instead of reopening dense workbench, dice or "
            "initiative, and identity or lifestyle parity closeout by family prose."
        )
        row["proof"] = list(QUEUE_PROOF)
    return row


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


def _fixture_tree(tmp_path: Path, *, direct: bool, closeout_complete: bool = True) -> dict[str, Path]:
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
    ui_local_release = tmp_path / "ui_local_release.json"
    dialog_parity = tmp_path / "dialog_parity.json"
    section_host = tmp_path / "section_host.json"
    gm_runboard = tmp_path / "gm_runboard.json"
    core_doc = tmp_path / "core_doc.md"

    _write_yaml(registry, _registry(closeout_complete=closeout_complete))
    _write_yaml(fleet_queue, {"items": [_queue_item(closeout_complete=closeout_complete)]})
    _write_yaml(design_queue, {"items": [_queue_item(closeout_complete=closeout_complete)]})
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
        ui_local_release,
        {
            "generated_at": "2026-05-05T12:00:00Z",
            "status": "passed",
            "journeys_passed": ["build_explain_publish"] if direct else [],
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
        "ui_local_release": ui_local_release,
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
                    "--ui-local-release-proof", str(fixture["ui_local_release"]),
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
            dense_row = next(row for row in payload["runtime_monitors"]["target_rows"]["rows"] if row["id"] == "family:dense_builder_and_career_workflows")
            assert any(item.endswith("SECTION_HOST_RULESET_PARITY.generated.json") for item in dense_row["evidence"])
            assert any(item.endswith("CHUMMER5A_SCREENSHOT_REVIEW_GATE.generated.json") for item in dense_row["evidence"])

    def test_materializer_blocks_when_rows_still_close_on_family_prose_and_broad_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path, direct=False)
            workflow_gate = json.loads(fixture["workflow_gate"].read_text(encoding="utf-8"))
            workflow_gate["workflowFamilyIds"] = []
            fixture["workflow_gate"].write_text(json.dumps(workflow_gate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
                    "--ui-local-release-proof", str(fixture["ui_local_release"]),
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
            assert any("live proof corpus still lacks direct route-local receipts" in item for item in payload["monitor_summary"]["runtime_blockers"])

    def test_materializer_projects_direct_row_evidence_when_runtime_receipts_are_current(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path, direct=True)
            parity_audit = json.loads(fixture["parity_audit"].read_text(encoding="utf-8"))
            for row in parity_audit["rows"]:
                row["reason"] = (
                    "All declared compare artifacts for this Chummer5A family are directly backed by current parity proof: "
                    + str(row.get("compare_artifacts") or [])
                    + "."
                )
                row["evidence"] = [
                    "/tmp/veteran_workflow_packs.yaml",
                    "/tmp/DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json",
                    "/tmp/DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json",
                ]
            parity_audit["elements"] = parity_audit["rows"]
            fixture["parity_audit"].write_text(json.dumps(parity_audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")

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
                    "--ui-local-release-proof", str(fixture["ui_local_release"]),
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
            assert payload["monitor_summary"]["route_local_proof_closeout_status"] == "warning"
            assert payload["package_closeout"]["ready"] is True
            dense_row = next(row for row in payload["runtime_monitors"]["target_rows"]["rows"] if row["id"] == "family:dense_builder_and_career_workflows")
            assert dense_row["source_reason"].startswith("All declared compare artifacts")
            assert dense_row["reason"].startswith("Fleet route-local closeout packet binds direct runtime/task-speed receipts")
            assert any(item.endswith("ui_local_release.json") for item in dense_row["evidence"])
            assert not dense_row["issues"]

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
                    "--ui-local-release-proof", str(fixture["ui_local_release"]),
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

    def test_materializer_fails_when_closeout_metadata_is_not_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path, direct=True, closeout_complete=False)
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
                    "--ui-local-release-proof", str(fixture["ui_local_release"]),
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
            assert payload["status"] == "fail"
            assert payload["package_closeout"]["ready"] is False
            assert any("status must be complete" in item or "queue status drifted" in item for item in payload["package_closeout"]["reasons"])


if __name__ == "__main__":
    unittest.main()
