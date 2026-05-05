from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


SCRIPT = Path("/docker/fleet/scripts/materialize_next90_m143_fleet_route_local_output_closeout_gates.py")
QUEUE_PROOF = [
    "/docker/fleet/scripts/materialize_next90_m143_fleet_route_local_output_closeout_gates.py",
    "/docker/fleet/scripts/verify_next90_m143_fleet_route_local_output_closeout_gates.py",
    "/docker/fleet/tests/test_materialize_next90_m143_fleet_route_local_output_closeout_gates.py",
    "/docker/fleet/tests/test_verify_next90_m143_fleet_route_local_output_closeout_gates.py",
    "/docker/fleet/.codex-studio/published/NEXT90_M143_FLEET_ROUTE_LOCAL_OUTPUT_CLOSEOUT_GATES.generated.json",
    "/docker/fleet/.codex-studio/published/NEXT90_M143_FLEET_ROUTE_LOCAL_OUTPUT_CLOSEOUT_GATES.generated.md",
    "/docker/fleet/feedback/2026-05-05-next90-m143-fleet-route-local-output-closeout.md",
]
REGISTRY_EVIDENCE = [
    "/docker/fleet/scripts/materialize_next90_m143_fleet_route_local_output_closeout_gates.py and /docker/fleet/scripts/verify_next90_m143_fleet_route_local_output_closeout_gates.py now fail closed when milestone 143 families rely on broad family prose, missing outputs, or reopened canonical closeout metadata instead of route-local output receipts.",
    "/docker/fleet/tests/test_materialize_next90_m143_fleet_route_local_output_closeout_gates.py and /docker/fleet/tests/test_verify_next90_m143_fleet_route_local_output_closeout_gates.py now cover route-local output evidence requirements plus canonical closeout metadata so stale or reopened rows break the gate.",
    "/docker/fleet/.codex-studio/published/NEXT90_M143_FLEET_ROUTE_LOCAL_OUTPUT_CLOSEOUT_GATES.generated.json and /docker/fleet/.codex-studio/published/NEXT90_M143_FLEET_ROUTE_LOCAL_OUTPUT_CLOSEOUT_GATES.generated.md record the current pass state for print/export/exchange and SR6 supplement/house-rule families against route-local receipts and output proof surfaces.",
    "python3 scripts/materialize_next90_m143_fleet_route_local_output_closeout_gates.py, python3 scripts/verify_next90_m143_fleet_route_local_output_closeout_gates.py --json, and python3 -m unittest tests.test_materialize_next90_m143_fleet_route_local_output_closeout_gates tests.test_verify_next90_m143_fleet_route_local_output_closeout_gates all exit 0.",
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


def _registry(*, closeout_complete: bool) -> dict:
    row = {
        "id": "143.6",
        "owner": "fleet",
        "title": "Fail closeout when these families remain green only by broad family prose, missing outputs, or stale route-local receipts.",
    }
    if closeout_complete:
        row["status"] = "complete"
        row["evidence"] = list(REGISTRY_EVIDENCE)
    return {"milestones": [{"id": 143, "work_tasks": [row]}]}


def _queue_item(*, closeout_complete: bool) -> dict:
    row = {
        "title": "Fail closeout when these families remain green only by broad family prose, missing outputs, or stale route-local receipts.",
        "task": "Fail closeout when these families remain green only by broad family prose, missing outputs, or stale route-local receipts.",
        "package_id": "next90-m143-fleet-fail-closeout-when-these-families-remain-green-only-by-broad-family-pr",
        "milestone_id": 143,
        "work_task_id": "143.6",
        "frontier_id": 8787562259,
        "wave": "W22P",
        "repo": "fleet",
        "allowed_paths": ["scripts", "tests", ".codex-studio", "feedback"],
        "owned_surfaces": ["fail_closeout_when_these_families_remain_green_only_by_b:fleet"],
    }
    if closeout_complete:
        row["status"] = "complete"
        row["completion_action"] = "verify_closed_package_only"
        row["landed_commit"] = "unlanded"
        row["do_not_reopen_reason"] = (
            "M143 fleet route-local output closeout gate is complete; future shards must verify the repo-local gate scripts, "
            "generated proof artifacts, and canonical queue/registry mirrors instead of reopening print or export or exchange "
            "and SR6 supplement or house-rule parity closeout by broad family prose."
        )
        row["proof"] = list(QUEUE_PROOF)
    return row


def _workflow_pack_payload() -> dict:
    return {
        "workflow_maps": [
            {
                "id": "import_export_round_trip",
                "compare_artifacts": [
                    "fixture:open_for_printing_menu_route",
                    "fixture:open_for_export_menu_route",
                    "fixture:print_multiple_menu_route",
                ],
            }
        ],
        "families": [
            {
                "id": "sheet_export_print_viewer_and_exchange",
                "compare_artifacts": ["menu:open_for_printing", "menu:open_for_export", "menu:file_print_multiple"],
            },
            {
                "id": "sr6_supplements_designers_and_house_rules",
                "compare_artifacts": ["workflow:sr6_supplements", "workflow:house_rules"],
            },
        ],
    }


def _parity_rows(*, direct: bool) -> list[dict]:
    broad = [
        "/tmp/veteran_workflow_packs.yaml",
        "/tmp/DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json",
        "/tmp/DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json",
    ]
    return [
        {
            "id": "family:sheet_export_print_viewer_and_exchange",
            "label": "Sheet Export Print Viewer And Exchange",
            "visual_parity": "yes",
            "behavioral_parity": "yes",
            "present_in_chummer5a": "yes",
            "present_in_chummer6": "yes",
            "removable_if_not_in_chummer5a": "no",
            "reason": (
                "Route-local print and exchange proof is cited."
                if direct
                else "All declared compare artifacts for this Chummer5A family are directly backed by current parity proof: ['menu:open_for_printing', 'menu:open_for_export', 'menu:file_print_multiple']."
            ),
            "evidence": (
                [
                    "/tmp/SECTION_HOST_RULESET_PARITY.generated.json",
                    "/tmp/GENERATED_DIALOG_ELEMENT_PARITY.generated.json",
                    "/tmp/NEXT90_M143_EXPORT_PRINT_SUPPLEMENT_RULE_ENVIRONMENT_RECEIPTS.md",
                    "/tmp/CHUMMER5A_SCREENSHOT_REVIEW_GATE.generated.json",
                ]
                if direct
                else broad
            ),
        },
        {
            "id": "family:sr6_supplements_designers_and_house_rules",
            "label": "Sr6 Supplements Designers And House Rules",
            "visual_parity": "yes",
            "behavioral_parity": "yes",
            "present_in_chummer5a": "yes",
            "present_in_chummer6": "yes",
            "removable_if_not_in_chummer5a": "no",
            "reason": (
                "Route-local SR6 rule-environment proof is cited."
                if direct
                else "All declared compare artifacts for this Chummer5A family are directly backed by current parity proof: ['workflow:sr6_supplements', 'workflow:house_rules']."
            ),
            "evidence": (
                [
                    "/tmp/NEXT90_M114_UI_RULE_STUDIO.generated.json",
                    "/tmp/NEXT90_M143_EXPORT_PRINT_SUPPLEMENT_RULE_ENVIRONMENT_RECEIPTS.md",
                    "/tmp/CHUMMER5A_SCREENSHOT_REVIEW_GATE.generated.json",
                ]
                if direct
                else broad
            ),
        },
    ]


def _fixture_tree(tmp_path: Path, *, direct: bool, closeout_complete: bool = True) -> dict[str, Path]:
    registry = tmp_path / "registry.yaml"
    fleet_queue = tmp_path / "fleet_queue.yaml"
    design_queue = tmp_path / "design_queue.yaml"
    guide = tmp_path / "guide.md"
    workflow_pack = tmp_path / "workflow_pack.yaml"
    parity_audit = tmp_path / "parity_audit.json"
    screenshot_gate = tmp_path / "screenshot_gate.json"
    visual_gate = tmp_path / "visual_gate.json"
    section_host = tmp_path / "section_host.json"
    dialog_parity = tmp_path / "dialog_parity.json"
    rule_studio = tmp_path / "rule_studio.json"
    core_doc = tmp_path / "core_doc.md"

    _write_yaml(registry, _registry(closeout_complete=closeout_complete))
    _write_yaml(fleet_queue, {"items": [_queue_item(closeout_complete=closeout_complete)]})
    _write_yaml(design_queue, {"items": [_queue_item(closeout_complete=closeout_complete)]})
    _write_text(
        guide,
        "## Wave 22P - close human-tested parity proof and desktop executable trust before successor breadth\n"
        "### 143. Direct parity proof for print/export/exchange and SR6 supplements or house-rule workflows\n"
        "Exit: print/export/exchange plus SR6 supplement/house-rule families all flip to direct `yes/yes` parity with current screenshot/runtime proof and receipt-backed outputs.\n",
    )
    _write_yaml(workflow_pack, _workflow_pack_payload())
    rows = _parity_rows(direct=direct)
    _write_json(parity_audit, {"generated_at": "2026-05-05T12:00:00Z", "rows": rows, "elements": rows})
    _write_json(
        screenshot_gate,
        {
            "generated_at": "2026-05-05T12:00:00Z",
            "status": "pass",
            "reviewJobs": (
                {
                    "print_export_exchange": {
                        "screenshots": ["12-open-for-printing-dialog.png", "13-open-for-export-dialog.png", "14-print-multiple-dialog.png"],
                        "evidenceKeys": ["open_for_printing_menu_route", "open_for_export_menu_route", "print_multiple_menu_route"],
                    },
                    "sr6_rule_environment": {
                        "screenshots": ["15-sr6-rule-environment.png"],
                        "evidenceKeys": ["sr6_supplements", "house_rules"],
                    },
                }
                if direct
                else {"dense_builder": {"screenshots": ["05-dense-section-light.png"], "evidenceKeys": ["legacy_dense_builder_rhythm"]}}
            ),
        },
    )
    _write_json(
        visual_gate,
        {
            "generated_at": "2026-05-05T12:00:00Z",
            "status": "pass",
            "screenshots": ["12-open-for-printing-dialog.png", "13-open-for-export-dialog.png"] if direct else ["05-dense-section-light.png"],
        },
    )
    _write_json(
        section_host,
        {
            "generated_at": "2026-05-05T12:00:00Z",
            "status": "pass",
            "evidence": {
                "commandIdsFound": ["open_for_printing", "open_for_export", "print_multiple"],
            },
        },
    )
    _write_json(
        dialog_parity,
        {
            "generated_at": "2026-05-05T12:00:00Z",
            "status": "pass",
            "evidence": {
                "commandIdsFound": ["open_for_printing", "open_for_export", "print_multiple"] if direct else ["open_for_printing", "open_for_export"],
                "rebuildableDialogIdsFound": ["dialog.print_multiple"] if direct else [],
            },
        },
    )
    _write_json(
        rule_studio,
        {
            "generatedAt": "2026-05-05T12:00:00Z",
            "status": "pass",
            "evidence": {"ownedSurfaces": ["rule_environment_studio:desktop"]},
        },
    )
    _write_text(
        core_doc,
        (
            "WorkspaceExchangeDeterministicReceipt\n"
            "family:sheet_export_print_viewer_and_exchange\n"
            "Sr6SuccessorLaneDeterministicReceipt\n"
            "family:sr6_supplements_designers_and_house_rules\n"
            "supplement\n"
            "house-rule\n"
        )
        if direct
        else "WorkspaceExchangeDeterministicReceipt\nfamily:sheet_export_print_viewer_and_exchange\n"
    )
    return {
        "registry": registry,
        "fleet_queue": fleet_queue,
        "design_queue": design_queue,
        "guide": guide,
        "workflow_pack": workflow_pack,
        "parity_audit": parity_audit,
        "screenshot_gate": screenshot_gate,
        "visual_gate": visual_gate,
        "section_host": section_host,
        "dialog_parity": dialog_parity,
        "rule_studio": rule_studio,
        "core_doc": core_doc,
    }


class MaterializeNext90M143FleetRouteLocalOutputCloseoutGatesTest(unittest.TestCase):
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
                    "--screenshot-review-gate", str(fixture["screenshot_gate"]),
                    "--desktop-visual-familiarity-gate", str(fixture["visual_gate"]),
                    "--section-host-ruleset-parity", str(fixture["section_host"]),
                    "--generated-dialog-parity", str(fixture["dialog_parity"]),
                    "--m114-rule-studio", str(fixture["rule_studio"]),
                    "--core-m143-receipts-doc", str(fixture["core_doc"]),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            payload = json.loads(artifact.read_text(encoding="utf-8"))
            assert payload["status"] == "pass"
            assert payload["monitor_summary"]["route_local_output_closeout_status"] == "pass"
            assert payload["package_closeout"]["ready"] is True

    def test_materializer_blocks_when_rows_still_close_on_family_prose_and_missing_receipts(self) -> None:
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
                    "--screenshot-review-gate", str(fixture["screenshot_gate"]),
                    "--desktop-visual-familiarity-gate", str(fixture["visual_gate"]),
                    "--section-host-ruleset-parity", str(fixture["section_host"]),
                    "--generated-dialog-parity", str(fixture["dialog_parity"]),
                    "--m114-rule-studio", str(fixture["rule_studio"]),
                    "--core-m143-receipts-doc", str(fixture["core_doc"]),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            payload = json.loads(artifact.read_text(encoding="utf-8"))
            assert payload["status"] == "pass"
            assert payload["monitor_summary"]["route_local_output_closeout_status"] == "blocked"
            assert any(
                "family prose" in item or "route-local receipts" in item or "receipt:workspace_exchange" in item
                for item in payload["monitor_summary"]["runtime_blockers"]
            )

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
                    "--screenshot-review-gate", str(fixture["screenshot_gate"]),
                    "--desktop-visual-familiarity-gate", str(fixture["visual_gate"]),
                    "--section-host-ruleset-parity", str(fixture["section_host"]),
                    "--generated-dialog-parity", str(fixture["dialog_parity"]),
                    "--m114-rule-studio", str(fixture["rule_studio"]),
                    "--core-m143-receipts-doc", str(fixture["core_doc"]),
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
