#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

try:
    from scripts.materialize_next90_m128_fleet_trust_plane_monitors import (
        CRASH_REPORTING,
        DEFAULT_OUTPUT,
        DESIGN_QUEUE_STAGING,
        FLAGSHIP_READINESS,
        LOCALIZATION_SYSTEM,
        NEXT90_GUIDE,
        PRIVACY_BOUNDARIES,
        QUEUE_STAGING,
        SUCCESSOR_REGISTRY,
        SUPPORT_PACKETS,
        SUPPORT_STATUS,
        TELEMETRY_MODEL,
        TELEMETRY_SCHEMA,
        WEEKLY_PRODUCT_PULSE,
        build_payload,
    )
except ModuleNotFoundError:
    from materialize_next90_m128_fleet_trust_plane_monitors import (  # type: ignore
        CRASH_REPORTING,
        DEFAULT_OUTPUT,
        DESIGN_QUEUE_STAGING,
        FLAGSHIP_READINESS,
        LOCALIZATION_SYSTEM,
        NEXT90_GUIDE,
        PRIVACY_BOUNDARIES,
        QUEUE_STAGING,
        SUCCESSOR_REGISTRY,
        SUPPORT_PACKETS,
        SUPPORT_STATUS,
        TELEMETRY_MODEL,
        TELEMETRY_SCHEMA,
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
    parser = argparse.ArgumentParser(description="Verify the Fleet M128 trust-plane monitor packet.")
    parser.add_argument("--artifact", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--queue-staging", default=str(QUEUE_STAGING))
    parser.add_argument("--design-queue-staging", default=str(DESIGN_QUEUE_STAGING))
    parser.add_argument("--next90-guide", default=str(NEXT90_GUIDE))
    parser.add_argument("--localization-system", default=str(LOCALIZATION_SYSTEM))
    parser.add_argument("--telemetry-model", default=str(TELEMETRY_MODEL))
    parser.add_argument("--telemetry-schema", default=str(TELEMETRY_SCHEMA))
    parser.add_argument("--privacy-boundaries", default=str(PRIVACY_BOUNDARIES))
    parser.add_argument("--crash-reporting", default=str(CRASH_REPORTING))
    parser.add_argument("--support-status", default=str(SUPPORT_STATUS))
    parser.add_argument("--flagship-readiness", default=str(FLAGSHIP_READINESS))
    parser.add_argument("--support-packets", default=str(SUPPORT_PACKETS))
    parser.add_argument("--weekly-product-pulse", default=str(WEEKLY_PRODUCT_PULSE))
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
            next90_guide_path=Path(args.next90_guide).resolve(),
            localization_system_path=Path(args.localization_system).resolve(),
            telemetry_model_path=Path(args.telemetry_model).resolve(),
            telemetry_schema_path=Path(args.telemetry_schema).resolve(),
            privacy_boundaries_path=Path(args.privacy_boundaries).resolve(),
            crash_reporting_path=Path(args.crash_reporting).resolve(),
            support_status_path=Path(args.support_status).resolve(),
            flagship_readiness_path=Path(args.flagship_readiness).resolve(),
            support_packets_path=Path(args.support_packets).resolve(),
            weekly_product_pulse_path=Path(args.weekly_product_pulse).resolve(),
            generated_at=str(actual.get("generated_at") or "").strip() or None,
        )
        if actual.get("contract_name") != "fleet.next90_m128_trust_plane_monitors":
            issues.append("generated artifact contract_name is missing or unexpected")
        if actual.get("package_id") != "next90-m128-fleet-add-freshness-and-contradiction-monitors-for-telemetry-p":
            issues.append("generated artifact package_id drifted from the assigned Fleet M128 package")
        if _normalized_payload(actual) != _normalized_payload(expected):
            for key, message in (
                ("status", "monitor status drifted from recomputed trust-plane truth"),
                ("canonical_alignment", "canonical alignment drifted from queue and registry truth"),
                ("canonical_monitors", "canonical monitor sections drifted from trust-plane canon"),
                ("runtime_monitors", "runtime monitor sections drifted from recomputed trust-plane evidence"),
                ("monitor_summary", "monitor summary drifted from recomputed trust-plane evidence"),
                ("package_closeout", "package closeout posture drifted from recomputed trust-plane evidence"),
                ("source_inputs", "source input links drifted from recomputed source truth"),
                ("milestone_id", "milestone_id drifted from the assigned Fleet M128 package"),
                ("frontier_id", "frontier_id drifted from the assigned Fleet M128 package"),
            ):
                _compare(issues, actual, expected, key, message)
            if not issues:
                issues.append("generated artifact contains unexpected drift outside the allowed generated_at field")

    result = {"status": "pass" if not issues else "fail", "artifact": str(artifact_path), "issues": issues}
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif issues:
        print("M128 trust-plane monitors verifier failed:", file=sys.stderr)
        for issue in issues:
            print(f" - {issue}", file=sys.stderr)
    else:
        print("M128 trust-plane monitors verifier passed")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
