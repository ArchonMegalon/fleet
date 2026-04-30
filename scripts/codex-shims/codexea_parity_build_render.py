#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from typing import Any


def main() -> int:
    raw = sys.stdin.read().strip()
    if not raw:
        return 1
    try:
        summary = json.loads(raw)
    except Exception:
        print(raw)
        return 0
    if not isinstance(summary, dict) or str(summary.get("probe_kind") or "").strip().lower() != "parity_build":
        print(raw)
        return 0

    lines: list[str] = ["Parity build result:"]
    release_version = str(summary.get("release_version") or "").strip()
    if release_version:
        lines.append(f"- release_version={release_version}")
    applied_steps = [str(item).strip() for item in (summary.get("applied_steps") or []) if str(item).strip()]
    if applied_steps:
        lines.append("Applied:")
        for step in applied_steps[:10]:
            lines.append(f"- {step}")
    parity_summary = summary.get("parity_summary") if isinstance(summary.get("parity_summary"), dict) else {}
    if parity_summary:
        lines.append(
            "- parity_counts="
            f"visual {int(parity_summary.get('visual_yes_count') or 0)}/{int(parity_summary.get('visual_no_count') or 0)}"
            f", behavioral {int(parity_summary.get('behavioral_yes_count') or 0)}/{int(parity_summary.get('behavioral_no_count') or 0)}"
        )
    report_path = str(summary.get("parity_report_path") or "").strip()
    if report_path:
        lines.append(f"- parity_report={report_path}")
    remaining = summary.get("remaining_findings") if isinstance(summary.get("remaining_findings"), list) else []
    if remaining:
        lines.append("Remaining findings:")
        for index, item in enumerate(remaining[:8], start=1):
            if not isinstance(item, dict):
                continue
            severity = str(item.get("severity") or "info").strip().upper()
            category = str(item.get("category") or "gap").strip()
            summary_text = str(item.get("summary") or "").strip()
            detail = str(item.get("detail") or "").strip()
            segment = f"{index}. {severity} {category}: {summary_text}"
            if detail:
                segment += f" {detail}"
            lines.append(segment)
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
