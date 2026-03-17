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


if __name__ == "__main__":
    unittest.main()
