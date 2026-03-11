#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


OWNER = os.environ.get("CHUMMER6_REHOME_OWNER", "ArchonMegalon")
INITIAL_COMMIT_MESSAGE = os.environ.get("CHUMMER6_INITIAL_COMMIT_MESSAGE", "Initial clean import")
BACKUP_ROOT = Path("/tmp/chummer6_history_resets")
MANIFEST_PATH = Path("/tmp/chummer6_history_reset_manifest.json")
DEFAULT_GIT_NAME = os.environ.get("CHUMMER6_GIT_NAME", "ArchonMegalon")
DEFAULT_GIT_EMAIL = os.environ.get("CHUMMER6_GIT_EMAIL", "archon.megalon@gmail.com")

REPOS: list[dict[str, str]] = [
    {"id": "core", "path": "/docker/chummercomplete/chummer-core-engine", "new_name": "chummer6-core"},
    {"id": "design", "path": "/docker/chummercomplete/chummer-design", "new_name": "chummer6-design"},
    {"id": "ui", "path": "/docker/chummercomplete/chummer-presentation", "new_name": "chummer6-ui"},
    {"id": "hub", "path": "/docker/chummercomplete/chummer.run-services", "new_name": "chummer6-hub"},
    {"id": "mobile", "path": "/docker/chummercomplete/chummer-play", "new_name": "chummer6-mobile"},
    {"id": "ui-kit", "path": "/docker/chummercomplete/chummer-ui-kit", "new_name": "chummer6-ui-kit"},
    {"id": "hub-registry", "path": "/docker/chummercomplete/chummer-hub-registry", "new_name": "chummer6-hub-registry"},
    {"id": "media-factory", "path": "/docker/fleet/repos/chummer-media-factory", "new_name": "chummer6-media-factory"},
]

COMMON_IGNORE_LINES = [
    "# Local generated artifacts",
    ".codex-studio/",
    ".tmp/",
    ".local/",
    ".artifacts/",
    "publish_output/",
    "git/",
    "**/bin/",
    "**/obj/",
    "**/__pycache__/",
    "*.pyc",
    "*.pyo",
    "*.binlog",
    "*.user.delete",
    "*.suo",
]

REMOVE_DIR_NAMES = {
    "bin",
    "obj",
    "__pycache__",
    ".codex-studio",
    ".tmp",
    ".local",
    ".artifacts",
    "publish_output",
    "git",
}

REMOVE_FILE_SUFFIXES = (
    ".pyc",
    ".pyo",
    ".binlog",
    ".user.delete",
    ".suo",
)


def run(cmd: list[str], *, cwd: str | None = None, capture: bool = False, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        check=check,
        text=True,
        capture_output=capture,
    )


def output(cmd: list[str], *, cwd: str | None = None) -> str:
    return run(cmd, cwd=cwd, capture=True).stdout.strip()


def git_name() -> str:
    try:
        value = output(["git", "config", "--global", "user.name"])
    except subprocess.CalledProcessError:
        value = ""
    return value or DEFAULT_GIT_NAME


def git_email() -> str:
    try:
        value = output(["git", "config", "--global", "user.email"])
    except subprocess.CalledProcessError:
        value = ""
    return value or DEFAULT_GIT_EMAIL


def ensure_ignore(repo: Path) -> None:
    path = repo / ".gitignore"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = text.splitlines()
    missing = [line for line in COMMON_IGNORE_LINES if line not in lines]
    if not missing:
        return
    if text and not text.endswith("\n"):
        text += "\n"
    if text and not text.endswith("\n\n"):
        text += "\n"
    text += "\n".join(missing) + "\n"
    path.write_text(text, encoding="utf-8")


def strip_generated_artifacts(repo: Path) -> list[str]:
    removed: list[str] = []
    for path in sorted(repo.rglob("*")):
        if ".git" in path.parts:
            continue
        rel = path.relative_to(repo)
        if path.is_dir() and path.name in REMOVE_DIR_NAMES:
            shutil.rmtree(path)
            removed.append(str(rel))
            continue
        if path.is_file() and path.name.endswith(REMOVE_FILE_SUFFIXES):
            path.unlink()
            removed.append(str(rel))
    return removed


def reinit_repo(repo_path: str, *, repo_name: str, backup_dir: Path) -> dict[str, Any]:
    repo = Path(repo_path)
    git_dir = repo / ".git"
    if not repo.exists():
        raise SystemExit(f"missing repo path: {repo_path}")
    if not git_dir.exists():
        raise SystemExit(f"missing .git directory: {repo_path}")

    ensure_ignore(repo)
    removed = strip_generated_artifacts(repo)

    origin = f"https://github.com/{OWNER}/{repo_name}.git"
    old_origin = ""
    try:
        old_origin = output(["git", "-C", repo_path, "remote", "get-url", "origin"])
    except subprocess.CalledProcessError:
        old_origin = ""

    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.move(str(git_dir), str(backup_dir / ".git"))

    run(["git", "init", "--initial-branch=main"], cwd=repo_path)
    run(["git", "-C", repo_path, "config", "user.name", git_name()])
    run(["git", "-C", repo_path, "config", "user.email", git_email()])
    run(["git", "-C", repo_path, "remote", "add", "origin", origin])
    run(["git", "-C", repo_path, "add", "-A"])
    run(["git", "-C", repo_path, "commit", "-m", INITIAL_COMMIT_MESSAGE])
    run(["git", "-C", repo_path, "push", "-u", "--force", "origin", "main"])

    return {
        "path": repo_path,
        "repo": repo_name,
        "origin": origin,
        "previous_origin": old_origin,
        "backup_dir": str((backup_dir / ".git").resolve()),
        "head": output(["git", "-C", repo_path, "rev-parse", "--short", "HEAD"]),
        "removed_artifacts": removed,
    }


def main() -> int:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_root = BACKUP_ROOT / timestamp
    backup_root.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []

    for entry in REPOS:
        results.append(
            reinit_repo(
                entry["path"],
                repo_name=entry["new_name"],
                backup_dir=backup_root / entry["new_name"],
            )
        )

    MANIFEST_PATH.write_text(json.dumps({"timestamp": timestamp, "owner": OWNER, "repos": results}, indent=2) + "\n")
    print(json.dumps({"timestamp": timestamp, "owner": OWNER, "repos": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
