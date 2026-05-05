from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


SCRIPT = Path("/docker/fleet/scripts/materialize_next90_m139_fleet_operational_trust_closeout_gates.py")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _registry() -> dict:
    return {"milestones": [{"id": 139, "work_tasks": [{"id": "139.9", "owner": "fleet"}]}]}


def _queue_item() -> dict:
    return {
        "title": "Fail closeout when tonight-pack proof, broadcast cadence proof, moderation and appeals states, creator analytics bounds, or accessibility and cognitive-load gates are stale, missing, or contradictory.",
        "task": "Fail closeout when tonight-pack proof, broadcast cadence proof, moderation and appeals states, creator analytics bounds, or accessibility and cognitive-load gates are stale, missing, or contradictory.",
        "package_id": "next90-m139-fleet-fail-closeout-when-tonight-pack-proof-broadcast-cadence-proof-moderati",
        "milestone_id": 139,
        "work_task_id": "139.9",
        "frontier_id": 3411981369,
        "wave": "W26",
        "repo": "fleet",
        "allowed_paths": ["scripts", "tests", ".codex-studio", "feedback"],
        "owned_surfaces": ["fail_closeout_when_tonight_pack_proof_broadcast_cadence:fleet"],
    }


def _projection_artifact() -> dict:
    return {
        "contract_name": "fleet.next90_m139_release_health_public_trust_projections",
        "generated_at": "2026-05-05T12:00:00Z",
        "status": "pass",
        "projections": {
            "tonight_pack": {"status": "pass", "truth_sources": ["prep_packet_factory.first_proof"]},
            "world_broadcast_cadence": {"status": "pass", "truth_sources": ["world_broadcast_recipe_registry.recipes"]},
            "community_safety_moderation": {"status": "pass", "truth_sources": ["community_safety_event_and_appeal_states"]},
            "creator_analytics_bounds": {"status": "pass", "truth_sources": ["creator_publication_analytics_schema.fields"]},
            "accessibility_cognitive_load": {"status": "pass", "truth_sources": ["accessibility_cognitive_load_gates"]},
        },
        "package_closeout": {"warnings": []},
    }


def _fixture_tree(tmp_path: Path) -> dict[str, Path]:
    published = tmp_path / "published"
    registry = tmp_path / "registry.yaml"
    fleet_queue = tmp_path / "fleet_queue.yaml"
    design_queue = tmp_path / "design_queue.yaml"
    guide = tmp_path / "guide.md"
    prep = tmp_path / "prep.md"
    broadcast = tmp_path / "broadcast.md"
    safety_doc = tmp_path / "safety.md"
    creator_doc = tmp_path / "creator.md"
    accessibility_doc = tmp_path / "accessibility.md"
    faq_md = tmp_path / "faq.md"
    faq_registry = tmp_path / "faq_registry.yaml"
    feature_registry = tmp_path / "feature_registry.yaml"
    landing = tmp_path / "landing.yaml"
    flagship = tmp_path / "flagship.json"
    projections = tmp_path / "projections.json"

    _write_yaml(registry, _registry())
    _write_yaml(fleet_queue, {"items": [_queue_item()]})
    _write_yaml(design_queue, {"items": [_queue_item()]})
    _write_text(
        guide,
        "## Wave 26 - make the world, creator, and trust loops feel lived-in\n"
        "### 139. GM tonight pack, world broadcast cadence, creator analytics, community safety, and cognitive-load trust closure\n"
        "Exit: a GM can assemble tonight's governed pack, the world can talk back on a weekly cadence, creators can see bounded adoption feedback, moderation and appeals exist before public scale, and accessibility plus cognitive-load gates are release-bound truths.\n",
    )
    _write_text(prep, "It should begin with one usable packet a GM can run tonight.\none job\ngm_creates_a_playable_prep_packet\n")
    _write_text(broadcast, "Broadcasts are projections of approved truth, not independent fiction.\n* one city ticker\n* `ResolutionReport`\n")
    _write_text(
        safety_doc,
        "* observer-consent violation\n* a `CommunityScaleAuditPacket` or linked support-case receipt\nThey do not become support closure truth, release truth, or hidden organizer superpowers.\n",
    )
    _write_text(
        creator_doc,
        "Trust-ranking language must stay about discoverability order, not creator virtue or platform safety.\n* use moderation status as a proxy for compatibility\nThey must not expose private campaign names, private runner identities, or sensitive play telemetry.\n",
    )
    _write_text(
        accessibility_doc,
        "* keyboard-first dense workflows where the product claims expert speed\n* mobile glanceability for recap, readiness, and consequence moments\n* what matters right now\n",
    )
    _write_text(faq_md, "### Can I participate privately?\nYes.\n### What are badges and leaderboards for?\nVisibility.\n")
    _write_yaml(
        faq_registry,
        {
            "sections": [
                {
                    "entries": [
                        {"question": "Can I participate privately?", "answer": "Public recognition should remain opt-in, and private participation should still be possible."},
                        {"question": "What are badges and leaderboards for?", "answer": "They are recognition and visibility features, not authority."},
                    ]
                }
            ]
        },
    )
    _write_yaml(
        feature_registry,
        {
            "cards": [
                {"id": "lane_creator", "badge": "Preview lane"},
                {"id": "horizon_community_hub", "badge": "Research"},
                {"id": "horizon_black_ledger", "badge": "Research"},
                {"id": "productlift_feedback", "badge": "Public"},
                {"id": "productlift_roadmap", "badge": "Projection"},
                {"id": "productlift_changelog", "badge": "Closeout"},
            ]
        },
    )
    _write_yaml(
        landing,
        {
            "public_routes": [
                {"path": "/artifacts", "purpose": "teaser_gallery"},
                {"path": "/roadmap/community-hub", "purpose": "roadmap_detail"},
                {"path": "/roadmap/black-ledger", "purpose": "roadmap_detail"},
                {"path": "/feedback", "purpose": "public_feedback_entry"},
                {"path": "/roadmap", "purpose": "horizon_summary"},
                {"path": "/changelog", "purpose": "release_history"},
            ]
        },
    )
    _write_json(
        flagship,
        {
            "generated_at": "2026-05-05T12:00:00Z",
            "status": "pass",
            "readiness_planes": {"flagship_ready": {"status": "ready"}},
        },
    )
    _write_json(projections, _projection_artifact())
    return {
        "published": published,
        "registry": registry,
        "fleet_queue": fleet_queue,
        "design_queue": design_queue,
        "guide": guide,
        "prep": prep,
        "broadcast": broadcast,
        "safety_doc": safety_doc,
        "creator_doc": creator_doc,
        "accessibility_doc": accessibility_doc,
        "faq_md": faq_md,
        "faq_registry": faq_registry,
        "feature_registry": feature_registry,
        "landing": landing,
        "flagship": flagship,
        "projections": projections,
    }


class MaterializeNext90M139FleetOperationalTrustCloseoutGatesTest(unittest.TestCase):
    def test_materializer_emits_warning_gate_when_public_truth_is_bounded_but_dedicated_proofs_are_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path)
            artifact = tmp_path / "artifact.json"
            markdown = tmp_path / "artifact.md"
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--output", str(artifact),
                    "--markdown-output", str(markdown),
                    "--published-root", str(fixture["published"]),
                    "--successor-registry", str(fixture["registry"]),
                    "--fleet-queue-staging", str(fixture["fleet_queue"]),
                    "--design-queue-staging", str(fixture["design_queue"]),
                    "--next90-guide", str(fixture["guide"]),
                    "--prep-packet-factory", str(fixture["prep"]),
                    "--world-broadcast-cadence", str(fixture["broadcast"]),
                    "--community-safety-doc", str(fixture["safety_doc"]),
                    "--creator-analytics-doc", str(fixture["creator_doc"]),
                    "--accessibility-release-bar", str(fixture["accessibility_doc"]),
                    "--public-faq", str(fixture["faq_md"]),
                    "--public-faq-registry", str(fixture["faq_registry"]),
                    "--public-feature-registry", str(fixture["feature_registry"]),
                    "--public-landing-manifest", str(fixture["landing"]),
                    "--flagship-readiness", str(fixture["flagship"]),
                    "--release-health-public-trust-projections", str(fixture["projections"]),
                ],
                check=True,
            )
            payload = json.loads(artifact.read_text(encoding="utf-8"))

        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["monitor_summary"]["operational_trust_closeout_status"], "warning")
        self.assertEqual(payload["monitor_summary"]["runtime_blocker_count"], 0)
        self.assertTrue(any("No dedicated published `tonight_pack` proof artifact" in warning for warning in payload["package_closeout"]["warnings"]))

    def test_materializer_blocks_runtime_when_public_badge_overclaims(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path)
            bad_registry = yaml.safe_load(fixture["feature_registry"].read_text(encoding="utf-8"))
            bad_registry["cards"][0]["badge"] = "Available now"
            _write_yaml(fixture["feature_registry"], bad_registry)
            artifact = tmp_path / "artifact.json"
            markdown = tmp_path / "artifact.md"
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--output", str(artifact),
                    "--markdown-output", str(markdown),
                    "--published-root", str(fixture["published"]),
                    "--successor-registry", str(fixture["registry"]),
                    "--fleet-queue-staging", str(fixture["fleet_queue"]),
                    "--design-queue-staging", str(fixture["design_queue"]),
                    "--next90-guide", str(fixture["guide"]),
                    "--prep-packet-factory", str(fixture["prep"]),
                    "--world-broadcast-cadence", str(fixture["broadcast"]),
                    "--community-safety-doc", str(fixture["safety_doc"]),
                    "--creator-analytics-doc", str(fixture["creator_doc"]),
                    "--accessibility-release-bar", str(fixture["accessibility_doc"]),
                    "--public-faq", str(fixture["faq_md"]),
                    "--public-faq-registry", str(fixture["faq_registry"]),
                    "--public-feature-registry", str(fixture["feature_registry"]),
                    "--public-landing-manifest", str(fixture["landing"]),
                    "--flagship-readiness", str(fixture["flagship"]),
                    "--release-health-public-trust-projections", str(fixture["projections"]),
                ],
                check=True,
            )
            payload = json.loads(artifact.read_text(encoding="utf-8"))

        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["monitor_summary"]["operational_trust_closeout_status"], "blocked")
        self.assertTrue(any("PUBLIC_FEATURE_REGISTRY `lane_creator` badge drifted" in blocker for blocker in payload["monitor_summary"]["runtime_blockers"]))


if __name__ == "__main__":
    unittest.main()
