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
EXPECTED_COMPLETION_ACTION = "verify_closed_package_only"
EXPECTED_DO_NOT_REOPEN_REASON = (
    "M106 Fleet weekly governor packet is complete; future shards must verify the "
    "weekly packet receipt, registry row, queue row, and design-queue row instead "
    "of reopening the measured rollout packet package."
)
EXPECTED_LANDED_COMMIT = "b467c27"
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
    "5193bce",
    "f662ad3",
    "5882234",
    "6c376e0",
    "00e870e",
    "81e1de8",
    "941c54d",
    "6981667",
    "4a13b47",
    "d597376",
    "233a52a",
    "fba96cc",
    "15efd7c",
    "f3bfb8d",
    "d15a7ae",
    "ac1c4ac",
    "b909cc5",
    "787d27a",
    "b467c27",
)
OWNED_SURFACES = ("weekly_governor_packet", "measured_rollout_loop")
ALLOWED_PATHS = ("admin", "scripts", "tests", ".codex-studio")
CLOSED_FLAGSHIP_WAVE = "next_12_biggest_wins"
REQUIRED_DECISION_ACTIONS = (
    "launch_expand",
    "freeze_launch",
    "canary",
    "rollback",
    "focus_shift",
)
REQUIRED_DECISION_SOURCE_GATES = {
    "launch_expand": (
        "package_authority",
        "weekly_input_health",
        "source_input_health",
        "decision_alignment",
        "successor_dependencies",
        "flagship_readiness",
        "flagship_parity",
        "flagship_quality",
        "status_plane_final_claim",
        "journey_gates",
        "local_release_proof",
        "weekly_adoption_truth",
        "provider_canary",
        "closure_health",
        "support_packets",
        "support_followthrough_receipts",
    ),
    "freeze_launch": ("fail_closed_default",),
    "canary": ("provider_canary",),
    "rollback": (
        "closure_waiting_on_release_truth",
        "update_required_misrouted_cases",
        "support_followthrough_receipt_blockers",
        "release_health",
    ),
    "focus_shift": ("successor_wave_scope",),
}
UTC = dt.timezone.utc
WEEKLY_PULSE_MAX_AGE_SECONDS = 8 * 24 * 60 * 60
SUPPORT_PACKETS_MAX_AGE_SECONDS = 8 * 24 * 60 * 60
GENERATED_SOURCE_MAX_AGE_SECONDS = 8 * 24 * 60 * 60
GENERATED_AT_MAX_FUTURE_SKEW_SECONDS = 5 * 60
WEEKLY_PACKET_CADENCE_SECONDS = 7 * 24 * 60 * 60
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
    "/docker/fleet/scripts/run_next90_m106_weekly_governor_packet_tests.py",
    "/docker/fleet/scripts/verify_script_bootstrap_no_pythonpath.py",
    "/docker/fleet/tests/test_materialize_weekly_governor_packet.py",
    "/docker/fleet/tests/test_fleet_script_bootstrap_without_pythonpath.py",
    "/docker/fleet/.codex-studio/published/WEEKLY_GOVERNOR_PACKET.generated.json",
    "/docker/fleet/.codex-studio/published/WEEKLY_GOVERNOR_PACKET.generated.md",
    "python3 -m py_compile scripts/materialize_weekly_governor_packet.py scripts/verify_next90_m106_fleet_governor_packet.py tests/test_materialize_weekly_governor_packet.py",
    "python3 -m py_compile scripts/run_next90_m106_weekly_governor_packet_tests.py",
    "python3 -m py_compile scripts/verify_script_bootstrap_no_pythonpath.py tests/test_fleet_script_bootstrap_without_pythonpath.py",
    "python3 scripts/verify_next90_m106_fleet_governor_packet.py exits 0",
    "python3 scripts/run_next90_m106_weekly_governor_packet_tests.py exits 0",
    "direct tmp_path fixture invocation for tests/test_materialize_weekly_governor_packet.py exits 0",
    "verifier rebuilds the decision-critical packet projection from live source inputs",
    "markdown Generated timestamp must match JSON generated_at",
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
    "frontier-detail body strings are rejected as worker proof strings",
    "run-prompt authority labels are rejected as worker proof strings",
    "execution-discipline prompt strings are rejected as worker proof strings",
    "runtime handoff header and model metadata strings are rejected as worker proof strings",
    "runtime handoff frontier metadata strings are rejected as worker proof strings",
    "handoff polling phrase guard is enforced case-insensitively",
    "control-plane polling prohibition guard is enforced case-insensitively",
    "worker-run OODA helper guard is enforced case-insensitively",
    "telemetry-ownership handoff prompt strings are rejected as worker proof strings",
    "worker-safe resume context prompt strings are rejected as worker proof strings",
    "worker-run supervisor launcher guard is enforced case-insensitively",
    "run-helper failure proof strings are rejected case-insensitively",
    "repeat-prevention worker command guard records helper failure posture",
    "verifier rejects Fleet proof paths outside package allowed path roots",
    "production verifier rejects non-canonical source path overrides",
    "verifier rejects reused closed successor frontier rows outside the Fleet M106 package",
    "blocked support-packet proof routes exactly to the M102 reporter-receipts dependency package",
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
    "local proof floor commit 5193bce pinned for M106 refreshed packet artifact floor",
    "local proof floor commit f662ad3 pinned for M106 shorthand telemetry command guard",
    "local proof floor commit 5882234 pinned for M106 blocked dependency route guard",
    "local proof floor commit 6c376e0 pinned for M106 execution-discipline proof guard",
    "local proof floor commit 00e870e pinned for M106 direct fixture runner guard",
    "local proof floor commit 81e1de8 pinned for M106 refreshed source-input packet floor",
    "local proof floor commit 941c54d pinned for M106 handoff frontier metadata guard",
    "local proof floor commit 6981667 pinned for M106 worker helper rule guard",
    "local proof floor commit 4a13b47 pinned for M106 markdown timestamp proof guard",
    "local proof floor commit d597376 pinned for M106 telemetry handoff proof guard",
    "local proof floor commit 233a52a pinned for M106 shard-runtime-handoff guard",
    "local proof floor commit fba96cc pinned for M106 helper failure posture guard",
    "local proof floor commit 15efd7c pinned for M106 refreshed packet artifact floor",
    "local proof floor commit f3bfb8d pinned for M106 refreshed packet artifact floor",
    "local proof floor commit d15a7ae pinned for M106 queue closeout action guard",
    "local proof floor commit ac1c4ac pinned for M106 queue closeout proof floor",
    "local proof floor commit b909cc5 pinned for M106 codexea helper proof guard",
    "commit b909cc5 tightens the M106 codexea helper proof guard",
    "local proof floor commit 787d27a pinned for M106 packet refresh floor",
    "commit 787d27a pins the M106 packet refresh floor",
    "local proof floor commit b467c27 pinned for M106 design queue OODA prompt proof guard",
    "commit b467c27 tightens the M106 design queue OODA prompt proof guard",
    "do-not-reopen handoff routes remaining M106 work to dependency or sibling packages",
)
REQUIRED_REGISTRY_EVIDENCE_MARKERS = (
    "scripts/materialize_weekly_governor_packet.py",
    "scripts/verify_next90_m106_fleet_governor_packet.py",
    "scripts/run_next90_m106_weekly_governor_packet_tests.py",
    "scripts/verify_script_bootstrap_no_pythonpath.py",
    "tests/test_materialize_weekly_governor_packet.py",
    "tests/test_fleet_script_bootstrap_without_pythonpath.py",
    "WEEKLY_GOVERNOR_PACKET.generated.json",
    "WEEKLY_GOVERNOR_PACKET.generated.md",
    "py_compile scripts/materialize_weekly_governor_packet.py scripts/verify_next90_m106_fleet_governor_packet.py tests/test_materialize_weekly_governor_packet.py",
    "py_compile scripts/run_next90_m106_weekly_governor_packet_tests.py",
    "py_compile scripts/verify_script_bootstrap_no_pythonpath.py tests/test_fleet_script_bootstrap_without_pythonpath.py",
    "verify_next90_m106_fleet_governor_packet.py exits 0",
    "run_next90_m106_weekly_governor_packet_tests.py exits 0",
    "tmp_path fixture invocation",
    "decision-critical packet projection",
    "markdown Generated timestamp must match JSON generated_at",
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
    "frontier-detail body strings",
    "run-prompt authority labels",
    "execution-discipline prompt strings",
    "runtime handoff header and model metadata strings",
    "runtime handoff frontier metadata strings",
    "handoff polling phrase guard",
    "control-plane polling prohibition guard",
    "worker-run OODA helper guard",
    "telemetry-ownership handoff prompt strings",
    "worker-safe resume context prompt strings",
    "worker-run supervisor launcher guard",
    "run-helper failure proof strings",
    "repeat-prevention worker command guard records helper failure posture",
    "proof paths outside package allowed path roots",
    "non-canonical source path overrides",
    "reused closed successor frontier rows",
    "blocked support-packet proof routes exactly to the M102 reporter-receipts dependency package",
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
    "local proof floor commit 5193bce",
    "local proof floor commit f662ad3",
    "local proof floor commit 5882234",
    "local proof floor commit 6c376e0",
    "local proof floor commit 00e870e",
    "local proof floor commit 81e1de8",
    "local proof floor commit 941c54d",
    "local proof floor commit 6981667",
    "local proof floor commit 4a13b47",
    "local proof floor commit d597376",
    "local proof floor commit 233a52a",
    "local proof floor commit fba96cc",
    "local proof floor commit 15efd7c",
    "local proof floor commit f3bfb8d",
    "local proof floor commit d15a7ae",
    "local proof floor commit ac1c4ac",
    "local proof floor commit b909cc5",
    "commit b909cc5 tightens the M106 codexea helper proof guard",
    "local proof floor commit 787d27a",
    "commit 787d27a pins the M106 packet refresh floor",
    "local proof floor commit b467c27",
    "commit b467c27 tightens the M106 design queue OODA prompt proof guard",
    "do-not-reopen handoff routes remaining M106 work",
)
REQUIRED_RESOLVING_PROOF_PATHS = (
    "scripts/materialize_weekly_governor_packet.py",
    "scripts/verify_next90_m106_fleet_governor_packet.py",
    "scripts/run_next90_m106_weekly_governor_packet_tests.py",
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
    "status: complete; owners:",
    "deps: 101, 102, 103, 104, 105",
    "own and prove the surface slice(s): weekly_governor_packet, measured_rollout_loop",
    "refresh flagship proof and close out the queue slice honestly",
    "frontier ids:",
    "open milestone ids:",
    "mode: successor_wave",
    "polling_disabled",
    "runtime_handoff_path",
    "shard runtime handoff",
    "use the shard runtime handoff as the worker-safe resume context",
    "status_query_supported",
    "task-local telemetry file",
    "local machine-readable context",
    "implementation-only",
    "implementation only",
    "implementation-only retry",
    "this retry is implementation-only",
    "previous attempt burned time on supervisor helper loops",
    "retry is implementation-only",
    "successor-wave pass",
    "product advance successor-wave pass",
    "next-90-day product advance successor-wave pass",
    "run these exact commands first",
    "do not invent another orientation step",
    "read these files directly first",
    "historical operator status snippets",
    "stale notes rather than commands",
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
    "execution discipline",
    "first action rule",
    "if you stop, report only",
    "what shipped:",
    "what remains:",
    "exact blocker:",
    "writable scope roots",
    "operator telemetry",
    "do not invoke operator telemetry",
    "do not invoke operator telemetry or active-run helper commands from inside worker runs",
    "supervisor helper loop",
    "supervisor helper loops",
    "supervisor status polling",
    "supervisor eta polling",
    "supervisor status or eta helpers",
    "supervisor status or eta helpers inside this worker run",
    "do not query supervisor status",
    "do not query supervisor status or eta",
    "do not run supervisor status or eta helpers",
    "polling the supervisor again",
    "current flagship closeout",
    "do not reopen the closed flagship wave",
    "reopen the closed flagship wave",
    "active-run telemetry",
    "active run",
    "run id:",
    "selected account",
    "selected model",
    "prompt path",
    "recent stderr tail",
    "active-run helper",
    "active-run helper commands",
    "active run helper",
    "active worker run",
    "worker runs",
    "operator/OODA loop",
    "operator ooda loop",
    "operator/OODA loop owns telemetry",
    "operator/OODA loop owns telemetry; keep working the assigned slice",
    "operator ooda loop owns telemetry",
    "ooda loop owns telemetry",
    "operator-owned telemetry",
    "operator-owned run-helper",
    "operator-owned helper",
    "inside worker runs",
    "run failure",
    "count as run failure",
    "hard-blocked",
    "helpers are hard-blocked",
    "hard blocked",
    "non-zero during active runs",
    "return non-zero during active runs",
    "nonzero during active runs",
    "--telemetry-answer",
    "codexea telemetry",
    "codexea status",
    "codexea eta",
    "codexea watch",
    "codexea-watchdog",
    "codexea --telemetry",
    "codexea --status",
    "codexea --eta",
    "codexea --watch",
    "chummer_design_supervisor status",
    "chummer_design_supervisor eta",
    "supervisor status",
    "supervisor eta",
    "operator telemetry helper",
    "active-run status helper",
    "chummer_design_supervisor.py",
    "chummer_design_supervisor.py status",
    "chummer_design_supervisor.py eta",
)
REQUIRED_LAUNCH_SIGNALS = (
    "journey_gate_state",
    "journey_gate_blocked_count",
    "local_release_proof_status",
    "provider_canary_status",
    "closure_health_state",
)
REQUIRED_RISK_CLUSTER_FIELDS = ("cluster_id", "summary")
COMPLETE_STATUSES = {"complete", "closed", "done"}
SUPPORT_DEPENDENCY_PACKAGE_ID = "next90-m102-fleet-reporter-receipts"
EXPECTED_SUPPORT_BLOCKED_DEPENDENCY_PACKAGE_IDS = (SUPPORT_DEPENDENCY_PACKAGE_ID,)


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


def _duplicate_proof_entries(entries: List[str]) -> List[str]:
    duplicates: List[str] = []
    seen: set[str] = set()
    for entry in entries:
        normalized = str(entry or "").strip().rstrip(".")
        if not normalized:
            continue
        if normalized in seen and normalized not in duplicates:
            duplicates.append(normalized)
            continue
        seen.add(normalized)
    return duplicates


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


def _format_iso_utc(value: dt.datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _packet_schedule(generated_at: str) -> Dict[str, Any]:
    generated = _parse_iso_utc(generated_at)
    if generated is None:
        return {
            "cadence": "weekly",
            "generated_at": generated_at,
            "next_packet_due_at": "",
            "cadence_seconds": WEEKLY_PACKET_CADENCE_SECONDS,
            "max_age_seconds": WEEKLY_PACKET_CADENCE_SECONDS,
            "status": "invalid_generated_at",
        }
    return {
        "cadence": "weekly",
        "generated_at": _format_iso_utc(generated),
        "next_packet_due_at": _format_iso_utc(
            generated + dt.timedelta(seconds=WEEKLY_PACKET_CADENCE_SECONDS)
        ),
        "cadence_seconds": WEEKLY_PACKET_CADENCE_SECONDS,
        "max_age_seconds": WEEKLY_PACKET_CADENCE_SECONDS,
        "status": "scheduled",
    }


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


def _dependency_package_routes(
    *,
    dependency_posture: Dict[str, Any],
    design_queue: Dict[str, Any],
    queue: Dict[str, Any],
) -> Dict[str, Any]:
    design_items_by_milestone: Dict[int, List[Dict[str, Any]]] = {}
    queue_items_by_milestone: Dict[int, List[Dict[str, Any]]] = {}
    for source, target in (
        (design_queue.get("items") or [], design_items_by_milestone),
        (queue.get("items") or [], queue_items_by_milestone),
    ):
        for item in source:
            if not isinstance(item, dict):
                continue
            milestone_id = _coerce_int(item.get("milestone_id"), -1)
            if milestone_id >= 0:
                target.setdefault(milestone_id, []).append(item)

    rows: List[Dict[str, Any]] = []
    missing_package_milestone_ids: List[int] = []
    incomplete_package_milestone_ids: List[int] = []
    mirror_drift_milestone_ids: List[int] = []
    for dep in dependency_posture.get("dependencies") or []:
        if not isinstance(dep, dict):
            continue
        milestone_id = _coerce_int(dep.get("id"), -1)
        if milestone_id < 0:
            continue
        design_matches = design_items_by_milestone.get(milestone_id) or []
        queue_matches = queue_items_by_milestone.get(milestone_id) or []
        design_item = design_matches[0] if len(design_matches) == 1 else {}
        queue_item = queue_matches[0] if len(queue_matches) == 1 else {}
        package_id = str(
            queue_item.get("package_id")
            or design_item.get("package_id")
            or f"milestone-{milestone_id}"
        ).strip()
        queue_status = str(queue_item.get("status") or "").strip()
        design_status = str(design_item.get("status") or "").strip()
        completion_action = str(
            queue_item.get("completion_action")
            or design_item.get("completion_action")
            or ""
        ).strip()
        queue_closed = queue_status.lower() in COMPLETE_STATUSES
        design_closed = design_status.lower() in COMPLETE_STATUSES
        mirror_in_sync = bool(design_item and queue_item) and _queue_mirror_drift(
            design_item, queue_item
        ) == []
        registry_status = str(dep.get("status") or "").strip()
        registry_open = registry_status.lower() not in COMPLETE_STATUSES
        if not design_item or not queue_item:
            route_state = "package_row_missing"
            missing_package_milestone_ids.append(milestone_id)
        elif not mirror_in_sync:
            route_state = "queue_mirror_drift"
            mirror_drift_milestone_ids.append(milestone_id)
        elif queue_closed and design_closed and completion_action == EXPECTED_COMPLETION_ACTION:
            route_state = (
                "closed_package_verified_milestone_open"
                if registry_open
                else "closed_package_verified"
            )
        else:
            route_state = "package_incomplete"
            incomplete_package_milestone_ids.append(milestone_id)
        rows.append(
            {
                "milestone_id": milestone_id,
                "registry_status": registry_status or "missing",
                "package_id": package_id,
                "repo": str(queue_item.get("repo") or design_item.get("repo") or "").strip(),
                "queue_status": queue_status or "missing",
                "design_queue_status": design_status or "missing",
                "completion_action": completion_action or "missing",
                "queue_mirror_status": "in_sync" if mirror_in_sync else "drift_or_missing",
                "route_state": route_state,
                "operator_route": (
                    "verify_closed_package_only"
                    if route_state.startswith("closed_package_verified")
                    else "route_to_dependency_package"
                ),
                "launch_gate_contribution": (
                    "blocked_until_registry_milestone_complete"
                    if registry_open
                    else "clear"
                ),
            }
        )
    route_blockers = (
        missing_package_milestone_ids
        + incomplete_package_milestone_ids
        + mirror_drift_milestone_ids
    )
    return {
        "status": "pass" if not route_blockers else "blocked",
        "rows": rows,
        "missing_package_milestone_ids": missing_package_milestone_ids,
        "incomplete_package_milestone_ids": incomplete_package_milestone_ids,
        "mirror_drift_milestone_ids": mirror_drift_milestone_ids,
        "closed_package_count": sum(
            1
            for row in rows
            if str(row.get("route_state") or "").startswith("closed_package_verified")
        ),
        "open_registry_milestone_count": sum(
            1
            for row in rows
            if row.get("launch_gate_contribution")
            == "blocked_until_registry_milestone_complete"
        ),
        "rule": (
            "Closed dependency package rows are verified instead of reopened; "
            "launch expansion still waits for successor registry milestone status to close."
        ),
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
    if str(item.get("completion_action") or "").strip() != EXPECTED_COMPLETION_ACTION:
        issues.append(f"{prefix} item completion_action is not {EXPECTED_COMPLETION_ACTION}")
    if str(item.get("do_not_reopen_reason") or "").strip() != EXPECTED_DO_NOT_REOPEN_REASON:
        issues.append(f"{prefix} item do_not_reopen_reason no longer matches package closeout authority")
    if str(item.get("landed_commit") or "").strip() != EXPECTED_LANDED_COMMIT:
        issues.append(f"{prefix} item landed_commit does not pin Fleet M106 closeout authority")
    return issues


def _queue_proof_issues(item: Dict[str, Any], prefix: str, repo_root: Path) -> List[str]:
    issues: List[str] = []
    proof_entries = _norm_list(item.get("proof"))
    normalized_proof_entries = {entry.rstrip(".") for entry in proof_entries}
    duplicate_proof = _duplicate_proof_entries(proof_entries)
    missing_proof = [
        marker
        for marker in REQUIRED_QUEUE_PROOF_MARKERS
        if marker not in proof_entries and marker.rstrip(".") not in normalized_proof_entries
    ]
    if duplicate_proof:
        issues.append(
            f"{prefix} item proof contains duplicate weekly governor receipt(s): "
            + ", ".join(duplicate_proof)
        )
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
        "completion_action",
        "do_not_reopen_reason",
        "landed_commit",
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
            duplicate_registry_evidence = _duplicate_proof_entries(evidence_entries)
            missing_registry_evidence = [
                marker
                for marker in REQUIRED_REGISTRY_EVIDENCE_MARKERS
                if marker not in evidence_text
            ]
            if duplicate_registry_evidence:
                issues.append(
                    "registry work task 106.1 evidence contains duplicate weekly governor marker(s): "
                    + ", ".join(duplicate_registry_evidence)
                )
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
        "queue_completion_action": str(item.get("completion_action") or "").strip(),
        "design_queue_completion_action": str(design_item.get("completion_action") or "").strip(),
        "queue_do_not_reopen_reason": str(item.get("do_not_reopen_reason") or "").strip(),
        "design_queue_do_not_reopen_reason": str(design_item.get("do_not_reopen_reason") or "").strip(),
        "queue_landed_commit": str(item.get("landed_commit") or "").strip(),
        "design_queue_landed_commit": str(design_item.get("landed_commit") or "").strip(),
        "expected_completion_action": EXPECTED_COMPLETION_ACTION,
        "expected_do_not_reopen_reason": EXPECTED_DO_NOT_REOPEN_REASON,
        "expected_landed_commit": EXPECTED_LANDED_COMMIT,
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


def _risk_cluster_health(weekly_pulse: Dict[str, Any]) -> Dict[str, Any]:
    clusters = weekly_pulse.get("top_support_or_feedback_clusters")
    issues: List[str] = []
    if not isinstance(clusters, list):
        issues.append("weekly pulse top_support_or_feedback_clusters must be a list")
        clusters = []
    if not clusters:
        issues.append("weekly pulse top_support_or_feedback_clusters is empty")
    malformed_rows: List[str] = []
    for index, row in enumerate(clusters):
        if not isinstance(row, dict):
            malformed_rows.append(f"{index}:not_object")
            continue
        missing = [
            field
            for field in REQUIRED_RISK_CLUSTER_FIELDS
            if not str(row.get(field) or "").strip()
        ]
        if missing:
            malformed_rows.append(f"{index}:missing_" + "_".join(missing))
    if malformed_rows:
        issues.append(
            "weekly pulse top_support_or_feedback_clusters has malformed row(s): "
            + ", ".join(malformed_rows)
        )
    return {
        "status": "pass" if not issues else "fail",
        "cluster_count": len(clusters),
        "required_fields": list(REQUIRED_RISK_CLUSTER_FIELDS),
        "issues": issues,
    }


def verify_weekly_inputs(weekly_pulse: Dict[str, Any], launch_decision: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    generated_at = _parse_iso_utc(weekly_pulse.get("generated_at"))
    now = dt.datetime.now(UTC)
    risk_cluster_health = _risk_cluster_health(weekly_pulse)
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
    issues.extend(risk_cluster_health["issues"])
    return {
        "status": "pass" if not issues else "fail",
        "generated_at": str(weekly_pulse.get("generated_at") or "").strip(),
        "max_age_seconds": WEEKLY_PULSE_MAX_AGE_SECONDS,
        "required_launch_signals": list(REQUIRED_LAUNCH_SIGNALS),
        "risk_cluster_health": risk_cluster_health,
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
        source_path = str(dict(source_paths or {}).get(name) or "").strip()
        rows[name] = {
            "state": state,
            "required_key": required_key,
        }
        if source_path:
            rows[name]["source_path"] = source_path
            try:
                rows[name]["source_sha256"] = hashlib.sha256(
                    Path(source_path).read_bytes()
                ).hexdigest()
            except OSError:
                rows[name]["source_sha256"] = ""
                issues.append(f"{name} source_path cannot be read for source_sha256")
        if state != "present":
            issues.append(f"{name} is missing, empty, unparseable, or lacks {required_key}")
        if name in REQUIRED_GENERATED_SOURCE_INPUTS:
            generated_at = str(payload.get("generated_at") or "").strip() if present else ""
            rows[name]["generated_at"] = generated_at
            parsed_generated_at = _parse_iso_utc(generated_at)
            if state == "present" and not parsed_generated_at:
                issues.append(f"{name} generated_at is missing or invalid")
            elif state == "present" and parsed_generated_at:
                future_skew_seconds = int((parsed_generated_at - now).total_seconds())
                if future_skew_seconds > GENERATED_AT_MAX_FUTURE_SKEW_SECONDS:
                    issues.append(f"{name} generated_at is future-dated ({future_skew_seconds}s ahead)")
                elif name not in {"weekly_pulse", "support_packets"}:
                    rows[name]["max_age_seconds"] = GENERATED_SOURCE_MAX_AGE_SECONDS
                    age_seconds = int((now - parsed_generated_at).total_seconds())
                    if age_seconds > GENERATED_SOURCE_MAX_AGE_SECONDS:
                        issues.append(f"{name} is stale ({age_seconds}s old)")
    support_successor_proof = dict(support_packets.get("successor_package_verification") or {})
    support_successor_status = str(support_successor_proof.get("status") or "").strip()
    support_generated_at = _parse_iso_utc(support_packets.get("generated_at"))
    support_source_path = str(dict(source_paths or {}).get("support_packets") or "").strip()
    rows["support_packets"]["successor_package_verification_status"] = (
        support_successor_status or "missing"
    )
    rows["support_packets"]["max_age_seconds"] = SUPPORT_PACKETS_MAX_AGE_SECONDS
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
    launch_decision = _launch_decision(weekly_pulse)
    launch_signals = _decision_signal_map(launch_decision)
    supporting = dict(weekly_pulse.get("supporting_signals") or {})
    provider = dict(supporting.get("provider_route_stewardship") or {})
    closure = dict(supporting.get("closure_health") or {})
    adoption = dict(supporting.get("adoption_health") or {})
    journey_summary = dict(journey_gates.get("summary") or {})
    expected_launch_signals = {
        "journey_gate_state": str(
            journey_summary.get("overall_state")
            or dict(weekly_pulse.get("journey_gate_health") or {}).get("state")
            or ""
        ).strip(),
        "journey_gate_blocked_count": str(
            journey_summary.get("blocked_count")
            if "blocked_count" in journey_summary
            else ""
        ).strip(),
        "local_release_proof_status": str(
            adoption.get("local_release_proof_status") or ""
        ).strip(),
        "provider_canary_status": str(provider.get("canary_status") or "").strip(),
        "closure_health_state": str(closure.get("state") or "").strip(),
    }
    signal_mismatches = {
        key: {
            "cited": str(launch_signals.get(key) or "").strip(),
            "source": expected,
        }
        for key, expected in expected_launch_signals.items()
        if str(launch_signals.get(key) or "").strip()
        and expected
        and str(launch_signals.get(key) or "").strip() != expected
    }
    rows["launch_signal_truth_alignment"] = {
        "state": "pass" if not signal_mismatches else "fail",
        "expected_from_sources": expected_launch_signals,
        "cited_signals": {
            key: str(launch_signals.get(key) or "").strip()
            for key in REQUIRED_LAUNCH_SIGNALS
        },
        "mismatches": signal_mismatches,
    }
    if signal_mismatches:
        issues.append(
            "weekly pulse launch cited signal(s) do not match generated source truth: "
            + ", ".join(sorted(signal_mismatches))
        )
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


def _source_input_fingerprint(source_input_health: Dict[str, Any]) -> Dict[str, Any]:
    required_inputs = dict(source_input_health.get("required_inputs") or {})
    rows: List[Dict[str, str]] = []
    missing_inputs: List[str] = []
    for name in EXPECTED_PRODUCTION_SOURCE_PATHS:
        row = dict(required_inputs.get(name) or {})
        source_path = str(row.get("source_path") or "").strip()
        source_sha256 = str(row.get("source_sha256") or "").strip().lower()
        if not source_path or not source_sha256:
            missing_inputs.append(name)
        rows.append(
            {
                "name": name,
                "source_path": source_path,
                "source_sha256": source_sha256,
            }
        )
    fingerprint_material = "\n".join(
        f"{row['name']} {row['source_sha256']} {row['source_path']}" for row in rows
    )
    return {
        "status": "pass" if not missing_inputs else "fail",
        "source_count": len(rows),
        "missing_inputs": missing_inputs,
        "combined_source_sha256": hashlib.sha256(
            fingerprint_material.encode("utf-8")
        ).hexdigest(),
        "rows": rows,
    }


def _followthrough_group_rows(followthrough: Dict[str, Any], name: str) -> List[Dict[str, Any]]:
    groups = dict(followthrough.get("action_groups") or {})
    rows = groups.get(name)
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows if isinstance(row, dict)]


def _recomputed_followthrough_counts(followthrough: Dict[str, Any]) -> Dict[str, int]:
    ready_group_names = ("feedback", "fix_available", "please_test", "recovery")
    blocked_group_names = (
        "blocked_missing_install_receipts",
        "blocked_receipt_mismatch",
        "hold_until_fix_receipt",
    )
    action_groups = {
        name: _followthrough_group_rows(followthrough, name)
        for name in (*ready_group_names, *blocked_group_names)
    }
    ready_group_rows_present = any(action_groups[name] for name in ready_group_names)
    rows_by_key: Dict[str, Dict[str, Any]] = {}
    ready_keys: set[str] = set()
    ready_group_counts = {name: 0 for name in ready_group_names}
    for group_name, rows in action_groups.items():
        for index, row in enumerate(rows):
            packet_id = str(row.get("packet_id") or "").strip()
            row_key = packet_id or f"{group_name}:{index}"
            merged_row = dict(rows_by_key.get(row_key) or {})
            merged_row.update(row)
            rows_by_key[row_key] = merged_row
            receipt_ready = bool(row.get("installed_build_receipted")) and bool(
                row.get("installed_build_receipt_installation_matches")
            )
            if group_name in ready_group_names and receipt_ready:
                ready_keys.add(row_key)
                ready_group_counts[group_name] += 1

    merged_rows = list(rows_by_key.values())
    installed_build_receipted_present = any(
        "installed_build_receipted" in row for row in merged_rows
    )
    installation_bound_present = any(
        "installed_build_receipt_installation_matches" in row for row in merged_rows
    )
    return {
        "ready_count": len(ready_keys),
        "feedback_ready_count": ready_group_counts["feedback"],
        "fix_available_ready_count": ready_group_counts["fix_available"],
        "please_test_ready_count": ready_group_counts["please_test"],
        "recovery_loop_ready_count": ready_group_counts["recovery"],
        "blocked_missing_install_receipts_count": len(
            action_groups["blocked_missing_install_receipts"]
        ),
        "blocked_receipt_mismatch_count": len(action_groups["blocked_receipt_mismatch"]),
        "hold_until_fix_receipt_count": len(action_groups["hold_until_fix_receipt"]),
        "installed_build_receipted_count": (
            sum(1 for row in merged_rows if bool(row.get("installed_build_receipted")))
            if installed_build_receipted_present
            else -1
        ),
        "installation_bound_count": (
            sum(
                1
                for row in merged_rows
                if bool(row.get("installed_build_receipt_installation_matches"))
            )
            if installation_bound_present
            else -1
        ),
        "ready_group_rows_present": int(ready_group_rows_present),
        "ready_group_receipt_fields_present": int(
            installed_build_receipted_present or installation_bound_present
        ),
    }


def _support_summary(support_packets: Dict[str, Any]) -> Dict[str, Any]:
    summary = dict(support_packets.get("summary") or {})
    followthrough = dict(support_packets.get("reporter_followthrough_plan") or {})
    receipt_gates = dict(support_packets.get("followthrough_receipt_gates") or {})
    gate_counts = dict(receipt_gates.get("gate_counts") or {})
    recomputed_counts = _recomputed_followthrough_counts(followthrough)
    ready_group_rows_present = bool(recomputed_counts.get("ready_group_rows_present"))
    ready_group_receipt_fields_present = bool(
        recomputed_counts.get("ready_group_receipt_fields_present")
    )
    use_recomputed_ready_counts = (
        ready_group_rows_present and ready_group_receipt_fields_present
    )
    receipt_ready_count = (
        recomputed_counts["ready_count"]
        if use_recomputed_ready_counts
        else max(
            recomputed_counts["ready_count"],
            _coerce_int(receipt_gates.get("ready_count"), 0),
        )
    )
    plan_ready_count = (
        recomputed_counts["ready_count"]
        if use_recomputed_ready_counts
        else max(
            recomputed_counts["ready_count"],
            _coerce_int(followthrough.get("ready_count"), 0),
        )
    )
    summary_blocked_missing_count = _coerce_int(
        summary.get("reporter_followthrough_blocked_missing_install_receipts_count"),
        0,
    )
    summary_blocked_mismatch_count = _coerce_int(
        summary.get("reporter_followthrough_blocked_receipt_mismatch_count"),
        0,
    )
    plan_blocked_missing_count = max(
        recomputed_counts["blocked_missing_install_receipts_count"],
        _coerce_int(followthrough.get("blocked_missing_install_receipts_count"), 0),
    )
    plan_blocked_mismatch_count = max(
        recomputed_counts["blocked_receipt_mismatch_count"],
        _coerce_int(followthrough.get("blocked_receipt_mismatch_count"), 0),
    )
    plan_hold_until_fix_count = max(
        recomputed_counts["hold_until_fix_receipt_count"],
        _coerce_int(followthrough.get("hold_until_fix_receipt_count"), 0),
    )
    feedback_ready_count = (
        recomputed_counts["feedback_ready_count"]
        if use_recomputed_ready_counts
        else max(
            recomputed_counts["feedback_ready_count"],
            _coerce_int(receipt_gates.get("feedback_ready_count"), 0),
        )
    )
    fix_available_ready_count = (
        recomputed_counts["fix_available_ready_count"]
        if use_recomputed_ready_counts
        else max(
            recomputed_counts["fix_available_ready_count"],
            _coerce_int(receipt_gates.get("fix_available_ready_count"), 0),
        )
    )
    please_test_ready_count = (
        recomputed_counts["please_test_ready_count"]
        if use_recomputed_ready_counts
        else max(
            recomputed_counts["please_test_ready_count"],
            _coerce_int(receipt_gates.get("please_test_ready_count"), 0),
        )
    )
    recovery_ready_count = (
        recomputed_counts["recovery_loop_ready_count"]
        if use_recomputed_ready_counts
        else max(
            recomputed_counts["recovery_loop_ready_count"],
            _coerce_int(receipt_gates.get("recovery_loop_ready_count"), 0),
        )
    )
    gate_blocked_missing_count = max(
        recomputed_counts["blocked_missing_install_receipts_count"],
        _coerce_int(receipt_gates.get("blocked_missing_install_receipts_count"), 0),
    )
    gate_blocked_mismatch_count = max(
        recomputed_counts["blocked_receipt_mismatch_count"],
        _coerce_int(receipt_gates.get("blocked_receipt_mismatch_count"), 0),
    )
    gate_hold_until_fix_count = max(
        recomputed_counts["hold_until_fix_receipt_count"],
        _coerce_int(receipt_gates.get("hold_until_fix_receipt_count"), 0),
    )
    blocked_missing_count = max(
        summary_blocked_missing_count,
        plan_blocked_missing_count,
        gate_blocked_missing_count,
    )
    blocked_mismatch_count = max(
        summary_blocked_mismatch_count,
        plan_blocked_mismatch_count,
        gate_blocked_mismatch_count,
    )
    return {
        "open_packet_count": _coerce_int(summary.get("open_packet_count"), 0),
        "open_non_external_packet_count": _coerce_int(summary.get("open_non_external_packet_count"), 0),
        "closure_waiting_on_release_truth": _coerce_int(summary.get("closure_waiting_on_release_truth"), 0),
        "update_required_misrouted_case_count": _coerce_int(summary.get("update_required_misrouted_case_count"), 0),
        "reporter_followthrough_ready_count": receipt_ready_count,
        "feedback_followthrough_ready_count": feedback_ready_count,
        "fix_available_ready_count": fix_available_ready_count,
        "please_test_ready_count": please_test_ready_count,
        "recovery_loop_ready_count": recovery_ready_count,
        "reporter_followthrough_blocked_missing_install_receipts_count": blocked_missing_count,
        "reporter_followthrough_blocked_receipt_mismatch_count": blocked_mismatch_count,
        "reporter_followthrough_hold_until_fix_receipt_count": max(
            _coerce_int(summary.get("reporter_followthrough_hold_until_fix_receipt_count"), 0),
            plan_hold_until_fix_count,
            gate_hold_until_fix_count,
        ),
        "reporter_followthrough_plan_ready_count": plan_ready_count,
        "reporter_followthrough_plan_blocked_missing_install_receipts_count": plan_blocked_missing_count,
        "reporter_followthrough_plan_blocked_receipt_mismatch_count": plan_blocked_mismatch_count,
        "reporter_followthrough_plan_hold_until_fix_receipt_count": plan_hold_until_fix_count,
        "followthrough_receipt_gates_ready_count": (
            recomputed_counts["ready_count"]
            if use_recomputed_ready_counts
            else _coerce_int(receipt_gates.get("ready_count"), 0)
        ),
        "followthrough_receipt_gates_blocked_missing_install_receipts_count": gate_blocked_missing_count,
        "followthrough_receipt_gates_blocked_receipt_mismatch_count": gate_blocked_mismatch_count,
        "followthrough_receipt_gates_hold_until_fix_receipt_count": gate_hold_until_fix_count,
        "followthrough_receipt_gates_installed_build_receipted_count": (
            recomputed_counts["installed_build_receipted_count"]
            if recomputed_counts["installed_build_receipted_count"] >= 0
            else _coerce_int(gate_counts.get("installed_build_receipted"), 0)
        ),
        "followthrough_receipt_gates_installation_bound_count": (
            recomputed_counts["installation_bound_count"]
            if recomputed_counts["installation_bound_count"] >= 0
            else _coerce_int(gate_counts.get("installed_build_receipt_installation_bound"), 0)
        ),
    }


def _adoption_summary(weekly_pulse: Dict[str, Any]) -> Dict[str, Any]:
    supporting = dict(weekly_pulse.get("supporting_signals") or {})
    adoption = dict(supporting.get("adoption_health") or {})
    return {
        "state": str(adoption.get("state") or "unknown").strip() or "unknown",
        "local_release_proof_status": str(
            adoption.get("local_release_proof_status") or "unknown"
        ).strip()
        or "unknown",
        "proven_journey_count": _coerce_int(adoption.get("proven_journey_count"), 0),
        "proven_route_count": _coerce_int(adoption.get("proven_route_count"), 0),
        "history_snapshot_count": _coerce_int(adoption.get("history_snapshot_count"), 0),
        "summary": str(adoption.get("summary") or "").strip(),
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


def _flagship_quality_summary(flagship_readiness: Dict[str, Any]) -> Dict[str, Any]:
    coverage = dict(flagship_readiness.get("coverage_details") or {})
    desktop = dict(coverage.get("desktop_client") or {})
    desktop_evidence = dict(desktop.get("evidence") or {})
    polish = dict(coverage.get("ui_kit_and_flagship_polish") or {})
    polish_evidence = dict(polish.get("evidence") or {})

    localization_present = bool(
        desktop_evidence.get("ui_localization_release_gate_present")
    )
    localization_status = str(
        desktop_evidence.get("ui_localization_release_gate_status") or "unknown"
    ).strip() or "unknown"
    missing_locale_count = _coerce_int(
        desktop_evidence.get(
            "ui_localization_release_gate_missing_locale_summary_shipping_locale_count"
        ),
        0,
    )
    backlog_count = _coerce_int(
        desktop_evidence.get("ui_localization_release_gate_translation_backlog_finding_count"),
        0,
    )
    untranslated_locale_count = _coerce_int(
        desktop_evidence.get("ui_localization_release_gate_untranslated_locale_count"),
        0,
    )
    polish_status = str(polish.get("status") or "unknown").strip() or "unknown"
    polish_summary = str(polish.get("summary") or "").strip()
    accessibility_named = "accessibility" in polish_summary.lower() or any(
        "accessibility" in str(value).lower()
        for value in polish_evidence.values()
    )
    shipping_locales = _norm_list(
        desktop_evidence.get("ui_localization_release_gate_shipping_locales")
    )
    issues: List[str] = []
    if not localization_present:
        issues.append("localization release gate is missing")
    if localization_status != "pass":
        issues.append(f"localization release gate status is {localization_status}")
    if missing_locale_count:
        issues.append(f"{missing_locale_count} shipping locale summary row(s) are missing")
    if backlog_count:
        issues.append(f"{backlog_count} translation backlog finding(s) remain")
    if untranslated_locale_count:
        issues.append(f"{untranslated_locale_count} shipping locale(s) still have untranslated keys")
    if polish_status != "ready":
        issues.append(f"ui kit and flagship polish status is {polish_status}")
    if not accessibility_named:
        issues.append("ui kit and flagship polish proof does not name accessibility")

    return {
        "release_truth_status": "pass" if not issues else "blocked",
        "localization_release_gate_present": localization_present,
        "localization_release_gate_status": localization_status,
        "shipping_locale_count": _coerce_int(
            desktop_evidence.get("ui_localization_release_gate_shipping_locale_count"),
            len(shipping_locales),
        ),
        "shipping_locales": shipping_locales,
        "missing_locale_summary_shipping_locale_count": missing_locale_count,
        "translation_backlog_finding_count": backlog_count,
        "untranslated_locale_count": untranslated_locale_count,
        "ui_kit_and_flagship_polish_status": polish_status,
        "accessibility_proof_named": accessibility_named,
        "issues": issues,
    }


def _gate_row(name: str, state: str, required: str, observed: Any) -> Dict[str, str]:
    return {
        "name": name,
        "state": state,
        "required": required,
        "observed": str(observed if observed is not None else "unknown").strip() or "unknown",
    }


def _status_copy(*, launch_allowed: bool, rollback_watch: bool, launch_reason: str) -> Dict[str, Any]:
    provenance = {
        "derived_from": "measured_rollout_loop.decision_action_matrix",
        "decision_actions": list(REQUIRED_DECISION_ACTIONS),
    }
    if launch_allowed:
        return {
            **provenance,
            "state": "launch_expand_allowed",
            "headline": "Measured launch expansion is allowed.",
            "body": "Readiness, parity, support, canary, dependency, and release-proof gates are green for this weekly packet.",
        }
    if rollback_watch:
        return {
            **provenance,
            "state": "freeze_with_rollback_watch",
            "headline": "Launch expansion is frozen with rollback watch active.",
            "body": launch_reason
            or "Release or support truth requires rollback watch before any broader launch move.",
        }
    return {
        **provenance,
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
    for action in REQUIRED_DECISION_ACTIONS:
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


def _decision_action_matrix(
    *,
    decision_board: Dict[str, Any],
    decision_gate_ledger: Dict[str, Any],
    governor_decisions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    governor_by_action = {
        str(row.get("action") or "").strip(): row
        for row in governor_decisions
        if isinstance(row, dict)
    }
    rows: List[Dict[str, Any]] = []
    for action in REQUIRED_DECISION_ACTIONS:
        board = dict(decision_board.get(action) or {})
        ledger = decision_gate_ledger.get(action) or []
        governor = dict(governor_by_action.get(action) or {})
        board_state = str(board.get("state") or "").strip()
        governor_state = str(governor.get("state") or "").strip()
        ledger_gate_count = len(ledger) if isinstance(ledger, list) else 0
        governor_gate_count = _coerce_int(governor.get("gate_count"), -1)
        state_consistent = bool(board_state and board_state == governor_state)
        gate_count_consistent = bool(
            ledger_gate_count > 0 and governor_gate_count == ledger_gate_count
        )
        rows.append(
            {
                "action": action,
                "board_state": board_state or "missing",
                "ledger_gate_count": ledger_gate_count,
                "governor_state": governor_state or "missing",
                "governor_gate_count": governor_gate_count,
                "state_consistent": state_consistent,
                "gate_count_consistent": gate_count_consistent,
                "complete": bool(state_consistent and gate_count_consistent),
            }
        )
    return rows


def _decision_action_coverage(
    *,
    decision_board: Dict[str, Any],
    decision_gate_ledger: Dict[str, Any],
    governor_decisions: List[Dict[str, Any]],
    decision_action_matrix: List[Dict[str, Any]],
) -> Dict[str, Any]:
    governor_actions = {
        str(row.get("action") or "").strip()
        for row in governor_decisions
        if isinstance(row, dict)
    }
    matrix_by_action = {
        str(row.get("action") or "").strip(): row
        for row in decision_action_matrix
        if isinstance(row, dict)
    }
    rows: List[Dict[str, Any]] = []
    for action in REQUIRED_DECISION_ACTIONS:
        ledger = decision_gate_ledger.get(action)
        matrix_row = dict(matrix_by_action.get(action) or {})
        board_present = action in decision_board
        ledger_present = isinstance(ledger, list) and len(ledger) > 0
        governor_present = action in governor_actions
        matrix_complete = matrix_row.get("complete") is True
        rows.append(
            {
                "action": action,
                "board_present": board_present,
                "ledger_present": ledger_present,
                "governor_present": governor_present,
                "matrix_complete": matrix_complete,
                "covered": bool(
                    board_present
                    and ledger_present
                    and governor_present
                    and matrix_complete
                ),
            }
        )
    missing_actions = [
        row["action"]
        for row in rows
        if not row["board_present"]
        or not row["ledger_present"]
        or not row["governor_present"]
    ]
    incomplete_actions = [
        row["action"]
        for row in rows
        if row["board_present"]
        and row["ledger_present"]
        and row["governor_present"]
        and not row["matrix_complete"]
    ]
    return {
        "status": "pass" if not missing_actions and not incomplete_actions else "fail",
        "required_actions": list(REQUIRED_DECISION_ACTIONS),
        "covered_action_count": sum(1 for row in rows if row["covered"]),
        "required_action_count": len(REQUIRED_DECISION_ACTIONS),
        "missing_actions": missing_actions,
        "incomplete_actions": incomplete_actions,
        "rows": rows,
    }


def _decision_source_coverage(
    *,
    decision_board: Dict[str, Any],
    decision_gate_ledger: Dict[str, Any],
) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    for action in REQUIRED_DECISION_ACTIONS:
        board = dict(decision_board.get(action) or {})
        ledger_rows = [
            row for row in decision_gate_ledger.get(action) or [] if isinstance(row, dict)
        ]
        ledger_gate_names = {
            str(row.get("name") or "").strip()
            for row in ledger_rows
            if str(row.get("name") or "").strip()
        }
        required_gates = list(REQUIRED_DECISION_SOURCE_GATES[action])
        missing_gates = [
            gate_name for gate_name in required_gates if gate_name not in ledger_gate_names
        ]
        board_state = str(board.get("state") or "").strip()
        board_reason = str(board.get("reason") or board.get("next_decision") or "").strip()
        rows.append(
            {
                "action": action,
                "required_gates": required_gates,
                "missing_gates": missing_gates,
                "board_state_present": bool(board_state),
                "board_reason_present": bool(board_reason),
                "covered": bool(
                    not missing_gates and board_state and board_reason
                ),
            }
        )
    missing_actions = [row["action"] for row in rows if not row["covered"]]
    return {
        "status": "pass" if not missing_actions else "fail",
        "required_source_gates_by_action": {
            action: list(gates)
            for action, gates in REQUIRED_DECISION_SOURCE_GATES.items()
        },
        "covered_action_count": sum(1 for row in rows if row["covered"]),
        "required_action_count": len(REQUIRED_DECISION_ACTIONS),
        "missing_actions": missing_actions,
        "rows": rows,
    }


def _decision_action_routes(
    *,
    decision_board: Dict[str, Any],
    decision_gate_ledger: Dict[str, Any],
) -> Dict[str, Any]:
    route_contract = {
        "launch_expand": {
            "owner": "fleet",
            "route": "weekly_governor_packet.launch_expand",
            "cadence": "weekly",
            "trigger_gate": "launch_gate_summary.all_green",
            "unblock_condition": "all launch_expand gates pass",
            "operator_action_when_blocked": "do_not_expand_launch",
            "operator_action_when_clear": "promote_measured_launch_expansion",
        },
        "freeze_launch": {
            "owner": "fleet",
            "route": "weekly_governor_packet.freeze_launch",
            "cadence": "weekly",
            "trigger_gate": "launch_gate_summary.blocking_gate_names",
            "unblock_condition": "launch_expand becomes allowed",
            "operator_action_when_blocked": "keep_launch_frozen",
            "operator_action_when_clear": "leave_freeze_available",
        },
        "canary": {
            "owner": "fleet",
            "route": "measured_rollout_loop.canary",
            "cadence": "weekly",
            "trigger_gate": "provider_canary",
            "unblock_condition": "provider canary is green on all active lanes",
            "operator_action_when_blocked": "collect_canary_evidence",
            "operator_action_when_clear": "keep_canary_ready",
        },
        "rollback": {
            "owner": "fleet",
            "route": "measured_rollout_loop.rollback",
            "cadence": "weekly",
            "trigger_gate": "release_health",
            "unblock_condition": "release and support followthrough gates are clear",
            "operator_action_when_blocked": "prepare_rollback_or_revoke",
            "operator_action_when_clear": "keep_rollback_armed",
        },
        "focus_shift": {
            "owner": "fleet",
            "route": "measured_rollout_loop.focus_shift",
            "cadence": "weekly",
            "trigger_gate": "successor_wave_scope",
            "unblock_condition": "closed package stays verified and remaining work routes to dependency or sibling packages",
            "operator_action_when_blocked": "route_remaining_work_to_dependency_or_sibling_packages",
            "operator_action_when_clear": "route_remaining_work_to_dependency_or_sibling_packages",
        },
    }
    rows: List[Dict[str, Any]] = []
    for action in REQUIRED_DECISION_ACTIONS:
        board = dict(decision_board.get(action) or {})
        ledger_rows = [
            row for row in decision_gate_ledger.get(action) or [] if isinstance(row, dict)
        ]
        blocking_gates = [
            str(row.get("name") or "").strip() or "unknown"
            for row in ledger_rows
            if str(row.get("state") or "unknown").strip() not in {"pass", "clear"}
        ]
        gate_states = {
            str(row.get("name") or "").strip() or "unknown": str(
                row.get("state") or "unknown"
            ).strip()
            or "unknown"
            for row in ledger_rows
        }
        contract = dict(route_contract[action])
        state = str(board.get("state") or "unknown").strip() or "unknown"
        route_blocked = bool(blocking_gates) or state in {
            "active",
            "blocked",
            "accumulating",
            "watch",
        }
        operator_action = (
            str(contract.get("operator_action_when_blocked") or "").strip()
            if route_blocked
            else str(contract.get("operator_action_when_clear") or "").strip()
        )
        reason = str(board.get("reason") or board.get("next_decision") or "").strip()
        rows.append(
            {
                "action": action,
                "owner": contract["owner"],
                "route": contract["route"],
                "cadence": contract["cadence"],
                "trigger_gate": contract["trigger_gate"],
                "unblock_condition": contract["unblock_condition"],
                "route_blocked": route_blocked,
                "operator_action_when_blocked": contract["operator_action_when_blocked"],
                "operator_action_when_clear": contract["operator_action_when_clear"],
                "operator_action": operator_action,
                "state": state,
                "next_decision": reason,
                "reason": reason,
                "gate_states": gate_states,
                "blocking_gates": blocking_gates,
                "blocking_gate_count": len(blocking_gates),
                "ready_for_operator_packet": bool(
                    state
                    and reason
                    and contract.get("owner")
                    and contract.get("route")
                    and contract.get("cadence")
                    and contract.get("trigger_gate")
                    and contract.get("unblock_condition")
                    and operator_action
                    and gate_states
                ),
            }
        )
    missing_actions = [
        action
        for action in REQUIRED_DECISION_ACTIONS
        if not any(row["action"] == action for row in rows)
    ]
    incomplete_actions = [
        row["action"] for row in rows if row["ready_for_operator_packet"] is not True
    ]
    return {
        "status": "pass" if not missing_actions and not incomplete_actions else "fail",
        "required_actions": list(REQUIRED_DECISION_ACTIONS),
        "missing_actions": missing_actions,
        "incomplete_actions": incomplete_actions,
        "rows": rows,
    }


def _decision_receipts(
    *,
    decision_action_matrix: List[Dict[str, Any]],
    decision_action_routes: Dict[str, Any],
) -> Dict[str, Any]:
    matrix_by_action = {
        str(row.get("action") or "").strip(): row
        for row in decision_action_matrix
        if isinstance(row, dict)
    }
    route_by_action = {
        str(row.get("action") or "").strip(): row
        for row in decision_action_routes.get("rows") or []
        if isinstance(row, dict)
    }
    rows: List[Dict[str, Any]] = []
    for action in REQUIRED_DECISION_ACTIONS:
        matrix = dict(matrix_by_action.get(action) or {})
        route = dict(route_by_action.get(action) or {})
        receipt_source = {
            "action": action,
            "state": str(route.get("state") or matrix.get("board_state") or "").strip(),
            "route": str(route.get("route") or "").strip(),
            "operator_action": str(route.get("operator_action") or "").strip(),
            "ledger_gate_count": _coerce_int(matrix.get("ledger_gate_count"), 0),
            "governor_gate_count": _coerce_int(matrix.get("governor_gate_count"), 0),
            "blocking_gate_count": _coerce_int(route.get("blocking_gate_count"), 0),
            "blocking_gates": _norm_list(route.get("blocking_gates")),
            "gate_states": dict(route.get("gate_states") or {}),
            "matrix_complete": matrix.get("complete") is True,
            "ready_for_operator_packet": route.get("ready_for_operator_packet") is True,
        }
        digest = hashlib.sha256(
            json.dumps(receipt_source, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        ).hexdigest()
        rows.append(
            {
                "action": action,
                "receipt_id": f"m106-{action}-{digest[:16]}",
                "receipt_sha256": digest,
                "state": receipt_source["state"] or "missing",
                "route": receipt_source["route"] or "missing",
                "operator_action": receipt_source["operator_action"] or "missing",
                "ledger_gate_count": receipt_source["ledger_gate_count"],
                "governor_gate_count": receipt_source["governor_gate_count"],
                "blocking_gate_count": receipt_source["blocking_gate_count"],
                "blocking_gates": receipt_source["blocking_gates"],
                "matrix_complete": receipt_source["matrix_complete"],
                "ready_for_operator_packet": receipt_source["ready_for_operator_packet"],
            }
        )
    incomplete_actions = [
        row["action"]
        for row in rows
        if row["matrix_complete"] is not True
        or row["ready_for_operator_packet"] is not True
        or not str(row.get("receipt_id") or "").startswith(f"m106-{row['action']}-")
    ]
    return {
        "status": "pass" if not incomplete_actions else "fail",
        "required_actions": list(REQUIRED_DECISION_ACTIONS),
        "receipt_count": len(rows),
        "incomplete_actions": incomplete_actions,
        "rows": rows,
    }


def _weekly_operator_handoff(
    *,
    schedule: Dict[str, Any],
    launch_gate_summary: Dict[str, Any],
    decision_action_routes: Dict[str, Any],
    decision_receipts: Dict[str, Any],
) -> Dict[str, Any]:
    receipt_by_action = {
        str(row.get("action") or "").strip(): row
        for row in decision_receipts.get("rows") or []
        if isinstance(row, dict)
    }
    rows: List[Dict[str, Any]] = []
    incomplete_actions: List[str] = []
    for route in decision_action_routes.get("rows") or []:
        if not isinstance(route, dict):
            continue
        action = str(route.get("action") or "").strip()
        if action not in REQUIRED_DECISION_ACTIONS:
            continue
        receipt = dict(receipt_by_action.get(action) or {})
        row = {
            "action": action,
            "state": str(route.get("state") or "").strip() or "unknown",
            "route": str(route.get("route") or "").strip() or "missing",
            "operator_action": str(route.get("operator_action") or "").strip() or "missing",
            "receipt_id": str(receipt.get("receipt_id") or "").strip() or "missing",
            "blocking_gate_count": _coerce_int(route.get("blocking_gate_count"), 0),
            "blocking_gates": _norm_list(route.get("blocking_gates")),
            "next_decision": str(route.get("next_decision") or "").strip(),
        }
        if (
            row["route"] == "missing"
            or row["operator_action"] == "missing"
            or row["receipt_id"] == "missing"
            or not row["next_decision"]
        ):
            incomplete_actions.append(action)
        rows.append(row)
    present_actions = {row["action"] for row in rows}
    missing_actions = [
        action for action in REQUIRED_DECISION_ACTIONS if action not in present_actions
    ]
    return {
        "status": "pass" if not missing_actions and not incomplete_actions else "fail",
        "cadence": str(schedule.get("cadence") or "").strip() or "weekly",
        "schedule_ref": "governor_packet_schedule.next_packet_due_at",
        "source": "measured_rollout_loop.decision_action_routes+decision_receipts",
        "required_actions": list(REQUIRED_DECISION_ACTIONS),
        "action_count": len(rows),
        "missing_actions": missing_actions,
        "incomplete_actions": incomplete_actions,
        "launch_gate_blocking_names": _norm_list(
            launch_gate_summary.get("blocking_gate_names")
        ),
        "rows": rows,
    }


def _launch_gate_summary(launch_gate_ledger: List[Dict[str, Any]]) -> Dict[str, Any]:
    states: Dict[str, int] = {}
    blocking_gate_names: List[str] = []
    for row in launch_gate_ledger:
        if not isinstance(row, dict):
            continue
        state = str(row.get("state") or "unknown").strip() or "unknown"
        states[state] = states.get(state, 0) + 1
        if state != "pass":
            name = str(row.get("name") or "").strip()
            blocking_gate_names.append(name or "unknown")
    return {
        "gate_count": len([row for row in launch_gate_ledger if isinstance(row, dict)]),
        "pass_count": states.get("pass", 0),
        "blocked_count": states.get("blocked", 0),
        "fail_count": states.get("fail", 0),
        "watch_count": states.get("watch", 0),
        "accumulating_count": states.get("accumulating", 0),
        "unknown_count": states.get("unknown", 0),
        "blocking_gate_names": blocking_gate_names,
        "all_green": not blocking_gate_names,
    }


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
    adoption_summary = _adoption_summary(weekly_pulse)
    local_release_proof = str(
        adoption.get("local_release_proof_status")
        or launch_signals.get("local_release_proof_status")
        or "unknown"
    ).strip()
    canary_status = str(
        provider.get("canary_status") or launch_signals.get("provider_canary_status") or "unknown"
    ).strip()
    closure_state = str(
        closure.get("state") or launch_signals.get("closure_health_state") or "unknown"
    ).strip()
    status_plane_final_claim = str(
        status_plane.get("whole_product_final_claim_status") or ""
    ).strip()
    journey_state = str(
        journey_summary.get("overall_state")
        or (weekly_pulse.get("journey_gate_health") or {}).get("state")
        or launch_signals.get("journey_gate_state")
        or "unknown"
    ).strip()
    readiness_status = str(flagship_readiness.get("status") or "unknown").strip()
    parity = _flagship_parity_summary(flagship_readiness)
    quality = _flagship_quality_summary(flagship_readiness)
    parity_gold_ready = parity["release_truth_status"] == "gold_ready"
    quality_ready = quality["release_truth_status"] == "pass"
    dependency_posture = dict(verification.get("dependency_posture") or {})
    dependency_package_routes = _dependency_package_routes(
        dependency_posture=dependency_posture,
        design_queue=design_queue,
        queue=queue,
    )
    dependency_status = str(dependency_posture.get("status") or "open").strip()
    launch_allowed = (
        verification["status"] == "pass"
        and weekly_input_health["status"] == "pass"
        and source_input_health["status"] == "pass"
        and dependency_status == "satisfied"
        and readiness_status == "pass"
        and parity_gold_ready
        and quality_ready
        and status_plane_final_claim == "pass"
        and journey_state == "ready"
        and local_release_proof == "passed"
        and adoption_summary["state"] != "unknown"
        and adoption_summary["history_snapshot_count"] > 0
        and canary_status == "Canary green on all active lanes"
        and closure_state == "clear"
        and support["open_non_external_packet_count"] == 0
        and support["reporter_followthrough_blocked_missing_install_receipts_count"] == 0
        and support["reporter_followthrough_blocked_receipt_mismatch_count"] == 0
        and support["followthrough_receipt_gates_blocked_missing_install_receipts_count"] == 0
        and support["followthrough_receipt_gates_blocked_receipt_mismatch_count"] == 0
    )
    launch_action = str(launch_decision.get("action") or "freeze_launch").strip()
    decision_alignment = _decision_alignment(launch_action, launch_allowed)
    freeze_active = not launch_allowed
    rollback_watch = (
        support["closure_waiting_on_release_truth"] > 0
        or support["update_required_misrouted_case_count"] > 0
        or support["reporter_followthrough_blocked_missing_install_receipts_count"] > 0
        or support["reporter_followthrough_blocked_receipt_mismatch_count"] > 0
        or support["followthrough_receipt_gates_blocked_missing_install_receipts_count"] > 0
        or support["followthrough_receipt_gates_blocked_receipt_mismatch_count"] > 0
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
            "flagship_quality",
            "pass" if quality_ready else "blocked",
            "localization pass and accessibility/polish proof ready",
            quality["release_truth_status"],
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
            "weekly_adoption_truth",
            "pass"
            if adoption_summary["state"] != "unknown"
            and adoption_summary["history_snapshot_count"] > 0
            else "blocked",
            "present with measured history",
            (
                f"{adoption_summary['state']} / "
                f"{adoption_summary['history_snapshot_count']} history snapshots"
            ),
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
        _gate_row(
            "support_followthrough_receipts",
            "pass"
            if support["reporter_followthrough_blocked_missing_install_receipts_count"] == 0
            and support["reporter_followthrough_blocked_receipt_mismatch_count"] == 0
            and support["followthrough_receipt_gates_blocked_missing_install_receipts_count"] == 0
            and support["followthrough_receipt_gates_blocked_receipt_mismatch_count"] == 0
            else "blocked",
            "0 missing or mismatched install receipt blockers",
            (
                "reporter_missing="
                f"{support['reporter_followthrough_blocked_missing_install_receipts_count']}; "
                "reporter_mismatch="
                f"{support['reporter_followthrough_blocked_receipt_mismatch_count']}; "
                "receipt_gate_missing="
                f"{support['followthrough_receipt_gates_blocked_missing_install_receipts_count']}; "
                "receipt_gate_mismatch="
                f"{support['followthrough_receipt_gates_blocked_receipt_mismatch_count']}"
            ),
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
            "support_followthrough_receipt_blockers",
            "watch"
            if support["reporter_followthrough_blocked_missing_install_receipts_count"] > 0
            or support["reporter_followthrough_blocked_receipt_mismatch_count"] > 0
            or support["followthrough_receipt_gates_blocked_missing_install_receipts_count"] > 0
            or support["followthrough_receipt_gates_blocked_receipt_mismatch_count"] > 0
            else "clear",
            "0 missing or mismatched install receipt blockers",
            (
                "reporter_missing="
                f"{support['reporter_followthrough_blocked_missing_install_receipts_count']}; "
                "reporter_mismatch="
                f"{support['reporter_followthrough_blocked_receipt_mismatch_count']}; "
                "receipt_gate_missing="
                f"{support['followthrough_receipt_gates_blocked_missing_install_receipts_count']}; "
                "receipt_gate_mismatch="
                f"{support['followthrough_receipt_gates_blocked_receipt_mismatch_count']}"
            ),
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
        and quality_ready
        and status_plane_final_claim == "pass"
        and support["open_non_external_packet_count"] == 0
        and support["reporter_followthrough_blocked_missing_install_receipts_count"] == 0
        and support["reporter_followthrough_blocked_receipt_mismatch_count"] == 0
        and support["followthrough_receipt_gates_blocked_missing_install_receipts_count"] == 0
        and support["followthrough_receipt_gates_blocked_receipt_mismatch_count"] == 0
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
        "dependency_package_routes": dependency_package_routes,
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
            "rule": (
                "Worker proof must come from repo-local files, generated packets, and tests, "
                "not operator telemetry, supervisor helper loops, supervisor status/ETA helpers, "
                "or active-run helper commands; "
                "active-run helpers are hard-blocked, count as run failure, and return non-zero "
                "during active runs."
            ),
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
            "reason": "All measured launch gates are green." if launch_allowed else "Hold expansion until successor dependencies, readiness, parity, localization/accessibility quality, status-plane final claim, local release proof, canary, closure, and support gates are all green.",
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
    governor_decisions = _governor_decision_rows(decision_board, decision_gate_ledger)
    decision_action_matrix = _decision_action_matrix(
        decision_board=decision_board,
        decision_gate_ledger=decision_gate_ledger,
        governor_decisions=governor_decisions,
    )
    decision_action_coverage = _decision_action_coverage(
        decision_board=decision_board,
        decision_gate_ledger=decision_gate_ledger,
        governor_decisions=governor_decisions,
        decision_action_matrix=decision_action_matrix,
    )
    decision_source_coverage = _decision_source_coverage(
        decision_board=decision_board,
        decision_gate_ledger=decision_gate_ledger,
    )
    decision_action_routes = _decision_action_routes(
        decision_board=decision_board,
        decision_gate_ledger=decision_gate_ledger,
    )
    decision_receipts = _decision_receipts(
        decision_action_matrix=decision_action_matrix,
        decision_action_routes=decision_action_routes,
    )
    launch_gate_summary = _launch_gate_summary(launch_gate_ledger)
    source_input_fingerprint = _source_input_fingerprint(source_input_health)
    generated_at = iso_now()
    governor_packet_schedule = _packet_schedule(generated_at)
    weekly_operator_handoff = _weekly_operator_handoff(
        schedule=governor_packet_schedule,
        launch_gate_summary=launch_gate_summary,
        decision_action_routes=decision_action_routes,
        decision_receipts=decision_receipts,
    )
    return {
        "contract_name": "fleet.weekly_governor_packet",
        "schema_version": 1,
        "status": packet_status,
        "status_reason": status_reason,
        "generated_at": generated_at,
        "governor_packet_schedule": governor_packet_schedule,
        "as_of": str(weekly_pulse.get("as_of") or "").strip(),
        "program_wave": "next_90_day_product_advance",
        "wave_id": WAVE_ID,
        "successor_frontier_ids": list(SUCCESSOR_FRONTIER_IDS),
        "package_verification": verification,
        "weekly_input_health": weekly_input_health,
        "source_input_health": source_input_health,
        "source_input_fingerprint": source_input_fingerprint,
        "decision_alignment": decision_alignment,
        "source_paths": source_paths,
        "truth_inputs": {
            "weekly_pulse_contract": str(weekly_pulse.get("contract_name") or "").strip(),
            "weekly_pulse_version": _coerce_int(weekly_pulse.get("contract_version"), 0),
            "flagship_readiness_status": readiness_status,
            "flagship_parity_release_truth": parity,
            "flagship_quality_release_truth": quality,
            "journey_gate_state": journey_state,
            "local_release_proof_status": local_release_proof,
            "provider_canary_status": canary_status,
            "closure_health_state": closure_state,
            "successor_dependency_status": dependency_status,
            "successor_dependency_posture": dependency_posture,
            "successor_dependency_package_routes": dependency_package_routes,
            "support_summary": support,
            "adoption_health": adoption_summary,
            "status_plane_final_claim": status_plane_final_claim,
            "closed_flagship_registry_status": str(closed_flagship_registry.get("status") or "").strip(),
        },
        "decision_board": decision_board,
        "decision_gate_ledger": decision_gate_ledger,
        "governor_decisions": governor_decisions,
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
            "dependency_package_routes": dependency_package_routes,
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
            "launch_expansion_ready": launch_allowed,
            "freeze_active": freeze_active,
            "canary_ready": canary_status == "Canary green on all active lanes",
            "rollback_watch": rollback_watch,
            "blocked_dependency_package_ids": blocked_dependency_package_ids,
            "dependency_package_routes": dependency_package_routes,
            "required_decision_actions": list(REQUIRED_DECISION_ACTIONS),
            "launch_gate_summary": launch_gate_summary,
            "decision_action_matrix": decision_action_matrix,
            "decision_action_coverage": decision_action_coverage,
            "decision_source_coverage": decision_source_coverage,
            "decision_action_routes": decision_action_routes,
            "decision_receipts": decision_receipts,
            "weekly_operator_handoff": weekly_operator_handoff,
            "evidence_requirements": [
                "successor registry and queue item match package authority",
                "design-owned queue staging and Fleet queue mirror both carry the completed package proof",
                "successor registry work task 106.1 remains complete with weekly governor evidence markers",
                "successor dependency milestones are complete before launch expansion is allowed",
                "closed dependency package rows route to verify_closed_package_only instead of reopening completed predecessor packages",
                "weekly pulse cites journey, local release proof, canary, and closure signals",
                "weekly adoption truth is present with measured history before launch expansion is allowed",
                "flagship readiness remains green before any launch expansion",
                "flagship parity remains at veteran_ready or gold_ready before the measured loop can steer launch decisions",
                "localization and accessibility/polish proof remain green before measured rollout readiness",
                "status-plane final claim remains pass before launch expansion or measured rollout readiness",
                "support packet counts stay clear for non-external closure work",
                "support followthrough stays free of missing or mismatched install receipt blockers",
                "fix-available, please-test, and recovery followthrough counts come from install-aware receipt gates",
                "each measured decision cites its required source gate rows before the packet can claim decision-source coverage",
                "each measured decision names an owner, route, trigger gate, and unblock condition before the packet can drive operator action",
                "each measured decision publishes gate-state, blocking-count, and operator-action fields before the weekly packet can drive launch, freeze, canary, rollback, or focus-shift action",
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
    schedule = dict(payload.get("governor_packet_schedule") or {})
    closeout = dict(payload.get("package_closeout") or {})
    repeat_prevention = dict(payload.get("repeat_prevention") or {})
    worker_command_guard = dict(repeat_prevention.get("worker_command_guard") or {})
    flagship_wave_guard = dict(repeat_prevention.get("flagship_wave_guard") or {})
    weekly = dict(payload.get("weekly_input_health") or {})
    sources = dict(payload.get("source_input_health") or {})
    source_inputs = dict(sources.get("required_inputs") or {})
    launch_signal_alignment = dict(source_inputs.get("launch_signal_truth_alignment") or {})
    decision_alignment = dict(payload.get("decision_alignment") or {})
    support = dict(truth.get("support_summary") or {})
    adoption = dict(truth.get("adoption_health") or {})
    dependency = dict(truth.get("successor_dependency_posture") or {})
    dependency_routes = dict(truth.get("successor_dependency_package_routes") or {})
    parity = dict(truth.get("flagship_parity_release_truth") or {})
    quality = dict(truth.get("flagship_quality_release_truth") or {})
    public_copy = dict(payload.get("public_status_copy") or {})
    gate_ledger = dict(payload.get("decision_gate_ledger") or {})
    launch_gate_summary = dict(loop.get("launch_gate_summary") or {})
    source_coverage = dict(loop.get("decision_source_coverage") or {})
    action_routes = dict(loop.get("decision_action_routes") or {})
    operator_handoff = dict(loop.get("weekly_operator_handoff") or {})
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
            f"- Source input fingerprint: {_markdown_status(dict(payload.get('source_input_fingerprint') or {}).get('combined_source_sha256'))}",
            f"- Launch cited signal truth alignment: {_markdown_status(launch_signal_alignment.get('state'))}",
            f"- Decision alignment: {_markdown_status(decision_alignment.get('status'))}",
            f"- Expected launch action: {_markdown_status(decision_alignment.get('expected_action'))}",
            f"- Actual launch action: {_markdown_status(decision_alignment.get('actual_action'))}",
            f"- Package closeout: {_markdown_status(closeout.get('status'))}",
            f"- Do not reopen package: {bool(closeout.get('do_not_reopen_package'))}",
            f"- Measured rollout loop: {_markdown_status(loop.get('loop_status'))}",
            f"- Governor packet cadence: {_markdown_status(schedule.get('cadence'))}",
            f"- Next packet due: {_markdown_status(schedule.get('next_packet_due_at'))}",
            f"- Decision action coverage: {_markdown_status(dict(loop.get('decision_action_coverage') or {}).get('status'))}",
            f"- Decision actions covered: {dict(loop.get('decision_action_coverage') or {}).get('covered_action_count', 0)} / {dict(loop.get('decision_action_coverage') or {}).get('required_action_count', 0)}",
            f"- Decision source coverage: {_markdown_status(source_coverage.get('status'))}",
            f"- Decision sources covered: {source_coverage.get('covered_action_count', 0)} / {source_coverage.get('required_action_count', 0)}",
            f"- Decision action routing: {_markdown_status(action_routes.get('status'))}",
            f"- Weekly operator handoff: {_markdown_status(operator_handoff.get('status'))}",
            f"- Weekly operator handoff actions: {operator_handoff.get('action_count', 0)} / {len(operator_handoff.get('required_actions') or [])}",
            f"- Launch expansion ready: {bool(loop.get('launch_expansion_ready'))}",
            f"- Launch gates green: {bool(launch_gate_summary.get('all_green'))}",
            f"- Launch gate pass count: {launch_gate_summary.get('pass_count', 0)}",
            f"- Launch gate blocked count: {launch_gate_summary.get('blocked_count', 0)}",
            f"- Launch gate fail count: {launch_gate_summary.get('fail_count', 0)}",
            f"- Launch gate blocking names: {_markdown_list(launch_gate_summary.get('blocking_gate_names'))}",
            f"- Freeze active: {bool(loop.get('freeze_active'))}",
            f"- Canary ready: {bool(loop.get('canary_ready'))}",
            f"- Rollback watch: {bool(loop.get('rollback_watch'))}",
            f"- Registry work task 106.1 status: {_markdown_status(verification.get('registry_work_task_status'))}",
            f"- Required registry evidence markers: {len(verification.get('required_registry_evidence_markers') or [])}",
            f"- Queue closeout status: {_markdown_status(verification.get('queue_status'))}",
            f"- Queue mirror status: {_markdown_status(verification.get('queue_mirror_status'))}",
            f"- Required queue proof markers: {len(verification.get('required_queue_proof_markers') or [])}",
            f"- Required resolving proof paths: {_markdown_list(verification.get('required_resolving_proof_paths'))}",
            f"- Successor dependency posture: {_markdown_status(dependency.get('status'))}",
            f"- Open successor dependencies: {_markdown_list(dependency.get('open_dependency_ids'))}",
            f"- Dependency package routing: {_markdown_status(dependency_routes.get('status'))}",
            f"- Closed dependency packages verified: {dependency_routes.get('closed_package_count', 0)}",
            f"- Open registry dependency milestones: {dependency_routes.get('open_registry_milestone_count', 0)}",
            f"- Remaining sibling work tasks: {_markdown_list(closeout.get('remaining_sibling_work_task_ids'))}",
            f"- Flagship readiness: {_markdown_status(truth.get('flagship_readiness_status'))}",
            f"- Flagship parity release truth: {_markdown_status(parity.get('release_truth_status'))}",
            f"- Flagship quality release truth: {_markdown_status(quality.get('release_truth_status'))}",
            f"- Localization gate: {_markdown_status(quality.get('localization_release_gate_status'))}",
            f"- Accessibility proof named: {_markdown_status(quality.get('accessibility_proof_named'))}",
            f"- Journey gate state: {_markdown_status(truth.get('journey_gate_state'))}",
            f"- Local release proof: {_markdown_status(truth.get('local_release_proof_status'))}",
            f"- Weekly adoption state: {_markdown_status(adoption.get('state'))}",
            f"- Weekly adoption history snapshots: {adoption.get('history_snapshot_count', 0)}",
            f"- Weekly adoption proven journeys: {adoption.get('proven_journey_count', 0)}",
            f"- Weekly adoption proven routes: {adoption.get('proven_route_count', 0)}",
            f"- Provider canary: {_markdown_status(truth.get('provider_canary_status'))}",
            f"- Closure health: {_markdown_status(truth.get('closure_health_state'))}",
            f"- Open non-external support packets: {support.get('open_non_external_packet_count', 0)}",
            f"- Reporter followthrough ready: {support.get('reporter_followthrough_ready_count', 0)}",
            f"- Feedback followthrough ready: {support.get('feedback_followthrough_ready_count', 0)}",
            f"- Fix-available ready: {support.get('fix_available_ready_count', 0)}",
            f"- Please-test ready: {support.get('please_test_ready_count', 0)}",
            f"- Recovery-loop ready: {support.get('recovery_loop_ready_count', 0)}",
            f"- Followthrough blocked on install receipts: {support.get('reporter_followthrough_blocked_missing_install_receipts_count', 0)}",
            f"- Followthrough receipt mismatches: {support.get('reporter_followthrough_blocked_receipt_mismatch_count', 0)}",
            f"- Followthrough waiting on fix receipt: {support.get('reporter_followthrough_hold_until_fix_receipt_count', 0)}",
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
            f"- Dependency package route rule: {_markdown_status(dict(repeat_prevention.get('dependency_package_routes') or {}).get('rule'))}",
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
            f"- Derived from: {_markdown_status(public_copy.get('derived_from'))}",
            f"- Decision actions: {_markdown_list(public_copy.get('decision_actions'))}",
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

    lines.extend(
        [
            "",
            "## Decision Action Matrix",
            "",
            "| Action | Board state | Ledger gates | Governor state | Governor gates | Complete |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in loop.get("decision_action_matrix") or []:
        if not isinstance(row, dict):
            continue
        lines.append(
            f"| {_markdown_status(row.get('action'))} | {_markdown_status(row.get('board_state'))} | "
            f"{row.get('ledger_gate_count', 0)} | {_markdown_status(row.get('governor_state'))} | "
            f"{row.get('governor_gate_count', 0)} | {bool(row.get('complete'))} |"
        )
    if not loop.get("decision_action_matrix"):
        lines.append("| none | missing | 0 | missing | 0 | False |")

    lines.extend(
        [
            "",
            "## Decision Source Coverage",
            "",
            "| Action | Required gates | Missing gates | Covered |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in source_coverage.get("rows") or []:
        if not isinstance(row, dict):
            continue
        lines.append(
            f"| {_markdown_status(row.get('action'))} | "
            f"{_markdown_list(row.get('required_gates'))} | "
            f"{_markdown_list(row.get('missing_gates'))} | "
            f"{bool(row.get('covered'))} |"
        )
    if not source_coverage.get("rows"):
        lines.append("| none | none | none | False |")

    lines.extend(
        [
            "",
            "## Decision Action Routes",
            "",
            "| Action | Owner | Route | Cadence | Trigger gate | Route blocked | Operator action | Blocked action | Clear action | Blocking gates | Next decision | Ready |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in action_routes.get("rows") or []:
        if not isinstance(row, dict):
            continue
        lines.append(
            f"| {_markdown_status(row.get('action'))} | "
            f"{_markdown_status(row.get('owner'))} | "
            f"{_markdown_status(row.get('route'))} | "
            f"{_markdown_status(row.get('cadence'))} | "
            f"{_markdown_status(row.get('trigger_gate'))} | "
            f"{bool(row.get('route_blocked'))} | "
            f"{_markdown_status(row.get('operator_action'))} | "
            f"{_markdown_status(row.get('operator_action_when_blocked'))} | "
            f"{_markdown_status(row.get('operator_action_when_clear'))} | "
            f"{_markdown_list(row.get('blocking_gates'))} | "
            f"{_markdown_status(row.get('next_decision'))} | "
            f"{bool(row.get('ready_for_operator_packet'))} |"
        )
    if not action_routes.get("rows"):
        lines.append(
            "| none | unknown | unknown | unknown | unknown | False | unknown | unknown | unknown | none | none | False |"
        )

    lines.extend(
        [
            "",
            "## Weekly Operator Handoff",
            "",
            f"- Source: {_markdown_status(operator_handoff.get('source'))}",
            f"- Cadence: {_markdown_status(operator_handoff.get('cadence'))}",
            f"- Schedule ref: {_markdown_status(operator_handoff.get('schedule_ref'))}",
            f"- Launch gate blocking names: {_markdown_list(operator_handoff.get('launch_gate_blocking_names'))}",
            "",
            "| Action | State | Route | Operator action | Receipt | Blocking gates | Next decision |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in operator_handoff.get("rows") or []:
        if not isinstance(row, dict):
            continue
        lines.append(
            f"| {_markdown_status(row.get('action'))} | "
            f"{_markdown_status(row.get('state'))} | "
            f"{_markdown_status(row.get('route'))} | "
            f"{_markdown_status(row.get('operator_action'))} | "
            f"{_markdown_status(row.get('receipt_id'))} | "
            f"{_markdown_list(row.get('blocking_gates'))} | "
            f"{_markdown_status(row.get('next_decision'))} |"
        )
    if not operator_handoff.get("rows"):
        lines.append("| none | unknown | unknown | unknown | missing | none | none |")

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

    lines.extend(
        [
            "",
            "## Dependency Package Routes",
            "",
            "| Milestone | Package | Registry | Queue | Design queue | Route | Launch gate |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in dependency_routes.get("rows") or []:
        if not isinstance(row, dict):
            continue
        lines.append(
            f"| {row.get('milestone_id', 'unknown')} | "
            f"{_markdown_status(row.get('package_id'))} | "
            f"{_markdown_status(row.get('registry_status'))} | "
            f"{_markdown_status(row.get('queue_status'))} | "
            f"{_markdown_status(row.get('design_queue_status'))} | "
            f"{_markdown_status(row.get('operator_route'))} | "
            f"{_markdown_status(row.get('launch_gate_contribution'))} |"
        )
    if not dependency_routes.get("rows"):
        lines.append("| none | none | unknown | unknown | unknown | unknown | unknown |")

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
