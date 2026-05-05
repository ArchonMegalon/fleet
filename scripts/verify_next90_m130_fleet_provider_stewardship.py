#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

try:
    from scripts.materialize_next90_m130_fleet_provider_stewardship import (
        DEFAULT_OUTPUT,
        DEFAULT_LIVE_ADMIN_STATUS_OUTPUT,
        DEFAULT_LIVE_PROVIDER_CREDIT_OUTPUT,
        DESIGN_QUEUE_STAGING,
        EXTERNAL_TOOLS_PLANE,
        LTD_CAPABILITY_MAP,
        PROVIDER_ROUTE_STEWARDSHIP,
        QUEUE_STAGING,
        SUCCESSOR_REGISTRY,
        WEEKLY_GOVERNOR_PACKET,
        build_payload,
    )
except ModuleNotFoundError:
    from materialize_next90_m130_fleet_provider_stewardship import (  # type: ignore
        DEFAULT_OUTPUT,
        DEFAULT_LIVE_ADMIN_STATUS_OUTPUT,
        DEFAULT_LIVE_PROVIDER_CREDIT_OUTPUT,
        DESIGN_QUEUE_STAGING,
        EXTERNAL_TOOLS_PLANE,
        LTD_CAPABILITY_MAP,
        PROVIDER_ROUTE_STEWARDSHIP,
        QUEUE_STAGING,
        SUCCESSOR_REGISTRY,
        WEEKLY_GOVERNOR_PACKET,
        build_payload,
    )


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify the Fleet M130 provider stewardship monitor packet.")
    parser.add_argument("--artifact", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--queue-staging", default=str(QUEUE_STAGING))
    parser.add_argument("--design-queue-staging", default=str(DESIGN_QUEUE_STAGING))
    parser.add_argument("--external-tools-plane", default=str(EXTERNAL_TOOLS_PLANE))
    parser.add_argument("--ltd-capability-map", default=str(LTD_CAPABILITY_MAP))
    parser.add_argument("--provider-route-stewardship", default=str(PROVIDER_ROUTE_STEWARDSHIP))
    parser.add_argument("--weekly-governor-packet", default=str(WEEKLY_GOVERNOR_PACKET))
    parser.add_argument("--admin-status", default=str(DEFAULT_LIVE_ADMIN_STATUS_OUTPUT))
    parser.add_argument("--provider-credit", default=str(DEFAULT_LIVE_PROVIDER_CREDIT_OUTPUT))
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
            external_tools_plane_path=Path(args.external_tools_plane).resolve(),
            ltd_capability_map_path=Path(args.ltd_capability_map).resolve(),
            provider_route_stewardship_path=Path(args.provider_route_stewardship).resolve(),
            weekly_governor_packet_path=Path(args.weekly_governor_packet).resolve(),
            admin_status=_read_json(Path(args.admin_status).resolve()),
            provider_credit=_read_json(Path(args.provider_credit).resolve()),
            admin_status_source=str(Path(args.admin_status).resolve()),
            provider_credit_source=str(Path(args.provider_credit).resolve()),
            generated_at=str(actual.get("generated_at") or "").strip() or None,
        )
        if actual.get("contract_name") != "fleet.next90_m130_provider_stewardship_monitor":
            issues.append("generated artifact contract_name is missing or unexpected")
        if actual.get("package_id") != "next90-m130-fleet-add-provider-health-credit-runway-kill-switch-fallback-a":
            issues.append("generated artifact package_id drifted from the assigned Fleet M130 package")
        if _normalized_payload(actual) != _normalized_payload(expected):
            for key, message in (
                ("status", "monitor status drifted from recomputed stewardship truth"),
                ("canonical_alignment", "canonical alignment drifted from queue and registry truth"),
                ("canonical_monitors", "canonical monitor sections drifted from design-owned stewardship truth"),
                ("runtime_monitors", "runtime monitor sections drifted from recomputed admin/provider truth"),
                ("governor_monitors", "governor monitor section drifted from recomputed weekly governor truth"),
                ("package_closeout", "package closeout posture drifted from recomputed stewardship truth"),
                ("source_inputs", "source input links drifted from recomputed source truth"),
                ("milestone_id", "milestone_id drifted from the assigned Fleet M130 package"),
                ("frontier_id", "frontier_id drifted from the assigned Fleet M130 package"),
            ):
                _compare(issues, actual, expected, key, message)
            if not issues:
                issues.append("generated artifact contains unexpected drift outside the allowed generated_at field")

    result = {
        "status": "pass" if not issues else "fail",
        "artifact": str(artifact_path),
        "issues": issues,
    }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif issues:
        print("M130 provider stewardship verifier failed:", file=sys.stderr)
        for issue in issues:
            print(f" - {issue}", file=sys.stderr)
    else:
        print("M130 provider stewardship verifier passed")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
