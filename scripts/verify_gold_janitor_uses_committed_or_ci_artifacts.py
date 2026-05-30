#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "final_gold_janitor.py"
FORBIDDEN = (
    "/docker/chummercomplete/_completion/full_product_reaudit_v16",
    'Path("/docker/chummercomplete")',
    "WORKSPACE = Path",
)


def main() -> int:
    text = SCRIPT.read_text(encoding="utf-8")
    hits = [item for item in FORBIDDEN if item in text]
    if hits:
        print("gold janitor still uses local-only gate roots: " + ", ".join(hits))
        return 1
    if 'ROOT / "_completion" / "full_product_reaudit_v17"' not in text:
        print("gold janitor does not use repo-relative V17 artifact root")
        return 1
    if '"ls-files"' not in text or "--error-unmatch" not in text:
        print("gold janitor does not verify git-tracked durable artifacts")
        return 1
    print("gold janitor durable artifact policy passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
