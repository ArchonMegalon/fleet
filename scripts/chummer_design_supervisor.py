#!/usr/bin/env python3
"""Run a long-lived Chummer design supervisor from Fleet."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib
import json
import os
import re
import stat
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

import yaml


DEFAULT_WORKSPACE_ROOT = Path("/docker/fleet")
DEFAULT_ACCOUNTS_PATH = DEFAULT_WORKSPACE_ROOT / "config" / "accounts.yaml"
DEFAULT_SCOPE_ROOTS = [
    Path("/docker/fleet"),
    Path("/docker/chummercomplete"),
    Path("/docker/fleet/repos"),
    Path("/docker/chummer5a"),
    Path("/docker/EA"),
]
DEFAULT_DESIGN_PRODUCT_ROOT = Path("/docker/chummercomplete/chummer-design/products/chummer")
DEFAULT_REGISTRY_PATH = DEFAULT_DESIGN_PRODUCT_ROOT / "NEXT_20_BIG_WINS_AFTER_POST_AUDIT_CLOSEOUT_REGISTRY.yaml"
DEFAULT_PROGRAM_MILESTONES_PATH = DEFAULT_DESIGN_PRODUCT_ROOT / "PROGRAM_MILESTONES.yaml"
DEFAULT_ROADMAP_PATH = DEFAULT_DESIGN_PRODUCT_ROOT / "ROADMAP.md"
DEFAULT_GOLDEN_JOURNEY_GATES_PATH = DEFAULT_DESIGN_PRODUCT_ROOT / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"
DEFAULT_WEEKLY_PULSE_PATH = DEFAULT_DESIGN_PRODUCT_ROOT / "WEEKLY_PRODUCT_PULSE.generated.json"
DEFAULT_HANDOFF_PATH = DEFAULT_WORKSPACE_ROOT / "NEXT_SESSION_HANDOFF.md"
DEFAULT_PROJECTS_DIR = DEFAULT_WORKSPACE_ROOT / "config" / "projects"
DEFAULT_STATUS_PLANE_PATH = DEFAULT_WORKSPACE_ROOT / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
DEFAULT_PROGRESS_REPORT_PATH = DEFAULT_WORKSPACE_ROOT / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
DEFAULT_PROGRESS_HISTORY_PATH = DEFAULT_WORKSPACE_ROOT / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
DEFAULT_SUPPORT_PACKETS_PATH = DEFAULT_WORKSPACE_ROOT / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
DEFAULT_COMPLETION_REVIEW_FRONTIER_PUBLISHED_PATH = (
    DEFAULT_WORKSPACE_ROOT / ".codex-studio" / "published" / "COMPLETION_REVIEW_FRONTIER.generated.yaml"
)
DEFAULT_COMPLETION_REVIEW_FRONTIER_MIRROR_PATH = (
    DEFAULT_WORKSPACE_ROOT / ".codex-design" / "product" / "COMPLETION_REVIEW_FRONTIER.generated.yaml"
)
DEFAULT_UI_LINUX_DESKTOP_REPO_ROOT = Path("/docker/chummercomplete/chummer6-ui")
DEFAULT_UI_LINUX_DESKTOP_EXIT_GATE_PATH = (
    Path("/docker/chummercomplete/chummer6-ui/.codex-studio/published/UI_LINUX_DESKTOP_EXIT_GATE.generated.json")
)
DEFAULT_STATE_ROOT = DEFAULT_WORKSPACE_ROOT / "state" / "chummer_design_supervisor"
DEFAULT_STATE_PATH = DEFAULT_STATE_ROOT / "state.json"
DEFAULT_HISTORY_PATH = DEFAULT_STATE_ROOT / "history.jsonl"
DEFAULT_RUNS_DIR = DEFAULT_STATE_ROOT / "runs"
DEFAULT_LOCK_PATH = DEFAULT_STATE_ROOT / "loop.lock"
DEFAULT_WORKER_BIN = "codex"
DEFAULT_MODEL = ""
DEFAULT_FALLBACK_MODELS = ("gpt-5.4",)
DEFAULT_FALLBACK_WORKER_LANES = {
    "core": ("repair",),
    "jury": ("core", "repair"),
    "survival": ("repair",),
}
DEFAULT_ACCOUNT_OWNER_IDS = ("tibor.girschele", "the.girscheles", "archon.megalon")
DEFAULT_POLL_SECONDS = 20.0
DEFAULT_COOLDOWN_SECONDS = 5.0
DEFAULT_FAILURE_BACKOFF_SECONDS = 45.0
DEFAULT_EXTERNAL_BLOCKER_BACKOFF_SECONDS = 300.0
DEFAULT_RATE_LIMIT_BACKOFF_SECONDS = 60
DEFAULT_SPARK_BACKOFF_SECONDS = 900
DEFAULT_USAGE_LIMIT_BACKOFF_SECONDS = 21600
DEFAULT_AUTH_FAILURE_BACKOFF_SECONDS = 43200
DEFAULT_BACKEND_UNAVAILABLE_BACKOFF_SECONDS = 300
COMPLETION_AUDIT_HISTORY_LIMIT = 10
WEEKLY_PULSE_MAX_AGE_SECONDS = 8 * 24 * 3600
LINUX_DESKTOP_EXIT_GATE_MAX_AGE_SECONDS = 24 * 3600
ACTIVE_STATUSES = {"in_progress", "not_started", "open", "planned", "queued"}
DONE_STATUSES = {"complete", "completed", "done", "closed", "released"}
BLOCKER_CLEAR_VALUES = {"", "none", "no", "n/a", "no blocker", "no exact blocker"}
CHATGPT_AUTH_KINDS = {"chatgpt_auth_json", "auth_json"}
READY_ACCOUNT_STATES = {"", "ready", "unknown", "ok"}
SPARK_MODEL = "gpt-5.3-codex-spark"
FLAGSHIP_UI_APP_KEY = "avalonia"
FLAGSHIP_UI_PROJECT_PATH = "Chummer.Avalonia/Chummer.Avalonia.csproj"
FLAGSHIP_UI_LAUNCH_TARGET = "Chummer.Avalonia"
FLAGSHIP_UI_READY_CHECKPOINT = "pre_ui_event_loop"
FLAGSHIP_UI_LINUX_TEST_PROJECT_PATH = "Chummer.Desktop.Runtime.Tests/Chummer.Desktop.Runtime.Tests.csproj"
FLAGSHIP_UI_LINUX_TEST_ASSEMBLY_NAME = "Chummer.Desktop.Runtime.Tests.dll"
FLAGSHIP_UI_LINUX_OUTPUT_ROOT = Path(".codex-studio/out/linux-desktop-exit-gate")
FLAGSHIP_UI_LINUX_DEB_PACKAGE_NAME = "chummer6-avalonia"
FLAGSHIP_UI_LINUX_WRAPPER_NAME = "chummer6-avalonia"
FLAGSHIP_UI_LINUX_DESKTOP_ENTRY_NAME = "Chummer6 Avalonia Desktop"
FLAGSHIP_UI_LINUX_GATE_INPUT_MARKERS = (
    "Chummer.Avalonia/",
    "Chummer.Desktop.Runtime/",
    "Chummer.Desktop.Runtime.Tests/",
    "Chummer.Tests/",
    "Chummer.Presentation/",
    "scripts/ai/",
    "scripts/build-desktop-installer.sh",
    "scripts/run-desktop-startup-smoke.sh",
    "scripts/materialize-linux-desktop-exit-gate.sh",
    "Directory.Build.props",
    "Directory.Build.targets",
    "Directory.Packages.props",
    "NuGet.Config",
    "global.json",
)
RETRYABLE_WORKER_ERROR_SIGNALS = (
    "usage limit",
    "rate limit",
    "quota",
    "upstream_timeout",
    "switch to another model",
    "not supported",
    "unsupported",
)
ETA_HISTORY_LIMIT = 50
ETA_STATUS_LOW_CONFIDENCE = "low"
ETA_STATUS_MEDIUM_CONFIDENCE = "medium"
ETA_STATUS_HIGH_CONFIDENCE = "high"
ETA_STATUS_BLOCKED_CONFIDENCE = "blocked"
ETA_EXTERNAL_BLOCKER_SIGNALS = (
    "usage limit",
    "rate limit",
    "quota",
    "refresh token",
    "auth session",
    "api key",
    "revoked",
    "expired",
    "backend unavailable",
    "upstream_timeout",
    "session is expired",
    "could not be refreshed",
)
LOCK_TTL_SECONDS = 300.0
LOCK_ACQUIRE_RETRIES = 12
LOCK_RETRY_SECONDS = 0.25
FOCUS_PROFILES: Dict[str, Dict[str, Any]] = {
    "desktop_client": {
        "description": "Prioritize desktop-client delivery across UI, core, rules, and SR4-SR6 readiness.",
        "owners": [
            "chummer6-ui",
            "chummer6-core",
            "chummer6-hub",
            "chummer6-ui-kit",
            "chummer6-hub-registry",
            "chummer6-design",
        ],
        "texts": [
            "desktop",
            "client",
            "workbench",
            "build lab",
            "build",
            "rules",
            "rule-environment",
            "navigator",
            "explain",
            "receipt",
            "onboarding",
            "starter",
            "sr4",
            "sr5",
            "sr6",
            "avalonia",
            "blazor",
        ],
    },
}
SYNTHETIC_COMPLETION_REVIEW_ID_BASE = 900_000_000
_SIBLING_MODULE_CACHE: Dict[str, Any] = {}


@dataclass(frozen=True)
class Milestone:
    id: int
    title: str
    wave: str
    status: str
    owners: List[str]
    exit_criteria: List[str]
    dependencies: List[int]


@dataclass(frozen=True)
class WorkerAccount:
    alias: str
    owner_id: str
    auth_kind: str
    auth_json_file: str
    api_key_env: str
    api_key_file: str
    allowed_models: List[str]
    health_state: str
    spark_enabled: bool
    bridge_priority: int
    forced_login_method: str
    forced_chatgpt_workspace_id: str
    openai_base_url: str
    home_dir: str


@dataclass
class WorkerRun:
    run_id: str
    started_at: str
    finished_at: str
    worker_command: List[str]
    attempted_accounts: List[str]
    attempted_models: List[str]
    selected_account_alias: str
    worker_exit_code: int
    frontier_ids: List[int]
    open_milestone_ids: List[int]
    primary_milestone_id: Optional[int]
    prompt_path: str
    stdout_path: str
    stderr_path: str
    last_message_path: str
    final_message: str
    shipped: str
    remains: str
    blocker: str
    accepted: bool
    acceptance_reason: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_shared_flags(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument(
            "--registry-path",
            default=str(DEFAULT_REGISTRY_PATH),
            help=f"Path to the active Chummer design registry (default: {DEFAULT_REGISTRY_PATH}).",
        )
        subparser.add_argument(
            "--program-milestones-path",
            default=str(DEFAULT_PROGRAM_MILESTONES_PATH),
            help=f"Path to PROGRAM_MILESTONES.yaml (default: {DEFAULT_PROGRAM_MILESTONES_PATH}).",
        )
        subparser.add_argument(
            "--roadmap-path",
            default=str(DEFAULT_ROADMAP_PATH),
            help=f"Path to ROADMAP.md (default: {DEFAULT_ROADMAP_PATH}).",
        )
        subparser.add_argument(
            "--handoff-path",
            default=str(DEFAULT_HANDOFF_PATH),
            help=f"Path to NEXT_SESSION_HANDOFF.md (default: {DEFAULT_HANDOFF_PATH}).",
        )
        subparser.add_argument(
            "--projects-dir",
            default=str(DEFAULT_PROJECTS_DIR),
            help=f"Path to Fleet project config YAMLs used for repo-local backlog synthesis (default: {DEFAULT_PROJECTS_DIR}).",
        )
        subparser.add_argument(
            "--journey-gates-path",
            default="",
            help=(
                "Optional path to GOLDEN_JOURNEY_RELEASE_GATES.yaml used for the completion audit. "
                "Defaults to the Fleet design mirror, then canonical design truth."
            ),
        )
        subparser.add_argument(
            "--weekly-pulse-path",
            default=str(DEFAULT_WEEKLY_PULSE_PATH),
            help=f"Path to WEEKLY_PRODUCT_PULSE.generated.json (default: {DEFAULT_WEEKLY_PULSE_PATH}).",
        )
        subparser.add_argument(
            "--accounts-path",
            default=str(DEFAULT_ACCOUNTS_PATH),
            help=f"Path to Fleet accounts config used for worker account rotation (default: {DEFAULT_ACCOUNTS_PATH}).",
        )
        subparser.add_argument(
            "--workspace-root",
            default=str(DEFAULT_WORKSPACE_ROOT),
            help=f"Fleet workspace root for the worker (default: {DEFAULT_WORKSPACE_ROOT}).",
        )
        subparser.add_argument(
            "--scope-root",
            action="append",
            default=[],
            help="Additional writable roots to pass to the worker. Repeatable.",
        )
        subparser.add_argument(
            "--state-root",
            default=str(DEFAULT_STATE_ROOT),
            help=f"State directory for supervisor logs and state (default: {DEFAULT_STATE_ROOT}).",
        )
        subparser.add_argument(
            "--status-plane-path",
            default=str(DEFAULT_STATUS_PLANE_PATH),
            help=f"Path to STATUS_PLANE.generated.yaml (default: {DEFAULT_STATUS_PLANE_PATH}).",
        )
        subparser.add_argument(
            "--progress-report-path",
            default=str(DEFAULT_PROGRESS_REPORT_PATH),
            help=f"Path to PROGRESS_REPORT.generated.json (default: {DEFAULT_PROGRESS_REPORT_PATH}).",
        )
        subparser.add_argument(
            "--progress-history-path",
            default=str(DEFAULT_PROGRESS_HISTORY_PATH),
            help=f"Path to PROGRESS_HISTORY.generated.json (default: {DEFAULT_PROGRESS_HISTORY_PATH}).",
        )
        subparser.add_argument(
            "--support-packets-path",
            default=str(DEFAULT_SUPPORT_PACKETS_PATH),
            help=f"Path to SUPPORT_CASE_PACKETS.generated.json (default: {DEFAULT_SUPPORT_PACKETS_PATH}).",
        )
        subparser.add_argument(
            "--ui-linux-desktop-exit-gate-path",
            default=str(DEFAULT_UI_LINUX_DESKTOP_EXIT_GATE_PATH),
            help=(
                "Path to the repo-local Linux desktop exit gate proof that must show build, startup-smoke, "
                f"and unit-test success (default: {DEFAULT_UI_LINUX_DESKTOP_EXIT_GATE_PATH})."
            ),
        )
        subparser.add_argument(
            "--ui-linux-desktop-repo-root",
            default=str(DEFAULT_UI_LINUX_DESKTOP_REPO_ROOT),
            help=(
                "Path to the UI repo root whose tracked git state must match the Linux desktop exit-gate proof "
                f"(default: {DEFAULT_UI_LINUX_DESKTOP_REPO_ROOT})."
            ),
        )
        subparser.add_argument(
            "--worker-bin",
            default=os.environ.get("CHUMMER_DESIGN_SUPERVISOR_WORKER_BIN", DEFAULT_WORKER_BIN),
            help=f"Worker binary to launch (default: {DEFAULT_WORKER_BIN}).",
        )
        subparser.add_argument(
            "--worker-model",
            default=os.environ.get("CHUMMER_DESIGN_SUPERVISOR_WORKER_MODEL", DEFAULT_MODEL),
            help="Optional worker model override.",
        )
        subparser.add_argument(
            "--worker-lane",
            default=os.environ.get("CHUMMER_DESIGN_SUPERVISOR_WORKER_LANE", ""),
            help="Optional worker lane prefix (for example: core when worker_bin is codexea).",
        )
        subparser.add_argument(
            "--fallback-worker-model",
            action="append",
            default=[],
            help="Optional fallback worker model when the current model returns a retryable quota/support error. Repeatable.",
        )
        subparser.add_argument(
            "--fallback-worker-lane",
            action="append",
            default=[],
            help="Optional fallback direct worker lane when the configured lane returns a retryable timeout/quota error. Repeatable.",
        )
        subparser.add_argument(
            "--account-owner-id",
            action="append",
            default=[],
            help="Restrict worker account rotation to one or more account owner ids from accounts.yaml. Repeatable.",
        )
        subparser.add_argument(
            "--account-alias",
            action="append",
            default=[],
            help="Restrict worker account rotation to explicit account aliases from accounts.yaml. Repeatable.",
        )
        subparser.add_argument(
            "--focus-owner",
            action="append",
            default=[],
            help="Bias the frontier toward milestones owned by one or more repos/owners first. Repeatable.",
        )
        subparser.add_argument(
            "--focus-profile",
            action="append",
            default=[],
            help="Apply a named steering profile before explicit focus owners/texts. Repeatable.",
        )
        subparser.add_argument(
            "--focus-text",
            action="append",
            default=[],
            help="Bias the frontier toward milestones whose title/exit criteria contain these case-insensitive terms. Repeatable.",
        )
        subparser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print derived prompt metadata without launching the worker.",
        )

    once_parser = subparsers.add_parser("once", help="Launch one bounded worker run from the current design frontier.")
    add_shared_flags(once_parser)

    loop_parser = subparsers.add_parser("loop", help="Keep launching worker runs until design completion or a hard blocker.")
    add_shared_flags(loop_parser)
    loop_parser.add_argument(
        "--poll-seconds",
        type=float,
        default=DEFAULT_POLL_SECONDS,
        help=f"Sleep between supervisor iterations (default: {DEFAULT_POLL_SECONDS}).",
    )
    loop_parser.add_argument(
        "--cooldown-seconds",
        type=float,
        default=DEFAULT_COOLDOWN_SECONDS,
        help=f"Pause after a successful worker run before the next derivation (default: {DEFAULT_COOLDOWN_SECONDS}).",
    )
    loop_parser.add_argument(
        "--failure-backoff-seconds",
        type=float,
        default=DEFAULT_FAILURE_BACKOFF_SECONDS,
        help=f"Pause after a failed worker run before retrying (default: {DEFAULT_FAILURE_BACKOFF_SECONDS}).",
    )
    loop_parser.add_argument(
        "--max-runs",
        type=int,
        default=0,
        help="Stop after N worker launches. 0 means no explicit limit.",
    )
    loop_parser.add_argument(
        "--stop-on-blocker",
        action="store_true",
        help="Stop when the worker reports a non-empty Exact blocker field.",
    )

    status_parser = subparsers.add_parser("status", help="Print the current supervisor state.")
    add_shared_flags(status_parser)
    status_parser.add_argument(
        "--json",
        action="store_true",
        help="Render status as JSON.",
    )

    eta_parser = subparsers.add_parser("eta", help="Estimate completion ETA from live design state and recent history.")
    add_shared_flags(eta_parser)
    eta_parser.add_argument(
        "--json",
        action="store_true",
        help="Render ETA payload as JSON.",
    )

    trace_parser = subparsers.add_parser("trace", help="Render recent supervisor loop history.")
    add_shared_flags(trace_parser)
    trace_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of recent runs to render. 0 means all recorded runs.",
    )
    trace_parser.add_argument(
        "--json",
        action="store_true",
        help="Render trace payload as JSON.",
    )

    derive_parser = subparsers.add_parser("derive", help="Print the next-worker prompt without launching it.")
    add_shared_flags(derive_parser)
    return parser.parse_args()


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _iso(value: dt.datetime) -> str:
    current = value.astimezone(dt.timezone.utc).replace(microsecond=0)
    return current.isoformat().replace("+00:00", "Z")


def _iso_now() -> str:
    return _iso(_utc_now())


def _slug_timestamp(value: Optional[dt.datetime] = None) -> str:
    current = value or _utc_now()
    return current.strftime("%Y%m%dT%H%M%SZ")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="ignore")


def _read_yaml(path: Path) -> Dict[str, Any]:
    payload = yaml.safe_load(_read_text(path))
    return dict(payload or {})


def _read_json_file(path: Path) -> Dict[str, Any]:
    payload = json.loads(_read_text(path))
    return dict(payload or {})


def _parse_iso(value: str) -> Optional[dt.datetime]:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _normalize_blocker(value: str) -> str:
    return " ".join(str(value or "").split()).strip()


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _load_sibling_module(module_name: str) -> Any:
    cached = _SIBLING_MODULE_CACHE.get(module_name)
    if cached is not None:
        return cached
    scripts_root = str(Path(__file__).resolve().parent)
    if scripts_root not in sys.path:
        sys.path.insert(0, scripts_root)
    module = importlib.import_module(module_name)
    _SIBLING_MODULE_CACHE[module_name] = module
    return module


def _load_readiness_module() -> Any:
    cached = _SIBLING_MODULE_CACHE.get("admin.readiness")
    if cached is not None:
        return cached
    fleet_root = str(Path(__file__).resolve().parents[1])
    if fleet_root not in sys.path:
        sys.path.insert(0, fleet_root)
    module = importlib.import_module("admin.readiness")
    _SIBLING_MODULE_CACHE["admin.readiness"] = module
    return module


def _milestone_status_rank(status: str) -> int:
    normalized = str(status or "").strip().lower()
    if normalized == "in_progress":
        return 0
    if normalized == "not_started":
        return 1
    if normalized in {"open", "planned", "queued"}:
        return 2
    if normalized in DONE_STATUSES:
        return 9
    return 5


def _parse_frontier_ids_from_handoff(text: str) -> List[int]:
    source_lines = str(text or "").splitlines()
    preferred_lines = [
        raw
        for raw in source_lines[:40]
        if "milestone" in raw.lower() and "remain active" in raw.lower()
    ]
    rows: List[int] = []
    for raw in (preferred_lines or source_lines[:20]):
        if "milestone" not in raw.lower():
            continue
        matches = re.findall(r"`(\d{1,2})`", raw)
        if not matches:
            matches = re.findall(r"(?<![A-Za-z])(\d{1,2})(?![A-Za-z])", raw)
        for match in matches:
            value = int(match)
            if 1 <= value <= 99 and value not in rows:
                rows.append(value)
    return rows


def _load_open_milestones(registry_path: Path) -> tuple[List[Milestone], Dict[str, int]]:
    payload = _read_yaml(registry_path)
    wave_order = {
        str(row.get("id") or "").strip(): index
        for index, row in enumerate(payload.get("waves") or [])
        if isinstance(row, dict) and str(row.get("id") or "").strip()
    }
    milestones: List[Milestone] = []
    for row in payload.get("milestones") or []:
        if not isinstance(row, dict):
            continue
        status = str(row.get("status") or "").strip().lower()
        if status in DONE_STATUSES:
            continue
        if status not in ACTIVE_STATUSES:
            continue
        milestone_id = int(row.get("id") or 0)
        if milestone_id <= 0:
            continue
        milestones.append(
            Milestone(
                id=milestone_id,
                title=str(row.get("title") or "").strip(),
                wave=str(row.get("wave") or "").strip(),
                status=status,
                owners=[str(owner).strip() for owner in (row.get("owners") or []) if str(owner).strip()],
                exit_criteria=[str(item).strip() for item in (row.get("exit_criteria") or []) if str(item).strip()],
                dependencies=[int(item) for item in (row.get("dependencies") or []) if int(item)],
            )
        )
    milestones.sort(key=lambda item: (_milestone_status_rank(item.status), wave_order.get(item.wave, 999), item.id))
    return milestones, wave_order


def _select_frontier(open_milestones: List[Milestone], handoff_text: str) -> tuple[List[Milestone], List[int]]:
    handoff_ids = _parse_frontier_ids_from_handoff(handoff_text)
    frontier: List[Milestone] = [item for item in open_milestones if item.id in handoff_ids]
    if not frontier:
        frontier = [item for item in open_milestones if item.status == "in_progress"]
    if not frontier:
        frontier = list(open_milestones[: min(5, len(open_milestones))])
    frontier_ids = [item.id for item in frontier]
    return frontier, frontier_ids


def _milestone_brief(item: Milestone) -> str:
    owners = ", ".join(item.owners) if item.owners else "unassigned"
    deps = ", ".join(str(dep) for dep in item.dependencies) if item.dependencies else "none"
    exits = "; ".join(item.exit_criteria) if item.exit_criteria else "no explicit exit criteria recorded"
    return f"{item.id} [{item.wave}] {item.title} (status: {item.status}; owners: {owners}; deps: {deps}; exit: {exits})"


def _scope_roots(args: argparse.Namespace) -> List[Path]:
    roots: List[Path] = []
    seen: set[str] = set()
    for raw in [str(item) for item in DEFAULT_SCOPE_ROOTS] + list(args.scope_root or []):
        path = Path(raw).resolve()
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        roots.append(path)
    return roots


def _text_list(values: Sequence[Any]) -> List[str]:
    rows: List[str] = []
    seen: set[str] = set()
    for value in values or []:
        text = str(value or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        rows.append(text)
    return rows


def _configured_focus_profiles(args: argparse.Namespace) -> List[str]:
    requested = _text_list(args.focus_profile or [])
    return [item for item in requested if item in FOCUS_PROFILES]


def _configured_focus_owners(args: argparse.Namespace) -> List[str]:
    owners: List[str] = []
    for profile in _configured_focus_profiles(args):
        owners.extend(FOCUS_PROFILES.get(profile, {}).get("owners") or [])
    owners.extend(args.focus_owner or [])
    return _text_list(owners)


def _configured_focus_texts(args: argparse.Namespace) -> List[str]:
    texts: List[str] = []
    for profile in _configured_focus_profiles(args):
        texts.extend(FOCUS_PROFILES.get(profile, {}).get("texts") or [])
    texts.extend(args.focus_text or [])
    return _text_list(texts)


def _milestone_matches_focus(item: Milestone, focus_owners: Sequence[str], focus_texts: Sequence[str]) -> bool:
    normalized_focus_owners = {str(value).strip().lower() for value in focus_owners if str(value).strip()}
    normalized_focus_texts = [str(value).strip().lower() for value in focus_texts if str(value).strip()]
    owner_match = not normalized_focus_owners or any(owner.lower() in normalized_focus_owners for owner in item.owners)
    if not owner_match:
        return False
    if not normalized_focus_texts:
        return True
    haystack = " ".join([item.title, item.wave, item.status, *item.exit_criteria]).lower()
    return any(term in haystack for term in normalized_focus_texts)


def _focused_frontier(args: argparse.Namespace, open_milestones: List[Milestone], frontier: List[Milestone]) -> List[Milestone]:
    focus_profiles = _configured_focus_profiles(args)
    focus_owners = _configured_focus_owners(args)
    focus_texts = _configured_focus_texts(args)
    if not focus_profiles and not focus_owners and not focus_texts:
        return frontier
    if focus_profiles:
        preferred = [item for item in open_milestones if _milestone_matches_focus(item, focus_owners, focus_texts)]
        return preferred[: min(5, len(preferred))] or frontier
    preferred = [item for item in frontier if _milestone_matches_focus(item, focus_owners, focus_texts)]
    if preferred:
        return preferred
    preferred = [item for item in open_milestones if _milestone_matches_focus(item, focus_owners, focus_texts)]
    return preferred[: min(5, len(preferred))] or frontier


def _all_registry_milestones(registry_path: Path) -> Dict[int, Milestone]:
    payload = _read_yaml(registry_path)
    rows: Dict[int, Milestone] = {}
    for row in payload.get("milestones") or []:
        if not isinstance(row, dict):
            continue
        milestone_id = int(row.get("id") or 0)
        if milestone_id <= 0:
            continue
        rows[milestone_id] = Milestone(
            id=milestone_id,
            title=str(row.get("title") or "").strip(),
            wave=str(row.get("wave") or "").strip(),
            status=str(row.get("status") or "").strip().lower(),
            owners=[str(owner).strip() for owner in (row.get("owners") or []) if str(owner).strip()],
            exit_criteria=[str(item).strip() for item in (row.get("exit_criteria") or []) if str(item).strip()],
            dependencies=[int(item) for item in (row.get("dependencies") or []) if int(item)],
        )
    return rows


def _append_unique_ids(target: List[int], values: Iterable[Any], *, limit: int = 5) -> List[int]:
    for raw in values:
        value = int(raw or 0)
        if value <= 0 or value in target:
            continue
        target.append(value)
        if len(target) >= limit:
            break
    return target


def _completion_review_target_ids(history: Sequence[Dict[str, Any]], *, limit: int = 5) -> List[int]:
    targets: List[int] = []
    for run in reversed(history):
        accepted, _ = _run_receipt_status(run)
        if accepted or int(run.get("worker_exit_code") or 0) != 0:
            continue
        _append_unique_ids(targets, run.get("frontier_ids") or [], limit=limit)
        _append_unique_ids(targets, [run.get("primary_milestone_id")], limit=limit)
        if len(targets) >= limit:
            return targets
    for run in reversed(history):
        accepted, _ = _run_receipt_status(run)
        if not accepted:
            continue
        _append_unique_ids(targets, run.get("frontier_ids") or [], limit=limit)
        _append_unique_ids(targets, [run.get("primary_milestone_id")], limit=limit)
        if targets:
            return targets
    return targets


def _append_completion_review_milestone(frontier: List[Milestone], item: Milestone, *, limit: int = 5) -> None:
    if item.id in {row.id for row in frontier}:
        return
    frontier.append(item)
    del frontier[limit:]


def _completion_review_frontier(audit: Dict[str, Any], registry_path: Path, history: Sequence[Dict[str, Any]]) -> List[Milestone]:
    milestone_map = _all_registry_milestones(registry_path)
    frontier: List[Milestone] = []
    backlog_audit = dict(audit.get("repo_backlog_audit") or {})
    if backlog_audit.get("status") == "fail":
        for row in backlog_audit.get("open_items") or []:
            if not isinstance(row, dict):
                continue
            task = str(row.get("task") or "").strip()
            repo_slug = str(row.get("repo_slug") or row.get("project_id") or "").strip()
            project_id = str(row.get("project_id") or repo_slug or "unknown").strip()
            exit_criteria = [
                f"Close or materially implement the active repo-local backlog item: {task or 'unnamed queue item'}.",
                "Refresh queue/workpackage truth so completion no longer depends on stale or unresolved repo-local backlog evidence.",
            ]
            source_path = str(row.get("queue_source_path") or "").strip()
            if source_path:
                exit_criteria.append(f"Current backlog source: {source_path}.")
            _append_completion_review_milestone(
                frontier,
                _synthetic_completion_review_milestone(
                    key=f"repo-backlog:{project_id}:{task}",
                    title=f"Repo backlog: {project_id}: {task or 'unnamed queue item'}",
                    owners=[repo_slug] if repo_slug else ([project_id] if project_id else []),
                    exit_criteria=exit_criteria,
                ),
            )
            if len(frontier) >= 5:
                return frontier
    journey_audit = dict(audit.get("journey_gate_audit") or {})
    for collection_name in ("blocked_journeys", "warning_journeys"):
        for row in journey_audit.get(collection_name) or []:
            if not isinstance(row, dict):
                continue
            reasons = [
                str(item).strip()
                for item in ((row.get("blocking_reasons") or []) + (row.get("warning_reasons") or []))
                if str(item).strip()
            ]
            _append_completion_review_milestone(
                frontier,
                _synthetic_completion_review_milestone(
                    key=f"journey:{row.get('id') or row.get('title') or 'unknown'}",
                    title=f"Completion gate: {row.get('title') or row.get('id') or 'golden journey'}",
                    owners=[str(item).strip() for item in (row.get("owner_repos") or []) if str(item).strip()],
                    exit_criteria=reasons
                    or [
                        "Restore boring release proof for this golden journey and reopen any false-complete canon claims if evidence is missing."
                    ],
                ),
            )
            if len(frontier) >= 5:
                return frontier
    linux_gate_audit = dict(audit.get("linux_desktop_exit_gate_audit") or {})
    if linux_gate_audit.get("status") == "fail":
        linux_reasons = [str(linux_gate_audit.get("reason") or "").strip()]
        _append_completion_review_milestone(
            frontier,
            _synthetic_completion_review_milestone(
                key="linux_desktop_exit_gate",
                title="Completion gate: Linux desktop exit gate",
                owners=["chummer6-ui", "fleet"],
                exit_criteria=linux_reasons
                + [
                    "Build the Linux desktop binary, package the primary .deb plus fallback archive, run startup smoke on both packaged outputs, run desktop runtime unit tests, and refresh UI_LINUX_DESKTOP_EXIT_GATE.generated.json.",
                ],
            ),
        )
        if len(frontier) >= 5:
            return frontier
    weekly_pulse_audit = dict(audit.get("weekly_pulse_audit") or {})
    if weekly_pulse_audit.get("status") == "fail":
        pulse_reasons = [str(weekly_pulse_audit.get("reason") or "").strip()]
        _append_completion_review_milestone(
            frontier,
            _synthetic_completion_review_milestone(
                key="weekly_product_pulse",
                title="Completion gate: weekly product pulse",
                owners=["chummer6-design", "fleet"],
                exit_criteria=pulse_reasons
                + [
                    "Refresh whole-product pulse evidence so journey health, drift counts, and blocker posture are trustworthy."
                ],
            ),
        )
        if len(frontier) >= 5:
            return frontier
    for milestone_id in _completion_review_target_ids(history):
        _append_completion_review_milestone(
            frontier,
            milestone_map.get(
                milestone_id,
                Milestone(
                    id=milestone_id,
                    title=f"Completion review target {milestone_id}",
                    wave="review",
                    status="review_required",
                    owners=[],
                    exit_criteria=["Audit whether this milestone is actually complete and reopen it if evidence is missing."],
                    dependencies=[],
                ),
            ),
        )
    return frontier


def _completion_review_run_lines(history: Sequence[Dict[str, Any]], *, limit: int = 5) -> List[str]:
    rows: List[str] = []
    for run in reversed(history):
        accepted, reason = _run_receipt_status(run)
        if accepted or int(run.get("worker_exit_code") or 0) != 0:
            continue
        frontier_ids = ", ".join(str(value) for value in (run.get("frontier_ids") or [])) or "none"
        primary = run.get("primary_milestone_id") or "none"
        rows.append(
            f"- run {run.get('run_id') or 'unknown'} primary={primary} frontier={frontier_ids} "
            f"reason={reason or 'untrusted receipt'}"
        )
        if len(rows) >= limit:
            break
    return rows


def _latest_trusted_receipt_line(history: Sequence[Dict[str, Any]]) -> str:
    for run in reversed(history):
        accepted, _ = _run_receipt_status(run)
        if not accepted:
            continue
        frontier_ids = ", ".join(str(value) for value in (run.get("frontier_ids") or [])) or "none"
        primary = run.get("primary_milestone_id") or "none"
        shipped = _summarize_trace_value(run.get("shipped"), max_len=120)
        remains = _summarize_trace_value(run.get("remains"), max_len=120)
        return (
            f"- run {run.get('run_id') or 'unknown'} primary={primary} frontier={frontier_ids} "
            f"shipped={shipped} remains={remains}"
        )
    return "- none"


def _synthetic_completion_review_id(key: str) -> int:
    digest = hashlib.sha1(str(key).encode("utf-8")).hexdigest()
    return SYNTHETIC_COMPLETION_REVIEW_ID_BASE + int(digest[:8], 16)


def _synthetic_completion_review_milestone(
    *,
    key: str,
    title: str,
    owners: Sequence[str],
    exit_criteria: Sequence[str],
) -> Milestone:
    criteria = [str(item).strip() for item in exit_criteria if str(item).strip()]
    if not criteria:
        criteria = ["Audit and repair the missing completion evidence for this release-proof seam."]
    return Milestone(
        id=_synthetic_completion_review_id(key),
        title=title,
        wave="completion_review",
        status="review_required",
        owners=[str(item).strip() for item in owners if str(item).strip()],
        exit_criteria=criteria[:4],
        dependencies=[],
    )


def _completion_review_journey_lines(audit: Dict[str, Any], *, limit: int = 4) -> List[str]:
    rows: List[str] = []
    for collection_name in ("blocked_journeys", "warning_journeys"):
        for row in audit.get(collection_name) or []:
            if not isinstance(row, dict):
                continue
            reasons = [
                str(item).strip()
                for item in ((row.get("blocking_reasons") or []) + (row.get("warning_reasons") or []))
                if str(item).strip()
            ]
            owner_text = ", ".join(str(item).strip() for item in (row.get("owner_repos") or []) if str(item).strip()) or "none"
            rows.append(
                f"- journey {row.get('id') or 'unknown'} state={row.get('state') or 'unknown'} "
                f"owners={owner_text} reason={_summarize_trace_value(reasons[0] if reasons else row.get('title') or 'missing proof', max_len=160)}"
            )
            if len(rows) >= limit:
                return rows
    return rows


def _completion_review_weekly_pulse_lines(audit: Dict[str, Any]) -> List[str]:
    if not isinstance(audit, dict) or not audit:
        return ["- none"]
    return [
        f"- pulse_path={audit.get('path') or 'unknown'}",
        f"- generated_at={audit.get('generated_at') or 'unknown'} as_of={audit.get('as_of') or 'unknown'}",
        (
            f"- release_health={audit.get('release_health_state') or 'unknown'} "
            f"journey_gate_health={audit.get('journey_gate_health_state') or 'unknown'} "
            f"design_drift_count={audit.get('design_drift_count') or 0} "
            f"public_promise_drift_count={audit.get('public_promise_drift_count') or 0} "
            f"oldest_blocker_days={audit.get('oldest_blocker_days') or 0}"
        ),
    ]


def _completion_review_repo_backlog_lines(audit: Dict[str, Any], *, limit: int = 5) -> List[str]:
    if not isinstance(audit, dict) or audit.get("status") != "fail":
        return ["- none"]
    rows: List[str] = []
    for row in audit.get("open_items") or []:
        if not isinstance(row, dict):
            continue
        rows.append(
            f"- project={row.get('project_id') or 'unknown'} repo={row.get('repo_slug') or 'unknown'} "
            f"task={_summarize_trace_value(row.get('task') or 'unnamed queue item', max_len=160)}"
        )
        if len(rows) >= limit:
            break
    return rows or ["- none"]


def _completion_review_linux_exit_gate_lines(audit: Dict[str, Any]) -> List[str]:
    if not isinstance(audit, dict) or not audit:
        return ["- none"]
    return [
        f"- proof_path={audit.get('path') or 'unknown'}",
        (
            f"- generated_at={audit.get('generated_at') or 'unknown'} "
            f"age_seconds={audit.get('age_seconds') or 0} "
            f"proof_status={audit.get('proof_status') or 'unknown'} "
            f"stage={audit.get('stage') or 'unknown'}"
        ),
        (
            f"- head={audit.get('head_id') or 'unknown'} "
            f"launch_target={audit.get('launch_target') or 'unknown'} "
            f"rid={audit.get('rid') or 'unknown'} "
            f"snapshot_mode={audit.get('source_snapshot_mode') or 'unknown'} "
            f"install_mode={audit.get('primary_install_mode') or 'unknown'} "
            f"install_verification={audit.get('primary_install_verification_status') or 'unknown'} "
            f"primary_smoke={audit.get('primary_smoke_status') or 'unknown'} "
            f"fallback_smoke={audit.get('fallback_smoke_status') or 'unknown'} "
            f"unit_tests={audit.get('unit_test_status') or 'unknown'} "
            f"totals={audit.get('test_total') or 0}/{audit.get('test_passed') or 0}/{audit.get('test_failed') or 0}/{audit.get('test_skipped') or 0}"
        ),
        (
            f"- install_verification_path={audit.get('primary_install_verification_path') or 'unknown'} "
            f"snapshot_entries={audit.get('source_snapshot_entry_count') or 0} "
            f"snapshot_finish_entries={audit.get('source_snapshot_finish_entry_count') or 0} "
            f"snapshot_sha={audit.get('source_snapshot_worktree_sha256') or 'missing'} "
            f"snapshot_finish_sha={audit.get('source_snapshot_finish_worktree_sha256') or 'missing'} "
            f"snapshot_stable={audit.get('source_snapshot_identity_stable') or False} "
            f"wrapper_sha={audit.get('primary_install_wrapper_sha256') or 'missing'} "
            f"desktop_sha={audit.get('primary_install_desktop_entry_sha256') or 'missing'}"
        ),
        (
            f"- proof_git={audit.get('proof_git_head') or 'unknown'} "
            f"current_git={audit.get('current_git_head') or 'unknown'}"
        ),
        f"- reason={_summarize_trace_value(audit.get('reason') or 'unknown', max_len=160)}",
    ]


def _completion_review_frontier_paths(workspace_root: Path) -> tuple[Path, Path]:
    workspace = Path(workspace_root).resolve()
    return (
        workspace / ".codex-studio" / "published" / "COMPLETION_REVIEW_FRONTIER.generated.yaml",
        workspace / ".codex-design" / "product" / "COMPLETION_REVIEW_FRONTIER.generated.yaml",
    )


def _write_yaml(path: Path, payload: Dict[str, Any]) -> None:
    _ensure_dir(path.parent)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _completion_review_frontier_payload(
    *,
    args: argparse.Namespace,
    state_root: Path,
    mode: str,
    frontier: Sequence[Milestone],
    focus_profiles: Sequence[str],
    focus_owners: Sequence[str],
    focus_texts: Sequence[str],
    completion_audit: Dict[str, Any],
    eta: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    repo_backlog_audit = dict(completion_audit.get("repo_backlog_audit") or {})
    receipt_audit = dict(completion_audit.get("receipt_audit") or {})
    journey_gate_audit = dict(completion_audit.get("journey_gate_audit") or {})
    linux_gate_audit = dict(completion_audit.get("linux_desktop_exit_gate_audit") or {})
    weekly_pulse_audit = dict(completion_audit.get("weekly_pulse_audit") or {})
    open_items = [dict(row) for row in (repo_backlog_audit.get("open_items") or []) if isinstance(row, dict)]
    frontier_rows = [
        {
            "id": item.id,
            "title": item.title,
            "wave": item.wave,
            "status": item.status,
            "owners": list(item.owners),
            "dependencies": list(item.dependencies),
            "exit_criteria": list(item.exit_criteria),
        }
        for item in frontier
    ]
    payload: Dict[str, Any] = {
        "contract_name": "fleet.completion_review_frontier",
        "schema_version": 1,
        "generated_at": _iso_now(),
        "mode": mode,
        "state_root": str(state_root),
        "source_registry_path": str(Path(args.registry_path).resolve()),
        "handoff_path": str(Path(args.handoff_path).resolve()),
        "projects_dir": str(Path(args.projects_dir).resolve()),
        "primary_probe_shard": _primary_probe_shard_name(state_root),
        "focus": {
            "profiles": list(focus_profiles),
            "owners": list(focus_owners),
            "texts": list(focus_texts),
        },
        "completion_audit": {
            "status": str(completion_audit.get("status") or "").strip(),
            "reason": str(completion_audit.get("reason") or "").strip(),
        },
        "receipt_audit": {
            "status": str(receipt_audit.get("status") or "").strip(),
            "reason": str(receipt_audit.get("reason") or "").strip(),
            "latest_run_id": str(receipt_audit.get("latest_run_id") or "").strip(),
            "latest_run_reason": str(receipt_audit.get("latest_run_reason") or "").strip(),
        },
        "journey_gate_audit": {
            "status": str(journey_gate_audit.get("status") or "").strip(),
            "reason": str(journey_gate_audit.get("reason") or "").strip(),
            "blocked_journey_count": len(journey_gate_audit.get("blocked_journeys") or []),
            "warning_journey_count": len(journey_gate_audit.get("warning_journeys") or []),
        },
        "linux_desktop_exit_gate_audit": {
            "status": str(linux_gate_audit.get("status") or "").strip(),
            "reason": str(linux_gate_audit.get("reason") or "").strip(),
            "path": str(linux_gate_audit.get("path") or "").strip(),
            "generated_at": str(linux_gate_audit.get("generated_at") or "").strip(),
        },
        "weekly_pulse_audit": {
            "status": str(weekly_pulse_audit.get("status") or "").strip(),
            "reason": str(weekly_pulse_audit.get("reason") or "").strip(),
            "path": str(weekly_pulse_audit.get("path") or "").strip(),
            "generated_at": str(weekly_pulse_audit.get("generated_at") or "").strip(),
        },
        "repo_backlog_audit": {
            "status": str(repo_backlog_audit.get("status") or "").strip(),
            "reason": str(repo_backlog_audit.get("reason") or "").strip(),
            "open_item_count": int(repo_backlog_audit.get("open_item_count") or 0),
            "open_project_count": int(repo_backlog_audit.get("open_project_count") or 0),
            "open_items": open_items,
        },
        "frontier_count": len(frontier_rows),
        "frontier_ids": [item["id"] for item in frontier_rows],
        "frontier": frontier_rows,
    }
    if eta:
        payload["eta"] = {
            "status": str(eta.get("status") or "").strip(),
            "eta_human": str(eta.get("eta_human") or "").strip(),
            "eta_confidence": str(eta.get("eta_confidence") or "").strip(),
            "basis": str(eta.get("basis") or "").strip(),
            "blocking_reason": str(eta.get("blocking_reason") or "").strip(),
            "summary": str(eta.get("summary") or "").strip(),
        }
    return payload


def _materialize_completion_review_frontier(
    *,
    args: argparse.Namespace,
    state_root: Path,
    mode: str,
    frontier: Sequence[Milestone],
    focus_profiles: Sequence[str],
    focus_owners: Sequence[str],
    focus_texts: Sequence[str],
    completion_audit: Dict[str, Any],
    eta: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    published_path, mirror_path = _completion_review_frontier_paths(Path(args.workspace_root).resolve())
    payload = _completion_review_frontier_payload(
        args=args,
        state_root=state_root,
        mode=mode,
        frontier=frontier,
        focus_profiles=focus_profiles,
        focus_owners=focus_owners,
        focus_texts=focus_texts,
        completion_audit=completion_audit,
        eta=eta,
    )
    _write_yaml(published_path, payload)
    _write_yaml(mirror_path, payload)
    return {
        "published_path": str(published_path),
        "mirror_path": str(mirror_path),
    }


def build_worker_prompt(
    *,
    registry_path: Path,
    program_milestones_path: Path,
    roadmap_path: Path,
    handoff_path: Path,
    open_milestones: List[Milestone],
    frontier: List[Milestone],
    scope_roots: List[Path],
    focus_profiles: Sequence[str],
    focus_owners: Sequence[str],
    focus_texts: Sequence[str],
) -> str:
    frontier_text = "\n".join(f"- {_milestone_brief(item)}" for item in frontier) or "- none"
    open_text = "\n".join(f"- {_milestone_brief(item)}" for item in open_milestones[:15]) or "- none"
    scope_text = "\n".join(f"- {path}" for path in scope_roots)
    open_ids = ", ".join(str(item.id) for item in open_milestones) or "none"
    frontier_ids = ", ".join(str(item.id) for item in frontier) or "none"
    focus_lines = []
    if focus_profiles:
        focus_lines.append(f"- profile focus: {', '.join(focus_profiles)}")
    if focus_owners:
        focus_lines.append(f"- owner focus: {', '.join(focus_owners)}")
    if focus_texts:
        focus_lines.append(f"- text focus: {', '.join(focus_texts)}")
    focus_text = "\n".join(focus_lines) if focus_lines else "- none"
    return (
        "Continue autonomously across all Chummer6 repos in this workspace until the product is fully finished for public release exactly as defined by "
        "/docker/chummercomplete/chummer-design. Treat the design canon, milestone files, roadmap, public guides, generated artifacts, failing tests, and live repo evidence as the sole definition of done.\n\n"
        "Do not stop for progress reports, summaries, plans, clean repos, clean worktrees, completed waves, completed slices, or lack of pre-existing local diffs. "
        "When one slice lands, immediately re-derive and execute the next highest-impact unfinished work. Audit, implement, wire, regenerate, verify, test, commit, push, and refresh /docker/fleet/NEXT_SESSION_HANDOFF.md in small safe increments. "
        "Include adjacent cleanup, generated outputs, docs, mirrors, and necessary concurrent local changes to keep the whole system green.\n\n"
        "Treat concurrent work by other developers as normal. Work around it, include necessary local changes when they are understood and safe, and never revert unrelated edits.\n\n"
        "Start by reading these files directly:\n"
        f"- {registry_path}\n"
        f"- {program_milestones_path}\n"
        f"- {roadmap_path}\n"
        f"- {handoff_path}\n\n"
        f"Writable scope roots:\n{scope_text}\n\n"
        f"Current steering focus:\n{focus_text}\n\n"
        f"Current active frontier from design plus handoff:\n{frontier_text}\n\n"
        f"Current open milestone ids: {open_ids}\n"
        f"Frontier milestone ids to prioritize first: {frontier_ids}\n\n"
        f"Select the next highest-impact unfinished slice yourself from that frontier, land it end to end, and if meaningful adjacent work remains within the same momentum window, continue before stopping. "
        "Only stop if there is no meaningful repo-local work left that advances full design materialization, a hard external blocker exists, or the platform/session actually terminates.\n\n"
        "If you stop, report only:\n"
        "What shipped: ...\n"
        "What remains: ...\n"
        "Exact blocker: ...\n"
    )


def build_completion_review_prompt(
    *,
    registry_path: Path,
    program_milestones_path: Path,
    roadmap_path: Path,
    handoff_path: Path,
    frontier_artifact_path: Path,
    frontier: List[Milestone],
    scope_roots: List[Path],
    focus_profiles: Sequence[str],
    focus_owners: Sequence[str],
    focus_texts: Sequence[str],
    audit: Dict[str, Any],
    history: Sequence[Dict[str, Any]],
) -> str:
    scope_text = "\n".join(f"- {path}" for path in scope_roots)
    frontier_text = "\n".join(f"- {_milestone_brief(item)}" for item in frontier) or "- none"
    frontier_ids = ", ".join(str(item.id) for item in frontier) or "none"
    suspicious_runs = "\n".join(_completion_review_run_lines(history)) or "- none"
    latest_trusted = _latest_trusted_receipt_line(history)
    journey_audit = dict(audit.get("journey_gate_audit") or {})
    linux_desktop_exit_gate_audit = dict(audit.get("linux_desktop_exit_gate_audit") or {})
    weekly_pulse_audit = dict(audit.get("weekly_pulse_audit") or {})
    repo_backlog_audit = dict(audit.get("repo_backlog_audit") or {})
    journey_lines = "\n".join(_completion_review_journey_lines(journey_audit)) or "- none"
    linux_gate_lines = "\n".join(_completion_review_linux_exit_gate_lines(linux_desktop_exit_gate_audit)) or "- none"
    weekly_pulse_lines = "\n".join(_completion_review_weekly_pulse_lines(weekly_pulse_audit))
    repo_backlog_lines = "\n".join(_completion_review_repo_backlog_lines(repo_backlog_audit))
    focus_lines = []
    if focus_profiles:
        focus_lines.append(f"- profile focus: {', '.join(focus_profiles)}")
    if focus_owners:
        focus_lines.append(f"- owner focus: {', '.join(focus_owners)}")
    if focus_texts:
        focus_lines.append(f"- text focus: {', '.join(focus_texts)}")
    focus_text = "\n".join(focus_lines) if focus_lines else "- none"
    return (
        "Run a false-complete recovery pass for the Chummer design supervisor.\n\n"
        "The active design registry currently shows no open milestones, but the supervisor completion audit failed. "
        "Treat this as proof that the loop reached an untrusted completion conclusion and must now repair itself.\n\n"
        f"Completion audit failure:\n- status: {audit.get('status') or 'unknown'}\n- reason: {audit.get('reason') or 'unknown'}\n\n"
        "Start by reading these files directly:\n"
        f"- {registry_path}\n"
        f"- {program_milestones_path}\n"
        f"- {roadmap_path}\n"
        f"- {handoff_path}\n\n"
        "Active synthetic completion-review frontier artifact:\n"
        f"- {frontier_artifact_path}\n\n"
        f"Writable scope roots:\n{scope_text}\n\n"
        f"Current steering focus:\n{focus_text}\n\n"
        f"Suspicious zero-exit receipts to audit first:\n{suspicious_runs}\n\n"
        f"Most recent trusted receipt:\n{latest_trusted}\n\n"
        f"Golden journey release-proof gaps:\n{journey_lines}\n\n"
        f"Linux desktop exit-gate gaps:\n{linux_gate_lines}\n\n"
        f"Weekly product pulse gaps:\n{weekly_pulse_lines}\n\n"
        f"Repo-local backlog gaps that still need canon-backed milestones:\n{repo_backlog_lines}\n\n"
        f"Recovery frontier ids to verify or reopen first: {frontier_ids}\n"
        f"Recovery frontier detail:\n{frontier_text}\n\n"
        "Treat the synthetic frontier artifact as the active source of truth for unfinished work while the registry stays closed.\n\n"
        "Your required order of work:\n"
        "1. Verify whether the recovery-frontier milestones, repo-local backlog items, blocked golden journeys, and weekly-pulse claims are actually complete in repo-local evidence.\n"
        "2. If backlog or proof gaps remain, land the highest-impact missing implementation, release-proof, or generated-artifact slice from that synthetic frontier before doing canon cleanup.\n"
        "3. If the work proves the design canon or handoff is falsely closed or stale, refresh them so the normal frontier becomes truthful again.\n"
        "4. Only accept completion once the trusted structured receipt and the current repo-local proof both agree that nothing meaningful remains.\n\n"
        "Do not simply restate the registry. Repair the loop's source of truth or produce the missing trusted evidence.\n\n"
        "If you stop, report only:\n"
        "What shipped: ...\n"
        "What remains: ...\n"
        "Exact blocker: ...\n"
    )


def _default_worker_command(
    *,
    worker_bin: str,
    worker_lane: str,
    workspace_root: Path,
    scope_roots: List[Path],
    run_dir: Path,
    worker_model: str,
) -> List[str]:
    command = [
        worker_bin,
    ]
    if worker_lane:
        command.append(worker_lane)
    command.extend(
        [
            "exec",
            "-C",
            str(workspace_root),
            "--skip-git-repo-check",
            "--dangerously-bypass-approvals-and-sandbox",
            "--color",
            "never",
            "-o",
            str(run_dir / "last_message.txt"),
            "-",
        ]
    )
    if worker_model:
        command[2 + (1 if worker_lane else 0) : 2 + (1 if worker_lane else 0)] = ["-m", worker_model]
    for scope_root in scope_roots:
        if scope_root == workspace_root:
            continue
        insert_at = 2 + (1 if worker_lane else 0) + (2 if worker_model else 0)
        command[insert_at:insert_at] = ["--add-dir", str(scope_root)]
    return command


def _worker_model_candidates(args: argparse.Namespace) -> List[str]:
    primary = str(args.worker_model or "").strip()
    configured_fallbacks = [str(item or "").strip() for item in (args.fallback_worker_model or []) if str(item or "").strip()]
    if configured_fallbacks:
        fallbacks = configured_fallbacks
    else:
        env_value = os.environ.get("CHUMMER_DESIGN_SUPERVISOR_FALLBACK_MODELS")
        if env_value is None:
            fallbacks = [] if str(args.worker_lane or "").strip() else list(DEFAULT_FALLBACK_MODELS)
        else:
            fallbacks = [item.strip() for item in env_value.split(",") if item.strip()]
    models: List[str] = []
    seen: set[str] = set()
    for candidate in [primary, *fallbacks]:
        key = candidate or "<default>"
        if key in seen:
            continue
        seen.add(key)
        models.append(candidate)
    return models or [primary]


def _worker_lane_candidates(args: argparse.Namespace) -> List[str]:
    primary = str(args.worker_lane or "").strip()
    if not primary:
        return [""]
    configured_fallbacks = [
        str(item or "").strip() for item in (args.fallback_worker_lane or []) if str(item or "").strip()
    ]
    if configured_fallbacks:
        fallbacks = configured_fallbacks
    else:
        env_value = os.environ.get("CHUMMER_DESIGN_SUPERVISOR_FALLBACK_LANES")
        if env_value is None:
            fallbacks = list(DEFAULT_FALLBACK_WORKER_LANES.get(primary, ()))
        else:
            fallbacks = [item.strip() for item in env_value.split(",") if item.strip()]
    lanes: List[str] = []
    seen: set[str] = set()
    for candidate in [primary, *fallbacks]:
        key = candidate or "<default>"
        if key in seen:
            continue
        seen.add(key)
        lanes.append(candidate)
    return lanes or [primary]


def _retryable_worker_error(stderr_text: str) -> bool:
    compact = " ".join(str(stderr_text or "").split()).strip().lower()
    return bool(compact) and any(signal in compact for signal in RETRYABLE_WORKER_ERROR_SIGNALS)


def _retryable_worker_rejection(reason_text: str, stderr_text: str = "") -> bool:
    return _retryable_worker_error(reason_text) or _retryable_worker_error(stderr_text)


def _parse_final_message_sections(text: str) -> Dict[str, str]:
    compact = str(text or "").replace("\r\n", "\n")
    patterns = {
        "shipped": r"(?ims)^What shipped:\s*(.*?)(?=^What remains:|^Exact blocker:|\Z)",
        "remains": r"(?ims)^What remains:\s*(.*?)(?=^Exact blocker:|\Z)",
        "blocker": r"(?ims)^Exact blocker:\s*(.*?)(?=\Z)",
    }
    parsed: Dict[str, str] = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, compact)
        parsed[key] = " ".join(match.group(1).split()).strip() if match else ""
    return parsed


def _final_message_reports_error(text: str) -> bool:
    compact = str(text or "").replace("\r\n", "\n").strip()
    if not compact:
        return False
    if re.search(r"(?im)^\s*error\s*:", compact):
        return True
    return "upstream_timeout:" in compact.lower()


def _assess_worker_result(
    worker_exit_code: int,
    final_message: str,
    parsed: Optional[Dict[str, str]] = None,
) -> tuple[bool, str]:
    if int(worker_exit_code) != 0:
        return False, f"worker exit {worker_exit_code}"
    compact = str(final_message or "").strip()
    if not compact:
        return False, "missing final message"
    if _final_message_reports_error(compact):
        return False, _summarize_trace_value(compact, max_len=96)
    sections = parsed or _parse_final_message_sections(compact)
    missing_labels: List[str] = []
    labels = {
        "shipped": "What shipped",
        "remains": "What remains",
        "blocker": "Exact blocker",
    }
    for key, label in labels.items():
        if not sections.get(key):
            missing_labels.append(label)
    if missing_labels:
        return False, f"missing structured closeout fields: {', '.join(missing_labels)}"
    return True, ""


def _state_payload_path(state_root: Path) -> Path:
    return state_root / "state.json"


def _history_payload_path(state_root: Path) -> Path:
    return state_root / "history.jsonl"


def _lock_payload_path(state_root: Path) -> Path:
    return state_root / "loop.lock"


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    _ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    _ensure_dir(path.parent)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _read_state(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(_read_text(path))
    except Exception:
        return {}


def _read_history(path: Path, *, limit: int = 10) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for raw in _read_text(path).splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    if limit > 0:
        rows = rows[-limit:]
    return rows


def _state_updated_at(state: Dict[str, Any]) -> Optional[dt.datetime]:
    return _parse_iso(str(state.get("updated_at") or ""))


def _run_updated_at(run: Dict[str, Any]) -> Optional[dt.datetime]:
    return _run_finished_at(run) or _parse_iso(str(run.get("started_at") or ""))


def _shard_state_roots(state_root: Path) -> List[Path]:
    if not state_root.exists() or not state_root.is_dir():
        return []
    roots: List[Path] = []
    for candidate in sorted(state_root.iterdir()):
        if not candidate.is_dir() or not candidate.name.startswith("shard-"):
            continue
        if _state_payload_path(candidate).exists() or _history_payload_path(candidate).exists():
            roots.append(candidate)
    return roots


def _latest_nonempty_state_field(state_items: Sequence[Dict[str, Any]], field: str) -> Any:
    default_time = dt.datetime.min.replace(tzinfo=dt.timezone.utc)
    rows = sorted(
        [item for item in state_items if item.get("state")],
        key=lambda item: _state_updated_at(dict(item.get("state") or {})) or default_time,
        reverse=True,
    )
    for item in rows:
        state = dict(item.get("state") or {})
        value = state.get(field)
        if value not in (None, "", [], {}):
            return value
    return {}


def _effective_supervisor_state(
    state_root: Path,
    *,
    history_limit: int = 10,
) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    base_state = _read_state(_state_payload_path(state_root))
    base_history = _read_history(_history_payload_path(state_root), limit=history_limit)
    shard_roots = _shard_state_roots(state_root)
    if not shard_roots:
        return base_state, base_history

    state_items: List[Dict[str, Any]] = []
    combined_history: List[Dict[str, Any]] = []
    if base_state or base_history:
        state_items.append({"name": "base", "root": state_root, "state": base_state})
        for run in base_history:
            payload = dict(run)
            payload["_shard"] = "base"
            combined_history.append(payload)
    for shard_root in shard_roots:
        shard_state = _read_state(_state_payload_path(shard_root))
        shard_history = _read_history(_history_payload_path(shard_root), limit=history_limit)
        state_items.append({"name": shard_root.name, "root": shard_root, "state": shard_state})
        for run in shard_history:
            payload = dict(run)
            payload["_shard"] = shard_root.name
            combined_history.append(payload)

    default_time = dt.datetime.min.replace(tzinfo=dt.timezone.utc)
    combined_history.sort(key=lambda item: _run_updated_at(item) or default_time)
    if history_limit > 0:
        combined_history = combined_history[-history_limit:]

    populated_states = [item for item in state_items if item.get("state")]
    if not populated_states:
        return {}, combined_history
    latest_item = max(
        populated_states,
        key=lambda item: _state_updated_at(dict(item.get("state") or {})) or default_time,
    )
    latest_state = dict(latest_item.get("state") or {})
    aggregate = dict(latest_state)
    aggregate["state_root"] = str(state_root)
    aggregate["shard_count"] = len(shard_roots)
    aggregate["open_milestone_ids"] = sorted(
        {
            _coerce_int(value, value)
            for item in populated_states
            for value in (dict(item.get("state") or {}).get("open_milestone_ids") or [])
        }
    )
    aggregate["frontier_ids"] = sorted(
        {
            _coerce_int(value, value)
            for item in populated_states
            for value in (dict(item.get("state") or {}).get("frontier_ids") or [])
        }
    )
    for key in ("focus_profiles", "focus_owners", "focus_texts"):
        aggregate[key] = sorted(
            {
                str(value)
                for item in populated_states
                for value in (dict(item.get("state") or {}).get(key) or [])
                if str(value)
            }
        )
    modes = {
        str(dict(item.get("state") or {}).get("mode") or "").strip()
        for item in populated_states
        if str(dict(item.get("state") or {}).get("mode") or "").strip()
    }
    if len(modes) == 1:
        aggregate["mode"] = next(iter(modes))
    elif modes:
        aggregate["mode"] = "sharded"
    latest_run = combined_history[-1] if combined_history else dict(latest_state.get("last_run") or {})
    if latest_run:
        aggregate["last_run"] = dict(latest_run)
    completion_audit = _latest_nonempty_state_field(populated_states, "completion_audit")
    if completion_audit:
        aggregate["completion_audit"] = completion_audit
    eta = _latest_nonempty_state_field(populated_states, "eta")
    if eta:
        aggregate["eta"] = eta
    aggregate["shards"] = [
        {
            "name": str(item["name"]),
            "state_root": str(item["root"]),
            "updated_at": dict(item.get("state") or {}).get("updated_at") or "",
            "mode": dict(item.get("state") or {}).get("mode") or "",
            "frontier_ids": list(dict(item.get("state") or {}).get("frontier_ids") or []),
            "open_milestone_ids": list(dict(item.get("state") or {}).get("open_milestone_ids") or []),
            "eta_status": str((dict(item.get("state") or {}).get("eta") or {}).get("status") or "").strip(),
            "last_run_id": str((dict(item.get("state") or {}).get("last_run") or {}).get("run_id") or "").strip(),
        }
        for item in populated_states
        if str(item["name"]) != "base"
    ]
    return aggregate, combined_history


def _aggregate_state_root(state_root: Path) -> Path:
    if state_root.name.startswith("shard-") and state_root.parent.exists():
        return state_root.parent
    return state_root


def _completion_review_history(state_root: Path, *, limit: int) -> List[Dict[str, Any]]:
    aggregate_root = _aggregate_state_root(state_root)
    _, history = _effective_supervisor_state(aggregate_root, history_limit=limit)
    return history


def _primary_probe_shard_name(state_root: Path) -> str:
    aggregate_root = _aggregate_state_root(state_root)
    shard_roots = _shard_state_roots(aggregate_root)
    if not shard_roots:
        return ""
    return shard_roots[0].name


def _should_defer_external_blocker_probe(
    state_root: Path,
    *,
    blocker_reason: str,
) -> bool:
    blocker = str(blocker_reason or "").strip()
    if not blocker:
        return False
    if not state_root.name.startswith("shard-") or state_root.name == "base":
        return False
    primary_shard = _primary_probe_shard_name(state_root)
    if not primary_shard:
        return False
    return state_root.name != primary_shard


def _median(values: Sequence[float]) -> float:
    rows = sorted(float(value) for value in values)
    if not rows:
        return 0.0
    middle = len(rows) // 2
    if len(rows) % 2:
        return rows[middle]
    return (rows[middle - 1] + rows[middle]) / 2.0


def _milestone_eta_bounds_hours(item: Milestone) -> tuple[float, float]:
    normalized = str(item.status or "").strip().lower()
    if normalized == "in_progress":
        return 4.0, 10.0
    if normalized == "not_started":
        return 8.0, 20.0
    if normalized in {"open", "planned", "queued"}:
        return 6.0, 16.0
    if normalized == "review_required":
        return 1.0, 4.0
    return 6.0, 16.0


def _milestone_effort_units(item: Milestone) -> float:
    low_hours, high_hours = _milestone_eta_bounds_hours(item)
    return max(0.25, (low_hours + high_hours) / 12.0)


def _run_finished_at(run: Dict[str, Any]) -> Optional[dt.datetime]:
    return _parse_iso(str(run.get("finished_at") or run.get("started_at") or ""))


def _run_duration_hours(run: Dict[str, Any]) -> float:
    started_at = _parse_iso(str(run.get("started_at") or ""))
    finished_at = _run_finished_at(run)
    if started_at is None or finished_at is None:
        return 0.0
    duration_hours = (finished_at - started_at).total_seconds() / 3600.0
    return duration_hours if duration_hours > 0 else 0.0


def _history_run_is_accepted(run: Dict[str, Any]) -> bool:
    accepted = run.get("accepted")
    if isinstance(accepted, bool):
        return accepted
    accepted, _ = _run_receipt_status(run)
    return accepted


def _eta_external_blocker_reason(history: Sequence[Dict[str, Any]], completion_audit: Optional[Dict[str, Any]] = None) -> str:
    if isinstance(completion_audit, dict) and str(completion_audit.get("status") or "").strip().lower() == "pass":
        return ""
    candidates: List[str] = []
    if history:
        latest_run = history[-1]
        candidates.extend(
            [
                str(latest_run.get("blocker") or ""),
                str(latest_run.get("acceptance_reason") or ""),
                _failure_hint_for_run(latest_run),
            ]
        )
    if isinstance(completion_audit, dict):
        candidates.append(str(completion_audit.get("reason") or ""))
        receipt_audit = completion_audit.get("receipt_audit") or {}
        if isinstance(receipt_audit, dict):
            candidates.append(str(receipt_audit.get("reason") or ""))
    for raw in candidates:
        text = _normalize_blocker(raw)
        if not text:
            continue
        normalized = text.lower()
        if any(signal in normalized for signal in ETA_EXTERNAL_BLOCKER_SIGNALS):
            return text
    return ""


def _format_eta_bound(hours: float) -> str:
    value = max(0.0, float(hours))
    if value <= 0.2:
        return "now"
    if value < 1.0:
        minutes = max(15, int(round((value * 60.0) / 15.0) * 15))
        return f"{minutes}m"
    if value < 24.0:
        rounded_hours = int(round(value))
        return f"{max(1, rounded_hours)}h"
    days = value / 24.0
    if days < 7.0:
        rounded_days = round(days, 1)
        return f"{int(rounded_days)}d" if rounded_days.is_integer() else f"{rounded_days:.1f}d"
    weeks = days / 7.0
    rounded_weeks = round(weeks, 1)
    return f"{int(rounded_weeks)}w" if rounded_weeks.is_integer() else f"{rounded_weeks:.1f}w"


def _format_eta_window(low_hours: float, high_hours: float) -> str:
    low = max(0.0, float(low_hours))
    high = max(low, float(high_hours))
    if high <= 0.2:
        return "ready now"
    if abs(high - low) <= max(0.25, high * 0.15):
        return f"~{_format_eta_bound((low + high) / 2.0)}"
    return f"{_format_eta_bound(low)}-{_format_eta_bound(high)}"


def _estimate_open_milestone_eta(
    open_milestones: Sequence[Milestone],
    history: Sequence[Dict[str, Any]],
    now: dt.datetime,
) -> Dict[str, Any]:
    current_open_count = len(open_milestones)
    in_progress_count = sum(1 for item in open_milestones if item.status == "in_progress")
    not_started_count = sum(1 for item in open_milestones if item.status == "not_started")
    heuristic_low_hours = sum(_milestone_eta_bounds_hours(item)[0] for item in open_milestones)
    heuristic_high_hours = sum(_milestone_eta_bounds_hours(item)[1] for item in open_milestones)
    effort_units = sum(_milestone_effort_units(item) for item in open_milestones)

    accepted_runs = [run for run in history if _history_run_is_accepted(run)]
    accepted_snapshots: List[tuple[dt.datetime, int]] = []
    for run in accepted_runs:
        finished_at = _run_finished_at(run)
        if finished_at is None:
            continue
        accepted_snapshots.append((finished_at, len(run.get("open_milestone_ids") or [])))
    accepted_snapshots.sort(key=lambda item: item[0])

    velocity_samples: List[float] = []
    if accepted_snapshots:
        snapshots = accepted_snapshots + [(now, current_open_count)]
        for previous, current in zip(snapshots, snapshots[1:]):
            elapsed_hours = (current[0] - previous[0]).total_seconds() / 3600.0
            delta = previous[1] - current[1]
            if elapsed_hours <= 0.0 or delta <= 0:
                continue
            velocity_samples.append(delta / elapsed_hours)
    if velocity_samples:
        burn_rate_per_hour = _median(velocity_samples)
        midpoint_hours = current_open_count / max(0.05, burn_rate_per_hour)
        low_hours = max(0.5, midpoint_hours * 0.75)
        high_hours = max(low_hours + 0.5, midpoint_hours * 1.5)
        confidence = ETA_STATUS_HIGH_CONFIDENCE if len(velocity_samples) >= 3 else ETA_STATUS_MEDIUM_CONFIDENCE
        observed_per_day = burn_rate_per_hour * 24.0
        return {
            "status": "estimated",
            "eta_human": _format_eta_window(low_hours, high_hours),
            "eta_confidence": confidence,
            "basis": "empirical_open_milestone_burn",
            "summary": (
                f"{current_open_count} open milestones remain ({in_progress_count} in progress, "
                f"{not_started_count} not started); observed burn is about {observed_per_day:.1f} milestones/day."
            ),
            "predicted_completion_at": _iso(now + dt.timedelta(hours=(low_hours + high_hours) / 2.0)),
            "range_low_hours": round(low_hours, 2),
            "range_high_hours": round(high_hours, 2),
            "remaining_open_milestones": current_open_count,
            "remaining_in_progress_milestones": in_progress_count,
            "remaining_not_started_milestones": not_started_count,
            "remaining_effort_units": round(effort_units, 2),
            "history_sample_count": len(velocity_samples),
            "observed_burn_milestones_per_day": round(observed_per_day, 2),
            "blocking_reason": "",
        }

    duration_samples = [duration for duration in (_run_duration_hours(run) for run in accepted_runs) if duration > 0.0]
    if duration_samples:
        median_duration_hours = _median(duration_samples)
        midpoint_hours = max(1.0, effort_units * median_duration_hours)
        low_hours = max(0.5, midpoint_hours * 0.75)
        high_hours = max(high_hours if (high_hours := heuristic_high_hours) > 0 else low_hours + 0.5, midpoint_hours * 1.5)
        confidence = ETA_STATUS_MEDIUM_CONFIDENCE if len(duration_samples) >= 3 else ETA_STATUS_LOW_CONFIDENCE
        return {
            "status": "estimated",
            "eta_human": _format_eta_window(low_hours, high_hours),
            "eta_confidence": confidence,
            "basis": "accepted_run_median_duration",
            "summary": (
                f"{current_open_count} open milestones remain ({in_progress_count} in progress, "
                f"{not_started_count} not started); based on a median accepted run time of {median_duration_hours:.1f}h."
            ),
            "predicted_completion_at": _iso(now + dt.timedelta(hours=(low_hours + high_hours) / 2.0)),
            "range_low_hours": round(low_hours, 2),
            "range_high_hours": round(high_hours, 2),
            "remaining_open_milestones": current_open_count,
            "remaining_in_progress_milestones": in_progress_count,
            "remaining_not_started_milestones": not_started_count,
            "remaining_effort_units": round(effort_units, 2),
            "history_sample_count": len(duration_samples),
            "observed_burn_milestones_per_day": 0.0,
            "blocking_reason": "",
        }

    low_hours = max(0.5, heuristic_low_hours)
    high_hours = max(low_hours + 0.5, heuristic_high_hours)
    return {
        "status": "estimated",
        "eta_human": _format_eta_window(low_hours, high_hours),
        "eta_confidence": ETA_STATUS_LOW_CONFIDENCE,
        "basis": "heuristic_status_mix",
        "summary": (
            f"{current_open_count} open milestones remain ({in_progress_count} in progress, "
            f"{not_started_count} not started); range is a fallback heuristic from the current status mix."
        ),
        "predicted_completion_at": _iso(now + dt.timedelta(hours=(low_hours + high_hours) / 2.0)),
        "range_low_hours": round(low_hours, 2),
        "range_high_hours": round(high_hours, 2),
        "remaining_open_milestones": current_open_count,
        "remaining_in_progress_milestones": in_progress_count,
        "remaining_not_started_milestones": not_started_count,
        "remaining_effort_units": round(effort_units, 2),
        "history_sample_count": 0,
        "observed_burn_milestones_per_day": 0.0,
        "blocking_reason": "",
    }


def _estimate_completion_review_eta(
    frontier: Sequence[Milestone],
    completion_audit: Dict[str, Any],
    history: Sequence[Dict[str, Any]],
    now: dt.datetime,
) -> Dict[str, Any]:
    journey_gate_audit = dict(completion_audit.get("journey_gate_audit") or {})
    linux_gate_audit = dict(completion_audit.get("linux_desktop_exit_gate_audit") or {})
    weekly_pulse_audit = dict(completion_audit.get("weekly_pulse_audit") or {})
    repo_backlog_audit = dict(completion_audit.get("repo_backlog_audit") or {})
    receipt_audit = dict(completion_audit.get("receipt_audit") or {})
    blocked_journeys = len(journey_gate_audit.get("blocked_journeys") or [])
    warning_journeys = len(journey_gate_audit.get("warning_journeys") or [])
    components: List[str] = []
    recovery_units = 0.0

    if receipt_audit.get("status") != "pass":
        components.append("trusted completion receipt")
        recovery_units += 1.0
    if journey_gate_audit.get("status") != "pass":
        components.append("golden journey proof")
        recovery_units += max(1.0, blocked_journeys * 1.5 + warning_journeys * 0.5)
    if linux_gate_audit.get("status") != "pass":
        components.append("Linux desktop exit gate")
        linux_reason = str(linux_gate_audit.get("reason") or "").lower()
        recovery_units += 1.0 if "stale" in linux_reason else 2.0
    if weekly_pulse_audit.get("status") != "pass":
        components.append("weekly product pulse")
        pulse_reason = str(weekly_pulse_audit.get("reason") or "").lower()
        recovery_units += 0.5 if "stale" in pulse_reason else 1.0
    if repo_backlog_audit.get("status") != "pass":
        components.append("repo-local backlog milestones")
        recovery_units += max(1.0, min(6.0, float(repo_backlog_audit.get("open_item_count") or 0)))
    if recovery_units <= 0.0:
        recovery_units = max(1.0, len(frontier) * 0.75)
    low_hours = max(0.5, recovery_units * 0.75)
    high_hours = max(low_hours + 0.5, recovery_units * 2.0)
    component_text = ", ".join(components) if components else "completion review recovery"
    return {
        "status": "recovery",
        "eta_human": _format_eta_window(low_hours, high_hours),
        "eta_confidence": ETA_STATUS_MEDIUM_CONFIDENCE if len(components) <= 2 else ETA_STATUS_LOW_CONFIDENCE,
        "basis": "completion_review_recovery",
        "summary": (
            f"Registry closure is not yet trustworthy; recovery still needs {component_text}. "
            f"Blocked journeys={blocked_journeys}, warning journeys={warning_journeys}, review frontier={len(frontier)}."
        ),
        "predicted_completion_at": _iso(now + dt.timedelta(hours=(low_hours + high_hours) / 2.0)),
        "range_low_hours": round(low_hours, 2),
        "range_high_hours": round(high_hours, 2),
        "remaining_open_milestones": 0,
        "remaining_in_progress_milestones": 0,
        "remaining_not_started_milestones": 0,
        "remaining_effort_units": round(recovery_units, 2),
        "history_sample_count": len(history),
        "observed_burn_milestones_per_day": 0.0,
        "blocking_reason": "",
    }


def _apply_eta_blocker(snapshot: Dict[str, Any], blocker_reason: str) -> Dict[str, Any]:
    reason = _normalize_blocker(blocker_reason)
    if not reason:
        return snapshot
    eta = dict(snapshot)
    eta["status"] = "blocked"
    eta["blocking_reason"] = reason
    eta["basis"] = f"{snapshot.get('basis') or 'unknown'}+external_blocker"
    eta_human = str(snapshot.get("eta_human") or "").strip()
    if eta_human and eta_human not in {"unknown", "ready now"}:
        eta["eta_human"] = f"{eta_human} after unblock"
    else:
        eta["eta_human"] = "blocked"
    summary = str(snapshot.get("summary") or "").strip()
    if summary:
        eta["summary"] = f"{summary} Current external blocker: {reason}"
    else:
        eta["summary"] = f"ETA is blocked by an external worker/runtime issue: {reason}"
    eta["predicted_completion_at"] = ""
    current_confidence = str(snapshot.get("eta_confidence") or ETA_STATUS_LOW_CONFIDENCE).strip().lower()
    if current_confidence == ETA_STATUS_HIGH_CONFIDENCE:
        eta["eta_confidence"] = ETA_STATUS_MEDIUM_CONFIDENCE
    elif current_confidence in {ETA_STATUS_BLOCKED_CONFIDENCE, ETA_STATUS_LOW_CONFIDENCE, ""}:
        eta["eta_confidence"] = ETA_STATUS_LOW_CONFIDENCE
    else:
        eta["eta_confidence"] = current_confidence
    return eta


def _build_eta_snapshot(
    *,
    mode: str,
    open_milestones: Sequence[Milestone],
    frontier: Sequence[Milestone],
    history: Sequence[Dict[str, Any]],
    completion_audit: Optional[Dict[str, Any]] = None,
    now: Optional[dt.datetime] = None,
) -> Dict[str, Any]:
    current_time = now or _utc_now()
    blocker_reason = _eta_external_blocker_reason(history, completion_audit)
    base_snapshot: Dict[str, Any]
    if completion_audit and completion_audit.get("status") == "pass" and not open_milestones:
        base_snapshot = {
            "status": "ready",
            "eta_human": "ready now",
            "eta_confidence": ETA_STATUS_HIGH_CONFIDENCE,
            "basis": "completion_audit_pass",
            "summary": "Whole-product completion audit is green on current repo-local evidence.",
            "predicted_completion_at": _iso(current_time),
            "range_low_hours": 0.0,
            "range_high_hours": 0.0,
            "remaining_open_milestones": 0,
            "remaining_in_progress_milestones": 0,
            "remaining_not_started_milestones": 0,
            "remaining_effort_units": 0.0,
            "history_sample_count": len(history),
            "observed_burn_milestones_per_day": 0.0,
            "blocking_reason": "",
        }
    elif open_milestones:
        base_snapshot = _estimate_open_milestone_eta(open_milestones, history, current_time)
    elif completion_audit:
        base_snapshot = _estimate_completion_review_eta(frontier, completion_audit, history, current_time)
    else:
        base_snapshot = {
            "status": "unknown",
            "eta_human": "unknown",
            "eta_confidence": ETA_STATUS_LOW_CONFIDENCE,
            "basis": "insufficient_state",
            "summary": "Fleet does not have enough live design state yet to estimate completion.",
            "predicted_completion_at": "",
            "range_low_hours": 0.0,
            "range_high_hours": 0.0,
            "remaining_open_milestones": 0,
            "remaining_in_progress_milestones": 0,
            "remaining_not_started_milestones": 0,
            "remaining_effort_units": 0.0,
            "history_sample_count": len(history),
            "observed_burn_milestones_per_day": 0.0,
            "blocking_reason": "",
        }
    return _apply_eta_blocker(base_snapshot, blocker_reason)


def _render_eta(eta: Dict[str, Any]) -> str:
    if not eta:
        return "ETA is unavailable."
    lines = [
        f"status: {eta.get('status') or 'unknown'}",
        f"eta_human: {eta.get('eta_human') or 'unknown'}",
        f"eta_confidence: {eta.get('eta_confidence') or 'unknown'}",
        f"basis: {eta.get('basis') or 'unknown'}",
        f"summary: {eta.get('summary') or 'none'}",
        f"predicted_completion_at: {eta.get('predicted_completion_at') or 'unknown'}",
        (
            "range_hours: "
            f"{eta.get('range_low_hours', 0.0)}-{eta.get('range_high_hours', 0.0)}"
        ),
        (
            "remaining_open_milestones: "
            f"{eta.get('remaining_open_milestones', 0)}"
        ),
    ]
    blocker_reason = str(eta.get("blocking_reason") or "").strip()
    if blocker_reason:
        lines.append(f"blocking_reason: {blocker_reason}")
    return "\n".join(lines)


def derive_eta(args: argparse.Namespace) -> Dict[str, Any]:
    state_root = Path(args.state_root).resolve()
    _, history = _effective_supervisor_state(state_root, history_limit=ETA_HISTORY_LIMIT)
    context = derive_context(args)
    audit: Optional[Dict[str, Any]] = None
    if not context["open_milestones"]:
        audit = _design_completion_audit(args, history[-COMPLETION_AUDIT_HISTORY_LIMIT:])
        if audit.get("status") != "pass":
            context = derive_completion_review_context(args, state_root, base_context=context, audit=audit)
            audit = dict(context.get("completion_audit") or audit)
    return _build_eta_snapshot(
        mode=("completion_review" if not context["open_milestones"] else "live"),
        open_milestones=context["open_milestones"],
        frontier=context["frontier"],
        history=history,
        completion_audit=audit,
    )


def _pid_alive(pid: Optional[int]) -> bool:
    try:
        if not pid:
            return False
        os.kill(int(pid), 0)
        return True
    except (ProcessLookupError, OSError):
        return False


def _pid_start_ticks(pid: Optional[int]) -> str:
    try:
        if not pid:
            return ""
        raw = _read_text(Path(f"/proc/{int(pid)}/stat")).strip()
    except Exception:
        return ""
    if ")" not in raw:
        return ""
    suffix = raw.rsplit(")", 1)[1].strip().split()
    return suffix[19] if len(suffix) > 19 else ""


def _is_lock_stale(raw: Dict[str, Any], now: dt.datetime, ttl_seconds: float) -> bool:
    created_raw = str(raw.get("created_at") or "").strip()
    pid = raw.get("pid")
    if not _pid_alive(pid):
        return True
    if int(pid or 0) == os.getpid():
        return True
    stored_start_ticks = str(raw.get("proc_start_ticks") or "").strip()
    if stored_start_ticks and _pid_start_ticks(pid) != stored_start_ticks:
        return True
    if not created_raw:
        return True
    try:
        created_at = dt.datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
    except ValueError:
        return True
    if ttl_seconds > 0 and (now - created_at).total_seconds() > float(ttl_seconds):
        return True
    return False


def _acquire_lock(path: Path, *, ttl_seconds: float) -> None:
    _ensure_dir(path.parent)
    for attempt in range(LOCK_ACQUIRE_RETRIES):
        now = _utc_now()
        if path.exists():
            try:
                raw = json.loads(_read_text(path))
            except Exception:
                raw = {}
            if raw and not _is_lock_stale(raw, now, ttl_seconds):
                holder_pid = raw.get("pid")
                raise RuntimeError(f"design supervisor lock already held by pid={holder_pid} at {path}")
            path.unlink(missing_ok=True)
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            if attempt >= LOCK_ACQUIRE_RETRIES - 1:
                raise RuntimeError(f"design supervisor lock race at {path}")
            time.sleep(LOCK_RETRY_SECONDS)
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "pid": os.getpid(),
                    "created_at": now.isoformat(),
                    "proc_start_ticks": _pid_start_ticks(os.getpid()),
                },
                handle,
            )
        return
    raise RuntimeError(f"design supervisor lock unavailable at {path}")


def _release_lock(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass


def derive_context(args: argparse.Namespace) -> Dict[str, Any]:
    registry_path = Path(args.registry_path).resolve()
    program_milestones_path = Path(args.program_milestones_path).resolve()
    roadmap_path = Path(args.roadmap_path).resolve()
    handoff_path = Path(args.handoff_path).resolve()
    workspace_root = Path(args.workspace_root).resolve()
    scope_roots = _scope_roots(args)
    open_milestones, wave_order = _load_open_milestones(registry_path)
    handoff_text = _read_text(handoff_path) if handoff_path.exists() else ""
    frontier, frontier_ids = _select_frontier(open_milestones, handoff_text)
    frontier = _focused_frontier(args, open_milestones, frontier)
    frontier_ids = [item.id for item in frontier]
    focus_profiles = _configured_focus_profiles(args)
    focus_owners = _configured_focus_owners(args)
    focus_texts = _configured_focus_texts(args)
    prompt = build_worker_prompt(
        registry_path=registry_path,
        program_milestones_path=program_milestones_path,
        roadmap_path=roadmap_path,
        handoff_path=handoff_path,
        open_milestones=open_milestones,
        frontier=frontier,
        scope_roots=scope_roots,
        focus_profiles=focus_profiles,
        focus_owners=focus_owners,
        focus_texts=focus_texts,
    )
    return {
        "registry_path": registry_path,
        "program_milestones_path": program_milestones_path,
        "roadmap_path": roadmap_path,
        "handoff_path": handoff_path,
        "workspace_root": workspace_root,
        "scope_roots": scope_roots,
        "open_milestones": open_milestones,
        "wave_order": wave_order,
        "frontier": frontier,
        "frontier_ids": frontier_ids,
        "focus_profiles": focus_profiles,
        "focus_owners": focus_owners,
        "focus_texts": focus_texts,
        "prompt": prompt,
    }


def derive_completion_review_context(
    args: argparse.Namespace,
    state_root: Path,
    *,
    base_context: Optional[Dict[str, Any]] = None,
    audit: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    context = dict(base_context or derive_context(args))
    history = _completion_review_history(state_root, limit=COMPLETION_AUDIT_HISTORY_LIMIT)
    review_audit = dict(audit or _design_completion_audit(args, history))
    frontier = _completion_review_frontier(review_audit, Path(args.registry_path).resolve(), history)
    frontier = _focused_frontier(args, frontier, frontier)
    frontier_paths = _completion_review_frontier_paths(Path(args.workspace_root).resolve())
    prompt = build_completion_review_prompt(
        registry_path=context["registry_path"],
        program_milestones_path=context["program_milestones_path"],
        roadmap_path=context["roadmap_path"],
        handoff_path=context["handoff_path"],
        frontier_artifact_path=frontier_paths[0],
        frontier=frontier,
        scope_roots=context["scope_roots"],
        focus_profiles=context["focus_profiles"],
        focus_owners=context["focus_owners"],
        focus_texts=context["focus_texts"],
        audit=review_audit,
        history=history,
    )
    materialized_paths = _materialize_completion_review_frontier(
        args=args,
        state_root=state_root,
        mode="completion_review",
        frontier=frontier,
        focus_profiles=context["focus_profiles"],
        focus_owners=context["focus_owners"],
        focus_texts=context["focus_texts"],
        completion_audit=review_audit,
    )
    context.update(
        {
            "open_milestones": [],
            "frontier": frontier,
            "frontier_ids": [item.id for item in frontier],
            "prompt": prompt,
            "completion_audit": review_audit,
            "completion_history": history,
            "completion_review_frontier_path": materialized_paths["published_path"],
            "completion_review_frontier_mirror_path": materialized_paths["mirror_path"],
        }
    )
    return context


def _live_state_with_current_completion_audit(
    args: argparse.Namespace,
    state_root: Path,
    state: Dict[str, Any],
    history: List[Dict[str, Any]],
    *,
    include_shards: bool = True,
) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    effective_args = argparse.Namespace(**vars(args))
    if not _text_list(getattr(effective_args, "focus_profile", []) or []):
        effective_args.focus_profile = list(state.get("focus_profiles") or [])
    if not _text_list(getattr(effective_args, "focus_owner", []) or []):
        effective_args.focus_owner = list(state.get("focus_owners") or [])
    if not _text_list(getattr(effective_args, "focus_text", []) or []):
        effective_args.focus_text = list(state.get("focus_texts") or [])
    context = derive_context(effective_args)
    updated = dict(state)
    if context["open_milestones"]:
        eta = _build_eta_snapshot(
            mode=str(updated.get("mode") or "live"),
            open_milestones=context["open_milestones"],
            frontier=context["frontier"],
            history=history,
            completion_audit=None,
        )
        updated.update(
            {
                "mode": str(updated.get("mode") or "live"),
                "open_milestone_ids": [item.id for item in context["open_milestones"]],
                "frontier_ids": [item.id for item in context["frontier"]],
                "focus_profiles": list(context["focus_profiles"]),
                "focus_owners": list(context["focus_owners"]),
                "focus_texts": list(context["focus_texts"]),
                "eta": eta,
                "completion_review_frontier_path": "",
                "completion_review_frontier_mirror_path": "",
            }
        )
        return updated, history

    review_history = _completion_review_history(state_root, limit=ETA_HISTORY_LIMIT)
    audit = _design_completion_audit(effective_args, review_history[-COMPLETION_AUDIT_HISTORY_LIMIT:])
    if audit.get("status") == "pass":
        eta = _build_eta_snapshot(
            mode="complete",
            open_milestones=[],
            frontier=[],
            history=review_history,
            completion_audit=audit,
        )
        frontier_paths = _materialize_completion_review_frontier(
            args=effective_args,
            state_root=state_root,
            mode="complete",
            frontier=[],
            focus_profiles=context["focus_profiles"],
            focus_owners=context["focus_owners"],
            focus_texts=context["focus_texts"],
            completion_audit=audit,
            eta=eta,
        )
        updated.update(
            {
                "mode": "complete",
                "open_milestone_ids": [],
                "frontier_ids": [],
                "focus_profiles": list(context["focus_profiles"]),
                "focus_owners": list(context["focus_owners"]),
                "focus_texts": list(context["focus_texts"]),
                "completion_audit": audit,
                "eta": eta,
                "completion_review_frontier_path": frontier_paths["published_path"],
                "completion_review_frontier_mirror_path": frontier_paths["mirror_path"],
            }
        )
        if include_shards:
            updated["shards"] = _live_shard_summaries(effective_args, state_root)
            updated["shard_count"] = len(updated.get("shards") or [])
        return updated, review_history

    review_context = derive_completion_review_context(effective_args, state_root, base_context=context, audit=audit)
    eta = _build_eta_snapshot(
        mode="completion_review",
        open_milestones=[],
        frontier=review_context["frontier"],
        history=review_history,
        completion_audit=review_context["completion_audit"],
    )
    frontier_paths = _materialize_completion_review_frontier(
        args=effective_args,
        state_root=state_root,
        mode="completion_review",
        frontier=review_context["frontier"],
        focus_profiles=review_context["focus_profiles"],
        focus_owners=review_context["focus_owners"],
        focus_texts=review_context["focus_texts"],
        completion_audit=review_context["completion_audit"],
        eta=eta,
    )
    updated.update(
        {
            "mode": "completion_review",
            "open_milestone_ids": [],
            "frontier_ids": [item.id for item in review_context["frontier"]],
            "focus_profiles": list(review_context["focus_profiles"]),
            "focus_owners": list(review_context["focus_owners"]),
            "focus_texts": list(review_context["focus_texts"]),
            "completion_audit": dict(review_context["completion_audit"]),
            "eta": eta,
            "completion_review_frontier_path": frontier_paths["published_path"],
            "completion_review_frontier_mirror_path": frontier_paths["mirror_path"],
        }
    )
    if include_shards:
        updated["shards"] = _live_shard_summaries(effective_args, state_root)
        updated["shard_count"] = len(updated.get("shards") or [])
    return updated, review_history


def _live_shard_summaries(args: argparse.Namespace, state_root: Path) -> List[Dict[str, Any]]:
    aggregate_root = _aggregate_state_root(state_root)
    summaries: List[Dict[str, Any]] = []
    for shard_root in _shard_state_roots(aggregate_root):
        shard_state = _read_state(_state_payload_path(shard_root))
        shard_history = _read_history(_history_payload_path(shard_root), limit=ETA_HISTORY_LIMIT)
        updated_shard, _ = _live_state_with_current_completion_audit(
            args,
            shard_root,
            shard_state,
            shard_history,
            include_shards=False,
        )
        summaries.append(
            {
                "name": shard_root.name,
                "state_root": str(shard_root),
                "updated_at": updated_shard.get("updated_at") or "",
                "mode": updated_shard.get("mode") or "",
                "frontier_ids": list(updated_shard.get("frontier_ids") or []),
                "open_milestone_ids": list(updated_shard.get("open_milestone_ids") or []),
                "eta_status": str((updated_shard.get("eta") or {}).get("status") or "").strip(),
                "last_run_id": str((updated_shard.get("last_run") or {}).get("run_id") or "").strip(),
            }
        )
    return summaries


def _write_run_artifacts(run_dir: Path, prompt: str) -> Path:
    _ensure_dir(run_dir)
    prompt_path = run_dir / "prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8")
    return prompt_path


def _account_runtime_path(state_root: Path) -> Path:
    return state_root / "account_runtime.json"


def _read_account_runtime(path: Path) -> Dict[str, Any]:
    payload = _read_state(path)
    sources = payload.get("sources")
    if not isinstance(sources, dict):
        payload["sources"] = {}
    return payload


def _write_account_runtime(path: Path, payload: Dict[str, Any]) -> None:
    payload = dict(payload or {})
    payload["updated_at"] = _iso_now()
    payload["sources"] = dict(payload.get("sources") or {})
    _write_json(path, payload)


def _credential_source_key(account: WorkerAccount) -> str:
    if account.auth_kind in CHATGPT_AUTH_KINDS:
        if account.auth_json_file:
            return f"{account.auth_kind}:{account.auth_json_file}"
    elif account.auth_kind == "api_key":
        if account.api_key_env:
            return f"{account.auth_kind}:env:{account.api_key_env}"
        if account.api_key_file:
            return f"{account.auth_kind}:file:{account.api_key_file}"
    return f"alias:{account.alias}"


def _credential_source_fingerprint(account: WorkerAccount, workspace_root: Path) -> str:
    try:
        if account.auth_kind in CHATGPT_AUTH_KINDS:
            path = Path(account.auth_json_file).expanduser()
            if not path.exists() or not path.is_file():
                return f"missing:{path}"
            return hashlib.sha256(path.read_bytes()).hexdigest()[:24]
        if account.auth_kind == "api_key":
            if account.api_key_env:
                value = _resolve_env_secret(account.api_key_env, workspace_root)
                return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24] if value else f"missing-env:{account.api_key_env}"
            if account.api_key_file:
                path = Path(account.api_key_file).expanduser()
                if not path.exists() or not path.is_file():
                    return f"missing:{path}"
                value = _read_text(path).strip()
                return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24] if value else f"empty:{path}"
    except Exception as exc:
        return f"error:{type(exc).__name__}"
    return ""


def _refresh_source_credential_state(
    payload: Dict[str, Any],
    account: WorkerAccount,
    workspace_root: Path,
    *,
    now: Optional[dt.datetime] = None,
) -> bool:
    current = now or _utc_now()
    sources = dict(payload.get("sources") or {})
    key = _credential_source_key(account)
    item = dict(sources.get(key) or {})
    fingerprint = _credential_source_fingerprint(account, workspace_root)
    previous = str(item.get("credential_fingerprint") or "").strip()
    if not item and not fingerprint:
        return False
    dirty = False
    if previous != fingerprint:
        item["alias"] = account.alias
        item["owner_id"] = account.owner_id
        item["source_key"] = key
        item["credential_fingerprint"] = fingerprint
        if previous and (
            (_parse_iso(str(item.get("backoff_until") or "")) or current) > current
            or (_parse_iso(str(item.get("spark_backoff_until") or "")) or current) > current
            or str(item.get("last_error") or "").strip()
        ):
            item["backoff_until"] = ""
            item["spark_backoff_until"] = ""
            item["last_error"] = ""
        sources[key] = item
        payload["sources"] = sources
        dirty = True
    return dirty


def _account_home(state_root: Path, account: WorkerAccount) -> Path:
    explicit_home = str(account.home_dir or "").strip()
    if explicit_home:
        path = Path(explicit_home).expanduser()
    elif account.auth_kind in CHATGPT_AUTH_KINDS and account.auth_json_file:
        source_hash = hashlib.sha1(_credential_source_key(account).encode("utf-8")).hexdigest()[:16]
        path = state_root / "codex-homes" / f"chatgpt-{source_hash}"
    else:
        path = state_root / "codex-homes" / account.alias
    _ensure_dir(path)
    return path


def _direct_worker_home(state_root: Path, worker_lane: str) -> Path:
    token = re.sub(r"[^A-Za-z0-9._-]+", "-", str(worker_lane or "default").strip()) or "default"
    path = state_root / "codex-homes" / f"direct-{token}"
    _ensure_dir(path)
    return path


def _prepare_direct_worker_environment(state_root: Path, worker_lane: str) -> Dict[str, str]:
    home = _direct_worker_home(state_root, worker_lane)
    env = os.environ.copy()
    env["CODEX_HOME"] = str(home)
    env["HOME"] = str(home)
    return env


def _write_toml_string(value: str) -> str:
    return json.dumps(value)


def _seed_auth_json(home: Path, source_path: Path) -> None:
    if not source_path.exists():
        raise RuntimeError(f"missing auth_json_file: {source_path}")
    target = home / "auth.json"
    target.write_bytes(source_path.read_bytes())


def _resolve_env_secret(name: str, workspace_root: Path) -> str:
    env_name = str(name or "").strip()
    if not env_name:
        return ""
    direct = str(os.environ.get(env_name, "") or "").strip()
    if direct:
        return direct
    for candidate in (
        workspace_root / "runtime.env",
        workspace_root / "runtime.ea.env",
        workspace_root / ".env",
        Path("/docker/.env"),
        Path("/docker/EA/.env"),
        Path("/docker/chummer5a/.env"),
        Path("/docker/chummer5a/.env.providers"),
    ):
        if not candidate.exists() or not candidate.is_file():
            continue
        for raw_line in _read_text(candidate).splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() != env_name:
                continue
            resolved = value.strip().strip("'").strip('"')
            if resolved:
                return resolved
    return ""


def _read_api_key(account: WorkerAccount, workspace_root: Path) -> str:
    if account.api_key_env:
        resolved = _resolve_env_secret(account.api_key_env, workspace_root)
        if resolved:
            return resolved
        raise RuntimeError(f"missing environment variable for api_key_env: {account.api_key_env}")
    if account.api_key_file:
        path = Path(account.api_key_file).expanduser()
        if not path.exists():
            raise RuntimeError(f"missing api_key_file: {path}")
        api_key = _read_text(path).strip()
        if api_key:
            return api_key
        raise RuntimeError(f"empty api_key_file: {path}")
    raise RuntimeError(f"no API key source configured for {account.alias}")


def _prepare_account_environment(state_root: Path, workspace_root: Path, account: WorkerAccount) -> Dict[str, str]:
    home = _account_home(state_root, account)
    config_lines = ['cli_auth_credentials_store = "file"']
    if account.forced_login_method:
        config_lines.append(f"forced_login_method = {_write_toml_string(account.forced_login_method)}")
    if account.forced_chatgpt_workspace_id:
        config_lines.append(
            f"forced_chatgpt_workspace_id = {_write_toml_string(account.forced_chatgpt_workspace_id)}"
        )
    (home / "config.toml").write_text("\n".join(config_lines) + "\n", encoding="utf-8")

    env = os.environ.copy()
    env["CODEX_HOME"] = str(home)
    env["HOME"] = str(home)
    if account.auth_kind in CHATGPT_AUTH_KINDS:
        _seed_auth_json(home, Path(account.auth_json_file).expanduser())
    elif account.auth_kind == "api_key":
        env["CODEX_API_KEY"] = _read_api_key(account, workspace_root)
    else:
        raise RuntimeError(f"unsupported auth_kind for {account.alias}: {account.auth_kind}")
    if account.openai_base_url:
        env["OPENAI_BASE_URL"] = account.openai_base_url
    return env


def _default_account_owner_ids(accounts_payload: Dict[str, Any]) -> List[str]:
    configured = _text_list((accounts_payload.get("account_policy") or {}).get("protected_owner_ids") or [])
    return configured or list(DEFAULT_ACCOUNT_OWNER_IDS)


def _load_worker_accounts(args: argparse.Namespace) -> List[WorkerAccount]:
    accounts_path = Path(args.accounts_path).resolve()
    if not accounts_path.exists():
        return []
    payload = _read_yaml(accounts_path)
    raw_accounts = payload.get("accounts") or {}
    if not isinstance(raw_accounts, dict):
        return []
    alias_filter = set(_text_list(args.account_alias or []))
    explicit_owner_filter = _text_list(args.account_owner_id or [])
    owner_filter = explicit_owner_filter or ([] if alias_filter else _default_account_owner_ids(payload))
    owner_order = {value: index for index, value in enumerate(owner_filter)}
    rows: List[WorkerAccount] = []
    for alias, raw in raw_accounts.items():
        if not isinstance(raw, dict):
            continue
        clean_alias = str(alias or "").strip()
        if not clean_alias:
            continue
        if alias_filter and clean_alias not in alias_filter:
            continue
        owner_id = str(raw.get("owner_id") or "").strip()
        if owner_filter and owner_id not in owner_order:
            continue
        auth_kind = str(raw.get("auth_kind") or "api_key").strip()
        if auth_kind not in CHATGPT_AUTH_KINDS and auth_kind != "api_key":
            continue
        health_state = str(raw.get("health_state") or "").strip().lower()
        if health_state not in READY_ACCOUNT_STATES:
            continue
        rows.append(
            WorkerAccount(
                alias=clean_alias,
                owner_id=owner_id,
                auth_kind=auth_kind,
                auth_json_file=str(raw.get("auth_json_file") or "").strip(),
                api_key_env=str(raw.get("api_key_env") or "").strip(),
                api_key_file=str(raw.get("api_key_file") or "").strip(),
                allowed_models=_text_list(raw.get("allowed_models") or []),
                health_state=health_state,
                spark_enabled=bool(raw.get("spark_enabled", SPARK_MODEL in (raw.get("allowed_models") or []))),
                bridge_priority=int(raw.get("bridge_priority") or 999),
                forced_login_method=str(raw.get("forced_login_method") or "").strip(),
                forced_chatgpt_workspace_id=str(raw.get("forced_chatgpt_workspace_id") or "").strip(),
                openai_base_url=str(raw.get("openai_base_url") or "").strip(),
                home_dir=str(raw.get("home_dir") or raw.get("codex_home") or "").strip(),
            )
        )
    rows.sort(
        key=lambda item: (
            owner_order.get(item.owner_id, 999 if explicit_owner_filter or not alias_filter else 0),
            item.bridge_priority,
            item.alias,
        )
    )
    return rows


def _parse_backoff_seconds(text: str, default_seconds: int) -> Optional[int]:
    lower = str(text or "").lower()
    if "429" not in lower and "rate limit" not in lower and "too many requests" not in lower:
        return None
    patterns = [
        (r"retry after\s+(\d+)\s*s", 1),
        (r"try again in\s+(\d+)\s*s", 1),
        (r"after\s+(\d+)\s*seconds", 1),
        (r"after\s+(\d+)\s*minutes", 60),
        (r"(\d+)\s*seconds?", 1),
        (r"(\d+)\s*minutes?", 60),
    ]
    for pattern, multiplier in patterns:
        match = re.search(pattern, lower)
        if match:
            return max(int(match.group(1)) * multiplier, default_seconds)
    return default_seconds


def _parse_spark_pool_backoff_seconds(text: str, default_seconds: int) -> Optional[int]:
    lower = str(text or "").lower()
    spark_signals = ("spark", "codex spark", "spark pool", "spark token", "spark quota", "spark credits")
    exhaustion_signals = ("depleted", "exhausted", "empty", "unavailable", "quota exceeded", "limit reached", "out of")
    if not any(signal in lower for signal in spark_signals):
        return None
    if not any(signal in lower for signal in exhaustion_signals) and "429" not in lower and "rate limit" not in lower:
        return None
    return _parse_backoff_seconds(text, default_seconds) or default_seconds


def _parse_auth_failure_message(text: str) -> Optional[str]:
    lower = str(text or "").lower()
    markers = [
        ("refresh_token_reused", "chatgpt auth refresh token was invalidated by another session"),
        ("access token could not be refreshed", "chatgpt auth refresh token is stale"),
        ("refresh token was already used", "chatgpt auth refresh token is stale"),
        ("provided authentication token is expired", "chatgpt auth session is expired"),
        ("please log out and sign in again", "chatgpt auth session requires a fresh login"),
        ("incorrect api key provided", "api key is invalid or revoked"),
        ("invalid api key", "api key is invalid or revoked"),
    ]
    for needle, message in markers:
        if needle in lower:
            return message
    if "401 unauthorized" in lower and ("token" in lower or "api key" in lower or "auth" in lower):
        return "authentication failed for this account"
    return None


def _parse_backend_unavailable_message(text: str) -> Optional[str]:
    raw = str(text or "")
    match = re.search(r"upstream_unavailable:([^\n\"']+)", raw, flags=re.IGNORECASE)
    if match:
        return f"backend unavailable: {match.group(1).strip().rstrip('}').rstrip(']')}"
    if "gemini_vortex_cli_missing" in raw.lower():
        return "backend unavailable: gemini_vortex:gemini_vortex_cli_missing"
    return None


def _parse_usage_limit_reset_at(text: str) -> Optional[dt.datetime]:
    raw = str(text or "")
    lower = raw.lower()
    if "usage limit" not in lower and "send a request to your admin" not in lower:
        return None
    match = re.search(
        r"try again at\s+([A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?,\s+\d{4}\s+\d{1,2}:\d{2}\s+[AP]M)",
        raw,
        re.IGNORECASE,
    )
    if not match:
        return None
    candidate = re.sub(r"(\d)(st|nd|rd|th)", r"\1", match.group(1), flags=re.IGNORECASE).strip()
    for fmt in ("%b %d, %Y %I:%M %p", "%B %d, %Y %I:%M %p"):
        try:
            return dt.datetime.strptime(candidate, fmt).replace(tzinfo=dt.timezone.utc)
        except ValueError:
            continue
    return None


def _parse_usage_limit_backoff_seconds(text: str, default_seconds: int, *, now: Optional[dt.datetime] = None) -> Optional[int]:
    raw = str(text or "")
    lower = raw.lower()
    if "usage limit" not in lower and "send a request to your admin" not in lower:
        return None
    current = now or _utc_now()
    reset_at = _parse_usage_limit_reset_at(raw)
    if reset_at is None:
        return default_seconds
    seconds = int((reset_at - current).total_seconds())
    return max(seconds, default_seconds) if seconds > 0 else default_seconds


def _parse_unsupported_chatgpt_model(text: str) -> Optional[str]:
    raw = str(text or "")
    lower = raw.lower()
    if "not supported when using codex with a chatgpt account" not in lower:
        return None
    match = re.search(r"'([^']+)'", raw)
    if match:
        return str(match.group(1) or "").strip() or None
    return "unknown"


def _set_source_backoff(
    payload: Dict[str, Any],
    account: WorkerAccount,
    *,
    backoff_until: Optional[dt.datetime] = None,
    spark_backoff_until: Optional[dt.datetime] = None,
    last_error: str = "",
) -> None:
    sources = dict(payload.get("sources") or {})
    key = _credential_source_key(account)
    item = dict(sources.get(key) or {})
    item["alias"] = account.alias
    item["owner_id"] = account.owner_id
    item["source_key"] = key
    if backoff_until is not None:
        item["backoff_until"] = _iso(backoff_until)
    if spark_backoff_until is not None:
        item["spark_backoff_until"] = _iso(spark_backoff_until)
    if last_error:
        item["last_error"] = last_error
    sources[key] = item
    payload["sources"] = sources


def _clear_source_backoff(payload: Dict[str, Any], account: WorkerAccount) -> None:
    sources = dict(payload.get("sources") or {})
    key = _credential_source_key(account)
    item = dict(sources.get(key) or {})
    item["alias"] = account.alias
    item["owner_id"] = account.owner_id
    item["source_key"] = key
    item["backoff_until"] = ""
    item["spark_backoff_until"] = ""
    item["last_error"] = ""
    sources[key] = item
    payload["sources"] = sources


def _active_source_backoff(
    payload: Dict[str, Any],
    account: WorkerAccount,
    *,
    model: str = "",
    now: Optional[dt.datetime] = None,
) -> tuple[Optional[dt.datetime], str]:
    current = now or _utc_now()
    item = dict((payload.get("sources") or {}).get(_credential_source_key(account)) or {})
    if not item:
        return None, ""
    backoff_until = _parse_iso(str(item.get("backoff_until") or ""))
    if backoff_until is not None and backoff_until > current:
        return backoff_until, str(item.get("last_error") or "").strip()
    if model == SPARK_MODEL:
        spark_backoff_until = _parse_iso(str(item.get("spark_backoff_until") or ""))
        if spark_backoff_until is not None and spark_backoff_until > current:
            return spark_backoff_until, str(item.get("last_error") or "").strip()
    return None, ""


def _candidate_models_for_account(
    account: WorkerAccount,
    model_candidates: Sequence[str],
    account_runtime: Dict[str, Any],
    *,
    now: Optional[dt.datetime] = None,
) -> List[str]:
    current = now or _utc_now()
    rows: List[str] = []
    for candidate in model_candidates:
        if candidate == SPARK_MODEL and not account.spark_enabled:
            continue
        backoff_until, _ = _active_source_backoff(account_runtime, account, model=candidate, now=current)
        if backoff_until is not None:
            continue
        rows.append(candidate)
    return rows


def launch_worker(args: argparse.Namespace, context: Dict[str, Any], state_root: Path) -> WorkerRun:
    open_milestones: List[Milestone] = context["open_milestones"]
    frontier: List[Milestone] = context["frontier"]
    prompt = str(context["prompt"])
    run_id = _slug_timestamp()
    run_dir = state_root / "runs" / run_id
    prompt_path = _write_run_artifacts(run_dir, prompt)
    stdout_path = run_dir / "worker.stdout.log"
    stderr_path = run_dir / "worker.stderr.log"
    last_message_path = run_dir / "last_message.txt"
    model_candidates = _worker_model_candidates(args)
    worker_lane_candidates = _worker_lane_candidates(args)
    account_candidates = _load_worker_accounts(args)
    account_runtime_path = _account_runtime_path(state_root)
    account_runtime = _read_account_runtime(account_runtime_path)
    worker_command = _default_worker_command(
        worker_bin=args.worker_bin,
        worker_lane=worker_lane_candidates[0],
        workspace_root=Path(args.workspace_root).resolve(),
        scope_roots=context["scope_roots"],
        run_dir=run_dir,
        worker_model=model_candidates[0],
    )
    started_at = _iso_now()
    if args.dry_run:
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        last_message_path.write_text("", encoding="utf-8")
        return WorkerRun(
            run_id=run_id,
            started_at=started_at,
            finished_at=started_at,
            worker_command=worker_command,
            attempted_accounts=[],
            attempted_models=[item or "default" for item in model_candidates[:1]],
            selected_account_alias="",
            worker_exit_code=0,
            frontier_ids=[item.id for item in frontier],
            open_milestone_ids=[item.id for item in open_milestones],
            primary_milestone_id=(frontier[0].id if frontier else None),
            prompt_path=str(prompt_path),
            stdout_path=str(stdout_path),
            stderr_path=str(stderr_path),
            last_message_path=str(last_message_path),
            final_message="",
            shipped="",
            remains="",
            blocker="",
            accepted=True,
            acceptance_reason="",
        )
    workspace_root = Path(args.workspace_root).resolve()
    attempted_accounts: List[str] = []
    attempted_models: List[str] = []
    selected_account_alias = ""
    completed: subprocess.CompletedProcess[str] | None = None
    accepted = False
    acceptance_reason = "worker not launched"
    parsed: Dict[str, str] = {"shipped": "", "remains": "", "blocker": ""}
    final_message = ""
    direct_worker_lane = worker_lane_candidates[0]
    if direct_worker_lane:
        account_candidates = []
    else:
        account_runtime_dirty = False
        for account in account_candidates:
            if _refresh_source_credential_state(account_runtime, account, workspace_root):
                account_runtime_dirty = True
        if account_runtime_dirty:
            _write_account_runtime(account_runtime_path, account_runtime)
    with stdout_path.open("w", encoding="utf-8") as stdout_handle, stderr_path.open("w", encoding="utf-8") as stderr_handle:
        if account_candidates:
            attempt_index = 0
            total_attempts = sum(
                max(1, len(_candidate_models_for_account(account, model_candidates, account_runtime)))
                for account in account_candidates
            )
            stop_retrying = False
            for account in account_candidates:
                source_backoff_until, source_backoff_reason = _active_source_backoff(account_runtime, account, now=_utc_now())
                if source_backoff_until is not None:
                    stderr_handle.write(
                        f"[fleet-supervisor] skip account={account.alias} owner={account.owner_id} "
                        f"until={_iso(source_backoff_until)} reason={source_backoff_reason or 'backoff'}\n"
                    )
                    stderr_handle.flush()
                    continue
                candidate_models = _candidate_models_for_account(account, model_candidates, account_runtime)
                if not candidate_models:
                    stderr_handle.write(
                        f"[fleet-supervisor] skip account={account.alias} owner={account.owner_id} no_models_available\n"
                    )
                    stderr_handle.flush()
                    continue
                try:
                    worker_env = _prepare_account_environment(state_root, workspace_root, account)
                except Exception as exc:
                    message = f"account bootstrap failed: {exc}"
                    until = _utc_now() + dt.timedelta(seconds=DEFAULT_AUTH_FAILURE_BACKOFF_SECONDS)
                    _set_source_backoff(account_runtime, account, backoff_until=until, last_error=message)
                    _write_account_runtime(account_runtime_path, account_runtime)
                    stderr_handle.write(
                        f"[fleet-supervisor] skip account={account.alias} owner={account.owner_id} "
                        f"until={_iso(until)} reason={message}\n"
                    )
                    stderr_handle.flush()
                    continue
                for candidate_model in candidate_models:
                    attempt_index += 1
                    worker_command = _default_worker_command(
                        worker_bin=args.worker_bin,
                        worker_lane=direct_worker_lane,
                        workspace_root=workspace_root,
                        scope_roots=context["scope_roots"],
                        run_dir=run_dir,
                        worker_model=candidate_model,
                    )
                    attempted_accounts.append(account.alias)
                    attempted_models.append(candidate_model or "default")
                    selected_account_alias = account.alias
                    stderr_handle.write(
                        f"[fleet-supervisor] attempt {attempt_index}/{max(1, total_attempts)} "
                        f"account={account.alias} owner={account.owner_id} model={candidate_model or 'default'}\n"
                    )
                    stderr_handle.flush()
                    completed = subprocess.run(
                        worker_command,
                        input=prompt,
                        text=True,
                        capture_output=True,
                        cwd=str(workspace_root),
                        env=worker_env,
                        check=False,
                    )
                    if completed.stdout:
                        stdout_handle.write(completed.stdout)
                    if completed.stderr:
                        stderr_handle.write(completed.stderr)
                    stdout_handle.flush()
                    stderr_handle.flush()
                    final_message = _read_text(last_message_path).strip() if last_message_path.exists() else ""
                    parsed = _parse_final_message_sections(final_message)
                    accepted, acceptance_reason = _assess_worker_result(completed.returncode, final_message, parsed)
                    if completed.returncode == 0 and accepted:
                        _clear_source_backoff(account_runtime, account)
                        _write_account_runtime(account_runtime_path, account_runtime)
                        break
                    if completed.returncode == 0:
                        stderr_handle.write(
                            f"[fleet-supervisor] rejected result account={account.alias} "
                            f"model={candidate_model or 'default'} reason={acceptance_reason}\n"
                        )
                        stderr_handle.flush()
                        continue
                    now = _utc_now()
                    auth_failure = _parse_auth_failure_message(completed.stderr)
                    if auth_failure:
                        until = now + dt.timedelta(seconds=DEFAULT_AUTH_FAILURE_BACKOFF_SECONDS)
                        _set_source_backoff(account_runtime, account, backoff_until=until, last_error=auth_failure)
                        _write_account_runtime(account_runtime_path, account_runtime)
                        break
                    usage_limit_backoff = _parse_usage_limit_backoff_seconds(
                        completed.stderr,
                        DEFAULT_USAGE_LIMIT_BACKOFF_SECONDS,
                        now=now,
                    )
                    if usage_limit_backoff is not None:
                        until = now + dt.timedelta(seconds=usage_limit_backoff)
                        reset_at = _parse_usage_limit_reset_at(completed.stderr)
                        message = (
                            f"usage-limited until {_iso(reset_at)}"
                            if reset_at is not None
                            else f"usage-limited; recheck at {_iso(until)}"
                        )
                        _set_source_backoff(account_runtime, account, backoff_until=until, last_error=message)
                        _write_account_runtime(account_runtime_path, account_runtime)
                        break
                    backend_unavailable = _parse_backend_unavailable_message(completed.stderr)
                    if backend_unavailable is not None:
                        until = now + dt.timedelta(seconds=DEFAULT_BACKEND_UNAVAILABLE_BACKOFF_SECONDS)
                        _set_source_backoff(account_runtime, account, backoff_until=until, last_error=backend_unavailable)
                        _write_account_runtime(account_runtime_path, account_runtime)
                        break
                    spark_backoff = (
                        _parse_spark_pool_backoff_seconds(completed.stderr, DEFAULT_SPARK_BACKOFF_SECONDS)
                        if candidate_model == SPARK_MODEL
                        else None
                    )
                    if spark_backoff is not None:
                        until = now + dt.timedelta(seconds=spark_backoff)
                        _set_source_backoff(
                            account_runtime,
                            account,
                            spark_backoff_until=until,
                            last_error=f"spark pool unavailable for {spark_backoff}s",
                        )
                        _write_account_runtime(account_runtime_path, account_runtime)
                        continue
                    unsupported_model = _parse_unsupported_chatgpt_model(completed.stderr)
                    if unsupported_model is not None:
                        continue
                    rate_limit_backoff = _parse_backoff_seconds(completed.stderr, DEFAULT_RATE_LIMIT_BACKOFF_SECONDS)
                    if rate_limit_backoff is not None:
                        until = now + dt.timedelta(seconds=rate_limit_backoff)
                        _set_source_backoff(
                            account_runtime,
                            account,
                            backoff_until=until,
                            last_error=f"rate limited for {rate_limit_backoff}s",
                        )
                        _write_account_runtime(account_runtime_path, account_runtime)
                        break
                    if not _retryable_worker_error(completed.stderr):
                        stop_retrying = True
                        break
                if completed is not None and completed.returncode == 0 and accepted:
                    break
                if stop_retrying:
                    break
        else:
            attempt_index = 0
            total_attempts = max(1, len(worker_lane_candidates) * len(model_candidates))
            stop_retrying = False
            for candidate_lane in worker_lane_candidates:
                worker_env = _prepare_direct_worker_environment(state_root, candidate_lane)
                lane_alias = f"lane:{candidate_lane}" if candidate_lane else "default"
                for candidate_model in model_candidates:
                    attempt_index += 1
                    worker_command = _default_worker_command(
                        worker_bin=args.worker_bin,
                        worker_lane=candidate_lane,
                        workspace_root=workspace_root,
                        scope_roots=context["scope_roots"],
                        run_dir=run_dir,
                        worker_model=candidate_model,
                    )
                    attempted_accounts.append(lane_alias)
                    attempted_models.append(candidate_model or "default")
                    selected_account_alias = lane_alias if candidate_lane else ""
                    stderr_handle.write(
                        f"[fleet-supervisor] attempt {attempt_index}/{total_attempts} "
                        f"account={lane_alias} lane={candidate_lane or 'default'} model={candidate_model or 'default'}\n"
                    )
                    stderr_handle.flush()
                    completed = subprocess.run(
                        worker_command,
                        input=prompt,
                        text=True,
                        capture_output=True,
                        cwd=str(workspace_root),
                        env=worker_env,
                        check=False,
                    )
                    if completed.stdout:
                        stdout_handle.write(completed.stdout)
                    if completed.stderr:
                        stderr_handle.write(completed.stderr)
                    stdout_handle.flush()
                    stderr_handle.flush()
                    final_message = _read_text(last_message_path).strip() if last_message_path.exists() else ""
                    parsed = _parse_final_message_sections(final_message)
                    accepted, acceptance_reason = _assess_worker_result(completed.returncode, final_message, parsed)
                    if completed.returncode == 0 and accepted:
                        break
                    if completed.returncode == 0:
                        stderr_handle.write(
                            f"[fleet-supervisor] rejected result account={lane_alias} "
                            f"lane={candidate_lane or 'default'} model={candidate_model or 'default'} reason={acceptance_reason}\n"
                        )
                        stderr_handle.flush()
                        if (
                            attempt_index >= total_attempts
                            or not _retryable_worker_rejection(acceptance_reason, completed.stderr)
                        ):
                            stop_retrying = True
                            break
                        continue
                    if attempt_index >= total_attempts or not _retryable_worker_error(completed.stderr):
                        stop_retrying = True
                        break
                if completed is not None and completed.returncode == 0 and accepted:
                    break
                if stop_retrying:
                    break
        if completed is None:
            stderr_handle.write("[fleet-supervisor] no eligible worker account/model attempts were runnable\n")
            stderr_handle.flush()
    if not final_message and last_message_path.exists():
        final_message = _read_text(last_message_path).strip()
        parsed = _parse_final_message_sections(final_message)
    if completed is not None:
        accepted, acceptance_reason = _assess_worker_result(completed.returncode, final_message, parsed)
    finished_at = _iso_now()
    exit_code = int(completed.returncode) if completed is not None else 1
    return WorkerRun(
        run_id=run_id,
        started_at=started_at,
        finished_at=finished_at,
        worker_command=worker_command,
        attempted_accounts=attempted_accounts,
        attempted_models=attempted_models,
        selected_account_alias=selected_account_alias,
        worker_exit_code=exit_code,
        frontier_ids=[item.id for item in frontier],
        open_milestone_ids=[item.id for item in open_milestones],
        primary_milestone_id=(frontier[0].id if frontier else None),
        prompt_path=str(prompt_path),
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
        last_message_path=str(last_message_path),
        final_message=final_message,
        shipped=parsed.get("shipped", ""),
        remains=parsed.get("remains", ""),
        blocker=parsed.get("blocker", ""),
        accepted=accepted,
        acceptance_reason=acceptance_reason,
    )


def _run_payload(run: WorkerRun) -> Dict[str, Any]:
    return asdict(run)


def _write_state(
    state_root: Path,
    *,
    mode: str,
    run: Optional[WorkerRun],
    open_milestones: Iterable[Milestone],
    frontier: Iterable[Milestone],
    focus_profiles: Sequence[str] = (),
    focus_owners: Sequence[str] = (),
    focus_texts: Sequence[str] = (),
    completion_audit: Optional[Dict[str, Any]] = None,
    eta: Optional[Dict[str, Any]] = None,
    completion_review_frontier_path: str = "",
    completion_review_frontier_mirror_path: str = "",
) -> None:
    payload: Dict[str, Any] = {
        "updated_at": _iso_now(),
        "mode": mode,
        "open_milestone_ids": [item.id for item in open_milestones],
        "frontier_ids": [item.id for item in frontier],
        "focus_profiles": list(focus_profiles),
        "focus_owners": list(focus_owners),
        "focus_texts": list(focus_texts),
    }
    if run is not None:
        payload["last_run"] = _run_payload(run)
    if completion_audit:
        payload["completion_audit"] = dict(completion_audit)
    if eta:
        payload["eta"] = dict(eta)
    if completion_review_frontier_path:
        payload["completion_review_frontier_path"] = str(completion_review_frontier_path)
    if completion_review_frontier_mirror_path:
        payload["completion_review_frontier_mirror_path"] = str(completion_review_frontier_mirror_path)
    _write_json(_state_payload_path(state_root), payload)
    if run is not None:
        _append_jsonl(_history_payload_path(state_root), payload["last_run"])


def _render_status(state: Dict[str, Any]) -> str:
    if not state:
        return "No supervisor state recorded."
    lines = [
        f"updated_at: {state.get('updated_at') or 'unknown'}",
        f"mode: {state.get('mode') or 'unknown'}",
        f"open_milestone_ids: {', '.join(str(value) for value in (state.get('open_milestone_ids') or [])) or 'none'}",
        f"frontier_ids: {', '.join(str(value) for value in (state.get('frontier_ids') or [])) or 'none'}",
        f"focus_profiles: {', '.join(str(value) for value in (state.get('focus_profiles') or [])) or 'none'}",
        f"focus_owners: {', '.join(str(value) for value in (state.get('focus_owners') or [])) or 'none'}",
        f"focus_texts: {', '.join(str(value) for value in (state.get('focus_texts') or [])) or 'none'}",
    ]
    completion_review_frontier_path = str(state.get("completion_review_frontier_path") or "").strip()
    if completion_review_frontier_path:
        lines.append(f"completion_review_frontier.path: {completion_review_frontier_path}")
    completion_review_frontier_mirror_path = str(state.get("completion_review_frontier_mirror_path") or "").strip()
    if completion_review_frontier_mirror_path:
        lines.append(f"completion_review_frontier.mirror_path: {completion_review_frontier_mirror_path}")
    eta = state.get("eta") or {}
    if isinstance(eta, dict) and eta:
        lines.extend(
            [
                f"eta.status: {eta.get('status') or 'unknown'}",
                f"eta.human: {eta.get('eta_human') or 'unknown'}",
                f"eta.confidence: {eta.get('eta_confidence') or 'unknown'}",
                f"eta.basis: {eta.get('basis') or 'unknown'}",
                f"eta.summary: {eta.get('summary') or 'none'}",
                f"eta.predicted_completion_at: {eta.get('predicted_completion_at') or 'unknown'}",
            ]
        )
        blocker_reason = str(eta.get("blocking_reason") or "").strip()
        if blocker_reason:
            lines.append(f"eta.blocking_reason: {blocker_reason}")
    run = state.get("last_run") or {}
    if isinstance(run, dict) and run:
        inferred_accepted = False
        inferred_reason = ""
        if _run_has_receipt_fields(run):
            inferred_accepted, inferred_reason = _run_receipt_status(run)
        accepted_value = run.get("accepted") if "accepted" in run else (inferred_accepted if _run_has_receipt_fields(run) else "unknown")
        acceptance_reason = str(run.get("acceptance_reason") or "").strip() or inferred_reason or "none"
        failure_hint = _failure_hint_for_run(run)
        lines.extend(
            [
                f"last_run.run_id: {run.get('run_id') or 'unknown'}",
                f"last_run.worker_exit_code: {run.get('worker_exit_code')}",
                f"last_run.account_alias: {run.get('selected_account_alias') or 'none'}",
                f"last_run.primary_milestone_id: {run.get('primary_milestone_id') or 'none'}",
                f"last_run.accepted: {accepted_value}",
                f"last_run.acceptance_reason: {acceptance_reason}",
                f"last_run.blocker: {run.get('blocker') or 'none'}",
                f"last_run.failure_hint: {failure_hint or 'none'}",
                f"last_run.last_message_path: {run.get('last_message_path') or ''}",
            ]
        )
    completion_audit = state.get("completion_audit") or {}
    if isinstance(completion_audit, dict) and completion_audit:
        lines.extend(
            [
                f"completion_audit.status: {completion_audit.get('status') or 'unknown'}",
                f"completion_audit.reason: {completion_audit.get('reason') or 'none'}",
            ]
        )
        journey_gate_audit = completion_audit.get("journey_gate_audit") or {}
        if isinstance(journey_gate_audit, dict) and journey_gate_audit:
            lines.extend(
                [
                    f"completion_audit.journey_gate_status: {journey_gate_audit.get('status') or 'unknown'}",
                    f"completion_audit.journey_gate_reason: {journey_gate_audit.get('reason') or 'none'}",
                ]
            )
        weekly_pulse_audit = completion_audit.get("weekly_pulse_audit") or {}
        if isinstance(weekly_pulse_audit, dict) and weekly_pulse_audit:
            lines.extend(
                [
                    f"completion_audit.weekly_pulse_status: {weekly_pulse_audit.get('status') or 'unknown'}",
                    f"completion_audit.weekly_pulse_reason: {weekly_pulse_audit.get('reason') or 'none'}",
                ]
            )
        repo_backlog_audit = completion_audit.get("repo_backlog_audit") or {}
        if isinstance(repo_backlog_audit, dict) and repo_backlog_audit:
            lines.extend(
                [
                    f"completion_audit.repo_backlog_status: {repo_backlog_audit.get('status') or 'unknown'}",
                    f"completion_audit.repo_backlog_reason: {repo_backlog_audit.get('reason') or 'none'}",
                    (
                        "completion_audit.repo_backlog_open_item_count: "
                        f"{repo_backlog_audit.get('open_item_count', 0)}"
                    ),
                    (
                        "completion_audit.repo_backlog_open_project_count: "
                        f"{repo_backlog_audit.get('open_project_count', 0)}"
                    ),
                ]
            )
        linux_gate_audit = completion_audit.get("linux_desktop_exit_gate_audit") or {}
        if isinstance(linux_gate_audit, dict) and linux_gate_audit:
            lines.extend(
                [
                    f"completion_audit.linux_gate_status: {linux_gate_audit.get('status') or 'unknown'}",
                    f"completion_audit.linux_gate_reason: {linux_gate_audit.get('reason') or 'none'}",
                    (
                        "completion_audit.linux_gate_snapshot_mode: "
                        f"{linux_gate_audit.get('source_snapshot_mode') or 'unknown'}"
                    ),
                    (
                        "completion_audit.linux_gate_snapshot_sha: "
                        f"{linux_gate_audit.get('source_snapshot_worktree_sha256') or 'none'}"
                    ),
                    (
                        "completion_audit.linux_gate_snapshot_finish_sha: "
                        f"{linux_gate_audit.get('source_snapshot_finish_worktree_sha256') or 'none'}"
                    ),
                    (
                        "completion_audit.linux_gate_snapshot_stable: "
                        f"{linux_gate_audit.get('source_snapshot_identity_stable') or False}"
                    ),
                    f"completion_audit.linux_gate_install_mode: {linux_gate_audit.get('primary_install_mode') or 'unknown'}",
                    (
                        "completion_audit.linux_gate_install_verification_status: "
                        f"{linux_gate_audit.get('primary_install_verification_status') or 'unknown'}"
                    ),
                    (
                        "completion_audit.linux_gate_install_verification_path: "
                        f"{linux_gate_audit.get('primary_install_verification_path') or 'none'}"
                    ),
                ]
            )
    shards = state.get("shards") or []
    if isinstance(shards, list) and shards:
        lines.append(f"shards: {len(shards)}")
        for shard in shards:
            if not isinstance(shard, dict):
                continue
            frontier_ids = ",".join(str(value) for value in (shard.get("frontier_ids") or [])) or "none"
            open_ids = ",".join(str(value) for value in (shard.get("open_milestone_ids") or [])) or "none"
            lines.append(
                " ".join(
                    [
                        f"shard.{shard.get('name') or 'unknown'}:",
                        f"updated_at={shard.get('updated_at') or 'unknown'}",
                        f"mode={shard.get('mode') or 'unknown'}",
                        f"open={open_ids}",
                        f"frontier={frontier_ids}",
                        f"eta={shard.get('eta_status') or 'unknown'}",
                        f"last_run={shard.get('last_run_id') or 'none'}",
                    ]
                )
            )
    return "\n".join(lines)


def _summarize_trace_value(value: Any, *, max_len: int = 72) -> str:
    text = " ".join(str(value or "").split()).strip()
    if not text:
        return "none"
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


def _resolve_run_artifact_path(raw_path: str) -> Path:
    path = Path(str(raw_path or "").strip()).expanduser()
    if path.exists() or not str(path):
        return path
    try:
        relative = path.relative_to(Path("/var/lib/codex-fleet"))
    except ValueError:
        return path
    return (DEFAULT_WORKSPACE_ROOT / "state" / relative).resolve()


def _run_final_message(run: Dict[str, Any]) -> str:
    inline = str(run.get("final_message") or "").strip()
    if inline:
        return inline
    message_raw = str(run.get("last_message_path") or "").strip()
    if not message_raw:
        return ""
    message_path = _resolve_run_artifact_path(message_raw)
    if not message_path.exists() or message_path.is_dir():
        return ""
    return _read_text(message_path).strip()


def _run_has_receipt_fields(run: Dict[str, Any]) -> bool:
    if "accepted" in run:
        return True
    if str(run.get("final_message") or "").strip():
        return True
    return bool(str(run.get("last_message_path") or "").strip())


def _run_receipt_status(run: Dict[str, Any]) -> tuple[bool, str]:
    accepted = run.get("accepted")
    if isinstance(accepted, bool):
        if accepted:
            if not any(str(run.get(key) or "").strip() for key in ("shipped", "remains", "blocker", "final_message")):
                return False, "accepted receipt is missing structured closeout content"
            return True, ""
        return False, str(run.get("acceptance_reason") or "").strip() or "worker result rejected"
    final_message = _run_final_message(run)
    parsed = _parse_final_message_sections(final_message)
    return _assess_worker_result(int(run.get("worker_exit_code") or 0), final_message, parsed)


def _completion_audit(history: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    audit: Dict[str, Any] = {
        "status": "pass",
        "reason": "recent supervisor history ends with a trusted structured worker receipt",
        "accepted_run_ids": [],
        "rejected_zero_exit_run_ids": [],
        "latest_run_id": "",
        "latest_run_reason": "",
        "history_limit": int(COMPLETION_AUDIT_HISTORY_LIMIT),
    }
    if not history:
        audit["status"] = "fail"
        audit["reason"] = "no supervisor run history recorded; explicit completion review is required"
        return audit
    latest_run = history[-1]
    latest_run_id = str(latest_run.get("run_id") or "unknown")
    latest_accepted = False
    latest_reason = ""
    for run in history:
        run_id = str(run.get("run_id") or "unknown")
        accepted, reason = _run_receipt_status(run)
        if accepted:
            audit["accepted_run_ids"].append(run_id)
        elif int(run.get("worker_exit_code") or 0) == 0:
            audit["rejected_zero_exit_run_ids"].append(run_id)
        if run is latest_run:
            latest_accepted = accepted
            latest_reason = reason
    audit["latest_run_id"] = latest_run_id
    audit["latest_run_reason"] = latest_reason
    if not latest_accepted:
        audit["status"] = "fail"
        audit["reason"] = (
            f"latest worker receipt {latest_run_id} is not trusted: {latest_reason or 'missing structured closeout'}"
        )
        return audit
    if audit["rejected_zero_exit_run_ids"]:
        audit["status"] = "fail"
        audit["reason"] = (
            "recent zero-exit worker receipts were rejected: "
            + ", ".join(str(item) for item in audit["rejected_zero_exit_run_ids"][:5])
        )
        return audit
    if not audit["accepted_run_ids"]:
        audit["status"] = "fail"
        audit["reason"] = "no accepted structured worker receipts recorded in recent supervisor history"
    return audit


def _synthetic_completion_receipt_audit(
    receipt_audit: Dict[str, Any],
    journey_gate_audit: Dict[str, Any],
    linux_desktop_exit_gate_audit: Dict[str, Any],
    weekly_pulse_audit: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    if str(receipt_audit.get("status") or "").strip().lower() == "pass":
        return dict(receipt_audit)
    supporting_audits = (journey_gate_audit, linux_desktop_exit_gate_audit, weekly_pulse_audit)
    if any(str(audit.get("status") or "").strip().lower() != "pass" for audit in supporting_audits):
        return None
    latest_reason = _normalize_blocker(
        str(receipt_audit.get("latest_run_reason") or receipt_audit.get("reason") or "")
    )
    normalized_reason = latest_reason.lower()
    if not latest_reason or not any(signal in normalized_reason for signal in ETA_EXTERNAL_BLOCKER_SIGNALS):
        return None
    synthetic_audit = dict(receipt_audit)
    accepted_run_ids = list(synthetic_audit.get("accepted_run_ids") or [])
    latest_run_id = str(synthetic_audit.get("latest_run_id") or "").strip()
    synthetic_run_id = f"synthetic:{latest_run_id or 'completion-evidence'}"
    if synthetic_run_id not in accepted_run_ids:
        accepted_run_ids.append(synthetic_run_id)
    synthetic_audit.update(
        {
            "status": "pass",
            "reason": (
                "current repo-local completion proof is green; "
                f"using a supervisor evidence receipt because the latest worker failure is external: {latest_reason}"
            ),
            "accepted_run_ids": accepted_run_ids,
            "synthetic": True,
            "synthetic_receipt": {
                "shipped": "whole-product completion proof refreshed from current repo-local evidence",
                "remains": "none",
                "blocker": latest_reason,
            },
        }
    )
    return synthetic_audit


def _load_project_cfgs(projects_dir: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not projects_dir.exists() or not projects_dir.is_dir():
        return rows
    for path in sorted(projects_dir.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        payload = _read_yaml(path)
        if not payload:
            continue
        payload = dict(payload)
        payload["_config_path"] = str(path)
        rows.append(payload)
    return rows


def _project_repo_owner(project_cfg: Dict[str, Any]) -> str:
    review = dict(project_cfg.get("review") or {})
    repo = str(review.get("repo") or "").strip()
    if repo:
        return repo
    project_path = str(project_cfg.get("path") or "").strip()
    if project_path:
        return Path(project_path).name
    return str(project_cfg.get("id") or "").strip()


def _project_effective_queue(project_cfg: Dict[str, Any]) -> List[str]:
    queue = [str(item).strip() for item in (project_cfg.get("queue") or []) if str(item).strip()]
    readiness = _load_readiness_module()
    for source_cfg in project_cfg.get("queue_sources") or []:
        if not isinstance(source_cfg, dict):
            continue
        queue = [
            str(item).strip()
            for item in readiness._apply_queue_source(project_cfg, queue, source_cfg)
            if str(item).strip()
        ]
    deduped: List[str] = []
    seen: set[str] = set()
    for item in queue:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _repo_backlog_audit(args: argparse.Namespace) -> Dict[str, Any]:
    audit: Dict[str, Any] = {
        "status": "pass",
        "reason": "no active repo-local queue items remain outside the design registry",
        "open_item_count": 0,
        "open_project_count": 0,
        "open_items": [],
    }
    rows: List[Dict[str, Any]] = []
    for project_cfg in _load_project_cfgs(Path(args.projects_dir).resolve()):
        if project_cfg.get("enabled") is False:
            continue
        project_id = str(project_cfg.get("id") or "").strip()
        if not project_id:
            continue
        queue_items = _project_effective_queue(project_cfg)
        if not queue_items:
            continue
        repo_slug = _project_repo_owner(project_cfg)
        queue_source_path = ""
        for source_cfg in project_cfg.get("queue_sources") or []:
            if not isinstance(source_cfg, dict):
                continue
            source_path = str(source_cfg.get("path") or "").strip()
            if source_path:
                queue_source_path = source_path
                break
        for task in queue_items:
            rows.append(
                {
                    "project_id": project_id,
                    "repo_slug": repo_slug,
                    "task": task,
                    "queue_source_path": queue_source_path,
                }
            )
    if not rows:
        return audit
    audit["status"] = "fail"
    audit["open_items"] = rows[:25]
    audit["open_item_count"] = len(rows)
    audit["open_project_count"] = len(
        {
            (str(row.get("project_id") or "").strip(), str(row.get("repo_slug") or "").strip())
            for row in rows
        }
    )
    project_labels: List[str] = []
    for row in rows:
        label = str(row.get("project_id") or row.get("repo_slug") or "").strip()
        if label and label not in project_labels:
            project_labels.append(label)
    audit["reason"] = (
        "active repo-local backlog remains outside the closed design registry: "
        + ", ".join(project_labels[:5])
    )
    return audit


def _journey_gate_audit(args: argparse.Namespace) -> Dict[str, Any]:
    audit: Dict[str, Any] = {
        "status": "pass",
        "reason": "golden journey release proof is ready on current repo-local evidence",
        "overall_state": "ready",
        "generated_at": "",
        "source_registry_path": "",
        "blocked_journeys": [],
        "warning_journeys": [],
    }
    try:
        module = _load_sibling_module("materialize_journey_gates")
        registry_override = str(getattr(args, "journey_gates_path", "") or "").strip() or None
        payload = module.build_payload(
            registry_path=module.resolve_registry_path(registry_override),
            status_plane_path=Path(args.status_plane_path).resolve(),
            progress_report_path=Path(args.progress_report_path).resolve(),
            progress_history_path=Path(args.progress_history_path).resolve(),
            support_packets_path=Path(args.support_packets_path).resolve(),
        )
    except Exception as exc:
        audit["status"] = "fail"
        audit["overall_state"] = "error"
        audit["reason"] = f"golden journey audit could not run: {exc}"
        return audit

    summary = dict(payload.get("summary") or {})
    overall_state = str(summary.get("overall_state") or "unknown").strip()
    audit["overall_state"] = overall_state
    audit["generated_at"] = str(payload.get("generated_at") or "").strip()
    audit["source_registry_path"] = str(payload.get("source_registry_path") or "").strip()
    journeys = [dict(row) for row in (payload.get("journeys") or []) if isinstance(row, dict)]
    audit["blocked_journeys"] = [row for row in journeys if str(row.get("state") or "").strip() == "blocked"]
    audit["warning_journeys"] = [row for row in journeys if str(row.get("state") or "").strip() == "warning"]
    if overall_state != "ready":
        audit["status"] = "fail"
        reason = str(summary.get("recommended_action") or "").strip()
        if not reason:
            reason = f"golden journey release proof is {overall_state}"
        audit["reason"] = reason
    return audit


def _weekly_pulse_audit(args: argparse.Namespace) -> Dict[str, Any]:
    path = Path(args.weekly_pulse_path).resolve()
    audit: Dict[str, Any] = {
        "status": "pass",
        "reason": "weekly product pulse is fresh and reports no remaining drift or blocker pressure",
        "path": str(path),
        "generated_at": "",
        "as_of": "",
        "active_wave": "",
        "active_wave_status": "",
        "release_health_state": "",
        "journey_gate_health_state": "",
        "design_drift_count": 0,
        "public_promise_drift_count": 0,
        "oldest_blocker_days": 0,
    }
    if not path.is_file():
        audit["status"] = "fail"
        audit["reason"] = f"weekly product pulse is missing: {path}"
        return audit
    payload = _read_state(path)
    if not payload:
        audit["status"] = "fail"
        audit["reason"] = f"weekly product pulse could not be read: {path}"
        return audit
    generated_at = str(payload.get("generated_at") or "").strip()
    audit["generated_at"] = generated_at
    audit["as_of"] = str(payload.get("as_of") or "").strip()
    audit["active_wave"] = str(payload.get("active_wave") or "").strip()
    audit["active_wave_status"] = str(payload.get("active_wave_status") or "").strip()
    audit["journey_gate_health_state"] = str((payload.get("journey_gate_health") or {}).get("state") or "").strip()
    snapshot = dict(payload.get("snapshot") or {})
    release_health = dict(snapshot.get("release_health") or {})
    audit["release_health_state"] = str(release_health.get("state") or "").strip()
    audit["design_drift_count"] = _coerce_int(snapshot.get("design_drift_count"), 0)
    audit["public_promise_drift_count"] = _coerce_int(snapshot.get("public_promise_drift_count"), 0)
    audit["oldest_blocker_days"] = _coerce_int(snapshot.get("oldest_blocker_days"), 0)

    generated_at_dt = _parse_iso(generated_at)
    if generated_at_dt is None:
        audit["status"] = "fail"
        audit["reason"] = "weekly product pulse is missing a valid generated_at timestamp"
        return audit
    age_seconds = max(0, int((_utc_now() - generated_at_dt).total_seconds()))
    audit["age_seconds"] = age_seconds
    if age_seconds > WEEKLY_PULSE_MAX_AGE_SECONDS:
        audit["status"] = "fail"
        audit["reason"] = f"weekly product pulse is stale ({age_seconds}s old)"
        return audit
    if str(audit["active_wave_status"]).strip().lower() not in DONE_STATUSES:
        audit["status"] = "fail"
        audit["reason"] = (
            f"weekly product pulse still reports the active wave as {audit['active_wave_status'] or 'unknown'}"
        )
        return audit
    if str(audit["journey_gate_health_state"]).strip().lower() != "ready":
        audit["status"] = "fail"
        audit["reason"] = (
            f"weekly product pulse reports journey gate health as {audit['journey_gate_health_state'] or 'unknown'}"
        )
        return audit
    if str(audit["release_health_state"]).strip().lower() not in {"green", "green_or_explained", "ready"}:
        audit["status"] = "fail"
        audit["reason"] = (
            f"weekly product pulse reports release health as {audit['release_health_state'] or 'unknown'}"
        )
        return audit
    if audit["design_drift_count"] > 0:
        audit["status"] = "fail"
        audit["reason"] = f"weekly product pulse still reports design_drift_count={audit['design_drift_count']}"
        return audit
    if audit["public_promise_drift_count"] > 0:
        audit["status"] = "fail"
        audit["reason"] = (
            "weekly product pulse still reports "
            f"public_promise_drift_count={audit['public_promise_drift_count']}"
        )
        return audit
    if audit["oldest_blocker_days"] > 0:
        audit["status"] = "fail"
        audit["reason"] = f"weekly product pulse still reports oldest_blocker_days={audit['oldest_blocker_days']}"
        return audit
    return audit


def _repo_git_state(
    repo_root: Path,
    *,
    exclude_paths: Sequence[Path] = (),
    include_markers: Sequence[str] = (),
) -> Dict[str, Any]:
    state: Dict[str, Any] = {
        "repo_root": str(repo_root),
        "available": False,
        "head": "",
        "tracked_diff_sha256": "",
        "tracked_diff_line_count": 0,
    }
    if not repo_root.exists():
        return state
    try:
        head = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        listing = subprocess.run(
            ["git", "-C", str(repo_root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            check=True,
            capture_output=True,
        ).stdout.decode("utf-8", errors="surrogateescape")
    except Exception:
        return state
    exclude_markers: List[str] = []
    for candidate in exclude_paths:
        try:
            relative = candidate.resolve().relative_to(repo_root.resolve())
        except Exception:
            continue
        marker = relative.as_posix().rstrip("/")
        if marker:
            exclude_markers.append(marker)
    def collect_entries(apply_include_markers: bool) -> List[str]:
        entries: List[str] = []
        seen: Set[str] = set()
        for raw_item in listing.split("\0"):
            relative = raw_item.strip()
            if not relative or relative in seen:
                continue
            if any(relative == marker or relative.startswith(f"{marker}/") for marker in exclude_markers):
                continue
            if apply_include_markers and include_markers and not any(
                relative.startswith(marker) if marker.endswith("/") else relative == marker
                for marker in include_markers
            ):
                continue
            seen.add(relative)
            entries.append(relative)
        entries.sort()
        return entries

    entries = collect_entries(True)
    if include_markers and not entries:
        entries = collect_entries(False)
    digest = hashlib.sha256()
    entry_count = 0
    for relative in entries:
        path = repo_root / relative
        try:
            stat_result = os.lstat(path)
        except FileNotFoundError:
            digest.update(f"missing\0{relative}\0".encode("utf-8"))
            entry_count += 1
            continue
        mode = stat.S_IMODE(stat_result.st_mode)
        if stat.S_ISLNK(stat_result.st_mode):
            digest.update(f"symlink\0{relative}\0{mode:o}\0{os.readlink(path)}\0".encode("utf-8"))
            entry_count += 1
            continue
        if not stat.S_ISREG(stat_result.st_mode):
            continue
        digest.update(f"file\0{relative}\0{mode:o}\0".encode("utf-8"))
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        digest.update(b"\0")
        entry_count += 1
    state.update(
        {
            "available": True,
            "head": head,
            "tracked_diff_sha256": digest.hexdigest(),
            "tracked_diff_line_count": entry_count,
        }
    )
    return state


def _path_within(path: Optional[Path], root: Path) -> bool:
    if path is None:
        return False
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def _sha256_file(path: Path) -> str:
    if not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _trx_summary(path: Path) -> Dict[str, int]:
    summary = {"total": 0, "passed": 0, "failed": 0, "skipped": 0}
    if not path.is_file():
        return summary
    try:
        root = ET.fromstring(_read_text(path))
    except ET.ParseError:
        return summary
    counters = None
    for element in root.iter():
        if element.tag.endswith("Counters"):
            counters = element
            break
    if counters is None:
        return summary
    for key in summary:
        raw = counters.attrib.get(key)
        try:
            summary[key] = int(raw) if raw is not None else 0
        except ValueError:
            summary[key] = 0
    return summary


def _trx_assemblies(path: Path) -> List[str]:
    if not path.is_file():
        return []
    try:
        root = ET.fromstring(_read_text(path))
    except ET.ParseError:
        return []
    assemblies: List[str] = []
    seen: Set[str] = set()
    for element in root.iter():
        if not element.tag.endswith("UnitTest"):
            continue
        storage = Path(str(element.attrib.get("storage") or "").strip()).name
        if storage and storage not in seen:
            assemblies.append(storage)
            seen.add(storage)
        for child in element:
            if not child.tag.endswith("TestMethod"):
                continue
            code_base = Path(str(child.attrib.get("codeBase") or "").strip()).name
            if code_base and code_base not in seen:
                assemblies.append(code_base)
                seen.add(code_base)
    return assemblies


def _rid_arch(rid: str) -> str:
    rid_text = str(rid or "").strip().lower()
    if rid_text.endswith("-x64"):
        return "x64"
    if rid_text.endswith("-arm64"):
        return "arm64"
    if rid_text.endswith("-x86"):
        return "x86"
    return ""


def _rid_deb_arch(rid: str) -> str:
    rid_text = str(rid or "").strip().lower()
    if rid_text == "linux-x64":
        return "amd64"
    if rid_text == "linux-arm64":
        return "arm64"
    return ""


def _linux_desktop_exit_gate_audit(args: argparse.Namespace) -> Dict[str, Any]:
    path = Path(args.ui_linux_desktop_exit_gate_path).resolve()
    repo_root = Path(args.ui_linux_desktop_repo_root).resolve()
    expected_output_root = (repo_root / FLAGSHIP_UI_LINUX_OUTPUT_ROOT).resolve()
    audit: Dict[str, Any] = {
        "status": "pass",
        "reason": "linux desktop binary build/start/test proof is ready on current repo-local evidence",
        "path": str(path),
        "repo_root": str(repo_root),
        "generated_at": "",
        "age_seconds": 0,
        "proof_status": "",
        "stage": "",
        "head_id": "",
        "project_path": "",
        "launch_target": "",
        "ready_checkpoint": "",
        "platform": "",
        "rid": "",
        "run_root": "",
        "primary_package_kind": "",
        "fallback_package_kind": "",
        "binary_exists": False,
        "binary_executable": False,
        "binary_sha256": "",
        "installer_exists": False,
        "installer_sha256": "",
        "archive_exists": False,
        "archive_sha256": "",
        "primary_smoke_status": "",
        "fallback_smoke_status": "",
        "primary_install_mode": "",
        "primary_install_verification_path": "",
        "primary_install_verification_status": "",
        "primary_install_wrapper_sha256": "",
        "primary_install_desktop_entry_sha256": "",
        "unit_test_status": "",
        "unit_test_framework": "",
        "test_total": 0,
        "test_passed": 0,
        "test_failed": 0,
        "test_skipped": 0,
        "unit_test_assemblies": [],
        "proof_git_available": False,
        "proof_git_head": "",
        "proof_tracked_diff_sha256": "",
        "proof_git_start_head": "",
        "proof_git_start_tracked_diff_sha256": "",
        "proof_git_finish_head": "",
        "proof_git_finish_tracked_diff_sha256": "",
        "proof_git_identity_stable": False,
        "current_git_available": False,
        "current_git_head": "",
        "proof_git_head_matches_current": False,
        "current_tracked_diff_sha256": "",
        "source_snapshot_mode": "",
        "source_snapshot_root": "",
        "source_snapshot_worktree_sha256": "",
        "source_snapshot_finish_worktree_sha256": "",
        "source_snapshot_entry_count": 0,
        "source_snapshot_finish_entry_count": 0,
        "source_snapshot_identity_stable": False,
        "unit_test_project_path": "",
        "unit_test_trx_path": "",
    }
    if not path.is_file():
        audit["status"] = "fail"
        audit["reason"] = f"linux desktop binary build/start/test proof is missing: {path}"
        return audit
    payload = _read_state(path)
    if not payload:
        audit["status"] = "fail"
        audit["reason"] = f"linux desktop binary build/start/test proof could not be read: {path}"
        return audit
    contract_name = str(payload.get("contract_name") or "").strip()
    if contract_name != "chummer6-ui.linux_desktop_exit_gate":
        audit["status"] = "fail"
        audit["reason"] = f"linux desktop exit gate proof uses an unexpected contract: {contract_name or 'missing'}"
        return audit
    generated_at = str(payload.get("generated_at") or "").strip()
    audit["generated_at"] = generated_at
    generated_at_dt = _parse_iso(generated_at)
    if generated_at_dt is None:
        audit["status"] = "fail"
        audit["reason"] = "linux desktop exit gate proof is missing a valid generated_at timestamp"
        return audit
    audit["age_seconds"] = max(0, int((_utc_now() - generated_at_dt).total_seconds()))
    if audit["age_seconds"] > LINUX_DESKTOP_EXIT_GATE_MAX_AGE_SECONDS:
        audit["status"] = "fail"
        audit["reason"] = f"linux desktop exit gate proof is stale ({audit['age_seconds']}s old)"
        return audit
    audit["proof_status"] = str(payload.get("status") or "").strip()
    audit["stage"] = str(payload.get("stage") or "").strip()
    head = dict(payload.get("head") or {})
    build = dict(payload.get("build") or {})
    startup_smoke = dict(payload.get("startup_smoke") or {})
    primary_smoke = dict(startup_smoke.get("primary") or {})
    fallback_smoke = dict(startup_smoke.get("fallback") or {})
    unit_tests = dict(payload.get("unit_tests") or {})
    unit_test_summary = dict(unit_tests.get("summary") or {})
    proof_git = dict(payload.get("git") or {})
    proof_git_start = dict(proof_git.get("start") or {})
    proof_git_finish = dict(proof_git.get("finish") or {})
    source_snapshot = dict(payload.get("source_snapshot") or {})
    run_root_value = str(payload.get("run_root") or "").strip()
    run_root = Path(run_root_value).resolve() if run_root_value else None
    publish_dir = Path(str(build.get("publish_dir") or "")).resolve() if str(build.get("publish_dir") or "").strip() else None
    dist_dir = Path(str(build.get("dist_dir") or "")).resolve() if str(build.get("dist_dir") or "").strip() else None
    binary_path = Path(str(build.get("binary_path") or "")).resolve() if str(build.get("binary_path") or "").strip() else None
    installer_path = Path(str(build.get("installer_path") or "")).resolve() if str(build.get("installer_path") or "").strip() else None
    archive_path = Path(str(build.get("archive_path") or "")).resolve() if str(build.get("archive_path") or "").strip() else None
    primary_artifact_path = (
        Path(str(primary_smoke.get("artifact_path") or "")).resolve()
        if str(primary_smoke.get("artifact_path") or "").strip()
        else None
    )
    fallback_artifact_path = (
        Path(str(fallback_smoke.get("artifact_path") or "")).resolve()
        if str(fallback_smoke.get("artifact_path") or "").strip()
        else None
    )
    primary_receipt_path = (
        Path(str(primary_smoke.get("receipt_path") or "")).resolve()
        if str(primary_smoke.get("receipt_path") or "").strip()
        else None
    )
    fallback_receipt_path = (
        Path(str(fallback_smoke.get("receipt_path") or "")).resolve()
        if str(fallback_smoke.get("receipt_path") or "").strip()
        else None
    )
    test_results_dir = (
        Path(str(unit_tests.get("results_directory") or "")).resolve()
        if str(unit_tests.get("results_directory") or "").strip()
        else None
    )
    trx_path = Path(str(unit_tests.get("trx_path") or "")).resolve() if str(unit_tests.get("trx_path") or "").strip() else None
    exclude_paths = [path]
    if run_root:
        exclude_paths.append(run_root.parent)
    current_git = _repo_git_state(
        repo_root,
        exclude_paths=exclude_paths,
        include_markers=FLAGSHIP_UI_LINUX_GATE_INPUT_MARKERS,
    )
    primary_receipt_payload = _read_state(primary_receipt_path) if primary_receipt_path else {}
    fallback_receipt_payload = _read_state(fallback_receipt_path) if fallback_receipt_path else {}
    primary_install_verification_path = (
        Path(str(primary_receipt_payload.get("artifactInstallVerificationPath") or "")).resolve()
        if str(primary_receipt_payload.get("artifactInstallVerificationPath") or "").strip()
        else None
    )
    primary_install_verification = _read_state(primary_install_verification_path) if primary_install_verification_path else {}
    primary_install_launch_capture_path = (
        Path(str(primary_install_verification.get("installedLaunchCapturePath") or "")).resolve()
        if str(primary_install_verification.get("installedLaunchCapturePath") or "").strip()
        else None
    )
    primary_install_wrapper_capture_path = (
        Path(str(primary_install_verification.get("wrapperCapturePath") or "")).resolve()
        if str(primary_install_verification.get("wrapperCapturePath") or "").strip()
        else None
    )
    primary_install_desktop_capture_path = (
        Path(str(primary_install_verification.get("desktopEntryCapturePath") or "")).resolve()
        if str(primary_install_verification.get("desktopEntryCapturePath") or "").strip()
        else None
    )
    primary_dpkg_log_path = (
        Path(str(primary_install_verification.get("dpkgLogPath") or "")).resolve()
        if str(primary_install_verification.get("dpkgLogPath") or "").strip()
        else None
    )
    primary_dpkg_log_text = _read_text(primary_dpkg_log_path) if primary_dpkg_log_path and primary_dpkg_log_path.is_file() else ""
    primary_install_launch_capture_sha = _sha256_file(primary_install_launch_capture_path) if primary_install_launch_capture_path else ""
    primary_install_wrapper_capture_sha = _sha256_file(primary_install_wrapper_capture_path) if primary_install_wrapper_capture_path else ""
    primary_install_desktop_capture_sha = _sha256_file(primary_install_desktop_capture_path) if primary_install_desktop_capture_path else ""
    primary_install_wrapper_capture_text = (
        _read_text(primary_install_wrapper_capture_path) if primary_install_wrapper_capture_path and primary_install_wrapper_capture_path.is_file() else ""
    )
    primary_install_desktop_capture_text = (
        _read_text(primary_install_desktop_capture_path) if primary_install_desktop_capture_path and primary_install_desktop_capture_path.is_file() else ""
    )
    trx_summary = _trx_summary(trx_path) if trx_path else {"total": 0, "passed": 0, "failed": 0, "skipped": 0}
    trx_assemblies = _trx_assemblies(trx_path) if trx_path else []
    expected_arch = _rid_arch(str(head.get("rid") or ""))
    expected_deb_arch = _rid_deb_arch(str(head.get("rid") or ""))
    binary_sha256 = _sha256_file(binary_path) if binary_path else ""
    installer_sha256 = _sha256_file(installer_path) if installer_path else ""
    archive_sha256 = _sha256_file(archive_path) if archive_path else ""
    primary_expected_digest = f"sha256:{installer_sha256}" if installer_sha256 else ""
    fallback_expected_digest = f"sha256:{archive_sha256}" if archive_sha256 else ""
    expected_wrapper_content = (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f'exec "/opt/chummer6/{FLAGSHIP_UI_APP_KEY}-{str(head.get("rid") or "").strip()}/{FLAGSHIP_UI_LAUNCH_TARGET}" "$@"\n'
    )
    expected_desktop_entry_content = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={FLAGSHIP_UI_LINUX_DESKTOP_ENTRY_NAME}\n"
        f"Exec=/usr/bin/{FLAGSHIP_UI_LINUX_WRAPPER_NAME}\n"
        "Terminal=false\n"
        "Categories=Game;\n"
        "StartupNotify=true\n"
    )

    audit["head_id"] = str(head.get("app_key") or "").strip()
    audit["project_path"] = str(head.get("project_path") or "").strip()
    audit["launch_target"] = str(head.get("launch_target") or "").strip()
    audit["ready_checkpoint"] = str(head.get("ready_checkpoint") or "").strip()
    audit["platform"] = str(head.get("platform") or "").strip()
    audit["rid"] = str(head.get("rid") or "").strip()
    audit["run_root"] = str(run_root) if run_root else ""
    audit["primary_package_kind"] = str(build.get("primary_package_kind") or "").strip()
    audit["fallback_package_kind"] = str(build.get("fallback_package_kind") or "").strip()
    audit["binary_exists"] = bool(binary_path and binary_path.is_file())
    audit["binary_executable"] = bool(binary_path and binary_path.is_file() and os.access(binary_path, os.X_OK))
    audit["binary_sha256"] = binary_sha256
    audit["installer_exists"] = bool(installer_path and installer_path.is_file())
    audit["installer_sha256"] = installer_sha256
    audit["archive_exists"] = bool(archive_path and archive_path.is_file())
    audit["archive_sha256"] = archive_sha256
    audit["primary_install_mode"] = str(primary_receipt_payload.get("artifactInstallMode") or "").strip()
    audit["primary_install_verification_path"] = str(primary_install_verification_path) if primary_install_verification_path else ""
    audit["primary_install_wrapper_sha256"] = str(primary_install_verification.get("wrapperSha256") or "").strip()
    audit["primary_install_desktop_entry_sha256"] = str(primary_install_verification.get("desktopEntrySha256") or "").strip()
    audit["unit_test_framework"] = str(unit_tests.get("framework") or "").strip()
    audit["unit_test_project_path"] = str(unit_tests.get("project_path") or "").strip()
    audit["unit_test_trx_path"] = str(trx_path) if trx_path else ""
    audit["unit_test_assemblies"] = trx_assemblies
    audit["test_total"] = trx_summary["total"]
    audit["test_passed"] = trx_summary["passed"]
    audit["test_failed"] = trx_summary["failed"]
    audit["test_skipped"] = trx_summary["skipped"]
    audit["proof_git_available"] = bool(proof_git.get("available"))
    audit["proof_git_head"] = str(proof_git.get("head") or "").strip()
    audit["proof_tracked_diff_sha256"] = str(proof_git.get("tracked_diff_sha256") or "").strip()
    audit["proof_git_start_head"] = str(proof_git_start.get("head") or "").strip()
    audit["proof_git_start_tracked_diff_sha256"] = str(proof_git_start.get("tracked_diff_sha256") or "").strip()
    audit["proof_git_finish_head"] = str(proof_git_finish.get("head") or "").strip()
    audit["proof_git_finish_tracked_diff_sha256"] = str(proof_git_finish.get("tracked_diff_sha256") or "").strip()
    audit["proof_git_identity_stable"] = bool(proof_git.get("identity_stable"))
    audit["current_git_available"] = bool(current_git.get("available"))
    audit["current_git_head"] = str(current_git.get("head") or "").strip()
    audit["proof_git_head_matches_current"] = bool(audit["proof_git_head"]) and audit["proof_git_head"] == audit["current_git_head"]
    audit["current_tracked_diff_sha256"] = str(current_git.get("tracked_diff_sha256") or "").strip()
    audit["source_snapshot_mode"] = str(source_snapshot.get("mode") or "").strip()
    audit["source_snapshot_root"] = str(source_snapshot.get("snapshot_root") or "").strip()
    audit["source_snapshot_worktree_sha256"] = str(source_snapshot.get("worktree_sha256") or "").strip()
    audit["source_snapshot_finish_worktree_sha256"] = str(source_snapshot.get("finish_worktree_sha256") or "").strip()
    audit["source_snapshot_entry_count"] = _coerce_int(source_snapshot.get("entry_count"), 0)
    audit["source_snapshot_finish_entry_count"] = _coerce_int(source_snapshot.get("finish_entry_count"), 0)
    audit["source_snapshot_identity_stable"] = bool(source_snapshot.get("identity_stable"))
    audit["primary_install_verification_status"] = (
        "passed"
        if primary_install_verification
        and audit["primary_install_mode"] == "dpkg_rootless_install"
        and primary_install_verification_path
        and _path_within(primary_install_verification_path, run_root or repo_root)
        and primary_dpkg_log_path
        and _path_within(primary_dpkg_log_path, run_root or repo_root)
        and primary_install_launch_capture_path
        and _path_within(primary_install_launch_capture_path, run_root or repo_root)
        and primary_install_wrapper_capture_path
        and _path_within(primary_install_wrapper_capture_path, run_root or repo_root)
        and primary_install_desktop_capture_path
        and _path_within(primary_install_desktop_capture_path, run_root or repo_root)
        and str(primary_install_verification.get("mode") or "").strip() == "dpkg_rootless_install"
        and str(primary_install_verification.get("packageName") or "").strip() == FLAGSHIP_UI_LINUX_DEB_PACKAGE_NAME
        and (not expected_deb_arch or str(primary_install_verification.get("packageArch") or "").strip() == expected_deb_arch)
        and str(primary_install_verification.get("statusAfterInstall") or "").strip() == "install ok installed"
        and str(primary_install_verification.get("statusAfterPurge") or "").strip() == "not-installed"
        and bool(primary_install_verification.get("installedLaunchPathExistsAfterInstall"))
        and bool(primary_install_verification.get("wrapperExistsAfterInstall"))
        and bool(primary_install_verification.get("desktopEntryExistsAfterInstall"))
        and not bool(primary_install_verification.get("installedLaunchPathExistsAfterPurge"))
        and not bool(primary_install_verification.get("wrapperExistsAfterPurge"))
        and not bool(primary_install_verification.get("desktopEntryExistsAfterPurge"))
        and str(primary_install_verification.get("installedLaunchPath") or "").strip().endswith(
            f"/opt/chummer6/{FLAGSHIP_UI_APP_KEY}-{audit['rid']}/{FLAGSHIP_UI_LAUNCH_TARGET}"
        )
        and str(primary_install_verification.get("installedLaunchPathSha256") or "").strip() == primary_install_launch_capture_sha
        and str(primary_install_verification.get("wrapperPath") or "").strip().endswith(f"/usr/bin/{FLAGSHIP_UI_LINUX_WRAPPER_NAME}")
        and str(primary_install_verification.get("wrapperSha256") or "").strip() == primary_install_wrapper_capture_sha
        and str(primary_install_verification.get("wrapperContent") or "") == primary_install_wrapper_capture_text
        and primary_install_wrapper_capture_text == expected_wrapper_content
        and str(primary_install_verification.get("desktopEntryPath") or "").strip().endswith(
            f"/usr/share/applications/chummer6-{FLAGSHIP_UI_APP_KEY}.desktop"
        )
        and str(primary_install_verification.get("desktopEntrySha256") or "").strip() == primary_install_desktop_capture_sha
        and str(primary_install_verification.get("desktopEntryContent") or "") == primary_install_desktop_capture_text
        and primary_install_desktop_capture_text == expected_desktop_entry_content
        and f"install {FLAGSHIP_UI_LINUX_DEB_PACKAGE_NAME}:{expected_deb_arch or ''}".strip(":") in primary_dpkg_log_text
        and f"status installed {FLAGSHIP_UI_LINUX_DEB_PACKAGE_NAME}:{expected_deb_arch or ''}".strip(":") in primary_dpkg_log_text
        and f"remove {FLAGSHIP_UI_LINUX_DEB_PACKAGE_NAME}:{expected_deb_arch or ''}".strip(":") in primary_dpkg_log_text
        and f"status not-installed {FLAGSHIP_UI_LINUX_DEB_PACKAGE_NAME}:{expected_deb_arch or ''}".strip(":") in primary_dpkg_log_text
        else ("missing" if not primary_install_verification_path else "invalid")
    )
    audit["primary_smoke_status"] = (
        "passed"
        if primary_receipt_payload
        and primary_artifact_path == installer_path
        and str(primary_smoke.get("package_kind") or "").strip() == "deb"
        and str(primary_smoke.get("status") or "").strip() == "passed"
        and str(primary_receipt_payload.get("headId") or "").strip() == FLAGSHIP_UI_APP_KEY
        and str(primary_receipt_payload.get("platform") or "").strip() == "linux"
        and (not expected_arch or str(primary_receipt_payload.get("arch") or "").strip() == expected_arch)
        and str(primary_receipt_payload.get("readyCheckpoint") or "").strip() == FLAGSHIP_UI_READY_CHECKPOINT
        and Path(str(primary_receipt_payload.get("processPath") or "").strip()).name == FLAGSHIP_UI_LAUNCH_TARGET
        and str(primary_receipt_payload.get("channelId") or "").strip() == str(head.get("channel") or "").strip()
        and str(primary_receipt_payload.get("version") or "").strip() == str(head.get("version") or "").strip()
        and str(primary_receipt_payload.get("artifactDigest") or "").strip() == primary_expected_digest
        and audit["primary_install_verification_status"] == "passed"
        else ("missing" if not (primary_receipt_path and primary_receipt_path.is_file()) else "invalid")
    )
    audit["fallback_smoke_status"] = (
        "passed"
        if fallback_receipt_payload
        and fallback_artifact_path == archive_path
        and str(fallback_smoke.get("package_kind") or "").strip() == "archive"
        and str(fallback_smoke.get("status") or "").strip() == "passed"
        and str(fallback_receipt_payload.get("headId") or "").strip() == FLAGSHIP_UI_APP_KEY
        and str(fallback_receipt_payload.get("platform") or "").strip() == "linux"
        and (not expected_arch or str(fallback_receipt_payload.get("arch") or "").strip() == expected_arch)
        and str(fallback_receipt_payload.get("readyCheckpoint") or "").strip() == FLAGSHIP_UI_READY_CHECKPOINT
        and Path(str(fallback_receipt_payload.get("processPath") or "").strip()).name == FLAGSHIP_UI_LAUNCH_TARGET
        and str(fallback_receipt_payload.get("channelId") or "").strip() == str(head.get("channel") or "").strip()
        and str(fallback_receipt_payload.get("version") or "").strip() == str(head.get("version") or "").strip()
        and str(fallback_receipt_payload.get("artifactDigest") or "").strip() == fallback_expected_digest
        else ("missing" if not (fallback_receipt_path and fallback_receipt_path.is_file()) else "invalid")
    )
    audit["unit_test_status"] = (
        "passed"
        if trx_path
        and trx_path.is_file()
        and str(unit_tests.get("status") or "").strip() == "passed"
        and audit["unit_test_framework"] == "net10.0"
        and trx_summary["failed"] == 0
        and trx_summary["total"] > 0
        and FLAGSHIP_UI_LINUX_TEST_ASSEMBLY_NAME in trx_assemblies
        else (
            "missing"
            if not (trx_path and trx_path.is_file())
            else ("invalid" if FLAGSHIP_UI_LINUX_TEST_ASSEMBLY_NAME not in trx_assemblies else "failed")
        )
    )

    if audit["proof_status"] != "passed":
        audit["status"] = "fail"
        audit["reason"] = str(payload.get("reason") or "linux desktop exit gate proof did not pass")
        return audit
    if audit["stage"] != "complete":
        audit["status"] = "fail"
        audit["reason"] = f"linux desktop exit gate proof ended at stage={audit['stage'] or 'unknown'}"
        return audit
    if audit["head_id"] != FLAGSHIP_UI_APP_KEY or audit["launch_target"] != FLAGSHIP_UI_LAUNCH_TARGET:
        audit["status"] = "fail"
        audit["reason"] = (
            "linux desktop exit gate proof does not target the flagship Avalonia head "
            f"({audit['head_id'] or 'unknown'} / {audit['launch_target'] or 'unknown'})"
        )
        return audit
    if audit["project_path"] != FLAGSHIP_UI_PROJECT_PATH:
        audit["status"] = "fail"
        audit["reason"] = (
            "linux desktop exit gate proof used the wrong flagship project path "
            f"({audit['project_path'] or 'unknown'})"
        )
        return audit
    if audit["ready_checkpoint"] != FLAGSHIP_UI_READY_CHECKPOINT:
        audit["status"] = "fail"
        audit["reason"] = (
            "linux desktop exit gate proof used the wrong readiness checkpoint "
            f"({audit['ready_checkpoint'] or 'unknown'})"
        )
        return audit
    if audit["platform"] != "linux" or not audit["rid"].startswith("linux-"):
        audit["status"] = "fail"
        audit["reason"] = (
            f"linux desktop exit gate proof targets {audit['platform'] or 'unknown'} {audit['rid'] or 'unknown'} instead of linux"
        )
        return audit
    if not run_root or not run_root.is_dir():
        audit["status"] = "fail"
        audit["reason"] = "linux desktop exit gate proof is missing a valid run_root"
        return audit
    if not _path_within(run_root, expected_output_root):
        audit["status"] = "fail"
        audit["reason"] = "linux desktop exit gate proof points outside the canonical output root"
        return audit
    if audit["source_snapshot_mode"] != "filesystem_copy" or not audit["source_snapshot_root"]:
        audit["status"] = "fail"
        audit["reason"] = "linux desktop exit gate proof is missing immutable source-snapshot metadata"
        return audit
    if audit["source_snapshot_entry_count"] <= 0 or not audit["source_snapshot_worktree_sha256"]:
        audit["status"] = "fail"
        audit["reason"] = "linux desktop exit gate proof source snapshot is empty or missing its worktree fingerprint"
        return audit
    if (
        audit["source_snapshot_finish_entry_count"] <= 0
        or not audit["source_snapshot_finish_worktree_sha256"]
        or not audit["source_snapshot_identity_stable"]
    ):
        audit["status"] = "fail"
        audit["reason"] = "linux desktop exit gate proof source snapshot did not stay stable through the full run"
        return audit
    if (
        audit["source_snapshot_entry_count"] != audit["source_snapshot_finish_entry_count"]
        or audit["source_snapshot_worktree_sha256"] != audit["source_snapshot_finish_worktree_sha256"]
    ):
        audit["status"] = "fail"
        audit["reason"] = "linux desktop exit gate proof source snapshot finish fingerprint does not match the initial snapshot"
        return audit
    for candidate, label in (
        (publish_dir, "publish_dir"),
        (dist_dir, "dist_dir"),
        (test_results_dir, "results_directory"),
        (binary_path, "binary_path"),
        (installer_path, "installer_path"),
        (archive_path, "archive_path"),
        (primary_receipt_path, "primary receipt"),
        (fallback_receipt_path, "fallback receipt"),
        (trx_path, "unit-test trx"),
    ):
        if not _path_within(candidate, run_root):
            audit["status"] = "fail"
            audit["reason"] = f"linux desktop exit gate proof points {label} outside the gate run_root"
            return audit
    if audit["unit_test_project_path"] != FLAGSHIP_UI_LINUX_TEST_PROJECT_PATH:
        audit["status"] = "fail"
        audit["reason"] = (
            "linux desktop exit gate proof used the wrong unit-test project "
            f"({audit['unit_test_project_path'] or 'unknown'})"
        )
        return audit
    if audit["unit_test_framework"] != "net10.0":
        audit["status"] = "fail"
        audit["reason"] = (
            "linux desktop exit gate proof used the wrong unit-test target framework "
            f"({audit['unit_test_framework'] or 'unknown'})"
        )
        return audit
    if str(unit_tests.get("assembly_name") or "").strip() != FLAGSHIP_UI_LINUX_TEST_ASSEMBLY_NAME:
        audit["status"] = "fail"
        audit["reason"] = (
            "linux desktop exit gate proof used the wrong unit-test assembly "
            f"({str(unit_tests.get('assembly_name') or '').strip() or 'unknown'})"
        )
        return audit
    if audit["current_git_available"]:
        if not audit["proof_git_available"]:
            audit["status"] = "fail"
            audit["reason"] = "linux desktop exit gate proof is missing tracked git-state metadata"
            return audit
        if not audit["proof_git_start_head"] or not audit["proof_git_finish_head"]:
            audit["status"] = "fail"
            audit["reason"] = "linux desktop exit gate proof is missing start/finish git snapshots"
            return audit
        if not audit["proof_git_identity_stable"]:
            audit["status"] = "fail"
            audit["reason"] = "linux desktop exit gate repo changed while the proof run was executing"
            return audit
        if (
            audit["proof_git_head"] != audit["proof_git_finish_head"]
            or audit["proof_tracked_diff_sha256"] != audit["proof_git_finish_tracked_diff_sha256"]
            or audit["proof_git_start_head"] != audit["proof_git_finish_head"]
            or audit["proof_git_start_tracked_diff_sha256"] != audit["proof_git_finish_tracked_diff_sha256"]
        ):
            audit["status"] = "fail"
            audit["reason"] = "linux desktop exit gate proof recorded inconsistent git snapshots"
            return audit
        if audit["proof_tracked_diff_sha256"] != audit["current_tracked_diff_sha256"]:
            audit["status"] = "fail"
            audit["reason"] = "linux desktop exit gate proof no longer matches the current tracked UI worktree state"
            return audit
        if (
            audit["source_snapshot_worktree_sha256"] != audit["proof_tracked_diff_sha256"]
            or audit["source_snapshot_worktree_sha256"] != audit["proof_git_start_tracked_diff_sha256"]
            or audit["source_snapshot_worktree_sha256"] != audit["proof_git_finish_tracked_diff_sha256"]
            or audit["source_snapshot_finish_worktree_sha256"] != audit["proof_tracked_diff_sha256"]
            or audit["source_snapshot_finish_worktree_sha256"] != audit["proof_git_start_tracked_diff_sha256"]
            or audit["source_snapshot_finish_worktree_sha256"] != audit["proof_git_finish_tracked_diff_sha256"]
        ):
            audit["status"] = "fail"
            audit["reason"] = "linux desktop exit gate proof source snapshot does not match the recorded git worktree fingerprint"
            return audit
    if audit["primary_package_kind"] != "deb":
        audit["status"] = "fail"
        audit["reason"] = (
            f"linux desktop exit gate proof reports primary_package_kind={audit['primary_package_kind'] or 'unknown'}"
        )
        return audit
    if audit["fallback_package_kind"] != "archive":
        audit["status"] = "fail"
        audit["reason"] = (
            f"linux desktop exit gate proof reports fallback_package_kind={audit['fallback_package_kind'] or 'unknown'}"
        )
        return audit
    if not bool(build.get("self_contained")) or not bool(build.get("single_file")):
        audit["status"] = "fail"
        audit["reason"] = "linux desktop exit gate proof did not record a self-contained single-file Linux publish"
        return audit
    if not audit["binary_exists"]:
        audit["status"] = "fail"
        audit["reason"] = "linux desktop exit gate did not record a built Linux desktop binary"
        return audit
    if not audit["binary_executable"]:
        audit["status"] = "fail"
        audit["reason"] = "linux desktop exit gate binary is not executable on disk"
        return audit
    if not audit["installer_exists"]:
        audit["status"] = "fail"
        audit["reason"] = "linux desktop exit gate did not record a built Linux .deb installer"
        return audit
    if not audit["archive_exists"]:
        audit["status"] = "fail"
        audit["reason"] = "linux desktop exit gate did not record a built Linux archive artifact"
        return audit
    if str(build.get("binary_sha256") or "").strip() != audit["binary_sha256"]:
        audit["status"] = "fail"
        audit["reason"] = "linux desktop exit gate proof binary digest does not match the built binary"
        return audit
    if str(build.get("installer_sha256") or "").strip() != audit["installer_sha256"]:
        audit["status"] = "fail"
        audit["reason"] = "linux desktop exit gate proof installer digest does not match the built installer"
        return audit
    if str(build.get("archive_sha256") or "").strip() != audit["archive_sha256"]:
        audit["status"] = "fail"
        audit["reason"] = "linux desktop exit gate proof archive digest does not match the built archive"
        return audit
    if audit["primary_install_verification_status"] != "passed":
        audit["status"] = "fail"
        audit["reason"] = (
            "linux desktop exit gate primary .deb install/remove verification is "
            f"{audit['primary_install_verification_status'] or 'unknown'}"
        )
        return audit
    if audit["primary_smoke_status"] != "passed":
        audit["status"] = "fail"
        audit["reason"] = (
            f"linux desktop exit gate primary startup smoke is {audit['primary_smoke_status'] or 'unknown'}"
        )
        return audit
    if audit["fallback_smoke_status"] != "passed":
        audit["status"] = "fail"
        audit["reason"] = (
            f"linux desktop exit gate fallback startup smoke is {audit['fallback_smoke_status'] or 'unknown'}"
        )
        return audit
    if audit["unit_test_status"] != "passed":
        audit["status"] = "fail"
        audit["reason"] = f"linux desktop exit gate unit-test status is {audit['unit_test_status'] or 'unknown'}"
        return audit
    for key, label in (
        ("total", "total"),
        ("passed", "passed"),
        ("failed", "failed"),
        ("skipped", "skipped"),
    ):
        raw_value = unit_test_summary.get(key)
        if raw_value in (None, ""):
            continue
        try:
            expected_value = int(raw_value)
        except (TypeError, ValueError):
            audit["status"] = "fail"
            audit["reason"] = f"linux desktop exit gate proof carries a non-numeric unit-test {label} count"
            return audit
        if expected_value != trx_summary[key]:
            audit["status"] = "fail"
            audit["reason"] = f"linux desktop exit gate proof unit-test {label} count does not match the TRX"
            return audit
    if audit["test_total"] <= 0:
        audit["status"] = "fail"
        audit["reason"] = "linux desktop exit gate recorded no executed unit tests"
        return audit
    if audit["test_failed"] > 0:
        audit["status"] = "fail"
        audit["reason"] = f"linux desktop exit gate recorded failed unit tests: {audit['test_failed']}"
        return audit
    return audit


def _design_completion_audit(args: argparse.Namespace, history: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    receipt_audit = _completion_audit(history)
    journey_gate_audit = _journey_gate_audit(args)
    linux_desktop_exit_gate_audit = _linux_desktop_exit_gate_audit(args)
    weekly_pulse_audit = _weekly_pulse_audit(args)
    repo_backlog_audit = _repo_backlog_audit(args)
    synthetic_receipt_audit = _synthetic_completion_receipt_audit(
        receipt_audit,
        journey_gate_audit,
        linux_desktop_exit_gate_audit,
        weekly_pulse_audit,
    )
    if repo_backlog_audit.get("status") == "fail":
        synthetic_receipt_audit = None
    if synthetic_receipt_audit is not None:
        receipt_audit = synthetic_receipt_audit
    audit: Dict[str, Any] = {
        "status": "pass",
        "reason": "trusted completion receipt plus whole-product release proof and Linux desktop exit gate are ready",
        "receipt_audit": receipt_audit,
        "journey_gate_audit": journey_gate_audit,
        "linux_desktop_exit_gate_audit": linux_desktop_exit_gate_audit,
        "weekly_pulse_audit": weekly_pulse_audit,
        "repo_backlog_audit": repo_backlog_audit,
    }
    if receipt_audit.get("status") != "pass":
        audit.update(
            {
                "status": "fail",
                "reason": str(receipt_audit.get("reason") or "receipt audit failed"),
            }
        )
        audit.update(receipt_audit)
        return audit

    if journey_gate_audit.get("status") != "pass":
        audit["status"] = "fail"
        audit["reason"] = str(journey_gate_audit.get("reason") or "golden journey audit failed")
        return audit
    if linux_desktop_exit_gate_audit.get("status") != "pass":
        audit["status"] = "fail"
        audit["reason"] = str(
            linux_desktop_exit_gate_audit.get("reason") or "linux desktop exit gate audit failed"
        )
        return audit
    if weekly_pulse_audit.get("status") != "pass":
        audit["status"] = "fail"
        audit["reason"] = str(weekly_pulse_audit.get("reason") or "weekly product pulse audit failed")
        return audit
    if repo_backlog_audit.get("status") != "pass":
        audit["status"] = "fail"
        audit["reason"] = str(repo_backlog_audit.get("reason") or "repo-local backlog audit failed")
        return audit

    audit.update(receipt_audit)
    return audit


def _failure_hint_for_run(run: Dict[str, Any]) -> str:
    accepted = run.get("accepted")
    acceptance_reason = str(run.get("acceptance_reason") or "").strip()
    if accepted is False and acceptance_reason:
        return acceptance_reason
    if int(run.get("worker_exit_code") or 0) == 0 and _run_has_receipt_fields(run):
        inferred_accepted, inferred_reason = _run_receipt_status(run)
        if not inferred_accepted and inferred_reason:
            return inferred_reason
    blocker = _normalize_blocker(str(run.get("blocker") or ""))
    if blocker and blocker.lower() not in BLOCKER_CLEAR_VALUES:
        return blocker
    stderr_raw = str(run.get("stderr_path") or "").strip()
    if not stderr_raw:
        return ""
    stderr_path = _resolve_run_artifact_path(stderr_raw)
    if not stderr_path.exists() or stderr_path.is_dir():
        return ""
    lines = [line.strip() for line in _read_text(stderr_path).splitlines() if line.strip()]
    if not lines:
        return ""
    for line in reversed(lines):
        marker_index = line.find("ERROR:")
        if marker_index >= 0:
            return _summarize_trace_value(line[marker_index:], max_len=96)
    return _summarize_trace_value(lines[-1], max_len=96)


def _render_trace(state: Dict[str, Any], history: List[Dict[str, Any]]) -> str:
    status_text = _render_status(state)
    if not history:
        return f"{status_text}\ntrace: none"
    lines = [status_text, "trace:"]
    for run in reversed(history):
        finished_at = str(run.get("finished_at") or run.get("started_at") or "unknown")
        frontier_ids = ",".join(str(value) for value in (run.get("frontier_ids") or [])) or "none"
        shipped = _summarize_trace_value(run.get("shipped"))
        remains = _summarize_trace_value(run.get("remains"))
        blocker = _summarize_trace_value(run.get("blocker"), max_len=40)
        if _run_has_receipt_fields(run):
            inferred_accepted, _ = _run_receipt_status(run)
            accepted_value: Any = run.get("accepted") if "accepted" in run else inferred_accepted
        else:
            accepted_value = "unknown"
        segments = [
            f"- {finished_at}",
            f"run={run.get('run_id') or 'unknown'}",
            f"shard={run.get('_shard') or 'none'}",
            f"exit={run.get('worker_exit_code')}",
            f"account={run.get('selected_account_alias') or 'none'}",
            f"primary={run.get('primary_milestone_id') or 'none'}",
            f"frontier={frontier_ids}",
            f"accepted={'yes' if accepted_value is True else 'no' if accepted_value is False else 'unknown'}",
            f"blocker={blocker}",
            f"shipped={shipped}",
            f"remains={remains}",
        ]
        failure_hint = _failure_hint_for_run(run)
        if failure_hint:
            segments.append(f"hint={failure_hint}")
        lines.append(" ".join(segments))
    return "\n".join(lines)


def run_once(args: argparse.Namespace) -> int:
    state_root = Path(args.state_root).resolve()
    _ensure_dir(state_root)
    context = derive_context(args)
    audit: Optional[Dict[str, Any]] = None
    history = _read_history(_history_payload_path(state_root), limit=ETA_HISTORY_LIMIT)
    if not context["open_milestones"]:
        completion_history = _completion_review_history(state_root, limit=ETA_HISTORY_LIMIT)
        audit = _design_completion_audit(args, completion_history[-COMPLETION_AUDIT_HISTORY_LIMIT:])
        if audit.get("status") != "pass":
            context = derive_completion_review_context(args, state_root, base_context=context, audit=audit)
        history = completion_history
    if args.command == "derive":
        print(context["prompt"])
        return 0
    if not context["open_milestones"] and not context["frontier"]:
        review_audit = audit or _design_completion_audit(args, history[-COMPLETION_AUDIT_HISTORY_LIMIT:])
        eta = _build_eta_snapshot(
            mode="complete",
            open_milestones=[],
            frontier=[],
            history=history,
            completion_audit=review_audit,
        )
        frontier_paths = _materialize_completion_review_frontier(
            args=args,
            state_root=state_root,
            mode="complete",
            frontier=[],
            focus_profiles=context["focus_profiles"],
            focus_owners=context["focus_owners"],
            focus_texts=context["focus_texts"],
            completion_audit=review_audit,
            eta=eta,
        )
        _write_state(
            state_root,
            mode="complete",
            run=None,
            open_milestones=[],
            frontier=[],
            focus_profiles=context["focus_profiles"],
            focus_owners=context["focus_owners"],
            focus_texts=context["focus_texts"],
            completion_audit=review_audit,
            eta=eta,
            completion_review_frontier_path=frontier_paths["published_path"],
            completion_review_frontier_mirror_path=frontier_paths["mirror_path"],
        )
        print("No open milestones remain in the active design registry.")
        return 0
    run = launch_worker(args, context, state_root)
    eta = _build_eta_snapshot(
        mode=("completion_review" if not context["open_milestones"] else "once"),
        open_milestones=context["open_milestones"],
        frontier=context["frontier"],
        history=history + [_run_payload(run)],
        completion_audit=(context.get("completion_audit") if not context["open_milestones"] else None),
    )
    frontier_paths = {
        "published_path": str(context.get("completion_review_frontier_path") or ""),
        "mirror_path": str(context.get("completion_review_frontier_mirror_path") or ""),
    }
    if not context["open_milestones"] and context.get("completion_audit"):
        frontier_paths = _materialize_completion_review_frontier(
            args=args,
            state_root=state_root,
            mode="completion_review",
            frontier=context["frontier"],
            focus_profiles=context["focus_profiles"],
            focus_owners=context["focus_owners"],
            focus_texts=context["focus_texts"],
            completion_audit=context["completion_audit"],
            eta=eta,
        )
    _write_state(
        state_root,
        mode=("completion_review" if not context["open_milestones"] else "once"),
        run=run,
        open_milestones=context["open_milestones"],
        frontier=context["frontier"],
        focus_profiles=context["focus_profiles"],
        focus_owners=context["focus_owners"],
        focus_texts=context["focus_texts"],
        completion_audit=(context.get("completion_audit") if not context["open_milestones"] else None),
        eta=eta,
        completion_review_frontier_path=frontier_paths["published_path"],
        completion_review_frontier_mirror_path=frontier_paths["mirror_path"],
    )
    if args.dry_run:
        print(json.dumps(_run_payload(run), indent=2, sort_keys=True))
        return 0
    return 0 if run.accepted else max(1, run.worker_exit_code)


def run_loop(args: argparse.Namespace) -> int:
    state_root = Path(args.state_root).resolve()
    _ensure_dir(state_root)
    lock_path = _lock_payload_path(state_root)
    try:
        _acquire_lock(lock_path, ttl_seconds=max(60.0, float(args.poll_seconds) * 4, LOCK_TTL_SECONDS / 2))
    except RuntimeError as exc:
        print(f"[fleet-supervisor] {exc}", flush=True)
        return 0
    run_count = 0
    last_idle_notice = ""
    try:
        while True:
            context = derive_context(args)
            open_milestones: List[Milestone] = context["open_milestones"]
            frontier: List[Milestone] = context["frontier"]
            history = _read_history(_history_payload_path(state_root), limit=ETA_HISTORY_LIMIT)
            if not open_milestones:
                history = _completion_review_history(state_root, limit=ETA_HISTORY_LIMIT)
                audit = _design_completion_audit(
                    args, history[-COMPLETION_AUDIT_HISTORY_LIMIT:]
                )
                if audit.get("status") == "pass":
                    eta = _build_eta_snapshot(
                        mode="complete",
                        open_milestones=[],
                        frontier=[],
                        history=history,
                        completion_audit=audit,
                    )
                    frontier_paths = _materialize_completion_review_frontier(
                        args=args,
                        state_root=state_root,
                        mode="complete",
                        frontier=[],
                        focus_profiles=context["focus_profiles"],
                        focus_owners=context["focus_owners"],
                        focus_texts=context["focus_texts"],
                        completion_audit=audit,
                        eta=eta,
                    )
                    _write_state(
                        state_root,
                        mode="complete",
                        run=None,
                        open_milestones=[],
                        frontier=[],
                        focus_profiles=context["focus_profiles"],
                        focus_owners=context["focus_owners"],
                        focus_texts=context["focus_texts"],
                        completion_audit=audit,
                        eta=eta,
                        completion_review_frontier_path=frontier_paths["published_path"],
                        completion_review_frontier_mirror_path=frontier_paths["mirror_path"],
                    )
                    notice = "[fleet-supervisor] no open milestones remain in the active design registry"
                    if notice != last_idle_notice:
                        print(notice, flush=True)
                        last_idle_notice = notice
                    if args.max_runs:
                        return 0
                    time.sleep(max(1.0, float(args.poll_seconds)))
                    continue
                context = derive_completion_review_context(args, state_root, base_context=context, audit=audit)
                frontier = context["frontier"]
                blocker_reason = _eta_external_blocker_reason(history, context.get("completion_audit"))
                if _should_defer_external_blocker_probe(state_root, blocker_reason=blocker_reason):
                    eta = _build_eta_snapshot(
                        mode="completion_review",
                        open_milestones=[],
                        frontier=frontier,
                        history=history,
                        completion_audit=context.get("completion_audit"),
                    )
                    frontier_paths = _materialize_completion_review_frontier(
                        args=args,
                        state_root=state_root,
                        mode="completion_review",
                        frontier=frontier,
                        focus_profiles=context["focus_profiles"],
                        focus_owners=context["focus_owners"],
                        focus_texts=context["focus_texts"],
                        completion_audit=context["completion_audit"],
                        eta=eta,
                    )
                    _write_state(
                        state_root,
                        mode="completion_review",
                        run=None,
                        open_milestones=[],
                        frontier=frontier,
                        focus_profiles=context["focus_profiles"],
                        focus_owners=context["focus_owners"],
                        focus_texts=context["focus_texts"],
                        completion_audit=context.get("completion_audit"),
                        eta=eta,
                        completion_review_frontier_path=frontier_paths["published_path"],
                        completion_review_frontier_mirror_path=frontier_paths["mirror_path"],
                    )
                    notice = (
                        "[fleet-supervisor] external blocker active in completion review; "
                        f"deferring probe to primary shard {(_primary_probe_shard_name(state_root) or 'unknown')}"
                    )
                    if notice != last_idle_notice:
                        print(notice, flush=True)
                        last_idle_notice = notice
                    time.sleep(
                        max(
                            1.0,
                            float(args.failure_backoff_seconds),
                            DEFAULT_EXTERNAL_BLOCKER_BACKOFF_SECONDS,
                        )
                    )
                    continue
            last_idle_notice = ""
            run = launch_worker(args, context, state_root)
            eta = _build_eta_snapshot(
                mode=("completion_review" if not open_milestones else "loop"),
                open_milestones=context["open_milestones"],
                frontier=frontier,
                history=history + [_run_payload(run)],
                completion_audit=(context.get("completion_audit") if not open_milestones else None),
            )
            frontier_paths = {
                "published_path": str(context.get("completion_review_frontier_path") or ""),
                "mirror_path": str(context.get("completion_review_frontier_mirror_path") or ""),
            }
            if not open_milestones and context.get("completion_audit"):
                frontier_paths = _materialize_completion_review_frontier(
                    args=args,
                    state_root=state_root,
                    mode="completion_review",
                    frontier=frontier,
                    focus_profiles=context["focus_profiles"],
                    focus_owners=context["focus_owners"],
                    focus_texts=context["focus_texts"],
                    completion_audit=context["completion_audit"],
                    eta=eta,
                )
            _write_state(
                state_root,
                mode=("completion_review" if not open_milestones else "loop"),
                run=run,
                open_milestones=context["open_milestones"],
                frontier=frontier,
                focus_profiles=context["focus_profiles"],
                focus_owners=context["focus_owners"],
                focus_texts=context["focus_texts"],
                completion_audit=(context.get("completion_audit") if not open_milestones else None),
                eta=eta,
                completion_review_frontier_path=frontier_paths["published_path"],
                completion_review_frontier_mirror_path=frontier_paths["mirror_path"],
            )
            run_count += 1
            blocker = _normalize_blocker(run.blocker).lower()
            if args.dry_run:
                print(json.dumps(_run_payload(run), indent=2, sort_keys=True))
                return 0
            if run.worker_exit_code != 0 or not run.accepted:
                failure_reason = run.acceptance_reason or f"worker exit {run.worker_exit_code}"
                print(f"[fleet-supervisor] worker result rejected: {failure_reason}; backing off", flush=True)
                backoff_seconds = max(1.0, float(args.failure_backoff_seconds))
                if _eta_external_blocker_reason(history + [_run_payload(run)], context.get("completion_audit")):
                    backoff_seconds = max(backoff_seconds, DEFAULT_EXTERNAL_BLOCKER_BACKOFF_SECONDS)
                time.sleep(backoff_seconds)
                if args.max_runs and run_count >= int(args.max_runs):
                    return max(1, run.worker_exit_code)
                continue
            if args.stop_on_blocker and blocker not in BLOCKER_CLEAR_VALUES:
                print(f"[fleet-supervisor] stopping on blocker: {run.blocker}", flush=True)
                return 0
            if args.max_runs and run_count >= int(args.max_runs):
                return 0
            time.sleep(max(1.0, float(args.cooldown_seconds or args.poll_seconds)))
    finally:
        _release_lock(lock_path)


def main() -> None:
    args = parse_args()
    if args.command == "status":
        state_root = Path(args.state_root).resolve()
        state, history = _effective_supervisor_state(state_root, history_limit=ETA_HISTORY_LIMIT)
        state, history = _live_state_with_current_completion_audit(args, state_root, state, history)
        if args.json:
            print(json.dumps(state, indent=2, sort_keys=True))
        else:
            print(_render_status(state))
        return
    if args.command == "eta":
        eta = derive_eta(args)
        if args.json:
            print(json.dumps(eta, indent=2, sort_keys=True))
        else:
            print(_render_eta(eta))
        return
    if args.command == "trace":
        state_root = Path(args.state_root).resolve()
        state, history = _effective_supervisor_state(state_root, history_limit=max(0, int(args.limit)))
        state, history = _live_state_with_current_completion_audit(args, state_root, state, history)
        if args.json:
            print(json.dumps({"state": state, "history": history}, indent=2, sort_keys=True))
        else:
            print(_render_trace(state, history))
        return
    if args.command in {"once", "derive"}:
        raise SystemExit(run_once(args))
    if args.command == "loop":
        raise SystemExit(run_loop(args))
    raise SystemExit(f"unsupported command: {args.command}")


if __name__ == "__main__":
    main()
