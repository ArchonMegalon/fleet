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

PACKAGE_ID = "next90-m139-fleet-fail-closeout-when-tonight-pack-proof-broadcast-cadence-proof-moderati"
FRONTIER_ID = 3411981369
MILESTONE_ID = 139
WORK_TASK_ID = "139.9"
WAVE_ID = "W26"
QUEUE_TITLE = (
    "Fail closeout when tonight-pack proof, broadcast cadence proof, moderation and appeals states, creator analytics "
    "bounds, or accessibility and cognitive-load gates are stale, missing, or contradictory."
)
OWNED_SURFACES = ["fail_closeout_when_tonight_pack_proof_broadcast_cadence:fleet"]
ALLOWED_PATHS = ["scripts", "tests", ".codex-studio", "feedback"]

DEFAULT_OUTPUT = PUBLISHED / "NEXT90_M139_FLEET_OPERATIONAL_TRUST_CLOSEOUT_GATES.generated.json"
DEFAULT_MARKDOWN = PUBLISHED / "NEXT90_M139_FLEET_OPERATIONAL_TRUST_CLOSEOUT_GATES.generated.md"

SUCCESSOR_REGISTRY = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
FLEET_QUEUE_STAGING = PUBLISHED / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
DESIGN_QUEUE_STAGING = PRODUCT_MIRROR / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
NEXT90_GUIDE = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_GUIDE.md"
PREP_PACKET_FACTORY = PRODUCT_MIRROR / "PREP_PACKET_FACTORY_AND_PROCEDURAL_TABLES.md"
WORLD_BROADCAST_CADENCE = PRODUCT_MIRROR / "WORLD_BROADCAST_AND_FACTION_PROPAGANDA_CADENCE.md"
COMMUNITY_SAFETY_DOC = PRODUCT_MIRROR / "COMMUNITY_SAFETY_MODERATION_AND_APPEALS.md"
CREATOR_ANALYTICS_DOC = PRODUCT_MIRROR / "CREATOR_DASHBOARD_AND_ADOPTION_ANALYTICS.md"
ACCESSIBILITY_RELEASE_BAR = PRODUCT_MIRROR / "ACCESSIBILITY_AND_COGNITIVE_LOAD_RELEASE_BAR.md"
PUBLIC_FAQ = PRODUCT_MIRROR / "public-guide" / "FAQ.md"
PUBLIC_FAQ_REGISTRY = PRODUCT_MIRROR / "PUBLIC_FAQ_REGISTRY.yaml"
PUBLIC_FEATURE_REGISTRY = PRODUCT_MIRROR / "PUBLIC_FEATURE_REGISTRY.yaml"
PUBLIC_LANDING_MANIFEST = PRODUCT_MIRROR / "PUBLIC_LANDING_MANIFEST.yaml"
FLAGSHIP_READINESS = PUBLISHED / "FLAGSHIP_PRODUCT_READINESS.generated.json"
M139_PROJECTIONS = PUBLISHED / "NEXT90_M139_FLEET_RELEASE_HEALTH_PUBLIC_TRUST_PROJECTIONS.generated.json"

PROOF_FRESHNESS_HOURS = 72

GUIDE_MARKERS = {
    "wave_26": "## Wave 26 - make the world, creator, and trust loops feel lived-in",
    "milestone_139": "### 139. GM tonight pack, world broadcast cadence, creator analytics, community safety, and cognitive-load trust closure",
    "exit_contract": "Exit: a GM can assemble tonight's governed pack, the world can talk back on a weekly cadence, creators can see bounded adoption feedback, moderation and appeals exist before public scale, and accessibility plus cognitive-load gates are release-bound truths.",
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
ACCESSIBILITY_RELEASE_BAR_MARKERS = {
    "keyboard_first": "* keyboard-first dense workflows where the product claims expert speed",
    "mobile_glanceability": "* mobile glanceability for recap, readiness, and consequence moments",
    "what_matters_now": "* what matters right now",
}
FAQ_ENTRY_RULES = {
    "Can I participate privately?": {"must_contain": ("opt-in", "private participation")},
    "What are badges and leaderboards for?": {"must_contain": ("recognition", "not authority")},
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
REQUIRED_PROJECTION_KEYS = {
    "tonight_pack",
    "world_broadcast_cadence",
    "community_safety_moderation",
    "creator_analytics_bounds",
    "accessibility_cognitive_load",
}
DEDICATED_PROOF_HINTS = {
    "tonight_pack": ("TONIGHT_PACK", "PREP_PACKET"),
    "world_broadcast_cadence": ("WORLD_BROADCAST", "CITY_TICKER"),
    "community_safety_moderation": ("COMMUNITY_SAFETY", "APPEAL"),
    "creator_analytics_bounds": ("CREATOR_ANALYTICS", "CREATOR_PUBLICATION_ANALYTICS"),
    "accessibility_cognitive_load": ("ACCESSIBILITY", "COGNITIVE"),
}


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize the Fleet M139 operational trust closeout gate packet.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--markdown-output", default=str(DEFAULT_MARKDOWN))
    parser.add_argument("--published-root", default=str(PUBLISHED))
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--fleet-queue-staging", default=str(FLEET_QUEUE_STAGING))
    parser.add_argument("--design-queue-staging", default=str(DESIGN_QUEUE_STAGING))
    parser.add_argument("--next90-guide", default=str(NEXT90_GUIDE))
    parser.add_argument("--prep-packet-factory", default=str(PREP_PACKET_FACTORY))
    parser.add_argument("--world-broadcast-cadence", default=str(WORLD_BROADCAST_CADENCE))
    parser.add_argument("--community-safety-doc", default=str(COMMUNITY_SAFETY_DOC))
    parser.add_argument("--creator-analytics-doc", default=str(CREATOR_ANALYTICS_DOC))
    parser.add_argument("--accessibility-release-bar", default=str(ACCESSIBILITY_RELEASE_BAR))
    parser.add_argument("--public-faq", default=str(PUBLIC_FAQ))
    parser.add_argument("--public-faq-registry", default=str(PUBLIC_FAQ_REGISTRY))
    parser.add_argument("--public-feature-registry", default=str(PUBLIC_FEATURE_REGISTRY))
    parser.add_argument("--public-landing-manifest", default=str(PUBLIC_LANDING_MANIFEST))
    parser.add_argument("--flagship-readiness", default=str(FLAGSHIP_READINESS))
    parser.add_argument("--release-health-public-trust-projections", default=str(M139_PROJECTIONS))
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


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
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


def _parse_iso_utc(value: str) -> dt.datetime | None:
    text = _normalize_text(value)
    if not text:
        return None
    try:
        return dt.datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(dt.timezone.utc)
    except ValueError:
        return None


def _age_hours(value: str, *, now: dt.datetime) -> int | None:
    parsed = _parse_iso_utc(value)
    if parsed is None:
        return None
    delta = now - parsed
    return max(int(delta.total_seconds() // 3600), 0)


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
        warnings.append("Fleet queue mirror row is still missing for work task 139.9.")
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


def _public_truth_runtime_monitor(
    *,
    faq_text: str,
    faq_registry: Dict[str, Any],
    public_feature_registry: Dict[str, Any],
    public_landing_manifest: Dict[str, Any],
) -> Dict[str, Any]:
    runtime_blockers: List[str] = []
    warnings: List[str] = []
    bounded_faq_count = 0

    faq_entries = _faq_entries(faq_registry)
    for question, spec in FAQ_ENTRY_RULES.items():
        answer = faq_entries.get(question, "")
        if not answer:
            runtime_blockers.append(f"PUBLIC_FAQ_REGISTRY is missing boundary answer `{question}`.")
            continue
        missing = [marker for marker in spec["must_contain"] if marker not in answer]
        if missing:
            runtime_blockers.append(f"PUBLIC_FAQ_REGISTRY `{question}` answer is missing: {', '.join(missing)}.")
        else:
            bounded_faq_count += 1

    cards = _card_index(public_feature_registry)
    for card_id, expected_badge in REQUIRED_PUBLIC_CARD_BADGES.items():
        card = dict(cards.get(card_id) or {})
        if not card:
            runtime_blockers.append(f"PUBLIC_FEATURE_REGISTRY is missing bounded public card `{card_id}`.")
            continue
        badge = _normalize_text(card.get("badge"))
        if badge != expected_badge:
            runtime_blockers.append(f"PUBLIC_FEATURE_REGISTRY `{card_id}` badge drifted from `{expected_badge}`.")

    routes = _route_index(public_landing_manifest)
    for route_id, expected_purpose in REQUIRED_PUBLIC_ROUTE_PURPOSES.items():
        route = dict(routes.get(route_id) or {})
        if not route:
            runtime_blockers.append(f"PUBLIC_LANDING_MANIFEST is missing route `{route_id}`.")
            continue
        purpose = _normalize_text(route.get("purpose"))
        if purpose != expected_purpose:
            runtime_blockers.append(f"PUBLIC_LANDING_MANIFEST `{route_id}` purpose drifted from `{expected_purpose}`.")

    if "Can I participate privately?" not in faq_text:
        warnings.append("FAQ.md did not surface the private-participation boundary in markdown form.")
    if "What are badges and leaderboards for?" not in faq_text:
        warnings.append("FAQ.md did not surface the badges-and-leaderboards boundary in markdown form.")

    return {
        "state": "pass",
        "issues": [],
        "runtime_blockers": runtime_blockers,
        "warnings": warnings,
        "bounded_faq_count": bounded_faq_count,
    }


def _projection_artifact_monitor(payload: Dict[str, Any], *, now: dt.datetime) -> Dict[str, Any]:
    runtime_blockers: List[str] = []
    warnings: List[str] = []
    if not payload:
        runtime_blockers.append("Machine-readable M139 release-health/public-trust projections artifact is missing.")
        return {
            "state": "pass",
            "issues": [],
            "runtime_blockers": runtime_blockers,
            "warnings": warnings,
            "projection_statuses": {},
            "generated_at": "",
            "age_hours": None,
        }
    generated_at = _normalize_text(payload.get("generated_at") or payload.get("generatedAt"))
    age = _age_hours(generated_at, now=now)
    if _normalize_text(payload.get("contract_name")) != "fleet.next90_m139_release_health_public_trust_projections":
        runtime_blockers.append("Machine-readable M139 release-health/public-trust projections artifact contract_name drifted.")
    if _normalize_text(payload.get("status")).lower() not in {"pass", "passed", "ready"}:
        runtime_blockers.append("Machine-readable M139 release-health/public-trust projections artifact is not passing.")
    if age is None:
        runtime_blockers.append("Machine-readable M139 release-health/public-trust projections artifact generated_at is missing or invalid.")
    elif age > PROOF_FRESHNESS_HOURS:
        runtime_blockers.append(
            f"Machine-readable M139 release-health/public-trust projections artifact freshness exceeded the {PROOF_FRESHNESS_HOURS}h threshold ({age}h)."
        )

    projections = dict(payload.get("projections") or {})
    missing_keys = sorted(REQUIRED_PROJECTION_KEYS - set(projections))
    if missing_keys:
        runtime_blockers.append(
            "Machine-readable M139 release-health/public-trust projections artifact is missing required projections: "
            + ", ".join(missing_keys)
            + "."
        )
    projection_statuses: Dict[str, str] = {}
    for key in sorted(REQUIRED_PROJECTION_KEYS):
        row = dict(projections.get(key) or {})
        status = _normalize_text(row.get("status")).lower()
        projection_statuses[key] = status
        if row and status not in {"pass", "passed", "ready"}:
            runtime_blockers.append(f"M139 projection `{key}` is {status or 'unknown'}.")
        if row and not _normalize_list(row.get("truth_sources")):
            runtime_blockers.append(f"M139 projection `{key}` is missing truth_sources.")

    for warning in _normalize_list(dict(payload.get("package_closeout") or {}).get("warnings")):
        warnings.append(f"projection_packet: {warning}")

    return {
        "state": "pass",
        "issues": [],
        "runtime_blockers": runtime_blockers,
        "warnings": warnings,
        "projection_statuses": projection_statuses,
        "generated_at": generated_at,
        "age_hours": age,
    }


def _direct_proof_presence_monitor(published_root: Path) -> Dict[str, Any]:
    warnings: List[str] = []
    evidence: Dict[str, List[str]] = {}
    filenames = [path.name for path in published_root.rglob("*") if path.is_file()]
    for proof_id, hints in DEDICATED_PROOF_HINTS.items():
        matches = sorted(name for name in filenames if any(hint in name for hint in hints))
        evidence[proof_id] = matches
        if not matches:
            warnings.append(f"No dedicated published `{proof_id}` proof artifact is present yet.")
    return {
        "state": "pass",
        "issues": [],
        "runtime_blockers": [],
        "warnings": warnings,
        "evidence": evidence,
    }


def _flagship_readiness_alignment_monitor(
    payload: Dict[str, Any],
    *,
    projection_artifact_monitor: Dict[str, Any],
    public_truth_runtime_monitor: Dict[str, Any],
) -> Dict[str, Any]:
    runtime_blockers: List[str] = []
    if not payload:
        return {
            "state": "pass",
            "issues": [],
            "runtime_blockers": ["FLAGSHIP_PRODUCT_READINESS artifact is missing or invalid."],
            "flagship_ready_status": "",
            "generated_at": "",
        }

    readiness_planes = dict(payload.get("readiness_planes") or {})
    flagship_ready = dict(readiness_planes.get("flagship_ready") or {})
    flagship_ready_status = _normalize_text(flagship_ready.get("status") or payload.get("status")).lower()
    if (
        projection_artifact_monitor.get("runtime_blockers")
        or public_truth_runtime_monitor.get("runtime_blockers")
    ) and flagship_ready_status in {"ready", "pass", "passed"}:
        runtime_blockers.append(
            "FLAGSHIP_PRODUCT_READINESS still reports flagship_ready while M139 closeout proof is stale, missing, or contradicted."
        )
    return {
        "state": "pass",
        "issues": [],
        "runtime_blockers": runtime_blockers,
        "flagship_ready_status": flagship_ready_status,
        "generated_at": _normalize_text(payload.get("generated_at") or payload.get("generatedAt")),
    }


def build_payload(
    *,
    published_root: Path,
    registry_path: Path,
    fleet_queue_path: Path,
    design_queue_path: Path,
    next90_guide_path: Path,
    prep_packet_factory_path: Path,
    world_broadcast_cadence_path: Path,
    community_safety_doc_path: Path,
    creator_analytics_doc_path: Path,
    accessibility_release_bar_path: Path,
    public_faq_path: Path,
    public_faq_registry_path: Path,
    public_feature_registry_path: Path,
    public_landing_manifest_path: Path,
    flagship_readiness_path: Path,
    projections_path: Path,
    generated_at: str | None = None,
) -> Dict[str, Any]:
    generated_at = generated_at or _utc_now()
    now = _parse_iso_utc(generated_at) or dt.datetime.now(dt.timezone.utc)

    registry = _load_yaml(registry_path)
    fleet_queue = _load_yaml(fleet_queue_path)
    design_queue = _load_yaml(design_queue_path)
    next90_guide = _load_text(next90_guide_path)
    prep_packet_factory = _load_text(prep_packet_factory_path)
    world_broadcast_cadence = _load_text(world_broadcast_cadence_path)
    community_safety_doc = _load_text(community_safety_doc_path)
    creator_analytics_doc = _load_text(creator_analytics_doc_path)
    accessibility_release_bar = _load_text(accessibility_release_bar_path)
    public_faq = _load_text(public_faq_path)
    public_faq_registry = _load_yaml(public_faq_registry_path)
    public_feature_registry = _load_yaml(public_feature_registry_path)
    public_landing_manifest = _load_yaml(public_landing_manifest_path)
    flagship_readiness = _load_json(flagship_readiness_path)
    projections = _load_json(projections_path)

    milestone = _find_milestone(registry, MILESTONE_ID)
    work_task = _find_work_task(milestone, WORK_TASK_ID)
    fleet_queue_item = _find_queue_item(fleet_queue, WORK_TASK_ID)
    design_queue_item = _find_queue_item(design_queue, WORK_TASK_ID)

    guide_monitor = _marker_monitor(next90_guide, GUIDE_MARKERS, label="Next90 guide canon")
    prep_packet_monitor = _marker_monitor(prep_packet_factory, PREP_PACKET_MARKERS, label="Prep packet canon")
    world_broadcast_monitor = _marker_monitor(world_broadcast_cadence, WORLD_BROADCAST_MARKERS, label="World broadcast canon")
    community_safety_monitor = _marker_monitor(community_safety_doc, COMMUNITY_SAFETY_MARKERS, label="Community safety canon")
    creator_analytics_monitor = _marker_monitor(creator_analytics_doc, CREATOR_ANALYTICS_MARKERS, label="Creator analytics canon")
    accessibility_monitor = _marker_monitor(accessibility_release_bar, ACCESSIBILITY_RELEASE_BAR_MARKERS, label="Accessibility release bar canon")
    queue_alignment = _queue_alignment(work_task=work_task, fleet_queue_item=fleet_queue_item, design_queue_item=design_queue_item)
    public_truth_monitor = _public_truth_runtime_monitor(
        faq_text=public_faq,
        faq_registry=public_faq_registry,
        public_feature_registry=public_feature_registry,
        public_landing_manifest=public_landing_manifest,
    )
    projection_monitor = _projection_artifact_monitor(projections, now=now)
    direct_proof_monitor = _direct_proof_presence_monitor(published_root)
    flagship_alignment_monitor = _flagship_readiness_alignment_monitor(
        flagship_readiness,
        projection_artifact_monitor=projection_monitor,
        public_truth_runtime_monitor=public_truth_monitor,
    )

    blockers: List[str] = []
    runtime_blockers: List[str] = []
    warnings: List[str] = []
    for name, section in (
        ("next90_guide", guide_monitor),
        ("prep_packet_factory", prep_packet_monitor),
        ("world_broadcast_cadence", world_broadcast_monitor),
        ("community_safety_doc", community_safety_monitor),
        ("creator_analytics_doc", creator_analytics_monitor),
        ("accessibility_release_bar", accessibility_monitor),
        ("queue_alignment", queue_alignment),
        ("public_truth", public_truth_monitor),
        ("m139_projections", projection_monitor),
        ("direct_proof_presence", direct_proof_monitor),
        ("flagship_readiness_alignment", flagship_alignment_monitor),
    ):
        blockers.extend(f"{name}: {issue}" for issue in section.get("issues") or [])
        runtime_blockers.extend(f"{name}: {issue}" for issue in section.get("runtime_blockers") or [])
        warnings.extend(section.get("warnings") or [])

    operational_trust_closeout_status = "blocked" if runtime_blockers else "warning" if warnings else "pass"
    return {
        "contract_name": "fleet.next90_m139_operational_trust_closeout_gates",
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
            "community_safety_doc": community_safety_monitor,
            "creator_analytics_doc": creator_analytics_monitor,
            "accessibility_release_bar": accessibility_monitor,
            "queue_alignment": queue_alignment,
        },
        "runtime_monitors": {
            "public_truth": public_truth_monitor,
            "m139_projections": projection_monitor,
            "direct_proof_presence": direct_proof_monitor,
            "flagship_readiness_alignment": flagship_alignment_monitor,
        },
        "monitor_summary": {
            "operational_trust_closeout_status": operational_trust_closeout_status,
            "runtime_blocker_count": len(runtime_blockers),
            "warning_count": len(warnings),
            "bounded_faq_count": public_truth_monitor.get("bounded_faq_count"),
            "projection_runtime_blocker_count": len(projection_monitor.get("runtime_blockers") or []),
            "dedicated_proof_slot_count": len(DEDICATED_PROOF_HINTS),
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
            "prep_packet_factory": _text_source_link(prep_packet_factory_path),
            "world_broadcast_cadence": _text_source_link(world_broadcast_cadence_path),
            "community_safety_doc": _text_source_link(community_safety_doc_path),
            "creator_analytics_doc": _text_source_link(creator_analytics_doc_path),
            "accessibility_release_bar": _text_source_link(accessibility_release_bar_path),
            "public_faq": _text_source_link(public_faq_path),
            "public_faq_registry": _source_link(public_faq_registry_path, public_faq_registry),
            "public_feature_registry": _source_link(public_feature_registry_path, public_feature_registry),
            "public_landing_manifest": _source_link(public_landing_manifest_path, public_landing_manifest),
            "flagship_readiness": _source_link(flagship_readiness_path, flagship_readiness),
            "release_health_public_trust_projections": _source_link(projections_path, projections),
        },
    }


def render_markdown(payload: Dict[str, Any]) -> str:
    summary = dict(payload.get("monitor_summary") or {})
    closeout = dict(payload.get("package_closeout") or {})
    lines = [
        "# Fleet M139 operational trust closeout gates",
        "",
        f"- status: {payload.get('status')}",
        f"- package_id: {payload.get('package_id')}",
        f"- frontier_id: {payload.get('frontier_id')}",
        f"- generated_at: {payload.get('generated_at')}",
        "",
        "## Monitor summary",
        f"- operational_trust_closeout_status: {summary.get('operational_trust_closeout_status')}",
        f"- runtime_blocker_count: {summary.get('runtime_blocker_count')}",
        f"- warning_count: {summary.get('warning_count')}",
        f"- bounded_faq_count: {summary.get('bounded_faq_count')}",
        f"- projection_runtime_blocker_count: {summary.get('projection_runtime_blocker_count')}",
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
        published_root=Path(args.published_root).resolve(),
        registry_path=Path(args.successor_registry).resolve(),
        fleet_queue_path=Path(args.fleet_queue_staging).resolve(),
        design_queue_path=Path(args.design_queue_staging).resolve(),
        next90_guide_path=Path(args.next90_guide).resolve(),
        prep_packet_factory_path=Path(args.prep_packet_factory).resolve(),
        world_broadcast_cadence_path=Path(args.world_broadcast_cadence).resolve(),
        community_safety_doc_path=Path(args.community_safety_doc).resolve(),
        creator_analytics_doc_path=Path(args.creator_analytics_doc).resolve(),
        accessibility_release_bar_path=Path(args.accessibility_release_bar).resolve(),
        public_faq_path=Path(args.public_faq).resolve(),
        public_faq_registry_path=Path(args.public_faq_registry).resolve(),
        public_feature_registry_path=Path(args.public_feature_registry).resolve(),
        public_landing_manifest_path=Path(args.public_landing_manifest).resolve(),
        flagship_readiness_path=Path(args.flagship_readiness).resolve(),
        projections_path=Path(args.release_health_public_trust_projections).resolve(),
    )
    _write_json_file(output_path, payload)
    _write_markdown_file(markdown_path, render_markdown(payload))
    print(json.dumps({"status": payload["status"], "artifact": str(output_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
