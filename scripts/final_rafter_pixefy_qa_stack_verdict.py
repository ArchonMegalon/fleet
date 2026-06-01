#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from rafter_pixefy_common import COMPLETION, ROOT, now_utc, write_json
from verify_committed_rafter_pixefy_ci_receipt import collect_provider_failures, load_json


READY_TOKEN = "RAFTER_PIXEFY_QA_STACK_READY"


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


def _load_optional_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _without_generated_at(payload: dict[str, Any]) -> dict[str, Any]:
    copy = dict(payload)
    copy.pop("generated_at_utc", None)
    return copy


def _binding_version(provider: str) -> str:
    gate_path = {
        "Rafter": COMPLETION / "rafter" / "RAFTER_SECURITY_GOLD_GATE.generated.json",
        "Pixefy": COMPLETION / "pixefy" / "PIXEFY_RESPONSIVE_VISUAL_QA.generated.json",
    }[provider]
    gate = load_json(gate_path)
    binding = gate.get("active_release_binding") if isinstance(gate.get("active_release_binding"), dict) else {}
    return str(binding.get("version") or "").strip()


def main() -> int:
    failures: list[str] = []
    provider_failures = {
        "Rafter": collect_provider_failures("Rafter"),
        "Pixefy": collect_provider_failures("Pixefy"),
    }
    for provider, provider_failure_list in provider_failures.items():
        failures.extend(f"{provider.lower()}:{failure}" for failure in provider_failure_list)

    top_level_verdict = COMPLETION / "rafter_pixefy" / "FINAL_RAFTER_PIXEFY_QA_STACK_VERDICT.md"
    full_product_verdicts = [
        COMPLETION / "full_product_reaudit_v18" / "FINAL_RAFTER_PIXEFY_QA_STACK_VERDICT.md",
        COMPLETION / "full_product_reaudit_v17" / "FINAL_RAFTER_PIXEFY_QA_STACK_VERDICT.md",
    ]
    if _read_text(top_level_verdict) != READY_TOKEN:
        failures.append("top_level_final_verdict_not_ready")
    if not any(_read_text(path) == READY_TOKEN for path in full_product_verdicts):
        failures.append("full_product_final_verdict_not_ready")

    reasons_path = COMPLETION / "rafter_pixefy" / "FINAL_RAFTER_PIXEFY_QA_STACK_REASONS.generated.json"
    previous_reasons = _load_optional_json(reasons_path)
    if previous_reasons.get("verdict") not in (READY_TOKEN, None):
        failures.append("previous_final_reasons_verdict_not_ready")

    rafter_version = _binding_version("Rafter")
    pixefy_version = _binding_version("Pixefy")
    if not rafter_version or not pixefy_version:
        failures.append("provider_build_binding_version_missing")
    if rafter_version != pixefy_version:
        failures.append("provider_build_binding_versions_disagree")

    verdict = READY_TOKEN if not failures else "NOT_READY"
    receipt_body = {
        "verdict": verdict,
        "gold_claim_allowed": verdict == READY_TOKEN,
        "active_release_binding": {
            "version": rafter_version if rafter_version == pixefy_version else "",
            "rafter_version": rafter_version,
            "pixefy_version": pixefy_version,
        },
        "provider_failures": provider_failures,
        "reasons": failures,
        "checked_artifacts": [
            str(top_level_verdict.relative_to(ROOT)),
            *[
                str(path.relative_to(ROOT))
                for path in full_product_verdicts
                if path.exists()
            ],
            "scripts/verify_committed_rafter_pixefy_ci_receipt.py",
        ],
    }
    generated_at = (
        str(previous_reasons.get("generated_at_utc"))
        if _without_generated_at(previous_reasons) == receipt_body and previous_reasons.get("generated_at_utc")
        else now_utc()
    )
    receipt = {"generated_at_utc": generated_at, **receipt_body}
    write_json(reasons_path, receipt)

    if failures:
        print("Rafter/Pixefy final verdict failed: " + ", ".join(failures), file=sys.stderr)
        return 1
    print(READY_TOKEN)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
