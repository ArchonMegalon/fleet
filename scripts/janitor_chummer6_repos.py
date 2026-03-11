#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


COMMON_IGNORE_LINES = [
    "# Local agent and worker artifacts",
    ".agent-memory.md",
    "AGENT_MEMORY.md",
    ".agent-state.json",
    ".aider.chat.history.md",
    ".aider.input.history",
    ".aider.tags.cache.v4",
    ".codex-studio/",
    ".codex.boot.prompt.txt",
    ".codex.resume.boot.txt",
    ".tmp/",
    ".local/",
    ".artifacts/",
    "audit.md",
    "skillsneeded.txt",
    "day1.prompt.txt",
    "aider_output.txt",
    "*.binlog",
    "build*.log",
    "solution*.log",
    "err.log",
    "publish_output/",
    "git/",
]

REPOS = [
    {
        "path": Path("/docker/chummercomplete/chummer-core-engine"),
        "label": "chummer6-core",
        "commit": "janitor(core): remove local worker artifacts",
        "remove": [
            ".agent-memory.md",
            "AGENT_MEMORY.md",
            ".codex-studio",
            ".codex.boot.prompt.txt",
            ".codex.resume.boot.txt",
            "audit.md",
            "build_error_log.txt",
            "build_log.txt",
            "day1.prompt.txt",
            "git",
            "plain-build.binlog",
            "skillsneeded.txt",
            "solution-build.binlog",
        ],
    },
    {
        "path": Path("/docker/chummercomplete/chummer-design"),
        "label": "chummer6-design",
        "commit": "janitor(design): remove local worker artifacts",
        "remove": [
            ".codex-studio",
        ],
    },
    {
        "path": Path("/docker/chummercomplete/chummer-presentation"),
        "label": "chummer6-ui",
        "commit": "janitor(ui): remove local worker artifacts",
        "remove": [
            ".agent-memory.md",
            ".codex-studio",
            ".codex.resume.boot.txt",
            ".local",
            "aider_output.txt",
            "audit.md",
            "chummer-presentation.binlog",
            "fail.binlog",
            "git",
            "publish_output",
            "solution_fixed.binlog",
        ],
    },
    {
        "path": Path("/docker/chummercomplete/chummer.run-services"),
        "label": "chummer6-hub",
        "commit": "janitor(hub): remove local worker artifacts",
        "remove": [
            ".agent-memory.md",
            ".codex-studio",
            ".codex.boot.prompt.txt",
            ".codex.resume.boot.txt",
            "audit.md",
            "git",
            "skillsneeded.txt",
        ],
    },
    {
        "path": Path("/docker/chummercomplete/chummer-play"),
        "label": "chummer6-mobile",
        "commit": "janitor(mobile): remove local worker artifacts",
        "remove": [
            ".agent-state.json",
            ".codex-studio",
        ],
    },
    {
        "path": Path("/docker/chummercomplete/chummer-ui-kit"),
        "label": "chummer6-ui-kit",
        "commit": "janitor(ui-kit): remove local worker artifacts",
        "remove": [
            ".agent-memory.md",
            ".agent-state.json",
            ".codex-studio",
        ],
    },
    {
        "path": Path("/docker/chummercomplete/chummer-hub-registry"),
        "label": "chummer6-hub-registry",
        "commit": "janitor(hub-registry): remove local worker artifacts",
        "remove": [
            ".agent-memory.md",
            ".agent-state.json",
            ".codex-studio",
        ],
    },
    {
        "path": Path("/docker/fleet/repos/chummer-media-factory"),
        "label": "chummer6-media-factory",
        "commit": "janitor(media-factory): remove local worker artifacts",
        "remove": [
            ".codex-studio",
        ],
    },
]


def run(repo: Path, *args: str, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=check,
        text=True,
        capture_output=capture,
    )


def output(repo: Path, *args: str) -> str:
    return run(repo, *args, capture=True).stdout.strip()


def is_tracked(repo: Path, rel: str) -> bool:
    result = run(repo, "ls-files", "--error-unmatch", "--", rel, check=False, capture=True)
    return result.returncode == 0


def ensure_ignore(repo: Path) -> bool:
    path = repo / ".gitignore"
    changed = False
    if path.exists():
        text = path.read_text(encoding="utf-8")
    else:
        text = ""
    lines = text.splitlines()
    missing = [line for line in COMMON_IGNORE_LINES if line not in lines]
    if missing:
        if text and not text.endswith("\n"):
            text += "\n"
        if text and not text.endswith("\n\n"):
            text += "\n"
        text += "\n".join(missing) + "\n"
        path.write_text(text, encoding="utf-8")
        changed = True
    return changed


def remove_path(path: Path) -> bool:
    if not path.exists():
        return False
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    return True


def stage_paths(repo: Path, paths: list[str]) -> None:
    for rel in paths:
        if (repo / rel).exists() or is_tracked(repo, rel):
            run(repo, "add", "-A", "--", rel)


def has_staged_changes(repo: Path) -> bool:
    result = run(repo, "diff", "--cached", "--quiet", "--exit-code", check=False)
    return result.returncode != 0


def commit_and_push(repo: Path, message: str) -> str:
    if not has_staged_changes(repo):
        return ""
    run(repo, "commit", "-m", message)
    branch = output(repo, "branch", "--show-current")
    run(repo, "push", "-u", "origin", branch)
    return output(repo, "rev-parse", "--short", "HEAD")


def main() -> int:
    summary: list[dict[str, object]] = []
    for entry in REPOS:
        repo = entry["path"]
        removed: list[str] = []
        ignore_changed = ensure_ignore(repo)
        for rel in entry["remove"]:
            if remove_path(repo / rel):
                removed.append(rel)
        stage_paths(repo, [".gitignore", *entry["remove"]])
        commit = commit_and_push(repo, entry["commit"])
        summary.append(
            {
                "repo": entry["label"],
                "path": str(repo),
                "removed": removed,
                "ignore_changed": ignore_changed,
                "commit": commit,
                "clean": output(repo, "status", "--short") == "",
            }
        )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
