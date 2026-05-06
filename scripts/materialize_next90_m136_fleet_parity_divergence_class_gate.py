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

PACKAGE_ID = "next90-m136-fleet-fail-parity-closeout-when-remaining-deltas-are-not-classified-as-must"
FRONTIER_ID = 2977536653
MILESTONE_ID = 136
WORK_TASK_ID = "136.16"
WAVE_ID = "W23"
QUEUE_TITLE = "Fail parity closeout when remaining deltas are not classified as must-match, may-improve, or may-remove-if-non-degrading in the audit artifacts."
OWNED_SURFACES = ["fail_parity_closeout_when_remaining_deltas_are_not_class:fleet"]
ALLOWED_PATHS = ["scripts", "tests", ".codex-studio", "feedback"]

DEFAULT_OUTPUT = PUBLISHED / "NEXT90_M136_FLEET_PARITY_DIVERGENCE_CLASS_GATE.generated.json"
DEFAULT_MARKDOWN = PUBLISHED / "NEXT90_M136_FLEET_PARITY_DIVERGENCE_CLASS_GATE.generated.md"

SUCCESSOR_REGISTRY = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
FLEET_QUEUE_STAGING = PUBLISHED / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
DESIGN_QUEUE_STAGING = PRODUCT_MIRROR / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
NEXT90_GUIDE = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_GUIDE.md"
FLAGSHIP_READINESS_PLANES = PRODUCT_MIRROR / "FLAGSHIP_READINESS_PLANES.yaml"
FLAGSHIP_PRODUCT_BAR = PRODUCT_MIRROR / "FLAGSHIP_PRODUCT_BAR.md"
FLAGSHIP_RELEASE_ACCEPTANCE = PRODUCT_MIRROR / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
PARITY_SPEC = PRODUCT_MIRROR / "CHUMMER5A_HUMAN_PARITY_ACCEPTANCE_SPEC.md"
PARITY_AUDIT = PRESENTATION_ROOT / "CHUMMER5A_UI_ELEMENT_PARITY_AUDIT.generated.json"

GUIDE_MARKERS = {
    "wave_23": "## Wave 23 - close calm-under-pressure payoff and veteran continuity",
    "milestone_136": "### 136. Calm-under-pressure payoff, veteran-depth parity, and campaign continuity closure",
}
BAR_MARKERS = {
    "release_proof_classifies_intentional_divergence": "Release proof must also classify intentional divergence explicitly:",
    "must_match": "* `must_match`",
    "may_improve": "* `may_improve`",
    "may_remove_if_non_degrading": "* `may_remove_if_non_degrading`",
}
SPEC_MARKERS = {
    "may_improve": "Allowed modernization maps to the divergence class `may_improve`.",
    "must_match": "it is a `must_match` failure until the replacement route proves equal or better directness, speed, and trust.",
    "may_remove_if_non_degrading": "This is the divergence class `may_remove_if_non_degrading`.",
}
ACCEPTANCE_MARKER = "Parity doctrine must classify remaining differences as `must_match`, `may_improve`, or `may_remove_if_non_degrading`; unclassified drift does not count as flagship-ready modernization."
CLASSIFICATION_FIELDS = ("divergence_class", "divergence_classification")


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize the Fleet M136 parity divergence-class gate packet.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--markdown-output", default=str(DEFAULT_MARKDOWN))
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--fleet-queue-staging", default=str(FLEET_QUEUE_STAGING))
    parser.add_argument("--design-queue-staging", default=str(DESIGN_QUEUE_STAGING))
    parser.add_argument("--next90-guide", default=str(NEXT90_GUIDE))
    parser.add_argument("--flagship-readiness-planes", default=str(FLAGSHIP_READINESS_PLANES))
    parser.add_argument("--flagship-product-bar", default=str(FLAGSHIP_PRODUCT_BAR))
    parser.add_argument("--flagship-release-acceptance", default=str(FLAGSHIP_RELEASE_ACCEPTANCE))
    parser.add_argument("--parity-spec", default=str(PARITY_SPEC))
    parser.add_argument("--parity-audit", default=str(PARITY_AUDIT))
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
        warnings.append("Fleet queue mirror row is still missing for work task 136.16.")
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


def _divergence_contract_monitor(planes_payload: Dict[str, Any], acceptance_payload: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    policy = dict(planes_payload.get("policy") or {})
    divergence_rows = [dict(row) for row in (policy.get("divergence_classes") or []) if isinstance(row, dict)]
    divergence_ids = [_normalize_text(row.get("id")) for row in divergence_rows if _normalize_text(row.get("id"))]
    if divergence_ids != ["must_match", "may_improve", "may_remove_if_non_degrading"]:
        issues.append("FLAGSHIP_READINESS_PLANES divergence_classes drifted from the must_match/may_improve/may_remove_if_non_degrading contract.")
    whole_product_rules = _normalize_list(acceptance_payload.get("whole_product_release_rules"))
    if ACCEPTANCE_MARKER not in whole_product_rules:
        issues.append("FLAGSHIP_RELEASE_ACCEPTANCE no longer compiles the divergence-class closeout doctrine.")
    return {
        "state": "pass" if not issues else "fail",
        "issues": issues,
        "allowed_divergence_classes": divergence_ids,
    }


def _delta_rows_monitor(parity_audit: Dict[str, Any]) -> Dict[str, Any]:
    runtime_blockers: List[str] = []
    rows = [dict(row) for row in (parity_audit.get("elements") or []) if isinstance(row, dict)]
    delta_rows: List[Dict[str, Any]] = []
    for row in rows:
        if (
            _normalize_text(row.get("visual_parity")).lower() != "yes"
            or _normalize_text(row.get("behavioral_parity")).lower() != "yes"
            or _normalize_text(row.get("present_in_chummer5a")).lower() == "no"
            or _normalize_text(row.get("removable_without_workflow_degradation")).lower() == "yes"
        ):
            delta_rows.append(row)
    if not parity_audit:
        runtime_blockers.append("Chummer5A UI element parity audit is missing.")
    return {
        "state": "pass",
        "issues": [],
        "runtime_blockers": runtime_blockers,
        "delta_rows": [
            {
                "id": _normalize_text(row.get("id")),
                "visual_parity": _normalize_text(row.get("visual_parity")),
                "behavioral_parity": _normalize_text(row.get("behavioral_parity")),
                "present_in_chummer5a": _normalize_text(row.get("present_in_chummer5a")),
                "removable_without_workflow_degradation": _normalize_text(row.get("removable_without_workflow_degradation")),
                "divergence_class": _normalize_text(row.get("divergence_class")),
                "divergence_classification": _normalize_text(row.get("divergence_classification")),
            }
            for row in delta_rows
        ],
    }


def _classification_monitor(delta_rows: List[Dict[str, Any]], allowed_classes: List[str]) -> Dict[str, Any]:
    runtime_blockers: List[str] = []
    classified_delta_ids: List[str] = []
    unclassified_delta_ids: List[str] = []
    invalid_classifications: List[str] = []
    for row in delta_rows:
        delta_id = _normalize_text(row.get("id"))
        classification = ""
        for field in CLASSIFICATION_FIELDS:
            classification = _normalize_text(row.get(field))
            if classification:
                break
        if not classification:
            unclassified_delta_ids.append(delta_id)
            continue
        if classification not in allowed_classes:
            invalid_classifications.append(f"{delta_id}:{classification}")
            continue
        classified_delta_ids.append(delta_id)
    if unclassified_delta_ids:
        runtime_blockers.append(
            "Parity audit delta rows are still missing a machine-readable divergence class: " + ", ".join(unclassified_delta_ids) + "."
        )
    if invalid_classifications:
        runtime_blockers.append(
            "Parity audit delta rows use invalid divergence classes: " + ", ".join(invalid_classifications) + "."
        )
    return {
        "state": "pass",
        "issues": [],
        "runtime_blockers": runtime_blockers,
        "classified_delta_ids": classified_delta_ids,
        "unclassified_delta_ids": unclassified_delta_ids,
        "invalid_classifications": invalid_classifications,
    }


def build_payload(
    *,
    registry_path: Path,
    fleet_queue_path: Path,
    design_queue_path: Path,
    next90_guide_path: Path,
    flagship_readiness_planes_path: Path,
    flagship_product_bar_path: Path,
    flagship_release_acceptance_path: Path,
    parity_spec_path: Path,
    parity_audit_path: Path,
    generated_at: str | None = None,
) -> Dict[str, Any]:
    generated_at = generated_at or _utc_now()
    registry = _load_yaml(registry_path)
    fleet_queue = _load_yaml(fleet_queue_path)
    design_queue = _load_yaml(design_queue_path)
    next90_guide = _load_text(next90_guide_path)
    flagship_readiness_planes = _load_yaml(flagship_readiness_planes_path)
    flagship_product_bar = _load_text(flagship_product_bar_path)
    flagship_release_acceptance = _load_yaml(flagship_release_acceptance_path)
    parity_spec = _load_text(parity_spec_path)
    parity_audit = _load_json(parity_audit_path)

    milestone = _find_milestone(registry, MILESTONE_ID)
    work_task = _find_work_task(milestone, WORK_TASK_ID)
    fleet_queue_item = _find_queue_item(fleet_queue, WORK_TASK_ID)
    design_queue_item = _find_queue_item(design_queue, WORK_TASK_ID)

    guide_monitor = _marker_monitor(next90_guide, GUIDE_MARKERS, label="Next90 guide canon")
    bar_monitor = _marker_monitor(flagship_product_bar, BAR_MARKERS, label="Flagship product bar canon")
    spec_monitor = _marker_monitor(parity_spec, SPEC_MARKERS, label="Human parity acceptance spec")
    queue_alignment = _queue_alignment(
        work_task=work_task,
        fleet_queue_item=fleet_queue_item,
        design_queue_item=design_queue_item,
    )
    divergence_contract_monitor = _divergence_contract_monitor(flagship_readiness_planes, flagship_release_acceptance)
    delta_rows_monitor = _delta_rows_monitor(parity_audit)
    classification_monitor = _classification_monitor(
        delta_rows_monitor.get("delta_rows") or [],
        divergence_contract_monitor.get("allowed_divergence_classes") or [],
    )

    blockers: List[str] = []
    runtime_blockers: List[str] = []
    warnings: List[str] = []
    for name, section in (
        ("next90_guide", guide_monitor),
        ("flagship_product_bar", bar_monitor),
        ("parity_spec", spec_monitor),
        ("queue_alignment", queue_alignment),
        ("divergence_contract", divergence_contract_monitor),
        ("delta_rows", delta_rows_monitor),
        ("classification", classification_monitor),
    ):
        blockers.extend(f"{name}: {issue}" for issue in section.get("issues") or [])
        runtime_blockers.extend(f"{name}: {issue}" for issue in section.get("runtime_blockers") or [])
        warnings.extend(section.get("warnings") or [])

    divergence_status = "blocked" if runtime_blockers else "warning" if warnings else "pass"
    return {
        "contract_name": "fleet.next90_m136_parity_divergence_class_gate",
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
            "parity_spec": spec_monitor,
            "queue_alignment": queue_alignment,
            "divergence_contract": divergence_contract_monitor,
        },
        "runtime_monitors": {
            "delta_rows": delta_rows_monitor,
            "classification": classification_monitor,
        },
        "monitor_summary": {
            "divergence_status": divergence_status,
            "delta_row_count": len(delta_rows_monitor.get("delta_rows") or []),
            "classified_delta_count": len(classification_monitor.get("classified_delta_ids") or []),
            "unclassified_delta_count": len(classification_monitor.get("unclassified_delta_ids") or []),
            "runtime_blocker_count": len(runtime_blockers),
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
            "flagship_readiness_planes": _source_link(flagship_readiness_planes_path, flagship_readiness_planes),
            "flagship_product_bar": _text_source_link(flagship_product_bar_path),
            "flagship_release_acceptance": _source_link(flagship_release_acceptance_path, flagship_release_acceptance),
            "parity_spec": _text_source_link(parity_spec_path),
            "parity_audit": _source_link(parity_audit_path, parity_audit),
        },
    }


def render_markdown(payload: Dict[str, Any]) -> str:
    summary = dict(payload.get("monitor_summary") or {})
    closeout = dict(payload.get("package_closeout") or {})
    lines = [
        "# Fleet M136 parity divergence class gate",
        "",
        f"- status: {payload.get('status')}",
        f"- divergence_status: {summary.get('divergence_status')}",
        f"- package_id: {payload.get('package_id')}",
        f"- frontier_id: {payload.get('frontier_id')}",
        f"- generated_at: {payload.get('generated_at')}",
        "",
        "## Runtime summary",
        f"- delta_row_count: {summary.get('delta_row_count')}",
        f"- classified_delta_count: {summary.get('classified_delta_count')}",
        f"- unclassified_delta_count: {summary.get('unclassified_delta_count')}",
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
        flagship_readiness_planes_path=Path(args.flagship_readiness_planes).resolve(),
        flagship_product_bar_path=Path(args.flagship_product_bar).resolve(),
        flagship_release_acceptance_path=Path(args.flagship_release_acceptance).resolve(),
        parity_spec_path=Path(args.parity_spec).resolve(),
        parity_audit_path=Path(args.parity_audit).resolve(),
    )
    _write_json_file(output_path, payload)
    _write_markdown_file(markdown_path, render_markdown(payload))
    print(json.dumps({"status": payload["status"], "artifact": str(output_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
