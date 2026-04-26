from __future__ import annotations

import json
import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path

import yaml

MATERIALIZER = Path("/docker/fleet/scripts/materialize_next90_m111_fleet_install_aware_followthrough.py")
VERIFIER = Path("/docker/fleet/scripts/verify_next90_m111_fleet_install_aware_followthrough.py")
FIXTURE_MODULE = Path("/docker/fleet/tests/test_materialize_next90_m111_fleet_install_aware_followthrough.py")


def _fixture_tree(tmp_path: Path) -> dict[str, Path]:
    spec = importlib.util.spec_from_file_location("m111_fixture_module", FIXTURE_MODULE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._fixture_tree(tmp_path)


def _materialize(paths: dict[str, Path]) -> Path:
    result = subprocess.run(
        [
            sys.executable,
            str(MATERIALIZER),
            "--support-packets",
            str(paths["support"]),
            "--weekly-governor-packet",
            str(paths["governor"]),
            "--weekly-product-pulse",
            str(paths["pulse"]),
            "--progress-report",
            str(paths["progress"]),
            "--successor-registry",
            str(paths["registry"]),
            "--queue-staging",
            str(paths["queue"]),
            "--output",
            str(paths["out"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return paths["out"]


class VerifyNext90M111InstallAwareFollowthroughTests(unittest.TestCase):
    def _tmp_dir(self, suffix: str) -> Path:
        tmp_path = Path(self.id().replace(".", "_") + suffix)
        tmp_path.mkdir(parents=True, exist_ok=True)
        return tmp_path

    def test_verify_next90_m111_install_aware_followthrough_passes_on_clean_sources(self) -> None:
        tmp_path = self._tmp_dir("_pass")
        try:
            paths = _fixture_tree(tmp_path)
            artifact = _materialize(paths)
            result = subprocess.run(
                [
                    sys.executable,
                    str(VERIFIER),
                    "--artifact",
                    str(artifact),
                    "--support-packets",
                    str(paths["support"]),
                    "--weekly-governor-packet",
                    str(paths["governor"]),
                    "--weekly-product-pulse",
                    str(paths["pulse"]),
                    "--progress-report",
                    str(paths["progress"]),
                    "--successor-registry",
                    str(paths["registry"]),
                    "--queue-staging",
                    str(paths["queue"]),
                ],
                cwd="/docker/fleet",
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
        finally:
            if tmp_path.exists():
                import shutil

                shutil.rmtree(tmp_path)

    def test_verify_next90_m111_install_aware_followthrough_rejects_publication_ref_drift(self) -> None:
        tmp_path = self._tmp_dir("_drift")
        try:
            paths = _fixture_tree(tmp_path)
            artifact = _materialize(paths)
            payload = json.loads(artifact.read_text(encoding="utf-8"))
            payload["publication_refs"][2]["as_of"] = "2026-04-22"
            artifact.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(VERIFIER),
                    "--artifact",
                    str(artifact),
                    "--support-packets",
                    str(paths["support"]),
                    "--weekly-governor-packet",
                    str(paths["governor"]),
                    "--weekly-product-pulse",
                    str(paths["pulse"]),
                    "--progress-report",
                    str(paths["progress"]),
                    "--successor-registry",
                    str(paths["registry"]),
                    "--queue-staging",
                    str(paths["queue"]),
                ],
                cwd="/docker/fleet",
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn(
                "publication refs no longer match the promoted support, governor, pulse, and progress artifacts",
                result.stderr,
            )
        finally:
            if tmp_path.exists():
                import shutil

                shutil.rmtree(tmp_path)

    def test_verify_next90_m111_install_aware_followthrough_rejects_support_and_governor_source_refresh_drift(self) -> None:
        tmp_path = self._tmp_dir("_source_refresh")
        try:
            paths = _fixture_tree(tmp_path)
            artifact = _materialize(paths)

            support_payload = json.loads(paths["support"].read_text(encoding="utf-8"))
            support_payload["generated_at"] = "2026-04-23T19:33:36Z"
            paths["support"].write_text(json.dumps(support_payload, indent=2) + "\n", encoding="utf-8")

            governor_payload = json.loads(paths["governor"].read_text(encoding="utf-8"))
            governor_payload["generated_at"] = "2026-04-23T19:33:39Z"
            paths["governor"].write_text(json.dumps(governor_payload, indent=2) + "\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(VERIFIER),
                    "--artifact",
                    str(artifact),
                    "--support-packets",
                    str(paths["support"]),
                    "--weekly-governor-packet",
                    str(paths["governor"]),
                    "--weekly-product-pulse",
                    str(paths["pulse"]),
                    "--progress-report",
                    str(paths["progress"]),
                    "--successor-registry",
                    str(paths["registry"]),
                    "--queue-staging",
                    str(paths["queue"]),
                ],
                cwd="/docker/fleet",
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn(
                "support receipt truth no longer matches the published install-aware support packet",
                result.stderr,
            )
            self.assertIn(
                "launch truth no longer matches the published governor packet and weekly pulse",
                result.stderr,
            )
            self.assertIn(
                "publication refs no longer match the promoted support, governor, pulse, and progress artifacts",
                result.stderr,
            )
        finally:
            if tmp_path.exists():
                import shutil

                shutil.rmtree(tmp_path)

    def test_verify_next90_m111_install_aware_followthrough_rejects_regenerated_queue_closure_drift(self) -> None:
        tmp_path = self._tmp_dir("_queue_closure")
        try:
            paths = _fixture_tree(tmp_path)
            queue_payload = yaml.safe_load(paths["queue"].read_text(encoding="utf-8"))
            queue_payload["items"][0]["completion_action"] = "manual_review"
            paths["queue"].write_text(yaml.safe_dump(queue_payload, sort_keys=False), encoding="utf-8")
            artifact = _materialize(paths)

            result = subprocess.run(
                [
                    sys.executable,
                    str(VERIFIER),
                    "--artifact",
                    str(artifact),
                    "--support-packets",
                    str(paths["support"]),
                    "--weekly-governor-packet",
                    str(paths["governor"]),
                    "--weekly-product-pulse",
                    str(paths["pulse"]),
                    "--progress-report",
                    str(paths["progress"]),
                    "--successor-registry",
                    str(paths["registry"]),
                    "--queue-staging",
                    str(paths["queue"]),
                ],
                cwd="/docker/fleet",
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn(
                "canonical Fleet queue closure metadata no longer matches the assigned M111 package contract",
                result.stderr,
            )
        finally:
            if tmp_path.exists():
                import shutil

                shutil.rmtree(tmp_path)

    def test_verify_next90_m111_install_aware_followthrough_rejects_regenerated_registry_closure_drift(self) -> None:
        tmp_path = self._tmp_dir("_registry_closure")
        try:
            paths = _fixture_tree(tmp_path)
            registry_payload = yaml.safe_load(paths["registry"].read_text(encoding="utf-8"))
            registry_payload["milestones"][0]["work_tasks"][0]["do_not_reopen_reason"] = "stale"
            paths["registry"].write_text(yaml.safe_dump(registry_payload, sort_keys=False), encoding="utf-8")
            artifact = _materialize(paths)

            result = subprocess.run(
                [
                    sys.executable,
                    str(VERIFIER),
                    "--artifact",
                    str(artifact),
                    "--support-packets",
                    str(paths["support"]),
                    "--weekly-governor-packet",
                    str(paths["governor"]),
                    "--weekly-product-pulse",
                    str(paths["pulse"]),
                    "--progress-report",
                    str(paths["progress"]),
                    "--successor-registry",
                    str(paths["registry"]),
                    "--queue-staging",
                    str(paths["queue"]),
                ],
                cwd="/docker/fleet",
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn(
                "canonical successor registry closure metadata no longer matches the assigned M111 work-task contract",
                result.stderr,
            )
        finally:
            if tmp_path.exists():
                import shutil

                shutil.rmtree(tmp_path)
