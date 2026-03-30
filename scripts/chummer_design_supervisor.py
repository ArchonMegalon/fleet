#!/usr/bin/env python3
"""Run a long-lived Chummer design supervisor from Fleet."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

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
DEFAULT_HANDOFF_PATH = DEFAULT_WORKSPACE_ROOT / "NEXT_SESSION_HANDOFF.md"
DEFAULT_STATE_ROOT = DEFAULT_WORKSPACE_ROOT / "state" / "chummer_design_supervisor"
DEFAULT_STATE_PATH = DEFAULT_STATE_ROOT / "state.json"
DEFAULT_HISTORY_PATH = DEFAULT_STATE_ROOT / "history.jsonl"
DEFAULT_RUNS_DIR = DEFAULT_STATE_ROOT / "runs"
DEFAULT_LOCK_PATH = DEFAULT_STATE_ROOT / "loop.lock"
DEFAULT_WORKER_BIN = "codex"
DEFAULT_MODEL = ""
DEFAULT_FALLBACK_MODELS = ("gpt-5.4",)
DEFAULT_ACCOUNT_OWNER_IDS = ("tibor.girschele", "the.girscheles", "archon.megalon")
DEFAULT_POLL_SECONDS = 20.0
DEFAULT_COOLDOWN_SECONDS = 5.0
DEFAULT_FAILURE_BACKOFF_SECONDS = 45.0
DEFAULT_RATE_LIMIT_BACKOFF_SECONDS = 60
DEFAULT_SPARK_BACKOFF_SECONDS = 900
DEFAULT_USAGE_LIMIT_BACKOFF_SECONDS = 21600
DEFAULT_AUTH_FAILURE_BACKOFF_SECONDS = 43200
DEFAULT_BACKEND_UNAVAILABLE_BACKOFF_SECONDS = 300
ACTIVE_STATUSES = {"in_progress", "not_started", "open", "planned", "queued"}
DONE_STATUSES = {"complete", "completed", "done", "closed", "released"}
BLOCKER_CLEAR_VALUES = {"", "none", "no", "n/a", "no blocker", "no exact blocker"}
CHATGPT_AUTH_KINDS = {"chatgpt_auth_json", "auth_json"}
READY_ACCOUNT_STATES = {"", "ready", "unknown", "ok"}
SPARK_MODEL = "gpt-5.3-codex-spark"
RETRYABLE_WORKER_ERROR_SIGNALS = (
    "usage limit",
    "rate limit",
    "quota",
    "switch to another model",
    "not supported",
    "unsupported",
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
            "--fallback-worker-model",
            action="append",
            default=[],
            help="Optional fallback worker model when the current model returns a retryable quota/support error. Repeatable.",
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
    status_parser.add_argument(
        "--state-root",
        default=str(DEFAULT_STATE_ROOT),
        help=f"State directory for supervisor logs and state (default: {DEFAULT_STATE_ROOT}).",
    )
    status_parser.add_argument(
        "--json",
        action="store_true",
        help="Render status as JSON.",
    )

    trace_parser = subparsers.add_parser("trace", help="Render recent supervisor loop history.")
    trace_parser.add_argument(
        "--state-root",
        default=str(DEFAULT_STATE_ROOT),
        help=f"State directory for supervisor logs and state (default: {DEFAULT_STATE_ROOT}).",
    )
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
    return path.read_text(encoding="utf-8", errors="ignore")


def _read_yaml(path: Path) -> Dict[str, Any]:
    payload = yaml.safe_load(_read_text(path))
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


def _default_worker_command(
    *,
    worker_bin: str,
    workspace_root: Path,
    scope_roots: List[Path],
    run_dir: Path,
    worker_model: str,
) -> List[str]:
    command = [
        worker_bin,
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
    if worker_model:
        command[2:2] = ["-m", worker_model]
    for scope_root in scope_roots:
        if scope_root == workspace_root:
            continue
        command[2:2] = ["--add-dir", str(scope_root)]
    return command


def _worker_model_candidates(args: argparse.Namespace) -> List[str]:
    primary = str(args.worker_model or "").strip()
    configured_fallbacks = [str(item or "").strip() for item in (args.fallback_worker_model or []) if str(item or "").strip()]
    if configured_fallbacks:
        fallbacks = configured_fallbacks
    else:
        env_value = os.environ.get("CHUMMER_DESIGN_SUPERVISOR_FALLBACK_MODELS")
        if env_value is None:
            fallbacks = list(DEFAULT_FALLBACK_MODELS)
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


def _retryable_worker_error(stderr_text: str) -> bool:
    compact = " ".join(str(stderr_text or "").split()).strip().lower()
    return bool(compact) and any(signal in compact for signal in RETRYABLE_WORKER_ERROR_SIGNALS)


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
    account_candidates = _load_worker_accounts(args)
    account_runtime_path = _account_runtime_path(state_root)
    account_runtime = _read_account_runtime(account_runtime_path)
    worker_command = _default_worker_command(
        worker_bin=args.worker_bin,
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
        )
    workspace_root = Path(args.workspace_root).resolve()
    attempted_accounts: List[str] = []
    attempted_models: List[str] = []
    selected_account_alias = ""
    completed: subprocess.CompletedProcess[str] | None = None
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
                    if completed.returncode == 0:
                        _clear_source_backoff(account_runtime, account)
                        _write_account_runtime(account_runtime_path, account_runtime)
                        break
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
                if completed is not None and completed.returncode == 0:
                    break
                if stop_retrying:
                    break
        else:
            for index, candidate_model in enumerate(model_candidates, start=1):
                worker_command = _default_worker_command(
                    worker_bin=args.worker_bin,
                    workspace_root=workspace_root,
                    scope_roots=context["scope_roots"],
                    run_dir=run_dir,
                    worker_model=candidate_model,
                )
                attempted_accounts.append("default")
                attempted_models.append(candidate_model or "default")
                stderr_handle.write(
                    f"[fleet-supervisor] attempt {index}/{len(model_candidates)} account=default model={candidate_model or 'default'}\n"
                )
                stderr_handle.flush()
                completed = subprocess.run(
                    worker_command,
                    input=prompt,
                    text=True,
                    capture_output=True,
                    cwd=str(workspace_root),
                    check=False,
                )
                if completed.stdout:
                    stdout_handle.write(completed.stdout)
                if completed.stderr:
                    stderr_handle.write(completed.stderr)
                stdout_handle.flush()
                stderr_handle.flush()
                if completed.returncode == 0:
                    break
                if index >= len(model_candidates) or not _retryable_worker_error(completed.stderr):
                    break
        if completed is None:
            stderr_handle.write("[fleet-supervisor] no eligible worker account/model attempts were runnable\n")
            stderr_handle.flush()
    final_message = _read_text(last_message_path).strip() if last_message_path.exists() else ""
    parsed = _parse_final_message_sections(final_message)
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
    run = state.get("last_run") or {}
    if isinstance(run, dict) and run:
        failure_hint = _failure_hint_for_run(run)
        lines.extend(
            [
                f"last_run.run_id: {run.get('run_id') or 'unknown'}",
                f"last_run.worker_exit_code: {run.get('worker_exit_code')}",
                f"last_run.account_alias: {run.get('selected_account_alias') or 'none'}",
                f"last_run.primary_milestone_id: {run.get('primary_milestone_id') or 'none'}",
                f"last_run.blocker: {run.get('blocker') or 'none'}",
                f"last_run.failure_hint: {failure_hint or 'none'}",
                f"last_run.last_message_path: {run.get('last_message_path') or ''}",
            ]
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


def _failure_hint_for_run(run: Dict[str, Any]) -> str:
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
        segments = [
            f"- {finished_at}",
            f"run={run.get('run_id') or 'unknown'}",
            f"exit={run.get('worker_exit_code')}",
            f"account={run.get('selected_account_alias') or 'none'}",
            f"primary={run.get('primary_milestone_id') or 'none'}",
            f"frontier={frontier_ids}",
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
    if args.command == "derive":
        print(context["prompt"])
        return 0
    if not context["open_milestones"]:
        _write_state(
            state_root,
            mode="idle",
            run=None,
            open_milestones=[],
            frontier=[],
            focus_profiles=context["focus_profiles"],
            focus_owners=context["focus_owners"],
            focus_texts=context["focus_texts"],
        )
        print("No open milestones remain in the active design registry.")
        return 0
    run = launch_worker(args, context, state_root)
    _write_state(
        state_root,
        mode="once",
        run=run,
        open_milestones=context["open_milestones"],
        frontier=context["frontier"],
        focus_profiles=context["focus_profiles"],
        focus_owners=context["focus_owners"],
        focus_texts=context["focus_texts"],
    )
    if args.dry_run:
        print(json.dumps(_run_payload(run), indent=2, sort_keys=True))
        return 0
    return run.worker_exit_code


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
    try:
        while True:
            context = derive_context(args)
            open_milestones: List[Milestone] = context["open_milestones"]
            frontier: List[Milestone] = context["frontier"]
            if not open_milestones:
                _write_state(
                    state_root,
                    mode="complete",
                    run=None,
                    open_milestones=[],
                    frontier=[],
                    focus_profiles=context["focus_profiles"],
                    focus_owners=context["focus_owners"],
                    focus_texts=context["focus_texts"],
                )
                print("[fleet-supervisor] no open milestones remain in the active design registry", flush=True)
                return 0
            run = launch_worker(args, context, state_root)
            _write_state(
                state_root,
                mode="loop",
                run=run,
                open_milestones=open_milestones,
                frontier=frontier,
                focus_profiles=context["focus_profiles"],
                focus_owners=context["focus_owners"],
                focus_texts=context["focus_texts"],
            )
            run_count += 1
            blocker = _normalize_blocker(run.blocker).lower()
            if args.dry_run:
                print(json.dumps(_run_payload(run), indent=2, sort_keys=True))
                return 0
            if run.worker_exit_code != 0:
                print(f"[fleet-supervisor] worker exit {run.worker_exit_code}; backing off", flush=True)
                time.sleep(max(1.0, float(args.failure_backoff_seconds)))
                if args.max_runs and run_count >= int(args.max_runs):
                    return run.worker_exit_code
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
        state = _read_state(_state_payload_path(Path(args.state_root).resolve()))
        if args.json:
            print(json.dumps(state, indent=2, sort_keys=True))
        else:
            print(_render_status(state))
        return
    if args.command == "trace":
        state_root = Path(args.state_root).resolve()
        state = _read_state(_state_payload_path(state_root))
        history = _read_history(_history_payload_path(state_root), limit=max(0, int(args.limit)))
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
