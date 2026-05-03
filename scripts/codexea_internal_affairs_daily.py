#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import os
import fcntl
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


WATCHDOG_SCRIPT = Path("/home/tibor/codexea-internal-affairs-watchdog.sh")
WATCHDOG_UNIT = "codexea-internal-affairs-watchdog.service"
WATCH_ROOT = Path("/tmp/codexea-internal-affairs-watch")
RUNS_DIR = WATCH_ROOT / "runs"
FLEET_HEALTH_RUNS_DIR = Path("/tmp/codexea-fleet-health-watch/runs")
PID_FILE = WATCH_ROOT / "supervisor.pid"
STATE_DIR = Path.home() / ".local" / "state" / "codexea-internal-affairs"
LOCK_FILE = STATE_DIR / "daily.lock"
STATE_FILE = STATE_DIR / "daily-state.json"
LOG_FILE = STATE_DIR / "daily.log"
FLEET_STATE = Path("/docker/fleet/state/chummer_design_supervisor/state.json")
FLEET_STATE_MATERIALIZED = Path("/docker/fleet/state/chummer_design_supervisor/status-live-refresh.materialized.json")
DEFAULT_RECIPIENT = "tibor.girschele@gmail.com"
DEFAULT_SENDER_EMAIL = "ia@chummer.run"
DEFAULT_SENDER_NAME = "Internal Affairs"
LOCAL_TZ = ZoneInfo(os.environ.get("CODEXEA_INTERNAL_AFFAIRS_TIMEZONE", "Europe/Vienna"))
EA_ENV_FILE = Path("/docker/EA/.env")


def log(message: str) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(tz=LOCAL_TZ).isoformat()
    LOG_FILE.open("a", encoding="utf-8").write(f"[{stamp}] {message}\n")


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def load_state() -> dict[str, Any]:
    payload = load_json(STATE_FILE, {})
    return payload if isinstance(payload, dict) else {}


def save_state(payload: dict[str, Any]) -> None:
    save_json(STATE_FILE, payload)


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def parse_utc_timestamp(value: Any) -> dt.datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def systemd_watchdog_pid() -> int | None:
    try:
        active = subprocess.run(
            ["systemctl", "--user", "is-active", WATCHDOG_UNIT],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return None
    if active.returncode != 0 or active.stdout.strip() != "active":
        return None
    try:
        show = subprocess.run(
            ["systemctl", "--user", "show", "--property=MainPID", "--value", WATCHDOG_UNIT],
            capture_output=True,
            text=True,
            check=False,
        )
        pid = int((show.stdout or "0").strip() or "0")
    except Exception:
        return None
    if pid > 0 and pid_alive(pid):
        PID_FILE.write_text(f"{pid}\n", encoding="utf-8")
        return pid
    return None


def current_watchdog_pid() -> int | None:
    pid = systemd_watchdog_pid()
    if pid is not None:
        return pid
    try:
        pid = int(PID_FILE.read_text(encoding="utf-8").strip() or "0")
    except Exception:
        pid = 0
    if pid > 0 and pid_alive(pid):
        return pid
    try:
        completed = subprocess.run(
            ["pgrep", "-f", str(WATCHDOG_SCRIPT)],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return None
    for raw in completed.stdout.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            candidate = int(raw)
        except ValueError:
            continue
        if candidate != os.getpid() and pid_alive(candidate):
            PID_FILE.write_text(f"{candidate}\n", encoding="utf-8")
            return candidate
    return None


def start_watchdog(*, dry_run: bool) -> str:
    pid = current_watchdog_pid()
    if pid is not None:
        return f"already running pid={pid}"
    if dry_run:
        return "dry-run start skipped"
    start = subprocess.run(
        ["systemctl", "--user", "start", WATCHDOG_UNIT],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    if start.returncode != 0:
        subprocess.run(
            [
                "systemd-run",
                "--user",
                "--unit=codexea-internal-affairs-watchdog",
                "--collect",
                "--property=WorkingDirectory=/home/tibor",
                str(WATCHDOG_SCRIPT),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            check=False,
        )
    time.sleep(2)
    pid = current_watchdog_pid()
    return f"started pid={pid}" if pid is not None else "start requested; pid not confirmed yet"


def parse_run_dir_started_at(run_dir: Path) -> dt.datetime | None:
    try:
        return dt.datetime.strptime(run_dir.name, "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def run_summary(run_dir: Path) -> dict[str, Any]:
    summary = load_json(run_dir / "run-summary.json", {})
    if isinstance(summary, dict) and summary:
        return summary
    exit_status = None
    try:
        exit_status = int((run_dir / "exit_status.txt").read_text(encoding="utf-8").strip())
    except Exception:
        exit_status = None
    last_message = ""
    try:
        last_message = "\n".join((run_dir / "last_message.txt").read_text(encoding="utf-8", errors="ignore").splitlines()[:3]).strip()
    except Exception:
        last_message = ""
    stderr_tail = []
    try:
        stderr_tail = (run_dir / "stderr.log").read_text(encoding="utf-8", errors="ignore").splitlines()[-8:]
    except Exception:
        stderr_tail = []
    return {
        "lane": "core",
        "started_at": "",
        "finished_at": "",
        "exit_status": exit_status,
        "status_reason": "inflight" if exit_status is None else "",
        "changed_files": [],
        "before": {},
        "after": {},
        "last_message_excerpt": last_message,
        "stderr_tail": stderr_tail,
    }


def summaries_for_date(target_date: dt.date) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    run_roots = {
        "internal_affairs": RUNS_DIR,
        "fleet_health": FLEET_HEALTH_RUNS_DIR,
    }
    for watchdog, root in run_roots.items():
        if not root.exists():
            continue
        for run_dir in sorted([path for path in root.iterdir() if path.is_dir()]):
            started_utc = parse_run_dir_started_at(run_dir)
            if started_utc is None:
                continue
            started_local = started_utc.astimezone(LOCAL_TZ)
            if started_local.date() != target_date:
                continue
            payload = run_summary(run_dir)
            payload["watchdog"] = str(payload.get("watchdog") or watchdog)
            payload["run_dir"] = str(run_dir)
            payload["started_local"] = started_local.isoformat()
            rows.append(payload)
    rows.sort(key=lambda row: str(row.get("started_local") or ""))
    return rows


def _select_fleet_snapshot(primary: dict[str, Any], secondary: dict[str, Any]) -> dict[str, Any]:
    primary_ts = parse_utc_timestamp(primary.get("updated_at"))
    secondary_ts = parse_utc_timestamp(secondary.get("updated_at"))
    if secondary_ts and (not primary_ts or secondary_ts > primary_ts):
        chosen, fallback = secondary, primary
    else:
        chosen, fallback = primary, secondary
    merged = dict(fallback)
    merged.update(chosen)
    for key, value in fallback.items():
        if merged.get(key) in (None, "") and value not in (None, ""):
            merged[key] = value
    return merged


def current_fleet_snapshot() -> dict[str, Any]:
    primary = load_json(FLEET_STATE, {})
    materialized = load_json(FLEET_STATE_MATERIALIZED, {})
    primary = primary if isinstance(primary, dict) else {}
    materialized = materialized if isinstance(materialized, dict) else {}
    if primary and materialized:
        return _select_fleet_snapshot(primary, materialized)
    if primary:
        return primary
    if materialized:
        return materialized
    return {}


def compact_fleet_status(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "updated_at": payload.get("updated_at"),
        "active_runs_count": payload.get("active_runs_count"),
        "productive_active_runs_count": payload.get("productive_active_runs_count"),
        "waiting_active_runs_count": payload.get("waiting_active_runs_count"),
        "nonproductive_active_runs_count": payload.get("nonproductive_active_runs_count"),
        "remaining_open_milestones": payload.get("remaining_open_milestones"),
        "allowed_active_shards": payload.get("allowed_active_shards"),
        "last_run_blocker": payload.get("last_run_blocker"),
        "preflight_failure_reason": payload.get("preflight_failure_reason"),
    }


def record_run_state(
    *,
    target_date: dt.date,
    dry_run: bool,
    summary_status: str | None,
    watchdog_status: str | None,
) -> dict[str, Any]:
    state = load_state()
    state["last_run_at"] = dt.datetime.now(tz=LOCAL_TZ).isoformat()
    state["last_target_date"] = target_date.isoformat()
    state["last_dry_run"] = bool(dry_run)
    state["last_summary_status"] = str(summary_status or "").strip()
    state["last_watchdog_action"] = str(watchdog_status or "").strip()
    results = [item for item in [state["last_summary_status"], state["last_watchdog_action"]] if item]
    state["last_results"] = results
    snapshot = current_fleet_snapshot()
    state["last_fleet_status"] = compact_fleet_status(snapshot)
    state["fleet_snapshot"] = snapshot
    save_state(state)
    return state


def derive_changed_files_from_run_dir(run_dir: Path) -> list[str]:
    changed_files: list[str] = []
    for label in ("fleet", "ea"):
        before_path = run_dir / f"git-before-{label}.txt"
        after_path = run_dir / f"git-after-{label}.txt"
        before_lines = {
            line.rstrip()
            for line in before_path.read_text(encoding="utf-8", errors="ignore").splitlines()
            if line.strip()
        } if before_path.exists() else set()
        after_lines = {
            line.rstrip()
            for line in after_path.read_text(encoding="utf-8", errors="ignore").splitlines()
            if line.strip()
        } if after_path.exists() else set()
        for line in sorted(after_lines - before_lines):
            payload = line[3:].strip() if len(line) > 3 else line.strip()
            if " -> " in payload:
                payload = payload.split(" -> ", 1)[1].strip()
            if payload:
                changed_files.append(payload)
    return sorted(dict.fromkeys(changed_files))


def blocker_text(value: Any) -> str:
    text = str(value or "").strip()
    return text if text else "none"


def build_summary(target_date: dt.date) -> tuple[str, str, str]:
    rows = summaries_for_date(target_date)
    completed_rows = [row for row in rows if row.get("exit_status") is not None]
    inflight_rows = [row for row in rows if row.get("exit_status") is None]
    current = current_fleet_snapshot()
    lane_counts: collections.Counter[str] = collections.Counter()
    watchdog_counts: collections.Counter[str] = collections.Counter()
    exit_counts: collections.Counter[str] = collections.Counter()
    status_reason_counts: collections.Counter[str] = collections.Counter()
    blockers_before: collections.Counter[str] = collections.Counter()
    blockers_after: collections.Counter[str] = collections.Counter()
    changed_files_counter: collections.Counter[str] = collections.Counter()
    wait_delta_total = 0
    productive_delta_total = 0
    changed_cycle_count = 0

    highlights: list[str] = []
    for row in completed_rows:
        watchdog = str(row.get("watchdog") or "unknown").strip() or "unknown"
        lane = str(row.get("lane") or "core").strip() or "core"
        status_reason = str(row.get("status_reason") or "").strip()
        watchdog_counts[watchdog] += 1
        lane_counts[lane] += 1
        exit_counts[str(row.get("exit_status"))] += 1
        if status_reason:
            status_reason_counts[status_reason] += 1
        before = row.get("before") or {}
        after = row.get("after") or {}
        blockers_before[blocker_text(before.get("last_run_blocker") or before.get("preflight_failure_reason"))] += 1
        blockers_after[blocker_text(after.get("last_run_blocker") or after.get("preflight_failure_reason"))] += 1
        wait_before = int(before.get("waiting_active_runs_count") or 0)
        wait_after = int(after.get("waiting_active_runs_count") or 0)
        prod_before = int(before.get("productive_active_runs_count") or 0)
        prod_after = int(after.get("productive_active_runs_count") or 0)
        wait_delta_total += wait_after - wait_before
        productive_delta_total += prod_after - prod_before
        run_dir_value = str(row.get("run_dir") or "").strip()
        changed_files = []
        if run_dir_value:
            changed_files = derive_changed_files_from_run_dir(Path(run_dir_value))
        if not changed_files:
            changed_files = [str(item).strip() for item in (row.get("changed_files") or []) if str(item).strip()]
        if changed_files:
            changed_cycle_count += 1
            for path in changed_files:
                changed_files_counter[path] += 1
            sample = ", ".join(changed_files[:4])
            highlights.append(
                f"- {row.get('started_local')}: watchdog={watchdog}, lane={lane}, touched {len(changed_files)} file(s): {sample}"
            )
        else:
            excerpt = str(row.get("last_message_excerpt") or "").strip()
            if not excerpt:
                stderr_tail = [str(item).strip() for item in (row.get("stderr_tail") or []) if str(item).strip()]
                excerpt = stderr_tail[-1] if stderr_tail else ""
            if excerpt:
                highlights.append(
                    f"- {row.get('started_local')}: watchdog={watchdog}, lane={lane}, surfaced: {excerpt[:220]}"
                )

    top_files = [f"{path} ({count})" for path, count in changed_files_counter.most_common(8)]
    top_before = [f"{name} ({count})" for name, count in blockers_before.most_common(6)]
    top_after = [f"{name} ({count})" for name, count in blockers_after.most_common(6)]
    current_blocker = blocker_text(
        current.get("last_run_blocker") or current.get("preflight_failure_reason")
    )

    subject = f"CodexEA internal affairs summary for {target_date.isoformat()}"
    preview = (
        f"{len(completed_rows)} completed cycles, {len(inflight_rows)} still in flight, {changed_cycle_count} with code changes, "
        f"{len(changed_files_counter)} unique files touched across internal-affairs and fleet-health, current blocker: {current_blocker}."
    )

    lines = [
        subject,
        "",
        "Current fleet snapshot",
        f"- updated_at: {current.get('updated_at')}",
        f"- active_runs_count: {current.get('active_runs_count')}",
        f"- productive_active_runs_count: {current.get('productive_active_runs_count')}",
        f"- waiting_active_runs_count: {current.get('waiting_active_runs_count')}",
        f"- nonproductive_active_runs_count: {current.get('nonproductive_active_runs_count')}",
        f"- remaining_open_milestones: {current.get('remaining_open_milestones')}",
        f"- allowed_active_shards: {current.get('allowed_active_shards')}",
        f"- current_blocker: {current_blocker}",
        "",
        "Daily statistics",
        f"- cycles observed: {len(rows)}",
        f"- cycles completed: {len(completed_rows)}",
        f"- cycles still in flight at summary time: {len(inflight_rows)}",
        f"- cycles with code changes: {changed_cycle_count}",
        f"- unique files touched: {len(changed_files_counter)}",
        f"- watchdog distribution: {', '.join(f'{watchdog}={count}' for watchdog, count in sorted(watchdog_counts.items())) or 'none'}",
        f"- lane distribution: {', '.join(f'{lane}={count}' for lane, count in sorted(lane_counts.items())) or 'none'}",
        f"- exit statuses: {', '.join(f'{status}={count}' for status, count in sorted(exit_counts.items())) or 'none'}",
        f"- deferred/system reasons: {', '.join(f'{reason}={count}' for reason, count in sorted(status_reason_counts.items())) or 'none'}",
        f"- net waiting delta across cycles: {wait_delta_total}",
        f"- net productive delta across cycles: {productive_delta_total}",
        f"- blockers before cycles: {', '.join(top_before) or 'none'}",
        f"- blockers after cycles: {', '.join(top_after) or 'none'}",
    ]
    if inflight_rows:
        samples = []
        for row in inflight_rows[:5]:
            samples.append(
                f"{row.get('watchdog') or 'unknown'}:{row.get('lane') or 'core'}:{row.get('started_local') or row.get('run_dir')}"
            )
        lines.append(f"- in-flight cycle samples: {', '.join(samples)}")
    lines.extend(["", "Important findings and fixes"])
    if highlights:
        lines.extend(highlights[:12])
    else:
        lines.append("- No structured findings were recorded for that day.")
    if top_files:
        lines.extend(["", "Top files touched", *[f"- {item}" for item in top_files]])
    body = "\n".join(lines).strip() + "\n"
    return subject, preview, body


def send_summary_email(*, target_date: dt.date, recipient: str, dry_run: bool, force: bool) -> str:
    state = load_state()
    sent = state.get("sent_summaries") or {}
    date_key = target_date.isoformat()
    subject, preview, body = build_summary(target_date)
    if dry_run:
        print(subject)
        print()
        print(body)
        return f"dry-run summary generated for {date_key}"
    if not force and isinstance(sent, dict) and date_key in sent:
        return f"summary already sent for {date_key}"

    load_env_file(EA_ENV_FILE)
    sender_email = str(os.environ.get("EA_INTERNAL_AFFAIRS_EMAIL_FROM") or DEFAULT_SENDER_EMAIL).strip() or DEFAULT_SENDER_EMAIL
    sender_name = str(os.environ.get("EA_INTERNAL_AFFAIRS_EMAIL_NAME") or DEFAULT_SENDER_NAME).strip() or DEFAULT_SENDER_NAME
    sys.path.insert(0, "/docker/EA/ea")
    from app.services.registration_email import send_plaintext_digest_email

    receipt = send_plaintext_digest_email(
        recipient_email=recipient,
        digest_key=f"codexea-internal-affairs-{date_key}",
        headline=subject,
        preview_text=preview,
        plain_text=body,
        sender_email=sender_email,
        sender_name=sender_name,
    )
    sent_payload = dict(sent) if isinstance(sent, dict) else {}
    sent_payload[date_key] = {
        "recipient": recipient,
        "provider": receipt.provider,
        "message_id": receipt.message_id,
        "accepted_at": receipt.accepted_at,
        "subject": subject,
    }
    state["sent_summaries"] = sent_payload
    save_state(state)
    return f"summary sent for {date_key} message_id={receipt.message_id}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send CodexEA internal-affairs daily summaries and ensure the watchdog is running.")
    parser.add_argument("--recipient", default=DEFAULT_RECIPIENT)
    parser.add_argument("--target-date", default="", help="Summary date in YYYY-MM-DD local time. Defaults to yesterday.")
    parser.add_argument("--send-summary-only", action="store_true")
    parser.add_argument("--start-only", action="store_true")
    parser.add_argument("--force-send", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with LOCK_FILE.open("w", encoding="utf-8") as lock_handle:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            print("daily coordinator already running")
            return 0
        args = parse_args()
        if args.target_date:
            target_date = dt.date.fromisoformat(str(args.target_date).strip())
        else:
            target_date = (dt.datetime.now(tz=LOCAL_TZ) - dt.timedelta(days=1)).date()

        results: list[str] = []
        summary_result = ""
        watchdog_result = ""
        if not args.start_only:
            summary_result = send_summary_email(
                target_date=target_date,
                recipient=str(args.recipient or DEFAULT_RECIPIENT).strip(),
                dry_run=bool(args.dry_run),
                force=bool(args.force_send),
            )
            log(summary_result)
            results.append(summary_result)

        if not args.send_summary_only:
            watchdog_result = start_watchdog(dry_run=bool(args.dry_run))
            log(watchdog_result)
            results.append(watchdog_result)

        record_run_state(
            target_date=target_date,
            dry_run=bool(args.dry_run),
            summary_status=summary_result,
            watchdog_status=watchdog_result,
        )

        for item in results:
            print(item)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
