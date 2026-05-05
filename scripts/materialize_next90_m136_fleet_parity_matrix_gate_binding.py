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

PACKAGE_ID = "next90-m136-fleet-bind-the-machine-readable-human-parity-matrix-into-audit-gate-consumpt"
FRONTIER_ID = 4491585022
MILESTONE_ID = 136
WORK_TASK_ID = "136.9"
WAVE_ID = "W23"
QUEUE_TITLE = "Bind the machine-readable human parity matrix into audit/gate consumption so hard families cannot close on prose-only proof."
OWNED_SURFACES = ["bind_the_machine_readable_human_parity_matrix_into_audit:fleet"]
ALLOWED_PATHS = ["scripts", "tests", ".codex-studio", "feedback"]

DEFAULT_OUTPUT = PUBLISHED / "NEXT90_M136_FLEET_PARITY_MATRIX_GATE_BINDING.generated.json"
DEFAULT_MARKDOWN = PUBLISHED / "NEXT90_M136_FLEET_PARITY_MATRIX_GATE_BINDING.generated.md"

SUCCESSOR_REGISTRY = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
FLEET_QUEUE_STAGING = PUBLISHED / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
DESIGN_QUEUE_STAGING = PRODUCT_MIRROR / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
NEXT90_GUIDE = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_GUIDE.md"
PARITY_SPEC = PRODUCT_MIRROR / "CHUMMER5A_HUMAN_PARITY_ACCEPTANCE_SPEC.md"
PARITY_MATRIX = PRODUCT_MIRROR / "CHUMMER5A_HUMAN_PARITY_ACCEPTANCE_MATRIX.yaml"
FLAGSHIP_READINESS_PLANES = PRODUCT_MIRROR / "FLAGSHIP_READINESS_PLANES.yaml"
FLAGSHIP_PRODUCT_BAR = PRODUCT_MIRROR / "FLAGSHIP_PRODUCT_BAR.md"
PARITY_AUDIT = PRESENTATION_ROOT / "CHUMMER5A_UI_ELEMENT_PARITY_AUDIT.generated.json"
M136_AGGREGATE_GATE = PUBLISHED / "NEXT90_M136_FLEET_AGGREGATE_READINESS_PARITY_GATES.generated.json"
FLAGSHIP_PRODUCT_READINESS = PUBLISHED / "FLAGSHIP_PRODUCT_READINESS.generated.json"
FLAGSHIP_READINESS_SCRIPT = ROOT / "scripts" / "materialize_flagship_product_readiness.py"

GUIDE_MARKERS = {
    "wave_23": "## Wave 23 - close calm-under-pressure payoff and veteran continuity",
    "milestone_136": "### 136. Calm-under-pressure payoff, veteran-depth parity, and campaign continuity closure",
}
SPEC_MARKERS = {
    "machine_readable_companion": "The machine-readable companion for this canon is `CHUMMER5A_HUMAN_PARITY_ACCEPTANCE_MATRIX.yaml`.",
    "no_generic_flagship_ready": 'No gate may collapse these families into a generic "desktop parity" or "flagship readiness" pass.',
    "consume_matrix": "The gate stack should consume `CHUMMER5A_HUMAN_PARITY_ACCEPTANCE_MATRIX.yaml` for the field list, family ids, surface ids, required screenshots, and milestone mapping instead of re-encoding that shape ad hoc.",
}
FLAGSHIP_BAR_MARKERS = {
    "matrix_governs_hard_families": "For the remaining hard parity families, familiarity is judged by `CHUMMER5A_HUMAN_PARITY_ACCEPTANCE_SPEC.md` and `CHUMMER5A_HUMAN_PARITY_ACCEPTANCE_MATRIX.yaml`, not by aggregate desktop readiness alone.",
}
MATRIX_TO_AUDIT_FAMILY_IDS = {
    "translator_xml_bridge": "family:custom_data_xml_and_translator_bridge",
    "dense_builder_and_career": "family:dense_builder_and_career_workflows",
    "dice_initiative_and_table_utilities": "family:dice_initiative_and_table_utilities",
    "identity_contacts_lifestyles_history": "family:identity_contacts_lifestyles_history",
    "legacy_and_adjacent_import_oracles": "family:legacy_and_adjacent_import_oracles",
    "sheet_export_print_viewer_exchange": "family:sheet_export_print_viewer_and_exchange",
    "sr6_supplements_designers_house_rules": "family:sr6_supplements_designers_and_house_rules",
}
FLAGSHIP_SCRIPT_MARKERS = {
    "gate_helper": "def _m136_aggregate_readiness_gate_audit(payload: Dict[str, Any]) -> Dict[str, Any]:",
    "gate_ready_evidence": '"m136_aggregate_readiness_gate_ready":',
    "flagship_reason": "M136 aggregate-readiness parity gate is not ready.",
}


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize the Fleet M136 parity-matrix gate-binding packet.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--markdown-output", default=str(DEFAULT_MARKDOWN))
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--fleet-queue-staging", default=str(FLEET_QUEUE_STAGING))
    parser.add_argument("--design-queue-staging", default=str(DESIGN_QUEUE_STAGING))
    parser.add_argument("--next90-guide", default=str(NEXT90_GUIDE))
    parser.add_argument("--parity-spec", default=str(PARITY_SPEC))
    parser.add_argument("--parity-matrix", default=str(PARITY_MATRIX))
    parser.add_argument("--flagship-readiness-planes", default=str(FLAGSHIP_READINESS_PLANES))
    parser.add_argument("--flagship-product-bar", default=str(FLAGSHIP_PRODUCT_BAR))
    parser.add_argument("--parity-audit", default=str(PARITY_AUDIT))
    parser.add_argument("--m136-aggregate-gate", default=str(M136_AGGREGATE_GATE))
    parser.add_argument("--flagship-product-readiness", default=str(FLAGSHIP_PRODUCT_READINESS))
    parser.add_argument("--flagship-readiness-script", default=str(FLAGSHIP_READINESS_SCRIPT))
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


def _marker_monitor(text: str, markers: Dict[str, str], *, label: str) -> Dict[str, Any]:
    checks = {name: marker in text for name, marker in markers.items()}
    issues = [f"{label} missing required marker: {name}" for name, present in checks.items() if not present]
    return {"state": "pass" if not issues else "fail", "checks": checks, "issues": issues}


def _matrix_release_blocking_rows(matrix: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        dict(row)
        for row in (matrix.get("families") or [])
        if isinstance(row, dict) and row.get("release_blocking") is True and _normalize_text(row.get("id"))
    ]


def _matrix_release_blocking_family_ids(matrix: Dict[str, Any]) -> List[str]:
    return [_normalize_text(row.get("id")) for row in _matrix_release_blocking_rows(matrix)]


def _matrix_required_screenshot_ids(matrix: Dict[str, Any]) -> List[str]:
    return sorted(
        {
            screenshot
            for row in _matrix_release_blocking_rows(matrix)
            for screenshot in _normalize_list(row.get("required_screenshots"))
        }
    )


def _matrix_surface_ids(matrix: Dict[str, Any]) -> List[str]:
    return sorted(
        {
            _normalize_text(surface.get("id"))
            for row in _matrix_release_blocking_rows(matrix)
            for surface in (row.get("surfaces") or [])
            if isinstance(surface, dict) and _normalize_text(surface.get("id"))
        }
    )


def _matrix_milestone_task_ids(matrix: Dict[str, Any]) -> List[str]:
    return sorted(
        {
            _normalize_text(row.get("milestone_task_id"))
            for row in _matrix_release_blocking_rows(matrix)
            if _normalize_text(row.get("milestone_task_id"))
        }
    )


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
        warnings.append("Fleet queue mirror row is still missing for work task 136.9.")

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
        "fleet_queue_status": _normalize_text(fleet_queue_item.get("status")),
        "design_queue_status": _normalize_text(design_queue_item.get("status")),
        "work_task_status": _normalize_text(work_task.get("status")),
    }


def _planes_monitor(planes: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    plane_rows = [dict(row) for row in (planes.get("planes") or []) if isinstance(row, dict)]
    by_id = {_normalize_text(row.get("id")): row for row in plane_rows if _normalize_text(row.get("id"))}
    veteran_deep = by_id.get("veteran_deep_workflow_ready", {})
    if "CHUMMER5A_HUMAN_PARITY_ACCEPTANCE_MATRIX.yaml" not in _normalize_list(veteran_deep.get("source_artifacts")):
        issues.append("FLAGSHIP_READINESS_PLANES veteran_deep_workflow_ready no longer lists CHUMMER5A_HUMAN_PARITY_ACCEPTANCE_MATRIX.yaml as a source artifact.")
    if "/docker/chummercomplete/chummer-presentation/.codex-studio/published/CHUMMER5A_UI_ELEMENT_PARITY_AUDIT.generated.json" not in _normalize_list(veteran_deep.get("proving_artifacts")):
        issues.append("FLAGSHIP_READINESS_PLANES veteran_deep_workflow_ready no longer lists CHUMMER5A_UI_ELEMENT_PARITY_AUDIT.generated.json as a proving artifact.")
    return {
        "state": "pass" if not issues else "fail",
        "issues": issues,
        "plane_ids": sorted(by_id),
    }


def _matrix_monitor(matrix: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    rows = _matrix_release_blocking_rows(matrix)
    family_ids = _matrix_release_blocking_family_ids(matrix)
    surface_ids = _matrix_surface_ids(matrix)
    screenshot_ids = _matrix_required_screenshot_ids(matrix)
    milestone_task_ids = _matrix_milestone_task_ids(matrix)
    if not rows:
        issues.append("Parity acceptance matrix is missing release-blocking family rows.")
    for row in rows:
        family_id = _normalize_text(row.get("id"))
        if family_id not in MATRIX_TO_AUDIT_FAMILY_IDS:
            issues.append(f"Parity acceptance matrix family {family_id} is missing an audit-binding alias.")
        if not _normalize_text(row.get("milestone_task_id")):
            issues.append(f"Parity acceptance matrix family {family_id} is missing milestone_task_id.")
        if not _normalize_list(row.get("required_screenshots")):
            issues.append(f"Parity acceptance matrix family {family_id} is missing required_screenshots.")
        surfaces = [dict(surface) for surface in (row.get("surfaces") or []) if isinstance(surface, dict)]
        if not surfaces:
            issues.append(f"Parity acceptance matrix family {family_id} is missing surfaces.")
        for surface in surfaces:
            surface_id = _normalize_text(surface.get("id")) or "unknown_surface"
            if not _normalize_list(surface.get("must_remain_first_class")):
                issues.append(
                    f"Parity acceptance matrix family {family_id} surface {surface_id} is missing must_remain_first_class entries."
                )
    return {
        "state": "pass" if not issues else "fail",
        "issues": issues,
        "release_blocking_family_ids": family_ids,
        "release_blocking_surface_ids": surface_ids,
        "required_screenshot_ids": screenshot_ids,
        "milestone_task_ids": milestone_task_ids,
    }


def _parity_audit_binding_monitor(matrix: Dict[str, Any], parity_audit: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    runtime_blockers: List[str] = []
    elements = [dict(row) for row in (parity_audit.get("elements") or []) if isinstance(row, dict)]
    by_id = {_normalize_text(row.get("id")): row for row in elements if _normalize_text(row.get("id"))}
    missing_family_rows: List[str] = []
    prose_only_family_rows: List[str] = []
    for family_id in _matrix_release_blocking_family_ids(matrix):
        audit_id = MATRIX_TO_AUDIT_FAMILY_IDS.get(family_id, "")
        if not audit_id:
            continue
        row = by_id.get(audit_id)
        if not row:
            missing_family_rows.append(family_id)
            continue
        evidence = _normalize_list(row.get("evidence"))
        if not evidence or not any(item.endswith(".generated.json") for item in evidence):
            prose_only_family_rows.append(family_id)
        for field in ("visual_parity", "behavioral_parity", "present_in_chummer5a", "reason"):
            if not _normalize_text(row.get(field)):
                runtime_blockers.append(f"Parity audit family row {family_id} is missing required field {field}.")
    if missing_family_rows:
        runtime_blockers.append(
            "Parity audit is missing release-blocking family rows for: " + ", ".join(missing_family_rows) + "."
        )
    if prose_only_family_rows:
        runtime_blockers.append(
            "Parity audit still leaves release-blocking families on prose-only evidence: " + ", ".join(prose_only_family_rows) + "."
        )
    return {
        "state": "pass" if not issues else "fail",
        "issues": issues,
        "runtime_blockers": runtime_blockers,
        "missing_family_rows": missing_family_rows,
        "prose_only_family_rows": prose_only_family_rows,
    }


def _m136_gate_binding_monitor(matrix: Dict[str, Any], gate_payload: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    runtime_blockers: List[str] = []
    required_family_ids = _matrix_release_blocking_family_ids(matrix)
    required_screenshot_ids = _matrix_required_screenshot_ids(matrix)
    milestone_task_ids = _matrix_milestone_task_ids(matrix)
    if not gate_payload:
        runtime_blockers.append("M136 aggregate-readiness parity gate artifact is missing.")
        return {
            "state": "pass",
            "issues": issues,
            "runtime_blockers": runtime_blockers,
        }
    if _normalize_text(gate_payload.get("contract_name")) != "fleet.next90_m136_aggregate_readiness_parity_gates":
        issues.append("M136 aggregate-readiness parity gate contract_name drifted.")
    if _normalize_text(gate_payload.get("status")) != "pass":
        runtime_blockers.append("M136 aggregate-readiness parity gate package is not passing.")
    gate_matrix_monitor = dict((gate_payload.get("canonical_monitors") or {}).get("parity_matrix") or {})
    gate_parity_family_monitor = dict((gate_payload.get("runtime_monitors") or {}).get("parity_family_proof") or {})
    gate_summary = dict(gate_payload.get("monitor_summary") or {})
    if list(gate_matrix_monitor.get("required_family_ids") or []) != required_family_ids:
        runtime_blockers.append("M136 aggregate gate required_family_ids drifted from the parity matrix.")
    if list(gate_matrix_monitor.get("milestone_task_ids") or []) != milestone_task_ids:
        runtime_blockers.append("M136 aggregate gate milestone_task_ids drifted from the parity matrix.")
    if list(gate_matrix_monitor.get("required_screenshot_ids") or []) != required_screenshot_ids:
        runtime_blockers.append("M136 aggregate gate required_screenshot_ids drifted from the parity matrix.")
    if list(gate_parity_family_monitor.get("required_family_ids") or []) != required_family_ids:
        runtime_blockers.append("M136 aggregate gate parity_family_proof.required_family_ids drifted from the parity matrix.")
    if int(gate_summary.get("required_family_count") or 0) != len(required_family_ids):
        runtime_blockers.append("M136 aggregate gate required_family_count drifted from the parity matrix.")
    return {
        "state": "pass" if not issues else "fail",
        "issues": issues,
        "runtime_blockers": runtime_blockers,
        "aggregate_readiness_status": _normalize_text(gate_summary.get("aggregate_readiness_status")),
    }


def _flagship_script_binding_monitor(script_text: str) -> Dict[str, Any]:
    checks = {name: marker in script_text for name, marker in FLAGSHIP_SCRIPT_MARKERS.items()}
    issues = [f"Flagship readiness script missing required marker: {name}" for name, present in checks.items() if not present]
    return {"state": "pass" if not issues else "fail", "checks": checks, "issues": issues}


def _published_flagship_contradiction_monitor(
    flagship_payload: Dict[str, Any],
    gate_monitor: Dict[str, Any],
) -> Dict[str, Any]:
    runtime_blockers: List[str] = []
    gate_status = _normalize_text(gate_monitor.get("aggregate_readiness_status")).lower()
    flagship_status = _normalize_text(flagship_payload.get("status")).lower()
    if gate_status == "blocked" and flagship_status == "pass":
        runtime_blockers.append(
            "Published FLAGSHIP_PRODUCT_READINESS still reports pass while the M136 aggregate-readiness parity gate is blocked."
        )
    return {
        "state": "pass",
        "issues": [],
        "runtime_blockers": runtime_blockers,
        "flagship_status": flagship_status,
    }


def build_payload(
    *,
    registry_path: Path,
    fleet_queue_path: Path,
    design_queue_path: Path,
    next90_guide_path: Path,
    parity_spec_path: Path,
    parity_matrix_path: Path,
    flagship_readiness_planes_path: Path,
    flagship_product_bar_path: Path,
    parity_audit_path: Path,
    m136_aggregate_gate_path: Path,
    flagship_product_readiness_path: Path,
    flagship_readiness_script_path: Path,
    generated_at: str | None = None,
) -> Dict[str, Any]:
    generated_at = generated_at or _utc_now()

    registry = _load_yaml(registry_path)
    fleet_queue = _load_yaml(fleet_queue_path)
    design_queue = _load_yaml(design_queue_path)
    next90_guide = _load_text(next90_guide_path)
    parity_spec = _load_text(parity_spec_path)
    parity_matrix = _load_yaml(parity_matrix_path)
    flagship_readiness_planes = _load_yaml(flagship_readiness_planes_path)
    flagship_product_bar = _load_text(flagship_product_bar_path)
    parity_audit = _load_json(parity_audit_path)
    m136_aggregate_gate = _load_json(m136_aggregate_gate_path)
    flagship_product_readiness = _load_json(flagship_product_readiness_path)
    flagship_readiness_script = _load_text(flagship_readiness_script_path)

    milestone = _find_milestone(registry, MILESTONE_ID)
    work_task = _find_work_task(milestone, WORK_TASK_ID)
    fleet_queue_item = _find_queue_item(fleet_queue, WORK_TASK_ID)
    design_queue_item = _find_queue_item(design_queue, WORK_TASK_ID)

    guide_monitor = _marker_monitor(next90_guide, GUIDE_MARKERS, label="Next90 guide canon")
    spec_monitor = _marker_monitor(parity_spec, SPEC_MARKERS, label="Human parity acceptance spec")
    flagship_bar_monitor = _marker_monitor(flagship_product_bar, FLAGSHIP_BAR_MARKERS, label="Flagship product bar canon")
    queue_alignment = _queue_alignment(
        work_task=work_task,
        fleet_queue_item=fleet_queue_item,
        design_queue_item=design_queue_item,
    )
    planes_monitor = _planes_monitor(flagship_readiness_planes)
    matrix_monitor = _matrix_monitor(parity_matrix)
    parity_audit_binding_monitor = _parity_audit_binding_monitor(parity_matrix, parity_audit)
    m136_gate_binding_monitor = _m136_gate_binding_monitor(parity_matrix, m136_aggregate_gate)
    flagship_script_binding_monitor = _flagship_script_binding_monitor(flagship_readiness_script)
    published_flagship_contradiction_monitor = _published_flagship_contradiction_monitor(
        flagship_product_readiness,
        m136_gate_binding_monitor,
    )

    blockers: List[str] = []
    runtime_blockers: List[str] = []
    warnings: List[str] = []
    for name, section in (
        ("next90_guide", guide_monitor),
        ("parity_spec", spec_monitor),
        ("flagship_product_bar", flagship_bar_monitor),
        ("queue_alignment", queue_alignment),
        ("flagship_readiness_planes", planes_monitor),
        ("parity_matrix", matrix_monitor),
        ("flagship_script_binding", flagship_script_binding_monitor),
        ("parity_audit_binding", parity_audit_binding_monitor),
        ("m136_gate_binding", m136_gate_binding_monitor),
        ("published_flagship_contradiction", published_flagship_contradiction_monitor),
    ):
        blockers.extend(f"{name}: {issue}" for issue in section.get("issues") or [])
        runtime_blockers.extend(f"{name}: {issue}" for issue in section.get("runtime_blockers") or [])
        warnings.extend(section.get("warnings") or [])

    matrix_binding_status = "blocked" if runtime_blockers else "warning" if warnings else "pass"
    return {
        "contract_name": "fleet.next90_m136_parity_matrix_gate_binding",
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
            "parity_spec": spec_monitor,
            "flagship_product_bar": flagship_bar_monitor,
            "queue_alignment": queue_alignment,
            "flagship_readiness_planes": planes_monitor,
            "parity_matrix": matrix_monitor,
            "flagship_script_binding": flagship_script_binding_monitor,
        },
        "runtime_monitors": {
            "parity_audit_binding": parity_audit_binding_monitor,
            "m136_gate_binding": m136_gate_binding_monitor,
            "published_flagship_contradiction": published_flagship_contradiction_monitor,
        },
        "monitor_summary": {
            "matrix_binding_status": matrix_binding_status,
            "release_blocking_family_count": len(matrix_monitor.get("release_blocking_family_ids") or []),
            "surface_count": len(matrix_monitor.get("release_blocking_surface_ids") or []),
            "required_screenshot_count": len(matrix_monitor.get("required_screenshot_ids") or []),
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
            "parity_spec": _text_source_link(parity_spec_path),
            "parity_matrix": _source_link(parity_matrix_path, parity_matrix),
            "flagship_readiness_planes": _source_link(flagship_readiness_planes_path, flagship_readiness_planes),
            "flagship_product_bar": _text_source_link(flagship_product_bar_path),
            "parity_audit": _source_link(parity_audit_path, parity_audit),
            "m136_aggregate_gate": _source_link(m136_aggregate_gate_path, m136_aggregate_gate),
            "flagship_product_readiness": _source_link(flagship_product_readiness_path, flagship_product_readiness),
            "flagship_readiness_script": _text_source_link(flagship_readiness_script_path),
        },
    }


def render_markdown(payload: Dict[str, Any]) -> str:
    summary = dict(payload.get("monitor_summary") or {})
    closeout = dict(payload.get("package_closeout") or {})
    lines = [
        "# Fleet M136 parity-matrix gate binding",
        "",
        f"- status: {payload.get('status')}",
        f"- matrix_binding_status: {summary.get('matrix_binding_status')}",
        f"- package_id: {payload.get('package_id')}",
        f"- frontier_id: {payload.get('frontier_id')}",
        f"- generated_at: {payload.get('generated_at')}",
        "",
        "## Runtime summary",
        f"- release_blocking_family_count: {summary.get('release_blocking_family_count')}",
        f"- surface_count: {summary.get('surface_count')}",
        f"- required_screenshot_count: {summary.get('required_screenshot_count')}",
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
        parity_spec_path=Path(args.parity_spec).resolve(),
        parity_matrix_path=Path(args.parity_matrix).resolve(),
        flagship_readiness_planes_path=Path(args.flagship_readiness_planes).resolve(),
        flagship_product_bar_path=Path(args.flagship_product_bar).resolve(),
        parity_audit_path=Path(args.parity_audit).resolve(),
        m136_aggregate_gate_path=Path(args.m136_aggregate_gate).resolve(),
        flagship_product_readiness_path=Path(args.flagship_product_readiness).resolve(),
        flagship_readiness_script_path=Path(args.flagship_readiness_script).resolve(),
    )
    _write_json_file(output_path, payload)
    _write_markdown_file(markdown_path, render_markdown(payload))
    print(json.dumps({"status": payload["status"], "artifact": str(output_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
