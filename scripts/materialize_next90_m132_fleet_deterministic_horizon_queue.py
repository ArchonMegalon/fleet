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

PACKAGE_ID = "next90-m132-fleet-schedule-deterministic-horizon-slices-only-after-owner-h"
FRONTIER_ID = 8249224665
MILESTONE_ID = 132
WORK_TASK_ID = "132.6"
WAVE_ID = "W20"
QUEUE_TITLE = "Schedule deterministic horizon slices only after owner handoff gates, proof scopes, and stop conditions are satisfied."
QUEUE_TASK = QUEUE_TITLE
WORK_TASK_TITLE = QUEUE_TITLE
WORK_TASK_DEPENDENCIES = [114, 115, 126]
OWNED_SURFACES = ["schedule_deterministic_horizon_slices_only:fleet"]
ALLOWED_PATHS = ["scripts", "tests", ".codex-studio", "feedback"]

DEFAULT_OUTPUT = PUBLISHED / "NEXT90_M132_FLEET_DETERMINISTIC_HORIZON_QUEUE.generated.json"
DEFAULT_MARKDOWN = PUBLISHED / "NEXT90_M132_FLEET_DETERMINISTIC_HORIZON_QUEUE.generated.md"

SUCCESSOR_REGISTRY = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
QUEUE_STAGING = PUBLISHED / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
DESIGN_QUEUE_STAGING = PRODUCT_MIRROR / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
HORIZON_REGISTRY = PRODUCT_MIRROR / "HORIZON_REGISTRY.yaml"
NEXT90_GUIDE = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_GUIDE.md"

HORIZON_HANDOFF_GATE_DESIGN_TASK_ID = "126.1"
DETERMINISTIC_HORIZON_GATE_DESIGN_TASK_ID = "132.7"
HORIZON_HANDOFF_REQUIRED_FIELDS = (
    "owner_handoff_gate",
    "owning_repos",
    "allowed_surfaces",
    "proof_gate",
    "public_claim_posture",
    "stop_condition",
)
GUIDE_MARKERS = {
    "wave_20": "## Wave 20 - implement rules, source, and deterministic horizon tranche",
    "milestone_132": "### 132. Deterministic horizon implementation tranche: NEXUS-PAN, ALICE, KARMA FORGE, Knowledge Fabric, and Local Co-Processor",
    "owner_handoff": "owner handoff gates",
    "executable_proof": "executable proof",
    "assistant_rule_invention": "without assistant-side rules invention",
}
HORIZON_RULE_MARKERS = {
    "future_lane_only": "future-capability lane, not a shipment promise.",
    "eventual_build_path": "eventual build path",
    "owner_handoff_and_proof": "its owner handoff gate is materially satisfied",
    "blockers_outrank_storytelling": "Open flagship blockers and lived-system release blockers outrank horizon storytelling",
}


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize the Fleet M132 deterministic horizon queue guard packet.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--markdown-output", default=str(DEFAULT_MARKDOWN))
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--queue-staging", default=str(QUEUE_STAGING))
    parser.add_argument("--design-queue-staging", default=str(DESIGN_QUEUE_STAGING))
    parser.add_argument("--horizon-registry", default=str(HORIZON_REGISTRY))
    parser.add_argument("--next90-guide", default=str(NEXT90_GUIDE))
    return parser.parse_args(argv)


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_list(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []
    return [_normalize_text(value) for value in values if _normalize_text(value)]


def _read_yaml(path: Path) -> Dict[str, Any]:
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


def _read_text(path: Path) -> str:
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


def _source_link(path: Path, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "path": _display_path(path),
        "sha256": _sha256_file(path),
        "generated_at": _normalize_text(payload.get("generated_at")),
    }


def _text_source_link(path: Path) -> Dict[str, Any]:
    return {"path": _display_path(path), "sha256": _sha256_file(path), "generated_at": ""}


def _find_queue_item(queue: Dict[str, Any], package_id: str) -> Dict[str, Any]:
    for row in queue.get("items") or []:
        if isinstance(row, dict) and _normalize_text(row.get("package_id")) == package_id:
            return dict(row)
    return {}


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


def _queue_items_from_payload(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [dict(row) for row in (payload.get("items") or []) if isinstance(row, dict)]


def _next_wave_registry_work_task_status_by_id(registry: Dict[str, Any]) -> Dict[str, str]:
    rows: Dict[str, str] = {}
    for milestone in registry.get("milestones") or []:
        if not isinstance(milestone, dict):
            continue
        for task in milestone.get("work_tasks") or []:
            if not isinstance(task, dict):
                continue
            task_id = _normalize_text(task.get("id"))
            if task_id:
                rows[task_id] = _normalize_text(task.get("status")).lower()
    return rows


def _milestone_title_by_id(registry: Dict[str, Any]) -> Dict[int, str]:
    rows: Dict[int, str] = {}
    for milestone in registry.get("milestones") or []:
        if isinstance(milestone, dict) and int(milestone.get("id") or 0) > 0:
            rows[int(milestone.get("id") or 0)] = _normalize_text(milestone.get("title"))
    return rows


def _queue_alignment(
    queue_item: Dict[str, Any],
    design_queue_item: Dict[str, Any],
    work_task: Dict[str, Any],
    milestone: Dict[str, Any],
) -> Dict[str, Any]:
    issues: List[str] = []
    if not queue_item:
        issues.append("Fleet queue row is missing.")
    if not design_queue_item:
        issues.append("Design queue row is missing.")
    if not work_task:
        issues.append("Canonical registry work task is missing.")
    expected = {
        "title": QUEUE_TITLE,
        "task": QUEUE_TASK,
        "milestone_id": MILESTONE_ID,
        "work_task_id": WORK_TASK_ID,
        "repo": "fleet",
        "wave": WAVE_ID,
        "frontier_id": FRONTIER_ID,
    }
    for field, expected_value in expected.items():
        expected_text = _normalize_text(expected_value)
        if queue_item and _normalize_text(queue_item.get(field)) != expected_text:
            issues.append(f"Fleet queue {field} drifted.")
        if design_queue_item and _normalize_text(design_queue_item.get(field)) != expected_text:
            issues.append(f"Design queue {field} drifted.")
    if queue_item and _normalize_list(queue_item.get("allowed_paths")) != ALLOWED_PATHS:
        issues.append("Fleet queue allowed_paths drifted.")
    if design_queue_item and _normalize_list(design_queue_item.get("allowed_paths")) != ALLOWED_PATHS:
        issues.append("Design queue allowed_paths drifted.")
    if queue_item and _normalize_list(queue_item.get("owned_surfaces")) != OWNED_SURFACES:
        issues.append("Fleet queue owned_surfaces drifted.")
    if design_queue_item and _normalize_list(design_queue_item.get("owned_surfaces")) != OWNED_SURFACES:
        issues.append("Design queue owned_surfaces drifted.")
    if work_task:
        if _normalize_text(work_task.get("owner")) != "fleet":
            issues.append("Canonical registry work task owner drifted.")
        if _normalize_text(work_task.get("title")) != WORK_TASK_TITLE:
            issues.append("Canonical registry work task title drifted.")
    if milestone and [int(value) for value in milestone.get("dependencies") or []] != WORK_TASK_DEPENDENCIES:
        issues.append("Canonical registry milestone dependencies drifted from M132 requirement set.")
    return {
        "state": "pass" if not issues else "fail",
        "issues": issues,
        "fleet_queue_status": _normalize_text(queue_item.get("status")),
        "design_queue_status": _normalize_text(design_queue_item.get("status")),
        "registry_status": _normalize_text(milestone.get("status")),
        "work_task_status": _normalize_text(work_task.get("status")),
    }


def _marker_monitor(text: str, markers: Dict[str, str], *, label: str) -> Dict[str, Any]:
    checks = {name: marker in text for name, marker in markers.items()}
    issues = [f"{label} missing required marker: {name}" for name, present in checks.items() if not present]
    return {"state": "pass" if not issues else "fail", "checks": checks, "issues": issues}


def _horizon_registry_monitor(registry: Dict[str, Any]) -> Dict[str, Any]:
    missing_by_repo: Dict[str, List[Dict[str, Any]]] = {}
    issues: List[str] = []
    global_blockers: List[str] = []
    horizons = [dict(row) for row in (registry.get("horizons") or []) if isinstance(row, dict)]
    if not horizons:
        issues.append("Horizon registry is empty.")
        global_blockers.append("horizon registry is empty")
    for row in horizons:
        horizon_id = _normalize_text(row.get("id"))
        owners = [owner for owner in _normalize_list(row.get("owning_repos")) if owner]
        missing_fields: List[str] = []
        for field in HORIZON_HANDOFF_REQUIRED_FIELDS:
            value = row.get(field)
            if field == "owning_repos":
                if not owners:
                    missing_fields.append(field)
                continue
            if isinstance(value, list):
                if not any(_normalize_text(item) for item in value):
                    missing_fields.append(field)
                continue
            if not _normalize_text(value):
                missing_fields.append(field)
        if not missing_fields:
            continue
        entry = {"horizon_id": horizon_id, "missing_fields": missing_fields}
        for owner in owners or ["unowned"]:
            missing_by_repo.setdefault(owner, []).append(dict(entry))
    if missing_by_repo.get("unowned"):
        global_blockers.append("one or more horizons are missing owning_repos and cannot be handed off safely")
    return {
        "state": "pass" if not issues else "fail",
        "horizon_count": len(horizons),
        "repos_with_missing_handoff_fields": sorted(missing_by_repo),
        "missing_by_repo": missing_by_repo,
        "global_blockers": global_blockers,
        "issues": issues,
    }


def _queue_item_is_deterministic_horizon_candidate(
    item: Dict[str, Any],
    *,
    milestone_titles: Dict[int, str],
) -> bool:
    milestone_id = int(item.get("milestone_id") or 0)
    if milestone_id == 132:
        return True
    haystack = " ".join(
        [
            milestone_titles.get(milestone_id, ""),
            _normalize_text(item.get("title")),
            _normalize_text(item.get("task")),
            _normalize_text(item.get("package_id")),
        ]
    ).lower()
    return "deterministic horizon" in haystack


def _queue_gate_monitor(
    *,
    registry: Dict[str, Any],
    queue_payload: Dict[str, Any],
    horizon_monitor: Dict[str, Any],
) -> Dict[str, Any]:
    milestone_titles = _milestone_title_by_id(registry)
    work_task_status = _next_wave_registry_work_task_status_by_id(registry)
    handoff_design_gate_status = _normalize_text(work_task_status.get(HORIZON_HANDOFF_GATE_DESIGN_TASK_ID)).lower()
    handoff_design_gate_done = handoff_design_gate_status in {"complete", "completed", "done", "landed", "shipped"}
    deterministic_design_gate_status = _normalize_text(
        work_task_status.get(DETERMINISTIC_HORIZON_GATE_DESIGN_TASK_ID)
    ).lower()
    deterministic_design_gate_done = deterministic_design_gate_status in {
        "complete",
        "completed",
        "done",
        "landed",
        "shipped",
    }
    missing_by_repo = dict(horizon_monitor.get("missing_by_repo") or {})
    global_blockers = [_normalize_text(value) for value in (horizon_monitor.get("global_blockers") or []) if _normalize_text(value)]
    blocked_rows: List[Dict[str, Any]] = []
    ready_rows: List[Dict[str, Any]] = []
    for item in _queue_items_from_payload(queue_payload):
        if not _queue_item_is_deterministic_horizon_candidate(item, milestone_titles=milestone_titles):
            continue
        repo = _normalize_text(item.get("repo"))
        reasons: List[str] = []
        if not handoff_design_gate_done:
            reasons.append("design handoff gate task 126.1 is not done")
        if not deterministic_design_gate_done:
            reasons.append("deterministic horizon design gate task 132.7 is not done")
        reasons.extend(global_blockers)
        if repo and missing_by_repo.get(repo):
            reasons.append(
                "horizon registry still lacks required handoff fields for "
                + repo
                + ": "
                + ", ".join(sorted({_normalize_text(entry.get('horizon_id')) for entry in missing_by_repo.get(repo) or []}))
            )
        row = {
            "package_id": _normalize_text(item.get("package_id")),
            "work_task_id": _normalize_text(item.get("work_task_id")),
            "repo": repo,
            "title": _normalize_text(item.get("title")),
            "reasons": reasons,
        }
        if reasons:
            blocked_rows.append(row)
        else:
            ready_rows.append(row)
    warnings: List[str] = []
    if blocked_rows:
        warnings.append(
            f"Deterministic horizon queue slices are currently blocked for {len(blocked_rows)} item(s) until handoff and proof truth is satisfied."
        )
    return {
        "state": "pass",
        "handoff_design_gate_task_id": HORIZON_HANDOFF_GATE_DESIGN_TASK_ID,
        "handoff_design_gate_task_status": handoff_design_gate_status or "unknown",
        "handoff_design_gate_task_done": handoff_design_gate_done,
        "deterministic_design_gate_task_id": DETERMINISTIC_HORIZON_GATE_DESIGN_TASK_ID,
        "deterministic_design_gate_task_status": deterministic_design_gate_status or "unknown",
        "deterministic_design_gate_task_done": deterministic_design_gate_done,
        "global_blockers": global_blockers,
        "blocked_deterministic_queue_item_count": len(blocked_rows),
        "ready_deterministic_queue_item_count": len(ready_rows),
        "blocked_items": blocked_rows,
        "ready_items": ready_rows,
        "warnings": warnings,
        "issues": [],
    }


def build_payload(
    *,
    registry_path: Path,
    queue_path: Path,
    design_queue_path: Path,
    horizon_registry_path: Path,
    next90_guide_path: Path,
    generated_at: str | None = None,
) -> Dict[str, Any]:
    generated_at = generated_at or _utc_now()
    registry = _read_yaml(registry_path)
    queue = _read_yaml(queue_path)
    design_queue = _read_yaml(design_queue_path)
    horizon_registry = _read_yaml(horizon_registry_path)
    next90_guide = _read_text(next90_guide_path)

    milestone = _find_milestone(registry, MILESTONE_ID)
    work_task = _find_work_task(milestone, WORK_TASK_ID)
    queue_item = _find_queue_item(queue, PACKAGE_ID)
    design_queue_item = _find_queue_item(design_queue, PACKAGE_ID)

    canonical_alignment = _queue_alignment(queue_item, design_queue_item, work_task, milestone)
    guide_monitor = _marker_monitor(next90_guide, GUIDE_MARKERS, label="Next90 guide canon")
    horizon_rule_monitor = _marker_monitor(
        _read_text(horizon_registry_path),
        HORIZON_RULE_MARKERS,
        label="Horizon registry canon",
    )
    horizon_monitor = _horizon_registry_monitor(horizon_registry)
    gate_monitor = _queue_gate_monitor(registry=registry, queue_payload=queue, horizon_monitor=horizon_monitor)

    blockers: List[str] = []
    for section_name, section in (
        ("canonical_alignment", canonical_alignment),
        ("guide_monitor", guide_monitor),
        ("horizon_rule_monitor", horizon_rule_monitor),
        ("horizon_registry_monitor", horizon_monitor),
    ):
        for issue in section.get("issues") or []:
            blockers.append(f"{section_name}: {issue}")

    warnings: List[str] = []
    warnings.extend(gate_monitor.get("warnings") or [])

    return {
        "contract_name": "fleet.next90_m132_deterministic_horizon_queue_guard",
        "generated_at": generated_at,
        "status": "pass" if not blockers else "blocked",
        "package_id": PACKAGE_ID,
        "frontier_id": FRONTIER_ID,
        "milestone_id": MILESTONE_ID,
        "work_task_id": WORK_TASK_ID,
        "wave": WAVE_ID,
        "queue_title": QUEUE_TITLE,
        "queue_task": QUEUE_TASK,
        "owned_surfaces": OWNED_SURFACES,
        "allowed_paths": ALLOWED_PATHS,
        "canonical_alignment": canonical_alignment,
        "canonical_monitors": {
            "next90_guide": guide_monitor,
            "horizon_rules": horizon_rule_monitor,
            "horizon_registry": horizon_monitor,
        },
        "queue_gate_monitor": gate_monitor,
        "package_closeout": {
            "state": "pass" if not blockers else "blocked",
            "blockers": blockers,
            "warnings": warnings,
        },
        "source_inputs": {
            "successor_registry": _source_link(registry_path, registry),
            "queue_staging": _source_link(queue_path, queue),
            "design_queue_staging": _source_link(design_queue_path, design_queue),
            "horizon_registry": _source_link(horizon_registry_path, horizon_registry),
            "next90_guide": _text_source_link(next90_guide_path),
        },
    }


def render_markdown(payload: Dict[str, Any]) -> str:
    monitor = dict(payload.get("queue_gate_monitor") or {})
    closeout = dict(payload.get("package_closeout") or {})
    lines = [
        "# Fleet M132 deterministic horizon queue guard",
        "",
        f"- status: {payload.get('status')}",
        f"- package_id: {payload.get('package_id')}",
        f"- frontier_id: {payload.get('frontier_id')}",
        f"- generated_at: {payload.get('generated_at')}",
        "",
        "## Queue gate",
        f"- handoff design gate: {monitor.get('handoff_design_gate_task_id')} ({monitor.get('handoff_design_gate_task_status')})",
        f"- deterministic design gate: {monitor.get('deterministic_design_gate_task_id')} ({monitor.get('deterministic_design_gate_task_status')})",
        f"- blocked deterministic queue items: {monitor.get('blocked_deterministic_queue_item_count', 0)}",
        f"- ready deterministic queue items: {monitor.get('ready_deterministic_queue_item_count', 0)}",
        "",
        "## Blocked items",
    ]
    for row in monitor.get("blocked_items") or []:
        lines.append(f"- {row.get('package_id')}: {', '.join(row.get('reasons') or [])}")
    lines.extend(["", "## Package closeout", f"- state: {closeout.get('state') or 'blocked'}"])
    if closeout.get("warnings"):
        lines.append("- warnings:")
        lines.extend([f"  - {warning}" for warning in closeout.get("warnings") or []])
    return "\n".join(lines) + "\n"


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(
        registry_path=Path(args.successor_registry).resolve(),
        queue_path=Path(args.queue_staging).resolve(),
        design_queue_path=Path(args.design_queue_staging).resolve(),
        horizon_registry_path=Path(args.horizon_registry).resolve(),
        next90_guide_path=Path(args.next90_guide).resolve(),
    )
    output_path = Path(args.output).resolve()
    markdown_path = Path(args.markdown_output).resolve()
    _write_json_file(output_path, payload)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "artifact": str(output_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
