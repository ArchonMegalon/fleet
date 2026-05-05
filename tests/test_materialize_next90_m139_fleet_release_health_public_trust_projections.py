from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


SCRIPT = Path("/docker/fleet/scripts/materialize_next90_m139_fleet_release_health_public_trust_projections.py")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _registry() -> dict:
    return {"milestones": [{"id": 139, "work_tasks": [{"id": "139.10", "owner": "fleet"}]}]}


def _queue_item() -> dict:
    return {
        "title": "Bind COMMUNITY_SAFETY_EVENT_AND_APPEAL_STATES, WORLD_BROADCAST_RECIPE_REGISTRY, CREATOR_PUBLICATION_ANALYTICS_SCHEMA, and ACCESSIBILITY_COGNITIVE_LOAD_GATES into machine-readable release-health and public-trust projections.",
        "task": "Bind COMMUNITY_SAFETY_EVENT_AND_APPEAL_STATES, WORLD_BROADCAST_RECIPE_REGISTRY, CREATOR_PUBLICATION_ANALYTICS_SCHEMA, and ACCESSIBILITY_COGNITIVE_LOAD_GATES into machine-readable release-health and public-trust projections.",
        "package_id": "next90-m139-fleet-bind-community-safety-event-and-appeal-states-world-broadcast-recipe-r",
        "milestone_id": 139,
        "work_task_id": "139.10",
        "frontier_id": 2565904250,
        "wave": "W26",
        "repo": "fleet",
        "allowed_paths": ["scripts", "tests", ".codex-studio", "feedback"],
        "owned_surfaces": ["bind_community_safety_event_and_appeal_states_world_broa:fleet"],
    }


def _fixture_tree(tmp_path: Path) -> dict[str, Path]:
    registry = tmp_path / "registry.yaml"
    fleet_queue = tmp_path / "fleet_queue.yaml"
    design_queue = tmp_path / "design_queue.yaml"
    guide = tmp_path / "guide.md"
    prep = tmp_path / "prep.md"
    opposition = tmp_path / "opposition.yaml"
    broadcast = tmp_path / "broadcast.md"
    broadcast_registry = tmp_path / "broadcast_registry.yaml"
    safety_doc = tmp_path / "safety.md"
    safety_states = tmp_path / "safety_states.yaml"
    creator_doc = tmp_path / "creator.md"
    creator_schema = tmp_path / "creator_schema.yaml"
    creator_policy = tmp_path / "creator_policy.md"
    product_analytics = tmp_path / "analytics.md"
    accessibility_doc = tmp_path / "accessibility.md"
    accessibility_gates = tmp_path / "accessibility_gates.yaml"
    faq_registry = tmp_path / "faq_registry.yaml"
    feature_registry = tmp_path / "feature_registry.yaml"
    landing = tmp_path / "landing.yaml"

    _write_yaml(registry, _registry())
    _write_yaml(fleet_queue, {"items": [_queue_item()]})
    _write_yaml(design_queue, {"items": [_queue_item()]})
    _write_text(guide, "## Wave 26 - make the world, creator, and trust loops feel lived-in\n### 139. GM tonight pack, world broadcast cadence, creator analytics, community safety, and cognitive-load trust closure\n")
    _write_text(prep, "It should begin with one usable packet a GM can run tonight.\none job\ngm_creates_a_playable_prep_packet\n")
    _write_yaml(
        opposition,
        {
            "packet_families": [
                {"id": "ganger_squad"},
                {"id": "corp_security_team"},
                {"id": "spirit_cell"},
                {"id": "drone_team"},
                {"id": "beginner_one_shot_bundle"},
            ]
        },
    )
    _write_text(broadcast, "Broadcasts are projections of approved truth, not independent fiction.\n* one city ticker\n* `ResolutionReport`\n")
    _write_yaml(
        broadcast_registry,
        {
            "recipes": [
                {"id": "weekly_city_ticker", "source_objects": ["WorldTick", "NewsItem"]},
                {"id": "faction_spin_card", "source_objects": ["ResolutionReport", "WorldTick"]},
                {"id": "gm_job_digest", "source_objects": ["JobPacket", "IntelReport"]},
                {"id": "public_safe_media_card", "source_objects": ["NewsItem", "WorldTick"]},
                {"id": "recruitment_or_announcement_packet", "source_objects": ["OpenRun", "NewsItem"]},
            ]
        },
    )
    _write_text(safety_doc, "* observer-consent violation\n* a `CommunityScaleAuditPacket` or linked support-case receipt\nThey do not become support closure truth, release truth, or hidden organizer superpowers.\n")
    _write_yaml(
        safety_states,
        {
            "event_families": [
                "no_show",
                "unsafe_content",
                "harassment",
                "spoiler_leak",
                "application_dispute",
                "gm_or_organizer_escalation",
                "faction_or_leaderboard_gaming",
                "observer_consent_violation",
            ],
            "states": ["reported", "triaged", "evidence_requested", "temporary_action", "resolved", "appealed", "closed"],
            "required_fields": [
                "reporter_visibility",
                "subject_visibility",
                "evidence_posture",
                "retention_posture",
                "publication_posture",
                "appeal_deadline",
            ],
        },
    )
    _write_text(creator_doc, "Trust-ranking language must stay about discoverability order, not creator virtue or platform safety.\n* use moderation status as a proxy for compatibility\nThey must not expose private campaign names, private runner identities, or sensitive play telemetry.\n")
    _write_yaml(
        creator_schema,
        {
            "fields": [{"id": field_id} for field_id in (
                "compatibility_posture",
                "moderation_status",
                "trust_ranking_posture",
                "trust_ranking_reason_chips",
                "adoption_band",
                "update_request_count_band",
                "support_issue_count_band",
                "media_collateral_status",
            )],
            "privacy_rules": [
                "no_private_campaign_names",
                "no_private_runner_names",
                "no_raw_character_sheet_warehouse",
                "no_sensitive_session_telemetry_exposure",
            ],
            "claim_guards": [
                "compatibility_posture_must_not_be_inferred_from_moderation_status",
                "moderation_status_must_not_claim_build_or_rule_environment_fit",
                "trust_ranking_posture_must_not_claim_creator_endorsement_or_platform_safety",
                "adoption_and_support_fields_must_be_banded_before_public_exposure",
                "unknown_compatibility_must_stay_visible_until_receipts_are_current",
            ],
        },
    )
    _write_text(creator_policy, "## Truth order\nIf compatibility receipts are stale or missing, the product must say compatibility is unknown.\n* present trust ranking as a platform safety certification or social credit score\n")
    _write_text(product_analytics, "Hub owns journey receipts. Analytics tools observe and aggregate. Product Governor interprets.\nDo not collect raw character sheets, campaign notes, private runner state, support payloads, raw transcripts, or sourcebook text for analytics.\n")
    _write_text(accessibility_doc, "* keyboard-first dense workflows where the product claims expert speed\n* mobile glanceability for recap, readiness, and consequence moments\n* what matters right now\n")
    _write_yaml(
        accessibility_gates,
        {
            "gates": [
                {"id": "keyboard_first_expert_workflow", "required_surfaces": ["flagship_desktop_workbench", "dense_builder", "ready_for_tonight"]},
                {"id": "warning_and_legality_clarity", "required_surfaces": ["build_lab", "explain_drawer", "run_application_preflight"]},
                {"id": "reduced_motion_safe_critical_flows", "required_surfaces": ["install_and_first_run", "recovery_and_restore", "recap_and_return_moment"]},
                {"id": "screen_reader_safe_trust_surfaces", "required_surfaces": ["install_help", "explain", "recovery", "support"]},
                {"id": "mobile_glanceability", "required_surfaces": ["recap", "ready_for_tonight", "consequence_feed"]},
            ]
        },
    )
    _write_yaml(
        faq_registry,
        {
            "sections": [
                {"entries": [
                    {"question": "Can I participate privately?", "answer": "Public recognition should remain opt-in, and private participation should still be possible."},
                    {"question": "What are badges and leaderboards for?", "answer": "They are recognition and visibility features, not authority."},
                ]}
            ]
        },
    )
    _write_yaml(
        feature_registry,
        {
            "cards": [
                {"id": "lane_creator", "title": "Creator", "badge": "Preview lane"},
                {"id": "horizon_community_hub", "title": "COMMUNITY HUB", "badge": "Research"},
                {"id": "horizon_black_ledger", "title": "BLACK LEDGER", "badge": "Research"},
                {"id": "productlift_feedback", "title": "Public feedback board", "badge": "Public"},
                {"id": "productlift_roadmap", "title": "Public roadmap projection", "badge": "Projection"},
                {"id": "productlift_changelog", "title": "User-requested changelog", "badge": "Closeout"},
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
    return {
        "registry": registry,
        "fleet_queue": fleet_queue,
        "design_queue": design_queue,
        "guide": guide,
        "prep": prep,
        "opposition": opposition,
        "broadcast": broadcast,
        "broadcast_registry": broadcast_registry,
        "safety_doc": safety_doc,
        "safety_states": safety_states,
        "creator_doc": creator_doc,
        "creator_schema": creator_schema,
        "creator_policy": creator_policy,
        "product_analytics": product_analytics,
        "accessibility_doc": accessibility_doc,
        "accessibility_gates": accessibility_gates,
        "faq_registry": faq_registry,
        "feature_registry": feature_registry,
        "landing": landing,
    }


class MaterializeNext90M139FleetReleaseHealthPublicTrustProjectionsTest(unittest.TestCase):
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
                    "--output", str(artifact),
                    "--markdown-output", str(markdown),
                    "--successor-registry", str(fixture["registry"]),
                    "--fleet-queue-staging", str(fixture["fleet_queue"]),
                    "--design-queue-staging", str(fixture["design_queue"]),
                    "--next90-guide", str(fixture["guide"]),
                    "--prep-packet-factory", str(fixture["prep"]),
                    "--opposition-packet-registry", str(fixture["opposition"]),
                    "--world-broadcast-cadence", str(fixture["broadcast"]),
                    "--world-broadcast-recipe-registry", str(fixture["broadcast_registry"]),
                    "--community-safety-doc", str(fixture["safety_doc"]),
                    "--community-safety-states", str(fixture["safety_states"]),
                    "--creator-analytics-doc", str(fixture["creator_doc"]),
                    "--creator-analytics-schema", str(fixture["creator_schema"]),
                    "--creator-trust-policy", str(fixture["creator_policy"]),
                    "--product-analytics-model", str(fixture["product_analytics"]),
                    "--accessibility-release-bar", str(fixture["accessibility_doc"]),
                    "--accessibility-gates", str(fixture["accessibility_gates"]),
                    "--public-faq-registry", str(fixture["faq_registry"]),
                    "--public-feature-registry", str(fixture["feature_registry"]),
                    "--public-landing-manifest", str(fixture["landing"]),
                ],
                check=True,
            )
            payload = json.loads(artifact.read_text(encoding="utf-8"))

        self.assertEqual(payload["status"], "pass")
        self.assertEqual(sorted(payload["projections"]), [
            "accessibility_cognitive_load",
            "community_safety_moderation",
            "creator_analytics_bounds",
            "tonight_pack",
            "world_broadcast_cadence",
        ])
        self.assertEqual(
            payload["public_truth_projection"]["public_card_postures"]["lane_creator"]["badge"],
            "Preview lane",
        )

    def test_materializer_blocks_when_public_trust_inputs_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path)
            bad_faq = yaml.safe_load(fixture["faq_registry"].read_text(encoding="utf-8"))
            bad_faq["sections"][0]["entries"][0]["answer"] = "Recognition is mandatory."
            _write_yaml(fixture["faq_registry"], bad_faq)
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
                    "--prep-packet-factory", str(fixture["prep"]),
                    "--opposition-packet-registry", str(fixture["opposition"]),
                    "--world-broadcast-cadence", str(fixture["broadcast"]),
                    "--world-broadcast-recipe-registry", str(fixture["broadcast_registry"]),
                    "--community-safety-doc", str(fixture["safety_doc"]),
                    "--community-safety-states", str(fixture["safety_states"]),
                    "--creator-analytics-doc", str(fixture["creator_doc"]),
                    "--creator-analytics-schema", str(fixture["creator_schema"]),
                    "--creator-trust-policy", str(fixture["creator_policy"]),
                    "--product-analytics-model", str(fixture["product_analytics"]),
                    "--accessibility-release-bar", str(fixture["accessibility_doc"]),
                    "--accessibility-gates", str(fixture["accessibility_gates"]),
                    "--public-faq-registry", str(fixture["faq_registry"]),
                    "--public-feature-registry", str(fixture["feature_registry"]),
                    "--public-landing-manifest", str(fixture["landing"]),
                ],
                check=True,
            )
            payload = json.loads(artifact.read_text(encoding="utf-8"))

        self.assertEqual(payload["status"], "blocked")
        self.assertTrue(
            any("public_faq_registry:" in blocker for blocker in payload["package_closeout"]["blockers"])
        )


if __name__ == "__main__":
    unittest.main()
