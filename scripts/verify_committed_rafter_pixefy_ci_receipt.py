#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

PROVIDERS = {
    "Rafter": {
        "provider_path": ROOT / "_completion" / "rafter" / "RAFTER_PROVIDER_VERIFICATION.generated.json",
        "gate_path": ROOT / "_completion" / "rafter" / "RAFTER_SECURITY_GOLD_GATE.generated.json",
        "provider_status": "verified",
        "gate_status": "pass",
        "gate_name": "RAFTER_SECURITY_GOLD_GATE",
    },
    "Pixefy": {
        "provider_path": ROOT / "_completion" / "pixefy" / "PIXEFY_PROVIDER_VERIFICATION.generated.json",
        "gate_path": ROOT / "_completion" / "pixefy" / "PIXEFY_RESPONSIVE_VISUAL_QA.generated.json",
        "provider_status": "verified",
        "gate_status": "pass",
        "gate_name": "PIXEFY_RESPONSIVE_VISUAL_QA",
    },
}


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"missing receipt: {path.relative_to(ROOT)}") from None
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid receipt json: {path.relative_to(ROOT)}: {exc}") from None
    if not isinstance(payload, dict):
        raise SystemExit(f"receipt must be a JSON object: {path.relative_to(ROOT)}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify committed Rafter/Pixefy CI receipts without local provider secrets.")
    parser.add_argument("provider", choices=sorted(PROVIDERS))
    args = parser.parse_args()

    spec = PROVIDERS[args.provider]
    provider = load_json(spec["provider_path"])
    gate = load_json(spec["gate_path"])
    failures: list[str] = []

    if str(provider.get("service") or "").strip() != args.provider:
        failures.append("provider_service_mismatch")
    if str(provider.get("status") or "").strip().lower() != spec["provider_status"]:
        failures.append("provider_not_verified")
    if provider.get("failures"):
        failures.append("provider_receipt_has_failures")
    if str(gate.get("gate") or "").strip() != spec["gate_name"]:
        failures.append("gate_name_mismatch")
    if str(gate.get("status") or "").strip().lower() != spec["gate_status"]:
        failures.append("gate_not_pass")
    if gate.get("failures"):
        failures.append("gate_receipt_has_failures")
    if not str(gate.get("generated_at_utc") or gate.get("generated_at") or "").strip():
        failures.append("gate_missing_generation_timestamp")

    if failures:
        print(f"{args.provider} committed CI receipt failed: {', '.join(failures)}", file=sys.stderr)
        return 1
    print(f"{args.provider} committed CI receipt verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
