#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml

try:
    from scripts.materialize_compile_manifest import (
        repo_root_for_published_path,
        write_compile_manifest,
        write_text_atomic,
    )
except ModuleNotFoundError:
    from materialize_compile_manifest import (
        repo_root_for_published_path,
        write_compile_manifest,
        write_text_atomic,
    )


ROOT = Path("/docker/fleet")
PUBLISHED = ROOT / ".codex-studio" / "published"
SUCCESSOR_REGISTRY = (
    Path("/docker/chummercomplete/chummer-design/products/chummer")
    / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
)
CLOSED_FLAGSHIP_REGISTRY_PATH = (
    Path("/docker/chummercomplete/chummer-design/products/chummer")
    / "NEXT_12_BIGGEST_WINS_REGISTRY.yaml"
)
DESIGN_QUEUE_STAGING = (
    Path("/docker/chummercomplete/chummer-design/products/chummer")
    / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
)
QUEUE_STAGING = PUBLISHED / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
WEEKLY_PULSE = PUBLISHED / "WEEKLY_PRODUCT_PULSE.generated.json"
FLAGSHIP_READINESS = PUBLISHED / "FLAGSHIP_PRODUCT_READINESS.generated.json"
JOURNEY_GATES = PUBLISHED / "JOURNEY_GATES.generated.json"
SUPPORT_PACKETS = PUBLISHED / "SUPPORT_CASE_PACKETS.generated.json"
STATUS_PLANE = PUBLISHED / "STATUS_PLANE.generated.yaml"
EXPECTED_PRODUCTION_SOURCE_PATHS = {
    "successor_registry": str(SUCCESSOR_REGISTRY),
    "closed_flagship_registry": str(CLOSED_FLAGSHIP_REGISTRY_PATH),
    "design_queue_staging": str(DESIGN_QUEUE_STAGING),
    "queue_staging": str(QUEUE_STAGING),
    "weekly_pulse": str(WEEKLY_PULSE),
    "flagship_readiness": str(FLAGSHIP_READINESS),
    "journey_gates": str(JOURNEY_GATES),
    "support_packets": str(SUPPORT_PACKETS),
    "status_plane": str(STATUS_PLANE),
}
PACKAGE_ID = "next90-m106-fleet-governor-packet"
EXPECTED_PACKAGE_TITLE = (
    "Publish weekly governor packets with measured launch, freeze, canary, and rollback decisions"
)
EXPECTED_PACKAGE_TASK = (
    "Turn readiness, parity, support, and rollout truth into a weekly governor packet "
    "that drives measured product decisions."
)
EXPECTED_MILESTONE_TITLE = "Product-governor weekly adoption and measured rollout loop"
MILESTONE_ID = 106
PROGRAM_WAVE = "next_90_day_product_advance"
WAVE_ID = "W8"
QUEUE_STATUS = "live_parallel_successor"
SUCCESSOR_FRONTIER_IDS = ("2376135131",)
LOCAL_PROOF_FLOOR_COMMITS = (
    "065c653",
    "fb47ce8",
    "5e6a468",
    "f66dbaa",
    "f490e53",
    "e9ea391",
    "aefd72c",
    "21e00dd",
    "3eec697",
    "6fd5bfe",
    "3418b3c",
    "3580ba8",
    "eeafd9e",
    "1ba508e",
    "6d1663c",
    "ade57ae",
    "55d8282",
    "144eae5",
    "543dfd5",
    "f16f13b",
    "999231f",
    "25836f6",
    "3e7ee9b",
    "17189be",
    "9d2ea4c",
    "bb49fc1",
    "26679c7",
    "ef50370",
    "a1be389",
    "83d2d21",
    "e74a7ec",
    "8fb8d40",
    "dd5fdb5",
    "52fe086",
    "6c429cb",
)
OWNED_SURFACES = ("weekly_governor_packet", "measured_rollout_loop")
ALLOWED_PATHS = ("admin", "scripts", "tests", ".codex-studio")
CLOSED_FLAGSHIP_WAVE = "next_12_biggest_wins"
UTC = dt.timezone.utc
WEEKLY_PULSE_MAX_AGE_SECONDS = 8 * 24 * 60 * 60
SUPPORT_PACKETS_MAX_AGE_SECONDS = 8 * 24 * 60 * 60
GENERATED_AT_MAX_FUTURE_SKEW_SECONDS = 5 * 60
REQUIRED_GENERATED_SOURCE_INPUTS = (
    "weekly_pulse",
    "flagship_readiness",
    "journey_gates",
    "support_packets",
    "status_plane",
)
REQUIRED_QUEUE_PROOF_MARKERS = (
    "/docker/fleet/scripts/materialize_weekly_governor_packet.py",
    "/docker/fleet/scripts/verify_next90_m106_fleet_governor_packet.py",
    "/docker/fleet/scripts/verify_script_bootstrap_no_pythonpath.py",
    "/docker/fleet/tests/test_materialize_weekly_governor_packet.py",
    "/docker/fleet/tests/test_fleet_script_bootstrap_without_pythonpath.py",
    "/docker/fleet/.codex-studio/published/WEEKLY_GOVERNOR_PACKET.generated.json",
    "/docker/fleet/.codex-studio/published/WEEKLY_GOVERNOR_PACKET.generated.md",
    "python3 -m py_compile scripts/materialize_weekly_governor_packet.py scripts/verify_next90_m106_fleet_governor_packet.py tests/test_materialize_weekly_governor_packet.py",
    "python3 -m py_compile scripts/verify_script_bootstrap_no_pythonpath.py tests/test_fleet_script_bootstrap_without_pythonpath.py",
    "python3 scripts/verify_next90_m106_fleet_governor_packet.py exits 0",
    "direct tmp_path fixture invocation for tests/test_materialize_weekly_governor_packet.py exits 0",
    "verifier rebuilds the decision-critical packet projection from live source inputs",
    "verifier rejects checked-in packet freshness drift against generated readiness, journey, support, weekly pulse, and status-plane inputs",
    "future-dated weekly and source generated_at receipts are rejected",
    "verifier rejects compile manifest freshness drift after weekly packet refresh",
    "verifier rejects support-packet source_sha256 drift against SUPPORT_CASE_PACKETS.generated.json",
    "verifier requires every measured rollout action to appear in both the decision board and decision gate ledger",
    "weekly pulse duplicate or ambiguous launch governance actions are rejected",
    "status-plane final claim drift blocks launch expansion and measured rollout readiness",
    "status_reason distinguishes closed Fleet package proof from blocked rollout gates",
    "forbidden worker proof strings are rejected case-insensitively",
    "task-local telemetry field names are rejected as worker proof strings",
    "successor-wave telemetry summary strings are rejected as worker proof strings",
    "literal successor-wave telemetry labels are rejected as worker proof strings",
    "frontier-detail prompt strings are rejected as worker proof strings",
    "run-prompt authority labels are rejected as worker proof strings",
    "handoff polling phrase guard is enforced case-insensitively",
    "control-plane polling prohibition guard is enforced case-insensitively",
    "worker-run OODA helper guard is enforced case-insensitively",
    "worker-run supervisor launcher guard is enforced case-insensitively",
    "run-helper failure proof strings are rejected case-insensitively",
    "verifier rejects Fleet proof paths outside package allowed path roots",
    "production verifier rejects non-canonical source path overrides",
    "verifier rejects reused closed successor frontier rows outside the Fleet M106 package",
    "no-PYTHONPATH bootstrap guard includes the standalone M106 verifier",
    "successor frontier 2376135131 pinned for next90-m106-fleet-governor-packet repeat prevention",
    "local proof floor commit 1ba508e pinned for M106 governor packet repeat prevention",
    "local proof floor commit 6d1663c pinned for M106 governor packet dependency-routing guard",
    "local proof floor commit ade57ae pinned for M106 task-local telemetry field guard",
    "local proof floor commit 55d8282 pinned for M106 source-authority guard",
    "local proof floor commit 144eae5 pinned for M106 worker-run helper guard",
    "local proof floor commit 543dfd5 pinned for M106 markdown proof-floor guard",
    "local proof floor commit f16f13b pinned for M106 run-helper failure guard",
    "local proof floor commit 999231f pinned for M106 source-input refresh guard",
    "local proof floor commit 25836f6 pinned for M106 source refresh proof floor",
    "local proof floor commit 3e7ee9b pinned for M106 governor packet proof floor",
    "local proof floor commit 17189be pinned for M106 future-dated source timestamp guard",
    "local proof floor commit 9d2ea4c pinned for M106 timestamp guard proof floor",
    "local proof floor commit bb49fc1 pinned for M106 run-prompt authority guard",
    "local proof floor commit 26679c7 pinned for M106 refreshed packet artifact floor",
    "local proof floor commit ef50370 pinned for M106 refreshed proof-floor guard",
    "local proof floor commit a1be389 pinned for M106 successor telemetry prompt-label guard",
    "local proof floor commit 83d2d21 pinned for M106 OODA telemetry ownership guard",
    "local proof floor commit e74a7ec pinned for M106 OODA telemetry proof floor",
    "local proof floor commit 8fb8d40 pinned for M106 refreshed packet artifact floor",
    "local proof floor commit dd5fdb5 pinned for M106 weekly governor proof floor",
    "local proof floor commit 52fe086 pinned for M106 governor packet proof floor",
    "local proof floor commit 6c429cb pinned for M106 verified closeout proof floor",
    "do-not-reopen handoff routes remaining M106 work to dependency or sibling packages",
)
REQUIRED_REGISTRY_EVIDENCE_MARKERS = (
    "scripts/materialize_weekly_governor_packet.py",
    "scripts/verify_next90_m106_fleet_governor_packet.py",
    "scripts/verify_script_bootstrap_no_pythonpath.py",
    "tests/test_materialize_weekly_governor_packet.py",
    "tests/test_fleet_script_bootstrap_without_pythonpath.py",
    "WEEKLY_GOVERNOR_PACKET.generated.json",
    "WEEKLY_GOVERNOR_PACKET.generated.md",
    "py_compile scripts/materialize_weekly_governor_packet.py scripts/verify_next90_m106_fleet_governor_packet.py tests/test_materialize_weekly_governor_packet.py",
    "py_compile scripts/verify_script_bootstrap_no_pythonpath.py tests/test_fleet_script_bootstrap_without_pythonpath.py",
    "verify_next90_m106_fleet_governor_packet.py exits 0",
    "tmp_path fixture invocation",
    "decision-critical packet projection",
    "packet freshness drift against generated readiness",
    "future-dated weekly and source generated_at receipts",
    "compile manifest freshness drift",
    "support-packet source_sha256 drift",
    "every measured rollout action",
    "weekly pulse duplicate or ambiguous launch governance actions",
    "status-plane final claim drift",
    "status_reason distinguishes closed Fleet package proof from blocked rollout gates",
    "forbidden worker proof strings",
    "task-local telemetry field names",
    "successor-wave telemetry summary strings",
    "literal successor-wave telemetry labels",
    "frontier-detail prompt strings",
    "run-prompt authority labels",
    "handoff polling phrase guard",
    "control-plane polling prohibition guard",
    "worker-run OODA helper guard",
    "worker-run supervisor launcher guard",
    "run-helper failure proof strings",
    "proof paths outside package allowed path roots",
    "non-canonical source path overrides",
    "reused closed successor frontier rows",
    "no-PYTHONPATH bootstrap guard includes the standalone M106 verifier",
    "successor frontier 2376135131",
    "local proof floor commit 1ba508e",
    "local proof floor commit 6d1663c",
    "local proof floor commit ade57ae",
    "local proof floor commit 55d8282",
    "local proof floor commit 144eae5",
    "local proof floor commit 543dfd5",
    "local proof floor commit f16f13b",
    "local proof floor commit 999231f",
    "local proof floor commit 25836f6",
    "local proof floor commit 3e7ee9b",
    "local proof floor commit 17189be",
    "local proof floor commit 9d2ea4c",
    "local proof floor commit bb49fc1",
    "local proof floor commit 26679c7",
    "local proof floor commit ef50370",
    "local proof floor commit a1be389",
    "local proof floor commit 83d2d21",
    "local proof floor commit e74a7ec",
    "local proof floor commit 8fb8d40",
    "local proof floor commit dd5fdb5",
    "local proof floor commit 52fe086",
    "local proof floor commit 6c429cb",
    "do-not-reopen handoff routes remaining M106 work",
)
REQUIRED_RESOLVING_PROOF_PATHS = (
    "scripts/materialize_weekly_governor_packet.py",
    "scripts/verify_next90_m106_fleet_governor_packet.py",
    "scripts/verify_script_bootstrap_no_pythonpath.py",
    "tests/test_materialize_weekly_governor_packet.py",
    "tests/test_fleet_script_bootstrap_without_pythonpath.py",
)
DISALLOWED_WORKER_PROOF_COMMAND_MARKERS = (
    "/var/lib/codex-fleet",
    "ACTIVE_RUN_HANDOFF.generated.md",
    "run_ooda_design_supervisor_until_quiet",
    "run_chummer_design_supervisor.sh",
    "run_ooda_design_supervisor.sh",
    "ooda_design_supervisor.py",
    "TASK_LOCAL_TELEMETRY.generated.json",
    "first_commands",
    "focus_owners",
    "focus_profiles",
    "focus_texts",
    "frontier_briefs",
    "polling_disabled",
    "runtime_handoff_path",
    "status_query_supported",
    "task-local telemetry file",
    "local machine-readable context",
    "remaining milestones",
    "remaining queue items",
    "critical path",
    "successor-wave telemetry:",
    "eta:",
    "eta ",
    "successor frontier detail:",
    "successor frontier ids to prioritize first",
    "current steering focus",
    "assigned successor queue package",
    "assigned slice authority",
    "execution rules inside this run",
    "first action rule",
    "writable scope roots",
    "operator telemetry",
    "supervisor status polling",
    "supervisor eta polling",
    "do not query supervisor status",
    "do not query supervisor status or eta",
    "polling the supervisor again",
    "active-run telemetry",
    "active-run helper",
    "active-run helper commands",
    "active run helper",
    "active worker run",
    "worker runs",
    "operator/OODA loop",
    "operator ooda loop",
    "operator/OODA loop owns telemetry",
    "operator ooda loop owns telemetry",
    "ooda loop owns telemetry",
    "operator-owned telemetry",
    "operator-owned run-helper",
    "operator-owned helper",
    "inside worker runs",
    "run failure",
    "hard-blocked",
    "hard blocked",
    "non-zero during active runs",
    "nonzero during active runs",
    "--telemetry-answer",
    "codexea --telemetry",
    "chummer_design_supervisor status",
    "chummer_design_supervisor eta",
    "chummer_design_supervisor.py",
    "chummer_design_supervisor.py status",
    "chummer_design_supervisor.py eta",
)
REQUIRED_LAUNCH_SIGNALS = (
    "journey_gate_state",
    "local_release_proof_status",
    "provider_canary_status",
    "closure_health_state",
)
COMPLETE_STATUSES = {"complete", "closed", "done"}
SUPPORT_DEPENDENCY_PACKAGE_ID = "next90-m102-fleet-reporter-receipts"


def iso_now() -> str:
    return dt.datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize the Fleet weekly governor packet for successor milestone 106."
    )
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument(
        "--out",
        default=str(PUBLISHED / "WEEKLY_GOVERNOR_PACKET.generated.json"),
        help="output path for WEEKLY_GOVERNOR_PACKET.generated.json",
    )
    parser.add_argument(
        "--markdown-out",
        default="",
        help="operator-readable Markdown companion for the weekly governor packet",
    )
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--closed-flagship-registry", default=str(CLOSED_FLAGSHIP_REGISTRY_PATH))
    parser.add_argument("--design-queue-staging", default=str(DESIGN_QUEUE_STAGING))
    parser.add_argument("--queue-staging", default=str(QUEUE_STAGING))
    parser.add_argument("--weekly-pulse", default=str(WEEKLY_PULSE))
    parser.add_argument("--flagship-readiness", default=str(FLAGSHIP_READINESS))
    parser.add_argument("--journey-gates", default=str(JOURNEY_GATES))
    parser.add_argument("--support-packets", default=str(SUPPORT_PACKETS))
    parser.add_argument("--status-plane", default=str(STATUS_PLANE))
    return parser.parse_args(argv)


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_yaml(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _norm_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _disallowed_worker_proof_entries(entries: List[str]) -> List[str]:
    blocked: List[str] = []
    for entry in entries:
        normalized_entry = entry.lower()
        for marker in DISALLOWED_WORKER_PROOF_COMMAND_MARKERS:
            if marker.lower() in normalized_entry:
                blocked.append(entry)
                break
    return blocked


def _resolve_fleet_proof_path(repo_root: Path, marker: str) -> Path:
    text = str(marker or "").strip()
    prefix = "/docker/fleet/"
    if text.startswith(prefix):
        text = text[len(prefix):]
    return repo_root / text


def _missing_resolving_proof_paths(repo_root: Path) -> List[str]:
    missing: List[str] = []
    for marker in REQUIRED_RESOLVING_PROOF_PATHS:
        if not _resolve_fleet_proof_path(repo_root, marker).is_file():
            missing.append(marker)
    return missing


def _local_commit_resolution(repo_root: Path) -> Dict[str, Any]:
    rows: List[Dict[str, str]] = []
    missing: List[str] = []
    if not (repo_root / ".git").exists():
        return {
            "status": "not_checked",
            "reason": "repo_root is not a git checkout",
            "required_commits": list(LOCAL_PROOF_FLOOR_COMMITS),
            "commits": [],
            "missing_commits": [],
        }
    for commit in LOCAL_PROOF_FLOOR_COMMITS:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "cat-file", "-e", f"{commit}^{{commit}}"],
            check=False,
            capture_output=True,
            text=True,
        )
        status = "present" if result.returncode == 0 else "missing"
        rows.append({"commit": commit, "status": status})
        if status != "present":
            missing.append(commit)
    return {
        "status": "pass" if not missing else "fail",
        "required_commits": list(LOCAL_PROOF_FLOOR_COMMITS),
        "commits": rows,
        "missing_commits": missing,
    }


def _fleet_proof_path_scope_issues(entries: List[str]) -> List[str]:
    issues: List[str] = []
    allowed_prefixes = tuple(f"{root}/" for root in ALLOWED_PATHS)
    for entry in entries:
        text = str(entry or "").strip()
        first_token = text.split(maxsplit=1)[0] if text else ""
        candidates: List[str] = []
        if first_token:
            candidates.append(first_token)
        candidates.extend(re.findall(r"/docker/fleet/[^\s,;:]+", text))
        candidates.extend(re.findall(r"/docker/(?!fleet/)[^\s,;:]+", text))
        seen: set[str] = set()
        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            relative = ""
            if candidate.startswith("/docker/fleet/"):
                relative = candidate.removeprefix("/docker/fleet/")
            elif candidate.startswith("/docker/"):
                issues.append(candidate)
                continue
            elif candidate.startswith(tuple(f"{root}/" for root in ALLOWED_PATHS)):
                relative = candidate
            if relative and not relative.startswith(allowed_prefixes):
                issues.append(candidate)
    return issues


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_iso_utc(value: Any) -> dt.datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _find_milestone(registry: Dict[str, Any]) -> Dict[str, Any]:
    for row in registry.get("milestones") or []:
        if isinstance(row, dict) and _coerce_int(row.get("id"), -1) == MILESTONE_ID:
            return row
    return {}


def _find_wave(registry: Dict[str, Any]) -> Dict[str, Any]:
    for row in registry.get("waves") or []:
        if isinstance(row, dict) and str(row.get("id") or "").strip() == WAVE_ID:
            return row
    return {}


def _milestone_index(registry: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    indexed: Dict[int, Dict[str, Any]] = {}
    for row in registry.get("milestones") or []:
        if not isinstance(row, dict):
            continue
        milestone_id = _coerce_int(row.get("id"), -1)
        if milestone_id >= 0:
            indexed[milestone_id] = row
    return indexed


def _dependency_posture(registry: Dict[str, Any], milestone: Dict[str, Any]) -> Dict[str, Any]:
    indexed = _milestone_index(registry)
    dependencies = [
        _coerce_int(dep, -1)
        for dep in (milestone.get("dependencies") or [])
        if _coerce_int(dep, -1) >= 0
    ]
    rows: List[Dict[str, Any]] = []
    open_dependencies: List[int] = []
    missing_dependencies: List[int] = []
    for dep in dependencies:
        dep_row = indexed.get(dep) or {}
        status = str(dep_row.get("status") or "missing").strip()
        if not dep_row:
            missing_dependencies.append(dep)
        elif status.lower() not in COMPLETE_STATUSES:
            open_dependencies.append(dep)
        rows.append(
            {
                "id": dep,
                "title": str(dep_row.get("title") or "").strip(),
                "status": status,
            }
        )
    return {
        "status": "satisfied" if not open_dependencies and not missing_dependencies else "open",
        "dependencies": rows,
        "open_dependency_ids": open_dependencies,
        "missing_dependency_ids": missing_dependencies,
    }


def _find_queue_item(queue: Dict[str, Any]) -> Dict[str, Any]:
    matches = _find_queue_items(queue)
    return matches[0] if matches else {}


def _find_queue_items(queue: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        row
        for row in queue.get("items") or []
        if isinstance(row, dict) and str(row.get("package_id") or "").strip() == PACKAGE_ID
    ]


def _find_registry_work_task(milestone: Dict[str, Any], task_id: str) -> Dict[str, Any]:
    matches = _find_registry_work_tasks(milestone, task_id)
    return matches[0] if matches else {}


def _find_registry_work_tasks(
    milestone: Dict[str, Any], task_id: str
) -> List[Dict[str, Any]]:
    return [
        row
        for row in milestone.get("work_tasks") or []
        if isinstance(row, dict) and str(row.get("id") or "").strip() == task_id
    ]


def _work_task_posture(milestone: Dict[str, Any]) -> Dict[str, Any]:
    rows: List[Dict[str, str]] = []
    open_sibling_ids: List[str] = []
    for row in milestone.get("work_tasks") or []:
        if not isinstance(row, dict):
            continue
        task_id = str(row.get("id") or "").strip()
        status = str(row.get("status") or "").strip()
        owner = str(row.get("owner") or "").strip()
        rows.append(
            {
                "id": task_id,
                "owner": owner,
                "status": status,
                "title": str(row.get("title") or "").strip(),
            }
        )
        if task_id != "106.1" and status.lower() not in COMPLETE_STATUSES:
            open_sibling_ids.append(task_id)
    return {
        "work_tasks": rows,
        "open_sibling_work_task_ids": open_sibling_ids,
    }


def _queue_authority_issues(item: Dict[str, Any], prefix: str) -> List[str]:
    issues: List[str] = []
    if str(item.get("title") or "").strip() != EXPECTED_PACKAGE_TITLE:
        issues.append(f"{prefix} item title no longer matches package authority")
    if str(item.get("task") or "").strip() != EXPECTED_PACKAGE_TASK:
        issues.append(f"{prefix} item task no longer matches package authority")
    frontier_id = str(item.get("frontier_id") or "").strip()
    if frontier_id not in SUCCESSOR_FRONTIER_IDS:
        issues.append(f"{prefix} item frontier_id does not match successor frontier 2376135131")
    if str(item.get("wave") or "").strip() != WAVE_ID:
        issues.append(f"{prefix} item wave is not W8")
    if _coerce_int(item.get("milestone_id"), -1) != MILESTONE_ID:
        issues.append(f"{prefix} item milestone_id does not match milestone 106")
    if str(item.get("repo") or "").strip() != "fleet":
        issues.append(f"{prefix} item repo is not fleet")
    if _norm_list(item.get("allowed_paths")) != list(ALLOWED_PATHS):
        issues.append(f"{prefix} item allowed_paths no longer match package authority")
    if _norm_list(item.get("owned_surfaces")) != list(OWNED_SURFACES):
        issues.append(f"{prefix} item owned_surfaces no longer match package authority")
    if str(item.get("status") or "").strip().lower() not in COMPLETE_STATUSES:
        if prefix == "queue":
            issues.append("queue item is not marked complete in staging queue")
        else:
            issues.append(f"{prefix} item is not marked complete")
    return issues


def _queue_proof_issues(item: Dict[str, Any], prefix: str, repo_root: Path) -> List[str]:
    issues: List[str] = []
    proof_entries = _norm_list(item.get("proof"))
    missing_proof = [
        marker
        for marker in REQUIRED_QUEUE_PROOF_MARKERS
        if marker not in proof_entries
    ]
    if missing_proof:
        issues.append(
            f"{prefix} item proof is missing required weekly governor receipt(s): "
            + ", ".join(missing_proof)
        )
    disallowed_proof = _disallowed_worker_proof_entries(proof_entries)
    if disallowed_proof:
        issues.append(
            f"{prefix} item proof includes active-run or operator-helper command evidence "
            "that worker packages must not invoke: "
            + ", ".join(disallowed_proof)
        )
    out_of_scope_paths = _fleet_proof_path_scope_issues(proof_entries)
    if out_of_scope_paths:
        issues.append(
            f"{prefix} item proof includes Fleet proof path(s) outside allowed package roots "
            f"{', '.join(ALLOWED_PATHS)}: "
            + ", ".join(out_of_scope_paths)
        )
    missing_resolving_paths = _missing_resolving_proof_paths(repo_root)
    missing_from_queue = [
        marker
        for marker in missing_resolving_paths
        if f"/docker/fleet/{marker}" in proof_entries or marker in proof_entries
    ]
    if missing_from_queue:
        issues.append(
            f"{prefix} item proof includes source anchor(s) that no longer resolve: "
            + ", ".join(missing_from_queue)
        )
    return issues


def _queue_mirror_drift(design_item: Dict[str, Any], item: Dict[str, Any]) -> List[Dict[str, Any]]:
    drift: List[Dict[str, Any]] = []
    comparable_fields = (
        "title",
        "task",
        "package_id",
        "frontier_id",
        "milestone_id",
        "wave",
        "repo",
        "status",
        "proof",
        "allowed_paths",
        "owned_surfaces",
    )
    for field in comparable_fields:
        design_value = design_item.get(field)
        mirror_value = item.get(field)
        if design_value != mirror_value:
            drift.append(
                {
                    "field": field,
                    "design_queue": design_value,
                    "fleet_queue": mirror_value,
                }
            )
    return drift


def _frontier_reuse_issues(items: List[Dict[str, Any]], prefix: str) -> List[str]:
    reused = [
        str(row.get("package_id") or "").strip() or "<missing>"
        for row in items
        if str(row.get("package_id") or "").strip() != PACKAGE_ID
        and str(row.get("frontier_id") or "").strip() in SUCCESSOR_FRONTIER_IDS
    ]
    if not reused:
        return []
    return [
        f"{prefix} reuses closed successor frontier 2376135131 outside {PACKAGE_ID}: "
        + ", ".join(reused)
    ]


def verify_package(
    registry: Dict[str, Any],
    design_queue: Dict[str, Any],
    queue: Dict[str, Any],
    repo_root: Path,
) -> Dict[str, Any]:
    milestone = _find_milestone(registry)
    wave = _find_wave(registry)
    design_items = _find_queue_items(design_queue)
    items = _find_queue_items(queue)
    design_item = _find_queue_item(design_queue)
    item = _find_queue_item(queue)
    registry_work_tasks = (
        _find_registry_work_tasks(milestone, "106.1") if milestone else []
    )
    registry_work_task = registry_work_tasks[0] if registry_work_tasks else {}
    dependency_posture = _dependency_posture(registry, milestone) if milestone else {
        "status": "open",
        "dependencies": [],
        "open_dependency_ids": [],
        "missing_dependency_ids": [],
    }
    local_commit_resolution = _local_commit_resolution(repo_root)
    issues: List[str] = []
    if not milestone:
        issues.append(f"milestone {MILESTONE_ID} is missing from successor registry")
    if str(registry.get("program_wave") or "").strip() != PROGRAM_WAVE:
        issues.append("successor registry program_wave is not next_90_day_product_advance")
    if not wave:
        issues.append("successor registry wave W8 is missing")
    else:
        wave_milestone_ids = [
            _coerce_int(row, -1)
            for row in (wave.get("milestone_ids") or [])
            if _coerce_int(row, -1) >= 0
        ]
        if MILESTONE_ID not in wave_milestone_ids:
            issues.append("successor registry wave W8 does not include milestone 106")
    if not item:
        issues.append(f"queue item {PACKAGE_ID} is missing from staging queue")
    elif len(items) > 1:
        issues.append(f"queue staging has duplicate package rows for {PACKAGE_ID}")
    if not design_item:
        issues.append(f"design queue item {PACKAGE_ID} is missing from canonical staging queue")
    elif len(design_items) > 1:
        issues.append(f"design queue staging has duplicate package rows for {PACKAGE_ID}")
    issues.extend(_frontier_reuse_issues(design_queue.get("items") or [], "design queue"))
    issues.extend(_frontier_reuse_issues(queue.get("items") or [], "queue"))
    if str(design_queue.get("program_wave") or "").strip() != PROGRAM_WAVE:
        issues.append("design queue staging program_wave is not next_90_day_product_advance")
    if str(design_queue.get("status") or "").strip() != QUEUE_STATUS:
        issues.append("design queue staging status is not live_parallel_successor")
    if str(design_queue.get("source_registry_path") or "").strip() != str(SUCCESSOR_REGISTRY):
        issues.append("design queue staging source_registry_path is not the canonical successor registry")
    if str(queue.get("program_wave") or "").strip() != PROGRAM_WAVE:
        issues.append("queue staging program_wave is not next_90_day_product_advance")
    if str(queue.get("status") or "").strip() != QUEUE_STATUS:
        issues.append("queue staging status is not live_parallel_successor")
    if str(queue.get("source_registry_path") or "").strip() != str(SUCCESSOR_REGISTRY):
        issues.append("queue staging source_registry_path is not the canonical successor registry")
    if str(queue.get("source_design_queue_path") or "").strip() != str(DESIGN_QUEUE_STAGING):
        issues.append("queue staging source_design_queue_path is not the canonical design staging queue")
    if design_item:
        issues.extend(_queue_authority_issues(design_item, "design queue"))
        issues.extend(_queue_proof_issues(design_item, "design queue", repo_root))
    if item:
        issues.extend(_queue_authority_issues(item, "queue"))
        issues.extend(_queue_proof_issues(item, "queue", repo_root))
    queue_mirror_drift = _queue_mirror_drift(design_item, item) if design_item and item else []
    if queue_mirror_drift:
        issues.append(
            "Fleet queue mirror package row diverges from design-owned queue staging for field(s): "
            + ", ".join(row["field"] for row in queue_mirror_drift)
        )
    if milestone:
        if str(milestone.get("title") or "").strip() != EXPECTED_MILESTONE_TITLE:
            issues.append("milestone 106 title no longer matches package authority")
        if str(milestone.get("status") or "").strip() != "in_progress":
            issues.append("milestone 106 is not in_progress in successor registry")
        owners = set(_norm_list(milestone.get("owners")))
        if "fleet" not in owners:
            issues.append("milestone 106 no longer names fleet as an owner")
        if not registry_work_task:
            issues.append("fleet registry work task 106.1 is missing from milestone 106")
        if len(registry_work_tasks) > 1:
            issues.append("milestone 106 has duplicate registry work task 106.1 rows")
        if registry_work_task:
            if str(registry_work_task.get("owner") or "").strip() != "fleet":
                issues.append("registry work task 106.1 is no longer owned by fleet")
            if str(registry_work_task.get("status") or "").strip().lower() not in COMPLETE_STATUSES:
                issues.append("registry work task 106.1 is not marked complete")
            evidence_text = "\n".join(_norm_list(registry_work_task.get("evidence")))
            evidence_entries = _norm_list(registry_work_task.get("evidence"))
            missing_registry_evidence = [
                marker
                for marker in REQUIRED_REGISTRY_EVIDENCE_MARKERS
                if marker not in evidence_text
            ]
            if missing_registry_evidence:
                issues.append(
                    "registry work task 106.1 evidence is missing required weekly governor marker(s): "
                    + ", ".join(missing_registry_evidence)
                )
            disallowed_registry_evidence = _disallowed_worker_proof_entries(evidence_entries)
            if disallowed_registry_evidence:
                issues.append(
                    "registry work task 106.1 evidence includes active-run or operator-helper "
                    "command evidence that worker packages must not invoke: "
                    + ", ".join(disallowed_registry_evidence)
                )
            out_of_scope_evidence_paths = _fleet_proof_path_scope_issues(evidence_entries)
            if out_of_scope_evidence_paths:
                issues.append(
                    "registry work task 106.1 evidence includes Fleet proof path(s) outside "
                    f"allowed package roots {', '.join(ALLOWED_PATHS)}: "
                    + ", ".join(out_of_scope_evidence_paths)
                )
            missing_resolving_paths = _missing_resolving_proof_paths(repo_root)
            missing_from_registry = [
                marker
                for marker in missing_resolving_paths
                if marker in evidence_text or f"/docker/fleet/{marker}" in evidence_text
            ]
            if missing_from_registry:
                issues.append(
                    "registry work task 106.1 evidence includes source anchor(s) that no longer resolve: "
                    + ", ".join(missing_from_registry)
                )
    if local_commit_resolution["status"] == "fail":
        issues.append(
            "local M106 proof floor commit(s) no longer resolve in Fleet repo: "
            + ", ".join(local_commit_resolution["missing_commits"])
        )
    return {
        "status": "pass" if not issues else "fail",
        "package_id": PACKAGE_ID,
        "milestone_id": MILESTONE_ID,
        "successor_frontier_ids": list(SUCCESSOR_FRONTIER_IDS),
        "repo": "fleet",
        "owned_surfaces": list(OWNED_SURFACES),
        "allowed_paths": list(ALLOWED_PATHS),
        "registry_milestone_title": str(milestone.get("title") or "").strip(),
        "expected_registry_milestone_title": EXPECTED_MILESTONE_TITLE,
        "registry_status": str(milestone.get("status") or "").strip(),
        "registry_work_task_status": str(registry_work_task.get("status") or "").strip(),
        "registry_work_task_owner": str(registry_work_task.get("owner") or "").strip(),
        "registry_dependencies": [
            _coerce_int(dep, -1)
            for dep in (milestone.get("dependencies") or [])
            if _coerce_int(dep, -1) >= 0
        ],
        "dependency_posture": dependency_posture,
        "queue_status": str(item.get("status") or "").strip(),
        "design_queue_status": str(design_item.get("status") or "").strip(),
        "queue_frontier_id": str(item.get("frontier_id") or "").strip(),
        "design_queue_frontier_id": str(design_item.get("frontier_id") or "").strip(),
        "design_queue_source_registry_path": str(design_queue.get("source_registry_path") or "").strip(),
        "queue_source_registry_path": str(queue.get("source_registry_path") or "").strip(),
        "queue_source_design_queue_path": str(queue.get("source_design_queue_path") or "").strip(),
        "queue_title": str(item.get("title") or "").strip(),
        "queue_task": str(item.get("task") or "").strip(),
        "expected_queue_title": EXPECTED_PACKAGE_TITLE,
        "expected_queue_task": EXPECTED_PACKAGE_TASK,
        "queue_mirror_status": "in_sync" if not queue_mirror_drift else "drift",
        "queue_mirror_drift": queue_mirror_drift,
        "required_queue_proof_markers": list(REQUIRED_QUEUE_PROOF_MARKERS),
        "required_registry_evidence_markers": list(REQUIRED_REGISTRY_EVIDENCE_MARKERS),
        "required_resolving_proof_paths": list(REQUIRED_RESOLVING_PROOF_PATHS),
        "local_proof_floor_commits": list(LOCAL_PROOF_FLOOR_COMMITS),
        "local_commit_resolution": local_commit_resolution,
        "disallowed_worker_proof_command_markers": list(DISALLOWED_WORKER_PROOF_COMMAND_MARKERS),
        "issues": issues,
    }


def _decision_signal_map(decision: Dict[str, Any]) -> Dict[str, str]:
    signals: Dict[str, str] = {}
    for item in decision.get("cited_signals") or []:
        text = str(item or "").strip()
        if not text:
            continue
        key, _, value = text.partition("=")
        if key.strip():
            signals[key.strip()] = value.strip()
    return signals


def _launch_decision(weekly_pulse: Dict[str, Any]) -> Dict[str, Any]:
    for row in weekly_pulse.get("governor_decisions") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("action") or "").strip() in {"freeze_launch", "launch_expand"}:
            return row
    return {}


def verify_weekly_inputs(weekly_pulse: Dict[str, Any], launch_decision: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    generated_at = _parse_iso_utc(weekly_pulse.get("generated_at"))
    now = dt.datetime.now(UTC)
    decision_actions = [
        str(row.get("action") or "").strip()
        for row in weekly_pulse.get("governor_decisions") or []
        if isinstance(row, dict) and str(row.get("action") or "").strip()
    ]
    duplicate_actions = sorted(
        {
            action
            for action in decision_actions
            if decision_actions.count(action) > 1
        }
    )
    launch_action_rows = [
        action for action in decision_actions if action in {"freeze_launch", "launch_expand"}
    ]
    if str(weekly_pulse.get("contract_name") or "").strip() != "chummer.weekly_product_pulse":
        issues.append("weekly pulse contract_name is missing or unexpected")
    if _coerce_int(weekly_pulse.get("contract_version"), 0) < 3:
        issues.append("weekly pulse contract_version is stale; expected >=3")
    if not generated_at:
        issues.append("weekly pulse generated_at is missing or invalid")
    else:
        future_skew_seconds = int((generated_at - now).total_seconds())
        if future_skew_seconds > GENERATED_AT_MAX_FUTURE_SKEW_SECONDS:
            issues.append(f"weekly pulse generated_at is future-dated ({future_skew_seconds}s ahead)")
        age_seconds = int((now - generated_at).total_seconds())
        if age_seconds > WEEKLY_PULSE_MAX_AGE_SECONDS:
            issues.append(f"weekly pulse is stale ({age_seconds}s old)")
    if not launch_decision:
        issues.append("weekly pulse is missing a launch governance decision")
    else:
        signals = _decision_signal_map(launch_decision)
        missing = [key for key in REQUIRED_LAUNCH_SIGNALS if not signals.get(key)]
        if missing:
            issues.append("weekly pulse launch governance decision is missing cited signal(s): " + ", ".join(missing))
    if duplicate_actions:
        issues.append(
            "weekly pulse governor_decisions has duplicate action row(s): "
            + ", ".join(duplicate_actions)
        )
    if len(launch_action_rows) != 1:
        issues.append(
            "weekly pulse must contain exactly one launch governance action "
            f"(freeze_launch or launch_expand); found {len(launch_action_rows)}"
        )
    return {
        "status": "pass" if not issues else "fail",
        "generated_at": str(weekly_pulse.get("generated_at") or "").strip(),
        "max_age_seconds": WEEKLY_PULSE_MAX_AGE_SECONDS,
        "required_launch_signals": list(REQUIRED_LAUNCH_SIGNALS),
        "issues": issues,
    }


def verify_source_inputs(
    *,
    repo_root: Path,
    registry: Dict[str, Any],
    closed_flagship_registry: Dict[str, Any],
    design_queue: Dict[str, Any],
    queue: Dict[str, Any],
    weekly_pulse: Dict[str, Any],
    flagship_readiness: Dict[str, Any],
    journey_gates: Dict[str, Any],
    support_packets: Dict[str, Any],
    status_plane: Dict[str, Any],
    source_paths: Dict[str, str],
) -> Dict[str, Any]:
    required: Dict[str, tuple[Dict[str, Any], str]] = {
        "successor_registry": (registry, "program_wave"),
        "closed_flagship_registry": (closed_flagship_registry, "program_wave"),
        "design_queue_staging": (design_queue, "items"),
        "queue_staging": (queue, "items"),
        "weekly_pulse": (weekly_pulse, "contract_name"),
        "flagship_readiness": (flagship_readiness, "status"),
        "journey_gates": (journey_gates, "summary"),
        "support_packets": (support_packets, "summary"),
        "status_plane": (status_plane, "whole_product_final_claim_status"),
    }
    rows: Dict[str, Dict[str, Any]] = {}
    issues: List[str] = []
    now = dt.datetime.now(UTC)
    for name, (payload, required_key) in required.items():
        present = bool(payload)
        has_required_key = bool(payload.get(required_key)) if present else False
        state = "present" if present and has_required_key else "missing_or_unparseable"
        rows[name] = {
            "state": state,
            "required_key": required_key,
        }
        if state != "present":
            issues.append(f"{name} is missing, empty, unparseable, or lacks {required_key}")
        if name in REQUIRED_GENERATED_SOURCE_INPUTS:
            generated_at = str(payload.get("generated_at") or "").strip() if present else ""
            rows[name]["generated_at"] = generated_at
            rows[name]["source_path"] = str(dict(source_paths or {}).get(name) or "").strip()
            parsed_generated_at = _parse_iso_utc(generated_at)
            if state == "present" and not parsed_generated_at:
                issues.append(f"{name} generated_at is missing or invalid")
            elif state == "present" and parsed_generated_at:
                future_skew_seconds = int((parsed_generated_at - now).total_seconds())
                if future_skew_seconds > GENERATED_AT_MAX_FUTURE_SKEW_SECONDS:
                    issues.append(f"{name} generated_at is future-dated ({future_skew_seconds}s ahead)")
    support_successor_proof = dict(support_packets.get("successor_package_verification") or {})
    support_successor_status = str(support_successor_proof.get("status") or "").strip()
    support_generated_at = _parse_iso_utc(support_packets.get("generated_at"))
    support_source_path = str(dict(source_paths or {}).get("support_packets") or "").strip()
    rows["support_packets"]["successor_package_verification_status"] = (
        support_successor_status or "missing"
    )
    rows["support_packets"]["max_age_seconds"] = SUPPORT_PACKETS_MAX_AGE_SECONDS
    if support_source_path:
        try:
            rows["support_packets"]["source_sha256"] = hashlib.sha256(
                Path(support_source_path).read_bytes()
            ).hexdigest()
        except OSError:
            rows["support_packets"]["source_sha256"] = ""
    if rows["support_packets"]["state"] == "present" and support_successor_status != "pass":
        issues.append(
            "support_packets successor_package_verification.status is not pass; "
            "weekly governor support truth must be backed by the M102 receipt-gated package proof"
        )
    if rows["support_packets"]["state"] == "present":
        if not support_generated_at:
            issues.append("support_packets generated_at is missing or invalid")
        else:
            support_age_seconds = int((now - support_generated_at).total_seconds())
            if support_age_seconds > SUPPORT_PACKETS_MAX_AGE_SECONDS:
                issues.append(f"support_packets are stale ({support_age_seconds}s old)")
    closed_flagship_status = str(closed_flagship_registry.get("status") or "").strip()
    closed_flagship_wave = str(closed_flagship_registry.get("program_wave") or "").strip()
    closed_waves = [
        row
        for row in closed_flagship_registry.get("waves") or []
        if isinstance(row, dict)
    ]
    closed_milestones = [
        row
        for row in closed_flagship_registry.get("milestones") or []
        if isinstance(row, dict)
    ]
    open_closed_waves = [
        str(row.get("id") or "").strip()
        for row in closed_waves
        if str(row.get("status") or "").strip().lower() not in COMPLETE_STATUSES
    ]
    open_closed_milestones = [
        _coerce_int(row.get("id"), -1)
        for row in closed_milestones
        if str(row.get("status") or "").strip().lower() not in COMPLETE_STATUSES
        and _coerce_int(row.get("id"), -1) >= 0
    ]
    rows["closed_flagship_registry"].update(
        {
            "program_wave": closed_flagship_wave,
            "status": closed_flagship_status or "missing",
            "source_path": str(dict(source_paths or {}).get("closed_flagship_registry") or "").strip(),
            "wave_count": len(closed_waves),
            "milestone_count": len(closed_milestones),
            "open_wave_ids": open_closed_waves,
            "open_milestone_ids": open_closed_milestones,
        }
    )
    if rows["closed_flagship_registry"]["state"] == "present":
        if closed_flagship_wave != CLOSED_FLAGSHIP_WAVE:
            issues.append("closed_flagship_registry program_wave is not next_12_biggest_wins")
        if closed_flagship_status.lower() not in COMPLETE_STATUSES:
            issues.append("closed_flagship_registry status is not complete")
        if open_closed_waves:
            issues.append(
                "closed_flagship_registry has reopened wave(s): "
                + ", ".join(open_closed_waves)
            )
        if open_closed_milestones:
            issues.append(
                "closed_flagship_registry has reopened milestone(s): "
                + ", ".join(str(item) for item in open_closed_milestones)
            )
    disallowed_source_paths = _disallowed_worker_proof_entries(
        [f"{name}: {path}" for name, path in sorted(dict(source_paths or {}).items())]
    )
    rows["source_path_hygiene"] = {
        "state": "pass" if not disallowed_source_paths else "fail",
        "blocked_markers": list(DISALLOWED_WORKER_PROOF_COMMAND_MARKERS),
        "disallowed_source_paths": disallowed_source_paths,
    }
    if disallowed_source_paths:
        issues.append(
            "weekly governor source paths include active-run or operator-helper evidence "
            "that worker packets must not cite: "
            + ", ".join(disallowed_source_paths)
        )
    production_path_drift: Dict[str, Dict[str, str]] = {}
    if repo_root.resolve() == ROOT.resolve():
        for name, expected_path in EXPECTED_PRODUCTION_SOURCE_PATHS.items():
            actual_path = str(dict(source_paths or {}).get(name) or "").strip()
            if actual_path != expected_path:
                production_path_drift[name] = {
                    "expected": expected_path,
                    "actual": actual_path,
                }
    rows["source_path_authority"] = {
        "state": "pass" if not production_path_drift else "fail",
        "expected_paths": dict(EXPECTED_PRODUCTION_SOURCE_PATHS),
        "production_path_drift": production_path_drift,
    }
    if production_path_drift:
        issues.append(
            "weekly governor production source paths must use canonical registry, queue, "
            "and generated artifact inputs; non-canonical override(s): "
            + ", ".join(sorted(production_path_drift))
        )
    return {
        "status": "pass" if not issues else "fail",
        "required_inputs": rows,
        "issues": issues,
    }


def _support_summary(support_packets: Dict[str, Any]) -> Dict[str, Any]:
    summary = dict(support_packets.get("summary") or {})
    followthrough = dict(support_packets.get("reporter_followthrough_plan") or {})
    receipt_gates = dict(support_packets.get("followthrough_receipt_gates") or {})
    gate_counts = dict(receipt_gates.get("gate_counts") or {})
    return {
        "open_packet_count": _coerce_int(summary.get("open_packet_count"), 0),
        "open_non_external_packet_count": _coerce_int(summary.get("open_non_external_packet_count"), 0),
        "closure_waiting_on_release_truth": _coerce_int(summary.get("closure_waiting_on_release_truth"), 0),
        "update_required_misrouted_case_count": _coerce_int(summary.get("update_required_misrouted_case_count"), 0),
        "reporter_followthrough_ready_count": _coerce_int(summary.get("reporter_followthrough_ready_count"), 0),
        "fix_available_ready_count": _coerce_int(summary.get("fix_available_ready_count"), 0),
        "please_test_ready_count": _coerce_int(summary.get("please_test_ready_count"), 0),
        "recovery_loop_ready_count": _coerce_int(summary.get("recovery_loop_ready_count"), 0),
        "reporter_followthrough_blocked_missing_install_receipts_count": _coerce_int(
            summary.get("reporter_followthrough_blocked_missing_install_receipts_count"),
            0,
        ),
        "reporter_followthrough_blocked_receipt_mismatch_count": _coerce_int(
            summary.get("reporter_followthrough_blocked_receipt_mismatch_count"),
            0,
        ),
        "reporter_followthrough_plan_ready_count": _coerce_int(followthrough.get("ready_count"), 0),
        "reporter_followthrough_plan_blocked_missing_install_receipts_count": _coerce_int(
            followthrough.get("blocked_missing_install_receipts_count"),
            0,
        ),
        "reporter_followthrough_plan_blocked_receipt_mismatch_count": _coerce_int(
            followthrough.get("blocked_receipt_mismatch_count"),
            0,
        ),
        "followthrough_receipt_gates_ready_count": _coerce_int(receipt_gates.get("ready_count"), 0),
        "followthrough_receipt_gates_blocked_missing_install_receipts_count": _coerce_int(
            receipt_gates.get("blocked_missing_install_receipts_count"),
            0,
        ),
        "followthrough_receipt_gates_blocked_receipt_mismatch_count": _coerce_int(
            receipt_gates.get("blocked_receipt_mismatch_count"),
            0,
        ),
        "followthrough_receipt_gates_installed_build_receipted_count": _coerce_int(
            gate_counts.get("installed_build_receipted"),
            0,
        ),
        "followthrough_receipt_gates_installation_bound_count": _coerce_int(
            gate_counts.get("installed_build_receipt_installation_bound"),
            0,
        ),
    }


def _flagship_parity_summary(flagship_readiness: Dict[str, Any]) -> Dict[str, Any]:
    planes = dict(flagship_readiness.get("readiness_planes") or {})
    flagship = dict(planes.get("flagship_ready") or {})
    evidence = dict(flagship.get("evidence") or {})
    status_counts = {
        str(key): _coerce_int(value, 0)
        for key, value in dict(evidence.get("status_counts") or {}).items()
    }
    families_below_task = _norm_list(evidence.get("families_below_task_proven"))
    families_below_veteran = _norm_list(evidence.get("families_below_veteran_approved"))
    families_below_gold = _norm_list(evidence.get("families_below_gold_ready"))
    known_family_count = sum(status_counts.values())
    if not evidence or not bool(evidence.get("registry_present")) or known_family_count == 0:
        release_truth_status = "unknown"
    elif families_below_task or families_below_veteran:
        release_truth_status = "blocked"
    elif families_below_gold:
        release_truth_status = "veteran_ready"
    else:
        release_truth_status = "gold_ready"
    return {
        "release_truth_status": release_truth_status,
        "readiness_plane_status": str(flagship.get("status") or "unknown").strip(),
        "registry_path": str(evidence.get("registry_path") or "").strip(),
        "registry_present": bool(evidence.get("registry_present")),
        "status_counts": status_counts,
        "families_below_task_proven": families_below_task,
        "families_below_veteran_approved": families_below_veteran,
        "families_below_gold_ready": families_below_gold,
    }


def _gate_row(name: str, state: str, required: str, observed: Any) -> Dict[str, str]:
    return {
        "name": name,
        "state": state,
        "required": required,
        "observed": str(observed if observed is not None else "unknown").strip() or "unknown",
    }


def _status_copy(*, launch_allowed: bool, rollback_watch: bool, launch_reason: str) -> Dict[str, str]:
    if launch_allowed:
        return {
            "state": "launch_expand_allowed",
            "headline": "Measured launch expansion is allowed.",
            "body": "Readiness, parity, support, canary, dependency, and release-proof gates are green for this weekly packet.",
        }
    if rollback_watch:
        return {
            "state": "freeze_with_rollback_watch",
            "headline": "Launch expansion is frozen with rollback watch active.",
            "body": launch_reason
            or "Release or support truth requires rollback watch before any broader launch move.",
        }
    return {
        "state": "freeze_launch",
        "headline": "Launch expansion remains frozen.",
        "body": launch_reason
        or "Measured launch gates are incomplete, so the weekly governor packet holds broad promotion.",
    }


def _decision_alignment(actual_action: str, launch_allowed: bool) -> Dict[str, Any]:
    expected_action = "launch_expand" if launch_allowed else "freeze_launch"
    action = str(actual_action or "").strip() or "freeze_launch"
    issues: List[str] = []
    if action != expected_action:
        issues.append(
            f"weekly pulse launch action {action} does not match measured gate action {expected_action}"
        )
    return {
        "status": "pass" if not issues else "fail",
        "actual_action": action,
        "expected_action": expected_action,
        "issues": issues,
    }


def _governor_decision_rows(
    decision_board: Dict[str, Any],
    decision_gate_ledger: Dict[str, Any],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for action in ("launch_expand", "freeze_launch", "canary", "rollback", "focus_shift"):
        board = dict(decision_board.get(action) or {})
        rows.append(
            {
                "action": action,
                "state": str(board.get("state") or "unknown").strip() or "unknown",
                "reason": str(board.get("reason") or "").strip(),
                "gate_count": len(decision_gate_ledger.get(action) or []),
            }
        )
    return rows


def _blocked_dependency_package_ids(source_input_health: Dict[str, Any]) -> List[str]:
    issues = _norm_list(source_input_health.get("issues"))
    blocked: List[str] = []
    if any("support_packets successor_package_verification.status" in issue for issue in issues):
        blocked.append(SUPPORT_DEPENDENCY_PACKAGE_ID)
    return blocked


def build_payload(
    *,
    repo_root: Path,
    registry: Dict[str, Any],
    closed_flagship_registry: Dict[str, Any],
    design_queue: Dict[str, Any],
    queue: Dict[str, Any],
    weekly_pulse: Dict[str, Any],
    flagship_readiness: Dict[str, Any],
    journey_gates: Dict[str, Any],
    support_packets: Dict[str, Any],
    status_plane: Dict[str, Any],
    source_paths: Dict[str, str],
) -> Dict[str, Any]:
    verification = verify_package(registry, design_queue, queue, repo_root)
    milestone = _find_milestone(registry)
    work_task_posture = _work_task_posture(milestone) if milestone else {
        "work_tasks": [],
        "open_sibling_work_task_ids": [],
    }
    launch_decision = _launch_decision(weekly_pulse)
    weekly_input_health = verify_weekly_inputs(weekly_pulse, launch_decision)
    source_input_health = verify_source_inputs(
        repo_root=repo_root,
        registry=registry,
        closed_flagship_registry=closed_flagship_registry,
        design_queue=design_queue,
        queue=queue,
        weekly_pulse=weekly_pulse,
        flagship_readiness=flagship_readiness,
        journey_gates=journey_gates,
        support_packets=support_packets,
        status_plane=status_plane,
        source_paths=source_paths,
    )
    launch_signals = _decision_signal_map(launch_decision)
    supporting = dict(weekly_pulse.get("supporting_signals") or {})
    provider = dict(supporting.get("provider_route_stewardship") or {})
    closure = dict(supporting.get("closure_health") or {})
    adoption = dict(supporting.get("adoption_health") or {})
    journey_summary = dict(journey_gates.get("summary") or {})
    support = _support_summary(support_packets)
    local_release_proof = str(
        launch_signals.get("local_release_proof_status")
        or adoption.get("local_release_proof_status")
        or "unknown"
    ).strip()
    canary_status = str(
        launch_signals.get("provider_canary_status") or provider.get("canary_status") or "unknown"
    ).strip()
    closure_state = str(
        launch_signals.get("closure_health_state") or closure.get("state") or "unknown"
    ).strip()
    status_plane_final_claim = str(
        status_plane.get("whole_product_final_claim_status") or ""
    ).strip()
    journey_state = str(
        launch_signals.get("journey_gate_state")
        or journey_summary.get("overall_state")
        or (weekly_pulse.get("journey_gate_health") or {}).get("state")
        or "unknown"
    ).strip()
    readiness_status = str(flagship_readiness.get("status") or "unknown").strip()
    parity = _flagship_parity_summary(flagship_readiness)
    parity_gold_ready = parity["release_truth_status"] == "gold_ready"
    dependency_posture = dict(verification.get("dependency_posture") or {})
    dependency_status = str(dependency_posture.get("status") or "open").strip()
    launch_allowed = (
        verification["status"] == "pass"
        and weekly_input_health["status"] == "pass"
        and source_input_health["status"] == "pass"
        and dependency_status == "satisfied"
        and readiness_status == "pass"
        and parity_gold_ready
        and status_plane_final_claim == "pass"
        and journey_state == "ready"
        and local_release_proof == "passed"
        and canary_status == "Canary green on all active lanes"
        and closure_state == "clear"
        and support["open_non_external_packet_count"] == 0
    )
    launch_action = str(launch_decision.get("action") or "freeze_launch").strip()
    decision_alignment = _decision_alignment(launch_action, launch_allowed)
    freeze_active = not launch_allowed
    rollback_watch = (
        support["closure_waiting_on_release_truth"] > 0
        or support["update_required_misrouted_case_count"] > 0
        or str((weekly_pulse.get("release_health") or {}).get("state") or "").strip() not in {
            "green",
            "green_or_explained",
            "ready",
        }
    )
    launch_gate_ledger = [
        _gate_row(
            "package_authority",
            "pass" if verification["status"] == "pass" else "fail",
            "pass",
            verification["status"],
        ),
        _gate_row(
            "weekly_input_health",
            "pass" if weekly_input_health["status"] == "pass" else "fail",
            "pass",
            weekly_input_health["status"],
        ),
        _gate_row(
            "source_input_health",
            "pass" if source_input_health["status"] == "pass" else "fail",
            "pass",
            source_input_health["status"],
        ),
        _gate_row(
            "decision_alignment",
            "pass" if decision_alignment["status"] == "pass" else "fail",
            decision_alignment["expected_action"],
            decision_alignment["actual_action"],
        ),
        _gate_row(
            "successor_dependencies",
            "pass" if dependency_status == "satisfied" else "blocked",
            "satisfied",
            dependency_status,
        ),
        _gate_row(
            "flagship_readiness",
            "pass" if readiness_status == "pass" else "blocked",
            "pass",
            readiness_status,
        ),
        _gate_row(
            "flagship_parity",
            "pass" if parity_gold_ready else "blocked",
            "gold_ready",
            parity["release_truth_status"],
        ),
        _gate_row(
            "status_plane_final_claim",
            "pass" if status_plane_final_claim == "pass" else "blocked",
            "pass",
            status_plane_final_claim or "unknown",
        ),
        _gate_row(
            "journey_gates",
            "pass" if journey_state == "ready" else "blocked",
            "ready",
            journey_state,
        ),
        _gate_row(
            "local_release_proof",
            "pass" if local_release_proof == "passed" else "blocked",
            "passed",
            local_release_proof,
        ),
        _gate_row(
            "provider_canary",
            "pass" if canary_status == "Canary green on all active lanes" else "blocked",
            "Canary green on all active lanes",
            canary_status,
        ),
        _gate_row("closure_health", "pass" if closure_state == "clear" else "blocked", "clear", closure_state),
        _gate_row(
            "support_packets",
            "pass" if support["open_non_external_packet_count"] == 0 else "blocked",
            "0 open non-external packets",
            support["open_non_external_packet_count"],
        ),
    ]
    rollback_gate_ledger = [
        _gate_row(
            "closure_waiting_on_release_truth",
            "watch" if support["closure_waiting_on_release_truth"] > 0 else "clear",
            "0",
            support["closure_waiting_on_release_truth"],
        ),
        _gate_row(
            "update_required_misrouted_cases",
            "watch" if support["update_required_misrouted_case_count"] > 0 else "clear",
            "0",
            support["update_required_misrouted_case_count"],
        ),
        _gate_row(
            "release_health",
            "clear"
            if str((weekly_pulse.get("release_health") or {}).get("state") or "").strip()
            in {"green", "green_or_explained", "ready"}
            else "watch",
            "green, green_or_explained, or ready",
            (weekly_pulse.get("release_health") or {}).get("state"),
        ),
    ]
    launch_reason = str(launch_decision.get("reason") or "").strip()
    measured_loop_ready = (
        verification["status"] == "pass"
        and weekly_input_health["status"] == "pass"
        and source_input_health["status"] == "pass"
        and decision_alignment["status"] == "pass"
        and readiness_status == "pass"
        and parity["release_truth_status"] in {"gold_ready", "veteran_ready"}
        and status_plane_final_claim == "pass"
        and support["open_non_external_packet_count"] == 0
    )
    package_complete = (
        verification["status"] == "pass"
        and str(verification.get("queue_status") or "").strip().lower() in COMPLETE_STATUSES
        and str(verification.get("registry_work_task_status") or "").strip().lower() in COMPLETE_STATUSES
    )
    remaining_dependency_ids = [
        _coerce_int(dep, -1)
        for dep in (
            list(dependency_posture.get("open_dependency_ids") or [])
            + list(dependency_posture.get("missing_dependency_ids") or [])
        )
        if _coerce_int(dep, -1) >= 0
    ]
    open_sibling_work_task_ids = _norm_list(work_task_posture.get("open_sibling_work_task_ids"))
    blocked_dependency_package_ids = _blocked_dependency_package_ids(source_input_health)
    repeat_prevention = {
        "status": "closed_for_fleet_package" if package_complete else "blocked",
        "closed_package_id": PACKAGE_ID,
        "closed_work_task_id": "106.1",
        "closed_successor_frontier_ids": list(SUCCESSOR_FRONTIER_IDS),
        "local_proof_floor_commits": list(LOCAL_PROOF_FLOOR_COMMITS),
        "local_commit_resolution": verification.get("local_commit_resolution"),
        "do_not_reopen_owned_surfaces": package_complete,
        "owned_surfaces": list(OWNED_SURFACES),
        "allowed_paths": list(ALLOWED_PATHS),
        "remaining_dependency_ids": remaining_dependency_ids,
        "blocked_dependency_package_ids": blocked_dependency_package_ids,
        "remaining_sibling_work_task_ids": open_sibling_work_task_ids,
        "handoff_rule": (
            "Do not repeat the Fleet weekly governor packet slice when package_verification.status is pass; "
            "route remaining M106 work to the listed dependency or sibling packages."
            if package_complete
            else "Package verification is blocked; fix package_verification.issues before treating this slice as closed."
        ),
        "worker_command_guard": {
            "status": "active_run_helpers_forbidden",
            "blocked_markers": list(DISALLOWED_WORKER_PROOF_COMMAND_MARKERS),
            "rule": "Worker proof must come from repo-local files, generated packets, and tests, not operator telemetry or active-run helper commands.",
        },
        "flagship_wave_guard": {
            "status": "closed_wave_not_reopened",
            "closed_wave": CLOSED_FLAGSHIP_WAVE,
            "closed_registry_status": str(closed_flagship_registry.get("status") or "").strip(),
            "closed_registry_path": str(dict(source_paths or {}).get("closed_flagship_registry") or "").strip(),
            "closed_registry_wave_count": len(
                [
                    row
                    for row in closed_flagship_registry.get("waves") or []
                    if isinstance(row, dict)
                ]
            ),
            "closed_registry_milestone_count": len(
                [
                    row
                    for row in closed_flagship_registry.get("milestones") or []
                    if isinstance(row, dict)
                ]
            ),
            "readiness_inputs": "read-only readiness, parity, journey, and support snapshots",
            "rule": (
                "Successor M106 packet work may summarize flagship readiness inputs, "
                "but must not reopen or re-scope the closed flagship wave."
            ),
        },
    }
    packet_status = "ready" if package_complete and measured_loop_ready else "blocked"
    if package_complete and measured_loop_ready:
        status_reason = "Fleet package is closed and the weekly measured rollout loop is ready."
    elif package_complete:
        status_reason = (
            "Fleet package is closed; measured rollout remains blocked by current "
            "source, dependency, or sibling gates."
        )
    else:
        status_reason = (
            "Fleet package closeout is blocked; inspect package_verification issues "
            "before treating this slice as closed."
        )
    decision_board = {
        "current_launch_action": launch_action,
        "current_launch_reason": str(launch_decision.get("reason") or "").strip(),
        "launch_expand": {
            "state": "allowed" if launch_allowed else "blocked",
            "reason": "All measured launch gates are green." if launch_allowed else "Hold expansion until successor dependencies, readiness, parity, status-plane final claim, local release proof, canary, closure, and support gates are all green.",
        },
        "freeze_launch": {
            "state": "active" if freeze_active else "available",
            "reason": str(launch_decision.get("reason") or "Freeze remains the fail-closed default when launch gates are incomplete.").strip(),
        },
        "canary": {
            "state": "ready" if canary_status == "Canary green on all active lanes" else "accumulating",
            "reason": canary_status or "Canary evidence is unavailable.",
            "next_decision": str(provider.get("next_decision") or "").strip(),
        },
        "rollback": {
            "state": "watch" if rollback_watch else "armed",
            "reason": "Rollback stays armed from release/support truth; watch is active when support closure or release health is not clear.",
        },
        "focus_shift": {
            "state": "queued_successor_wave",
            "reason": "Flagship closeout is complete; successor milestone 106 is the scoped Fleet packet slice.",
        },
    }
    decision_gate_ledger = {
        "launch_expand": launch_gate_ledger,
        "freeze_launch": [
            _gate_row(
                "fail_closed_default",
                "active" if freeze_active else "available",
                "active when any launch gate is not pass",
                "active" if freeze_active else "available",
            ),
        ],
        "canary": [
            _gate_row(
                "provider_canary",
                "ready" if canary_status == "Canary green on all active lanes" else "accumulating",
                "Canary green on all active lanes",
                canary_status,
            ),
        ],
        "rollback": rollback_gate_ledger,
        "focus_shift": [
            _gate_row(
                "successor_wave_scope",
                "queued_successor_wave",
                "closed flagship wave remains read-only and M106 routes only scoped successor work",
                "next90-m106-fleet-governor-packet",
            ),
        ],
    }
    return {
        "contract_name": "fleet.weekly_governor_packet",
        "schema_version": 1,
        "status": packet_status,
        "status_reason": status_reason,
        "generated_at": iso_now(),
        "as_of": str(weekly_pulse.get("as_of") or "").strip(),
        "program_wave": "next_90_day_product_advance",
        "wave_id": WAVE_ID,
        "successor_frontier_ids": list(SUCCESSOR_FRONTIER_IDS),
        "package_verification": verification,
        "weekly_input_health": weekly_input_health,
        "source_input_health": source_input_health,
        "decision_alignment": decision_alignment,
        "source_paths": source_paths,
        "truth_inputs": {
            "weekly_pulse_contract": str(weekly_pulse.get("contract_name") or "").strip(),
            "weekly_pulse_version": _coerce_int(weekly_pulse.get("contract_version"), 0),
            "flagship_readiness_status": readiness_status,
            "flagship_parity_release_truth": parity,
            "journey_gate_state": journey_state,
            "local_release_proof_status": local_release_proof,
            "provider_canary_status": canary_status,
            "closure_health_state": closure_state,
            "successor_dependency_status": dependency_status,
            "successor_dependency_posture": dependency_posture,
            "support_summary": support,
            "status_plane_final_claim": status_plane_final_claim,
            "closed_flagship_registry_status": str(closed_flagship_registry.get("status") or "").strip(),
        },
        "decision_board": decision_board,
        "decision_gate_ledger": decision_gate_ledger,
        "governor_decisions": _governor_decision_rows(decision_board, decision_gate_ledger),
        "public_status_copy": _status_copy(
            launch_allowed=launch_allowed,
            rollback_watch=rollback_watch,
            launch_reason=launch_reason,
        ),
        "package_closeout": {
            "status": "fleet_package_complete" if package_complete else "blocked",
            "do_not_reopen_package": package_complete,
            "package_scope": "next90-m106 Fleet weekly governor packet only",
            "successor_frontier_ids": list(SUCCESSOR_FRONTIER_IDS),
            "owned_surfaces": list(OWNED_SURFACES),
            "closeout_reason": (
                "Fleet package authority, queue closeout, registry work task 106.1, generated packet, markdown packet, and proof markers are current."
                if package_complete
                else "Fleet package authority or proof is not complete; inspect package_verification issues before reusing this slice."
            ),
            "remaining_milestone_dependency_ids": remaining_dependency_ids,
            "blocked_dependency_package_ids": blocked_dependency_package_ids,
            "remaining_sibling_work_task_ids": open_sibling_work_task_ids,
            "milestone_106_still_open_because": (
                "successor dependencies and sibling work tasks remain outside this Fleet package"
                if remaining_dependency_ids and open_sibling_work_task_ids
                else "successor dependencies remain outside this Fleet package"
                if remaining_dependency_ids
                else "sibling work tasks remain outside this Fleet package"
                if open_sibling_work_task_ids
                else "no open dependency or sibling task remains visible in the successor registry"
            ),
            "work_task_posture": work_task_posture,
        },
        "measured_rollout_loop": {
            "loop_status": "ready" if measured_loop_ready else "blocked",
            "cadence": "weekly",
            "blocked_dependency_package_ids": blocked_dependency_package_ids,
            "required_decision_actions": [
                "launch_expand",
                "freeze_launch",
                "canary",
                "rollback",
                "focus_shift",
            ],
            "evidence_requirements": [
                "successor registry and queue item match package authority",
                "design-owned queue staging and Fleet queue mirror both carry the completed package proof",
                "successor registry work task 106.1 remains complete with weekly governor evidence markers",
                "successor dependency milestones are complete before launch expansion is allowed",
                "weekly pulse cites journey, local release proof, canary, and closure signals",
                "flagship readiness remains green before any launch expansion",
                "flagship parity remains at veteran_ready or gold_ready before the measured loop can steer launch decisions",
                "status-plane final claim remains pass before launch expansion or measured rollout readiness",
                "support packet counts stay clear for non-external closure work",
                "fix-available, please-test, and recovery followthrough counts come from install-aware receipt gates",
                "queue closeout status remains complete and carries the required weekly governor proof receipts",
                "public status copy is derived from the same measured decision ledger as the governor packet",
            ],
        },
        "repeat_prevention": repeat_prevention,
        "risk_clusters": weekly_pulse.get("top_support_or_feedback_clusters") or [],
    }


def _markdown_status(value: Any) -> str:
    text = str(value or "").strip()
    return text if text else "unknown"


def _markdown_list(values: Any) -> str:
    if not isinstance(values, list) or not values:
        return "none"
    return ", ".join(str(value) for value in values)


def render_markdown_packet(payload: Dict[str, Any]) -> str:
    verification = dict(payload.get("package_verification") or {})
    truth = dict(payload.get("truth_inputs") or {})
    decision_board = dict(payload.get("decision_board") or {})
    loop = dict(payload.get("measured_rollout_loop") or {})
    closeout = dict(payload.get("package_closeout") or {})
    repeat_prevention = dict(payload.get("repeat_prevention") or {})
    worker_command_guard = dict(repeat_prevention.get("worker_command_guard") or {})
    flagship_wave_guard = dict(repeat_prevention.get("flagship_wave_guard") or {})
    weekly = dict(payload.get("weekly_input_health") or {})
    sources = dict(payload.get("source_input_health") or {})
    decision_alignment = dict(payload.get("decision_alignment") or {})
    support = dict(truth.get("support_summary") or {})
    dependency = dict(truth.get("successor_dependency_posture") or {})
    parity = dict(truth.get("flagship_parity_release_truth") or {})
    public_copy = dict(payload.get("public_status_copy") or {})
    gate_ledger = dict(payload.get("decision_gate_ledger") or {})
    risk_clusters = payload.get("risk_clusters") if isinstance(payload.get("risk_clusters"), list) else []

    lines = [
        "# Weekly Governor Packet",
        "",
        f"Generated: {_markdown_status(payload.get('generated_at'))}",
        f"As of: {_markdown_status(payload.get('as_of'))}",
        f"Package: {_markdown_status(verification.get('package_id'))}",
        f"Milestone: {verification.get('milestone_id', 'unknown')} - {_markdown_status(verification.get('registry_milestone_title'))}",
        "",
        "## Decision Board",
        "",
        "| Decision | State | Reason |",
        "| --- | --- | --- |",
    ]
    for key, label in (
        ("launch_expand", "Launch expand"),
        ("freeze_launch", "Freeze launch"),
        ("canary", "Canary"),
        ("rollback", "Rollback"),
        ("focus_shift", "Focus shift"),
    ):
        row = dict(decision_board.get(key) or {})
        reason = str(row.get("reason") or row.get("next_decision") or "").strip()
        lines.append(f"| {label} | {_markdown_status(row.get('state'))} | {reason or 'none'} |")

    lines.extend(
        [
            "",
            "## Measured Truth",
            "",
            f"- Package verification: {_markdown_status(verification.get('status'))}",
            f"- Weekly input health: {_markdown_status(weekly.get('status'))}",
            f"- Source input health: {_markdown_status(sources.get('status'))}",
            f"- Decision alignment: {_markdown_status(decision_alignment.get('status'))}",
            f"- Expected launch action: {_markdown_status(decision_alignment.get('expected_action'))}",
            f"- Actual launch action: {_markdown_status(decision_alignment.get('actual_action'))}",
            f"- Package closeout: {_markdown_status(closeout.get('status'))}",
            f"- Do not reopen package: {bool(closeout.get('do_not_reopen_package'))}",
            f"- Measured rollout loop: {_markdown_status(loop.get('loop_status'))}",
            f"- Registry work task 106.1 status: {_markdown_status(verification.get('registry_work_task_status'))}",
            f"- Required registry evidence markers: {len(verification.get('required_registry_evidence_markers') or [])}",
            f"- Queue closeout status: {_markdown_status(verification.get('queue_status'))}",
            f"- Queue mirror status: {_markdown_status(verification.get('queue_mirror_status'))}",
            f"- Required queue proof markers: {len(verification.get('required_queue_proof_markers') or [])}",
            f"- Required resolving proof paths: {_markdown_list(verification.get('required_resolving_proof_paths'))}",
            f"- Successor dependency posture: {_markdown_status(dependency.get('status'))}",
            f"- Open successor dependencies: {_markdown_list(dependency.get('open_dependency_ids'))}",
            f"- Remaining sibling work tasks: {_markdown_list(closeout.get('remaining_sibling_work_task_ids'))}",
            f"- Flagship readiness: {_markdown_status(truth.get('flagship_readiness_status'))}",
            f"- Flagship parity release truth: {_markdown_status(parity.get('release_truth_status'))}",
            f"- Journey gate state: {_markdown_status(truth.get('journey_gate_state'))}",
            f"- Local release proof: {_markdown_status(truth.get('local_release_proof_status'))}",
            f"- Provider canary: {_markdown_status(truth.get('provider_canary_status'))}",
            f"- Closure health: {_markdown_status(truth.get('closure_health_state'))}",
            f"- Open non-external support packets: {support.get('open_non_external_packet_count', 0)}",
            f"- Reporter followthrough ready: {support.get('reporter_followthrough_ready_count', 0)}",
            f"- Fix-available ready: {support.get('fix_available_ready_count', 0)}",
            f"- Please-test ready: {support.get('please_test_ready_count', 0)}",
            f"- Recovery-loop ready: {support.get('recovery_loop_ready_count', 0)}",
            f"- Followthrough blocked on install receipts: {support.get('reporter_followthrough_blocked_missing_install_receipts_count', 0)}",
            f"- Followthrough receipt mismatches: {support.get('reporter_followthrough_blocked_receipt_mismatch_count', 0)}",
            f"- Receipt-gated followthrough ready: {support.get('followthrough_receipt_gates_ready_count', 0)}",
            f"- Receipt-gated installed-build receipts: {support.get('followthrough_receipt_gates_installed_build_receipted_count', 0)}",
            f"- Closeout reason: {_markdown_status(closeout.get('closeout_reason'))}",
            f"- Milestone 106 still open because: {_markdown_status(closeout.get('milestone_106_still_open_because'))}",
            "",
            "## Repeat Prevention",
            "",
            f"- Status: {_markdown_status(repeat_prevention.get('status'))}",
            f"- Closed package: {_markdown_status(repeat_prevention.get('closed_package_id'))}",
            f"- Closed work task: {_markdown_status(repeat_prevention.get('closed_work_task_id'))}",
            f"- Closed successor frontier ids: {_markdown_list(repeat_prevention.get('closed_successor_frontier_ids'))}",
            f"- Local proof floor commits: {_markdown_list(repeat_prevention.get('local_proof_floor_commits'))}",
            f"- Do not reopen owned surfaces: {bool(repeat_prevention.get('do_not_reopen_owned_surfaces'))}",
            f"- Owned surfaces: {_markdown_list(repeat_prevention.get('owned_surfaces'))}",
            f"- Allowed paths: {_markdown_list(repeat_prevention.get('allowed_paths'))}",
            f"- Remaining dependency packages: {_markdown_list(repeat_prevention.get('remaining_dependency_ids'))}",
            f"- Blocked dependency packages: {_markdown_list(repeat_prevention.get('blocked_dependency_package_ids'))}",
            f"- Remaining sibling work tasks: {_markdown_list(repeat_prevention.get('remaining_sibling_work_task_ids'))}",
            f"- Handoff rule: {_markdown_status(repeat_prevention.get('handoff_rule'))}",
            f"- Worker command guard: {_markdown_status(worker_command_guard.get('status'))}",
            f"- Blocked helper markers: {_markdown_list(worker_command_guard.get('blocked_markers'))}",
            f"- Flagship wave guard: {_markdown_status(flagship_wave_guard.get('status'))}",
            f"- Closed flagship wave: {_markdown_status(flagship_wave_guard.get('closed_wave'))}",
            f"- Flagship readiness inputs: {_markdown_status(flagship_wave_guard.get('readiness_inputs'))}",
            "",
            "## Public Status Copy",
            "",
            f"- State: {_markdown_status(public_copy.get('state'))}",
            f"- Headline: {_markdown_status(public_copy.get('headline'))}",
            f"- Body: {_markdown_status(public_copy.get('body'))}",
            "",
            "## Launch Gate Ledger",
            "",
            "| Gate | State | Required | Observed |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in gate_ledger.get("launch_expand") or []:
        if not isinstance(row, dict):
            continue
        lines.append(
            f"| {_markdown_status(row.get('name'))} | {_markdown_status(row.get('state'))} | "
            f"{_markdown_status(row.get('required'))} | {_markdown_status(row.get('observed'))} |"
        )
    if not gate_ledger.get("launch_expand"):
        lines.append("| none | unknown | unknown | unknown |")

    lines.extend(
        [
            "",
            "## Required Weekly Actions",
            "",
        ]
    )
    for action in loop.get("required_decision_actions") or []:
        lines.append(f"- {action}")
    if not loop.get("required_decision_actions"):
        lines.append("- none")

    lines.extend(["", "## Evidence Requirements", ""])
    for requirement in loop.get("evidence_requirements") or []:
        lines.append(f"- {requirement}")
    if not loop.get("evidence_requirements"):
        lines.append("- none")

    lines.extend(["", "## Risk Clusters", ""])
    for cluster in risk_clusters:
        if not isinstance(cluster, dict):
            continue
        lines.append(
            f"- {_markdown_status(cluster.get('cluster_id'))}: "
            f"{_markdown_status(cluster.get('summary'))}"
        )
    if not risk_clusters:
        lines.append("- none")

    lines.extend(["", "## Source Paths", ""])
    for key, path in sorted(dict(payload.get("source_paths") or {}).items()):
        lines.append(f"- {key}: {path}")
    lines.append("")
    return "\n".join(lines)


def materialize(args: argparse.Namespace) -> Path:
    out_path = Path(args.out).resolve()
    markdown_out_path = (
        Path(args.markdown_out).resolve()
        if str(args.markdown_out or "").strip()
        else out_path.with_name("WEEKLY_GOVERNOR_PACKET.generated.md")
    )
    source_paths = {
        "successor_registry": str(Path(args.successor_registry).resolve()),
        "closed_flagship_registry": str(Path(args.closed_flagship_registry).resolve()),
        "design_queue_staging": str(Path(args.design_queue_staging).resolve()),
        "queue_staging": str(Path(args.queue_staging).resolve()),
        "weekly_pulse": str(Path(args.weekly_pulse).resolve()),
        "flagship_readiness": str(Path(args.flagship_readiness).resolve()),
        "journey_gates": str(Path(args.journey_gates).resolve()),
        "support_packets": str(Path(args.support_packets).resolve()),
        "status_plane": str(Path(args.status_plane).resolve()),
    }
    payload = build_payload(
        repo_root=Path(args.repo_root).resolve(),
        registry=_read_yaml(Path(args.successor_registry).resolve()),
        closed_flagship_registry=_read_yaml(Path(args.closed_flagship_registry).resolve()),
        design_queue=_read_yaml(Path(args.design_queue_staging).resolve()),
        queue=_read_yaml(Path(args.queue_staging).resolve()),
        weekly_pulse=_read_json(Path(args.weekly_pulse).resolve()),
        flagship_readiness=_read_json(Path(args.flagship_readiness).resolve()),
        journey_gates=_read_json(Path(args.journey_gates).resolve()),
        support_packets=_read_json(Path(args.support_packets).resolve()),
        status_plane=_read_yaml(Path(args.status_plane).resolve()),
        source_paths=source_paths,
    )
    write_text_atomic(out_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    if markdown_out_path is not None:
        write_text_atomic(markdown_out_path, render_markdown_packet(payload))
    repo_root = repo_root_for_published_path(out_path)
    if repo_root is not None:
        write_compile_manifest(repo_root)
    return out_path


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    out_path = materialize(args)
    print(f"wrote weekly governor packet: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
