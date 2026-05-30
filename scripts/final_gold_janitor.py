#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from rafter_pixefy_common import COMPLETION, now_utc, write_json


ROOT = Path(__file__).resolve().parents[1]
V17 = ROOT / "_completion" / "full_product_reaudit_v17"

REQUIRED_GATES = {
    "LIVE_BACKED_RELEASE_TRUTH_MATRIX.generated.json": "json_pass",
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


def rel(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT.resolve()))


def read_json_status(path: Path) -> str:
    if not path.is_file():
        return "missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "invalid_json"
    return str(payload.get("status") or "missing")


def gate_pass(path: Path, expected: str) -> bool:
    if expected == "json_pass":
        return read_json_status(path) == "pass"
    return path.is_file() and expected in path.read_text(encoding="utf-8")


def git_tracked(path: Path) -> bool:
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", rel(path)],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-durable-artifacts", action="store_true")
    args = parser.parse_args()

    gate_results: dict[str, dict[str, object]] = {}
    for name, expected in REQUIRED_GATES.items():
        path = V17 / name
        result = {
            "required": True,
            "path": rel(path),
            "expected": expected,
            "exists": path.is_file(),
            "tracked": git_tracked(path),
            "status": read_json_status(path) if expected == "json_pass" else ("present" if path.is_file() else "missing"),
            "pass": gate_pass(path, expected),
        }
        if args.require_durable_artifacts:
            result["pass"] = bool(result["pass"] and result["tracked"])
        gate_results[name] = result

    missing = [name for name, result in gate_results.items() if not result["exists"]]
    untracked = [name for name, result in gate_results.items() if args.require_durable_artifacts and not result["tracked"]]
    failing = [name for name, result in gate_results.items() if result["exists"] and not result["pass"] and name not in untracked]
    reasons = [f"missing:{name}" for name in missing]
    reasons += [f"not_durable:{name}" for name in untracked]
    reasons += [f"failing:{name}" for name in failing]
    final = "GOLD_READY" if not reasons else "NOT_GOLD"

    output = {
        "generated_at_utc": now_utc(),
        "status": "pass" if final == "GOLD_READY" else "fail",
        "verdict": final,
        "scope": "full_estate_v17",
        "artifact_root": rel(V17),
        "durable_artifacts_required": bool(args.require_durable_artifacts),
        "required_gates": gate_results,
        "missing_gates": missing,
        "untracked_gates": untracked,
        "failing_gates": failing,
        "reasons": reasons,
    }
    write_json(COMPLETION / "FINAL_GOLD_JANITOR.generated.json", output)
    write_json(V17 / "FINAL_GOLD_JANITOR.generated.json", output)
    (V17 / "FINAL_GOLD_VERDICT.md").write_text(final + "\n", encoding="utf-8")
    print(final)
    return 0 if final == "GOLD_READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
