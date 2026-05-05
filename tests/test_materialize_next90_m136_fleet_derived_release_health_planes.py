from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


SCRIPT = Path("/docker/fleet/scripts/materialize_next90_m136_fleet_derived_release_health_planes.py")

PACKAGE_ID = "next90-m136-fleet-publish-derived-release-health-planes-from-live-proof-so-structural-gr"
QUEUE_TITLE = (
    "Publish derived release-health planes from live proof so structural green cannot masquerade as SR5 veteran, "
    "durability, explainability, or public-shelf readiness."
)


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _registry() -> dict:
    return {
        "milestones": [
            {
                "id": 136,
                "dependencies": [113, 114, 123, 124, 133, 134, 135, 141, 142, 143, 144],
                "work_tasks": [
                    {
                        "id": "136.11",
                        "owner": "fleet",
                        "title": QUEUE_TITLE,
                    }
                ],
            }
        ]
    }


def _queue_item() -> dict:
    return {
        "title": QUEUE_TITLE,
        "task": QUEUE_TITLE,
        "package_id": PACKAGE_ID,
        "work_task_id": "136.11",
        "frontier_id": 8422537713,
        "milestone_id": 136,
        "status": "not_started",
        "wave": "W23",
        "repo": "fleet",
        "allowed_paths": ["scripts", "tests", ".codex-studio", "feedback"],
        "owned_surfaces": ["publish_derived_release_health_planes_from_live_proof_so:fleet"],
    }


def _guide() -> str:
    return """## Wave 23 - close calm-under-pressure payoff and veteran continuity

### 136. Calm-under-pressure payoff, veteran-depth parity, and campaign continuity closure
"""


def _bar() -> str:
    return """### 2a. Trust, durability, and explainability outrank cosmetic similarity
Those planes are machine-tracked in `FLAGSHIP_READINESS_PLANES.yaml`.
"""


def _planes() -> dict:
    return {
        "purpose": "Machine-readable release-health planes that separate structural completion from flagship replacement truth.",
        "status_values": ["missing", "warning", "ready"],
        "policy": {
            "structural_green_is_not_flagship_green": [
                "Empty milestone registries, green repo tests, or broad parity `covered` language do not imply flagship replacement readiness.",
                "Every release-health plane must name an owner repo, source artifact, proving artifact, and concrete fail condition.",
            ]
        },
        "planes": [
            {
                "id": "structural_ready",
                "owner_repos": ["fleet"],
                "source_artifacts": ["STATUS_PLANE.generated.yaml"],
                "proving_artifacts": ["/docker/fleet/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json"],
                "fail_when": ["Structural route proof drifts from governed control-loop truth"],
            },
            {
                "id": "flagship_ready",
                "owner_repos": ["fleet", "chummer6-design"],
                "source_artifacts": ["FLAGSHIP_RELEASE_ACCEPTANCE.yaml"],
                "proving_artifacts": ["/docker/fleet/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json"],
                "fail_when": [
                    "Any release-health plane below `ready`",
                    "Any in-scope flagship parity family below `gold_ready`",
                ],
            },
            {
                "id": "sr5_veteran_ready",
                "owner_repos": ["fleet", "chummer6-ui"],
                "source_artifacts": ["VETERAN_FIRST_MINUTE_GATE.yaml"],
                "proving_artifacts": [
                    "/docker/chummercomplete/chummer-presentation/.codex-studio/published/DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json",
                    "/docker/fleet/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json",
                ],
                "fail_when": [
                    "A veteran cannot orient in the first minute without browser ritual or dashboard detour",
                    "Dialog-level parity evidence stays stale or incomplete for release-blocking SR5 families",
                ],
            },
            {
                "id": "veteran_deep_workflow_ready",
                "owner_repos": ["fleet", "chummer6-ui"],
                "source_artifacts": ["CHUMMER5A_HUMAN_PARITY_ACCEPTANCE_MATRIX.yaml"],
                "proving_artifacts": [
                    "/docker/chummercomplete/chummer-presentation/.codex-studio/published/DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json",
                    "/docker/chummercomplete/chummer-presentation/.codex-studio/published/CHUMMER5A_UI_ELEMENT_PARITY_AUDIT.generated.json",
                ],
                "fail_when": [
                    "Dense builder, import, continuity, utility, or export families remain below `veteran_approved`",
                    "Workflow execution proof leaves unresolved flagship-family receipts",
                ],
            },
            {
                "id": "primary_route_ready",
                "owner_repos": ["fleet"],
                "source_artifacts": ["PRIMARY_ROUTE_REGISTRY.yaml"],
                "proving_artifacts": ["/docker/fleet/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json"],
                "fail_when": ["Route truth drifts"],
            },
            {
                "id": "public_shelf_ready",
                "owner_repos": ["fleet", "chummer6-hub"],
                "source_artifacts": ["PUBLIC_RELEASE_EXPERIENCE.yaml"],
                "proving_artifacts": [
                    "/docker/chummercomplete/chummer-presentation/Docker/Downloads/RELEASE_CHANNEL.generated.json",
                    "/docker/fleet/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json",
                ],
                "fail_when": [
                    "Public shelf, route posture, and promoted tuples disagree",
                    "The recommended public path is thinner or riskier than the flagship desktop promise",
                ],
            },
            {
                "id": "data_durability_ready",
                "owner_repos": ["fleet", "chummer6-core"],
                "source_artifacts": ["CONFIDENCE_READINESS_AND_CONTINUITY_GUIDE.md"],
                "proving_artifacts": [
                    "/docker/chummercomplete/chummer6-core/.codex-studio/published/ENGINE_PROOF_PACK.generated.json",
                    "/docker/fleet/.codex-studio/published/JOURNEY_GATES.generated.json",
                ],
                "fail_when": [
                    "Character, campaign, import, restore, or export flows can lose governed truth across update, rollback, or migration"
                ],
            },
            {
                "id": "rules_explainability_ready",
                "owner_repos": ["fleet", "chummer6-core"],
                "source_artifacts": ["EXPLAIN_EVERY_VALUE_AND_GROUNDED_FOLLOW_UP.md"],
                "proving_artifacts": [
                    "/docker/chummercomplete/chummer6-core/.codex-studio/published/ENGINE_PROOF_PACK.generated.json",
                    "/docker/fleet/.codex-studio/published/JOURNEY_GATES.generated.json",
                ],
                "fail_when": [
                    "Important computed values cannot be explained where users ask why",
                    "Explain coverage-registry, source-anchor class, or bounded follow-up release-gate truth drifts from Fleet closeout evidence",
                    "Explain/build journeys remain blocked or implicit",
                ],
            },
        ],
    }


def _flagship_payload(*, data_durability_effective: str = "ready", flagship_ready: str = "ready") -> dict:
    return {
        "generated_at": "2026-05-05T15:30:00Z",
        "coverage": {"rules_engine_and_import": "ready"},
        "coverage_details": {
            "rules_engine_and_import": {
                "evidence": {
                    "build_explain_publish": "ready",
                    "build_explain_publish_effective": "ready",
                    "build_explain_publish_local_blocking_reason_count": 0,
                    "build_explain_publish_external_blocking_reason_count": 0,
                    "build_explain_publish_rules_scope_blocking_reason_count": 0,
                }
            }
        },
        "readiness_planes": {
            "structural_ready": {
                "status": "ready",
                "summary": "Structural delivery, journey, and control-loop truth are coherent.",
                "reasons": [],
                "evidence": {
                    "dispatchable_truth_ready": True,
                    "journey_effective_overall_state": "ready",
                    "journey_overall_desktop_scoped_blocked": False,
                    "journey_local_blocker_autofix_routing_ready": True,
                    "supervisor_recent_enough": True,
                    "runtime_healing_alert_state": "healthy",
                },
            },
            "flagship_ready": {
                "status": flagship_ready,
                "summary": "Flagship replacement truth is fully green.",
                "reasons": [] if flagship_ready == "ready" else ["Data-durability readiness plane is not ready."],
                "evidence": {
                    "registry_present": True,
                    "families_below_gold_ready": [],
                    "coverage_gap_keys": [],
                    "parity_lab_ready": True,
                    "m136_aggregate_readiness_gate_ready": True,
                    "structural_ready": True,
                    "veteran_ready": True,
                    "veteran_deep_workflow_ready": True,
                    "public_shelf_ready": True,
                    "data_durability_ready": data_durability_effective == "ready",
                    "rules_explainability_ready": True,
                },
            },
            "sr5_veteran_ready": {
                "status": "ready",
                "summary": "SR5 veteran orientation and familiarity proof is current for the promoted desktop route.",
                "reasons": [],
                "evidence": {
                    "registry_present": True,
                    "required_landmark_count": 5,
                    "task_count": 2,
                    "visual_gate_ready": True,
                    "parity_lab_ready": True,
                    "parity_lab_capture_pack_present": True,
                    "parity_lab_veteran_compare_pack_present": True,
                    "parity_lab_family_target_count": 7,
                    "parity_lab_invalid_target_family_ids": [],
                    "parity_lab_missing_flagship_family_ids": [],
                    "parity_lab_families_below_target": [],
                    "parity_lab_capture_missing_non_negotiable_ids": [],
                    "parity_lab_workflow_missing_non_negotiable_ids": [],
                    "parity_lab_missing_whole_product_coverage_keys": [],
                },
            },
            "veteran_deep_workflow_ready": {
                "status": "ready",
                "summary": "Dense veteran workflows are directly proven at a veteran-approved bar.",
                "reasons": [],
                "evidence": {
                    "desktop_client_ready": True,
                    "workflow_unresolved_receipt_count": 0,
                    "workflow_unresolved_receipts_sr4_sr6_only": False,
                    "families_below_veteran_approved": [],
                    "ui_element_parity_audit_required": True,
                    "ui_element_parity_audit_release_blocking_ready": True,
                    "ui_element_parity_audit_gap_ids": [],
                },
            },
            "primary_route_ready": {
                "status": "ready",
                "summary": "Primary route truth is current.",
                "reasons": [],
                "evidence": {},
            },
            "public_shelf_ready": {
                "status": "ready",
                "summary": "Public shelf, route truth, and registry posture are aligned.",
                "reasons": [],
                "evidence": {
                    "hub_and_registry_ready": True,
                    "primary_route_ready": True,
                    "release_channel_freshness_ok": True,
                    "release_channel_has_windows_public_installer": True,
                    "ui_windows_exit_gate_raw_ready": True,
                    "ui_windows_exit_gate_effective_ready": True,
                    "release_channel_missing_required_platform_head_pairs": [],
                },
            },
            "data_durability_ready": {
                "status": "ready",
                "summary": "Data durability and reversible migration proof are current.",
                "reasons": [],
                "evidence": {
                    "rules_engine_and_import_ready": True,
                    "install_claim_restore_continue_effective": data_durability_effective,
                    "families_below_task_proven": [],
                    "ui_element_parity_audit_gap_ids": [],
                },
            },
            "rules_explainability_ready": {
                "status": "ready",
                "summary": "Rules explainability and import-certification proof is current.",
                "reasons": [],
                "evidence": {
                    "rules_engine_and_import_ready": True,
                    "build_explain_publish": "ready",
                    "build_explain_publish_effective": "ready",
                    "build_explain_publish_rules_scope_blocking_reason_count": 0,
                    "rules_certification_status": "passed",
                },
            },
        },
    }


def _fixture_tree(
    tmp_path: Path,
    *,
    include_fleet_queue_row: bool = True,
    data_durability_effective: str = "ready",
    flagship_ready: str = "ready",
    include_rules_plane: bool = True,
) -> dict[str, Path]:
    registry = tmp_path / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
    fleet_queue = tmp_path / "fleet-queue.yaml"
    design_queue = tmp_path / "design-queue.yaml"
    guide = tmp_path / "NEXT_90_DAY_PRODUCT_ADVANCE_GUIDE.md"
    planes = tmp_path / "FLAGSHIP_READINESS_PLANES.yaml"
    bar = tmp_path / "FLAGSHIP_PRODUCT_BAR.md"
    flagship = tmp_path / "FLAGSHIP_PRODUCT_READINESS.generated.json"

    _write_yaml(registry, _registry())
    _write_yaml(fleet_queue, {"items": [_queue_item()]} if include_fleet_queue_row else {"items": []})
    _write_yaml(design_queue, {"items": [_queue_item()]})
    _write_text(guide, _guide())
    planes_payload = _planes()
    if not include_rules_plane:
        planes_payload["planes"] = [row for row in planes_payload["planes"] if row.get("id") != "rules_explainability_ready"]
    _write_yaml(planes, planes_payload)
    _write_text(bar, _bar())
    _write_json(flagship, _flagship_payload(data_durability_effective=data_durability_effective, flagship_ready=flagship_ready))

    return {
        "registry": registry,
        "fleet_queue": fleet_queue,
        "design_queue": design_queue,
        "guide": guide,
        "planes": planes,
        "bar": bar,
        "flagship": flagship,
    }


class MaterializeNext90M136FleetDerivedReleaseHealthPlanesTest(unittest.TestCase):
    def _run_materializer(self, fixture: dict[str, Path], artifact: Path, markdown: Path) -> dict:
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--output",
                str(artifact),
                "--markdown-output",
                str(markdown),
                "--successor-registry",
                str(fixture["registry"]),
                "--fleet-queue-staging",
                str(fixture["fleet_queue"]),
                "--design-queue-staging",
                str(fixture["design_queue"]),
                "--next90-guide",
                str(fixture["guide"]),
                "--flagship-readiness-planes",
                str(fixture["planes"]),
                "--flagship-product-bar",
                str(fixture["bar"]),
                "--flagship-product-readiness",
                str(fixture["flagship"]),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(artifact.read_text(encoding="utf-8"))

    def test_materializer_passes_with_bound_planes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path)
            payload = self._run_materializer(fixture, tmp_path / "artifact.json", tmp_path / "artifact.md")

        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["monitor_summary"]["derivation_status"], "pass")
        self.assertEqual(payload["monitor_summary"]["runtime_blocker_count"], 0)

    def test_materializer_blocks_structural_masquerade(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path, data_durability_effective="blocked", flagship_ready="ready")
            payload = self._run_materializer(fixture, tmp_path / "artifact.json", tmp_path / "artifact.md")

        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["monitor_summary"]["derivation_status"], "blocked")
        blockers = payload["monitor_summary"]["runtime_blockers"]
        self.assertTrue(any("data_durability_ready ready-state drifted" in blocker for blocker in blockers))
        self.assertTrue(any("flagship_ready evidence.data_durability_ready drifted" in blocker for blocker in blockers))

    def test_materializer_blocks_missing_plane_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path, include_rules_plane=False)
            payload = self._run_materializer(fixture, tmp_path / "artifact.json", tmp_path / "artifact.md")

        self.assertEqual(payload["status"], "blocked")
        issues = payload["canonical_monitors"]["flagship_readiness_planes"]["issues"]
        self.assertTrue(any("rules_explainability_ready" in issue for issue in issues))
