#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List

import yaml


ROOT = Path("/docker/fleet")
PUBLISHED = ROOT / ".codex-studio" / "published"
PRODUCT_MIRROR = Path("/docker/chummercomplete/chummer-design/products/chummer")

PACKAGE_ID = "next90-m135-fleet-add-full-design-queued-coverage-verification-mirror-fres"
FRONTIER_ID = 7361549676
MILESTONE_ID = 135
WORK_TASK_ID = "135.2"
DESIGN_COVERAGE_TASK_ID = "135.1"
WAVE_ID = "W22"
QUEUE_TITLE = "Add full-design queued-coverage verification, mirror freshness checks, missing-row detection, and status-plane reporting."
QUEUE_TASK = QUEUE_TITLE
WORK_TASK_TITLE = QUEUE_TITLE
WORK_TASK_DEPENDENCIES = [127, 128, 129, 130, 131, 132, 133, 134]
OWNED_SURFACES = ["add_full_design_queued_coverage:fleet"]
ALLOWED_PATHS = ["scripts", "tests", ".codex-studio", "feedback"]

DEFAULT_OUTPUT = PUBLISHED / "NEXT90_M135_FLEET_DESIGN_QUEUED_COVERAGE.generated.json"
DEFAULT_MARKDOWN = PUBLISHED / "NEXT90_M135_FLEET_DESIGN_QUEUED_COVERAGE.generated.md"

SUCCESSOR_REGISTRY = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
QUEUE_STAGING = PUBLISHED / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
DESIGN_QUEUE_STAGING = PRODUCT_MIRROR / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
NEXT90_GUIDE = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_GUIDE.md"
SYNC_MANIFEST = PRODUCT_MIRROR / "sync" / "sync-manifest.yaml"
MIRROR_BACKLOG = PRODUCT_MIRROR / "sync" / "LOCAL_MIRROR_PUBLISH_BACKLOG.md"
MIRROR_EVIDENCE = PRODUCT_MIRROR / "sync" / "LOCAL_MIRROR_PUBLISH_EVIDENCE.md"
PROGRAM_MILESTONES = PRODUCT_MIRROR / "PROGRAM_MILESTONES.yaml"
STATUS_PLANE = PUBLISHED / "STATUS_PLANE.generated.yaml"

STATUS_PLANE_FRESHNESS_HOURS = 24
DONE_STATUSES = {"complete", "completed", "done", "landed", "shipped"}
REPO_TO_STATUS_PLANE_ID = {
    "chummer6-design": "design",
    "fleet": "fleet",
    "chummer6-core": "core",
    "chummer6-hub": "hub",
    "chummer6-hub-registry": "hub-registry",
    "chummer6-ui": "ui",
    "chummer6-mobile": "mobile",
    "chummer6-ui-kit": "ui-kit",
    "chummer6-media-factory": "media-factory",
    "executive-assistant": "ea",
}
GUIDE_MARKERS = {
    "wave_22": "## Wave 22 - close backbone, contract, repo-boundary, and final design coverage",
    "milestone_135": "### 135. Product backbone, contract sets, ownership matrix, repo hygiene, and final design coverage closeout",
    "exit_contract": "Exit: every canonical design source family is implemented, explicitly non-goal/future-only, or represented by a repo-owned executable milestone with queue slice, allowed paths, proof gate, and stop condition.",
}
SYNC_MANIFEST_REQUIRED_GROUPS = {
    "base_governance",
    "horizons",
    "public_surface",
    "release",
    "support_plane",
    "external_tools",
}
ISO_TIMESTAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize the Fleet M135 design queued-coverage packet.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--markdown-output", default=str(DEFAULT_MARKDOWN))
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--queue-staging", default=str(QUEUE_STAGING))
    parser.add_argument("--design-queue-staging", default=str(DESIGN_QUEUE_STAGING))
    parser.add_argument("--next90-guide", default=str(NEXT90_GUIDE))
    parser.add_argument("--sync-manifest", default=str(SYNC_MANIFEST))
    parser.add_argument("--mirror-backlog", default=str(MIRROR_BACKLOG))
    parser.add_argument("--mirror-evidence", default=str(MIRROR_EVIDENCE))
    parser.add_argument("--program-milestones", default=str(PROGRAM_MILESTONES))
    parser.add_argument("--status-plane", default=str(STATUS_PLANE))
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
        if "\nitems:\n" not in raw:
            return {}
        try:
            payload = yaml.safe_load("items:\n" + raw.split("\nitems:\n", 1)[1]) or {}
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


def _parse_date_utc(value: str) -> dt.datetime | None:
    text = _normalize_text(value)
    if not text:
        return None
    try:
        return dt.datetime.fromisoformat(text).replace(tzinfo=dt.timezone.utc)
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
        issues.append("Canonical registry milestone dependencies drifted from M135 requirement set.")
    return {
        "state": "pass" if not issues else "fail",
        "issues": issues,
        "fleet_queue_status": _normalize_text(queue_item.get("status")),
        "design_queue_status": _normalize_text(design_queue_item.get("status")),
        "registry_status": _normalize_text(milestone.get("status")),
        "work_task_status": _normalize_text(work_task.get("status")),
    }


def _sync_manifest_monitor(payload: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    source_groups = dict(payload.get("product_source_groups") or {})
    group_names = sorted(name for name in source_groups if _normalize_text(name))
    if _normalize_text(payload.get("canonical_source_repo")) != "chummer6-design":
        issues.append("sync-manifest canonical_source_repo drifted away from chummer6-design.")
    for group_name in sorted(SYNC_MANIFEST_REQUIRED_GROUPS):
        if group_name not in source_groups:
            issues.append(f"sync-manifest is missing required source family group `{group_name}`.")
    return {
        "state": "pass" if not issues else "fail",
        "source_family_group_count": len(group_names),
        "source_family_groups": group_names,
        "repo_alias_count": len(dict(payload.get("repo_root_aliases") or {})),
        "issues": issues,
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
    rows: List[Dict[str, Any]] = []
    queued_count = 0
    shipped_count = 0
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
            queued_count += 1
        status = _normalize_text(task.get("status")).lower()
        if status in DONE_STATUSES:
            shipped_count += 1
        rows.append(
            {
                "work_task_id": task_id,
                "owner": owner,
                "title": _normalize_text(task.get("title")),
                "registry_status": status or "unknown",
                "queued_in_fleet": bool(fleet_rows),
                "queued_in_design": bool(design_rows),
                "queued_ready": not reasons,
                "reasons": sorted(set(reasons)),
            }
        )
    design_coverage_task = _find_work_task(milestone, DESIGN_COVERAGE_TASK_ID)
    design_coverage_status = _normalize_text(design_coverage_task.get("status")).lower()
    design_coverage_done = design_coverage_status in DONE_STATUSES
    if not design_coverage_done:
        runtime_blockers.append(
            f"design coverage ledger task {DESIGN_COVERAGE_TASK_ID} is {design_coverage_status or 'unknown'}."
        )
    if shipped_count == 0:
        warnings.append("Milestone 135 currently has queued coverage but no shipped closeout tasks yet.")
    return {
        "state": "pass" if not issues else "fail",
        "expected_work_task_count": len(work_tasks),
        "queued_work_task_count": queued_count,
        "shipped_work_task_count": shipped_count,
        "design_coverage_task_id": DESIGN_COVERAGE_TASK_ID,
        "design_coverage_task_status": design_coverage_status or "unknown",
        "design_coverage_task_done": design_coverage_done,
        "work_tasks": rows,
        "runtime_blockers": runtime_blockers,
        "warnings": warnings,
        "issues": issues,
    }


def _parse_markdown_table_rows(text: str, *, prefix: str) -> List[List[str]]:
    rows: List[List[str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith(f"| {prefix}"):
            continue
        parts = [part.strip() for part in stripped.split("|")[1:-1]]
        if parts:
            rows.append(parts)
    return rows


def _latest_evidence_timestamp(text: str) -> str:
    timestamps = [_parse_iso_utc(match.group(0)) for match in ISO_TIMESTAMP_RE.finditer(text)]
    valid = [value for value in timestamps if value is not None]
    if not valid:
        return ""
    latest = max(valid)
    return latest.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _mirror_freshness_monitor(
    *,
    milestone: Dict[str, Any],
    sync_manifest: Dict[str, Any],
    mirror_backlog_text: str,
    mirror_evidence_text: str,
    program_milestones: Dict[str, Any],
    program_milestones_path: Path,
) -> Dict[str, Any]:
    issues: List[str] = []
    runtime_blockers: List[str] = []
    warnings: List[str] = []

    expected_repos = sorted(
        owner for owner in _normalize_list(milestone.get("owners")) if owner and owner != "chummer6-design"
    )
    backlog_rows = _parse_markdown_table_rows(mirror_backlog_text, prefix="WL-D008-")
    evidence_rows = _parse_markdown_table_rows(mirror_evidence_text, prefix="WL-D008-")
    backlog_repos = {row[2] for row in backlog_rows if len(row) >= 3}
    evidence_repos = {row[1] for row in evidence_rows if len(row) >= 2}
    missing_backlog_repos = sorted(set(expected_repos) - backlog_repos)
    missing_evidence_repos = sorted(set(expected_repos) - evidence_repos)
    if missing_backlog_repos:
        runtime_blockers.append(
            "mirror backlog is missing repo row(s): " + ", ".join(missing_backlog_repos)
        )
    if missing_evidence_repos:
        runtime_blockers.append(
            "mirror evidence is missing repo row(s): " + ", ".join(missing_evidence_repos)
        )

    program_milestones_last_reviewed = _normalize_text(program_milestones.get("last_reviewed"))
    program_milestones_last_reviewed_at = _parse_date_utc(program_milestones_last_reviewed)
    latest_evidence_at = _latest_evidence_timestamp(mirror_evidence_text)
    latest_evidence_dt = _parse_iso_utc(latest_evidence_at)
    if program_milestones_last_reviewed_at and latest_evidence_dt and latest_evidence_dt < program_milestones_last_reviewed_at:
        runtime_blockers.append(
            f"mirror evidence is older than PROGRAM_MILESTONES last_reviewed ({latest_evidence_at} < {program_milestones_last_reviewed})."
        )

    current_program_sha = _sha256_file(program_milestones_path)
    observed_source_shas = {
        row[3].strip("`")
        for row in evidence_rows
        if len(row) >= 4 and row[3].strip("`")
    }
    if current_program_sha and current_program_sha not in observed_source_shas:
        runtime_blockers.append(
            "mirror evidence does not cover the current PROGRAM_MILESTONES checksum."
        )

    recurring_rows = _parse_markdown_table_rows(mirror_backlog_text, prefix="WL-D018-")
    recurring_statuses = [_normalize_text(row[1]).lower() for row in recurring_rows if len(row) >= 2]
    if recurring_statuses and all(status == "queued" for status in recurring_statuses):
        warnings.append("Recurring WL-D018 mirror backlog is still fully queued.")

    repo_alias_count = len(dict(sync_manifest.get("repo_root_aliases") or {}))
    return {
        "state": "pass" if not issues else "fail",
        "expected_repo_count": len(expected_repos),
        "expected_repos": expected_repos,
        "backlog_repo_count": len(backlog_repos),
        "evidence_repo_count": len(evidence_repos),
        "repo_alias_count": repo_alias_count,
        "missing_backlog_repos": missing_backlog_repos,
        "missing_evidence_repos": missing_evidence_repos,
        "program_milestones_last_reviewed": program_milestones_last_reviewed,
        "latest_evidence_at": latest_evidence_at,
        "current_program_milestones_sha256": current_program_sha,
        "observed_program_milestones_source_sha256_count": len(observed_source_shas),
        "recurring_statuses": recurring_statuses,
        "runtime_blockers": runtime_blockers,
        "warnings": warnings,
        "issues": issues,
    }


def _status_plane_monitor(
    *,
    milestone: Dict[str, Any],
    status_plane: Dict[str, Any],
    now: dt.datetime,
) -> Dict[str, Any]:
    issues: List[str] = []
    runtime_blockers: List[str] = []
    warnings: List[str] = []
    if not status_plane:
        issues.append("STATUS_PLANE.generated.yaml is missing or invalid.")
        return {
            "state": "fail",
            "project_count": 0,
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
            if owner != "chummer6-design" or REPO_TO_STATUS_PLANE_ID.get(owner)
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
        "project_count": len(project_rows),
        "expected_owner_project_ids": expected_project_ids,
        "missing_owner_project_ids": missing_owner_project_ids,
        "whole_product_final_claim_status": _normalize_text(status_plane.get("whole_product_final_claim_status")),
        "whole_product_final_claim_ready": int(status_plane.get("whole_product_final_claim_ready") or 0),
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
    sync_manifest_path: Path,
    mirror_backlog_path: Path,
    mirror_evidence_path: Path,
    program_milestones_path: Path,
    status_plane_path: Path,
    generated_at: str | None = None,
) -> Dict[str, Any]:
    generated_at = generated_at or _utc_now()
    registry = _read_yaml(registry_path)
    queue = _read_yaml(queue_path)
    design_queue = _read_yaml(design_queue_path)
    next90_guide = _read_text(next90_guide_path)
    sync_manifest = _read_yaml(sync_manifest_path)
    mirror_backlog_text = _read_text(mirror_backlog_path)
    mirror_evidence_text = _read_text(mirror_evidence_path)
    program_milestones = _read_yaml(program_milestones_path)
    status_plane = _read_yaml(status_plane_path)
    reference_now = _parse_iso_utc(generated_at) or dt.datetime.now(dt.timezone.utc)

    milestone = _find_milestone(registry, MILESTONE_ID)
    work_task = _find_work_task(milestone, WORK_TASK_ID)
    queue_item = _find_queue_item(queue, PACKAGE_ID)
    design_queue_item = _find_queue_item(design_queue, PACKAGE_ID)

    canonical_alignment = _queue_alignment(queue_item, design_queue_item, work_task, milestone)
    guide_monitor = _marker_monitor(next90_guide, GUIDE_MARKERS, label="Next90 guide canon")
    sync_manifest_monitor = _sync_manifest_monitor(sync_manifest)
    queue_coverage_monitor = _queue_coverage_monitor(
        milestone=milestone,
        queue_payload=queue,
        design_queue_payload=design_queue,
    )
    mirror_monitor = _mirror_freshness_monitor(
        milestone=milestone,
        sync_manifest=sync_manifest,
        mirror_backlog_text=mirror_backlog_text,
        mirror_evidence_text=mirror_evidence_text,
        program_milestones=program_milestones,
        program_milestones_path=program_milestones_path,
    )
    status_plane_monitor = _status_plane_monitor(
        milestone=milestone,
        status_plane=status_plane,
        now=reference_now,
    )

    blockers: List[str] = []
    runtime_blockers: List[str] = []
    warnings: List[str] = []
    for section_name, section in (
        ("canonical_alignment", canonical_alignment),
        ("next90_guide", guide_monitor),
        ("sync_manifest", sync_manifest_monitor),
        ("queue_coverage_monitor", queue_coverage_monitor),
        ("mirror_freshness_monitor", mirror_monitor),
        ("status_plane_monitor", status_plane_monitor),
    ):
        for issue in section.get("issues") or []:
            blockers.append(f"{section_name}: {issue}")
        for runtime_blocker in section.get("runtime_blockers") or []:
            runtime_blockers.append(f"{section_name}: {runtime_blocker}")
        warnings.extend(section.get("warnings") or [])

    design_coverage_status = "blocked" if runtime_blockers else "warning" if warnings else "pass"

    return {
        "contract_name": "fleet.next90_m135_design_queued_coverage",
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
            "sync_manifest": sync_manifest_monitor,
        },
        "runtime_monitors": {
            "queue_coverage": queue_coverage_monitor,
            "mirror_freshness": mirror_monitor,
            "status_plane": status_plane_monitor,
        },
        "monitor_summary": {
            "design_coverage_status": design_coverage_status,
            "source_family_group_count": sync_manifest_monitor.get("source_family_group_count"),
            "queued_work_task_count": queue_coverage_monitor.get("queued_work_task_count"),
            "expected_work_task_count": queue_coverage_monitor.get("expected_work_task_count"),
            "shipped_work_task_count": queue_coverage_monitor.get("shipped_work_task_count"),
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
            "sync_manifest": _source_link(sync_manifest_path, sync_manifest),
            "mirror_backlog": _text_source_link(mirror_backlog_path),
            "mirror_evidence": _text_source_link(mirror_evidence_path),
            "program_milestones": _source_link(program_milestones_path, program_milestones),
            "status_plane": _source_link(status_plane_path, status_plane),
        },
    }


def render_markdown(payload: Dict[str, Any]) -> str:
    summary = dict(payload.get("monitor_summary") or {})
    closeout = dict(payload.get("package_closeout") or {})
    lines = [
        "# Fleet M135 design queued coverage",
        "",
        f"- status: {payload.get('status')}",
        f"- design_coverage_status: {summary.get('design_coverage_status')}",
        f"- package_id: {payload.get('package_id')}",
        f"- frontier_id: {payload.get('frontier_id')}",
        f"- generated_at: {payload.get('generated_at')}",
        "",
        "## Runtime summary",
        f"- source_family_group_count: {summary.get('source_family_group_count')}",
        f"- queued_work_task_count: {summary.get('queued_work_task_count')} / {summary.get('expected_work_task_count')}",
        f"- shipped_work_task_count: {summary.get('shipped_work_task_count')}",
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
        sync_manifest_path=Path(args.sync_manifest).resolve(),
        mirror_backlog_path=Path(args.mirror_backlog).resolve(),
        mirror_evidence_path=Path(args.mirror_evidence).resolve(),
        program_milestones_path=Path(args.program_milestones).resolve(),
        status_plane_path=Path(args.status_plane).resolve(),
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
