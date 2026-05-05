#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

try:
    from scripts.materialize_next90_m138_fleet_hero_path_projections import (
        CAMPAIGN_ADOPTION_FLOW,
        DEFAULT_OUTPUT,
        DESIGN_QUEUE_STAGING,
        FLEET_QUEUE_STAGING,
        FOUNDRY_FIRST_HANDOFF,
        NEXT90_GUIDE,
        OPEN_RUN_JOURNEY,
        PUBLIC_FAQ_REGISTRY,
        PUBLIC_FEATURE_REGISTRY,
        PUBLIC_GUIDE_COMMUNITY_HUB,
        PUBLIC_LANDING_MANIFEST,
        PUBLIC_ONBOARDING_PATHS,
        READY_FOR_TONIGHT_GATES,
        ROLE_KIT_REGISTRY,
        SOURCE_AWARE_EXPLAIN,
        SUCCESSOR_REGISTRY,
        VTT_EXPORT_TARGET_ACCEPTANCE,
        build_payload,
    )
except ModuleNotFoundError:
    from materialize_next90_m138_fleet_hero_path_projections import (  # type: ignore
        CAMPAIGN_ADOPTION_FLOW,
        DEFAULT_OUTPUT,
        DESIGN_QUEUE_STAGING,
        FLEET_QUEUE_STAGING,
        FOUNDRY_FIRST_HANDOFF,
        NEXT90_GUIDE,
        OPEN_RUN_JOURNEY,
        PUBLIC_FAQ_REGISTRY,
        PUBLIC_FEATURE_REGISTRY,
        PUBLIC_GUIDE_COMMUNITY_HUB,
        PUBLIC_LANDING_MANIFEST,
        PUBLIC_ONBOARDING_PATHS,
        READY_FOR_TONIGHT_GATES,
        ROLE_KIT_REGISTRY,
        SOURCE_AWARE_EXPLAIN,
        SUCCESSOR_REGISTRY,
        VTT_EXPORT_TARGET_ACCEPTANCE,
        build_payload,
    )


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify the Fleet M138 hero-path projections packet.")
    parser.add_argument("--artifact", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--fleet-queue-staging", default=str(FLEET_QUEUE_STAGING))
    parser.add_argument("--design-queue-staging", default=str(DESIGN_QUEUE_STAGING))
    parser.add_argument("--next90-guide", default=str(NEXT90_GUIDE))
    parser.add_argument("--ready-for-tonight-gates", default=str(READY_FOR_TONIGHT_GATES))
    parser.add_argument("--public-onboarding-paths", default=str(PUBLIC_ONBOARDING_PATHS))
    parser.add_argument("--role-kit-registry", default=str(ROLE_KIT_REGISTRY))
    parser.add_argument("--source-aware-explain", default=str(SOURCE_AWARE_EXPLAIN))
    parser.add_argument("--campaign-adoption-flow", default=str(CAMPAIGN_ADOPTION_FLOW))
    parser.add_argument("--foundry-first-handoff", default=str(FOUNDRY_FIRST_HANDOFF))
    parser.add_argument("--vtt-export-target-acceptance", default=str(VTT_EXPORT_TARGET_ACCEPTANCE))
    parser.add_argument("--public-faq-registry", default=str(PUBLIC_FAQ_REGISTRY))
    parser.add_argument("--public-guide-community-hub", default=str(PUBLIC_GUIDE_COMMUNITY_HUB))
    parser.add_argument("--open-run-journey", default=str(OPEN_RUN_JOURNEY))
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
            ready_for_tonight_gates_path=Path(args.ready_for_tonight_gates).resolve(),
            public_onboarding_paths_path=Path(args.public_onboarding_paths).resolve(),
            role_kit_registry_path=Path(args.role_kit_registry).resolve(),
            source_aware_explain_path=Path(args.source_aware_explain).resolve(),
            campaign_adoption_flow_path=Path(args.campaign_adoption_flow).resolve(),
            foundry_first_handoff_path=Path(args.foundry_first_handoff).resolve(),
            vtt_export_target_acceptance_path=Path(args.vtt_export_target_acceptance).resolve(),
            public_faq_registry_path=Path(args.public_faq_registry).resolve(),
            public_guide_community_hub_path=Path(args.public_guide_community_hub).resolve(),
            open_run_journey_path=Path(args.open_run_journey).resolve(),
            public_feature_registry_path=Path(args.public_feature_registry).resolve(),
            public_landing_manifest_path=Path(args.public_landing_manifest).resolve(),
            generated_at=_normalized_payload(actual).get("generated_at") or actual.get("generated_at"),
        )
        if actual.get("contract_name") != "fleet.next90_m138_hero_path_projections":
            issues.append("generated artifact contract_name is missing or unexpected")
        if actual.get("package_id") != "next90-m138-fleet-bind-ready-for-tonight-gates-role-kit-registry-vtt-export-target-accep":
            issues.append("generated artifact package_id drifted from the assigned Fleet M138 package")
        if _normalized_payload(actual) != _normalized_payload(expected):
            for key, message in (
                ("status", "projection status drifted from recomputed hero-path projection truth"),
                ("canonical_monitors", "canonical monitors drifted from recomputed hero-path projection truth"),
                ("projection_summary", "projection summary drifted from recomputed hero-path projection truth"),
                ("projections", "projection bodies drifted from recomputed hero-path projection truth"),
                ("public_truth_projection", "public truth projection drifted from recomputed hero-path projection truth"),
                ("package_closeout", "package closeout drifted from recomputed hero-path projection truth"),
                ("source_inputs", "source input links drifted from recomputed source truth"),
            ):
                _compare(issues, actual, expected, key, message)
            if not issues:
                issues.append("generated artifact contains unexpected drift outside the allowed generated_at field")

    result = {"status": "pass" if not issues else "fail", "artifact": str(artifact_path), "issues": issues}
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif issues:
        print("M138 hero-path projections verifier failed:", file=sys.stderr)
        for issue in issues:
            print(f" - {issue}", file=sys.stderr)
    else:
        print("M138 hero-path projections verifier passed")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
