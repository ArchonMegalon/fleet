from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path("/docker/fleet/scripts/materialize_campaign_os_continuity_monitor.py")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_campaign_os_continuity_monitor_publishes_warming_up_window(tmp_path: Path) -> None:
    readiness = tmp_path / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    journey = tmp_path / "JOURNEY_GATES.generated.json"
    support = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    progress_report = tmp_path / "PROGRESS_REPORT.generated.json"
    progress_history = tmp_path / "PROGRESS_HISTORY.generated.json"
    weekly = tmp_path / "WEEKLY_GOVERNOR_PACKET.generated.json"
    completion_frontier = tmp_path / "COMPLETION_REVIEW_FRONTIER.generated.yaml"
    out = tmp_path / "CAMPAIGN_OS_CONTINUITY_LIVENESS.generated.json"

    _write_json(
        readiness,
        {
            "generated_at": "2026-04-18T17:00:00Z",
            "status": "fail",
        },
    )
    _write_json(
        journey,
        {
            "generated_at": "2026-04-18T17:05:00Z",
            "summary": {"overall_state": "blocked"},
        },
    )
    _write_json(
        support,
        {
            "generated_at": "2026-04-18T17:10:00Z",
            "summary": {"open_non_external_packet_count": 1, "needs_human_response": 0},
        },
    )
    _write_json(
        progress_report,
        {
            "generated_at": "2026-04-18T17:11:00Z",
            "overall_status": "active",
            "repo_backlog": {"open_item_count": 0},
            "flagship_readiness": {"status": "warning"},
        },
    )
    _write_json(
        progress_history,
        {
            "generated_at": "2026-04-18T17:12:00Z",
            "snapshots": [
                {"as_of": "2026-03-23"},
                {"as_of": "2026-03-30"},
                {"as_of": "2026-04-06"},
                {"as_of": "2026-04-13"},
            ],
        },
    )
    _write_json(
        weekly,
        {
            "generated_at": "2026-04-16T19:01:44Z",
            "launch_governance": {"action": "hold"},
        },
    )
    completion_frontier.write_text(
        "completion_audit:\n  status: fail\nrepo_backlog_audit:\n  open_item_count: 0\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--readiness-path",
            str(readiness),
            "--journey-path",
            str(journey),
            "--support-path",
            str(support),
            "--progress-report-path",
            str(progress_report),
            "--progress-history-path",
            str(progress_history),
            "--weekly-packet-path",
            str(weekly),
            "--completion-frontier-path",
            str(completion_frontier),
            "--out",
            str(out),
            "--now",
            "2026-04-18T18:00:00Z",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["status"] == "pass"
    assert payload["monitor_state"] == "warning"
    assert payload["coverage"]["state"] == "warming_up"
    assert payload["summary"]["coverage_window_days"] == 26
    assert payload["summary"]["blocking_issue_count"] == 0
    assert payload["summary"]["warning_issue_count"] >= 1
    assert any(front["id"] == "publication_quality" and front["state"] == "warming_up" for front in payload["fronts"])


def test_campaign_os_continuity_monitor_fails_when_required_inputs_are_missing(tmp_path: Path) -> None:
    readiness = tmp_path / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    readiness.write_text('{"generated_at":"2026-04-18T17:00:00Z","status":"pass"}\n', encoding="utf-8")
    out = tmp_path / "CAMPAIGN_OS_CONTINUITY_LIVENESS.generated.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--readiness-path",
            str(readiness),
            "--journey-path",
            str(tmp_path / "missing-journey.json"),
            "--support-path",
            str(tmp_path / "missing-support.json"),
            "--progress-report-path",
            str(tmp_path / "missing-progress-report.json"),
            "--progress-history-path",
            str(tmp_path / "missing-history.json"),
            "--weekly-packet-path",
            str(tmp_path / "missing-weekly.json"),
            "--completion-frontier-path",
            str(tmp_path / "missing-frontier.yaml"),
            "--out",
            str(out),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert not out.exists()
    assert "campaign-os continuity monitor failed" in result.stderr


def test_campaign_os_continuity_monitor_blocks_publication_quality_drift(tmp_path: Path) -> None:
    readiness = tmp_path / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    journey = tmp_path / "JOURNEY_GATES.generated.json"
    support = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    progress_report = tmp_path / "PROGRESS_REPORT.generated.json"
    progress_history = tmp_path / "PROGRESS_HISTORY.generated.json"
    weekly = tmp_path / "WEEKLY_GOVERNOR_PACKET.generated.json"
    completion_frontier = tmp_path / "COMPLETION_REVIEW_FRONTIER.generated.yaml"
    out = tmp_path / "CAMPAIGN_OS_CONTINUITY_LIVENESS.generated.json"

    _write_json(readiness, {"generated_at": "2026-04-18T17:00:00Z", "status": "fail"})
    _write_json(journey, {"generated_at": "2026-04-18T17:05:00Z", "summary": {"overall_state": "ready"}})
    _write_json(support, {"generated_at": "2026-04-18T17:10:00Z", "summary": {"open_non_external_packet_count": 0, "needs_human_response": 0}})
    _write_json(
        progress_report,
        {
            "generated_at": "2026-04-18T17:11:00Z",
            "overall_status": "complete",
            "repo_backlog": {"open_item_count": 0},
            "flagship_readiness": {"status": "ready"},
        },
    )
    _write_json(
        progress_history,
        {
            "generated_at": "2026-04-18T17:12:00Z",
            "snapshots": [{"as_of": "2026-04-10"}, {"as_of": "2026-04-12"}, {"as_of": "2026-04-15"}, {"as_of": "2026-04-18"}],
        },
    )
    _write_json(weekly, {"generated_at": "2026-04-18T17:20:00Z", "launch_governance": {"action": "hold"}})
    completion_frontier.write_text(
        "completion_audit:\n  status: fail\nrepo_backlog_audit:\n  open_item_count: 2\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--readiness-path",
            str(readiness),
            "--journey-path",
            str(journey),
            "--support-path",
            str(support),
            "--progress-report-path",
            str(progress_report),
            "--progress-history-path",
            str(progress_history),
            "--weekly-packet-path",
            str(weekly),
            "--completion-frontier-path",
            str(completion_frontier),
            "--out",
            str(out),
            "--now",
            "2026-04-18T18:00:00Z",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    publication_front = next(front for front in payload["fronts"] if front["id"] == "publication_quality")
    assert publication_front["state"] == "blocked"
    assert any("backlog count" in reason for reason in publication_front["reasons"])
    assert any("claims completion" in reason for reason in publication_front["reasons"])
