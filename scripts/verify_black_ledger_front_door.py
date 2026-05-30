#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import urllib.request


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "chummer-v18-black-ledger-gate/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", "ignore")


def text_only(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="https://chummer.run/")
    args = parser.parse_args()
    html = fetch(args.url)
    text = text_only(html).lower()
    first_window = text[:2200]
    required = ["black ledger", "city", "faction"]
    missing = [token for token in required if token not in first_window]
    if "explainable shadowrun" in first_window:
        missing.append("generic_explainable_shadowrun_hero")
    if missing:
        print("black ledger front door failed: " + ", ".join(missing))
        return 1
    print("black ledger front door passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
