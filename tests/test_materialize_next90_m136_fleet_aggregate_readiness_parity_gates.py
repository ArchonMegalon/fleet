from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


SCRIPT = Path("/docker/fleet/scripts/materialize_next90_m136_fleet_aggregate_readiness_parity_gates.py")

PACKAGE_ID = "next90-m136-fleet-fail-closed-on-aggregate-readiness-when-family-level-parity-proof-sub"
QUEUE_TITLE = (
    "Fail closed on aggregate readiness when family-level parity proof, sub-dialog screenshot packs, "
    "dialog-level element inventories, or continuity journey receipts are stale or missing."
)
REQUIRED_MATRIX_FAMILY_IDS = [
    "translator_xml_bridge",
    "dense_builder_and_career",
    "dice_initiative_and_table_utilities",
    "identity_contacts_lifestyles_history",
    "legacy_and_adjacent_import_oracles",
    "sheet_export_print_viewer_exchange",
    "sr6_supplements_designers_house_rules",
]
MATRIX_TO_AUDIT_FAMILY_IDS = {
    "translator_xml_bridge": "family:custom_data_xml_and_translator_bridge",
    "dense_builder_and_career": "family:dense_builder_and_career_workflows",
    "dice_initiative_and_table_utilities": "family:dice_initiative_and_table_utilities",
    "identity_contacts_lifestyles_history": "family:identity_contacts_lifestyles_history",
    "legacy_and_adjacent_import_oracles": "family:legacy_and_adjacent_import_oracles",
    "sheet_export_print_viewer_exchange": "family:sheet_export_print_viewer_and_exchange",
    "sr6_supplements_designers_house_rules": "family:sr6_supplements_designers_and_house_rules",
}


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _write_split_queue_yaml(path: Path, item: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        yaml.safe_dump([item], sort_keys=False)
        + "mode: append\n"
        + "items:\n"
        + yaml.safe_dump([item], sort_keys=False)
    )
    path.write_text(payload, encoding="utf-8")


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
                "owners": [
                    "chummer6-core",
                    "chummer6-hub",
                    "chummer6-hub-registry",
                    "chummer6-ui",
                    "chummer6-ui-kit",
                    "chummer6-mobile",
                    "executive-assistant",
                    "fleet",
                    "chummer6-design",
                ],
                "dependencies": [113, 114, 123, 124, 133, 134, 135, 141, 142, 143, 144],
                "work_tasks": [
                    {
                        "id": "136.6",
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
        "work_task_id": "136.6",
        "frontier_id": 2277811964,
        "milestone_id": 136,
        "status": "not_started",
        "wave": "W23",
        "repo": "fleet",
        "allowed_paths": ["scripts", "tests", ".codex-studio", "feedback"],
        "owned_surfaces": ["fail_closed_on_aggregate_readiness_when_family_level_par:fleet"],
    }


def _guide() -> str:
    return """## Wave 23 - close calm-under-pressure payoff and veteran continuity

### 136. Calm-under-pressure payoff, veteran-depth parity, and campaign continuity closure

Exit: the product proves the calm-under-pressure loop, reaches zero `no` rows in the Chummer5A human-parity matrix, closes the hard veteran parity families, closes split-brain release truth, and publishes dependable companion continuity rather than broad structural green.
"""


def _parity_matrix() -> dict:
    return {
        "summary": None,
        "families": [
            {
                "id": family_id,
                "release_blocking": True,
                "required_screenshots": [f"{family_id}_shot_a", f"{family_id}_shot_b"],
                "surfaces": [
                    {
                        "id": f"{family_id}_surface",
                        "must_remain_first_class": ["primary_surface", "secondary_surface"],
                    }
                ],
            }
            for family_id in REQUIRED_MATRIX_FAMILY_IDS
        ],
    }


def _parity_audit(*, generated_at: str) -> dict:
    return {
        "generated_at": generated_at,
        "summary": {
            "total_elements": len(REQUIRED_MATRIX_FAMILY_IDS),
            "visual_no_count": 0,
            "behavioral_no_count": 0,
        },
        "elements": [
            {
                "id": audit_id,
                "label": audit_id,
                "visual_parity": "yes",
                "behavioral_parity": "yes",
            }
            for audit_id in MATRIX_TO_AUDIT_FAMILY_IDS.values()
        ],
    }


def _ui_direct_workflow_proof(*, generated_at: str, dense_ready: bool = True) -> dict:
    return {
        "generatedAt": generated_at,
        "status": "pass" if dense_ready else "fail",
        "evidence": {
            "familyChecks": {
                "family:dense_builder_and_career_workflows": {
                    "row_present": dense_ready,
                    "visual_parity_yes": dense_ready,
                    "behavioral_parity_yes": dense_ready,
                    "required_suffixes_present": dense_ready,
                    "disallowed_external_receipts_clear": dense_ready,
                }
            }
        },
    }


def _screenshot_gate(*, generated_at: str, status: str = "pass") -> dict:
    return {
        "generated_at": generated_at,
        "status": status,
        "summary": "fixture",
    }


def _visual_gate(*, generated_at: str, status: str = "pass") -> dict:
    return {
        "generated_at": generated_at,
        "status": status,
        "summary": "fixture",
    }


def _continuity(*, generated_at: str, status: str = "pass") -> dict:
    return {
        "generated_at": generated_at,
        "status": status,
        "summary": {"coverage_window_days": 120, "required_window_days": 120},
    }


def _journey_gates(*, generated_at: str, overall_state: str = "ready") -> dict:
    return {
        "generated_at": generated_at,
        "summary": {"overall_state": overall_state},
        "journeys": [],
    }


def _flagship_readiness(*, generated_at: str, status: str = "pass") -> dict:
    return {"generated_at": generated_at, "status": status}


def _fixture_tree(
    tmp_path: Path,
    *,
    include_fleet_queue_row: bool,
    parity_audit_generated_at: str,
    screenshot_review_generated_at: str,
    visual_gate_generated_at: str,
    visual_gate_status: str,
    continuity_status: str,
    continuity_generated_at: str,
    journey_generated_at: str,
    flagship_status: str,
) -> dict[str, Path]:
    registry_path = tmp_path / "registry.yaml"
    fleet_queue_path = tmp_path / "fleet_queue.yaml"
    design_queue_path = tmp_path / "design_queue.yaml"
    guide_path = tmp_path / "NEXT90_GUIDE.md"
    parity_matrix_path = tmp_path / "PARITY_MATRIX.yaml"
    flagship_path = tmp_path / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    continuity_path = tmp_path / "CAMPAIGN_OS_CONTINUITY_LIVENESS.generated.json"
    journey_path = tmp_path / "JOURNEY_GATES.generated.json"
    parity_audit_path = tmp_path / "CHUMMER5A_UI_ELEMENT_PARITY_AUDIT.generated.json"
    screenshot_path = tmp_path / "CHUMMER5A_SCREENSHOT_REVIEW_GATE.generated.json"
    visual_path = tmp_path / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    ui_direct_workflow_proof_path = tmp_path / "NEXT90_M142_UI_DIRECT_WORKFLOW_PROOF.generated.json"

    _write_yaml(registry_path, _registry())
    _write_yaml(
        fleet_queue_path,
        {"items": [_design_queue_item()] if include_fleet_queue_row else []},
    )
    _write_yaml(design_queue_path, {"items": [_design_queue_item()]})
    _write_text(guide_path, _guide())
    _write_yaml(parity_matrix_path, _parity_matrix())
    _write_json(flagship_path, _flagship_readiness(generated_at="2026-05-05T12:00:00Z", status=flagship_status))
    _write_json(
        continuity_path,
        _continuity(generated_at=continuity_generated_at, status=continuity_status),
    )
    _write_json(journey_path, _journey_gates(generated_at=journey_generated_at))
    _write_json(parity_audit_path, _parity_audit(generated_at=parity_audit_generated_at))
    _write_json(screenshot_path, _screenshot_gate(generated_at=screenshot_review_generated_at))
    _write_json(visual_path, _visual_gate(generated_at=visual_gate_generated_at, status=visual_gate_status))
    _write_json(
        ui_direct_workflow_proof_path,
        _ui_direct_workflow_proof(generated_at=parity_audit_generated_at),
    )
    return {
        "registry": registry_path,
        "fleet_queue": fleet_queue_path,
        "design_queue": design_queue_path,
        "guide": guide_path,
        "parity_matrix": parity_matrix_path,
        "flagship": flagship_path,
        "continuity": continuity_path,
        "journey": journey_path,
        "parity_audit": parity_audit_path,
        "screenshot": screenshot_path,
        "visual": visual_path,
        "ui_direct_workflow_proof": ui_direct_workflow_proof_path,
    }


class MaterializeNext90M136FleetAggregateReadinessParityGatesTest(unittest.TestCase):
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
                "--parity-matrix",
                str(fixture["parity_matrix"]),
                "--flagship-product-readiness",
                str(fixture["flagship"]),
                "--campaign-continuity-liveness",
                str(fixture["continuity"]),
                "--journey-gates",
                str(fixture["journey"]),
                "--parity-audit",
                str(fixture["parity_audit"]),
                "--ui-direct-workflow-proof",
                str(fixture["ui_direct_workflow_proof"]),
                "--screenshot-review-gate",
                str(fixture["screenshot"]),
                "--visual-familiarity-gate",
                str(fixture["visual"]),
            ],
            check=True,
        )
        return json.loads(artifact_path.read_text(encoding="utf-8"))

    def test_runtime_blockers_fail_open_the_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(
                tmp_path,
                include_fleet_queue_row=False,
                parity_audit_generated_at="2026-05-02T08:00:00Z",
                screenshot_review_generated_at="2026-05-05T12:00:00Z",
                visual_gate_generated_at="2026-05-05T12:00:00Z",
                visual_gate_status="fail",
                continuity_status="fail",
                continuity_generated_at="2026-05-05T12:00:00Z",
                journey_generated_at="2026-05-05T12:00:00Z",
                flagship_status="pass",
            )
            artifact = tmp_path / "artifact.json"
            payload = self._run_materializer(fixture, artifact)

        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["monitor_summary"]["aggregate_readiness_status"], "blocked")
        self.assertTrue(
            any("Fleet queue mirror row is still missing" in row for row in payload["package_closeout"]["warnings"])
        )
        self.assertTrue(
            any("Desktop visual familiarity gate is not passing" in row for row in payload["monitor_summary"]["runtime_blockers"])
        )
        self.assertTrue(
            any("Flagship product readiness is still green" in row for row in payload["monitor_summary"]["runtime_blockers"])
        )

    def test_missing_dialog_level_inventory_blocks_the_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(
                tmp_path,
                include_fleet_queue_row=True,
                parity_audit_generated_at="2026-05-05T12:00:00Z",
                screenshot_review_generated_at="2026-05-05T12:00:00Z",
                visual_gate_generated_at="2026-05-05T12:00:00Z",
                visual_gate_status="pass",
                continuity_status="pass",
                continuity_generated_at="2026-05-05T12:00:00Z",
                journey_generated_at="2026-05-05T12:00:00Z",
                flagship_status="fail",
            )
            matrix = yaml.safe_load(fixture["parity_matrix"].read_text(encoding="utf-8"))
            matrix["families"][0]["surfaces"] = []
            _write_yaml(fixture["parity_matrix"], matrix)
            artifact = tmp_path / "artifact.json"
            payload = self._run_materializer(fixture, artifact)

        self.assertEqual(payload["status"], "blocked")
        self.assertTrue(any("dialog-level surfaces" in row for row in payload["package_closeout"]["blockers"]))

    def test_green_runtime_can_pass_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(
                tmp_path,
                include_fleet_queue_row=True,
                parity_audit_generated_at="2026-05-05T12:00:00Z",
                screenshot_review_generated_at="2026-05-05T12:00:00Z",
                visual_gate_generated_at="2026-05-05T12:00:00Z",
                visual_gate_status="pass",
                continuity_status="pass",
                continuity_generated_at="2026-05-05T12:00:00Z",
                journey_generated_at="2026-05-05T12:00:00Z",
                flagship_status="fail",
            )
            artifact = tmp_path / "artifact.json"
            payload = self._run_materializer(fixture, artifact)

        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["monitor_summary"]["aggregate_readiness_status"], "pass")
        self.assertEqual(payload["monitor_summary"]["receipt_runtime_blocker_count"], 0)

    def test_split_queue_yaml_fallback_preserves_queue_alignment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(
                tmp_path,
                include_fleet_queue_row=True,
                parity_audit_generated_at="2026-05-05T12:00:00Z",
                screenshot_review_generated_at="2026-05-05T12:00:00Z",
                visual_gate_generated_at="2026-05-05T12:00:00Z",
                visual_gate_status="pass",
                continuity_status="pass",
                continuity_generated_at="2026-05-05T12:00:00Z",
                journey_generated_at="2026-05-05T12:00:00Z",
                flagship_status="fail",
            )
            queue_item = _design_queue_item()
            _write_split_queue_yaml(fixture["fleet_queue"], queue_item)
            _write_split_queue_yaml(fixture["design_queue"], queue_item)
            artifact = tmp_path / "artifact.json"
            payload = self._run_materializer(fixture, artifact)

        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["canonical_monitors"]["queue_alignment"]["state"], "pass")
        self.assertEqual(payload["package_closeout"]["state"], "pass")

    def test_missing_generated_at_uses_file_mtime_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(
                tmp_path,
                include_fleet_queue_row=True,
                parity_audit_generated_at="2026-05-05T12:00:00Z",
                screenshot_review_generated_at="2026-05-05T12:00:00Z",
                visual_gate_generated_at="2026-05-05T12:00:00Z",
                visual_gate_status="pass",
                continuity_status="pass",
                continuity_generated_at="2026-05-05T12:00:00Z",
                journey_generated_at="2026-05-05T12:00:00Z",
                flagship_status="fail",
            )
            screenshot_payload = json.loads(fixture["screenshot"].read_text(encoding="utf-8"))
            screenshot_payload.pop("generated_at", None)
            _write_json(fixture["screenshot"], screenshot_payload)
            visual_payload = json.loads(fixture["visual"].read_text(encoding="utf-8"))
            visual_payload.pop("generated_at", None)
            _write_json(fixture["visual"], visual_payload)
            recent_timestamp = 1777982400  # 2026-05-05T12:00:00Z
            os.utime(fixture["screenshot"], (recent_timestamp, recent_timestamp))
            os.utime(fixture["visual"], (recent_timestamp, recent_timestamp))

            artifact = tmp_path / "artifact.json"
            payload = self._run_materializer(fixture, artifact)

        self.assertEqual(payload["monitor_summary"]["aggregate_readiness_status"], "pass")
        self.assertFalse(
            any("generated_at is missing or invalid" in row for row in payload["monitor_summary"]["runtime_blockers"])
        )
        self.assertEqual(
            payload["source_inputs"]["screenshot_review_gate"]["generated_at"],
            "2026-05-05T12:00:00Z",
        )

    def test_ui_direct_workflow_proof_can_override_stale_dense_family_row(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(
                tmp_path,
                include_fleet_queue_row=True,
                parity_audit_generated_at="2026-05-05T12:00:00Z",
                screenshot_review_generated_at="2026-05-05T12:00:00Z",
                visual_gate_generated_at="2026-05-05T12:00:00Z",
                visual_gate_status="pass",
                continuity_status="pass",
                continuity_generated_at="2026-05-05T12:00:00Z",
                journey_generated_at="2026-05-05T12:00:00Z",
                flagship_status="fail",
            )
            parity_audit = json.loads(fixture["parity_audit"].read_text(encoding="utf-8"))
            parity_audit["summary"]["visual_no_count"] = 1
            parity_audit["summary"]["behavioral_no_count"] = 1
            dense_row = next(row for row in parity_audit["elements"] if row["id"] == "family:dense_builder_and_career_workflows")
            dense_row["visual_parity"] = "no"
            dense_row["behavioral_parity"] = "no"
            fixture["parity_audit"].write_text(json.dumps(parity_audit, indent=2) + "\n", encoding="utf-8")

            artifact = tmp_path / "artifact.json"
            payload = self._run_materializer(fixture, artifact)

        self.assertEqual(payload["monitor_summary"]["aggregate_readiness_status"], "pass")
        self.assertEqual(
            payload["runtime_monitors"]["parity_family_proof"]["overridden_family_proofs"],
            ["dense_builder_and_career"],
        )
        self.assertEqual(payload["runtime_monitors"]["parity_family_proof"]["effective_visual_no_count"], 0)
        self.assertEqual(payload["runtime_monitors"]["parity_family_proof"]["effective_behavioral_no_count"], 0)


if __name__ == "__main__":
    unittest.main()
