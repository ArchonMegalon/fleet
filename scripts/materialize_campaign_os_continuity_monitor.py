#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

try:
    from scripts.materialize_compile_manifest import repo_root_for_published_path, write_compile_manifest, write_text_atomic
except ModuleNotFoundError:
    from materialize_compile_manifest import repo_root_for_published_path, write_compile_manifest, write_text_atomic


UTC = dt.timezone.utc
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / ".codex-studio" / "published" / "CAMPAIGN_OS_CONTINUITY_LIVENESS.generated.json"
DEFAULT_READINESS = ROOT / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
DEFAULT_JOURNEY = ROOT / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
DEFAULT_SUPPORT = ROOT / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
DEFAULT_PROGRESS_REPORT = ROOT / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
DEFAULT_PROGRESS_HISTORY = ROOT / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
DEFAULT_WEEKLY_PACKET = ROOT / ".codex-studio" / "published" / "WEEKLY_GOVERNOR_PACKET.generated.json"
DEFAULT_COMPLETION_FRONTIER = ROOT / ".codex-studio" / "published" / "COMPLETION_REVIEW_FRONTIER.generated.yaml"

READINESS_WINDOW_MINUTES = 90
JOURNEY_WINDOW_MINUTES = 90
SUPPORT_WINDOW_MINUTES = 90
WEEKLY_PACKET_WINDOW_HOURS = 24 * 8
MONITOR_WINDOW_HOURS = 24
TARGET_WINDOW_DAYS = 120


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize 4-month continuity-liveness monitoring for campaign OS proof fronts."
    )
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="output path")
    parser.add_argument("--readiness-path", default=str(DEFAULT_READINESS), help="flagship readiness proof path")
    parser.add_argument("--journey-path", default=str(DEFAULT_JOURNEY), help="journey gates proof path")
    parser.add_argument("--support-path", default=str(DEFAULT_SUPPORT), help="support packets path")
    parser.add_argument("--progress-report-path", default=str(DEFAULT_PROGRESS_REPORT), help="progress report path")
    parser.add_argument("--progress-history-path", default=str(DEFAULT_PROGRESS_HISTORY), help="progress history path")
    parser.add_argument("--weekly-packet-path", default=str(DEFAULT_WEEKLY_PACKET), help="weekly governor packet path")
    parser.add_argument("--completion-frontier-path", default=str(DEFAULT_COMPLETION_FRONTIER), help="completion frontier path")
    parser.add_argument("--now", default=None, help="optional ISO timestamp override for tests")
    return parser.parse_args(argv)


def _parse_now(raw: str | None) -> dt.datetime:
    if not raw:
        return dt.datetime.now(UTC).replace(microsecond=0)
    clean = str(raw).strip().replace("Z", "+00:00")
    parsed = dt.datetime.fromisoformat(clean)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).replace(microsecond=0)


def _parse_timestamp(value: Any) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _parse_date(value: Any) -> dt.date | None:
    if not value:
        return None
    try:
        return dt.date.fromisoformat(str(value).strip())
    except ValueError:
        return None


def _load_json(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected mapping payload: {path}")
    return data


def _load_yaml(path: Path) -> Dict[str, Any]:
    import yaml

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"expected mapping payload: {path}")
    return data


def _iso(value: dt.datetime | None) -> str:
    if value is None:
        return ""
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _age_minutes(now: dt.datetime, at: dt.datetime | None) -> int | None:
    if at is None:
        return None
    return max(0, int((now - at).total_seconds() // 60))


def _age_hours(now: dt.datetime, at: dt.datetime | None) -> int | None:
    minutes = _age_minutes(now, at)
    if minutes is None:
        return None
    return max(0, minutes // 60)


def _fresh_state(age_minutes: int | None, *, freshness_minutes: int) -> str:
    if age_minutes is None:
        return "missing"
    return "fresh" if age_minutes <= freshness_minutes else "stale"


def _front_state(states: List[str]) -> str:
    if any(state == "blocked" for state in states):
        return "blocked"
    if any(state == "warning" for state in states):
        return "warning"
    if any(state == "warming_up" for state in states):
        return "warming_up"
    return "healthy"


def _snapshot_dates(history_payload: Dict[str, Any]) -> List[dt.date]:
    rows = history_payload.get("snapshots") or []
    dates: List[dt.date] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        parsed = _parse_date(row.get("as_of"))
        if parsed is not None:
            dates.append(parsed)
    return sorted(set(dates))


def _largest_gap_days(dates: List[dt.date]) -> int:
    if len(dates) < 2:
        return 0
    return max((current - previous).days for previous, current in zip(dates, dates[1:]))


def build_payload(
    *,
    now: dt.datetime,
    readiness_path: Path,
    journey_path: Path,
    support_path: Path,
    progress_report_path: Path,
    progress_history_path: Path,
    weekly_packet_path: Path,
    completion_frontier_path: Path,
) -> Dict[str, Any]:
    readiness = _load_json(readiness_path)
    journey = _load_json(journey_path)
    support = _load_json(support_path)
    progress_report = _load_json(progress_report_path)
    progress_history = _load_json(progress_history_path)
    weekly_packet = _load_json(weekly_packet_path)
    completion_frontier = _load_yaml(completion_frontier_path)

    readiness_at = _parse_timestamp(readiness.get("generated_at"))
    journey_at = _parse_timestamp(journey.get("generated_at"))
    support_at = _parse_timestamp(support.get("generated_at"))
    progress_history_at = _parse_timestamp(progress_history.get("generated_at"))
    weekly_at = _parse_timestamp(weekly_packet.get("generated_at"))

    readiness_age = _age_minutes(now, readiness_at)
    journey_age = _age_minutes(now, journey_at)
    support_age = _age_minutes(now, support_at)
    weekly_age_hours = _age_hours(now, weekly_at)

    readiness_freshness = _fresh_state(readiness_age, freshness_minutes=READINESS_WINDOW_MINUTES)
    journey_freshness = _fresh_state(journey_age, freshness_minutes=JOURNEY_WINDOW_MINUTES)
    support_freshness = _fresh_state(support_age, freshness_minutes=SUPPORT_WINDOW_MINUTES)
    weekly_freshness = "missing"
    if weekly_age_hours is not None:
        weekly_freshness = "fresh" if weekly_age_hours <= WEEKLY_PACKET_WINDOW_HOURS else "stale"

    readiness_status = str(readiness.get("status") or "").strip().lower()
    journey_state = str((journey.get("summary") or {}).get("overall_state") or "").strip().lower()
    support_summary = dict(support.get("summary") or {})
    weekly_decision = str((weekly_packet.get("launch_governance") or {}).get("action") or "").strip().lower()

    dates = _snapshot_dates(progress_history)
    earliest_date = dates[0] if dates else None
    latest_date = dates[-1] if dates else None
    coverage_days = max(0, (now.date() - earliest_date).days) if earliest_date else 0
    recent_28d_count = sum(1 for item in dates if (now.date() - item).days <= 28)
    largest_gap_days = _largest_gap_days(dates)
    coverage_state = "meeting_target" if coverage_days >= TARGET_WINDOW_DAYS else "warming_up"

    continuity_states: List[str] = []
    continuity_reasons: List[str] = []
    if readiness_freshness != "fresh":
        continuity_states.append("blocked")
        continuity_reasons.append("flagship readiness proof is stale or missing")
    if journey_freshness != "fresh":
        continuity_states.append("blocked")
        continuity_reasons.append("journey gates proof is stale or missing")
    if readiness_status not in {"pass", "passed", "ready"}:
        continuity_states.append("warning")
        continuity_reasons.append(f"flagship readiness status is {readiness_status or 'missing'}")
    if journey_state == "blocked":
        continuity_states.append("warning")
        continuity_reasons.append("journey gates still report blocked campaign journeys")
    elif journey_state == "warning":
        continuity_states.append("warning")
        continuity_reasons.append("journey gates still report warning posture")

    publication_states: List[str] = []
    publication_reasons: List[str] = []
    progress_report_status = str(progress_report.get("overall_status") or "").strip().lower()
    progress_report_flagship = dict(progress_report.get("flagship_readiness") or {})
    progress_report_backlog = dict(progress_report.get("repo_backlog") or {})
    frontier_completion = dict(completion_frontier.get("completion_audit") or {})
    frontier_backlog = dict(completion_frontier.get("repo_backlog_audit") or {})
    if progress_history_at is None:
        publication_states.append("blocked")
        publication_reasons.append("progress history is missing")
    if str(progress_report.get("generated_at") or "").strip() == "":
        publication_states.append("blocked")
        publication_reasons.append("progress report is missing")
    progress_report_backlog_count = int(progress_report_backlog.get("open_item_count") or 0)
    frontier_backlog_count = int(frontier_backlog.get("open_item_count") or 0)
    if progress_report_backlog_count != frontier_backlog_count:
        publication_states.append("blocked")
        publication_reasons.append(
            f"progress report backlog count ({progress_report_backlog_count}) disagrees with completion frontier backlog count ({frontier_backlog_count})"
        )
    if (
        str(progress_report_flagship.get("status") or "").strip().lower() in {"ready", "pass", "passed"}
        and readiness_status not in {"pass", "passed", "ready"}
    ):
        publication_states.append("blocked")
        publication_reasons.append("progress report claims flagship readiness is ready while current readiness proof is not green")
    if progress_report_status == "complete" and (
        str(frontier_completion.get("status") or "").strip().lower() == "fail"
        or readiness_status not in {"pass", "passed", "ready"}
    ):
        publication_states.append("blocked")
        publication_reasons.append("public progress still claims completion while current closeout proof is failing")
    if weekly_freshness != "fresh":
        publication_states.append("warning")
        publication_reasons.append("weekly governor packet is stale or missing")
    if coverage_state != "meeting_target":
        publication_states.append("warming_up")
        publication_reasons.append(
            f"observed history covers {coverage_days} of {TARGET_WINDOW_DAYS} required days"
        )
    if recent_28d_count < 4:
        publication_states.append("warning")
        publication_reasons.append("progress history has fewer than 4 snapshots in the last 28 days")
    if largest_gap_days > 10:
        publication_states.append("warning")
        publication_reasons.append(f"largest progress-history gap is {largest_gap_days} days")

    support_states: List[str] = []
    support_reasons: List[str] = []
    if support_freshness != "fresh":
        support_states.append("blocked")
        support_reasons.append("support packets are stale or missing")
    if weekly_freshness != "fresh":
        support_states.append("warning")
        support_reasons.append("weekly governor packet freshness is stale or missing")
    if int(support_summary.get("open_non_external_packet_count") or 0) > 0:
        support_states.append("warning")
        support_reasons.append("non-external support packets remain open")
    if int(support_summary.get("needs_human_response") or 0) > 0:
        support_states.append("warning")
        support_reasons.append("support still needs human response")

    fronts = [
        {
            "id": "campaign_continuity",
            "title": "Campaign continuity proof front",
            "state": _front_state(continuity_states),
            "reasons": continuity_reasons,
            "signals": {
                "flagship_readiness_status": readiness_status or "missing",
                "flagship_readiness_freshness": readiness_freshness,
                "journey_gates_state": journey_state or "missing",
                "journey_gates_freshness": journey_freshness,
            },
        },
        {
            "id": "publication_quality",
            "title": "Publication quality and continuity history front",
            "state": _front_state(publication_states),
            "reasons": publication_reasons,
            "signals": {
                "coverage_window_days": coverage_days,
                "required_window_days": TARGET_WINDOW_DAYS,
                "snapshot_count": len(dates),
                "recent_28d_snapshot_count": recent_28d_count,
                "largest_gap_days": largest_gap_days,
                "progress_report_status": progress_report_status or "missing",
                "progress_report_backlog_open_item_count": progress_report_backlog_count,
                "completion_frontier_backlog_open_item_count": frontier_backlog_count,
                "progress_report_flagship_status": str(progress_report_flagship.get("status") or "missing"),
                "weekly_governor_action": weekly_decision or "missing",
            },
        },
        {
            "id": "support_signal_freshness",
            "title": "Support-signal freshness front",
            "state": _front_state(support_states),
            "reasons": support_reasons,
            "signals": {
                "support_packets_freshness": support_freshness,
                "weekly_governor_freshness": weekly_freshness,
                "open_non_external_packet_count": int(support_summary.get("open_non_external_packet_count") or 0),
                "needs_human_response_count": int(support_summary.get("needs_human_response") or 0),
            },
        },
    ]

    front_states = [str(front["state"]) for front in fronts]
    blocking_issue_count = sum(1 for front in fronts if front["state"] == "blocked")
    warning_issue_count = sum(1 for front in fronts if front["state"] == "warning")
    warming_up_count = sum(1 for front in fronts if front["state"] == "warming_up")
    monitor_state = _front_state(front_states)
    status = "pass" if blocking_issue_count == 0 else "fail"

    return {
        "contract_name": "fleet.campaign_os_continuity_liveness",
        "schema_version": 1,
        "generated_at": _iso(now),
        "status": status,
        "monitor_state": monitor_state,
        "summary": {
            "blocking_issue_count": blocking_issue_count,
            "warning_issue_count": warning_issue_count,
            "warming_up_front_count": warming_up_count,
            "coverage_window_days": coverage_days,
            "required_window_days": TARGET_WINDOW_DAYS,
            "snapshot_count": len(dates),
            "recent_28d_snapshot_count": recent_28d_count,
            "largest_gap_days": largest_gap_days,
            "recommended_action": (
                "Keep the 4-month monitor running until coverage reaches the target window."
                if coverage_state != "meeting_target"
                else "4-month continuity monitoring is active on current evidence."
            ),
        },
        "cadence_targets": {
            "readiness_and_journey_refresh_minutes": READINESS_WINDOW_MINUTES,
            "support_refresh_minutes": SUPPORT_WINDOW_MINUTES,
            "weekly_governor_refresh_hours": WEEKLY_PACKET_WINDOW_HOURS,
            "monitor_refresh_hours": MONITOR_WINDOW_HOURS,
            "target_window_days": TARGET_WINDOW_DAYS,
        },
        "coverage": {
            "state": coverage_state,
            "earliest_snapshot_date": earliest_date.isoformat() if earliest_date else "",
            "latest_snapshot_date": latest_date.isoformat() if latest_date else "",
        },
        "fronts": fronts,
        "evidence": {
            "flagship_product_readiness": {
                "path": str(readiness_path),
                "generated_at": _iso(readiness_at),
                "freshness": readiness_freshness,
            },
            "journey_gates": {
                "path": str(journey_path),
                "generated_at": _iso(journey_at),
                "freshness": journey_freshness,
            },
            "support_case_packets": {
                "path": str(support_path),
                "generated_at": _iso(support_at),
                "freshness": support_freshness,
            },
            "progress_history": {
                "path": str(progress_history_path),
                "generated_at": _iso(progress_history_at),
            },
            "progress_report": {
                "path": str(progress_report_path),
                "generated_at": str(progress_report.get("generated_at") or "").strip(),
            },
            "weekly_governor_packet": {
                "path": str(weekly_packet_path),
                "generated_at": _iso(weekly_at),
                "freshness": weekly_freshness,
            },
            "completion_review_frontier": {
                "path": str(completion_frontier_path),
                "generated_at": str(completion_frontier.get("generated_at") or "").strip(),
            },
        },
    }


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    out_path = Path(args.out).resolve()
    try:
        payload = build_payload(
            now=_parse_now(args.now),
            readiness_path=Path(args.readiness_path).resolve(),
            journey_path=Path(args.journey_path).resolve(),
            support_path=Path(args.support_path).resolve(),
            progress_report_path=Path(args.progress_report_path).resolve(),
            progress_history_path=Path(args.progress_history_path).resolve(),
            weekly_packet_path=Path(args.weekly_packet_path).resolve(),
            completion_frontier_path=Path(args.completion_frontier_path).resolve(),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"campaign-os continuity monitor failed: {exc}", file=sys.stderr)
        return 1

    write_text_atomic(out_path, json.dumps(payload, indent=2, sort_keys=False) + "\n")
    repo_root = repo_root_for_published_path(out_path)
    if repo_root is not None:
        write_compile_manifest(repo_root)
    print(f"wrote campaign OS continuity monitor: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
