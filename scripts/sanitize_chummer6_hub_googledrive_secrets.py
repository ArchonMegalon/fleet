#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


REPO = Path("/docker/chummercomplete/chummer.run-services")
GOOGLE_DIR = REPO / "ChummerHub" / "Services" / "GoogleDrive"
CS_PROJ = REPO / "ChummerHub" / "ChummerHub.csproj"
GITIGNORE = REPO / ".gitignore"
SECRET_JSON = GOOGLE_DIR / "SINners.json"
SECRET_TEXT = GOOGLE_DIR / "TextFile.txt"
TEMPLATE_JSON = GOOGLE_DIR / "SINners.template.json"
TEMPLATE_TEXT = GOOGLE_DIR / "TextFile.template.txt"
BACKUP_ROOT = Path("/tmp/chummer6_hub_secret_cleanup")
COMMIT_MESSAGE = os.environ.get("CHUMMER6_HUB_SANITIZE_COMMIT_MESSAGE", "Initial import")
DEFAULT_GIT_NAME = os.environ.get("CHUMMER6_GIT_NAME", "ArchonMegalon")
DEFAULT_GIT_EMAIL = os.environ.get("CHUMMER6_GIT_EMAIL", "archon.megalon@gmail.com")


def run(*args: str, cwd: Path | None = None, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=str(cwd) if cwd else None,
        check=check,
        text=True,
        capture_output=capture,
    )


def output(*args: str, cwd: Path | None = None) -> str:
    return run(*args, cwd=cwd, capture=True).stdout.strip()


def maybe_output(*args: str, cwd: Path | None = None) -> str:
    result = run(*args, cwd=cwd, check=False, capture=True)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def ensure_ignore_entry(text: str, entry: str) -> str:
    lines = text.splitlines()
    if entry in lines:
        return text
    if text and not text.endswith("\n"):
        text += "\n"
    return text + entry + "\n"


def patch_worktree() -> dict[str, list[str]]:
    removed: list[str] = []
    written: list[str] = []

    if SECRET_JSON.exists():
        SECRET_JSON.unlink()
        removed.append(str(SECRET_JSON.relative_to(REPO)))
    if SECRET_TEXT.exists():
        SECRET_TEXT.unlink()
        removed.append(str(SECRET_TEXT.relative_to(REPO)))

    TEMPLATE_JSON.write_text(
        json.dumps(
            {
                "type": "service_account",
                "project_id": "replace-me",
                "private_key_id": "replace-me",
                "private_key": "-----BEGIN PRIVATE KEY-----\\nREPLACE_ME\\n-----END PRIVATE KEY-----\\n",
                "client_email": "replace-me@example.invalid",
                "client_id": "replace-me",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    written.append(str(TEMPLATE_JSON.relative_to(REPO)))

    TEMPLATE_TEXT.write_text(
        "Replace this file locally with non-committed Google OAuth notes or token fixtures if needed.\n",
        encoding="utf-8",
    )
    written.append(str(TEMPLATE_TEXT.relative_to(REPO)))

    gitignore_text = GITIGNORE.read_text(encoding="utf-8")
    for entry in (
        "/ChummerHub/Services/GoogleDrive/SINners.json",
        "/ChummerHub/Services/GoogleDrive/TextFile.txt",
    ):
        gitignore_text = ensure_ignore_entry(gitignore_text, entry)
    GITIGNORE.write_text(gitignore_text, encoding="utf-8")

    csproj_text = CS_PROJ.read_text(encoding="utf-8")
    csproj_text = csproj_text.replace(
        'Content Remove="Services\\GoogleDrive\\SINners.json"',
        'Content Remove="Services\\GoogleDrive\\SINners.template.json"',
    )
    csproj_text = csproj_text.replace(
        'EmbeddedResource Include="Services\\GoogleDrive\\SINners.json"',
        'EmbeddedResource Include="Services\\GoogleDrive\\SINners.template.json"',
    )
    CS_PROJ.write_text(csproj_text, encoding="utf-8")
    written.append(str(CS_PROJ.relative_to(REPO)))
    written.append(str(GITIGNORE.relative_to(REPO)))

    return {"removed": removed, "written": written}


def reinitialize_git() -> dict[str, str]:
    current_origin = output("git", "-C", str(REPO), "remote", "get-url", "origin")
    legacy_origin = maybe_output("git", "-C", str(REPO), "remote", "get-url", "legacy-origin")
    global_name = maybe_output("git", "config", "--global", "user.name") or DEFAULT_GIT_NAME
    global_email = maybe_output("git", "config", "--global", "user.email") or DEFAULT_GIT_EMAIL
    previous_head = maybe_output("git", "-C", str(REPO), "rev-parse", "--short", "HEAD")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = BACKUP_ROOT / timestamp
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.move(str(REPO / ".git"), str(backup_dir / ".git"))

    run("git", "init", "--initial-branch=main", cwd=REPO)
    run("git", "-C", str(REPO), "config", "user.name", global_name)
    run("git", "-C", str(REPO), "config", "user.email", global_email)
    run("git", "-C", str(REPO), "remote", "add", "origin", current_origin)
    if legacy_origin:
        run("git", "-C", str(REPO), "remote", "add", "legacy-origin", legacy_origin)
    run("git", "-C", str(REPO), "add", "-A")
    run("git", "-C", str(REPO), "commit", "-m", COMMIT_MESSAGE)
    run("git", "-C", str(REPO), "push", "-u", "--force", "origin", "main")
    current_head = output("git", "-C", str(REPO), "rev-parse", "--short", "HEAD")
    return {
        "previous_head": previous_head,
        "current_head": current_head,
        "origin": current_origin,
        "legacy_origin": legacy_origin,
        "backup_dir": str(backup_dir),
    }


def main() -> int:
    patched = patch_worktree()
    git_state = reinitialize_git()
    tracked = output(
        "git",
        "-C",
        str(REPO),
        "ls-files",
        "--",
        "ChummerHub/Services/GoogleDrive/SINners.json",
        "ChummerHub/Services/GoogleDrive/TextFile.txt",
    )
    payload = {
        "repo": str(REPO),
        "patched": patched,
        "git": git_state,
        "tracked_secret_files": tracked.splitlines() if tracked else [],
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
