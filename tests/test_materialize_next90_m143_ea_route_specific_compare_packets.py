from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


SCRIPT = Path("/docker/fleet/scripts/materialize_next90_m143_ea_route_specific_compare_packets.py")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_tree(tmp_path: Path) -> dict[str, Path]:
    telemetry = tmp_path / "task_local_telemetry.json"
    handoff = tmp_path / "ACTIVE_RUN_HANDOFF.generated.md"
    run_telemetry = tmp_path / "runs" / "fake-run" / "TASK_LOCAL_TELEMETRY.generated.json"
    readiness = tmp_path / "readiness.json"
    workflow_pack = tmp_path / "workflow_pack.yaml"
    parity_audit = tmp_path / "parity_audit.json"
    screenshot_gate = tmp_path / "screenshot_gate.json"
    section_host = tmp_path / "section_host.json"
    dialog_parity = tmp_path / "dialog_parity.json"
    rule_studio = tmp_path / "rule_studio.json"
    core_doc = tmp_path / "core_doc.md"
    fleet_gate = tmp_path / "fleet_gate.json"

    telemetry_payload = {
        "mode": "implementation_only",
        "scope_label": "Full Chummer5A parity and flagship proof closeout",
        "slice_summary": "Milestone 143 remains open. Outstanding readiness coverage: desktop_client.",
        "status_query_supported": False,
        "polling_disabled": True,
        "remaining_open_milestones": 1,
        "remaining_not_started_milestones": 1,
        "missing_flagship_coverage": "desktop_client",
        "frontier_briefs": ["5326878760 [flagship_product] M143 EA compare pack open."],
    }
    _write_json(telemetry, telemetry_payload)
    _write_json(
        run_telemetry,
        {
            **telemetry_payload,
            "slice_summary": "Telemetry resolved through the active runtime handoff.",
        },
    )
    _write_text(handoff, "- Run id: fake-run\n")
    _write_json(
        readiness,
        {
            "status": "fail",
            "missing_keys": [],
            "warning_keys": ["desktop_client"],
            "scoped_warning_keys": ["desktop_client"],
            "flagship_readiness_audit": {"reason": "desktop_client warning"},
        },
    )
    _write_yaml(
        workflow_pack,
        {
            "route_specific_compare_packs": [
                {
                    "family_id": "sheet_export_print_viewer_and_exchange",
                    "summary": "Route-local print/export proof.",
                    "compare_artifacts": ["menu:open_for_printing", "menu:open_for_export", "menu:file_print_multiple"],
                    "route_proofs": [
                        {
                            "route_id": "menu:open_for_printing",
                            "proof_receipts": [str(section_host)],
                            "required_tokens": ["open_for_printing"],
                        },
                        {
                            "route_id": "menu:open_for_export",
                            "proof_receipts": [str(section_host)],
                            "required_tokens": ["open_for_export"],
                        },
                        {
                            "route_id": "menu:file_print_multiple",
                            "proof_receipts": [str(dialog_parity)],
                            "required_tokens": ["print_multiple"],
                        },
                    ],
                    "artifact_proofs": {
                        "screenshot_receipts": [str(screenshot_gate)],
                        "required_screenshot_markers": [
                            "print_export_exchange",
                            "open_for_printing_menu_route",
                            "open_for_export_menu_route",
                            "print_multiple_menu_route",
                        ],
                        "output_receipts": [str(core_doc)],
                        "required_output_tokens": [
                            "WorkspaceExchangeDeterministicReceipt",
                            "family:sheet_export_print_viewer_and_exchange",
                        ],
                    },
                },
                {
                    "family_id": "sr6_supplements_designers_and_house_rules",
                    "summary": "Route-local SR6 proof.",
                    "compare_artifacts": ["workflow:sr6_supplements", "workflow:house_rules"],
                    "route_proofs": [
                        {
                            "route_id": "workflow:sr6_supplements",
                            "proof_receipts": [str(core_doc)],
                            "required_tokens": [
                                "Sr6SuccessorLaneDeterministicReceipt",
                                "family:sr6_supplements_designers_and_house_rules",
                                "supplement",
                            ],
                        },
                        {
                            "route_id": "workflow:house_rules",
                            "proof_receipts": [str(core_doc)],
                            "required_tokens": [
                                "Sr6SuccessorLaneDeterministicReceipt",
                                "family:sr6_supplements_designers_and_house_rules",
                                "house-rule",
                            ],
                        },
                        {
                            "route_id": "surface:rule_environment_studio",
                            "proof_receipts": [str(rule_studio)],
                            "required_tokens": ["rule_environment_studio"],
                        },
                    ],
                    "artifact_proofs": {
                        "screenshot_receipts": [str(screenshot_gate)],
                        "required_screenshot_markers": ["sr6_rule_environment", "sr6_supplements", "house_rules"],
                        "output_receipts": [],
                        "required_output_tokens": [],
                    },
                },
            ]
        },
    )
    _write_json(
        parity_audit,
        {
            "rows": [
                {
                    "id": "family:sheet_export_print_viewer_and_exchange",
                    "present_in_chummer5a": "yes",
                    "present_in_chummer6": "yes",
                    "visual_parity": "yes",
                    "behavioral_parity": "yes",
                    "removable_if_not_in_chummer5a": "no",
                    "reason": "Route-local print proof.",
                    "evidence": [str(workflow_pack), str(core_doc)],
                },
                {
                    "id": "family:sr6_supplements_designers_and_house_rules",
                    "present_in_chummer5a": "yes",
                    "present_in_chummer6": "yes",
                    "visual_parity": "yes",
                    "behavioral_parity": "yes",
                    "removable_if_not_in_chummer5a": "no",
                    "reason": "Route-local SR6 proof.",
                    "evidence": [str(workflow_pack), str(rule_studio), str(core_doc)],
                },
            ]
        },
    )
    _write_json(
        screenshot_gate,
        {
            "markers": [
                "print_export_exchange",
                "open_for_printing_menu_route",
                "open_for_export_menu_route",
                "print_multiple_menu_route",
                "sr6_rule_environment",
                "sr6_supplements",
                "house_rules",
            ]
        },
    )
    _write_json(section_host, {"tokens": ["open_for_printing", "open_for_export"]})
    _write_json(dialog_parity, {"tokens": ["print_multiple"]})
    _write_json(rule_studio, {"tokens": ["rule_environment_studio"]})
    _write_text(
        core_doc,
        "WorkspaceExchangeDeterministicReceipt family:sheet_export_print_viewer_and_exchange\n"
        "Sr6SuccessorLaneDeterministicReceipt family:sr6_supplements_designers_and_house_rules supplement house-rule\n",
    )
    _write_json(
        fleet_gate,
        {
            "runtime_monitors": {
                "proof_corpus": {
                    "family_receipt_summary": {
                        "family:sheet_export_print_viewer_and_exchange": {
                            "satisfied_route_receipts": [
                                "menu:open_for_printing",
                                "menu:open_for_export",
                                "menu:file_print_multiple",
                            ]
                        },
                        "family:sr6_supplements_designers_and_house_rules": {
                            "satisfied_route_receipts": [
                                "workflow:sr6_supplements",
                                "workflow:house_rules",
                                "surface:rule_environment_studio",
                            ]
                        },
                    }
                }
            }
        },
    )
    return {
        "telemetry": telemetry,
        "handoff": handoff,
        "run_telemetry": run_telemetry,
        "readiness": readiness,
        "workflow_pack": workflow_pack,
        "parity_audit": parity_audit,
        "screenshot_gate": screenshot_gate,
        "section_host": section_host,
        "dialog_parity": dialog_parity,
        "rule_studio": rule_studio,
        "core_doc": core_doc,
        "fleet_gate": fleet_gate,
    }


class MaterializeNext90M143EaRouteSpecificComparePacketsTest(unittest.TestCase):
    def test_materializes_family_and_route_packets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path)
            artifact = tmp_path / "artifact.yaml"
            markdown = tmp_path / "artifact.md"
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--output", str(artifact),
                    "--markdown-output", str(markdown),
                    "--task-local-telemetry", str(fixture["telemetry"]),
                    "--runtime-handoff", str(fixture["handoff"]),
                    "--readiness", str(fixture["readiness"]),
                    "--workflow-pack", str(fixture["workflow_pack"]),
                    "--parity-audit", str(fixture["parity_audit"]),
                    "--screenshot-review-gate", str(fixture["screenshot_gate"]),
                    "--section-host-ruleset-parity", str(fixture["section_host"]),
                    "--generated-dialog-parity", str(fixture["dialog_parity"]),
                    "--m114-rule-studio", str(fixture["rule_studio"]),
                    "--core-m143-receipts-doc", str(fixture["core_doc"]),
                    "--fleet-m143-gate", str(fixture["fleet_gate"]),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            payload = yaml.safe_load(artifact.read_text(encoding="utf-8"))
            assert payload["contract_name"] == "executive_assistant.m143_route_specific_compare_packets"
            assert payload["milestone"]["package_id"] == "next90-m143-ea-compile-route-specific-compare-packs-and-artifact-proofs-for-print-export"
            assert payload["whole_product_frontier_coverage"]["desktop_client_status"] == "warning"

            families = {
                row["family_id"]: row
                for row in payload["family_route_specific_compare_packets"]
            }
            assert set(families) == {
                "sheet_export_print_viewer_and_exchange",
                "sr6_supplements_designers_and_house_rules",
            }
            sheet_routes = {
                row["route_id"]: row
                for row in families["sheet_export_print_viewer_and_exchange"]["route_specific_compare_pack"]["route_receipts"]
            }
            assert sheet_routes["menu:file_print_multiple"]["status"] == "pass"
            assert families["sheet_export_print_viewer_and_exchange"]["artifact_proof_pack"]["status"] == "pass"

            markdown_text = markdown.read_text(encoding="utf-8")
            assert "## Family route-specific compare packets" in markdown_text
            assert "#### menu:open_for_printing" in markdown_text

    def test_materializes_from_runtime_handoff_when_task_local_telemetry_is_omitted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path)
            artifact = tmp_path / "artifact.yaml"
            markdown = tmp_path / "artifact.md"
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--output", str(artifact),
                    "--markdown-output", str(markdown),
                    "--runtime-handoff", str(fixture["handoff"]),
                    "--readiness", str(fixture["readiness"]),
                    "--workflow-pack", str(fixture["workflow_pack"]),
                    "--parity-audit", str(fixture["parity_audit"]),
                    "--screenshot-review-gate", str(fixture["screenshot_gate"]),
                    "--section-host-ruleset-parity", str(fixture["section_host"]),
                    "--generated-dialog-parity", str(fixture["dialog_parity"]),
                    "--m114-rule-studio", str(fixture["rule_studio"]),
                    "--core-m143-receipts-doc", str(fixture["core_doc"]),
                    "--fleet-m143-gate", str(fixture["fleet_gate"]),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            payload = yaml.safe_load(artifact.read_text(encoding="utf-8"))
            assert payload["sync_context"]["task_local_telemetry_path"] == str(fixture["run_telemetry"])
            assert (
                payload["sync_context"]["task_local_telemetry_snapshot"]["slice_summary"]
                == "Telemetry resolved through the active runtime handoff."
            )


if __name__ == "__main__":
    unittest.main()
