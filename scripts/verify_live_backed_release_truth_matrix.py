#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

from rafter_pixefy_common import now_utc, write_json


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "_completion" / "full_product_reaudit_v17"
STATUS_URL = "https://chummer.run/status"
DOWNLOADS_URL = "https://chummer.run/downloads"


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "chummer-v17-release-gate/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", "ignore")


def text_only(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def main() -> int:
    status_html = fetch(STATUS_URL)
    downloads_html = fetch(DOWNLOADS_URL)
    status_text = text_only(status_html)
    downloads_text = text_only(downloads_html)
    status_lower = status_text.lower()
    downloads_lower = downloads_text.lower()
    stale_hits = [
        phrase
        for phrase in ("proof freshness is missing", "proof freshness missing", "proof is stale", "missing or stale", "not gold-ready", "not gold ready")
        if phrase in status_lower
    ]
    demo_hits = [phrase for phrase in ("load demo runner", "demo runner") if phrase in downloads_lower]
    build_match = re.search(r"run-\d{8}-\d{6}", status_text)
    status = "pass" if not stale_hits and not demo_hits and build_match else "fail"
    matrix = {
        "generated_at_utc": now_utc(),
        "status": status,
        "base_url": "https://chummer.run",
        "live_sources": {
            "status_url": STATUS_URL,
            "downloads_url": DOWNLOADS_URL,
        },
        "checks": {
            "status_has_build_id": bool(build_match),
            "build_id": build_match.group(0) if build_match else "",
            "status_stale_or_not_gold_hits": stale_hits,
            "downloads_demo_runner_hits": demo_hits,
            "gold_claim_allowed": status == "pass",
            "supportability_state": "gold_supported" if status == "pass" else "not_gold",
        },
    }
    alignment = {
        "generated_at_utc": matrix["generated_at_utc"],
        "status": status,
        "public_host": "chummer.run",
        "status_url": STATUS_URL,
        "downloads_url": DOWNLOADS_URL,
        "contains_stale_or_not_gold_language": bool(stale_hits),
        "contains_demo_runner_language": bool(demo_hits),
        "build_id": matrix["checks"]["build_id"],
        "status_text_sample": status_text[:800],
        "downloads_text_sample": downloads_text[:800],
    }
    write_json(OUT / "LIVE_BACKED_RELEASE_TRUTH_MATRIX.generated.json", matrix)
    write_json(OUT / "LIVE_STATUS_RELEASE_ALIGNMENT.generated.json", alignment)
    print(status)
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
