#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

try:
    from scripts.materialize_next90_m133_fleet_media_social_horizon_monitors import (
        BUILD_EXPLAIN_ARTIFACT_TRUTH_POLICY,
        COMMUNITY_SAFETY_STATES,
        DEFAULT_OUTPUT,
        DESIGN_QUEUE_STAGING,
        EXTERNAL_TOOLS_PLANE,
        FLAGSHIP_READINESS,
        HORIZON_REGISTRY,
        HUB_LOCAL_RELEASE_PROOF,
        JOURNEY_GATES,
        MEDIA_LOCAL_RELEASE_PROOF,
        MEDIA_SOCIAL_LTD_GUIDE,
        NEXT90_GUIDE,
        PROVIDER_STEWARDSHIP,
        QUEUE_STAGING,
        RELEASE_CHANNEL,
        SUCCESSOR_REGISTRY,
        build_payload,
    )
except ModuleNotFoundError:
    from materialize_next90_m133_fleet_media_social_horizon_monitors import (  # type: ignore
        BUILD_EXPLAIN_ARTIFACT_TRUTH_POLICY,
        COMMUNITY_SAFETY_STATES,
        DEFAULT_OUTPUT,
        DESIGN_QUEUE_STAGING,
        EXTERNAL_TOOLS_PLANE,
        FLAGSHIP_READINESS,
        HORIZON_REGISTRY,
        HUB_LOCAL_RELEASE_PROOF,
        JOURNEY_GATES,
        MEDIA_LOCAL_RELEASE_PROOF,
        MEDIA_SOCIAL_LTD_GUIDE,
        NEXT90_GUIDE,
        PROVIDER_STEWARDSHIP,
        QUEUE_STAGING,
        RELEASE_CHANNEL,
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
    parser = argparse.ArgumentParser(description="Verify the Fleet M133 media/social horizon monitor packet.")
    parser.add_argument("--artifact", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--queue-staging", default=str(QUEUE_STAGING))
    parser.add_argument("--design-queue-staging", default=str(DESIGN_QUEUE_STAGING))
    parser.add_argument("--next90-guide", default=str(NEXT90_GUIDE))
    parser.add_argument("--horizon-registry", default=str(HORIZON_REGISTRY))
    parser.add_argument("--media-social-ltd-guide", default=str(MEDIA_SOCIAL_LTD_GUIDE))
    parser.add_argument("--external-tools-plane", default=str(EXTERNAL_TOOLS_PLANE))
    parser.add_argument(
        "--build-explain-artifact-truth-policy",
        default=str(BUILD_EXPLAIN_ARTIFACT_TRUTH_POLICY),
    )
    parser.add_argument("--community-safety-states", default=str(COMMUNITY_SAFETY_STATES))
    parser.add_argument("--journey-gates", default=str(JOURNEY_GATES))
    parser.add_argument("--flagship-readiness", default=str(FLAGSHIP_READINESS))
    parser.add_argument("--provider-stewardship", default=str(PROVIDER_STEWARDSHIP))
    parser.add_argument("--media-local-release-proof", default=str(MEDIA_LOCAL_RELEASE_PROOF))
    parser.add_argument("--hub-local-release-proof", default=str(HUB_LOCAL_RELEASE_PROOF))
    parser.add_argument("--release-channel", default=str(RELEASE_CHANNEL))
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
            horizon_registry_path=Path(args.horizon_registry).resolve(),
            media_social_ltd_guide_path=Path(args.media_social_ltd_guide).resolve(),
            external_tools_plane_path=Path(args.external_tools_plane).resolve(),
            build_explain_artifact_truth_policy_path=Path(args.build_explain_artifact_truth_policy).resolve(),
            community_safety_states_path=Path(args.community_safety_states).resolve(),
            journey_gates_path=Path(args.journey_gates).resolve(),
            flagship_readiness_path=Path(args.flagship_readiness).resolve(),
            provider_stewardship_path=Path(args.provider_stewardship).resolve(),
            media_local_release_proof_path=Path(args.media_local_release_proof).resolve(),
            hub_local_release_proof_path=Path(args.hub_local_release_proof).resolve(),
            release_channel_path=Path(args.release_channel).resolve(),
            generated_at=str(actual.get("generated_at") or "").strip() or None,
        )
        if actual.get("contract_name") != "fleet.next90_m133_media_social_horizon_monitors":
            issues.append("generated artifact contract_name is missing or unexpected")
        if actual.get("package_id") != "next90-m133-fleet-monitor-media-social-horizon-proof-freshness-consent-gat":
            issues.append("generated artifact package_id drifted from the assigned Fleet M133 package")
        if _normalized_payload(actual) != _normalized_payload(expected):
            for key, message in (
                ("status", "monitor status drifted from recomputed media/social horizon truth"),
                ("canonical_alignment", "canonical alignment drifted from queue and registry truth"),
                ("canonical_monitors", "canonical monitor sections drifted from media/social horizon canon"),
                ("runtime_monitors", "runtime monitor sections drifted from recomputed media/social evidence"),
                ("monitor_summary", "monitor summary drifted from recomputed media/social evidence"),
                ("package_closeout", "package closeout posture drifted from recomputed media/social evidence"),
                ("source_inputs", "source input links drifted from recomputed source truth"),
                ("milestone_id", "milestone_id drifted from the assigned Fleet M133 package"),
                ("frontier_id", "frontier_id drifted from the assigned Fleet M133 package"),
            ):
                _compare(issues, actual, expected, key, message)
            if not issues:
                issues.append("generated artifact contains unexpected drift outside the allowed generated_at field")

    result = {"status": "pass" if not issues else "fail", "artifact": str(artifact_path), "issues": issues}
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif issues:
        print("M133 media/social horizon monitor verifier failed:", file=sys.stderr)
        for issue in issues:
            print(f" - {issue}", file=sys.stderr)
    else:
        print("M133 media/social horizon monitor verifier passed")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
