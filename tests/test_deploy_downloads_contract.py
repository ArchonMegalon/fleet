from __future__ import annotations

import unittest
from pathlib import Path


DEPLOY_SCRIPT = Path("/docker/fleet/scripts/deploy.sh")


class DeployDownloadsContractTests(unittest.TestCase):
    def test_build_commands_delegate_to_ui_owned_release_pipeline(self) -> None:
        script = DEPLOY_SCRIPT.read_text(encoding="utf-8")

        self.assertIn('CHUMMER_UI_REPO_ROOT:-/docker/chummercomplete/chummer6-ui', script)
        self.assertIn('scripts/build-desktop-installer.sh', script)
        self.assertIn('scripts/generate-releases-manifest.sh', script)
        self.assertIn('scripts/publish-download-bundle.sh', script)
        self.assertIn('gh api user >/dev/null 2>&1', script)

    def test_legacy_patch_and_build_path_stays_explicitly_legacy(self) -> None:
        script = DEPLOY_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("build_chummer_legacy_windows_downloads()", script)
        self.assertIn("patch_chummer_desktop_source", script)
        self.assertIn("build_chummer_legacy_windows_downloads", script)


if __name__ == "__main__":
    unittest.main()
