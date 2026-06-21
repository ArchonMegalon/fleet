#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DESIGN_ROOT = Path("/docker/chummercomplete/chummer-design")
PRODUCT_ROOT = DESIGN_ROOT / "products" / "chummer"
MIRROR_PRODUCT_ROOT = ROOT / ".codex-design" / "product"

REPO_NAME_MAP = [
    ("chummer.run-services", "chummer6-hub"),
    ("chummer-core-engine", "chummer6-core"),
    ("chummer-presentation", "chummer6-ui"),
    ("chummer-play", "chummer6-mobile"),
    ("chummer-ui-kit", "chummer6-ui-kit"),
    ("chummer-hub-registry", "chummer6-hub-registry"),
    ("chummer-media-factory", "chummer6-media-factory"),
    ("chummer-design", "chummer6-design"),
]

PATH_REPLACEMENTS = [
    ("/docker/chummercomplete/chummer-media-factory", "/docker/fleet/repos/chummer-media-factory"),
]


def target_files() -> list[Path]:
    files: list[Path] = []
    for pattern in ("**/*.md", "**/*.yaml", "**/*.yml"):
        for candidate in PRODUCT_ROOT.glob(pattern):
            if "feedback" in candidate.parts:
                continue
            if candidate.is_file():
                files.append(candidate)
    seen: set[Path] = set()
    ordered: list[Path] = []
    for file_path in files:
        if file_path not in seen:
            seen.add(file_path)
            ordered.append(file_path)
    return ordered


def rewrite(text: str) -> str:
    updated = text
    for old, new in REPO_NAME_MAP:
        updated = updated.replace(old, new)
    for old, new in PATH_REPLACEMENTS:
        updated = updated.replace(old, new)
    return updated


def main() -> int:
    changed: list[str] = []
    expected_relative_paths: set[Path] = set()
    for path in target_files():
        original = path.read_text(encoding="utf-8")
        updated = rewrite(original)
        relative_path = path.relative_to(PRODUCT_ROOT)
        expected_relative_paths.add(relative_path)
        target = MIRROR_PRODUCT_ROOT / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or target.read_text(encoding="utf-8") != updated:
            target.write_text(updated, encoding="utf-8")
            changed.append(str(target))
        shutil.copystat(path, target)
    for target in MIRROR_PRODUCT_ROOT.glob("**/*"):
        if not target.is_file() or target.suffix.lower() not in {".md", ".yaml", ".yml"}:
            continue
        relative_path = target.relative_to(MIRROR_PRODUCT_ROOT)
        if relative_path in expected_relative_paths:
            continue
        target.unlink()
        changed.append(str(target))
    for item in changed:
        print(item)
    print(f"changed_files={len(changed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
