#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

try:
    from scripts.materialize_next90_m140_fleet_portability_and_cadence_closeout_gates import (
        CREATOR_OPERATING_SYSTEM,
        DEFAULT_OUTPUT,
        DESIGN_QUEUE_STAGING,
        FLAGSHIP_READINESS,
        FLEET_QUEUE_STAGING,
        LTD_CADENCE_REGISTRY,
        LTD_CADENCE_SYSTEM,
        LTD_RUNTIME_REGISTRY,
        NEXT90_GUIDE,
        PUBLIC_FAQ,
        PUBLIC_FAQ_REGISTRY,
        PUBLIC_FEATURE_REGISTRY,
        PUBLIC_LANDING_MANIFEST,
        PUBLISHED,
        ROADMAP,
        RUNNER_PASSPORT_ACCEPTANCE,
        RUNNER_PASSPORT_DOC,
        SUCCESSOR_REGISTRY,
        WORLD_DISPATCH_DOC,
        WORLD_DISPATCH_GATES,
        build_payload,
    )
except ModuleNotFoundError:
    from materialize_next90_m140_fleet_portability_and_cadence_closeout_gates import (  # type: ignore
        CREATOR_OPERATING_SYSTEM,
        DEFAULT_OUTPUT,
        DESIGN_QUEUE_STAGING,
        FLAGSHIP_READINESS,
        FLEET_QUEUE_STAGING,
        LTD_CADENCE_REGISTRY,
        LTD_CADENCE_SYSTEM,
        LTD_RUNTIME_REGISTRY,
        NEXT90_GUIDE,
        PUBLIC_FAQ,
        PUBLIC_FAQ_REGISTRY,
        PUBLIC_FEATURE_REGISTRY,
        PUBLIC_LANDING_MANIFEST,
        PUBLISHED,
        ROADMAP,
        RUNNER_PASSPORT_ACCEPTANCE,
        RUNNER_PASSPORT_DOC,
        SUCCESSOR_REGISTRY,
        WORLD_DISPATCH_DOC,
        WORLD_DISPATCH_GATES,
        build_payload,
    )


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify the Fleet M140 portability/cadence closeout gate packet.")
    parser.add_argument("--artifact", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--published-root", default=str(PUBLISHED))
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--fleet-queue-staging", default=str(FLEET_QUEUE_STAGING))
    parser.add_argument("--design-queue-staging", default=str(DESIGN_QUEUE_STAGING))
    parser.add_argument("--next90-guide", default=str(NEXT90_GUIDE))
    parser.add_argument("--roadmap", default=str(ROADMAP))
    parser.add_argument("--runner-passport-doc", default=str(RUNNER_PASSPORT_DOC))
    parser.add_argument("--runner-passport-acceptance", default=str(RUNNER_PASSPORT_ACCEPTANCE))
    parser.add_argument("--world-dispatch-doc", default=str(WORLD_DISPATCH_DOC))
    parser.add_argument("--world-dispatch-gates", default=str(WORLD_DISPATCH_GATES))
    parser.add_argument("--creator-operating-system", default=str(CREATOR_OPERATING_SYSTEM))
    parser.add_argument("--ltd-cadence-system", default=str(LTD_CADENCE_SYSTEM))
    parser.add_argument("--ltd-cadence-registry", default=str(LTD_CADENCE_REGISTRY))
    parser.add_argument("--ltd-runtime-registry", default=str(LTD_RUNTIME_REGISTRY))
    parser.add_argument("--public-faq", default=str(PUBLIC_FAQ))
    parser.add_argument("--public-faq-registry", default=str(PUBLIC_FAQ_REGISTRY))
    parser.add_argument("--public-feature-registry", default=str(PUBLIC_FEATURE_REGISTRY))
    parser.add_argument("--public-landing-manifest", default=str(PUBLIC_LANDING_MANIFEST))
    parser.add_argument("--flagship-readiness", default=str(FLAGSHIP_READINESS))
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
            published_root=Path(args.published_root).resolve(),
            registry_path=Path(args.successor_registry).resolve(),
            fleet_queue_path=Path(args.fleet_queue_staging).resolve(),
            design_queue_path=Path(args.design_queue_staging).resolve(),
            next90_guide_path=Path(args.next90_guide).resolve(),
            roadmap_path=Path(args.roadmap).resolve(),
            runner_passport_doc_path=Path(args.runner_passport_doc).resolve(),
            runner_passport_acceptance_path=Path(args.runner_passport_acceptance).resolve(),
            world_dispatch_doc_path=Path(args.world_dispatch_doc).resolve(),
            world_dispatch_gates_path=Path(args.world_dispatch_gates).resolve(),
            creator_operating_system_path=Path(args.creator_operating_system).resolve(),
            ltd_cadence_system_path=Path(args.ltd_cadence_system).resolve(),
            ltd_cadence_registry_path=Path(args.ltd_cadence_registry).resolve(),
            ltd_runtime_registry_path=Path(args.ltd_runtime_registry).resolve(),
            public_faq_path=Path(args.public_faq).resolve(),
            public_faq_registry_path=Path(args.public_faq_registry).resolve(),
            public_feature_registry_path=Path(args.public_feature_registry).resolve(),
            public_landing_manifest_path=Path(args.public_landing_manifest).resolve(),
            flagship_readiness_path=Path(args.flagship_readiness).resolve(),
            generated_at=_normalized_payload(actual).get("generated_at") or actual.get("generated_at"),
        )
        if actual.get("contract_name") != "fleet.next90_m140_portability_and_cadence_closeout_gates":
            issues.append("generated artifact contract_name is missing or unexpected")
        if actual.get("package_id") != "next90-m140-fleet-fail-closeout-when-runner-passport-proof-weekly-dispatch-cadence-creat":
            issues.append("generated artifact package_id drifted from the assigned Fleet M140 package")
        if _normalized_payload(actual) != _normalized_payload(expected):
            for key, message in (
                ("status", "closeout-gate status drifted from recomputed M140 truth"),
                ("canonical_monitors", "canonical monitors drifted from recomputed M140 truth"),
                ("runtime_monitors", "runtime monitors drifted from recomputed M140 truth"),
                ("monitor_summary", "monitor summary drifted from recomputed M140 truth"),
                ("package_closeout", "package closeout drifted from recomputed M140 truth"),
                ("source_inputs", "source input links drifted from recomputed source truth"),
            ):
                _compare(issues, actual, expected, key, message)
            if not issues:
                issues.append("generated artifact contains unexpected drift outside the allowed generated_at field")

    result = {"status": "pass" if not issues else "fail", "artifact": str(artifact_path), "issues": issues}
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif issues:
        print("M140 portability/cadence closeout gate verifier failed:", file=sys.stderr)
        for issue in issues:
            print(f" - {issue}", file=sys.stderr)
    else:
        print("M140 portability/cadence closeout gate verifier passed")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
