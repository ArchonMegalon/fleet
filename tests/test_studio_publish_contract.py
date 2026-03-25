from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path


MODULE_PATH = Path("/docker/fleet/studio/app.py")


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

    class DummyHTTPException(Exception):
        pass

    class DummyRequest:
        pass

    class DummyResponse:
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

    def dummy_form(*args, **kwargs):
        return None

    fastapi.FastAPI = DummyFastAPI
    fastapi.Form = dummy_form
    fastapi.HTTPException = DummyHTTPException
    fastapi.Request = DummyRequest
    responses.HTMLResponse = DummyResponse
    responses.JSONResponse = DummyResponse
    responses.PlainTextResponse = DummyResponse
    responses.RedirectResponse = DummyResponse
    sys.modules["fastapi"] = fastapi
    sys.modules["fastapi.responses"] = responses


def load_studio_module():
    install_fastapi_stubs()
    spec = importlib.util.spec_from_file_location("test_studio_publish_contract", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StudioPublishContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.studio = load_studio_module()

    def test_normalize_studio_role_name_maps_operator_alias(self) -> None:
        role = self.studio.normalize_studio_role_name("operator", {"designer": {}, "product_governor": {}})

        self.assertEqual(role, "product_governor")

    def test_safe_relative_publish_path_allows_workpackages_overlay(self) -> None:
        rel = self.studio.safe_relative_publish_path(".codex-studio/published/WORKPACKAGES.generated.yaml")

        self.assertEqual(rel.as_posix(), "WORKPACKAGES.generated.yaml")

    def test_safe_relative_publish_path_allows_progress_report_artifacts(self) -> None:
        rel = self.studio.safe_relative_publish_path(".codex-studio/published/PROGRESS_REPORT.generated.json")
        history_rel = self.studio.safe_relative_publish_path(".codex-studio/published/PROGRESS_HISTORY.generated.json")

        self.assertEqual(rel.as_posix(), "PROGRESS_REPORT.generated.json")
        self.assertEqual(history_rel.as_posix(), "PROGRESS_HISTORY.generated.json")

    def test_compile_manifest_payload_marks_workpackages_as_dispatchable_truth(self) -> None:
        payload = self.studio.compile_manifest_payload(
            {
                "target_type": "project",
                "target_id": "fleet",
                "project_cfg": {"lifecycle": "dispatchable"},
            },
            [
                {"path": "WORKPACKAGES.generated.yaml", "content": "work_packages: []\n"},
            ],
        )

        self.assertTrue(payload["stages"]["policy_compile"])
        self.assertTrue(payload["stages"]["execution_compile"])
        self.assertTrue(payload["stages"]["package_compile"])
        self.assertTrue(payload["stages"]["capacity_compile"])
        self.assertTrue(payload["dispatchable_truth_ready"])
        self.assertEqual(payload["dispatchable_truth_contract"]["scope"], "execution_truth_only")
        self.assertTrue(payload["dispatchable_truth_contract"]["execution_compile_required"])
        self.assertTrue(payload["dispatchable_truth_contract"]["design_compile_required_separately"])
        self.assertTrue(payload["dispatchable_truth_contract"]["package_compile_required_separately"])
        self.assertTrue(payload["dispatchable_truth_contract"]["capacity_compile_required_separately"])

    def test_compile_manifest_payload_marks_stale_workpackages_overlay_not_ready(self) -> None:
        stale_fingerprint = self.studio.work_package_source_queue_fingerprint(["Different Queue Slice"])

        payload = self.studio.compile_manifest_payload(
            {
                "target_type": "project",
                "target_id": "fleet",
                "project_cfg": {"lifecycle": "dispatchable", "queue": ["Live Queue Slice"]},
            },
            [
                {
                    "path": "WORKPACKAGES.generated.yaml",
                    "content": (
                        f"source_queue_fingerprint: {stale_fingerprint}\n"
                        "work_packages:\n"
                        "  - title: Overlay Slice\n"
                    ),
                },
            ],
        )

        self.assertTrue(payload["stages"]["execution_compile"])
        self.assertTrue(payload["stages"]["package_compile"])
        self.assertFalse(payload["dispatchable_truth_ready"])

    def test_compile_manifest_payload_marks_bound_queue_overlay_as_dispatchable_truth(self) -> None:
        base_queue = ["Base Queue Slice"]
        base_fingerprint = self.studio.work_package_source_queue_fingerprint(base_queue)

        payload = self.studio.compile_manifest_payload(
            {
                "target_type": "project",
                "target_id": "fleet",
                "project_cfg": {"lifecycle": "dispatchable", "queue": base_queue},
            },
            [
                {
                    "path": "QUEUE.generated.yaml",
                    "content": (
                        f"source_queue_fingerprint: {base_fingerprint}\n"
                        "mode: append\n"
                        "items:\n"
                        "  - Overlay Slice\n"
                    ),
                },
            ],
        )

        self.assertTrue(payload["stages"]["execution_compile"])
        self.assertTrue(payload["dispatchable_truth_ready"])

    def test_compile_manifest_payload_marks_stale_queue_overlay_not_ready(self) -> None:
        stale_fingerprint = self.studio.work_package_source_queue_fingerprint(["Different Queue Slice"])

        payload = self.studio.compile_manifest_payload(
            {
                "target_type": "project",
                "target_id": "fleet",
                "project_cfg": {"lifecycle": "dispatchable", "queue": ["Live Queue Slice"]},
            },
            [
                {
                    "path": "QUEUE.generated.yaml",
                    "content": (
                        f"source_queue_fingerprint: {stale_fingerprint}\n"
                        "mode: append\n"
                        "items:\n"
                        "  - Overlay Slice\n"
                    ),
                },
            ],
        )

        self.assertTrue(payload["stages"]["execution_compile"])
        self.assertFalse(payload["dispatchable_truth_ready"])

    def test_publish_target_files_stamps_queue_overlay_and_writes_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            target_cfg = {
                "target_type": "project",
                "target_id": "fleet",
                "path": str(root),
                "feedback_dir": "feedback",
                "project_cfg": {"id": "fleet", "lifecycle": "dispatchable", "queue": ["Base Queue Slice"]},
            }

            published_root, feedback_rel = self.studio.publish_target_files(
                target_cfg,
                files=[
                    {
                        "path": "QUEUE.generated.yaml",
                        "content": "mode: append\nitems:\n  - Overlay Slice\n",
                    }
                ],
                publish_feedback=False,
                feedback_note="",
            )

            queue_payload = self.studio.yaml.safe_load((published_root / "QUEUE.generated.yaml").read_text(encoding="utf-8")) or {}
            manifest_payload = json.loads((published_root / "compile.manifest.json").read_text(encoding="utf-8"))

        self.assertIsNone(feedback_rel)
        self.assertEqual(
            queue_payload.get("source_queue_fingerprint"),
            self.studio.work_package_source_queue_fingerprint(["Base Queue Slice"]),
        )
        self.assertTrue(manifest_payload["dispatchable_truth_ready"])
        self.assertEqual(manifest_payload["dispatchable_truth_contract"]["scope"], "execution_truth_only")

    def test_publish_target_files_stamps_queue_overlay_from_queue_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "WORKLIST.md").write_text("- [todo] wl-1 Source Queue Slice\n", encoding="utf-8")
            target_cfg = {
                "target_type": "project",
                "target_id": "core",
                "path": str(root),
                "feedback_dir": "feedback",
                "project_cfg": {
                    "id": "core",
                    "lifecycle": "dispatchable",
                    "path": str(root),
                    "queue": ["Base Queue Slice"],
                    "queue_sources": [{"kind": "worklist", "path": "WORKLIST.md", "mode": "append"}],
                },
            }

            published_root, _feedback_rel = self.studio.publish_target_files(
                target_cfg,
                files=[
                    {
                        "path": "QUEUE.generated.yaml",
                        "content": "mode: append\nitems:\n  - Overlay Slice\n",
                    }
                ],
                publish_feedback=False,
                feedback_note="",
            )

            queue_payload = self.studio.yaml.safe_load((published_root / "QUEUE.generated.yaml").read_text(encoding="utf-8")) or {}

        self.assertEqual(
            queue_payload.get("source_queue_fingerprint"),
            self.studio.work_package_source_queue_fingerprint(["Base Queue Slice", "Source Queue Slice"]),
        )

    def test_compile_manifest_payload_treats_status_plane_as_policy_compile_artifact(self) -> None:
        payload = self.studio.compile_manifest_payload(
            {
                "target_type": "project",
                "target_id": "fleet",
                "project_cfg": {"lifecycle": "dispatchable"},
            },
            [
                {"path": "STATUS_PLANE.generated.yaml", "content": "contract_name: fleet.status_plane\nschema_version: 1\n"},
            ],
        )

        self.assertTrue(payload["stages"]["policy_compile"])

    def test_studio_role_runtime_brief_uses_published_status_and_progress_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            published = root / ".codex-studio" / "published"
            published.mkdir(parents=True, exist_ok=True)
            (published / "STATUS_PLANE.generated.yaml").write_text(
                (
                    "readiness_summary:\n"
                    "  counts:\n"
                    "    package_canonical: 1\n"
                    "    publicly_promoted: 0\n"
                    "  warning_count: 2\n"
                    "  final_claim_ready: 1\n"
                    "dispatch_policy:\n"
                    "  participant_dispatch_canary_count: 2\n"
                    "  operator_only_projects:\n"
                    "    - fleet\n"
                ),
                encoding="utf-8",
            )
            (published / "PROGRESS_REPORT.generated.json").write_text(
                json.dumps(
                    {
                        "overall_progress_percent": 73,
                        "phase_label": "Scale & stabilize",
                        "next_checkpoint_eta_weeks_low": 2,
                        "next_checkpoint_eta_weeks_high": 4,
                    }
                ),
                encoding="utf-8",
            )
            original_root = self.studio.fleet_repo_root
            try:
                self.studio.fleet_repo_root = lambda: root
                brief = self.studio.studio_role_runtime_brief({"target_type": "fleet", "target_id": "fleet"}, "product_governor")
            finally:
                self.studio.fleet_repo_root = original_root

        self.assertIn("Readiness ladder", brief)
        self.assertIn("Dispatch posture", brief)
        self.assertIn("73%", brief)
        self.assertIn("2-4 weeks", brief)

    def test_build_prompt_includes_control_decision_contract_for_product_governor(self) -> None:
        original_build_conversation_window = self.studio.build_conversation_window
        original_existing_context_files = self.studio.existing_context_files
        original_fleet_repo_root = self.studio.fleet_repo_root
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            published = root / ".codex-studio" / "published"
            published.mkdir(parents=True, exist_ok=True)
            (published / "STATUS_PLANE.generated.yaml").write_text("projects: []\n", encoding="utf-8")
            (published / "PROGRESS_REPORT.generated.json").write_text("{}", encoding="utf-8")
            try:
                self.studio.build_conversation_window = lambda *_args, **_kwargs: "admin: give me the product pulse"
                self.studio.existing_context_files = lambda _target_cfg: [".codex-design/product/README.md"]
                self.studio.fleet_repo_root = lambda: root
                prompt = self.studio.build_prompt(
                    {"studio": {"session_message_window": 8, "roles": {"product_governor": {}}}},
                    {"target_type": "fleet", "target_id": "fleet"},
                    {"id": 7, "role": "operator", "summary": "Need a whole-product routing pass."},
                )
            finally:
                self.studio.build_conversation_window = original_build_conversation_window
                self.studio.existing_context_files = original_existing_context_files
                self.studio.fleet_repo_root = original_fleet_repo_root

        self.assertIn("Product Governor", prompt)
        self.assertIn("Role-priority files:", prompt)
        self.assertIn("proposal.control_decision", prompt)
        self.assertIn("Current runtime brief:", prompt)


if __name__ == "__main__":
    unittest.main()
