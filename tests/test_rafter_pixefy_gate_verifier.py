from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "verify_committed_rafter_pixefy_ci_receipt.py"
WORKFLOW_PATH = MODULE_PATH.parents[1] / ".github/workflows/release-qa-rafter-pixefy.yml"


def _load_module():
    spec = importlib.util.spec_from_file_location("verify_committed_rafter_pixefy_ci_receipt", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _gate(version: str = "run-20260601-070650") -> dict:
    return {
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "active_release_binding": {
            "verification_status": "pass",
            "base_url": "https://chummer.run",
            "channelId": "public_stable",
            "status": "published",
            "rolloutState": "public_stable",
            "version": version,
            "missingRequiredPlatformHeadRidTuples": [],
            "promotedPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:osx-arm64:macos",
                "avalonia:win-x64:windows",
            ],
        },
    }


def _live_manifest(version: str = "run-20260601-070650") -> dict:
    return {
        "channel": "public_stable",
        "version": version,
        "status": "published",
        "rolloutState": "public_stable",
        "desktopTupleCoverage": {
            "missingRequiredPlatformHeadRidTuples": [],
            "promotedPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:osx-arm64:macos",
                "avalonia:win-x64:windows",
            ],
        },
    }


class RafterPixefyGateVerifierTests(unittest.TestCase):
    def test_workflow_keeps_all_pr_source_checks_and_exact_release_triggers(self) -> None:
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.assertEqual(workflow.split("\non:\n", 1)[1].split("\njobs:\n", 1)[0], """  workflow_dispatch:
  schedule:
    - cron: "0 3 * * *"
  push:
    branches:
      - main
    paths:
      - ".github/workflows/release-qa-rafter-pixefy.yml"
      - "_completion/ltd_inventory/RAFTER_TIER3_LTDS_ENTRY.generated.json"
      - "_completion/ltd_inventory/PIXEFY_TIER3_LTDS_ENTRY.generated.json"
      - "_completion/rafter/**"
      - "_completion/pixefy/**"
      - "_completion/rafter_pixefy/**"
      - "providers/rafter/**"
      - "providers/pixefy/**"
      - "scripts/rafter_pixefy_common.py"
      - "scripts/verify_committed_rafter_pixefy_ci_receipt.py"
      - "scripts/verify_ltds_rafter_pixefy_entries.py"
      - "scripts/final_rafter_pixefy_qa_stack_verdict.py"
      - "tests/test_rafter_pixefy_gate_verifier.py"
  pull_request:
    branches:
      - main
""")

    def test_required_source_jobs_have_no_event_or_step_conditions(self) -> None:
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        source_jobs = workflow.split("\njobs:\n", 1)[1].split("\n  rafter-security-gate:\n", 1)[0]
        self.assertNotIn("if:", source_jobs)
        self.assertNotIn("needs:", source_jobs)
        self.assertNotIn("continue-on-error", source_jobs)
        for name in ("verify-ltd-inventory", "verifier-regression-tests"):
            self.assertIn(f"  {name}:\n    runs-on: ubuntu-latest\n", source_jobs)
        self.assertIn("run: python3 scripts/verify_ltds_rafter_pixefy_entries.py\n", source_jobs)
        self.assertIn("run: python3 -m unittest tests.test_rafter_pixefy_gate_verifier\n", source_jobs)
        self.assertIn("git diff --exit-code --", source_jobs)

    def test_live_gold_jobs_keep_dependencies_and_only_explicit_release_events(self) -> None:
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        condition = "    if: ${{ github.event_name == 'schedule' || github.event_name == 'workflow_dispatch' || github.event_name == 'push' }}\n"
        self.assertEqual(workflow.count(condition), 3)
        self.assertEqual(workflow.count("if:"), 3)
        self.assertNotIn("continue-on-error", workflow)
        for name, comment, dependencies, command in (
            ("rafter-security-gate", "    # PRs validate source; these jobs attest the live public desktop release.\n",
             ["verify-ltd-inventory", "verifier-regression-tests"],
             "scripts/verify_committed_rafter_pixefy_ci_receipt.py Rafter"),
            ("pixefy-visual-gate", "", ["verify-ltd-inventory", "verifier-regression-tests"],
             "scripts/verify_committed_rafter_pixefy_ci_receipt.py Pixefy"),
            ("final-rafter-pixefy-verdict", "", ["rafter-security-gate", "pixefy-visual-gate"],
             "scripts/final_rafter_pixefy_qa_stack_verdict.py"),
        ):
            with self.subTest(job=name):
                self.assertIn(f"  {name}:\n" + comment + condition +
                    "    runs-on: ubuntu-latest\n    timeout-minutes: 5\n    needs:\n" +
                    "".join(f"      - {dependency}\n" for dependency in dependencies), workflow)
                self.assertIn(f"        run: python3 {command}\n", workflow)

    def test_live_release_alignment_rejects_version_drift(self) -> None:
        module = _load_module()
        failures: list[str] = []
        with (
            mock.patch.object(module, "fetch_json", return_value=_live_manifest("run-older")),
            mock.patch.object(module, "fetch_text", return_value="Gold-ready on Public release Build run-older"),
        ):
            module.require_live_release_alignment(_gate("run-current"), failures)

        self.assertIn("live_release_version_mismatch", failures)
        self.assertIn("live_status_page_missing_bound_version", failures)

    def test_live_release_alignment_accepts_matching_public_stable_manifest(self) -> None:
        module = _load_module()
        failures: list[str] = []
        with (
            mock.patch.object(module, "fetch_json", return_value=_live_manifest()),
            mock.patch.object(module, "fetch_text", return_value="Gold-ready on Public release Build run-20260601-070650"),
        ):
            module.require_live_release_alignment(_gate(), failures)

        self.assertEqual([], failures)

    def test_pixefy_screenshot_verifier_rejects_missing_capture_file(self) -> None:
        module = _load_module()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            index = tmp_path / "index.json"
            index.write_text(
                json.dumps(
                    {
                        "status": "pass",
                        "routes": [
                            {
                                "route_id": "home",
                                "captures": [
                                    {
                                        "device_id": "iphone_se",
                                        "status": "captured",
                                        "screenshot_path": "screenshots/home__iphone_se.png",
                                    }
                                ],
                            }
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            failures: list[str] = []
            with mock.patch.object(module, "ROOT", tmp_path):
                module.require_pixefy_screenshots(
                    {"screenshot_index_path": index},
                    {"coverage": {"captured_device_route_pairs": 110, "missing_device_route_pairs": []}},
                    failures,
                )

        self.assertIn("pixefy_screenshot_index_pair_count_not_110", failures)
        self.assertIn("pixefy_screenshot_files_missing_or_empty", failures)

    def test_route_manifest_rejects_active_release_binding_drift(self) -> None:
        module = _load_module()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest = tmp_path / "rafter-route-manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "status": "pass",
                        "active_release_binding": {
                            "verification_status": "pass",
                            "version": "run-older",
                        },
                        "required_live_routes": [
                            "https://chummer.run/",
                            "https://chummer.run/downloads",
                            "https://chummer.run/status",
                        ],
                        "scanned_live_routes": [
                            "https://chummer.run/",
                            "https://chummer.run/downloads",
                            "https://chummer.run/status",
                        ],
                        "missing_live_routes": [],
                        "forbidden_public_copy_routes": [],
                        "route_results": [
                            {"url": "https://chummer.run/", "ok": True},
                            {"url": "https://chummer.run/downloads", "ok": True},
                            {"url": "https://chummer.run/status", "ok": True},
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            failures: list[str] = []
            with mock.patch.object(module, "ROOT", tmp_path):
                module.require_public_route_manifest(
                    {"route_manifest_path": manifest},
                    "Rafter",
                    _gate("run-current"),
                    failures,
                )

        self.assertIn("route_manifest_active_release_binding_version_mismatch", failures)


if __name__ == "__main__":
    unittest.main()
