from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import base64
from pathlib import Path

import yaml


MATERIALIZER = Path("/docker/fleet/scripts/materialize_next90_m145_fleet_explain_coverage_gate.py")
VERIFIER = Path("/docker/fleet/scripts/verify_next90_m145_fleet_explain_coverage_gate.py")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _base_registry() -> dict:
    return {
        "milestones": [
            {
                "id": 145,
                "work_tasks": [
                    {
                        "id": "145.1",
                        "owner": "chummer6-core",
                        "status": "complete",
                        "title": "Emit explanation packets, coverage-registry truth, and bounded counterfactual packets for every visible mechanical result.",
                    },
                    {
                        "id": "145.2",
                        "owner": "chummer6-ui",
                        "status": "complete",
                        "title": "Wire the desktop explain drawer, source-anchor launch, stale-state handling, and text-first follow-up on promoted workbench routes.",
                    },
                    {
                        "id": "145.3",
                        "owner": "chummer6-mobile",
                        "status": "complete",
                        "title": "Bring quick explain, source-anchor context, and bounded follow-up to mobile and live-play shells.",
                    },
                    {
                        "id": "145.4",
                        "owner": "executive-assistant",
                        "status": "done",
                        "title": "Compile grounded narration and follow-up packs strictly from explanation-packet and counterfactual truth.",
                    },
                    {
                        "id": "145.5",
                        "owner": "chummer6-media-factory",
                        "title": "Render optional audio or presenter siblings from approved explanation packets without becoming calculation authority.",
                    },
                    {
                        "id": "145.6",
                        "owner": "fleet",
                        "title": "Fail closeout when visible values, warnings, or bounded what-if answers ship without explain coverage and fallback proof.",
                    },
                    {
                        "id": "145.7",
                        "owner": "chummer6-design",
                        "status": "done",
                        "title": "Canonize explain-every-value truth order, source-anchor linkage, and bounded follow-up or presenter posture.",
                    },
                ],
            }
        ]
    }


def _queue_item(package_id: str, work_task_id: str, repo: str, status: str) -> dict:
    frontier_map = {
        "145.1": 1451045101,
        "145.2": 1452045202,
        "145.3": 1453045303,
        "145.4": 1454045404,
        "145.5": 1455045505,
        "145.6": 1456045606,
        "145.7": 1457045707,
    }
    title_map = {
        "145.1": "Emit explanation packets, coverage-registry truth, and bounded counterfactual packets for every visible mechanical result.",
        "145.2": "Wire the desktop explain drawer, source-anchor launch, stale-state handling, and text-first follow-up on promoted workbench routes.",
        "145.3": "Bring quick explain, source-anchor context, and bounded follow-up to mobile and live-play shells.",
        "145.4": "Compile grounded narration and follow-up packs strictly from explanation-packet and counterfactual truth.",
        "145.5": "Render optional audio or presenter siblings from approved explanation packets without becoming calculation authority.",
        "145.6": "Fail closeout when visible values, warnings, or bounded what-if answers ship without explain coverage and fallback proof.",
        "145.7": "Canonize explain-every-value truth order, source-anchor linkage, and bounded follow-up or presenter posture.",
    }
    task_map = {
        "145.1": "Emit first-party explanation packets, coverage-registry rows, and deterministic counterfactual packets for promoted visible mechanical results, legality states, warnings, and before-after deltas.",
        "145.2": "Wire packet-backed desktop explain drawers, source-anchor affordances, stale snapshot handling, and text-first bounded follow-up across promoted workbench routes.",
        "145.3": "Bring packet-backed quick explain, source-anchor context, stale-state posture, and bounded text-first follow-up to mobile and live-play shells.",
        "145.4": "Compile optional narration and grounded follow-up packs strictly from approved explanation-packet and counterfactual truth without inventing rules or arithmetic authority.",
        "145.5": "Render optional audio or presenter siblings from approved explanation packets while preserving packet identity, grounding scope, and first-party text fallback.",
        "145.6": "Fail closeout when promoted visible values, warnings, or bounded what-if answers ship without coverage-registry truth, deterministic packet proof, source-anchor posture, or text-first fallback.",
        "145.7": "Canonize explain-every-value truth order, source-anchor linkage, coverage-registry floor, and bounded follow-up or presenter posture in canonical design.",
    }
    item = {
        "package_id": package_id,
        "work_task_id": work_task_id,
        "frontier_id": frontier_map[work_task_id],
        "milestone_id": 145,
        "repo": repo,
        "status": status,
        "title": title_map[work_task_id],
        "task": task_map[work_task_id],
        "owned_surfaces": ["placeholder"],
        "allowed_paths": ["placeholder"],
    }
    if work_task_id == "145.6":
        item["owned_surfaces"] = ["explain_coverage_gate:fleet", "explain_fallback_truth:fleet"]
        item["allowed_paths"] = ["scripts", "tests", ".codex-studio", "feedback"]
    return item


def _fixture_tree(tmp_path: Path) -> dict[str, Path]:
    registry = tmp_path / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
    queue = tmp_path / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    design_queue = tmp_path / "DESIGN_NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    artifact = tmp_path / "NEXT90_M145_FLEET_EXPLAIN_COVERAGE_GATE.generated.json"
    core = tmp_path / "EXPLAIN_VALUE_PACKETS.generated.json"
    ui = tmp_path / "NEXT90_M145_UI_DESKTOP_EXPLAIN_DRAWER_AND_FOLLOW_UP.generated.json"
    mobile = tmp_path / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    media = tmp_path / "MEDIA_LOCAL_RELEASE_PROOF.generated.json"
    ea = tmp_path / "CHUMMER_EXPLAIN_NARRATION_PACKET_PACK.yaml"
    canon = tmp_path / "EXPLAIN_EVERY_VALUE_AND_GROUNDED_FOLLOW_UP.md"

    _write_yaml(registry, _base_registry())
    queue_payload = {
        "items": [
            _queue_item("next90-m145-core-explain-every-value-packets", "145.1", "chummer6-core", "complete"),
            _queue_item("next90-m145-ui-desktop-explain-drawer-and-follow-up", "145.2", "chummer6-ui", "complete"),
            _queue_item("next90-m145-mobile-quick-explain-and-follow-up", "145.3", "chummer6-mobile", "complete"),
            _queue_item("next90-m145-ea-grounded-explain-narration-packs", "145.4", "executive-assistant", "done"),
            _queue_item("next90-m145-media-factory-explain-presenter-siblings", "145.5", "chummer6-media-factory", "not_started"),
            _queue_item("next90-m145-fleet-explain-coverage-gate", "145.6", "fleet", "not_started"),
            _queue_item("next90-m145-design-explain-every-value-canon", "145.7", "chummer6-design", "done"),
        ]
    }
    _write_yaml(queue, queue_payload)
    _write_yaml(design_queue, queue_payload)

    _write_json(
        core,
        {
            "status": "passed",
            "coverage_registry_kinds": [
                "mechanical-result",
                "legality-state",
                "warning",
                "before-after-delta",
                "counterfactual",
                "source-anchor",
            ],
            "counterfactual_outcome_kinds": ["why", "why-not", "what-if"],
            "proof_anchor_count": 3,
            "verification_commands": [
                "python3 tests/test_explain_value_packet_receipt.py",
                "python3 scripts/verify-explain-value-packets.py",
            ],
            "unresolved": {"missing_files": [], "snippet_failures": {}},
        },
    )
    _write_json(
        ui,
        {
            "status": "pass",
            "unresolved": [],
            "evidence": {
                "sourceChecks": {
                    "Chummer.Avalonia/MainWindow.FeedbackCoordinator.cs": {
                        "Explain follow-up stayed text-first with source-anchor and stale-state posture visible.": True
                    },
                    "Chummer.Avalonia/DesktopExplainDrawerFollowUpWindow.cs": {
                        'CreateSection("Bounded follow-up", FirstNonBlank(_context.FollowUp, "No bounded follow-up is attached to this packet."))': True
                    },
                }
            },
        },
    )
    _write_json(
        mobile,
        {
            "status": "passed",
            "journeys_passed": ["quick_explain_follow_up"],
            "required_markers": {
                "quick_explain_follow_up": [
                    "source-anchor context",
                    "grounded text-first follow-up bounded to the claimed live-play shell",
                ]
            },
        },
    )
    _write_yaml(
        ea,
        {
            "status": "complete",
            "quality_gates": {
                "required_labels": ["packet_grounded", "text_first_fallback", "no_arithmetic_authority"]
            },
            "fail_closed_posture": {
                "missing_counterfactual": "Refuse the why-not or what-if answer and point back to the first-party explain drawer."
            },
            "compile_contract": {
                "grounded_follow_up_pack": {
                    "refusal_rule": "Unsupported or missing packet classes must produce an unavailable response with the missing packet reason instead of guessed advice."
                }
            },
        },
    )
    canon.write_text(
        "\n".join(
            [
                "# Explain every value",
                "Coverage registry",
                "text explanation is always the first-party fallback",
                "source anchors stay attached to the same packet",
                "If Chummer cannot produce the required packet, it should say so plainly and fall back to text guidance instead of guessing.",
                "The gate should fail closed",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "registry": registry,
        "queue": queue,
        "design_queue": design_queue,
        "artifact": artifact,
        "core": core,
        "ui": ui,
        "mobile": mobile,
        "media": media,
        "ea": ea,
        "canon": canon,
    }


def _materialize(paths: dict[str, Path]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(MATERIALIZER),
            "--output",
            str(paths["artifact"]),
            "--successor-registry",
            str(paths["registry"]),
            "--queue-staging",
            str(paths["queue"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--core-receipt",
            str(paths["core"]),
            "--ui-receipt",
            str(paths["ui"]),
            "--mobile-receipt",
            str(paths["mobile"]),
            "--media-receipt",
            str(paths["media"]),
            "--ea-packet-pack",
            str(paths["ea"]),
            "--design-canon",
            str(paths["canon"]),
        ],
        cwd="/docker/fleet",
        capture_output=True,
        text=True,
        check=False,
    )


class VerifyNext90M145FleetExplainCoverageGateTests(unittest.TestCase):
    def test_materializer_blocks_when_local_fleet_package_closes_ahead_of_design_queue_and_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            paths = _fixture_tree(Path(tmp_dir))
            queue_payload = yaml.safe_load(paths["queue"].read_text(encoding="utf-8"))
            for item in queue_payload["items"]:
                if item["work_task_id"] == "145.6":
                    item["status"] = "complete"
            _write_yaml(paths["queue"], queue_payload)

            result = _materialize(paths)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "blocked")
            self.assertIn(
                "design queue row is not closed after the local Fleet package row marked this package closed",
                payload["canonical_alignment"]["issues"],
            )
            self.assertIn(
                "registry work-task row is not closed after the local Fleet package row marked this package closed",
                payload["canonical_alignment"]["issues"],
            )
            self.assertEqual(payload["canonical_alignment"]["queue_status"], "complete")
            self.assertEqual(payload["canonical_alignment"]["design_queue_status"], "not_started")
            self.assertEqual(payload["canonical_alignment"]["registry_status"], "")

    def test_materializer_passes_when_fleet_package_and_sibling_proof_are_closed_everywhere(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            paths = _fixture_tree(Path(tmp_dir))
            queue_payload = yaml.safe_load(paths["queue"].read_text(encoding="utf-8"))
            design_queue_payload = yaml.safe_load(paths["design_queue"].read_text(encoding="utf-8"))
            registry_payload = yaml.safe_load(paths["registry"].read_text(encoding="utf-8"))
            for payload in (queue_payload, design_queue_payload):
                for item in payload["items"]:
                    if item["work_task_id"] == "145.6":
                        item["status"] = "complete"
            for work_task in registry_payload["milestones"][0]["work_tasks"]:
                if work_task["id"] == "145.6":
                    work_task["status"] = "complete"
            _write_yaml(paths["queue"], queue_payload)
            _write_yaml(paths["design_queue"], design_queue_payload)
            _write_yaml(paths["registry"], registry_payload)

            result = _materialize(paths)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "pass")
            self.assertEqual(payload["canonical_alignment"]["issues"], [])
            self.assertEqual(payload["canonical_alignment"]["queue_status"], "complete")
            self.assertEqual(payload["canonical_alignment"]["design_queue_status"], "complete")
            self.assertEqual(payload["canonical_alignment"]["registry_status"], "complete")

    def test_materializer_does_not_block_on_unshipped_optional_presenter_sibling(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            paths = _fixture_tree(Path(tmp_dir))
            result = _materialize(paths)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            self.assertEqual(payload["aggregate_checks"]["presenter_optional_fallback"]["status"], "not_shipped")
            blockers = payload["package_closeout"]["blocked_reasons"]
            self.assertFalse(any("presenter sibling proof is not published yet" in blocker for blocker in blockers))
            presenter_surface = next(
                surface for surface in payload["surface_receipts"] if surface["work_task_id"] == "145.5"
            )
            self.assertFalse(presenter_surface["shipped"])
            self.assertEqual(presenter_surface["blocking_reasons"], [])

    def test_materializer_blocks_when_shipped_presenter_sibling_proof_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            paths = _fixture_tree(Path(tmp_dir))
            queue_payload = yaml.safe_load(paths["queue"].read_text(encoding="utf-8"))
            design_queue_payload = yaml.safe_load(paths["design_queue"].read_text(encoding="utf-8"))
            for payload in (queue_payload, design_queue_payload):
                for item in payload["items"]:
                    if item["work_task_id"] == "145.5":
                        item["status"] = "complete"
            _write_yaml(paths["queue"], queue_payload)
            _write_yaml(paths["design_queue"], design_queue_payload)

            result = _materialize(paths)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "blocked")
            blockers = payload["package_closeout"]["blocked_reasons"]
            self.assertTrue(any("presenter sibling proof is not published yet" in blocker for blocker in blockers))
            self.assertEqual(payload["aggregate_checks"]["presenter_optional_fallback"]["status"], "blocked")

    def test_materializer_blocks_when_design_queue_lags_closed_core_surface(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            paths = _fixture_tree(Path(tmp_dir))
            design_queue_payload = yaml.safe_load(paths["design_queue"].read_text(encoding="utf-8"))
            for item in design_queue_payload["items"]:
                if item["work_task_id"] == "145.1":
                    item["status"] = "not_started"
            _write_yaml(paths["design_queue"], design_queue_payload)

            result = _materialize(paths)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "blocked")
            blockers = payload["package_closeout"]["blocked_reasons"]
            self.assertTrue(any("design queue row is not closed after the local queue marked this package closed" in blocker for blocker in blockers))
            self.assertEqual(payload["aggregate_checks"]["coverage_registry_truth"]["status"], "blocked")
            self.assertEqual(payload["aggregate_checks"]["deterministic_packet_proof"]["status"], "blocked")

    def test_materializer_accepts_media_successor_package_receipt_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            paths = _fixture_tree(Path(tmp_dir))
            media_payload = {
                "status": "passed",
                "successor_packages": [
                    {
                        "package_id": "next90-m145-media-factory-explain-presenter-siblings",
                        "status": "complete",
                        "explain_presenter_guards": [
                            "first-party text fallback stays first-class in the render receipt and text fallback receipt so optional media surfaces never become the only explain surface",
                            "queue and registry mirrors must match the canonical M145 package and task blocks exactly so repo-local proof cannot drift on status or scoped fields",
                        ],
                        "receipt_rows": [
                            "ExplainPresenterTextFallbackReceipt",
                            "ExplainPresenterSiblingRoleReceiptGroup",
                        ],
                    }
                ],
            }
            _write_json(paths["media"], media_payload)
            queue_payload = yaml.safe_load(paths["queue"].read_text(encoding="utf-8"))
            design_queue_payload = yaml.safe_load(paths["design_queue"].read_text(encoding="utf-8"))
            for payload in (queue_payload, design_queue_payload):
                for item in payload["items"]:
                    if item["work_task_id"] == "145.5":
                        item["status"] = "complete"
            _write_yaml(paths["queue"], queue_payload)
            _write_yaml(paths["design_queue"], design_queue_payload)

            result = _materialize(paths)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))

            presenter_surface = next(
                surface for surface in payload["surface_receipts"] if surface["work_task_id"] == "145.5"
            )
            self.assertTrue(presenter_surface["proof_passed"])
            self.assertEqual(presenter_surface["blocking_reasons"], [])
            self.assertEqual(presenter_surface["proof_evidence"]["proof_source"], "successor_package")
            self.assertEqual(payload["aggregate_checks"]["presenter_optional_fallback"]["status"], "pass")

    def test_materializer_blocks_when_core_receipt_omits_before_after_delta_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            paths = _fixture_tree(Path(tmp_dir))
            core_payload = json.loads(paths["core"].read_text(encoding="utf-8"))
            core_payload["coverage_registry_kinds"] = [
                kind for kind in core_payload["coverage_registry_kinds"] if kind != "before-after-delta"
            ]
            _write_json(paths["core"], core_payload)

            result = _materialize(paths)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "blocked")
            core_surface = next(
                surface for surface in payload["surface_receipts"] if surface["work_task_id"] == "145.1"
            )
            self.assertIn(
                "core coverage-registry kinds do not cover result, legality, warning, before-after delta, counterfactual, and source-anchor truth",
                core_surface["blocking_reasons"],
            )
            self.assertEqual(payload["aggregate_checks"]["coverage_registry_truth"]["status"], "blocked")
            self.assertEqual(payload["aggregate_checks"]["deterministic_packet_proof"]["status"], "blocked")

    def test_materializer_blocks_when_core_receipt_omits_deterministic_proof_anchors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            paths = _fixture_tree(Path(tmp_dir))
            core_payload = json.loads(paths["core"].read_text(encoding="utf-8"))
            core_payload["proof_anchor_count"] = 0
            _write_json(paths["core"], core_payload)

            result = _materialize(paths)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "blocked")
            core_surface = next(
                surface for surface in payload["surface_receipts"] if surface["work_task_id"] == "145.1"
            )
            self.assertIn(
                "core explanation-packet receipt is missing deterministic proof anchors",
                core_surface["blocking_reasons"],
            )
            self.assertEqual(payload["aggregate_checks"]["deterministic_packet_proof"]["status"], "blocked")

    def test_materializer_blocks_when_shipped_sibling_queue_title_drifts_from_design_mirror(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            paths = _fixture_tree(Path(tmp_dir))
            queue_payload = yaml.safe_load(paths["queue"].read_text(encoding="utf-8"))
            for item in queue_payload["items"]:
                if item["work_task_id"] == "145.1":
                    item["title"] = "drifted core title"
            _write_yaml(paths["queue"], queue_payload)

            result = _materialize(paths)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "blocked")
            core_surface = next(
                surface for surface in payload["surface_receipts"] if surface["work_task_id"] == "145.1"
            )
            self.assertIn("queue title drifted from the design queue mirror", core_surface["blocking_reasons"])
            self.assertEqual(payload["aggregate_checks"]["coverage_registry_truth"]["status"], "blocked")
            self.assertEqual(payload["aggregate_checks"]["deterministic_packet_proof"]["status"], "blocked")

    def test_materializer_blocks_when_shipped_sibling_queue_owned_surfaces_drift_from_design_mirror(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            paths = _fixture_tree(Path(tmp_dir))
            queue_payload = yaml.safe_load(paths["queue"].read_text(encoding="utf-8"))
            for item in queue_payload["items"]:
                if item["work_task_id"] == "145.3":
                    item["owned_surfaces"] = ["wrong-surface"]
            _write_yaml(paths["queue"], queue_payload)

            result = _materialize(paths)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "blocked")
            mobile_surface = next(
                surface for surface in payload["surface_receipts"] if surface["work_task_id"] == "145.3"
            )
            self.assertIn("queue owned_surfaces drifted from the design queue mirror", mobile_surface["blocking_reasons"])
            self.assertEqual(payload["aggregate_checks"]["source_anchor_posture"]["status"], "blocked")
            self.assertEqual(payload["aggregate_checks"]["text_first_fallback"]["status"], "blocked")

    def test_verifier_accepts_clean_blocked_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            paths = _fixture_tree(Path(tmp_dir))
            result = _materialize(paths)
            self.assertEqual(result.returncode, 0, result.stderr)
            verify = subprocess.run(
                [
                    sys.executable,
                    str(VERIFIER),
                    "--artifact",
                    str(paths["artifact"]),
                    "--successor-registry",
                    str(paths["registry"]),
                    "--queue-staging",
                    str(paths["queue"]),
                    "--design-queue-staging",
                    str(paths["design_queue"]),
                    "--core-receipt",
                    str(paths["core"]),
                    "--ui-receipt",
                    str(paths["ui"]),
                    "--mobile-receipt",
                    str(paths["mobile"]),
                    "--media-receipt",
                    str(paths["media"]),
                    "--ea-packet-pack",
                    str(paths["ea"]),
                    "--design-canon",
                    str(paths["canon"]),
                ],
                cwd="/docker/fleet",
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(verify.returncode, 0, verify.stderr)

    def test_verifier_rejects_queue_title_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            paths = _fixture_tree(Path(tmp_dir))
            result = _materialize(paths)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            payload["queue_title"] = "bad title"
            paths["artifact"].write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            verify = subprocess.run(
                [
                    sys.executable,
                    str(VERIFIER),
                    "--artifact",
                    str(paths["artifact"]),
                    "--successor-registry",
                    str(paths["registry"]),
                    "--queue-staging",
                    str(paths["queue"]),
                    "--design-queue-staging",
                    str(paths["design_queue"]),
                    "--core-receipt",
                    str(paths["core"]),
                    "--ui-receipt",
                    str(paths["ui"]),
                    "--mobile-receipt",
                    str(paths["mobile"]),
                    "--media-receipt",
                    str(paths["media"]),
                    "--ea-packet-pack",
                    str(paths["ea"]),
                    "--design-canon",
                    str(paths["canon"]),
                ],
                cwd="/docker/fleet",
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(verify.returncode, 1)
            self.assertIn("queue title drifted from the Fleet M145 package contract", verify.stderr)

    def test_verifier_rejects_frontier_id_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            paths = _fixture_tree(Path(tmp_dir))
            result = _materialize(paths)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            payload["frontier_id"] = 999
            paths["artifact"].write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            verify = subprocess.run(
                [
                    sys.executable,
                    str(VERIFIER),
                    "--artifact",
                    str(paths["artifact"]),
                    "--successor-registry",
                    str(paths["registry"]),
                    "--queue-staging",
                    str(paths["queue"]),
                    "--design-queue-staging",
                    str(paths["design_queue"]),
                    "--core-receipt",
                    str(paths["core"]),
                    "--ui-receipt",
                    str(paths["ui"]),
                    "--mobile-receipt",
                    str(paths["mobile"]),
                    "--media-receipt",
                    str(paths["media"]),
                    "--ea-packet-pack",
                    str(paths["ea"]),
                    "--design-canon",
                    str(paths["canon"]),
                ],
                cwd="/docker/fleet",
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(verify.returncode, 1)
            self.assertIn("frontier_id drifted from the assigned Fleet M145 package", verify.stderr)

    def test_verifier_rejects_unexpected_extra_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            paths = _fixture_tree(Path(tmp_dir))
            result = _materialize(paths)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            payload["unexpected_extra_field"] = {"helper": "still blocked"}
            paths["artifact"].write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            verify = subprocess.run(
                [
                    sys.executable,
                    str(VERIFIER),
                    "--artifact",
                    str(paths["artifact"]),
                    "--successor-registry",
                    str(paths["registry"]),
                    "--queue-staging",
                    str(paths["queue"]),
                    "--design-queue-staging",
                    str(paths["design_queue"]),
                    "--core-receipt",
                    str(paths["core"]),
                    "--ui-receipt",
                    str(paths["ui"]),
                    "--mobile-receipt",
                    str(paths["mobile"]),
                    "--media-receipt",
                    str(paths["media"]),
                    "--ea-packet-pack",
                    str(paths["ea"]),
                    "--design-canon",
                    str(paths["canon"]),
                ],
                cwd="/docker/fleet",
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(verify.returncode, 1)
            self.assertIn("generated artifact contains unexpected drift outside the allowed generated_at field", verify.stderr)

    def test_materializer_blocks_when_queue_root_cites_worker_local_helper_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            paths = _fixture_tree(Path(tmp_dir))
            queue_payload = yaml.safe_load(paths["queue"].read_text(encoding="utf-8"))
            queue_payload["source_registry_path"] = "supervisor status"
            _write_yaml(paths["queue"], queue_payload)

            result = _materialize(paths)
            self.assertEqual(result.returncode, 0, result.stderr)

            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "blocked")
            self.assertIn(
                "local queue staging cites worker-local telemetry/helper proof: supervisor status",
                payload["canonical_alignment"]["issues"],
            )

    def test_materializer_blocks_when_local_queue_frontier_id_drifts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            paths = _fixture_tree(Path(tmp_dir))
            queue_payload = yaml.safe_load(paths["queue"].read_text(encoding="utf-8"))
            for item in queue_payload["items"]:
                if item["work_task_id"] == "145.6":
                    item["frontier_id"] = 999
            _write_yaml(paths["queue"], queue_payload)

            result = _materialize(paths)
            self.assertEqual(result.returncode, 0, result.stderr)

            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "blocked")
            self.assertIn(
                "local queue frontier_id drifted from the Fleet M145 package contract",
                payload["canonical_alignment"]["issues"],
            )

    def test_materializer_blocks_when_design_queue_package_identity_drifts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            paths = _fixture_tree(Path(tmp_dir))
            design_queue_payload = yaml.safe_load(paths["design_queue"].read_text(encoding="utf-8"))
            for item in design_queue_payload["items"]:
                if item["work_task_id"] == "145.6":
                    item["repo"] = "wrong-repo"
                    item["milestone_id"] = 999
                    item["package_id"] = "wrong-package"
            _write_yaml(paths["design_queue"], design_queue_payload)

            result = _materialize(paths)
            self.assertEqual(result.returncode, 0, result.stderr)

            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "blocked")
            self.assertIn(
                "design queue package_id drifted from the Fleet M145 package contract",
                payload["canonical_alignment"]["issues"],
            )
            self.assertIn(
                "design queue repo drifted from the Fleet M145 package contract",
                payload["canonical_alignment"]["issues"],
            )
            self.assertIn(
                "design queue milestone_id drifted from the Fleet M145 package contract",
                payload["canonical_alignment"]["issues"],
            )

    def test_materializer_blocks_when_registry_milestone_cites_encoded_worker_local_helper_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            paths = _fixture_tree(Path(tmp_dir))
            registry_payload = yaml.safe_load(paths["registry"].read_text(encoding="utf-8"))
            encoded = base64.b64encode(b"ACTIVE_RUN_HANDOFF.generated.md").decode("ascii")
            registry_payload["milestones"][0]["summary"] = encoded
            _write_yaml(paths["registry"], registry_payload)

            result = _materialize(paths)
            self.assertEqual(result.returncode, 0, result.stderr)

            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "blocked")
            self.assertIn(
                "registry milestone cites worker-local telemetry/helper proof: ACTIVE_RUN_HANDOFF.generated.md",
                payload["canonical_alignment"]["issues"],
            )

    def test_materializer_blocks_when_shipped_sibling_registry_row_cites_worker_local_helper_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            paths = _fixture_tree(Path(tmp_dir))
            registry_payload = yaml.safe_load(paths["registry"].read_text(encoding="utf-8"))
            for task in registry_payload["milestones"][0]["work_tasks"]:
                if task["id"] == "145.1":
                    task["evidence"] = ["supervisor eta"]
            _write_yaml(paths["registry"], registry_payload)

            result = _materialize(paths)
            self.assertEqual(result.returncode, 0, result.stderr)

            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "blocked")
            core_surface = next(
                surface for surface in payload["surface_receipts"] if surface["work_task_id"] == "145.1"
            )
            self.assertIn(
                "registry work-task row cites worker-local telemetry/helper proof: supervisor eta",
                core_surface["blocking_reasons"],
            )
            self.assertEqual(payload["aggregate_checks"]["coverage_registry_truth"]["status"], "blocked")
            self.assertEqual(payload["aggregate_checks"]["deterministic_packet_proof"]["status"], "blocked")

    def test_materializer_blocks_when_core_receipt_cites_encoded_worker_local_helper_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            paths = _fixture_tree(Path(tmp_dir))
            core_payload = json.loads(paths["core"].read_text(encoding="utf-8"))
            core_payload["proof_anchor"] = base64.b64encode(b"TASK_LOCAL_TELEMETRY.generated.json").decode("ascii")
            _write_json(paths["core"], core_payload)

            result = _materialize(paths)
            self.assertEqual(result.returncode, 0, result.stderr)

            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "blocked")
            core_surface = next(
                surface for surface in payload["surface_receipts"] if surface["work_task_id"] == "145.1"
            )
            self.assertIn(
                "core explanation-packet receipt cites worker-local telemetry/helper proof: TASK_LOCAL_TELEMETRY.generated.json",
                core_surface["blocking_reasons"],
            )
            self.assertEqual(payload["aggregate_checks"]["coverage_registry_truth"]["status"], "blocked")
            self.assertEqual(payload["aggregate_checks"]["deterministic_packet_proof"]["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
