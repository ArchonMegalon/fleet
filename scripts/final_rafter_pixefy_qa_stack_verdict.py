#!/usr/bin/env python3
from __future__ import annotations

import sys

from rafter_pixefy_common import COMPLETION, load_optional_json, now_utc, write_json


def main() -> int:
    reasons: list[str] = []
    rafter_provider = load_optional_json(COMPLETION / "rafter" / "RAFTER_PROVIDER_VERIFICATION.generated.json")
    pixefy_provider = load_optional_json(COMPLETION / "pixefy" / "PIXEFY_PROVIDER_VERIFICATION.generated.json")
    rafter_gate = load_optional_json(COMPLETION / "rafter" / "RAFTER_SECURITY_GOLD_GATE.generated.json")
    pixefy_gate = load_optional_json(COMPLETION / "pixefy" / "PIXEFY_RESPONSIVE_VISUAL_QA.generated.json")

    if not rafter_provider or rafter_provider.get("status") != "verified":
        reasons.append("rafter_provider_verification_missing_or_not_verified")
    if not pixefy_provider or pixefy_provider.get("status") != "verified":
        reasons.append("pixefy_provider_verification_missing_or_not_verified")
    if not rafter_gate or rafter_gate.get("status") != "pass":
        reasons.append("rafter_security_gold_gate_not_pass")
    if not pixefy_gate or pixefy_gate.get("status") != "pass":
        reasons.append("pixefy_responsive_visual_qa_not_pass")
    if rafter_gate and not (rafter_gate.get("scan_freshness") or {}).get("fresh"):
        reasons.append("rafter_scan_stale_or_missing")
    if pixefy_gate and not (pixefy_gate.get("screenshot_freshness") or {}).get("fresh"):
        reasons.append("pixefy_screenshot_set_stale_or_missing")
    if pixefy_gate and (pixefy_gate.get("review") or {}).get("human_review_status") != "pass":
        reasons.append("pixefy_human_visual_review_not_pass")

    verdict = "RAFTER_PIXEFY_QA_STACK_READY" if not reasons else "NOT_READY"
    out_dir = COMPLETION / "rafter_pixefy"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "FINAL_RAFTER_PIXEFY_QA_STACK_VERDICT.md").write_text(verdict + "\n", encoding="utf-8")
    write_json(out_dir / "FINAL_RAFTER_PIXEFY_QA_STACK_REASONS.generated.json", {
        "generated_at_utc": now_utc(),
        "verdict": verdict,
        "reasons": reasons,
        "gold_claim_allowed": verdict == "RAFTER_PIXEFY_QA_STACK_READY",
    })
    print(verdict)
    return 0 if verdict == "RAFTER_PIXEFY_QA_STACK_READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
