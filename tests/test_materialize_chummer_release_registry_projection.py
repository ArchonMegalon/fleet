from __future__ import annotations

import datetime as dt
import importlib.util
import json
import sys
import tempfile
import unittest
from unittest import mock
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
    @staticmethod
    def _receipt_json(*, recorded_at_utc: str, ready_checkpoint: str = "pre_ui_event_loop") -> str:
        return json.dumps(
            {
                "status": "pass",
                "readyCheckpoint": ready_checkpoint,
                "headId": "avalonia",
                "platform": "linux",
                "arch": "x64",
                "recordedAtUtc": recorded_at_utc,
            }
        )

    @staticmethod
    def _utc_iso(hours_ago: int) -> str:
        value = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours_ago)
        return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def test_resolve_startup_smoke_dir_falls_back_to_first_receipt_dir(self) -> None:
        module = _load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing_primary = root / "missing-startup-smoke"
            fallback = root / "ui-startup-smoke"
            fallback.mkdir(parents=True, exist_ok=True)
            (fallback / "startup-smoke-avalonia-linux-x64.receipt.json").write_text(
                self._receipt_json(recorded_at_utc=self._utc_iso(hours_ago=1)),
                encoding="utf-8",
            )

            with mock.patch.object(module, "DEFAULT_STARTUP_SMOKE_DIR", missing_primary):
                resolved = module.resolve_startup_smoke_dir(
                    missing_primary,
                    fallback_dirs=(missing_primary, fallback),
                )
            self.assertEqual(resolved, fallback)

    def test_resolve_startup_smoke_dir_skips_stale_receipts_for_fresh_fallback(self) -> None:
        module = _load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing_primary = root / "missing-startup-smoke"
            stale = root / "stale-startup-smoke"
            fresh = root / "fresh-startup-smoke"
            stale.mkdir(parents=True, exist_ok=True)
            fresh.mkdir(parents=True, exist_ok=True)
            (stale / "startup-smoke-avalonia-linux-x64.receipt.json").write_text(
                self._receipt_json(
                    recorded_at_utc=self._utc_iso(
                        hours_ago=(module.STARTUP_SMOKE_MAX_AGE_SECONDS // 3600) + 1
                    )
                ),
                encoding="utf-8",
            )
            (fresh / "startup-smoke-avalonia-linux-x64.receipt.json").write_text(
                self._receipt_json(recorded_at_utc=self._utc_iso(hours_ago=1)),
                encoding="utf-8",
            )

            with mock.patch.object(module, "DEFAULT_STARTUP_SMOKE_DIR", missing_primary):
                resolved = module.resolve_startup_smoke_dir(
                    missing_primary,
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
                self._receipt_json(recorded_at_utc=self._utc_iso(hours_ago=1)),
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
            missing_primary = root / "missing-startup-smoke"
            wrong_checkpoint = root / "wrong-startup-smoke"
            correct_checkpoint = root / "correct-startup-smoke"
            wrong_checkpoint.mkdir(parents=True, exist_ok=True)
            correct_checkpoint.mkdir(parents=True, exist_ok=True)
            (wrong_checkpoint / "startup-smoke-avalonia-linux-x64.receipt.json").write_text(
                self._receipt_json(recorded_at_utc=self._utc_iso(hours_ago=1), ready_checkpoint="before_ui"),
                encoding="utf-8",
            )
            (correct_checkpoint / "startup-smoke-avalonia-linux-x64.receipt.json").write_text(
                self._receipt_json(recorded_at_utc=self._utc_iso(hours_ago=1)),
                encoding="utf-8",
            )

            with mock.patch.object(module, "DEFAULT_STARTUP_SMOKE_DIR", missing_primary):
                resolved = module.resolve_startup_smoke_dir(
                    missing_primary,
                    fallback_dirs=(wrong_checkpoint, correct_checkpoint),
                )
            self.assertEqual(resolved, correct_checkpoint)

    def test_resolve_startup_smoke_dir_ignores_future_dated_receipts(self) -> None:
        module = _load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing_primary = root / "missing-startup-smoke"
            future = root / "future-startup-smoke"
            fresh = root / "fresh-startup-smoke"
            future.mkdir(parents=True, exist_ok=True)
            fresh.mkdir(parents=True, exist_ok=True)
            (future / "startup-smoke-avalonia-linux-x64.receipt.json").write_text(
                self._receipt_json(recorded_at_utc="2999-01-01T00:00:00Z"),
                encoding="utf-8",
            )
            (fresh / "startup-smoke-avalonia-linux-x64.receipt.json").write_text(
                self._receipt_json(recorded_at_utc=self._utc_iso(hours_ago=1)),
                encoding="utf-8",
            )

            with mock.patch.object(module, "DEFAULT_STARTUP_SMOKE_DIR", missing_primary):
                resolved = module.resolve_startup_smoke_dir(
                    missing_primary,
                    fallback_dirs=(future, fresh),
            )
            self.assertEqual(resolved, fresh)

    def test_resolve_downloads_dir_prefers_fallback_with_more_manifest_artifacts(self) -> None:
        module = _load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            requested = root / "ui-downloads"
            fallback = root / "portal-downloads"
            requested.mkdir(parents=True, exist_ok=True)
            fallback.mkdir(parents=True, exist_ok=True)
            manifest = root / "RELEASE_CHANNEL.generated.json"
            manifest.write_text(
                json.dumps(
                    {
                        "artifacts": [
                            {"fileName": "chummer-avalonia-win-x64-installer.exe"},
                            {"fileName": "chummer-avalonia-win-x64.zip"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            (requested / "chummer-avalonia-win-x64.zip").write_text("zip", encoding="utf-8")
            (fallback / "chummer-avalonia-win-x64.zip").write_text("zip", encoding="utf-8")
            (fallback / "chummer-avalonia-win-x64-installer.exe").write_text("exe", encoding="utf-8")

            resolved = module.resolve_downloads_dir(
                requested,
                manifest_path=manifest,
                fallback_dirs=(fallback,),
            )

            self.assertEqual(resolved, fallback)

    def test_resolve_downloads_dir_keeps_requested_dir_when_manifest_coverage_is_equal(self) -> None:
        module = _load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            requested = root / "ui-downloads"
            fallback = root / "portal-downloads"
            requested.mkdir(parents=True, exist_ok=True)
            fallback.mkdir(parents=True, exist_ok=True)
            manifest = root / "RELEASE_CHANNEL.generated.json"
            manifest.write_text(
                json.dumps({"artifacts": [{"fileName": "chummer-avalonia-win-x64.zip"}]}),
                encoding="utf-8",
            )
            (requested / "chummer-avalonia-win-x64.zip").write_text("zip", encoding="utf-8")
            (fallback / "chummer-avalonia-win-x64.zip").write_text("zip", encoding="utf-8")

            resolved = module.resolve_downloads_dir(
                requested,
                manifest_path=manifest,
                fallback_dirs=(fallback,),
            )

            self.assertEqual(resolved, requested)

    def test_main_skips_proof_argument_by_default(self) -> None:
        module = _load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            materializer = root / "materialize_public_release_channel.py"
            manifest = root / "RELEASE_CHANNEL.generated.json"
            out_path = root / "out.json"
            compat_path = root / "releases.json"
            materializer.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            manifest.write_text("{}", encoding="utf-8")
            captured: dict[str, list[str]] = {}

            def _fake_run(cmd: list[str], check: bool = False):
                captured["cmd"] = list(cmd)
                return type("Completed", (), {"returncode": 0})()

            with mock.patch.object(module, "REGISTRY_MATERIALIZER", materializer):
                with mock.patch.object(module, "resolve_startup_smoke_dir", return_value=None):
                    with mock.patch.object(module.subprocess, "run", side_effect=_fake_run):
                        with mock.patch.object(
                            sys,
                            "argv",
                            [
                                "materialize_chummer_release_registry_projection.py",
                                "--manifest",
                                str(manifest),
                                "--output",
                                str(out_path),
                                "--compat-output",
                                str(compat_path),
                            ],
                        ):
                            rc = module.main()
            self.assertEqual(rc, 0)
            self.assertIn("cmd", captured)
            self.assertNotIn("--proof", captured["cmd"])

    def test_main_passes_explicit_proof_argument(self) -> None:
        module = _load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            materializer = root / "materialize_public_release_channel.py"
            manifest = root / "RELEASE_CHANNEL.generated.json"
            proof = root / "proof.json"
            out_path = root / "out.json"
            compat_path = root / "releases.json"
            materializer.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            manifest.write_text("{}", encoding="utf-8")
            proof.write_text("{}", encoding="utf-8")
            captured: dict[str, list[str]] = {}

            def _fake_run(cmd: list[str], check: bool = False):
                captured["cmd"] = list(cmd)
                return type("Completed", (), {"returncode": 0})()

            with mock.patch.object(module, "REGISTRY_MATERIALIZER", materializer):
                with mock.patch.object(module, "resolve_startup_smoke_dir", return_value=None):
                    with mock.patch.object(module.subprocess, "run", side_effect=_fake_run):
                        with mock.patch.object(
                            sys,
                            "argv",
                            [
                                "materialize_chummer_release_registry_projection.py",
                                "--manifest",
                                str(manifest),
                                "--output",
                                str(out_path),
                                "--compat-output",
                                str(compat_path),
                                "--proof",
                                str(proof),
                            ],
                        ):
                            rc = module.main()
            self.assertEqual(rc, 0)
            self.assertIn("cmd", captured)
            self.assertIn("--proof", captured["cmd"])


if __name__ == "__main__":
    unittest.main()
