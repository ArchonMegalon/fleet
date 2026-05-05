from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


SCRIPT = Path("/docker/fleet/scripts/materialize_next90_m138_fleet_hero_path_projections.py")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    _write_text(path, json.dumps(payload, indent=2) + "\n")


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _registry() -> dict:
    return {
        "milestones": [
            {
                "id": 138,
                "title": "First emotional wins, no-desktop participation, and adoption confidence closure",
                "work_tasks": [
                    {
                        "id": "138.10",
                        "owner": "fleet",
                        "title": "Bind READY_FOR_TONIGHT_GATES, ROLE_KIT_REGISTRY, VTT_EXPORT_TARGET_ACCEPTANCE, and related newcomer-path proof into machine-readable readiness and public-truth projections.",
                    }
                ],
            }
        ]
    }


def _queue_item() -> dict:
    return {
        "title": "Bind READY_FOR_TONIGHT_GATES, ROLE_KIT_REGISTRY, VTT_EXPORT_TARGET_ACCEPTANCE, and related newcomer-path proof into machine-readable readiness and public-truth projections.",
        "task": "Bind READY_FOR_TONIGHT_GATES, ROLE_KIT_REGISTRY, VTT_EXPORT_TARGET_ACCEPTANCE, and related newcomer-path proof into machine-readable readiness and public-truth projections.",
        "package_id": "next90-m138-fleet-bind-ready-for-tonight-gates-role-kit-registry-vtt-export-target-accep",
        "milestone_id": 138,
        "work_task_id": "138.10",
        "frontier_id": 7914546694,
        "wave": "W25",
        "repo": "fleet",
        "allowed_paths": ["scripts", "tests", ".codex-studio", "feedback"],
        "owned_surfaces": ["bind_ready_for_tonight_gates_role_kit_registry_vtt_expor:fleet"],
    }


def _fixture_tree(tmp_path: Path) -> dict[str, Path]:
    registry = tmp_path / "registry.yaml"
    fleet_queue = tmp_path / "fleet_queue.yaml"
    design_queue = tmp_path / "design_queue.yaml"
    next90_guide = tmp_path / "guide.md"
    ready_for_tonight_gates = tmp_path / "gates.yaml"
    public_onboarding = tmp_path / "onboarding.md"
    role_kit_registry = tmp_path / "role_kits.yaml"
    source_aware_explain = tmp_path / "explain.md"
    campaign_adoption = tmp_path / "adoption.md"
    foundry = tmp_path / "foundry.md"
    vtt_acceptance = tmp_path / "vtt.yaml"
    public_faq_registry = tmp_path / "faq_registry.yaml"
    community_hub = tmp_path / "community_hub.md"
    open_run_journey = tmp_path / "journey.md"
    public_feature_registry = tmp_path / "feature_registry.yaml"
    public_landing_manifest = tmp_path / "landing_manifest.yaml"

    _write_yaml(registry, _registry())
    _write_yaml(fleet_queue, {"items": [_queue_item()]})
    _write_yaml(design_queue, {"items": [_queue_item()]})
    _write_text(
        next90_guide,
        "## Wave 25 - turn first emotional wins into release-gated product truth\n### 138. First emotional wins, no-desktop participation, and adoption confidence closure\n",
    )
    _write_yaml(
        ready_for_tonight_gates,
        {
            "gates": [
                {"id": "player_readiness_verdict", "required_outputs": ["status", "blocking_reasons"]},
                {"id": "gm_readiness_verdict", "required_outputs": ["status", "export_readiness"]},
                {"id": "organizer_publishability_verdict", "required_outputs": ["status", "proof_receipts"]},
            ]
        },
    )
    _write_text(public_onboarding, "Desktop remains the expert flagship.\n")
    _write_yaml(
        role_kit_registry,
        {
            "role_kits": [{"id": role_kit_id} for role_kit_id in (
                "street_sam_starter",
                "face_starter",
                "mage_starter",
                "decker_starter",
                "rigger_starter",
                "general_survivor_starter",
            )]
        },
    )
    _write_text(source_aware_explain, "No cloud rulebook upload is required.\n")
    _write_text(campaign_adoption, "Chummer should let a table start from current truth.\n")
    _write_text(foundry, "Chummer remains the canonical truth.\n")
    _write_yaml(
        vtt_acceptance,
        {
            "primary_target": {
                "id": "foundry_first",
                "required_proofs": [
                    "runner_export",
                    "opposition_packet_export",
                    "player_safe_handout_export",
                    "visible_export_receipt_or_failure",
                ],
                "authority_rule": {"chummer_is_truth": True, "target_is_projection_only": True},
            }
        },
    )
    _write_yaml(
        public_faq_registry,
        {
            "sections": [
                {
                    "entries": [
                        {"question": "Would I need a Windows PC to join a run?", "answer": "Bounded answer."},
                        {"question": "Is Chummer trying to replace Discord or VTTs?", "answer": "Bounded answer."},
                    ]
                }
            ]
        },
    )
    _write_text(community_hub, "Future concept. Discord can remain the community and meeting surface.\n")
    _write_text(open_run_journey, "Windows-only requirement\n")
    _write_yaml(public_feature_registry, {"cards": []})
    _write_yaml(public_landing_manifest, {"public_routes": [{"path": "/faq"}, {"path": "/roadmap/community-hub"}]})
    return {
        "registry": registry,
        "fleet_queue": fleet_queue,
        "design_queue": design_queue,
        "next90_guide": next90_guide,
        "ready_for_tonight_gates": ready_for_tonight_gates,
        "public_onboarding": public_onboarding,
        "role_kit_registry": role_kit_registry,
        "source_aware_explain": source_aware_explain,
        "campaign_adoption": campaign_adoption,
        "foundry": foundry,
        "vtt_acceptance": vtt_acceptance,
        "public_faq_registry": public_faq_registry,
        "community_hub": community_hub,
        "open_run_journey": open_run_journey,
        "public_feature_registry": public_feature_registry,
        "public_landing_manifest": public_landing_manifest,
    }


class MaterializeNext90M138FleetHeroPathProjectionsTest(unittest.TestCase):
    def test_materializer_emits_projection_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path)
            artifact = tmp_path / "artifact.json"
            markdown = tmp_path / "artifact.md"
            subprocess.run(
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
                    "--ready-for-tonight-gates",
                    str(fixture["ready_for_tonight_gates"]),
                    "--public-onboarding-paths",
                    str(fixture["public_onboarding"]),
                    "--role-kit-registry",
                    str(fixture["role_kit_registry"]),
                    "--source-aware-explain",
                    str(fixture["source_aware_explain"]),
                    "--campaign-adoption-flow",
                    str(fixture["campaign_adoption"]),
                    "--foundry-first-handoff",
                    str(fixture["foundry"]),
                    "--vtt-export-target-acceptance",
                    str(fixture["vtt_acceptance"]),
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
                ],
                check=True,
            )
            payload = json.loads(artifact.read_text(encoding="utf-8"))

        self.assertEqual(payload["status"], "pass")
        self.assertEqual(sorted(payload["projections"]), [
            "adoption_confidence",
            "foundry_first_handoff",
            "newcomer_path",
            "ready_for_tonight",
        ])


if __name__ == "__main__":
    unittest.main()
