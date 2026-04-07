from __future__ import annotations

import importlib.util
import pathlib
import tempfile


def _load_controller_module():
    path = pathlib.Path("/docker/fleet/controller/app.py")
    spec = importlib.util.spec_from_file_location("fleet_controller_app_startup_dirs_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_ensure_dirs_falls_back_when_runtime_mount_is_not_writable(monkeypatch) -> None:
    module = _load_controller_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = pathlib.Path(tmpdir)
        fallback_root = root / "fallback"
        blocked_root = root / "blocked"
        blocked_root.mkdir()

        module.DB_PATH = blocked_root / "fleet.db"
        module.LOG_DIR = blocked_root / "logs"
        module.WORKTREE_ROOT = blocked_root / "worktrees"
        module.CONTROLLER_HEARTBEAT_PATH = blocked_root / "controller-heartbeat.json"
        module.CODEX_HOME_ROOT = blocked_root / "codex-homes"
        module.GROUP_ROOT = blocked_root / "groups"
        module.MAIL_OUTBOX_ROOT = blocked_root / "mail-outbox"
        module.MAIL_STATE_PATH = blocked_root / "mail-state.json"
        module.RUNTIME_FALLBACK_ROOT = fallback_root

        real_access = module.os.access

        def fake_access(path, mode):
            path_obj = pathlib.Path(path)
            if str(path_obj).startswith(str(blocked_root)):
                return False
            return real_access(path, mode)

        monkeypatch.setattr(module.os, "access", fake_access)

        module.ensure_dirs()

        assert module.DB_PATH == fallback_root / "fleet.db"
        assert module.LOG_DIR == fallback_root / "logs"
        assert module.WORKTREE_ROOT == fallback_root / "worktrees"
        assert module.CONTROLLER_HEARTBEAT_PATH == fallback_root / "controller-heartbeat.json"
        assert module.CODEX_HOME_ROOT == fallback_root / "codex-homes"
        assert module.GROUP_ROOT == fallback_root / "groups"
        assert module.MAIL_OUTBOX_ROOT == fallback_root / "mail-outbox"
        assert module.MAIL_STATE_PATH == fallback_root / "mail-state.json"
