from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path("/docker/fleet/admin/readiness.py")


def load_readiness_module():
    spec = importlib.util.spec_from_file_location("test_readiness_module", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReadinessTaxonomyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.readiness = load_readiness_module()

    def test_boundary_pure_repo_stops_before_public_promotion(self) -> None:
        payload = self.readiness.derive_project_readiness(
            project_id="ui-kit",
            repo_slug="chummer6-ui-kit",
            lifecycle="scaffold",
            runtime_status="scaffold_complete",
            runtime_completion_state="scaffold_complete",
            compile_summary_payload={"published_at": "2026-03-18T10:00:00Z"},
            compile_health_payload={"status": "ready", "summary": "compile artifacts are current for the declared lifecycle"},
            deployment={
                "status": "protected_preview",
                "promotion_stage": "protected_preview",
                "target_url": "https://chummer.run/uikit",
                "visibility": "public",
            },
            boundary_meta={"status": "healthy", "score": 0.74, "reason": "Shared package boundary is clear."},
        )

        self.assertEqual(payload["stage"], "boundary_pure")
        self.assertEqual(payload["next_stage"], "publicly_promoted")
        self.assertEqual(payload["terminal_stage"], "publicly_promoted")
        self.assertFalse(payload["final_claim_allowed"])
        self.assertEqual(payload["warning_count"], 0)

    def test_promoted_surface_without_boundary_purity_raises_validator_warning(self) -> None:
        payload = self.readiness.derive_project_readiness(
            project_id="ui",
            repo_slug="chummer6-ui",
            lifecycle="live",
            runtime_status="queue_exhausted",
            runtime_completion_state="runtime_complete",
            compile_summary_payload={"published_at": "2026-03-18T10:00:00Z"},
            compile_health_payload={"status": "ready", "summary": "compile artifacts are current for the declared lifecycle"},
            deployment={
                "status": "promoted_preview",
                "promotion_stage": "promoted_preview",
                "target_url": "https://chummer.run/blazor/",
                "visibility": "public",
            },
            boundary_meta={"status": "risk", "score": 0.41, "reason": "Legacy desktop/helper roots still spill across the repo."},
        )

        self.assertEqual(payload["stage"], "package_canonical")
        self.assertEqual(payload["next_stage"], "boundary_pure")
        self.assertTrue(any(item["kind"] == "deployment_ahead_of_boundary" for item in payload["validator_checks"]))

    def test_group_deployment_requires_boundary_pure_owner_projects_before_public_promotion(self) -> None:
        payload = self.readiness.derive_group_deployment_readiness(
            group_id="chummer-vnext",
            deployment={
                "status": "promoted_preview",
                "promotion_stage": "promoted_preview",
                "target_url": "https://chummer.run",
            },
            owner_projects=[
                {
                    "id": "ui",
                    "readiness": {
                        "stage": "package_canonical",
                        "label": "Package-Canonical",
                        "checks": {"boundary_pure": {"evidence_met": False}},
                    },
                },
                {
                    "id": "mobile",
                    "readiness": {
                        "stage": "boundary_pure",
                        "label": "Boundary-Pure",
                        "checks": {"boundary_pure": {"evidence_met": True}},
                    },
                },
            ],
        )

        self.assertFalse(payload["publicly_promoted"])
        self.assertEqual(payload["blocking_owner_projects"], ["ui"])
        self.assertIn("not boundary-pure", payload["summary"])

    def test_studio_compile_summary_treats_workpackages_as_dispatchable_truth(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            published = root / ".codex-studio" / "published"
            published.mkdir(parents=True, exist_ok=True)
            (published / "compile.manifest.json").write_text(
                json.dumps(
                    {
                        "published_at": "2026-03-23T10:00:00Z",
                        "artifacts": ["WORKPACKAGES.generated.yaml"],
                        "stages": {
                            "design_compile": True,
                            "policy_compile": True,
                            "execution_compile": False,
                            "capacity_compile": False,
                        },
                        "dispatchable_truth_ready": False,
                    }
                ),
                encoding="utf-8",
            )

            summary = self.readiness.studio_compile_summary(root)
            health = self.readiness.compile_health(summary, "dispatchable")

        self.assertTrue(summary["stages"]["execution_compile"])
        self.assertTrue(summary["stages"]["package_compile"])
        self.assertTrue(summary["dispatchable_truth_ready"])
        self.assertEqual(health["status"], "ready")


if __name__ == "__main__":
    unittest.main()
