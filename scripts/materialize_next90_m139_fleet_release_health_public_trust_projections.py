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

PACKAGE_ID = "next90-m139-fleet-bind-community-safety-event-and-appeal-states-world-broadcast-recipe-r"
FRONTIER_ID = 2565904250
MILESTONE_ID = 139
WORK_TASK_ID = "139.10"
WAVE_ID = "W26"
QUEUE_TITLE = (
    "Bind COMMUNITY_SAFETY_EVENT_AND_APPEAL_STATES, WORLD_BROADCAST_RECIPE_REGISTRY, "
    "CREATOR_PUBLICATION_ANALYTICS_SCHEMA, and ACCESSIBILITY_COGNITIVE_LOAD_GATES into machine-readable "
    "release-health and public-trust projections."
)
OWNED_SURFACES = ["bind_community_safety_event_and_appeal_states_world_broa:fleet"]
ALLOWED_PATHS = ["scripts", "tests", ".codex-studio", "feedback"]

DEFAULT_OUTPUT = PUBLISHED / "NEXT90_M139_FLEET_RELEASE_HEALTH_PUBLIC_TRUST_PROJECTIONS.generated.json"
DEFAULT_MARKDOWN = PUBLISHED / "NEXT90_M139_FLEET_RELEASE_HEALTH_PUBLIC_TRUST_PROJECTIONS.generated.md"

SUCCESSOR_REGISTRY = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
FLEET_QUEUE_STAGING = PUBLISHED / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
DESIGN_QUEUE_STAGING = PRODUCT_MIRROR / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
NEXT90_GUIDE = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_GUIDE.md"
PREP_PACKET_FACTORY = PRODUCT_MIRROR / "PREP_PACKET_FACTORY_AND_PROCEDURAL_TABLES.md"
OPPOSITION_PACKET_REGISTRY = PRODUCT_MIRROR / "OPPOSITION_PACKET_REGISTRY.yaml"
WORLD_BROADCAST_CADENCE = PRODUCT_MIRROR / "WORLD_BROADCAST_AND_FACTION_PROPAGANDA_CADENCE.md"
WORLD_BROADCAST_RECIPE_REGISTRY = PRODUCT_MIRROR / "WORLD_BROADCAST_RECIPE_REGISTRY.yaml"
COMMUNITY_SAFETY_DOC = PRODUCT_MIRROR / "COMMUNITY_SAFETY_MODERATION_AND_APPEALS.md"
COMMUNITY_SAFETY_STATES = PRODUCT_MIRROR / "COMMUNITY_SAFETY_EVENT_AND_APPEAL_STATES.yaml"
CREATOR_ANALYTICS_DOC = PRODUCT_MIRROR / "CREATOR_DASHBOARD_AND_ADOPTION_ANALYTICS.md"
CREATOR_ANALYTICS_SCHEMA = PRODUCT_MIRROR / "CREATOR_PUBLICATION_ANALYTICS_SCHEMA.yaml"
CREATOR_TRUST_POLICY = PRODUCT_MIRROR / "CREATOR_PUBLICATION_TRUST_AND_COMPATIBILITY_POLICY.md"
PRODUCT_ANALYTICS_MODEL = PRODUCT_MIRROR / "PRODUCT_ANALYTICS_AND_JOURNEY_PROOF_MODEL.md"
ACCESSIBILITY_RELEASE_BAR = PRODUCT_MIRROR / "ACCESSIBILITY_AND_COGNITIVE_LOAD_RELEASE_BAR.md"
ACCESSIBILITY_GATES = PRODUCT_MIRROR / "ACCESSIBILITY_COGNITIVE_LOAD_GATES.yaml"
PUBLIC_FAQ_REGISTRY = PRODUCT_MIRROR / "PUBLIC_FAQ_REGISTRY.yaml"
PUBLIC_FEATURE_REGISTRY = PRODUCT_MIRROR / "PUBLIC_FEATURE_REGISTRY.yaml"
PUBLIC_LANDING_MANIFEST = PRODUCT_MIRROR / "PUBLIC_LANDING_MANIFEST.yaml"

GUIDE_MARKERS = {
    "wave_26": "## Wave 26 - make the world, creator, and trust loops feel lived-in",
    "milestone_139": "### 139. GM tonight pack, world broadcast cadence, creator analytics, community safety, and cognitive-load trust closure",
}
PREP_PACKET_MARKERS = {
    "proposal_scope": "It should begin with one usable packet a GM can run tonight.",
    "first_proof": "one job",
    "release_gate": "gm_creates_a_playable_prep_packet",
}
WORLD_BROADCAST_MARKERS = {
    "receipts": "Broadcasts are projections of approved truth, not independent fiction.",
    "weekly_cadence": "* one city ticker",
    "authority_rule": "* `ResolutionReport`",
}
COMMUNITY_SAFETY_MARKERS = {
    "minimum_event_families": "* observer-consent violation",
    "required_states": "* a `CommunityScaleAuditPacket` or linked support-case receipt",
    "boundary": "They do not become support closure truth, release truth, or hidden organizer superpowers.",
}
CREATOR_ANALYTICS_MARKERS = {
    "discoverability_boundary": "Trust-ranking language must stay about discoverability order, not creator virtue or platform safety.",
    "claim_rule": "* use moderation status as a proxy for compatibility",
    "privacy_boundary": "They must not expose private campaign names, private runner identities, or sensitive play telemetry.",
}
CREATOR_TRUST_POLICY_MARKERS = {
    "truth_order": "## Truth order",
    "fallback": "If compatibility receipts are stale or missing, the product must say compatibility is unknown.",
    "forbidden": "* present trust ranking as a platform safety certification or social credit score",
}
PRODUCT_ANALYTICS_MARKERS = {
    "core_rule": "Hub owns journey receipts. Analytics tools observe and aggregate. Product Governor interprets.",
    "privacy": "Do not collect raw character sheets, campaign notes, private runner state, support payloads, raw transcripts, or sourcebook text for analytics.",
}
ACCESSIBILITY_RELEASE_BAR_MARKERS = {
    "keyboard_first": "* keyboard-first dense workflows where the product claims expert speed",
    "mobile_glanceability": "* mobile glanceability for recap, readiness, and consequence moments",
    "what_matters_now": "* what matters right now",
}

REQUIRED_WORLD_RECIPES = {
    "weekly_city_ticker": {"WorldTick", "NewsItem"},
    "faction_spin_card": {"ResolutionReport", "WorldTick"},
    "gm_job_digest": {"JobPacket", "IntelReport"},
    "public_safe_media_card": {"NewsItem", "WorldTick"},
    "recruitment_or_announcement_packet": {"OpenRun", "NewsItem"},
}
REQUIRED_EVENT_FAMILIES = {
    "no_show",
    "unsafe_content",
    "harassment",
    "spoiler_leak",
    "application_dispute",
    "gm_or_organizer_escalation",
    "faction_or_leaderboard_gaming",
    "observer_consent_violation",
}
REQUIRED_EVENT_STATES = {
    "reported",
    "triaged",
    "evidence_requested",
    "temporary_action",
    "resolved",
    "appealed",
    "closed",
}
REQUIRED_EVENT_FIELDS = {
    "reporter_visibility",
    "subject_visibility",
    "evidence_posture",
    "retention_posture",
    "publication_posture",
    "appeal_deadline",
}
REQUIRED_ANALYTICS_FIELDS = {
    "compatibility_posture",
    "moderation_status",
    "trust_ranking_posture",
    "trust_ranking_reason_chips",
    "adoption_band",
    "update_request_count_band",
    "support_issue_count_band",
    "media_collateral_status",
}
REQUIRED_PRIVACY_RULES = {
    "no_private_campaign_names",
    "no_private_runner_names",
    "no_raw_character_sheet_warehouse",
    "no_sensitive_session_telemetry_exposure",
}
REQUIRED_CLAIM_GUARDS = {
    "compatibility_posture_must_not_be_inferred_from_moderation_status",
    "moderation_status_must_not_claim_build_or_rule_environment_fit",
    "trust_ranking_posture_must_not_claim_creator_endorsement_or_platform_safety",
    "adoption_and_support_fields_must_be_banded_before_public_exposure",
    "unknown_compatibility_must_stay_visible_until_receipts_are_current",
}
REQUIRED_ACCESSIBILITY_GATES = {
    "keyboard_first_expert_workflow": {"flagship_desktop_workbench", "dense_builder", "ready_for_tonight"},
    "warning_and_legality_clarity": {"build_lab", "explain_drawer", "run_application_preflight"},
    "reduced_motion_safe_critical_flows": {"install_and_first_run", "recovery_and_restore", "recap_and_return_moment"},
    "screen_reader_safe_trust_surfaces": {"install_help", "explain", "recovery", "support"},
    "mobile_glanceability": {"recap", "ready_for_tonight", "consequence_feed"},
}
REQUIRED_OPPOSITION_FAMILIES = {
    "ganger_squad",
    "corp_security_team",
    "spirit_cell",
    "drone_team",
    "beginner_one_shot_bundle",
}
REQUIRED_FAQ_QUESTIONS = {
    "Can I participate privately?": ("opt-in", "private participation"),
    "What are badges and leaderboards for?": ("recognition", "not authority"),
}
REQUIRED_PUBLIC_CARD_BADGES = {
    "lane_creator": "Preview lane",
    "horizon_community_hub": "Research",
    "horizon_black_ledger": "Research",
    "productlift_feedback": "Public",
    "productlift_roadmap": "Projection",
    "productlift_changelog": "Closeout",
}
REQUIRED_PUBLIC_ROUTE_PURPOSES = {
    "/artifacts": "teaser_gallery",
    "/roadmap/community-hub": "roadmap_detail",
    "/roadmap/black-ledger": "roadmap_detail",
    "/feedback": "public_feedback_entry",
    "/roadmap": "horizon_summary",
    "/changelog": "release_history",
}
PUBLIC_CARD_IDS = (
    "lane_creator",
    "horizon_community_hub",
    "horizon_black_ledger",
    "productlift_feedback",
    "productlift_roadmap",
    "productlift_changelog",
)
PUBLIC_ROUTE_IDS = ("/artifacts", "/roadmap/community-hub", "/roadmap/black-ledger", "/feedback", "/roadmap", "/changelog")


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize the Fleet M139 release-health/public-trust projection packet.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--markdown-output", default=str(DEFAULT_MARKDOWN))
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--fleet-queue-staging", default=str(FLEET_QUEUE_STAGING))
    parser.add_argument("--design-queue-staging", default=str(DESIGN_QUEUE_STAGING))
    parser.add_argument("--next90-guide", default=str(NEXT90_GUIDE))
    parser.add_argument("--prep-packet-factory", default=str(PREP_PACKET_FACTORY))
    parser.add_argument("--opposition-packet-registry", default=str(OPPOSITION_PACKET_REGISTRY))
    parser.add_argument("--world-broadcast-cadence", default=str(WORLD_BROADCAST_CADENCE))
    parser.add_argument("--world-broadcast-recipe-registry", default=str(WORLD_BROADCAST_RECIPE_REGISTRY))
    parser.add_argument("--community-safety-doc", default=str(COMMUNITY_SAFETY_DOC))
    parser.add_argument("--community-safety-states", default=str(COMMUNITY_SAFETY_STATES))
    parser.add_argument("--creator-analytics-doc", default=str(CREATOR_ANALYTICS_DOC))
    parser.add_argument("--creator-analytics-schema", default=str(CREATOR_ANALYTICS_SCHEMA))
    parser.add_argument("--creator-trust-policy", default=str(CREATOR_TRUST_POLICY))
    parser.add_argument("--product-analytics-model", default=str(PRODUCT_ANALYTICS_MODEL))
    parser.add_argument("--accessibility-release-bar", default=str(ACCESSIBILITY_RELEASE_BAR))
    parser.add_argument("--accessibility-gates", default=str(ACCESSIBILITY_GATES))
    parser.add_argument("--public-faq-registry", default=str(PUBLIC_FAQ_REGISTRY))
    parser.add_argument("--public-feature-registry", default=str(PUBLIC_FEATURE_REGISTRY))
    parser.add_argument("--public-landing-manifest", default=str(PUBLIC_LANDING_MANIFEST))
    return parser.parse_args(argv)


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_list(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []
    return [_normalize_text(value) for value in values if _normalize_text(value)]


def _load_yaml(path: Path) -> Dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, yaml.YAMLError):
        return {}
    try:
        payload = yaml.safe_load(raw) or {}
    except yaml.YAMLError:
        marker = "\nitems:\n"
        if marker not in raw:
            return {}
        try:
            payload = yaml.safe_load("items:\n" + raw.split(marker, 1)[1]) or {}
        except yaml.YAMLError:
            return {}
    if isinstance(payload, list):
        return {"items": payload}
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


def _file_generated_at(path: Path) -> str:
    try:
        return dt.datetime.fromtimestamp(path.stat().st_mtime, tz=dt.timezone.utc).replace(microsecond=0).isoformat().replace(
            "+00:00", "Z"
        )
    except OSError:
        return ""


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve())
    except OSError:
        return str(path)


def _write_json_file(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _source_link(path: Path, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "path": _display_path(path),
        "sha256": _sha256_file(path),
        "generated_at": _normalize_text(payload.get("generated_at") or payload.get("generatedAt")) or _file_generated_at(path),
    }


def _text_source_link(path: Path) -> Dict[str, Any]:
    return {"path": _display_path(path), "sha256": _sha256_file(path), "generated_at": _file_generated_at(path)}


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


def _marker_monitor(text: str, markers: Dict[str, str], *, label: str) -> Dict[str, Any]:
    normalized_text = " ".join(text.split())
    checks = {
        name: marker in text or " ".join(marker.split()) in normalized_text
        for name, marker in markers.items()
    }
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
        warnings.append("Fleet queue mirror row is still missing for work task 139.10.")
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
    for label, row in (("design", design_queue_item), ("fleet", fleet_queue_item)):
        if not row:
            continue
        for key, value in expected.items():
            if row.get(key) != value:
                issues.append(f"{label} queue row {key} drifted from the assigned M139 package.")
        if sorted(_normalize_list(row.get("allowed_paths"))) != sorted(ALLOWED_PATHS):
            issues.append(f"{label} queue row allowed_paths drifted from the assigned M139 package.")
        if sorted(_normalize_list(row.get("owned_surfaces"))) != sorted(OWNED_SURFACES):
            issues.append(f"{label} queue row owned_surfaces drifted from the assigned M139 package.")
    return {"state": "pass" if not issues else "fail", "issues": issues, "warnings": warnings}


def _world_broadcast_registry_monitor(payload: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    recipes = {
        _normalize_text(row.get("id")): set(_normalize_list(row.get("source_objects")))
        for row in payload.get("recipes") or []
        if isinstance(row, dict) and _normalize_text(row.get("id"))
    }
    for recipe_id, expected_sources in REQUIRED_WORLD_RECIPES.items():
        observed = recipes.get(recipe_id)
        if observed is None:
            issues.append(f"WORLD_BROADCAST_RECIPE_REGISTRY is missing recipe `{recipe_id}`.")
            continue
        missing = sorted(expected_sources - observed)
        if missing:
            issues.append(f"WORLD_BROADCAST_RECIPE_REGISTRY `{recipe_id}` is missing source_objects: {', '.join(missing)}.")
    return {"state": "pass" if not issues else "fail", "issues": issues}


def _community_safety_state_monitor(payload: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    event_families = set(_normalize_list(payload.get("event_families")))
    states = set(_normalize_list(payload.get("states")))
    fields = set(_normalize_list(payload.get("required_fields")))
    missing_families = sorted(REQUIRED_EVENT_FAMILIES - event_families)
    missing_states = sorted(REQUIRED_EVENT_STATES - states)
    missing_fields = sorted(REQUIRED_EVENT_FIELDS - fields)
    if missing_families:
        issues.append("COMMUNITY_SAFETY_EVENT_AND_APPEAL_STATES is missing event_families: " + ", ".join(missing_families) + ".")
    if missing_states:
        issues.append("COMMUNITY_SAFETY_EVENT_AND_APPEAL_STATES is missing states: " + ", ".join(missing_states) + ".")
    if missing_fields:
        issues.append("COMMUNITY_SAFETY_EVENT_AND_APPEAL_STATES is missing required_fields: " + ", ".join(missing_fields) + ".")
    return {"state": "pass" if not issues else "fail", "issues": issues}


def _creator_analytics_schema_monitor(payload: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    fields = {
        _normalize_text(row.get("id")): dict(row)
        for row in payload.get("fields") or []
        if isinstance(row, dict) and _normalize_text(row.get("id"))
    }
    missing_fields = sorted(REQUIRED_ANALYTICS_FIELDS - set(fields))
    if missing_fields:
        issues.append("CREATOR_PUBLICATION_ANALYTICS_SCHEMA is missing fields: " + ", ".join(missing_fields) + ".")
    privacy_rules = set(_normalize_list(payload.get("privacy_rules")))
    claim_guards = set(_normalize_list(payload.get("claim_guards")))
    missing_privacy = sorted(REQUIRED_PRIVACY_RULES - privacy_rules)
    missing_claim_guards = sorted(REQUIRED_CLAIM_GUARDS - claim_guards)
    if missing_privacy:
        issues.append("CREATOR_PUBLICATION_ANALYTICS_SCHEMA is missing privacy_rules: " + ", ".join(missing_privacy) + ".")
    if missing_claim_guards:
        issues.append("CREATOR_PUBLICATION_ANALYTICS_SCHEMA is missing claim_guards: " + ", ".join(missing_claim_guards) + ".")
    return {"state": "pass" if not issues else "fail", "issues": issues}


def _accessibility_gate_monitor(payload: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    gates = {
        _normalize_text(row.get("id")): set(_normalize_list(row.get("required_surfaces")))
        for row in payload.get("gates") or []
        if isinstance(row, dict) and _normalize_text(row.get("id"))
    }
    for gate_id, expected_surfaces in REQUIRED_ACCESSIBILITY_GATES.items():
        observed = gates.get(gate_id)
        if observed is None:
            issues.append(f"ACCESSIBILITY_COGNITIVE_LOAD_GATES is missing gate `{gate_id}`.")
            continue
        missing = sorted(expected_surfaces - observed)
        if missing:
            issues.append(f"ACCESSIBILITY_COGNITIVE_LOAD_GATES `{gate_id}` is missing required_surfaces: {', '.join(missing)}.")
    return {"state": "pass" if not issues else "fail", "issues": issues}


def _opposition_registry_monitor(payload: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    families = {
        _normalize_text(row.get("id"))
        for row in payload.get("packet_families") or []
        if isinstance(row, dict) and _normalize_text(row.get("id"))
    }
    missing = sorted(REQUIRED_OPPOSITION_FAMILIES - families)
    if missing:
        issues.append("OPPOSITION_PACKET_REGISTRY is missing packet_families: " + ", ".join(missing) + ".")
    return {"state": "pass" if not issues else "fail", "issues": issues}


def _faq_registry_monitor(payload: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    entries = _faq_entries(payload)
    for question, markers in REQUIRED_FAQ_QUESTIONS.items():
        answer = entries.get(question, "")
        if not answer:
            issues.append(f"PUBLIC_FAQ_REGISTRY is missing question `{question}`.")
            continue
        missing = [marker for marker in markers if marker not in answer]
        if missing:
            issues.append(f"PUBLIC_FAQ_REGISTRY `{question}` answer is missing: {', '.join(missing)}.")
    return {"state": "pass" if not issues else "fail", "issues": issues}


def _public_feature_monitor(payload: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    cards = _card_index(payload)
    missing = sorted(set(REQUIRED_PUBLIC_CARD_BADGES) - set(cards))
    if missing:
        issues.append("PUBLIC_FEATURE_REGISTRY is missing cards: " + ", ".join(missing) + ".")
    for card_id, expected_badge in REQUIRED_PUBLIC_CARD_BADGES.items():
        card = dict(cards.get(card_id) or {})
        if not card:
            continue
        badge = _normalize_text(card.get("badge"))
        if badge != expected_badge:
            issues.append(f"PUBLIC_FEATURE_REGISTRY `{card_id}` badge drifted from `{expected_badge}`.")
    return {"state": "pass" if not issues else "fail", "issues": issues}


def _public_landing_monitor(payload: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    routes = _route_index(payload)
    missing = sorted(set(REQUIRED_PUBLIC_ROUTE_PURPOSES) - set(routes))
    if missing:
        issues.append("PUBLIC_LANDING_MANIFEST is missing routes: " + ", ".join(missing) + ".")
    for route_id, expected_purpose in REQUIRED_PUBLIC_ROUTE_PURPOSES.items():
        route = dict(routes.get(route_id) or {})
        if not route:
            continue
        purpose = _normalize_text(route.get("purpose"))
        if purpose != expected_purpose:
            issues.append(f"PUBLIC_LANDING_MANIFEST `{route_id}` purpose drifted from `{expected_purpose}`.")
    return {"state": "pass" if not issues else "fail", "issues": issues}


def _faq_entries(payload: Dict[str, Any]) -> Dict[str, str]:
    entries: Dict[str, str] = {}
    for section in payload.get("sections") or []:
        if not isinstance(section, dict):
            continue
        for row in section.get("entries") or []:
            if not isinstance(row, dict):
                continue
            question = _normalize_text(row.get("question"))
            answer = _normalize_text(row.get("answer"))
            if question:
                entries[question] = answer
    return entries


def _card_index(payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {
        _normalize_text(row.get("id")): dict(row)
        for row in payload.get("cards") or []
        if isinstance(row, dict) and _normalize_text(row.get("id"))
    }


def _route_index(payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    indexed: Dict[str, Dict[str, Any]] = {}
    for collection in ("public_routes", "auth_routes", "registered_routes"):
        for row in payload.get(collection) or []:
            if isinstance(row, dict) and _normalize_text(row.get("path")):
                indexed[_normalize_text(row.get("path"))] = dict(row)
    return indexed


def build_payload(
    *,
    registry_path: Path,
    fleet_queue_path: Path,
    design_queue_path: Path,
    next90_guide_path: Path,
    prep_packet_factory_path: Path,
    opposition_packet_registry_path: Path,
    world_broadcast_cadence_path: Path,
    world_broadcast_recipe_registry_path: Path,
    community_safety_doc_path: Path,
    community_safety_states_path: Path,
    creator_analytics_doc_path: Path,
    creator_analytics_schema_path: Path,
    creator_trust_policy_path: Path,
    product_analytics_model_path: Path,
    accessibility_release_bar_path: Path,
    accessibility_gates_path: Path,
    public_faq_registry_path: Path,
    public_feature_registry_path: Path,
    public_landing_manifest_path: Path,
    generated_at: str | None = None,
) -> Dict[str, Any]:
    generated_at = generated_at or _utc_now()
    registry = _load_yaml(registry_path)
    fleet_queue = _load_yaml(fleet_queue_path)
    design_queue = _load_yaml(design_queue_path)
    next90_guide = _load_text(next90_guide_path)
    prep_packet_factory = _load_text(prep_packet_factory_path)
    opposition_packet_registry = _load_yaml(opposition_packet_registry_path)
    world_broadcast_cadence = _load_text(world_broadcast_cadence_path)
    world_broadcast_recipe_registry = _load_yaml(world_broadcast_recipe_registry_path)
    community_safety_doc = _load_text(community_safety_doc_path)
    community_safety_states = _load_yaml(community_safety_states_path)
    creator_analytics_doc = _load_text(creator_analytics_doc_path)
    creator_analytics_schema = _load_yaml(creator_analytics_schema_path)
    creator_trust_policy = _load_text(creator_trust_policy_path)
    product_analytics_model = _load_text(product_analytics_model_path)
    accessibility_release_bar = _load_text(accessibility_release_bar_path)
    accessibility_gates = _load_yaml(accessibility_gates_path)
    public_faq_registry = _load_yaml(public_faq_registry_path)
    public_feature_registry = _load_yaml(public_feature_registry_path)
    public_landing_manifest = _load_yaml(public_landing_manifest_path)

    milestone = _find_milestone(registry, MILESTONE_ID)
    work_task = _find_work_task(milestone, WORK_TASK_ID)
    fleet_queue_item = _find_queue_item(fleet_queue, WORK_TASK_ID)
    design_queue_item = _find_queue_item(design_queue, WORK_TASK_ID)

    guide_monitor = _marker_monitor(next90_guide, GUIDE_MARKERS, label="Next90 guide canon")
    prep_packet_monitor = _marker_monitor(prep_packet_factory, PREP_PACKET_MARKERS, label="Prep packet canon")
    world_broadcast_monitor = _marker_monitor(world_broadcast_cadence, WORLD_BROADCAST_MARKERS, label="World broadcast canon")
    community_safety_doc_monitor = _marker_monitor(community_safety_doc, COMMUNITY_SAFETY_MARKERS, label="Community safety canon")
    creator_analytics_doc_monitor = _marker_monitor(creator_analytics_doc, CREATOR_ANALYTICS_MARKERS, label="Creator analytics canon")
    creator_trust_policy_monitor = _marker_monitor(creator_trust_policy, CREATOR_TRUST_POLICY_MARKERS, label="Creator trust policy canon")
    product_analytics_monitor = _marker_monitor(product_analytics_model, PRODUCT_ANALYTICS_MARKERS, label="Product analytics model canon")
    accessibility_release_bar_monitor = _marker_monitor(accessibility_release_bar, ACCESSIBILITY_RELEASE_BAR_MARKERS, label="Accessibility release bar canon")
    queue_alignment = _queue_alignment(work_task=work_task, fleet_queue_item=fleet_queue_item, design_queue_item=design_queue_item)
    opposition_registry_monitor = _opposition_registry_monitor(opposition_packet_registry)
    world_recipe_monitor = _world_broadcast_registry_monitor(world_broadcast_recipe_registry)
    community_safety_state_monitor = _community_safety_state_monitor(community_safety_states)
    creator_schema_monitor = _creator_analytics_schema_monitor(creator_analytics_schema)
    accessibility_monitor = _accessibility_gate_monitor(accessibility_gates)
    faq_registry_monitor = _faq_registry_monitor(public_faq_registry)
    public_feature_monitor = _public_feature_monitor(public_feature_registry)
    public_landing_monitor = _public_landing_monitor(public_landing_manifest)

    blockers: List[str] = []
    warnings: List[str] = list(queue_alignment.get("warnings") or [])
    for name, section in (
        ("next90_guide", guide_monitor),
        ("prep_packet_factory", prep_packet_monitor),
        ("world_broadcast_cadence", world_broadcast_monitor),
        ("community_safety_doc", community_safety_doc_monitor),
        ("creator_analytics_doc", creator_analytics_doc_monitor),
        ("creator_trust_policy", creator_trust_policy_monitor),
        ("product_analytics_model", product_analytics_monitor),
        ("accessibility_release_bar", accessibility_release_bar_monitor),
        ("queue_alignment", queue_alignment),
        ("opposition_packet_registry", opposition_registry_monitor),
        ("world_broadcast_recipe_registry", world_recipe_monitor),
        ("community_safety_states", community_safety_state_monitor),
        ("creator_analytics_schema", creator_schema_monitor),
        ("accessibility_gates", accessibility_monitor),
        ("public_faq_registry", faq_registry_monitor),
        ("public_feature_registry", public_feature_monitor),
        ("public_landing_manifest", public_landing_monitor),
    ):
        blockers.extend(f"{name}: {issue}" for issue in section.get("issues") or [])

    opposition_families = {
        _normalize_text(row.get("id")): dict(row)
        for row in opposition_packet_registry.get("packet_families") or []
        if isinstance(row, dict) and _normalize_text(row.get("id"))
    }
    faq_entries = _faq_entries(public_faq_registry)
    public_cards = _card_index(public_feature_registry)
    public_routes = _route_index(public_landing_manifest)

    tonight_pack_projection = {
        "status": "pass",
        "projection_kind": "governed_tonight_pack",
        "required_pack_elements": [
            "job_packet",
            "opposition_packet",
            "player_safe_brief",
            "reward_model",
            "foundry_or_vtt_hint",
        ],
        "available_opposition_packet_families": sorted(set(opposition_families) & REQUIRED_OPPOSITION_FAMILIES),
        "truth_sources": [
            "prep_packet_factory.first_proof",
            "opposition_packet_registry.packet_families",
        ],
    }
    world_broadcast_projection = {
        "status": "pass",
        "projection_kind": "weekly_world_publication_cadence",
        "recipe_ids": list(REQUIRED_WORLD_RECIPES.keys()),
        "truth_sources": [
            "world_broadcast_recipe_registry.recipes",
            "world_broadcast_and_faction_propaganda_cadence.weekly_cadence",
        ],
    }
    community_safety_projection = {
        "status": "pass",
        "projection_kind": "moderation_and_appeals_state_machine",
        "event_family_count": len(_normalize_list(community_safety_states.get("event_families"))),
        "state_count": len(_normalize_list(community_safety_states.get("states"))),
        "required_field_count": len(_normalize_list(community_safety_states.get("required_fields"))),
        "truth_sources": [
            "community_safety_event_and_appeal_states",
            "community_safety_moderation_and_appeals.audit_boundary",
        ],
    }
    creator_analytics_projection = {
        "status": "pass",
        "projection_kind": "bounded_creator_publication_analytics",
        "field_ids": sorted(REQUIRED_ANALYTICS_FIELDS),
        "privacy_rules": sorted(REQUIRED_PRIVACY_RULES),
        "claim_guards": sorted(REQUIRED_CLAIM_GUARDS),
        "truth_sources": [
            "creator_publication_analytics_schema.fields",
            "creator_publication_trust_and_compatibility_policy.truth_order",
            "product_analytics_and_journey_proof_model.core_rule",
        ],
    }
    accessibility_projection = {
        "status": "pass",
        "projection_kind": "release_bound_accessibility_and_cognitive_load",
        "gate_ids": sorted(REQUIRED_ACCESSIBILITY_GATES),
        "required_surfaces_by_gate": {gate_id: sorted(required) for gate_id, required in REQUIRED_ACCESSIBILITY_GATES.items()},
        "truth_sources": [
            "accessibility_cognitive_load_gates",
            "accessibility_and_cognitive_load_release_bar",
        ],
    }

    for projection in (tonight_pack_projection, world_broadcast_projection, community_safety_projection, creator_analytics_projection, accessibility_projection):
        if blockers:
            projection["status"] = "blocked"

    payload = {
        "contract_name": "fleet.next90_m139_release_health_public_trust_projections",
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
            "prep_packet_factory": prep_packet_monitor,
            "world_broadcast_cadence": world_broadcast_monitor,
            "community_safety_doc": community_safety_doc_monitor,
            "creator_analytics_doc": creator_analytics_doc_monitor,
            "creator_trust_policy": creator_trust_policy_monitor,
            "product_analytics_model": product_analytics_monitor,
            "accessibility_release_bar": accessibility_release_bar_monitor,
            "queue_alignment": queue_alignment,
            "opposition_packet_registry": opposition_registry_monitor,
            "world_broadcast_recipe_registry": world_recipe_monitor,
            "community_safety_states": community_safety_state_monitor,
            "creator_analytics_schema": creator_schema_monitor,
            "accessibility_gates": accessibility_monitor,
            "public_faq_registry": faq_registry_monitor,
            "public_feature_registry": public_feature_monitor,
            "public_landing_manifest": public_landing_monitor,
        },
        "projection_summary": {
            "projection_count": 5,
            "public_card_count": len([card_id for card_id in PUBLIC_CARD_IDS if card_id in public_cards]),
            "public_route_count": len([route_id for route_id in PUBLIC_ROUTE_IDS if route_id in public_routes]),
            "faq_question_count": len([question for question in REQUIRED_FAQ_QUESTIONS if question in faq_entries]),
            "warning_count": len(warnings),
        },
        "projections": {
            "tonight_pack": tonight_pack_projection,
            "world_broadcast_cadence": world_broadcast_projection,
            "community_safety_moderation": community_safety_projection,
            "creator_analytics_bounds": creator_analytics_projection,
            "accessibility_cognitive_load": accessibility_projection,
        },
        "public_truth_projection": {
            "faq_entries": {question: faq_entries.get(question, "") for question in REQUIRED_FAQ_QUESTIONS},
            "public_card_postures": {
                card_id: {
                    "title": _normalize_text(public_cards.get(card_id, {}).get("title")),
                    "badge": _normalize_text(public_cards.get(card_id, {}).get("badge")),
                }
                for card_id in PUBLIC_CARD_IDS
                if card_id in public_cards
            },
            "public_route_purposes": {
                route_id: _normalize_text(public_routes.get(route_id, {}).get("purpose"))
                for route_id in PUBLIC_ROUTE_IDS
                if route_id in public_routes
            },
        },
        "package_closeout": {
            "state": "pass" if not blockers else "blocked",
            "blockers": blockers,
            "warnings": warnings,
        },
        "source_inputs": {
            "successor_registry": _source_link(registry_path, registry),
            "fleet_queue_staging": _source_link(fleet_queue_path, fleet_queue),
            "design_queue_staging": _source_link(design_queue_path, design_queue),
            "next90_guide": _text_source_link(next90_guide_path),
            "prep_packet_factory": _text_source_link(prep_packet_factory_path),
            "opposition_packet_registry": _source_link(opposition_packet_registry_path, opposition_packet_registry),
            "world_broadcast_cadence": _text_source_link(world_broadcast_cadence_path),
            "world_broadcast_recipe_registry": _source_link(world_broadcast_recipe_registry_path, world_broadcast_recipe_registry),
            "community_safety_doc": _text_source_link(community_safety_doc_path),
            "community_safety_states": _source_link(community_safety_states_path, community_safety_states),
            "creator_analytics_doc": _text_source_link(creator_analytics_doc_path),
            "creator_analytics_schema": _source_link(creator_analytics_schema_path, creator_analytics_schema),
            "creator_trust_policy": _text_source_link(creator_trust_policy_path),
            "product_analytics_model": _text_source_link(product_analytics_model_path),
            "accessibility_release_bar": _text_source_link(accessibility_release_bar_path),
            "accessibility_gates": _source_link(accessibility_gates_path, accessibility_gates),
            "public_faq_registry": _source_link(public_faq_registry_path, public_faq_registry),
            "public_feature_registry": _source_link(public_feature_registry_path, public_feature_registry),
            "public_landing_manifest": _source_link(public_landing_manifest_path, public_landing_manifest),
        },
    }
    return payload


def render_markdown(payload: Dict[str, Any]) -> str:
    summary = dict(payload.get("projection_summary") or {})
    closeout = dict(payload.get("package_closeout") or {})
    lines = [
        "# Fleet M139 release-health and public-trust projections",
        "",
        f"- status: {payload.get('status')}",
        f"- package_id: {payload.get('package_id')}",
        f"- frontier_id: {payload.get('frontier_id')}",
        f"- generated_at: {payload.get('generated_at')}",
        "",
        "## Projection summary",
        f"- projection_count: {summary.get('projection_count')}",
        f"- public_card_count: {summary.get('public_card_count')}",
        f"- public_route_count: {summary.get('public_route_count')}",
        f"- faq_question_count: {summary.get('faq_question_count')}",
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
        prep_packet_factory_path=Path(args.prep_packet_factory).resolve(),
        opposition_packet_registry_path=Path(args.opposition_packet_registry).resolve(),
        world_broadcast_cadence_path=Path(args.world_broadcast_cadence).resolve(),
        world_broadcast_recipe_registry_path=Path(args.world_broadcast_recipe_registry).resolve(),
        community_safety_doc_path=Path(args.community_safety_doc).resolve(),
        community_safety_states_path=Path(args.community_safety_states).resolve(),
        creator_analytics_doc_path=Path(args.creator_analytics_doc).resolve(),
        creator_analytics_schema_path=Path(args.creator_analytics_schema).resolve(),
        creator_trust_policy_path=Path(args.creator_trust_policy).resolve(),
        product_analytics_model_path=Path(args.product_analytics_model).resolve(),
        accessibility_release_bar_path=Path(args.accessibility_release_bar).resolve(),
        accessibility_gates_path=Path(args.accessibility_gates).resolve(),
        public_faq_registry_path=Path(args.public_faq_registry).resolve(),
        public_feature_registry_path=Path(args.public_feature_registry).resolve(),
        public_landing_manifest_path=Path(args.public_landing_manifest).resolve(),
    )
    _write_json_file(output_path, payload)
    _write_markdown_file(markdown_path, render_markdown(payload))
    print(json.dumps({"status": payload["status"], "artifact": str(output_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
