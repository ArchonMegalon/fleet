#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


FLEET_ROOT = Path("/docker/fleet")
SOURCE = FLEET_ROOT / "feedback" / "2026-03-18-chummer-horizons-and-fleet-milestone-drift-reaudit.md"
TARGET = FLEET_ROOT / "state" / "groups" / "chummer-vnext" / "feedback" / SOURCE.name


def main() -> None:
    content = SOURCE.read_text(encoding="utf-8")
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(content, encoding="utf-8")
    print(TARGET)


if __name__ == "__main__":
    main()
