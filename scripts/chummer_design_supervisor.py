#!/usr/bin/env python3
"""Run a long-lived Chummer design supervisor from Fleet."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import yaml


DEFAULT_WORKSPACE_ROOT = Path("/docker/fleet")
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
DEFAULT_POLL_SECONDS = 20.0
DEFAULT_COOLDOWN_SECONDS = 5.0
DEFAULT_FAILURE_BACKOFF_SECONDS = 45.0
ACTIVE_STATUSES = {"in_progress", "not_started", "open", "planned", "queued"}
DONE_STATUSES = {"complete", "completed", "done", "closed", "released"}
BLOCKER_CLEAR_VALUES = {"", "none", "no", "n/a", "no blocker", "no exact blocker"}
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


@dataclass(frozen=True)
class Milestone:
    id: int
    title: str
    wave: str
    status: str
    owners: List[str]
    exit_criteria: List[str]
    dependencies: List[int]


@dataclass
class WorkerRun:
    run_id: str
    started_at: str
    finished_at: str
    worker_command: List[str]
    attempted_models: List[str]
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


def _iso_now() -> str:
    return _utc_now().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _slug_timestamp(value: Optional[dt.datetime] = None) -> str:
    current = value or _utc_now()
    return current.strftime("%Y%m%dT%H%M%SZ")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _read_yaml(path: Path) -> Dict[str, Any]:
    payload = yaml.safe_load(_read_text(path))
    return dict(payload or {})


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


def build_worker_prompt(
    *,
    registry_path: Path,
    program_milestones_path: Path,
    roadmap_path: Path,
    handoff_path: Path,
    open_milestones: List[Milestone],
    frontier: List[Milestone],
    scope_roots: List[Path],
) -> str:
    frontier_text = "\n".join(f"- {_milestone_brief(item)}" for item in frontier) or "- none"
    open_text = "\n".join(f"- {_milestone_brief(item)}" for item in open_milestones[:15]) or "- none"
    scope_text = "\n".join(f"- {path}" for path in scope_roots)
    open_ids = ", ".join(str(item.id) for item in open_milestones) or "none"
    frontier_ids = ", ".join(str(item.id) for item in frontier) or "none"
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


def _is_lock_stale(raw: Dict[str, Any], now: dt.datetime, ttl_seconds: float) -> bool:
    created_raw = str(raw.get("created_at") or "").strip()
    pid = raw.get("pid")
    if not _pid_alive(pid):
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
            json.dump({"pid": os.getpid(), "created_at": now.isoformat()}, handle)
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
    prompt = build_worker_prompt(
        registry_path=registry_path,
        program_milestones_path=program_milestones_path,
        roadmap_path=roadmap_path,
        handoff_path=handoff_path,
        open_milestones=open_milestones,
        frontier=frontier,
        scope_roots=scope_roots,
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
        "prompt": prompt,
    }


def _write_run_artifacts(run_dir: Path, prompt: str) -> Path:
    _ensure_dir(run_dir)
    prompt_path = run_dir / "prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8")
    return prompt_path


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
            attempted_models=[item or "default" for item in model_candidates[:1]],
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
    attempted_models: List[str] = []
    completed: subprocess.CompletedProcess[str] | None = None
    with stdout_path.open("w", encoding="utf-8") as stdout_handle, stderr_path.open("w", encoding="utf-8") as stderr_handle:
        for index, candidate_model in enumerate(model_candidates, start=1):
            worker_command = _default_worker_command(
                worker_bin=args.worker_bin,
                workspace_root=Path(args.workspace_root).resolve(),
                scope_roots=context["scope_roots"],
                run_dir=run_dir,
                worker_model=candidate_model,
            )
            attempted_models.append(candidate_model or "default")
            stderr_handle.write(
                f"[fleet-supervisor] attempt {index}/{len(model_candidates)} model={candidate_model or 'default'}\n"
            )
            stderr_handle.flush()
            completed = subprocess.run(
                worker_command,
                input=prompt,
                text=True,
                capture_output=True,
                cwd=str(Path(args.workspace_root).resolve()),
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
    final_message = _read_text(last_message_path).strip() if last_message_path.exists() else ""
    parsed = _parse_final_message_sections(final_message)
    finished_at = _iso_now()
    exit_code = int(completed.returncode) if completed is not None else 1
    return WorkerRun(
        run_id=run_id,
        started_at=started_at,
        finished_at=finished_at,
        worker_command=worker_command,
        attempted_models=attempted_models,
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


def _write_state(state_root: Path, *, mode: str, run: Optional[WorkerRun], open_milestones: Iterable[Milestone], frontier: Iterable[Milestone]) -> None:
    payload: Dict[str, Any] = {
        "updated_at": _iso_now(),
        "mode": mode,
        "open_milestone_ids": [item.id for item in open_milestones],
        "frontier_ids": [item.id for item in frontier],
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
    ]
    run = state.get("last_run") or {}
    if isinstance(run, dict) and run:
        failure_hint = _failure_hint_for_run(run)
        lines.extend(
            [
                f"last_run.run_id: {run.get('run_id') or 'unknown'}",
                f"last_run.worker_exit_code: {run.get('worker_exit_code')}",
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


def _failure_hint_for_run(run: Dict[str, Any]) -> str:
    blocker = _normalize_blocker(str(run.get("blocker") or ""))
    if blocker and blocker.lower() not in BLOCKER_CLEAR_VALUES:
        return blocker
    stderr_raw = str(run.get("stderr_path") or "").strip()
    if not stderr_raw:
        return ""
    stderr_path = Path(stderr_raw).expanduser()
    if not stderr_path.exists() or stderr_path.is_dir():
        return ""
    lines = [line.strip() for line in _read_text(stderr_path).splitlines() if line.strip()]
    if not lines:
        return ""
    for line in reversed(lines):
        if line.startswith("ERROR:"):
            return _summarize_trace_value(line, max_len=96)
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
        _write_state(state_root, mode="idle", run=None, open_milestones=[], frontier=[])
        print("No open milestones remain in the active design registry.")
        return 0
    run = launch_worker(args, context, state_root)
    _write_state(
        state_root,
        mode="once",
        run=run,
        open_milestones=context["open_milestones"],
        frontier=context["frontier"],
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
                _write_state(state_root, mode="complete", run=None, open_milestones=[], frontier=[])
                print("[fleet-supervisor] no open milestones remain in the active design registry", flush=True)
                return 0
            run = launch_worker(args, context, state_root)
            _write_state(state_root, mode="loop", run=run, open_milestones=open_milestones, frontier=frontier)
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
