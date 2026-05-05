#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

try:
    from scripts.materialize_next90_m125_fleet_signal_cluster_queue import (
        CLICKRANK_LANE,
        DEFAULT_OUTPUT,
        DEFAULT_SIGNAL_SOURCE_OUTPUT,
        DESIGN_QUEUE_STAGING,
        FEEDBACK_AND_SIGNAL_OODA_LOOP,
        KATTEB_LANE,
        PRODUCTLIFT_BRIDGE,
        PUBLIC_SIGNAL_TO_CANON_PIPELINE,
        QUEUE_STAGING,
        SUCCESSOR_REGISTRY,
        SUPPORT_CASE_PACKETS,
        WEEKLY_PRODUCT_PULSE,
        build_payload,
    )
except ModuleNotFoundError:
    from materialize_next90_m125_fleet_signal_cluster_queue import (  # type: ignore
        CLICKRANK_LANE,
        DEFAULT_OUTPUT,
        DEFAULT_SIGNAL_SOURCE_OUTPUT,
        DESIGN_QUEUE_STAGING,
        FEEDBACK_AND_SIGNAL_OODA_LOOP,
        KATTEB_LANE,
        PRODUCTLIFT_BRIDGE,
        PUBLIC_SIGNAL_TO_CANON_PIPELINE,
        QUEUE_STAGING,
        SUCCESSOR_REGISTRY,
        SUPPORT_CASE_PACKETS,
        WEEKLY_PRODUCT_PULSE,
        build_payload,
    )


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify the Fleet M125 signal-cluster queue synthesis packet.")
    parser.add_argument("--artifact", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--queue-staging", default=str(QUEUE_STAGING))
    parser.add_argument("--design-queue-staging", default=str(DESIGN_QUEUE_STAGING))
    parser.add_argument("--public-signal-pipeline", default=str(PUBLIC_SIGNAL_TO_CANON_PIPELINE))
    parser.add_argument("--feedback-ooda-loop", default=str(FEEDBACK_AND_SIGNAL_OODA_LOOP))
    parser.add_argument("--productlift-bridge", default=str(PRODUCTLIFT_BRIDGE))
    parser.add_argument("--katteb-lane", default=str(KATTEB_LANE))
    parser.add_argument("--clickrank-lane", default=str(CLICKRANK_LANE))
    parser.add_argument("--weekly-product-pulse", default=str(WEEKLY_PRODUCT_PULSE))
    parser.add_argument("--support-case-packets", default=str(SUPPORT_CASE_PACKETS))
    parser.add_argument("--signal-source", default=str(DEFAULT_SIGNAL_SOURCE_OUTPUT))
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
        signal_source_path = Path(args.signal_source).resolve()
        expected = build_payload(
            registry_path=Path(args.successor_registry).resolve(),
            queue_path=Path(args.queue_staging).resolve(),
            design_queue_path=Path(args.design_queue_staging).resolve(),
            public_signal_pipeline_path=Path(args.public_signal_pipeline).resolve(),
            feedback_ooda_loop_path=Path(args.feedback_ooda_loop).resolve(),
            productlift_bridge_path=Path(args.productlift_bridge).resolve(),
            katteb_lane_path=Path(args.katteb_lane).resolve(),
            clickrank_lane_path=Path(args.clickrank_lane).resolve(),
            weekly_product_pulse_path=Path(args.weekly_product_pulse).resolve(),
            support_case_packets_path=Path(args.support_case_packets).resolve(),
            signal_source_path=signal_source_path,
            signal_source_payload=_read_json(signal_source_path),
            generated_at=str(actual.get("generated_at") or "").strip() or None,
        )
        if actual.get("contract_name") != "fleet.next90_m125_signal_cluster_queue_synthesis":
            issues.append("generated artifact contract_name is missing or unexpected")
        if actual.get("package_id") != "next90-m125-fleet-add-signal-cluster-to-queue-synthesis-for-repeated-produ":
            issues.append("generated artifact package_id drifted from the assigned Fleet M125 package")
        if _normalized_payload(actual) != _normalized_payload(expected):
            for key, message in (
                ("status", "monitor status drifted from recomputed signal-cluster truth"),
                ("canonical_alignment", "canonical alignment drifted from queue and registry truth"),
                ("canonical_monitors", "canonical monitor sections drifted from public-signal canon"),
                ("queue_synthesis", "queue synthesis section drifted from recomputed signal-source truth"),
                ("package_closeout", "package closeout posture drifted from recomputed signal-cluster truth"),
                ("source_inputs", "source input links drifted from recomputed source truth"),
                ("milestone_id", "milestone_id drifted from the assigned Fleet M125 package"),
                ("frontier_id", "frontier_id drifted from the assigned Fleet M125 package"),
            ):
                _compare(issues, actual, expected, key, message)
            if not issues:
                issues.append("generated artifact contains unexpected drift outside the allowed generated_at field")

    result = {"status": "pass" if not issues else "fail", "artifact": str(artifact_path), "issues": issues}
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif issues:
        print("M125 signal-cluster queue verifier failed:", file=sys.stderr)
        for issue in issues:
            print(f" - {issue}", file=sys.stderr)
    else:
        print("M125 signal-cluster queue verifier passed")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
