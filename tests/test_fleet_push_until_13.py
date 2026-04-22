from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


MODULE_PATH = Path("/docker/fleet/scripts/fleet_push_until_13.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("fleet_push_until_13", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_main_handles_trigger_timeout_and_keeps_loop_alive(monkeypatch, tmp_path: Path) -> None:
    module = _load_module()

    class _Conn:
        def __enter__(self):
            return object()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(module, "connect", lambda _path: _Conn())
    monkeypatch.setattr(module, "active_runtime_count", lambda _conn: 0)
    monkeypatch.setattr(module, "ready_projects", lambda _conn: ["fleet"])
    monkeypatch.setattr(module, "trigger_run_now", lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError("timed out")))

    def _stop_after_one_sleep(_seconds: float) -> None:
        raise SystemExit(0)

    monkeypatch.setattr(module.time, "sleep", _stop_after_one_sleep)
    monkeypatch.setattr(sys, "argv", ["fleet_push_until_13.py", "--db", str(tmp_path / "fleet.db"), "--poll-seconds", "1"])

    with pytest.raises(SystemExit) as exc:
        module.main()

    assert exc.value.code == 0
