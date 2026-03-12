#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import pathlib
import re
import sys


EA_LTDS_PATH = pathlib.Path("/docker/EA/LTDs.md")

ONEMIN_ROW = (
    "| `1min.AI` | `Advanced Business Plan` | `3 licenses / 3 accounts` | `Owned` |  | `Tier 1` | "
    "Local `.env` key rotation slots plus `scripts/resolve_onemin_ai_key.sh` | "
    "Three-account holding; primary and fallback API-key flow is wired locally and kept out of git. |"
)

DISCOVERY_ROW = (
    "| `1min.AI` |  | `manual_seeded` | `local_env` |  | "
    "API-key rotation slots exist locally for a 3-account holding; account emails are still not documented here. |"
)


def replace_first(text: str, pattern: str, replacement: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    return updated if count else text


def main() -> int:
    if not EA_LTDS_PATH.exists():
        print(f"missing file: {EA_LTDS_PATH}", file=sys.stderr)
        return 1

    text = EA_LTDS_PATH.read_text(encoding="utf-8")
    today = dt.date.today().isoformat()

    text = replace_first(text, r"^Updated:\s+\d{4}-\d{2}-\d{2}$", f"Updated: {today}")
    text = replace_first(
        text,
        r"^\| `1min\.AI` \|.*$",
        ONEMIN_ROW,
    )
    text = replace_first(
        text,
        r"^- Multiple-account holding: `1min\.AI` \(`\d+ licenses / \d+ accounts`\)$",
        "- Multiple-account holding: `1min.AI` (`3 licenses / 3 accounts`)",
    )
    text = replace_first(
        text,
        r"^\| `1min\.AI` \|  \| `manual_seeded` \| `local_env` \|  \|.*$",
        DISCOVERY_ROW,
    )

    EA_LTDS_PATH.write_text(text, encoding="utf-8")
    print(f"updated {EA_LTDS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
