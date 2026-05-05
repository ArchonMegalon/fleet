from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


SCRIPT = Path("/docker/fleet/scripts/materialize_next90_m118_fleet_ea_organizer_packets.py")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _write_pass_script(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "#!/usr/bin/env python3\n"
        "print(" + repr(text) + ")\n",
        encoding="utf-8",
    )


def _base_registry() -> dict:
    return {
        "milestones": [
            {
                "id": 118,
                "title": "Organizer, league, convention, and season operations",
                "work_tasks": [
                    {"id": "118.1", "owner": "chummer6-hub", "title": "Land organizer, league, convention, and season operation contracts with roles, rosters, events, and audit receipts."},
                    {"id": "118.2", "owner": "chummer6-ui", "title": "Surface organizer operations on desktop without confusing GM, player, creator, and operator roles."},
                    {"id": "118.3", "owner": "executive-assistant", "title": "Compile organizer packets, event prep, and followthrough from governed operations truth."},
                    {"id": "118.4", "owner": "fleet", "title": "Add operator-loop checks for organizer health, support risk, and publication readiness."},
                ],
            }
        ]
    }


def _closure_reason() -> str:
    return (
        "M118 Fleet organizer operator packets are complete; future shards must verify the organizer operator packet receipt, "
        "standalone verifier, registry row, queue row, and design queue row instead of reopening the organizer health and "
        "publication readiness packet slice."
    )


def _queue_payload() -> dict:
    base_item = {
        "title": "Compile organizer health and publication readiness packets",
        "task": "Add fleet and EA operator-loop packets for organizer health, event prep, support risk, and publication readiness.",
        "package_id": "next90-m118-fleet-ea-organizer-packets",
        "milestone_id": 118,
        "work_task_id": "118.4",
        "status": "in_progress",
        "wave": "W13",
        "repo": "fleet",
        "allowed_paths": ["scripts", "tests", ".codex-studio", "feedback"],
        "owned_surfaces": ["organizer_health_packets", "publication_readiness:operator"],
    }
    return {"items": [base_item]}


def _complete_queue_payload() -> dict:
    payload = _queue_payload()
    payload["items"][0]["status"] = "complete"
    payload["items"][0]["completion_action"] = "verify_closed_package_only"
    payload["items"][0]["do_not_reopen_reason"] = _closure_reason()
    return payload


def _fixture_tree(tmp_path: Path, *, include_ea_organizer_pack: bool) -> dict[str, Path]:
    registry = tmp_path / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
    queue = tmp_path / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    design_queue = tmp_path / "DESIGN_NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    weekly = tmp_path / "WEEKLY_GOVERNOR_PACKET.generated.json"
    support = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    hub = tmp_path / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    organizer_verifier = tmp_path / "verify_next90_m118_hub_organizer_ops.py"
    creator_verifier = tmp_path / "verify_next90_m116_hub_creator_publication.py"
    ea_safe_pack = tmp_path / "CHUMMER_OPERATOR_SAFE_PACKET_PACK.yaml"
    ea_organizer_pack = tmp_path / "CHUMMER_ORGANIZER_PACKET_PACK.yaml"
    artifact = tmp_path / "NEXT90_M118_FLEET_EA_ORGANIZER_PACKETS.generated.json"
    markdown = tmp_path / "NEXT90_M118_FLEET_EA_ORGANIZER_PACKETS.generated.md"

    _write_yaml(registry, _base_registry())
    _write_yaml(queue, _queue_payload())
    _write_yaml(design_queue, _queue_payload())
    _write_json(
        weekly,
        {
            "generated_at": "2026-05-05T09:31:02Z",
            "as_of": "2026-05-05",
            "status": "blocked",
            "contract_name": "fleet.weekly_governor_packet",
            "decision_alignment": {"status": "pass", "actual_action": "freeze_launch"},
            "public_status_copy": {"state": "freeze_launch"},
        },
    )
    _write_json(
        support,
        {
            "generated_at": "2026-05-05T09:30:53Z",
            "contract_name": "fleet.support_case_packets",
            "summary": {
                "open_packet_count": 0,
                "needs_human_response": 0,
                "update_required_case_count": 0,
                "closure_waiting_on_release_truth": 0,
            },
            "packets": [],
            "followthrough_receipt_gates": {
                "package_id": "next90-m102-fleet-reporter-receipts",
            },
            "successor_package_verification": {"status": "pass"},
        },
    )
    _write_json(
        hub,
        {
            "generated_at": "2026-05-05T09:47:22Z",
            "status": "passed",
            "successor_queue_packages_by_id": {
                "next90-m117-hub-artifact-shelf-v2": {"status": "in_progress"},
            },
            "proof_receipts": [
                {"receipt_id": "artifact_shelf:v2", "summary": "Shared shelf truth is present."},
                {"receipt_id": "artifact_audience_filters", "summary": "Audience filters are present."},
            ],
        },
    )
    _write_pass_script(organizer_verifier, "next90 m118 hub organizer ops proof passed")
    _write_pass_script(creator_verifier, "next90 m116 hub creator publication proof passed")
    _write_yaml(
        ea_safe_pack,
        {
            "contract_name": "ea.chummer_operator_safe_packet_pack",
            "package_id": "next90-m113-executive-assistant-operator-safe-packets",
            "milestone_id": 113,
            "owned_surfaces": ["gm_prep_packets", "roster_movement_followthrough"],
            "governed_truth_bundle": {"bundle_id": "ea-m113-operator-safe-packets-v1"},
            "proof_guardrails": {"canonical_package_verification": {"queue_package_id": "next90-m113-executive-assistant-operator-safe-packets"}},
            "packet_families": {"gm_prep_packets": {"state": "ready"}},
        },
    )
    if include_ea_organizer_pack:
        _write_yaml(
            ea_organizer_pack,
            {
                "contract_name": "ea.chummer_organizer_followthrough_packet_pack",
                "package_id": "next90-m118-ea-organizer-followthrough",
                "milestone_id": 118,
                "owned_surfaces": ["organizer_followthrough:ea", "event_prep_packets"],
                "source_truth": {"hub_organizer_ops": {"required": True}},
                "proof_guardrails": {"canonical_package_verification": {"queue_package_id": "next90-m118-ea-organizer-followthrough"}},
                "packet_families": {"event_prep_packets": {"state": "ready"}},
            },
        )
    return {
        "registry": registry,
        "queue": queue,
        "design_queue": design_queue,
        "weekly": weekly,
        "support": support,
        "hub": hub,
        "organizer_verifier": organizer_verifier,
        "creator_verifier": creator_verifier,
        "ea_safe_pack": ea_safe_pack,
        "ea_organizer_pack": ea_organizer_pack,
        "artifact": artifact,
        "markdown": markdown,
    }


def _materialize(paths: dict[str, Path]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--output",
            str(paths["artifact"]),
            "--markdown-output",
            str(paths["markdown"]),
            "--successor-registry",
            str(paths["registry"]),
            "--queue-staging",
            str(paths["queue"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--weekly-governor-packet",
            str(paths["weekly"]),
            "--support-packets",
            str(paths["support"]),
            "--hub-local-release-proof",
            str(paths["hub"]),
            "--hub-organizer-verifier",
            str(paths["organizer_verifier"]),
            "--hub-creator-publication-verifier",
            str(paths["creator_verifier"]),
            "--ea-operator-safe-pack",
            str(paths["ea_safe_pack"]),
            "--ea-organizer-packet-pack",
            str(paths["ea_organizer_pack"]),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


class MaterializeNext90M118FleetEaOrganizerPacketsTests(unittest.TestCase):
    def test_materialize_accepts_fully_completed_closeout_guard_state(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fleet-m118-") as temp_dir:
            paths = _fixture_tree(Path(temp_dir), include_ea_organizer_pack=True)
            _write_yaml(paths["queue"], _complete_queue_payload())
            _write_yaml(paths["design_queue"], _complete_queue_payload())
            _write_yaml(
                paths["registry"],
                {
                    "milestones": [
                        {
                            "id": 118,
                            "title": "Organizer, league, convention, and season operations",
                            "work_tasks": [
                                {"id": "118.1", "owner": "chummer6-hub", "title": "Land organizer, league, convention, and season operation contracts with roles, rosters, events, and audit receipts."},
                                {"id": "118.2", "owner": "chummer6-ui", "title": "Surface organizer operations on desktop without confusing GM, player, creator, and operator roles."},
                                {"id": "118.3", "owner": "executive-assistant", "title": "Compile organizer packets, event prep, and followthrough from governed operations truth."},
                                {
                                    "id": "118.4",
                                    "owner": "fleet",
                                    "title": "Add operator-loop checks for organizer health, support risk, and publication readiness.",
                                    "status": "complete",
                                    "completion_action": "verify_closed_package_only",
                                    "do_not_reopen_reason": _closure_reason(),
                                },
                            ],
                        }
                    ]
                },
            )

            result = _materialize(paths)
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "pass")
            self.assertTrue(payload["agreement"]["closed_anywhere"])
            self.assertEqual(payload["agreement"]["fleet_queue_status"], "complete")
            self.assertEqual(payload["agreement"]["design_queue_status"], "complete")
            self.assertEqual(payload["agreement"]["registry_work_task_status"], "complete")
            self.assertEqual(payload["agreement"]["expected_completion_action"], "verify_closed_package_only")
            self.assertEqual(payload["agreement"]["expected_do_not_reopen_reason"], _closure_reason())

    def test_materialize_blocks_when_ea_organizer_pack_is_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fleet-m118-") as temp_dir:
            paths = _fixture_tree(Path(temp_dir), include_ea_organizer_pack=False)
            result = _materialize(paths)
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "blocked")
            self.assertEqual(payload["organizer_health"]["ea_event_prep_followthrough"]["state"], "blocked")
            self.assertEqual(
                payload["source_packet_links"]["hub_publication_receipts"]["receipt_ids"],
                ["artifact_shelf:v2", "artifact_audience_filters"],
            )
            self.assertIn("EA still lacks", payload["status_reason"])
            self.assertTrue(paths["markdown"].is_file())

    def test_materialize_blocks_when_hub_audience_filter_receipt_is_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fleet-m118-") as temp_dir:
            paths = _fixture_tree(Path(temp_dir), include_ea_organizer_pack=True)
            hub_payload = json.loads(paths["hub"].read_text(encoding="utf-8"))
            hub_payload["proof_receipts"] = [
                receipt
                for receipt in hub_payload["proof_receipts"]
                if receipt.get("receipt_id") != "artifact_audience_filters"
            ]
            _write_json(paths["hub"], hub_payload)

            result = _materialize(paths)
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "blocked")
            self.assertEqual(payload["organizer_health"]["artifact_shelf_publication_surface"]["state"], "blocked")
            self.assertEqual(payload["publication_readiness"]["state"], "blocked")
            self.assertFalse(payload["organizer_health"]["artifact_shelf_publication_surface"]["filter_receipt_present"])
            self.assertIn("audience-filter receipt is missing", payload["publication_readiness"]["summary"])
            self.assertIn(
                "Restore the Hub artifact audience-filter receipt before trusting organizer publication-readiness summaries.",
                payload["next_actions"],
            )

    def test_materialize_passes_when_all_operator_inputs_exist(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fleet-m118-") as temp_dir:
            paths = _fixture_tree(Path(temp_dir), include_ea_organizer_pack=True)
            result = _materialize(paths)
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "pass")
            self.assertEqual(payload["support_risk"]["state"], "low")
            self.assertEqual(payload["publication_readiness"]["state"], "watch")
            self.assertEqual(payload["organizer_health"]["ea_event_prep_followthrough"]["state"], "ready")
            self.assertEqual(payload["source_packet_links"]["weekly_governor"]["contract_name"], "fleet.weekly_governor_packet")
            self.assertEqual(payload["source_packet_links"]["support_followthrough"]["package_id"], "next90-m102-fleet-reporter-receipts")
            self.assertFalse(payload["agreement"]["closed_anywhere"])

    def test_materialize_keeps_publication_readiness_on_watch_for_freeze_variants(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fleet-m118-") as temp_dir:
            paths = _fixture_tree(Path(temp_dir), include_ea_organizer_pack=True)
            weekly_payload = json.loads(paths["weekly"].read_text(encoding="utf-8"))
            weekly_payload["public_status_copy"]["state"] = "freeze_with_rollback_watch"
            paths["weekly"].write_text(json.dumps(weekly_payload, indent=2) + "\n", encoding="utf-8")

            result = _materialize(paths)
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "pass")
            self.assertEqual(payload["publication_readiness"]["state"], "watch")
            self.assertIn("still frozen", payload["publication_readiness"]["summary"])

    def test_materialize_blocks_when_ea_organizer_pack_is_placeholder_yaml(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fleet-m118-") as temp_dir:
            paths = _fixture_tree(Path(temp_dir), include_ea_organizer_pack=True)
            _write_yaml(paths["ea_organizer_pack"], {"contract_name": "ea.placeholder"})
            result = _materialize(paths)
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            followthrough = payload["organizer_health"]["ea_event_prep_followthrough"]
            self.assertEqual(payload["status"], "blocked")
            self.assertEqual(followthrough["state"], "blocked")
            self.assertIn("package_id drifted", followthrough["organizer_pack_issues"])
            self.assertIn("incomplete or drifted", followthrough["summary"])

    def test_materialize_fail_closes_partial_completed_queue_authority(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fleet-m118-") as temp_dir:
            paths = _fixture_tree(Path(temp_dir), include_ea_organizer_pack=True)

            queue_payload = _queue_payload()
            queue_payload["items"][0]["status"] = "complete"
            queue_payload["items"][0]["completion_action"] = "verify_closed_package_only"
            queue_payload["items"][0]["do_not_reopen_reason"] = _closure_reason()
            _write_yaml(paths["queue"], queue_payload)

            result = _materialize(paths)
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "blocked")
            self.assertTrue(payload["agreement"]["closed_anywhere"])
            self.assertEqual(payload["agreement"]["fleet_queue_status"], "complete")
            self.assertEqual(payload["agreement"]["design_queue_status"], "in_progress")
            self.assertEqual(payload["agreement"]["registry_work_task_status"], "")
            self.assertIn(
                "Design queue status drifted from completed package closure.",
                payload["organizer_health"]["queue_alignment"]["issues"],
            )
            self.assertIn(
                "Registry work-task status drifted from completed package closure.",
                payload["organizer_health"]["queue_alignment"]["issues"],
            )
            self.assertIn(
                "Repair Fleet/design queue or registry drift before trusting the M118 operator packet.",
                payload["next_actions"],
            )


if __name__ == "__main__":
    unittest.main()
