#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml


ROOT = Path("/docker/fleet")
PUBLISHED = ROOT / ".codex-studio" / "published"
PRODUCT_MIRROR = Path("/docker/chummercomplete/chummer-design/products/chummer")

PACKAGE_ID = "next90-m131-fleet-verify-public-guide-regeneration-visibility-source-fresh"
FRONTIER_ID = 5694544514
MILESTONE_ID = 131
WORK_TASK_ID = "131.5"
WAVE_ID = "W19"
QUEUE_TITLE = "Verify public-guide regeneration, visibility-source freshness, crawl-budget discipline, and unsupported-claim rejection gates."
QUEUE_TASK = QUEUE_TITLE
WORK_TASK_TITLE = QUEUE_TITLE
WORK_TASK_DEPENDENCIES = [107, 111, 120, 125]
OWNED_SURFACES = ["verify_public_guide_regeneration_visibility:fleet"]
ALLOWED_PATHS = ["scripts", "tests", ".codex-studio", "feedback"]

DEFAULT_OUTPUT = PUBLISHED / "NEXT90_M131_FLEET_PUBLIC_GUIDE_GATES.generated.json"
DEFAULT_MARKDOWN = PUBLISHED / "NEXT90_M131_FLEET_PUBLIC_GUIDE_GATES.generated.md"

SUCCESSOR_REGISTRY = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
QUEUE_STAGING = PUBLISHED / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
DESIGN_QUEUE_STAGING = PRODUCT_MIRROR / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
NEXT90_GUIDE = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_GUIDE.md"
PUBLIC_GROWTH_STACK = PRODUCT_MIRROR / "PUBLIC_GROWTH_AND_VISIBILITY_STACK.md"
PUBLIC_GUIDE_EXPORT_MANIFEST = PRODUCT_MIRROR / "PUBLIC_GUIDE_EXPORT_MANIFEST.yaml"
PUBLIC_GUIDE_POLICY = PRODUCT_MIRROR / "PUBLIC_GUIDE_POLICY.md"
PUBLIC_VISIBILITY_POLICY = PRODUCT_MIRROR / "PUBLIC_SITE_VISIBILITY_AND_SEARCH_OPTIMIZATION.md"
PUBLIC_SIGNAL_PIPELINE = PRODUCT_MIRROR / "PUBLIC_SIGNAL_TO_CANON_PIPELINE.md"
KATTEB_GUIDE_LANE = PRODUCT_MIRROR / "KATTEB_PUBLIC_GUIDE_OPTIMIZATION_LANE.md"
GUIDE_VERIFY_SCRIPT = ROOT / "scripts" / "verify_chummer6_guide_surface.py"
FLAGSHIP_QUEUE_SCRIPT = ROOT / "scripts" / "materialize_chummer6_flagship_queue.py"
GUIDE_REPO_ROOT = Path("/docker/chummercomplete/Chummer6")

GUIDE_HEAD_FRESHNESS_HOURS = 168

GUIDE_MARKERS = {
    "wave_19": "## Wave 19 - finish account/community, provider, and public-guide substrate",
    "milestone_131": "### 131. Public guide, help, FAQ, content export, media briefs, and search visibility completion",
    "exit_contract": "Exit: guide, help, FAQ, public parts, media briefs, metadata, schema, sitemap, visibility, and content-export outputs compile from Chummer-owned source truth before public output changes.",
}
GROWTH_STACK_MARKERS = {
    "clickrank_entry": "ClickRank audit",
    "source_patch": "-> Hub or public-guide source patch",
    "non_authority_boundary": "None of those tools may own:",
    "success_metric": "no public claim outruns Chummer-owned release evidence",
}
EXPORT_MANIFEST_MARKERS = {
    "root_horizon_authority": "The root `products/chummer/HORIZON_REGISTRY.yaml` is the authority for horizon eligibility;",
    "productlift_projection_only": "ProductLift-backed `/feedback`, `/roadmap`, and `/changelog` pages are public projections only;",
    "katteb_source_first": "accepted suggestions must return to Chummer-owned source before generated guide output changes.",
    "clickrank_source_first": "accepted recommendations must return to Chummer-owned source before generated guide or public site output changes.",
}
GUIDE_POLICY_MARKERS = {
    "subordinate_to_landing": "`Chummer6` must stay subordinate to `PUBLIC_LANDING_POLICY.md`",
    "feature_map_guard": "`Chummer6` must not invent a public feature map that contradicts `PUBLIC_LANDING_MANIFEST.yaml` or `PUBLIC_FEATURE_REGISTRY.yaml`.",
    "root_horizon_authority": "The root `products/chummer/HORIZON_REGISTRY.yaml` is the only source of truth for horizon existence, order, and public-guide eligibility.",
    "clickrank_source_first": "accepted changes still land upstream in Chummer-owned source before publication.",
}
VISIBILITY_POLICY_MARKERS = {
    "source_first": "Accepted changes must be patched upstream into Chummer-owned source, then regenerated or republished.",
    "crawl_budget": "Treat the crawled-page capacity as a scarce public-launch budget.",
    "low_value_duplicate_block": "Do not crawl every generated path, archive page, machine output, internal proof page, or low-value duplicate.",
    "unsupported_claim_guard": "public claims that contradict release evidence",
}
SIGNAL_PIPELINE_MARKERS = {
    "canon_decision": "Public signal is input. Canon is decided by Chummer.",
    "upstream_canonical_edit": "upstream canonical source edit",
    "claim_rejection": "unsupported claims are rejected or removed",
    "source_regeneration": "generated guide or public page is regenerated from Chummer-owned source",
}
KATTEB_LANE_MARKERS = {
    "golden_rule": "accepted changes must flow upstream into `chummer6-design` or a Chummer-owned public-guide source registry before the guide is regenerated.",
    "no_direct_generated_edits": "The generated public guide must never be hand-edited to accept Katteb output.",
    "review_rule": "No Katteb output may publish without human review and Product Governor or delegated content-owner approval.",
    "unsupported_claim_guard": "Claims that unshipped features are available.",
}


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize the Fleet M131 public-guide gates packet.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--markdown-output", default=str(DEFAULT_MARKDOWN))
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--queue-staging", default=str(QUEUE_STAGING))
    parser.add_argument("--design-queue-staging", default=str(DESIGN_QUEUE_STAGING))
    parser.add_argument("--next90-guide", default=str(NEXT90_GUIDE))
    parser.add_argument("--growth-stack", default=str(PUBLIC_GROWTH_STACK))
    parser.add_argument("--guide-export-manifest", default=str(PUBLIC_GUIDE_EXPORT_MANIFEST))
    parser.add_argument("--guide-policy", default=str(PUBLIC_GUIDE_POLICY))
    parser.add_argument("--visibility-policy", default=str(PUBLIC_VISIBILITY_POLICY))
    parser.add_argument("--signal-pipeline", default=str(PUBLIC_SIGNAL_PIPELINE))
    parser.add_argument("--katteb-lane", default=str(KATTEB_GUIDE_LANE))
    parser.add_argument("--guide-verify-script", default=str(GUIDE_VERIFY_SCRIPT))
    parser.add_argument("--flagship-queue-script", default=str(FLAGSHIP_QUEUE_SCRIPT))
    parser.add_argument("--guide-repo-root", default=str(GUIDE_REPO_ROOT))
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
        issues.append("Canonical registry milestone dependencies drifted from M131 requirement set.")
    return {
        "state": "pass" if not issues else "fail",
        "issues": issues,
        "fleet_queue_status": _normalize_text(queue_item.get("status")),
        "design_queue_status": _normalize_text(design_queue_item.get("status")),
        "registry_status": _normalize_text(milestone.get("status")),
        "work_task_status": _normalize_text(work_task.get("status")),
    }


def _run_command(command: List[str]) -> Dict[str, Any]:
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as exc:
        return {"ok": False, "command": command, "issues": [f"failed to execute {' '.join(command)}: {exc}"]}
    return {
        "ok": True,
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def _command_summary(result: Dict[str, Any]) -> str:
    for field in ("stderr", "stdout"):
        text = _normalize_text(result.get(field))
        if not text:
            continue
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if lines:
            return lines[-1]
    return f"command exited with code {int(result.get('returncode') or 0)}"


def _guide_surface_runtime_monitor(script_path: Path) -> Dict[str, Any]:
    issues: List[str] = []
    warnings: List[str] = []
    runtime_blockers: List[str] = []
    if not script_path.exists():
        issues.append(f"Guide surface verifier is missing: {script_path}")
        return {
            "state": "fail",
            "issues": issues,
            "warnings": warnings,
            "runtime_blockers": runtime_blockers,
            "gate_status": "unknown",
            "returncode": None,
            "command": [],
            "summary": "",
        }
    result = _run_command([sys.executable, str(script_path)])
    if not result.get("ok"):
        issues.extend(result.get("issues") or [])
        return {
            "state": "fail",
            "issues": issues,
            "warnings": warnings,
            "runtime_blockers": runtime_blockers,
            "gate_status": "unknown",
            "returncode": None,
            "command": result.get("command") or [],
            "summary": "",
        }
    summary = _command_summary(result)
    gate_status = "pass" if int(result.get("returncode") or 0) == 0 else "blocked"
    if gate_status != "pass":
        runtime_blockers.append(f"Guide surface verifier blocked regeneration: {summary}")
    return {
        "state": "pass" if not issues else "fail",
        "issues": issues,
        "warnings": warnings,
        "runtime_blockers": runtime_blockers,
        "gate_status": gate_status,
        "returncode": int(result.get("returncode") or 0),
        "command": result.get("command") or [],
        "summary": summary,
    }


def _flagship_queue_runtime_monitor(script_path: Path, *, guide_repo_root: Path) -> Dict[str, Any]:
    issues: List[str] = []
    warnings: List[str] = []
    runtime_blockers: List[str] = []
    if not script_path.exists():
        issues.append(f"Flagship queue materializer is missing: {script_path}")
        return {
            "state": "fail",
            "issues": issues,
            "warnings": warnings,
            "runtime_blockers": runtime_blockers,
            "flagship_queue_status": "unknown",
            "findings": [],
            "queue_task_count": 0,
            "queue_tasks": [],
            "guide_root": "",
            "returncode": None,
            "command": [],
        }
    result = _run_command([sys.executable, str(script_path), "--json"])
    if not result.get("ok"):
        issues.extend(result.get("issues") or [])
        return {
            "state": "fail",
            "issues": issues,
            "warnings": warnings,
            "runtime_blockers": runtime_blockers,
            "flagship_queue_status": "unknown",
            "findings": [],
            "queue_task_count": 0,
            "queue_tasks": [],
            "guide_root": "",
            "returncode": None,
            "command": result.get("command") or [],
        }
    try:
        payload = json.loads(_normalize_text(result.get("stdout")) or "{}")
    except json.JSONDecodeError:
        issues.append("Flagship queue materializer did not emit valid JSON.")
        payload = {}
    if not isinstance(payload, dict):
        issues.append("Flagship queue materializer emitted a non-object payload.")
        payload = {}
    status = _normalize_text(payload.get("status")) or "unknown"
    findings = _normalize_list(payload.get("findings"))
    queue_tasks = _normalize_list(payload.get("tasks"))
    guide_root = _normalize_text(payload.get("guide_root"))
    if guide_root:
        try:
            if Path(guide_root).resolve() != guide_repo_root.resolve():
                issues.append("Flagship queue materializer is pointing at a different guide root.")
        except OSError:
            issues.append("Flagship queue materializer returned an unreadable guide root.")
    if status == "unknown":
        issues.append("Flagship queue materializer payload is missing status.")
    if status != "pass":
        if findings:
            runtime_blockers.extend([f"Flagship queue finding: {finding}" for finding in findings])
        else:
            runtime_blockers.append(f"Flagship queue status is {status}.")
    remaining = payload.get("onemin_total_remaining_credits")
    floor = payload.get("onemin_credit_floor")
    burn_allowed = bool(payload.get("onemin_credit_burn_allowed"))
    if floor is not None and not burn_allowed:
        warnings.append(
            f"Flagship queue cannot burn 1min credits at the current floor ({remaining} / {floor})."
        )
    return {
        "state": "pass" if not issues else "fail",
        "issues": issues,
        "warnings": warnings,
        "runtime_blockers": runtime_blockers,
        "flagship_queue_status": status,
        "findings": findings,
        "queue_task_count": int(payload.get("queue_task_count") or 0),
        "queue_tasks": queue_tasks,
        "guide_root": guide_root,
        "onemin_total_remaining_credits": remaining,
        "onemin_credit_floor": floor,
        "onemin_credit_burn_allowed": burn_allowed,
        "returncode": int(result.get("returncode") or 0),
        "command": result.get("command") or [],
    }


def _git_value(repo_root: Path, *args: str) -> tuple[str, str]:
    result = _run_command(["git", "-C", str(repo_root), *args])
    if not result.get("ok"):
        return "", _normalize_text((result.get("issues") or [""])[0])
    if int(result.get("returncode") or 0) != 0:
        return "", _command_summary(result)
    return _normalize_text(result.get("stdout")), ""


def _guide_repo_freshness_monitor(repo_root: Path, *, now: dt.datetime) -> Dict[str, Any]:
    issues: List[str] = []
    warnings: List[str] = []
    runtime_blockers: List[str] = []
    if not repo_root.exists():
        issues.append(f"Guide repo root is missing: {repo_root}")
        return {
            "state": "fail",
            "issues": issues,
            "warnings": warnings,
            "runtime_blockers": runtime_blockers,
            "gate_status": "unknown",
            "head_sha": "",
            "head_committed_at": "",
            "head_age_hours": None,
            "dirty_path_count": None,
        }
    head_sha, sha_error = _git_value(repo_root, "rev-parse", "HEAD")
    head_committed_at, time_error = _git_value(repo_root, "show", "-s", "--format=%cI", "HEAD")
    dirty_output, dirty_error = _git_value(repo_root, "status", "--porcelain")
    if sha_error:
        issues.append(f"Guide repo HEAD lookup failed: {sha_error}")
    if time_error:
        issues.append(f"Guide repo HEAD timestamp lookup failed: {time_error}")
    head_age_hours: float | None = None
    if head_committed_at:
        parsed = _parse_iso_utc(head_committed_at)
        if parsed is None:
            issues.append("Guide repo HEAD committed_at is invalid.")
        else:
            head_age_hours = round(max(0.0, (now - parsed).total_seconds()) / 3600.0, 2)
            if head_age_hours > GUIDE_HEAD_FRESHNESS_HOURS:
                runtime_blockers.append(
                    f"Guide repo HEAD age {head_age_hours}h exceeded the {GUIDE_HEAD_FRESHNESS_HOURS}h freshness threshold."
                )
    dirty_path_count = 0
    if dirty_error:
        warnings.append(f"Guide repo dirtiness check failed: {dirty_error}")
    elif dirty_output:
        dirty_path_count = len([line for line in dirty_output.splitlines() if line.strip()])
        warnings.append(f"Guide repo has {dirty_path_count} uncommitted path(s).")
    gate_status = "pass" if not runtime_blockers else "blocked"
    return {
        "state": "pass" if not issues else "fail",
        "issues": issues,
        "warnings": warnings,
        "runtime_blockers": runtime_blockers,
        "gate_status": gate_status,
        "head_sha": head_sha,
        "head_committed_at": head_committed_at,
        "head_age_hours": head_age_hours,
        "dirty_path_count": dirty_path_count,
    }


def build_payload(
    *,
    registry_path: Path,
    queue_path: Path,
    design_queue_path: Path,
    next90_guide_path: Path,
    growth_stack_path: Path,
    guide_export_manifest_path: Path,
    guide_policy_path: Path,
    visibility_policy_path: Path,
    signal_pipeline_path: Path,
    katteb_lane_path: Path,
    guide_verify_script_path: Path,
    flagship_queue_script_path: Path,
    guide_repo_root: Path,
    generated_at: str | None = None,
) -> Dict[str, Any]:
    generated_at = generated_at or _utc_now()
    registry = _read_yaml(registry_path)
    queue = _read_yaml(queue_path)
    design_queue = _read_yaml(design_queue_path)
    next90_guide = _read_text(next90_guide_path)
    growth_stack = _read_text(growth_stack_path)
    guide_export_manifest = _read_text(guide_export_manifest_path)
    guide_policy = _read_text(guide_policy_path)
    visibility_policy = _read_text(visibility_policy_path)
    signal_pipeline = _read_text(signal_pipeline_path)
    katteb_lane = _read_text(katteb_lane_path)
    reference_now = _parse_iso_utc(generated_at) or dt.datetime.now(dt.timezone.utc)

    milestone = _find_milestone(registry, MILESTONE_ID)
    work_task = _find_work_task(milestone, WORK_TASK_ID)
    queue_item = _find_queue_item(queue, PACKAGE_ID)
    design_queue_item = _find_queue_item(design_queue, PACKAGE_ID)

    canonical_alignment = _queue_alignment(queue_item, design_queue_item, work_task, milestone)
    guide_monitor = _marker_monitor(next90_guide, GUIDE_MARKERS, label="Next90 guide canon")
    growth_stack_monitor = _marker_monitor(growth_stack, GROWTH_STACK_MARKERS, label="Public growth stack canon")
    export_manifest_monitor = _marker_monitor(
        guide_export_manifest,
        EXPORT_MANIFEST_MARKERS,
        label="Public guide export manifest canon",
    )
    guide_policy_monitor = _marker_monitor(guide_policy, GUIDE_POLICY_MARKERS, label="Public guide policy canon")
    visibility_policy_monitor = _marker_monitor(
        visibility_policy,
        VISIBILITY_POLICY_MARKERS,
        label="Visibility policy canon",
    )
    signal_pipeline_monitor = _marker_monitor(
        signal_pipeline,
        SIGNAL_PIPELINE_MARKERS,
        label="Public signal pipeline canon",
    )
    katteb_lane_monitor = _marker_monitor(katteb_lane, KATTEB_LANE_MARKERS, label="Katteb guide lane canon")
    guide_surface_monitor = _guide_surface_runtime_monitor(guide_verify_script_path)
    flagship_queue_monitor = _flagship_queue_runtime_monitor(
        flagship_queue_script_path,
        guide_repo_root=guide_repo_root,
    )
    guide_repo_monitor = _guide_repo_freshness_monitor(guide_repo_root, now=reference_now)

    blockers: List[str] = []
    runtime_blockers: List[str] = []
    warnings: List[str] = []
    for section_name, section in (
        ("canonical_alignment", canonical_alignment),
        ("next90_guide", guide_monitor),
        ("growth_stack", growth_stack_monitor),
        ("guide_export_manifest", export_manifest_monitor),
        ("guide_policy", guide_policy_monitor),
        ("visibility_policy", visibility_policy_monitor),
        ("signal_pipeline", signal_pipeline_monitor),
        ("katteb_lane", katteb_lane_monitor),
        ("guide_surface_gate", guide_surface_monitor),
        ("flagship_queue_gate", flagship_queue_monitor),
        ("guide_repo_freshness", guide_repo_monitor),
    ):
        for issue in section.get("issues") or []:
            blockers.append(f"{section_name}: {issue}")
        for runtime_blocker in section.get("runtime_blockers") or []:
            runtime_blockers.append(f"{section_name}: {runtime_blocker}")
        warnings.extend(section.get("warnings") or [])

    public_guide_gate_status = "blocked" if runtime_blockers else "warning" if warnings else "pass"
    closeout_warnings = list(runtime_blockers) + warnings

    return {
        "contract_name": "fleet.next90_m131_public_guide_gates",
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
            "growth_stack": growth_stack_monitor,
            "guide_export_manifest": export_manifest_monitor,
            "guide_policy": guide_policy_monitor,
            "visibility_policy": visibility_policy_monitor,
            "signal_pipeline": signal_pipeline_monitor,
            "katteb_lane": katteb_lane_monitor,
        },
        "runtime_monitors": {
            "guide_surface_gate": guide_surface_monitor,
            "flagship_queue_gate": flagship_queue_monitor,
            "guide_repo_freshness": guide_repo_monitor,
        },
        "monitor_summary": {
            "public_guide_gate_status": public_guide_gate_status,
            "runtime_blocker_count": len(runtime_blockers),
            "warning_count": len(warnings),
            "guide_surface_gate_status": guide_surface_monitor.get("gate_status"),
            "flagship_queue_status": flagship_queue_monitor.get("flagship_queue_status"),
            "flagship_queue_task_count": flagship_queue_monitor.get("queue_task_count"),
            "guide_repo_head_sha": guide_repo_monitor.get("head_sha"),
            "guide_repo_head_age_hours": guide_repo_monitor.get("head_age_hours"),
            "runtime_blockers": runtime_blockers,
        },
        "package_closeout": {
            "state": "pass" if not blockers else "blocked",
            "blockers": blockers,
            "warnings": closeout_warnings,
        },
        "source_inputs": {
            "successor_registry": _source_link(registry_path, registry),
            "queue_staging": _source_link(queue_path, queue),
            "design_queue_staging": _source_link(design_queue_path, design_queue),
            "next90_guide": _text_source_link(next90_guide_path),
            "growth_stack": _text_source_link(growth_stack_path),
            "guide_export_manifest": _text_source_link(guide_export_manifest_path),
            "guide_policy": _text_source_link(guide_policy_path),
            "visibility_policy": _text_source_link(visibility_policy_path),
            "signal_pipeline": _text_source_link(signal_pipeline_path),
            "katteb_lane": _text_source_link(katteb_lane_path),
            "guide_verify_script": _text_source_link(guide_verify_script_path),
            "flagship_queue_script": _text_source_link(flagship_queue_script_path),
        },
    }


def render_markdown(payload: Dict[str, Any]) -> str:
    summary = dict(payload.get("monitor_summary") or {})
    closeout = dict(payload.get("package_closeout") or {})
    lines = [
        "# Fleet M131 public-guide gates",
        "",
        f"- status: {payload.get('status')}",
        f"- public_guide_gate_status: {summary.get('public_guide_gate_status')}",
        f"- package_id: {payload.get('package_id')}",
        f"- frontier_id: {payload.get('frontier_id')}",
        f"- generated_at: {payload.get('generated_at')}",
        "",
        "## Runtime summary",
        f"- guide_surface_gate_status: {summary.get('guide_surface_gate_status')}",
        f"- flagship_queue_status: {summary.get('flagship_queue_status')}",
        f"- flagship_queue_task_count: {summary.get('flagship_queue_task_count')}",
        f"- guide_repo_head_sha: {summary.get('guide_repo_head_sha')}",
        f"- guide_repo_head_age_hours: {summary.get('guide_repo_head_age_hours')}",
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
        growth_stack_path=Path(args.growth_stack).resolve(),
        guide_export_manifest_path=Path(args.guide_export_manifest).resolve(),
        guide_policy_path=Path(args.guide_policy).resolve(),
        visibility_policy_path=Path(args.visibility_policy).resolve(),
        signal_pipeline_path=Path(args.signal_pipeline).resolve(),
        katteb_lane_path=Path(args.katteb_lane).resolve(),
        guide_verify_script_path=Path(args.guide_verify_script).resolve(),
        flagship_queue_script_path=Path(args.flagship_queue_script).resolve(),
        guide_repo_root=Path(args.guide_repo_root).resolve(),
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
