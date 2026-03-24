from __future__ import annotations

import importlib.util
import tempfile
import types
import unittest
from pathlib import Path
import sys


MODULE_PATH = Path("/docker/fleet/controller/app.py")


def install_fastapi_stubs() -> None:
    if "fastapi" in sys.modules and "fastapi.responses" in sys.modules:
        return

    fastapi = types.ModuleType("fastapi")
    responses = types.ModuleType("fastapi.responses")

    class DummyFastAPI:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __getattr__(self, _name):
            def decorator(*args, **kwargs):
                def wrapper(func):
                    return func

                return wrapper

            return decorator

    class DummyHTTPException(Exception):
        pass

    class DummyRequest:
        pass

    class DummyResponse:
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

    def dummy_form(*args, **kwargs):
        return None

    fastapi.FastAPI = DummyFastAPI
    fastapi.Form = dummy_form
    fastapi.HTTPException = DummyHTTPException
    fastapi.Request = DummyRequest
    responses.HTMLResponse = DummyResponse
    responses.JSONResponse = DummyResponse
    responses.PlainTextResponse = DummyResponse
    responses.RedirectResponse = DummyResponse
    responses.Response = DummyResponse
    sys.modules["fastapi"] = fastapi
    sys.modules["fastapi.responses"] = responses


def load_controller_module():
    install_fastapi_stubs()
    spec = importlib.util.spec_from_file_location("test_work_package_collision_regressions", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WorkPackageCollisionRegressions(unittest.TestCase):
    def setUp(self) -> None:
        self.controller = load_controller_module()

    def test_scope_claim_conflicts_detects_wildcard_overlap(self) -> None:
        self.assertTrue(
            self.controller.scope_claim_conflicts("path", "src/**/*.py", "path", "src/api/routes.py")
        )

    def test_package_changed_paths_within_scope_rejects_denied_paths(self) -> None:
        package = {
            "allowed_paths": ["src/**"],
            "denied_paths": ["src/generated/**"],
            "max_touched_files": 3,
        }

        ok, reason = self.controller.package_changed_paths_within_scope(
            package,
            "/docker/fleet",
            changed_paths=["src/generated/schema.py"],
        )

        self.assertFalse(ok)
        self.assertIn("package changed denied path src/generated/schema.py", reason)

    def test_active_scope_claim_survives_sync_and_blocks_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_root = root / "repo"
            published = repo_root / ".codex-studio" / "published"
            published.mkdir(parents=True, exist_ok=True)
            (published / "WORKPACKAGES.generated.yaml").write_text(
                "\n".join(
                    [
                        "work_packages:",
                        "  - package_id: fleet-a",
                        "    title: Slice A",
                        "    owned_surfaces:",
                        "      - build_root:fleet",
                        "  - package_id: fleet-b",
                        "    title: Slice B",
                        "    owned_surfaces:",
                        "      - build_root:fleet",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            self.controller.init_db()

            config = {
                "projects": [
                    {
                        "id": "fleet",
                        "path": str(repo_root),
                        "queue": [],
                        "enabled": True,
                        "booster_pool_contract": {"pool": "operator_funded", "project_safety_cap": 2},
                    }
                ],
                "lanes": {"core": {"id": "core", "runtime_model": "ea-coder-hard"}},
                "accounts": {},
            }

            self.controller.sync_config_to_db(config)
            packages = self.controller.work_package_rows(project_id="fleet")
            self.controller.activate_work_package_scope_claims("fleet-a")
            self.controller.sync_work_packages_to_db(config)

            self.assertEqual(
                [claim["claim_state"] for claim in self.controller.scope_claim_rows(package_id="fleet-a")],
                ["active"],
            )
            self.assertEqual(
                self.controller.work_package_scope_conflict(packages[1]),
                "scope conflict with fleet-a on surface:build_root:fleet",
            )


if __name__ == "__main__":
    unittest.main()
