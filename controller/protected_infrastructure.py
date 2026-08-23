from __future__ import annotations

import os
from pathlib import Path
import re
from typing import Sequence


_VEXP_LIFECYCLE_ACTIONS = {
    "clean",
    "disable",
    "kill",
    "mask",
    "prune",
    "reset",
    "restart",
    "stop",
    "uninstall",
}
_VEXP_RUNTIME_RE = re.compile(
    r"(?:vexp(?:-cli)?[^\n\x00]*(?:\bdaemon\b|\bmcp\b|\bproxy\b)|"
    r"vexp-(?:http-)?supervisor|vexp-codex-mcp|\.vexp/(?:daemon|index|mcp))",
    re.IGNORECASE,
)
_SHELL_VEXP_LIFECYCLE_RE = re.compile(
    r"(?:\bvexp\s+(?:clean|disable|kill|mask|prune|reset|restart|stop|uninstall)\b|"
    r"\b(?:pkill|killall)\b[^\n;&|]*\bvexp\b|"
    r"\b(?:service|systemctl)\b[^\n;&|]*(?:\b(?:kill|restart|stop|disable|mask)\b[^\n;&|]*\bvexp\b|"
    r"\bvexp\b[^\n;&|]*\b(?:kill|restart|stop|disable|mask)\b))",
    re.IGNORECASE,
)


def _process_cmdline(pid: int, *, proc_root: Path = Path("/proc")) -> str:
    try:
        raw = (proc_root / str(int(pid)) / "cmdline").read_bytes()
    except (OSError, ValueError):
        raw = b""
    text = raw.replace(b"\x00", b" ").decode("utf-8", errors="replace").strip()
    if text:
        return text
    try:
        return (proc_root / str(int(pid)) / "comm").read_text(encoding="utf-8", errors="replace").strip()
    except (OSError, ValueError):
        return ""


def is_vexp_runtime_process(pid: int, *, proc_root: Path = Path("/proc")) -> bool:
    return bool(_VEXP_RUNTIME_RE.search(_process_cmdline(pid, proc_root=proc_root)))


def _process_group_id(pid: int, *, proc_root: Path = Path("/proc")) -> int | None:
    try:
        stat_text = (proc_root / str(int(pid)) / "stat").read_text(encoding="utf-8", errors="replace")
        fields = stat_text.rsplit(")", 1)[1].strip().split()
        return int(fields[2])
    except (IndexError, OSError, TypeError, ValueError):
        return None


def process_group_signal_targets(root_pid: int, *, proc_root: Path = Path("/proc")) -> tuple[int, ...]:
    """Return group members that may be signalled, excluding vexp runtime infrastructure."""

    root_pid = int(root_pid)
    root_pgid = _process_group_id(root_pid, proc_root=proc_root)
    if root_pgid is None:
        return () if is_vexp_runtime_process(root_pid, proc_root=proc_root) else (root_pid,)
    targets: list[int] = []
    try:
        entries = tuple(proc_root.iterdir())
    except OSError:
        entries = ()
    for entry in entries:
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if _process_group_id(pid, proc_root=proc_root) != root_pgid:
            continue
        if is_vexp_runtime_process(pid, proc_root=proc_root):
            continue
        targets.append(pid)
    if root_pid not in targets and not is_vexp_runtime_process(root_pid, proc_root=proc_root):
        targets.append(root_pid)
    return tuple(sorted(set(targets), reverse=True))


def signal_process_group_preserving_vexp(root_pid: int, signal_number: int) -> tuple[int, ...]:
    targets = process_group_signal_targets(root_pid)
    signalled: list[int] = []
    for pid in targets:
        try:
            os.kill(pid, signal_number)
        except ProcessLookupError:
            continue
        signalled.append(pid)
    return tuple(signalled)


def command_targets_vexp_lifecycle(command: Sequence[object]) -> bool:
    words = [str(item or "").strip() for item in command if str(item or "").strip()]
    if not words:
        return False
    executable = Path(words[0]).name.lower()
    lowered = [word.lower() for word in words[1:]]
    if executable == "vexp":
        action = next((word for word in lowered if not word.startswith("-")), "")
        return action in _VEXP_LIFECYCLE_ACTIONS
    if executable in {"pkill", "killall"}:
        return any("vexp" in word for word in lowered)
    if executable in {"service", "systemctl"}:
        return any(word in _VEXP_LIFECYCLE_ACTIONS for word in lowered) and any("vexp" in word for word in lowered)
    if executable in {"bash", "dash", "sh", "zsh"}:
        return bool(_SHELL_VEXP_LIFECYCLE_RE.search(" ".join(words[1:])))
    if executable == "kill":
        for word in lowered:
            try:
                pid = abs(int(word))
            except ValueError:
                continue
            if pid and is_vexp_runtime_process(pid):
                return True
    return False


def assert_command_preserves_protected_infrastructure(command: Sequence[object]) -> None:
    if command_targets_vexp_lifecycle(command):
        raise RuntimeError("protected_infrastructure:vexp_lifecycle_command_blocked")


def is_protected_cleanup_path(path: Path | str) -> bool:
    candidate = Path(path)
    lexical_parts = candidate.parts
    resolved_parts = candidate.resolve(strict=False).parts
    return any(part.lower() == ".vexp" for part in (*lexical_parts, *resolved_parts))


def assert_cleanup_target_is_safe(path: Path | str) -> None:
    if is_protected_cleanup_path(path):
        raise RuntimeError("protected_infrastructure:vexp_cleanup_target_blocked")
