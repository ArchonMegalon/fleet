#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

try:
    from scripts.materialize_next90_m143_fleet_route_local_output_closeout_gates import (
        CORE_M143_RECEIPTS_DOC,
        DEFAULT_OUTPUT,
        DESKTOP_VISUAL_FAMILIARITY_GATE,
        DESIGN_QUEUE_STAGING,
        FLEET_QUEUE_STAGING,
        GENERATED_DIALOG_PARITY,
        M114_RULE_STUDIO,
        NEXT90_GUIDE,
        PARITY_AUDIT,
        SCREENSHOT_REVIEW_GATE,
        SECTION_HOST_RULESET_PARITY,
        SUCCESSOR_REGISTRY,
        WORKFLOW_PACK,
        build_payload,
    )
except ModuleNotFoundError:
    script_dir = Path(__file__).resolve().parent
    if str(script_dir) not in sys.path:
        sys.path.insert(0, str(script_dir))
    from materialize_next90_m143_fleet_route_local_output_closeout_gates import (  # type: ignore
        CORE_M143_RECEIPTS_DOC,
        DEFAULT_OUTPUT,
        DESKTOP_VISUAL_FAMILIARITY_GATE,
        DESIGN_QUEUE_STAGING,
        FLEET_QUEUE_STAGING,
        GENERATED_DIALOG_PARITY,
        M114_RULE_STUDIO,
        NEXT90_GUIDE,
        PARITY_AUDIT,
        SCREENSHOT_REVIEW_GATE,
        SECTION_HOST_RULESET_PARITY,
        SUCCESSOR_REGISTRY,
        WORKFLOW_PACK,
        build_payload,
    )


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify the Fleet M143 route-local output closeout gate packet.")
    parser.add_argument("--artifact", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--fleet-queue-staging", default=str(FLEET_QUEUE_STAGING))
    parser.add_argument("--design-queue-staging", default=str(DESIGN_QUEUE_STAGING))
    parser.add_argument("--next90-guide", default=str(NEXT90_GUIDE))
    parser.add_argument("--workflow-pack", default=str(WORKFLOW_PACK))
    parser.add_argument("--parity-audit", default=str(PARITY_AUDIT))
    parser.add_argument("--screenshot-review-gate", default=str(SCREENSHOT_REVIEW_GATE))
    parser.add_argument("--desktop-visual-familiarity-gate", default=str(DESKTOP_VISUAL_FAMILIARITY_GATE))
    parser.add_argument("--section-host-ruleset-parity", default=str(SECTION_HOST_RULESET_PARITY))
    parser.add_argument("--generated-dialog-parity", default=str(GENERATED_DIALOG_PARITY))
    parser.add_argument("--m114-rule-studio", default=str(M114_RULE_STUDIO))
    parser.add_argument("--core-m143-receipts-doc", default=str(CORE_M143_RECEIPTS_DOC))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def verify(args: argparse.Namespace) -> Dict[str, Any]:
    artifact_path = Path(args.artifact).resolve()
    actual = _load_json(artifact_path)
    expected = build_payload(
        registry_path=Path(args.successor_registry).resolve(),
        fleet_queue_path=Path(args.fleet_queue_staging).resolve(),
        design_queue_path=Path(args.design_queue_staging).resolve(),
        next90_guide_path=Path(args.next90_guide).resolve(),
        workflow_pack_path=Path(args.workflow_pack).resolve(),
        parity_audit_path=Path(args.parity_audit).resolve(),
        screenshot_review_gate_path=Path(args.screenshot_review_gate).resolve(),
        desktop_visual_familiarity_gate_path=Path(args.desktop_visual_familiarity_gate).resolve(),
        section_host_ruleset_parity_path=Path(args.section_host_ruleset_parity).resolve(),
        generated_dialog_parity_path=Path(args.generated_dialog_parity).resolve(),
        m114_rule_studio_path=Path(args.m114_rule_studio).resolve(),
        core_m143_receipts_doc_path=Path(args.core_m143_receipts_doc).resolve(),
        generated_at=str(actual.get("generated_at") or ""),
    )

    issues: List[str] = []
    if not actual:
        issues.append("generated artifact is missing or invalid JSON")
    else:
        if actual.get("contract_name") != "fleet.next90_m143_route_local_output_closeout_gates":
            issues.append("generated artifact contract_name drifted from the assigned Fleet M143 packet")
        if actual.get("package_id") != "next90-m143-fleet-fail-closeout-when-these-families-remain-green-only-by-broad-family-pr":
            issues.append("generated artifact package_id drifted from the assigned Fleet M143 package")
        for field, message in (
            ("status", "closeout-gate status drifted from recomputed M143 truth"),
            ("canonical_monitors", "canonical monitors drifted from recomputed M143 truth"),
            ("runtime_monitors", "runtime monitors drifted from recomputed M143 truth"),
            ("monitor_summary", "monitor summary drifted from recomputed M143 truth"),
            ("package_closeout", "package closeout drifted from recomputed M143 truth"),
        ):
            if actual.get(field) != expected.get(field):
                issues.append(message)

    return {"artifact": str(artifact_path), "issues": issues, "status": "pass" if not issues else "fail"}


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    payload = verify(args)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif payload["status"] != "pass":
        print("M143 route-local output closeout gate verifier failed:", file=sys.stderr)
        for issue in payload["issues"]:
            print(f"- {issue}", file=sys.stderr)
    else:
        print("M143 route-local output closeout gate verifier passed")
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
