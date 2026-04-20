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
