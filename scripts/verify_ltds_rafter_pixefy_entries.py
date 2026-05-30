#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

from rafter_pixefy_common import COMPLETION, ROOT, now_utc, write_json


def main() -> int:
    ltds = ROOT / "LTDs.md"
    text = ltds.read_text(encoding="utf-8") if ltds.exists() else ""
    failures: list[str] = []
    if "`Rafter`" not in text:
        failures.append("rafter_row_missing")
    if "`Pixefy`" not in text:
        failures.append("pixefy_row_missing")
    if "PixiFy" in text:
        failures.append("pixefy_misspelled_as_pixify")
    for service in ("Rafter", "Pixefy"):
        marker = f"| `{service}` |"
        row = next((line for line in text.splitlines() if line.startswith(marker)), "")
        if not row:
            continue
        if "`Tier 1`" in row or "`Tier 2`" in row:
            failures.append(f"{service.lower()}_promoted_above_tier3_before_provider_verification")
        forbidden_ready = ("runtime-ready", "runtime ready", "release-ready", "gold ready", "wired")
        if any(token in row.lower() for token in forbidden_ready):
            failures.append(f"{service.lower()}_row_claims_runtime_ready_without_proof")
    if text.count("| `Rafter` |") != 1:
        failures.append("rafter_row_count_not_one")
    if text.count("| `Pixefy` |") != 1:
        failures.append("pixefy_row_count_not_one")

    updated = now_utc()
    write_json(COMPLETION / "ltd_inventory" / "RAFTER_TIER3_LTDS_ENTRY.generated.json", {
        "service": "Rafter",
        "plan": "License Tier 3 / highest AppSumo tier",
        "holding": "1 account",
        "status": "Owned" if "`Rafter`" in text else "missing",
        "workspace_integration_tier": "Tier 3",
        "runtime_status": "not_wired",
        "provider_verification_status": "pending",
        "release_gate_status": "not_ready",
        "source": "user_reported",
        "updated_at_utc": updated,
        "gold_claim_allowed": False,
        "verification_status": "pass" if not failures else "fail",
        "failures": [f for f in failures if f.startswith("rafter")],
    })
    write_json(COMPLETION / "ltd_inventory" / "PIXEFY_TIER3_LTDS_ENTRY.generated.json", {
        "service": "Pixefy",
        "plan": "License Tier 3 / highest AppSumo tier",
        "holding": "1 account",
        "status": "Owned" if "`Pixefy`" in text else "missing",
        "workspace_integration_tier": "Tier 3",
        "runtime_status": "not_wired",
        "provider_verification_status": "pending",
        "release_gate_status": "not_ready",
        "source": "user_reported",
        "updated_at_utc": updated,
        "gold_claim_allowed": False,
        "verification_status": "pass" if not failures else "fail",
        "failures": [f for f in failures if f.startswith("pixefy")],
    })
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print("Rafter/Pixefy LTD inventory entries verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
