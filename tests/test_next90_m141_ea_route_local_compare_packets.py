from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


MATERIALIZE_SCRIPT = Path("/docker/fleet/scripts/materialize_next90_m141_ea_route_local_compare_packets.py")
VERIFY_SCRIPT = Path("/docker/fleet/scripts/verify_next90_m141_ea_route_local_compare_packets.py")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    _write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _fixture_tree(tmp_path: Path) -> dict[str, Path]:
    shard_root = tmp_path / "shard-5"
    run_id = "20260505T224749Z-shard-5"
    stale_run_id = "20260505T223247Z-shard-5"
    runtime_handoff = shard_root / "ACTIVE_RUN_HANDOFF.generated.md"
    active_telemetry = shard_root / "runs" / run_id / "TASK_LOCAL_TELEMETRY.generated.json"
    stale_telemetry = shard_root / "runs" / stale_run_id / "TASK_LOCAL_TELEMETRY.generated.json"
    readiness = tmp_path / "readiness.json"
    capture_pack = tmp_path / "capture_pack.yaml"
    workflow_pack = tmp_path / "workflow_pack.yaml"
    parity_audit = tmp_path / "parity_audit.json"
    screenshot_review_gate = tmp_path / "screenshot_review_gate.json"
    desktop_visual_gate = tmp_path / "desktop_visual_gate.json"
    veteran_task_gate = tmp_path / "veteran_task_gate.json"
    ui_release_gate = tmp_path / "ui_release_gate.json"
    import_receipts_doc = tmp_path / "NEXT90_M141_IMPORT_ROUTE_RECEIPTS.md"
    import_receipts_json = tmp_path / "NEXT90_M141_IMPORT_ROUTE_RECEIPTS.generated.json"
    import_parity_certification = tmp_path / "IMPORT_PARITY_CERTIFICATION.generated.json"

    _write_text(runtime_handoff, f"- Run id: {run_id}\n")
    _write_json(
        active_telemetry,
        {
            "mode": "implementation_only",
            "scope_label": "Full Chummer5A parity and flagship proof closeout",
            "slice_summary": "Milestone 141 remains open. Outstanding readiness coverage: desktop_client.",
            "status_query_supported": False,
            "polling_disabled": True,
            "remaining_open_milestones": 1,
            "remaining_not_started_milestones": 1,
            "missing_flagship_coverage": "desktop_client",
            "frontier_briefs": ["2841916304 [flagship_product] Compile route-local screenshot packs."],
        },
    )
    _write_json(
        stale_telemetry,
        {
            "mode": "implementation_only",
            "scope_label": "stale",
            "slice_summary": "stale",
            "status_query_supported": False,
            "polling_disabled": True,
            "remaining_open_milestones": 1,
            "remaining_not_started_milestones": 1,
            "missing_flagship_coverage": "desktop_client",
            "frontier_briefs": ["111 [flagship_product] stale."],
        },
    )
    _write_json(
        readiness,
        {
            "generated_at": "2026-05-05T22:45:56Z",
            "coverage": {"desktop_client": "missing"},
            "coverage_details": {"desktop_client": {"summary": "Desktop flagship proof is still incomplete."}},
            "missing_keys": ["desktop_client"],
        },
    )
    _write_yaml(
        capture_pack,
        {
            "oracle_surface_extract": {
                "source_line_proofs": {
                    "file_and_settings_routes": [
                        {
                            "id": "translator_route",
                            "file": "/docker/chummer5a/Chummer/Forms/ChummerMainForm.Designer.cs",
                            "line": 808,
                            "expected_substring": 'this.mnuToolsTranslator.Text = "&Translator";',
                        },
                        {
                            "id": "xml_amendment_editor_route",
                            "file": "/docker/chummer5a/Chummer/Forms/ChummerMainForm.Designer.cs",
                            "line": 823,
                            "expected_substring": 'this.mnuXmlEditor.Text = "&XML Amendment Editor";',
                        },
                        {
                            "id": "hero_lab_importer_route",
                            "file": "/docker/chummer5a/Chummer/Forms/ChummerMainForm.Designer.cs",
                            "line": 838,
                            "expected_substring": 'this.mnuHeroLabImporter.Text = "&Hero Lab Importer";',
                        },
                    ]
                }
            }
        },
    )
    _write_yaml(
        workflow_pack,
        {
            "families": [
                {
                    "id": "custom_data_xml_and_translator_bridge",
                    "compare_artifacts": ["menu:translator", "menu:xml_editor"],
                },
                {
                    "id": "legacy_and_adjacent_import_oracles",
                    "compare_artifacts": ["menu:hero_lab_importer", "workflow:import_oracle"],
                },
            ]
        },
    )
    parity_rows = [
        {
            "id": "source:translator_route",
            "present_in_chummer5a": "yes",
            "present_in_chummer6": "yes",
            "visual_parity": "yes",
            "behavioral_parity": "yes",
            "removable_if_not_in_chummer5a": "no",
            "reason": "Translator proof.",
            "evidence": ["/tmp/translator-proof"],
        },
        {
            "id": "source:xml_amendment_editor_route",
            "present_in_chummer5a": "yes",
            "present_in_chummer6": "yes",
            "visual_parity": "yes",
            "behavioral_parity": "yes",
            "removable_if_not_in_chummer5a": "no",
            "reason": "XML proof.",
            "evidence": ["/tmp/xml-proof"],
        },
        {
            "id": "source:hero_lab_importer_route",
            "present_in_chummer5a": "yes",
            "present_in_chummer6": "yes",
            "visual_parity": "yes",
            "behavioral_parity": "yes",
            "removable_if_not_in_chummer5a": "no",
            "reason": "Hero Lab proof.",
            "evidence": ["/tmp/hero-proof"],
        },
        {
            "id": "family:custom_data_xml_and_translator_bridge",
            "present_in_chummer5a": "yes",
            "present_in_chummer6": "yes",
            "visual_parity": "yes",
            "behavioral_parity": "yes",
            "removable_if_not_in_chummer5a": "no",
            "reason": "Family translator/XML proof.",
            "evidence": ["/tmp/family-xml-proof"],
        },
        {
            "id": "family:legacy_and_adjacent_import_oracles",
            "present_in_chummer5a": "yes",
            "present_in_chummer6": "yes",
            "visual_parity": "yes",
            "behavioral_parity": "yes",
            "removable_if_not_in_chummer5a": "no",
            "reason": "Family import proof.",
            "evidence": ["/tmp/family-import-proof"],
        },
    ]
    _write_json(parity_audit, {"generated_at": "2026-05-05T20:18:25Z", "rows": parity_rows})
    _write_json(
        screenshot_review_gate,
        {
            "generated_at": "2026-05-05T21:48:31Z",
            "evidence": {
                "screenshotDirectory": "/tmp/ui-flagship-release-gate-screenshots",
                "routeLocalReceipts": {
                    "translator_xml_custom_data": {
                        "workflowFamilyId": "improvements-explain-result-parity",
                        "legacyBehaviorLineage": "Translator and XML continuity.",
                        "routeIds": [
                            "translator",
                            "xml_editor",
                            "source:translator_route",
                            "source:xml_amendment_editor_route",
                            "family:custom_data_xml_and_translator_bridge",
                        ],
                    },
                    "hero_lab_import_oracle": {
                        "workflowFamilyId": "create-open-import-save-save-as-print-export",
                        "legacyBehaviorLineage": "Hero Lab continuity.",
                        "routeIds": [
                            "hero_lab_importer",
                            "source:hero_lab_importer_route",
                            "family:legacy_and_adjacent_import_oracles",
                        ],
                    },
                },
            },
        },
    )
    _write_json(desktop_visual_gate, {"generated_at": "2026-05-05T22:44:12Z", "status": "pass"})
    _write_json(
        veteran_task_gate,
        {
            "generated_at": "2026-05-05T21:49:04Z",
            "proofs": {
                "translator_xml_custom_data": {
                    "tests": [
                        "ExecuteCommandAsync_translator_opens_dialog_with_master_index_lane_posture",
                        "ExecuteCommandAsync_xml_editor_opens_dialog_with_xml_bridge_posture",
                    ]
                },
                "hero_lab_import_oracle": {
                    "tests": ["ExecuteCommandAsync_hero_lab_importer_opens_dialog_with_import_oracle_lane_posture"]
                },
            },
        },
    )
    _write_json(
        ui_release_gate,
        {
            "generated_at": "2026-05-05T22:41:00Z",
            "visualReviewEvidence": {
                "expectedScreenshots": [
                    "38-translator-dialog-light.png",
                    "39-xml-editor-dialog-light.png",
                    "40-hero-lab-importer-dialog-light.png",
                ]
            },
            "proofs": {
                "translator_xml_custom_data": {
                    "tests": ["ExecuteCommandAsync_translator_opens_dialog_with_master_index_lane_posture"]
                },
                "hero_lab_import_oracle": {
                    "tests": ["ExecuteCommandAsync_hero_lab_importer_opens_dialog_with_import_oracle_lane_posture"]
                },
            },
        },
    )
    _write_text(
        import_receipts_doc,
        "customDataXmlBridgeDeterministicReceipt\n"
        "translatorDeterministicReceipt\n"
        "importOracleDeterministicReceipt\n"
        "family:custom_data_xml_and_translator_bridge\n"
        "family:legacy_and_adjacent_import_oracles\n",
    )
    _write_json(import_receipts_json, {"generated_at": "2026-05-05T22:22:46Z", "status": "pass"})
    _write_json(import_parity_certification, {"generated_at": "2026-04-04T19:20:00Z", "status": "passed"})

    return {
        "runtime_handoff": runtime_handoff,
        "active_telemetry": active_telemetry,
        "stale_telemetry": stale_telemetry,
        "readiness": readiness,
        "capture_pack": capture_pack,
        "workflow_pack": workflow_pack,
        "parity_audit": parity_audit,
        "screenshot_review_gate": screenshot_review_gate,
        "desktop_visual_gate": desktop_visual_gate,
        "veteran_task_gate": veteran_task_gate,
        "ui_release_gate": ui_release_gate,
        "import_receipts_doc": import_receipts_doc,
        "import_receipts_json": import_receipts_json,
        "import_parity_certification": import_parity_certification,
    }


class Next90M141EaRouteLocalComparePacketsTest(unittest.TestCase):
    def test_materializer_uses_active_run_from_runtime_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path)
            artifact = tmp_path / "artifact.yaml"
            markdown = tmp_path / "artifact.md"
            subprocess.run(
                [
                    sys.executable,
                    str(MATERIALIZE_SCRIPT),
                    "--output",
                    str(artifact),
                    "--markdown-output",
                    str(markdown),
                    "--runtime-handoff",
                    str(fixture["runtime_handoff"]),
                    "--readiness",
                    str(fixture["readiness"]),
                    "--capture-pack",
                    str(fixture["capture_pack"]),
                    "--workflow-pack",
                    str(fixture["workflow_pack"]),
                    "--parity-audit",
                    str(fixture["parity_audit"]),
                    "--screenshot-review-gate",
                    str(fixture["screenshot_review_gate"]),
                    "--desktop-visual-gate",
                    str(fixture["desktop_visual_gate"]),
                    "--veteran-task-gate",
                    str(fixture["veteran_task_gate"]),
                    "--ui-release-gate",
                    str(fixture["ui_release_gate"]),
                    "--import-receipts-doc",
                    str(fixture["import_receipts_doc"]),
                    "--import-receipts-json",
                    str(fixture["import_receipts_json"]),
                    "--import-parity-certification",
                    str(fixture["import_parity_certification"]),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            payload = yaml.safe_load(artifact.read_text(encoding="utf-8"))
            assert payload["sync_context"]["task_local_telemetry_path"] == str(fixture["active_telemetry"])
            assert payload["milestone"]["frontier_id"] == 2841916304
            assert payload["sync_context"]["desktop_visual_gate_generated_at"] == "2026-05-05T22:44:12Z"

    def test_verifier_uses_runtime_handoff_when_task_local_path_is_not_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path)
            artifact = tmp_path / "artifact.yaml"
            markdown = tmp_path / "artifact.md"
            subprocess.run(
                [
                    sys.executable,
                    str(MATERIALIZE_SCRIPT),
                    "--output",
                    str(artifact),
                    "--markdown-output",
                    str(markdown),
                    "--runtime-handoff",
                    str(fixture["runtime_handoff"]),
                    "--readiness",
                    str(fixture["readiness"]),
                    "--capture-pack",
                    str(fixture["capture_pack"]),
                    "--workflow-pack",
                    str(fixture["workflow_pack"]),
                    "--parity-audit",
                    str(fixture["parity_audit"]),
                    "--screenshot-review-gate",
                    str(fixture["screenshot_review_gate"]),
                    "--desktop-visual-gate",
                    str(fixture["desktop_visual_gate"]),
                    "--veteran-task-gate",
                    str(fixture["veteran_task_gate"]),
                    "--ui-release-gate",
                    str(fixture["ui_release_gate"]),
                    "--import-receipts-doc",
                    str(fixture["import_receipts_doc"]),
                    "--import-receipts-json",
                    str(fixture["import_receipts_json"]),
                    "--import-parity-certification",
                    str(fixture["import_parity_certification"]),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            verify = subprocess.run(
                [
                    sys.executable,
                    str(VERIFY_SCRIPT),
                    "--artifact",
                    str(artifact),
                    "--markdown-artifact",
                    str(markdown),
                    "--runtime-handoff",
                    str(fixture["runtime_handoff"]),
                    "--readiness",
                    str(fixture["readiness"]),
                    "--capture-pack",
                    str(fixture["capture_pack"]),
                    "--workflow-pack",
                    str(fixture["workflow_pack"]),
                    "--parity-audit",
                    str(fixture["parity_audit"]),
                    "--screenshot-review-gate",
                    str(fixture["screenshot_review_gate"]),
                    "--desktop-visual-gate",
                    str(fixture["desktop_visual_gate"]),
                    "--veteran-task-gate",
                    str(fixture["veteran_task_gate"]),
                    "--ui-release-gate",
                    str(fixture["ui_release_gate"]),
                    "--import-receipts-doc",
                    str(fixture["import_receipts_doc"]),
                    "--import-receipts-json",
                    str(fixture["import_receipts_json"]),
                    "--import-parity-certification",
                    str(fixture["import_parity_certification"]),
                    "--json",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            assert '"status": "pass"' in verify.stdout


if __name__ == "__main__":
    unittest.main()
