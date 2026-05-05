#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

try:
    from scripts.materialize_next90_m129_fleet_participation_lane_receipts import (
        ADR_PATH,
        DEFAULT_OUTPUT,
        DESIGN_QUEUE_STAGING,
        FLEET_AGENT_TEMPLATE,
        FLEET_PROJECT,
        FLEET_PUBLISHED_ROOT,
        HUB_PROJECT,
        HUB_PUBLISHED_ROOT,
        NEXT90_GUIDE,
        OWNERSHIP_MATRIX,
        PACKAGE_ID,
        QUEUE_STAGING,
        REGISTRY_PUBLISHED_ROOT,
        STATUS_PLANE,
        SUCCESSOR_REGISTRY,
        WORKFLOW_PATH,
        build_payload,
    )
except ModuleNotFoundError:
    from materialize_next90_m129_fleet_participation_lane_receipts import (  # type: ignore
        ADR_PATH,
        DEFAULT_OUTPUT,
        DESIGN_QUEUE_STAGING,
        FLEET_AGENT_TEMPLATE,
        FLEET_PROJECT,
        FLEET_PUBLISHED_ROOT,
        HUB_PROJECT,
        HUB_PUBLISHED_ROOT,
        NEXT90_GUIDE,
        OWNERSHIP_MATRIX,
        PACKAGE_ID,
        QUEUE_STAGING,
        REGISTRY_PUBLISHED_ROOT,
        STATUS_PLANE,
        SUCCESSOR_REGISTRY,
        WORKFLOW_PATH,
        build_payload,
    )


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify the Fleet M129 participation-lane receipt packet.")
    parser.add_argument("--artifact", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--queue-staging", default=str(QUEUE_STAGING))
    parser.add_argument("--design-queue-staging", default=str(DESIGN_QUEUE_STAGING))
    parser.add_argument("--next90-guide", default=str(NEXT90_GUIDE))
    parser.add_argument("--adr", default=str(ADR_PATH))
    parser.add_argument("--workflow", default=str(WORKFLOW_PATH))
    parser.add_argument("--ownership-matrix", default=str(OWNERSHIP_MATRIX))
    parser.add_argument("--fleet-project", default=str(FLEET_PROJECT))
    parser.add_argument("--hub-project", default=str(HUB_PROJECT))
    parser.add_argument("--fleet-agent-template", default=str(FLEET_AGENT_TEMPLATE))
    parser.add_argument("--status-plane", default=str(STATUS_PLANE))
    parser.add_argument("--fleet-published-root", default=str(FLEET_PUBLISHED_ROOT))
    parser.add_argument("--hub-published-root", default=str(HUB_PUBLISHED_ROOT))
    parser.add_argument("--registry-published-root", default=str(REGISTRY_PUBLISHED_ROOT))
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
            adr_path=Path(args.adr).resolve(),
            workflow_path=Path(args.workflow).resolve(),
            ownership_matrix_path=Path(args.ownership_matrix).resolve(),
            fleet_project_path=Path(args.fleet_project).resolve(),
            hub_project_path=Path(args.hub_project).resolve(),
            fleet_agent_template_path=Path(args.fleet_agent_template).resolve(),
            status_plane_path=Path(args.status_plane).resolve(),
            fleet_published_root=Path(args.fleet_published_root).resolve(),
            hub_published_root=Path(args.hub_published_root).resolve(),
            registry_published_root=Path(args.registry_published_root).resolve(),
            generated_at=str(actual.get("generated_at") or "").strip() or None,
        )
        if actual.get("contract_name") != "fleet.next90_m129_participation_lane_receipts":
            issues.append("generated artifact contract_name is missing or unexpected")
        if actual.get("package_id") != PACKAGE_ID:
            issues.append("generated artifact package_id drifted from the assigned Fleet M129 package")
        if _normalized_payload(actual) != _normalized_payload(expected):
            for key, message in (
                ("status", "monitor status drifted from recomputed participation-lane truth"),
                ("canonical_alignment", "canonical alignment drifted from queue and registry truth"),
                ("canonical_monitors", "canonical monitor sections drifted from participation canon"),
                ("runtime_monitors", "runtime monitor sections drifted from recomputed participation evidence"),
                ("monitor_summary", "monitor summary drifted from recomputed participation evidence"),
                ("package_closeout", "package closeout posture drifted from recomputed participation evidence"),
                ("source_inputs", "source input links drifted from recomputed source truth"),
                ("milestone_id", "milestone_id drifted from the assigned Fleet M129 package"),
                ("frontier_id", "frontier_id drifted from the assigned Fleet M129 package"),
            ):
                _compare(issues, actual, expected, key, message)
            if not issues:
                issues.append("generated artifact contains unexpected drift outside the allowed generated_at field")

    result = {"status": "pass" if not issues else "fail", "artifact": str(artifact_path), "issues": issues}
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif issues:
        print("M129 participation-lane receipt verifier failed:", file=sys.stderr)
        for issue in issues:
            print(f" - {issue}", file=sys.stderr)
    else:
        print("M129 participation-lane receipt verifier passed")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
