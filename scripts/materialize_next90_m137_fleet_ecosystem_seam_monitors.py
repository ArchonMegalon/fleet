#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

import yaml


ROOT = Path("/docker/fleet")
PUBLISHED = ROOT / ".codex-studio" / "published"
PRODUCT_MIRROR = Path("/docker/chummercomplete/chummer-design/products/chummer")

PACKAGE_ID = "next90-m137-fleet-monitor-unsupported-ecosystem-claims-stale-seam-proof-consent-drift-an"
FRONTIER_ID = 9074685645
MILESTONE_ID = 137
WORK_TASK_ID = "137.7"
WAVE_ID = "W24"
QUEUE_TITLE = "Monitor unsupported ecosystem claims, stale seam proof, consent drift, and public-posture mismatch across first-party and integration-ready lanes."
OWNED_SURFACES = ["monitor_unsupported_ecosystem_claims_stale_seam_proof_co:fleet"]
ALLOWED_PATHS = ["scripts", "tests", ".codex-studio", "feedback"]

DEFAULT_OUTPUT = PUBLISHED / "NEXT90_M137_FLEET_ECOSYSTEM_SEAM_MONITORS.generated.json"
DEFAULT_MARKDOWN = PUBLISHED / "NEXT90_M137_FLEET_ECOSYSTEM_SEAM_MONITORS.generated.md"

SUCCESSOR_REGISTRY = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
FLEET_QUEUE_STAGING = PUBLISHED / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
DESIGN_QUEUE_STAGING = PRODUCT_MIRROR / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
NEXT90_GUIDE = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_GUIDE.md"
ROADMAP = PRODUCT_MIRROR / "ROADMAP.md"
HORIZON_REGISTRY = PRODUCT_MIRROR / "HORIZON_REGISTRY.yaml"
LTD_INTEGRATION_GUIDE = PRODUCT_MIRROR / "HORIZON_AND_FEATURE_LTD_INTEGRATION_GUIDE.md"
EXTERNAL_TOOLS_PLANE = PRODUCT_MIRROR / "EXTERNAL_TOOLS_PLANE.md"
OPEN_RUNS_AND_COMMUNITY_HUB = PRODUCT_MIRROR / "OPEN_RUNS_AND_COMMUNITY_HUB.md"
OPEN_RUNS_REPUTATION_AND_SEASONAL_HONORS = PRODUCT_MIRROR / "OPEN_RUNS_REPUTATION_AND_SEASONAL_HONORS.yaml"
COMMUNITY_SAFETY_STATES = PRODUCT_MIRROR / "COMMUNITY_SAFETY_EVENT_AND_APPEAL_STATES.yaml"
CREATOR_PUBLICATION_POLICY = PRODUCT_MIRROR / "CREATOR_PUBLICATION_TRUST_AND_COMPATIBILITY_POLICY.md"
PUBLIC_CONCIERGE_WORKFLOWS = PRODUCT_MIRROR / "PUBLIC_CONCIERGE_WORKFLOWS.yaml"
PUBLIC_FEATURE_REGISTRY = PRODUCT_MIRROR / "PUBLIC_FEATURE_REGISTRY.yaml"
PUBLIC_LANDING_MANIFEST = PRODUCT_MIRROR / "PUBLIC_LANDING_MANIFEST.yaml"
PUBLIC_RELEASE_EXPERIENCE = PRODUCT_MIRROR / "PUBLIC_RELEASE_EXPERIENCE.yaml"
PUBLIC_GUIDE_ROOT = PRODUCT_MIRROR / "public-guide" / "HORIZONS"
M133_MEDIA_SOCIAL_MONITORS = PUBLISHED / "NEXT90_M133_FLEET_MEDIA_SOCIAL_HORIZON_MONITORS.generated.json"
M131_PUBLIC_GUIDE_GATES = PUBLISHED / "NEXT90_M131_FLEET_PUBLIC_GUIDE_GATES.generated.json"
FLAGSHIP_READINESS = PUBLISHED / "FLAGSHIP_PRODUCT_READINESS.generated.json"
JOURNEY_GATES = PUBLISHED / "JOURNEY_GATES.generated.json"

PROOF_FRESHNESS_HOURS = 72

GUIDE_MARKERS = {
    "wave_24": "## Wave 24 - make ecosystem leverage explicit without losing truth authority",
    "milestone_137": "### 137. Ecosystem leverage, community formation, and acquisition-fit integration seams",
    "exit_contract": "Exit: Open Runs, Community Hub, publication, recap, route, and community formation seams connect back to campaign, consent, release, and trust truth instead of behaving like detached horizons.",
}
ROADMAP_MARKERS = {
    "acquisition_fit_boundary": "* keep acquisition-fit or owned-LTD seams explicit for scheduling, publication, route intelligence, coaching, and migration-confidence without letting them become shadow truth owners",
    "public_and_operator_stack": "creator publication, artifact shelves, organizer/community operations, guided onboarding, and public launch-health packets",
}
LTD_GUIDE_MARKERS = {
    "truth_first": "* keep Chummer-owned truth, receipts, and approvals first-party",
    "nexus_pan": "* `nexus-pan` - continuity truth stays first-party; bounded delivery, help, preview, and operator-capture lanes only",
    "community_hub": "* `community-hub` - strongest intake, scheduling, review, and closeout LTD fit",
    "runsite": "* `runsite` - strongest spatial, explorable-tour, route, and orientation LTD fit",
    "runbook_press": "* `runbook-press` - strongest long-form authoring, render, and explainer LTD fit",
    "table_pulse": "* `table-pulse` - strongest opt-in coaching and debrief LTD fit",
}
EXTERNAL_TOOLS_MARKERS = {
    "community_hub_lane": "* `community-hub` - open-run discovery and scheduling may use",
    "community_hub_boundary": "may not own run, roster, consent, or resolution truth",
    "runsite_boundary": "route, map, and tour siblings stay first-party inspectable truth and the media layer may not become tactical authority",
    "runbook_press_lane": "* `runbook-press` - long-form authoring and export may use `First Book ai`, `MarkupGo`, and `Documentation.AI`",
    "table_pulse_lane": "* `table-pulse` - post-session coaching packets may use `Nonverbia` as the primary analysis lane",
    "productlift_boundary": "* public feature ideas, votes, roadmap projection, changelog projection, and voter closeout may use `ProductLift` only as a projection of Chummer-owned design, milestone, release, and closeout truth",
}
OPEN_RUNS_MARKERS = {
    "canonical_rule": "An `OpenRun` is Chummer-owned run-network truth.",
    "productlift_projection_only": "ProductLift only collects ideas, votes, comments, and projection status. It does not own run truth, roster truth, scheduling truth, meeting handoff truth, world truth, or closeout truth.",
    "meeting_projection_only": "Meeting tools are projection lanes, not truth owners.",
    "observer_consent": "No observer joins or records unless the GM and all required accepted players explicitly consent for that run.",
}
CREATOR_POLICY_MARKERS = {
    "truth_order": "## Truth order",
    "compatibility_unknown": "If compatibility receipts are stale or missing, the product must say compatibility is unknown.",
    "no_moderation_as_compatibility": "* present moderation approval as proof of compatibility",
    "no_trust_rank_as_certification": "* present trust ranking as a platform safety certification or social credit score",
}
PUBLIC_RELEASE_MARKERS = {
    "concierge_preview": "public_concierge_summary: Public concierge widgets may appear only as bounded preview overlays on low-risk public surfaces;",
    "fallback_distinct": "- Fixed route, fallback route, and recovery route language must remain distinct on public surfaces; warm concierge copy may not blur them.",
    "no_fix_overclaim": "- Concierge copy must not imply that a fix is already available, installed, or correct for this user unless the same claim is already true in first-party release or support truth.",
}
PUBLIC_GUIDE_MARKERS = {
    "community_hub": {
        "discord_boundary": "No. Chummer owns campaign logic. Discord can remain the community and meeting surface.",
        "not_lfg": "No. It includes rule-environment preflight, runner applications, scheduling, table contract, roster truth, and run closeout.",
    },
    "jackpoint": {
        "no_invention": "No. It should work from approved source packets and show what it used.",
        "source_trails": "It is an artifact studio with source trails.",
    },
    "runsite": {
        "not_tactical": "No. It is prep and spatial understanding. Tactical play can still happen in a VTT.",
        "permissioned_artifact": "It is a permissioned spatial artifact.",
    },
    "runbook_press": {
        "no_invention": "No. It must use approved source packets and preserve review state.",
        "pipeline": "It is a long-form publishing pipeline.",
    },
}

TARGET_HORIZON_IDS = (
    "nexus-pan",
    "jackpoint",
    "community-hub",
    "runsite",
    "runbook-press",
    "table-pulse",
)
EXPECTED_PUBLIC_GUIDE_ENABLED = {
    "nexus-pan": True,
    "jackpoint": True,
    "community-hub": True,
    "runsite": True,
    "runbook-press": True,
    "table-pulse": False,
}
EXPECTED_PUBLIC_SIGNAL = {
    "nexus-pan": True,
    "jackpoint": True,
    "community-hub": True,
    "runsite": True,
    "runbook-press": True,
    "table-pulse": False,
}
EXPECTED_ACCESS_POSTURES = {
    "jackpoint": "booster_first",
    "community-hub": "booster_first",
    "runbook-press": "booster_first",
}
PUBLIC_CARD_SPECS = {
    "horizon_nexus_pan": {
        "title": "NEXUS-PAN",
        "allowed_badges": {"Preparing", "Research"},
        "detail_route": "/roadmap/nexus-pan",
        "detail_primary_href": "/now#real-mobile-prep",
        "require_proof_note": False,
    },
    "horizon_jackpoint": {
        "title": "JACKPOINT",
        "allowed_badges": {"Preview lane", "Research"},
        "detail_route": "/roadmap/jackpoint",
        "detail_primary_href": "/artifacts/dossier-brief",
        "require_proof_note": True,
    },
    "horizon_runsite": {
        "title": "RUNSITE",
        "allowed_badges": {"Preview lane", "Research"},
        "detail_route": "/roadmap/runsite",
        "detail_primary_href": "/artifacts/runsite-pack",
        "require_proof_note": True,
    },
    "horizon_runbook_press": {
        "title": "RUNBOOK PRESS",
        "allowed_badges": {"Preview lane", "Research"},
        "detail_route": "/roadmap/runbook-press",
        "detail_primary_href": "/artifacts/campaign-primer",
        "require_proof_note": True,
    },
    "horizon_community_hub": {
        "title": "COMMUNITY HUB",
        "allowed_badges": {"Research", "Preview lane"},
        "detail_route": "/roadmap/community-hub",
        "detail_primary_href": "/roadmap/black-ledger",
        "require_proof_note": False,
    },
}
ABSENT_PUBLIC_CARD_IDS = {"horizon_table_pulse"}
PUBLIC_CARD_TO_HORIZON = {
    "horizon_nexus_pan": "nexus-pan",
    "horizon_jackpoint": "jackpoint",
    "horizon_runsite": "runsite",
    "horizon_runbook_press": "runbook-press",
    "horizon_community_hub": "community-hub",
}
REQUIRED_PUBLIC_CONTROLS = {
    "kill_switch",
    "first_party_fallback",
    "posture_copy_review",
    "recovery_link_set",
    "telemetry_event_logging",
}
REQUIRED_FORBIDDEN_SURFACES = {
    "desktop_client",
    "mobile_client",
    "signed_in_home",
    "campaign_workspace",
}
CONCIERGE_FLOW_SPECS = {
    "campaign_invite_concierge": {
        "entry_surface": "tokenized_invite_page_without_private_truth",
        "fixed_route_target": "first_party_invite_or_join_page",
        "proof_anchor": "approved_campaign_primer_pack",
    },
    "creator_consult_concierge": {
        "entry_surface": "creator_page",
        "fixed_route_target": "creator_page",
        "proof_anchor": "creator_publish_policy",
    },
    "release_concierge": {
        "entry_surface": "now_or_release_or_public_help_page",
        "fixed_route_target": "release_notes_page",
        "proof_anchor": "release_channel_truth",
    },
    "runsite_host_choice": {
        "entry_surface": "runsite_page",
        "fixed_route_target": "runsite_page",
        "proof_anchor": "approved_runsite_pack",
    },
}
COMMUNITY_SAFETY_REQUIRED_FIELDS = {
    "reporter_visibility",
    "subject_visibility",
    "evidence_posture",
    "retention_posture",
    "publication_posture",
    "appeal_deadline",
}
CONSENT_WORKFLOW_FORBIDDEN = {
    "automatic_recording",
    "player_scoring",
    "moderation_truth",
    "automatic_world_mutation",
}
TARGET_JOURNEY_IDS = (
    "campaign_session_recover_recap",
    "organize_community_and_close_loop",
    "report_cluster_release_notify",
)


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize the Fleet M137 ecosystem seam monitor packet.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--markdown-output", default=str(DEFAULT_MARKDOWN))
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--fleet-queue-staging", default=str(FLEET_QUEUE_STAGING))
    parser.add_argument("--design-queue-staging", default=str(DESIGN_QUEUE_STAGING))
    parser.add_argument("--next90-guide", default=str(NEXT90_GUIDE))
    parser.add_argument("--roadmap", default=str(ROADMAP))
    parser.add_argument("--horizon-registry", default=str(HORIZON_REGISTRY))
    parser.add_argument("--ltd-integration-guide", default=str(LTD_INTEGRATION_GUIDE))
    parser.add_argument("--external-tools-plane", default=str(EXTERNAL_TOOLS_PLANE))
    parser.add_argument("--open-runs-community-hub", default=str(OPEN_RUNS_AND_COMMUNITY_HUB))
    parser.add_argument("--open-runs-honors", default=str(OPEN_RUNS_REPUTATION_AND_SEASONAL_HONORS))
    parser.add_argument("--community-safety-states", default=str(COMMUNITY_SAFETY_STATES))
    parser.add_argument("--creator-publication-policy", default=str(CREATOR_PUBLICATION_POLICY))
    parser.add_argument("--public-concierge-workflows", default=str(PUBLIC_CONCIERGE_WORKFLOWS))
    parser.add_argument("--public-feature-registry", default=str(PUBLIC_FEATURE_REGISTRY))
    parser.add_argument("--public-landing-manifest", default=str(PUBLIC_LANDING_MANIFEST))
    parser.add_argument("--public-release-experience", default=str(PUBLIC_RELEASE_EXPERIENCE))
    parser.add_argument("--public-guide-root", default=str(PUBLIC_GUIDE_ROOT))
    parser.add_argument("--m133-media-social-monitors", default=str(M133_MEDIA_SOCIAL_MONITORS))
    parser.add_argument("--m131-public-guide-gates", default=str(M131_PUBLIC_GUIDE_GATES))
    parser.add_argument("--flagship-readiness", default=str(FLAGSHIP_READINESS))
    parser.add_argument("--journey-gates", default=str(JOURNEY_GATES))
    return parser.parse_args(argv)


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [_normalize_text(item) for item in value if _normalize_text(item)]


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_yaml(path: Path) -> Dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve())
    except OSError:
        return str(path)


def _source_link(path: Path, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "path": _display_path(path),
        "sha256": _sha256_file(path),
        "generated_at": _normalize_text(payload.get("generated_at") or payload.get("generatedAt")),
    }


def _text_source_link(path: Path) -> Dict[str, Any]:
    return {"path": _display_path(path), "sha256": _sha256_file(path), "generated_at": ""}


def _write_json_file(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _find_milestone(registry: Dict[str, Any], milestone_id: int) -> Dict[str, Any]:
    for row in registry.get("milestones") or []:
        if isinstance(row, dict) and int(row.get("id") or 0) == milestone_id:
            return dict(row)
    return {}


def _find_work_task(milestone: Dict[str, Any], work_task_id: str) -> Dict[str, Any]:
    for row in milestone.get("work_tasks") or []:
        if isinstance(row, dict) and _normalize_text(row.get("id")) == work_task_id:
            return dict(row)
    return {}


def _find_queue_item(queue: Dict[str, Any], work_task_id: str) -> Dict[str, Any]:
    for row in queue.get("items") or []:
        if isinstance(row, dict) and _normalize_text(row.get("work_task_id")) == work_task_id:
            return dict(row)
    return {}


def _parse_iso_utc(value: str) -> dt.datetime | None:
    text = _normalize_text(value)
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return dt.datetime.fromisoformat(text)
    except ValueError:
        return None


def _age_hours(value: str, *, now: dt.datetime) -> float | None:
    parsed = _parse_iso_utc(value)
    if parsed is None:
        return None
    return round(max(0.0, (now - parsed).total_seconds()) / 3600.0, 2)


def _is_ready(value: Any) -> bool:
    return _normalize_text(value).lower() == "ready"


def _is_passing(value: Any) -> bool:
    return _normalize_text(value).lower() in {"pass", "passed", "ready", "ok", "published", "publishable"}


def _marker_monitor(text: str, markers: Dict[str, str], *, label: str) -> Dict[str, Any]:
    checks = {name: marker in text for name, marker in markers.items()}
    issues = [f"{label} missing required marker: {name}" for name, present in checks.items() if not present]
    return {"state": "pass" if not issues else "fail", "checks": checks, "issues": issues}


def _queue_alignment(*, work_task: Dict[str, Any], fleet_queue_item: Dict[str, Any], design_queue_item: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    warnings: List[str] = []
    if not work_task:
        issues.append("Canonical registry work task is missing.")
    if not design_queue_item:
        issues.append("Design queue row is missing.")
    if not fleet_queue_item:
        warnings.append("Fleet queue mirror row is still missing for work task 137.7.")
    expected = {
        "title": QUEUE_TITLE,
        "task": QUEUE_TITLE,
        "package_id": PACKAGE_ID,
        "work_task_id": WORK_TASK_ID,
        "frontier_id": FRONTIER_ID,
        "milestone_id": MILESTONE_ID,
        "wave": WAVE_ID,
        "repo": "fleet",
    }
    if work_task:
        if _normalize_text(work_task.get("owner")) != "fleet":
            issues.append("Canonical registry work task owner drifted from fleet.")
        if _normalize_text(work_task.get("title")) != QUEUE_TITLE:
            issues.append("Canonical registry work task title drifted.")
    for label, row in (("fleet", fleet_queue_item), ("design", design_queue_item)):
        if not row:
            continue
        for field, expected_value in expected.items():
            if _normalize_text(row.get(field)) != _normalize_text(expected_value):
                if label == "design":
                    issues.append(f"Design queue {field} drifted.")
                else:
                    warnings.append(f"Fleet queue {field} drifted from design authority.")
        if _normalize_list(row.get("allowed_paths")) != ALLOWED_PATHS:
            if label == "design":
                issues.append("Design queue allowed_paths drifted.")
            else:
                warnings.append("Fleet queue allowed_paths drifted from design authority.")
        if _normalize_list(row.get("owned_surfaces")) != OWNED_SURFACES:
            if label == "design":
                issues.append("Design queue owned_surfaces drifted.")
            else:
                warnings.append("Fleet queue owned_surfaces drifted from design authority.")
    return {"state": "pass" if not issues else "fail", "issues": issues, "warnings": warnings}


def _horizon_registry_monitor(payload: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    warnings: List[str] = []
    horizons = {
        _normalize_text(row.get("id")): dict(row)
        for row in payload.get("horizons") or []
        if isinstance(row, dict) and _normalize_text(row.get("id"))
    }
    monitored_rows: List[Dict[str, Any]] = []
    for horizon_id in TARGET_HORIZON_IDS:
        row = horizons.get(horizon_id)
        if not row:
            issues.append(f"HORIZON_REGISTRY is missing {horizon_id}.")
            continue
        build_path = dict(row.get("build_path") or {})
        public_guide = dict(row.get("public_guide") or {})
        tool_posture = dict(row.get("tool_posture") or {})
        promoted = _normalize_list(tool_posture.get("promoted"))
        bounded = _normalize_list(tool_posture.get("bounded"))
        if _normalize_text(row.get("status")) != "horizon":
            issues.append(f"Horizon `{horizon_id}` status drifted away from `horizon`.")
        if _normalize_text(build_path.get("current_state")) != "horizon":
            issues.append(f"Horizon `{horizon_id}` build_path.current_state drifted away from `horizon`.")
        if _normalize_text(build_path.get("next_state")) != "bounded_research":
            issues.append(f"Horizon `{horizon_id}` build_path.next_state drifted away from `bounded_research`.")
        if bool(public_guide.get("enabled")) != EXPECTED_PUBLIC_GUIDE_ENABLED[horizon_id]:
            issues.append(
                f"Horizon `{horizon_id}` public_guide.enabled drifted from the expected {str(EXPECTED_PUBLIC_GUIDE_ENABLED[horizon_id]).lower()} posture."
            )
        if bool(row.get("public_signal_eligible")) != EXPECTED_PUBLIC_SIGNAL[horizon_id]:
            issues.append(
                f"Horizon `{horizon_id}` public_signal_eligible drifted from the expected {str(EXPECTED_PUBLIC_SIGNAL[horizon_id]).lower()} posture."
            )
        expected_access_posture = EXPECTED_ACCESS_POSTURES.get(horizon_id)
        actual_access_posture = _normalize_text(row.get("access_posture"))
        if expected_access_posture:
            if actual_access_posture != expected_access_posture:
                issues.append(
                    f"Horizon `{horizon_id}` access_posture drifted from `{expected_access_posture}`."
                )
        elif actual_access_posture:
            warnings.append(f"Horizon `{horizon_id}` now declares access_posture `{actual_access_posture}`; audit public promise posture.")
        if not _normalize_text(row.get("owner_handoff_gate")):
            issues.append(f"Horizon `{horizon_id}` is missing owner_handoff_gate.")
        if not _normalize_list(row.get("owning_repos")):
            issues.append(f"Horizon `{horizon_id}` is missing owning_repos.")
        if not promoted and not bounded:
            issues.append(f"Horizon `{horizon_id}` is missing tool_posture promoted/bounded lanes.")
        monitored_rows.append(
            {
                "id": horizon_id,
                "status": _normalize_text(row.get("status")),
                "public_guide_enabled": bool(public_guide.get("enabled")),
                "public_signal_eligible": bool(row.get("public_signal_eligible")),
                "access_posture": actual_access_posture,
                "owning_repo_count": len(_normalize_list(row.get("owning_repos"))),
                "promoted_tool_count": len(promoted),
                "bounded_tool_count": len(bounded),
            }
        )
    return {
        "state": "pass" if not issues else "fail",
        "issues": issues,
        "warnings": warnings,
        "monitored_horizon_count": len(monitored_rows),
        "monitored_horizons": monitored_rows,
    }


def _consent_registry_monitor(open_runs_honors: Dict[str, Any], community_safety: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    workflows = {
        _normalize_text(row.get("key")): dict(row)
        for row in open_runs_honors.get("workflows") or []
        if isinstance(row, dict) and _normalize_text(row.get("key"))
    }
    observer_workflow = workflows.get("god_observer_consent", {})
    if not observer_workflow:
        issues.append("OPEN_RUNS_REPUTATION_AND_SEASONAL_HONORS is missing workflow `god_observer_consent`.")
    else:
        if _normalize_text(observer_workflow.get("owner_repo")) != "chummer6-hub":
            issues.append("god_observer_consent owner_repo drifted from chummer6-hub.")
        external_tools = set(_normalize_list(observer_workflow.get("external_tools")))
        for tool in ("hedy.ai", "Nonverbia", "Table Pulse"):
            if tool not in external_tools:
                issues.append(f"god_observer_consent external_tools is missing `{tool}`.")
        forbidden = set(_normalize_list(observer_workflow.get("forbidden")))
        for clause in sorted(CONSENT_WORKFLOW_FORBIDDEN):
            if clause not in forbidden:
                issues.append(f"god_observer_consent forbidden rules are missing `{clause}`.")
    schedule_workflow = workflows.get("schedule_and_handoff", {})
    if not schedule_workflow:
        issues.append("OPEN_RUNS_REPUTATION_AND_SEASONAL_HONORS is missing workflow `schedule_and_handoff`.")
    else:
        forbidden = set(_normalize_list(schedule_workflow.get("forbidden")))
        for clause in ("external_calendar_as_run_truth", "meeting_url_as_authority"):
            if clause not in forbidden:
                issues.append(f"schedule_and_handoff forbidden rules are missing `{clause}`.")
    object_rows = dict(open_runs_honors.get("objects") or {})
    if "ObserverConsent" not in _normalize_list(object_rows.get("open_runs")):
        issues.append("OPEN_RUNS_REPUTATION_AND_SEASONAL_HONORS open_runs objects are missing ObserverConsent.")
    if "MeetingHandoff" not in _normalize_list(object_rows.get("open_runs")):
        issues.append("OPEN_RUNS_REPUTATION_AND_SEASONAL_HONORS open_runs objects are missing MeetingHandoff.")
    event_families = set(_normalize_list(community_safety.get("event_families")))
    required_fields = set(_normalize_list(community_safety.get("required_fields")))
    if "observer_consent_violation" not in event_families:
        issues.append("COMMUNITY_SAFETY_EVENT_AND_APPEAL_STATES is missing observer_consent_violation.")
    for field in sorted(COMMUNITY_SAFETY_REQUIRED_FIELDS):
        if field not in required_fields:
            issues.append(f"COMMUNITY_SAFETY_EVENT_AND_APPEAL_STATES is missing required field `{field}`.")
    return {
        "state": "pass" if not issues else "fail",
        "issues": issues,
        "observer_external_tool_count": len(_normalize_list(observer_workflow.get("external_tools"))),
        "community_safety_event_family_count": len(event_families),
    }


def _public_concierge_workflow_monitor(payload: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    defaults = dict(payload.get("defaults") or {})
    required_controls = set(_normalize_list(defaults.get("required_controls")))
    forbidden_surfaces = set(_normalize_list(defaults.get("hard_forbidden_surfaces")))
    for control in sorted(REQUIRED_PUBLIC_CONTROLS):
        if control not in required_controls:
            issues.append(f"PUBLIC_CONCIERGE_WORKFLOWS defaults.required_controls is missing `{control}`.")
    for surface in sorted(REQUIRED_FORBIDDEN_SURFACES):
        if surface not in forbidden_surfaces:
            issues.append(f"PUBLIC_CONCIERGE_WORKFLOWS defaults.hard_forbidden_surfaces is missing `{surface}`.")
    flows = {
        _normalize_text(row.get("id")): dict(row)
        for row in payload.get("flows") or []
        if isinstance(row, dict) and _normalize_text(row.get("id"))
    }
    monitored_flows: List[Dict[str, Any]] = []
    for flow_id, spec in CONCIERGE_FLOW_SPECS.items():
        row = flows.get(flow_id, {})
        if not row:
            issues.append(f"PUBLIC_CONCIERGE_WORKFLOWS is missing flow `{flow_id}`.")
            continue
        posture = dict(row.get("posture") or {})
        proof_anchors = set(_normalize_list(row.get("proof_anchors")))
        if _normalize_text(row.get("entry_surface")) != spec["entry_surface"]:
            issues.append(f"PUBLIC_CONCIERGE_WORKFLOWS `{flow_id}` entry_surface drifted.")
        if _normalize_text(posture.get("widget_surface_posture")) != "preview":
            issues.append(f"PUBLIC_CONCIERGE_WORKFLOWS `{flow_id}` widget_surface_posture drifted away from `preview`.")
        if _normalize_text(posture.get("fixed_route_target")) != spec["fixed_route_target"]:
            issues.append(f"PUBLIC_CONCIERGE_WORKFLOWS `{flow_id}` fixed_route_target drifted.")
        if spec["proof_anchor"] not in proof_anchors:
            issues.append(f"PUBLIC_CONCIERGE_WORKFLOWS `{flow_id}` proof_anchors is missing `{spec['proof_anchor']}`.")
        monitored_flows.append(
            {
                "id": flow_id,
                "entry_surface": _normalize_text(row.get("entry_surface")),
                "fixed_route_target": _normalize_text(posture.get("fixed_route_target")),
                "proof_anchor_count": len(proof_anchors),
            }
        )
    return {
        "state": "pass" if not issues else "fail",
        "issues": issues,
        "monitored_flow_count": len(monitored_flows),
        "monitored_flows": monitored_flows,
    }


def _route_index(payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    indexed: Dict[str, Dict[str, Any]] = {}
    for collection_name in ("public_routes", "auth_routes", "registered_routes"):
        for row in payload.get(collection_name) or []:
            if not isinstance(row, dict):
                continue
            path = _normalize_text(row.get("path"))
            if path:
                indexed[path] = dict(row)
    return indexed


def _href_path(value: str) -> str:
    return _normalize_text(value).split("#", 1)[0]


def _expected_route_purpose(path: str) -> str | None:
    if path.startswith("/roadmap/"):
        return "roadmap_detail"
    if path.startswith("/artifacts/"):
        return "artifact_detail"
    return None


def _public_feature_registry_monitor(feature_registry: Dict[str, Any], landing_manifest: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    runtime_blockers: List[str] = []
    warnings: List[str] = []
    cards = {
        _normalize_text(row.get("id")): dict(row)
        for row in feature_registry.get("cards") or []
        if isinstance(row, dict) and _normalize_text(row.get("id"))
    }
    routes = _route_index(landing_manifest)
    for card_id in sorted(ABSENT_PUBLIC_CARD_IDS):
        if card_id in cards:
            runtime_blockers.append(
                f"PUBLIC_FEATURE_REGISTRY unexpectedly exposes `{card_id}` even though that lane is not public-guide eligible."
            )
    monitored_cards: List[Dict[str, Any]] = []
    for card_id, spec in PUBLIC_CARD_SPECS.items():
        card = cards.get(card_id, {})
        if not card:
            runtime_blockers.append(f"PUBLIC_FEATURE_REGISTRY is missing card `{card_id}`.")
            continue
        badge = _normalize_text(card.get("badge"))
        detail_route = _normalize_text(card.get("detail_route"))
        detail_primary_href = _normalize_text(card.get("detail_primary_href"))
        fallback_route = _normalize_text(card.get("fallback_route"))
        if _normalize_text(card.get("title")) != spec["title"]:
            runtime_blockers.append(f"PUBLIC_FEATURE_REGISTRY `{card_id}` title drifted from `{spec['title']}`.")
        if badge not in spec["allowed_badges"]:
            runtime_blockers.append(f"PUBLIC_FEATURE_REGISTRY `{card_id}` badge `{badge}` overclaims the horizon posture.")
        if _normalize_text(card.get("audience")) != "public":
            runtime_blockers.append(f"PUBLIC_FEATURE_REGISTRY `{card_id}` audience drifted away from `public`.")
        if not bool(card.get("external_ok")):
            runtime_blockers.append(f"PUBLIC_FEATURE_REGISTRY `{card_id}` no longer allows bounded external explainers.")
        if detail_route != spec["detail_route"]:
            runtime_blockers.append(f"PUBLIC_FEATURE_REGISTRY `{card_id}` detail_route drifted.")
        if detail_primary_href != spec["detail_primary_href"]:
            runtime_blockers.append(f"PUBLIC_FEATURE_REGISTRY `{card_id}` detail_primary_href drifted.")
        if not fallback_route:
            runtime_blockers.append(f"PUBLIC_FEATURE_REGISTRY `{card_id}` is missing fallback_route.")
        if spec["require_proof_note"] and not _normalize_text(card.get("proof_note")):
            runtime_blockers.append(f"PUBLIC_FEATURE_REGISTRY `{card_id}` is missing proof_note for a preview-lane claim.")
        for href in (detail_route, detail_primary_href):
            path = _href_path(href)
            route = routes.get(path)
            if not route:
                runtime_blockers.append(f"PUBLIC_LANDING_MANIFEST is missing route `{path}` referenced by `{card_id}`.")
                continue
            expected_purpose = _expected_route_purpose(path)
            if expected_purpose and _normalize_text(route.get("purpose")) != expected_purpose:
                runtime_blockers.append(
                    f"PUBLIC_LANDING_MANIFEST route `{path}` purpose drifted from `{expected_purpose}`."
                )
            if route.get("must_exist") is not True:
                runtime_blockers.append(f"PUBLIC_LANDING_MANIFEST route `{path}` no longer carries must_exist=true.")
        monitored_cards.append(
            {
                "id": card_id,
                "horizon_id": PUBLIC_CARD_TO_HORIZON[card_id],
                "badge": badge,
                "detail_route": detail_route,
                "detail_primary_href": detail_primary_href,
                "proof_note_present": bool(_normalize_text(card.get("proof_note"))),
            }
        )
    return {
        "state": "pass" if not issues else "fail",
        "issues": issues,
        "warnings": warnings,
        "runtime_blockers": runtime_blockers,
        "monitored_public_card_count": len(monitored_cards),
        "monitored_public_cards": monitored_cards,
    }


def _public_guide_boundary_monitor(public_guide_root: Path) -> Dict[str, Any]:
    issues: List[str] = []
    monitored_docs: Dict[str, Dict[str, Any]] = {}
    for doc_id, markers in PUBLIC_GUIDE_MARKERS.items():
        path = public_guide_root / f"{doc_id.replace('_', '-')}.md"
        text = _load_text(path)
        if not text:
            issues.append(f"Public guide horizon doc is missing or unreadable: {path}")
            monitored_docs[doc_id] = {"state": "fail", "issues": [f"missing: {path}"]}
            continue
        monitor = _marker_monitor(text, markers, label=f"Public guide {doc_id}")
        monitored_docs[doc_id] = monitor
        issues.extend(monitor.get("issues") or [])
    return {"state": "pass" if not issues else "fail", "issues": issues, "docs": monitored_docs}


def _single_packet_monitor(
    *,
    label: str,
    payload: Dict[str, Any],
    now: dt.datetime,
    acceptable_statuses: set[str],
) -> Dict[str, Any]:
    issues: List[str] = []
    runtime_blockers: List[str] = []
    if not payload:
        issues.append(f"{label} artifact is missing or invalid.")
        return {
            "state": "fail",
            "issues": issues,
            "runtime_blockers": runtime_blockers,
            "status": "missing",
            "generated_at": "",
            "age_hours": None,
        }
    status = _normalize_text(payload.get("status"))
    generated_at = _normalize_text(payload.get("generated_at") or payload.get("generatedAt"))
    age = _age_hours(generated_at, now=now)
    if status.lower() not in acceptable_statuses:
        runtime_blockers.append(f"{label} status is {status or 'unknown'}.")
    if age is None:
        issues.append(f"{label} generated_at is missing or invalid.")
    elif age > PROOF_FRESHNESS_HOURS:
        runtime_blockers.append(
            f"{label} freshness exceeded the {PROOF_FRESHNESS_HOURS}h threshold ({age}h)."
        )
    return {
        "state": "pass" if not issues else "fail",
        "issues": issues,
        "runtime_blockers": runtime_blockers,
        "status": status,
        "generated_at": generated_at,
        "age_hours": age,
    }


def _journey_state_monitor(payload: Dict[str, Any], now: dt.datetime) -> Dict[str, Any]:
    issues: List[str] = []
    runtime_blockers: List[str] = []
    if not payload:
        issues.append("JOURNEY_GATES artifact is missing or invalid.")
        return {
            "state": "fail",
            "issues": issues,
            "runtime_blockers": runtime_blockers,
            "generated_at": "",
            "age_hours": None,
            "monitored_journeys": [],
        }
    generated_at = _normalize_text(payload.get("generated_at") or payload.get("generatedAt"))
    age = _age_hours(generated_at, now=now)
    if age is None:
        issues.append("JOURNEY_GATES generated_at is missing or invalid.")
    elif age > PROOF_FRESHNESS_HOURS:
        runtime_blockers.append(
            f"JOURNEY_GATES freshness exceeded the {PROOF_FRESHNESS_HOURS}h threshold ({age}h)."
        )
    journeys = {
        _normalize_text(row.get("id")): dict(row)
        for row in payload.get("journeys") or []
        if isinstance(row, dict) and _normalize_text(row.get("id"))
    }
    monitored: List[Dict[str, Any]] = []
    for journey_id in TARGET_JOURNEY_IDS:
        row = journeys.get(journey_id, {})
        if not row:
            runtime_blockers.append(f"JOURNEY_GATES is missing journey `{journey_id}`.")
            continue
        state = _normalize_text(row.get("state"))
        if state != "ready":
            runtime_blockers.append(f"Journey `{journey_id}` is {state or 'unknown'}.")
        monitored.append(
            {
                "id": journey_id,
                "state": state,
                "blocking_reason_count": len(_normalize_list(row.get("blocking_reasons"))),
                "warning_reason_count": len(_normalize_list(row.get("warning_reasons"))),
            }
        )
    return {
        "state": "pass" if not issues else "fail",
        "issues": issues,
        "runtime_blockers": runtime_blockers,
        "generated_at": generated_at,
        "age_hours": age,
        "monitored_journeys": monitored,
    }


def _dependency_proof_monitor(
    *,
    m133_payload: Dict[str, Any],
    m131_payload: Dict[str, Any],
    flagship_payload: Dict[str, Any],
    journey_payload: Dict[str, Any],
    now: dt.datetime,
) -> Dict[str, Any]:
    issues: List[str] = []
    runtime_blockers: List[str] = []
    m133_monitor = _single_packet_monitor(
        label="M133 media/social horizon monitors",
        payload=m133_payload,
        now=now,
        acceptable_statuses={"pass"},
    )
    m131_monitor = _single_packet_monitor(
        label="M131 public guide gates",
        payload=m131_payload,
        now=now,
        acceptable_statuses={"pass"},
    )
    flagship_monitor = _single_packet_monitor(
        label="FLAGSHIP_PRODUCT_READINESS",
        payload=flagship_payload,
        now=now,
        acceptable_statuses={"pass"},
    )
    journey_monitor = _journey_state_monitor(journey_payload, now=now)
    flagship_planes = dict(flagship_payload.get("readiness_planes") or {})
    flagship_ready = dict(flagship_planes.get("flagship_ready") or {})
    if flagship_ready and _normalize_text(flagship_ready.get("status")) != "ready":
        runtime_blockers.append(
            f"FLAGSHIP_PRODUCT_READINESS flagship_ready plane is {_normalize_text(flagship_ready.get('status')) or 'unknown'}."
        )
    for name, section in (
        ("m133", m133_monitor),
        ("m131", m131_monitor),
        ("flagship", flagship_monitor),
        ("journey", journey_monitor),
    ):
        issues.extend(f"{name}: {issue}" for issue in section.get("issues") or [])
        runtime_blockers.extend(f"{name}: {issue}" for issue in section.get("runtime_blockers") or [])
    return {
        "state": "pass" if not issues else "fail",
        "issues": issues,
        "runtime_blockers": runtime_blockers,
        "m133_media_social": m133_monitor,
        "m131_public_guide": m131_monitor,
        "flagship_readiness": flagship_monitor,
        "journeys": journey_monitor,
    }


def build_payload(
    *,
    registry_path: Path,
    fleet_queue_path: Path,
    design_queue_path: Path,
    next90_guide_path: Path,
    roadmap_path: Path,
    horizon_registry_path: Path,
    ltd_integration_guide_path: Path,
    external_tools_plane_path: Path,
    open_runs_community_hub_path: Path,
    open_runs_honors_path: Path,
    community_safety_states_path: Path,
    creator_publication_policy_path: Path,
    public_concierge_workflows_path: Path,
    public_feature_registry_path: Path,
    public_landing_manifest_path: Path,
    public_release_experience_path: Path,
    public_guide_root: Path,
    m133_media_social_monitors_path: Path,
    m131_public_guide_gates_path: Path,
    flagship_readiness_path: Path,
    journey_gates_path: Path,
    generated_at: str | None = None,
) -> Dict[str, Any]:
    generated_at = generated_at or _utc_now()
    reference_now = _parse_iso_utc(generated_at) or dt.datetime.now(dt.timezone.utc)
    registry = _load_yaml(registry_path)
    fleet_queue = _load_yaml(fleet_queue_path)
    design_queue = _load_yaml(design_queue_path)
    next90_guide = _load_text(next90_guide_path)
    roadmap = _load_text(roadmap_path)
    horizon_registry = _load_yaml(horizon_registry_path)
    ltd_integration_guide = _load_text(ltd_integration_guide_path)
    external_tools_plane = _load_text(external_tools_plane_path)
    open_runs_community_hub = _load_text(open_runs_community_hub_path)
    open_runs_honors = _load_yaml(open_runs_honors_path)
    community_safety_states = _load_yaml(community_safety_states_path)
    creator_publication_policy = _load_text(creator_publication_policy_path)
    public_concierge_workflows = _load_yaml(public_concierge_workflows_path)
    public_feature_registry = _load_yaml(public_feature_registry_path)
    public_landing_manifest = _load_yaml(public_landing_manifest_path)
    public_release_experience = _load_text(public_release_experience_path)
    m133_media_social_monitors = _load_json(m133_media_social_monitors_path)
    m131_public_guide_gates = _load_json(m131_public_guide_gates_path)
    flagship_readiness = _load_json(flagship_readiness_path)
    journey_gates = _load_json(journey_gates_path)

    milestone = _find_milestone(registry, MILESTONE_ID)
    work_task = _find_work_task(milestone, WORK_TASK_ID)
    fleet_queue_item = _find_queue_item(fleet_queue, WORK_TASK_ID)
    design_queue_item = _find_queue_item(design_queue, WORK_TASK_ID)

    guide_monitor = _marker_monitor(next90_guide, GUIDE_MARKERS, label="Next90 guide canon")
    roadmap_monitor = _marker_monitor(roadmap, ROADMAP_MARKERS, label="Roadmap canon")
    ltd_guide_monitor = _marker_monitor(ltd_integration_guide, LTD_GUIDE_MARKERS, label="LTD integration guide canon")
    external_tools_monitor = _marker_monitor(external_tools_plane, EXTERNAL_TOOLS_MARKERS, label="External tools plane canon")
    open_runs_monitor = _marker_monitor(open_runs_community_hub, OPEN_RUNS_MARKERS, label="Open runs and Community Hub canon")
    creator_policy_monitor = _marker_monitor(
        creator_publication_policy,
        CREATOR_POLICY_MARKERS,
        label="Creator publication policy canon",
    )
    public_release_monitor = _marker_monitor(
        public_release_experience,
        PUBLIC_RELEASE_MARKERS,
        label="Public release experience canon",
    )
    queue_alignment = _queue_alignment(
        work_task=work_task,
        fleet_queue_item=fleet_queue_item,
        design_queue_item=design_queue_item,
    )
    horizon_monitor = _horizon_registry_monitor(horizon_registry)
    consent_monitor = _consent_registry_monitor(open_runs_honors, community_safety_states)
    concierge_monitor = _public_concierge_workflow_monitor(public_concierge_workflows)
    public_guide_monitor = _public_guide_boundary_monitor(public_guide_root)
    public_feature_monitor = _public_feature_registry_monitor(public_feature_registry, public_landing_manifest)
    dependency_monitor = _dependency_proof_monitor(
        m133_payload=m133_media_social_monitors,
        m131_payload=m131_public_guide_gates,
        flagship_payload=flagship_readiness,
        journey_payload=journey_gates,
        now=reference_now,
    )

    blockers: List[str] = []
    runtime_blockers: List[str] = []
    warnings: List[str] = []
    for name, section in (
        ("next90_guide", guide_monitor),
        ("roadmap", roadmap_monitor),
        ("queue_alignment", queue_alignment),
        ("horizon_registry", horizon_monitor),
        ("ltd_integration_guide", ltd_guide_monitor),
        ("external_tools_plane", external_tools_monitor),
        ("open_runs_community_hub", open_runs_monitor),
        ("open_runs_consent", consent_monitor),
        ("creator_publication_policy", creator_policy_monitor),
        ("public_concierge_workflows", concierge_monitor),
        ("public_release_experience", public_release_monitor),
        ("public_guide_boundaries", public_guide_monitor),
        ("public_feature_posture", public_feature_monitor),
        ("dependency_proof", dependency_monitor),
    ):
        blockers.extend(f"{name}: {issue}" for issue in section.get("issues") or [])
        runtime_blockers.extend(f"{name}: {issue}" for issue in section.get("runtime_blockers") or [])
        warnings.extend(section.get("warnings") or [])

    ecosystem_seam_status = "blocked" if runtime_blockers else "warning" if warnings else "pass"
    return {
        "contract_name": "fleet.next90_m137_ecosystem_seam_monitors",
        "generated_at": generated_at,
        "status": "pass" if not blockers else "blocked",
        "package_id": PACKAGE_ID,
        "frontier_id": FRONTIER_ID,
        "milestone_id": MILESTONE_ID,
        "work_task_id": WORK_TASK_ID,
        "wave": WAVE_ID,
        "queue_title": QUEUE_TITLE,
        "owned_surfaces": OWNED_SURFACES,
        "allowed_paths": ALLOWED_PATHS,
        "canonical_monitors": {
            "next90_guide": guide_monitor,
            "roadmap": roadmap_monitor,
            "queue_alignment": queue_alignment,
            "horizon_registry": horizon_monitor,
            "ltd_integration_guide": ltd_guide_monitor,
            "external_tools_plane": external_tools_monitor,
            "open_runs_community_hub": open_runs_monitor,
            "open_runs_consent": consent_monitor,
            "creator_publication_policy": creator_policy_monitor,
            "public_concierge_workflows": concierge_monitor,
            "public_release_experience": public_release_monitor,
            "public_guide_boundaries": public_guide_monitor,
        },
        "runtime_monitors": {
            "public_feature_posture": public_feature_monitor,
            "dependency_proof": dependency_monitor,
        },
        "monitor_summary": {
            "ecosystem_seam_status": ecosystem_seam_status,
            "runtime_blocker_count": len(runtime_blockers),
            "warning_count": len(warnings),
            "monitored_horizon_count": horizon_monitor.get("monitored_horizon_count"),
            "monitored_public_card_count": public_feature_monitor.get("monitored_public_card_count"),
            "dependency_runtime_blocker_count": len(dependency_monitor.get("runtime_blockers") or []),
            "runtime_blockers": runtime_blockers,
        },
        "package_closeout": {
            "state": "pass" if not blockers else "blocked",
            "blockers": blockers,
            "warnings": list(runtime_blockers) + warnings,
        },
        "source_inputs": {
            "successor_registry": _source_link(registry_path, registry),
            "fleet_queue_staging": _source_link(fleet_queue_path, fleet_queue),
            "design_queue_staging": _source_link(design_queue_path, design_queue),
            "next90_guide": _text_source_link(next90_guide_path),
            "roadmap": _text_source_link(roadmap_path),
            "horizon_registry": _source_link(horizon_registry_path, horizon_registry),
            "ltd_integration_guide": _text_source_link(ltd_integration_guide_path),
            "external_tools_plane": _text_source_link(external_tools_plane_path),
            "open_runs_community_hub": _text_source_link(open_runs_community_hub_path),
            "open_runs_honors": _source_link(open_runs_honors_path, open_runs_honors),
            "community_safety_states": _source_link(community_safety_states_path, community_safety_states),
            "creator_publication_policy": _text_source_link(creator_publication_policy_path),
            "public_concierge_workflows": _source_link(public_concierge_workflows_path, public_concierge_workflows),
            "public_feature_registry": _source_link(public_feature_registry_path, public_feature_registry),
            "public_landing_manifest": _source_link(public_landing_manifest_path, public_landing_manifest),
            "public_release_experience": _text_source_link(public_release_experience_path),
            "public_guide_root": _text_source_link(public_guide_root),
            "m133_media_social_monitors": _source_link(m133_media_social_monitors_path, m133_media_social_monitors),
            "m131_public_guide_gates": _source_link(m131_public_guide_gates_path, m131_public_guide_gates),
            "flagship_readiness": _source_link(flagship_readiness_path, flagship_readiness),
            "journey_gates": _source_link(journey_gates_path, journey_gates),
        },
    }


def render_markdown(payload: Dict[str, Any]) -> str:
    summary = dict(payload.get("monitor_summary") or {})
    closeout = dict(payload.get("package_closeout") or {})
    lines = [
        "# Fleet M137 ecosystem seam monitors",
        "",
        f"- status: {payload.get('status')}",
        f"- ecosystem_seam_status: {summary.get('ecosystem_seam_status')}",
        f"- package_id: {payload.get('package_id')}",
        f"- frontier_id: {payload.get('frontier_id')}",
        f"- generated_at: {payload.get('generated_at')}",
        "",
        "## Runtime summary",
        f"- monitored_horizon_count: {summary.get('monitored_horizon_count')}",
        f"- monitored_public_card_count: {summary.get('monitored_public_card_count')}",
        f"- dependency_runtime_blocker_count: {summary.get('dependency_runtime_blocker_count')}",
        f"- runtime_blocker_count: {summary.get('runtime_blocker_count')}",
        f"- warning_count: {summary.get('warning_count')}",
        "",
        "## Package closeout",
        f"- state: {closeout.get('state') or 'blocked'}",
    ]
    if closeout.get("blockers"):
        lines.append("- blockers:")
        lines.extend(f"  - {item}" for item in closeout["blockers"])
    if closeout.get("warnings"):
        lines.append("- warnings:")
        lines.extend(f"  - {item}" for item in closeout["warnings"])
    return "\n".join(lines) + "\n"


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    output_path = Path(args.output).resolve()
    markdown_path = Path(args.markdown_output).resolve()
    payload = build_payload(
        registry_path=Path(args.successor_registry).resolve(),
        fleet_queue_path=Path(args.fleet_queue_staging).resolve(),
        design_queue_path=Path(args.design_queue_staging).resolve(),
        next90_guide_path=Path(args.next90_guide).resolve(),
        roadmap_path=Path(args.roadmap).resolve(),
        horizon_registry_path=Path(args.horizon_registry).resolve(),
        ltd_integration_guide_path=Path(args.ltd_integration_guide).resolve(),
        external_tools_plane_path=Path(args.external_tools_plane).resolve(),
        open_runs_community_hub_path=Path(args.open_runs_community_hub).resolve(),
        open_runs_honors_path=Path(args.open_runs_honors).resolve(),
        community_safety_states_path=Path(args.community_safety_states).resolve(),
        creator_publication_policy_path=Path(args.creator_publication_policy).resolve(),
        public_concierge_workflows_path=Path(args.public_concierge_workflows).resolve(),
        public_feature_registry_path=Path(args.public_feature_registry).resolve(),
        public_landing_manifest_path=Path(args.public_landing_manifest).resolve(),
        public_release_experience_path=Path(args.public_release_experience).resolve(),
        public_guide_root=Path(args.public_guide_root).resolve(),
        m133_media_social_monitors_path=Path(args.m133_media_social_monitors).resolve(),
        m131_public_guide_gates_path=Path(args.m131_public_guide_gates).resolve(),
        flagship_readiness_path=Path(args.flagship_readiness).resolve(),
        journey_gates_path=Path(args.journey_gates).resolve(),
    )
    _write_json_file(output_path, payload)
    _write_markdown_file(markdown_path, render_markdown(payload))
    print(json.dumps({"status": payload["status"], "artifact": str(output_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
