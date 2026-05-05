from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


SCRIPT = Path("/docker/fleet/scripts/materialize_next90_m140_fleet_portability_and_cadence_closeout_gates.py")


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
    return {"milestones": [{"id": 140, "work_tasks": [{"id": "140.9", "owner": "fleet"}]}]}


def _queue_item() -> dict:
    return {
        "title": "Fail closeout when runner-passport proof, weekly dispatch cadence, creator operating-system fields, or LTD cadence bindings are stale, missing, or contradicted by public posture.",
        "task": "Fail closeout when runner-passport proof, weekly dispatch cadence, creator operating-system fields, or LTD cadence bindings are stale, missing, or contradicted by public posture.",
        "package_id": "next90-m140-fleet-fail-closeout-when-runner-passport-proof-weekly-dispatch-cadence-creat",
        "milestone_id": 140,
        "work_task_id": "140.9",
        "frontier_id": 4145512253,
        "wave": "W27",
        "repo": "fleet",
        "allowed_paths": ["scripts", "tests", ".codex-studio", "feedback"],
        "owned_surfaces": ["fail_closeout_when_runner_passport_proof_weekly_dispatch:fleet"],
    }


def _fixture_tree(tmp_path: Path) -> dict[str, Path]:
    published = tmp_path / "published"
    registry = tmp_path / "registry.yaml"
    fleet_queue = tmp_path / "fleet_queue.yaml"
    design_queue = tmp_path / "design_queue.yaml"
    guide = tmp_path / "guide.md"
    roadmap = tmp_path / "roadmap.md"
    passport_doc = tmp_path / "passport.md"
    passport_acceptance = tmp_path / "passport_acceptance.yaml"
    dispatch_doc = tmp_path / "dispatch.md"
    dispatch_gates = tmp_path / "dispatch_gates.yaml"
    creator_doc = tmp_path / "creator.md"
    ltd_system = tmp_path / "ltd_system.md"
    ltd_registry = tmp_path / "ltd_registry.yaml"
    ltd_runtime = tmp_path / "ltd_runtime.yaml"
    faq_md = tmp_path / "faq.md"
    faq_registry = tmp_path / "faq_registry.yaml"
    feature_registry = tmp_path / "feature_registry.yaml"
    landing = tmp_path / "landing.yaml"
    flagship = tmp_path / "flagship.json"

    _write_yaml(registry, _registry())
    _write_yaml(fleet_queue, {"items": [_queue_item()]})
    _write_yaml(design_queue, {"items": [_queue_item()]})
    _write_text(
        guide,
        "## Wave 27 - turn portability, return cadence, creator health, and LTD followthrough into habit\n"
        "### 140. Runner passport, weekly world dispatch, creator operating system, and LTD-powered cadence closure\n"
        "Exit: a runner can carry governed trust posture between communities, the world can emit recurring return prompts from approved truth, creator publication behaves like a live operating system instead of a shelf, and LTD-powered followthrough loops stay bounded by Chummer-owned receipts instead of becoming shadow authority.\n",
    )
    _write_text(
        roadmap,
        "* the active ritual-value overlay is the repeat-use bundle around `RUNNER_PASSPORT_AND_CROSS_COMMUNITY_TRUST.md`, `WORLD_DISPATCH_AND_REACTIVATION_LOOP.md`, `CREATOR_OPERATING_SYSTEM.md`, and `LTD_CADENCE_AND_FOLLOWTHROUGH_SYSTEM.md`; it keeps the product from stopping at controlled capability when users would really pay attention to weekly trust, reactivation, creator health, and community portability\n",
    )
    _write_text(
        passport_doc,
        "A `RunnerPassport` is not the runner dossier itself.\nIt is the portable proof of what a community needs to know before it can trust the dossier quickly.\nThe passport is not a permanent social score.\n",
    )
    _write_yaml(
        passport_acceptance,
        {
            "required_fields": [
                "runner_identity_ref",
                "rule_environment_fingerprint",
                "approval_state",
                "review_timestamp",
                "reviewer_role",
                "unresolved_warning_refs",
                "dossier_posture",
                "export_eligibility",
                "validity_window",
            ],
            "usage_lanes": [
                "open_run_application_preflight",
                "community_rule_environment",
                "no_desktop_participation",
                "campaign_adoption",
                "organizer_review",
            ],
            "boundary_rules": ["not_a_social_score", "scoped_to_governed_trust_and_compatibility"],
        },
    )
    _write_text(
        dispatch_doc,
        "* one city or campaign ticker\n* one optional public-safe recruitment or return prompt\nIt is the recurring projection of approved campaign and world truth through inspectable receipts.\n",
    )
    _write_yaml(
        dispatch_gates,
        {
            "required_outputs": [
                "city_or_campaign_ticker",
                "faction_or_world_spin_item",
                "gm_only_digest",
                "player_safe_what_changed_card",
                "optional_recruitment_or_return_prompt",
            ],
            "required_provenance": ["ResolutionReport", "WorldTick", "NewsItem"],
            "reactivation_rules": [
                "dispatch_must_point_to_next_useful_action",
                "public_safe_outputs_must_not_leak_private_campaign_truth",
            ],
        },
    )
    _write_text(
        creator_doc,
        "Trust ranking should stay discoverability language, not endorsement language.\n* compatibility and breakage posture from receipt-backed registry truth\npublication becomes a graveyard instead of an ecosystem.\n",
    )
    _write_text(
        ltd_system,
        "LTDs should amplify Chummer's cadence.\nThe LTD stack should create cadence, not shadow authority.\nIf a loop cannot be mirrored back into Chummer-owned receipts, it should stay outside the canonical product lane.\n",
    )
    _write_yaml(
        ltd_registry,
        {
            "loops": [
                {"id": "weekly_world_dispatch"},
                {"id": "open_run_recruitment_and_reminder"},
                {"id": "beginner_and_gm_clinic_followthrough"},
                {"id": "creator_publication_followthrough"},
                {"id": "blocker_reactivation_and_recovery"},
            ],
            "boundary_rules": [
                "ltds_do_not_own_rules_campaign_release_or_moderation_truth",
                "every_loop_must_mirror_back_into_chummer_owned_receipts",
            ],
        },
    )
    _write_yaml(
        ltd_runtime,
        {
            "core_rule": "Chummer owns truth; tools collect, administer, render, publish, schedule, archive, or amplify it.",
            "product_systems": {
                "trust_closure_system": {},
                "public_growth_system": {},
                "community_hub_ops": {},
            },
        },
    )
    _write_text(faq_md, "### Creator\nPreview only.\n")
    _write_yaml(faq_registry, {"sections": [{"entries": [{"question": "General", "answer": "No vendor naming here."}]}]})
    _write_yaml(
        feature_registry,
        {
            "cards": [
                {
                    "id": "lane_gm",
                    "title": "GM",
                    "summary": "Run from a reliable campaign ledger, recover state, and return to the right next-session context.",
                    "badge": "Mixed",
                    "href": "/now#real-mobile-prep",
                },
                {
                    "id": "lane_creator",
                    "title": "Creator",
                    "summary": "Publish primers, briefing reels, and artifact bundles with provenance.",
                    "badge": "Preview lane",
                    "href": "/artifacts",
                },
            ]
        },
    )
    _write_yaml(landing, {"public_routes": [{"path": "/artifacts", "purpose": "teaser_gallery"}]})
    _write_json(
        flagship,
        {
            "generated_at": "2026-05-05T12:00:00Z",
            "status": "pass",
            "readiness_planes": {"flagship_ready": {"status": "ready"}},
        },
    )
    return {
        "published": published,
        "registry": registry,
        "fleet_queue": fleet_queue,
        "design_queue": design_queue,
        "guide": guide,
        "roadmap": roadmap,
        "passport_doc": passport_doc,
        "passport_acceptance": passport_acceptance,
        "dispatch_doc": dispatch_doc,
        "dispatch_gates": dispatch_gates,
        "creator_doc": creator_doc,
        "ltd_system": ltd_system,
        "ltd_registry": ltd_registry,
        "ltd_runtime": ltd_runtime,
        "faq_md": faq_md,
        "faq_registry": faq_registry,
        "feature_registry": feature_registry,
        "landing": landing,
        "flagship": flagship,
    }


class MaterializeNext90M140FleetPortabilityAndCadenceCloseoutGatesTest(unittest.TestCase):
    def test_materializer_emits_warning_gate_when_public_posture_is_bounded_but_direct_proofs_are_absent(self) -> None:
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
                    "--roadmap", str(fixture["roadmap"]),
                    "--runner-passport-doc", str(fixture["passport_doc"]),
                    "--runner-passport-acceptance", str(fixture["passport_acceptance"]),
                    "--world-dispatch-doc", str(fixture["dispatch_doc"]),
                    "--world-dispatch-gates", str(fixture["dispatch_gates"]),
                    "--creator-operating-system", str(fixture["creator_doc"]),
                    "--ltd-cadence-system", str(fixture["ltd_system"]),
                    "--ltd-cadence-registry", str(fixture["ltd_registry"]),
                    "--ltd-runtime-registry", str(fixture["ltd_runtime"]),
                    "--public-faq", str(fixture["faq_md"]),
                    "--public-faq-registry", str(fixture["faq_registry"]),
                    "--public-feature-registry", str(fixture["feature_registry"]),
                    "--public-landing-manifest", str(fixture["landing"]),
                    "--flagship-readiness", str(fixture["flagship"]),
                ],
                check=True,
            )
            payload = json.loads(artifact.read_text(encoding="utf-8"))

        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["monitor_summary"]["portability_and_cadence_closeout_status"], "warning")
        self.assertEqual(payload["monitor_summary"]["runtime_blocker_count"], 0)
        self.assertTrue(any("runner_passport" in warning for warning in payload["package_closeout"]["warnings"]))

    def test_materializer_blocks_runtime_when_public_badge_overclaims(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path)
            bad_registry = yaml.safe_load(fixture["feature_registry"].read_text(encoding="utf-8"))
            bad_registry["cards"][1]["badge"] = "Available now"
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
                    "--roadmap", str(fixture["roadmap"]),
                    "--runner-passport-doc", str(fixture["passport_doc"]),
                    "--runner-passport-acceptance", str(fixture["passport_acceptance"]),
                    "--world-dispatch-doc", str(fixture["dispatch_doc"]),
                    "--world-dispatch-gates", str(fixture["dispatch_gates"]),
                    "--creator-operating-system", str(fixture["creator_doc"]),
                    "--ltd-cadence-system", str(fixture["ltd_system"]),
                    "--ltd-cadence-registry", str(fixture["ltd_registry"]),
                    "--ltd-runtime-registry", str(fixture["ltd_runtime"]),
                    "--public-faq", str(fixture["faq_md"]),
                    "--public-faq-registry", str(fixture["faq_registry"]),
                    "--public-feature-registry", str(fixture["feature_registry"]),
                    "--public-landing-manifest", str(fixture["landing"]),
                    "--flagship-readiness", str(fixture["flagship"]),
                ],
                check=True,
            )
            payload = json.loads(artifact.read_text(encoding="utf-8"))

        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["monitor_summary"]["portability_and_cadence_closeout_status"], "blocked")
        self.assertTrue(any("lane_creator" in blocker for blocker in payload["monitor_summary"]["runtime_blockers"]))


if __name__ == "__main__":
    unittest.main()
