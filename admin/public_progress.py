from __future__ import annotations

import datetime as dt
import html
import json
import math
import os
import pathlib
import re
import sqlite3
import subprocess
import sys
from typing import Any, Callable, Dict, List, Optional, Sequence

import yaml


ADMIN_DIR = pathlib.Path(__file__).resolve().parent
FLEET_ROOT = ADMIN_DIR.parent
MOUNTED_ADMIN_DIR = pathlib.Path("/docker/fleet/admin")
if (MOUNTED_ADMIN_DIR / "readiness.py").exists() and str(MOUNTED_ADMIN_DIR) not in sys.path:
    sys.path.insert(0, str(MOUNTED_ADMIN_DIR))
if str(ADMIN_DIR) not in sys.path:
    sys.path.insert(0, str(ADMIN_DIR))

from readiness import _apply_queue_source, project_repo_slug, studio_compile_summary


UTC = dt.timezone.utc
PUBLIC_PROGRESS_CONTRACT_NAME = "fleet.public_progress_report"
PUBLIC_PROGRESS_CONTRACT_VERSION = "2026-03-23"
PUBLIC_PROGRESS_HISTORY_CONTRACT_NAME = "fleet.public_progress_history"
PUBLIC_PROGRESS_HISTORY_CONTRACT_VERSION = "2026-03-23"
CHUMMER_DESIGN_ROOT = pathlib.Path("/docker/chummercomplete/chummer-design")
CHUMMER_PRODUCT_CANON_DIR = CHUMMER_DESIGN_ROOT / "products" / "chummer"
CHUMMER_HUB_ROOT = pathlib.Path("/docker/chummercomplete/chummer6-hub")
CHUMMER_CORE_ROOT = pathlib.Path("/docker/chummercomplete/chummer6-core")


def _published_status(path: pathlib.Path) -> tuple[int, int]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return (0, 0)
    status = str(payload.get("status") or "").strip().lower()
    if status in {"pass", "passed", "ready"}:
        return (2, 1)
    if status in {"warning"}:
        return (1, 1)
    if status:
        return (-2, 1)
    return (0, 1)


def _ui_repo_candidate_score(candidate: pathlib.Path) -> tuple[int, int]:
    published_root = candidate / ".codex-studio" / "published"
    score = 0
    inspected = 0
    for name, weight in (
        ("DESKTOP_EXECUTABLE_EXIT_GATE.generated.json", 10),
        ("UI_LINUX_DESKTOP_EXIT_GATE.generated.json", 6),
        ("UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json", 6),
        ("CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json", 5),
        ("SR6_DESKTOP_WORKFLOW_PARITY.generated.json", 5),
        ("DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json", 4),
        ("DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json", 4),
        ("UI_FLAGSHIP_RELEASE_GATE.generated.json", 3),
    ):
        status_score, inspected_flag = _published_status(published_root / name)
        score += status_score * weight
        inspected += inspected_flag
    return score, inspected


def _ui_repo_candidates() -> tuple[pathlib.Path, ...]:
    return (
        pathlib.Path("/docker/chummercomplete/chummer-presentation-clean"),
        pathlib.Path("/docker/chummercomplete/chummer6-ui"),
        pathlib.Path("/docker/chummercomplete/chummer6-ui-finish"),
        pathlib.Path("/docker/chummercomplete/chummer-presentation"),
    )


def _ui_repo_required_gate_sort_key(candidate: pathlib.Path) -> tuple[int, float, int, float]:
    published_root = candidate / ".codex-studio" / "published"
    executable_status, _ = _published_status(published_root / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json")
    linux_status, _ = _published_status(published_root / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json")
    executable_mtime = 0.0
    linux_mtime = 0.0
    try:
        executable_mtime = (published_root / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json").stat().st_mtime
    except OSError:
        pass
    try:
        linux_mtime = (published_root / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json").stat().st_mtime
    except OSError:
        pass
    return executable_status, executable_mtime, linux_status, linux_mtime


def _preferred_chummer_ui_root() -> pathlib.Path:
    override = str(os.environ.get("CHUMMER_UI_REPO_ROOT", "") or "").strip()
    if override:
        return pathlib.Path(override)
    best_candidate: pathlib.Path | None = None
    best_score: tuple[int, float, int, float, int, int] | None = None
    for candidate in _ui_repo_candidates():
        if not candidate.exists():
            continue
        aggregate_score, inspected = _ui_repo_candidate_score(candidate)
        candidate_score = (*_ui_repo_required_gate_sort_key(candidate), aggregate_score, inspected)
        if best_candidate is None or candidate_score > (best_score or (0, 0.0, 0, 0.0, 0, 0)):
            best_candidate = candidate
            best_score = candidate_score
    if best_candidate is not None:
        return best_candidate
    return pathlib.Path("/docker/chummercomplete/chummer6-ui")


CHUMMER_UI_ROOT = _preferred_chummer_ui_root()

DEFAULT_PROGRESS_CONFIG_PATH = FLEET_ROOT / "config" / "public_progress_parts.yaml"
DEFAULT_PROGRAM_MILESTONES_PATH = FLEET_ROOT / "config" / "program_milestones.yaml"
DEFAULT_PROJECTS_DIR = FLEET_ROOT / "config" / "projects"
DEFAULT_PROGRESS_REPORT_PATH = FLEET_ROOT / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
DEFAULT_PROGRESS_HISTORY_PATH = FLEET_ROOT / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
DEFAULT_POSTER_PATH = (MOUNTED_ADMIN_DIR if MOUNTED_ADMIN_DIR.exists() else ADMIN_DIR) / "assets" / "progress_poster.svg"
DEFAULT_DB_PATH = pathlib.Path(os.environ.get("FLEET_DB_PATH", str(FLEET_ROOT / "state" / "fleet.db")))
DEFAULT_DESIGN_SUPERVISOR_STATE_PATH = FLEET_ROOT / "state" / "chummer_design_supervisor" / "state.json"
DEFAULT_HUB_PARTICIPATE_URL = "https://chummer.run/participate"
CANON_PROGRESS_CONFIG_PATH = CHUMMER_PRODUCT_CANON_DIR / "PUBLIC_PROGRESS_PARTS.yaml"
CANON_PROGRESS_REPORT_PATH = CHUMMER_PRODUCT_CANON_DIR / "PROGRESS_REPORT.generated.json"
CANON_PROGRESS_HISTORY_PATH = CHUMMER_PRODUCT_CANON_DIR / "PROGRESS_HISTORY.generated.json"
CANON_PROGRESS_HTML_PATH = CHUMMER_PRODUCT_CANON_DIR / "PROGRESS_REPORT.generated.html"
CANON_PROGRESS_POSTER_PATH = CHUMMER_PRODUCT_CANON_DIR / "PROGRESS_REPORT_POSTER.svg"
HUB_PROGRESS_MIRROR_DIR = CHUMMER_HUB_ROOT / ".codex-design" / "product"
HUB_PROGRESS_CONFIG_PATH = HUB_PROGRESS_MIRROR_DIR / "PUBLIC_PROGRESS_PARTS.yaml"
HUB_PROGRESS_REPORT_PATH = HUB_PROGRESS_MIRROR_DIR / "PROGRESS_REPORT.generated.json"
HUB_PROGRESS_HISTORY_PATH = HUB_PROGRESS_MIRROR_DIR / "PROGRESS_HISTORY.generated.json"
HUB_PROGRESS_HTML_PATH = HUB_PROGRESS_MIRROR_DIR / "PROGRESS_REPORT.generated.html"
HUB_PROGRESS_POSTER_PATH = HUB_PROGRESS_MIRROR_DIR / "PROGRESS_REPORT_POSTER.svg"
DEFAULT_IMPORT_PARITY_CERTIFICATION_PATH = CHUMMER_CORE_ROOT / ".codex-studio" / "published" / "IMPORT_PARITY_CERTIFICATION.generated.json"
DEFAULT_CHUMMER5A_DESKTOP_WORKFLOW_PARITY_PATH = CHUMMER_UI_ROOT / ".codex-studio" / "published" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
DEFAULT_SR4_DESKTOP_WORKFLOW_PARITY_PATH = CHUMMER_UI_ROOT / ".codex-studio" / "published" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
DEFAULT_SR6_DESKTOP_WORKFLOW_PARITY_PATH = CHUMMER_UI_ROOT / ".codex-studio" / "published" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
DEFAULT_DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE_PATH = CHUMMER_UI_ROOT / ".codex-studio" / "published" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
DEFAULT_DESKTOP_EXECUTABLE_EXIT_GATE_PATH = CHUMMER_UI_ROOT / ".codex-studio" / "published" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
NEXT20_REGISTRY_PATH = CHUMMER_PRODUCT_CANON_DIR / "NEXT_20_BIG_WINS_REGISTRY.yaml"
POST_AUDIT_NEXT20_REGISTRY_PATH = CHUMMER_PRODUCT_CANON_DIR / "POST_AUDIT_NEXT_20_BIG_WINS_REGISTRY.yaml"
NEXT12_REGISTRY_PATH = CHUMMER_PRODUCT_CANON_DIR / "NEXT_12_BIGGEST_WINS_REGISTRY.yaml"
ACTIVE_WAVE_REGISTRY_PATH = NEXT12_REGISTRY_PATH
LEGACY_ACTIVE_WAVE_REGISTRY_PATH = CHUMMER_PRODUCT_CANON_DIR / "NEXT_20_BIG_WINS_AFTER_POST_AUDIT_CLOSEOUT_REGISTRY.yaml"


def _same_path(left: pathlib.Path, right: pathlib.Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except Exception:
        return str(left) == str(right)


def progress_config_path(repo_root: pathlib.Path = FLEET_ROOT) -> pathlib.Path:
    local_path = repo_root / "config" / "public_progress_parts.yaml"
    if _same_path(repo_root, FLEET_ROOT) and CANON_PROGRESS_CONFIG_PATH.exists():
        return CANON_PROGRESS_CONFIG_PATH
    if local_path.exists():
        return local_path
    if CANON_PROGRESS_CONFIG_PATH.exists():
        return CANON_PROGRESS_CONFIG_PATH
    return local_path


def program_milestones_path(repo_root: pathlib.Path = FLEET_ROOT) -> pathlib.Path:
    local_path = repo_root / "config" / "program_milestones.yaml"
    if local_path.exists():
        return local_path
    return local_path


def progress_report_artifact_candidates(repo_root: pathlib.Path = FLEET_ROOT) -> List[pathlib.Path]:
    local_path = repo_root / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    candidates: List[pathlib.Path] = []
    if _same_path(repo_root, FLEET_ROOT):
        candidates.extend([local_path, CANON_PROGRESS_REPORT_PATH])
    else:
        candidates.extend([local_path, CANON_PROGRESS_REPORT_PATH])
    deduped: List[pathlib.Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(path)
    return deduped


def progress_history_artifact_candidates(repo_root: pathlib.Path = FLEET_ROOT) -> List[pathlib.Path]:
    local_path = repo_root / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    candidates: List[pathlib.Path] = []
    if _same_path(repo_root, FLEET_ROOT):
        candidates.extend([local_path, CANON_PROGRESS_HISTORY_PATH])
    else:
        candidates.append(local_path)
    deduped: List[pathlib.Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(path)
    return deduped


def progress_poster_path() -> pathlib.Path:
    if CANON_PROGRESS_POSTER_PATH.exists():
        return CANON_PROGRESS_POSTER_PATH
    return DEFAULT_POSTER_PATH


def _parse_date(value: Any) -> Optional[dt.date]:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return dt.date.fromisoformat(raw)
    except ValueError:
        return None


def _parse_eta_human_weeks(value: Any) -> tuple[int | None, int | None]:
    raw = str(value or "").strip().lower()
    if not raw:
        return (None, None)
    pieces = [piece.strip() for piece in raw.split("-", 1)]
    if not pieces:
        return (None, None)

    def _parse_piece(piece: str) -> float | None:
        match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([dhmw])?", piece.strip())
        if not match:
            return None
        value_number = float(match.group(1))
        unit = (match.group(2) or "w").strip().lower()
        if unit == "h":
            return value_number / (24.0 * 7.0)
        if unit == "d":
            return value_number / 7.0
        if unit in {"w", ""}:
            return value_number
        return None

    first = _parse_piece(pieces[0])
    second = _parse_piece(pieces[1]) if len(pieces) > 1 else first
    if first is None:
        return (None, None)
    if second is None:
        second = first
    low = min(first, second)
    high = max(first, second)
    return (int(math.ceil(max(0.0, low))), int(math.ceil(max(0.0, high))))


def _infer_supervisor_eta_scope(eta: Dict[str, Any]) -> tuple[str, str, str]:
    scope_kind = str(eta.get("scope_kind") or "").strip()
    scope_label = str(eta.get("scope_label") or "").strip()
    scope_warning = str(eta.get("scope_warning") or "").strip()
    if scope_kind:
        if scope_kind == "completion_review_recovery" and not (scope_label or scope_warning):
            return (
                "completion_review_recovery",
                "Completion review and proof recovery",
                "This ETA is not a full-product parity ETA unless flagship readiness is also green.",
            )
        if scope_kind == "flagship_product_readiness" and not scope_label:
            return (
                "flagship_product_readiness",
                "Full Chummer5A parity and flagship proof closeout",
                scope_warning,
            )
        if scope_kind == "repo_local_completion_ready" and not (scope_label or scope_warning):
            return (
                "repo_local_completion_ready",
                "Repo-local completion review",
                "Repo-local completion is not the same as final release or parity closure.",
            )
        if scope_kind == "open_milestone_frontier" and not (scope_label or scope_warning):
            return (
                "open_milestone_frontier",
                "Current open milestone frontier",
                "This is a tactical frontier ETA only, not a full-product parity ETA.",
            )
        if scope_kind == "aggregate_shard_mixed_scope" and not scope_label:
            return (
                "aggregate_shard_mixed_scope",
                "Aggregate multi-shard ETA",
                scope_warning,
            )
        return scope_kind, scope_label, scope_warning
    basis = str(eta.get("basis") or "").strip().lower()
    status = str(eta.get("status") or "").strip().lower()
    remaining_open = int(eta.get("remaining_open_milestones") or 0)
    if basis == "completion_review_recovery" or status == "recovery":
        return (
            "completion_review_recovery",
            "Completion review and proof recovery",
            "This ETA is not a full-product parity ETA unless flagship readiness is also green.",
        )
    if "full_product" in basis or status == "flagship_delivery":
        return (
            "flagship_product_readiness",
            "Full Chummer5A parity and flagship proof closeout",
            "",
        )
    if basis == "completion_audit_pass" or status == "ready":
        return (
            "repo_local_completion_ready",
            "Repo-local completion review",
            "Repo-local completion is not the same as final release or parity closure.",
        )
    if basis in {"empirical_open_milestone_burn", "heuristic_status_mix"} or remaining_open > 0:
        return (
            "open_milestone_frontier",
            "Current open milestone frontier",
            "This is a tactical frontier ETA only, not a full-product parity ETA.",
        )
    return ("unknown", "Unknown ETA scope", "")


def _design_supervisor_state_root(state_path: pathlib.Path) -> pathlib.Path:
    candidate = state_path.parent if state_path.name == "state.json" else state_path
    if candidate.name == "design-supervisor" and candidate.parent.name == "state":
        return candidate.parent / "chummer_design_supervisor"
    if candidate.name.startswith("shard-") or candidate.name.startswith("orphaned-shard-"):
        if candidate.parent.name == "design-supervisor" and candidate.parent.parent.name == "state":
            return candidate.parent.parent / "chummer_design_supervisor" / candidate.name
    return candidate


def _supervisor_state_has_runtime_signal(state: Dict[str, Any]) -> bool:
    if not isinstance(state, dict) or not state:
        return False
    if int(state.get("active_runs_count") or 0) > 0:
        return True
    if state.get("frontier_ids") or state.get("open_milestone_ids") or state.get("active_runs"):
        return True
    eta = dict(state.get("eta") or {})
    if not eta:
        return False
    if str(eta.get("eta_human") or "").strip() or str(eta.get("scope_kind") or "").strip():
        return True
    return any(int(eta.get(key) or 0) > 0 for key in (
        "remaining_open_milestones",
        "remaining_in_progress_milestones",
        "remaining_not_started_milestones",
    ))


def _rebuild_chummer_design_supervisor_state_from_shards(state_root: pathlib.Path) -> Dict[str, Any]:
    if not state_root.exists() or not state_root.is_dir():
        return {}
    shard_dirs = sorted(
        candidate
        for candidate in state_root.iterdir()
        if candidate.is_dir() and candidate.name.startswith("shard-") and (candidate / "state.json").exists()
    )
    if not shard_dirs:
        return {}

    freshest_updated_at: Optional[dt.datetime] = None
    active_runs: List[Dict[str, Any]] = []
    frontier_ids: set[int] = set()
    open_milestone_ids: set[int] = set()
    modes: set[str] = set()
    eta_scope_kinds: set[str] = set()
    remaining_open_total = 0
    remaining_in_progress_total = 0
    remaining_not_started_total = 0

    for shard_dir in shard_dirs:
        try:
            state = _load_json(shard_dir / "state.json")
        except json.JSONDecodeError:
            continue
        if not isinstance(state, dict) or not state:
            continue
        updated_at = _parse_iso(state.get("updated_at"))
        if updated_at is None:
            try:
                updated_at = dt.datetime.fromtimestamp((shard_dir / "state.json").stat().st_mtime, tz=UTC)
            except OSError:
                updated_at = None
        if updated_at is not None and (freshest_updated_at is None or updated_at > freshest_updated_at):
            freshest_updated_at = updated_at
        mode = str(state.get("mode") or "").strip()
        if mode:
            modes.add(mode)
        for raw_id in state.get("frontier_ids") or []:
            try:
                frontier_ids.add(int(raw_id))
            except (TypeError, ValueError):
                continue
        for raw_id in state.get("open_milestone_ids") or []:
            try:
                open_milestone_ids.add(int(raw_id))
            except (TypeError, ValueError):
                continue
        active_run = state.get("active_run") or {}
        if isinstance(active_run, dict) and str(active_run.get("run_id") or "").strip():
            active_runs.append(
                {
                    "run_id": str(active_run.get("run_id") or "").strip(),
                    "_shard": shard_dir.name,
                    "frontier_ids": sorted(
                        int(raw_id)
                        for raw_id in (active_run.get("frontier_ids") or [])
                        if isinstance(raw_id, int)
                    ),
                }
            )
        eta = dict(state.get("eta") or {})
        scope_kind, _scope_label, _scope_warning = _infer_supervisor_eta_scope(eta)
        if scope_kind and scope_kind != "unknown":
            eta_scope_kinds.add(scope_kind)
        shard_remaining_in_progress = int(eta.get("remaining_in_progress_milestones") or 0)
        shard_remaining_not_started = int(eta.get("remaining_not_started_milestones") or 0)
        shard_remaining_open = max(
            int(eta.get("remaining_open_milestones") or 0),
            shard_remaining_in_progress + shard_remaining_not_started,
            len([raw_id for raw_id in (state.get("frontier_ids") or []) if str(raw_id).strip()]),
        )
        remaining_open_total += shard_remaining_open
        remaining_in_progress_total += shard_remaining_in_progress
        remaining_not_started_total += shard_remaining_not_started

    if remaining_in_progress_total <= 0 and active_runs:
        remaining_in_progress_total = min(remaining_open_total or len(active_runs), len(active_runs))
    if remaining_not_started_total + remaining_in_progress_total != remaining_open_total:
        remaining_not_started_total = max(0, remaining_open_total - remaining_in_progress_total)

    aggregate_eta: Dict[str, Any] = {}
    if len(eta_scope_kinds) > 1:
        aggregate_eta = {
            "status": "tracked",
            "eta_human": "tracked",
            "scope_kind": "aggregate_shard_mixed_scope",
            "scope_label": "Aggregate multi-shard ETA",
            "scope_warning": (
                "Aggregate shard status currently mixes multiple ETA scopes. Use the supervisor ETA command for a "
                "fresh whole-fleet forecast instead of reading this as a single parity horizon."
            ),
        }
    elif eta_scope_kinds:
        scope_kind = next(iter(eta_scope_kinds))
        _scope_kind, scope_label, scope_warning = _infer_supervisor_eta_scope({"scope_kind": scope_kind})
        aggregate_eta = {
            "status": "tracked" if len(shard_dirs) > 1 else "",
            "eta_human": "tracked" if len(shard_dirs) > 1 else "",
            "scope_kind": scope_kind,
            "scope_label": scope_label,
            "scope_warning": scope_warning,
        }
    if aggregate_eta:
        aggregate_eta.update(
            {
                "remaining_open_milestones": remaining_open_total,
                "remaining_in_progress_milestones": remaining_in_progress_total,
                "remaining_not_started_milestones": remaining_not_started_total,
            }
        )

    mode = next(iter(modes)) if len(modes) == 1 else ("sharded" if modes else "unknown")
    if len(shard_dirs) > 1 and mode != "complete":
        mode = "sharded"
    rebuilt: Dict[str, Any] = {
        "mode": mode,
        "active_runs_count": len(active_runs),
        "frontier_ids": sorted(frontier_ids),
        "open_milestone_ids": sorted(open_milestone_ids),
    }
    if freshest_updated_at is not None:
        rebuilt["updated_at"] = freshest_updated_at.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    if active_runs:
        rebuilt["active_runs"] = active_runs
    if aggregate_eta:
        rebuilt["eta"] = aggregate_eta
    return rebuilt


def _load_chummer_design_supervisor_state(*, state_path: pathlib.Path | None = None) -> Dict[str, Any]:
    if state_path is None:
        raw_root = str(os.environ.get("CHUMMER_DESIGN_SUPERVISOR_STATE_ROOT") or "").strip()
        if raw_root:
            candidate = pathlib.Path(raw_root)
            state_path = candidate if candidate.name == "state.json" else (candidate / "state.json")
        else:
            state_path = DEFAULT_DESIGN_SUPERVISOR_STATE_PATH
    try:
        state = _load_json(state_path)
    except json.JSONDecodeError:
        state = {}
    if _supervisor_state_has_runtime_signal(state):
        return state
    rebuilt = _rebuild_chummer_design_supervisor_state_from_shards(_design_supervisor_state_root(state_path))
    if not rebuilt:
        return state
    merged = dict(state or {})
    merged.update(rebuilt)
    return merged


def _load_yaml(path: pathlib.Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {}


def _load_json(path: pathlib.Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _read_text(path: pathlib.Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _status_is_pass_like(value: Any) -> bool:
    return str(value or "").strip().lower() in {"pass", "passed", "ready", "green", "complete", "completed", "ok"}


def _join_sentences(*parts: Any) -> str:
    clean_parts: List[str] = []
    for part in parts:
        clean = str(part or "").strip()
        if not clean:
            continue
        clean_parts.append(clean.rstrip("."))
    return f"{'. '.join(clean_parts)}." if clean_parts else ""


def _flagship_readiness_truth() -> Dict[str, Any]:
    import_parity = _load_json(DEFAULT_IMPORT_PARITY_CERTIFICATION_PATH)
    chummer5a_workflow = _load_json(DEFAULT_CHUMMER5A_DESKTOP_WORKFLOW_PARITY_PATH)
    sr4_workflow = _load_json(DEFAULT_SR4_DESKTOP_WORKFLOW_PARITY_PATH)
    sr6_workflow = _load_json(DEFAULT_SR6_DESKTOP_WORKFLOW_PARITY_PATH)
    visual_familiarity = _load_json(DEFAULT_DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE_PATH)
    executable_gate = _load_json(DEFAULT_DESKTOP_EXECUTABLE_EXIT_GATE_PATH)

    feature_parity_proven = all(
        _status_is_pass_like(payload.get("status"))
        for payload in (import_parity, chummer5a_workflow, sr4_workflow, sr6_workflow)
    )
    layout_familiarity_proven = _status_is_pass_like(visual_familiarity.get("status"))
    executable_gate_status = str(executable_gate.get("status") or "unknown").strip().lower()
    executable_gate_ready = _status_is_pass_like(executable_gate_status)
    blocking_reasons = [
        str(item).strip()
        for item in (
            executable_gate.get("blocking_findings")
            or executable_gate.get("blockingFindings")
            or executable_gate.get("reasons")
            or []
        )
        if str(item).strip()
    ]
    windows_blocking_reasons = [reason for reason in blocking_reasons if "windows" in reason.lower()]

    summary = "Flagship desktop proof is not currently green."
    status = "unknown"
    if feature_parity_proven and layout_familiarity_proven and executable_gate_ready:
        status = "ready"
        summary = "Feature parity, desktop layout familiarity, and executable flagship proof are all green."
    elif feature_parity_proven and layout_familiarity_proven and windows_blocking_reasons:
        status = "warning"
        summary = "Feature parity and desktop layout familiarity are proven, but flagship desktop proof is still blocked by Windows installer/startup evidence."
    elif feature_parity_proven and layout_familiarity_proven:
        status = "warning"
        summary = "Feature parity and desktop layout familiarity are proven, but executable flagship proof is not green yet."
    elif executable_gate_ready:
        status = "warning"
        summary = "Executable flagship proof is green, but parity and layout proof are not complete enough to widen final claims."
    elif blocking_reasons:
        status = "warning"
        summary = str(executable_gate.get("summary") or summary).strip() or summary

    return {
        "status": status,
        "summary": summary,
        "feature_parity_proven": feature_parity_proven,
        "layout_familiarity_proven": layout_familiarity_proven,
        "desktop_executable_gate_status": executable_gate_status or "unknown",
        "desktop_executable_gate_summary": str(executable_gate.get("summary") or "").strip(),
        "windows_blocking_reason_count": len(windows_blocking_reasons),
        "windows_blocking_reasons": windows_blocking_reasons[:4],
        "proofs": {
            "import_parity_status": str(import_parity.get("status") or "").strip(),
            "chummer5a_workflow_parity_status": str(chummer5a_workflow.get("status") or "").strip(),
            "sr4_workflow_parity_status": str(sr4_workflow.get("status") or "").strip(),
            "sr6_workflow_parity_status": str(sr6_workflow.get("status") or "").strip(),
            "desktop_visual_familiarity_status": str(visual_familiarity.get("status") or "").strip(),
            "desktop_executable_gate_status": executable_gate_status or "unknown",
        },
    }


def _product_canon_dir_for_repo(repo_root: pathlib.Path = FLEET_ROOT) -> pathlib.Path:
    local_canon_dir = repo_root / "products" / "chummer"
    if not _same_path(repo_root, FLEET_ROOT) and local_canon_dir.exists():
        return local_canon_dir
    return CHUMMER_PRODUCT_CANON_DIR


def _current_recommended_wave(repo_root: pathlib.Path = FLEET_ROOT) -> str:
    roadmap_path = _product_canon_dir_for_repo(repo_root) / "ROADMAP.md"
    text = _read_text(roadmap_path)
    match = re.search(r"The current recommended wave is \*\*(.+?)\*\*\.", text)
    if match:
        return match.group(1).strip()
    return "Scale & stabilize"


def _active_wave_status(active_wave: str, repo_root: pathlib.Path = FLEET_ROOT) -> str:
    product_canon_dir = _product_canon_dir_for_repo(repo_root)
    next12_registry_path = product_canon_dir / "NEXT_12_BIGGEST_WINS_REGISTRY.yaml"
    registry_map = {
        "Next 12 Biggest Wins": ACTIVE_WAVE_REGISTRY_PATH if _same_path(repo_root, FLEET_ROOT) else next12_registry_path,
        "Next 20 Big Wins After Post-Audit Closeout": product_canon_dir / "NEXT_20_BIG_WINS_AFTER_POST_AUDIT_CLOSEOUT_REGISTRY.yaml",
        "Post-Audit Next 20 Big Wins": product_canon_dir / "POST_AUDIT_NEXT_20_BIG_WINS_REGISTRY.yaml",
        "Next 20 Big Wins": product_canon_dir / "NEXT_20_BIG_WINS_REGISTRY.yaml",
    }
    active_wave_key = str(active_wave or "").strip()
    registry_path = registry_map.get(active_wave_key)
    if registry_path is None and active_wave_key.lower().startswith("next 12"):
        registry_path = next12_registry_path
    if registry_path is None and next12_registry_path.exists():
        registry_path = next12_registry_path
    if registry_path is None or not registry_path.exists():
        return "unknown"
    payload = _load_yaml(registry_path)
    return str(payload.get("status") or "").strip().lower() or "unknown"


def _project_configs(projects_dir: pathlib.Path) -> Dict[str, Dict[str, Any]]:
    configs: Dict[str, Dict[str, Any]] = {}
    if not projects_dir.exists():
        return configs
    for path in sorted(projects_dir.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        payload = _load_yaml(path)
        project_id = str(payload.get("id") or path.stem).strip()
        if project_id:
            configs[project_id] = payload
    return configs


def _queue_item_label(item: Any) -> str:
    if isinstance(item, dict):
        for key in ("title", "task", "summary", "label", "package_id", "id"):
            value = str(item.get(key) or "").strip()
            if value:
                return value
        return ""
    return str(item or "").strip()


def _queue_item_active(item: Any) -> bool:
    if not isinstance(item, dict):
        return True
    status = str(item.get("status") or item.get("state") or "").strip().lower().replace("_", " ")
    if not status:
        return True
    return status not in {"complete", "completed", "done", "closed", "released"}


def _project_active_queue(project_cfg: Dict[str, Any]) -> List[Any]:
    queue = [item for item in (project_cfg.get("queue") or []) if _queue_item_active(item)]
    for source_cfg in project_cfg.get("queue_sources") or []:
        if isinstance(source_cfg, dict):
            queue = [item for item in _apply_queue_source(project_cfg, queue, source_cfg) if _queue_item_active(item)]
    return queue


def _repo_local_backlog_snapshot(project_cfgs: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    rows: List[Dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for project_id, project_cfg in project_cfgs.items():
        if project_cfg.get("enabled") is False:
            continue
        queue = _project_active_queue(project_cfg)
        if not queue:
            continue
        repo_slug = project_repo_slug(project_cfg)
        for item in queue:
            task = _queue_item_label(item)
            if not task:
                continue
            dedupe_key = (str(project_id).strip().lower(), task.lower())
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            rows.append(
                {
                    "project_id": str(project_id).strip(),
                    "repo_slug": repo_slug,
                    "task": task,
                }
            )
    lead_task = str((rows[0] if rows else {}).get("task") or "").strip()
    return {
        "open_item_count": len(rows),
        "open_project_count": len(
            {str(row.get("project_id") or "").strip() for row in rows if str(row.get("project_id") or "").strip()}
        ),
        "lead_task": lead_task,
        "open_items": rows[:25],
    }


def _open_milestone_items(project_meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for raw in project_meta.get("remaining_milestones") or []:
        row = dict(raw or {})
        status = str(row.get("status") or "open").strip().lower()
        if status == "complete":
            continue
        items.append(row)
    return items


def _open_milestone_weight(project_meta: Dict[str, Any]) -> int:
    total = 0
    for row in _open_milestone_items(project_meta):
        try:
            total += int(row.get("weight") or 0)
        except Exception:
            continue
    return total


def _recent_commit_count(repo_root: pathlib.Path, *, since_days: int = 7) -> int:
    try:
        if not repo_root.exists():
            return 0
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-list", "--count", f"--since={since_days}.days", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception:
        return 0
    if result.returncode != 0:
        return 0
    try:
        return max(0, int(str(result.stdout or "").strip() or "0"))
    except Exception:
        return 0


def _phase_label(progress_percent: int, labels: Sequence[Dict[str, Any]]) -> str:
    chosen = "In progress"
    for row in labels or []:
        try:
            threshold = int(row.get("min_progress_percent") or 0)
        except Exception:
            threshold = 0
        if progress_percent >= threshold:
            chosen = str(row.get("label") or chosen).strip() or chosen
    return chosen


def _momentum_label(score: float, labels: Sequence[Dict[str, Any]], override: str = "") -> str:
    if str(override or "").strip():
        return str(override).strip()
    chosen = "Stale"
    ordered_labels = sorted(
        [dict(row or {}) for row in (labels or []) if isinstance(row, dict)],
        key=lambda row: float(row.get("min_score") or 0.0),
    )
    for row in ordered_labels:
        try:
            threshold = float(row.get("min_score") or 0.0)
        except Exception:
            threshold = 0.0
        if score >= threshold:
            chosen = str(row.get("label") or chosen).strip() or chosen
    return chosen


def _eta_band(
    *,
    remaining_open_weight: int,
    remaining_open_milestones: int,
    uncovered_scope_count: int,
    recent_commit_count_7d: int,
    eta_cfg: Dict[str, Any],
    low_override: Any = None,
    high_override: Any = None,
) -> Dict[str, Any]:
    remaining_weight_unit = float(eta_cfg.get("remaining_weight_unit") or 4.0)
    scope_multiplier_divisor = float(eta_cfg.get("scope_multiplier_divisor") or 8.0)
    activity_divisor = float(eta_cfg.get("activity_divisor") or 18.0)
    min_velocity = float(eta_cfg.get("min_velocity") or 0.6)
    max_velocity = float(eta_cfg.get("max_velocity") or 1.8)
    low_multiplier = float(eta_cfg.get("low_multiplier") or 0.8)
    high_multiplier = float(eta_cfg.get("high_multiplier") or 1.35)
    min_low_weeks = int(eta_cfg.get("min_low_weeks") or 1)
    max_high_weeks = int(eta_cfg.get("max_high_weeks") or 16)

    weighted_units = max(1.0, float(remaining_open_weight or 0) / max(1.0, remaining_weight_unit))
    scope_multiplier = 1.0 + (float(uncovered_scope_count or 0) / max(1.0, scope_multiplier_divisor))
    momentum_score = float(recent_commit_count_7d or 0) / max(1.0, weighted_units)
    velocity = max(min_velocity, min(max_velocity, momentum_score / max(0.1, activity_divisor)))
    center = (weighted_units * scope_multiplier) / max(0.1, velocity)

    calc_low = max(min_low_weeks, math.floor(center * low_multiplier))
    calc_high = min(max_high_weeks, max(calc_low, math.ceil(center * high_multiplier)))

    low = calc_low
    high = calc_high
    source = "formula"
    if low_override is not None and high_override is not None:
        try:
            low = max(min_low_weeks, int(low_override))
            high = min(max_high_weeks, max(low, int(high_override)))
            source = "config_override"
        except Exception:
            low = calc_low
            high = calc_high
            source = "formula"

    return {
        "momentum_score": round(momentum_score, 2),
        "weighted_units": round(weighted_units, 2),
        "scope_multiplier": round(scope_multiplier, 2),
        "center_weeks": round(center, 2),
        "eta_weeks_low": low,
        "eta_weeks_high": high,
        "eta_source": source,
    }


def _snapshot_part_map(snapshot: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {
        str(item.get("id") or "").strip(): dict(item)
        for item in (snapshot.get("parts") or [])
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    }


def _history_eta_band(
    *,
    part_id: str,
    current_date: dt.date,
    remaining_open_weight: int,
    eta_cfg: Dict[str, Any],
    history_payload: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    if remaining_open_weight <= 0:
        return {
            "momentum_score": 0.0,
            "weighted_units": 0.0,
            "scope_multiplier": 1.0,
            "center_weeks": 0.0,
            "eta_weeks_low": 0,
            "eta_weeks_high": 0,
            "eta_source": "history_velocity",
            "history_velocity_weight_points_per_week": 0.0,
        }
    snapshots = list(history_payload.get("snapshots") or [])
    relevant: List[tuple[dt.date, int]] = []
    for snapshot in snapshots:
        if not isinstance(snapshot, dict):
            continue
        snapshot_date = _parse_date(snapshot.get("as_of"))
        if snapshot_date is None or snapshot_date >= current_date:
            continue
        part_snapshot = _snapshot_part_map(snapshot).get(part_id)
        if not part_snapshot:
            continue
        try:
            remaining_weight = int(part_snapshot.get("remaining_open_weight") or 0)
        except Exception:
            continue
        relevant.append((snapshot_date, remaining_weight))
    if len(relevant) < 2:
        return None

    weighted_units = max(1.0, float(remaining_open_weight or 0) / max(1.0, float(eta_cfg.get("remaining_weight_unit") or 4.0)))
    low_multiplier = float(eta_cfg.get("low_multiplier") or 0.8)
    high_multiplier = float(eta_cfg.get("high_multiplier") or 1.35)
    min_low_weeks = int(eta_cfg.get("min_low_weeks") or 1)
    max_high_weeks = int(eta_cfg.get("max_high_weeks") or 16)

    deltas: List[float] = []
    for (older_date, older_weight), (newer_date, newer_weight) in zip(relevant, relevant[1:]):
        days = (newer_date - older_date).days
        if days <= 0:
            continue
        delta_weight = older_weight - newer_weight
        if delta_weight <= 0:
            continue
        deltas.append((float(delta_weight) * 7.0) / float(days))
    if not deltas:
        return None
    velocity = sum(deltas[-3:]) / float(min(len(deltas), 3))
    if velocity <= 0:
        return None
    center = float(remaining_open_weight) / velocity
    calc_low = max(min_low_weeks, math.floor(center * low_multiplier))
    calc_high = min(max_high_weeks, max(calc_low, math.ceil(center * high_multiplier)))
    return {
        "momentum_score": round(velocity, 2),
        "weighted_units": round(weighted_units, 2),
        "scope_multiplier": 1.0,
        "center_weeks": round(center, 2),
        "eta_weeks_low": calc_low,
        "eta_weeks_high": calc_high,
        "eta_source": "history_velocity",
        "history_velocity_weight_points_per_week": round(velocity, 2),
    }


def hub_participate_url() -> str:
    raw = str(os.environ.get("CHUMMER6_HUB_PARTICIPATE_URL") or "").strip()
    if not raw:
        return DEFAULT_HUB_PARTICIPATE_URL
    return raw.rstrip("/")


def _parse_iso(value: Any) -> Optional[dt.datetime]:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return dt.datetime.fromisoformat(raw).astimezone(UTC)
    except ValueError:
        return None


def _booster_intervals(db_path: pathlib.Path, *, now: dt.datetime, window_days: int = 7) -> List[tuple[dt.datetime, dt.datetime]]:
    if not db_path.exists():
        return []
    window_start = now - dt.timedelta(days=window_days)
    conn = sqlite3.connect(str(db_path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    try:
        rows = conn.execute(
            """
            SELECT started_at, finished_at, decision_reason
            FROM runs
            WHERE job_kind='coding'
              AND started_at IS NOT NULL
              AND (
                decision_reason LIKE '%task_lane=core_booster%'
                OR decision_reason LIKE '%selected lane: core_booster%'
              )
            ORDER BY started_at
            """
        ).fetchall()
    finally:
        conn.close()

    intervals: List[tuple[dt.datetime, dt.datetime]] = []
    for row in rows:
        started_at = _parse_iso(row["started_at"])
        finished_at = _parse_iso(row["finished_at"]) or now
        if started_at is None:
            continue
        if finished_at <= window_start or started_at >= now:
            continue
        start = max(started_at, window_start)
        end = min(finished_at, now)
        if end > start:
            intervals.append((start, end))
    return intervals


def booster_participation_summary(
    *,
    db_path: pathlib.Path = DEFAULT_DB_PATH,
    now: Optional[dt.datetime] = None,
    quiet_gap_minutes: int = 90,
) -> Dict[str, Any]:
    now_dt = now or dt.datetime.now(tz=UTC)
    intervals = _booster_intervals(db_path, now=now_dt)
    if not intervals:
        return {
            "average_active_boosters": 0.0,
            "peak_active_boosters": 0,
            "burst_started_at": "",
            "window_label": "No recent booster burst recorded",
            "participate_url": hub_participate_url(),
        }

    burst_start = intervals[0][0]
    last_end = intervals[0][1]
    quiet_gap = dt.timedelta(minutes=max(1, quiet_gap_minutes))
    for start, end in intervals[1:]:
        if start - last_end > quiet_gap:
            burst_start = start
        if end > last_end:
            last_end = end

    active_intervals = [(max(start, burst_start), end) for start, end in intervals if end > burst_start]
    active_intervals = [(start, end) for start, end in active_intervals if end > start]
    window_end = now_dt
    current_burst_live = now_dt - last_end <= quiet_gap
    if not current_burst_live and last_end < now_dt:
        window_end = last_end
    points: List[tuple[dt.datetime, int]] = []
    for start, end in active_intervals:
        points.append((start, 1))
        points.append((end, -1))
    points.sort(key=lambda item: (item[0], item[1]))
    total_booster_seconds = 0.0
    peak_active = 0
    active = 0
    cursor = burst_start
    for timestamp, delta in points:
        if timestamp > cursor:
            total_booster_seconds += active * (timestamp - cursor).total_seconds()
            cursor = timestamp
        active += delta
        peak_active = max(peak_active, active)
    if window_end > cursor:
        total_booster_seconds += active * (window_end - cursor).total_seconds()
    window_seconds = max(1.0, (window_end - burst_start).total_seconds())
    average_active = total_booster_seconds / window_seconds
    burst_day = "today" if burst_start.date() == now_dt.date() else burst_start.strftime("%B %d")
    return {
        "average_active_boosters": round(average_active, 1),
        "peak_active_boosters": peak_active,
        "burst_started_at": burst_start.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "window_label": (
            f"Average active boosters since the current burst began {burst_day}"
            if current_burst_live
            else f"Average active boosters in the most recent burst ({burst_day})"
        ),
        "participate_url": hub_participate_url(),
    }


def _part_compile_rollup(project_rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    mapped_project_count = len(project_rows)
    dispatchable_truth_ready_count = 0
    package_compile_count = 0
    capacity_compile_count = 0
    published_artifact_count = 0
    lifecycle_counts: Dict[str, int] = {}

    for row in project_rows:
        compile_payload = dict(row.get("compile") or {})
        stages = dict(compile_payload.get("stages") or {})
        if compile_payload.get("dispatchable_truth_ready"):
            dispatchable_truth_ready_count += 1
        if stages.get("package_compile"):
            package_compile_count += 1
        if stages.get("capacity_compile"):
            capacity_compile_count += 1
        published_artifact_count += len(compile_payload.get("artifacts") or [])
        lifecycle = str(row.get("lifecycle") or "").strip() or "undeclared"
        lifecycle_counts[lifecycle] = lifecycle_counts.get(lifecycle, 0) + 1

    return {
        "mapped_project_count": mapped_project_count,
        "dispatchable_truth_ready": dispatchable_truth_ready_count > 0,
        "dispatchable_truth_ready_count": dispatchable_truth_ready_count,
        "package_compile": package_compile_count > 0,
        "package_compile_count": package_compile_count,
        "capacity_compile": capacity_compile_count > 0,
        "capacity_compile_count": capacity_compile_count,
        "published_artifacts_present": published_artifact_count > 0,
        "published_artifact_count": published_artifact_count,
        "lifecycle_counts": lifecycle_counts,
    }


def _overall_momentum(parts: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    active_parts = [row for row in parts if int(row.get("remaining_open_milestones") or 0) > 0]
    ranked_parts = active_parts or list(parts)
    if not ranked_parts:
        return {
            "label": "Complete",
            "summary": "All mapped public parts are currently at zero open milestones.",
        }
    lead = max(
        ranked_parts,
        key=lambda row: (
            int(row.get("remaining_open_weight") or 0),
            int(row.get("eta_weeks_high") or 0),
            -int(row.get("progress_percent") or 0),
        ),
    )
    lead_label = str(lead.get("momentum_label") or "").strip() or "Steady"
    lead_name = str(lead.get("short_public_name") or lead.get("public_name") or lead.get("id") or "Current long pole").strip()
    return {
        "label": lead_label,
        "summary": f"{lead_name} is currently setting the delivery pace.",
    }


def _release_readiness_summary(parts: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    active_parts = [row for row in parts if int(row.get("remaining_open_milestones") or 0) > 0]
    if not active_parts:
        return {
            "status": "ready",
            "summary": "All mapped public parts are at zero open milestone weight.",
            "blocking_parts": [],
        }
    not_dispatchable = [
        str(row.get("short_public_name") or row.get("public_name") or row.get("id") or "").strip()
        for row in active_parts
        if not bool(dict(row.get("source_status") or {}).get("dispatchable_truth_ready"))
    ]
    no_package_compile = [
        str(row.get("short_public_name") or row.get("public_name") or row.get("id") or "").strip()
        for row in active_parts
        if not bool(dict(row.get("source_status") or {}).get("package_compile"))
    ]
    no_artifacts = [
        str(row.get("short_public_name") or row.get("public_name") or row.get("id") or "").strip()
        for row in active_parts
        if not bool(dict(row.get("source_status") or {}).get("published_artifacts_present"))
    ]
    blocking_parts = sorted({label for label in (not_dispatchable + no_package_compile + no_artifacts) if label})
    if blocking_parts:
        return {
            "status": "warning",
            "summary": "Some active public parts are still missing dispatchable/package/published proof.",
            "blocking_parts": blocking_parts,
        }
    return {
        "status": "tracked",
        "summary": "Active public parts are dispatchable and publishing artifacts; remaining work is milestone closure and acceptance proof.",
        "blocking_parts": [],
    }


def _parity_summary(parts: Sequence[Dict[str, Any]], *, flagship_readiness: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    uncovered_parts = [
        {
            "part_id": str(row.get("id") or "").strip(),
            "label": str(row.get("short_public_name") or row.get("public_name") or row.get("id") or "").strip(),
            "uncovered_scope_count": int(row.get("uncovered_scope_count") or 0),
        }
        for row in parts
        if int(row.get("uncovered_scope_count") or 0) > 0
    ]
    if uncovered_parts:
        return {
            "status": "warning",
            "summary": "Some public parts still carry uncovered-scope markers and should not be treated as parity-complete.",
            "uncovered_parts": uncovered_parts,
        }
    if flagship_readiness:
        feature_parity_proven = bool(flagship_readiness.get("feature_parity_proven"))
        layout_familiarity_proven = bool(flagship_readiness.get("layout_familiarity_proven"))
        desktop_executable_gate_ready = str(flagship_readiness.get("desktop_executable_gate_status") or "").strip().lower() in {
            "pass",
            "passed",
            "ready",
            "green",
        }
        if feature_parity_proven and layout_familiarity_proven and not desktop_executable_gate_ready:
            return {
                "status": "warning",
                "summary": "Rules/import and workflow parity are proven, and the desktop visual-familiarity gate is green, but final parity still cannot be claimed until executable flagship proof closes.",
                "uncovered_parts": [],
            }
        if feature_parity_proven and layout_familiarity_proven:
            return {
                "status": "ready",
                "summary": "Rules/import and workflow parity are proven, and the desktop visual-familiarity gate is green.",
                "uncovered_parts": [],
            }
    return {
        "status": "tracked",
        "summary": "No uncovered-scope markers are currently attached to the mapped public parts. Release-blocking parity still closes through the flagship gate.",
        "uncovered_parts": [],
    }


def _top_risks_summary(parts: Sequence[Dict[str, Any]], *, history_snapshot_count: int) -> List[Dict[str, Any]]:
    risks: List[Dict[str, Any]] = []
    for row in sorted(
        parts,
        key=lambda item: (
            -int(item.get("uncovered_scope_count") or 0),
            -int(item.get("remaining_open_milestones") or 0),
            -int(item.get("eta_weeks_high") or 0),
            str(item.get("public_name") or item.get("id") or ""),
        ),
    ):
        label = str(row.get("short_public_name") or row.get("public_name") or row.get("id") or "").strip()
        if not label:
            continue
        uncovered_scope_count = int(row.get("uncovered_scope_count") or 0)
        source_status = dict(row.get("source_status") or {})
        if uncovered_scope_count > 0:
            risks.append(
                {
                    "key": f"{row.get('id')}:uncovered_scope",
                    "summary": f"{label} still carries {uncovered_scope_count} uncovered-scope marker(s).",
                }
            )
        elif int(row.get("remaining_open_milestones") or 0) > 0 and not bool(source_status.get("dispatchable_truth_ready")):
            risks.append(
                {
                    "key": f"{row.get('id')}:dispatchable_truth",
                    "summary": f"{label} still lacks dispatchable-truth readiness while milestone work remains open.",
                }
            )
        elif int(row.get("remaining_open_milestones") or 0) > 0 and not bool(source_status.get("package_compile")):
            risks.append(
                {
                    "key": f"{row.get('id')}:package_compile",
                    "summary": f"{label} still lacks package-compile proof while milestone work remains open.",
                }
            )
        if len(risks) >= 4:
            break
    if history_snapshot_count < 4:
        risks.append(
            {
                "key": "history_depth",
                "summary": f"Public progress history only has {history_snapshot_count} snapshot(s), so velocity confidence is still shallow.",
            }
        )
    return risks[:5]


def load_progress_history_payload(*, repo_root: pathlib.Path = FLEET_ROOT) -> Dict[str, Any]:
    for artifact_path in progress_history_artifact_candidates(repo_root):
        payload = _load_json(artifact_path)
        if isinstance(payload.get("snapshots"), list):
            return payload
    return {
        "contract_name": PUBLIC_PROGRESS_HISTORY_CONTRACT_NAME,
        "contract_version": PUBLIC_PROGRESS_HISTORY_CONTRACT_VERSION,
        "snapshots": [],
    }


def progress_history_snapshot(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "as_of": str(payload.get("as_of") or "").strip(),
        "overall_progress_percent": int(payload.get("overall_progress_percent") or 0),
        "phase_label": str(payload.get("phase_label") or "").strip(),
        "parts": [
            {
                "id": str(part.get("id") or "").strip(),
                "public_name": str(part.get("public_name") or "").strip(),
                "progress_percent": int(part.get("progress_percent") or 0),
                "remaining_open_weight": int(part.get("remaining_open_weight") or 0),
                "remaining_open_milestones": int(part.get("remaining_open_milestones") or 0),
                "recent_commit_count_7d": int(part.get("recent_commit_count_7d") or 0),
                "uncovered_scope_count": int(part.get("uncovered_scope_count") or 0),
                "eta_weeks_low": int(part.get("eta_weeks_low") or 0),
                "eta_weeks_high": int(part.get("eta_weeks_high") or 0),
                "eta_source": str(part.get("eta_source") or "").strip(),
            }
            for part in (payload.get("parts") or [])
            if isinstance(part, dict) and str(part.get("id") or "").strip()
        ],
    }


def merge_progress_history(existing: Dict[str, Any], payload: Dict[str, Any], *, max_snapshots: int = 52) -> Dict[str, Any]:
    snapshots_by_date: Dict[str, Dict[str, Any]] = {}
    for snapshot in existing.get("snapshots") or []:
        if not isinstance(snapshot, dict):
            continue
        as_of = str(snapshot.get("as_of") or "").strip()
        if as_of:
            snapshots_by_date[as_of] = dict(snapshot)
    current_snapshot = progress_history_snapshot(payload)
    as_of = str(current_snapshot.get("as_of") or "").strip()
    if as_of:
        snapshots_by_date[as_of] = current_snapshot
    ordered_snapshots = [snapshots_by_date[key] for key in sorted(snapshots_by_date.keys())][-max_snapshots:]
    return {
        "contract_name": PUBLIC_PROGRESS_HISTORY_CONTRACT_NAME,
        "contract_version": PUBLIC_PROGRESS_HISTORY_CONTRACT_VERSION,
        "generated_at": dt.datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "snapshot_count": len(ordered_snapshots),
        "snapshots": ordered_snapshots,
    }


def _method_limitations(
    configured_limitations: List[str],
    *,
    history_snapshot_count: int,
    history_backed_eta: bool,
    eta_sources: Sequence[str],
    eta_scope: str,
    queue_open_milestones: int,
) -> List[str]:
    history_absence_markers = (
        "no long-term public history yet",
        "does not yet expose a durable public weekly progress history",
        "no persisted week-over-week public status history yet",
        "until weekly historical snapshots are published",
    )
    config_override_markers = (
        "momentum-based planning band",
        "short-horizon momentum proxy",
    )
    limitations: List[str] = []
    eta_source_set = {str(item or "").strip() for item in eta_sources if str(item or "").strip()}
    config_override_only = eta_source_set == {"config_override"}
    for item in configured_limitations:
        clean = str(item or "").strip()
        if not clean:
            continue
        lowered = clean.lower()
        if history_snapshot_count > 0 and any(marker in lowered for marker in history_absence_markers):
            continue
        if config_override_only and any(marker in lowered for marker in config_override_markers):
            continue
        limitations.append(clean)
    if config_override_only:
        config_override_note = (
            "Current public ETA uses configured planning bands for each part while weekly history accumulates."
        )
        if history_snapshot_count > 0:
            config_override_note = (
                "Current public ETA still uses configured planning bands for each part; weekly history is now being recorded so measured velocity can replace those overrides once enough snapshots accumulate."
            )
        if config_override_note not in limitations:
            limitations.append(config_override_note)
    if history_snapshot_count > 0 and not config_override_only:
        history_note = (
            "Weekly public progress history is now being recorded; ETA still uses the short-horizon momentum proxy until enough snapshots accumulate."
        )
        if history_backed_eta:
            history_note = (
                "Weekly public progress history is now available; ETA uses recorded velocity where enough snapshots exist and falls back to the short-horizon momentum proxy elsewhere."
            )
        if history_note not in limitations:
            limitations.append(history_note)
    if eta_scope in {"full_product_queue", "full_product_queue_unestimated"} and queue_open_milestones > 0:
        queue_note = (
            f"Mapped public milestones are complete, but the full-product frontier remains open with {queue_open_milestones} milestone(s). "
            "Full completion requires full frontier closure."
        )
        if queue_note not in limitations:
            limitations.append(queue_note)
    if eta_scope == "full_product_queue_unestimated":
        scope_note = (
            "The current supervisor ETA is tactical or otherwise not yet calendar-grade enough for a full-product parity forecast, so the public surface tracks the remaining frontier without publishing a parity date band."
        )
        if scope_note not in limitations:
            limitations.append(scope_note)
    return limitations


def build_progress_report_payload(
    *,
    repo_root: pathlib.Path = FLEET_ROOT,
    as_of: Optional[dt.date] = None,
    commit_counter: Optional[Callable[[pathlib.Path], int]] = None,
    now: Optional[dt.datetime] = None,
    history_payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    config = _load_yaml(progress_config_path(repo_root))
    milestones = _load_yaml(program_milestones_path(repo_root))
    project_cfgs = _project_configs(repo_root / "config" / "projects")
    project_milestones = dict(milestones.get("projects") or {})
    parts_cfg = list(config.get("parts") or [])
    phase_labels = list(config.get("phase_labels") or [])
    momentum_labels = list(config.get("momentum_labels") or [])
    eta_cfg = dict(config.get("eta_formula") or {})
    recent_copy = dict(config.get("recent_movement_copy") or {})
    history_payload = history_payload or load_progress_history_payload(repo_root=repo_root)

    current_now = now or dt.datetime.now(tz=UTC)
    current_date = as_of or _parse_date(config.get("as_of")) or current_now.date()
    counter = commit_counter or (lambda repo_path: _recent_commit_count(repo_path, since_days=7))
    parts: List[Dict[str, Any]] = []
    total_design_weight = 0
    total_open_weight = 0
    mapped_open_milestones = 0
    repo_backlog = _repo_local_backlog_snapshot(project_cfgs)
    repo_backlog_open_item_count = int(repo_backlog.get("open_item_count") or 0)
    repo_backlog_open_project_count = int(repo_backlog.get("open_project_count") or 0)
    repo_backlog_lead_task = str(repo_backlog.get("lead_task") or "").strip()
    supervisor_state = _load_chummer_design_supervisor_state()
    supervisor_eta = dict(supervisor_state.get("eta") or {})
    supervisor_open_frontier_milestones = int(supervisor_eta.get("remaining_open_milestones") or 0)
    supervisor_frontier_ids = list(supervisor_state.get("frontier_ids") or [])
    supervisor_open_milestone_ids = list(supervisor_state.get("open_milestone_ids") or [])
    supervisor_active_runs = [
        item
        for item in (supervisor_state.get("active_runs") or [])
        if isinstance(item, dict) and str(item.get("run_id") or "").strip()
    ]
    supervisor_active_runs_count = int(supervisor_state.get("active_runs_count") or len(supervisor_active_runs))
    supervisor_mode = str(supervisor_state.get("mode") or "").strip() or "unknown"
    supervisor_eta_human = str(supervisor_eta.get("eta_human") or "").strip()
    supervisor_eta_scope_kind, supervisor_eta_scope_label, supervisor_eta_scope_warning = _infer_supervisor_eta_scope(
        supervisor_eta
    )
    supervisor_eta_is_full_product = supervisor_eta_scope_kind == "flagship_product_readiness"
    flagship_readiness = _flagship_readiness_truth()
    supervisor_full_product_eta_weeks_low, supervisor_full_product_eta_weeks_high = (
        _parse_eta_human_weeks(supervisor_eta_human)
        if supervisor_eta_is_full_product
        else (None, None)
    )
    supervisor_has_calendar_eta = (
        supervisor_eta_is_full_product
        and supervisor_full_product_eta_weeks_low is not None
        and supervisor_full_product_eta_weeks_high is not None
    )

    for part_cfg in parts_cfg:
        project_ids = [str(item).strip() for item in (part_cfg.get("mapped_projects") or []) if str(item).strip()]
        design_total_weight = 0
        open_weight = 0
        remaining_count = 0
        uncovered_scope_count = 0
        recent_commit_count_7d = 0
        project_rows: List[Dict[str, Any]] = []

        for project_id in project_ids:
            project_cfg = dict(project_cfgs.get(project_id) or {})
            milestone_meta = dict(project_milestones.get(project_id) or {})
            repo_root_path = pathlib.Path(str(project_cfg.get("path") or "")).expanduser() if project_cfg.get("path") else pathlib.Path(".")
            compile_payload = studio_compile_summary(repo_root_path, str(project_cfg.get("design_doc") or ""))
            commit_count = counter(repo_root_path)
            project_row = {
                "id": project_id,
                "repo_slug": project_repo_slug(project_cfg),
                "path": str(repo_root_path),
                "lifecycle": str(project_cfg.get("lifecycle") or ""),
                "recent_commit_count_7d": commit_count,
                "design_total_weight": int(milestone_meta.get("design_total_weight") or 0),
                "remaining_open_weight": _open_milestone_weight(milestone_meta),
                "remaining_open_milestones": len(_open_milestone_items(milestone_meta)),
                "uncovered_scope_count": len([item for item in (milestone_meta.get("uncovered_scope") or []) if str(item).strip()]),
                "compile": compile_payload,
            }
            project_rows.append(project_row)
            design_total_weight += project_row["design_total_weight"]
            open_weight += project_row["remaining_open_weight"]
            remaining_count += project_row["remaining_open_milestones"]
            uncovered_scope_count += project_row["uncovered_scope_count"]
            recent_commit_count_7d += commit_count

        progress_percent = 0
        if design_total_weight > 0:
            progress_percent = int(round(((design_total_weight - open_weight) / design_total_weight) * 100))
        total_design_weight += design_total_weight
        total_open_weight += open_weight

        eta_payload = _history_eta_band(
            part_id=str(part_cfg.get("id") or "").strip(),
            current_date=current_date,
            remaining_open_weight=open_weight,
            eta_cfg=eta_cfg,
            history_payload=history_payload,
        )
        if eta_payload is None:
            eta_payload = _eta_band(
                remaining_open_weight=open_weight,
                remaining_open_milestones=remaining_count,
                uncovered_scope_count=uncovered_scope_count,
                recent_commit_count_7d=recent_commit_count_7d,
                eta_cfg=eta_cfg,
                low_override=part_cfg.get("eta_weeks_low_override"),
                high_override=part_cfg.get("eta_weeks_high_override"),
            )
        momentum_label = _momentum_label(
            eta_payload["momentum_score"],
            momentum_labels,
            override=str(part_cfg.get("momentum_label_override") or ""),
        )
        part_payload = {
            "id": str(part_cfg.get("id") or "").strip(),
            "public_name": str(part_cfg.get("public_name") or "").strip(),
            "short_public_name": str(part_cfg.get("short_public_name") or part_cfg.get("public_name") or "").strip(),
            "mapped_projects": project_ids,
            "progress_percent": progress_percent,
            "momentum_label": momentum_label,
            "eta_weeks_low": eta_payload["eta_weeks_low"],
            "eta_weeks_high": eta_payload["eta_weeks_high"],
            "summary": str(part_cfg.get("summary") or "").strip(),
            "milestones": [dict(item or {}) for item in (part_cfg.get("milestones") or []) if isinstance(item, dict)],
            "recent_commit_count_7d": recent_commit_count_7d,
            "remaining_open_weight": open_weight,
            "remaining_open_milestones": remaining_count,
            "uncovered_scope_count": uncovered_scope_count,
            "momentum_score": eta_payload["momentum_score"],
            "eta_source": eta_payload["eta_source"],
            "formula": {
                "weighted_units": eta_payload["weighted_units"],
                "scope_multiplier": eta_payload["scope_multiplier"],
                "center_weeks": eta_payload["center_weeks"],
            },
            "history_velocity_weight_points_per_week": float(eta_payload.get("history_velocity_weight_points_per_week") or 0.0),
            "source_status": _part_compile_rollup(project_rows),
            "source_projects": project_rows,
        }
        parts.append(part_payload)
        mapped_open_milestones += remaining_count

    overall_progress_percent = 0
    if total_design_weight > 0:
        overall_progress_percent = int(round(((total_design_weight - total_open_weight) / total_design_weight) * 100))
    if repo_backlog_open_item_count > 0 and overall_progress_percent >= 100:
        overall_progress_percent = 99

    active_parts = [row for row in parts if int(row.get("remaining_open_milestones") or 0) > 0]
    next_checkpoint_eta_weeks_low = min((int(row.get("eta_weeks_low") or 0) for row in active_parts), default=0)
    next_checkpoint_eta_weeks_high = min((int(row.get("eta_weeks_high") or 0) for row in active_parts), default=0)
    eta_scope = "mapped_frontier"
    if not active_parts and mapped_open_milestones <= 0 and supervisor_open_frontier_milestones > 0:
        eta_scope = "full_product_queue" if supervisor_has_calendar_eta else "full_product_queue_unestimated"
        if supervisor_has_calendar_eta and supervisor_full_product_eta_weeks_low is not None:
            next_checkpoint_eta_weeks_low = supervisor_full_product_eta_weeks_low
        if supervisor_has_calendar_eta and supervisor_full_product_eta_weeks_high is not None:
            next_checkpoint_eta_weeks_high = supervisor_full_product_eta_weeks_high
    longest_pole = max(
        parts,
        key=lambda row: (
            int(row.get("eta_weeks_high") or 0),
            int(row.get("eta_weeks_low") or 0),
            -int(row.get("progress_percent") or 0),
        ),
        default={},
    )

    recent_movement = []
    for title in config.get("recent_movement") or []:
        clean = str(title or "").strip()
        if not clean:
            continue
        recent_movement.append(
            {
                "title": clean,
                "body": str(recent_copy.get(clean) or "").strip(),
            }
        )
    history_snapshot_count = len(list(history_payload.get("snapshots") or []))
    eta_sources = sorted({str(part.get("eta_source") or "").strip() for part in parts if str(part.get("eta_source") or "").strip()})
    history_backed_eta = any(str(part.get("eta_source") or "") == "history_velocity" for part in parts)
    phase_label = _phase_label(overall_progress_percent, phase_labels)
    active_wave = _current_recommended_wave(repo_root)
    active_wave_status = _active_wave_status(active_wave, repo_root)
    active_slice = active_wave
    if not active_parts and repo_backlog_lead_task:
        active_slice = repo_backlog_lead_task
    eta_summary = _eta_label(next_checkpoint_eta_weeks_low, next_checkpoint_eta_weeks_high)
    queue_scope_active = eta_scope in {"full_product_queue", "full_product_queue_unestimated"}
    if eta_scope == "full_product_queue_unestimated":
        eta_summary = "tracked in full-product frontier"
    if not eta_summary and repo_backlog_open_item_count > 0 and not active_parts:
        eta_summary = "tracked in repo backlog"
    momentum = _overall_momentum(parts)
    release_readiness = _release_readiness_summary(parts)
    parity = _parity_summary(parts, flagship_readiness=flagship_readiness)
    top_risks = _top_risks_summary(parts, history_snapshot_count=history_snapshot_count)
    if release_readiness.get("status") == "ready" and active_wave_status not in {"ready", "complete", "completed", "closed", "shipped"}:
        release_readiness = {
            "status": "tracked",
            "summary": (
                f"Mapped public parts are at zero open milestone weight, but the active wave is still {active_wave_status}; "
                "flagship and release claims remain open until that wave closes."
            ),
            "blocking_parts": list(release_readiness.get("blocking_parts") or []),
        }
    if not active_parts and queue_scope_active:
        queue_scope_note = ""
        if supervisor_eta_scope_kind and supervisor_eta_scope_kind != "flagship_product_readiness":
            queue_scope_note = (
                f" The current supervisor ETA is scoped to {supervisor_eta_scope_label or supervisor_eta_scope_kind}, "
                "so it should not be read as a full-product parity ETA."
            )
        release_readiness = {
            "status": "tracked",
            "summary": (
                f"Mapped public parts are at zero open milestone weight, but there are still {supervisor_open_frontier_milestones} open milestones in the full-product frontier."
                f"{queue_scope_note}"
            ),
            "blocking_parts": list(release_readiness.get("blocking_parts") or []),
        }
    if not top_risks and active_wave_status not in {"ready", "complete", "completed", "closed", "shipped", "unknown", ""}:
        top_risks = [
            {
                "key": "active_wave",
                "summary": f"The active wave is still {active_wave_status}, so public progress is ahead of final release closure.",
            }
        ]
    if not top_risks and not active_parts and queue_scope_active:
        top_risks = [
            {
                "key": "full_product_queue",
                "summary": (
                    f"{supervisor_open_frontier_milestones} open milestones remain in the full-product frontier."
                    + (
                        f" The current supervisor ETA is scoped to {supervisor_eta_scope_label or supervisor_eta_scope_kind}, not full-product parity."
                        if supervisor_eta_scope_kind and supervisor_eta_scope_kind != "flagship_product_readiness"
                        else ""
                    )
                ),
            }
        ]
    if not active_parts and repo_backlog_open_item_count > 0:
        backlog_summary = (
            f"Mapped public parts are at zero open milestone weight, but repo-local backlog still has {repo_backlog_open_item_count} active item(s) across {repo_backlog_open_project_count} project(s)."
        )
        if repo_backlog_lead_task:
            backlog_summary += f" Next up: {repo_backlog_lead_task}."
        release_readiness = {
            "status": "warning",
            "summary": backlog_summary,
            "blocking_parts": list(release_readiness.get("blocking_parts") or []),
        }
        repo_backlog_risk = {
            "key": "repo_local_backlog",
            "summary": backlog_summary,
        }
        existing_risk_keys = {str(row.get("key") or "").strip() for row in top_risks if isinstance(row, dict)}
        if repo_backlog_risk["key"] not in existing_risk_keys:
            top_risks = [repo_backlog_risk, *top_risks]
    if str(flagship_readiness.get("status") or "").strip() == "warning":
        release_readiness = {
            "status": "warning",
            "summary": _join_sentences(flagship_readiness.get("summary"), release_readiness.get("summary")),
            "blocking_parts": list(release_readiness.get("blocking_parts") or []),
        }
        flagship_risk = {
            "key": "flagship_release_truth",
            "summary": str(flagship_readiness.get("summary") or "").strip(),
        }
        existing_risk_keys = {str(row.get("key") or "").strip() for row in top_risks if isinstance(row, dict)}
        if flagship_risk["key"] not in existing_risk_keys and flagship_risk["summary"]:
            top_risks = [flagship_risk, *top_risks]
    headline = str(((config.get("hero") or {}).get("headline")) or "").strip()
    overall_status = str(active_wave_status or release_readiness.get("status") or phase_label or "tracked").strip()

    return {
        "contract_name": PUBLIC_PROGRESS_CONTRACT_NAME,
        "contract_version": PUBLIC_PROGRESS_CONTRACT_VERSION,
        "generated_at": current_now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "as_of": current_date.isoformat(),
        "history_snapshot_count": history_snapshot_count,
        "brand": str(config.get("brand") or "Chummer6").strip() or "Chummer6",
        # Compatibility aliases: some downstream readers still consume the earlier
        # flat fields directly instead of the richer nested/public-guide shapes.
        "active_wave": active_wave,
        "active_wave_status": active_wave_status,
        "active_slice": active_slice,
        "headline": headline,
        "overall_status": overall_status,
        "progress_percent": overall_progress_percent,
        "percent_complete": overall_progress_percent,
        "percent_inflight": 0,
        "percent_blocked": 0,
        "momentum": momentum,
        "top_risks": top_risks,
        "flagship_readiness": flagship_readiness,
        "release_readiness": release_readiness,
        "parity": parity,
        "repo_backlog": repo_backlog,
        "hero": {
            "headline": headline,
            "support": str(((config.get("hero") or {}).get("support")) or "").strip(),
            "ctas": [dict(item or {}) for item in (((config.get("hero") or {}).get("ctas")) or []) if isinstance(item, dict)],
        },
        "overall_progress_percent": overall_progress_percent,
        "phase_label": phase_label,
        "current_phase": phase_label,
        "next_checkpoint_eta_weeks_low": next_checkpoint_eta_weeks_low,
        "next_checkpoint_eta_weeks_high": next_checkpoint_eta_weeks_high,
        "eta_summary": eta_summary,
        "eta_human": eta_summary or supervisor_eta_human or ("tracked" if eta_scope == "full_product_queue_unestimated" else None),
        "longest_pole": {
            "id": str(longest_pole.get("id") or "").strip(),
            "label": str(longest_pole.get("short_public_name") or longest_pole.get("public_name") or "").strip(),
            "eta_weeks_low": int(longest_pole.get("eta_weeks_low") or 0),
            "eta_weeks_high": int(longest_pole.get("eta_weeks_high") or 0),
        },
        "parts": parts,
        "recent_movement": recent_movement,
        "participation": {
            "headline": str(((config.get("participation") or {}).get("headline")) or "How to participate").strip(),
            "body": str(((config.get("participation") or {}).get("body")) or "").strip(),
            "cta_label": str(((config.get("participation") or {}).get("cta_label")) or "Open the participation page").strip(),
            "cta_href": hub_participate_url(),
        },
        "method": {
            "progress_formula_version": str(((config.get("method") or {}).get("progress_formula_version")) or "public_progress_v1"),
            "eta_formula_version": (
                "history_velocity_v1"
                if eta_sources == ["history_velocity"]
                else "config_override_v1"
                if eta_sources == ["config_override"]
                else "history_velocity_with_overrides_v1"
                if history_backed_eta
                else str(((config.get("method") or {}).get("eta_formula_version")) or "momentum_proxy_v1")
            ),
            "copy": str(((config.get("method") or {}).get("copy")) or "").strip(),
            "limitations": _method_limitations(
                [str(item).strip() for item in (((config.get("method") or {}).get("limitations")) or []) if str(item).strip()],
                history_snapshot_count=history_snapshot_count,
                history_backed_eta=history_backed_eta,
                eta_sources=eta_sources,
                eta_scope=eta_scope,
                queue_open_milestones=supervisor_open_frontier_milestones,
            ),
            "history_snapshot_count": history_snapshot_count,
        },
        "eta_scope": eta_scope,
        "full_product_queue": {
            "mode": supervisor_mode,
            "active_runs_count": supervisor_active_runs_count,
            "active_frontier_ids": [int(item) for item in supervisor_frontier_ids if isinstance(item, int)],
            "open_frontier_milestones": supervisor_open_frontier_milestones,
            "open_milestone_ids_count": len([item for item in supervisor_open_milestone_ids if str(item).strip()]),
            "eta": {
                "eta_human": supervisor_eta_human,
                "eta_status": str(supervisor_eta.get("status") or "unknown").strip(),
                "scope_kind": supervisor_eta_scope_kind,
                "scope_label": supervisor_eta_scope_label,
                "scope_warning": supervisor_eta_scope_warning,
                "eta_weeks_low": supervisor_full_product_eta_weeks_low,
                "eta_weeks_high": supervisor_full_product_eta_weeks_high,
                "remaining_open_milestones": int(supervisor_open_frontier_milestones),
                "remaining_in_progress_milestones": int(supervisor_eta.get("remaining_in_progress_milestones") or 0),
                "remaining_not_started_milestones": int(supervisor_eta.get("remaining_not_started_milestones") or 0),
            },
            "active_runs": [
                {
                    "run_id": str((item or {}).get("run_id") or "").strip(),
                    "shard": str((item or {}).get("_shard") or "").strip(),
                    "frontier_count": len((item or {}).get("frontier_ids") or []),
                    "frontier_ids": sorted(
                        int(frontier_id)
                        for frontier_id in (item or {}).get("frontier_ids") or []
                        if isinstance(frontier_id, int)
                    ),
                }
                for item in sorted(
                    supervisor_active_runs,
                    key=lambda item: (
                        str((item or {}).get("_shard") or "").strip(),
                        str((item or {}).get("run_id") or "").strip(),
                    ),
                )
            ],
        },
        "closing": {
            "headline": str(((config.get("closing") or {}).get("headline")) or "").strip(),
            "body": str(((config.get("closing") or {}).get("body")) or "").strip(),
        },
    }


def load_progress_report_payload(
    *,
    repo_root: pathlib.Path = FLEET_ROOT,
    prefer_generated: bool = True,
    as_of: Optional[dt.date] = None,
) -> Dict[str, Any]:
    if prefer_generated:
        for artifact_path in progress_report_artifact_candidates(repo_root):
            payload = _load_json(artifact_path)
            if payload.get("parts"):
                return payload
    return build_progress_report_payload(repo_root=repo_root, as_of=as_of)


def poster_svg_text(path: Optional[pathlib.Path] = None) -> str:
    target_path = path or progress_poster_path()
    return target_path.read_text(encoding="utf-8")


def _eta_label(low: Any, high: Any) -> str:
    try:
        low_int = int(low)
        high_int = int(high)
    except Exception:
        return ""
    if low_int <= 0 and high_int <= 0:
        return ""
    if low_int == high_int:
        return f"{low_int} weeks"
    return f"{low_int}-{high_int} weeks"


def _display_date(value: Any) -> str:
    parsed = _parse_date(value)
    if parsed is None:
        return str(value or "").strip()
    return parsed.strftime("%B %d, %Y")


def _html_list(items: Sequence[str]) -> str:
    return "".join(items)


def _human_join(items: Sequence[str]) -> str:
    clean = [str(item).strip() for item in items if str(item).strip()]
    if not clean:
        return ""
    if len(clean) == 1:
        return clean[0]
    if len(clean) == 2:
        return f"{clean[0]} and {clean[1]}"
    return f"{', '.join(clean[:-1])}, and {clean[-1]}"


def render_progress_report_html(payload: Dict[str, Any], *, poster_url: str = "/api/public/progress-poster.svg") -> str:
    hero = dict(payload.get("hero") or {})
    brand = html.escape(str(payload.get("brand") or "Chummer6"))
    headline = html.escape(str(hero.get("headline") or ""))
    support = html.escape(str(hero.get("support") or ""))
    overall_progress = int(payload.get("overall_progress_percent") or 0)
    phase_label = html.escape(str(payload.get("phase_label") or ""))
    next_eta = _eta_label(payload.get("next_checkpoint_eta_weeks_low"), payload.get("next_checkpoint_eta_weeks_high"))
    longest_pole = dict(payload.get("longest_pole") or {})
    longest_pole_label = html.escape(str(longest_pole.get("label") or ""))
    as_of_label = html.escape(_display_date(payload.get("as_of")))
    parts_payload = [dict(part or {}) for part in (payload.get("parts") or []) if isinstance(part, dict)]
    part_count = len(parts_payload)
    part_count_label = "part" if part_count == 1 else "parts"
    participation = dict(payload.get("participation") or {})
    participate_href = html.escape(str(participation.get("cta_href") or "#participate"))
    participate_label = html.escape(str(participation.get("cta_label") or "Learn how to participate"))
    participation_headline = html.escape(str(participation.get("headline") or "How to participate"))
    participation_body = html.escape(str(participation.get("body") or ""))
    top_mover_labels = [
        str(part.get("short_public_name") or part.get("public_name") or "").strip()
        for part in sorted(
            [part for part in parts_payload if int(part.get("remaining_open_milestones") or 0) > 0],
            key=lambda part: (
                int(part.get("eta_weeks_low") or 0),
                int(part.get("eta_weeks_high") or 0),
                -int(part.get("progress_percent") or 0),
            ),
        )[:3]
    ]
    next_checkpoint_copy = (
        f"Fastest-moving areas are {html.escape(_human_join(top_mover_labels))}."
        if top_mover_labels
        else "The fastest-moving areas are the ones closest to milestone closure."
    )

    ctas = []
    for item in hero.get("ctas") or []:
        href = html.escape(str((item or {}).get("href") or "#"))
        label = html.escape(str((item or {}).get("label") or "Open"))
        kind = " primary" if str((item or {}).get("kind") or "").strip().lower() == "primary" else ""
        ctas.append(f'<a class="cta{kind}" href="{href}">{label}</a>')

    part_rows = []
    timeline_rows = []
    for part in parts_payload:
        public_name = html.escape(str(part.get("public_name") or ""))
        summary = html.escape(str(part.get("summary") or ""))
        momentum_label = html.escape(str(part.get("momentum_label") or ""))
        eta_label = html.escape(_eta_label(part.get("eta_weeks_low"), part.get("eta_weeks_high")))
        progress_percent = int(part.get("progress_percent") or 0)
        part_rows.append(
            f"""
      <article class="part-row">
        <div class="part-head">
          <div>
            <h3>{public_name}</h3>
            <p>{summary}</p>
          </div>
          <div class="part-meta">
            <div class="meta-chip">{momentum_label} momentum</div>
            <div class="meta-eta">ETA {eta_label}</div>
          </div>
        </div>
        <div class="progress-line" role="img" aria-label="{public_name} progress {progress_percent} percent">
          <span style="width:{progress_percent}%"></span>
        </div>
        <div class="part-foot">
          <strong>{progress_percent}%</strong>
          <span>weighted milestone progress</span>
        </div>
      </article>
""".rstrip()
        )
        steps = []
        for item in part.get("milestones") or []:
            phase = str((item or {}).get("phase") or "").strip().lower()
            title = html.escape(str((item or {}).get("title") or ""))
            body = html.escape(str((item or {}).get("body") or ""))
            kicker = {"landed": "Landed", "now": "Now", "target": "Target"}.get(phase, phase.title() or "Step")
            current = " current" if phase == "now" else ""
            steps.append(
                f"""
          <div class="timeline-step{current}">
            <span class="step-kicker">{html.escape(kicker)}</span>
            <p><strong>{title}</strong>. {body}</p>
          </div>
""".rstrip()
            )
        timeline_rows.append(
            f"""
      <section class="timeline-row">
        <div class="timeline-title">
          <h3>{public_name}</h3>
          <div class="timeline-eta">ETA {eta_label}</div>
        </div>
        <div class="timeline-track">
{_html_list(steps)}
        </div>
      </section>
""".rstrip()
        )

    weekly_rows = []
    for item in payload.get("recent_movement") or []:
        title = html.escape(str((item or {}).get("title") or ""))
        body = html.escape(str((item or {}).get("body") or ""))
        weekly_rows.append(
            f"""
        <div class="weekly-item">
          <strong>{title}</strong>
          <p>{body}</p>
        </div>
""".rstrip()
        )

    limitations = [str(item).strip() for item in ((payload.get("method") or {}).get("limitations") or []) if str(item).strip()]
    limitation_copy = " ".join(html.escape(item) for item in limitations)
    method_copy = html.escape(str(((payload.get("method") or {}).get("copy")) or "").strip())
    closing = dict(payload.get("closing") or {})
    closing_headline = html.escape(str(closing.get("headline") or ""))
    closing_body = html.escape(str(closing.get("body") or ""))

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{brand} Progress Report</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    :root {{
      --bg: #09121b;
      --bg-2: #101b28;
      --bg-3: #162435;
      --paper: #edf3f7;
      --muted: #98a7b6;
      --text: #f6fbff;
      --line: rgba(255,255,255,.12);
      --line-strong: rgba(255,255,255,.24);
      --accent: #6be0c1;
      --accent-2: #f3a95d;
      --accent-3: #89b6ff;
      --good: #8ae59e;
      --shadow: 0 28px 100px rgba(0,0,0,.34);
      --max: 1260px;
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      margin: 0;
      font-family: "Aptos", "IBM Plex Sans", "Segoe UI Variable", "Segoe UI", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at 12% 18%, rgba(107,224,193,.18), transparent 34%),
        radial-gradient(circle at 88% 15%, rgba(137,182,255,.18), transparent 28%),
        linear-gradient(180deg, #08111a 0%, #0b1520 40%, #08121a 100%);
      min-height: 100vh;
      overflow-x: hidden;
    }}
    body::before {{
      content: "";
      position: fixed;
      inset: 0;
      background-image:
        linear-gradient(rgba(255,255,255,.025) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,.025) 1px, transparent 1px);
      background-size: 44px 44px;
      mask-image: linear-gradient(180deg, rgba(0,0,0,.7), rgba(0,0,0,.15));
      pointer-events: none;
    }}
    a:focus-visible {{
      outline: 2px solid rgba(107,224,193,.75);
      outline-offset: 4px;
    }}
    .shell {{ position: relative; z-index: 1; }}
    .hero {{
      position: relative;
      min-height: 96vh;
      padding: 40px 28px 36px;
      display: flex;
      align-items: center;
      overflow: hidden;
      border-bottom: 1px solid var(--line);
    }}
    .hero::after {{
      content: "";
      position: absolute;
      inset: 0;
      background:
        linear-gradient(180deg, rgba(4,8,12,.04) 0%, rgba(4,8,12,.12) 45%, rgba(4,8,12,.52) 100%);
      pointer-events: none;
    }}
    .hero::before {{
      content: "";
      position: absolute;
      inset: 0;
      background:
        radial-gradient(circle at 22% 26%, rgba(107,224,193,.14), transparent 34%),
        radial-gradient(circle at 78% 18%, rgba(243,169,93,.12), transparent 28%),
        radial-gradient(circle at 64% 56%, rgba(137,182,255,.14), transparent 36%);
      pointer-events: none;
      z-index: 1;
    }}
    .hero-visual {{
      position: absolute;
      inset: 0;
      opacity: .9;
      filter: saturate(1.05);
    }}
    .hero-poster {{
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
      animation: posterDrift 18s ease-in-out infinite;
      transform-origin: center center;
    }}
    .hero-copy {{
      width: min(var(--max), calc(100vw - 56px));
      margin: 0 auto;
      position: relative;
      z-index: 2;
      padding-top: 54px;
    }}
    .brand {{
      font-size: clamp(2.5rem, 5.8vw, 5.7rem);
      line-height: .9;
      font-weight: 800;
      letter-spacing: .08em;
      text-transform: uppercase;
      margin: 0 0 20px;
      text-wrap: balance;
    }}
    .hero h1 {{
      margin: 0;
      max-width: 11ch;
      font-size: clamp(2rem, 4.2vw, 4rem);
      line-height: .98;
      letter-spacing: -.03em;
      font-weight: 650;
    }}
    .hero p {{
      margin: 22px 0 0;
      max-width: 54ch;
      font-size: clamp(1rem, 1.6vw, 1.24rem);
      line-height: 1.55;
      color: rgba(246,251,255,.86);
    }}
    .cta-group {{
      display: flex;
      gap: 14px;
      flex-wrap: wrap;
      margin-top: 28px;
    }}
    .cta {{
      appearance: none;
      border: 1px solid var(--line-strong);
      color: var(--text);
      text-decoration: none;
      padding: 14px 18px;
      border-radius: 999px;
      font-size: .96rem;
      letter-spacing: .01em;
      background: rgba(255,255,255,.035);
      backdrop-filter: blur(10px);
      transition: transform .18s ease, border-color .2s ease, background .2s ease;
    }}
    .cta.primary {{
      background: linear-gradient(135deg, rgba(107,224,193,.18), rgba(137,182,255,.14));
      border-color: rgba(107,224,193,.38);
    }}
    .cta:hover {{
      transform: translateY(-1px);
      border-color: rgba(255,255,255,.42);
      background: rgba(255,255,255,.07);
    }}
    .section {{
      width: min(var(--max), calc(100vw - 56px));
      margin: 0 auto;
      padding: 72px 0;
    }}
    .section-header {{
      max-width: 62ch;
      margin-bottom: 28px;
    }}
    .kicker {{
      display: inline-flex;
      align-items: center;
      gap: 10px;
      font-size: .76rem;
      text-transform: uppercase;
      letter-spacing: .18em;
      color: var(--muted);
      margin-bottom: 16px;
    }}
    .kicker::before {{
      content: "";
      width: 34px;
      height: 1px;
      background: linear-gradient(90deg, var(--accent), transparent);
    }}
    .section h2 {{
      margin: 0;
      font-size: clamp(1.7rem, 2.8vw, 3rem);
      line-height: 1.03;
      letter-spacing: -.03em;
      font-weight: 680;
      text-wrap: balance;
    }}
    .section-header p {{
      margin: 14px 0 0;
      color: rgba(246,251,255,.78);
      line-height: 1.65;
      font-size: 1.05rem;
    }}
    .pulse-band {{
      width: min(var(--max), calc(100vw - 56px));
      margin: -88px auto 0;
      position: relative;
      z-index: 3;
      border: 1px solid rgba(255,255,255,.1);
      background:
        linear-gradient(180deg, rgba(255,255,255,.05), rgba(255,255,255,.02));
      backdrop-filter: blur(14px);
      box-shadow: var(--shadow);
    }}
    .pulse-grid {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
    }}
    .pulse-cell {{
      padding: 24px 24px 22px;
      border-right: 1px solid var(--line);
    }}
    .pulse-cell:last-child {{ border-right: 0; }}
    .pulse-label {{
      display: block;
      font-size: .76rem;
      letter-spacing: .16em;
      text-transform: uppercase;
      color: var(--muted);
      margin-bottom: 8px;
    }}
    .pulse-value {{
      display: block;
      font-size: clamp(1.6rem, 3.2vw, 2.5rem);
      line-height: 1;
      letter-spacing: -.03em;
      font-weight: 700;
    }}
    .pulse-copy {{
      display: block;
      margin-top: 8px;
      color: rgba(246,251,255,.76);
      font-size: .96rem;
      line-height: 1.45;
      max-width: 24ch;
    }}
    .part-list, .timeline-wrap, .weekly-list {{
      border-top: 1px solid var(--line);
    }}
    .part-row, .timeline-row, .weekly-item {{
      border-bottom: 1px solid var(--line);
    }}
    .part-row {{
      padding: 26px 0 22px;
    }}
    .part-head {{
      display: flex;
      justify-content: space-between;
      gap: 20px;
      align-items: flex-start;
      margin-bottom: 18px;
    }}
    .part-head h3 {{
      margin: 0 0 8px;
      font-size: 1.4rem;
      line-height: 1.05;
      letter-spacing: -.02em;
    }}
    .part-head p {{
      margin: 0;
      color: rgba(246,251,255,.74);
      max-width: 58ch;
      line-height: 1.58;
    }}
    .part-meta {{
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      gap: 10px;
      flex-shrink: 0;
      min-width: 150px;
    }}
    .meta-chip {{
      padding: 8px 12px;
      border: 1px solid rgba(107,224,193,.28);
      background: rgba(107,224,193,.08);
      color: #cbfff1;
      border-radius: 999px;
      font-size: .78rem;
      letter-spacing: .08em;
      text-transform: uppercase;
    }}
    .meta-eta {{
      font-size: 1rem;
      color: rgba(246,251,255,.86);
      font-weight: 600;
    }}
    .progress-line {{
      height: 10px;
      width: 100%;
      border-radius: 999px;
      background: rgba(255,255,255,.08);
      overflow: hidden;
      position: relative;
    }}
    .progress-line span {{
      display: block;
      height: 100%;
      border-radius: inherit;
      background:
        linear-gradient(90deg, var(--accent), var(--accent-3), var(--accent-2));
      box-shadow: 0 0 32px rgba(107,224,193,.36);
      animation: fillReveal 1.1s ease both;
    }}
    .part-foot {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: baseline;
      margin-top: 10px;
      color: rgba(246,251,255,.76);
    }}
    .part-foot strong {{
      font-size: 1.18rem;
      color: var(--text);
      letter-spacing: -.02em;
    }}
    .timeline-row {{
      padding: 28px 0 30px;
    }}
    .timeline-title {{
      display: flex;
      justify-content: space-between;
      gap: 18px;
      align-items: baseline;
      margin-bottom: 16px;
    }}
    .timeline-title h3 {{
      margin: 0;
      font-size: 1.35rem;
      letter-spacing: -.02em;
    }}
    .timeline-eta {{
      color: rgba(246,251,255,.76);
      font-weight: 600;
    }}
    .timeline-track {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 18px;
      position: relative;
    }}
    .timeline-track::before {{
      content: "";
      position: absolute;
      top: 18px;
      left: 0;
      right: 0;
      height: 1px;
      background: linear-gradient(90deg, rgba(255,255,255,.14), rgba(255,255,255,.08));
      z-index: 0;
    }}
    .timeline-step {{
      position: relative;
      padding-top: 38px;
    }}
    .timeline-step::before {{
      content: "";
      position: absolute;
      top: 8px;
      left: 0;
      width: 18px;
      height: 18px;
      border-radius: 50%;
      border: 3px solid rgba(255,255,255,.4);
      background: var(--bg);
      z-index: 1;
    }}
    .timeline-step.current::before {{
      border-color: var(--accent);
      box-shadow: 0 0 0 10px rgba(107,224,193,.08);
      animation: pulse 2.4s infinite ease-in-out;
    }}
    .step-kicker {{
      display: inline-block;
      font-size: .76rem;
      text-transform: uppercase;
      letter-spacing: .14em;
      color: var(--muted);
      margin-bottom: 8px;
    }}
    .timeline-step p {{
      margin: 0;
      color: rgba(246,251,255,.82);
      line-height: 1.58;
    }}
    .timeline-step strong {{
      color: var(--text);
    }}
    .weekly-item {{
      display: grid;
      grid-template-columns: 220px 1fr;
      gap: 18px;
      padding: 18px 0;
    }}
    .weekly-item strong {{
      display: block;
      font-size: 1rem;
      line-height: 1.25;
    }}
    .weekly-item p {{
      margin: 0;
      color: rgba(246,251,255,.78);
      line-height: 1.65;
    }}
    .method {{
      border: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(255,255,255,.04), rgba(255,255,255,.02));
      padding: 28px;
    }}
    .method p {{
      margin: 0;
      color: rgba(246,251,255,.8);
      line-height: 1.7;
      max-width: 75ch;
    }}
    .closing {{
      padding-top: 24px;
      padding-bottom: 110px;
    }}
    .closing p {{
      max-width: 58ch;
      font-size: clamp(1.1rem, 1.7vw, 1.28rem);
      color: rgba(246,251,255,.86);
      line-height: 1.7;
    }}
    .footer-note {{
      color: var(--muted);
      font-size: .88rem;
      margin-top: 18px;
    }}
    @keyframes pulse {{
      0%, 100% {{ transform: scale(1); box-shadow: 0 0 0 10px rgba(107,224,193,.08); }}
      50% {{ transform: scale(1.08); box-shadow: 0 0 0 18px rgba(107,224,193,.02); }}
    }}
    @keyframes posterDrift {{
      0%, 100% {{ transform: scale(1.03) translate3d(0, 0, 0); }}
      50% {{ transform: scale(1.07) translate3d(0, -8px, 0); }}
    }}
    @keyframes fillReveal {{
      from {{ transform: scaleX(.2); transform-origin: left center; filter: saturate(.7); }}
      to {{ transform: scaleX(1); transform-origin: left center; filter: saturate(1); }}
    }}
    @media (prefers-reduced-motion: reduce) {{
      html {{ scroll-behavior: auto; }}
      *, *::before, *::after {{
        animation: none !important;
        transition: none !important;
      }}
    }}
    @media (max-width: 980px) {{
      .pulse-grid {{ grid-template-columns: repeat(2, 1fr); }}
      .pulse-cell:nth-child(2) {{ border-right: 0; }}
      .pulse-cell:nth-child(-n+2) {{ border-bottom: 1px solid var(--line); }}
      .timeline-track {{ grid-template-columns: 1fr; gap: 12px; }}
      .timeline-track::before {{ display: none; }}
      .timeline-step {{ padding-top: 0; padding-left: 34px; }}
      .timeline-step::before {{ top: 4px; }}
      .weekly-item {{ grid-template-columns: 1fr; gap: 8px; }}
    }}
    @media (max-width: 760px) {{
      .hero {{ min-height: auto; padding: 26px 18px 32px; }}
      .hero-copy, .section, .pulse-band {{ width: min(var(--max), calc(100vw - 36px)); }}
      .pulse-band {{ margin-top: -44px; }}
      .part-head, .timeline-title {{ flex-direction: column; align-items: flex-start; }}
      .part-meta {{ align-items: flex-start; min-width: 0; }}
      .section {{ padding: 58px 0; }}
      .pulse-grid {{ grid-template-columns: 1fr; }}
      .pulse-cell {{ border-right: 0; border-bottom: 1px solid var(--line); }}
      .pulse-cell:last-child {{ border-bottom: 0; }}
      .brand {{ letter-spacing: .06em; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <header class="hero">
      <div class="hero-visual" aria-hidden="true">
        <img class="hero-poster" src="{html.escape(poster_url)}" alt="" decoding="async" fetchpriority="high" />
      </div>
      <div class="hero-copy">
        <div class="brand">{brand}</div>
        <h1>{headline}</h1>
        <p>{support}</p>
        <div class="cta-group">
          {_html_list(ctas)}
        </div>
      </div>
    </header>

    <section class="pulse-band" id="program" aria-label="Program pulse">
      <div class="pulse-grid">
        <div class="pulse-cell">
          <span class="pulse-label">Overall progress</span>
          <span class="pulse-value">{overall_progress}%</span>
          <span class="pulse-copy">Weighted milestone completion across the {part_count} public product {part_count_label}.</span>
        </div>
        <div class="pulse-cell">
          <span class="pulse-label">Current phase</span>
          <span class="pulse-value">{phase_label}</span>
          <span class="pulse-copy">The architecture is real; the focus is on making it boring, fast, and public-ready.</span>
        </div>
        <div class="pulse-cell">
          <span class="pulse-label">Next checkpoint</span>
          <span class="pulse-value">{html.escape(next_eta)}</span>
          <span class="pulse-copy">{next_checkpoint_copy}</span>
        </div>
        <div class="pulse-cell">
          <span class="pulse-label">Longest pole</span>
          <span class="pulse-value">{longest_pole_label}</span>
          <span class="pulse-copy">Hosted account, registry, and media surfaces still carry the deepest remaining completion wave.</span>
        </div>
      </div>
    </section>

    <section class="section">
      <div class="section-header">
        <div class="kicker">Public view</div>
        <h2>Where the program stands right now.</h2>
        <p>These are the product parts a normal reader can understand without caring how the repos are split. Each line shows weighted progress, recent momentum, and a near-term ETA based on the current milestone map and the recent delivery pace.</p>
      </div>
      <div class="part-list">
{_html_list(part_rows)}
      </div>
    </section>

    <section class="section" id="timeline">
      <div class="section-header">
        <div class="kicker">Timeline by product area</div>
        <h2>Major milestones, from what just landed to what comes next.</h2>
        <p>This is the public-facing version of the roadmap: one timeline per product part, focused on what changed, what is actively being closed, and what a complete checkpoint should look like.</p>
      </div>
      <div class="timeline-wrap">
{_html_list(timeline_rows)}
      </div>
    </section>

    <section class="section">
      <div class="section-header">
        <div class="kicker">Recent movement</div>
        <h2>What changed in the latest delivery burst.</h2>
      </div>
      <div class="weekly-list">
{_html_list(weekly_rows)}
      </div>
    </section>

    <section class="section" id="method">
      <div class="section-header">
        <div class="kicker">Method</div>
        <h2>How the progress and ETA are calculated.</h2>
      </div>
      <div class="method">
        <p>{method_copy} {limitation_copy}</p>
      </div>
    </section>

    <section class="section" id="participate">
      <div class="section-header">
        <div class="kicker">Participation</div>
        <h2>{participation_headline}</h2>
      </div>
      <div class="method">
        <p>{participation_body} <a class="cta primary" href="{participate_href}" style="margin-left: 0.75rem; display: inline-flex; align-items: center;">{participate_label}</a></p>
      </div>
    </section>

    <section class="section closing">
      <div class="section-header">
        <div class="kicker">What this means</div>
        <h2>{closing_headline}</h2>
      </div>
      <p>{closing_body}</p>
      <div class="footer-note">Status snapshot: {as_of_label}.</div>
    </section>
  </div>
</body>
</html>
"""
