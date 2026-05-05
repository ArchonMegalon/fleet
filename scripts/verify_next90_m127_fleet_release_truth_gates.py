#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

try:
    from scripts.materialize_next90_m127_fleet_release_truth_gates import (
        ACCEPTANCE_MATRIX,
        DEFAULT_OUTPUT,
        DESIGN_QUEUE_STAGING,
        EXTERNAL_PROOF_RUNBOOK,
        FLAGSHIP_PRODUCT_READINESS,
        NEXT90_GUIDE,
        PUBLIC_AUTO_UPDATE_POLICY,
        PUBLIC_DOWNLOADS_POLICY,
        QUEUE_STAGING,
        REPO_HARDENING_CHECKLIST,
        REPO_HYGIENE_POLICY,
        SUCCESSOR_REGISTRY,
        build_payload,
    )
except ModuleNotFoundError:
    from materialize_next90_m127_fleet_release_truth_gates import (  # type: ignore
        ACCEPTANCE_MATRIX,
        DEFAULT_OUTPUT,
        DESIGN_QUEUE_STAGING,
        EXTERNAL_PROOF_RUNBOOK,
        FLAGSHIP_PRODUCT_READINESS,
        NEXT90_GUIDE,
        PUBLIC_AUTO_UPDATE_POLICY,
        PUBLIC_DOWNLOADS_POLICY,
        QUEUE_STAGING,
        REPO_HARDENING_CHECKLIST,
        REPO_HYGIENE_POLICY,
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
    parser = argparse.ArgumentParser(description="Verify the Fleet M127 release-truth gate packet.")
    parser.add_argument("--artifact", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--queue-staging", default=str(QUEUE_STAGING))
    parser.add_argument("--design-queue-staging", default=str(DESIGN_QUEUE_STAGING))
    parser.add_argument("--next90-guide", default=str(NEXT90_GUIDE))
    parser.add_argument("--acceptance-matrix", default=str(ACCEPTANCE_MATRIX))
    parser.add_argument("--public-downloads-policy", default=str(PUBLIC_DOWNLOADS_POLICY))
    parser.add_argument("--public-auto-update-policy", default=str(PUBLIC_AUTO_UPDATE_POLICY))
    parser.add_argument("--repo-hardening-checklist", default=str(REPO_HARDENING_CHECKLIST))
    parser.add_argument("--repo-hygiene-policy", default=str(REPO_HYGIENE_POLICY))
    parser.add_argument("--external-proof-runbook", default=str(EXTERNAL_PROOF_RUNBOOK))
    parser.add_argument("--flagship-product-readiness", default=str(FLAGSHIP_PRODUCT_READINESS))
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
            acceptance_matrix_path=Path(args.acceptance_matrix).resolve(),
            public_downloads_policy_path=Path(args.public_downloads_policy).resolve(),
            public_auto_update_policy_path=Path(args.public_auto_update_policy).resolve(),
            repo_hardening_checklist_path=Path(args.repo_hardening_checklist).resolve(),
            repo_hygiene_policy_path=Path(args.repo_hygiene_policy).resolve(),
            external_proof_runbook_path=Path(args.external_proof_runbook).resolve(),
            flagship_product_readiness_path=Path(args.flagship_product_readiness).resolve(),
            generated_at=str(actual.get("generated_at") or "").strip() or None,
        )
        if actual.get("contract_name") != "fleet.next90_m127_release_truth_gate_monitor":
            issues.append("generated artifact contract_name is missing or unexpected")
        if actual.get("package_id") != "next90-m127-fleet-promote-platform-acceptance-release-evidence-packs-repo":
            issues.append("generated artifact package_id drifted from the assigned Fleet M127 package")
        if _normalized_payload(actual) != _normalized_payload(expected):
            for key, message in (
                ("status", "monitor status drifted from recomputed release-truth gate posture"),
                ("canonical_alignment", "canonical alignment drifted from queue and registry truth"),
                ("canonical_monitors", "canonical monitor sections drifted from release canon truth"),
                ("runtime_monitors", "runtime monitor sections drifted from recomputed release evidence truth"),
                ("gate_summary", "gate summary drifted from recomputed release-truth posture"),
                ("package_closeout", "package closeout posture drifted from recomputed release-truth posture"),
                ("source_inputs", "source input links drifted from recomputed source truth"),
                ("milestone_id", "milestone_id drifted from the assigned Fleet M127 package"),
                ("frontier_id", "frontier_id drifted from the assigned Fleet M127 package"),
            ):
                _compare(issues, actual, expected, key, message)
            if not issues:
                issues.append("generated artifact contains unexpected drift outside the allowed generated_at field")

    result = {"status": "pass" if not issues else "fail", "artifact": str(artifact_path), "issues": issues}
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif issues:
        print("M127 release-truth gates verifier failed:", file=sys.stderr)
        for issue in issues:
            print(f" - {issue}", file=sys.stderr)
    else:
        print("M127 release-truth gates verifier passed")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
