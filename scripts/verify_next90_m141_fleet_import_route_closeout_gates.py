#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

try:
    from scripts.materialize_next90_m141_fleet_import_route_closeout_gates import (
        DEFAULT_OUTPUT,
        DESIGN_QUEUE_STAGING,
        ENGINE_PROOF_PACK,
        FLEET_QUEUE_STAGING,
        IMPORT_PARITY_CERTIFICATION,
        IMPORT_RECEIPTS_DOC,
        LEGACY_CHROME_POLICY,
        NEXT90_GUIDE,
        PARITY_ACCEPTANCE_MATRIX,
        PARITY_AUDIT,
        PUBLISHED,
        SUCCESSOR_REGISTRY,
        UI_RELEASE_GATE,
        VETERAN_TASK_TIME_GATE,
        VISUAL_FAMILIARITY_GATE,
        build_payload,
    )
except ModuleNotFoundError:
    from materialize_next90_m141_fleet_import_route_closeout_gates import (  # type: ignore
        DEFAULT_OUTPUT,
        DESIGN_QUEUE_STAGING,
        ENGINE_PROOF_PACK,
        FLEET_QUEUE_STAGING,
        IMPORT_PARITY_CERTIFICATION,
        IMPORT_RECEIPTS_DOC,
        LEGACY_CHROME_POLICY,
        NEXT90_GUIDE,
        PARITY_ACCEPTANCE_MATRIX,
        PARITY_AUDIT,
        PUBLISHED,
        SUCCESSOR_REGISTRY,
        UI_RELEASE_GATE,
        VETERAN_TASK_TIME_GATE,
        VISUAL_FAMILIARITY_GATE,
        build_payload,
    )


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify the Fleet M141 import-route closeout gate packet.")
    parser.add_argument("--artifact", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--published-root", default=str(PUBLISHED))
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--fleet-queue-staging", default=str(FLEET_QUEUE_STAGING))
    parser.add_argument("--design-queue-staging", default=str(DESIGN_QUEUE_STAGING))
    parser.add_argument("--next90-guide", default=str(NEXT90_GUIDE))
    parser.add_argument("--parity-acceptance-matrix", default=str(PARITY_ACCEPTANCE_MATRIX))
    parser.add_argument("--legacy-chrome-policy", default=str(LEGACY_CHROME_POLICY))
    parser.add_argument("--parity-audit", default=str(PARITY_AUDIT))
    parser.add_argument("--visual-familiarity-gate", default=str(VISUAL_FAMILIARITY_GATE))
    parser.add_argument("--veteran-task-time-gate", default=str(VETERAN_TASK_TIME_GATE))
    parser.add_argument("--ui-release-gate", default=str(UI_RELEASE_GATE))
    parser.add_argument("--import-receipts-doc", default=str(IMPORT_RECEIPTS_DOC))
    parser.add_argument("--import-parity-certification", default=str(IMPORT_PARITY_CERTIFICATION))
    parser.add_argument("--engine-proof-pack", default=str(ENGINE_PROOF_PACK))
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
            parity_acceptance_matrix_path=Path(args.parity_acceptance_matrix).resolve(),
            legacy_chrome_policy_path=Path(args.legacy_chrome_policy).resolve(),
            parity_audit_path=Path(args.parity_audit).resolve(),
            visual_familiarity_gate_path=Path(args.visual_familiarity_gate).resolve(),
            veteran_task_time_gate_path=Path(args.veteran_task_time_gate).resolve(),
            ui_release_gate_path=Path(args.ui_release_gate).resolve(),
            import_receipts_doc_path=Path(args.import_receipts_doc).resolve(),
            import_parity_certification_path=Path(args.import_parity_certification).resolve(),
            engine_proof_pack_path=Path(args.engine_proof_pack).resolve(),
            generated_at=_normalized_payload(actual).get("generated_at") or actual.get("generated_at"),
        )
        if actual.get("contract_name") != "fleet.next90_m141_import_route_closeout_gates":
            issues.append("generated artifact contract_name is missing or unexpected")
        if actual.get("package_id") != "next90-m141-fleet-fail-closeout-when-any-of-the-five-route-or-family-rows-in-this-milest":
            issues.append("generated artifact package_id drifted from the assigned Fleet M141 package")
        if _normalized_payload(actual) != _normalized_payload(expected):
            for key, message in (
                ("status", "closeout-gate status drifted from recomputed M141 truth"),
                ("canonical_monitors", "canonical monitors drifted from recomputed M141 truth"),
                ("runtime_monitors", "runtime monitors drifted from recomputed M141 truth"),
                ("monitor_summary", "monitor summary drifted from recomputed M141 truth"),
                ("package_closeout", "package closeout drifted from recomputed M141 truth"),
                ("source_inputs", "source input links drifted from recomputed source truth"),
            ):
                _compare(issues, actual, expected, key, message)
            if not issues:
                issues.append("generated artifact contains unexpected drift outside the allowed generated_at field")

    result = {"status": "pass" if not issues else "fail", "artifact": str(artifact_path), "issues": issues}
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif issues:
        print("M141 import-route closeout gate verifier failed:", file=sys.stderr)
        for issue in issues:
            print(f" - {issue}", file=sys.stderr)
    else:
        print("M141 import-route closeout gate verifier passed")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
