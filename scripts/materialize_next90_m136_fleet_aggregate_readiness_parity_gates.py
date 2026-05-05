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
PRESENTATION_ROOT = Path("/docker/chummercomplete/chummer-presentation/.codex-studio/published")

PACKAGE_ID = "next90-m136-fleet-fail-closed-on-aggregate-readiness-when-family-level-parity-proof-sub"
FRONTIER_ID = 2277811964
MILESTONE_ID = 136
WORK_TASK_ID = "136.6"
WAVE_ID = "W23"
QUEUE_TITLE = (
    "Fail closed on aggregate readiness when family-level parity proof, sub-dialog screenshot packs, "
    "dialog-level element inventories, or continuity journey receipts are stale or missing."
)
OWNED_SURFACES = ["fail_closed_on_aggregate_readiness_when_family_level_par:fleet"]
ALLOWED_PATHS = ["scripts", "tests", ".codex-studio", "feedback"]

DEFAULT_OUTPUT = PUBLISHED / "NEXT90_M136_FLEET_AGGREGATE_READINESS_PARITY_GATES.generated.json"
DEFAULT_MARKDOWN = PUBLISHED / "NEXT90_M136_FLEET_AGGREGATE_READINESS_PARITY_GATES.generated.md"

SUCCESSOR_REGISTRY = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
FLEET_QUEUE_STAGING = PUBLISHED / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
DESIGN_QUEUE_STAGING = PRODUCT_MIRROR / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
NEXT90_GUIDE = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_GUIDE.md"
PARITY_MATRIX = PRODUCT_MIRROR / "CHUMMER5A_HUMAN_PARITY_ACCEPTANCE_MATRIX.yaml"
FLAGSHIP_PRODUCT_READINESS = PUBLISHED / "FLAGSHIP_PRODUCT_READINESS.generated.json"
CAMPAIGN_CONTINUITY_LIVENESS = PUBLISHED / "CAMPAIGN_OS_CONTINUITY_LIVENESS.generated.json"
JOURNEY_GATES = PUBLISHED / "JOURNEY_GATES.generated.json"
PARITY_AUDIT = PRESENTATION_ROOT / "CHUMMER5A_UI_ELEMENT_PARITY_AUDIT.generated.json"
SCREENSHOT_REVIEW_GATE = PRESENTATION_ROOT / "CHUMMER5A_SCREENSHOT_REVIEW_GATE.generated.json"
VISUAL_FAMILIARITY_GATE = PRESENTATION_ROOT / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"

DONE_STATUSES = {"complete", "completed", "done", "landed", "shipped"}
GUIDE_MARKERS = {
    "wave_23": "## Wave 23 - close calm-under-pressure payoff and veteran continuity",
    "milestone_136": "### 136. Calm-under-pressure payoff, veteran-depth parity, and campaign continuity closure",
    "exit_contract": "Exit: the product proves the calm-under-pressure loop, reaches zero `no` rows in the Chummer5A human-parity matrix, closes the hard veteran parity families, closes split-brain release truth, and publishes dependable companion continuity rather than broad structural green.",
}
REQUIRED_MATRIX_FAMILY_IDS = [
    "translator_xml_bridge",
    "dense_builder_and_career",
    "dice_initiative_and_table_utilities",
    "identity_contacts_lifestyles_history",
    "legacy_and_adjacent_import_oracles",
    "sheet_export_print_viewer_exchange",
    "sr6_supplements_designers_house_rules",
]
MATRIX_TO_AUDIT_FAMILY_IDS = {
    "translator_xml_bridge": "family:custom_data_xml_and_translator_bridge",
    "dense_builder_and_career": "family:dense_builder_and_career_workflows",
    "dice_initiative_and_table_utilities": "family:dice_initiative_and_table_utilities",
    "identity_contacts_lifestyles_history": "family:identity_contacts_lifestyles_history",
    "legacy_and_adjacent_import_oracles": "family:legacy_and_adjacent_import_oracles",
    "sheet_export_print_viewer_exchange": "family:sheet_export_print_viewer_and_exchange",
    "sr6_supplements_designers_house_rules": "family:sr6_supplements_designers_and_house_rules",
}
PARITY_AUDIT_MAX_AGE_HOURS = 72
SCREENSHOT_GATE_MAX_AGE_HOURS = 72
CONTINUITY_MAX_AGE_HOURS = 48
FLAGSHIP_READINESS_MAX_AGE_HOURS = 48


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize the Fleet M136 aggregate-readiness parity gate packet.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--markdown-output", default=str(DEFAULT_MARKDOWN))
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--fleet-queue-staging", default=str(FLEET_QUEUE_STAGING))
    parser.add_argument("--design-queue-staging", default=str(DESIGN_QUEUE_STAGING))
    parser.add_argument("--next90-guide", default=str(NEXT90_GUIDE))
    parser.add_argument("--parity-matrix", default=str(PARITY_MATRIX))
    parser.add_argument("--flagship-product-readiness", default=str(FLAGSHIP_PRODUCT_READINESS))
    parser.add_argument("--campaign-continuity-liveness", default=str(CAMPAIGN_CONTINUITY_LIVENESS))
    parser.add_argument("--journey-gates", default=str(JOURNEY_GATES))
    parser.add_argument("--parity-audit", default=str(PARITY_AUDIT))
    parser.add_argument("--screenshot-review-gate", default=str(SCREENSHOT_REVIEW_GATE))
    parser.add_argument("--visual-familiarity-gate", default=str(VISUAL_FAMILIARITY_GATE))
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
        "generated_at": _normalize_text(payload.get("generated_at") or payload.get("generatedAt")),
    }


def _text_source_link(path: Path) -> Dict[str, Any]:
    return {"path": _display_path(path), "sha256": _sha256_file(path), "generated_at": ""}


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


def _is_pass_status(value: Any) -> bool:
    return _normalize_text(value).lower() in {"pass", "passed", "ready", "published", "ok"}


def _marker_monitor(text: str, markers: Dict[str, str], *, label: str) -> Dict[str, Any]:
    checks = {name: marker in text for name, marker in markers.items()}
    issues = [f"{label} missing required marker: {name}" for name, present in checks.items() if not present]
    return {"state": "pass" if not issues else "fail", "checks": checks, "issues": issues}


def _queue_alignment(
    *,
    milestone: Dict[str, Any],
    work_task: Dict[str, Any],
    fleet_queue_item: Dict[str, Any],
    design_queue_item: Dict[str, Any],
) -> Dict[str, Any]:
    issues: List[str] = []
    runtime_blockers: List[str] = []
    warnings: List[str] = []
    if not work_task:
        issues.append("Canonical registry work task is missing.")
    if not design_queue_item:
        issues.append("Design queue row is missing.")
    if not fleet_queue_item:
        warnings.append("Fleet queue mirror row is still missing for work task 136.6.")

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
    if milestone and [int(value) for value in milestone.get("dependencies") or []] != [113, 114, 123, 124, 133, 134, 135, 141, 142, 143, 144]:
        issues.append("Canonical registry milestone dependencies drifted from M136 requirement set.")

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
        "runtime_blockers": runtime_blockers,
        "warnings": warnings,
        "fleet_queue_status": _normalize_text(fleet_queue_item.get("status")),
        "design_queue_status": _normalize_text(design_queue_item.get("status")),
        "work_task_status": _normalize_text(work_task.get("status")),
    }


def _parity_matrix_monitor(matrix: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    rows = [dict(row) for row in (matrix.get("families") or []) if isinstance(row, dict)]
    by_id = {_normalize_text(row.get("id")): row for row in rows if _normalize_text(row.get("id"))}
    for family_id in REQUIRED_MATRIX_FAMILY_IDS:
        row = by_id.get(family_id)
        if not row:
            issues.append(f"Parity acceptance matrix is missing release-blocking family {family_id}.")
            continue
        if row.get("release_blocking") is not True:
            issues.append(f"Parity acceptance matrix family {family_id} must remain release_blocking=true.")
        if not _normalize_list(row.get("required_screenshots")):
            issues.append(f"Parity acceptance matrix family {family_id} is missing required_screenshots.")
        surfaces = [dict(item) for item in (row.get("surfaces") or []) if isinstance(item, dict)]
        if not surfaces:
            issues.append(f"Parity acceptance matrix family {family_id} is missing dialog-level surfaces.")
            continue
        for surface in surfaces:
            surface_id = _normalize_text(surface.get("id")) or "unknown_surface"
            if not _normalize_list(surface.get("must_remain_first_class")):
                issues.append(
                    f"Parity acceptance matrix family {family_id} surface {surface_id} is missing must_remain_first_class entries."
                )
    return {
        "state": "pass" if not issues else "fail",
        "issues": issues,
        "family_count": len(rows),
        "required_family_ids": REQUIRED_MATRIX_FAMILY_IDS,
    }


def _parity_family_monitor(matrix: Dict[str, Any], parity_audit: Dict[str, Any], *, now: dt.datetime) -> Dict[str, Any]:
    issues: List[str] = []
    runtime_blockers: List[str] = []
    warnings: List[str] = []
    elements = [dict(row) for row in (parity_audit.get("elements") or []) if isinstance(row, dict)]
    rows_by_id = {_normalize_text(row.get("id")): row for row in elements if _normalize_text(row.get("id"))}
    generated_at = _normalize_text(parity_audit.get("generated_at") or parity_audit.get("generatedAt"))
    age_hours = _age_hours(generated_at, now=now)
    if not parity_audit:
        runtime_blockers.append("Chummer5A UI element parity audit is missing.")
    elif age_hours is None:
        runtime_blockers.append("Chummer5A UI element parity audit generated_at is missing or invalid.")
    elif age_hours > PARITY_AUDIT_MAX_AGE_HOURS:
        runtime_blockers.append(
            f"Chummer5A UI element parity audit is stale ({age_hours}h > {PARITY_AUDIT_MAX_AGE_HOURS}h)."
        )

    summary = dict(parity_audit.get("summary") or {})
    visual_no_count = int(summary.get("visual_no_count") or 0)
    behavioral_no_count = int(summary.get("behavioral_no_count") or 0)
    if visual_no_count > 0 or behavioral_no_count > 0:
        runtime_blockers.append(
            "Parity audit still reports unresolved no-counts: "
            f"visual_no_count={visual_no_count}, behavioral_no_count={behavioral_no_count}."
        )

    missing_family_proofs: List[str] = []
    unresolved_family_proofs: List[str] = []
    for family_id in REQUIRED_MATRIX_FAMILY_IDS:
        audit_id = MATRIX_TO_AUDIT_FAMILY_IDS[family_id]
        row = rows_by_id.get(audit_id)
        if not row:
            missing_family_proofs.append(family_id)
            continue
        visual = _normalize_text(row.get("visual_parity")).lower()
        behavioral = _normalize_text(row.get("behavioral_parity")).lower()
        if visual != "yes" or behavioral != "yes":
            unresolved_family_proofs.append(family_id)

    if missing_family_proofs:
        runtime_blockers.append(
            "Release-blocking family parity proof is missing for: " + ", ".join(missing_family_proofs) + "."
        )
    if unresolved_family_proofs:
        runtime_blockers.append(
            "Release-blocking family parity proof is unresolved for: " + ", ".join(unresolved_family_proofs) + "."
        )

    return {
        "state": "pass" if not issues else "fail",
        "generated_at": generated_at,
        "age_hours": age_hours,
        "element_count": len(elements),
        "visual_no_count": visual_no_count,
        "behavioral_no_count": behavioral_no_count,
        "missing_family_proofs": missing_family_proofs,
        "unresolved_family_proofs": unresolved_family_proofs,
        "runtime_blockers": runtime_blockers,
        "warnings": warnings,
        "issues": issues,
    }


def _single_artifact_gate_monitor(
    payload: Dict[str, Any],
    *,
    label: str,
    max_age_hours: int,
    now: dt.datetime,
) -> Dict[str, Any]:
    runtime_blockers: List[str] = []
    generated_at = _normalize_text(payload.get("generated_at") or payload.get("generatedAt"))
    age_hours = _age_hours(generated_at, now=now)
    if not payload:
        runtime_blockers.append(f"{label} is missing.")
    elif not _is_pass_status(payload.get("status")):
        runtime_blockers.append(f"{label} is not passing.")
    if payload:
        if age_hours is None:
            runtime_blockers.append(f"{label} generated_at is missing or invalid.")
        elif age_hours > max_age_hours:
            runtime_blockers.append(f"{label} is stale ({age_hours}h > {max_age_hours}h).")
    return {
        "generated_at": generated_at,
        "age_hours": age_hours,
        "status": _normalize_text(payload.get("status")),
        "runtime_blockers": runtime_blockers,
    }


def _screenshot_pack_monitor(
    screenshot_review_gate: Dict[str, Any],
    visual_familiarity_gate: Dict[str, Any],
    *,
    now: dt.datetime,
) -> Dict[str, Any]:
    issues: List[str] = []
    runtime_blockers: List[str] = []
    screenshot_review = _single_artifact_gate_monitor(
        screenshot_review_gate,
        label="Sub-dialog screenshot review gate",
        max_age_hours=SCREENSHOT_GATE_MAX_AGE_HOURS,
        now=now,
    )
    visual_familiarity = _single_artifact_gate_monitor(
        visual_familiarity_gate,
        label="Desktop visual familiarity gate",
        max_age_hours=SCREENSHOT_GATE_MAX_AGE_HOURS,
        now=now,
    )
    runtime_blockers.extend(screenshot_review["runtime_blockers"])
    runtime_blockers.extend(visual_familiarity["runtime_blockers"])
    return {
        "state": "pass" if not issues else "fail",
        "screenshot_review_gate": screenshot_review,
        "visual_familiarity_gate": visual_familiarity,
        "runtime_blockers": runtime_blockers,
        "warnings": [],
        "issues": issues,
    }


def _continuity_monitor(
    continuity_liveness: Dict[str, Any],
    journey_gates: Dict[str, Any],
    *,
    now: dt.datetime,
) -> Dict[str, Any]:
    issues: List[str] = []
    runtime_blockers: List[str] = []
    continuity_generated_at = _normalize_text(
        continuity_liveness.get("generated_at") or continuity_liveness.get("generatedAt")
    )
    continuity_age_hours = _age_hours(continuity_generated_at, now=now)
    if not continuity_liveness:
        runtime_blockers.append("Campaign continuity liveness artifact is missing.")
    else:
        if not _is_pass_status(continuity_liveness.get("status")):
            runtime_blockers.append("Campaign continuity liveness is not passing.")
        if continuity_age_hours is None:
            runtime_blockers.append("Campaign continuity liveness generated_at is missing or invalid.")
        elif continuity_age_hours > CONTINUITY_MAX_AGE_HOURS:
            runtime_blockers.append(
                f"Campaign continuity liveness is stale ({continuity_age_hours}h > {CONTINUITY_MAX_AGE_HOURS}h)."
            )

    journey_generated_at = _normalize_text(journey_gates.get("generated_at") or journey_gates.get("generatedAt"))
    journey_age_hours = _age_hours(journey_generated_at, now=now)
    journey_summary = dict(journey_gates.get("summary") or {})
    if not journey_gates:
        runtime_blockers.append("Journey gates artifact is missing.")
    else:
        if _normalize_text(journey_summary.get("overall_state")).lower() != "ready":
            runtime_blockers.append("Journey gates do not currently report overall_state=ready.")
        if journey_age_hours is None:
            runtime_blockers.append("Journey gates generated_at is missing or invalid.")
        elif journey_age_hours > CONTINUITY_MAX_AGE_HOURS:
            runtime_blockers.append(
                f"Journey gates are stale ({journey_age_hours}h > {CONTINUITY_MAX_AGE_HOURS}h)."
            )

    return {
        "state": "pass" if not issues else "fail",
        "continuity_status": _normalize_text(continuity_liveness.get("status")),
        "continuity_generated_at": continuity_generated_at,
        "continuity_age_hours": continuity_age_hours,
        "journey_overall_state": _normalize_text(journey_summary.get("overall_state")),
        "journey_generated_at": journey_generated_at,
        "journey_age_hours": journey_age_hours,
        "runtime_blockers": runtime_blockers,
        "warnings": [],
        "issues": issues,
    }


def _aggregate_readiness_monitor(
    flagship_readiness: Dict[str, Any],
    *,
    direct_runtime_blockers: List[str],
    now: dt.datetime,
) -> Dict[str, Any]:
    issues: List[str] = []
    runtime_blockers: List[str] = []
    generated_at = _normalize_text(flagship_readiness.get("generated_at") or flagship_readiness.get("generatedAt"))
    age_hours = _age_hours(generated_at, now=now)
    readiness_status = _normalize_text(flagship_readiness.get("status"))
    if not flagship_readiness:
        runtime_blockers.append("Flagship product readiness artifact is missing.")
    else:
        if age_hours is None:
            runtime_blockers.append("Flagship product readiness generated_at is missing or invalid.")
        elif age_hours > FLAGSHIP_READINESS_MAX_AGE_HOURS:
            runtime_blockers.append(
                f"Flagship product readiness is stale ({age_hours}h > {FLAGSHIP_READINESS_MAX_AGE_HOURS}h)."
            )
        if _is_pass_status(readiness_status) and direct_runtime_blockers:
            runtime_blockers.append(
                "Flagship product readiness is still green while direct parity or continuity proof is blocked."
            )
    return {
        "state": "pass" if not issues else "fail",
        "generated_at": generated_at,
        "age_hours": age_hours,
        "status": readiness_status,
        "runtime_blockers": runtime_blockers,
        "warnings": [],
        "issues": issues,
    }


def build_payload(
    *,
    registry_path: Path,
    fleet_queue_path: Path,
    design_queue_path: Path,
    next90_guide_path: Path,
    parity_matrix_path: Path,
    flagship_product_readiness_path: Path,
    campaign_continuity_liveness_path: Path,
    journey_gates_path: Path,
    parity_audit_path: Path,
    screenshot_review_gate_path: Path,
    visual_familiarity_gate_path: Path,
    generated_at: str | None = None,
) -> Dict[str, Any]:
    generated_at = generated_at or _utc_now()
    now = _parse_iso_utc(generated_at) or dt.datetime.now(dt.timezone.utc)

    registry = _load_yaml(registry_path)
    fleet_queue = _load_yaml(fleet_queue_path)
    design_queue = _load_yaml(design_queue_path)
    next90_guide = _load_text(next90_guide_path)
    parity_matrix = _load_yaml(parity_matrix_path)
    flagship_readiness = _load_json(flagship_product_readiness_path)
    continuity_liveness = _load_json(campaign_continuity_liveness_path)
    journey_gates = _load_json(journey_gates_path)
    parity_audit = _load_json(parity_audit_path)
    screenshot_review_gate = _load_json(screenshot_review_gate_path)
    visual_familiarity_gate = _load_json(visual_familiarity_gate_path)

    milestone = _find_milestone(registry, MILESTONE_ID)
    work_task = _find_work_task(milestone, WORK_TASK_ID)
    fleet_queue_item = _find_queue_item(fleet_queue, WORK_TASK_ID)
    design_queue_item = _find_queue_item(design_queue, WORK_TASK_ID)

    guide_monitor = _marker_monitor(next90_guide, GUIDE_MARKERS, label="Next90 guide canon")
    queue_alignment = _queue_alignment(
        milestone=milestone,
        work_task=work_task,
        fleet_queue_item=fleet_queue_item,
        design_queue_item=design_queue_item,
    )
    parity_matrix_monitor = _parity_matrix_monitor(parity_matrix)
    parity_family_monitor = _parity_family_monitor(parity_matrix, parity_audit, now=now)
    screenshot_pack_monitor = _screenshot_pack_monitor(
        screenshot_review_gate,
        visual_familiarity_gate,
        now=now,
    )
    continuity_monitor = _continuity_monitor(
        continuity_liveness,
        journey_gates,
        now=now,
    )

    direct_runtime_blockers: List[str] = []
    for section in (queue_alignment, parity_family_monitor, screenshot_pack_monitor, continuity_monitor):
        direct_runtime_blockers.extend(section.get("runtime_blockers") or [])
    aggregate_readiness_monitor = _aggregate_readiness_monitor(
        flagship_readiness,
        direct_runtime_blockers=direct_runtime_blockers,
        now=now,
    )

    blockers: List[str] = []
    runtime_blockers: List[str] = []
    warnings: List[str] = []
    for name, section in (
        ("next90_guide", guide_monitor),
        ("queue_alignment", queue_alignment),
        ("parity_matrix", parity_matrix_monitor),
        ("parity_family_monitor", parity_family_monitor),
        ("screenshot_pack_monitor", screenshot_pack_monitor),
        ("continuity_monitor", continuity_monitor),
        ("aggregate_readiness_monitor", aggregate_readiness_monitor),
    ):
        blockers.extend(f"{name}: {issue}" for issue in section.get("issues") or [])
        runtime_blockers.extend(f"{name}: {issue}" for issue in section.get("runtime_blockers") or [])
        warnings.extend(section.get("warnings") or [])

    aggregate_readiness_status = "blocked" if runtime_blockers else "warning" if warnings else "pass"
    return {
        "contract_name": "fleet.next90_m136_aggregate_readiness_parity_gates",
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
            "parity_matrix": parity_matrix_monitor,
        },
        "runtime_monitors": {
            "parity_family_proof": parity_family_monitor,
            "screenshot_packs": screenshot_pack_monitor,
            "continuity_receipts": continuity_monitor,
            "aggregate_readiness": aggregate_readiness_monitor,
        },
        "monitor_summary": {
            "aggregate_readiness_status": aggregate_readiness_status,
            "required_family_count": len(REQUIRED_MATRIX_FAMILY_IDS),
            "receipt_runtime_blocker_count": len(runtime_blockers),
            "warning_count": len(warnings),
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
            "parity_matrix": _source_link(parity_matrix_path, parity_matrix),
            "flagship_product_readiness": _source_link(flagship_product_readiness_path, flagship_readiness),
            "campaign_continuity_liveness": _source_link(campaign_continuity_liveness_path, continuity_liveness),
            "journey_gates": _source_link(journey_gates_path, journey_gates),
            "parity_audit": _source_link(parity_audit_path, parity_audit),
            "screenshot_review_gate": _source_link(screenshot_review_gate_path, screenshot_review_gate),
            "visual_familiarity_gate": _source_link(visual_familiarity_gate_path, visual_familiarity_gate),
        },
    }


def render_markdown(payload: Dict[str, Any]) -> str:
    summary = dict(payload.get("monitor_summary") or {})
    closeout = dict(payload.get("package_closeout") or {})
    lines = [
        "# Fleet M136 aggregate-readiness parity gates",
        "",
        f"- status: {payload.get('status')}",
        f"- aggregate_readiness_status: {summary.get('aggregate_readiness_status')}",
        f"- package_id: {payload.get('package_id')}",
        f"- frontier_id: {payload.get('frontier_id')}",
        f"- generated_at: {payload.get('generated_at')}",
        "",
        "## Runtime summary",
        f"- required_family_count: {summary.get('required_family_count')}",
        f"- receipt_runtime_blocker_count: {summary.get('receipt_runtime_blocker_count')}",
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
        parity_matrix_path=Path(args.parity_matrix).resolve(),
        flagship_product_readiness_path=Path(args.flagship_product_readiness).resolve(),
        campaign_continuity_liveness_path=Path(args.campaign_continuity_liveness).resolve(),
        journey_gates_path=Path(args.journey_gates).resolve(),
        parity_audit_path=Path(args.parity_audit).resolve(),
        screenshot_review_gate_path=Path(args.screenshot_review_gate).resolve(),
        visual_familiarity_gate_path=Path(args.visual_familiarity_gate).resolve(),
    )
    _write_json_file(output_path, payload)
    _write_markdown_file(markdown_path, render_markdown(payload))
    print(json.dumps({"status": payload["status"], "artifact": str(output_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
