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

PACKAGE_ID = "next90-m127-fleet-promote-platform-acceptance-release-evidence-packs-repo"
FRONTIER_ID = 6924107419
MILESTONE_ID = 127
WORK_TASK_ID = "127.4"
WAVE_ID = "W18"
QUEUE_TITLE = "Promote platform acceptance, release evidence packs, repo hardening, and external-host proof orchestration into repeatable gates."
QUEUE_TASK = QUEUE_TITLE
WORK_TASK_TITLE = QUEUE_TITLE
WORK_TASK_DEPENDENCIES = [101, 102, 120]
OWNED_SURFACES = ["promote_platform_acceptance_release_evidence:fleet"]
ALLOWED_PATHS = ["scripts", "tests", ".codex-studio", "feedback"]

DEFAULT_OUTPUT = PUBLISHED / "NEXT90_M127_FLEET_RELEASE_TRUTH_GATES.generated.json"
DEFAULT_MARKDOWN = PUBLISHED / "NEXT90_M127_FLEET_RELEASE_TRUTH_GATES.generated.md"

SUCCESSOR_REGISTRY = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
QUEUE_STAGING = PUBLISHED / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
DESIGN_QUEUE_STAGING = PRODUCT_MIRROR / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
NEXT90_GUIDE = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_GUIDE.md"
ACCEPTANCE_MATRIX = PRODUCT_MIRROR / "DESKTOP_PLATFORM_ACCEPTANCE_MATRIX.yaml"
PUBLIC_DOWNLOADS_POLICY = PRODUCT_MIRROR / "PUBLIC_DOWNLOADS_POLICY.md"
PUBLIC_AUTO_UPDATE_POLICY = PRODUCT_MIRROR / "PUBLIC_AUTO_UPDATE_POLICY.md"
REPO_HARDENING_CHECKLIST = PRODUCT_MIRROR / "REPO_HARDENING_CHECKLIST.yaml"
REPO_HYGIENE_POLICY = PRODUCT_MIRROR / "REPO_HYGIENE_RELEASE_TRUST_AND_AUTOMATION_SAFETY.md"
EXTERNAL_PROOF_RUNBOOK = PUBLISHED / "EXTERNAL_PROOF_RUNBOOK.generated.md"
FLAGSHIP_PRODUCT_READINESS = PUBLISHED / "FLAGSHIP_PRODUCT_READINESS.generated.json"

GUIDE_MARKERS = {
    "wave_18": "## Wave 18 - finish release operations, localization, privacy, and support trust",
    "milestone_127": "### 127. Release pipeline, updater, platform acceptance, and public downloads completion",
    "release_truth_chain": "release, installer, updater, rollback, revoke, download, proof shelf, platform acceptance, and public channel surfaces compile from one release-truth chain.",
}
DOWNLOADS_MARKERS = {
    "authority": "`chummer.run` is the only official client download source.",
    "proof_shelf": "The downloads surface is a proof shelf first:",
    "fallback_labels": "label secondary heads, archives, and manual packages as fallback or recovery paths",
}
AUTO_UPDATE_MARKERS = {
    "public_promises": "Public copy may promise:",
    "paused_rollout": "`paused rollout`",
    "registry_truth": "Registry owns promoted desktop head and update-feed truth.",
    "fixed_rule": "The phrase `fixed` is user-safe only when the fix is actually available on that user's channel according to registry truth.",
}
REPO_HYGIENE_MARKERS = {
    "release_manifest_chain": "### 2. One signed release-manifest chain",
    "workflow_hardening": "### 4. GitHub Actions and workflow hardening",
    "blast_radius_limits": "### 7. Fleet blast-radius limits",
    "user_loops": "Golden user loops outrank feature sprawl.",
}
TARGET_HARDENING_INITIATIVES = ("RH-001", "RH-002", "RH-003", "RH-005", "RH-006")
REQUIRED_PLATFORM_IDS = ("windows", "linux", "macOS")


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize the Fleet M127 release-truth gate packet.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--markdown-output", default=str(DEFAULT_MARKDOWN))
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--queue-staging", default=str(QUEUE_STAGING))
    parser.add_argument("--design-queue-staging", default=str(DESIGN_QUEUE_STAGING))
    parser.add_argument("--next90-guide", default=str(NEXT90_GUIDE))
    parser.add_argument("--acceptance-matrix", default=str(ACCEPTANCE_MATRIX))
    parser.add_argument("--public-downloads-policy", default=str(PUBLIC_DOWNLOADS_POLICY))
    parser.add_argument("--public-auto-update-policy", default=str(PUBLIC_AUTO_UPDATE_POLICY))
    parser.add_argument("--repo-hardening-checklist", default=str(REPO_HARDENING_CHECKLIST))
    parser.add_argument("--repo-hygiene-policy", default=str(REPO_HYGIENE_POLICY))
    parser.add_argument("--external-proof-runbook", default=str(EXTERNAL_PROOF_RUNBOOK))
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


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


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
        issues.append("Canonical registry milestone dependencies drifted from M127 requirement set.")
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


def _platform_acceptance_monitor(payload: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    warnings: List[str] = []
    platform_rows = [dict(row) for row in (payload.get("platforms") or []) if isinstance(row, dict)]
    summary: Dict[str, Dict[str, Any]] = {}
    by_id = {_normalize_text(row.get("id")): row for row in platform_rows}
    for platform_id in REQUIRED_PLATFORM_IDS:
        row = by_id.get(platform_id)
        if not row:
            issues.append(f"Acceptance matrix is missing platform: {platform_id}")
            continue
        summary[platform_id] = {
            "public_shelf_status": _normalize_text(row.get("public_shelf_status")),
            "primary_package_kind": _normalize_text(row.get("primary_package_kind")),
            "startup_smoke_gate": _normalize_text(row.get("startup_smoke_gate")),
            "signing_posture": _normalize_text(row.get("signing_posture")),
            "updater_mode": _normalize_text(row.get("updater_mode")),
            "supportability": _normalize_text(row.get("supportability")),
        }
        for field in ("public_shelf_status", "primary_package_kind", "startup_smoke_gate", "signing_posture", "updater_mode"):
            if not _normalize_text(row.get(field)):
                issues.append(f"Acceptance matrix {platform_id} is missing {field}.")
        if not _normalize_text(row.get("public_shelf_status")).startswith("promoted"):
            warnings.append(
                f"Acceptance matrix keeps {platform_id} in {_normalize_text(row.get('public_shelf_status')) or 'unknown'} posture instead of a promoted public lane."
            )
    return {
        "state": "pass" if not issues else "fail",
        "platform_count": len(platform_rows),
        "platforms": summary,
        "issues": issues,
        "warnings": warnings,
    }


def _repo_hardening_monitor(checklist: Dict[str, Any], hygiene_text: str) -> Dict[str, Any]:
    issues: List[str] = []
    warnings: List[str] = []
    initiatives = [dict(row) for row in (checklist.get("initiatives") or []) if isinstance(row, dict)]
    by_id = {_normalize_text(row.get("id")): row for row in initiatives}
    target_rows: List[Dict[str, Any]] = []
    for initiative_id in TARGET_HARDENING_INITIATIVES:
        row = by_id.get(initiative_id)
        if not row:
            issues.append(f"Repo hardening checklist is missing initiative {initiative_id}.")
            continue
        target_rows.append(row)
        status = _normalize_text(row.get("status"))
        if status in {"proposed", "not_started"}:
            warnings.append(f"Repo hardening initiative {initiative_id} is still {status}.")
        owners = _normalize_list(row.get("owners"))
        if "fleet" not in owners:
            issues.append(f"Repo hardening initiative {initiative_id} no longer names fleet as an owner.")
    hygiene_marker_monitor = _marker_monitor(hygiene_text, REPO_HYGIENE_MARKERS, label="Repo hygiene canon")
    issues.extend(hygiene_marker_monitor.get("issues") or [])
    return {
        "state": "pass" if not issues else "fail",
        "target_initiative_ids": list(TARGET_HARDENING_INITIATIVES),
        "target_initiatives": [
            {
                "id": _normalize_text(row.get("id")),
                "title": _normalize_text(row.get("title")),
                "status": _normalize_text(row.get("status")),
                "owners": _normalize_list(row.get("owners")),
            }
            for row in target_rows
        ],
        "hygiene_marker_monitor": hygiene_marker_monitor,
        "issues": issues,
        "warnings": warnings,
    }


def _extract_runbook_field(text: str, key: str) -> str:
    prefix = f"- {key}:"
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith(prefix):
            continue
        return line.split(":", 1)[1].strip().strip("`")
    return ""


def _external_proof_runbook_monitor(text: str) -> Dict[str, Any]:
    issues: List[str] = []
    gate_failures: List[str] = []
    warnings: List[str] = []
    unresolved_request_count = _extract_runbook_field(text, "unresolved_request_count")
    command_bundle_sha256 = _extract_runbook_field(text, "command_bundle_sha256")
    capture_deadline_utc = _extract_runbook_field(text, "capture_deadline_utc")
    retained_host_lane_count = text.count("### Host:")
    has_retained_host_section = "## Retained Host Lanes" in text
    has_zero_backlog_note = "No unresolved external-proof requests are currently queued." in text

    if not unresolved_request_count:
        issues.append("External proof runbook is missing unresolved_request_count.")
    elif unresolved_request_count != "0":
        gate_failures.append("External proof runbook unresolved_request_count is not zero.")
    if not command_bundle_sha256:
        issues.append("External proof runbook is missing command_bundle_sha256.")
    if not capture_deadline_utc:
        warnings.append("External proof runbook capture_deadline_utc is missing.")
    if not has_retained_host_section:
        issues.append("External proof runbook is missing retained host lanes.")
    if retained_host_lane_count < 3:
        issues.append("External proof runbook does not retain all three host lanes.")
    return {
        "state": "pass" if not issues else "fail",
        "release_gate_status": "pass" if not gate_failures else "blocked",
        "generated_at": _extract_runbook_field(text, "generated_at"),
        "unresolved_request_count": int(unresolved_request_count or 0),
        "capture_deadline_utc": capture_deadline_utc,
        "command_bundle_sha256": command_bundle_sha256,
        "retained_host_lane_count": retained_host_lane_count,
        "has_zero_backlog_note": has_zero_backlog_note,
        "issues": issues,
        "gate_failures": gate_failures,
        "warnings": warnings,
    }


def _flagship_readiness_monitor(payload: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    gate_failures: List[str] = []
    warnings: List[str] = []
    external_host_proof = dict(payload.get("external_host_proof") or {})
    status = _normalize_text(payload.get("status")) or "unknown"
    scoped_status = _normalize_text(payload.get("scoped_status")) or "unknown"
    external_status = _normalize_text(external_host_proof.get("status")) or "unknown"
    unresolved_request_count = int(external_host_proof.get("unresolved_request_count") or 0)
    if status == "unknown":
        issues.append("Flagship readiness status is missing.")
    elif status != "pass":
        gate_failures.append(f"Flagship readiness status is {status}.")
    if scoped_status == "unknown":
        issues.append("Flagship readiness scoped_status is missing.")
    elif scoped_status != "pass":
        gate_failures.append(f"Flagship readiness scoped_status is {scoped_status}.")
    if external_status == "unknown":
        issues.append("Flagship readiness external_host_proof.status is missing.")
    elif external_status != "pass":
        gate_failures.append(f"Flagship readiness external_host_proof.status is {external_status}.")
    if unresolved_request_count != 0:
        gate_failures.append("Flagship readiness still reports unresolved external host proof.")
    if not _normalize_text(external_host_proof.get("command_bundle_sha256")):
        issues.append("Flagship readiness external_host_proof.command_bundle_sha256 is missing.")
    warning_keys = payload.get("warning_keys") or []
    if isinstance(warning_keys, list) and warning_keys:
        warnings.append(f"Flagship readiness still carries {len(warning_keys)} warning key(s).")
    return {
        "state": "pass" if not issues else "fail",
        "release_gate_status": "pass" if not gate_failures else "blocked",
        "status": status,
        "scoped_status": scoped_status,
        "external_host_proof_status": external_status,
        "external_host_proof": {
            "unresolved_request_count": unresolved_request_count,
            "runbook_generated_at": _normalize_text(external_host_proof.get("runbook_generated_at")),
            "command_bundle_sha256": _normalize_text(external_host_proof.get("command_bundle_sha256")),
            "runbook_synced": bool(external_host_proof.get("runbook_synced")),
        },
        "issues": issues,
        "gate_failures": gate_failures,
        "warnings": warnings,
    }


def build_payload(
    *,
    registry_path: Path,
    queue_path: Path,
    design_queue_path: Path,
    next90_guide_path: Path,
    acceptance_matrix_path: Path,
    public_downloads_policy_path: Path,
    public_auto_update_policy_path: Path,
    repo_hardening_checklist_path: Path,
    repo_hygiene_policy_path: Path,
    external_proof_runbook_path: Path,
    flagship_product_readiness_path: Path,
    generated_at: str | None = None,
) -> Dict[str, Any]:
    generated_at = generated_at or _utc_now()
    registry = _read_yaml(registry_path)
    queue = _read_yaml(queue_path)
    design_queue = _read_yaml(design_queue_path)
    next90_guide = _read_text(next90_guide_path)
    acceptance_matrix = _read_yaml(acceptance_matrix_path)
    public_downloads_policy = _read_text(public_downloads_policy_path)
    public_auto_update_policy = _read_text(public_auto_update_policy_path)
    repo_hardening_checklist = _read_yaml(repo_hardening_checklist_path)
    repo_hygiene_policy = _read_text(repo_hygiene_policy_path)
    external_proof_runbook = _read_text(external_proof_runbook_path)
    flagship_product_readiness = _read_json(flagship_product_readiness_path)

    milestone = _find_milestone(registry, MILESTONE_ID)
    work_task = _find_work_task(milestone, WORK_TASK_ID)
    queue_item = _find_queue_item(queue, PACKAGE_ID)
    design_queue_item = _find_queue_item(design_queue, PACKAGE_ID)

    canonical_alignment = _queue_alignment(queue_item, design_queue_item, work_task, milestone)
    guide_monitor = _marker_monitor(next90_guide, GUIDE_MARKERS, label="Next90 guide canon")
    downloads_monitor = _marker_monitor(public_downloads_policy, DOWNLOADS_MARKERS, label="Public downloads policy")
    auto_update_monitor = _marker_monitor(public_auto_update_policy, AUTO_UPDATE_MARKERS, label="Public auto-update policy")
    acceptance_monitor = _platform_acceptance_monitor(acceptance_matrix)
    repo_hardening_monitor = _repo_hardening_monitor(repo_hardening_checklist, repo_hygiene_policy)
    runbook_monitor = _external_proof_runbook_monitor(external_proof_runbook)
    flagship_monitor = _flagship_readiness_monitor(flagship_product_readiness)

    blockers: List[str] = []
    gate_failures: List[str] = []
    warnings: List[str] = []
    for section_name, section in (
        ("canonical_alignment", canonical_alignment),
        ("next90_guide", guide_monitor),
        ("public_downloads_policy", downloads_monitor),
        ("public_auto_update_policy", auto_update_monitor),
        ("acceptance_matrix", acceptance_monitor),
        ("repo_hardening", repo_hardening_monitor),
        ("external_proof_runbook", runbook_monitor),
        ("flagship_product_readiness", flagship_monitor),
    ):
        for issue in section.get("issues") or []:
            blockers.append(f"{section_name}: {issue}")
        for failure in section.get("gate_failures") or []:
            gate_failures.append(f"{section_name}: {failure}")
        warnings.extend(section.get("warnings") or [])
    warnings.extend(gate_failures)

    return {
        "contract_name": "fleet.next90_m127_release_truth_gate_monitor",
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
            "public_downloads_policy": downloads_monitor,
            "public_auto_update_policy": auto_update_monitor,
            "acceptance_matrix": acceptance_monitor,
            "repo_hardening": repo_hardening_monitor,
        },
        "runtime_monitors": {
            "external_proof_runbook": runbook_monitor,
            "flagship_product_readiness": flagship_monitor,
        },
        "gate_summary": {
            "platforms": acceptance_monitor.get("platforms"),
            "hardening_initiative_statuses": {
                row.get("id"): row.get("status") for row in (repo_hardening_monitor.get("target_initiatives") or [])
            },
            "external_proof_unresolved_request_count": runbook_monitor.get("unresolved_request_count"),
            "flagship_status": flagship_monitor.get("status"),
            "release_gate_status": "pass" if not gate_failures else "blocked",
            "gate_failures": gate_failures,
            "fail_closed": not gate_failures,
        },
        "package_closeout": {
            "state": "pass" if not blockers else "blocked",
            "blockers": blockers,
            "warnings": warnings,
        },
        "source_inputs": {
            "successor_registry": _source_link(registry_path, registry),
            "queue_staging": _source_link(queue_path, queue),
            "design_queue_staging": _source_link(design_queue_path, design_queue),
            "next90_guide": _text_source_link(next90_guide_path),
            "acceptance_matrix": _source_link(acceptance_matrix_path, acceptance_matrix),
            "public_downloads_policy": _text_source_link(public_downloads_policy_path),
            "public_auto_update_policy": _text_source_link(public_auto_update_policy_path),
            "repo_hardening_checklist": _source_link(repo_hardening_checklist_path, repo_hardening_checklist),
            "repo_hygiene_policy": _text_source_link(repo_hygiene_policy_path),
            "external_proof_runbook": _text_source_link(external_proof_runbook_path),
            "flagship_product_readiness": _source_link(flagship_product_readiness_path, flagship_product_readiness),
        },
    }


def render_markdown(payload: Dict[str, Any]) -> str:
    gate_summary = dict(payload.get("gate_summary") or {})
    closeout = dict(payload.get("package_closeout") or {})
    lines = [
        "# Fleet M127 release-truth gates",
        "",
        f"- status: {payload.get('status')}",
        f"- package_id: {payload.get('package_id')}",
        f"- frontier_id: {payload.get('frontier_id')}",
        f"- generated_at: {payload.get('generated_at')}",
        "",
        "## Gate summary",
        f"- external proof unresolved requests: {gate_summary.get('external_proof_unresolved_request_count')}",
        f"- flagship status: {gate_summary.get('flagship_status')}",
        "",
        "## Platform posture",
    ]
    for platform_id, row in (gate_summary.get("platforms") or {}).items():
        lines.append(
            f"- {platform_id}: {row.get('public_shelf_status')} / {row.get('primary_package_kind')} / {row.get('updater_mode')}"
        )
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
        next90_guide_path=Path(args.next90_guide).resolve(),
        acceptance_matrix_path=Path(args.acceptance_matrix).resolve(),
        public_downloads_policy_path=Path(args.public_downloads_policy).resolve(),
        public_auto_update_policy_path=Path(args.public_auto_update_policy).resolve(),
        repo_hardening_checklist_path=Path(args.repo_hardening_checklist).resolve(),
        repo_hygiene_policy_path=Path(args.repo_hygiene_policy).resolve(),
        external_proof_runbook_path=Path(args.external_proof_runbook).resolve(),
        flagship_product_readiness_path=Path(args.flagship_product_readiness).resolve(),
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
