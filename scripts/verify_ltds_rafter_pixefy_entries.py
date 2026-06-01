#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

from rafter_pixefy_common import COMPLETION, ROOT, load_optional_json, now_utc, write_json


PROOF_BY_SERVICE = {
    "Rafter": {
        "provider": COMPLETION / "rafter" / "RAFTER_PROVIDER_VERIFICATION.generated.json",
        "gate": COMPLETION / "rafter" / "RAFTER_SECURITY_GOLD_GATE.generated.json",
        "provider_ready_statuses": {"verified"},
        "gate_ready_statuses": {"pass"},
    },
    "Pixefy": {
        "provider": COMPLETION / "pixefy" / "PIXEFY_PROVIDER_VERIFICATION.generated.json",
        "gate": COMPLETION / "pixefy" / "PIXEFY_RESPONSIVE_VISUAL_QA.generated.json",
        "provider_ready_statuses": {"verified"},
        "gate_ready_statuses": {"pass"},
    },
}


def _status(payload: dict | None) -> str:
    if not payload:
        return ""
    return str(payload.get("status") or payload.get("gate_status") or payload.get("verification_status") or "").strip().lower()


def _service_verified(service: str) -> bool:
    proof = PROOF_BY_SERVICE[service]
    provider_status = _status(load_optional_json(proof["provider"]))
    gate_status = _status(load_optional_json(proof["gate"]))
    return (
        provider_status in proof["provider_ready_statuses"]
        and gate_status in proof["gate_ready_statuses"]
    )


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
    service_verified: dict[str, bool] = {}
    for service in ("Rafter", "Pixefy"):
        marker = f"| `{service}` |"
        row = next((line for line in text.splitlines() if line.startswith(marker)), "")
        service_verified[service] = _service_verified(service)
        if not row:
            continue
        if ("`Tier 1`" in row or "`Tier 2`" in row) and not service_verified[service]:
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
        "provider_verification_status": "verified" if service_verified.get("Rafter") else "pending",
        "release_gate_status": "pass" if service_verified.get("Rafter") else "not_ready",
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
        "provider_verification_status": "verified" if service_verified.get("Pixefy") else "pending",
        "release_gate_status": "pass" if service_verified.get("Pixefy") else "not_ready",
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
