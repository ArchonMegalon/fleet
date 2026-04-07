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
                        "id": "core-engine",
                        "public_name": "Core Rules Engine",
                        "short_public_name": "Core Engine",
                        "mapped_projects": ["alpha"],
                        "summary": "Alpha summary.",
                        "eta_weeks_low_override": 3,
                        "eta_weeks_high_override": 5,
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
    history_path = tmp_path / "PROGRESS_HISTORY.generated.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--history-out",
            str(history_path),
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
    assert payload["history_snapshot_count"] == 1
    assert payload["active_wave"] == "Next 12 Biggest Wins"
    assert payload["active_wave_status"] == "active"
    assert payload["current_phase"] == "Scale & stabilize"
    assert payload["eta_summary"] == "3-5 weeks"
    assert payload["method"]["history_snapshot_count"] == 1
    assert "No long-term public history yet." not in payload["method"]["limitations"]
    assert any("now being recorded" in item for item in payload["method"]["limitations"])
    assert payload["parts"][0]["public_name"] == "Core Rules Engine"
    assert payload["parts"][0]["source_status"]["package_compile"] is False
    assert "average_active_boosters" not in payload["participation"]
    history_payload = json.loads(history_path.read_text(encoding="utf-8"))
    assert history_payload["snapshot_count"] == 1
    assert history_payload["snapshots"][0]["as_of"] == "2026-03-23"


def test_materialize_public_progress_report_writes_canon_bundle_and_hub_mirror(tmp_path: Path) -> None:
    _seed_repo_root(tmp_path)
    out_path = tmp_path / "canon" / "PROGRESS_REPORT.generated.json"
    html_path = tmp_path / "canon" / "PROGRESS_REPORT.generated.html"
    poster_path = tmp_path / "canon" / "PROGRESS_REPORT_POSTER.svg"
    history_path = tmp_path / "canon" / "PROGRESS_HISTORY.generated.json"
    preview_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    mirror_root = tmp_path / "hub"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--html-out",
            str(html_path),
            "--poster-out",
            str(poster_path),
            "--preview-out",
            str(preview_path),
            "--history-out",
            str(history_path),
            "--mirror-root",
            str(mirror_root),
            "--as-of",
            "2026-03-23",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert out_path.exists()
    assert html_path.exists()
    assert poster_path.exists()
    assert history_path.exists()
    assert preview_path.exists()
    manifest_path = tmp_path / ".codex-studio" / "published" / "compile.manifest.json"
    assert manifest_path.exists()
    mirror_dir = mirror_root / ".codex-design" / "product"
    assert (mirror_dir / "PROGRESS_REPORT.generated.json").exists()
    assert (mirror_dir / "PROGRESS_REPORT.generated.html").exists()
    assert (mirror_dir / "PROGRESS_REPORT_POSTER.svg").exists()
    assert (mirror_dir / "PROGRESS_HISTORY.generated.json").exists()
    html = html_path.read_text(encoding="utf-8")
    assert "/api/public/progress-poster.svg" in html
    assert "How to participate" in html
    assert "Average active boosters" not in html
    assert "<svg" in poster_path.read_text(encoding="utf-8")
    mirror_payload = json.loads((mirror_dir / "PROGRESS_REPORT.generated.json").read_text(encoding="utf-8"))
    assert mirror_payload["as_of"] == "2026-03-23"
    assert mirror_payload["history_snapshot_count"] == 1
    assert mirror_payload["method"]["history_snapshot_count"] == 1
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert "PROGRESS_REPORT.generated.json" in manifest_payload["artifacts"]
