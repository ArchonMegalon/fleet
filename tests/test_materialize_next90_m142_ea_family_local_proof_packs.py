from __future__ import annotations

import importlib.util
import tempfile
import time
import unittest
from pathlib import Path


SCRIPT = Path("/docker/fleet/scripts/materialize_next90_m142_ea_family_local_proof_packs.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("materialize_next90_m142_ea_family_local_proof_packs", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LatestExistingPathTests(unittest.TestCase):
    def test_latest_existing_path_prefers_newest_match(self) -> None:
        module = _load_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            older = root / "shard-1" / "runs" / "older" / "TASK_LOCAL_TELEMETRY.generated.json"
            newer = root / "shard-2" / "runs" / "newer" / "TASK_LOCAL_TELEMETRY.generated.json"
            fallback = root / "fallback.json"

            older.parent.mkdir(parents=True, exist_ok=True)
            newer.parent.mkdir(parents=True, exist_ok=True)
            older.write_text("{}", encoding="utf-8")
            time.sleep(0.01)
            newer.write_text("{}", encoding="utf-8")

            module.SUPERVISOR_ROOT = root
            self.assertEqual(
                module._latest_existing_path("shard-*/runs/*/TASK_LOCAL_TELEMETRY.generated.json", fallback),
                newer,
            )

    def test_latest_existing_path_uses_fallback_when_no_match_exists(self) -> None:
        module = _load_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            fallback = root / "fallback.json"
            module.SUPERVISOR_ROOT = root
            self.assertEqual(
                module._latest_existing_path("shard-*/ACTIVE_RUN_HANDOFF.generated.md", fallback),
                fallback,
            )


if __name__ == "__main__":
    unittest.main()
