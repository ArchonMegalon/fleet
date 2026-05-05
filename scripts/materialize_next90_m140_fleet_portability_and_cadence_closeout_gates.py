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

PACKAGE_ID = "next90-m140-fleet-fail-closeout-when-runner-passport-proof-weekly-dispatch-cadence-creat"
FRONTIER_ID = 4145512253
MILESTONE_ID = 140
WORK_TASK_ID = "140.9"
WAVE_ID = "W27"
QUEUE_TITLE = (
    "Fail closeout when runner-passport proof, weekly dispatch cadence, creator operating-system fields, "
    "or LTD cadence bindings are stale, missing, or contradicted by public posture."
)
OWNED_SURFACES = ["fail_closeout_when_runner_passport_proof_weekly_dispatch:fleet"]
ALLOWED_PATHS = ["scripts", "tests", ".codex-studio", "feedback"]

DEFAULT_OUTPUT = PUBLISHED / "NEXT90_M140_FLEET_PORTABILITY_AND_CADENCE_CLOSEOUT_GATES.generated.json"
DEFAULT_MARKDOWN = PUBLISHED / "NEXT90_M140_FLEET_PORTABILITY_AND_CADENCE_CLOSEOUT_GATES.generated.md"

SUCCESSOR_REGISTRY = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
FLEET_QUEUE_STAGING = PUBLISHED / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
DESIGN_QUEUE_STAGING = PRODUCT_MIRROR / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
NEXT90_GUIDE = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_GUIDE.md"
ROADMAP = PRODUCT_MIRROR / "ROADMAP.md"
RUNNER_PASSPORT_DOC = PRODUCT_MIRROR / "RUNNER_PASSPORT_AND_CROSS_COMMUNITY_TRUST.md"
RUNNER_PASSPORT_ACCEPTANCE = PRODUCT_MIRROR / "RUNNER_PASSPORT_ACCEPTANCE.yaml"
WORLD_DISPATCH_DOC = PRODUCT_MIRROR / "WORLD_DISPATCH_AND_REACTIVATION_LOOP.md"
WORLD_DISPATCH_GATES = PRODUCT_MIRROR / "WORLD_DISPATCH_REACTIVATION_GATES.yaml"
CREATOR_OPERATING_SYSTEM = PRODUCT_MIRROR / "CREATOR_OPERATING_SYSTEM.md"
LTD_CADENCE_SYSTEM = PRODUCT_MIRROR / "LTD_CADENCE_AND_FOLLOWTHROUGH_SYSTEM.md"
LTD_CADENCE_REGISTRY = PRODUCT_MIRROR / "LTD_CADENCE_AND_FOLLOWTHROUGH_REGISTRY.yaml"
LTD_RUNTIME_REGISTRY = PRODUCT_MIRROR / "LTD_RUNTIME_AND_PROJECTION_REGISTRY.yaml"
PUBLIC_FAQ = PRODUCT_MIRROR / "public-guide" / "FAQ.md"
PUBLIC_FAQ_REGISTRY = PRODUCT_MIRROR / "PUBLIC_FAQ_REGISTRY.yaml"
PUBLIC_FEATURE_REGISTRY = PRODUCT_MIRROR / "PUBLIC_FEATURE_REGISTRY.yaml"
PUBLIC_LANDING_MANIFEST = PRODUCT_MIRROR / "PUBLIC_LANDING_MANIFEST.yaml"
FLAGSHIP_READINESS = PUBLISHED / "FLAGSHIP_PRODUCT_READINESS.generated.json"

GUIDE_MARKERS = {
    "wave_27": "## Wave 27 - turn portability, return cadence, creator health, and LTD followthrough into habit",
    "milestone_140": "### 140. Runner passport, weekly world dispatch, creator operating system, and LTD-powered cadence closure",
    "exit_contract": "Exit: a runner can carry governed trust posture between communities, the world can emit recurring return prompts from approved truth, creator publication behaves like a live operating system instead of a shelf, and LTD-powered followthrough loops stay bounded by Chummer-owned receipts instead of becoming shadow authority.",
}
ROADMAP_MARKERS = {
    "ritual_value_overlay": "* the active ritual-value overlay is the repeat-use bundle around `RUNNER_PASSPORT_AND_CROSS_COMMUNITY_TRUST.md`, `WORLD_DISPATCH_AND_REACTIVATION_LOOP.md`, `CREATOR_OPERATING_SYSTEM.md`, and `LTD_CADENCE_AND_FOLLOWTHROUGH_SYSTEM.md`;",
}
RUNNER_PASSPORT_MARKERS = {
    "not_dossier": "A `RunnerPassport` is not the runner dossier itself.",
    "portable_proof": "It is the portable proof of what a community needs to know before it can trust the dossier quickly.",
    "not_social_score": "The passport is not a permanent social score.",
}
WORLD_DISPATCH_MARKERS = {
    "ticker": "* one city or campaign ticker",
    "return_prompt": "* one optional public-safe recruitment or return prompt",
    "receipt_projection": "It is the recurring projection of approved campaign and world truth through inspectable receipts.",
}
CREATOR_OPERATING_MARKERS = {
    "discoverability_not_endorsement": "Trust ranking should stay discoverability language, not endorsement language.",
    "breakage_posture": "* compatibility and breakage posture from receipt-backed registry truth",
    "graveyard_warning": "publication becomes a graveyard instead of an ecosystem.",
}
LTD_CADENCE_MARKERS = {
    "amplify": "LTDs should amplify Chummer's cadence.",
    "no_shadow_authority": "The LTD stack should create cadence, not shadow authority.",
    "receipt_mirror": "If a loop cannot be mirrored back into Chummer-owned receipts, it should stay outside the canonical product lane.",
}

REQUIRED_RUNNER_PASSPORT_FIELDS = {
    "runner_identity_ref",
    "rule_environment_fingerprint",
    "approval_state",
    "review_timestamp",
    "reviewer_role",
    "unresolved_warning_refs",
    "dossier_posture",
    "export_eligibility",
    "validity_window",
}
REQUIRED_RUNNER_PASSPORT_USAGE_LANES = {
    "open_run_application_preflight",
    "community_rule_environment",
    "no_desktop_participation",
    "campaign_adoption",
    "organizer_review",
}
REQUIRED_RUNNER_PASSPORT_BOUNDARIES = {
    "not_a_social_score",
    "scoped_to_governed_trust_and_compatibility",
}
REQUIRED_WORLD_DISPATCH_OUTPUTS = {
    "city_or_campaign_ticker",
    "faction_or_world_spin_item",
    "gm_only_digest",
    "player_safe_what_changed_card",
    "optional_recruitment_or_return_prompt",
}
REQUIRED_WORLD_DISPATCH_PROVENANCE = {"ResolutionReport", "WorldTick", "NewsItem"}
REQUIRED_WORLD_DISPATCH_RULES = {
    "dispatch_must_point_to_next_useful_action",
    "public_safe_outputs_must_not_leak_private_campaign_truth",
}
REQUIRED_LTD_LOOPS = {
    "weekly_world_dispatch",
    "open_run_recruitment_and_reminder",
    "beginner_and_gm_clinic_followthrough",
    "creator_publication_followthrough",
    "blocker_reactivation_and_recovery",
}
REQUIRED_LTD_BOUNDARY_RULES = {
    "ltds_do_not_own_rules_campaign_release_or_moderation_truth",
    "every_loop_must_mirror_back_into_chummer_owned_receipts",
}
REQUIRED_PRODUCT_SYSTEMS = {"trust_closure_system", "public_growth_system", "community_hub_ops"}
FORBIDDEN_PUBLIC_LTD_NAMES = {"signitic", "emailit", "lunacal", "facepop", "teable", "nextstep", "deftform"}
TRACKED_PUBLIC_CARD_IDS = {"lane_gm", "lane_creator"}
REQUIRED_PUBLIC_CARD_BADGES = {"lane_creator": "Preview lane"}
REQUIRED_PUBLIC_ROUTE_PURPOSES = {"/artifacts": "teaser_gallery"}
PORTABILITY_AND_CADENCE_TERMS = (
    "passport",
    "dispatch",
    "reactivation",
    "return prompt",
    "creator health",
    "creator operating",
)
LIVE_PUBLIC_BADGES = {"Available now", "Live now", "Inspectable", "Workflow"}
DIRECT_PROOF_HINTS = {
    "runner_passport": ("RUNNER_PASSPORT", "PASSPORT"),
    "world_dispatch": ("WORLD_DISPATCH", "DISPATCH"),
    "creator_operating_system": ("CREATOR_OPERATING", "CREATOR_HEALTH"),
    "ltd_cadence": ("LTD_CADENCE", "FOLLOWTHROUGH"),
}


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize the Fleet M140 portability/cadence closeout gate packet.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--markdown-output", default=str(DEFAULT_MARKDOWN))
    parser.add_argument("--published-root", default=str(PUBLISHED))
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--fleet-queue-staging", default=str(FLEET_QUEUE_STAGING))
    parser.add_argument("--design-queue-staging", default=str(DESIGN_QUEUE_STAGING))
    parser.add_argument("--next90-guide", default=str(NEXT90_GUIDE))
    parser.add_argument("--roadmap", default=str(ROADMAP))
    parser.add_argument("--runner-passport-doc", default=str(RUNNER_PASSPORT_DOC))
    parser.add_argument("--runner-passport-acceptance", default=str(RUNNER_PASSPORT_ACCEPTANCE))
    parser.add_argument("--world-dispatch-doc", default=str(WORLD_DISPATCH_DOC))
    parser.add_argument("--world-dispatch-gates", default=str(WORLD_DISPATCH_GATES))
    parser.add_argument("--creator-operating-system", default=str(CREATOR_OPERATING_SYSTEM))
    parser.add_argument("--ltd-cadence-system", default=str(LTD_CADENCE_SYSTEM))
    parser.add_argument("--ltd-cadence-registry", default=str(LTD_CADENCE_REGISTRY))
    parser.add_argument("--ltd-runtime-registry", default=str(LTD_RUNTIME_REGISTRY))
    parser.add_argument("--public-faq", default=str(PUBLIC_FAQ))
    parser.add_argument("--public-faq-registry", default=str(PUBLIC_FAQ_REGISTRY))
    parser.add_argument("--public-feature-registry", default=str(PUBLIC_FEATURE_REGISTRY))
    parser.add_argument("--public-landing-manifest", default=str(PUBLIC_LANDING_MANIFEST))
    parser.add_argument("--flagship-readiness", default=str(FLAGSHIP_READINESS))
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
    except OSError:
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
    checks = {name: marker in text or " ".join(marker.split()) in normalized_text for name, marker in markers.items()}
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
        warnings.append("Fleet queue mirror row is still missing for work task 140.9.")
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
                issues.append(f"{label} queue row {key} drifted from the assigned M140 package.")
        if sorted(_normalize_list(row.get("allowed_paths"))) != sorted(ALLOWED_PATHS):
            issues.append(f"{label} queue row allowed_paths drifted from the assigned M140 package.")
        if sorted(_normalize_list(row.get("owned_surfaces"))) != sorted(OWNED_SURFACES):
            issues.append(f"{label} queue row owned_surfaces drifted from the assigned M140 package.")
    return {"state": "pass" if not issues else "fail", "issues": issues, "warnings": warnings}


def _runner_passport_acceptance_monitor(payload: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    fields = set(_normalize_list(payload.get("required_fields")))
    lanes = set(_normalize_list(payload.get("usage_lanes")))
    boundaries = set(_normalize_list(payload.get("boundary_rules")))
    missing_fields = sorted(REQUIRED_RUNNER_PASSPORT_FIELDS - fields)
    missing_lanes = sorted(REQUIRED_RUNNER_PASSPORT_USAGE_LANES - lanes)
    missing_boundaries = sorted(REQUIRED_RUNNER_PASSPORT_BOUNDARIES - boundaries)
    if missing_fields:
        issues.append("RUNNER_PASSPORT_ACCEPTANCE is missing required_fields: " + ", ".join(missing_fields) + ".")
    if missing_lanes:
        issues.append("RUNNER_PASSPORT_ACCEPTANCE is missing usage_lanes: " + ", ".join(missing_lanes) + ".")
    if missing_boundaries:
        issues.append("RUNNER_PASSPORT_ACCEPTANCE is missing boundary_rules: " + ", ".join(missing_boundaries) + ".")
    return {"state": "pass" if not issues else "fail", "issues": issues}


def _world_dispatch_gate_monitor(payload: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    outputs = set(_normalize_list(payload.get("required_outputs")))
    provenance = set(_normalize_list(payload.get("required_provenance")))
    rules = set(_normalize_list(payload.get("reactivation_rules")))
    missing_outputs = sorted(REQUIRED_WORLD_DISPATCH_OUTPUTS - outputs)
    missing_provenance = sorted(REQUIRED_WORLD_DISPATCH_PROVENANCE - provenance)
    missing_rules = sorted(REQUIRED_WORLD_DISPATCH_RULES - rules)
    if missing_outputs:
        issues.append("WORLD_DISPATCH_REACTIVATION_GATES is missing required_outputs: " + ", ".join(missing_outputs) + ".")
    if missing_provenance:
        issues.append("WORLD_DISPATCH_REACTIVATION_GATES is missing required_provenance: " + ", ".join(missing_provenance) + ".")
    if missing_rules:
        issues.append("WORLD_DISPATCH_REACTIVATION_GATES is missing reactivation_rules: " + ", ".join(missing_rules) + ".")
    return {"state": "pass" if not issues else "fail", "issues": issues}


def _ltd_cadence_registry_monitor(payload: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    loops = {
        _normalize_text(row.get("id"))
        for row in payload.get("loops") or []
        if isinstance(row, dict) and _normalize_text(row.get("id"))
    }
    boundaries = set(_normalize_list(payload.get("boundary_rules")))
    missing_loops = sorted(REQUIRED_LTD_LOOPS - loops)
    missing_boundaries = sorted(REQUIRED_LTD_BOUNDARY_RULES - boundaries)
    if missing_loops:
        issues.append("LTD_CADENCE_AND_FOLLOWTHROUGH_REGISTRY is missing loops: " + ", ".join(missing_loops) + ".")
    if missing_boundaries:
        issues.append(
            "LTD_CADENCE_AND_FOLLOWTHROUGH_REGISTRY is missing boundary_rules: " + ", ".join(missing_boundaries) + "."
        )
    return {"state": "pass" if not issues else "fail", "issues": issues}


def _ltd_runtime_registry_monitor(payload: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    if _normalize_text(payload.get("core_rule")) != "Chummer owns truth; tools collect, administer, render, publish, schedule, archive, or amplify it.":
        issues.append("LTD_RUNTIME_AND_PROJECTION_REGISTRY core_rule drifted from the canonical truth-owner boundary.")
    systems = payload.get("product_systems") or {}
    if not isinstance(systems, dict):
        issues.append("LTD_RUNTIME_AND_PROJECTION_REGISTRY product_systems is missing.")
        return {"state": "fail", "issues": issues}
    missing_systems = sorted(system for system in REQUIRED_PRODUCT_SYSTEMS if system not in systems)
    if missing_systems:
        issues.append("LTD_RUNTIME_AND_PROJECTION_REGISTRY is missing product_systems: " + ", ".join(missing_systems) + ".")
    return {"state": "pass" if not issues else "fail", "issues": issues}


def _faq_entries(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for section in payload.get("sections") or []:
        if not isinstance(section, dict):
            continue
        for row in section.get("entries") or []:
            if isinstance(row, dict):
                entries.append(dict(row))
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


def _public_posture_runtime_monitor(
    *,
    faq_text: str,
    faq_registry: Dict[str, Any],
    public_feature_registry: Dict[str, Any],
    public_landing_manifest: Dict[str, Any],
) -> Dict[str, Any]:
    runtime_blockers: List[str] = []
    warnings: List[str] = []
    bounded_card_count = 0

    cards = _card_index(public_feature_registry)
    for card_id, expected_badge in REQUIRED_PUBLIC_CARD_BADGES.items():
        card = dict(cards.get(card_id) or {})
        if not card:
            runtime_blockers.append(f"PUBLIC_FEATURE_REGISTRY is missing bounded public card `{card_id}`.")
            continue
        badge = _normalize_text(card.get("badge"))
        if badge != expected_badge:
            runtime_blockers.append(f"PUBLIC_FEATURE_REGISTRY `{card_id}` badge drifted from `{expected_badge}`.")
        else:
            bounded_card_count += 1

    for row in public_feature_registry.get("cards") or []:
        if not isinstance(row, dict):
            continue
        text = " ".join(
            _normalize_text(row.get(field))
            for field in ("id", "title", "summary", "href", "detail_route", "action_label")
        ).lower()
        badge = _normalize_text(row.get("badge"))
        if any(term in text for term in PORTABILITY_AND_CADENCE_TERMS) and badge in LIVE_PUBLIC_BADGES:
            runtime_blockers.append(
                "PUBLIC_FEATURE_REGISTRY exposes live portability/cadence posture without closeout proof: "
                + (_normalize_text(row.get("id")) or _normalize_text(row.get("title")) or "unknown_card")
                + "."
            )
        if any(name in text for name in FORBIDDEN_PUBLIC_LTD_NAMES):
            runtime_blockers.append(
                "PUBLIC_FEATURE_REGISTRY leaks LTD vendor names into public posture: "
                + (_normalize_text(row.get("id")) or _normalize_text(row.get("title")) or "unknown_card")
                + "."
            )

    routes = _route_index(public_landing_manifest)
    route_texts: List[str] = []
    for route_id, route in routes.items():
        route_text = " ".join(_normalize_text(route.get(field)) for field in ("path", "purpose", "title", "summary")).lower()
        route_texts.append(route_text)
        if any(term in route_text for term in PORTABILITY_AND_CADENCE_TERMS):
            runtime_blockers.append(f"PUBLIC_LANDING_MANIFEST exposes route `{route_id}` with portability/cadence overclaim.")
        if any(name in route_text for name in FORBIDDEN_PUBLIC_LTD_NAMES):
            runtime_blockers.append(f"PUBLIC_LANDING_MANIFEST exposes route `{route_id}` with LTD vendor naming.")
    for route_id, expected_purpose in REQUIRED_PUBLIC_ROUTE_PURPOSES.items():
        route = dict(routes.get(route_id) or {})
        if not route:
            runtime_blockers.append(f"PUBLIC_LANDING_MANIFEST is missing route `{route_id}`.")
            continue
        purpose = _normalize_text(route.get("purpose"))
        if purpose != expected_purpose:
            runtime_blockers.append(f"PUBLIC_LANDING_MANIFEST `{route_id}` purpose drifted from `{expected_purpose}`.")

    faq_entries = _faq_entries(faq_registry)
    faq_strings = [(" ".join([_normalize_text(row.get("question")), _normalize_text(row.get("answer"))])).lower() for row in faq_entries]
    for text in faq_strings:
        if any(name in text for name in FORBIDDEN_PUBLIC_LTD_NAMES):
            runtime_blockers.append("PUBLIC_FAQ_REGISTRY exposes LTD vendor naming in public help posture.")
            break

    faq_markdown = faq_text.lower()
    if any(name in faq_markdown for name in FORBIDDEN_PUBLIC_LTD_NAMES):
        runtime_blockers.append("FAQ.md exposes LTD vendor naming in public help posture.")
    if "creator" not in faq_markdown:
        warnings.append("FAQ.md does not yet mention creator posture in markdown form.")

    return {
        "state": "pass",
        "issues": [],
        "runtime_blockers": runtime_blockers,
        "warnings": warnings,
        "bounded_card_count": bounded_card_count,
    }


def _direct_proof_presence_monitor(published_root: Path) -> Dict[str, Any]:
    warnings: List[str] = []
    evidence: Dict[str, List[str]] = {}
    filenames = [path.name for path in published_root.rglob("*") if path.is_file()]
    for proof_id, hints in DIRECT_PROOF_HINTS.items():
        matches = sorted(name for name in filenames if any(hint in name for hint in hints))
        evidence[proof_id] = matches
        if not matches:
            warnings.append(f"No dedicated published `{proof_id}` proof artifact is present yet.")
    return {"state": "pass", "issues": [], "runtime_blockers": [], "warnings": warnings, "evidence": evidence}


def _flagship_readiness_alignment_monitor(payload: Dict[str, Any], *, runtime_blockers: List[str]) -> Dict[str, Any]:
    blockers: List[str] = []
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
    if runtime_blockers and flagship_ready_status in {"ready", "pass", "passed"}:
        blockers.append(
            "FLAGSHIP_PRODUCT_READINESS still reports flagship_ready while M140 closeout proof is stale, missing, or contradicted."
        )
    return {
        "state": "pass",
        "issues": [],
        "runtime_blockers": blockers,
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
    roadmap_path: Path,
    runner_passport_doc_path: Path,
    runner_passport_acceptance_path: Path,
    world_dispatch_doc_path: Path,
    world_dispatch_gates_path: Path,
    creator_operating_system_path: Path,
    ltd_cadence_system_path: Path,
    ltd_cadence_registry_path: Path,
    ltd_runtime_registry_path: Path,
    public_faq_path: Path,
    public_faq_registry_path: Path,
    public_feature_registry_path: Path,
    public_landing_manifest_path: Path,
    flagship_readiness_path: Path,
    generated_at: str | None = None,
) -> Dict[str, Any]:
    generated_at = generated_at or _utc_now()

    registry = _load_yaml(registry_path)
    fleet_queue = _load_yaml(fleet_queue_path)
    design_queue = _load_yaml(design_queue_path)
    next90_guide = _load_text(next90_guide_path)
    roadmap = _load_text(roadmap_path)
    runner_passport_doc = _load_text(runner_passport_doc_path)
    runner_passport_acceptance = _load_yaml(runner_passport_acceptance_path)
    world_dispatch_doc = _load_text(world_dispatch_doc_path)
    world_dispatch_gates = _load_yaml(world_dispatch_gates_path)
    creator_operating_system = _load_text(creator_operating_system_path)
    ltd_cadence_system = _load_text(ltd_cadence_system_path)
    ltd_cadence_registry = _load_yaml(ltd_cadence_registry_path)
    ltd_runtime_registry = _load_yaml(ltd_runtime_registry_path)
    public_faq = _load_text(public_faq_path)
    public_faq_registry = _load_yaml(public_faq_registry_path)
    public_feature_registry = _load_yaml(public_feature_registry_path)
    public_landing_manifest = _load_yaml(public_landing_manifest_path)
    flagship_readiness = _load_json(flagship_readiness_path)

    milestone = _find_milestone(registry, MILESTONE_ID)
    work_task = _find_work_task(milestone, WORK_TASK_ID)
    fleet_queue_item = _find_queue_item(fleet_queue, WORK_TASK_ID)
    design_queue_item = _find_queue_item(design_queue, WORK_TASK_ID)

    guide_monitor = _marker_monitor(next90_guide, GUIDE_MARKERS, label="Next90 guide canon")
    roadmap_monitor = _marker_monitor(roadmap, ROADMAP_MARKERS, label="Roadmap canon")
    runner_passport_doc_monitor = _marker_monitor(runner_passport_doc, RUNNER_PASSPORT_MARKERS, label="Runner passport canon")
    runner_passport_acceptance_monitor = _runner_passport_acceptance_monitor(runner_passport_acceptance)
    world_dispatch_doc_monitor = _marker_monitor(world_dispatch_doc, WORLD_DISPATCH_MARKERS, label="World dispatch canon")
    world_dispatch_gates_monitor = _world_dispatch_gate_monitor(world_dispatch_gates)
    creator_operating_system_monitor = _marker_monitor(
        creator_operating_system,
        CREATOR_OPERATING_MARKERS,
        label="Creator operating system canon",
    )
    ltd_cadence_system_monitor = _marker_monitor(ltd_cadence_system, LTD_CADENCE_MARKERS, label="LTD cadence canon")
    ltd_cadence_registry_monitor = _ltd_cadence_registry_monitor(ltd_cadence_registry)
    ltd_runtime_registry_monitor = _ltd_runtime_registry_monitor(ltd_runtime_registry)
    queue_alignment = _queue_alignment(work_task=work_task, fleet_queue_item=fleet_queue_item, design_queue_item=design_queue_item)
    public_posture_monitor = _public_posture_runtime_monitor(
        faq_text=public_faq,
        faq_registry=public_faq_registry,
        public_feature_registry=public_feature_registry,
        public_landing_manifest=public_landing_manifest,
    )
    direct_proof_monitor = _direct_proof_presence_monitor(published_root)

    blockers: List[str] = []
    runtime_blockers: List[str] = []
    warnings: List[str] = []
    for name, section in (
        ("next90_guide", guide_monitor),
        ("roadmap", roadmap_monitor),
        ("runner_passport_doc", runner_passport_doc_monitor),
        ("runner_passport_acceptance", runner_passport_acceptance_monitor),
        ("world_dispatch_doc", world_dispatch_doc_monitor),
        ("world_dispatch_gates", world_dispatch_gates_monitor),
        ("creator_operating_system", creator_operating_system_monitor),
        ("ltd_cadence_system", ltd_cadence_system_monitor),
        ("ltd_cadence_registry", ltd_cadence_registry_monitor),
        ("ltd_runtime_registry", ltd_runtime_registry_monitor),
        ("queue_alignment", queue_alignment),
        ("public_posture", public_posture_monitor),
        ("direct_proof_presence", direct_proof_monitor),
    ):
        blockers.extend(f"{name}: {issue}" for issue in section.get("issues") or [])
        runtime_blockers.extend(f"{name}: {issue}" for issue in section.get("runtime_blockers") or [])
        warnings.extend(section.get("warnings") or [])

    flagship_alignment_monitor = _flagship_readiness_alignment_monitor(flagship_readiness, runtime_blockers=runtime_blockers)
    runtime_blockers.extend(f"flagship_readiness_alignment: {issue}" for issue in flagship_alignment_monitor.get("runtime_blockers") or [])

    portability_and_cadence_closeout_status = "blocked" if runtime_blockers else "warning" if warnings else "pass"
    return {
        "contract_name": "fleet.next90_m140_portability_and_cadence_closeout_gates",
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
            "runner_passport_doc": runner_passport_doc_monitor,
            "runner_passport_acceptance": runner_passport_acceptance_monitor,
            "world_dispatch_doc": world_dispatch_doc_monitor,
            "world_dispatch_gates": world_dispatch_gates_monitor,
            "creator_operating_system": creator_operating_system_monitor,
            "ltd_cadence_system": ltd_cadence_system_monitor,
            "ltd_cadence_registry": ltd_cadence_registry_monitor,
            "ltd_runtime_registry": ltd_runtime_registry_monitor,
            "queue_alignment": queue_alignment,
        },
        "runtime_monitors": {
            "public_posture": public_posture_monitor,
            "direct_proof_presence": direct_proof_monitor,
            "flagship_readiness_alignment": flagship_alignment_monitor,
        },
        "monitor_summary": {
            "portability_and_cadence_closeout_status": portability_and_cadence_closeout_status,
            "runtime_blocker_count": len(runtime_blockers),
            "warning_count": len(warnings),
            "bounded_card_count": public_posture_monitor.get("bounded_card_count"),
            "dedicated_proof_slot_count": len(DIRECT_PROOF_HINTS),
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
            "runner_passport_doc": _text_source_link(runner_passport_doc_path),
            "runner_passport_acceptance": _source_link(runner_passport_acceptance_path, runner_passport_acceptance),
            "world_dispatch_doc": _text_source_link(world_dispatch_doc_path),
            "world_dispatch_gates": _source_link(world_dispatch_gates_path, world_dispatch_gates),
            "creator_operating_system": _text_source_link(creator_operating_system_path),
            "ltd_cadence_system": _text_source_link(ltd_cadence_system_path),
            "ltd_cadence_registry": _source_link(ltd_cadence_registry_path, ltd_cadence_registry),
            "ltd_runtime_registry": _source_link(ltd_runtime_registry_path, ltd_runtime_registry),
            "public_faq": _text_source_link(public_faq_path),
            "public_faq_registry": _source_link(public_faq_registry_path, public_faq_registry),
            "public_feature_registry": _source_link(public_feature_registry_path, public_feature_registry),
            "public_landing_manifest": _source_link(public_landing_manifest_path, public_landing_manifest),
            "flagship_readiness": _source_link(flagship_readiness_path, flagship_readiness),
        },
    }


def render_markdown(payload: Dict[str, Any]) -> str:
    summary = dict(payload.get("monitor_summary") or {})
    closeout = dict(payload.get("package_closeout") or {})
    lines = [
        "# Fleet M140 portability and cadence closeout gates",
        "",
        f"- status: {payload.get('status')}",
        f"- package_id: {payload.get('package_id')}",
        f"- frontier_id: {payload.get('frontier_id')}",
        f"- generated_at: {payload.get('generated_at')}",
        "",
        "## Monitor summary",
        f"- portability_and_cadence_closeout_status: {summary.get('portability_and_cadence_closeout_status')}",
        f"- runtime_blocker_count: {summary.get('runtime_blocker_count')}",
        f"- warning_count: {summary.get('warning_count')}",
        f"- bounded_card_count: {summary.get('bounded_card_count')}",
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
        roadmap_path=Path(args.roadmap).resolve(),
        runner_passport_doc_path=Path(args.runner_passport_doc).resolve(),
        runner_passport_acceptance_path=Path(args.runner_passport_acceptance).resolve(),
        world_dispatch_doc_path=Path(args.world_dispatch_doc).resolve(),
        world_dispatch_gates_path=Path(args.world_dispatch_gates).resolve(),
        creator_operating_system_path=Path(args.creator_operating_system).resolve(),
        ltd_cadence_system_path=Path(args.ltd_cadence_system).resolve(),
        ltd_cadence_registry_path=Path(args.ltd_cadence_registry).resolve(),
        ltd_runtime_registry_path=Path(args.ltd_runtime_registry).resolve(),
        public_faq_path=Path(args.public_faq).resolve(),
        public_faq_registry_path=Path(args.public_faq_registry).resolve(),
        public_feature_registry_path=Path(args.public_feature_registry).resolve(),
        public_landing_manifest_path=Path(args.public_landing_manifest).resolve(),
        flagship_readiness_path=Path(args.flagship_readiness).resolve(),
    )
    _write_json_file(output_path, payload)
    _write_markdown_file(markdown_path, render_markdown(payload))
    print(json.dumps({"status": payload["status"], "artifact": str(output_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
