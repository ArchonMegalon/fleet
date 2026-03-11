#!/usr/bin/env python3
from __future__ import annotations

import json
import pathlib
import sys

import yaml


DESIGN_ROOT = pathlib.Path("/docker/chummercomplete/chummer-design")
PLAY_ROOT = pathlib.Path("/docker/chummercomplete/chummer-play")
PRODUCT_ROOT = DESIGN_ROOT / "products" / "chummer"

ORPHAN_ROOT_PATHS = [
    DESIGN_ROOT / "BOUNDARIES_AND_CONTRACTS.md",
    DESIGN_ROOT / "VISION_AND_MILESTONES.md",
    DESIGN_ROOT / "chummer-media-factory.design.v1.md",
    DESIGN_ROOT / "chummer-media-factory",
]


def load_text(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


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
    checks["media_factory_in_product_readme"] = "chummer-media-factory" in readme_text
    checks["media_factory_in_sync_manifest"] = "chummer-media-factory" in mirror_repos
    checks["play_in_sync_manifest"] = "chummer-play" in mirror_repos
    checks["play_repo_mirror_present"] = (PLAY_ROOT / ".codex-design" / "product").exists()
    checks["play_repo_scope_present"] = (PLAY_ROOT / ".codex-design" / "repo" / "IMPLEMENTATION_SCOPE.md").exists()
    checks["orphan_root_paths_present"] = [str(path) for path in ORPHAN_ROOT_PATHS if path.exists()]

    if not checks["product_root_exists"]:
        failures.append(f"missing canonical product root: {PRODUCT_ROOT}")
    if not checks["media_factory_in_product_readme"]:
        failures.append("products/chummer/README.md does not include chummer-media-factory")
    if not checks["media_factory_in_sync_manifest"]:
        failures.append("sync-manifest.yaml does not mirror chummer-media-factory")
    if not checks["play_in_sync_manifest"]:
        failures.append("sync-manifest.yaml does not mirror chummer-play")
    if not checks["play_repo_mirror_present"]:
        failures.append("chummer-play is missing .codex-design/product mirror content")
    if not checks["play_repo_scope_present"]:
        failures.append("chummer-play is missing .codex-design/repo/IMPLEMENTATION_SCOPE.md")
    if checks["orphan_root_paths_present"]:
        failures.append("chummer-design still has orphan product docs at repo root")

    payload = {
        "ok": not failures,
        "checks": checks,
        "failures": failures,
    }
    print(json.dumps(payload, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
