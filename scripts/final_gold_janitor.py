#!/usr/bin/env python3
from __future__ import annotations

import sys

from pathlib import Path

from rafter_pixefy_common import COMPLETION, now_utc, write_json


WORKSPACE = Path("/docker/chummercomplete")
V16 = WORKSPACE / "_completion" / "full_product_reaudit_v16"

REQUIRED_GATES = {
    "RELEASE_TRUTH_MATRIX.generated.json": "json_pass",
    "LIVE_STATUS_RELEASE_ALIGNMENT.generated.json": "json_pass",
    "LIVE_CHUMMER_RUN_ROUTE_PROOF.generated.json": "json_pass",
    "CLASSIC_FORMPORT_FUNCTIONAL_PARITY_AUDIT.generated.json": "json_pass",
    "FINAL_SR4_RULE_AUTHORITY_VERDICT.md": "SR4_RULE_AUTHORITY_READY",
    "FINAL_SR5_RULE_AUTHORITY_VERDICT.md": "SR5_RULE_AUTHORITY_READY",
    "FINAL_SR6_RULE_AUTHORITY_VERDICT.md": "SR6_RULE_AUTHORITY_READY",
    "FINAL_MAGICFIT_PROVIDER_ADAPTER_VERDICT.md": "MAGICFIT_PROVIDER_ADAPTER_READY",
    "FINAL_RAFTER_PIXEFY_QA_STACK_VERDICT.md": "RAFTER_PIXEFY_QA_STACK_READY",
    "FINAL_BLACK_LEDGER_VIDEO_GLOBE_VERDICT.md": "BLACK_LEDGER_VIDEO_GLOBE_READY",
    "FINAL_FACTION_VIDEO_SERIES_VERDICT.md": "FACTION_VIDEO_SERIES_READY",
    "FINAL_BLACK_LEDGER_NEWSROOM_VERDICT.md": "BLACK_LEDGER_NEWSROOM_READY",
    "FINAL_PWA_GOLD_VERDICT.md": "GOLD_READY",
    "FINAL_TABLE_PULSE_OPTOUT_REMOTE_REACTION_VERDICT.md": "GOLD_READY",
}


def read_json_status(path: Path) -> str:
    if not path.is_file():
        return "missing"
    import json

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "invalid_json"
    return str(payload.get("status") or "missing")


def gate_pass(path: Path, expected: str) -> bool:
    if expected == "json_pass":
        return read_json_status(path) == "pass"
    return path.is_file() and expected in path.read_text(encoding="utf-8")


def main() -> int:
    gate_results = {}
    for name, expected in REQUIRED_GATES.items():
        path = V16 / name
        gate_results[name] = {
            "required": True,
            "path": str(path),
            "expected": expected,
            "exists": path.is_file(),
            "status": read_json_status(path) if expected == "json_pass" else ("present" if path.is_file() else "missing"),
            "pass": gate_pass(path, expected),
        }
    missing = [name for name, result in gate_results.items() if not result["exists"]]
    failing = [name for name, result in gate_results.items() if result["exists"] and not result["pass"]]
    reasons = [f"missing:{name}" for name in missing] + [f"failing:{name}" for name in failing]
    final = "GOLD_READY" if not missing and not failing else "NOT_GOLD"
    write_json(COMPLETION / "FINAL_GOLD_JANITOR.generated.json", {
        "generated_at_utc": now_utc(),
        "status": "pass" if final == "GOLD_READY" else "fail",
        "verdict": final,
        "scope": "full_estate_v16",
        "required_gates": gate_results,
        "missing_gates": missing,
        "failing_gates": failing,
        "reasons": reasons,
    })
    print(final)
    return 0 if final == "GOLD_READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
