#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

try:
    from scripts.materialize_next90_m136_fleet_parity_divergence_class_gate import (
        DEFAULT_OUTPUT,
        DESIGN_QUEUE_STAGING,
        FLEET_QUEUE_STAGING,
        FLAGSHIP_PRODUCT_BAR,
        FLAGSHIP_READINESS_PLANES,
        FLAGSHIP_RELEASE_ACCEPTANCE,
        NEXT90_GUIDE,
        PACKAGE_ID,
        PARITY_AUDIT,
        PARITY_SPEC,
        SUCCESSOR_REGISTRY,
        build_payload,
    )
except ModuleNotFoundError:
    from materialize_next90_m136_fleet_parity_divergence_class_gate import (  # type: ignore
        DEFAULT_OUTPUT,
        DESIGN_QUEUE_STAGING,
        FLEET_QUEUE_STAGING,
        FLAGSHIP_PRODUCT_BAR,
        FLAGSHIP_READINESS_PLANES,
        FLAGSHIP_RELEASE_ACCEPTANCE,
        NEXT90_GUIDE,
        PACKAGE_ID,
        PARITY_AUDIT,
        PARITY_SPEC,
        SUCCESSOR_REGISTRY,
        build_payload,
    )


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify the Fleet M136 parity divergence-class gate packet.")
    parser.add_argument("--artifact", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--fleet-queue-staging", default=str(FLEET_QUEUE_STAGING))
    parser.add_argument("--design-queue-staging", default=str(DESIGN_QUEUE_STAGING))
    parser.add_argument("--next90-guide", default=str(NEXT90_GUIDE))
    parser.add_argument("--flagship-readiness-planes", default=str(FLAGSHIP_READINESS_PLANES))
    parser.add_argument("--flagship-product-bar", default=str(FLAGSHIP_PRODUCT_BAR))
    parser.add_argument("--flagship-release-acceptance", default=str(FLAGSHIP_RELEASE_ACCEPTANCE))
    parser.add_argument("--parity-spec", default=str(PARITY_SPEC))
    parser.add_argument("--parity-audit", default=str(PARITY_AUDIT))
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
            fleet_queue_path=Path(args.fleet_queue_staging).resolve(),
            design_queue_path=Path(args.design_queue_staging).resolve(),
            next90_guide_path=Path(args.next90_guide).resolve(),
            flagship_readiness_planes_path=Path(args.flagship_readiness_planes).resolve(),
            flagship_product_bar_path=Path(args.flagship_product_bar).resolve(),
            flagship_release_acceptance_path=Path(args.flagship_release_acceptance).resolve(),
            parity_spec_path=Path(args.parity_spec).resolve(),
            parity_audit_path=Path(args.parity_audit).resolve(),
            generated_at=str(actual.get("generated_at") or "").strip() or None,
        )
        if actual.get("contract_name") != "fleet.next90_m136_parity_divergence_class_gate":
            issues.append("generated artifact contract_name is missing or unexpected")
        if actual.get("package_id") != PACKAGE_ID:
            issues.append("generated artifact package_id drifted from the assigned Fleet M136.16 package")
        if _normalized_payload(actual) != _normalized_payload(expected):
            for key, message in (
                ("status", "monitor status drifted from recomputed divergence-class truth"),
                ("canonical_monitors", "canonical monitor sections drifted from the M136.16 contract"),
                ("runtime_monitors", "runtime monitor sections drifted from recomputed divergence-class truth"),
                ("monitor_summary", "monitor summary drifted from recomputed divergence-class truth"),
                ("package_closeout", "package closeout posture drifted from recomputed divergence-class truth"),
                ("source_inputs", "source input links drifted from recomputed source truth"),
            ):
                _compare(issues, actual, expected, key, message)
            if not issues:
                issues.append("generated artifact contains unexpected drift outside the allowed generated_at field")

    result = {"status": "pass" if not issues else "fail", "artifact": str(artifact_path), "issues": issues}
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif issues:
        print("M136.16 parity divergence-class gate verifier failed:", file=sys.stderr)
        for issue in issues:
            print(f" - {issue}", file=sys.stderr)
    else:
        print("M136.16 parity divergence-class gate verifier passed")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
