from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


SCRIPT = Path("/docker/fleet/scripts/materialize_next90_m137_fleet_ecosystem_seam_monitors.py")


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
        "program_wave": "next_90_day_product_advance",
        "milestones": [
            {
                "id": 137,
                "title": "Ecosystem leverage, community formation, and acquisition-fit integration seams",
                "wave": "W24",
                "status": "not_started",
                "dependencies": [133, 135, 136],
                "work_tasks": [
                    {
                        "id": "137.7",
                        "owner": "fleet",
                        "title": "Monitor unsupported ecosystem claims, stale seam proof, consent drift, and public-posture mismatch across first-party and integration-ready lanes.",
                        "status": "not_started",
                    }
                ],
            }
        ],
    }


def _queue_item() -> dict:
    return {
        "title": "Monitor unsupported ecosystem claims, stale seam proof, consent drift, and public-posture mismatch across first-party and integration-ready lanes.",
        "task": "Monitor unsupported ecosystem claims, stale seam proof, consent drift, and public-posture mismatch across first-party and integration-ready lanes.",
        "package_id": "next90-m137-fleet-monitor-unsupported-ecosystem-claims-stale-seam-proof-consent-drift-an",
        "milestone_id": 137,
        "work_task_id": "137.7",
        "frontier_id": 9074685645,
        "status": "not_started",
        "wave": "W24",
        "repo": "fleet",
        "allowed_paths": ["scripts", "tests", ".codex-studio", "feedback"],
        "owned_surfaces": ["monitor_unsupported_ecosystem_claims_stale_seam_proof_co:fleet"],
    }


def _next90_guide() -> str:
    return """# Next 90 day product advance guide

## Wave 24 - make ecosystem leverage explicit without losing truth authority

### 137. Ecosystem leverage, community formation, and acquisition-fit integration seams

Exit: Open Runs, Community Hub, publication, recap, route, and community formation seams connect back to campaign, consent, release, and trust truth instead of behaving like detached horizons.
"""


def _roadmap() -> str:
    return """# Roadmap

* keep acquisition-fit or owned-LTD seams explicit for scheduling, publication, route intelligence, coaching, and migration-confidence without letting them become shadow truth owners
* creator publication, artifact shelves, organizer/community operations, guided onboarding, and public launch-health packets
"""


def _horizon_registry() -> dict:
    rows = []
    for horizon_id, access_posture, public_guide_enabled, public_signal_eligible, promoted, bounded in (
        ("nexus-pan", "", True, True, [], ["Emailit", "Documentation.AI"]),
        ("jackpoint", "booster_first", True, True, ["vidBoard", "MarkupGo"], ["Paperguide"]),
        ("community-hub", "booster_first", True, True, ["Teable", "Lunacal"], ["FacePop"]),
        ("runsite", "", True, True, ["Crezlo Tours", "AvoMap"], ["vidBoard"]),
        ("runbook-press", "booster_first", True, True, ["First Book ai", "MarkupGo"], ["Paperguide"]),
        ("table-pulse", "", False, False, ["Nonverbia"], ["hedy.ai"]),
    ):
        row = {
            "id": horizon_id,
            "title": horizon_id.upper().replace("-", " "),
            "status": "horizon",
            "build_path": {"current_state": "horizon", "next_state": "bounded_research"},
            "public_guide": {"enabled": public_guide_enabled, "order": 10},
            "owning_repos": ["chummer6-hub", "fleet"],
            "tool_posture": {"promoted": promoted, "bounded": bounded},
            "public_signal_eligible": public_signal_eligible,
            "owner_handoff_gate": f"{horizon_id} handoff gate",
        }
        if access_posture:
            row["access_posture"] = access_posture
        rows.append(row)
    return {"horizons": rows}


def _ltd_guide() -> str:
    return """# LTD integration guide

* keep Chummer-owned truth, receipts, and approvals first-party
* `nexus-pan` - continuity truth stays first-party; bounded delivery, help, preview, and operator-capture lanes only
* `community-hub` - strongest intake, scheduling, review, and closeout LTD fit
* `runsite` - strongest spatial, explorable-tour, route, and orientation LTD fit
* `runbook-press` - strongest long-form authoring, render, and explainer LTD fit
* `table-pulse` - strongest opt-in coaching and debrief LTD fit
"""


def _external_tools_plane() -> str:
    return """# External tools plane

* `community-hub` - open-run discovery and scheduling may use
may not own run, roster, consent, or resolution truth
route, map, and tour siblings stay first-party inspectable truth and the media layer may not become tactical authority
* `runbook-press` - long-form authoring and export may use `First Book ai`, `MarkupGo`, and `Documentation.AI`
* `table-pulse` - post-session coaching packets may use `Nonverbia` as the primary analysis lane
* public feature ideas, votes, roadmap projection, changelog projection, and voter closeout may use `ProductLift` only as a projection of Chummer-owned design, milestone, release, and closeout truth
"""


def _open_runs() -> str:
    return """# Open runs and Community Hub

An `OpenRun` is Chummer-owned run-network truth.
ProductLift only collects ideas, votes, comments, and projection status. It does not own run truth, roster truth, scheduling truth, meeting handoff truth, world truth, or closeout truth.
Meeting tools are projection lanes, not truth owners.
No observer joins or records unless the GM and all required accepted players explicitly consent for that run.
"""


def _open_runs_honors() -> dict:
    return {
        "objects": {"open_runs": ["ObserverConsent", "MeetingHandoff"]},
        "workflows": [
            {
                "key": "schedule_and_handoff",
                "owner_repo": "chummer6-hub",
                "forbidden": ["external_calendar_as_run_truth", "meeting_url_as_authority"],
            },
            {
                "key": "god_observer_consent",
                "owner_repo": "chummer6-hub",
                "external_tools": ["hedy.ai", "Nonverbia", "Table Pulse"],
                "forbidden": [
                    "automatic_recording",
                    "player_scoring",
                    "moderation_truth",
                    "automatic_world_mutation",
                ],
            },
        ],
    }


def _community_safety() -> dict:
    return {
        "event_families": ["observer_consent_violation", "unsafe_content"],
        "required_fields": [
            "reporter_visibility",
            "subject_visibility",
            "evidence_posture",
            "retention_posture",
            "publication_posture",
            "appeal_deadline",
        ],
    }


def _creator_policy() -> str:
    return """# Creator publication policy

## Truth order

If compatibility receipts are stale or missing, the product must say compatibility is unknown.
* present moderation approval as proof of compatibility
* present trust ranking as a platform safety certification or social credit score
"""


def _public_concierge_workflows() -> dict:
    return {
        "defaults": {
            "required_controls": [
                "kill_switch",
                "first_party_fallback",
                "posture_copy_review",
                "recovery_link_set",
                "telemetry_event_logging",
            ],
            "hard_forbidden_surfaces": [
                "desktop_client",
                "mobile_client",
                "signed_in_home",
                "campaign_workspace",
            ],
        },
        "flows": [
            {
                "id": "campaign_invite_concierge",
                "entry_surface": "tokenized_invite_page_without_private_truth",
                "proof_anchors": ["approved_campaign_primer_pack"],
                "posture": {"widget_surface_posture": "preview", "fixed_route_target": "first_party_invite_or_join_page"},
            },
            {
                "id": "creator_consult_concierge",
                "entry_surface": "creator_page",
                "proof_anchors": ["creator_publish_policy"],
                "posture": {"widget_surface_posture": "preview", "fixed_route_target": "creator_page"},
            },
            {
                "id": "release_concierge",
                "entry_surface": "now_or_release_or_public_help_page",
                "proof_anchors": ["release_channel_truth"],
                "posture": {"widget_surface_posture": "preview", "fixed_route_target": "release_notes_page"},
            },
            {
                "id": "runsite_host_choice",
                "entry_surface": "runsite_page",
                "proof_anchors": ["approved_runsite_pack"],
                "posture": {"widget_surface_posture": "preview", "fixed_route_target": "runsite_page"},
            },
        ],
    }


def _public_feature_registry(*, bad_badge: bool) -> dict:
    badge = "Available now" if bad_badge else "Preview lane"
    return {
        "cards": [
            {
                "id": "horizon_nexus_pan",
                "title": "NEXUS-PAN",
                "badge": "Preparing",
                "audience": "public",
                "detail_route": "/roadmap/nexus-pan",
                "detail_primary_href": "/now#real-mobile-prep",
                "fallback_route": "https://example.com/nexus-pan",
                "external_ok": True,
            },
            {
                "id": "horizon_jackpoint",
                "title": "JACKPOINT",
                "badge": badge,
                "audience": "public",
                "detail_route": "/roadmap/jackpoint",
                "detail_primary_href": "/artifacts/dossier-brief",
                "fallback_route": "https://example.com/jackpoint",
                "proof_note": "Has proof.",
                "external_ok": True,
            },
            {
                "id": "horizon_runsite",
                "title": "RUNSITE",
                "badge": "Preview lane",
                "audience": "public",
                "detail_route": "/roadmap/runsite",
                "detail_primary_href": "/artifacts/runsite-pack",
                "fallback_route": "https://example.com/runsite",
                "proof_note": "Has proof.",
                "external_ok": True,
            },
            {
                "id": "horizon_runbook_press",
                "title": "RUNBOOK PRESS",
                "badge": "Preview lane",
                "audience": "public",
                "detail_route": "/roadmap/runbook-press",
                "detail_primary_href": "/artifacts/campaign-primer",
                "fallback_route": "https://example.com/runbook-press",
                "proof_note": "Has proof.",
                "external_ok": True,
            },
            {
                "id": "horizon_community_hub",
                "title": "COMMUNITY HUB",
                "badge": "Research",
                "audience": "public",
                "detail_route": "/roadmap/community-hub",
                "detail_primary_href": "/roadmap/black-ledger",
                "fallback_route": "https://example.com/community-hub",
                "external_ok": True,
            },
        ]
    }


def _public_landing_manifest() -> dict:
    routes = [
        {"path": "/now", "purpose": "public_page", "must_exist": True},
        {"path": "/roadmap/nexus-pan", "purpose": "roadmap_detail", "must_exist": True},
        {"path": "/roadmap/jackpoint", "purpose": "roadmap_detail", "must_exist": True},
        {"path": "/roadmap/runsite", "purpose": "roadmap_detail", "must_exist": True},
        {"path": "/roadmap/runbook-press", "purpose": "roadmap_detail", "must_exist": True},
        {"path": "/roadmap/community-hub", "purpose": "roadmap_detail", "must_exist": True},
        {"path": "/roadmap/black-ledger", "purpose": "roadmap_detail", "must_exist": True},
        {"path": "/artifacts/dossier-brief", "purpose": "artifact_detail", "must_exist": True},
        {"path": "/artifacts/runsite-pack", "purpose": "artifact_detail", "must_exist": True},
        {"path": "/artifacts/campaign-primer", "purpose": "artifact_detail", "must_exist": True},
    ]
    return {"public_routes": routes, "auth_routes": [], "registered_routes": []}


def _public_release_experience() -> str:
    return """product: chummer
public_concierge_summary: Public concierge widgets may appear only as bounded preview overlays on low-risk public surfaces;
- Fixed route, fallback route, and recovery route language must remain distinct on public surfaces; warm concierge copy may not blur them.
- Concierge copy must not imply that a fix is already available, installed, or correct for this user unless the same claim is already true in first-party release or support truth.
"""


def _write_public_guides(root: Path) -> None:
    _write_text(
        root / "community-hub.md",
        """### Does it replace Discord?

No. Chummer owns campaign logic. Discord can remain the community and meeting surface.

### Is this just LFG?

No. It includes rule-environment preflight, runner applications, scheduling, table contract, roster truth, and run closeout.
""",
    )
    _write_text(
        root / "jackpoint.md",
        """### Will it invent story details?

No. It should work from approved source packets and show what it used.

It is an artifact studio with source trails.
""",
    )
    _write_text(
        root / "runsite.md",
        """### Is this a tactical map?

No. It is prep and spatial understanding. Tactical play can still happen in a VTT.

It is a permissioned spatial artifact.
""",
    )
    _write_text(
        root / "runbook-press.md",
        """### Will it make things up?

No. It must use approved source packets and preserve review state.

It is a long-form publishing pipeline.
""",
    )


def _artifact_payload(*, status: str, generated_at: str = "2026-05-05T12:00:00Z") -> dict:
    return {"status": status, "generated_at": generated_at}


def _flagship_readiness() -> dict:
    return {
        "status": "pass",
        "generated_at": "2026-05-05T12:00:00Z",
        "readiness_planes": {"flagship_ready": {"status": "ready"}},
    }


def _journey_gates() -> dict:
    return {
        "generated_at": "2026-05-05T12:00:00Z",
        "journeys": [
            {"id": "campaign_session_recover_recap", "state": "ready", "blocking_reasons": [], "warning_reasons": []},
            {"id": "organize_community_and_close_loop", "state": "ready", "blocking_reasons": [], "warning_reasons": []},
            {"id": "report_cluster_release_notify", "state": "ready", "blocking_reasons": [], "warning_reasons": []},
        ],
    }


def _fixture_tree(tmp_path: Path, *, blocked_runtime: bool) -> dict[str, Path]:
    registry = tmp_path / "registry.yaml"
    fleet_queue = tmp_path / "fleet_queue.yaml"
    design_queue = tmp_path / "design_queue.yaml"
    next90_guide = tmp_path / "guide.md"
    roadmap = tmp_path / "roadmap.md"
    horizon_registry = tmp_path / "horizon_registry.yaml"
    ltd_guide = tmp_path / "ltd_guide.md"
    external_tools = tmp_path / "external_tools.md"
    open_runs = tmp_path / "open_runs.md"
    open_runs_honors = tmp_path / "open_runs_honors.yaml"
    community_safety = tmp_path / "community_safety.yaml"
    creator_policy = tmp_path / "creator_policy.md"
    concierge = tmp_path / "concierge.yaml"
    feature_registry = tmp_path / "feature_registry.yaml"
    landing_manifest = tmp_path / "landing_manifest.yaml"
    release_experience = tmp_path / "release_experience.yaml"
    public_guide_root = tmp_path / "public-guide" / "HORIZONS"
    m133 = tmp_path / "m133.json"
    m131 = tmp_path / "m131.json"
    flagship = tmp_path / "flagship.json"
    journeys = tmp_path / "journeys.json"

    _write_yaml(registry, _registry())
    _write_yaml(fleet_queue, {"items": [_queue_item()]})
    _write_yaml(design_queue, {"items": [_queue_item()]})
    _write_text(next90_guide, _next90_guide())
    _write_text(roadmap, _roadmap())
    _write_yaml(horizon_registry, _horizon_registry())
    _write_text(ltd_guide, _ltd_guide())
    _write_text(external_tools, _external_tools_plane())
    _write_text(open_runs, _open_runs())
    _write_yaml(open_runs_honors, _open_runs_honors())
    _write_yaml(community_safety, _community_safety())
    _write_text(creator_policy, _creator_policy())
    _write_yaml(concierge, _public_concierge_workflows())
    _write_yaml(feature_registry, _public_feature_registry(bad_badge=blocked_runtime))
    _write_yaml(landing_manifest, _public_landing_manifest())
    _write_text(release_experience, _public_release_experience())
    _write_public_guides(public_guide_root)
    _write_json(m133, _artifact_payload(status="blocked" if blocked_runtime else "pass"))
    _write_json(m131, _artifact_payload(status="pass"))
    _write_json(flagship, _flagship_readiness())
    _write_json(journeys, _journey_gates())
    return {
        "registry": registry,
        "fleet_queue": fleet_queue,
        "design_queue": design_queue,
        "next90_guide": next90_guide,
        "roadmap": roadmap,
        "horizon_registry": horizon_registry,
        "ltd_guide": ltd_guide,
        "external_tools": external_tools,
        "open_runs": open_runs,
        "open_runs_honors": open_runs_honors,
        "community_safety": community_safety,
        "creator_policy": creator_policy,
        "concierge": concierge,
        "feature_registry": feature_registry,
        "landing_manifest": landing_manifest,
        "release_experience": release_experience,
        "public_guide_root": public_guide_root,
        "m133": m133,
        "m131": m131,
        "flagship": flagship,
        "journeys": journeys,
    }


class MaterializeNext90M137FleetEcosystemSeamMonitorsTest(unittest.TestCase):
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
                "--horizon-registry",
                str(fixture["horizon_registry"]),
                "--ltd-integration-guide",
                str(fixture["ltd_guide"]),
                "--external-tools-plane",
                str(fixture["external_tools"]),
                "--open-runs-community-hub",
                str(fixture["open_runs"]),
                "--open-runs-honors",
                str(fixture["open_runs_honors"]),
                "--community-safety-states",
                str(fixture["community_safety"]),
                "--creator-publication-policy",
                str(fixture["creator_policy"]),
                "--public-concierge-workflows",
                str(fixture["concierge"]),
                "--public-feature-registry",
                str(fixture["feature_registry"]),
                "--public-landing-manifest",
                str(fixture["landing_manifest"]),
                "--public-release-experience",
                str(fixture["release_experience"]),
                "--public-guide-root",
                str(fixture["public_guide_root"]),
                "--m133-media-social-monitors",
                str(fixture["m133"]),
                "--m131-public-guide-gates",
                str(fixture["m131"]),
                "--flagship-readiness",
                str(fixture["flagship"]),
                "--journey-gates",
                str(fixture["journeys"]),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn('"status"', completed.stdout)
        return json.loads(artifact.read_text(encoding="utf-8"))

    def test_materializer_passes_when_posture_and_proof_are_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path, blocked_runtime=False)
            artifact = tmp_path / "artifact.json"
            markdown = tmp_path / "artifact.md"
            payload = self._run_materializer(fixture, artifact, markdown)

        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["monitor_summary"]["ecosystem_seam_status"], "pass")
        self.assertEqual(payload["monitor_summary"]["runtime_blocker_count"], 0)
        self.assertEqual(payload["runtime_monitors"]["public_feature_posture"]["monitored_public_card_count"], 5)

    def test_materializer_flags_public_claim_and_dependency_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path, blocked_runtime=True)
            artifact = tmp_path / "artifact.json"
            markdown = tmp_path / "artifact.md"
            payload = self._run_materializer(fixture, artifact, markdown)

        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["monitor_summary"]["ecosystem_seam_status"], "blocked")
        warnings = payload["package_closeout"]["warnings"]
        self.assertTrue(any("badge `Available now` overclaims" in warning for warning in warnings))
        self.assertTrue(any("M133 media/social horizon monitors status is blocked" in warning for warning in warnings))


if __name__ == "__main__":
    unittest.main()
