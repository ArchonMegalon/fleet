#!/usr/bin/env python3
from __future__ import annotations

import sys

from rafter_pixefy_common import COMPLETION, now_utc, write_json


def main() -> int:
    verdict_path = COMPLETION / "rafter_pixefy" / "FINAL_RAFTER_PIXEFY_QA_STACK_VERDICT.md"
    verdict = verdict_path.read_text(encoding="utf-8").strip() if verdict_path.exists() else "MISSING"
    reasons = []
    if verdict != "RAFTER_PIXEFY_QA_STACK_READY":
        reasons.append("rafter_pixefy_qa_stack_not_ready")

    final = "GOLD_READY" if not reasons else "NOT_GOLD"
    write_json(COMPLETION / "FINAL_GOLD_JANITOR.generated.json", {
        "generated_at_utc": now_utc(),
        "status": "pass" if final == "GOLD_READY" else "fail",
        "verdict": final,
        "required_gates": {
            "rafter_pixefy": {
                "required": True,
                "verdict_file": str(verdict_path.relative_to(COMPLETION.parent)),
                "required_value": "RAFTER_PIXEFY_QA_STACK_READY",
                "actual_value": verdict,
            }
        },
        "reasons": reasons,
    })
    print(final)
    return 0 if final == "GOLD_READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
