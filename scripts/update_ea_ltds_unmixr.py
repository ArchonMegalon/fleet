#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import pathlib
import re
import sys


EA_LTDS_PATH = pathlib.Path("/docker/EA/LTDs.md")

APPSUMO_ROW = (
    "| `Unmixr AI` | `License Tier 4` | `1 license` | `Activated` |  | `Tier 3` | None | "
    "Tracked LTD only; no local runtime integration yet. |"
)

DISCOVERY_ROW = (
    "| `Unmixr AI` |  | `missing` | `manual_inventory` |  | No BrowserAct discovery run recorded yet. |"
)


def replace_or_insert_row(text: str, service_name: str, row: str, *, before_service: str) -> str:
    pattern = re.compile(rf"^\| `{re.escape(service_name)}` \|.*$", re.MULTILINE)
    if pattern.search(text):
        return pattern.sub(row, text, count=1)
    anchor = f"| `{before_service}` |"
    if anchor in text:
        return text.replace(anchor, row + "\n" + anchor, 1)
    return text


def main() -> int:
    if not EA_LTDS_PATH.exists():
        print(f"missing file: {EA_LTDS_PATH}", file=sys.stderr)
        return 1

    text = EA_LTDS_PATH.read_text(encoding="utf-8")
    today = dt.date.today().isoformat()

    text = re.sub(r"^Updated:\s+\d{4}-\d{2}-\d{2}$", f"Updated: {today}", text, count=1, flags=re.MULTILINE)
    text = re.sub(r"- `\d+` total LTD products tracked", "- `22` total LTD products tracked", text, count=1)

    text = replace_or_insert_row(text, "Unmixr AI", APPSUMO_ROW, before_service="Vizologi")
    text = replace_or_insert_row(text, "Unmixr AI", DISCOVERY_ROW, before_service="Vizologi")

    EA_LTDS_PATH.write_text(text, encoding="utf-8")
    print(f"updated {EA_LTDS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
