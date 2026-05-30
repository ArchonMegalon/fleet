#!/usr/bin/env python3
from __future__ import annotations

import argparse
import urllib.request
from pathlib import Path

from rafter_pixefy_common import now_utc, write_json


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "_completion" / "full_product_reaudit_v17" / "LIVE_CHUMMER_RUN_ROUTE_PROOF.generated.json"
ROUTES = [
    "/",
    "/downloads",
    "/status",
    "/ledger",
    "/ledger/map",
    "/ledger/factions",
    "/ledger/newsroom",
    "/play",
    "/mobile",
    "/help",
    "/feedback",
    "/feedback/operations",
    "/karma-forge",
    "/participate/karma-forge",
    "/proofs/mac-codex-release/HUB_LOCAL_RELEASE_PROOF.generated.json",
]


def probe(url: str) -> dict[str, object]:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "chummer-v17-route-proof/1.0"})
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read(250_000).decode("utf-8", "ignore")
            lowered = body.lower()
            return {
                "url": url,
                "status_code": int(response.status),
                "ok": 200 <= int(response.status) < 400,
                "body_bytes_sampled": len(body.encode("utf-8")),
                "demo_runner_hit": "demo runner" in lowered or "load demo runner" in lowered,
            }
    except Exception as exc:
        return {"url": url, "status_code": None, "ok": False, "error": f"{type(exc).__name__}: {exc}", "demo_runner_hit": False}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    base = "https://chummer.run"
    results = [probe(base + path) for path in ROUTES]
    failed = [row for row in results if not row.get("ok")]
    demo = [row for row in results if row.get("demo_runner_hit")]
    status = "pass" if not failed and not demo else "fail"
    payload = {
        "generated_at_utc": now_utc(),
        "status": status,
        "base_url": base,
        "public_host": "chummer.run",
        "strict_positive": bool(args.strict),
        "route_count": len(results),
        "failed_count": len(failed),
        "failed_paths": [str(row["url"]).replace(base, "") for row in failed],
        "demo_runner_paths": [str(row["url"]).replace(base, "") for row in demo],
        "routes": results,
    }
    write_json(OUT, payload)
    print(status)
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
