#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List

import yaml


ROOT = Path("/docker/fleet")
PUBLISHED = ROOT / ".codex-studio" / "published"
PRODUCT_MIRROR = Path("/docker/chummercomplete/chummer-design/products/chummer")

PACKAGE_ID = "next90-m129-fleet-keep-participant-lane-auth-lane-local-while-emitting-sig"
FRONTIER_ID = 7997916353
MILESTONE_ID = 129
WORK_TASK_ID = "129.4"
DESIGN_CANON_TASK_ID = "129.6"
WAVE_ID = "W19"
QUEUE_TITLE = "Keep participant-lane auth lane-local while emitting signed contribution receipts and sponsor-session execution metadata."
QUEUE_TASK = QUEUE_TITLE
WORK_TASK_TITLE = QUEUE_TITLE
WORK_TASK_DEPENDENCIES = [102, 105, 118, 125]
OWNED_SURFACES = ["keep_participant_lane_auth_lane:fleet"]
ALLOWED_PATHS = ["scripts", "tests", ".codex-studio", "feedback"]

DEFAULT_OUTPUT = PUBLISHED / "NEXT90_M129_FLEET_PARTICIPATION_LANE_RECEIPTS.generated.json"
DEFAULT_MARKDOWN = PUBLISHED / "NEXT90_M129_FLEET_PARTICIPATION_LANE_RECEIPTS.generated.md"

SUCCESSOR_REGISTRY = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
QUEUE_STAGING = PUBLISHED / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
DESIGN_QUEUE_STAGING = PRODUCT_MIRROR / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
NEXT90_GUIDE = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_GUIDE.md"
ADR_PATH = PRODUCT_MIRROR / "adrs" / "ADR-0006-participation-and-sponsored-execution-split.md"
WORKFLOW_PATH = PRODUCT_MIRROR / "PARTICIPATION_AND_BOOSTER_WORKFLOW.md"
OWNERSHIP_MATRIX = PRODUCT_MIRROR / "OWNERSHIP_MATRIX.md"
FLEET_PROJECT = PRODUCT_MIRROR / "projects" / "fleet.md"
HUB_PROJECT = PRODUCT_MIRROR / "projects" / "hub.md"
FLEET_AGENT_TEMPLATE = PRODUCT_MIRROR / "review" / "fleet.AGENTS.template.md"
STATUS_PLANE = PUBLISHED / "STATUS_PLANE.generated.yaml"
FLEET_PUBLISHED_ROOT = ROOT / ".codex-studio" / "published"
HUB_PUBLISHED_ROOT = Path("/docker/chummercomplete/chummer.run-services/.codex-studio/published")
REGISTRY_PUBLISHED_ROOT = Path("/docker/chummercomplete/chummer-hub-registry/.codex-studio/published")

DONE_STATUSES = {"complete", "completed", "done", "landed", "shipped"}
STATUS_PLANE_FRESHNESS_HOURS = 24
REPO_TO_STATUS_PLANE_ID = {
    "chummer6-hub": "hub",
    "chummer6-hub-registry": "hub-registry",
    "chummer6-ui": "ui",
    "fleet": "fleet",
    "executive-assistant": "ea",
    "chummer6-design": "design",
}
GUIDE_MARKERS = {
    "wave_19": "## Wave 19 - finish account/community, provider, and public-guide substrate",
    "milestone_129": "### 129. Account, identity, channel linking, participation, entitlements, and community ledger completion",
    "exit_contract": "Exit: accounts, identities, channels, groups, memberships, sponsorship, rewards, entitlements, participation, and lane-local Fleet receipt semantics form one reusable community substrate.",
}
ADR_MARKERS = {
    "hub_truth": "`chummer6-hub` owns sponsor intent, consent, user and group truth, sponsor-session records, ledgers, and recognition policy.",
    "fleet_lane_local": "`fleet` owns participant-lane provisioning, worker-host device auth, lane-local auth/cache storage, sponsored execution policy, and signed contribution receipts.",
    "recognition_rule": "Recognition must derive from validated contribution receipts rather than raw time or auth completion.",
}
WORKFLOW_MARKERS = {
    "lane_local_storage": "* lane-local auth/cache storage",
    "receipt_emission": "* signed contribution receipt emission",
    "receipt_projected": "13. `receipt_projected`",
    "sponsor_session_truth": "* sponsor-session truth",
    "raw_auth_lane_local": "* raw Codex/OpenAI auth material stays lane-local on Fleet",
}
OWNERSHIP_MARKERS = {
    "lane_local_auth": "* lane-local auth/cache storage on the execution host",
    "sponsor_metadata": "* sponsor-session execution metadata on participant lanes",
    "signed_receipts": "* signed contribution receipts emitted from meaningful execution events",
}
FLEET_PROJECT_MARKERS = {
    "lane_local_auth": "* lane-local worker auth/cache state on the execution host",
    "sponsor_metadata": "* sponsor-session execution metadata on participant lanes",
    "signed_receipts": "* signed contribution receipts emitted back to Hub after meaningful work",
}
HUB_PROJECT_MARKERS = {
    "receipt_ingest": "5. Fleet receipt ingest and sponsor-session projections",
    "reward_rule": "Rewards must be derived from validated Fleet contribution receipts, not from merely redeeming a code or completing device auth.",
    "sponsor_status": "* participation consent and sponsor-session status",
}
AGENT_MARKERS = {
    "lane_local_caches": "those caches must stay lane-local on the execution host.",
    "hub_truth_boundary": "Fleet may emit signed contribution receipts and hold sponsor-session execution metadata, but Hub remains the source of truth for accounts, groups, rewards, and entitlements.",
}
ARTIFACT_KEYWORDS = (
    "sponsor-session",
    "contribution receipt",
    "receipt_projected",
    "recognition_projected",
    "participant lane",
    "lane-local",
)


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize the Fleet M129 participation-lane receipt packet.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--markdown-output", default=str(DEFAULT_MARKDOWN))
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--queue-staging", default=str(QUEUE_STAGING))
    parser.add_argument("--design-queue-staging", default=str(DESIGN_QUEUE_STAGING))
    parser.add_argument("--next90-guide", default=str(NEXT90_GUIDE))
    parser.add_argument("--adr", default=str(ADR_PATH))
    parser.add_argument("--workflow", default=str(WORKFLOW_PATH))
    parser.add_argument("--ownership-matrix", default=str(OWNERSHIP_MATRIX))
    parser.add_argument("--fleet-project", default=str(FLEET_PROJECT))
    parser.add_argument("--hub-project", default=str(HUB_PROJECT))
    parser.add_argument("--fleet-agent-template", default=str(FLEET_AGENT_TEMPLATE))
    parser.add_argument("--status-plane", default=str(STATUS_PLANE))
    parser.add_argument("--fleet-published-root", default=str(FLEET_PUBLISHED_ROOT))
    parser.add_argument("--hub-published-root", default=str(HUB_PUBLISHED_ROOT))
    parser.add_argument("--registry-published-root", default=str(REGISTRY_PUBLISHED_ROOT))
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
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
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
        "generated_at": _normalize_text(payload.get("generated_at") or payload.get("generatedAt")),
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


def _queue_rows_for_milestone(queue: Dict[str, Any], milestone_id: int) -> List[Dict[str, Any]]:
    return [
        dict(row)
        for row in (queue.get("items") or [])
        if isinstance(row, dict) and int(row.get("milestone_id") or 0) == milestone_id
    ]


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


def _age_seconds(value: str, *, now: dt.datetime) -> int | None:
    parsed = _parse_iso_utc(value)
    if parsed is None:
        return None
    return max(0, int((now - parsed).total_seconds()))


def _marker_monitor(text: str, markers: Dict[str, str], *, label: str) -> Dict[str, Any]:
    checks = {name: marker in text for name, marker in markers.items()}
    issues = [f"{label} missing required marker: {name}" for name, present in checks.items() if not present]
    return {"state": "pass" if not issues else "fail", "checks": checks, "issues": issues}


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
        issues.append("Canonical registry milestone dependencies drifted from M129 requirement set.")
    return {
        "state": "pass" if not issues else "fail",
        "issues": issues,
        "fleet_queue_status": _normalize_text(queue_item.get("status")),
        "design_queue_status": _normalize_text(design_queue_item.get("status")),
        "registry_status": _normalize_text(milestone.get("status")),
        "work_task_status": _normalize_text(work_task.get("status")),
    }


def _queue_coverage_monitor(
    *,
    milestone: Dict[str, Any],
    queue_payload: Dict[str, Any],
    design_queue_payload: Dict[str, Any],
) -> Dict[str, Any]:
    issues: List[str] = []
    runtime_blockers: List[str] = []
    warnings: List[str] = []
    work_tasks = [dict(row) for row in (milestone.get("work_tasks") or []) if isinstance(row, dict)]
    queue_rows = _queue_rows_for_milestone(queue_payload, MILESTONE_ID)
    design_queue_rows = _queue_rows_for_milestone(design_queue_payload, MILESTONE_ID)
    ready_count = 0
    rows: List[Dict[str, Any]] = []
    for task in work_tasks:
        task_id = _normalize_text(task.get("id"))
        owner = _normalize_text(task.get("owner"))
        fleet_rows = [row for row in queue_rows if _normalize_text(row.get("work_task_id")) == task_id]
        design_rows = [row for row in design_queue_rows if _normalize_text(row.get("work_task_id")) == task_id]
        reasons: List[str] = []
        if not fleet_rows:
            reasons.append("fleet queue row missing")
        if not design_rows:
            reasons.append("design queue row missing")
        for row in fleet_rows + design_rows:
            if not _normalize_list(row.get("allowed_paths")):
                reasons.append(f"{_normalize_text(row.get('repo')) or 'queue'} row has empty allowed_paths")
            if not _normalize_list(row.get("owned_surfaces")):
                reasons.append(f"{_normalize_text(row.get('repo')) or 'queue'} row has empty owned_surfaces")
            if owner and _normalize_text(row.get("repo")) != owner:
                reasons.append(f"{_normalize_text(row.get('repo')) or 'queue'} row repo drifted from owner {owner}")
        if reasons:
            runtime_blockers.append(f"work task {task_id}: {', '.join(sorted(set(reasons)))}")
        else:
            ready_count += 1
        rows.append(
            {
                "work_task_id": task_id,
                "owner": owner,
                "title": _normalize_text(task.get("title")),
                "registry_status": _normalize_text(task.get("status")).lower() or "unknown",
                "queued_ready": not reasons,
                "reasons": sorted(set(reasons)),
            }
        )
    design_task = _find_work_task(milestone, DESIGN_CANON_TASK_ID)
    design_status = _normalize_text(design_task.get("status")).lower()
    if design_status not in DONE_STATUSES:
        runtime_blockers.append(
            f"design canon task {DESIGN_CANON_TASK_ID} is {design_status or 'unknown'}."
        )
    return {
        "state": "pass" if not issues else "fail",
        "expected_work_task_count": len(work_tasks),
        "queued_work_task_count": ready_count,
        "design_canon_task_id": DESIGN_CANON_TASK_ID,
        "design_canon_task_status": design_status or "unknown",
        "work_tasks": rows,
        "runtime_blockers": runtime_blockers,
        "warnings": warnings,
        "issues": issues,
    }


def _status_plane_monitor(*, milestone: Dict[str, Any], status_plane: Dict[str, Any], now: dt.datetime) -> Dict[str, Any]:
    issues: List[str] = []
    runtime_blockers: List[str] = []
    warnings: List[str] = []
    if not status_plane:
        issues.append("STATUS_PLANE.generated.yaml is missing or invalid.")
        return {
            "state": "fail",
            "missing_owner_project_ids": [],
            "runtime_blockers": runtime_blockers,
            "warnings": warnings,
            "issues": issues,
        }
    generated_at = _normalize_text(status_plane.get("generated_at"))
    age_seconds = _age_seconds(generated_at, now=now)
    if age_seconds is None:
        issues.append("status plane generated_at is missing or invalid.")
    elif age_seconds > STATUS_PLANE_FRESHNESS_HOURS * 3600:
        runtime_blockers.append(
            f"status plane freshness exceeded threshold ({age_seconds}s > {STATUS_PLANE_FRESHNESS_HOURS * 3600}s)."
        )
    project_rows = {
        _normalize_text(row.get("id")): dict(row)
        for row in status_plane.get("projects") or []
        if isinstance(row, dict) and _normalize_text(row.get("id"))
    }
    expected_project_ids = sorted(
        {
            REPO_TO_STATUS_PLANE_ID.get(owner, owner)
            for owner in _normalize_list(milestone.get("owners"))
            if REPO_TO_STATUS_PLANE_ID.get(owner, owner)
        }
    )
    missing_owner_project_ids = sorted(set(expected_project_ids) - set(project_rows))
    if missing_owner_project_ids:
        runtime_blockers.append(
            "status plane is missing owner project row(s): " + ", ".join(missing_owner_project_ids)
        )
    return {
        "state": "pass" if not issues else "fail",
        "generated_at": generated_at,
        "age_hours": None if age_seconds is None else round(age_seconds / 3600.0, 2),
        "expected_owner_project_ids": expected_project_ids,
        "missing_owner_project_ids": missing_owner_project_ids,
        "whole_product_final_claim_status": _normalize_text(status_plane.get("whole_product_final_claim_status")),
        "runtime_blockers": runtime_blockers,
        "warnings": warnings,
        "issues": issues,
    }


def _receipt_artifact_monitor(search_roots: List[Path]) -> Dict[str, Any]:
    issues: List[str] = []
    runtime_blockers: List[str] = []
    warnings: List[str] = []
    excluded_matches = {
        _display_path(DEFAULT_OUTPUT),
        _display_path(DEFAULT_MARKDOWN),
    }
    existing_roots = [str(path) for path in search_roots if path.exists()]
    if not existing_roots:
        runtime_blockers.append("No published sponsor-session or contribution-receipt artifact is currently discoverable.")
        warnings.append("No published roots exist for participation receipt scanning.")
        return {
            "state": "pass",
            "match_count": 0,
            "matches": [],
            "runtime_blockers": runtime_blockers,
            "warnings": warnings,
            "issues": issues,
        }
    pattern = "|".join(ARTIFACT_KEYWORDS)
    result = subprocess.run(
        ["rg", "-l", "-i", pattern, *existing_roots],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode not in {0, 1}:
        issues.append(f"receipt artifact scan failed: {result.stderr.strip() or 'unknown rg error'}")
        matches: List[str] = []
    else:
        matches = sorted(
            {
                line.strip()
                for line in (result.stdout or "").splitlines()
                if line.strip() and line.strip() not in excluded_matches
            }
        )
    if not matches:
        runtime_blockers.append("No published sponsor-session or contribution-receipt artifact is currently discoverable.")
    return {
        "state": "pass" if not issues else "fail",
        "match_count": len(matches),
        "matches": matches[:20],
        "runtime_blockers": runtime_blockers,
        "warnings": warnings,
        "issues": issues,
    }


def build_payload(
    *,
    registry_path: Path,
    queue_path: Path,
    design_queue_path: Path,
    next90_guide_path: Path,
    adr_path: Path,
    workflow_path: Path,
    ownership_matrix_path: Path,
    fleet_project_path: Path,
    hub_project_path: Path,
    fleet_agent_template_path: Path,
    status_plane_path: Path,
    fleet_published_root: Path,
    hub_published_root: Path,
    registry_published_root: Path,
    generated_at: str | None = None,
) -> Dict[str, Any]:
    generated_at = generated_at or _utc_now()
    registry = _read_yaml(registry_path)
    queue = _read_yaml(queue_path)
    design_queue = _read_yaml(design_queue_path)
    next90_guide = _read_text(next90_guide_path)
    adr_text = _read_text(adr_path)
    workflow_text = _read_text(workflow_path)
    ownership_text = _read_text(ownership_matrix_path)
    fleet_project_text = _read_text(fleet_project_path)
    hub_project_text = _read_text(hub_project_path)
    fleet_agent_template_text = _read_text(fleet_agent_template_path)
    status_plane = _read_yaml(status_plane_path)
    reference_now = _parse_iso_utc(generated_at) or dt.datetime.now(dt.timezone.utc)

    milestone = _find_milestone(registry, MILESTONE_ID)
    work_task = _find_work_task(milestone, WORK_TASK_ID)
    queue_item = _find_queue_item(queue, PACKAGE_ID)
    design_queue_item = _find_queue_item(design_queue, PACKAGE_ID)

    canonical_alignment = _queue_alignment(queue_item, design_queue_item, work_task, milestone)
    guide_monitor = _marker_monitor(next90_guide, GUIDE_MARKERS, label="Next90 guide canon")
    adr_monitor = _marker_monitor(adr_text, ADR_MARKERS, label="Participation ADR canon")
    workflow_monitor = _marker_monitor(workflow_text, WORKFLOW_MARKERS, label="Participation workflow canon")
    ownership_monitor = _marker_monitor(ownership_text, OWNERSHIP_MARKERS, label="Ownership matrix canon")
    fleet_project_monitor = _marker_monitor(fleet_project_text, FLEET_PROJECT_MARKERS, label="Fleet project canon")
    hub_project_monitor = _marker_monitor(hub_project_text, HUB_PROJECT_MARKERS, label="Hub project canon")
    agent_monitor = _marker_monitor(
        fleet_agent_template_text,
        AGENT_MARKERS,
        label="Fleet review template canon",
    )

    queue_coverage_monitor = _queue_coverage_monitor(
        milestone=milestone,
        queue_payload=queue,
        design_queue_payload=design_queue,
    )
    status_plane_monitor = _status_plane_monitor(
        milestone=milestone,
        status_plane=status_plane,
        now=reference_now,
    )
    artifact_monitor = _receipt_artifact_monitor(
        [fleet_published_root, hub_published_root, registry_published_root]
    )

    blockers: List[str] = []
    runtime_blockers: List[str] = []
    warnings: List[str] = []
    for section_name, section in (
        ("canonical_alignment", canonical_alignment),
        ("next90_guide", guide_monitor),
        ("adr", adr_monitor),
        ("workflow", workflow_monitor),
        ("ownership_matrix", ownership_monitor),
        ("fleet_project", fleet_project_monitor),
        ("hub_project", hub_project_monitor),
        ("fleet_agent_template", agent_monitor),
        ("queue_coverage_monitor", queue_coverage_monitor),
        ("status_plane_monitor", status_plane_monitor),
        ("artifact_monitor", artifact_monitor),
    ):
        for issue in section.get("issues") or []:
            blockers.append(f"{section_name}: {issue}")
        for runtime_blocker in section.get("runtime_blockers") or []:
            runtime_blockers.append(f"{section_name}: {runtime_blocker}")
        warnings.extend(section.get("warnings") or [])

    participation_status = "blocked" if runtime_blockers else "warning" if warnings else "pass"
    return {
        "contract_name": "fleet.next90_m129_participation_lane_receipts",
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
            "adr": adr_monitor,
            "workflow": workflow_monitor,
            "ownership_matrix": ownership_monitor,
            "fleet_project": fleet_project_monitor,
            "hub_project": hub_project_monitor,
            "fleet_agent_template": agent_monitor,
        },
        "runtime_monitors": {
            "queue_coverage": queue_coverage_monitor,
            "status_plane": status_plane_monitor,
            "receipt_artifacts": artifact_monitor,
        },
        "monitor_summary": {
            "participation_status": participation_status,
            "queued_work_task_count": queue_coverage_monitor.get("queued_work_task_count"),
            "expected_work_task_count": queue_coverage_monitor.get("expected_work_task_count"),
            "receipt_artifact_match_count": artifact_monitor.get("match_count"),
            "missing_status_plane_project_count": len(status_plane_monitor.get("missing_owner_project_ids") or []),
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
            "queue_staging": _source_link(queue_path, queue),
            "design_queue_staging": _source_link(design_queue_path, design_queue),
            "next90_guide": _text_source_link(next90_guide_path),
            "adr": _text_source_link(adr_path),
            "workflow": _text_source_link(workflow_path),
            "ownership_matrix": _text_source_link(ownership_matrix_path),
            "fleet_project": _text_source_link(fleet_project_path),
            "hub_project": _text_source_link(hub_project_path),
            "fleet_agent_template": _text_source_link(fleet_agent_template_path),
            "status_plane": _source_link(status_plane_path, status_plane),
            "fleet_published_root": _text_source_link(fleet_published_root),
            "hub_published_root": _text_source_link(hub_published_root),
            "registry_published_root": _text_source_link(registry_published_root),
        },
    }


def render_markdown(payload: Dict[str, Any]) -> str:
    summary = dict(payload.get("monitor_summary") or {})
    closeout = dict(payload.get("package_closeout") or {})
    lines = [
        "# Fleet M129 participation lane receipts",
        "",
        f"- status: {payload.get('status')}",
        f"- participation_status: {summary.get('participation_status')}",
        f"- package_id: {payload.get('package_id')}",
        f"- frontier_id: {payload.get('frontier_id')}",
        f"- generated_at: {payload.get('generated_at')}",
        "",
        "## Runtime summary",
        f"- queued_work_task_count: {summary.get('queued_work_task_count')} / {summary.get('expected_work_task_count')}",
        f"- receipt_artifact_match_count: {summary.get('receipt_artifact_match_count')}",
        f"- missing_status_plane_project_count: {summary.get('missing_status_plane_project_count')}",
        f"- runtime_blocker_count: {summary.get('runtime_blocker_count')}",
        f"- warning_count: {summary.get('warning_count')}",
        "",
        "## Package closeout",
        f"- state: {closeout.get('state') or 'blocked'}",
    ]
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
        next90_guide_path=Path(args.next90_guide).resolve(),
        adr_path=Path(args.adr).resolve(),
        workflow_path=Path(args.workflow).resolve(),
        ownership_matrix_path=Path(args.ownership_matrix).resolve(),
        fleet_project_path=Path(args.fleet_project).resolve(),
        hub_project_path=Path(args.hub_project).resolve(),
        fleet_agent_template_path=Path(args.fleet_agent_template).resolve(),
        status_plane_path=Path(args.status_plane).resolve(),
        fleet_published_root=Path(args.fleet_published_root).resolve(),
        hub_published_root=Path(args.hub_published_root).resolve(),
        registry_published_root=Path(args.registry_published_root).resolve(),
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
