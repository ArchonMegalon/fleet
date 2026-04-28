from __future__ import annotations

import asyncio
import datetime as dt
import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path("/docker/fleet/auditor/app.py")


def install_fastapi_stubs() -> None:
    if "fastapi" in sys.modules and "fastapi.responses" in sys.modules:
        return

    fastapi = types.ModuleType("fastapi")
    responses = types.ModuleType("fastapi.responses")

    class DummyFastAPI:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __getattr__(self, _name):
            def decorator(*args, **kwargs):
                def wrapper(func):
                    return func

                return wrapper

            return decorator

    fastapi.FastAPI = DummyFastAPI
    fastapi.Form = lambda *args, **kwargs: None
    fastapi.HTTPException = Exception
    fastapi.Request = object
    responses.HTMLResponse = object
    responses.JSONResponse = object
    responses.PlainTextResponse = object
    responses.RedirectResponse = object
    responses.Response = object
    sys.modules["fastapi"] = fastapi
    sys.modules["fastapi.responses"] = responses


def load_auditor_module():
    install_fastapi_stubs()
    spec = importlib.util.spec_from_file_location("test_auditor_app_module", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AuditorSynthesisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.auditor = load_auditor_module()

    def test_auditor_loop_retries_after_interval_config_failure(self) -> None:
        original_state = self.auditor.state
        self.auditor.state = self.auditor.RuntimeState()
        run_calls = {"count": 0}
        normalize_calls = {"count": 0}
        wait_calls = {"count": 0}

        async def fake_run_audit_pass() -> None:
            run_calls["count"] += 1
            if run_calls["count"] >= 2:
                self.auditor.state.stop.set()

        def fake_normalize_config():
            normalize_calls["count"] += 1
            if normalize_calls["count"] == 1:
                raise ValueError("broken config")
            return {"policies": {"auditor_interval_seconds": 30}}

        async def fake_wait_for(awaitable, timeout):
            wait_calls["count"] += 1
            if wait_calls["count"] == 1:
                awaitable.close()
                raise asyncio.TimeoutError
            return await awaitable

        try:
            with mock.patch.object(self.auditor, "run_audit_pass", new=fake_run_audit_pass), mock.patch.object(
                self.auditor, "normalize_config", new=fake_normalize_config
            ), mock.patch.object(self.auditor.asyncio, "wait_for", new=fake_wait_for), mock.patch.object(
                self.auditor.traceback, "print_exc"
            ) as print_exc:
                asyncio.run(self.auditor.auditor_loop())
        finally:
            self.auditor.state = original_state

        self.assertEqual(run_calls["count"], 2)
        self.assertEqual(normalize_calls["count"], 2)
        self.assertEqual(wait_calls["count"], 2)
        print_exc.assert_called_once()

    def test_synthesize_uncovered_scope_tasks_clusters_related_items(self) -> None:
        uncovered_scope = [
            "Contact and relationship graph UI",
            "Heat, faction, and favor continuity views",
            "Calendar, ledger, and downtime planner surfaces",
            "Runtime inspector, RuleProfile, and RulePack diagnostics",
            "Richer Hub client UX",
            "Portrait Forge selection and reroll UX depth",
            "NPC Persona Studio screens",
            "Coach, Shadowfeed, player dispatch, and review workflows",
            "Final accessibility, deployment, and browser-constraint signoff",
        ]

        tasks = self.auditor.synthesize_uncovered_scope_tasks(
            scope_id="ui",
            uncovered_scope=uncovered_scope,
            queue_exhausted=False,
        )

        self.assertLess(len(tasks), len(uncovered_scope))
        self.assertGreaterEqual(len(tasks), 2)
        self.assertEqual(sum(int(task["source_item_count"]) for task in tasks), len(uncovered_scope))
        self.assertTrue(any(task["synthesis_cluster"] == "product_completion" for task in tasks))
        self.assertTrue(any(task["synthesis_cluster"] == "release_hardening" for task in tasks))

    def test_design_mirror_status_reports_missing_and_drifted_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_ok = root / "source-ok.md"
            source_drift = root / "source-drift.md"
            target_ok = root / "target-ok.md"
            target_drift = root / "target-drift.md"
            missing_target = root / "missing.md"
            source_ok.write_text("same", encoding="utf-8")
            source_drift.write_text("expected", encoding="utf-8")
            target_ok.write_text("same", encoding="utf-8")
            target_drift.write_text("actual", encoding="utf-8")

            self.auditor.design_mirror_specs = lambda _config: [
                {
                    "project_id": "ui",
                    "files": [
                        {"source": source_ok, "target": target_ok},
                        {"source": source_drift, "target": target_drift},
                        {"source": source_ok, "target": missing_target},
                    ],
                }
            ]
            self.auditor.project_runtime_rows = lambda: {"ui": {"status": "dispatch_pending", "active_run_id": 0}}

            payload = self.auditor.design_mirror_status({})

            self.assertEqual(payload["stale_project_ids"], ["ui"])
            self.assertEqual(payload["missing_target_count"], 1)
            self.assertEqual(payload["drifted_target_count"], 1)
            self.assertEqual(payload["projects"][0]["state"], "missing_and_drifted")

    def test_synthesize_design_mirror_hygiene_tasks_requires_repeated_observations(self) -> None:
        project_state = {
            "missing_targets": [
                ".codex-design/product/README.md",
                ".codex-design/product/START_HERE.md",
            ],
            "drifted_targets": [
                {"path": ".codex-design/product/ROADMAP.md"},
                {"path": ".codex-design/review/REVIEW_CONTEXT.md"},
            ],
        }

        none = self.auditor.synthesize_design_mirror_hygiene_tasks(
            project_id="fleet",
            project_state=project_state,
            occurrence_count=2,
            min_repeat_count=3,
        )
        tasks = self.auditor.synthesize_design_mirror_hygiene_tasks(
            project_id="fleet",
            project_state=project_state,
            occurrence_count=3,
            min_repeat_count=3,
        )

        self.assertEqual(none, [])
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["synthesis_cluster"], "design_mirror_hygiene")
        self.assertEqual(tasks[0]["source_item_count"], 4)
        self.assertEqual(tasks[0]["mirror_cluster"], "product_bundle")
        self.assertEqual(tasks[0]["repeat_observation_count"], 3)

    def test_persist_findings_tracks_occurrence_count_for_repeated_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "fleet.db"
            original_db_path = self.auditor.DB_PATH
            self.auditor.DB_PATH = db_path
            try:
                self.auditor.init_db()
                now = dt.datetime(2026, 4, 18, 18, 0, tzinfo=dt.timezone.utc)
                finding = {
                    "scope_type": "project",
                    "scope_id": "fleet",
                    "finding_key": "project.design_mirror_missing_or_stale",
                    "severity": "medium",
                    "title": "Repo-local Chummer design mirror is missing or stale",
                    "summary": "mirror drift",
                    "evidence": [],
                    "candidate_tasks": [{"title": "Refresh local design mirror", "detail": "sync it"}],
                }

                self.auditor.persist_findings([finding], now)
                self.auditor.persist_findings([finding], now + dt.timedelta(minutes=5))

                with self.auditor.db() as conn:
                    row = conn.execute(
                        "SELECT occurrence_count FROM audit_findings WHERE scope_type='project' AND scope_id='fleet' AND finding_key='project.design_mirror_missing_or_stale'"
                    ).fetchone()

                self.assertIsNotNone(row)
                self.assertEqual(row["occurrence_count"], 2)
            finally:
                self.auditor.DB_PATH = original_db_path

    def test_design_mirror_specs_expand_product_groups(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            design_root = root / "design"
            repo_root = root / "fleet"
            (design_root / "products" / "chummer" / "projects").mkdir(parents=True, exist_ok=True)
            (design_root / "products" / "chummer" / "review").mkdir(parents=True, exist_ok=True)
            (design_root / "products" / "chummer" / "horizons").mkdir(parents=True, exist_ok=True)
            (design_root / "products" / "chummer" / "sync").mkdir(parents=True, exist_ok=True)
            repo_root.mkdir()

            (design_root / "products" / "chummer" / "README.md").write_text("product readme", encoding="utf-8")
            (design_root / "products" / "chummer" / "START_HERE.md").write_text("start here", encoding="utf-8")
            (design_root / "products" / "chummer" / "horizons" / "alice.md").write_text("horizon", encoding="utf-8")
            (design_root / "products" / "chummer" / "projects" / "fleet.md").write_text("repo scope", encoding="utf-8")
            (design_root / "products" / "chummer" / "review" / "fleet.AGENTS.template.md").write_text("review scope", encoding="utf-8")
            (design_root / "products" / "chummer" / "sync" / "sync-manifest.yaml").write_text(
                """
product_source_groups:
  base_governance:
    - products/chummer/README.md
    - products/chummer/START_HERE.md
  horizons:
    - products/chummer/horizons/alice.md
mirrors:
  - repo: fleet
    product_groups: [base_governance, horizons]
    repo_source: products/chummer/projects/fleet.md
    review_source: products/chummer/review/fleet.AGENTS.template.md
""".strip(),
                encoding="utf-8",
            )

            specs = self.auditor.design_mirror_specs(
                {
                    "projects": [
                        {"id": "design", "path": str(design_root)},
                        {"id": "fleet", "path": str(repo_root)},
                    ]
                }
            )

            self.assertEqual(len(specs), 1)
            targets = {item["target"].relative_to(repo_root).as_posix() for item in specs[0]["files"]}
            self.assertIn(".codex-design/product/README.md", targets)
            self.assertIn(".codex-design/product/START_HERE.md", targets)
            self.assertIn(".codex-design/product/horizons/alice.md", targets)
            self.assertIn(".codex-design/repo/IMPLEMENTATION_SCOPE.md", targets)
            self.assertIn(".codex-design/review/REVIEW_CONTEXT.md", targets)

    def test_persist_findings_resolves_stale_published_task_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "fleet.db"
            original_db_path = self.auditor.DB_PATH
            self.auditor.DB_PATH = db_path
            try:
                self.auditor.init_db()
                now = dt.datetime(2026, 3, 28, 22, 30, tzinfo=dt.timezone.utc)
                now_text = self.auditor.iso(now)
                with self.auditor.db() as conn:
                    conn.execute(
                        """
                        INSERT INTO audit_findings(
                            scope_type, scope_id, finding_key, severity, title, summary, status, source,
                            evidence_json, candidate_tasks_json, first_seen_at, last_seen_at, resolved_at
                        )
                        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            "project",
                            "fleet",
                            "project.design_mirror_missing_or_stale",
                            "medium",
                            "Repo-local Chummer design mirror is missing or stale",
                            "stale mirror finding",
                            "open",
                            "fleet-auditor",
                            "[]",
                            "[]",
                            now_text,
                            now_text,
                            None,
                        ),
                    )
                    conn.execute(
                        """
                        INSERT INTO audit_task_candidates(
                            scope_type, scope_id, finding_key, task_index, title, detail, task_meta_json, status, source,
                            first_seen_at, last_seen_at, resolved_at
                        )
                        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            "project",
                            "fleet",
                            "project.design_mirror_missing_or_stale",
                            0,
                            "Refresh local design mirror",
                            "Sync the approved Chummer design bundle into `fleet` under `.codex-design/` and refresh repo-local review context.",
                            "{}",
                            "published",
                            "fleet-auditor",
                            now_text,
                            now_text,
                            None,
                        ),
                    )

                self.auditor.persist_findings([], now)

                with self.auditor.db() as conn:
                    task = conn.execute("SELECT status, resolved_at FROM audit_task_candidates").fetchone()

                self.assertIsNotNone(task)
                self.assertEqual(task["status"], "resolved")
                self.assertEqual(task["resolved_at"], now_text)
            finally:
                self.auditor.DB_PATH = original_db_path

    def test_run_audit_pass_persists_trace_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "fleet.db"
            original_db_path = self.auditor.DB_PATH
            self.auditor.DB_PATH = db_path
            try:
                self.auditor.init_db()
                self.auditor.normalize_config = lambda: {}
                self.auditor.collect_findings = lambda _config: []
                self.auditor.persist_findings = lambda findings, now: (0, 0)

                import asyncio

                asyncio.run(self.auditor.run_audit_pass())
                status = self.auditor.auditor_status()

                self.assertTrue(str((status.get("last_run") or {}).get("trace_id") or "").startswith("auditor-"))
                self.assertEqual((status.get("last_run") or {}).get("status"), "succeeded")
            finally:
                self.auditor.DB_PATH = original_db_path

    def test_core_legacy_quarantine_helper_requires_inventory_and_verify_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "docs").mkdir(parents=True, exist_ok=True)
            (root / "scripts" / "ai").mkdir(parents=True, exist_ok=True)
            (root / "docs" / "LEGACY_ROOT_SURFACE_INVENTORY.md").write_text(
                """
# Legacy Root Surface Inventory

## Compatibility-only roots

- `Chummer/`
- `Plugins/`
- `Chummer.Infrastructure.Browser/`

## Exit statement

legacy-root quarantine is materially closed
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "scripts" / "ai" / "verify.sh").write_text(
                """
test -f docs/LEGACY_ROOT_SURFACE_INVENTORY.md
rg -n 'Chummer.Infrastructure.Browser/Chummer.Infrastructure.Browser.csproj' docs/LEGACY_ROOT_SURFACE_INVENTORY.md >/dev/null
rg -n 'WL-111' docs/LEGACY_PLUGIN_PURIFICATION_INCREMENT_WL111.md >/dev/null
rg -n 'WL-112' docs/LEGACY_PLUGIN_AND_HELPER_OPERATIONAL_EVIDENCE_WL112.md >/dev/null
""".strip()
                + "\n",
                encoding="utf-8",
            )

            self.assertTrue(self.auditor.core_legacy_quarantine_is_verifier_backed(root))

    def test_hub_media_contracts_helper_only_flags_render_only_dto_leakage(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            contracts_dir = root / "Chummer.Run.Contracts"
            contracts_dir.mkdir(parents=True, exist_ok=True)
            media_contracts = contracts_dir / "MediaContracts.cs"
            media_contracts.write_text(
                """
using Chummer.Media.Contracts;
namespace Chummer.Run.Contracts.Media;
public sealed record NewsBriefResult(string NewsBriefId, MediaRenderJobState? VideoJobState = null);
""".strip()
                + "\n",
                encoding="utf-8",
            )
            self.assertFalse(self.auditor.hub_media_contracts_still_mix_render_only_dtos(root))

            media_contracts.write_text(
                """
using Chummer.Media.Contracts;
namespace Chummer.Run.Contracts.Media;
public sealed record PacketFactoryRequest(string PacketId);
""".strip()
                + "\n",
                encoding="utf-8",
            )
            self.assertTrue(self.auditor.hub_media_contracts_still_mix_render_only_dtos(root))


if __name__ == "__main__":
    unittest.main()
