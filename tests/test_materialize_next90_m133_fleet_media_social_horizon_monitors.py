from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


SCRIPT = Path("/docker/fleet/scripts/materialize_next90_m133_fleet_media_social_horizon_monitors.py")


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
                "id": 133,
                "title": "Media and social horizon implementation tranche: JACKPOINT, RUNBOOK PRESS, GHOSTWIRE, RUNSITE, TABLE PULSE, and Community Hub",
                "wave": "W21",
                "status": "not_started",
                "owners": ["fleet", "chummer6-design"],
                "dependencies": [107, 110, 116, 117, 123, 124, 126],
                "work_tasks": [
                    {
                        "id": "133.7",
                        "owner": "fleet",
                        "title": "Monitor media/social horizon proof freshness, consent gates, unsupported public claims, and provider-health stop conditions.",
                        "status": "not_started",
                    }
                ],
            }
        ],
    }


def _queue_item() -> dict:
    return {
        "title": "Monitor media/social horizon proof freshness, consent gates, unsupported public claims, and provider-health stop conditions.",
        "task": "Monitor media/social horizon proof freshness, consent gates, unsupported public claims, and provider-health stop conditions.",
        "package_id": "next90-m133-fleet-monitor-media-social-horizon-proof-freshness-consent-gat",
        "milestone_id": 133,
        "work_task_id": "133.7",
        "frontier_id": 2336165027,
        "status": "not_started",
        "wave": "W21",
        "repo": "fleet",
        "allowed_paths": ["scripts", "tests", ".codex-studio", "feedback"],
        "owned_surfaces": ["monitor_media_social_horizon_proof:fleet"],
    }


def _next90_guide() -> str:
    return """# Next 90 day product advance guide

### 133. Media and social horizon implementation tranche: JACKPOINT, RUNBOOK PRESS, GHOSTWIRE, RUNSITE, TABLE PULSE, and Community Hub

Exit: media/social horizons become bounded implementation lanes with first-party manifests, consent, provenance, publication, revocation, inspectable artifacts, and unsupported-claim guards.
"""


def _ltd_guide() -> str:
    return """# LTD integration guide

### JACKPOINT
evidence provenance

### COMMUNITY HUB
consent truth

### RUNSITE
tactical authority

### RUNBOOK PRESS
publication truth

### GHOSTWIRE
replay truth

### TABLE PULSE
live surveillance

Those lanes may shape demand evidence.
"""


def _external_tools_plane() -> str:
    return """# External tools plane

accepted-roster truth, meeting-handoff truth, and observer-consent truth remain first-party
Chummer remains the first-party authority for run, roster, rule-environment, and closeout truth
### Rule 3 - receipt and provenance required
Every BLACK LEDGER or Community Hub Signitic campaign must carry approved source receipts, first-party destination URLs, UTM campaign naming, segment scope, expiry or review date, rollback owner, and a kill-switch path.
Emailit is production-eligible only while sender-domain authentication, suppression and unsubscribe policy, bounce handling, template registry, `EmailDeliveryReceipt`, kill switch, and provider-secret handling stay intact on the active lane.
"""


def _build_explain_policy() -> str:
    return """# Build and explain artifact truth policy

## Truth order

## Inspectable engine truth

## Receipt and anchor minimums

## Launch and UI rules
"""


def _community_safety_states() -> dict:
    return {
        "event_families": [
            "observer_consent_violation",
            "unsafe_content",
        ],
        "required_fields": [
            "reporter_visibility",
            "subject_visibility",
            "evidence_posture",
            "retention_posture",
            "publication_posture",
            "appeal_deadline",
        ],
    }


def _horizon_registry() -> dict:
    horizons = []
    for horizon_id, title, repos, gate in (
        ("jackpoint", "JACKPOINT", ["chummer6-hub", "chummer6-hub-registry", "chummer6-media-factory"], "Registry manifests and media receipts must survive format changes before the studio is promoted beyond horizon."),
        ("community-hub", "COMMUNITY HUB", ["chummer6-hub", "fleet"], "Open-run listing, accepted roster, meeting handoff, observer consent, and reputation events must stay Chummer-owned even when third-party meeting or analysis tools are in the loop."),
        ("runsite", "RUNSITE", ["chummer6-hub", "chummer6-media-factory"], "Spatial artifacts must remain clearly outside live mechanics and combat truth before any promotion."),
        ("runbook-press", "RUNBOOK PRESS", ["chummer6-hub", "chummer6-hub-registry", "chummer6-media-factory"], "Publication and compatibility metadata must remain registry-owned before this lane becomes research-ready."),
        ("ghostwire", "GHOSTWIRE", ["chummer6-core", "chummer6-hub"], "Replay must prove reducer-safe, receipt-backed reconstruction before it can leave horizon status."),
        ("table-pulse", "TABLE PULSE", ["chummer6-hub", "chummer6-media-factory"], "Coaching analysis only works when consent, privacy, and non-truth boundaries remain provable."),
    ):
        horizons.append(
            {
                "id": horizon_id,
                "title": title,
                "build_path": {
                    "current_state": "horizon",
                    "next_state": "bounded_research",
                },
                "owning_repos": repos,
                "owner_handoff_gate": gate,
                "allowed_surfaces": ["public_projection", "published_artifact"],
                "proof_gate": f"{horizon_id}.proof",
                "public_claim_posture": "source_backed_only",
                "stop_condition": f"{horizon_id}.stop_condition",
            }
        )
    return {"horizons": horizons}


def _journey_gates(*, blocked: bool) -> dict:
    def row(journey_id: str, state: str, warning_reasons: list[str] | None = None) -> dict:
        return {
            "id": journey_id,
            "state": state,
            "blocking_reasons": ["local blocker"] if state != "ready" else [],
            "warning_reasons": warning_reasons or [],
            "blocked_by_external_constraints_only": False,
            "external_proof_requests": [],
        }

    if blocked:
        rows = [
            row("build_explain_publish", "blocked"),
            row("campaign_session_recover_recap", "ready"),
            row("organize_community_and_close_loop", "ready"),
        ]
    else:
        rows = [
            row("build_explain_publish", "ready"),
            row("campaign_session_recover_recap", "ready"),
            row("organize_community_and_close_loop", "ready"),
        ]
    return {"generated_at": "2026-05-05T12:00:00Z", "journeys": rows}


def _flagship_readiness(media_proof_path: Path) -> dict:
    return {
        "coverage_details": {
            "media_artifacts": {
                "status": "ready",
                "evidence": {
                    "media_proof_path": str(media_proof_path),
                    "media_proof_status": "passed",
                    "build_explain_publish": "ready",
                },
            },
            "horizons_and_public_surface": {
                "status": "ready",
                "evidence": {
                    "public_group_deployment_status": "public",
                    "report_cluster_release_notify": "ready",
                },
            },
            "fleet_and_operator_loop": {
                "status": "ready",
                "evidence": {
                    "journey_overall_state": "ready",
                },
            },
        }
    }


def _provider_stewardship() -> dict:
    return {
        "status": "pass",
        "runtime_monitors": {
            "provider_routes": {
                "fallback_thin_count": 1,
                "fallback_thin_lanes": ["core"],
                "review_due_count": 0,
                "review_due_lanes": [],
                "revert_now_count": 0,
                "revert_now_lanes": [],
            }
        },
        "governor_monitors": {
            "provider_canary_gate": {"state": "ready"},
            "current_launch_action": "freeze_launch",
            "rollback_state": "armed",
        },
    }


def _proof_payload(*, status: str = "passed", generated_at: str = "2026-05-05T12:00:00Z") -> dict:
    return {"generated_at": generated_at, "status": status}


def _release_channel_payload() -> dict:
    return {
        "generated_at": "2026-05-05T12:00:00Z",
        "status": "published",
        "supportabilitySummary": "supportability",
        "knownIssueSummary": "known issues",
        "fixAvailabilitySummary": "fix availability",
        "releaseProof": {
            "status": "passed",
            "generatedAt": "2026-05-05T12:00:00Z",
        },
    }


def _fixture_tree(tmp_path: Path, *, blocked_runtime: bool) -> dict[str, Path]:
    registry_path = tmp_path / "registry.yaml"
    queue_path = tmp_path / "queue.yaml"
    design_queue_path = tmp_path / "design_queue.yaml"
    next90_guide_path = tmp_path / "NEXT90_GUIDE.md"
    horizon_registry_path = tmp_path / "HORIZON_REGISTRY.yaml"
    ltd_guide_path = tmp_path / "LTD_GUIDE.md"
    external_tools_path = tmp_path / "EXTERNAL_TOOLS.md"
    build_explain_policy_path = tmp_path / "BUILD_EXPLAIN.md"
    community_safety_path = tmp_path / "COMMUNITY_SAFETY.yaml"
    journey_gates_path = tmp_path / "journey_gates.json"
    flagship_readiness_path = tmp_path / "flagship_readiness.json"
    provider_stewardship_path = tmp_path / "provider_stewardship.json"
    media_proof_path = tmp_path / "media_proof.json"
    hub_proof_path = tmp_path / "hub_proof.json"
    release_channel_path = tmp_path / "release_channel.json"

    _write_yaml(registry_path, _registry())
    _write_yaml(queue_path, {"items": [_queue_item()]})
    _write_yaml(design_queue_path, {"items": [_queue_item()]})
    _write_text(next90_guide_path, _next90_guide())
    _write_yaml(horizon_registry_path, _horizon_registry())
    _write_text(ltd_guide_path, _ltd_guide())
    _write_text(external_tools_path, _external_tools_plane())
    _write_text(build_explain_policy_path, _build_explain_policy())
    _write_yaml(community_safety_path, _community_safety_states())
    _write_json(journey_gates_path, _journey_gates(blocked=blocked_runtime))
    _write_json(flagship_readiness_path, _flagship_readiness(media_proof_path))
    _write_json(provider_stewardship_path, _provider_stewardship())
    _write_json(media_proof_path, _proof_payload())
    _write_json(hub_proof_path, _proof_payload())
    _write_json(release_channel_path, _release_channel_payload())
    return {
        "registry": registry_path,
        "queue": queue_path,
        "design_queue": design_queue_path,
        "next90_guide": next90_guide_path,
        "horizon_registry": horizon_registry_path,
        "ltd_guide": ltd_guide_path,
        "external_tools": external_tools_path,
        "build_explain_policy": build_explain_policy_path,
        "community_safety": community_safety_path,
        "journey_gates": journey_gates_path,
        "flagship_readiness": flagship_readiness_path,
        "provider_stewardship": provider_stewardship_path,
        "media_proof": media_proof_path,
        "hub_proof": hub_proof_path,
        "release_channel": release_channel_path,
    }


class MaterializeNext90M133FleetMediaSocialHorizonMonitorsTest(unittest.TestCase):
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
                "--queue-staging",
                str(fixture["queue"]),
                "--design-queue-staging",
                str(fixture["design_queue"]),
                "--next90-guide",
                str(fixture["next90_guide"]),
                "--horizon-registry",
                str(fixture["horizon_registry"]),
                "--media-social-ltd-guide",
                str(fixture["ltd_guide"]),
                "--external-tools-plane",
                str(fixture["external_tools"]),
                "--build-explain-artifact-truth-policy",
                str(fixture["build_explain_policy"]),
                "--community-safety-states",
                str(fixture["community_safety"]),
                "--journey-gates",
                str(fixture["journey_gates"]),
                "--flagship-readiness",
                str(fixture["flagship_readiness"]),
                "--provider-stewardship",
                str(fixture["provider_stewardship"]),
                "--media-local-release-proof",
                str(fixture["media_proof"]),
                "--hub-local-release-proof",
                str(fixture["hub_proof"]),
                "--release-channel",
                str(fixture["release_channel"]),
            ],
            check=True,
        )
        return json.loads(artifact_path.read_text(encoding="utf-8"))

    def test_runtime_blockers_do_not_block_the_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path, blocked_runtime=True)
            artifact = tmp_path / "artifact.json"
            payload = self._run_materializer(fixture, artifact)

        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["monitor_summary"]["media_social_status"], "blocked")
        self.assertEqual(payload["runtime_monitors"]["journeys"]["monitored_journey_count"], 3)
        self.assertTrue(
            any("build_explain_publish" in row for row in payload["monitor_summary"]["runtime_blockers"])
        )

    def test_missing_canonical_marker_blocks_the_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path, blocked_runtime=False)
            _write_text(fixture["external_tools"], "# missing markers\n")
            artifact = tmp_path / "artifact.json"
            payload = self._run_materializer(fixture, artifact)

        self.assertEqual(payload["status"], "blocked")
        self.assertTrue(any("external_tools_plane" in row for row in payload["package_closeout"]["blockers"]))

    def test_stale_nested_release_channel_proof_is_a_runtime_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path, blocked_runtime=False)
            release_channel = _release_channel_payload()
            release_channel["generated_at"] = "2026-05-05T12:00:00Z"
            release_channel["releaseProof"]["generatedAt"] = "2026-05-01T12:00:00Z"
            _write_json(fixture["release_channel"], release_channel)
            artifact = tmp_path / "artifact.json"
            payload = self._run_materializer(fixture, artifact)

        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["monitor_summary"]["media_social_status"], "blocked")
        self.assertTrue(
            any(
                "release channel proof freshness exceeded threshold" in row.lower()
                for row in payload["monitor_summary"]["runtime_blockers"]
            )
        )


if __name__ == "__main__":
    unittest.main()
