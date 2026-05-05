from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


SCRIPT = Path("/docker/fleet/scripts/materialize_next90_m136_fleet_parity_matrix_gate_binding.py")

PACKAGE_ID = "next90-m136-fleet-bind-the-machine-readable-human-parity-matrix-into-audit-gate-consumpt"
QUEUE_TITLE = "Bind the machine-readable human parity matrix into audit/gate consumption so hard families cannot close on prose-only proof."
RELEASE_BLOCKING_FAMILIES = [
    ("translator_xml_bridge", "family:custom_data_xml_and_translator_bridge", "136.21"),
    ("dense_builder_and_career", "family:dense_builder_and_career_workflows", "136.22"),
    ("dice_initiative_and_table_utilities", "family:dice_initiative_and_table_utilities", "136.23"),
    ("identity_contacts_lifestyles_history", "family:identity_contacts_lifestyles_history", "136.24"),
    ("legacy_and_adjacent_import_oracles", "family:legacy_and_adjacent_import_oracles", "136.25"),
    ("sheet_export_print_viewer_exchange", "family:sheet_export_print_viewer_and_exchange", "136.26"),
    ("sr6_supplements_designers_house_rules", "family:sr6_supplements_designers_and_house_rules", "136.27"),
]


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _registry() -> dict:
    return {
        "milestones": [
            {
                "id": 136,
                "title": "Calm-under-pressure payoff, veteran-depth parity, and campaign continuity closure",
                "wave": "W23",
                "status": "not_started",
                "work_tasks": [
                    {
                        "id": "136.9",
                        "owner": "fleet",
                        "title": QUEUE_TITLE,
                        "status": "not_started",
                    }
                ],
            }
        ]
    }


def _design_queue_item() -> dict:
    return {
        "title": QUEUE_TITLE,
        "task": QUEUE_TITLE,
        "package_id": PACKAGE_ID,
        "work_task_id": "136.9",
        "frontier_id": 4491585022,
        "milestone_id": 136,
        "status": "not_started",
        "wave": "W23",
        "repo": "fleet",
        "allowed_paths": ["scripts", "tests", ".codex-studio", "feedback"],
        "owned_surfaces": ["bind_the_machine_readable_human_parity_matrix_into_audit:fleet"],
    }


def _guide() -> str:
    return """## Wave 23 - close calm-under-pressure payoff and veteran continuity

### 136. Calm-under-pressure payoff, veteran-depth parity, and campaign continuity closure
"""


def _parity_spec() -> str:
    return """The machine-readable companion for this canon is `CHUMMER5A_HUMAN_PARITY_ACCEPTANCE_MATRIX.yaml`.
No gate may collapse these families into a generic \"desktop parity\" or \"flagship readiness\" pass.
The gate stack should consume `CHUMMER5A_HUMAN_PARITY_ACCEPTANCE_MATRIX.yaml` for the field list, family ids, surface ids, required screenshots, and milestone mapping instead of re-encoding that shape ad hoc.
"""


def _flagship_product_bar() -> str:
    return """For the remaining hard parity families, familiarity is judged by `CHUMMER5A_HUMAN_PARITY_ACCEPTANCE_SPEC.md` and `CHUMMER5A_HUMAN_PARITY_ACCEPTANCE_MATRIX.yaml`, not by aggregate desktop readiness alone.
"""


def _parity_matrix() -> dict:
    return {
        "families": [
            {
                "id": family_id,
                "release_blocking": True,
                "milestone_task_id": milestone_task_id,
                "required_screenshots": [f"{family_id}_shot_a", f"{family_id}_shot_b"],
                "surfaces": [
                    {
                        "id": f"{family_id}_surface",
                        "must_remain_first_class": ["primary_control", "secondary_control"],
                    }
                ],
            }
            for family_id, _, milestone_task_id in RELEASE_BLOCKING_FAMILIES
        ]
    }


def _flagship_readiness_planes(*, include_matrix: bool = True) -> dict:
    source_artifacts = ["FLAGSHIP_PARITY_REGISTRY.yaml"]
    if include_matrix:
        source_artifacts.insert(0, "CHUMMER5A_HUMAN_PARITY_ACCEPTANCE_MATRIX.yaml")
    return {
        "planes": [
            {
                "id": "veteran_deep_workflow_ready",
                "source_artifacts": source_artifacts,
                "proving_artifacts": [
                    "/docker/chummercomplete/chummer-presentation/.codex-studio/published/CHUMMER5A_UI_ELEMENT_PARITY_AUDIT.generated.json",
                    "/docker/chummercomplete/chummer-presentation/.codex-studio/published/DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json",
                ],
            }
        ]
    }


def _parity_audit(*, prose_only_family: str | None = None) -> dict:
    rows = []
    for family_id, audit_id, _ in RELEASE_BLOCKING_FAMILIES:
        evidence = [
            "/tmp/CHUMMER5A_SCREENSHOT_REVIEW_GATE.generated.json",
            "/tmp/DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json",
        ]
        if family_id == prose_only_family:
            evidence = ["/tmp/notes.md"]
        rows.append(
            {
                "id": audit_id,
                "label": audit_id,
                "visual_parity": "yes",
                "behavioral_parity": "yes",
                "present_in_chummer5a": "yes",
                "reason": "fixture",
                "evidence": evidence,
            }
        )
    return {"generated_at": "2026-05-05T12:00:00Z", "elements": rows}


def _m136_aggregate_gate() -> dict:
    family_ids = [family_id for family_id, _, _ in RELEASE_BLOCKING_FAMILIES]
    return {
        "contract_name": "fleet.next90_m136_aggregate_readiness_parity_gates",
        "generated_at": "2026-05-05T12:00:00Z",
        "status": "pass",
        "canonical_monitors": {
            "parity_matrix": {
                "required_family_ids": family_ids,
                "required_screenshot_ids": sorted(
                    {f"{family_id}_shot_a" for family_id in family_ids} | {f"{family_id}_shot_b" for family_id in family_ids}
                ),
                "milestone_task_ids": [task_id for _, _, task_id in RELEASE_BLOCKING_FAMILIES],
            }
        },
        "runtime_monitors": {
            "parity_family_proof": {
                "required_family_ids": family_ids,
            }
        },
        "monitor_summary": {
            "aggregate_readiness_status": "blocked",
            "required_family_count": len(family_ids),
        },
    }


def _flagship_product_readiness(*, status: str = "pass") -> dict:
    return {"generated_at": "2026-05-05T12:00:00Z", "status": status}


def _flagship_script_text() -> str:
    return """def _m136_aggregate_readiness_gate_audit(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {}
"m136_aggregate_readiness_gate_ready":
"M136 aggregate-readiness parity gate is not ready."
"""


def _fixture_tree(
    tmp_path: Path,
    *,
    include_fleet_queue_row: bool,
    include_matrix_in_planes: bool,
    prose_only_family: str | None,
    flagship_status: str,
) -> dict[str, Path]:
    registry_path = tmp_path / "registry.yaml"
    fleet_queue_path = tmp_path / "fleet_queue.yaml"
    design_queue_path = tmp_path / "design_queue.yaml"
    guide_path = tmp_path / "NEXT90_GUIDE.md"
    parity_spec_path = tmp_path / "PARITY_SPEC.md"
    parity_matrix_path = tmp_path / "PARITY_MATRIX.yaml"
    planes_path = tmp_path / "FLAGSHIP_READINESS_PLANES.yaml"
    bar_path = tmp_path / "FLAGSHIP_PRODUCT_BAR.md"
    parity_audit_path = tmp_path / "PARITY_AUDIT.generated.json"
    m136_gate_path = tmp_path / "M136_GATE.generated.json"
    flagship_path = tmp_path / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    flagship_script_path = tmp_path / "materialize_flagship_product_readiness.py"

    _write_yaml(registry_path, _registry())
    _write_yaml(fleet_queue_path, {"items": [_design_queue_item()] if include_fleet_queue_row else []})
    _write_yaml(design_queue_path, {"items": [_design_queue_item()]})
    _write_text(guide_path, _guide())
    _write_text(parity_spec_path, _parity_spec())
    _write_yaml(parity_matrix_path, _parity_matrix())
    _write_yaml(planes_path, _flagship_readiness_planes(include_matrix=include_matrix_in_planes))
    _write_text(bar_path, _flagship_product_bar())
    _write_json(parity_audit_path, _parity_audit(prose_only_family=prose_only_family))
    _write_json(m136_gate_path, _m136_aggregate_gate())
    _write_json(flagship_path, _flagship_product_readiness(status=flagship_status))
    _write_text(flagship_script_path, _flagship_script_text())
    return {
        "registry": registry_path,
        "fleet_queue": fleet_queue_path,
        "design_queue": design_queue_path,
        "guide": guide_path,
        "parity_spec": parity_spec_path,
        "parity_matrix": parity_matrix_path,
        "planes": planes_path,
        "bar": bar_path,
        "parity_audit": parity_audit_path,
        "m136_gate": m136_gate_path,
        "flagship": flagship_path,
        "flagship_script": flagship_script_path,
    }


class MaterializeNext90M136FleetParityMatrixGateBindingTest(unittest.TestCase):
    def _run_materializer(self, fixture: dict[str, Path], artifact_path: Path) -> dict:
        markdown_path = artifact_path.with_suffix(".md")
        subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--output",
                str(artifact_path),
                "--markdown-output",
                str(markdown_path),
                "--successor-registry",
                str(fixture["registry"]),
                "--fleet-queue-staging",
                str(fixture["fleet_queue"]),
                "--design-queue-staging",
                str(fixture["design_queue"]),
                "--next90-guide",
                str(fixture["guide"]),
                "--parity-spec",
                str(fixture["parity_spec"]),
                "--parity-matrix",
                str(fixture["parity_matrix"]),
                "--flagship-readiness-planes",
                str(fixture["planes"]),
                "--flagship-product-bar",
                str(fixture["bar"]),
                "--parity-audit",
                str(fixture["parity_audit"]),
                "--m136-aggregate-gate",
                str(fixture["m136_gate"]),
                "--flagship-product-readiness",
                str(fixture["flagship"]),
                "--flagship-readiness-script",
                str(fixture["flagship_script"]),
            ],
            check=True,
        )
        return json.loads(artifact_path.read_text(encoding="utf-8"))

    def test_runtime_blockers_do_not_block_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(
                tmp_path,
                include_fleet_queue_row=False,
                include_matrix_in_planes=True,
                prose_only_family="translator_xml_bridge",
                flagship_status="pass",
            )
            artifact = tmp_path / "artifact.json"
            payload = self._run_materializer(fixture, artifact)

        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["monitor_summary"]["matrix_binding_status"], "blocked")
        self.assertTrue(
            any("prose-only evidence" in row for row in payload["monitor_summary"]["runtime_blockers"])
        )
        self.assertTrue(
            any("Published FLAGSHIP_PRODUCT_READINESS still reports pass" in row for row in payload["monitor_summary"]["runtime_blockers"])
        )
        self.assertTrue(
            any("Fleet queue mirror row is still missing" in row for row in payload["package_closeout"]["warnings"])
        )

    def test_missing_planes_matrix_binding_blocks_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(
                tmp_path,
                include_fleet_queue_row=True,
                include_matrix_in_planes=False,
                prose_only_family=None,
                flagship_status="fail",
            )
            artifact = tmp_path / "artifact.json"
            payload = self._run_materializer(fixture, artifact)

        self.assertEqual(payload["status"], "blocked")
        self.assertTrue(any("FLAGSHIP_READINESS_PLANES" in row for row in payload["package_closeout"]["blockers"]))


if __name__ == "__main__":
    unittest.main()
