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

        lane = consistency.infer_account_lane({"codex_model_aliases": ["ea-groundwork"]}, alias="acct-ea-groundwork")

        self.assertEqual(lane, "groundwork")

    def test_normalize_task_queue_item_adds_authority_defaults(self) -> None:
        consistency = load_consistency_module()

        item = consistency.normalize_task_queue_item({"title": "Draft product backlog packet"}, lanes=consistency.DEFAULT_LANES)

        self.assertEqual(item["dispatchability_state"], "dispatchable")
        self.assertFalse(item["design_sensitive"])
        self.assertFalse(item["architecture_sensitive"])
        self.assertFalse(item["groundwork_required"])
        self.assertFalse(item["jury_required"])
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


if __name__ == "__main__":
    unittest.main()
