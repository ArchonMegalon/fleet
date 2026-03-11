#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


OWNER = os.environ.get("CHUMMER6_REHOME_OWNER", "ArchonMegalon")
INITIAL_COMMIT_MESSAGE = os.environ.get("CHUMMER6_INITIAL_COMMIT_MESSAGE", "Initial import")
BACKUP_ROOT = Path("/tmp/chummer6_git_backups")
MANIFEST_PATH = Path("/tmp/chummer6_rehome_manifest.json")

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


def origin_slug(remote_url: str) -> str | None:
    text = remote_url.strip()
    if not text:
        return None
    match = re.search(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/.]+)(?:\.git)?$", text)
    if not match:
        return None
    return f"{match.group('owner')}/{match.group('repo')}"


def repo_visibility(slug: str | None) -> str:
    if not slug:
        return "public"
    try:
        value = output(["gh", "repo", "view", slug, "--json", "visibility", "--jq", ".visibility"])
    except subprocess.CalledProcessError:
        return "public"
    value = value.strip().lower()
    if value == "private":
        return "private"
    if value == "internal":
        return "internal"
    return "public"


def ensure_remote_repo(owner: str, repo_name: str, visibility: str) -> None:
    slug = f"{owner}/{repo_name}"
    view = subprocess.run(["gh", "repo", "view", slug, "--json", "nameWithOwner"], text=True, capture_output=True)
    if view.returncode == 0:
        return
    flag = "--public"
    if visibility == "private":
        flag = "--private"
    elif visibility == "internal":
        flag = "--internal"
    run(["gh", "repo", "create", slug, flag, "--confirm"])


def reinit_repo(repo_path: str, *, old_origin: str | None, new_origin: str, backup_dir: Path) -> None:
    repo = Path(repo_path)
    git_dir = repo / ".git"
    if not git_dir.exists():
        raise SystemExit(f"missing .git directory: {repo_path}")
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.move(str(git_dir), str(backup_dir / ".git"))
    run(["git", "init", "--initial-branch=main"], cwd=repo_path)
    if old_origin:
        run(["git", "-C", repo_path, "remote", "add", "legacy-origin", old_origin])
    run(["git", "-C", repo_path, "remote", "add", "origin", new_origin])
    run(["git", "-C", repo_path, "add", "-A"])
    run(["git", "-C", repo_path, "commit", "-m", INITIAL_COMMIT_MESSAGE])
    run(["git", "-C", repo_path, "push", "-u", "--force", "origin", "main"])


def main() -> int:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_root = BACKUP_ROOT / timestamp
    backup_root.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, Any]] = []

    for entry in REPOS:
        repo_path = entry["path"]
        new_name = entry["new_name"]
        old_origin = ""
        try:
            old_origin = output(["git", "-C", repo_path, "remote", "get-url", "origin"])
        except subprocess.CalledProcessError:
            old_origin = ""
        visibility = repo_visibility(origin_slug(old_origin))
        ensure_remote_repo(OWNER, new_name, visibility)
        new_origin = f"https://github.com/{OWNER}/{new_name}.git"
        reinit_repo(
            repo_path,
            old_origin=old_origin or None,
            new_origin=new_origin,
            backup_dir=backup_root / new_name,
        )
        manifest.append(
            {
                "id": entry["id"],
                "path": repo_path,
                "new_name": new_name,
                "new_origin": new_origin,
                "legacy_origin": old_origin,
                "backup_dir": str((backup_root / new_name).resolve()),
            }
        )

    MANIFEST_PATH.write_text(json.dumps({"owner": OWNER, "timestamp": timestamp, "repos": manifest}, indent=2) + "\n")
    print(json.dumps({"owner": OWNER, "timestamp": timestamp, "repos": manifest}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
