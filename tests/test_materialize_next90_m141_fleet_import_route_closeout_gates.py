from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


SCRIPT = Path("/docker/fleet/scripts/materialize_next90_m141_fleet_import_route_closeout_gates.py")
QUEUE_PROOF = [
    "/docker/fleet/scripts/materialize_next90_m141_fleet_import_route_closeout_gates.py",
    "/docker/fleet/scripts/verify_next90_m141_fleet_import_route_closeout_gates.py",
    "/docker/fleet/tests/test_materialize_next90_m141_fleet_import_route_closeout_gates.py",
    "/docker/fleet/tests/test_verify_next90_m141_fleet_import_route_closeout_gates.py",
    "/docker/fleet/.codex-studio/published/NEXT90_M141_FLEET_IMPORT_ROUTE_CLOSEOUT_GATES.generated.json",
    "/docker/fleet/.codex-studio/published/NEXT90_M141_FLEET_IMPORT_ROUTE_CLOSEOUT_GATES.generated.md",
    "/docker/fleet/feedback/2026-05-05-next90-m141-fleet-import-route-closeout.md",
]
REGISTRY_EVIDENCE = [
    "/docker/fleet/scripts/materialize_next90_m141_fleet_import_route_closeout_gates.py and /docker/fleet/scripts/verify_next90_m141_fleet_import_route_closeout_gates.py now fail closed when the milestone 141 route and family rows drift from direct proof receipts or when the canonical closeout metadata reopens.",
    "/docker/fleet/tests/test_materialize_next90_m141_fleet_import_route_closeout_gates.py and /docker/fleet/tests/test_verify_next90_m141_fleet_import_route_closeout_gates.py now cover append-style queue ingestion, direct field-shape requirements, and canonical closeout metadata so stale rows or reopened packages break the gate.",
    "/docker/fleet/.codex-studio/published/NEXT90_M141_FLEET_IMPORT_ROUTE_CLOSEOUT_GATES.generated.json and /docker/fleet/.codex-studio/published/NEXT90_M141_FLEET_IMPORT_ROUTE_CLOSEOUT_GATES.generated.md record the current pass state for translator, XML amendment, Hero Lab, and the two family rows against screenshot-backed, runtime-backed, and core deterministic import receipts.",
    "python3 scripts/materialize_next90_m141_fleet_import_route_closeout_gates.py, python3 scripts/verify_next90_m141_fleet_import_route_closeout_gates.py --json, and python3 -m unittest tests.test_materialize_next90_m141_fleet_import_route_closeout_gates tests.test_verify_next90_m141_fleet_import_route_closeout_gates all exit 0.",
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
        "id": "141.5",
        "owner": "fleet",
        "title": "Fail closeout when any of the five route or family rows in this milestone remain `no`, blank, stale, or unsupported by direct proof receipts.",
    }
    if closeout_complete:
        row["status"] = "complete"
        row["evidence"] = list(REGISTRY_EVIDENCE)
    return {"milestones": [{"id": 141, "work_tasks": [row]}]}


def _queue_item(*, closeout_complete: bool) -> dict:
    row = {
        "title": "Fail closeout when any of the five route or family rows in this milestone remain `no`, blank, stale, or unsupported by direct proof receipts.",
        "task": "Fail closeout when any of the five route or family rows in this milestone remain `no`, blank, stale, or unsupported by direct proof receipts.",
        "package_id": "next90-m141-fleet-fail-closeout-when-any-of-the-five-route-or-family-rows-in-this-milest",
        "milestone_id": 141,
        "work_task_id": "141.5",
        "frontier_id": 4147587006,
        "wave": "W22P",
        "repo": "fleet",
        "allowed_paths": ["scripts", "tests", ".codex-studio", "feedback"],
        "owned_surfaces": ["fail_closeout_when_any_of_the_five_route_or_family_rows:fleet"],
    }
    if closeout_complete:
        row["status"] = "complete"
        row["completion_action"] = "verify_closed_package_only"
        row["landed_commit"] = "unlanded"
        row["do_not_reopen_reason"] = (
            "M141 fleet import-route closeout gate is complete; future shards must verify the repo-local gate scripts, "
            "generated proof artifacts, and canonical queue/registry mirrors instead of reopening the translator, XML, "
            "Hero Lab, and adjacent import-route parity closeout slice."
        )
        row["proof"] = list(QUEUE_PROOF)
    return row


def _parity_rows(use_old_shape: bool) -> list[dict]:
    rows = [
        {
            "id": "source:translator_route",
            "label": "Translator route",
            "visual_parity": "yes",
            "behavioral_parity": "yes",
            "present_in_chummer5a": "yes",
            "reason": "Direct translator proof exists.",
            "evidence": [
                "/tmp/NEXT90_M141_IMPORT_ROUTE_RECEIPTS.md",
                "/tmp/VETERAN_TASK_TIME_EVIDENCE_GATE.generated.json",
                "/tmp/DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json",
            ],
        },
        {
            "id": "source:xml_amendment_editor_route",
            "label": "XML amendment editor route",
            "visual_parity": "yes",
            "behavioral_parity": "yes",
            "present_in_chummer5a": "yes",
            "reason": "Direct XML bridge proof exists.",
            "evidence": [
                "/tmp/NEXT90_M141_IMPORT_ROUTE_RECEIPTS.md",
                "/tmp/VETERAN_TASK_TIME_EVIDENCE_GATE.generated.json",
                "/tmp/DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json",
            ],
        },
        {
            "id": "source:hero_lab_importer_route",
            "label": "Hero Lab importer route",
            "visual_parity": "yes",
            "behavioral_parity": "yes",
            "present_in_chummer5a": "yes",
            "reason": "Direct import-oracle proof exists.",
            "evidence": [
                "/tmp/IMPORT_PARITY_CERTIFICATION.generated.json",
                "/tmp/VETERAN_TASK_TIME_EVIDENCE_GATE.generated.json",
                "/tmp/DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json",
            ],
        },
        {
            "id": "family:custom_data_xml_and_translator_bridge",
            "label": "Custom data/XML and translator bridge family",
            "visual_parity": "yes",
            "behavioral_parity": "yes",
            "present_in_chummer5a": "yes",
            "reason": "Family rows cite direct translator and XML proof.",
            "evidence": [
                "/tmp/NEXT90_M141_IMPORT_ROUTE_RECEIPTS.md",
                "/tmp/UI_FLAGSHIP_RELEASE_GATE.generated.json",
                "/tmp/DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json",
            ],
        },
        {
            "id": "family:legacy_and_adjacent_import_oracles",
            "label": "Legacy and adjacent import-oracle family",
            "visual_parity": "yes",
            "behavioral_parity": "yes",
            "present_in_chummer5a": "yes",
            "reason": "Family rows cite direct import-oracle proof.",
            "evidence": [
                "/tmp/IMPORT_PARITY_CERTIFICATION.generated.json",
                "/tmp/VETERAN_TASK_TIME_EVIDENCE_GATE.generated.json",
                "/tmp/DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json",
            ],
        },
    ]
    for row in rows:
        if use_old_shape:
            row["removable_without_workflow_degradation"] = "no"
        else:
            row["present_in_chummer6"] = "yes"
            row["removable_if_not_in_chummer5a"] = "no"
    return rows


def _fixture_tree(tmp_path: Path, *, use_old_shape: bool, closeout_complete: bool = True) -> dict[str, Path]:
    registry = tmp_path / "registry.yaml"
    fleet_queue = tmp_path / "fleet_queue.yaml"
    design_queue = tmp_path / "design_queue.yaml"
    guide = tmp_path / "guide.md"
    matrix = tmp_path / "matrix.yaml"
    policy = tmp_path / "policy.json"
    parity_audit = tmp_path / "parity_audit.json"
    visual_gate = tmp_path / "visual_gate.json"
    veteran_gate = tmp_path / "veteran_gate.json"
    ui_release = tmp_path / "ui_release.json"
    receipts_doc = tmp_path / "receipts.md"
    import_cert = tmp_path / "import_cert.json"
    engine_pack = tmp_path / "engine_pack.json"

    _write_yaml(registry, _registry(closeout_complete=closeout_complete))
    _write_yaml(fleet_queue, {"items": [_queue_item(closeout_complete=closeout_complete)]})
    _write_yaml(design_queue, {"items": [_queue_item(closeout_complete=closeout_complete)]})
    _write_text(
        guide,
        "## Wave 22P - close human-tested parity proof and desktop executable trust before successor breadth\n"
        "### 141. Direct parity proof for translator, XML amendment, Hero Lab, and adjacent import routes\n"
        "Exit: the translator, XML amendment editor, Hero Lab importer, custom-data/XML bridge, and adjacent import-oracle rows all flip to direct `yes/yes` parity with current screenshot-backed and runtime-backed receipts.\n",
    )
    _write_yaml(
        matrix,
        {
            "audit_required_fields": [
                "family_id",
                "surface_id",
                "dialog_id",
                "element_id",
                "element_label",
                "present_in_chummer5a",
                "present_in_chummer6",
                "visual_parity",
                "behavioral_parity",
                "removable_if_not_in_chummer5a",
                "reason",
            ],
            "field_rules": {
                "present_in_chummer5a": {"allowed_values": ["yes", "no"]},
                "present_in_chummer6": {"allowed_values": ["yes", "no"]},
                "visual_parity": {"allowed_values": ["yes", "no"]},
                "behavioral_parity": {"allowed_values": ["yes", "no"]},
                "removable_if_not_in_chummer5a": {"allowed_values": ["yes", "no"]},
            },
        },
    )
    _write_json(
        policy,
        {
            "auditRequiredFields": [
                "family_id",
                "surface_id",
                "dialog_id",
                "element_id",
                "element_label",
                "present_in_chummer5a",
                "present_in_chummer6",
                "visual_parity",
                "behavioral_parity",
                "removable_if_not_in_chummer5a",
                "reason",
            ],
            "allowedYesNoFields": [
                "present_in_chummer5a",
                "present_in_chummer6",
                "visual_parity",
                "behavioral_parity",
                "removable_if_not_in_chummer5a",
            ],
        },
    )
    rows = _parity_rows(use_old_shape)
    _write_json(parity_audit, {"generated_at": "2026-05-05T12:00:00Z", "rows": rows, "elements": rows})
    _write_json(
        visual_gate,
        {"generated_at": "2026-05-05T12:00:00Z", "status": "pass", "screenshots": ["38-translator-dialog-light.png", "39-xml-editor-dialog-light.png", "40-hero-lab-importer-dialog-light.png"]},
    )
    _write_json(
        veteran_gate,
        {
            "generated_at": "2026-05-05T12:00:00Z",
            "status": "pass",
            "taskTimeEvidence": {
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
            "requiredScreenshots": [
                "38-translator-dialog-light.png",
                "39-xml-editor-dialog-light.png",
                "40-hero-lab-importer-dialog-light.png",
            ],
        },
    )
    _write_json(
        ui_release,
        {
            "generated_at": "2026-05-05T12:00:00Z",
            "status": "pass",
            "proofs": {"translator_xml_custom_data": {"tests": ["ExecuteCommandAsync_translator_opens_dialog_with_master_index_lane_posture"]}},
        },
    )
    _write_text(
        receipts_doc,
        "customDataXmlBridgeDeterministicReceipt\ntranslatorDeterministicReceipt\nimportOracleDeterministicReceipt\n"
        "source:translator_route\nfamily:custom_data_xml_and_translator_bridge\nfamily:legacy_and_adjacent_import_oracles\n",
    )
    _write_json(
        import_cert,
        {
            "generated_at": "2026-05-05T12:00:00Z",
            "status": "passed",
            "coverage": {"sources_covered": 5, "sources_expected": 5, "coverage_percent": 100},
        },
    )
    _write_json(
        engine_pack,
        {
            "generated_at": "2026-05-05T12:00:00Z",
            "status": "pass",
            "required_oracle_suite_ids": ["amend_package"],
            "oracle_suites": [{"id": "amend_package"}],
        },
    )
    return {
        "registry": registry,
        "fleet_queue": fleet_queue,
        "design_queue": design_queue,
        "guide": guide,
        "matrix": matrix,
        "policy": policy,
        "parity_audit": parity_audit,
        "visual_gate": visual_gate,
        "veteran_gate": veteran_gate,
        "ui_release": ui_release,
        "receipts_doc": receipts_doc,
        "import_cert": import_cert,
        "engine_pack": engine_pack,
    }


class MaterializeNext90M141FleetImportRouteCloseoutGatesTest(unittest.TestCase):
    def test_materializer_accepts_list_root_queue_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path, use_old_shape=False)
            _write_yaml(fixture["fleet_queue"], [_queue_item(closeout_complete=True)])
            _write_yaml(fixture["design_queue"], [_queue_item(closeout_complete=True)])
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
                    "--parity-acceptance-matrix", str(fixture["matrix"]),
                    "--legacy-chrome-policy", str(fixture["policy"]),
                    "--parity-audit", str(fixture["parity_audit"]),
                    "--visual-familiarity-gate", str(fixture["visual_gate"]),
                    "--veteran-task-time-gate", str(fixture["veteran_gate"]),
                    "--ui-release-gate", str(fixture["ui_release"]),
                    "--import-receipts-doc", str(fixture["receipts_doc"]),
                    "--import-parity-certification", str(fixture["import_cert"]),
                    "--engine-proof-pack", str(fixture["engine_pack"]),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            payload = json.loads(artifact.read_text(encoding="utf-8"))
            assert payload["status"] == "pass"
            assert payload["package_closeout"]["ready"] is True

    def test_materializer_emits_passing_gate_when_rows_carry_direct_field_shape_and_proof_citations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path, use_old_shape=False)
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
                    "--parity-acceptance-matrix", str(fixture["matrix"]),
                    "--legacy-chrome-policy", str(fixture["policy"]),
                    "--parity-audit", str(fixture["parity_audit"]),
                    "--visual-familiarity-gate", str(fixture["visual_gate"]),
                    "--veteran-task-time-gate", str(fixture["veteran_gate"]),
                    "--ui-release-gate", str(fixture["ui_release"]),
                    "--import-receipts-doc", str(fixture["receipts_doc"]),
                    "--import-parity-certification", str(fixture["import_cert"]),
                    "--engine-proof-pack", str(fixture["engine_pack"]),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            payload = json.loads(artifact.read_text(encoding="utf-8"))
            assert payload["status"] == "pass"
            assert payload["monitor_summary"]["import_route_closeout_status"] == "pass"
            assert payload["package_closeout"]["ready"] is True

    def test_materializer_blocks_when_rows_still_use_the_old_field_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path, use_old_shape=True)
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
                    "--parity-acceptance-matrix", str(fixture["matrix"]),
                    "--legacy-chrome-policy", str(fixture["policy"]),
                    "--parity-audit", str(fixture["parity_audit"]),
                    "--visual-familiarity-gate", str(fixture["visual_gate"]),
                    "--veteran-task-time-gate", str(fixture["veteran_gate"]),
                    "--ui-release-gate", str(fixture["ui_release"]),
                    "--import-receipts-doc", str(fixture["receipts_doc"]),
                    "--import-parity-certification", str(fixture["import_cert"]),
                    "--engine-proof-pack", str(fixture["engine_pack"]),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            payload = json.loads(artifact.read_text(encoding="utf-8"))
            assert payload["status"] == "pass"
            assert payload["monitor_summary"]["import_route_closeout_status"] == "blocked"
            assert any(
                "present_in_chummer6 is missing or not `yes`" in item or "required `removable_if_not_in_chummer5a = no`" in item
                for item in payload["monitor_summary"]["runtime_blockers"]
            )

    def test_materializer_fails_when_closeout_metadata_is_not_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path, use_old_shape=False, closeout_complete=False)
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
                    "--parity-acceptance-matrix", str(fixture["matrix"]),
                    "--legacy-chrome-policy", str(fixture["policy"]),
                    "--parity-audit", str(fixture["parity_audit"]),
                    "--visual-familiarity-gate", str(fixture["visual_gate"]),
                    "--veteran-task-time-gate", str(fixture["veteran_gate"]),
                    "--ui-release-gate", str(fixture["ui_release"]),
                    "--import-receipts-doc", str(fixture["receipts_doc"]),
                    "--import-parity-certification", str(fixture["import_cert"]),
                    "--engine-proof-pack", str(fixture["engine_pack"]),
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
