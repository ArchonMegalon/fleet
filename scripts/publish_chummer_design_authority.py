#!/usr/bin/env python3
from __future__ import annotations

import json
import pathlib
import subprocess
import sys


DESIGN_REPO = pathlib.Path("/docker/chummercomplete/chummer-design")
PLAY_REPO = pathlib.Path("/docker/chummercomplete/chummer-play")


def run(repo: pathlib.Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=check,
        text=True,
        capture_output=True,
    )


def current_branch(repo: pathlib.Path) -> str:
    return run(repo, "branch", "--show-current").stdout.strip()


def stage(repo: pathlib.Path, *paths: str) -> None:
    run(repo, "add", "--", *paths)


def has_staged_changes(repo: pathlib.Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(repo), "diff", "--cached", "--quiet", "--exit-code"],
        text=True,
        capture_output=True,
    )
    return result.returncode != 0


def commit_if_needed(repo: pathlib.Path, message: str) -> str:
    if not has_staged_changes(repo):
        return ""
    run(repo, "commit", "-m", message)
    return run(repo, "rev-parse", "--short", "HEAD").stdout.strip()


def push_branch(repo: pathlib.Path, branch: str) -> None:
    run(repo, "push", "-u", "origin", branch)


def main() -> int:
    payload: dict[str, object] = {"updated": []}

    design_branch = current_branch(DESIGN_REPO)
    stage(DESIGN_REPO, "README.md", "products/chummer")
    design_commit = commit_if_needed(DESIGN_REPO, "design: publish canonical truth maintenance")
    push_branch(DESIGN_REPO, design_branch)
    payload["updated"].append(
        {
            "repo": str(DESIGN_REPO),
            "branch": design_branch,
            "commit": design_commit or run(DESIGN_REPO, "rev-parse", "--short", "HEAD").stdout.strip(),
        }
    )

    play_branch = current_branch(PLAY_REPO)
    stage(PLAY_REPO, ".codex-design")
    play_commit = commit_if_needed(PLAY_REPO, "chore(play): publish mirrored design context")
    push_branch(PLAY_REPO, play_branch)
    payload["updated"].append(
        {
            "repo": str(PLAY_REPO),
            "branch": play_branch,
            "commit": play_commit or run(PLAY_REPO, "rev-parse", "--short", "HEAD").stdout.strip(),
        }
    )

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        sys.stderr.write(exc.stderr or exc.stdout or str(exc))
        raise
