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


def upsert_row_in_section(text: str, section_header: str, service_name: str, row: str, *, before_service: str) -> str:
    start = text.find(section_header)
    if start < 0:
        return text
    next_heading = text.find("\n## ", start + len(section_header))
    if next_heading < 0:
        next_heading = len(text)
    section = text[start:next_heading]
    pattern = re.compile(rf"^\| `{re.escape(service_name)}` \|.*$", re.MULTILINE)
    if pattern.search(section):
        section = pattern.sub(row, section, count=1)
    else:
        anchor = f"| `{before_service}` |"
        if anchor in section:
            section = section.replace(anchor, row + "\n" + anchor, 1)
    return text[:start] + section + text[next_heading:]


def main() -> int:
    if not EA_LTDS_PATH.exists():
        print(f"missing file: {EA_LTDS_PATH}", file=sys.stderr)
        return 1

    text = EA_LTDS_PATH.read_text(encoding="utf-8")
    today = dt.date.today().isoformat()

    text = re.sub(r"^Updated:\s+\d{4}-\d{2}-\d{2}$", f"Updated: {today}", text, count=1, flags=re.MULTILINE)
    text = re.sub(r"- `\d+` total LTD products tracked", "- `22` total LTD products tracked", text, count=1)

    text = upsert_row_in_section(text, "## AppSumo LTDs", "Unmixr AI", APPSUMO_ROW, before_service="Vizologi")
    text = upsert_row_in_section(text, "## Discovery Tracking", "Unmixr AI", DISCOVERY_ROW, before_service="Vizologi")

    EA_LTDS_PATH.write_text(text, encoding="utf-8")
    print(f"updated {EA_LTDS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
