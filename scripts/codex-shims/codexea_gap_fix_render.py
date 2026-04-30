#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from typing import Any


def _status_parts(summary: dict[str, Any]) -> list[str]:
    status_summary = summary.get("status_summary") if isinstance(summary.get("status_summary"), dict) else {}
    parts: list[str] = []
    for key in (
        "workflow_gate",
        "visual_gate",
        "windows_gate",
        "linux_gate",
        "macos_gate",
        "desktop_executable_gate",
        "flagship_readiness",
    ):
        row = status_summary.get(key)
        if not isinstance(row, dict):
            continue
        status = str(row.get("status") or "").strip()
        if status:
            parts.append(f"{key}={status}")
    return parts


def main() -> int:
    raw = sys.stdin.read().strip()
    if not raw:
        return 1
    try:
        summary = json.loads(raw)
    except Exception:
        print(raw)
        return 0
    if not isinstance(summary, dict) or str(summary.get("probe_kind") or "").strip().lower() != "gap_fix":
        print(raw)
        return 0

    lines: list[str] = ["Gap fix result:"]
    applied_steps = [str(item).strip() for item in (summary.get("applied_steps") or []) if str(item).strip()]
    if applied_steps:
        lines.append("Applied:")
        for step in applied_steps[:8]:
            lines.append(f"- {step}")
    current_parts = _status_parts(summary)
    if current_parts:
        lines.append("Current status:")
        lines.append("- " + ", ".join(current_parts))
    remaining_findings = summary.get("remaining_findings") if isinstance(summary.get("remaining_findings"), list) else []
    if remaining_findings:
        lines.append("Remaining findings:")
        for index, item in enumerate(remaining_findings[:5], start=1):
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
