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
        (root / "products" / "chummer").mkdir(parents=True, exist_ok=True)
        (root / "state").mkdir(parents=True, exist_ok=True)
        (root / "repo-a").mkdir(parents=True, exist_ok=True)
        (root / "repo-b").mkdir(parents=True, exist_ok=True)
        (root / "products" / "chummer" / "ROADMAP.md").write_text(
            "The current recommended wave is **Next 12 Biggest Wins**.\n",
            encoding="utf-8",
        )
        (root / "products" / "chummer" / "NEXT_12_BIGGEST_WINS_REGISTRY.yaml").write_text(
            "status: active\n",
            encoding="utf-8",
        )
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
        self.assertEqual(payload["current_phase"], "Scale & stabilize")
        self.assertEqual(payload["active_wave"], "Next 12 Biggest Wins")
        self.assertEqual(payload["active_wave_status"], "active")
        self.assertEqual(payload["next_checkpoint_eta_weeks_low"], 1)
        self.assertEqual(payload["next_checkpoint_eta_weeks_high"], 3)
        self.assertEqual(payload["eta_summary"], "1-3 weeks")
        self.assertEqual(payload["longest_pole"]["label"], "Cloud & Publishing")
        self.assertEqual(payload["parts"][0]["progress_percent"], 80)
        self.assertEqual(payload["parts"][1]["progress_percent"], 50)
        self.assertEqual(payload["parts"][0]["public_name"], "Core Rules Engine")
        self.assertEqual(payload["generated_at"], "2026-03-23T10:00:00Z")
        self.assertEqual(payload["history_snapshot_count"], 0)
        self.assertFalse(payload["parts"][0]["source_status"]["package_compile"])
        self.assertFalse(payload["parts"][0]["source_status"]["dispatchable_truth_ready"])
        self.assertNotIn("average_active_boosters", payload["participation"])
        self.assertNotIn("peak_active_boosters", payload["participation"])

    def test_build_progress_report_payload_does_not_promote_tactical_supervisor_eta_to_full_product_weeks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._seed_repo_root(root)
            (root / "config" / "program_milestones.yaml").write_text(
                yaml.safe_dump(
                    {
                        "projects": {
                            "alpha": {
                                "design_total_weight": 10,
                                "uncovered_scope": [],
                                "remaining_milestones": [],
                            },
                            "beta": {
                                "design_total_weight": 20,
                                "uncovered_scope": [],
                                "remaining_milestones": [],
                            },
                        }
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            supervisor_state = {
                "mode": "sharded",
                "frontier_ids": [101, 102, 103],
                "open_milestone_ids": [101, 102, 103],
                "active_runs_count": 6,
                "eta": {
                    "status": "estimated",
                    "eta_human": "8-16h",
                    "eta_confidence": "medium",
                    "basis": "empirical_open_milestone_burn",
                    "scope_kind": "open_milestone_frontier",
                    "scope_label": "Current open milestone frontier",
                    "scope_warning": "This is a tactical frontier ETA only.",
                    "remaining_open_milestones": 3,
                    "remaining_in_progress_milestones": 3,
                    "remaining_not_started_milestones": 0,
                },
            }
            with mock.patch.object(self.progress, "load_progress_history_payload", return_value={"snapshots": []}):
                with mock.patch.object(self.progress, "_load_chummer_design_supervisor_state", return_value=supervisor_state):
                    payload = self.progress.build_progress_report_payload(
                        repo_root=root,
                        now=dt.datetime(2026, 3, 23, 10, 0, tzinfo=UTC),
                        commit_counter=lambda _repo: 0,
                    )

        self.assertEqual(payload["eta_scope"], "full_product_queue_unestimated")
        self.assertEqual(payload["eta_summary"], "tracked in full-product frontier")
        self.assertIsNone(payload["full_product_queue"]["eta"]["eta_weeks_low"])
        self.assertIsNone(payload["full_product_queue"]["eta"]["eta_weeks_high"])
        self.assertEqual(payload["full_product_queue"]["eta"]["scope_kind"], "open_milestone_frontier")
        self.assertIn("should not be read as a full-product parity ETA", payload["release_readiness"]["summary"])
        self.assertTrue(
            any("tactical" in str(item).lower() for item in (payload.get("method") or {}).get("limitations") or [])
        )

    def test_build_progress_report_payload_rebuilds_supervisor_state_from_shards_when_aggregate_state_is_blank(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._seed_repo_root(root)
            (root / "config" / "program_milestones.yaml").write_text(
                yaml.safe_dump(
                    {
                        "projects": {
                            "alpha": {
                                "design_total_weight": 10,
                                "uncovered_scope": [],
                                "remaining_milestones": [],
                            },
                            "beta": {
                                "design_total_weight": 20,
                                "uncovered_scope": [],
                                "remaining_milestones": [],
                            },
                        }
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            state_root = root / "state" / "chummer_design_supervisor"
            (state_root / "shard-1").mkdir(parents=True, exist_ok=True)
            (state_root / "shard-2").mkdir(parents=True, exist_ok=True)
            (state_root / "state.json").write_text(
                json.dumps({"mode": "sharded", "active_runs_count": 0, "eta": None}),
                encoding="utf-8",
            )
            (state_root / "shard-1" / "state.json").write_text(
                json.dumps(
                    {
                        "updated_at": "2026-04-08T18:04:07Z",
                        "mode": "flagship_product",
                        "frontier_ids": [101],
                        "active_run": {"run_id": "run-1", "frontier_ids": [101]},
                        "eta": {
                            "status": "flagship_delivery",
                            "scope_kind": "flagship_product_readiness",
                            "remaining_open_milestones": 0,
                            "remaining_in_progress_milestones": 0,
                            "remaining_not_started_milestones": 1,
                        },
                    }
                ),
                encoding="utf-8",
            )
            (state_root / "shard-2" / "state.json").write_text(
                json.dumps(
                    {
                        "updated_at": "2026-04-08T18:04:18Z",
                        "mode": "flagship_product",
                        "frontier_ids": [102],
                        "active_run": {"run_id": "run-2", "frontier_ids": [102]},
                        "eta": {
                            "status": "flagship_delivery",
                            "scope_kind": "flagship_product_readiness",
                            "remaining_open_milestones": 0,
                            "remaining_in_progress_milestones": 0,
                            "remaining_not_started_milestones": 1,
                        },
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.object(self.progress, "DEFAULT_DESIGN_SUPERVISOR_STATE_PATH", state_root / "state.json"):
                with mock.patch.object(self.progress, "load_progress_history_payload", return_value={"snapshots": []}):
                    payload = self.progress.build_progress_report_payload(
                        repo_root=root,
                        now=dt.datetime(2026, 4, 8, 18, 5, tzinfo=UTC),
                        commit_counter=lambda _repo: 0,
                    )

        self.assertEqual(payload["eta_scope"], "full_product_queue_unestimated")
        self.assertEqual(payload["eta_summary"], "tracked in full-product frontier")
        self.assertEqual(payload["full_product_queue"]["active_runs_count"], 2)
        self.assertEqual(payload["full_product_queue"]["open_frontier_milestones"], 2)
        self.assertEqual(payload["full_product_queue"]["eta"]["scope_kind"], "flagship_product_readiness")
        self.assertEqual(payload["full_product_queue"]["eta"]["remaining_open_milestones"], 2)
        self.assertIsNone(payload["full_product_queue"]["eta"]["eta_weeks_low"])
        self.assertIsNone(payload["full_product_queue"]["eta"]["eta_weeks_high"])

    def test_build_progress_report_payload_skips_blank_shard_state_files_when_rebuilding_supervisor_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._seed_repo_root(root)
            (root / "config" / "program_milestones.yaml").write_text(
                yaml.safe_dump(
                    {
                        "projects": {
                            "alpha": {
                                "design_total_weight": 10,
                                "uncovered_scope": [],
                                "remaining_milestones": [],
                            },
                            "beta": {
                                "design_total_weight": 20,
                                "uncovered_scope": [],
                                "remaining_milestones": [],
                            },
                        }
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            state_root = root / "state" / "chummer_design_supervisor"
            (state_root / "shard-1").mkdir(parents=True, exist_ok=True)
            (state_root / "shard-2").mkdir(parents=True, exist_ok=True)
            (state_root / "state.json").write_text("", encoding="utf-8")
            (state_root / "shard-1" / "state.json").write_text(
                json.dumps(
                    {
                        "updated_at": "2026-04-08T18:04:18Z",
                        "mode": "flagship_product",
                        "frontier_ids": [102],
                        "active_run": {"run_id": "run-2", "frontier_ids": [102]},
                        "eta": {
                            "status": "flagship_delivery",
                            "scope_kind": "flagship_product_readiness",
                            "remaining_open_milestones": 0,
                            "remaining_in_progress_milestones": 0,
                            "remaining_not_started_milestones": 1,
                        },
                    }
                ),
                encoding="utf-8",
            )
            (state_root / "shard-2" / "state.json").write_text("", encoding="utf-8")
            with mock.patch.object(self.progress, "DEFAULT_DESIGN_SUPERVISOR_STATE_PATH", state_root / "state.json"):
                with mock.patch.object(self.progress, "load_progress_history_payload", return_value={"snapshots": []}):
                    payload = self.progress.build_progress_report_payload(
                        repo_root=root,
                        now=dt.datetime(2026, 4, 8, 18, 5, tzinfo=UTC),
                        commit_counter=lambda _repo: 0,
                    )

        self.assertEqual(payload["full_product_queue"]["active_runs_count"], 1)
        self.assertEqual(payload["full_product_queue"]["open_frontier_milestones"], 1)
        self.assertEqual(payload["full_product_queue"]["eta"]["scope_kind"], "flagship_product_readiness")
        self.assertEqual(payload["full_product_queue"]["eta"]["remaining_open_milestones"], 1)

    def test_build_progress_report_payload_clamps_false_completion_when_repo_backlog_remains(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._seed_repo_root(root)
            (root / "fleet-repo").mkdir(parents=True, exist_ok=True)
            (root / "fleet-repo" / "WORKLIST.md").write_text(
                "\n".join(
                    [
                        "# Worklist Queue",
                        "",
                        "| ID | Status | Priority | Task | Owner | Notes |",
                        "|---|---|---|---|---|---|",
                        "| WL-300 | queued | P0 | Restore live queue truth | agent | note |",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "config" / "projects" / "fleet.yaml").write_text(
                yaml.safe_dump(
                    {
                        "id": "fleet",
                        "path": str(root / "fleet-repo"),
                        "review": {"repo": "fleet"},
                        "lifecycle": "live",
                        "queue": [],
                        "queue_sources": [{"kind": "worklist", "path": "WORKLIST.md", "mode": "replace"}],
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
                                "uncovered_scope": [],
                                "remaining_milestones": [],
                            },
                            "beta": {
                                "design_total_weight": 20,
                                "uncovered_scope": [],
                                "remaining_milestones": [],
                            },
                        }
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            with mock.patch.object(self.progress, "_load_chummer_design_supervisor_state", return_value={}):
                with mock.patch.object(self.progress, "load_progress_history_payload", return_value={"snapshots": []}):
                    payload = self.progress.build_progress_report_payload(
                        repo_root=root,
                        now=dt.datetime(2026, 3, 23, 10, 0, tzinfo=UTC),
                        commit_counter=lambda _repo: 0,
                    )

        self.assertEqual(payload["overall_progress_percent"], 99)
        self.assertEqual(payload["progress_percent"], 99)
        self.assertEqual(payload["percent_complete"], 99)
        self.assertEqual(payload["active_slice"], "Restore live queue truth")
        self.assertEqual(payload["eta_summary"], "tracked in repo backlog")
        self.assertEqual(payload["release_readiness"]["status"], "warning")
        self.assertTrue(any(risk.get("key") == "repo_local_backlog" for risk in payload["top_risks"]))
        self.assertEqual(payload["repo_backlog"]["open_item_count"], 1)
        self.assertEqual(payload["repo_backlog"]["open_project_count"], 1)
        self.assertEqual(payload["repo_backlog"]["lead_task"], "Restore live queue truth")

    def test_repo_local_backlog_snapshot_ignores_terminal_config_queue_items(self) -> None:
        snapshot = self.progress._repo_local_backlog_snapshot(
            {
                "fleet": {
                    "id": "fleet",
                    "path": "/docker/fleet",
                    "review": {"repo": "fleet"},
                    "queue": [
                        {
                            "package_id": "fleet-postclient-operating-profiles",
                            "title": "Add steady-state fleet operating profiles",
                            "status": "done",
                        },
                        {
                            "package_id": "fleet-postclient-proof-orchestration",
                            "title": "Promote executable gates into orchestrated jobs",
                            "status": "queued",
                        },
                    ],
                }
            }
        )

        self.assertEqual(snapshot["open_item_count"], 1)
        self.assertEqual(snapshot["lead_task"], "Promote executable gates into orchestrated jobs")

    def test_build_progress_report_payload_surfaces_flagship_truth_from_upstream_proofs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._seed_repo_root(root)
            (root / "config" / "program_milestones.yaml").write_text(
                yaml.safe_dump(
                    {
                        "projects": {
                            "alpha": {
                                "design_total_weight": 10,
                                "uncovered_scope": [],
                                "remaining_milestones": [],
                            },
                            "beta": {
                                "design_total_weight": 20,
                                "uncovered_scope": [],
                                "remaining_milestones": [],
                            },
                        }
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            proof_dir = root / "proofs"
            proof_dir.mkdir(parents=True, exist_ok=True)

            import_parity_path = proof_dir / "IMPORT_PARITY_CERTIFICATION.generated.json"
            import_parity_path.write_text(json.dumps({"status": "passed"}), encoding="utf-8")
            chummer5a_path = proof_dir / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
            chummer5a_path.write_text(json.dumps({"status": "pass"}), encoding="utf-8")
            sr4_path = proof_dir / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
            sr4_path.write_text(json.dumps({"status": "pass"}), encoding="utf-8")
            sr6_path = proof_dir / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
            sr6_path.write_text(json.dumps({"status": "pass"}), encoding="utf-8")
            visual_path = proof_dir / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
            visual_path.write_text(json.dumps({"status": "pass"}), encoding="utf-8")
            executable_path = proof_dir / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
            executable_path.write_text(
                json.dumps(
                    {
                        "status": "fail",
                        "summary": "Desktop executable exit gate is not fully proven.",
                        "reasons": [
                            "Release channel does not publish desktop install media for required platform 'windows'.",
                            "Windows gate reason: Windows startup smoke requires a Windows-capable host; current host cannot run promoted Windows installer smoke.",
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with mock.patch.object(self.progress, "DEFAULT_IMPORT_PARITY_CERTIFICATION_PATH", import_parity_path):
                with mock.patch.object(self.progress, "DEFAULT_CHUMMER5A_DESKTOP_WORKFLOW_PARITY_PATH", chummer5a_path):
                    with mock.patch.object(self.progress, "DEFAULT_SR4_DESKTOP_WORKFLOW_PARITY_PATH", sr4_path):
                        with mock.patch.object(self.progress, "DEFAULT_SR6_DESKTOP_WORKFLOW_PARITY_PATH", sr6_path):
                            with mock.patch.object(self.progress, "DEFAULT_DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE_PATH", visual_path):
                                with mock.patch.object(self.progress, "DEFAULT_DESKTOP_EXECUTABLE_EXIT_GATE_PATH", executable_path):
                                    with mock.patch.object(self.progress, "load_progress_history_payload", return_value={"snapshots": []}):
                                        payload = self.progress.build_progress_report_payload(
                                            repo_root=root,
                                            now=dt.datetime(2026, 3, 23, 10, 0, tzinfo=UTC),
                                            commit_counter=lambda _repo: 0,
                                        )

        self.assertEqual(payload["flagship_readiness"]["status"], "warning")
        self.assertTrue(payload["flagship_readiness"]["feature_parity_proven"])
        self.assertTrue(payload["flagship_readiness"]["layout_familiarity_proven"])
        self.assertEqual(payload["release_readiness"]["status"], "warning")
        self.assertIn("Windows installer/startup evidence", payload["release_readiness"]["summary"])
        self.assertEqual(payload["parity"]["status"], "warning")
        self.assertIn("desktop visual-familiarity gate is green", payload["parity"]["summary"])
        self.assertTrue(any(risk.get("key") == "flagship_release_truth" for risk in payload["top_risks"]))

    def test_design_supervisor_state_root_aliases_to_chummer_design_supervisor(self) -> None:
        self.assertEqual(
            self.progress._design_supervisor_state_root(Path("/docker/fleet/state/design-supervisor/state.json")),
            Path("/docker/fleet/state/chummer_design_supervisor"),
        )
        self.assertEqual(
            self.progress._design_supervisor_state_root(
                Path("/docker/fleet/state/design-supervisor/shard-7/state.json"),
            ),
            Path("/docker/fleet/state/chummer_design_supervisor/shard-7"),
        )
        self.assertEqual(
            self.progress._design_supervisor_state_root(
                Path("/docker/fleet/state/design-supervisor/orphaned-shard-7/state.json"),
            ),
            Path("/docker/fleet/state/chummer_design_supervisor/orphaned-shard-7"),
        )

    def test_repo_local_backlog_snapshot_dedupes_same_task_across_multiple_queue_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._seed_repo_root(root)
            repo = root / "ui-repo"
            repo.mkdir(parents=True, exist_ok=True)
            duplicate_task = "Improve onboarding trust copy"
            (repo / "WORKLIST.md").write_text(
                "\n".join(
                    [
                        "# Worklist Queue",
                        "",
                        "| ID | Status | Priority | Task | Owner | Notes |",
                        "|---|---|---|---|---|---|",
                        f"| WL-240 | queued | P0 | {duplicate_task} | agent | note |",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "external-ui-worklist.md").write_text(
                "\n".join(
                    [
                        "# Worklist Queue",
                        "",
                        "| ID | Status | Priority | Task | Owner | Notes |",
                        "|---|---|---|---|---|---|",
                        f"| WL-241 | queued | P1 | {duplicate_task} | agent | duplicate |",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "config" / "projects" / "ui.yaml").write_text(
                yaml.safe_dump(
                    {
                        "id": "ui",
                        "path": str(repo),
                        "review": {"repo": "ui"},
                        "lifecycle": "live",
                        "queue": [],
                        "queue_sources": [
                            {"kind": "worklist", "path": "WORKLIST.md", "mode": "replace"},
                            {"kind": "worklist", "path": str(root / "external-ui-worklist.md"), "mode": "append"},
                        ],
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )

            snapshot = self.progress._repo_local_backlog_snapshot(self.progress._project_configs(root / "config" / "projects"))

        self.assertEqual(snapshot["open_item_count"], 1)
        self.assertEqual(snapshot["open_project_count"], 1)
        self.assertEqual(snapshot["lead_task"], duplicate_task)
        self.assertEqual(snapshot["open_items"], [{"project_id": "ui", "repo_slug": "ui", "task": duplicate_task}])

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
        self.assertEqual(payload["method"]["eta_formula_version"], "history_velocity_with_overrides_v1")
        self.assertGreater(payload["parts"][0]["history_velocity_weight_points_per_week"], 0.0)
        self.assertEqual(payload["overall_progress_percent"], 60)

    def test_build_progress_report_payload_describes_config_override_eta_when_all_parts_use_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._seed_repo_root(root)
            config_path = root / "config" / "public_progress_parts.yaml"
            config_payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            for part in config_payload.get("parts") or []:
                if part.get("id") == "core-engine":
                    part["eta_weeks_low_override"] = 2
                    part["eta_weeks_high_override"] = 4
            config_path.write_text(yaml.safe_dump(config_payload, sort_keys=False), encoding="utf-8")

            payload = self.progress.build_progress_report_payload(
                repo_root=root,
                now=dt.datetime(2026, 3, 23, 10, 0, tzinfo=UTC),
                commit_counter=lambda _repo: 8,
            )

        self.assertEqual({part["eta_source"] for part in payload["parts"]}, {"config_override"})
        self.assertEqual(payload["method"]["eta_formula_version"], "config_override_v1")
        self.assertTrue(any("configured planning bands" in item for item in payload["method"]["limitations"]))

    def test_active_wave_status_prefers_active_registry_constant_for_next12_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            active_registry_path = root / "ACTIVE.yaml"
            next12_registry_path = root / "NEXT12.yaml"
            active_registry_path.write_text("status: active\n", encoding="utf-8")
            next12_registry_path.write_text("status: planned\n", encoding="utf-8")

            original_active_path = self.progress.ACTIVE_WAVE_REGISTRY_PATH
            original_next12_path = self.progress.NEXT12_REGISTRY_PATH
            try:
                self.progress.ACTIVE_WAVE_REGISTRY_PATH = active_registry_path
                self.progress.NEXT12_REGISTRY_PATH = next12_registry_path
                status = self.progress._active_wave_status("Next 12 Biggest Wins")
            finally:
                self.progress.ACTIVE_WAVE_REGISTRY_PATH = original_active_path
                self.progress.NEXT12_REGISTRY_PATH = original_next12_path

        self.assertEqual(status, "active")

    def test_published_progress_report_matches_generated_contract(self) -> None:
        repo_root = Path("/docker/fleet")
        published = repo_root / ".codex-studio" / "published"
        actual_report = json.loads((published / "PROGRESS_REPORT.generated.json").read_text(encoding="utf-8"))
        actual_history = json.loads((published / "PROGRESS_HISTORY.generated.json").read_text(encoding="utf-8"))
        commit_counts = {
            Path(str(row["path"])).resolve(): int(row["recent_commit_count_7d"])
            for part in actual_report["parts"]
            for row in part.get("source_projects") or []
            if str(row.get("path") or "").strip()
        }

        actual_full_queue = actual_report["full_product_queue"]
        actual_full_queue_eta = actual_full_queue.get("eta") or {}
        supervisor_state_snapshot = {
            "mode": actual_full_queue.get("mode"),
            "frontier_ids": list(actual_full_queue.get("active_frontier_ids") or []),
            "open_milestone_ids": list(actual_full_queue.get("open_milestone_ids") or []),
            "active_runs_count": int(actual_full_queue.get("active_runs_count") or 0),
            "active_runs": [],
            "eta": {
                "eta_human": actual_full_queue_eta.get("eta_human"),
                "scope_kind": actual_full_queue_eta.get("scope_kind"),
                "scope_label": actual_full_queue_eta.get("scope_label"),
                "scope_warning": actual_full_queue_eta.get("scope_warning"),
                "remaining_open_milestones": int(
                    actual_full_queue_eta.get("remaining_open_milestones") or 0
                ),
                "remaining_in_progress_milestones": int(
                    actual_full_queue_eta.get("remaining_in_progress_milestones") or 0
                ),
                "remaining_not_started_milestones": int(
                    actual_full_queue_eta.get("remaining_not_started_milestones") or 0
                ),
                "status": actual_full_queue_eta.get("eta_status") or "unknown",
            },
        }

        with mock.patch.object(
            self.progress,
            "_load_chummer_design_supervisor_state",
            return_value=supervisor_state_snapshot,
        ):
            expected_report = self.progress.build_progress_report_payload(
                repo_root=repo_root,
                as_of=dt.date.fromisoformat(str(actual_report["as_of"])),
                commit_counter=lambda repo: commit_counts.get(Path(repo).resolve(), 0),
            )
        expected_history = self.progress.merge_progress_history(actual_history, expected_report)
        expected_report["history_snapshot_count"] = int(expected_history.get("snapshot_count") or 0)
        expected_report.setdefault("method", {})["history_snapshot_count"] = int(expected_history.get("snapshot_count") or 0)

        def normalize_report(payload: dict) -> dict:
            normalized = json.loads(json.dumps(payload))
            normalized.pop("generated_at", None)
            for part in normalized.get("parts") or []:
                for row in part.get("source_projects") or []:
                    compile_payload = row.get("compile")
                    if isinstance(compile_payload, dict):
                        compile_payload.pop("published_at", None)
            return normalized

        self.assertEqual(normalize_report(actual_report), normalize_report(expected_report))
        self.assertEqual(
            {key: value for key, value in actual_history.items() if key != "generated_at"},
            {key: value for key, value in expected_history.items() if key != "generated_at"},
        )


if __name__ == "__main__":
    unittest.main()
