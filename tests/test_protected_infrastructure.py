from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load(relative_path: str, module_name: str):
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(params=["controller/protected_infrastructure.py", "studio/protected_infrastructure.py"])
def safety(request):
    return _load(request.param, "fleet_protected_infrastructure_" + request.param.split("/", 1)[0])


def _write_process(proc_root: Path, *, pid: int, pgid: int, command: str) -> None:
    process_root = proc_root / str(pid)
    process_root.mkdir(parents=True)
    (process_root / "stat").write_text(f"{pid} (worker) S 1 {pgid} 0 0\n", encoding="utf-8")
    (process_root / "cmdline").write_bytes(command.replace(" ", "\x00").encode("utf-8"))


def test_timeout_signal_targets_exclude_vexp_runtime(safety, tmp_path: Path) -> None:
    _write_process(tmp_path, pid=100, pgid=100, command="codex exec --json")
    _write_process(tmp_path, pid=101, pgid=100, command="python worker.py")
    _write_process(
        tmp_path,
        pid=102,
        pgid=100,
        command="/opt/vexp-core daemon --workspace /docker/example --socket /docker/example/.vexp/daemon.sock",
    )
    _write_process(tmp_path, pid=103, pgid=200, command="python unrelated.py")

    assert safety.process_group_signal_targets(100, proc_root=tmp_path) == (101, 100)


@pytest.mark.parametrize(
    "command",
    [
        ["vexp", "stop", "/docker/example"],
        ["bash", "-lc", "vexp stop /docker/example"],
        ["systemctl", "restart", "vexp-daemon.service"],
        ["pkill", "-f", "vexp-core daemon"],
    ],
)
def test_vexp_lifecycle_commands_fail_closed(safety, command) -> None:
    with pytest.raises(RuntimeError, match="vexp_lifecycle_command_blocked"):
        safety.assert_command_preserves_protected_infrastructure(command)


@pytest.mark.parametrize(
    "command",
    [
        ["vexp", "daemons"],
        ["vexp", "start", "/docker/example"],
        ["codex", "exec", "--json", "-"],
        ["git", "worktree", "prune"],
    ],
)
def test_non_destructive_commands_remain_allowed(safety, command) -> None:
    safety.assert_command_preserves_protected_infrastructure(command)


def test_vexp_state_is_never_a_cleanup_target(safety, tmp_path: Path) -> None:
    assert safety.is_protected_cleanup_path("/docker/example/.vexp/index")
    with pytest.raises(RuntimeError, match="vexp_cleanup_target_blocked"):
        safety.assert_cleanup_target_is_safe("/docker/example/.vexp")
    vexp_root = tmp_path / ".vexp"
    vexp_root.mkdir()
    alias = tmp_path / "cleanup-alias"
    alias.symlink_to(vexp_root, target_is_directory=True)
    assert safety.is_protected_cleanup_path(alias)
    safety.assert_cleanup_target_is_safe("/docker/fleet/state/worktrees/closed-package")
