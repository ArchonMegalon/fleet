from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path("/docker/fleet/admin/consistency.py")


def load_consistency_module():
    spec = importlib.util.spec_from_file_location("test_consistency_groundwork", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ConsistencyGroundworkTests(unittest.TestCase):
    def test_infer_account_lane_recognizes_groundwork_alias(self) -> None:
        consistency = load_consistency_module()

        lane = consistency.infer_account_lane({"codex_model_aliases": ["ea-groundwork-gemini"]}, alias="acct-ea-groundwork")

        self.assertEqual(lane, "groundwork")

    def test_infer_account_lane_recognizes_review_light_alias(self) -> None:
        consistency = load_consistency_module()

        lane = consistency.infer_account_lane({"codex_model_aliases": ["ea-review-light"]}, alias="acct-ea-review-light")

        self.assertEqual(lane, "review_light")

    def test_normalize_task_queue_item_adds_authority_defaults(self) -> None:
        consistency = load_consistency_module()

        item = consistency.normalize_task_queue_item({"title": "Draft product backlog packet"}, lanes=consistency.DEFAULT_LANES)

        self.assertEqual(item["dispatchability_state"], "dispatchable")
        self.assertFalse(item["design_sensitive"])
        self.assertFalse(item["architecture_sensitive"])
        self.assertFalse(item["groundwork_required"])
        self.assertFalse(item["jury_required"])
        self.assertEqual(item["workflow_kind"], "default")
        self.assertEqual(item["max_review_rounds"], 0)
        self.assertFalse(item["first_review_required"])
        self.assertFalse(item["jury_acceptance_required"])
        self.assertTrue(item["allow_credit_burn"])
        self.assertTrue(item["allow_paid_fast_lane"])
        self.assertFalse(item["allow_core_rescue"])
        self.assertEqual(item["core_rescue_after_round"], 0)
        self.assertEqual(item["landing_lane"], "core")
        self.assertFalse(item["operator_override_required"])
        self.assertFalse(item["protected_runtime"])
        self.assertEqual(item["signoff_requirements"], [])
        self.assertEqual(item["publish_truth_sources"], [])

    def test_protected_runtime_forces_core_and_operator_signoff(self) -> None:
        consistency = load_consistency_module()

        item = consistency.normalize_task_queue_item(
            {
                "title": "Rotate runtime credentials for the bridge worker",
                "design_sensitive": True,
                "protected_runtime": True,
                "publish_truth_sources": ["VISION.md", "ARCHITECTURE.md"],
            },
            lanes=consistency.DEFAULT_LANES,
        )

        self.assertEqual(item["allowed_lanes"], ["core"])
        self.assertTrue(item["operator_override_required"])
        self.assertEqual(item["required_reviewer_lane"], "core")
        self.assertEqual(item["publish_truth_sources"], ["VISION.md", "ARCHITECTURE.md"])
        self.assertIn("design_review", item["signoff_requirements"])
        self.assertIn("operator_signoff", item["signoff_requirements"])

    def test_groundwork_required_promotes_groundwork_lane(self) -> None:
        consistency = load_consistency_module()

        item = consistency.normalize_task_queue_item(
            {"title": "Architecture tradeoff review", "groundwork_required": True},
            lanes=consistency.DEFAULT_LANES,
        )

        self.assertEqual(item["allowed_lanes"][0], "groundwork")

    def test_review_light_is_valid_reviewer_lane(self) -> None:
        consistency = load_consistency_module()

        item = consistency.normalize_task_queue_item(
            {"title": "Summarize dashboard polish", "required_reviewer_lane": "review_light"},
            lanes=consistency.DEFAULT_LANES,
        )

        self.assertEqual(item["required_reviewer_lane"], "review_light")

    def test_jury_is_default_merge_authority_lane(self) -> None:
        consistency = load_consistency_module()

        self.assertEqual(consistency.DEFAULT_LANES["core"]["authority"], "run")
        self.assertFalse(consistency.DEFAULT_LANES["core"]["merge_protected_branches"])
        self.assertEqual(consistency.DEFAULT_LANES["jury"]["authority"], "approve_merge")
        self.assertTrue(consistency.DEFAULT_LANES["jury"]["merge_protected_branches"])

    def test_groundwork_review_loop_uses_review_light_then_jury_defaults(self) -> None:
        consistency = load_consistency_module()

        item = consistency.normalize_task_queue_item(
            {"title": "run the cheap loop", "workflow_kind": "groundwork_review_loop"},
            lanes=consistency.DEFAULT_LANES,
        )

        self.assertEqual(item["workflow_kind"], "groundwork_review_loop")
        self.assertTrue(item["groundwork_required"])
        self.assertTrue(item["jury_required"])
        self.assertEqual(item["required_reviewer_lane"], "review_light")
        self.assertEqual(item["final_reviewer_lane"], "jury")
        self.assertEqual(item["landing_lane"], "jury")
        self.assertEqual(item["allowed_lanes"], ["groundwork", "easy"])
        self.assertEqual(item["max_review_rounds"], 3)
        self.assertTrue(item["first_review_required"])
        self.assertTrue(item["jury_acceptance_required"])
        self.assertFalse(item["allow_credit_burn"])
        self.assertFalse(item["allow_paid_fast_lane"])
        self.assertFalse(item["allow_core_rescue"])
        self.assertEqual(item["core_rescue_after_round"], 0)

    def test_groundwork_review_loop_allows_paid_opt_in_when_explicit(self) -> None:
        consistency = load_consistency_module()

        item = consistency.normalize_task_queue_item(
            {
                "title": "allow explicit core rescue",
                "workflow_kind": "groundwork_review_loop",
                "allowed_lanes": ["groundwork", "easy", "repair", "core"],
                "allow_credit_burn": True,
                "allow_paid_fast_lane": True,
                "allow_core_rescue": True,
                "core_rescue_after_round": 3,
            },
            lanes=consistency.DEFAULT_LANES,
        )

        self.assertEqual(item["allowed_lanes"], ["groundwork", "easy", "repair", "core"])
        self.assertTrue(item["allow_credit_burn"])
        self.assertTrue(item["allow_paid_fast_lane"])
        self.assertTrue(item["allow_core_rescue"])
        self.assertEqual(item["core_rescue_after_round"], 3)

    def test_groundwork_review_loop_preserves_runtime_state_fields(self) -> None:
        consistency = load_consistency_module()

        item = consistency.normalize_task_queue_item(
            {
                "title": "rework the cheap loop",
                "workflow_kind": "groundwork_review_loop",
                "review_round": 2,
                "first_review_complete": True,
                "accepted_on_round": "core",
                "needs_core_rescue": True,
                "core_rescue_reason": "jury escalation requested",
                "jury_feedback_history": [{"review_round": 1, "verdict": "rework"}],
                "issue_fingerprints": ["ISSUE-1", "ISSUE-2"],
            },
            lanes=consistency.DEFAULT_LANES,
        )

        self.assertEqual(item["review_round"], 2)
        self.assertTrue(item["first_review_complete"])
        self.assertEqual(item["accepted_on_round"], "core")
        self.assertTrue(item["needs_core_rescue"])
        self.assertEqual(item["core_rescue_reason"], "jury escalation requested")
        self.assertEqual(item["jury_feedback_history"], [{"review_round": 1, "verdict": "rework"}])
        self.assertEqual(item["issue_fingerprints"], ["ISSUE-1", "ISSUE-2"])

    def test_local_review_config_warns_when_reviewer_lane_has_no_backing_account(self) -> None:
        consistency = load_consistency_module()

        warnings = consistency.config_consistency_warnings(
            {
                "lanes": consistency.DEFAULT_LANES,
                "accounts": {
                    "acct-ea-groundwork": {"lane": "groundwork", "codex_model_aliases": ["ea-groundwork-gemini"]},
                    "acct-ea-jury": {"lane": "jury", "codex_model_aliases": ["ea-audit-jury"]},
                },
                "projects": [
                    {
                        "id": "fleet",
                        "accounts": ["acct-ea-groundwork", "acct-ea-jury"],
                        "review": {"enabled": True, "mode": "local", "required_before_queue_advance": True},
                        "queue": [{"title": "cheap loop", "workflow_kind": "groundwork_review_loop"}],
                    }
                ],
            }
        )

        self.assertTrue(any(item["kind"] == "unserved_reviewer_lane" and item["scope_id"] == "fleet" for item in warnings))


if __name__ == "__main__":
    unittest.main()
