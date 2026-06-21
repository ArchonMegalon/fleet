#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "final_gold_janitor.py"
FORBIDDEN = (
    "/docker/chummercomplete/_completion/full_product_reaudit_v16",
    'Path("/docker/chummercomplete")',
    "WORKSPACE = Path",
    'Path("/docker/',
    "Path('/docker/",
    "full_product_reaudit_v18",
)


def main() -> int:
    text = SCRIPT.read_text(encoding="utf-8")
    hits = [item for item in FORBIDDEN if item in text]
    if hits:
        print("gold janitor still uses local-only gate roots: " + ", ".join(hits))
        return 1
    for required in (
        "CHUMMER_COMPLETION_ROOT",
        "CHUMMER_FINAL_GOLD_ARTIFACT_ROOT",
        "full_product_reaudit_v20",
        "_latest_reaudit_dir",
    ):
        if required not in text:
            print(f"gold janitor does not expose current proof-root discovery: {required}")
            return 1
    if 'ROOT / "_completion" / DEFAULT_REAUDIT_ROOT_NAME' not in text:
        print("gold janitor does not fail closed to the current configured proof root")
        return 1
    if '"ls-files"' not in text or "--error-unmatch" not in text:
        print("gold janitor does not verify git-tracked durable artifacts")
        return 1
    if "sha256_mismatch" not in text or "forbidden_absolute_path" not in text:
        print("gold janitor does not enforce SHA256 and local absolute path rejection")
        return 1
    print("gold janitor durable artifact policy passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
