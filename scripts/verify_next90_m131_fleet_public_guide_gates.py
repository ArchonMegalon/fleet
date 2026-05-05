#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

try:
    from scripts.materialize_next90_m131_fleet_public_guide_gates import (
        DEFAULT_OUTPUT,
        DESIGN_QUEUE_STAGING,
        FLAGSHIP_QUEUE_SCRIPT,
        GUIDE_REPO_ROOT,
        GUIDE_VERIFY_SCRIPT,
        KATTEB_GUIDE_LANE,
        NEXT90_GUIDE,
        PUBLIC_GROWTH_STACK,
        PUBLIC_GUIDE_EXPORT_MANIFEST,
        PUBLIC_GUIDE_POLICY,
        PUBLIC_SIGNAL_PIPELINE,
        PUBLIC_VISIBILITY_POLICY,
        QUEUE_STAGING,
        SUCCESSOR_REGISTRY,
        build_payload,
    )
except ModuleNotFoundError:
    from materialize_next90_m131_fleet_public_guide_gates import (  # type: ignore
        DEFAULT_OUTPUT,
        DESIGN_QUEUE_STAGING,
        FLAGSHIP_QUEUE_SCRIPT,
        GUIDE_REPO_ROOT,
        GUIDE_VERIFY_SCRIPT,
        KATTEB_GUIDE_LANE,
        NEXT90_GUIDE,
        PUBLIC_GROWTH_STACK,
        PUBLIC_GUIDE_EXPORT_MANIFEST,
        PUBLIC_GUIDE_POLICY,
        PUBLIC_SIGNAL_PIPELINE,
        PUBLIC_VISIBILITY_POLICY,
        QUEUE_STAGING,
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
    parser = argparse.ArgumentParser(description="Verify the Fleet M131 public-guide gates packet.")
    parser.add_argument("--artifact", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--queue-staging", default=str(QUEUE_STAGING))
    parser.add_argument("--design-queue-staging", default=str(DESIGN_QUEUE_STAGING))
    parser.add_argument("--next90-guide", default=str(NEXT90_GUIDE))
    parser.add_argument("--growth-stack", default=str(PUBLIC_GROWTH_STACK))
    parser.add_argument("--guide-export-manifest", default=str(PUBLIC_GUIDE_EXPORT_MANIFEST))
    parser.add_argument("--guide-policy", default=str(PUBLIC_GUIDE_POLICY))
    parser.add_argument("--visibility-policy", default=str(PUBLIC_VISIBILITY_POLICY))
    parser.add_argument("--signal-pipeline", default=str(PUBLIC_SIGNAL_PIPELINE))
    parser.add_argument("--katteb-lane", default=str(KATTEB_GUIDE_LANE))
    parser.add_argument("--guide-verify-script", default=str(GUIDE_VERIFY_SCRIPT))
    parser.add_argument("--flagship-queue-script", default=str(FLAGSHIP_QUEUE_SCRIPT))
    parser.add_argument("--guide-repo-root", default=str(GUIDE_REPO_ROOT))
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
            growth_stack_path=Path(args.growth_stack).resolve(),
            guide_export_manifest_path=Path(args.guide_export_manifest).resolve(),
            guide_policy_path=Path(args.guide_policy).resolve(),
            visibility_policy_path=Path(args.visibility_policy).resolve(),
            signal_pipeline_path=Path(args.signal_pipeline).resolve(),
            katteb_lane_path=Path(args.katteb_lane).resolve(),
            guide_verify_script_path=Path(args.guide_verify_script).resolve(),
            flagship_queue_script_path=Path(args.flagship_queue_script).resolve(),
            guide_repo_root=Path(args.guide_repo_root).resolve(),
            generated_at=str(actual.get("generated_at") or "").strip() or None,
        )
        if actual.get("contract_name") != "fleet.next90_m131_public_guide_gates":
            issues.append("generated artifact contract_name is missing or unexpected")
        if actual.get("package_id") != "next90-m131-fleet-verify-public-guide-regeneration-visibility-source-fresh":
            issues.append("generated artifact package_id drifted from the assigned Fleet M131 package")
        if _normalized_payload(actual) != _normalized_payload(expected):
            for key, message in (
                ("status", "monitor status drifted from recomputed public-guide truth"),
                ("canonical_alignment", "canonical alignment drifted from queue and registry truth"),
                ("canonical_monitors", "canonical monitor sections drifted from public-guide canon"),
                ("runtime_monitors", "runtime monitor sections drifted from recomputed guide evidence"),
                ("monitor_summary", "monitor summary drifted from recomputed guide evidence"),
                ("package_closeout", "package closeout posture drifted from recomputed guide evidence"),
                ("source_inputs", "source input links drifted from recomputed source truth"),
                ("milestone_id", "milestone_id drifted from the assigned Fleet M131 package"),
                ("frontier_id", "frontier_id drifted from the assigned Fleet M131 package"),
            ):
                _compare(issues, actual, expected, key, message)
            if not issues:
                issues.append("generated artifact contains unexpected drift outside the allowed generated_at field")

    result = {"status": "pass" if not issues else "fail", "artifact": str(artifact_path), "issues": issues}
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif issues:
        print("M131 public-guide gates verifier failed:", file=sys.stderr)
        for issue in issues:
            print(f" - {issue}", file=sys.stderr)
    else:
        print("M131 public-guide gates verifier passed")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
