#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

try:
    from scripts.materialize_next90_m139_fleet_release_health_public_trust_projections import (
        ACCESSIBILITY_GATES,
        ACCESSIBILITY_RELEASE_BAR,
        COMMUNITY_SAFETY_DOC,
        COMMUNITY_SAFETY_STATES,
        CREATOR_ANALYTICS_DOC,
        CREATOR_ANALYTICS_SCHEMA,
        CREATOR_TRUST_POLICY,
        DEFAULT_OUTPUT,
        DESIGN_QUEUE_STAGING,
        FLEET_QUEUE_STAGING,
        NEXT90_GUIDE,
        OPPOSITION_PACKET_REGISTRY,
        PREP_PACKET_FACTORY,
        PRODUCT_ANALYTICS_MODEL,
        PUBLIC_FAQ_REGISTRY,
        PUBLIC_FEATURE_REGISTRY,
        PUBLIC_LANDING_MANIFEST,
        SUCCESSOR_REGISTRY,
        WORLD_BROADCAST_CADENCE,
        WORLD_BROADCAST_RECIPE_REGISTRY,
        build_payload,
    )
except ModuleNotFoundError:
    from materialize_next90_m139_fleet_release_health_public_trust_projections import (  # type: ignore
        ACCESSIBILITY_GATES,
        ACCESSIBILITY_RELEASE_BAR,
        COMMUNITY_SAFETY_DOC,
        COMMUNITY_SAFETY_STATES,
        CREATOR_ANALYTICS_DOC,
        CREATOR_ANALYTICS_SCHEMA,
        CREATOR_TRUST_POLICY,
        DEFAULT_OUTPUT,
        DESIGN_QUEUE_STAGING,
        FLEET_QUEUE_STAGING,
        NEXT90_GUIDE,
        OPPOSITION_PACKET_REGISTRY,
        PREP_PACKET_FACTORY,
        PRODUCT_ANALYTICS_MODEL,
        PUBLIC_FAQ_REGISTRY,
        PUBLIC_FEATURE_REGISTRY,
        PUBLIC_LANDING_MANIFEST,
        SUCCESSOR_REGISTRY,
        WORLD_BROADCAST_CADENCE,
        WORLD_BROADCAST_RECIPE_REGISTRY,
        build_payload,
    )


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify the Fleet M139 release-health/public-trust projection packet.")
    parser.add_argument("--artifact", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--fleet-queue-staging", default=str(FLEET_QUEUE_STAGING))
    parser.add_argument("--design-queue-staging", default=str(DESIGN_QUEUE_STAGING))
    parser.add_argument("--next90-guide", default=str(NEXT90_GUIDE))
    parser.add_argument("--prep-packet-factory", default=str(PREP_PACKET_FACTORY))
    parser.add_argument("--opposition-packet-registry", default=str(OPPOSITION_PACKET_REGISTRY))
    parser.add_argument("--world-broadcast-cadence", default=str(WORLD_BROADCAST_CADENCE))
    parser.add_argument("--world-broadcast-recipe-registry", default=str(WORLD_BROADCAST_RECIPE_REGISTRY))
    parser.add_argument("--community-safety-doc", default=str(COMMUNITY_SAFETY_DOC))
    parser.add_argument("--community-safety-states", default=str(COMMUNITY_SAFETY_STATES))
    parser.add_argument("--creator-analytics-doc", default=str(CREATOR_ANALYTICS_DOC))
    parser.add_argument("--creator-analytics-schema", default=str(CREATOR_ANALYTICS_SCHEMA))
    parser.add_argument("--creator-trust-policy", default=str(CREATOR_TRUST_POLICY))
    parser.add_argument("--product-analytics-model", default=str(PRODUCT_ANALYTICS_MODEL))
    parser.add_argument("--accessibility-release-bar", default=str(ACCESSIBILITY_RELEASE_BAR))
    parser.add_argument("--accessibility-gates", default=str(ACCESSIBILITY_GATES))
    parser.add_argument("--public-faq-registry", default=str(PUBLIC_FAQ_REGISTRY))
    parser.add_argument("--public-feature-registry", default=str(PUBLIC_FEATURE_REGISTRY))
    parser.add_argument("--public-landing-manifest", default=str(PUBLIC_LANDING_MANIFEST))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def _normalized_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(payload)
    normalized.pop("generated_at", None)
    return normalized


def _compare(issues: List[str], actual: Dict[str, Any], expected: Dict[str, Any], key: str, message: str) -> None:
    if actual.get(key) != expected.get(key):
        issues.append(message)


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
            prep_packet_factory_path=Path(args.prep_packet_factory).resolve(),
            opposition_packet_registry_path=Path(args.opposition_packet_registry).resolve(),
            world_broadcast_cadence_path=Path(args.world_broadcast_cadence).resolve(),
            world_broadcast_recipe_registry_path=Path(args.world_broadcast_recipe_registry).resolve(),
            community_safety_doc_path=Path(args.community_safety_doc).resolve(),
            community_safety_states_path=Path(args.community_safety_states).resolve(),
            creator_analytics_doc_path=Path(args.creator_analytics_doc).resolve(),
            creator_analytics_schema_path=Path(args.creator_analytics_schema).resolve(),
            creator_trust_policy_path=Path(args.creator_trust_policy).resolve(),
            product_analytics_model_path=Path(args.product_analytics_model).resolve(),
            accessibility_release_bar_path=Path(args.accessibility_release_bar).resolve(),
            accessibility_gates_path=Path(args.accessibility_gates).resolve(),
            public_faq_registry_path=Path(args.public_faq_registry).resolve(),
            public_feature_registry_path=Path(args.public_feature_registry).resolve(),
            public_landing_manifest_path=Path(args.public_landing_manifest).resolve(),
            generated_at=_normalized_payload(actual).get("generated_at") or actual.get("generated_at"),
        )
        if actual.get("contract_name") != "fleet.next90_m139_release_health_public_trust_projections":
            issues.append("generated artifact contract_name is missing or unexpected")
        if actual.get("package_id") != "next90-m139-fleet-bind-community-safety-event-and-appeal-states-world-broadcast-recipe-r":
            issues.append("generated artifact package_id drifted from the assigned Fleet M139 package")
        if _normalized_payload(actual) != _normalized_payload(expected):
            for key, message in (
                ("status", "projection status drifted from recomputed release-health/public-trust truth"),
                ("canonical_monitors", "canonical monitors drifted from recomputed release-health/public-trust truth"),
                ("projection_summary", "projection summary drifted from recomputed release-health/public-trust truth"),
                ("projections", "projections drifted from recomputed release-health/public-trust truth"),
                ("public_truth_projection", "public truth projection drifted from recomputed release-health/public-trust truth"),
                ("package_closeout", "package closeout drifted from recomputed release-health/public-trust truth"),
                ("source_inputs", "source input links drifted from recomputed source truth"),
            ):
                _compare(issues, actual, expected, key, message)
            if not issues:
                issues.append("generated artifact contains unexpected drift outside the allowed generated_at field")

    result = {"status": "pass" if not issues else "fail", "artifact": str(artifact_path), "issues": issues}
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif issues:
        print("M139 release-health/public-trust projection verifier failed:", file=sys.stderr)
        for issue in issues:
            print(f" - {issue}", file=sys.stderr)
    else:
        print("M139 release-health/public-trust projection verifier passed")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
