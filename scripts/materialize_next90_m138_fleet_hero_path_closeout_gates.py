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

PACKAGE_ID = "next90-m138-fleet-fail-closeout-when-the-90-second-newcomer-path-ready-for-tonight-verdi"
FRONTIER_ID = 4764536356
MILESTONE_ID = 138
WORK_TASK_ID = "138.9"
WAVE_ID = "W25"
QUEUE_TITLE = (
    "Fail closeout when the 90-second newcomer path, Ready for Tonight verdicts, adoption-confidence receipts, "
    "or Foundry-first handoff receipts are stale, missing, or contradicted by public posture."
)
OWNED_SURFACES = ["fail_closeout_when_the_90_second_newcomer_path_ready_for:fleet"]
ALLOWED_PATHS = ["scripts", "tests", ".codex-studio", "feedback"]

DEFAULT_OUTPUT = PUBLISHED / "NEXT90_M138_FLEET_HERO_PATH_CLOSEOUT_GATES.generated.json"
DEFAULT_MARKDOWN = PUBLISHED / "NEXT90_M138_FLEET_HERO_PATH_CLOSEOUT_GATES.generated.md"

SUCCESSOR_REGISTRY = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
FLEET_QUEUE_STAGING = PUBLISHED / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
DESIGN_QUEUE_STAGING = PRODUCT_MIRROR / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
NEXT90_GUIDE = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_GUIDE.md"
ROADMAP = PRODUCT_MIRROR / "ROADMAP.md"
READY_FOR_TONIGHT_MODE = PRODUCT_MIRROR / "READY_FOR_TONIGHT_MODE.md"
READY_FOR_TONIGHT_GATES = PRODUCT_MIRROR / "READY_FOR_TONIGHT_GATES.yaml"
PUBLIC_ONBOARDING_PATHS = PRODUCT_MIRROR / "PUBLIC_ONBOARDING_PATHS_FOR_NO_DESKTOP_USERS.md"
ROLE_KITS_AND_STARTER_LOADOUTS = PRODUCT_MIRROR / "ROLE_KITS_AND_STARTER_LOADOUTS.md"
ROLE_KIT_REGISTRY = PRODUCT_MIRROR / "ROLE_KIT_REGISTRY.yaml"
SOURCE_AWARE_EXPLAIN = PRODUCT_MIRROR / "SOURCE_AWARE_EXPLAIN_PUBLIC_TRUST_HOOK.md"
CAMPAIGN_ADOPTION_FLOW = PRODUCT_MIRROR / "CAMPAIGN_ADOPTION_START_FROM_TODAY_FLOW.md"
FOUNDRY_FIRST_HANDOFF = PRODUCT_MIRROR / "FOUNDRY_FIRST_VTT_HANDOFF_PROOF.md"
VTT_EXPORT_TARGET_ACCEPTANCE = PRODUCT_MIRROR / "VTT_EXPORT_TARGET_ACCEPTANCE.yaml"
PUBLIC_FAQ = PRODUCT_MIRROR / "public-guide" / "FAQ.md"
PUBLIC_FAQ_REGISTRY = PRODUCT_MIRROR / "PUBLIC_FAQ_REGISTRY.yaml"
PUBLIC_GUIDE_COMMUNITY_HUB = PRODUCT_MIRROR / "public-guide" / "HORIZONS" / "community-hub.md"
OPEN_RUN_JOURNEY = PRODUCT_MIRROR / "journeys" / "find-and-join-an-open-run.md"
PUBLIC_FEATURE_REGISTRY = PRODUCT_MIRROR / "PUBLIC_FEATURE_REGISTRY.yaml"
PUBLIC_LANDING_MANIFEST = PRODUCT_MIRROR / "PUBLIC_LANDING_MANIFEST.yaml"
FLAGSHIP_READINESS = PUBLISHED / "FLAGSHIP_PRODUCT_READINESS.generated.json"
HERO_PATH_PROJECTIONS = PUBLISHED / "NEXT90_M138_FLEET_HERO_PATH_PROJECTIONS.generated.json"

PROOF_FRESHNESS_HOURS = 72

GUIDE_MARKERS = {
    "wave_25": "## Wave 25 - turn first emotional wins into release-gated product truth",
    "milestone_138": "### 138. First emotional wins, no-desktop participation, and adoption confidence closure",
    "exit_contract": "Exit: the hero paths are real and proven: `Ready for Tonight`, no-desktop beginner participation, start-from-today adoption, source-aware explain, role kits, and one excellent Foundry-first export handoff.",
}
ROADMAP_MARKERS = {
    "hero_path": "* make the first emotional wins impossible to miss: Ready for Tonight, start-from-today adoption, no-desktop participation, source-aware explain, starter role kits, and one excellent Foundry-first handoff",
}
READY_FOR_TONIGHT_MARKERS = {
    "not_dashboard": "`ReadyForTonight` is not a dashboard.",
    "cta": "`Make me ready for this run`",
    "output_contract": "* `proof_receipts`",
    "organizer_view": "### 3. Organizer or public-run readiness",
}
ONBOARDING_MARKERS = {
    "hero_path": "land on public run",
    "desktop_boundary": "Desktop remains the expert flagship.",
    "required_capability": "* receive the `make me ready` verdict and the one remaining missing item, if any",
    "acceptance_rule": "Public scale is not ready until a new player can determine in minutes whether they can join a beginner run without first installing a Windows desktop client.",
}
ROLE_KIT_MARKERS = {
    "governed_decisions": "They are governed starter decisions that reduce cognitive load while staying rule-environment aware and explainable.",
    "product_use": "* Ready for Tonight",
    "explain_rule": "* what can I safely swap",
}
SOURCE_AWARE_EXPLAIN_MARKERS = {
    "public_trust": "This file promotes source-aware explain from a useful feature to a public trust promise.",
    "no_cloud_upload": "No cloud rulebook upload is required.",
    "promoted_routes": "Every important visible mechanical value should either open the packet-backed explain drawer plus source anchor chain or remain an explicit release-blocking gap.",
}
CAMPAIGN_ADOPTION_MARKERS = {
    "start_from_today": "Chummer should let a table start from current truth.",
    "required_output": "* adoption receipt and replay-safe start anchor",
    "public_promise": "* mark what you do not know",
}
FOUNDRY_FIRST_MARKERS = {
    "proof_package": "`one runner -> one opposition packet -> one player-safe handout -> one export receipt`",
    "truth_boundary": "Chummer remains the canonical truth.",
    "non_goal": "* not making Foundry canonical",
}
FAQ_MARKERS = {
    "windows_question": "### Would I need a Windows PC to join a run?",
    "windows_answer": "No. The intended direction is that browsing runs, applying with a quickstart or approved runner, acknowledging table expectations, and receiving scheduling and handoff details should work without assuming a Windows-only setup.",
    "vtt_question": "### Is Chummer trying to replace Discord or VTTs?",
    "vtt_answer": "No. The intended posture is that Chummer owns rules, applications, scheduling records, and world consequences, while Discord, Teams, and VTTs remain play or communication surfaces.",
}
COMMUNITY_HUB_MARKERS = {
    "future_stage": "- Today: Future concept.",
    "desktop_boundary": "That is a core goal. Quickstart runners and mobile-first application paths should reduce the Windows-only chokepoint.",
    "discord_boundary": "No. Chummer owns campaign logic. Discord can remain the community and meeting surface.",
}
OPEN_RUN_JOURNEY_MARKERS = {
    "status": "Status: future_slice_with_bounded_research",
    "mobile_goal": "* A mobile-first player can apply through a quickstart path without a Windows-only requirement.",
    "handoff_truth": "* If scheduling or meeting handoff drift occurs, Chummer-owned receipts must win and the fix must be visible as a projection repair, not silent data disagreement.",
}

REQUIRED_READY_FOR_TONIGHT_GATES = {
    "player_readiness_verdict": {
        "required_inputs": {"runner_dossier", "rule_environment", "session_context", "join_handoff"},
        "required_outputs": {
            "status",
            "blocking_reasons",
            "fix_now_actions",
            "changed_since_last_session",
            "next_best_screen",
        },
    },
    "gm_readiness_verdict": {
        "required_inputs": {"open_run", "roster", "prep_packet", "opposition_packet", "resolution_backlog"},
        "required_outputs": {
            "status",
            "blocking_reasons",
            "unresolved_rewards",
            "unresolved_disputes",
            "export_readiness",
            "next_best_screen",
        },
    },
    "organizer_publishability_verdict": {
        "required_inputs": {"open_run_policy", "community_rule_environment", "table_contract", "safety_posture", "meeting_handoff"},
        "required_outputs": {
            "status",
            "publish_blockers",
            "moderation_risk",
            "participation_bridge_ready",
            "proof_receipts",
        },
    },
}
REQUIRED_ROLE_KITS = {
    "street_sam_starter",
    "face_starter",
    "mage_starter",
    "decker_starter",
    "rigger_starter",
    "general_survivor_starter",
}
REQUIRED_ROLE_KIT_ANSWERS = {
    "why_this_role",
    "why_this_loadout",
    "what_is_missing_for_tonight",
    "what_changes_under_rule_environment",
}
REQUIRED_VTT_PROOFS = {
    "runner_export",
    "opposition_packet_export",
    "player_safe_handout_export",
    "visible_export_receipt_or_failure",
}
FAQ_ENTRY_RULES = {
    "Would I need a Windows PC to join a run?": {
        "must_contain": (
            "No.",
            "intended direction",
            "quickstart or approved runner",
            "without assuming a Windows-only setup",
        ),
    },
    "Is Chummer trying to replace Discord or VTTs?": {
        "must_contain": (
            "No.",
            "Chummer owns rules, applications, scheduling records, and world consequences",
            "remain play or communication surfaces",
        ),
    },
}
PUBLIC_POSTURE_BOUNDARY_PHRASES = {
    "intended direction",
    "intended posture",
    "core goal",
    "future concept",
    "should reduce",
    "should work",
}
LIVE_PUBLIC_BADGES = {"Available now", "Live now", "Inspectable", "Workflow"}
HERO_PATH_TERMS = (
    "ready for tonight",
    "make me ready",
    "quickstart",
    "beginner",
    "foundry",
    "adoption confidence",
    "start from today",
)
REQUIRED_PROJECTION_KEYS = {
    "newcomer_path",
    "ready_for_tonight",
    "adoption_confidence",
    "foundry_first_handoff",
}


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize the Fleet M138 hero-path closeout gate packet.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--markdown-output", default=str(DEFAULT_MARKDOWN))
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--fleet-queue-staging", default=str(FLEET_QUEUE_STAGING))
    parser.add_argument("--design-queue-staging", default=str(DESIGN_QUEUE_STAGING))
    parser.add_argument("--next90-guide", default=str(NEXT90_GUIDE))
    parser.add_argument("--roadmap", default=str(ROADMAP))
    parser.add_argument("--ready-for-tonight-mode", default=str(READY_FOR_TONIGHT_MODE))
    parser.add_argument("--ready-for-tonight-gates", default=str(READY_FOR_TONIGHT_GATES))
    parser.add_argument("--public-onboarding-paths", default=str(PUBLIC_ONBOARDING_PATHS))
    parser.add_argument("--role-kits-and-starter-loadouts", default=str(ROLE_KITS_AND_STARTER_LOADOUTS))
    parser.add_argument("--role-kit-registry", default=str(ROLE_KIT_REGISTRY))
    parser.add_argument("--source-aware-explain", default=str(SOURCE_AWARE_EXPLAIN))
    parser.add_argument("--campaign-adoption-flow", default=str(CAMPAIGN_ADOPTION_FLOW))
    parser.add_argument("--foundry-first-handoff", default=str(FOUNDRY_FIRST_HANDOFF))
    parser.add_argument("--vtt-export-target-acceptance", default=str(VTT_EXPORT_TARGET_ACCEPTANCE))
    parser.add_argument("--public-faq", default=str(PUBLIC_FAQ))
    parser.add_argument("--public-faq-registry", default=str(PUBLIC_FAQ_REGISTRY))
    parser.add_argument("--public-guide-community-hub", default=str(PUBLIC_GUIDE_COMMUNITY_HUB))
    parser.add_argument("--open-run-journey", default=str(OPEN_RUN_JOURNEY))
    parser.add_argument("--public-feature-registry", default=str(PUBLIC_FEATURE_REGISTRY))
    parser.add_argument("--public-landing-manifest", default=str(PUBLIC_LANDING_MANIFEST))
    parser.add_argument("--flagship-readiness", default=str(FLAGSHIP_READINESS))
    parser.add_argument("--hero-path-projections", default=str(HERO_PATH_PROJECTIONS))
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
    return max(0.0, round((now - parsed).total_seconds() / 3600.0, 2))


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
        warnings.append("Fleet queue mirror row is still missing for work task 138.9.")

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


def _ready_for_tonight_gate_monitor(payload: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    gates = {
        _normalize_text(row.get("id")): dict(row)
        for row in payload.get("gates") or []
        if isinstance(row, dict) and _normalize_text(row.get("id"))
    }
    monitored: List[Dict[str, Any]] = []
    if _normalize_text(payload.get("artifact")) != "ready_for_tonight_gates":
        issues.append("READY_FOR_TONIGHT_GATES artifact drifted away from `ready_for_tonight_gates`.")
    for gate_id, spec in REQUIRED_READY_FOR_TONIGHT_GATES.items():
        row = gates.get(gate_id, {})
        if not row:
            issues.append(f"READY_FOR_TONIGHT_GATES is missing gate `{gate_id}`.")
            continue
        required_inputs = set(_normalize_list(row.get("required_inputs")))
        required_outputs = set(_normalize_list(row.get("required_outputs")))
        missing_inputs = sorted(spec["required_inputs"] - required_inputs)
        missing_outputs = sorted(spec["required_outputs"] - required_outputs)
        if missing_inputs:
            issues.append(f"READY_FOR_TONIGHT_GATES `{gate_id}` is missing required_inputs: {', '.join(missing_inputs)}.")
        if missing_outputs:
            issues.append(f"READY_FOR_TONIGHT_GATES `{gate_id}` is missing required_outputs: {', '.join(missing_outputs)}.")
        monitored.append(
            {
                "id": gate_id,
                "required_input_count": len(required_inputs),
                "required_output_count": len(required_outputs),
            }
        )
    return {
        "state": "pass" if not issues else "fail",
        "issues": issues,
        "monitored_gate_count": len(monitored),
        "monitored_gates": monitored,
    }


def _role_kit_registry_monitor(payload: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    rows = {
        _normalize_text(row.get("id")): dict(row)
        for row in payload.get("role_kits") or []
        if isinstance(row, dict) and _normalize_text(row.get("id"))
    }
    missing = sorted(REQUIRED_ROLE_KITS - set(rows))
    if missing:
        issues.append(f"ROLE_KIT_REGISTRY is missing required starter kits: {', '.join(missing)}.")
    monitored: List[Dict[str, Any]] = []
    for role_kit_id in sorted(REQUIRED_ROLE_KITS):
        row = rows.get(role_kit_id, {})
        if not row:
            continue
        must_answer = set(_normalize_list(row.get("must_answer")))
        missing_answers = sorted(REQUIRED_ROLE_KIT_ANSWERS - must_answer)
        if missing_answers:
            issues.append(f"ROLE_KIT_REGISTRY `{role_kit_id}` is missing must_answer entries: {', '.join(missing_answers)}.")
        if _normalize_text(row.get("audience")) != "beginner_or_returning_player":
            issues.append(f"ROLE_KIT_REGISTRY `{role_kit_id}` audience drifted away from beginner_or_returning_player.")
        monitored.append({"id": role_kit_id, "must_answer_count": len(must_answer)})
    return {
        "state": "pass" if not issues else "fail",
        "issues": issues,
        "monitored_role_kit_count": len(monitored),
        "monitored_role_kits": monitored,
    }


def _vtt_export_target_monitor(payload: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    primary = dict(payload.get("primary_target") or {})
    authority_rule = dict(primary.get("authority_rule") or {})
    proofs = set(_normalize_list(primary.get("required_proofs")))
    if _normalize_text(payload.get("artifact")) != "vtt_export_target_acceptance":
        issues.append("VTT_EXPORT_TARGET_ACCEPTANCE artifact drifted away from `vtt_export_target_acceptance`.")
    if _normalize_text(primary.get("id")) != "foundry_first":
        issues.append("VTT_EXPORT_TARGET_ACCEPTANCE primary_target.id drifted from `foundry_first`.")
    if _normalize_text(primary.get("kind")) != "structured_projection":
        issues.append("VTT_EXPORT_TARGET_ACCEPTANCE primary_target.kind drifted from `structured_projection`.")
    missing_proofs = sorted(REQUIRED_VTT_PROOFS - proofs)
    if missing_proofs:
        issues.append(f"VTT_EXPORT_TARGET_ACCEPTANCE primary_target.required_proofs is missing: {', '.join(missing_proofs)}.")
    if authority_rule.get("chummer_is_truth") is not True:
        issues.append("VTT_EXPORT_TARGET_ACCEPTANCE no longer states that Chummer is truth.")
    if authority_rule.get("target_is_projection_only") is not True:
        issues.append("VTT_EXPORT_TARGET_ACCEPTANCE no longer states that the target is projection only.")
    return {
        "state": "pass" if not issues else "fail",
        "issues": issues,
        "required_proof_count": len(proofs),
        "secondary_target_count": len(payload.get("secondary_targets") or []),
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


def _faq_registry_monitor(payload: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    entries = _faq_entries(payload)
    monitored: List[Dict[str, Any]] = []
    for question, spec in FAQ_ENTRY_RULES.items():
        answer = entries.get(question, "")
        if not answer:
            issues.append(f"PUBLIC_FAQ_REGISTRY is missing question `{question}`.")
            continue
        missing = [marker for marker in spec["must_contain"] if marker not in answer]
        if missing:
            issues.append(f"PUBLIC_FAQ_REGISTRY `{question}` answer is missing: {', '.join(missing)}.")
        monitored.append({"question": question, "answer_length": len(answer)})
    return {
        "state": "pass" if not issues else "fail",
        "issues": issues,
        "monitored_entry_count": len(monitored),
        "monitored_entries": monitored,
    }


def _public_posture_runtime_monitor(
    *,
    faq_text: str,
    faq_registry: Dict[str, Any],
    community_hub_text: str,
    public_feature_registry: Dict[str, Any],
    public_landing_manifest: Dict[str, Any],
) -> Dict[str, Any]:
    runtime_blockers: List[str] = []
    warnings: List[str] = []

    registry_entries = _faq_entries(faq_registry)
    bounded_faq_count = 0
    for question, spec in FAQ_ENTRY_RULES.items():
        answer = registry_entries.get(question, "")
        if answer and any(phrase in answer.lower() for phrase in PUBLIC_POSTURE_BOUNDARY_PHRASES):
            bounded_faq_count += 1
        elif answer:
            runtime_blockers.append(f"PUBLIC_FAQ_REGISTRY `{question}` overclaims the hero path without boundary language.")

    if "That is a core goal." not in community_hub_text:
        runtime_blockers.append("COMMUNITY HUB public guide no longer labels no-desktop participation as a core goal.")
    if "- Today: Future concept." not in community_hub_text:
        runtime_blockers.append("COMMUNITY HUB public guide no longer marks the horizon as future concept.")

    live_claiming_cards: List[str] = []
    for row in public_feature_registry.get("cards") or []:
        if not isinstance(row, dict):
            continue
        searchable = " ".join(
            [
                _normalize_text(row.get("title")),
                _normalize_text(row.get("summary")),
                _normalize_text(row.get("href")),
                _normalize_text(row.get("id")),
            ]
        ).lower()
        if not any(term in searchable for term in HERO_PATH_TERMS):
            continue
        badge = _normalize_text(row.get("badge"))
        if badge in LIVE_PUBLIC_BADGES:
            live_claiming_cards.append(_normalize_text(row.get("id")) or _normalize_text(row.get("title")) or "unknown_card")
    if live_claiming_cards:
        runtime_blockers.append(
            "PUBLIC_FEATURE_REGISTRY exposes live hero-path public cards without projection-backed closeout proof: "
            + ", ".join(sorted(live_claiming_cards))
            + "."
        )

    public_routes = [
        dict(row)
        for collection in ("public_routes", "auth_routes", "registered_routes")
        for row in (public_landing_manifest.get(collection) or [])
        if isinstance(row, dict)
    ]
    for route in public_routes:
        path = _normalize_text(route.get("path")).lower()
        if path in {"/faq", "/roadmap/community-hub"}:
            continue
        if any(term.replace(" ", "-") in path for term in HERO_PATH_TERMS):
            runtime_blockers.append(
                f"PUBLIC_LANDING_MANIFEST exposes hero-path route `{_normalize_text(route.get('path'))}` without closeout proof binding."
            )

    if "Would I need a Windows PC to join a run?" not in faq_text:
        warnings.append("FAQ.md did not surface the Windows join-path question in markdown form.")
    if "Is Chummer trying to replace Discord or VTTs?" not in faq_text:
        warnings.append("FAQ.md did not surface the Discord/VTT boundary question in markdown form.")

    return {
        "state": "pass",
        "issues": [],
        "runtime_blockers": runtime_blockers,
        "warnings": warnings,
        "bounded_faq_count": bounded_faq_count,
        "live_claiming_public_card_count": len(live_claiming_cards),
    }


def _hero_path_projection_monitor(payload: Dict[str, Any], *, now: dt.datetime) -> Dict[str, Any]:
    runtime_blockers: List[str] = []
    warnings: List[str] = []
    if not payload:
        runtime_blockers.append("Machine-readable hero-path projections artifact is missing.")
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
    if _normalize_text(payload.get("contract_name")) != "fleet.next90_m138_hero_path_projections":
        runtime_blockers.append("Machine-readable hero-path projections artifact contract_name drifted from the assigned projection contract.")
    if _normalize_text(payload.get("status")).lower() not in {"pass", "passed", "ready"}:
        runtime_blockers.append("Machine-readable hero-path projections artifact is not passing.")
    if age is None:
        runtime_blockers.append("Machine-readable hero-path projections artifact generated_at is missing or invalid.")
    elif age > PROOF_FRESHNESS_HOURS:
        runtime_blockers.append(
            f"Machine-readable hero-path projections artifact freshness exceeded the {PROOF_FRESHNESS_HOURS}h threshold ({age}h)."
        )
    projections = dict(payload.get("projections") or {})
    missing_keys = sorted(REQUIRED_PROJECTION_KEYS - set(projections))
    if missing_keys:
        runtime_blockers.append(
            "Machine-readable hero-path projections artifact is missing required projections: " + ", ".join(missing_keys) + "."
        )
    projection_statuses: Dict[str, str] = {}
    for key in sorted(REQUIRED_PROJECTION_KEYS):
        row = dict(projections.get(key) or {})
        status = _normalize_text(row.get("status")).lower()
        projection_statuses[key] = status
        if row and status not in {"pass", "passed", "ready"}:
            runtime_blockers.append(f"Hero-path projection `{key}` is {status or 'unknown'}.")
        truth_sources = _normalize_list(row.get("truth_sources"))
        if row and not truth_sources:
            runtime_blockers.append(f"Hero-path projection `{key}` is missing truth_sources.")
    return {
        "state": "pass",
        "issues": [],
        "runtime_blockers": runtime_blockers,
        "warnings": warnings,
        "projection_statuses": projection_statuses,
        "generated_at": generated_at,
        "age_hours": age,
    }


def _flagship_readiness_alignment_monitor(
    payload: Dict[str, Any],
    *,
    hero_path_projection_monitor: Dict[str, Any],
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
    if hero_path_projection_monitor.get("runtime_blockers") and flagship_ready_status in {"ready", "pass", "passed"}:
        runtime_blockers.append(
            "FLAGSHIP_PRODUCT_READINESS still reports flagship_ready while hero-path closeout proof is missing, stale, or contradicted."
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
    registry_path: Path,
    fleet_queue_path: Path,
    design_queue_path: Path,
    next90_guide_path: Path,
    roadmap_path: Path,
    ready_for_tonight_mode_path: Path,
    ready_for_tonight_gates_path: Path,
    public_onboarding_paths_path: Path,
    role_kits_and_starter_loadouts_path: Path,
    role_kit_registry_path: Path,
    source_aware_explain_path: Path,
    campaign_adoption_flow_path: Path,
    foundry_first_handoff_path: Path,
    vtt_export_target_acceptance_path: Path,
    public_faq_path: Path,
    public_faq_registry_path: Path,
    public_guide_community_hub_path: Path,
    open_run_journey_path: Path,
    public_feature_registry_path: Path,
    public_landing_manifest_path: Path,
    flagship_readiness_path: Path,
    hero_path_projections_path: Path,
    generated_at: str | None = None,
) -> Dict[str, Any]:
    generated_at = generated_at or _utc_now()
    now = _parse_iso_utc(generated_at) or dt.datetime.now(dt.timezone.utc)

    registry = _load_yaml(registry_path)
    fleet_queue = _load_yaml(fleet_queue_path)
    design_queue = _load_yaml(design_queue_path)
    next90_guide = _load_text(next90_guide_path)
    roadmap = _load_text(roadmap_path)
    ready_for_tonight_mode = _load_text(ready_for_tonight_mode_path)
    ready_for_tonight_gates = _load_yaml(ready_for_tonight_gates_path)
    public_onboarding_paths = _load_text(public_onboarding_paths_path)
    role_kits_and_starter_loadouts = _load_text(role_kits_and_starter_loadouts_path)
    role_kit_registry = _load_yaml(role_kit_registry_path)
    source_aware_explain = _load_text(source_aware_explain_path)
    campaign_adoption_flow = _load_text(campaign_adoption_flow_path)
    foundry_first_handoff = _load_text(foundry_first_handoff_path)
    vtt_export_target_acceptance = _load_yaml(vtt_export_target_acceptance_path)
    public_faq = _load_text(public_faq_path)
    public_faq_registry = _load_yaml(public_faq_registry_path)
    public_guide_community_hub = _load_text(public_guide_community_hub_path)
    open_run_journey = _load_text(open_run_journey_path)
    public_feature_registry = _load_yaml(public_feature_registry_path)
    public_landing_manifest = _load_yaml(public_landing_manifest_path)
    flagship_readiness = _load_json(flagship_readiness_path)
    hero_path_projections = _load_json(hero_path_projections_path)

    milestone = _find_milestone(registry, MILESTONE_ID)
    work_task = _find_work_task(milestone, WORK_TASK_ID)
    fleet_queue_item = _find_queue_item(fleet_queue, WORK_TASK_ID)
    design_queue_item = _find_queue_item(design_queue, WORK_TASK_ID)

    guide_monitor = _marker_monitor(next90_guide, GUIDE_MARKERS, label="Next90 guide canon")
    roadmap_monitor = _marker_monitor(roadmap, ROADMAP_MARKERS, label="Roadmap canon")
    ready_for_tonight_mode_monitor = _marker_monitor(
        ready_for_tonight_mode,
        READY_FOR_TONIGHT_MARKERS,
        label="READY_FOR_TONIGHT_MODE canon",
    )
    public_onboarding_monitor = _marker_monitor(
        public_onboarding_paths,
        ONBOARDING_MARKERS,
        label="PUBLIC_ONBOARDING_PATHS_FOR_NO_DESKTOP_USERS canon",
    )
    role_kits_doc_monitor = _marker_monitor(
        role_kits_and_starter_loadouts,
        ROLE_KIT_MARKERS,
        label="ROLE_KITS_AND_STARTER_LOADOUTS canon",
    )
    source_aware_explain_monitor = _marker_monitor(
        source_aware_explain,
        SOURCE_AWARE_EXPLAIN_MARKERS,
        label="SOURCE_AWARE_EXPLAIN_PUBLIC_TRUST_HOOK canon",
    )
    campaign_adoption_monitor = _marker_monitor(
        campaign_adoption_flow,
        CAMPAIGN_ADOPTION_MARKERS,
        label="CAMPAIGN_ADOPTION_START_FROM_TODAY_FLOW canon",
    )
    foundry_first_monitor = _marker_monitor(
        foundry_first_handoff,
        FOUNDRY_FIRST_MARKERS,
        label="FOUNDRY_FIRST_VTT_HANDOFF_PROOF canon",
    )
    faq_markdown_monitor = _marker_monitor(public_faq, FAQ_MARKERS, label="FAQ markdown canon")
    community_hub_monitor = _marker_monitor(
        public_guide_community_hub,
        COMMUNITY_HUB_MARKERS,
        label="COMMUNITY HUB public guide canon",
    )
    open_run_journey_monitor = _marker_monitor(
        open_run_journey,
        OPEN_RUN_JOURNEY_MARKERS,
        label="Find and join an open run canon",
    )
    queue_alignment = _queue_alignment(
        work_task=work_task,
        fleet_queue_item=fleet_queue_item,
        design_queue_item=design_queue_item,
    )
    ready_for_tonight_gate_monitor = _ready_for_tonight_gate_monitor(ready_for_tonight_gates)
    role_kit_registry_monitor = _role_kit_registry_monitor(role_kit_registry)
    vtt_export_monitor = _vtt_export_target_monitor(vtt_export_target_acceptance)
    faq_registry_monitor = _faq_registry_monitor(public_faq_registry)

    public_posture_runtime_monitor = _public_posture_runtime_monitor(
        faq_text=public_faq,
        faq_registry=public_faq_registry,
        community_hub_text=public_guide_community_hub,
        public_feature_registry=public_feature_registry,
        public_landing_manifest=public_landing_manifest,
    )
    hero_path_projection_monitor = _hero_path_projection_monitor(hero_path_projections, now=now)
    flagship_alignment_monitor = _flagship_readiness_alignment_monitor(
        flagship_readiness,
        hero_path_projection_monitor=hero_path_projection_monitor,
    )

    blockers: List[str] = []
    runtime_blockers: List[str] = []
    warnings: List[str] = []
    for name, section in (
        ("next90_guide", guide_monitor),
        ("roadmap", roadmap_monitor),
        ("queue_alignment", queue_alignment),
        ("ready_for_tonight_mode", ready_for_tonight_mode_monitor),
        ("ready_for_tonight_gates", ready_for_tonight_gate_monitor),
        ("public_onboarding_paths", public_onboarding_monitor),
        ("role_kits_and_starter_loadouts", role_kits_doc_monitor),
        ("role_kit_registry", role_kit_registry_monitor),
        ("source_aware_explain", source_aware_explain_monitor),
        ("campaign_adoption_flow", campaign_adoption_monitor),
        ("foundry_first_handoff", foundry_first_monitor),
        ("vtt_export_target_acceptance", vtt_export_monitor),
        ("faq_markdown", faq_markdown_monitor),
        ("faq_registry", faq_registry_monitor),
        ("community_hub_public_guide", community_hub_monitor),
        ("open_run_journey", open_run_journey_monitor),
        ("public_posture", public_posture_runtime_monitor),
        ("hero_path_projections", hero_path_projection_monitor),
        ("flagship_readiness_alignment", flagship_alignment_monitor),
    ):
        blockers.extend(f"{name}: {issue}" for issue in section.get("issues") or [])
        runtime_blockers.extend(f"{name}: {issue}" for issue in section.get("runtime_blockers") or [])
        warnings.extend(section.get("warnings") or [])

    hero_path_closeout_status = "blocked" if runtime_blockers else "warning" if warnings else "pass"
    return {
        "contract_name": "fleet.next90_m138_hero_path_closeout_gates",
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
            "ready_for_tonight_mode": ready_for_tonight_mode_monitor,
            "ready_for_tonight_gates": ready_for_tonight_gate_monitor,
            "public_onboarding_paths": public_onboarding_monitor,
            "role_kits_and_starter_loadouts": role_kits_doc_monitor,
            "role_kit_registry": role_kit_registry_monitor,
            "source_aware_explain": source_aware_explain_monitor,
            "campaign_adoption_flow": campaign_adoption_monitor,
            "foundry_first_handoff": foundry_first_monitor,
            "vtt_export_target_acceptance": vtt_export_monitor,
            "faq_markdown": faq_markdown_monitor,
            "faq_registry": faq_registry_monitor,
            "community_hub_public_guide": community_hub_monitor,
            "open_run_journey": open_run_journey_monitor,
        },
        "runtime_monitors": {
            "public_posture": public_posture_runtime_monitor,
            "hero_path_projections": hero_path_projection_monitor,
            "flagship_readiness_alignment": flagship_alignment_monitor,
        },
        "monitor_summary": {
            "hero_path_closeout_status": hero_path_closeout_status,
            "runtime_blocker_count": len(runtime_blockers),
            "warning_count": len(warnings),
            "bounded_faq_count": public_posture_runtime_monitor.get("bounded_faq_count"),
            "projection_runtime_blocker_count": len(hero_path_projection_monitor.get("runtime_blockers") or []),
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
            "ready_for_tonight_mode": _text_source_link(ready_for_tonight_mode_path),
            "ready_for_tonight_gates": _source_link(ready_for_tonight_gates_path, ready_for_tonight_gates),
            "public_onboarding_paths": _text_source_link(public_onboarding_paths_path),
            "role_kits_and_starter_loadouts": _text_source_link(role_kits_and_starter_loadouts_path),
            "role_kit_registry": _source_link(role_kit_registry_path, role_kit_registry),
            "source_aware_explain": _text_source_link(source_aware_explain_path),
            "campaign_adoption_flow": _text_source_link(campaign_adoption_flow_path),
            "foundry_first_handoff": _text_source_link(foundry_first_handoff_path),
            "vtt_export_target_acceptance": _source_link(vtt_export_target_acceptance_path, vtt_export_target_acceptance),
            "public_faq": _text_source_link(public_faq_path),
            "public_faq_registry": _source_link(public_faq_registry_path, public_faq_registry),
            "public_guide_community_hub": _text_source_link(public_guide_community_hub_path),
            "open_run_journey": _text_source_link(open_run_journey_path),
            "public_feature_registry": _source_link(public_feature_registry_path, public_feature_registry),
            "public_landing_manifest": _source_link(public_landing_manifest_path, public_landing_manifest),
            "flagship_readiness": _source_link(flagship_readiness_path, flagship_readiness),
            "hero_path_projections": _source_link(hero_path_projections_path, hero_path_projections),
        },
    }


def render_markdown(payload: Dict[str, Any]) -> str:
    summary = dict(payload.get("monitor_summary") or {})
    closeout = dict(payload.get("package_closeout") or {})
    lines = [
        "# Fleet M138 hero-path closeout gates",
        "",
        f"- status: {payload.get('status')}",
        f"- hero_path_closeout_status: {summary.get('hero_path_closeout_status')}",
        f"- package_id: {payload.get('package_id')}",
        f"- frontier_id: {payload.get('frontier_id')}",
        f"- generated_at: {payload.get('generated_at')}",
        "",
        "## Runtime summary",
        f"- bounded_faq_count: {summary.get('bounded_faq_count')}",
        f"- projection_runtime_blocker_count: {summary.get('projection_runtime_blocker_count')}",
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
        ready_for_tonight_mode_path=Path(args.ready_for_tonight_mode).resolve(),
        ready_for_tonight_gates_path=Path(args.ready_for_tonight_gates).resolve(),
        public_onboarding_paths_path=Path(args.public_onboarding_paths).resolve(),
        role_kits_and_starter_loadouts_path=Path(args.role_kits_and_starter_loadouts).resolve(),
        role_kit_registry_path=Path(args.role_kit_registry).resolve(),
        source_aware_explain_path=Path(args.source_aware_explain).resolve(),
        campaign_adoption_flow_path=Path(args.campaign_adoption_flow).resolve(),
        foundry_first_handoff_path=Path(args.foundry_first_handoff).resolve(),
        vtt_export_target_acceptance_path=Path(args.vtt_export_target_acceptance).resolve(),
        public_faq_path=Path(args.public_faq).resolve(),
        public_faq_registry_path=Path(args.public_faq_registry).resolve(),
        public_guide_community_hub_path=Path(args.public_guide_community_hub).resolve(),
        open_run_journey_path=Path(args.open_run_journey).resolve(),
        public_feature_registry_path=Path(args.public_feature_registry).resolve(),
        public_landing_manifest_path=Path(args.public_landing_manifest).resolve(),
        flagship_readiness_path=Path(args.flagship_readiness).resolve(),
        hero_path_projections_path=Path(args.hero_path_projections).resolve(),
    )
    _write_json_file(output_path, payload)
    _write_markdown_file(markdown_path, render_markdown(payload))
    print(json.dumps({"status": payload["status"], "artifact": str(output_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
