from __future__ import annotations

import datetime as dt
import html
import json
import math
import os
import pathlib
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

from readiness import project_repo_slug, studio_compile_summary


UTC = dt.timezone.utc
PUBLIC_PROGRESS_CONTRACT_NAME = "fleet.public_progress_report"
PUBLIC_PROGRESS_CONTRACT_VERSION = "2026-03-23"
CHUMMER_DESIGN_ROOT = pathlib.Path("/docker/chummercomplete/chummer-design")
CHUMMER_PRODUCT_CANON_DIR = CHUMMER_DESIGN_ROOT / "products" / "chummer"
CHUMMER_HUB_ROOT = pathlib.Path("/docker/chummercomplete/chummer6-hub")
DEFAULT_PROGRESS_CONFIG_PATH = FLEET_ROOT / "config" / "public_progress_parts.yaml"
DEFAULT_PROGRAM_MILESTONES_PATH = FLEET_ROOT / "config" / "program_milestones.yaml"
DEFAULT_PROJECTS_DIR = FLEET_ROOT / "config" / "projects"
DEFAULT_PROGRESS_REPORT_PATH = FLEET_ROOT / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
DEFAULT_POSTER_PATH = (MOUNTED_ADMIN_DIR if MOUNTED_ADMIN_DIR.exists() else ADMIN_DIR) / "assets" / "progress_poster.svg"
DEFAULT_DB_PATH = pathlib.Path(os.environ.get("FLEET_DB_PATH", str(FLEET_ROOT / "state" / "fleet.db")))
DEFAULT_HUB_PARTICIPATE_URL = "https://chummer.run/participate"
CANON_PROGRESS_CONFIG_PATH = CHUMMER_PRODUCT_CANON_DIR / "PUBLIC_PROGRESS_PARTS.yaml"
CANON_PROGRESS_REPORT_PATH = CHUMMER_PRODUCT_CANON_DIR / "PROGRESS_REPORT.generated.json"
CANON_PROGRESS_HTML_PATH = CHUMMER_PRODUCT_CANON_DIR / "PROGRESS_REPORT.generated.html"
CANON_PROGRESS_POSTER_PATH = CHUMMER_PRODUCT_CANON_DIR / "PROGRESS_REPORT_POSTER.svg"
HUB_PROGRESS_MIRROR_DIR = CHUMMER_HUB_ROOT / ".codex-design" / "product"
HUB_PROGRESS_CONFIG_PATH = HUB_PROGRESS_MIRROR_DIR / "PUBLIC_PROGRESS_PARTS.yaml"
HUB_PROGRESS_REPORT_PATH = HUB_PROGRESS_MIRROR_DIR / "PROGRESS_REPORT.generated.json"
HUB_PROGRESS_HTML_PATH = HUB_PROGRESS_MIRROR_DIR / "PROGRESS_REPORT.generated.html"
HUB_PROGRESS_POSTER_PATH = HUB_PROGRESS_MIRROR_DIR / "PROGRESS_REPORT_POSTER.svg"


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
        candidates.extend([CANON_PROGRESS_REPORT_PATH, local_path])
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
    chosen = "Quiet"
    for row in labels or []:
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
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
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
        "dispatchable_truth_ready_count": dispatchable_truth_ready_count,
        "package_compile_count": package_compile_count,
        "capacity_compile_count": capacity_compile_count,
        "published_artifact_count": published_artifact_count,
        "lifecycle_counts": lifecycle_counts,
    }


def build_progress_report_payload(
    *,
    repo_root: pathlib.Path = FLEET_ROOT,
    as_of: Optional[dt.date] = None,
    commit_counter: Optional[Callable[[pathlib.Path], int]] = None,
    now: Optional[dt.datetime] = None,
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

    current_date = as_of or _parse_date(config.get("as_of")) or dt.datetime.now(tz=UTC).date()
    counter = commit_counter or (lambda repo_path: _recent_commit_count(repo_path, since_days=7))
    booster_summary = booster_participation_summary(
        db_path=repo_root / "state" / "fleet.db",
        now=now or dt.datetime.now(tz=UTC),
    )

    parts: List[Dict[str, Any]] = []
    total_design_weight = 0
    total_open_weight = 0

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
            "source_status": _part_compile_rollup(project_rows),
            "source_projects": project_rows,
        }
        parts.append(part_payload)

    overall_progress_percent = 0
    if total_design_weight > 0:
        overall_progress_percent = int(round(((total_design_weight - total_open_weight) / total_design_weight) * 100))

    active_parts = [row for row in parts if int(row.get("remaining_open_milestones") or 0) > 0]
    next_checkpoint_eta_weeks_low = min((int(row.get("eta_weeks_low") or 0) for row in active_parts), default=0)
    next_checkpoint_eta_weeks_high = min((int(row.get("eta_weeks_high") or 0) for row in active_parts), default=0)
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

    return {
        "contract_name": PUBLIC_PROGRESS_CONTRACT_NAME,
        "contract_version": PUBLIC_PROGRESS_CONTRACT_VERSION,
        "as_of": current_date.isoformat(),
        "brand": str(config.get("brand") or "Chummer6").strip() or "Chummer6",
        "hero": {
            "headline": str(((config.get("hero") or {}).get("headline")) or "").strip(),
            "support": str(((config.get("hero") or {}).get("support")) or "").strip(),
            "ctas": [dict(item or {}) for item in (((config.get("hero") or {}).get("ctas")) or []) if isinstance(item, dict)],
        },
        "overall_progress_percent": overall_progress_percent,
        "phase_label": _phase_label(overall_progress_percent, phase_labels),
        "next_checkpoint_eta_weeks_low": next_checkpoint_eta_weeks_low,
        "next_checkpoint_eta_weeks_high": next_checkpoint_eta_weeks_high,
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
            "average_active_boosters": booster_summary["average_active_boosters"],
            "peak_active_boosters": booster_summary["peak_active_boosters"],
            "window_label": booster_summary["window_label"],
        },
        "method": {
            "progress_formula_version": str(((config.get("method") or {}).get("progress_formula_version")) or "public_progress_v1"),
            "eta_formula_version": str(((config.get("method") or {}).get("eta_formula_version")) or "momentum_proxy_v1"),
            "copy": str(((config.get("method") or {}).get("copy")) or "").strip(),
            "limitations": [str(item).strip() for item in (((config.get("method") or {}).get("limitations")) or []) if str(item).strip()],
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
    participation = dict(payload.get("participation") or {})
    booster_average = float(participation.get("average_active_boosters") or 0.0)
    booster_window_label = html.escape(str(participation.get("window_label") or ""))
    participate_href = html.escape(str(participation.get("cta_href") or "#participate"))
    participate_label = html.escape(str(participation.get("cta_label") or "Learn how to participate"))
    participation_headline = html.escape(str(participation.get("headline") or "How to participate"))
    participation_body = html.escape(str(participation.get("body") or ""))

    ctas = []
    for item in hero.get("ctas") or []:
        href = html.escape(str((item or {}).get("href") or "#"))
        label = html.escape(str((item or {}).get("label") or "Open"))
        kind = " primary" if str((item or {}).get("kind") or "").strip().lower() == "primary" else ""
        ctas.append(f'<a class="cta{kind}" href="{href}">{label}</a>')

    part_rows = []
    timeline_rows = []
    for part in payload.get("parts") or []:
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
    .booster-note {{
      width: min(var(--max), calc(100vw - 56px));
      margin: 18px auto 0;
      padding: 20px 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 18px;
      border-top: 1px solid var(--line);
      border-bottom: 1px solid var(--line);
      color: rgba(246,251,255,.84);
    }}
    .booster-note strong {{
      color: var(--text);
      letter-spacing: -.02em;
    }}
    .booster-note a {{
      color: #d7fff3;
      text-decoration: none;
      border-bottom: 1px solid rgba(107,224,193,.38);
    }}
    .booster-note a:hover {{
      border-color: rgba(107,224,193,.72);
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
      .booster-note {{ width: min(var(--max), calc(100vw - 36px)); flex-direction: column; align-items: flex-start; }}
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
          <span class="pulse-copy">Weighted milestone completion across the six public product parts.</span>
        </div>
        <div class="pulse-cell">
          <span class="pulse-label">Current phase</span>
          <span class="pulse-value">{phase_label}</span>
          <span class="pulse-copy">The architecture is real; the focus is on making it boring, fast, and public-ready.</span>
        </div>
        <div class="pulse-cell">
          <span class="pulse-label">Next checkpoint</span>
          <span class="pulse-value">{html.escape(next_eta)}</span>
          <span class="pulse-copy">Fastest-moving areas are Mission Control, Live Play, and Canon.</span>
        </div>
        <div class="pulse-cell">
          <span class="pulse-label">Longest pole</span>
          <span class="pulse-value">{longest_pole_label}</span>
          <span class="pulse-copy">Hosted account, registry, and media surfaces still carry the deepest remaining completion wave.</span>
        </div>
      </div>
    </section>

    <section class="booster-note" aria-label="Booster participation note">
      <div><strong>{booster_window_label}:</strong> {booster_average:.1f}. Lower sustained booster count directly slows progress.</div>
      <a href="#participate">See how to participate</a>
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
