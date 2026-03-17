from __future__ import annotations

import unittest
from pathlib import Path


DEPLOY_SCRIPT = Path("/docker/fleet/deploy-fleet.sh")
README = Path("/docker/fleet/README.md")


class DeployBundleContractTests(unittest.TestCase):
    def test_deploy_script_installs_full_compose_bundle(self) -> None:
        script = DEPLOY_SCRIPT.read_text(encoding="utf-8")

        self.assertIn('copy_tree "$BUNDLE_DIR/admin" "$INSTALL_DIR/admin"', script)
        self.assertIn('copy_tree "$BUNDLE_DIR/auditor" "$INSTALL_DIR/auditor"', script)
        self.assertIn('copy_tree "$BUNDLE_DIR/gateway" "$INSTALL_DIR/gateway"', script)
        self.assertIn('copy_tree "$BUNDLE_DIR/scripts" "$INSTALL_DIR/scripts"', script)
        self.assertIn('copy_tree "$BUNDLE_DIR/config" "$INSTALL_DIR/config" "accounts.yaml"', script)
        self.assertIn('copy_mutable_file "$BUNDLE_DIR/runtime.ea.env" "$INSTALL_DIR/runtime.ea.env"', script)

    def test_deploy_script_fails_closed_on_smoke_check_failure(self) -> None:
        script = DEPLOY_SCRIPT.read_text(encoding="utf-8")

        self.assertIn('wait_for_http "$dashboard_url/health" 120', script)
        self.assertIn('wait_for_http "$dashboard_url/api/status" 120', script)
        self.assertIn('"${COMPOSE[@]}" logs --tail=120 >&2 || true', script)

    def test_readme_describes_full_checkout_installer(self) -> None:
        readme = README.read_text(encoding="utf-8")

        self.assertIn("Run the installer from a full Fleet source checkout.", readme)
        self.assertIn("dashboard `/health` and `/api/status` checks", readme)


if __name__ == "__main__":
    unittest.main()
