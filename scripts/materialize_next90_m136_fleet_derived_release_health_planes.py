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

PACKAGE_ID = "next90-m136-fleet-publish-derived-release-health-planes-from-live-proof-so-structural-gr"
FRONTIER_ID = 8422537713
MILESTONE_ID = 136
WORK_TASK_ID = "136.11"
WAVE_ID = "W23"
QUEUE_TITLE = (
    "Publish derived release-health planes from live proof so structural green cannot masquerade as SR5 veteran, "
    "durability, explainability, or public-shelf readiness."
)
OWNED_SURFACES = ["publish_derived_release_health_planes_from_live_proof_so:fleet"]
ALLOWED_PATHS = ["scripts", "tests", ".codex-studio", "feedback"]

DEFAULT_OUTPUT = PUBLISHED / "NEXT90_M136_FLEET_DERIVED_RELEASE_HEALTH_PLANES.generated.json"
DEFAULT_MARKDOWN = PUBLISHED / "NEXT90_M136_FLEET_DERIVED_RELEASE_HEALTH_PLANES.generated.md"

SUCCESSOR_REGISTRY = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
FLEET_QUEUE_STAGING = PUBLISHED / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
DESIGN_QUEUE_STAGING = PRODUCT_MIRROR / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
NEXT90_GUIDE = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_GUIDE.md"
FLAGSHIP_READINESS_PLANES = PRODUCT_MIRROR / "FLAGSHIP_READINESS_PLANES.yaml"
FLAGSHIP_PRODUCT_BAR = PRODUCT_MIRROR / "FLAGSHIP_PRODUCT_BAR.md"
FLAGSHIP_PRODUCT_READINESS = PUBLISHED / "FLAGSHIP_PRODUCT_READINESS.generated.json"

GUIDE_MARKERS = {
    "wave_23": "## Wave 23 - close calm-under-pressure payoff and veteran continuity",
    "milestone_136": "### 136. Calm-under-pressure payoff, veteran-depth parity, and campaign continuity closure",
}
BAR_MARKERS = {
    "trust_outweighs_cosmetic_similarity": "### 2a. Trust, durability, and explainability outrank cosmetic similarity",
    "planes_machine_tracked": "Those planes are machine-tracked in `FLAGSHIP_READINESS_PLANES.yaml`.",
}
REQUIRED_PLANE_IDS = [
    "structural_ready",
    "flagship_ready",
    "sr5_veteran_ready",
    "veteran_deep_workflow_ready",
    "public_shelf_ready",
    "data_durability_ready",
    "rules_explainability_ready",
]
REQUIRED_CONTRACT_PLANE_IDS = [plane_id for plane_id in REQUIRED_PLANE_IDS if plane_id != "structural_ready"]
REQUIRED_PLANE_CONTRACTS = {
    "flagship_ready": {
        "fail_when": [
            "Any release-health plane below `ready`",
            "Any in-scope flagship parity family below `gold_ready`",
        ],
        "proving_artifacts": ["/docker/fleet/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json"],
    },
    "sr5_veteran_ready": {
        "fail_when": [
            "A veteran cannot orient in the first minute without browser ritual or dashboard detour",
            "Dialog-level parity evidence stays stale or incomplete for release-blocking SR5 families",
        ],
        "proving_artifacts": [
            "/docker/chummercomplete/chummer-presentation/.codex-studio/published/DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json",
            "/docker/fleet/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json",
        ],
    },
    "veteran_deep_workflow_ready": {
        "fail_when": [
            "Dense builder, import, continuity, utility, or export families remain below `veteran_approved`",
            "Workflow execution proof leaves unresolved flagship-family receipts",
        ],
        "proving_artifacts": [
            "/docker/chummercomplete/chummer-presentation/.codex-studio/published/DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json",
            "/docker/chummercomplete/chummer-presentation/.codex-studio/published/CHUMMER5A_UI_ELEMENT_PARITY_AUDIT.generated.json",
        ],
    },
    "public_shelf_ready": {
        "fail_when": [
            "Public shelf, route posture, and promoted tuples disagree",
            "The recommended public path is thinner or riskier than the flagship desktop promise",
        ],
        "proving_artifacts": [
            "/docker/chummercomplete/chummer-presentation/Docker/Downloads/RELEASE_CHANNEL.generated.json",
            "/docker/fleet/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json",
        ],
    },
    "data_durability_ready": {
        "fail_when": [
            "Character, campaign, import, restore, or export flows can lose governed truth across update, rollback, or migration",
        ],
        "proving_artifacts": [
            "/docker/chummercomplete/chummer6-core/.codex-studio/published/ENGINE_PROOF_PACK.generated.json",
            "/docker/fleet/.codex-studio/published/JOURNEY_GATES.generated.json",
        ],
    },
    "rules_explainability_ready": {
        "fail_when": [
            "Important computed values cannot be explained where users ask why",
            "Explain coverage-registry, source-anchor class, or bounded follow-up release-gate truth drifts from Fleet closeout evidence",
            "Explain/build journeys remain blocked or implicit",
        ],
        "proving_artifacts": [
            "/docker/chummercomplete/chummer6-core/.codex-studio/published/ENGINE_PROOF_PACK.generated.json",
            "/docker/fleet/.codex-studio/published/JOURNEY_GATES.generated.json",
        ],
    },
}


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize the Fleet M136 derived release-health plane packet.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--markdown-output", default=str(DEFAULT_MARKDOWN))
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--fleet-queue-staging", default=str(FLEET_QUEUE_STAGING))
    parser.add_argument("--design-queue-staging", default=str(DESIGN_QUEUE_STAGING))
    parser.add_argument("--next90-guide", default=str(NEXT90_GUIDE))
    parser.add_argument("--flagship-readiness-planes", default=str(FLAGSHIP_READINESS_PLANES))
    parser.add_argument("--flagship-product-bar", default=str(FLAGSHIP_PRODUCT_BAR))
    parser.add_argument("--flagship-product-readiness", default=str(FLAGSHIP_PRODUCT_READINESS))
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
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
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


def _is_ready(value: Any) -> bool:
    return _normalize_text(value).lower() == "ready"


def _is_passing(value: Any) -> bool:
    return _normalize_text(value).lower() in {"pass", "passed", "ready", "ok"}


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
        warnings.append("Fleet queue mirror row is still missing for work task 136.11.")

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
    return {
        "state": "pass" if not issues else "fail",
        "issues": issues,
        "warnings": warnings,
    }


def _planes_contract_monitor(planes_payload: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    warnings: List[str] = []
    if _normalize_text(planes_payload.get("purpose")) != "Machine-readable release-health planes that separate structural completion from flagship replacement truth.":
        issues.append("FLAGSHIP_READINESS_PLANES purpose drifted from the derived-plane contract.")
    status_values = _normalize_list(planes_payload.get("status_values"))
    if status_values != ["missing", "warning", "ready"]:
        issues.append("FLAGSHIP_READINESS_PLANES status_values drifted from the ready/warning/missing contract.")
    policy = dict(planes_payload.get("policy") or {})
    structural_policy = _normalize_list(policy.get("structural_green_is_not_flagship_green"))
    if "Every release-health plane must name an owner repo, source artifact, proving artifact, and concrete fail condition." not in structural_policy:
        issues.append("FLAGSHIP_READINESS_PLANES no longer requires explicit release-health plane derivation inputs.")
    plane_rows = [dict(row) for row in (planes_payload.get("planes") or []) if isinstance(row, dict)]
    by_id = {_normalize_text(row.get("id")): row for row in plane_rows if _normalize_text(row.get("id"))}
    missing_plane_ids = [plane_id for plane_id in REQUIRED_CONTRACT_PLANE_IDS if plane_id not in by_id]
    if missing_plane_ids:
        issues.append("FLAGSHIP_READINESS_PLANES is missing required plane ids: " + ", ".join(missing_plane_ids) + ".")
    for plane_id, contract in REQUIRED_PLANE_CONTRACTS.items():
        row = by_id.get(plane_id, {})
        if not row:
            continue
        owners = _normalize_list(row.get("owner_repos"))
        if "fleet" not in owners:
            issues.append(f"FLAGSHIP_READINESS_PLANES {plane_id} no longer lists fleet as an owner repo.")
        proving = _normalize_list(row.get("proving_artifacts"))
        for artifact in contract["proving_artifacts"]:
            if artifact not in proving:
                issues.append(f"FLAGSHIP_READINESS_PLANES {plane_id} is missing proving artifact {artifact}.")
        fail_when = _normalize_list(row.get("fail_when"))
        for clause in contract["fail_when"]:
            if clause not in fail_when:
                issues.append(f"FLAGSHIP_READINESS_PLANES {plane_id} is missing fail_when clause: {clause}")
    return {
        "state": "pass" if not issues else "fail",
        "issues": issues,
        "warnings": warnings,
        "required_plane_ids": REQUIRED_CONTRACT_PLANE_IDS,
    }


def _plane_payload(flagship_payload: Dict[str, Any], plane_id: str) -> Dict[str, Any]:
    planes = flagship_payload.get("readiness_planes")
    if not isinstance(planes, dict):
        return {}
    row = planes.get(plane_id)
    return dict(row) if isinstance(row, dict) else {}


def _coverage_status(flagship_payload: Dict[str, Any], coverage_id: str) -> str:
    coverage = flagship_payload.get("coverage")
    if not isinstance(coverage, dict):
        return ""
    return _normalize_text(coverage.get(coverage_id)).lower()


def _coverage_evidence(flagship_payload: Dict[str, Any], coverage_id: str) -> Dict[str, Any]:
    details = flagship_payload.get("coverage_details")
    if not isinstance(details, dict):
        return {}
    row = details.get(coverage_id)
    if not isinstance(row, dict):
        return {}
    evidence = row.get("evidence")
    return dict(evidence) if isinstance(evidence, dict) else {}


def _plane_presence_monitor(flagship_payload: Dict[str, Any]) -> Dict[str, Any]:
    runtime_blockers: List[str] = []
    plane_statuses: Dict[str, str] = {}
    for plane_id in REQUIRED_PLANE_IDS:
        row = _plane_payload(flagship_payload, plane_id)
        if not row:
            runtime_blockers.append(f"FLAGSHIP_PRODUCT_READINESS is missing release-health plane {plane_id}.")
            continue
        if _normalize_text(row.get("status")).lower() not in {"missing", "warning", "ready"}:
            runtime_blockers.append(f"FLAGSHIP_PRODUCT_READINESS plane {plane_id} has invalid status {_normalize_text(row.get('status'))!r}.")
        if "summary" not in row:
            runtime_blockers.append(f"FLAGSHIP_PRODUCT_READINESS plane {plane_id} is missing summary.")
        if not isinstance(row.get("reasons"), list):
            runtime_blockers.append(f"FLAGSHIP_PRODUCT_READINESS plane {plane_id} is missing reasons[].")
        if not isinstance(row.get("evidence"), dict):
            runtime_blockers.append(f"FLAGSHIP_PRODUCT_READINESS plane {plane_id} is missing evidence{{}}.")
        plane_statuses[plane_id] = _normalize_text(row.get("status"))
    return {
        "state": "pass",
        "issues": [],
        "runtime_blockers": runtime_blockers,
        "plane_statuses": plane_statuses,
    }


def _projection_monitor(plane_id: str, actual_ready: bool, expected_ready: bool, checks: Dict[str, bool], extra_blockers: List[str] | None = None) -> Dict[str, Any]:
    runtime_blockers = list(extra_blockers or [])
    if actual_ready != expected_ready:
        runtime_blockers.append(
            f"{plane_id} ready-state drifted from its direct proof: expected_ready={str(expected_ready).lower()}, actual_ready={str(actual_ready).lower()}."
        )
    return {
        "state": "pass",
        "issues": [],
        "runtime_blockers": runtime_blockers,
        "actual_ready": actual_ready,
        "expected_ready": expected_ready,
        "checks": checks,
    }


def _structural_projection(flagship_payload: Dict[str, Any]) -> Dict[str, Any]:
    plane = _plane_payload(flagship_payload, "structural_ready")
    evidence = dict(plane.get("evidence") or {})
    checks = {
        "dispatchable_truth_ready": bool(evidence.get("dispatchable_truth_ready")),
        "journey_effective_overall_state_ready": _normalize_text(evidence.get("journey_effective_overall_state")).lower() == "ready",
        "journey_overall_desktop_scoped_blocked_clear": not bool(evidence.get("journey_overall_desktop_scoped_blocked")),
        "journey_local_blocker_autofix_routing_ready": bool(evidence.get("journey_local_blocker_autofix_routing_ready")),
        "supervisor_recent_enough": bool(evidence.get("supervisor_recent_enough")),
        "runtime_healing_alert_state_healthy": _normalize_text(evidence.get("runtime_healing_alert_state")).lower() == "healthy",
    }
    return _projection_monitor("structural_ready", _is_ready(plane.get("status")), all(checks.values()), checks)


def _sr5_veteran_projection(flagship_payload: Dict[str, Any]) -> Dict[str, Any]:
    plane = _plane_payload(flagship_payload, "sr5_veteran_ready")
    evidence = dict(plane.get("evidence") or {})
    checks = {
        "registry_present": bool(evidence.get("registry_present")),
        "required_landmarks_present": int(evidence.get("required_landmark_count") or 0) > 0,
        "tasks_present": int(evidence.get("task_count") or 0) > 0,
        "visual_gate_ready": bool(evidence.get("visual_gate_ready")),
        "parity_lab_ready": bool(evidence.get("parity_lab_ready")),
        "capture_pack_present": bool(evidence.get("parity_lab_capture_pack_present", bool(_normalize_text(evidence.get("parity_lab_capture_pack_path"))))),
        "workflow_pack_present": bool(
            evidence.get("parity_lab_veteran_compare_pack_present", bool(_normalize_text(evidence.get("parity_lab_veteran_compare_pack_path"))))
        ),
        "family_targets_present": int(evidence.get("parity_lab_family_target_count") or 0) > 0,
        "invalid_targets_clear": not _normalize_list(evidence.get("parity_lab_invalid_target_family_ids")),
        "missing_flagship_families_clear": not _normalize_list(evidence.get("parity_lab_missing_flagship_family_ids")),
        "families_below_target_clear": not _normalize_list(evidence.get("parity_lab_families_below_target")),
        "capture_non_negotiables_clear": not _normalize_list(evidence.get("parity_lab_capture_missing_non_negotiable_ids")),
        "workflow_non_negotiables_clear": not _normalize_list(evidence.get("parity_lab_workflow_missing_non_negotiable_ids")),
        "whole_product_coverage_clear": not _normalize_list(evidence.get("parity_lab_missing_whole_product_coverage_keys")),
    }
    return _projection_monitor("sr5_veteran_ready", _is_ready(plane.get("status")), all(checks.values()), checks)


def _veteran_deep_projection(flagship_payload: Dict[str, Any]) -> Dict[str, Any]:
    plane = _plane_payload(flagship_payload, "veteran_deep_workflow_ready")
    evidence = dict(plane.get("evidence") or {})
    checks = {
        "desktop_client_ready": bool(evidence.get("desktop_client_ready")),
        "workflow_receipts_resolved": int(evidence.get("workflow_unresolved_receipt_count") or 0) == 0
        or bool(evidence.get("workflow_unresolved_receipts_sr4_sr6_only")),
        "families_below_veteran_approved_clear": not _normalize_list(evidence.get("families_below_veteran_approved")),
        "ui_element_parity_audit_required": bool(evidence.get("ui_element_parity_audit_required")),
        "ui_element_parity_release_blocking_ready": bool(evidence.get("ui_element_parity_audit_release_blocking_ready")),
        "ui_element_parity_gap_ids_clear": not _normalize_list(evidence.get("ui_element_parity_audit_gap_ids")),
    }
    return _projection_monitor("veteran_deep_workflow_ready", _is_ready(plane.get("status")), all(checks.values()), checks)


def _public_shelf_projection(flagship_payload: Dict[str, Any]) -> Dict[str, Any]:
    plane = _plane_payload(flagship_payload, "public_shelf_ready")
    evidence = dict(plane.get("evidence") or {})
    primary_route_ready = _is_ready(_plane_payload(flagship_payload, "primary_route_ready").get("status"))
    blockers: List[str] = []
    if bool(evidence.get("primary_route_ready")) != primary_route_ready:
        blockers.append("public_shelf_ready evidence.primary_route_ready drifted from primary_route_ready status.")
    checks = {
        "hub_and_registry_ready": bool(evidence.get("hub_and_registry_ready")),
        "primary_route_ready": primary_route_ready,
        "release_channel_freshness_ok": bool(evidence.get("release_channel_freshness_ok")),
        "missing_required_platform_head_pairs_clear": not _normalize_list(
            evidence.get("release_channel_missing_required_platform_head_pairs")
        ),
        "windows_public_installer_not_mismatched": not (
            bool(evidence.get("release_channel_has_windows_public_installer"))
            and not bool(evidence.get("ui_windows_exit_gate_raw_ready"))
        ),
    }
    return _projection_monitor("public_shelf_ready", _is_ready(plane.get("status")), all(checks.values()), checks, blockers)


def _data_durability_projection(flagship_payload: Dict[str, Any]) -> Dict[str, Any]:
    plane = _plane_payload(flagship_payload, "data_durability_ready")
    evidence = dict(plane.get("evidence") or {})
    rules_ready = _coverage_status(flagship_payload, "rules_engine_and_import") == "ready"
    blockers: List[str] = []
    if bool(evidence.get("rules_engine_and_import_ready")) != rules_ready:
        blockers.append("data_durability_ready evidence.rules_engine_and_import_ready drifted from coverage.rules_engine_and_import.")
    checks = {
        "rules_engine_and_import_ready": rules_ready,
        "install_claim_restore_continue_effective_ready": _normalize_text(
            evidence.get("install_claim_restore_continue_effective")
        ).lower()
        == "ready",
        "families_below_task_proven_clear": not _normalize_list(evidence.get("families_below_task_proven")),
        "ui_element_parity_gap_ids_clear": not _normalize_list(evidence.get("ui_element_parity_audit_gap_ids")),
    }
    return _projection_monitor("data_durability_ready", _is_ready(plane.get("status")), all(checks.values()), checks, blockers)


def _rules_explainability_projection(flagship_payload: Dict[str, Any]) -> Dict[str, Any]:
    plane = _plane_payload(flagship_payload, "rules_explainability_ready")
    evidence = dict(plane.get("evidence") or {})
    rules_detail = _coverage_evidence(flagship_payload, "rules_engine_and_import")
    rules_ready = _coverage_status(flagship_payload, "rules_engine_and_import") == "ready"
    journey_state = _normalize_text(rules_detail.get("build_explain_publish")).lower()
    journey_effective_state = _normalize_text(rules_detail.get("build_explain_publish_effective")).lower()
    local_blockers = int(rules_detail.get("build_explain_publish_local_blocking_reason_count") or 0)
    external_blockers = int(rules_detail.get("build_explain_publish_external_blocking_reason_count") or 0)
    rules_scope_blockers = int(rules_detail.get("build_explain_publish_rules_scope_blocking_reason_count") or 0)
    journey_ready = journey_effective_state == "ready" or journey_state == "ready" or (
        journey_state == "blocked" and (local_blockers + external_blockers) > 0 and rules_scope_blockers == 0
    )
    blockers: List[str] = []
    if _normalize_text(evidence.get("build_explain_publish")).lower() != journey_state:
        blockers.append("rules_explainability_ready evidence.build_explain_publish drifted from coverage_details.rules_engine_and_import.")
    if _normalize_text(evidence.get("build_explain_publish_effective")).lower() != journey_effective_state:
        blockers.append("rules_explainability_ready evidence.build_explain_publish_effective drifted from coverage_details.rules_engine_and_import.")
    if int(evidence.get("build_explain_publish_rules_scope_blocking_reason_count") or 0) != rules_scope_blockers:
        blockers.append(
            "rules_explainability_ready evidence.build_explain_publish_rules_scope_blocking_reason_count drifted from coverage_details.rules_engine_and_import."
        )
    if bool(evidence.get("rules_engine_and_import_ready")) != rules_ready:
        blockers.append("rules_explainability_ready evidence.rules_engine_and_import_ready drifted from coverage.rules_engine_and_import.")
    checks = {
        "rules_engine_and_import_ready": rules_ready,
        "build_explain_publish_ready": journey_ready,
        "rules_certification_ready": _is_passing(evidence.get("rules_certification_status")),
    }
    return _projection_monitor("rules_explainability_ready", _is_ready(plane.get("status")), all(checks.values()), checks, blockers)


def _flagship_projection(flagship_payload: Dict[str, Any]) -> Dict[str, Any]:
    plane = _plane_payload(flagship_payload, "flagship_ready")
    evidence = dict(plane.get("evidence") or {})
    blockers: List[str] = []
    plane_bool_keys = {
        "structural_ready": "structural_ready",
        "sr5_veteran_ready": "veteran_ready",
        "veteran_deep_workflow_ready": "veteran_deep_workflow_ready",
        "public_shelf_ready": "public_shelf_ready",
        "data_durability_ready": "data_durability_ready",
        "rules_explainability_ready": "rules_explainability_ready",
    }
    checks = {
        "registry_present": bool(evidence.get("registry_present")),
        "families_below_gold_ready_clear": not _normalize_list(evidence.get("families_below_gold_ready")),
        "coverage_gap_keys_clear": not _normalize_list(evidence.get("coverage_gap_keys")),
        "parity_lab_ready": bool(evidence.get("parity_lab_ready")),
        "m136_aggregate_gate_ready": bool(evidence.get("m136_aggregate_readiness_gate_ready")),
    }
    for plane_id, evidence_key in plane_bool_keys.items():
        actual_ready = _is_ready(_plane_payload(flagship_payload, plane_id).get("status"))
        if bool(evidence.get(evidence_key)) != actual_ready:
            blockers.append(f"flagship_ready evidence.{evidence_key} drifted from {plane_id} status.")
        checks[f"{plane_id}_ready"] = actual_ready
    expected_ready = all(checks.values())
    return _projection_monitor("flagship_ready", _is_ready(plane.get("status")), expected_ready, checks, blockers)


def _structural_masquerade_monitor(projection_monitors: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    runtime_blockers: List[str] = []
    structural_ready = bool(projection_monitors.get("structural_ready", {}).get("actual_ready"))
    if structural_ready:
        for plane_id in (
            "sr5_veteran_ready",
            "veteran_deep_workflow_ready",
            "public_shelf_ready",
            "data_durability_ready",
            "rules_explainability_ready",
        ):
            monitor = projection_monitors.get(plane_id, {})
            if bool(monitor.get("actual_ready")) and not bool(monitor.get("expected_ready")):
                runtime_blockers.append(
                    f"Structural green is still masquerading as {plane_id}: direct proof says non-ready while the plane is ready."
                )
    return {
        "state": "pass",
        "issues": [],
        "runtime_blockers": runtime_blockers,
        "structural_ready": structural_ready,
    }


def build_payload(
    *,
    registry_path: Path,
    fleet_queue_path: Path,
    design_queue_path: Path,
    next90_guide_path: Path,
    flagship_readiness_planes_path: Path,
    flagship_product_bar_path: Path,
    flagship_product_readiness_path: Path,
    generated_at: str | None = None,
) -> Dict[str, Any]:
    generated_at = generated_at or _utc_now()

    registry = _load_yaml(registry_path)
    fleet_queue = _load_yaml(fleet_queue_path)
    design_queue = _load_yaml(design_queue_path)
    next90_guide = _load_text(next90_guide_path)
    flagship_readiness_planes = _load_yaml(flagship_readiness_planes_path)
    flagship_product_bar = _load_text(flagship_product_bar_path)
    flagship_product_readiness = _load_json(flagship_product_readiness_path)

    milestone = _find_milestone(registry, MILESTONE_ID)
    work_task = _find_work_task(milestone, WORK_TASK_ID)
    fleet_queue_item = _find_queue_item(fleet_queue, WORK_TASK_ID)
    design_queue_item = _find_queue_item(design_queue, WORK_TASK_ID)

    guide_monitor = _marker_monitor(next90_guide, GUIDE_MARKERS, label="Next90 guide canon")
    bar_monitor = _marker_monitor(flagship_product_bar, BAR_MARKERS, label="Flagship product bar canon")
    queue_alignment = _queue_alignment(
        work_task=work_task,
        fleet_queue_item=fleet_queue_item,
        design_queue_item=design_queue_item,
    )
    planes_contract_monitor = _planes_contract_monitor(flagship_readiness_planes)
    plane_presence_monitor = _plane_presence_monitor(flagship_product_readiness)
    projection_monitors = {
        "structural_ready": _structural_projection(flagship_product_readiness),
        "sr5_veteran_ready": _sr5_veteran_projection(flagship_product_readiness),
        "veteran_deep_workflow_ready": _veteran_deep_projection(flagship_product_readiness),
        "public_shelf_ready": _public_shelf_projection(flagship_product_readiness),
        "data_durability_ready": _data_durability_projection(flagship_product_readiness),
        "rules_explainability_ready": _rules_explainability_projection(flagship_product_readiness),
        "flagship_ready": _flagship_projection(flagship_product_readiness),
    }
    structural_masquerade_monitor = _structural_masquerade_monitor(projection_monitors)

    blockers: List[str] = []
    runtime_blockers: List[str] = []
    warnings: List[str] = []
    for name, section in (
        ("next90_guide", guide_monitor),
        ("flagship_product_bar", bar_monitor),
        ("queue_alignment", queue_alignment),
        ("flagship_readiness_planes", planes_contract_monitor),
        ("plane_presence", plane_presence_monitor),
        ("structural_projection", projection_monitors["structural_ready"]),
        ("sr5_veteran_projection", projection_monitors["sr5_veteran_ready"]),
        ("veteran_deep_projection", projection_monitors["veteran_deep_workflow_ready"]),
        ("public_shelf_projection", projection_monitors["public_shelf_ready"]),
        ("data_durability_projection", projection_monitors["data_durability_ready"]),
        ("rules_explainability_projection", projection_monitors["rules_explainability_ready"]),
        ("flagship_projection", projection_monitors["flagship_ready"]),
        ("structural_masquerade", structural_masquerade_monitor),
    ):
        blockers.extend(f"{name}: {issue}" for issue in section.get("issues") or [])
        runtime_blockers.extend(f"{name}: {issue}" for issue in section.get("runtime_blockers") or [])
        warnings.extend(section.get("warnings") or [])

    blocked_plane_ids = [
        plane_id
        for plane_id, monitor in projection_monitors.items()
        if not bool(monitor.get("expected_ready"))
    ]
    derivation_status = "blocked" if runtime_blockers else "warning" if warnings else "pass"
    return {
        "contract_name": "fleet.next90_m136_derived_release_health_planes",
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
            "flagship_product_bar": bar_monitor,
            "queue_alignment": queue_alignment,
            "flagship_readiness_planes": planes_contract_monitor,
        },
        "runtime_monitors": {
            "plane_presence": plane_presence_monitor,
            "structural_projection": projection_monitors["structural_ready"],
            "sr5_veteran_projection": projection_monitors["sr5_veteran_ready"],
            "veteran_deep_projection": projection_monitors["veteran_deep_workflow_ready"],
            "public_shelf_projection": projection_monitors["public_shelf_ready"],
            "data_durability_projection": projection_monitors["data_durability_ready"],
            "rules_explainability_projection": projection_monitors["rules_explainability_ready"],
            "flagship_projection": projection_monitors["flagship_ready"],
            "structural_masquerade": structural_masquerade_monitor,
        },
        "monitor_summary": {
            "derivation_status": derivation_status,
            "required_plane_count": len(REQUIRED_PLANE_IDS),
            "runtime_blocker_count": len(runtime_blockers),
            "warning_count": len(warnings),
            "blocked_plane_ids": blocked_plane_ids,
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
            "flagship_readiness_planes": _source_link(flagship_readiness_planes_path, flagship_readiness_planes),
            "flagship_product_bar": _text_source_link(flagship_product_bar_path),
            "flagship_product_readiness": _source_link(flagship_product_readiness_path, flagship_product_readiness),
        },
    }


def render_markdown(payload: Dict[str, Any]) -> str:
    summary = dict(payload.get("monitor_summary") or {})
    closeout = dict(payload.get("package_closeout") or {})
    lines = [
        "# Fleet M136 derived release-health planes",
        "",
        f"- status: {payload.get('status')}",
        f"- derivation_status: {summary.get('derivation_status')}",
        f"- package_id: {payload.get('package_id')}",
        f"- frontier_id: {payload.get('frontier_id')}",
        f"- generated_at: {payload.get('generated_at')}",
        "",
        "## Runtime summary",
        f"- required_plane_count: {summary.get('required_plane_count')}",
        f"- runtime_blocker_count: {summary.get('runtime_blocker_count')}",
        f"- warning_count: {summary.get('warning_count')}",
        f"- blocked_plane_ids: {', '.join(summary.get('blocked_plane_ids') or []) or '(none)'}",
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
        flagship_readiness_planes_path=Path(args.flagship_readiness_planes).resolve(),
        flagship_product_bar_path=Path(args.flagship_product_bar).resolve(),
        flagship_product_readiness_path=Path(args.flagship_product_readiness).resolve(),
    )
    _write_json_file(output_path, payload)
    _write_markdown_file(markdown_path, render_markdown(payload))
    print(json.dumps({"status": payload["status"], "artifact": str(output_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
