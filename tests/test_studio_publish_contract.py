from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import datetime as dt
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

    def configure_temp_studio(self, root: Path) -> None:
        config_dir = root / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "policies.yaml").write_text("policies: {}\n", encoding="utf-8")
        (config_dir / "routing.yaml").write_text("spider: {}\n", encoding="utf-8")
        (config_dir / "groups.yaml").write_text("project_groups: []\n", encoding="utf-8")
        (config_dir / "accounts.yaml").write_text("accounts: {}\n", encoding="utf-8")
        (config_dir / "fleet.yaml").write_text(
            (
                "projects:\n"
                "  - id: fleet\n"
                f"    path: {root.as_posix()}\n"
                "studio:\n"
                "  autonomy:\n"
                "    enabled: true\n"
                "    poll_seconds: 30\n"
                "    auto_publish_recommended: true\n"
                "    roles:\n"
                "      designer:\n"
                "        enabled: true\n"
                "        target_type: fleet\n"
                "        target_id: fleet\n"
                "        interval_seconds: 1800\n"
                "        min_interval_seconds: 60\n"
                "      product_governor:\n"
                "        enabled: true\n"
                "        target_type: fleet\n"
                "        target_id: fleet\n"
                "        interval_seconds: 600\n"
                "        min_interval_seconds: 60\n"
                "  roles:\n"
                "    designer: {}\n"
                "    product_governor: {}\n"
            ),
            encoding="utf-8",
        )
        self.studio.CONFIG_PATH = config_dir / "fleet.yaml"
        self.studio.ACCOUNTS_PATH = config_dir / "accounts.yaml"
        self.studio.POLICIES_PATH = config_dir / "policies.yaml"
        self.studio.ROUTING_PATH = config_dir / "routing.yaml"
        self.studio.GROUPS_PATH = config_dir / "groups.yaml"
        self.studio.PROJECTS_DIR = config_dir / "projects"
        self.studio.PROJECT_INDEX_PATH = self.studio.PROJECTS_DIR / "_index.yaml"
        self.studio.DB_PATH = root / "state" / "fleet.db"
        self.studio.LOG_DIR = root / "state" / "logs"
        self.studio.CODEX_HOME_ROOT = root / "state" / "homes"
        self.studio.GROUP_ROOT = root / "state" / "groups"

    def write_autonomy_trigger_files(self, root: Path) -> None:
        for rel, content in {
            ".codex-design/product/LEAD_DESIGNER_OPERATING_MODEL.md": "designer\n",
            ".codex-design/product/OWNERSHIP_MATRIX.md": "ownership\n",
            ".codex-design/product/CONTRACT_SETS.yaml": "contracts: []\n",
            ".codex-design/product/PROGRAM_MILESTONES.yaml": "milestones: []\n",
            ".codex-design/product/GROUP_BLOCKERS.md": "# blockers\n",
            ".codex-design/product/PRODUCT_GOVERNOR_AND_AUTOPILOT_LOOP.md": "governor\n",
            ".codex-design/product/PRODUCT_HEALTH_SCORECARD.yaml": "scorecards: []\n",
            ".codex-design/product/FEEDBACK_AND_SIGNAL_OODA_LOOP.md": "ooda\n",
            ".codex-design/product/FEEDBACK_AND_CRASH_STATUS_MODEL.md": "status\n",
            ".codex-studio/published/STATUS_PLANE.generated.yaml": "projects: []\n",
            ".codex-studio/published/PROGRESS_REPORT.generated.json": "{}\n",
        }.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    def test_normalize_studio_role_name_maps_operator_alias(self) -> None:
        role = self.studio.normalize_studio_role_name("operator", {"designer": {}, "product_governor": {}})

        self.assertEqual(role, "product_governor")

    def test_studio_autonomy_should_queue_on_first_run_and_change(self) -> None:
        now = dt.datetime(2026, 3, 25, 12, 0, tzinfo=dt.timezone.utc)
        should_queue, reason = self.studio.studio_autonomy_should_queue(
            {"interval_seconds": 600, "min_interval_seconds": 60},
            None,
            now=now,
            trigger_fingerprint="abc",
        )

        self.assertTrue(should_queue)
        self.assertEqual(reason, "first autonomous pulse")

        state_row = {
            "last_run_at": "2026-03-25T11:58:00Z",
            "trigger_fingerprint": "old",
        }
        should_queue, reason = self.studio.studio_autonomy_should_queue(
            {"interval_seconds": 600, "min_interval_seconds": 60},
            state_row,
            now=now,
            trigger_fingerprint="new",
        )

        self.assertTrue(should_queue)
        self.assertEqual(reason, "trigger inputs changed")

    def test_safe_relative_publish_path_allows_workpackages_overlay(self) -> None:
        rel = self.studio.safe_relative_publish_path(".codex-studio/published/WORKPACKAGES.generated.yaml")

        self.assertEqual(rel.as_posix(), "WORKPACKAGES.generated.yaml")

    def test_safe_relative_publish_path_allows_progress_report_artifacts(self) -> None:
        rel = self.studio.safe_relative_publish_path(".codex-studio/published/PROGRESS_REPORT.generated.json")
        history_rel = self.studio.safe_relative_publish_path(".codex-studio/published/PROGRESS_HISTORY.generated.json")
        journey_rel = self.studio.safe_relative_publish_path(".codex-studio/published/JOURNEY_GATES.generated.json")

        self.assertEqual(rel.as_posix(), "PROGRESS_REPORT.generated.json")
        self.assertEqual(history_rel.as_posix(), "PROGRESS_HISTORY.generated.json")
        self.assertEqual(journey_rel.as_posix(), "JOURNEY_GATES.generated.json")

    def test_safe_relative_publish_path_allows_generated_proof_and_release_channel_artifacts(self) -> None:
        exit_gate_rel = self.studio.safe_relative_publish_path(".codex-studio/published/UI_LINUX_DESKTOP_EXIT_GATE.generated.json")
        proof_rel = self.studio.safe_relative_publish_path(".codex-studio/published/HUB_LOCAL_RELEASE_PROOF.generated.json")
        channel_rel = self.studio.safe_relative_publish_path(".codex-studio/published/RELEASE_CHANNEL.generated.json")
        compat_rel = self.studio.safe_relative_publish_path(".codex-studio/published/releases.json")
        proof_kit_rel = self.studio.safe_relative_publish_path(".codex-studio/published/external-proof-kit-20260405T233846Z.tar.gz")

        self.assertEqual(exit_gate_rel.as_posix(), "UI_LINUX_DESKTOP_EXIT_GATE.generated.json")
        self.assertEqual(proof_rel.as_posix(), "HUB_LOCAL_RELEASE_PROOF.generated.json")
        self.assertEqual(channel_rel.as_posix(), "RELEASE_CHANNEL.generated.json")
        self.assertEqual(compat_rel.as_posix(), "releases.json")
        self.assertEqual(proof_kit_rel.as_posix(), "external-proof-kit-20260405T233846Z.tar.gz")

    def test_safe_relative_publish_path_rejects_noncanonical_generated_artifacts(self) -> None:
        with self.assertRaises(ValueError):
            self.studio.safe_relative_publish_path(".codex-studio/published/ui_linux_desktop_exit_gate.generated.json")

        with self.assertRaises(ValueError):
            self.studio.safe_relative_publish_path(".codex-studio/published/ARBITRARY.txt")

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
            (published / "SUPPORT_CASE_PACKETS.generated.json").write_text(
                json.dumps(
                    {
                        "summary": {
                            "open_case_count": 3,
                            "design_impact_count": 1,
                            "lane_counts": {"code": 2, "canon": 1},
                            "owner_repo_counts": {"chummer6-design": 1, "chummer6-ui": 2},
                        }
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
        self.assertIn("Support pulse", brief)
        self.assertIn("3 open cases", brief)

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
            (published / "SUPPORT_CASE_PACKETS.generated.json").write_text("{}", encoding="utf-8")
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

    def test_create_session_records_automation_origin(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.configure_temp_studio(root)
            self.studio.init_db()

            session_id = self.studio.create_session(
                "project",
                "fleet",
                "operator",
                "",
                "Autonomous product pulse",
                origin_type="automation",
                origin_name="product_governor.autopilot",
                automation_fingerprint="fingerprint-1",
            )

            with self.studio.db() as conn:
                row = conn.execute("SELECT role, origin_type, origin_name, automation_fingerprint FROM studio_sessions WHERE id=?", (session_id,)).fetchone()

        self.assertEqual(row["role"], "product_governor")
        self.assertEqual(row["origin_type"], "automation")
        self.assertEqual(row["origin_name"], "product_governor.autopilot")
        self.assertEqual(row["automation_fingerprint"], "fingerprint-1")

    def test_resolve_target_cfg_uses_real_runner_project_for_fleet_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.configure_temp_studio(root)

            config = self.studio.normalize_config()
            target_cfg = self.studio.resolve_target_cfg(config, "fleet", "fleet")

        self.assertEqual(target_cfg["target_type"], "fleet")
        self.assertEqual(target_cfg["run_project_id"], "fleet")

    def test_resolve_target_cfg_uses_real_runner_project_for_group_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.configure_temp_studio(root)
            self.studio.GROUPS_PATH.write_text(
                "project_groups:\n  - id: hub\n    projects: [fleet]\n",
                encoding="utf-8",
            )

            config = self.studio.normalize_config()
            target_cfg = self.studio.resolve_target_cfg(config, "group", "hub")

        self.assertEqual(target_cfg["target_type"], "group")
        self.assertEqual(target_cfg["target_id"], "hub")
        self.assertEqual(target_cfg["run_project_id"], "fleet")

    def test_normalize_config_enables_skip_git_repo_check_for_designer_and_governor(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.configure_temp_studio(root)

            config = self.studio.normalize_config()

        self.assertTrue(config["studio"]["roles"]["designer"]["skip_git_repo_check"])
        self.assertTrue(config["studio"]["roles"]["product_governor"]["skip_git_repo_check"])

    def test_seed_auth_json_prefers_freshest_shared_auth_home(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.configure_temp_studio(root)
            homes_root = root / "state" / "homes"
            homes_root.mkdir(parents=True, exist_ok=True)
            self.studio.CODEX_HOME_ROOT = homes_root

            source = root / "secrets" / "chatgpt.auth.json"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text("source-token", encoding="utf-8")
            source_mtime = source.stat().st_mtime
            source_hash = self.studio.sha256_bytes(source.read_bytes())

            fresh_home = homes_root / "acct-shared-b"
            fresh_home.mkdir(parents=True, exist_ok=True)
            (fresh_home / ".auth_source.sha256").write_text(source_hash, encoding="utf-8")
            (fresh_home / "auth.json").write_text("fresh-token", encoding="utf-8")
            os.utime(fresh_home / "auth.json", (source_mtime + 30, source_mtime + 30))

            target_home = homes_root / "acct-studio-a"
            target_home.mkdir(parents=True, exist_ok=True)

            self.studio.seed_auth_json(target_home, source)

            self.assertEqual((target_home / "auth.json").read_text(encoding="utf-8"), "fresh-token")
            self.assertEqual((target_home / ".auth_source.sha256").read_text(encoding="utf-8"), source_hash)

    def test_parse_auth_failure_message_detects_reused_refresh_token(self) -> None:
        message = self.studio.parse_auth_failure_message(
            '401 Unauthorized {"code":"refresh_token_reused","message":"Please try signing in again."}'
        )

        self.assertEqual(message, "chatgpt auth refresh token was already used; sign in again")

    def test_parse_auth_failure_message_detects_ea_token_and_principal_failures(self) -> None:
        message = self.studio.parse_auth_failure_message(
            "401 Unauthorized: missing bearer or basic authentication in header"
        )
        self.assertEqual(message, "ea runtime auth token is missing")

        message = self.studio.parse_auth_failure_message("401 Unauthorized because missing x-ea-principal-id")
        self.assertEqual(message, "ea runtime principal is missing")

    def test_parse_auth_retry_seconds_defaults_and_parses_minutes(self) -> None:
        self.assertEqual(self.studio.parse_auth_retry_seconds("please retry after 90s", 30), 90)
        self.assertEqual(self.studio.parse_auth_retry_seconds("retry after 2m", 30), 120)
        self.assertEqual(self.studio.parse_auth_retry_seconds("rate limited", 45), 45)

    def test_model_supported_for_auth_kind_blocks_non_ea_models_for_ea_accounts(self) -> None:
        self.assertTrue(self.studio.model_supported_for_auth_kind("ea-groundwork-gemini", "ea"))
        self.assertFalse(self.studio.model_supported_for_auth_kind("gpt-5.3-codex", "ea"))

    def test_prepare_account_environment_supports_ea_runtime_accounts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.configure_temp_studio(root)
            self.studio.init_db()
            prior = {
                "EA_MCP_BASE_URL": os.environ.get("EA_MCP_BASE_URL"),
                "EA_MCP_API_TOKEN": os.environ.get("EA_MCP_API_TOKEN"),
                "EA_MCP_PRINCIPAL_ID": os.environ.get("EA_MCP_PRINCIPAL_ID"),
            }
            try:
                os.environ["EA_MCP_BASE_URL"] = "http://ea-runtime.local"
                os.environ["EA_MCP_API_TOKEN"] = "ea-token"
                os.environ["EA_MCP_PRINCIPAL_ID"] = "fleet-studio"

                env = self.studio.prepare_account_environment(
                    "acct-ea-groundwork",
                    {
                        "auth_kind": "ea",
                        "allowed_models": ["ea-groundwork-gemini"],
                    },
                )
            finally:
                for key, value in prior.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value

        self.assertEqual(env["EA_MCP_BASE_URL"], "http://ea-runtime.local")
        self.assertEqual(env["EA_MCP_API_TOKEN"], "ea-token")
        self.assertEqual(env["EA_MCP_PRINCIPAL_ID"], "fleet-studio")
        self.assertEqual(env["CODEXEA_RUNTIME_EA_ENV_PATH"], "/docker/fleet/runtime.ea.env")

    def test_prepare_account_environment_fails_without_ea_runtime_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.configure_temp_studio(root)
            self.studio.init_db()
            prior = {
                "EA_MCP_BASE_URL": os.environ.get("EA_MCP_BASE_URL"),
                "EA_MCP_API_TOKEN": os.environ.get("EA_MCP_API_TOKEN"),
                "EA_MCP_PRINCIPAL_ID": os.environ.get("EA_MCP_PRINCIPAL_ID"),
            }
            try:
                os.environ["EA_MCP_BASE_URL"] = "http://ea-runtime.local"
                os.environ.pop("EA_MCP_API_TOKEN", None)
                os.environ["EA_MCP_PRINCIPAL_ID"] = "fleet-studio"

                with self.assertRaises(RuntimeError, msg="EA runtime token is not configured"):
                    self.studio.prepare_account_environment(
                        "acct-ea-groundwork",
                        {
                            "auth_kind": "ea",
                            "allowed_models": ["ea-groundwork-gemini"],
                        },
                    )
            finally:
                for key, value in prior.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value

    def test_pick_studio_account_and_model_can_use_ea_accounts_when_role_is_ea_backed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.configure_temp_studio(root)
            prior_ea_env = {
                "EA_MCP_BASE_URL": os.environ.get("EA_MCP_BASE_URL"),
                "EA_MCP_API_TOKEN": os.environ.get("EA_MCP_API_TOKEN"),
                "EA_MCP_PRINCIPAL_ID": os.environ.get("EA_MCP_PRINCIPAL_ID"),
            }
            self.studio.ACCOUNTS_PATH.write_text(
                (
                    "accounts:\n"
                    "  acct-studio-a:\n"
                    "    auth_kind: chatgpt_auth_json\n"
                    "    auth_json_file: /missing/stale-auth.json\n"
                    "    allowed_models: [gpt-5.3-codex]\n"
                    "  acct-ea-groundwork:\n"
                    "    auth_kind: ea\n"
                    "    allowed_models: [ea-groundwork-gemini]\n"
                ),
                encoding="utf-8",
            )
            os.environ["EA_MCP_BASE_URL"] = "http://ea-runtime.local"
            os.environ["EA_MCP_API_TOKEN"] = "ea-token"
            os.environ["EA_MCP_PRINCIPAL_ID"] = "fleet-studio"
            try:
                self.studio.init_db()
                config = self.studio.normalize_config()
                self.studio.sync_accounts_to_db(config)

                alias, model, note = self.studio.pick_studio_account_and_model(
                    config,
                    {"path": root.as_posix()},
                    "designer",
                    {
                        "accounts": ["acct-studio-a", "acct-ea-groundwork"],
                        "models": ["ea-groundwork-gemini", "gpt-5.3-codex"],
                    },
                )
            finally:
                for key, value in prior_ea_env.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value

        self.assertEqual(alias, "acct-ea-groundwork")
        self.assertEqual(model, "ea-groundwork-gemini")
        self.assertIn("acct-ea-groundwork", note)

    def test_pick_studio_account_and_model_respects_configured_account_priority_before_lru(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.configure_temp_studio(root)
            prior_ea_env = {
                "EA_MCP_BASE_URL": os.environ.get("EA_MCP_BASE_URL"),
                "EA_MCP_API_TOKEN": os.environ.get("EA_MCP_API_TOKEN"),
                "EA_MCP_PRINCIPAL_ID": os.environ.get("EA_MCP_PRINCIPAL_ID"),
            }
            self.studio.ACCOUNTS_PATH.write_text(
                (
                    "accounts:\n"
                    "  acct-ea-groundwork:\n"
                    "    auth_kind: ea\n"
                    "    allowed_models: [ea-groundwork-gemini]\n"
                    "  acct-ea-groundwork-2:\n"
                    "    auth_kind: ea\n"
                    "    allowed_models: [ea-groundwork-gemini]\n"
                ),
                encoding="utf-8",
            )
            os.environ["EA_MCP_BASE_URL"] = "http://ea-runtime.local"
            os.environ["EA_MCP_API_TOKEN"] = "ea-token"
            os.environ["EA_MCP_PRINCIPAL_ID"] = "fleet-studio"
            try:
                self.studio.init_db()
                config = self.studio.normalize_config()
                self.studio.sync_accounts_to_db(config)

                with self.studio.db() as conn:
                    conn.execute(
                        "UPDATE accounts SET last_used_at=? WHERE alias='acct-ea-groundwork'",
                        ("2026-03-25T12:00:00Z",),
                    )
                    conn.execute(
                        "UPDATE accounts SET last_used_at=? WHERE alias='acct-ea-groundwork-2'",
                        ("2026-03-24T12:00:00Z",),
                    )

                alias, model, _ = self.studio.pick_studio_account_and_model(
                    config,
                    {"path": root.as_posix()},
                    "designer",
                    {
                        "accounts": ["acct-ea-groundwork", "acct-ea-groundwork-2"],
                        "models": ["ea-groundwork-gemini"],
                    },
                )
            finally:
                for key, value in prior_ea_env.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value

        self.assertEqual(alias, "acct-ea-groundwork")
        self.assertEqual(model, "ea-groundwork-gemini")

    def test_pick_studio_account_and_model_skips_ea_without_runtime_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.configure_temp_studio(root)
            self.studio.ACCOUNTS_PATH.write_text(
                (
                    "accounts:\n"
                    "  acct-ea-fleet:\n"
                    "    auth_kind: ea\n"
                    "    allowed_models: [ea-gemini-flash]\n"
                    "  acct-studio-api:\n"
                    "    auth_kind: api_key\n"
                    "    api_key_env: OPENAI_API_KEY\n"
                    "    allowed_models: [gpt-5.3-codex]\n"
                ),
                encoding="utf-8",
            )
            os.environ.pop("EA_MCP_API_TOKEN", None)
            os.environ["OPENAI_API_KEY"] = "openai-token"
            try:
                self.studio.init_db()
                config = self.studio.normalize_config()
                self.studio.sync_accounts_to_db(config)

                alias, model, note = self.studio.pick_studio_account_and_model(
                    config,
                    {"path": root.as_posix()},
                    "designer",
                    {
                        "accounts": ["acct-ea-fleet", "acct-studio-api"],
                        "models": ["ea-gemini-flash", "gpt-5.3-codex"],
                    },
                )
            finally:
                os.environ.pop("OPENAI_API_KEY", None)

        self.assertEqual(alias, "acct-studio-api")
        self.assertEqual(model, "gpt-5.3-codex")
        self.assertIn("acct-studio-api", note)

    def test_sync_accounts_to_db_preserves_runtime_auth_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.configure_temp_studio(root)
            self.studio.ACCOUNTS_PATH.write_text(
                (
                    "accounts:\n"
                    "  acct-studio-a:\n"
                    "    auth_kind: api_key\n"
                    "    api_key_env: OPENAI_API_KEY\n"
                    "    allowed_models: [gpt-5.3-codex]\n"
                ),
                encoding="utf-8",
            )
            self.studio.init_db()
            self.studio.sync_accounts_to_db(self.studio.normalize_config())

            with self.studio.db() as conn:
                conn.execute(
                    "UPDATE accounts SET health_state='auth_stale', last_error='stale token' WHERE alias='acct-studio-a'"
                )

            self.studio.sync_accounts_to_db(self.studio.normalize_config())

            with self.studio.db() as conn:
                row = conn.execute("SELECT health_state FROM accounts WHERE alias='acct-studio-a'").fetchone()

        self.assertEqual(row["health_state"], "auth_stale")

    def test_maybe_queue_automated_sessions_creates_autonomous_sessions_and_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.configure_temp_studio(root)
            self.write_autonomy_trigger_files(root)
            self.studio.init_db()
            config = self.studio.normalize_config()

            self.studio.maybe_queue_automated_sessions(config)

            with self.studio.db() as conn:
                sessions = conn.execute(
                    "SELECT role, origin_type, status FROM studio_sessions ORDER BY id ASC"
                ).fetchall()
                states = conn.execute(
                    "SELECT role, last_status, trigger_fingerprint FROM studio_automation_state ORDER BY role ASC"
                ).fetchall()

        self.assertEqual([row["role"] for row in sessions], ["designer", "product_governor"])
        self.assertTrue(all(row["origin_type"] == "automation" for row in sessions))
        self.assertTrue(all(row["status"] == "queued" for row in sessions))
        self.assertEqual([row["role"] for row in states], ["designer", "product_governor"])
        self.assertTrue(all(row["last_status"] == "queued" for row in states))
        self.assertTrue(all(row["trigger_fingerprint"] for row in states))

    def test_group_autonomy_targets_include_member_project_signals(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_dir = root / "config"
            projects_dir = config_dir / "projects"
            projects_dir.mkdir(parents=True, exist_ok=True)
            fleet_repo = root / "fleet"
            ea_repo = root / "ea"
            fleet_repo.mkdir(parents=True, exist_ok=True)
            ea_repo.mkdir(parents=True, exist_ok=True)
            self.write_autonomy_trigger_files(fleet_repo)
            for repo_root, marker in {
                fleet_repo: "fleet design\n",
                ea_repo: "ea design\n",
            }.items():
                (repo_root / ".codex-design" / "product").mkdir(parents=True, exist_ok=True)
                (repo_root / ".codex-design" / "product" / "PRODUCT_GOVERNOR_AND_AUTOPILOT_LOOP.md").write_text(marker, encoding="utf-8")
                (repo_root / ".codex-design" / "product" / "FEEDBACK_AND_SIGNAL_OODA_LOOP.md").write_text(marker, encoding="utf-8")
            (config_dir / "policies.yaml").write_text("policies: {}\n", encoding="utf-8")
            (config_dir / "routing.yaml").write_text("spider: {}\n", encoding="utf-8")
            (config_dir / "accounts.yaml").write_text("accounts: {}\n", encoding="utf-8")
            (config_dir / "groups.yaml").write_text(
                "project_groups:\n"
                "  - id: control-plane\n"
                "    projects: [fleet, ea]\n",
                encoding="utf-8",
            )
            (config_dir / "fleet.yaml").write_text(
                (
                    "studio:\n"
                    "  autonomy:\n"
                    "    enabled: true\n"
                    "    roles:\n"
                    "      designer:\n"
                    "        enabled: true\n"
                    "        target_type: group\n"
                    "        target_id: control-plane\n"
                    "        interval_seconds: 1800\n"
                    "        min_interval_seconds: 60\n"
                    "      product_governor:\n"
                    "        enabled: true\n"
                    "        target_type: group\n"
                    "        target_id: control-plane\n"
                    "        interval_seconds: 600\n"
                    "        min_interval_seconds: 60\n"
                    "  roles:\n"
                    "    designer: {}\n"
                    "    product_governor: {}\n"
                ),
                encoding="utf-8",
            )
            (projects_dir / "fleet.yaml").write_text(
                "id: fleet\n"
                f"path: {fleet_repo.as_posix()}\n"
                "design_doc: ARCHITECTURE.md\n"
                "state_file: .agent-state.json\n",
                encoding="utf-8",
            )
            (projects_dir / "ea.yaml").write_text(
                "id: ea\n"
                f"path: {ea_repo.as_posix()}\n"
                "design_doc: ARCHITECTURE_MAP.md\n"
                "state_file: .agent-state.json\n"
                "queue_sources:\n"
                "  - kind: tasks_work_log\n"
                "    path: TASKS_WORK_LOG.md\n",
                encoding="utf-8",
            )
            (projects_dir / "_index.yaml").write_text("projects:\n  - fleet.yaml\n  - ea.yaml\n", encoding="utf-8")
            (fleet_repo / "ARCHITECTURE.md").write_text("# Fleet design\n", encoding="utf-8")
            (ea_repo / "ARCHITECTURE_MAP.md").write_text("# EA design\n", encoding="utf-8")
            (ea_repo / "TASKS_WORK_LOG.md").write_text("| id | task | task | owner | status |\n", encoding="utf-8")

            self.studio.CONFIG_PATH = config_dir / "fleet.yaml"
            self.studio.ACCOUNTS_PATH = config_dir / "accounts.yaml"
            self.studio.POLICIES_PATH = config_dir / "policies.yaml"
            self.studio.ROUTING_PATH = config_dir / "routing.yaml"
            self.studio.GROUPS_PATH = config_dir / "groups.yaml"
            self.studio.PROJECTS_DIR = projects_dir
            self.studio.PROJECT_INDEX_PATH = projects_dir / "_index.yaml"
            self.studio.DB_PATH = root / "state" / "fleet.db"
            self.studio.LOG_DIR = root / "state" / "logs"
            self.studio.CODEX_HOME_ROOT = root / "state" / "homes"
            self.studio.GROUP_ROOT = root / "state" / "groups"
            self.studio.init_db()

            config = self.studio.normalize_config()
            target_cfg = self.studio.resolve_target_cfg(config, "group", "control-plane")
            fingerprint, payload = self.studio.automation_trigger_fingerprint(target_cfg, "product_governor")
            context_files = self.studio.existing_context_files(target_cfg)
            self.studio.maybe_queue_automated_sessions(config)

            with self.studio.db() as conn:
                sessions = conn.execute(
                    "SELECT role, target_type, target_id FROM studio_sessions ORDER BY id ASC"
                ).fetchall()

        self.assertTrue(fingerprint)
        self.assertEqual([row["target_type"] for row in sessions], ["group", "group"])
        self.assertTrue(all(row["target_id"] == "control-plane" for row in sessions))
        member_projects = {str(item["project_id"]) for item in payload["member_projects"]}
        self.assertEqual(member_projects, {"fleet", "ea"})
        self.assertTrue(any("ARCHITECTURE_MAP.md" in item for item in context_files))
        self.assertTrue(any("TASKS_WORK_LOG.md" in item for item in context_files))

    def test_update_studio_automation_state_preserves_unspecified_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.configure_temp_studio(root)
            self.studio.init_db()

            self.studio.update_studio_automation_state(
                "designer",
                "fleet",
                "fleet",
                trigger_fingerprint="fp-1",
                last_session_id=11,
                last_run_at="2026-03-25T12:00:00Z",
                last_status="queued",
            )
            self.studio.update_studio_automation_state(
                "designer",
                "fleet",
                "fleet",
                last_status="awaiting_account",
                last_message="no account",
            )

            row = self.studio.studio_automation_state_row("designer", "fleet", "fleet")

        self.assertEqual(row["trigger_fingerprint"], "fp-1")
        self.assertEqual(row["last_session_id"], 11)
        self.assertEqual(row["last_run_at"], "2026-03-25T12:00:00Z")
        self.assertEqual(row["last_status"], "awaiting_account")
        self.assertEqual(row["last_message"], "no account")


if __name__ == "__main__":
    unittest.main()
