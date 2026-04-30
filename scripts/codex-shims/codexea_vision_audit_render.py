#!/usr/bin/env python3
from __future__ import annotations

import json
import sys


def main() -> int:
    raw = sys.stdin.read().strip()
    if not raw:
        return 1
    try:
        summary = json.loads(raw)
    except Exception:
        print(raw)
        return 0
    if not isinstance(summary, dict) or str(summary.get("probe_kind") or "").strip().lower() != "vision_audit":
        print(raw)
        return 0

    payload = summary.get("summary") if isinstance(summary.get("summary"), dict) else {}
    lines: list[str] = ["Vision audit result:"]
    report_json = str(summary.get("report_json_path") or "").strip()
    report_md = str(summary.get("report_markdown_path") or "").strip()
    if report_json:
        lines.append(f"- report_json={report_json}")
    if report_md:
        lines.append(f"- report_markdown={report_md}")
    lines.append(f"- repo_grounded_findings={int(payload.get('repo_grounded_findings_count') or 0)}")
    lines.append(f"- speculative_integration_opportunities={int(payload.get('speculative_integration_opportunity_count') or 0)}")
    lines.append(
        "- ui_parity_counts="
        f"visual {int(payload.get('visual_yes_count') or 0)}/{int(payload.get('visual_no_count') or 0)}, "
        f"behavioral {int(payload.get('behavioral_yes_count') or 0)}/{int(payload.get('behavioral_no_count') or 0)}"
    )
    top_findings = summary.get("top_findings") if isinstance(summary.get("top_findings"), list) else []
    if top_findings:
        lines.append("Top findings:")
        for index, item in enumerate(top_findings[:5], start=1):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            severity = str(item.get("severity") or "info").strip().upper()
            impact = str(item.get("user_impact") or "").strip()
            owners = item.get("owner_shards") if isinstance(item.get("owner_shards"), list) else []
            owner_text = f" owners={owners}" if owners else ""
            segment = f"{index}. {severity}: {title}{owner_text}"
            if impact:
                segment += f" {impact}"
            lines.append(segment)
    top_opportunities = summary.get("top_integration_opportunities") if isinstance(summary.get("top_integration_opportunities"), list) else []
    if top_opportunities:
        lines.append("Top integration opportunities:")
        for index, item in enumerate(top_opportunities[:4], start=1):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            thesis = str(item.get("thesis") or "").strip()
            segment = f"{index}. {title}"
            if thesis:
                segment += f" {thesis}"
            lines.append(segment)
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
