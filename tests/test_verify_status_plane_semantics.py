from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path
from unittest import mock

import yaml


MODULE_PATH = Path("/docker/fleet/scripts/verify_status_plane_semantics.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("verify_status_plane_semantics", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sample_admin_status() -> dict:
    return {
        "generated_at": "2026-03-23T07:21:00Z",
        "public_status": {
            "generated_at": "2026-03-23T07:21:00Z",
            "deployment_posture": {
                "display": "protected_preview",
                "status": "protected_preview",
            },
            "mission_snapshot": {
                "headline": "Truth -> Slice -> Review -> Land",
                "health": "watch",
            },
            "queue_forecast": {
                "now": {"title": "Compile status plane"},
                "next": {"title": "Materialize support packets"},
            },
            "capacity_forecast": {
                "overall": "steady",
            },
            "blocker_forecast": {
                "now": "none",
            },
            "readiness_summary": {
                "counts": {
                    "pre_repo_local_complete": 0,
                    "repo_local_complete": 1,
                    "package_canonical": 0,
                    "boundary_pure": 0,
                    "publicly_promoted": 0,
                },
                "warning_count": 0,
                "final_claim_ready": 0,
            },
            "dispatch_policy": {
                "participant_dispatch_canary_count": 1,
                "participant_dispatch_canaries": [
                    {
                        "project_id": "core",
                        "review_mode": "github",
                        "eligible_task_classes": ["bounded_fix", "multi_file_impl"],
                        "landing_lane": "jury",
                        "require_jury_before_land": True,
                        "participant_first_dispatch": True,
                    }
                ],
                "operator_only_projects": ["fleet"],
            },
            "support_summary": {
                "open_case_count": 2,
                "closure_waiting_on_release_truth": 1,
            },
            "publish_readiness": {
                "status": "watch",
                "reason": "Support queue still has one fix awaiting reporter verification.",
                "control_decision": {
                    "primary_lane": "support",
                    "target_repo": "chummer6-hub",
                    "change_class": "type_c",
                    "exit_condition": "Closure waiting on release truth returns to zero.",
                },
            },
            "runtime_healing": {
                "generated_at": "2026-03-23T07:21:00Z",
                "enabled": True,
                "summary": {
                    "alert_state": "healthy",
                    "degraded_service_count": 0,
                    "recent_restart_count": 0,
                },
                "services": [],
            },
        },
        "projects": [
            {
                "id": "fleet",
                "lifecycle": "live",
                "runtime_status": "running",
                "readiness": {
                    "stage": "repo_local_complete",
                    "terminal_stage": "publicly_promoted",
                    "final_claim_allowed": False,
                    "warning_count": 0,
                },
                "deployment": {
                    "status": "protected_preview",
                    "promotion_stage": "protected_preview",
                    "access_posture": "protected",
                },
            }
        ],
        "groups": [
            {
                "id": "solo-fleet",
                "lifecycle": "live",
                "phase": "delivery",
                "deployment": {
                    "status": "protected_preview",
                    "promotion_stage": "protected_preview",
                    "access_posture": "protected",
                },
                "deployment_readiness": {
                    "publicly_promoted": False,
                    "blocking_owner_projects": ["fleet"],
                },
            }
        ],
    }


def test_flagship_claim_status_uses_readiness_plane_gaps_when_coverage_is_green() -> None:
    module = _load_module()
    readiness_path = Path("/tmp/fleet-flagship-readiness.verify.json")
    readiness_path.write_text(
        json.dumps(
            {
                "status": "fail",
                "warning_keys": [],
                "flagship_readiness_audit": {"warning_coverage_keys": []},
                "coverage": {
                    "desktop_client": "ready",
                    "fleet_and_operator_loop": "ready",
                },
                "readiness_planes": {
                    "structural_ready": {"status": "missing"},
                    "flagship_ready": {"status": "warning"},
                    "veteran_ready": {"status": "ready"},
                },
                "quality_policy": {
                    "bar": "top_flagship_grade",
                    "whole_project_frontier_required": True,
                    "feedback_autofix_loop_required": True,
                    "accept_lowered_standards": False,
                },
            }
        ),
        encoding="utf-8",
    )
    try:
        with mock.patch.object(module, "FLAGSHIP_READINESS_PATH", readiness_path):
            claim = module._flagship_claim_status()
    finally:
        readiness_path.unlink(missing_ok=True)

    assert claim["status"] == "fail"
    assert claim["warning_keys"] == ["flagship_ready", "structural_ready"]


def test_ui_independent_public_release_proof_bundle_promotes_public_stage(tmp_path: Path) -> None:
    module = _load_module()
    published_dir = tmp_path / "ui" / ".codex-studio" / "published"
    published_dir.mkdir(parents=True, exist_ok=True)
    for name in (
        "UI_LOCAL_RELEASE_PROOF.generated.json",
        "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json",
        "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json",
        "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json",
    ):
        (published_dir / name).write_text(json.dumps({"status": "pass"}) + "\n", encoding="utf-8")
    (published_dir / "USER_JOURNEY_TESTER_AUDIT.generated.json").write_text(
        json.dumps({"status": "pass", "open_blocking_findings_count": 0}) + "\n",
        encoding="utf-8",
    )
    (published_dir / "CHUMMER5A_UI_ELEMENT_PARITY_AUDIT.generated.json").write_text(
        json.dumps({"summary": {"visual_no_count": 0, "behavioral_no_count": 0}}) + "\n",
        encoding="utf-8",
    )

    stage = module._infer_fallback_readiness_stage(
        "ui",
        tmp_path / "ui",
        lifecycle="live",
        deployment={"status": "public", "promotion_stage": "promoted_preview", "access_posture": "public"},
    )

    assert stage == "publicly_promoted"


def test_ui_independent_public_release_proof_bundle_requires_clean_user_journey_audit(tmp_path: Path) -> None:
    module = _load_module()
    published_dir = tmp_path / "ui" / ".codex-studio" / "published"
    published_dir.mkdir(parents=True, exist_ok=True)
    for name in (
        "UI_LOCAL_RELEASE_PROOF.generated.json",
        "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json",
        "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json",
        "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json",
    ):
        (published_dir / name).write_text(json.dumps({"status": "pass"}) + "\n", encoding="utf-8")
    (published_dir / "USER_JOURNEY_TESTER_AUDIT.generated.json").write_text(
        json.dumps({"status": "pass", "open_blocking_findings_count": 2}) + "\n",
        encoding="utf-8",
    )
    (published_dir / "CHUMMER5A_UI_ELEMENT_PARITY_AUDIT.generated.json").write_text(
        json.dumps({"summary": {"visual_no_count": 0, "behavioral_no_count": 0}}) + "\n",
        encoding="utf-8",
    )

    stage = module._infer_fallback_readiness_stage(
        "ui",
        tmp_path / "ui",
        lifecycle="live",
        deployment={"status": "public", "promotion_stage": "promoted_preview", "access_posture": "public"},
    )

    assert stage == "repo_local_complete"


def test_ui_independent_public_release_proof_bundle_accepts_aggregate_visual_proof_when_visual_receipt_is_stale(tmp_path: Path) -> None:
    module = _load_module()
    published_dir = tmp_path / "ui" / ".codex-studio" / "published"
    published_dir.mkdir(parents=True, exist_ok=True)
    (published_dir / "UI_LOCAL_RELEASE_PROOF.generated.json").write_text(
        json.dumps({"status": "pass"}) + "\n",
        encoding="utf-8",
    )
    (published_dir / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json").write_text(
        json.dumps(
            {
                "status": "pass",
                "local_blocking_findings_count": 0,
                "evidence": {"visual_familiarity_status": "pass"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (published_dir / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json").write_text(
        json.dumps({"status": "pass"}) + "\n",
        encoding="utf-8",
    )
    (published_dir / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json").write_text(
        json.dumps({"status": "fail", "reasons": ["stale screenshots"]}) + "\n",
        encoding="utf-8",
    )
    (published_dir / "USER_JOURNEY_TESTER_AUDIT.generated.json").write_text(
        json.dumps({"status": "pass", "open_blocking_findings_count": 0}) + "\n",
        encoding="utf-8",
    )
    (published_dir / "CHUMMER5A_UI_ELEMENT_PARITY_AUDIT.generated.json").write_text(
        json.dumps({"summary": {"visual_no_count": 0, "behavioral_no_count": 0}}) + "\n",
        encoding="utf-8",
    )

    stage = module._infer_fallback_readiness_stage(
        "ui",
        tmp_path / "ui",
        lifecycle="live",
        deployment={"status": "public", "promotion_stage": "promoted_preview", "access_posture": "public"},
    )

    assert stage == "publicly_promoted"


def test_core_fallback_stage_requires_engine_proof_pack(monkeypatch, tmp_path: Path) -> None:
    module = _load_module()
    config_dir = tmp_path / "config" / "projects"
    published_dir = tmp_path / "core" / ".codex-studio" / "published"
    config_dir.mkdir(parents=True, exist_ok=True)
    published_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "core.yaml").write_text(
        f"""
id: core
enabled: true
lifecycle: live
path: {tmp_path / "core"}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (published_dir / "IMPORT_PARITY_CERTIFICATION.generated.json").write_text(
        json.dumps({"status": "passed"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "PROJECT_CONFIG_DIR", config_dir)

    rows = module._load_project_config_rows()
    assert len(rows) == 1
    assert rows[0]["id"] == "core"
    assert rows[0]["readiness"]["stage"] == "repo_local_complete"


def test_core_fallback_stage_uses_import_parity_and_engine_proof(monkeypatch, tmp_path: Path) -> None:
    module = _load_module()
    config_dir = tmp_path / "config" / "projects"
    published_dir = tmp_path / "core" / ".codex-studio" / "published"
    config_dir.mkdir(parents=True, exist_ok=True)
    published_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "core.yaml").write_text(
        f"""
id: core
enabled: true
lifecycle: live
path: {tmp_path / "core"}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (published_dir / "IMPORT_PARITY_CERTIFICATION.generated.json").write_text(
        json.dumps({"status": "passed"}) + "\n",
        encoding="utf-8",
    )
    (published_dir / "ENGINE_PROOF_PACK.generated.json").write_text(
        json.dumps({"status": "passed"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "PROJECT_CONFIG_DIR", config_dir)

    rows = module._load_project_config_rows()
    assert len(rows) == 1
    assert rows[0]["id"] == "core"
    assert rows[0]["readiness"]["stage"] == "boundary_pure"


def test_fleet_fallback_stage_stays_package_without_dispatchable_truth(monkeypatch, tmp_path: Path) -> None:
    module = _load_module()
    config_dir = tmp_path / "config" / "projects"
    project_root = tmp_path / "fleet"
    published_dir = project_root / ".codex-studio" / "published"
    config_dir.mkdir(parents=True, exist_ok=True)
    published_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "fleet.yaml").write_text(
        f"""
id: fleet
enabled: true
lifecycle: live
path: {project_root}
design_doc: {project_root / "README.md"}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (project_root / "README.md").write_text("# Fleet\n", encoding="utf-8")
    (published_dir / "compile.manifest.json").write_text(
        json.dumps(
            {
                "dispatchable_truth_ready": False,
                "artifacts": [
                    "STATUS_PLANE.generated.yaml",
                    "PROGRESS_REPORT.generated.json",
                    "PROGRESS_HISTORY.generated.json",
                    "SUPPORT_CASE_PACKETS.generated.json",
                    "JOURNEY_GATES.generated.json",
                ],
                "stages": {
                    "design_compile": True,
                    "policy_compile": True,
                    "execution_compile": True,
                    "package_compile": True,
                    "capacity_compile": True,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (published_dir / "SUPPORT_CASE_PACKETS.generated.json").write_text(
        json.dumps(
            {
                "contract_name": "fleet.support_case_packets",
                "schema_version": 1,
                "generated_at": "2026-04-04T18:30:00Z",
                "summary": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "PROJECT_CONFIG_DIR", config_dir)

    rows = module._load_project_config_rows()
    assert len(rows) == 1
    assert rows[0]["id"] == "fleet"
    assert rows[0]["readiness"]["stage"] == "package_canonical"


class VerifyStatusPlaneSemanticsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.verify = _load_module()

    def _normalized_admin_status(self, admin_status: dict) -> dict:
        return self.verify._ensure_project_inventory(copy.deepcopy(admin_status))

    def test_verify_status_plane_passes_when_semantics_match(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            admin_status = self._normalized_admin_status(_sample_admin_status())
            status_plane = self.verify.build_expected_status_plane(admin_status)
            status_plane_path = tmp_path / "STATUS_PLANE.generated.yaml"
            status_plane_path.write_text(yaml.safe_dump(status_plane, sort_keys=False), encoding="utf-8")
            status_json_path = tmp_path / "status.json"
            status_json_path.write_text(json.dumps(admin_status), encoding="utf-8")

            self.verify.run_verification(status_plane_path=status_plane_path, status_json_path=status_json_path)

            self.assertEqual(status_plane["dispatch_policy"]["participant_dispatch_canary_count"], 1)
            self.assertEqual(status_plane["dispatch_policy"]["participant_dispatch_canaries"][0]["project_id"], "core")
            self.assertEqual(status_plane["publish_readiness"]["status"], "watch")
            self.assertEqual(status_plane["support_summary"]["open_case_count"], 2)
            self.assertEqual(status_plane["mission_snapshot"]["headline"], "Truth -> Slice -> Review -> Land")

    def test_verify_status_plane_fails_when_readiness_stage_drifts(self) -> None:
        with self.subTest("drifted readiness"):
            from tempfile import TemporaryDirectory

            with TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                admin_status = self._normalized_admin_status(_sample_admin_status())
                expected = self.verify.build_expected_status_plane(admin_status)
                drifted = copy.deepcopy(expected)
                fleet_project = next(
                    row for row in drifted["projects"] if isinstance(row, dict) and row.get("id") == "fleet"
                )
                fleet_project["readiness_stage"] = "stage_drifted_for_test"
                status_plane_path = tmp_path / "STATUS_PLANE.generated.yaml"
                status_plane_path.write_text(yaml.safe_dump(drifted, sort_keys=False), encoding="utf-8")
                status_json_path = tmp_path / "status.json"
                status_json_path.write_text(json.dumps(admin_status), encoding="utf-8")

                with self.assertRaises(self.verify.StatusPlaneDriftError) as exc:
                    self.verify.run_verification(status_plane_path=status_plane_path, status_json_path=status_json_path)

                self.assertIn("mismatch at projects", str(exc.exception))

    def test_verify_status_plane_fails_when_artifact_missing(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            status_json_path = tmp_path / "status.json"
            status_json_path.write_text(json.dumps(_sample_admin_status()), encoding="utf-8")

            with self.assertRaises(self.verify.StatusPlaneDriftError) as exc:
                self.verify.run_verification(
                    status_plane_path=tmp_path / "STATUS_PLANE.generated.yaml",
                    status_json_path=status_json_path,
                )

            self.assertIn("status-plane artifact is missing", str(exc.exception))

    def test_verify_status_plane_ignores_generation_timestamp_churn(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            admin_status = self._normalized_admin_status(_sample_admin_status())
            expected = self.verify.build_expected_status_plane(admin_status)
            drifted = copy.deepcopy(expected)
            drifted["generated_at"] = "2026-03-23T07:20:00Z"
            drifted["source_public_status_generated_at"] = "2026-03-23T07:20:30Z"
            status_plane_path = tmp_path / "STATUS_PLANE.generated.yaml"
            status_plane_path.write_text(yaml.safe_dump(drifted, sort_keys=False), encoding="utf-8")
            status_json_path = tmp_path / "status.json"
            status_json_path.write_text(json.dumps(admin_status), encoding="utf-8")

            self.verify.run_verification(status_plane_path=status_plane_path, status_json_path=status_json_path)

    def test_verify_status_plane_ignores_external_proof_cooldown_countdown_churn(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            admin_status = self._normalized_admin_status(_sample_admin_status())
            admin_status["public_status"]["external_proof_autoingest"] = {
                "generated_at": "2026-05-01T09:23:15Z",
                "enabled": True,
                "current_state": "cooldown",
                "commands_dir": "/docker/fleet/.codex-studio/published/external-proof-commands",
                "observed_bundle_count": 3,
                "last_attempt_at": "2026-05-01T09:22:44Z",
                "last_success_at": "",
                "last_result": "cooldown",
                "last_detail": "waiting 89s before retrying host proof bundle ingest",
                "summary": {
                    "alert_state": "tracking",
                    "alert_reason": "waiting 89s before retrying host proof bundle ingest",
                    "recommended_action": "Wait for the retry window or inspect the last failure detail.",
                },
            }
            status_plane = self.verify.build_expected_status_plane(admin_status)
            status_plane["external_proof_autoingest"] = copy.deepcopy(admin_status["public_status"]["external_proof_autoingest"])
            status_plane_path = tmp_path / "STATUS_PLANE.generated.yaml"
            status_plane_path.write_text(yaml.safe_dump(status_plane, sort_keys=False), encoding="utf-8")
            status_json_path = tmp_path / "status.json"
            status_json_path.write_text(json.dumps(admin_status), encoding="utf-8")

            local_cooldown = {
                "generated_at": "2026-05-01T09:24:15Z",
                "enabled": True,
                "current_state": "cooldown",
                "commands_dir": "/docker/fleet/.codex-studio/published/external-proof-commands",
                "observed_bundle_count": 3,
                "last_attempt_at": "2026-05-01T09:22:44Z",
                "last_success_at": "",
                "last_result": "cooldown",
                "last_detail": "waiting 28s before retrying host proof bundle ingest",
                "summary": {
                    "alert_state": "tracking",
                    "alert_reason": "waiting 28s before retrying host proof bundle ingest",
                    "recommended_action": "Wait for the retry window or inspect the last failure detail.",
                },
            }

            with mock.patch.object(self.verify, "_external_proof_autoingest_from_state", return_value=local_cooldown):
                self.verify.run_verification(status_plane_path=status_plane_path, status_json_path=status_json_path)

    def test_verify_status_plane_normalizes_waiting_capacity_to_dispatch_pending(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            admin_status = self._normalized_admin_status(_sample_admin_status())
            admin_status["projects"][0]["runtime_status"] = "waiting_capacity"
            expected = self.verify.build_expected_status_plane(admin_status)
            self.assertEqual(expected["projects"][0]["runtime_status"], "dispatch_pending")
            status_plane_path = tmp_path / "STATUS_PLANE.generated.yaml"
            status_plane_path.write_text(yaml.safe_dump(expected, sort_keys=False), encoding="utf-8")
            status_json_path = tmp_path / "status.json"
            status_json_path.write_text(json.dumps(admin_status), encoding="utf-8")

            self.verify.run_verification(status_plane_path=status_plane_path, status_json_path=status_json_path)

    def test_verify_status_plane_normalizes_review_fix_to_dispatch_pending(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            admin_status = self._normalized_admin_status(_sample_admin_status())
            admin_status["projects"][0]["runtime_status"] = "review_fix"
            expected = self.verify.build_expected_status_plane(admin_status)
            self.assertEqual(expected["projects"][0]["runtime_status"], "dispatch_pending")
            status_plane_path = tmp_path / "STATUS_PLANE.generated.yaml"
            status_plane_path.write_text(yaml.safe_dump(expected, sort_keys=False), encoding="utf-8")
            status_json_path = tmp_path / "status.json"
            status_json_path.write_text(json.dumps(admin_status), encoding="utf-8")

            self.verify.run_verification(status_plane_path=status_plane_path, status_json_path=status_json_path)

    def test_verify_status_plane_normalizes_local_review_to_dispatch_pending(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            admin_status = self._normalized_admin_status(_sample_admin_status())
            admin_status["projects"][0]["runtime_status"] = "local_review"
            expected = self.verify.build_expected_status_plane(admin_status)
            self.assertEqual(expected["projects"][0]["runtime_status"], "dispatch_pending")
            status_plane_path = tmp_path / "STATUS_PLANE.generated.yaml"
            status_plane_path.write_text(yaml.safe_dump(expected, sort_keys=False), encoding="utf-8")
            status_json_path = tmp_path / "status.json"
            status_json_path.write_text(json.dumps(admin_status), encoding="utf-8")

            self.verify.run_verification(status_plane_path=status_plane_path, status_json_path=status_json_path)

    def test_load_admin_status_uses_default_snapshot_when_present(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            snapshot_path = tmp_path / "status-plane.verify.json"
            admin_status = _sample_admin_status()
            snapshot_path.write_text(json.dumps(admin_status), encoding="utf-8")

            original_snapshot_path = self.verify.DEFAULT_STATUS_JSON_SNAPSHOT_PATH
            try:
                self.verify.DEFAULT_STATUS_JSON_SNAPSHOT_PATH = snapshot_path
                loaded = self.verify.load_admin_status(None)
            finally:
                self.verify.DEFAULT_STATUS_JSON_SNAPSHOT_PATH = original_snapshot_path

            self.assertEqual(loaded["projects"][0]["id"], "fleet")

    def test_load_admin_status_can_skip_default_snapshot_and_use_live_fetch(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            snapshot_path = tmp_path / "status-plane.verify.json"
            snapshot_path.write_text(json.dumps({"projects": [{"id": "stale"}]}), encoding="utf-8")

            original_snapshot_path = self.verify.DEFAULT_STATUS_JSON_SNAPSHOT_PATH
            try:
                self.verify.DEFAULT_STATUS_JSON_SNAPSHOT_PATH = snapshot_path
                live_payload = _sample_admin_status()
                completed = mock.Mock(returncode=0, stdout=json.dumps(live_payload), stderr="")
                with mock.patch.object(self.verify.subprocess, "run", return_value=completed):
                    loaded = self.verify.load_admin_status(None, use_default_snapshot=False)
            finally:
                self.verify.DEFAULT_STATUS_JSON_SNAPSHOT_PATH = original_snapshot_path

            self.assertEqual(loaded["projects"][0]["id"], "fleet")

    def test_build_expected_status_plane_preserves_promoted_preview_public_access(self) -> None:
        admin_status = _sample_admin_status()
        admin_status["projects"][0]["readiness"]["stage"] = "publicly_promoted"
        admin_status["projects"][0]["readiness"]["final_claim_allowed"] = True
        admin_status["projects"][0]["deployment"] = {
            "status": "public",
            "promotion_stage": "promoted_preview",
            "access_posture": "public",
        }
        admin_status["groups"][0]["deployment"] = {
            "status": "public",
            "promotion_stage": "promoted_preview",
            "access_posture": "public",
        }
        admin_status["groups"][0]["deployment_readiness"] = {
            "publicly_promoted": True,
            "blocking_owner_projects": [],
        }

        expected = self.verify.build_expected_status_plane(admin_status)

        self.assertEqual(expected["projects"][0]["readiness_stage"], "publicly_promoted")
        self.assertEqual(expected["projects"][0]["deployment_status"], "public")
        self.assertEqual(expected["projects"][0]["deployment_promotion_stage"], "promoted_preview")
        self.assertEqual(expected["projects"][0]["deployment_access_posture"], "public")
        self.assertEqual(expected["groups"][0]["deployment_status"], "public")
        self.assertEqual(expected["groups"][0]["deployment_promotion_stage"], "promoted_preview")
        self.assertEqual(expected["groups"][0]["deployment_access_posture"], "public")


if __name__ == "__main__":
    unittest.main()
