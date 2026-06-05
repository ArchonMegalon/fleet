#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

from rafter_pixefy_common import now_utc, write_json


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "_completion" / "full_product_reaudit_v18"
STATUS_URL = "https://chummer.run/status"
DOWNLOADS_URL = "https://chummer.run/downloads"
HOME_URL = "https://chummer.run/"
RELEASE_CHANNEL_URL = "https://chummer.run/downloads/RELEASE_CHANNEL.generated.json"
RELEASES_URL = "https://chummer.run/downloads/releases.json"


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "chummer-v17-release-gate/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", "ignore")


def text_only(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def main() -> int:
    status_html = fetch(STATUS_URL)
    downloads_html = fetch(DOWNLOADS_URL)
    home_html = fetch(HOME_URL)
    release_channel = json.loads(fetch(RELEASE_CHANNEL_URL))
    releases = json.loads(fetch(RELEASES_URL))
    status_text = text_only(status_html)
    downloads_text = text_only(downloads_html)
    home_text = text_only(home_html)
    status_lower = status_text.lower()
    downloads_lower = downloads_text.lower()
    home_lower = home_text.lower()
    release_channel_version = str(release_channel.get("version") or "").strip()
    releases_version = str(releases.get("version") or "").strip()
    build_match = re.search(r"run-\d{8}-\d{6}", status_text)
    stale_hits = [
        phrase
        for phrase in (
            "proof freshness is missing",
            "proof freshness missing",
            "proof is stale",
            "missing or stale",
            "not gold-ready",
            "not gold ready",
            "review-required",
            "incomplete",
            "unavailable",
            "preview channel",
            "current preview channel",
            "preview posture",
            "public archive preview",
            "still manual",
        )
        if phrase in status_lower
    ]
    downloads_caution_hits = [
        phrase
        for phrase in (
            "load demo runner",
            "demo runner",
            "preview channel",
            "public archive preview",
            "still manual",
            "archive package",
        )
        if phrase in downloads_lower
    ]
    home_caution_hits = [
        phrase
        for phrase in (
            "mobile play shell preview",
            "preview",
        )
        if phrase in home_lower
    ]
    home_black_ledger_first = "black ledger" in home_lower[:2200] and "faction" in home_lower[:2200]
    reasons = []
    if stale_hits:
        reasons.append("status_caution_hits:" + ",".join(stale_hits))
    if downloads_caution_hits:
        reasons.append("downloads_caution_hits:" + ",".join(downloads_caution_hits))
    if home_caution_hits:
        reasons.append("home_caution_hits:" + ",".join(home_caution_hits))
    if not home_black_ledger_first:
        reasons.append("home_not_black_ledger_first")
    if not build_match:
        reasons.append("status_build_id_missing")
    elif release_channel_version and build_match.group(0) != release_channel_version:
        reasons.append(f"status_build_mismatch:{build_match.group(0)}!={release_channel_version}")
    if not release_channel_version:
        reasons.append("release_channel_version_missing")
    if not releases_version:
        reasons.append("releases_version_missing")
    elif release_channel_version and releases_version != release_channel_version:
        reasons.append(f"downloads_version_mismatch:{releases_version}!={release_channel_version}")
    if str(release_channel.get("rolloutState") or "").strip() != "public_stable":
        reasons.append("release_channel_not_public_stable")
    if str(release_channel.get("supportabilityState") or "").strip() != "gold_supported":
        reasons.append("release_channel_not_gold_supported")
    status = "pass" if not reasons else "fail"
    matrix = {
        "generated_at_utc": now_utc(),
        "status": status,
        "base_url": "https://chummer.run",
        "live_sources": {
            "home_url": HOME_URL,
            "status_url": STATUS_URL,
            "downloads_url": DOWNLOADS_URL,
            "release_channel_url": RELEASE_CHANNEL_URL,
            "releases_url": RELEASES_URL,
        },
        "checks": {
            "release_channel_version": release_channel_version,
            "releases_version": releases_version,
            "status_has_build_id": bool(build_match),
            "build_id": build_match.group(0) if build_match else "",
            "status_stale_or_not_gold_hits": stale_hits,
            "downloads_caution_hits": downloads_caution_hits,
            "home_caution_hits": home_caution_hits,
            "home_black_ledger_first": home_black_ledger_first,
            "gold_claim_allowed": status == "pass",
            "supportability_state": "gold_supported" if status == "pass" else "not_gold",
        },
        "reasons": reasons,
    }
    alignment = {
        "generated_at_utc": matrix["generated_at_utc"],
        "status": status,
        "public_host": "chummer.run",
        "status_url": STATUS_URL,
        "downloads_url": DOWNLOADS_URL,
        "release_channel_url": RELEASE_CHANNEL_URL,
        "releases_url": RELEASES_URL,
        "contains_stale_or_not_gold_language": bool(stale_hits),
        "contains_downloads_caution_language": bool(downloads_caution_hits),
        "contains_home_caution_language": bool(home_caution_hits),
        "build_id": matrix["checks"]["build_id"],
        "release_channel_version": release_channel_version,
        "releases_version": releases_version,
        "status_text_sample": status_text[:800],
        "downloads_text_sample": downloads_text[:800],
        "home_text_sample": home_text[:800],
        "reasons": reasons,
    }
    write_json(OUT / "LIVE_BACKED_RELEASE_TRUTH_MATRIX.generated.json", matrix)
    write_json(OUT / "LIVE_STATUS_RELEASE_ALIGNMENT.generated.json", alignment)
    print(status)
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
