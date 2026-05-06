#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

try:
    from scripts.materialize_next90_m142_fleet_route_local_proof_closeout_gates import (
        CLASSIC_DENSE_WORKBENCH_GATE,
        CORE_DENSE_RECEIPTS_DOC,
        DEFAULT_OUTPUT,
        DESIGN_QUEUE_STAGING,
        DESKTOP_VISUAL_FAMILIARITY_GATE,
        DESKTOP_WORKFLOW_EXECUTION_GATE,
        FLEET_QUEUE_STAGING,
        GENERATED_DIALOG_PARITY,
        GM_RUNBOARD_ROUTE,
        NEXT90_GUIDE,
        PARITY_AUDIT,
        PUBLISHED,
        SCREENSHOT_REVIEW_GATE,
        SECTION_HOST_RULESET_PARITY,
        SUCCESSOR_REGISTRY,
        UI_FLAGSHIP_RELEASE_GATE,
        UI_DIRECT_WORKFLOW_PROOF,
        UI_KIT_LOCAL_RELEASE_PROOF,
        UI_LOCAL_RELEASE_PROOF,
        VETERAN_TASK_TIME_GATE,
        WORKFLOW_PACK,
        build_payload,
    )
except ModuleNotFoundError:
    from materialize_next90_m142_fleet_route_local_proof_closeout_gates import (  # type: ignore
        CLASSIC_DENSE_WORKBENCH_GATE,
        CORE_DENSE_RECEIPTS_DOC,
        DEFAULT_OUTPUT,
        DESIGN_QUEUE_STAGING,
        DESKTOP_VISUAL_FAMILIARITY_GATE,
        DESKTOP_WORKFLOW_EXECUTION_GATE,
        FLEET_QUEUE_STAGING,
        GENERATED_DIALOG_PARITY,
        GM_RUNBOARD_ROUTE,
        NEXT90_GUIDE,
        PARITY_AUDIT,
        PUBLISHED,
        SCREENSHOT_REVIEW_GATE,
        SECTION_HOST_RULESET_PARITY,
        SUCCESSOR_REGISTRY,
        UI_FLAGSHIP_RELEASE_GATE,
        UI_DIRECT_WORKFLOW_PROOF,
        UI_KIT_LOCAL_RELEASE_PROOF,
        UI_LOCAL_RELEASE_PROOF,
        VETERAN_TASK_TIME_GATE,
        WORKFLOW_PACK,
        build_payload,
    )


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify the Fleet M142 route-local proof closeout gate packet.")
    parser.add_argument("--artifact", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--published-root", default=str(PUBLISHED))
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--fleet-queue-staging", default=str(FLEET_QUEUE_STAGING))
    parser.add_argument("--design-queue-staging", default=str(DESIGN_QUEUE_STAGING))
    parser.add_argument("--next90-guide", default=str(NEXT90_GUIDE))
    parser.add_argument("--workflow-pack", default=str(WORKFLOW_PACK))
    parser.add_argument("--parity-audit", default=str(PARITY_AUDIT))
    parser.add_argument("--desktop-visual-familiarity-gate", default=str(DESKTOP_VISUAL_FAMILIARITY_GATE))
    parser.add_argument("--desktop-workflow-execution-gate", default=str(DESKTOP_WORKFLOW_EXECUTION_GATE))
    parser.add_argument("--screenshot-review-gate", default=str(SCREENSHOT_REVIEW_GATE))
    parser.add_argument("--classic-dense-workbench-gate", default=str(CLASSIC_DENSE_WORKBENCH_GATE))
    parser.add_argument("--veteran-task-time-gate", default=str(VETERAN_TASK_TIME_GATE))
    parser.add_argument("--ui-flagship-release-gate", default=str(UI_FLAGSHIP_RELEASE_GATE))
    parser.add_argument("--ui-local-release-proof", default=str(UI_LOCAL_RELEASE_PROOF))
    parser.add_argument("--ui-kit-local-release-proof", default=str(UI_KIT_LOCAL_RELEASE_PROOF))
    parser.add_argument("--ui-direct-workflow-proof", default=str(UI_DIRECT_WORKFLOW_PROOF))
    parser.add_argument("--generated-dialog-parity", default=str(GENERATED_DIALOG_PARITY))
    parser.add_argument("--section-host-ruleset-parity", default=str(SECTION_HOST_RULESET_PARITY))
    parser.add_argument("--gm-runboard-route", default=str(GM_RUNBOARD_ROUTE))
    parser.add_argument("--core-dense-receipts-doc", default=str(CORE_DENSE_RECEIPTS_DOC))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def _normalized_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(payload)
    normalized.pop("generated_at", None)
    if "source_inputs" in normalized:
        normalized["source_inputs"] = _normalized_source_inputs(normalized.get("source_inputs") or {})
    return normalized


def _normalized_source_inputs(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    for key, value in (payload or {}).items():
        if not isinstance(value, dict):
            normalized[key] = value
            continue
        entry = dict(value)
        if entry.get("generated_at_source") == "file_mtime":
            entry.pop("generated_at", None)
        normalized[key] = entry
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
            workflow_pack_path=Path(args.workflow_pack).resolve(),
            parity_audit_path=Path(args.parity_audit).resolve(),
            desktop_visual_familiarity_gate_path=Path(args.desktop_visual_familiarity_gate).resolve(),
            desktop_workflow_execution_gate_path=Path(args.desktop_workflow_execution_gate).resolve(),
            screenshot_review_gate_path=Path(args.screenshot_review_gate).resolve(),
            classic_dense_workbench_gate_path=Path(args.classic_dense_workbench_gate).resolve(),
            veteran_task_time_gate_path=Path(args.veteran_task_time_gate).resolve(),
            ui_flagship_release_gate_path=Path(args.ui_flagship_release_gate).resolve(),
            ui_local_release_proof_path=Path(args.ui_local_release_proof).resolve(),
            ui_kit_local_release_proof_path=Path(args.ui_kit_local_release_proof).resolve(),
            ui_direct_workflow_proof_path=Path(args.ui_direct_workflow_proof).resolve(),
            generated_dialog_parity_path=Path(args.generated_dialog_parity).resolve(),
            section_host_ruleset_parity_path=Path(args.section_host_ruleset_parity).resolve(),
            gm_runboard_route_path=Path(args.gm_runboard_route).resolve(),
            core_dense_receipts_doc_path=Path(args.core_dense_receipts_doc).resolve(),
            generated_at=_normalized_payload(actual).get("generated_at") or actual.get("generated_at"),
        )
        if actual.get("contract_name") != "fleet.next90_m142_route_local_proof_closeout_gates":
            issues.append("generated artifact contract_name is missing or unexpected")
        if actual.get("package_id") != "next90-m142-fleet-fail-closeout-when-any-route-in-this-milestone-closes-on-family-prose":
            issues.append("generated artifact package_id drifted from the assigned Fleet M142 package")
        if _normalized_payload(actual) != _normalized_payload(expected):
            for key, message in (
                ("status", "closeout-gate status drifted from recomputed M142 truth"),
                ("canonical_monitors", "canonical monitors drifted from recomputed M142 truth"),
                ("runtime_monitors", "runtime monitors drifted from recomputed M142 truth"),
                ("monitor_summary", "monitor summary drifted from recomputed M142 truth"),
                ("package_closeout", "package closeout drifted from recomputed M142 truth"),
            ):
                _compare(issues, actual, expected, key, message)
            if _normalized_source_inputs(actual.get("source_inputs") or {}) != _normalized_source_inputs(expected.get("source_inputs") or {}):
                issues.append("source input links drifted from recomputed source truth")
            if not issues:
                issues.append("generated artifact contains unexpected drift outside the allowed generated_at field")

    result = {"status": "pass" if not issues else "fail", "artifact": str(artifact_path), "issues": issues}
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif issues:
        print("M142 route-local proof closeout gate verifier failed:", file=sys.stderr)
        for issue in issues:
            print(f" - {issue}", file=sys.stderr)
    else:
        print("M142 route-local proof closeout gate verifier passed")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
