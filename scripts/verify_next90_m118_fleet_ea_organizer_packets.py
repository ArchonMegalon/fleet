#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

try:
    from scripts.materialize_next90_m118_fleet_ea_organizer_packets import (
        DEFAULT_OUTPUT,
        DESIGN_QUEUE_STAGING,
        EA_OPERATOR_SAFE_PACK,
        EA_ORGANIZER_PACKET_PACK,
        HUB_CREATOR_PUBLICATION_VERIFIER,
        HUB_LOCAL_RELEASE_PROOF,
        HUB_ORGANIZER_VERIFIER,
        QUEUE_STAGING,
        SUCCESSOR_REGISTRY,
        SUPPORT_PACKETS,
        WEEKLY_GOVERNOR_PACKET,
        build_payload,
    )
except ModuleNotFoundError:
    from materialize_next90_m118_fleet_ea_organizer_packets import (  # type: ignore
        DEFAULT_OUTPUT,
        DESIGN_QUEUE_STAGING,
        EA_OPERATOR_SAFE_PACK,
        EA_ORGANIZER_PACKET_PACK,
        HUB_CREATOR_PUBLICATION_VERIFIER,
        HUB_LOCAL_RELEASE_PROOF,
        HUB_ORGANIZER_VERIFIER,
        QUEUE_STAGING,
        SUCCESSOR_REGISTRY,
        SUPPORT_PACKETS,
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
    parser = argparse.ArgumentParser(description="Verify the Fleet M118 organizer operator packet.")
    parser.add_argument("--artifact", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--queue-staging", default=str(QUEUE_STAGING))
    parser.add_argument("--design-queue-staging", default=str(DESIGN_QUEUE_STAGING))
    parser.add_argument("--weekly-governor-packet", default=str(WEEKLY_GOVERNOR_PACKET))
    parser.add_argument("--support-packets", default=str(SUPPORT_PACKETS))
    parser.add_argument("--hub-local-release-proof", default=str(HUB_LOCAL_RELEASE_PROOF))
    parser.add_argument("--hub-organizer-verifier", default=str(HUB_ORGANIZER_VERIFIER))
    parser.add_argument("--hub-creator-publication-verifier", default=str(HUB_CREATOR_PUBLICATION_VERIFIER))
    parser.add_argument("--ea-operator-safe-pack", default=str(EA_OPERATOR_SAFE_PACK))
    parser.add_argument("--ea-organizer-packet-pack", default=str(EA_ORGANIZER_PACKET_PACK))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


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
            weekly_governor_packet_path=Path(args.weekly_governor_packet).resolve(),
            support_packets_path=Path(args.support_packets).resolve(),
            hub_local_release_proof_path=Path(args.hub_local_release_proof).resolve(),
            hub_organizer_verifier_path=Path(args.hub_organizer_verifier).resolve(),
            hub_creator_publication_verifier_path=Path(args.hub_creator_publication_verifier).resolve(),
            ea_operator_safe_pack_path=Path(args.ea_operator_safe_pack).resolve(),
            ea_organizer_packet_pack_path=Path(args.ea_organizer_packet_pack).resolve(),
            generated_at=str(actual.get("generated_at") or "").strip() or None,
        )
        if actual.get("contract_name") != "fleet.next90_m118_organizer_operator_packets":
            issues.append("generated artifact contract_name is missing or unexpected")
        if actual.get("package_id") != "next90-m118-fleet-ea-organizer-packets":
            issues.append("generated artifact package_id drifted from the assigned Fleet M118 package")
        if _normalized_payload(actual) != _normalized_payload(expected):
            for key, message in (
                ("status", "packet status drifted from recomputed organizer/operator truth"),
                ("status_reason", "packet status_reason drifted from recomputed organizer/operator truth"),
                ("agreement", "queue/registry agreement drifted from canonical package truth"),
                ("organizer_health", "organizer health drifted from recomputed sibling proof truth"),
                ("support_risk", "support risk drifted from recomputed support packet truth"),
                ("publication_readiness", "publication readiness drifted from recomputed sibling proof truth"),
                ("source_inputs", "source input timestamps or packet status drifted from recomputed upstream evidence"),
                ("source_packet_links", "source packet links drifted from recomputed upstream packet and receipt truth"),
                ("next_actions", "operator next actions drifted from recomputed blocker truth"),
            ):
                if actual.get(key) != expected.get(key):
                    issues.append(message)
            if not issues:
                issues.append("generated artifact contains unexpected drift outside the allowed generated_at field")

    result = {"status": "pass" if not issues else "fail", "artifact": str(artifact_path), "issues": issues}
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif issues:
        print("M118 organizer operator packet verifier failed:", file=sys.stderr)
        for issue in issues:
            print(f" - {issue}", file=sys.stderr)
    else:
        print("M118 organizer operator packet verifier passed")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
