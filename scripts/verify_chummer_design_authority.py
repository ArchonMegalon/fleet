#!/usr/bin/env python3
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import yaml


DESIGN_ROOT = pathlib.Path("/docker/chummercomplete/chummer-design")
PLAY_ROOT = pathlib.Path("/docker/chummercomplete/chummer6-mobile")
PRODUCT_ROOT = DESIGN_ROOT / "products" / "chummer"

ORPHAN_ROOT_PATHS = [
    DESIGN_ROOT / "BOUNDARIES_AND_CONTRACTS.md",
    DESIGN_ROOT / "VISION_AND_MILESTONES.md",
    DESIGN_ROOT / "chummer-media-factory.design.v1.md",
    DESIGN_ROOT / "chummer-media-factory",
]

DESIGN_CANON_PATHS = ["README.md", "products/chummer"]
PLAY_MIRROR_PATHS = [".codex-design"]


def load_text(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def git_stdout(repo: pathlib.Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def git_path_status(repo: pathlib.Path, paths: list[str]) -> list[str]:
    try:
        result = git_stdout(repo, "status", "--short", "--", *paths)
    except Exception:
        return ["git status failed"]
    return [line for line in result.splitlines() if line.strip()]


def git_branch_sync(repo: pathlib.Path) -> dict[str, object]:
    result: dict[str, object] = {
        "branch": "",
        "upstream": "",
        "ahead": None,
        "behind": None,
    }
    try:
        result["branch"] = git_stdout(repo, "branch", "--show-current")
    except Exception:
        return result
    try:
        result["upstream"] = git_stdout(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
        counts = git_stdout(repo, "rev-list", "--left-right", "--count", "HEAD...@{upstream}")
        ahead_text, behind_text = counts.split()
        result["ahead"] = int(ahead_text)
        result["behind"] = int(behind_text)
    except Exception:
        result["upstream"] = ""
    return result


def main() -> int:
    failures: list[str] = []
    checks: dict[str, object] = {}

    readme_text = load_text(PRODUCT_ROOT / "README.md")
    sync_manifest_path = PRODUCT_ROOT / "sync" / "sync-manifest.yaml"
    sync_manifest = {}
    if sync_manifest_path.exists():
        try:
            sync_manifest = yaml.safe_load(sync_manifest_path.read_text(encoding="utf-8")) or {}
        except Exception as exc:  # noqa: BLE001
            failures.append(f"sync manifest unreadable: {exc}")
    else:
        failures.append(f"missing sync manifest: {sync_manifest_path}")

    mirrors = sync_manifest.get("mirrors") or []
    mirror_repos = {
        str(item.get("repo") or "").strip()
        for item in mirrors
        if isinstance(item, dict) and str(item.get("repo") or "").strip()
    }

    checks["product_root_exists"] = PRODUCT_ROOT.exists()
    checks["media_factory_in_product_readme"] = "chummer6-media-factory" in readme_text
    checks["media_factory_in_sync_manifest"] = "chummer6-media-factory" in mirror_repos
    checks["play_in_sync_manifest"] = "chummer6-mobile" in mirror_repos
    checks["play_repo_mirror_present"] = (PLAY_ROOT / ".codex-design" / "product").exists()
    checks["play_repo_scope_present"] = (PLAY_ROOT / ".codex-design" / "repo" / "IMPLEMENTATION_SCOPE.md").exists()
    checks["orphan_root_paths_present"] = [str(path) for path in ORPHAN_ROOT_PATHS if path.exists()]
    checks["design_canon_git_status"] = git_path_status(DESIGN_ROOT, DESIGN_CANON_PATHS)
    checks["play_mirror_git_status"] = git_path_status(PLAY_ROOT, PLAY_MIRROR_PATHS)
    checks["design_branch_sync"] = git_branch_sync(DESIGN_ROOT)
    checks["play_branch_sync"] = git_branch_sync(PLAY_ROOT)

    if not checks["product_root_exists"]:
        failures.append(f"missing canonical product root: {PRODUCT_ROOT}")
    if not checks["media_factory_in_product_readme"]:
        failures.append("products/chummer/README.md does not include chummer6-media-factory")
    if not checks["media_factory_in_sync_manifest"]:
        failures.append("sync-manifest.yaml does not mirror chummer6-media-factory")
    if not checks["play_in_sync_manifest"]:
        failures.append("sync-manifest.yaml does not mirror chummer6-mobile")
    if not checks["play_repo_mirror_present"]:
        failures.append("chummer6-mobile is missing .codex-design/product mirror content")
    if not checks["play_repo_scope_present"]:
        failures.append("chummer6-mobile is missing .codex-design/repo/IMPLEMENTATION_SCOPE.md")
    if checks["orphan_root_paths_present"]:
        failures.append("chummer-design still has orphan product docs at repo root")
    if checks["design_canon_git_status"]:
        failures.append("chummer-design canon has uncommitted local changes")
    if checks["play_mirror_git_status"]:
        failures.append("chummer6-mobile mirror has uncommitted local changes")
    for label in ("design_branch_sync", "play_branch_sync"):
        sync = checks[label]
        if not isinstance(sync, dict):
            continue
        upstream = str(sync.get("upstream") or "").strip()
        ahead = sync.get("ahead")
        behind = sync.get("behind")
        if not upstream:
            failures.append(f"{label.replace('_branch_sync', '')} has no upstream tracking branch")
            continue
        if isinstance(ahead, int) and ahead > 0:
            failures.append(f"{label.replace('_branch_sync', '')} has unpushed commits")
        if isinstance(behind, int) and behind > 0:
            failures.append(f"{label.replace('_branch_sync', '')} is behind its upstream")

    payload = {
        "ok": not failures,
        "checks": checks,
        "failures": failures,
    }
    print(json.dumps(payload, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
