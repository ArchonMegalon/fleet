#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

try:
    from scripts.materialize_next90_m137_fleet_ecosystem_seam_monitors import (
        COMMUNITY_SAFETY_STATES,
        CREATOR_PUBLICATION_POLICY,
        DEFAULT_OUTPUT,
        DESIGN_QUEUE_STAGING,
        EXTERNAL_TOOLS_PLANE,
        FLEET_QUEUE_STAGING,
        FLAGSHIP_READINESS,
        HORIZON_REGISTRY,
        JOURNEY_GATES,
        LTD_INTEGRATION_GUIDE,
        M131_PUBLIC_GUIDE_GATES,
        M133_MEDIA_SOCIAL_MONITORS,
        NEXT90_GUIDE,
        OPEN_RUNS_AND_COMMUNITY_HUB,
        OPEN_RUNS_REPUTATION_AND_SEASONAL_HONORS,
        PUBLIC_CONCIERGE_WORKFLOWS,
        PUBLIC_FEATURE_REGISTRY,
        PUBLIC_GUIDE_ROOT,
        PUBLIC_LANDING_MANIFEST,
        PUBLIC_RELEASE_EXPERIENCE,
        ROADMAP,
        SUCCESSOR_REGISTRY,
        build_payload,
    )
except ModuleNotFoundError:
    from materialize_next90_m137_fleet_ecosystem_seam_monitors import (  # type: ignore
        COMMUNITY_SAFETY_STATES,
        CREATOR_PUBLICATION_POLICY,
        DEFAULT_OUTPUT,
        DESIGN_QUEUE_STAGING,
        EXTERNAL_TOOLS_PLANE,
        FLEET_QUEUE_STAGING,
        FLAGSHIP_READINESS,
        HORIZON_REGISTRY,
        JOURNEY_GATES,
        LTD_INTEGRATION_GUIDE,
        M131_PUBLIC_GUIDE_GATES,
        M133_MEDIA_SOCIAL_MONITORS,
        NEXT90_GUIDE,
        OPEN_RUNS_AND_COMMUNITY_HUB,
        OPEN_RUNS_REPUTATION_AND_SEASONAL_HONORS,
        PUBLIC_CONCIERGE_WORKFLOWS,
        PUBLIC_FEATURE_REGISTRY,
        PUBLIC_GUIDE_ROOT,
        PUBLIC_LANDING_MANIFEST,
        PUBLIC_RELEASE_EXPERIENCE,
        ROADMAP,
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
    parser = argparse.ArgumentParser(description="Verify the Fleet M137 ecosystem seam monitor packet.")
    parser.add_argument("--artifact", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--fleet-queue-staging", default=str(FLEET_QUEUE_STAGING))
    parser.add_argument("--design-queue-staging", default=str(DESIGN_QUEUE_STAGING))
    parser.add_argument("--next90-guide", default=str(NEXT90_GUIDE))
    parser.add_argument("--roadmap", default=str(ROADMAP))
    parser.add_argument("--horizon-registry", default=str(HORIZON_REGISTRY))
    parser.add_argument("--ltd-integration-guide", default=str(LTD_INTEGRATION_GUIDE))
    parser.add_argument("--external-tools-plane", default=str(EXTERNAL_TOOLS_PLANE))
    parser.add_argument("--open-runs-community-hub", default=str(OPEN_RUNS_AND_COMMUNITY_HUB))
    parser.add_argument("--open-runs-honors", default=str(OPEN_RUNS_REPUTATION_AND_SEASONAL_HONORS))
    parser.add_argument("--community-safety-states", default=str(COMMUNITY_SAFETY_STATES))
    parser.add_argument("--creator-publication-policy", default=str(CREATOR_PUBLICATION_POLICY))
    parser.add_argument("--public-concierge-workflows", default=str(PUBLIC_CONCIERGE_WORKFLOWS))
    parser.add_argument("--public-feature-registry", default=str(PUBLIC_FEATURE_REGISTRY))
    parser.add_argument("--public-landing-manifest", default=str(PUBLIC_LANDING_MANIFEST))
    parser.add_argument("--public-release-experience", default=str(PUBLIC_RELEASE_EXPERIENCE))
    parser.add_argument("--public-guide-root", default=str(PUBLIC_GUIDE_ROOT))
    parser.add_argument("--m133-media-social-monitors", default=str(M133_MEDIA_SOCIAL_MONITORS))
    parser.add_argument("--m131-public-guide-gates", default=str(M131_PUBLIC_GUIDE_GATES))
    parser.add_argument("--flagship-readiness", default=str(FLAGSHIP_READINESS))
    parser.add_argument("--journey-gates", default=str(JOURNEY_GATES))
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
            roadmap_path=Path(args.roadmap).resolve(),
            horizon_registry_path=Path(args.horizon_registry).resolve(),
            ltd_integration_guide_path=Path(args.ltd_integration_guide).resolve(),
            external_tools_plane_path=Path(args.external_tools_plane).resolve(),
            open_runs_community_hub_path=Path(args.open_runs_community_hub).resolve(),
            open_runs_honors_path=Path(args.open_runs_honors).resolve(),
            community_safety_states_path=Path(args.community_safety_states).resolve(),
            creator_publication_policy_path=Path(args.creator_publication_policy).resolve(),
            public_concierge_workflows_path=Path(args.public_concierge_workflows).resolve(),
            public_feature_registry_path=Path(args.public_feature_registry).resolve(),
            public_landing_manifest_path=Path(args.public_landing_manifest).resolve(),
            public_release_experience_path=Path(args.public_release_experience).resolve(),
            public_guide_root=Path(args.public_guide_root).resolve(),
            m133_media_social_monitors_path=Path(args.m133_media_social_monitors).resolve(),
            m131_public_guide_gates_path=Path(args.m131_public_guide_gates).resolve(),
            flagship_readiness_path=Path(args.flagship_readiness).resolve(),
            journey_gates_path=Path(args.journey_gates).resolve(),
            generated_at=_normalized_payload(actual).get("generated_at") or actual.get("generated_at"),
        )
        if actual.get("contract_name") != "fleet.next90_m137_ecosystem_seam_monitors":
            issues.append("generated artifact contract_name is missing or unexpected")
        if actual.get("package_id") != "next90-m137-fleet-monitor-unsupported-ecosystem-claims-stale-seam-proof-consent-drift-an":
            issues.append("generated artifact package_id drifted from the assigned Fleet M137 package")
        if _normalized_payload(actual) != _normalized_payload(expected):
            for key, message in (
                ("status", "monitor status drifted from recomputed ecosystem seam truth"),
                ("canonical_monitors", "canonical monitors drifted from recomputed ecosystem seam truth"),
                ("runtime_monitors", "runtime monitors drifted from recomputed ecosystem seam truth"),
                ("monitor_summary", "monitor summary drifted from recomputed ecosystem seam truth"),
                ("package_closeout", "package closeout drifted from recomputed ecosystem seam truth"),
                ("source_inputs", "source input links drifted from recomputed source truth"),
                ("milestone_id", "milestone_id drifted from the assigned Fleet M137 package"),
                ("frontier_id", "frontier_id drifted from the assigned Fleet M137 package"),
            ):
                _compare(issues, actual, expected, key, message)
            if not issues:
                issues.append("generated artifact contains unexpected drift outside the allowed generated_at field")

    result = {"status": "pass" if not issues else "fail", "artifact": str(artifact_path), "issues": issues}
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif issues:
        print("M137 ecosystem seam monitor verifier failed:", file=sys.stderr)
        for issue in issues:
            print(f" - {issue}", file=sys.stderr)
    else:
        print("M137 ecosystem seam monitor verifier passed")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
