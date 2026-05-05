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

PACKAGE_ID = "next90-m138-fleet-bind-ready-for-tonight-gates-role-kit-registry-vtt-export-target-accep"
FRONTIER_ID = 7914546694
MILESTONE_ID = 138
WORK_TASK_ID = "138.10"
WAVE_ID = "W25"
QUEUE_TITLE = (
    "Bind READY_FOR_TONIGHT_GATES, ROLE_KIT_REGISTRY, VTT_EXPORT_TARGET_ACCEPTANCE, and related newcomer-path proof into "
    "machine-readable readiness and public-truth projections."
)
OWNED_SURFACES = ["bind_ready_for_tonight_gates_role_kit_registry_vtt_expor:fleet"]
ALLOWED_PATHS = ["scripts", "tests", ".codex-studio", "feedback"]

DEFAULT_OUTPUT = PUBLISHED / "NEXT90_M138_FLEET_HERO_PATH_PROJECTIONS.generated.json"
DEFAULT_MARKDOWN = PUBLISHED / "NEXT90_M138_FLEET_HERO_PATH_PROJECTIONS.generated.md"

SUCCESSOR_REGISTRY = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
FLEET_QUEUE_STAGING = PUBLISHED / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
DESIGN_QUEUE_STAGING = PRODUCT_MIRROR / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
NEXT90_GUIDE = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_GUIDE.md"
READY_FOR_TONIGHT_GATES = PRODUCT_MIRROR / "READY_FOR_TONIGHT_GATES.yaml"
PUBLIC_ONBOARDING_PATHS = PRODUCT_MIRROR / "PUBLIC_ONBOARDING_PATHS_FOR_NO_DESKTOP_USERS.md"
ROLE_KIT_REGISTRY = PRODUCT_MIRROR / "ROLE_KIT_REGISTRY.yaml"
SOURCE_AWARE_EXPLAIN = PRODUCT_MIRROR / "SOURCE_AWARE_EXPLAIN_PUBLIC_TRUST_HOOK.md"
CAMPAIGN_ADOPTION_FLOW = PRODUCT_MIRROR / "CAMPAIGN_ADOPTION_START_FROM_TODAY_FLOW.md"
FOUNDRY_FIRST_HANDOFF = PRODUCT_MIRROR / "FOUNDRY_FIRST_VTT_HANDOFF_PROOF.md"
VTT_EXPORT_TARGET_ACCEPTANCE = PRODUCT_MIRROR / "VTT_EXPORT_TARGET_ACCEPTANCE.yaml"
PUBLIC_FAQ_REGISTRY = PRODUCT_MIRROR / "PUBLIC_FAQ_REGISTRY.yaml"
PUBLIC_GUIDE_COMMUNITY_HUB = PRODUCT_MIRROR / "public-guide" / "HORIZONS" / "community-hub.md"
OPEN_RUN_JOURNEY = PRODUCT_MIRROR / "journeys" / "find-and-join-an-open-run.md"
PUBLIC_FEATURE_REGISTRY = PRODUCT_MIRROR / "PUBLIC_FEATURE_REGISTRY.yaml"
PUBLIC_LANDING_MANIFEST = PRODUCT_MIRROR / "PUBLIC_LANDING_MANIFEST.yaml"

GUIDE_MARKERS = {
    "wave_25": "## Wave 25 - turn first emotional wins into release-gated product truth",
    "milestone_138": "### 138. First emotional wins, no-desktop participation, and adoption confidence closure",
}
READY_FOR_TONIGHT_GATE_IDS = (
    "player_readiness_verdict",
    "gm_readiness_verdict",
    "organizer_publishability_verdict",
)
REQUIRED_ROLE_KITS = (
    "street_sam_starter",
    "face_starter",
    "mage_starter",
    "decker_starter",
    "rigger_starter",
    "general_survivor_starter",
)
REQUIRED_VTT_PROOFS = (
    "runner_export",
    "opposition_packet_export",
    "player_safe_handout_export",
    "visible_export_receipt_or_failure",
)
NEWCOMER_CAPABILITIES = (
    "mobile_readable_open_run_listing",
    "quickstart_runner_selection",
    "readable_legality_and_application_preflight",
    "table_contract_acknowledgement",
    "schedule_and_platform_readiness_check",
    "accepted_player_handoff_and_recap_receipt",
    "ready_for_tonight_verdict",
)
ADOPTION_OUTPUTS = (
    "migration_or_adoption_confidence",
    "safe_to_play_posture",
    "unresolved_review_items",
    "explicit_unknown_history_markers",
    "next_best_cleanup_actions",
    "adoption_receipt_and_replay_safe_start_anchor",
)
PUBLIC_FAQ_QUESTIONS = (
    "Would I need a Windows PC to join a run?",
    "Is Chummer trying to replace Discord or VTTs?",
)


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize the Fleet M138 hero-path projections packet.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--markdown-output", default=str(DEFAULT_MARKDOWN))
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--fleet-queue-staging", default=str(FLEET_QUEUE_STAGING))
    parser.add_argument("--design-queue-staging", default=str(DESIGN_QUEUE_STAGING))
    parser.add_argument("--next90-guide", default=str(NEXT90_GUIDE))
    parser.add_argument("--ready-for-tonight-gates", default=str(READY_FOR_TONIGHT_GATES))
    parser.add_argument("--public-onboarding-paths", default=str(PUBLIC_ONBOARDING_PATHS))
    parser.add_argument("--role-kit-registry", default=str(ROLE_KIT_REGISTRY))
    parser.add_argument("--source-aware-explain", default=str(SOURCE_AWARE_EXPLAIN))
    parser.add_argument("--campaign-adoption-flow", default=str(CAMPAIGN_ADOPTION_FLOW))
    parser.add_argument("--foundry-first-handoff", default=str(FOUNDRY_FIRST_HANDOFF))
    parser.add_argument("--vtt-export-target-acceptance", default=str(VTT_EXPORT_TARGET_ACCEPTANCE))
    parser.add_argument("--public-faq-registry", default=str(PUBLIC_FAQ_REGISTRY))
    parser.add_argument("--public-guide-community-hub", default=str(PUBLIC_GUIDE_COMMUNITY_HUB))
    parser.add_argument("--open-run-journey", default=str(OPEN_RUN_JOURNEY))
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
    checks = {name: marker in text for name, marker in markers.items()}
    issues = [f"{label} missing required marker: {name}" for name, present in checks.items() if not present]
    return {"state": "pass" if not issues else "fail", "checks": checks, "issues": issues}


def _queue_alignment(
    *,
    work_task: Dict[str, Any],
    fleet_queue_item: Dict[str, Any],
    design_queue_item: Dict[str, Any],
) -> Dict[str, Any]:
    issues: List[str] = []
    warnings: List[str] = []
    if not work_task:
        issues.append("Canonical registry work task is missing.")
    if not design_queue_item:
        issues.append("Design queue row is missing.")
    if not fleet_queue_item:
        warnings.append("Fleet queue mirror row is still missing for work task 138.10.")
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
                issues.append(f"{label} queue row {key} drifted from the assigned M138 package.")
        if sorted(_normalize_list(row.get("allowed_paths"))) != sorted(ALLOWED_PATHS):
            issues.append(f"{label} queue row allowed_paths drifted from the assigned M138 package.")
        if sorted(_normalize_list(row.get("owned_surfaces"))) != sorted(OWNED_SURFACES):
            issues.append(f"{label} queue row owned_surfaces drifted from the assigned M138 package.")
    return {"state": "pass" if not issues else "fail", "issues": issues, "warnings": warnings}


def _gate_projection_rows(payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {
        _normalize_text(row.get("id")): dict(row)
        for row in payload.get("gates") or []
        if isinstance(row, dict) and _normalize_text(row.get("id"))
    }


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


def _hero_path_public_cards(payload: Dict[str, Any]) -> List[str]:
    cards: List[str] = []
    for row in payload.get("cards") or []:
        if not isinstance(row, dict):
            continue
        searchable = " ".join(
            [
                _normalize_text(row.get("id")),
                _normalize_text(row.get("title")),
                _normalize_text(row.get("summary")),
                _normalize_text(row.get("href")),
            ]
        ).lower()
        if any(term in searchable for term in ("ready for tonight", "quickstart", "foundry", "start from today")):
            cards.append(_normalize_text(row.get("id")) or _normalize_text(row.get("title")))
    return cards


def _hero_path_public_routes(payload: Dict[str, Any]) -> List[str]:
    routes: List[str] = []
    for key in ("public_routes", "auth_routes", "registered_routes"):
        for row in payload.get(key) or []:
            if not isinstance(row, dict):
                continue
            path = _normalize_text(row.get("path"))
            lowered = path.lower()
            if any(term in lowered for term in ("ready-for-tonight", "quickstart", "foundry", "start-from-today")):
                routes.append(path)
    return routes


def build_payload(
    *,
    registry_path: Path,
    fleet_queue_path: Path,
    design_queue_path: Path,
    next90_guide_path: Path,
    ready_for_tonight_gates_path: Path,
    public_onboarding_paths_path: Path,
    role_kit_registry_path: Path,
    source_aware_explain_path: Path,
    campaign_adoption_flow_path: Path,
    foundry_first_handoff_path: Path,
    vtt_export_target_acceptance_path: Path,
    public_faq_registry_path: Path,
    public_guide_community_hub_path: Path,
    open_run_journey_path: Path,
    public_feature_registry_path: Path,
    public_landing_manifest_path: Path,
    generated_at: str | None = None,
) -> Dict[str, Any]:
    generated_at = generated_at or _utc_now()
    registry = _load_yaml(registry_path)
    fleet_queue = _load_yaml(fleet_queue_path)
    design_queue = _load_yaml(design_queue_path)
    next90_guide = _load_text(next90_guide_path)
    ready_for_tonight_gates = _load_yaml(ready_for_tonight_gates_path)
    public_onboarding_paths = _load_text(public_onboarding_paths_path)
    role_kit_registry = _load_yaml(role_kit_registry_path)
    source_aware_explain = _load_text(source_aware_explain_path)
    campaign_adoption_flow = _load_text(campaign_adoption_flow_path)
    foundry_first_handoff = _load_text(foundry_first_handoff_path)
    vtt_export_target_acceptance = _load_yaml(vtt_export_target_acceptance_path)
    public_faq_registry = _load_yaml(public_faq_registry_path)
    public_guide_community_hub = _load_text(public_guide_community_hub_path)
    open_run_journey = _load_text(open_run_journey_path)
    public_feature_registry = _load_yaml(public_feature_registry_path)
    public_landing_manifest = _load_yaml(public_landing_manifest_path)

    milestone = _find_milestone(registry, MILESTONE_ID)
    work_task = _find_work_task(milestone, WORK_TASK_ID)
    fleet_queue_item = _find_queue_item(fleet_queue, WORK_TASK_ID)
    design_queue_item = _find_queue_item(design_queue, WORK_TASK_ID)

    guide_monitor = _marker_monitor(next90_guide, GUIDE_MARKERS, label="Next90 guide canon")
    queue_alignment = _queue_alignment(
        work_task=work_task,
        fleet_queue_item=fleet_queue_item,
        design_queue_item=design_queue_item,
    )

    blockers: List[str] = []
    warnings: List[str] = list(queue_alignment.get("warnings") or [])
    blockers.extend(f"next90_guide: {issue}" for issue in guide_monitor.get("issues") or [])
    blockers.extend(f"queue_alignment: {issue}" for issue in queue_alignment.get("issues") or [])

    gate_rows = _gate_projection_rows(ready_for_tonight_gates)
    missing_gates = [gate_id for gate_id in READY_FOR_TONIGHT_GATE_IDS if gate_id not in gate_rows]
    if missing_gates:
        blockers.append("ready_for_tonight_gates: missing gate ids: " + ", ".join(missing_gates))

    role_kit_rows = {
        _normalize_text(row.get("id")): dict(row)
        for row in role_kit_registry.get("role_kits") or []
        if isinstance(row, dict) and _normalize_text(row.get("id"))
    }
    missing_role_kits = [role_kit_id for role_kit_id in REQUIRED_ROLE_KITS if role_kit_id not in role_kit_rows]
    if missing_role_kits:
        blockers.append("role_kit_registry: missing role kits: " + ", ".join(missing_role_kits))

    vtt_primary = dict(vtt_export_target_acceptance.get("primary_target") or {})
    vtt_required_proofs = _normalize_list(vtt_primary.get("required_proofs"))
    missing_vtt_proofs = [proof for proof in REQUIRED_VTT_PROOFS if proof not in vtt_required_proofs]
    if missing_vtt_proofs:
        blockers.append("vtt_export_target_acceptance: missing required proofs: " + ", ".join(missing_vtt_proofs))

    faq_entries = _faq_entries(public_faq_registry)
    missing_faq_questions = [question for question in PUBLIC_FAQ_QUESTIONS if question not in faq_entries]
    if missing_faq_questions:
        blockers.append("public_faq_registry: missing FAQ questions: " + ", ".join(missing_faq_questions))

    readiness_projection = {
        "status": "pass",
        "projection_kind": "governed_verdict_surface",
        "gate_ids": list(READY_FOR_TONIGHT_GATE_IDS),
        "required_outputs_by_gate": {
            gate_id: _normalize_list(gate_rows.get(gate_id, {}).get("required_outputs"))
            for gate_id in READY_FOR_TONIGHT_GATE_IDS
        },
        "role_kit_ids": list(REQUIRED_ROLE_KITS),
        "public_claim_posture": "not_publicly_live_claimed",
        "truth_sources": [
            "ready_for_tonight_gates.player_readiness_verdict",
            "ready_for_tonight_gates.gm_readiness_verdict",
            "ready_for_tonight_gates.organizer_publishability_verdict",
            "role_kit_registry.starter_loadouts",
            "source_aware_explain.public_trust_hook",
        ],
    }
    newcomer_projection = {
        "status": "pass",
        "projection_kind": "bounded_newcomer_path",
        "journey_id": "find_and_join_open_run",
        "required_capabilities": list(NEWCOMER_CAPABILITIES),
        "public_truth_routes": ["/faq", "/roadmap/community-hub"],
        "public_claim_posture": "bounded_future_goal",
        "desktop_boundary": "desktop_remains_expert_flagship",
        "truth_sources": [
            "public_onboarding_paths.no_desktop_users",
            "public_guide.community_hub",
            "journeys.find_and_join_open_run",
            "public_faq.no_windows_needed",
        ],
    }
    adoption_projection = {
        "status": "pass",
        "projection_kind": "start_from_today_adoption_receipt",
        "required_outputs": list(ADOPTION_OUTPUTS),
        "public_claim_posture": "bounded_public_promise",
        "truth_sources": [
            "campaign_adoption.start_from_today",
            "public_faq.no_windows_needed",
        ],
    }
    foundry_projection = {
        "status": "pass",
        "projection_kind": "projection_only_vtt_handoff",
        "primary_target_id": _normalize_text(vtt_primary.get("id")),
        "required_proofs": list(REQUIRED_VTT_PROOFS),
        "authority_rule": dict(vtt_primary.get("authority_rule") or {}),
        "public_claim_posture": "projection_only",
        "truth_sources": [
            "foundry_first_handoff.proof_package",
            "vtt_export_target_acceptance.primary_target",
            "journeys.find_and_join_open_run",
        ],
    }

    projections = {
        "newcomer_path": newcomer_projection,
        "ready_for_tonight": readiness_projection,
        "adoption_confidence": adoption_projection,
        "foundry_first_handoff": foundry_projection,
    }

    payload = {
        "contract_name": "fleet.next90_m138_hero_path_projections",
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
            "queue_alignment": queue_alignment,
        },
        "projection_summary": {
            "projection_count": len(projections),
            "hero_path_public_card_count": len(_hero_path_public_cards(public_feature_registry)),
            "hero_path_public_route_count": len(_hero_path_public_routes(public_landing_manifest)),
            "faq_question_count": len(faq_entries),
            "warning_count": len(warnings),
        },
        "projections": projections,
        "public_truth_projection": {
            "faq_entries": {
                question: faq_entries.get(question, "")
                for question in PUBLIC_FAQ_QUESTIONS
            },
            "community_hub_stage": "future_concept" if "Future concept." in public_guide_community_hub else "unknown",
            "community_hub_discord_boundary": "chummer_truth_discord_projection"
            if "Discord can remain the community and meeting surface." in public_guide_community_hub
            else "unknown",
            "open_run_mobile_boundary": "mobile_first_no_windows_requirement"
            if "Windows-only requirement" in open_run_journey
            else "unknown",
            "feature_registry_hero_path_cards": _hero_path_public_cards(public_feature_registry),
            "landing_manifest_hero_path_routes": _hero_path_public_routes(public_landing_manifest),
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
            "ready_for_tonight_gates": _source_link(ready_for_tonight_gates_path, ready_for_tonight_gates),
            "public_onboarding_paths": _text_source_link(public_onboarding_paths_path),
            "role_kit_registry": _source_link(role_kit_registry_path, role_kit_registry),
            "source_aware_explain": _text_source_link(source_aware_explain_path),
            "campaign_adoption_flow": _text_source_link(campaign_adoption_flow_path),
            "foundry_first_handoff": _text_source_link(foundry_first_handoff_path),
            "vtt_export_target_acceptance": _source_link(vtt_export_target_acceptance_path, vtt_export_target_acceptance),
            "public_faq_registry": _source_link(public_faq_registry_path, public_faq_registry),
            "public_guide_community_hub": _text_source_link(public_guide_community_hub_path),
            "open_run_journey": _text_source_link(open_run_journey_path),
            "public_feature_registry": _source_link(public_feature_registry_path, public_feature_registry),
            "public_landing_manifest": _source_link(public_landing_manifest_path, public_landing_manifest),
        },
    }
    if "No cloud rulebook upload is required." not in source_aware_explain:
        payload["package_closeout"]["blockers"].append("source_aware_explain: missing local-source trust boundary.")
    if "Desktop remains the expert flagship." not in public_onboarding_paths:
        payload["package_closeout"]["blockers"].append("public_onboarding_paths: missing expert flagship boundary.")
    if "Chummer should let a table start from current truth." not in campaign_adoption_flow:
        payload["package_closeout"]["blockers"].append("campaign_adoption_flow: missing start-from-today adoption rule.")
    if "Chummer remains the canonical truth." not in foundry_first_handoff:
        payload["package_closeout"]["blockers"].append("foundry_first_handoff: missing Chummer truth boundary.")
    if payload["package_closeout"]["blockers"]:
        payload["status"] = "blocked"
        payload["package_closeout"]["state"] = "blocked"
    return payload


def render_markdown(payload: Dict[str, Any]) -> str:
    summary = dict(payload.get("projection_summary") or {})
    closeout = dict(payload.get("package_closeout") or {})
    lines = [
        "# Fleet M138 hero-path projections",
        "",
        f"- status: {payload.get('status')}",
        f"- package_id: {payload.get('package_id')}",
        f"- frontier_id: {payload.get('frontier_id')}",
        f"- generated_at: {payload.get('generated_at')}",
        "",
        "## Projection summary",
        f"- projection_count: {summary.get('projection_count')}",
        f"- hero_path_public_card_count: {summary.get('hero_path_public_card_count')}",
        f"- hero_path_public_route_count: {summary.get('hero_path_public_route_count')}",
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
        ready_for_tonight_gates_path=Path(args.ready_for_tonight_gates).resolve(),
        public_onboarding_paths_path=Path(args.public_onboarding_paths).resolve(),
        role_kit_registry_path=Path(args.role_kit_registry).resolve(),
        source_aware_explain_path=Path(args.source_aware_explain).resolve(),
        campaign_adoption_flow_path=Path(args.campaign_adoption_flow).resolve(),
        foundry_first_handoff_path=Path(args.foundry_first_handoff).resolve(),
        vtt_export_target_acceptance_path=Path(args.vtt_export_target_acceptance).resolve(),
        public_faq_registry_path=Path(args.public_faq_registry).resolve(),
        public_guide_community_hub_path=Path(args.public_guide_community_hub).resolve(),
        open_run_journey_path=Path(args.open_run_journey).resolve(),
        public_feature_registry_path=Path(args.public_feature_registry).resolve(),
        public_landing_manifest_path=Path(args.public_landing_manifest).resolve(),
    )
    _write_json_file(output_path, payload)
    _write_markdown_file(markdown_path, render_markdown(payload))
    print(json.dumps({"status": payload["status"], "artifact": str(output_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
