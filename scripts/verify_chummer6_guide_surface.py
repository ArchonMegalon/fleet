#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


EA_SCRIPTS_DIR = Path("/docker/EA/scripts")
if str(EA_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(EA_SCRIPTS_DIR))

from chummer6_guide_canon import canonical_horizon_slugs, canonical_part_slugs


GUIDE_REPO = Path("/docker/chummercomplete/Chummer6")
FORBIDDEN_ROOT_PATHS = {
    "WHERE_THE_REAL_TRUTH_LIVES.md",
    "VISION.md",
    "ROADMAP.md",
    "ARCHITECTURE.md",
    "WORKLIST.md",
    "CONTRACT_SETS.yaml",
    "GROUP_BLOCKERS.md",
    "runtime-instructions.generated.md",
    "QUEUE.generated.yaml",
}
FORBIDDEN_DIRS = {"scripts", "src", "tests"}
LEGACY_PART_FILES = {
    "PARTS/fleet.md",
    "PARTS/presentation.md",
    "PARTS/play.md",
    "PARTS/run-services.md",
}
REQUIRED_ROOT_FILES = {
    "README.md",
    "START_HERE.md",
    "WHAT_CHUMMER6_IS.md",
    "WHERE_TO_GO_DEEPER.md",
    "GLOSSARY.md",
    "FAQ.md",
    "NOW/current-phase.md",
    "NOW/current-status.md",
    "NOW/public-surfaces.md",
    "PARTS/README.md",
    "HORIZONS/README.md",
}


def markdown_stems(root: Path) -> set[str]:
    if not root.exists():
        return set()
    return {path.stem for path in root.glob("*.md") if path.is_file() and path.name != "README.md"}


def verify_repo(root: Path = GUIDE_REPO) -> dict[str, object]:
    required = sorted(REQUIRED_ROOT_FILES)
    missing_required = [rel for rel in required if not (root / rel).exists()]
    if missing_required:
        raise FileNotFoundError(f"missing required guide files: {missing_required}")

    canonical_parts = canonical_part_slugs()
    missing_parts = [slug for slug in canonical_parts if not (root / "PARTS" / f"{slug}.md").exists()]
    if missing_parts:
        raise FileNotFoundError(f"missing canonical part pages: {missing_parts}")
    extra_parts = sorted(markdown_stems(root / "PARTS") - set(canonical_parts))
    if extra_parts:
        raise RuntimeError(f"non-canonical part pages still present: {extra_parts}")

    canonical_horizons = canonical_horizon_slugs()
    missing_horizons = [slug for slug in canonical_horizons if not (root / "HORIZONS" / f"{slug}.md").exists()]
    if missing_horizons:
        raise FileNotFoundError(f"missing canonical horizon pages: {missing_horizons}")
    extra_horizons = sorted(markdown_stems(root / "HORIZONS") - set(canonical_horizons))
    if extra_horizons:
        raise RuntimeError(f"non-canonical horizon pages still present: {extra_horizons}")

    updates = sorted(path.name for path in (root / "UPDATES").glob("*.md") if path.is_file())
    if not updates:
        raise FileNotFoundError("guide repo is missing update log pages under UPDATES/")

    forbidden_existing = sorted(
        rel for rel in FORBIDDEN_ROOT_PATHS | LEGACY_PART_FILES if (root / rel).exists()
    )
    if forbidden_existing:
        raise RuntimeError(f"forbidden guide paths still present: {forbidden_existing}")

    forbidden_dirs = sorted(name for name in FORBIDDEN_DIRS if (root / name).exists())
    if forbidden_dirs:
        raise RuntimeError(f"forbidden guide directories still present: {forbidden_dirs}")

    return {
        "parts": canonical_parts,
        "horizons": canonical_horizons,
        "updates": updates,
    }


def main() -> int:
    result = verify_repo()
    print(
        "guide surface verified:",
        f"parts={len(result['parts'])}",
        f"horizons={len(result['horizons'])}",
        f"updates={len(result['updates'])}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
