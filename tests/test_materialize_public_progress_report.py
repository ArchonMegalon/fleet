from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import yaml


SCRIPT = Path("/docker/fleet/scripts/materialize_public_progress_report.py")


def _seed_repo_root(root: Path) -> None:
    (root / "config" / "projects").mkdir(parents=True, exist_ok=True)
    (root / "state").mkdir(parents=True, exist_ok=True)
    (root / "repo-a").mkdir(parents=True, exist_ok=True)
    (root / "repo-b").mkdir(parents=True, exist_ok=True)
    (root / "config" / "public_progress_parts.yaml").write_text(
        yaml.safe_dump(
            {
                "as_of": "2026-03-23",
                "brand": "Chummer6",
                "hero": {
                    "headline": "Progress report",
                    "support": "A public progress surface.",
                    "ctas": [{"label": "See the program pulse", "href": "#program", "kind": "primary"}],
                },
                "phase_labels": [{"min_progress_percent": 0, "label": "Scale & stabilize"}],
                "momentum_labels": [{"min_score": 0, "label": "Moderate"}],
                "eta_formula": {},
                "method": {
                    "progress_formula_version": "public_progress_v1",
                    "eta_formula_version": "momentum_proxy_v1",
                    "copy": "Method copy.",
                    "limitations": ["No long-term public history yet."],
                },
                "recent_movement": ["Control plane tightened."],
                "recent_movement_copy": {"Control plane tightened.": "Recent movement body."},
                "closing": {"headline": "Closing", "body": "Closing body."},
                "participation": {
                    "headline": "How to participate",
                    "body": "Participation copy.",
                    "cta_label": "Open the participation page",
                },
                "parts": [
                    {
                        "id": "mission-control",
                        "public_name": "Mission Control & AI Runtime",
                        "short_public_name": "Mission Control",
                        "mapped_projects": ["alpha"],
                        "summary": "Alpha summary.",
                        "eta_weeks_low_override": 2,
                        "eta_weeks_high_override": 4,
                        "momentum_label_override": "Very high",
                        "milestones": [{"phase": "now", "title": "Now", "body": "Doing."}],
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (root / "config" / "program_milestones.yaml").write_text(
        yaml.safe_dump(
            {
                "projects": {
                    "alpha": {
                        "design_total_weight": 10,
                        "uncovered_scope": ["alpha-a"],
                        "remaining_milestones": [{"id": "A1", "weight": 2, "status": "open"}],
                    }
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (root / "config" / "projects" / "alpha.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "alpha",
                "path": str(root / "repo-a"),
                "review": {"repo": "alpha-repo"},
                "lifecycle": "live",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    conn = sqlite3.connect(root / "state" / "fleet.db")
    try:
        conn.execute(
            """
            CREATE TABLE runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT,
                finished_at TEXT,
                decision_reason TEXT,
                job_kind TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO runs(started_at, finished_at, decision_reason, job_kind) VALUES(?, ?, ?, 'coding')",
            ("2026-03-23T08:00:00Z", "2026-03-23T09:00:00Z", "task_lane=core_booster; selected lane: core_booster"),
        )
        conn.commit()
    finally:
        conn.close()


def test_materialize_public_progress_report(tmp_path: Path) -> None:
    _seed_repo_root(tmp_path)
    out_path = tmp_path / "PROGRESS_REPORT.generated.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--as-of",
            "2026-03-23",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["contract_name"] == "fleet.public_progress_report"
    assert payload["as_of"] == "2026-03-23"
    assert payload["overall_progress_percent"] == 80
    assert payload["parts"][0]["public_name"] == "Mission Control & AI Runtime"
    assert payload["participation"]["average_active_boosters"] == 1.0
