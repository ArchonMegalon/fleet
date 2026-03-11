#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


DESIGN_ROOT = Path("/docker/chummercomplete/chummer-design")
PRODUCT_ROOT = DESIGN_ROOT / "products" / "chummer"

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
    for root in [DESIGN_ROOT]:
        for rel in ["README.md", "WORKLIST.md"]:
            candidate = root / rel
            if candidate.exists():
                files.append(candidate)
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
    for path in target_files():
        original = path.read_text(encoding="utf-8")
        updated = rewrite(original)
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            changed.append(str(path))
    for item in changed:
        print(item)
    print(f"changed_files={len(changed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
