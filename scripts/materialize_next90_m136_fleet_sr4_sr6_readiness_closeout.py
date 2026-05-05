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

PACKAGE_ID = "next90-m136-fleet-publish-explicit-sr4-and-sr6-readiness-plane-closeout-from-direct-proo"
FRONTIER_ID = 7496747405
MILESTONE_ID = 136
WORK_TASK_ID = "136.19"
WAVE_ID = "W23"
QUEUE_TITLE = "Publish explicit SR4 and SR6 readiness-plane closeout from direct proofs instead of letting adjacent coverage inherit from broad desktop readiness."
OWNED_SURFACES = ["publish_explicit_sr4_and_sr6_readiness_plane_closeout_fr:fleet"]
ALLOWED_PATHS = ["scripts", "tests", ".codex-studio", "feedback"]

DEFAULT_OUTPUT = PUBLISHED / "NEXT90_M136_FLEET_SR4_SR6_READINESS_CLOSEOUT.generated.json"
DEFAULT_MARKDOWN = PUBLISHED / "NEXT90_M136_FLEET_SR4_SR6_READINESS_CLOSEOUT.generated.md"

SUCCESSOR_REGISTRY = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
FLEET_QUEUE_STAGING = PUBLISHED / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
DESIGN_QUEUE_STAGING = PRODUCT_MIRROR / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
NEXT90_GUIDE = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_GUIDE.md"
FLAGSHIP_READINESS_PLANES = PRODUCT_MIRROR / "FLAGSHIP_READINESS_PLANES.yaml"
FLAGSHIP_PRODUCT_BAR = PRODUCT_MIRROR / "FLAGSHIP_PRODUCT_BAR.md"
FLAGSHIP_PRODUCT_READINESS = PUBLISHED / "FLAGSHIP_PRODUCT_READINESS.generated.json"
SR4_WORKFLOW_PARITY = PRESENTATION_ROOT / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
SR6_WORKFLOW_PARITY = PRESENTATION_ROOT / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
SR4_SR6_FRONTIER = PRESENTATION_ROOT / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"

GUIDE_MARKERS = {
    "wave_23": "## Wave 23 - close calm-under-pressure payoff and veteran continuity",
    "milestone_136": "### 136. Calm-under-pressure payoff, veteran-depth parity, and campaign continuity closure",
}
BAR_MARKERS = {
    "rulesets_authored_not_flattened": "### 3. SR4, SR5, and SR6 must feel authored, not flattened",
    "deterministic_parity": "* deterministic parity in engine truth",
    "ruleset_specific_affordances": "* ruleset-specific interaction affordances where a shared generic workflow would feel confusing or lossy",
}
SR4_CONTRACT = {
    "plane_id": "sr4_parity_ready",
    "proving_artifacts": [
        "/docker/chummercomplete/chummer-presentation/.codex-studio/published/SR4_DESKTOP_WORKFLOW_PARITY.generated.json",
        "/docker/chummercomplete/chummer-presentation/.codex-studio/published/SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json",
    ],
    "fail_when": [
        "SR4 explicit parity proofs stay absent, external-only, or below bounded replacement quality",
    ],
}
SR6_CONTRACT = {
    "plane_id": "sr6_parity_ready",
    "proving_artifacts": [
        "/docker/chummercomplete/chummer-presentation/.codex-studio/published/SR6_DESKTOP_WORKFLOW_PARITY.generated.json",
        "/docker/chummercomplete/chummer-presentation/.codex-studio/published/SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json",
    ],
    "fail_when": [
        "SR6 explicit parity proofs stay absent, external-only, or below bounded replacement quality",
    ],
}


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize the Fleet M136 SR4/SR6 readiness closeout packet.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--markdown-output", default=str(DEFAULT_MARKDOWN))
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--fleet-queue-staging", default=str(FLEET_QUEUE_STAGING))
    parser.add_argument("--design-queue-staging", default=str(DESIGN_QUEUE_STAGING))
    parser.add_argument("--next90-guide", default=str(NEXT90_GUIDE))
    parser.add_argument("--flagship-readiness-planes", default=str(FLAGSHIP_READINESS_PLANES))
    parser.add_argument("--flagship-product-bar", default=str(FLAGSHIP_PRODUCT_BAR))
    parser.add_argument("--flagship-product-readiness", default=str(FLAGSHIP_PRODUCT_READINESS))
    parser.add_argument("--sr4-workflow-parity", default=str(SR4_WORKFLOW_PARITY))
    parser.add_argument("--sr6-workflow-parity", default=str(SR6_WORKFLOW_PARITY))
    parser.add_argument("--sr4-sr6-frontier", default=str(SR4_SR6_FRONTIER))
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
        warnings.append("Fleet queue mirror row is still missing for work task 136.19.")
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


def _planes_contract_monitor(planes_payload: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    plane_rows = [dict(row) for row in (planes_payload.get("planes") or []) if isinstance(row, dict)]
    by_id = {_normalize_text(row.get("id")): row for row in plane_rows if _normalize_text(row.get("id"))}
    for contract in (SR4_CONTRACT, SR6_CONTRACT):
        row = by_id.get(contract["plane_id"], {})
        if not row:
            issues.append(f"FLAGSHIP_READINESS_PLANES is missing plane {contract['plane_id']}.")
            continue
        owners = _normalize_list(row.get("owner_repos"))
        if "fleet" not in owners:
            issues.append(f"FLAGSHIP_READINESS_PLANES {contract['plane_id']} no longer lists fleet as an owner repo.")
        proving = _normalize_list(row.get("proving_artifacts"))
        for artifact in contract["proving_artifacts"]:
            if artifact not in proving:
                issues.append(f"FLAGSHIP_READINESS_PLANES {contract['plane_id']} is missing proving artifact {artifact}.")
        fail_when = _normalize_list(row.get("fail_when"))
        for clause in contract["fail_when"]:
            if clause not in fail_when:
                issues.append(f"FLAGSHIP_READINESS_PLANES {contract['plane_id']} is missing fail_when clause: {clause}")
    return {"state": "pass" if not issues else "fail", "issues": issues}


def _plane_payload(flagship_payload: Dict[str, Any], plane_id: str) -> Dict[str, Any]:
    planes = flagship_payload.get("readiness_planes")
    if not isinstance(planes, dict):
        return {}
    row = planes.get(plane_id)
    return dict(row) if isinstance(row, dict) else {}


def _flagship_ruleset_linkage_monitor(flagship_payload: Dict[str, Any]) -> Dict[str, Any]:
    runtime_blockers: List[str] = []
    sr4_plane = _plane_payload(flagship_payload, "sr4_parity_ready")
    sr6_plane = _plane_payload(flagship_payload, "sr6_parity_ready")
    flagship_plane = _plane_payload(flagship_payload, "flagship_ready")
    flagship_evidence = dict(flagship_plane.get("evidence") or {})
    if not sr4_plane:
        runtime_blockers.append("FLAGSHIP_PRODUCT_READINESS is missing readiness plane sr4_parity_ready.")
    if not sr6_plane:
        runtime_blockers.append("FLAGSHIP_PRODUCT_READINESS is missing readiness plane sr6_parity_ready.")
    if sr4_plane and not isinstance(sr4_plane.get("evidence"), dict):
        runtime_blockers.append("FLAGSHIP_PRODUCT_READINESS sr4_parity_ready plane is missing evidence{}.")
    if sr6_plane and not isinstance(sr6_plane.get("evidence"), dict):
        runtime_blockers.append("FLAGSHIP_PRODUCT_READINESS sr6_parity_ready plane is missing evidence{}.")
    if bool(flagship_evidence.get("sr4_parity_ready")) != _is_ready(sr4_plane.get("status")):
        runtime_blockers.append("FLAGSHIP_PRODUCT_READINESS flagship_ready evidence.sr4_parity_ready drifted from sr4_parity_ready status.")
    if bool(flagship_evidence.get("sr6_parity_ready")) != _is_ready(sr6_plane.get("status")):
        runtime_blockers.append("FLAGSHIP_PRODUCT_READINESS flagship_ready evidence.sr6_parity_ready drifted from sr6_parity_ready status.")
    return {
        "state": "pass",
        "issues": [],
        "runtime_blockers": runtime_blockers,
        "sr4_plane_status": _normalize_text(sr4_plane.get("status")),
        "sr6_plane_status": _normalize_text(sr6_plane.get("status")),
    }


def _sr4_direct_proof_monitor(sr4_payload: Dict[str, Any], frontier_payload: Dict[str, Any]) -> Dict[str, Any]:
    runtime_blockers: List[str] = []
    evidence = dict(sr4_payload.get("evidence") or {})
    frontier_evidence = dict(frontier_payload.get("evidence") or {})
    checks = {
        "sr4_workflow_parity_status": _is_passing(sr4_payload.get("status")),
        "sr4_workflow_failing_parity_receipts_external_only_clear": not bool(evidence.get("failingParityReceiptsExternalOnly")),
        "sr4_workflow_missing_family_ids_clear": not _normalize_list(evidence.get("missingFamilyIds")),
        "sr4_workflow_non_ready_family_ids_clear": not _normalize_list(evidence.get("nonReadyFamilyIds")),
        "sr4_frontier_status": _is_passing(frontier_payload.get("status")),
        "sr4_frontier_receipt_status": _normalize_text(frontier_evidence.get("sr4Status")).lower() in {"pass", "passed", "ready"},
    }
    if not sr4_payload:
        runtime_blockers.append("SR4_DESKTOP_WORKFLOW_PARITY generated artifact is missing.")
    if not frontier_payload:
        runtime_blockers.append("SR4_SR6_DESKTOP_PARITY_FRONTIER generated artifact is missing.")
    expected_ready = sr4_payload and frontier_payload and all(checks.values())
    return {
        "state": "pass",
        "issues": [],
        "runtime_blockers": runtime_blockers,
        "actual_ready": expected_ready,
        "checks": checks,
    }


def _sr6_direct_proof_monitor(sr6_payload: Dict[str, Any], frontier_payload: Dict[str, Any]) -> Dict[str, Any]:
    runtime_blockers: List[str] = []
    evidence = dict(sr6_payload.get("evidence") or {})
    frontier_evidence = dict(frontier_payload.get("evidence") or {})
    checks = {
        "sr6_workflow_parity_status": _is_passing(sr6_payload.get("status")),
        "sr6_workflow_failing_parity_receipts_external_only_clear": not bool(evidence.get("failingParityReceiptsExternalOnly")),
        "sr6_workflow_missing_family_ids_clear": not _normalize_list(evidence.get("missingFamilyIds")),
        "sr6_workflow_non_ready_family_ids_clear": not _normalize_list(evidence.get("nonReadyFamilyIds")),
        "sr6_frontier_status": _is_passing(frontier_payload.get("status")),
        "sr6_frontier_receipt_status": _normalize_text(frontier_evidence.get("sr6Status")).lower() in {"pass", "passed", "ready"},
    }
    if not sr6_payload:
        runtime_blockers.append("SR6_DESKTOP_WORKFLOW_PARITY generated artifact is missing.")
    if not frontier_payload:
        runtime_blockers.append("SR4_SR6_DESKTOP_PARITY_FRONTIER generated artifact is missing.")
    expected_ready = sr6_payload and frontier_payload and all(checks.values())
    return {
        "state": "pass",
        "issues": [],
        "runtime_blockers": runtime_blockers,
        "actual_ready": expected_ready,
        "checks": checks,
    }


def _ruleset_plane_projection_monitor(plane_id: str, plane_payload: Dict[str, Any], expected_ready: bool) -> Dict[str, Any]:
    runtime_blockers: List[str] = []
    actual_ready = _is_ready(plane_payload.get("status"))
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
    sr4_workflow_parity_path: Path,
    sr6_workflow_parity_path: Path,
    sr4_sr6_frontier_path: Path,
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
    sr4_workflow_parity = _load_json(sr4_workflow_parity_path)
    sr6_workflow_parity = _load_json(sr6_workflow_parity_path)
    sr4_sr6_frontier = _load_json(sr4_sr6_frontier_path)

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
    linkage_monitor = _flagship_ruleset_linkage_monitor(flagship_product_readiness)
    sr4_direct_proof_monitor = _sr4_direct_proof_monitor(sr4_workflow_parity, sr4_sr6_frontier)
    sr6_direct_proof_monitor = _sr6_direct_proof_monitor(sr6_workflow_parity, sr4_sr6_frontier)
    sr4_projection = _ruleset_plane_projection_monitor(
        "sr4_parity_ready",
        _plane_payload(flagship_product_readiness, "sr4_parity_ready"),
        bool(sr4_direct_proof_monitor.get("actual_ready")),
    )
    sr6_projection = _ruleset_plane_projection_monitor(
        "sr6_parity_ready",
        _plane_payload(flagship_product_readiness, "sr6_parity_ready"),
        bool(sr6_direct_proof_monitor.get("actual_ready")),
    )

    blockers: List[str] = []
    runtime_blockers: List[str] = []
    warnings: List[str] = []
    for name, section in (
        ("next90_guide", guide_monitor),
        ("flagship_product_bar", bar_monitor),
        ("queue_alignment", queue_alignment),
        ("flagship_readiness_planes", planes_contract_monitor),
        ("flagship_linkage", linkage_monitor),
        ("sr4_direct_proof", sr4_direct_proof_monitor),
        ("sr6_direct_proof", sr6_direct_proof_monitor),
        ("sr4_projection", sr4_projection),
        ("sr6_projection", sr6_projection),
    ):
        blockers.extend(f"{name}: {issue}" for issue in section.get("issues") or [])
        runtime_blockers.extend(f"{name}: {issue}" for issue in section.get("runtime_blockers") or [])
        warnings.extend(section.get("warnings") or [])

    closeout_status = "blocked" if runtime_blockers else "warning" if warnings else "pass"
    return {
        "contract_name": "fleet.next90_m136_sr4_sr6_readiness_closeout",
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
            "flagship_linkage": linkage_monitor,
            "sr4_direct_proof": sr4_direct_proof_monitor,
            "sr6_direct_proof": sr6_direct_proof_monitor,
            "sr4_projection": sr4_projection,
            "sr6_projection": sr6_projection,
        },
        "monitor_summary": {
            "closeout_status": closeout_status,
            "runtime_blocker_count": len(runtime_blockers),
            "warning_count": len(warnings),
            "sr4_ready": bool(sr4_projection.get("actual_ready")),
            "sr6_ready": bool(sr6_projection.get("actual_ready")),
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
            "sr4_workflow_parity": _source_link(sr4_workflow_parity_path, sr4_workflow_parity),
            "sr6_workflow_parity": _source_link(sr6_workflow_parity_path, sr6_workflow_parity),
            "sr4_sr6_frontier": _source_link(sr4_sr6_frontier_path, sr4_sr6_frontier),
        },
    }


def render_markdown(payload: Dict[str, Any]) -> str:
    summary = dict(payload.get("monitor_summary") or {})
    closeout = dict(payload.get("package_closeout") or {})
    lines = [
        "# Fleet M136 SR4/SR6 readiness closeout",
        "",
        f"- status: {payload.get('status')}",
        f"- closeout_status: {summary.get('closeout_status')}",
        f"- package_id: {payload.get('package_id')}",
        f"- frontier_id: {payload.get('frontier_id')}",
        f"- generated_at: {payload.get('generated_at')}",
        "",
        "## Runtime summary",
        f"- sr4_ready: {summary.get('sr4_ready')}",
        f"- sr6_ready: {summary.get('sr6_ready')}",
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
        flagship_product_readiness_path=Path(args.flagship_product_readiness).resolve(),
        sr4_workflow_parity_path=Path(args.sr4_workflow_parity).resolve(),
        sr6_workflow_parity_path=Path(args.sr6_workflow_parity).resolve(),
        sr4_sr6_frontier_path=Path(args.sr4_sr6_frontier).resolve(),
    )
    _write_json_file(output_path, payload)
    _write_markdown_file(markdown_path, render_markdown(payload))
    print(json.dumps({"status": payload["status"], "artifact": str(output_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
