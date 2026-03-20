#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from chummer6_design_canon import (
    canonical_horizon_slugs,
    canonical_part_slugs,
    load_faq_canon,
    load_help_canon,
    load_page_registry,
)


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
    "DOWNLOAD.md",
    "START_HERE.md",
    "WHAT_CHUMMER6_IS.md",
    "WHERE_TO_GO_DEEPER.md",
    "HOW_CAN_I_HELP.md",
    "GLOSSARY.md",
    "FAQ.md",
    "NOW/current-phase.md",
    "NOW/current-status.md",
    "NOW/public-surfaces.md",
    "PARTS/README.md",
    "HORIZONS/README.md",
    "UPDATES/README.md",
}
SUPPORT_PAGE_TOKENS = {"booster", "participate/codex", "review"}
README_SUPPORT_TOKENS = {"## How can I help?", "HOW_CAN_I_HELP.md", "participate/codex"}
README_UPDATES_TOKENS = {"## What Changed Lately", "UPDATES/README.md"}


def markdown_stems(root: Path) -> set[str]:
    if not root.exists():
        return set()
    return {path.stem for path in root.glob("*.md") if path.is_file() and path.name != "README.md"}


def verify_repo(root: Path = GUIDE_REPO) -> dict[str, object]:
    page_registry = load_page_registry()
    faq_registry = load_faq_canon()
    help_copy = load_help_canon()
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

    updates = sorted(
        path.name
        for path in (root / "UPDATES").glob("*.md")
        if path.is_file() and path.name != "README.md"
    )
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

    readme_text = (root / "README.md").read_text(encoding="utf-8")
    missing_readme_support = sorted(token for token in README_SUPPORT_TOKENS if token not in readme_text)
    if missing_readme_support:
        raise RuntimeError(f"README.md is missing support/help guidance: {missing_readme_support}")
    missing_readme_updates = sorted(token for token in README_UPDATES_TOKENS if token not in readme_text)
    if missing_readme_updates:
        raise RuntimeError(f"README.md is missing recent-update guidance: {missing_readme_updates}")

    updates_index_text = (root / "UPDATES" / "README.md").read_text(encoding="utf-8")
    for needle in ("Latest substantial pushes", "Monthly archive"):
        if needle not in updates_index_text:
            raise RuntimeError(f"UPDATES/README.md is missing required change-log section: {needle}")

    download_text = (root / "DOWNLOAD.md").read_text(encoding="utf-8")
    for needle in ("## Current build matrix", "SHA256", "GitHub releases"):
        if needle not in download_text:
            raise RuntimeError(f"DOWNLOAD.md is missing required release-shelf guidance: {needle}")

    support_text = (root / "HOW_CAN_I_HELP.md").read_text(encoding="utf-8").lower()
    missing_support_tokens = sorted(token for token in SUPPORT_PAGE_TOKENS if token not in support_text)
    if missing_support_tokens:
        raise RuntimeError(f"HOW_CAN_I_HELP.md is missing support tokens: {missing_support_tokens}")
    for expected in ("cheap baseline", "free later"):
        if expected not in support_text:
            raise RuntimeError(f"HOW_CAN_I_HELP.md is missing public help concept: {expected}")

    faq_text = (root / "FAQ.md").read_text(encoding="utf-8")
    missing_questions = sorted(
        str(entry.get("question") or "").strip()
        for section in faq_registry.values()
        for entry in section.get("entries") or []
        if isinstance(entry, dict)
        and bool(entry.get("required"))
        and str(entry.get("question") or "").strip()
        and str(entry.get("question") or "").strip() not in faq_text
    )
    if missing_questions:
        raise RuntimeError(f"FAQ.md is missing required questions: {missing_questions}")

    part_page_rules = ((page_registry.get("page_types") or {}).get("part_page") or {})
    forbidden_terms = [
        str(term).strip().lower()
        for term in (part_page_rules.get("forbidden_terms") or [])
        if str(term).strip()
    ]
    for slug in canonical_parts:
        page_text = (root / "PARTS" / f"{slug}.md").read_text(encoding="utf-8").lower()
        leaked = [term for term in forbidden_terms if term in page_text]
        if leaked:
            raise RuntimeError(f"part page leaked internal terms ({slug}): {leaked}")

    first_contact_terms = []
    for page_type in ("root_story", "help_page"):
        rules = ((page_registry.get("page_types") or {}).get(page_type) or {})
        first_contact_terms.extend(
            str(term).strip().lower()
            for term in (rules.get("forbidden_terms") or [])
            if str(term).strip()
        )
    if first_contact_terms:
        for rel in ("README.md", "START_HERE.md", "WHAT_CHUMMER6_IS.md", "HOW_CAN_I_HELP.md"):
            text = (root / rel).read_text(encoding="utf-8").lower()
            leaked = [term for term in first_contact_terms if term in text]
            if leaked:
                raise RuntimeError(f"first-contact page leaked operator jargon ({rel}): {leaked}")

    help_bullets = [str(line).strip().lower() for line in (help_copy.get("privacy_and_review_safety") or []) if str(line).strip()]
    for bullet in help_bullets:
        if bullet and bullet not in support_text:
            raise RuntimeError(f"HOW_CAN_I_HELP.md is missing required help bullet: {bullet}")

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
