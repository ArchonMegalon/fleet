from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


SCRIPT = Path("/docker/fleet/scripts/materialize_next90_m138_fleet_hero_path_closeout_gates.py")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    _write_text(path, json.dumps(payload, indent=2) + "\n")


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


def _registry() -> dict:
    return {
        "program_wave": "next_90_day_product_advance",
        "milestones": [
            {
                "id": 138,
                "title": "First emotional wins, no-desktop participation, and adoption confidence closure",
                "wave": "W25",
                "status": "not_started",
                "dependencies": [119, 123, 136, 137],
                "work_tasks": [
                    {
                        "id": "138.9",
                        "owner": "fleet",
                        "title": "Fail closeout when the 90-second newcomer path, Ready for Tonight verdicts, adoption-confidence receipts, or Foundry-first handoff receipts are stale, missing, or contradicted by public posture.",
                        "status": "not_started",
                    }
                ],
            }
        ],
    }


def _queue_item() -> dict:
    return {
        "title": "Fail closeout when the 90-second newcomer path, Ready for Tonight verdicts, adoption-confidence receipts, or Foundry-first handoff receipts are stale, missing, or contradicted by public posture.",
        "task": "Fail closeout when the 90-second newcomer path, Ready for Tonight verdicts, adoption-confidence receipts, or Foundry-first handoff receipts are stale, missing, or contradicted by public posture.",
        "package_id": "next90-m138-fleet-fail-closeout-when-the-90-second-newcomer-path-ready-for-tonight-verdi",
        "milestone_id": 138,
        "work_task_id": "138.9",
        "frontier_id": 4764536356,
        "status": "not_started",
        "wave": "W25",
        "repo": "fleet",
        "allowed_paths": ["scripts", "tests", ".codex-studio", "feedback"],
        "owned_surfaces": ["fail_closeout_when_the_90_second_newcomer_path_ready_for:fleet"],
    }


def _next90_guide() -> str:
    return """# Guide

## Wave 25 - turn first emotional wins into release-gated product truth

### 138. First emotional wins, no-desktop participation, and adoption confidence closure

Exit: the hero paths are real and proven: `Ready for Tonight`, no-desktop beginner participation, start-from-today adoption, source-aware explain, role kits, and one excellent Foundry-first export handoff.
"""


def _roadmap() -> str:
    return """# Roadmap

* make the first emotional wins impossible to miss: Ready for Tonight, start-from-today adoption, no-desktop participation, source-aware explain, starter role kits, and one excellent Foundry-first handoff
"""


def _ready_for_tonight_mode() -> str:
    return """# Ready for Tonight Mode

`ReadyForTonight` is not a dashboard.
`Make me ready for this run`
### 3. Organizer or public-run readiness
* `proof_receipts`
"""


def _ready_for_tonight_gates() -> dict:
    return {
        "artifact": "ready_for_tonight_gates",
        "gates": [
            {
                "id": "player_readiness_verdict",
                "required_inputs": ["runner_dossier", "rule_environment", "session_context", "join_handoff"],
                "required_outputs": [
                    "status",
                    "blocking_reasons",
                    "fix_now_actions",
                    "changed_since_last_session",
                    "next_best_screen",
                ],
            },
            {
                "id": "gm_readiness_verdict",
                "required_inputs": ["open_run", "roster", "prep_packet", "opposition_packet", "resolution_backlog"],
                "required_outputs": [
                    "status",
                    "blocking_reasons",
                    "unresolved_rewards",
                    "unresolved_disputes",
                    "export_readiness",
                    "next_best_screen",
                ],
            },
            {
                "id": "organizer_publishability_verdict",
                "required_inputs": ["open_run_policy", "community_rule_environment", "table_contract", "safety_posture", "meeting_handoff"],
                "required_outputs": [
                    "status",
                    "publish_blockers",
                    "moderation_risk",
                    "participation_bridge_ready",
                    "proof_receipts",
                ],
            },
        ],
    }


def _public_onboarding_paths() -> str:
    return """# Public onboarding

Desktop remains the expert flagship.
land on public run
* receive the `make me ready` verdict and the one remaining missing item, if any
Public scale is not ready until a new player can determine in minutes whether they can join a beginner run without first installing a Windows desktop client.
"""


def _role_kits_doc() -> str:
    return """# Role kits

They are governed starter decisions that reduce cognitive load while staying rule-environment aware and explainable.
* Ready for Tonight
* what can I safely swap
"""


def _role_kit_registry() -> dict:
    rows = []
    for role_kit_id in (
        "street_sam_starter",
        "face_starter",
        "mage_starter",
        "decker_starter",
        "rigger_starter",
        "general_survivor_starter",
    ):
        rows.append(
            {
                "id": role_kit_id,
                "audience": "beginner_or_returning_player",
                "must_answer": [
                    "why_this_role",
                    "why_this_loadout",
                    "what_is_missing_for_tonight",
                    "what_changes_under_rule_environment",
                ],
            }
        )
    return {"role_kits": rows}


def _source_aware_explain() -> str:
    return """# Source-aware explain

This file promotes source-aware explain from a useful feature to a public trust promise.
No cloud rulebook upload is required.
Every important visible mechanical value should either open the packet-backed explain drawer plus source anchor chain or remain an explicit release-blocking gap.
"""


def _campaign_adoption() -> str:
    return """# Campaign adoption

Chummer should let a table start from current truth.
* adoption receipt and replay-safe start anchor
* mark what you do not know
"""


def _foundry_first() -> str:
    return """# Foundry first

`one runner -> one opposition packet -> one player-safe handout -> one export receipt`
Chummer remains the canonical truth.
* not making Foundry canonical
"""


def _vtt_export_target_acceptance() -> dict:
    return {
        "artifact": "vtt_export_target_acceptance",
        "primary_target": {
            "id": "foundry_first",
            "kind": "structured_projection",
            "required_proofs": [
                "runner_export",
                "opposition_packet_export",
                "player_safe_handout_export",
                "visible_export_receipt_or_failure",
            ],
            "authority_rule": {"chummer_is_truth": True, "target_is_projection_only": True},
        },
        "secondary_targets": [{"id": "pdf_handoff"}],
    }


def _faq_md() -> str:
    return """# FAQ

### Would I need a Windows PC to join a run?

No. The intended direction is that browsing runs, applying with a quickstart or approved runner, acknowledging table expectations, and receiving scheduling and handoff details should work without assuming a Windows-only setup.

### Is Chummer trying to replace Discord or VTTs?

No. The intended posture is that Chummer owns rules, applications, scheduling records, and world consequences, while Discord, Teams, and VTTs remain play or communication surfaces.
"""


def _faq_registry() -> dict:
    return {
        "sections": [
            {
                "id": "participation_and_preview",
                "entries": [
                    {
                        "question": "Would I need a Windows PC to join a run?",
                        "answer": "No. The intended direction is that browsing runs, applying with a quickstart or approved runner, acknowledging table expectations, and receiving scheduling and handoff details should work without assuming a Windows-only setup.",
                    },
                    {
                        "question": "Is Chummer trying to replace Discord or VTTs?",
                        "answer": "No. The intended posture is that Chummer owns rules, applications, scheduling records, and world consequences, while Discord, Teams, and VTTs remain play or communication surfaces.",
                    },
                ],
            }
        ]
    }


def _community_hub() -> str:
    return """# COMMUNITY HUB

- Today: Future concept.
That is a core goal. Quickstart runners and mobile-first application paths should reduce the Windows-only chokepoint.
No. Chummer owns campaign logic. Discord can remain the community and meeting surface.
"""


def _open_run_journey() -> str:
    return """# Find and join an open run

Status: future_slice_with_bounded_research
* A mobile-first player can apply through a quickstart path without a Windows-only requirement.
* If scheduling or meeting handoff drift occurs, Chummer-owned receipts must win and the fix must be visible as a projection repair, not silent data disagreement.
"""


def _public_feature_registry(*, overclaim: bool) -> dict:
    cards = [
        {
            "id": "lane_player",
            "title": "Player",
            "summary": "Build a clean dossier and understand every number.",
            "href": "/downloads",
            "badge": "Available now",
        }
    ]
    if overclaim:
        cards.append(
            {
                "id": "ready_for_tonight_card",
                "title": "Ready for Tonight",
                "summary": "Get a live ready-for-tonight verdict now.",
                "href": "/ready-for-tonight",
                "badge": "Live now",
            }
        )
    return {"cards": cards}


def _public_landing_manifest(*, overclaim: bool) -> dict:
    public_routes = [
        {"path": "/faq", "purpose": "support_entry", "must_exist": True},
        {"path": "/roadmap/community-hub", "purpose": "roadmap_detail", "must_exist": True},
    ]
    if overclaim:
        public_routes.append({"path": "/ready-for-tonight", "purpose": "artifact_detail", "must_exist": True})
    return {"public_routes": public_routes, "auth_routes": [], "registered_routes": []}


def _flagship_readiness(*, ready: bool) -> dict:
    return {
        "status": "pass",
        "generated_at": "2026-05-05T12:00:00Z",
        "readiness_planes": {"flagship_ready": {"status": "ready" if ready else "blocked"}},
    }


def _hero_path_projections() -> dict:
    return {
        "contract_name": "fleet.next90_m138_hero_path_projections",
        "status": "pass",
        "generated_at": "2026-05-05T12:00:00Z",
        "projections": {
            "newcomer_path": {"status": "pass", "truth_sources": ["journey.find_and_join_open_run", "public_faq.no_windows_needed"]},
            "ready_for_tonight": {"status": "pass", "truth_sources": ["ready_for_tonight_gates.player_readiness_verdict"]},
            "adoption_confidence": {"status": "pass", "truth_sources": ["campaign_adoption.start_from_today"]},
            "foundry_first_handoff": {"status": "pass", "truth_sources": ["vtt_export_target_acceptance.primary_target"]},
        },
    }


def _fixture_tree(tmp_path: Path, *, projection_present: bool, overclaim_public: bool, flagship_ready: bool) -> dict[str, Path]:
    registry = tmp_path / "registry.yaml"
    fleet_queue = tmp_path / "fleet_queue.yaml"
    design_queue = tmp_path / "design_queue.yaml"
    next90_guide = tmp_path / "guide.md"
    roadmap = tmp_path / "roadmap.md"
    ready_for_tonight_mode = tmp_path / "ready_for_tonight_mode.md"
    ready_for_tonight_gates = tmp_path / "ready_for_tonight_gates.yaml"
    public_onboarding_paths = tmp_path / "public_onboarding.md"
    role_kits_doc = tmp_path / "role_kits.md"
    role_kit_registry = tmp_path / "role_kits.yaml"
    source_aware_explain = tmp_path / "source_aware_explain.md"
    campaign_adoption = tmp_path / "campaign_adoption.md"
    foundry_first = tmp_path / "foundry_first.md"
    vtt_export_target_acceptance = tmp_path / "vtt_export.yaml"
    public_faq = tmp_path / "FAQ.md"
    public_faq_registry = tmp_path / "public_faq_registry.yaml"
    community_hub = tmp_path / "community-hub.md"
    open_run_journey = tmp_path / "find-and-join-an-open-run.md"
    public_feature_registry = tmp_path / "public_feature_registry.yaml"
    public_landing_manifest = tmp_path / "public_landing_manifest.yaml"
    flagship = tmp_path / "flagship.json"
    hero_path_projections = tmp_path / "hero_path_projections.json"

    _write_yaml(registry, _registry())
    _write_yaml(fleet_queue, {"items": [_queue_item()]})
    _write_yaml(design_queue, {"items": [_queue_item()]})
    _write_text(next90_guide, _next90_guide())
    _write_text(roadmap, _roadmap())
    _write_text(ready_for_tonight_mode, _ready_for_tonight_mode())
    _write_yaml(ready_for_tonight_gates, _ready_for_tonight_gates())
    _write_text(public_onboarding_paths, _public_onboarding_paths())
    _write_text(role_kits_doc, _role_kits_doc())
    _write_yaml(role_kit_registry, _role_kit_registry())
    _write_text(source_aware_explain, _source_aware_explain())
    _write_text(campaign_adoption, _campaign_adoption())
    _write_text(foundry_first, _foundry_first())
    _write_yaml(vtt_export_target_acceptance, _vtt_export_target_acceptance())
    _write_text(public_faq, _faq_md())
    _write_yaml(public_faq_registry, _faq_registry())
    _write_text(community_hub, _community_hub())
    _write_text(open_run_journey, _open_run_journey())
    _write_yaml(public_feature_registry, _public_feature_registry(overclaim=overclaim_public))
    _write_yaml(public_landing_manifest, _public_landing_manifest(overclaim=overclaim_public))
    _write_json(flagship, _flagship_readiness(ready=flagship_ready))
    if projection_present:
        _write_json(hero_path_projections, _hero_path_projections())

    return {
        "registry": registry,
        "fleet_queue": fleet_queue,
        "design_queue": design_queue,
        "next90_guide": next90_guide,
        "roadmap": roadmap,
        "ready_for_tonight_mode": ready_for_tonight_mode,
        "ready_for_tonight_gates": ready_for_tonight_gates,
        "public_onboarding_paths": public_onboarding_paths,
        "role_kits_doc": role_kits_doc,
        "role_kit_registry": role_kit_registry,
        "source_aware_explain": source_aware_explain,
        "campaign_adoption": campaign_adoption,
        "foundry_first": foundry_first,
        "vtt_export_target_acceptance": vtt_export_target_acceptance,
        "public_faq": public_faq,
        "public_faq_registry": public_faq_registry,
        "community_hub": community_hub,
        "open_run_journey": open_run_journey,
        "public_feature_registry": public_feature_registry,
        "public_landing_manifest": public_landing_manifest,
        "flagship": flagship,
        "hero_path_projections": hero_path_projections,
    }


class MaterializeNext90M138FleetHeroPathCloseoutGatesTest(unittest.TestCase):
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
                str(fixture["next90_guide"]),
                "--roadmap",
                str(fixture["roadmap"]),
                "--ready-for-tonight-mode",
                str(fixture["ready_for_tonight_mode"]),
                "--ready-for-tonight-gates",
                str(fixture["ready_for_tonight_gates"]),
                "--public-onboarding-paths",
                str(fixture["public_onboarding_paths"]),
                "--role-kits-and-starter-loadouts",
                str(fixture["role_kits_doc"]),
                "--role-kit-registry",
                str(fixture["role_kit_registry"]),
                "--source-aware-explain",
                str(fixture["source_aware_explain"]),
                "--campaign-adoption-flow",
                str(fixture["campaign_adoption"]),
                "--foundry-first-handoff",
                str(fixture["foundry_first"]),
                "--vtt-export-target-acceptance",
                str(fixture["vtt_export_target_acceptance"]),
                "--public-faq",
                str(fixture["public_faq"]),
                "--public-faq-registry",
                str(fixture["public_faq_registry"]),
                "--public-guide-community-hub",
                str(fixture["community_hub"]),
                "--open-run-journey",
                str(fixture["open_run_journey"]),
                "--public-feature-registry",
                str(fixture["public_feature_registry"]),
                "--public-landing-manifest",
                str(fixture["public_landing_manifest"]),
                "--flagship-readiness",
                str(fixture["flagship"]),
                "--hero-path-projections",
                str(fixture["hero_path_projections"]),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn('"status"', completed.stdout)
        return json.loads(artifact.read_text(encoding="utf-8"))

    def test_materializer_blocks_runtime_when_projection_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path, projection_present=False, overclaim_public=False, flagship_ready=True)
            artifact = tmp_path / "artifact.json"
            markdown = tmp_path / "artifact.md"
            payload = self._run_materializer(fixture, artifact, markdown)

        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["monitor_summary"]["hero_path_closeout_status"], "blocked")
        self.assertTrue(
            any("Machine-readable hero-path projections artifact is missing." in item for item in payload["monitor_summary"]["runtime_blockers"])
        )
        self.assertTrue(
            any("FLAGSHIP_PRODUCT_READINESS still reports flagship_ready" in item for item in payload["monitor_summary"]["runtime_blockers"])
        )

    def test_materializer_passes_when_projection_and_public_posture_are_aligned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path, projection_present=True, overclaim_public=False, flagship_ready=True)
            artifact = tmp_path / "artifact.json"
            markdown = tmp_path / "artifact.md"
            payload = self._run_materializer(fixture, artifact, markdown)

        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["monitor_summary"]["hero_path_closeout_status"], "pass")
        self.assertEqual(payload["monitor_summary"]["runtime_blocker_count"], 0)

    def test_split_queue_yaml_fallback_preserves_queue_alignment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path, projection_present=True, overclaim_public=False, flagship_ready=True)
            queue_item = _queue_item()
            _write_split_queue_yaml(fixture["fleet_queue"], queue_item)
            _write_split_queue_yaml(fixture["design_queue"], queue_item)
            artifact = tmp_path / "artifact.json"
            markdown = tmp_path / "artifact.md"
            payload = self._run_materializer(fixture, artifact, markdown)

        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["canonical_monitors"]["queue_alignment"]["state"], "pass")
        self.assertEqual(payload["package_closeout"]["state"], "pass")


if __name__ == "__main__":
    unittest.main()
