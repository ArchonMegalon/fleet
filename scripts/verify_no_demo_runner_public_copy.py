#!/usr/bin/env python3
from __future__ import annotations

import argparse
import urllib.request


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "chummer-v17-release-gate/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", "ignore")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="https://chummer.run/downloads")
    args = parser.parse_args()
    body = fetch(args.url)
    if "Load Demo Runner" in body or "Demo Runner" in body:
        print("demo runner public copy found")
        return 1
    print("no demo runner public copy found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
