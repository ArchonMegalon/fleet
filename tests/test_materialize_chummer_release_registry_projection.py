from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path("/docker/fleet/scripts/materialize_chummer_release_registry_projection.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("materialize_chummer_release_registry_projection", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MaterializeReleaseRegistryProjectionTests(unittest.TestCase):
    def test_resolve_startup_smoke_dir_falls_back_to_first_receipt_dir(self) -> None:
        module = _load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing_primary = module.DEFAULT_STARTUP_SMOKE_DIR
            fallback = root / "ui-startup-smoke"
            fallback.mkdir(parents=True, exist_ok=True)
            (fallback / "startup-smoke-avalonia-linux-x64.receipt.json").write_text(
                '{"status":"pass","readyCheckpoint":"pre_ui_event_loop","headId":"avalonia","platform":"linux","arch":"x64","recordedAtUtc":"2026-04-03T18:00:00Z"}',
                encoding="utf-8",
            )

            resolved = module.resolve_startup_smoke_dir(
                missing_primary,
                fallback_dirs=(missing_primary, fallback),
            )
            self.assertEqual(resolved, fallback)

    def test_resolve_startup_smoke_dir_skips_stale_receipts_for_fresh_fallback(self) -> None:
        module = _load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stale = root / "stale-startup-smoke"
            fresh = root / "fresh-startup-smoke"
            stale.mkdir(parents=True, exist_ok=True)
            fresh.mkdir(parents=True, exist_ok=True)
            (stale / "startup-smoke-avalonia-linux-x64.receipt.json").write_text(
                '{"status":"pass","readyCheckpoint":"pre_ui_event_loop","headId":"avalonia","platform":"linux","arch":"x64","recordedAtUtc":"2026-03-01T00:00:00Z"}',
                encoding="utf-8",
            )
            (fresh / "startup-smoke-avalonia-linux-x64.receipt.json").write_text(
                '{"status":"pass","readyCheckpoint":"pre_ui_event_loop","headId":"avalonia","platform":"linux","arch":"x64","recordedAtUtc":"2026-04-03T18:00:00Z"}',
                encoding="utf-8",
            )

            resolved = module.resolve_startup_smoke_dir(
                module.DEFAULT_STARTUP_SMOKE_DIR,
                fallback_dirs=(stale, fresh),
            )
            self.assertEqual(resolved, fresh)

    def test_resolve_startup_smoke_dir_respects_explicit_nondefault_path(self) -> None:
        module = _load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            explicit_missing = root / "explicit-startup-smoke"
            fallback = root / "fallback-startup-smoke"
            fallback.mkdir(parents=True, exist_ok=True)
            (fallback / "startup-smoke-avalonia-linux-x64.receipt.json").write_text(
                '{"status":"pass","readyCheckpoint":"pre_ui_event_loop","headId":"avalonia","platform":"linux","arch":"x64","recordedAtUtc":"2026-04-03T18:00:00Z"}',
                encoding="utf-8",
            )

            resolved = module.resolve_startup_smoke_dir(
                explicit_missing,
                fallback_dirs=(fallback,),
            )
            self.assertIsNone(resolved)

    def test_resolve_startup_smoke_dir_ignores_wrong_ready_checkpoint(self) -> None:
        module = _load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wrong_checkpoint = root / "wrong-startup-smoke"
            correct_checkpoint = root / "correct-startup-smoke"
            wrong_checkpoint.mkdir(parents=True, exist_ok=True)
            correct_checkpoint.mkdir(parents=True, exist_ok=True)
            (wrong_checkpoint / "startup-smoke-avalonia-linux-x64.receipt.json").write_text(
                '{"status":"pass","readyCheckpoint":"before_ui","headId":"avalonia","platform":"linux","arch":"x64","recordedAtUtc":"2026-04-03T18:00:00Z"}',
                encoding="utf-8",
            )
            (correct_checkpoint / "startup-smoke-avalonia-linux-x64.receipt.json").write_text(
                '{"status":"pass","readyCheckpoint":"pre_ui_event_loop","headId":"avalonia","platform":"linux","arch":"x64","recordedAtUtc":"2026-04-03T18:00:00Z"}',
                encoding="utf-8",
            )

            resolved = module.resolve_startup_smoke_dir(
                module.DEFAULT_STARTUP_SMOKE_DIR,
                fallback_dirs=(wrong_checkpoint, correct_checkpoint),
            )
            self.assertEqual(resolved, correct_checkpoint)


if __name__ == "__main__":
    unittest.main()
