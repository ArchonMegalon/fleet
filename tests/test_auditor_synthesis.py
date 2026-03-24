from __future__ import annotations

import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path


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

    def test_design_mirror_specs_expand_product_groups(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            design_root = root / "design"
            repo_root = root / "fleet"
            (design_root / "products" / "chummer" / "projects").mkdir(parents=True, exist_ok=True)
            (design_root / "products" / "chummer" / "review").mkdir(parents=True, exist_ok=True)
            (design_root / "products" / "chummer" / "sync").mkdir(parents=True, exist_ok=True)
            repo_root.mkdir()

            (design_root / "products" / "chummer" / "README.md").write_text("product readme", encoding="utf-8")
            (design_root / "products" / "chummer" / "START_HERE.md").write_text("start here", encoding="utf-8")
            (design_root / "products" / "chummer" / "projects" / "fleet.md").write_text("repo scope", encoding="utf-8")
            (design_root / "products" / "chummer" / "review" / "fleet.AGENTS.template.md").write_text("review scope", encoding="utf-8")
            (design_root / "products" / "chummer" / "sync" / "sync-manifest.yaml").write_text(
                """
product_source_groups:
  base_governance:
    - products/chummer/README.md
    - products/chummer/START_HERE.md
mirrors:
  - repo: fleet
    product_groups: [base_governance]
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
            self.assertIn(".codex-design/repo/IMPLEMENTATION_SCOPE.md", targets)
            self.assertIn(".codex-design/review/REVIEW_CONTEXT.md", targets)


if __name__ == "__main__":
    unittest.main()
