from __future__ import annotations

import datetime as dt
import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml


MODULE_PATH = Path("/docker/fleet/admin/public_progress.py")
UTC = dt.timezone.utc


def load_module():
    spec = importlib.util.spec_from_file_location("test_public_progress_module", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PublicProgressReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.progress = load_module()

    def _seed_repo_root(self, root: Path) -> None:
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
                    "eta_formula": {
                        "remaining_weight_unit": 4.0,
                        "scope_multiplier_divisor": 8.0,
                        "activity_divisor": 18.0,
                        "min_velocity": 0.6,
                        "max_velocity": 1.8,
                        "low_multiplier": 0.8,
                        "high_multiplier": 1.35,
                        "min_low_weeks": 1,
                        "max_high_weeks": 16,
                    },
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
                            "milestones": [
                                {"phase": "landed", "title": "Landed", "body": "Done."},
                                {"phase": "now", "title": "Now", "body": "Doing."},
                                {"phase": "target", "title": "Target", "body": "Will do."},
                            ],
                        },
                        {
                            "id": "community-cloud",
                            "public_name": "Community Cloud & Publishing",
                            "short_public_name": "Cloud & Publishing",
                            "mapped_projects": ["beta"],
                            "summary": "Beta summary.",
                            "eta_weeks_low_override": 10,
                            "eta_weeks_high_override": 14,
                            "momentum_label_override": "Moderate",
                            "milestones": [
                                {"phase": "landed", "title": "Landed", "body": "Done."},
                                {"phase": "now", "title": "Now", "body": "Doing."},
                                {"phase": "target", "title": "Target", "body": "Will do."},
                            ],
                        },
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
                            "uncovered_scope": ["alpha-a", "alpha-b"],
                            "remaining_milestones": [{"id": "A1", "weight": 2, "status": "open"}],
                        },
                        "beta": {
                            "design_total_weight": 20,
                            "uncovered_scope": ["beta-a"],
                            "remaining_milestones": [
                                {"id": "B1", "weight": 10, "status": "open"},
                                {"id": "B2", "weight": 5, "status": "complete"},
                            ],
                        },
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
        (root / "config" / "projects" / "beta.yaml").write_text(
            yaml.safe_dump(
                {
                    "id": "beta",
                    "path": str(root / "repo-b"),
                    "review": {"repo": "beta-repo"},
                    "lifecycle": "dispatchable",
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )

        db_path = root / "state" / "fleet.db"
        conn = sqlite3.connect(db_path)
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
            rows = [
                ("2026-03-23T08:00:00Z", "2026-03-23T10:00:00Z"),
                ("2026-03-23T08:30:00Z", "2026-03-23T09:30:00Z"),
                ("2026-03-23T09:00:00Z", "2026-03-23T09:20:00Z"),
            ]
            for started_at, finished_at in rows:
                conn.execute(
                    "INSERT INTO runs(started_at, finished_at, decision_reason, job_kind) VALUES(?, ?, ?, 'coding')",
                    (started_at, finished_at, "route=multi_file_impl; task_lane=core_booster; selected lane: core_booster"),
                )
            conn.commit()
        finally:
            conn.close()

    def test_build_progress_report_payload_computes_weighted_progress_and_participation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._seed_repo_root(root)
            with mock.patch.object(self.progress, "load_progress_history_payload", return_value={"snapshots": []}):
                payload = self.progress.build_progress_report_payload(
                    repo_root=root,
                    now=dt.datetime(2026, 3, 23, 10, 0, tzinfo=UTC),
                    commit_counter=lambda repo: 12 if repo.name == "repo-a" else 4,
                )

        self.assertEqual(payload["overall_progress_percent"], 60)
        self.assertEqual(payload["phase_label"], "Scale & stabilize")
        self.assertEqual(payload["next_checkpoint_eta_weeks_low"], 1)
        self.assertEqual(payload["next_checkpoint_eta_weeks_high"], 3)
        self.assertEqual(payload["longest_pole"]["label"], "Cloud & Publishing")
        self.assertEqual(payload["parts"][0]["progress_percent"], 80)
        self.assertEqual(payload["parts"][1]["progress_percent"], 50)
        self.assertEqual(payload["parts"][0]["public_name"], "Core Rules Engine")
        self.assertEqual(payload["history_snapshot_count"], 0)
        self.assertFalse(payload["parts"][0]["source_status"]["package_compile"])
        self.assertFalse(payload["parts"][0]["source_status"]["dispatchable_truth_ready"])
        self.assertNotIn("average_active_boosters", payload["participation"])
        self.assertNotIn("peak_active_boosters", payload["participation"])

    def test_render_progress_report_html_contains_participation_link_and_poster(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._seed_repo_root(root)
            payload = self.progress.build_progress_report_payload(
                repo_root=root,
                now=dt.datetime(2026, 3, 23, 10, 0, tzinfo=UTC),
                commit_counter=lambda _repo: 8,
            )
            rendered = self.progress.render_progress_report_html(payload)

        self.assertIn("/api/public/progress-poster.svg", rendered)
        self.assertIn("How to participate", rendered)
        self.assertIn("Core Rules Engine", rendered)
        self.assertNotIn("Average active boosters", rendered)
        self.assertNotIn("Mission Control &amp; AI Runtime", rendered)

    def test_build_progress_report_payload_updates_history_limitations_once_snapshots_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._seed_repo_root(root)
            with mock.patch.object(
                self.progress,
                "load_progress_history_payload",
                return_value={
                    "snapshots": [
                        {
                            "as_of": "2026-03-16",
                            "parts": [],
                        }
                    ]
                },
            ):
                payload = self.progress.build_progress_report_payload(
                    repo_root=root,
                    now=dt.datetime(2026, 3, 23, 10, 0, tzinfo=UTC),
                    commit_counter=lambda _repo: 8,
                )

        limitations = payload["method"]["limitations"]
        self.assertEqual(payload["history_snapshot_count"], 1)
        self.assertEqual(payload["method"]["history_snapshot_count"], 1)
        self.assertNotIn("No long-term public history yet.", limitations)
        self.assertTrue(any("now being recorded" in item for item in limitations))

    def test_load_progress_report_payload_prefers_local_preview_artifact_for_fleet_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._seed_repo_root(root)
            canonical_path = root / "canon" / "PROGRESS_REPORT.generated.json"
            canonical_path.parent.mkdir(parents=True, exist_ok=True)
            canonical_path.write_text(
                json.dumps(
                    {
                        "contract_name": "fleet.public_progress_report",
                        "parts": [{"id": "canon"}],
                        "overall_progress_percent": 91,
                    }
                ),
                encoding="utf-8",
            )
            preview_path = root / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
            preview_path.parent.mkdir(parents=True, exist_ok=True)
            preview_path.write_text(
                json.dumps(
                    {
                        "contract_name": "fleet.public_progress_report",
                        "parts": [{"id": "preview"}],
                        "overall_progress_percent": 55,
                    }
                ),
                encoding="utf-8",
            )

            original_root = self.progress.FLEET_ROOT
            original_canon_path = self.progress.CANON_PROGRESS_REPORT_PATH
            try:
                self.progress.FLEET_ROOT = root
                self.progress.CANON_PROGRESS_REPORT_PATH = canonical_path
                payload = self.progress.load_progress_report_payload(repo_root=root)
            finally:
                self.progress.FLEET_ROOT = original_root
                self.progress.CANON_PROGRESS_REPORT_PATH = original_canon_path

        self.assertEqual(payload["parts"][0]["id"], "preview")

    def test_build_progress_report_payload_uses_history_velocity_when_snapshots_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._seed_repo_root(root)
            published = root / ".codex-studio" / "published"
            published.mkdir(parents=True, exist_ok=True)
            (published / "PROGRESS_HISTORY.generated.json").write_text(
                json.dumps(
                    {
                        "contract_name": "fleet.public_progress_history",
                        "contract_version": "2026-03-23",
                        "snapshots": [
                            {
                                "as_of": "2026-03-09",
                                "parts": [
                                    {
                                        "id": "core-engine",
                                        "remaining_open_weight": 6,
                                    }
                                ],
                            },
                            {
                                "as_of": "2026-03-16",
                                "parts": [
                                    {
                                        "id": "core-engine",
                                        "remaining_open_weight": 4,
                                    }
                                ],
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            payload = self.progress.build_progress_report_payload(
                repo_root=root,
                now=dt.datetime(2026, 3, 23, 10, 0, tzinfo=UTC),
                commit_counter=lambda repo: 12 if repo.name == "repo-a" else 4,
            )

        self.assertEqual(payload["parts"][0]["eta_source"], "history_velocity")
        self.assertEqual(payload["method"]["eta_formula_version"], "history_velocity_v1")
        self.assertGreater(payload["parts"][0]["history_velocity_weight_points_per_week"], 0.0)
        self.assertEqual(payload["overall_progress_percent"], 60)


if __name__ == "__main__":
    unittest.main()
