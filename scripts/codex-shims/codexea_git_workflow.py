#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _extract_staged_commands(prompt: str) -> list[str]:
    marker = "Run these exact commands first:"
    marker_index = prompt.find(marker)
    if marker_index < 0:
        return []
    commands: list[str] = []
    for raw_line in prompt[marker_index + len(marker) :].splitlines():
        line = raw_line.strip()
        if not line:
            if commands:
                break
            continue
        if line.startswith("$ "):
            commands.append(line[2:].strip())
            continue
        if line.startswith("- "):
            commands.append(line[2:].strip())
            continue
        break
    return [command for command in commands if command]


def _is_git_command(command: str, verb: str | None = None) -> bool:
    normalized = " ".join(command.strip().lower().split())
    if not normalized.startswith("git "):
        return False
    if verb is None:
        return True
    return normalized == f"git {verb}" or normalized.startswith(f"git {verb} ")


def _run_shell(command: str, cwd: Path) -> str:
    completed = subprocess.run(
        ["/bin/bash", "-lc", command],
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        if completed.stdout:
            sys.stderr.write(completed.stdout)
        if completed.stderr:
            sys.stderr.write(completed.stderr)
        raise SystemExit(completed.returncode)
    return completed.stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cwd", required=True)
    parser.add_argument("--prompt-file", required=True)
    parser.add_argument("--output-last-message")
    args = parser.parse_args()

    cwd = Path(args.cwd).expanduser().resolve()
    prompt = Path(args.prompt_file).read_text(encoding="utf-8", errors="replace")
    commands = _extract_staged_commands(prompt)
    if not commands:
        return 10
    if not all(_is_git_command(command) for command in commands):
        return 10
    if not any(_is_git_command(command, "add") for command in commands):
        return 10
    commit_command = next((command for command in commands if _is_git_command(command, "commit")), "")
    push_command = next((command for command in commands if _is_git_command(command, "push")), "")
    if not commit_command or not push_command:
        return 10

    for command in commands:
        if _is_git_command(command, "add"):
            _run_shell(command, cwd)
            continue
        if _is_git_command(command, "commit"):
            diff_check = subprocess.run(
                ["git", "diff", "--cached", "--quiet"],
                cwd=str(cwd),
                text=True,
                capture_output=True,
                check=False,
            )
            if diff_check.returncode == 0:
                continue
            _run_shell(command, cwd)
            continue
        if _is_git_command(command, "push"):
            _run_shell(command, cwd)
            continue
        _run_shell(command, cwd)

    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=str(cwd),
        text=True,
    ).strip()
    final_text = f"Pushed commit {head}"
    if args.output_last_message:
        output_path = Path(args.output_last_message).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(final_text + "\n", encoding="utf-8")
    print(final_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
