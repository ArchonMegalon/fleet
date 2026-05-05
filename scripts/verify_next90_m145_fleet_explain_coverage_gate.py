#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

try:
    from scripts.materialize_next90_m145_fleet_explain_coverage_gate import (
        DEFAULT_OUTPUT,
        build_payload,
    )
except ModuleNotFoundError:
    from materialize_next90_m145_fleet_explain_coverage_gate import (  # type: ignore
        DEFAULT_OUTPUT,
        build_payload,
    )


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify the Fleet M145 explain-coverage gate packet.")
    parser.add_argument("--artifact", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--successor-registry", required=True)
    parser.add_argument("--queue-staging", required=True)
    parser.add_argument("--design-queue-staging", required=True)
    parser.add_argument("--core-receipt", required=True)
    parser.add_argument("--ui-receipt", required=True)
    parser.add_argument("--mobile-receipt", required=True)
    parser.add_argument("--media-receipt", required=True)
    parser.add_argument("--ea-packet-pack", required=True)
    parser.add_argument("--design-canon", required=True)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def _compare(issues: List[str], actual: Dict[str, Any], expected: Dict[str, Any], key: str, message: str) -> None:
    if actual.get(key) != expected.get(key):
        issues.append(message)


def _normalized_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(payload)
    normalized.pop("generated_at", None)
    return normalized


def main() -> int:
    args = parse_args()
    artifact_path = Path(args.artifact).resolve()
    actual = _read_json(artifact_path)
    issues: List[str] = []
    if not actual:
        issues.append(f"generated artifact is missing or invalid: {artifact_path}")
    else:
        expected = build_payload(
            registry_path=Path(args.successor_registry).resolve(),
            queue_path=Path(args.queue_staging).resolve(),
            design_queue_path=Path(args.design_queue_staging).resolve(),
            core_receipt_path=Path(args.core_receipt).resolve(),
            ui_receipt_path=Path(args.ui_receipt).resolve(),
            mobile_receipt_path=Path(args.mobile_receipt).resolve(),
            media_receipt_path=Path(args.media_receipt).resolve(),
            ea_packet_pack_path=Path(args.ea_packet_pack).resolve(),
            design_canon_path=Path(args.design_canon).resolve(),
            generated_at=str(actual.get("generated_at") or "").strip() or None,
        )
        if actual.get("contract_name") != "fleet.next90_m145_explain_coverage_gate":
            issues.append("generated artifact contract_name is missing or unexpected")
        if actual.get("package_id") != "next90-m145-fleet-explain-coverage-gate":
            issues.append("generated artifact package_id drifted from the assigned Fleet M145 package")
        if _normalized_payload(actual) != _normalized_payload(expected):
            for key, message in (
                ("status", "gate status drifted from recomputed sibling proof truth"),
                ("queue_title", "queue title drifted from the Fleet M145 package contract"),
                ("queue_task", "queue task drifted from the Fleet M145 package contract"),
                ("canonical_alignment", "canonical alignment no longer matches registry and queue truth"),
                ("aggregate_checks", "aggregate explain-coverage checks drifted from recomputed proof truth"),
                ("surface_receipts", "surface receipt closure posture drifted from recomputed sibling proof truth"),
                ("package_closeout", "package closeout posture drifted from recomputed proof truth"),
                ("milestone_id", "milestone_id drifted from the assigned Fleet M145 package"),
                ("frontier_id", "frontier_id drifted from the assigned Fleet M145 package"),
            ):
                _compare(issues, actual, expected, key, message)
            if not issues:
                issues.append("generated artifact contains unexpected drift outside the allowed generated_at field")
        if str(actual.get("status") or "").strip().lower() not in {"pass", "blocked"}:
            issues.append("gate status must stay pass or blocked")

    result = {
        "status": "pass" if not issues else "fail",
        "artifact": str(artifact_path),
        "issues": issues,
    }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif issues:
        print("M145 explain-coverage gate verifier failed:", file=sys.stderr)
        for issue in issues:
            print(f" - {issue}", file=sys.stderr)
    else:
        print("M145 explain-coverage gate verifier passed")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
