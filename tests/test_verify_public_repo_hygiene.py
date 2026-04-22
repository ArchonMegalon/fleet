from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path("/docker/fleet/scripts/verify_public_repo_hygiene.py")


class VerifyPublicRepoHygieneTests(unittest.TestCase):
    def _init_repo(self) -> Path:
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        root = Path(tempdir.name)
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.name", "Test User"], check=True)
        return root

    def test_passes_with_example_env_and_normal_file(self) -> None:
        root = self._init_repo()
        (root / "runtime.ea.env.example").write_text("EA_API_TOKEN=\n", encoding="utf-8")
        (root / "README.md").write_text("# Fleet\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "."], check=True)

        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--repo-root", str(root)],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("public repo hygiene ok", result.stdout)

    def test_fails_for_tracked_runtime_state(self) -> None:
        root = self._init_repo()
        (root / "controller.db").write_text("", encoding="utf-8")
        (root / "runtime.ea.env").write_text("EA_API_TOKEN=secret\n", encoding="utf-8")
        (root / "logs").mkdir()
        (root / "logs" / "summary.json").write_text("{}", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "."], check=True)

        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--repo-root", str(root)],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("controller.db", result.stderr)
        self.assertIn("runtime.ea.env", result.stderr)
        self.assertIn("logs/summary.json", result.stderr)

    def test_fails_for_tracked_large_blob(self) -> None:
        root = self._init_repo()
        payload = root / "artifact.bin"
        payload.write_bytes(b"0" * (50 * 1024 * 1024))
        subprocess.run(["git", "-C", str(root), "add", "."], check=True)

        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--repo-root", str(root)],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("artifact.bin", result.stderr)
        self.assertIn("too large", result.stderr)


if __name__ == "__main__":
    unittest.main()
