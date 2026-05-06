#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

import yaml

try:
    from scripts.materialize_next90_m142_ea_family_local_proof_packs import (
        DEFAULT_CORE_DENSE_RECEIPTS,
        DEFAULT_DESKTOP_VISUAL_GATE,
        DEFAULT_DIALOG_PARITY,
        DEFAULT_GM_RUNBOARD_ROUTE,
        DEFAULT_OUTPUT,
        DEFAULT_PARITY_AUDIT,
        DEFAULT_READINESS,
        DEFAULT_RUNTIME_HANDOFF,
        DEFAULT_SCREENSHOT_REVIEW_GATE,
        DEFAULT_SECTION_HOST_PARITY,
        DEFAULT_TASK_LOCAL_TELEMETRY,
        DEFAULT_UI_LOCAL_RELEASE_PROOF,
        DEFAULT_UI_RELEASE_GATE,
        DEFAULT_VETERAN_TASK_GATE,
        DEFAULT_WORKFLOW_PACK,
        DEFAULT_CLASSIC_DENSE_GATE,
        build_payload,
    )
except ModuleNotFoundError:
    from materialize_next90_m142_ea_family_local_proof_packs import (  # type: ignore
        DEFAULT_CORE_DENSE_RECEIPTS,
        DEFAULT_DESKTOP_VISUAL_GATE,
        DEFAULT_DIALOG_PARITY,
        DEFAULT_GM_RUNBOARD_ROUTE,
        DEFAULT_OUTPUT,
        DEFAULT_PARITY_AUDIT,
        DEFAULT_READINESS,
        DEFAULT_RUNTIME_HANDOFF,
        DEFAULT_SCREENSHOT_REVIEW_GATE,
        DEFAULT_SECTION_HOST_PARITY,
        DEFAULT_TASK_LOCAL_TELEMETRY,
        DEFAULT_UI_LOCAL_RELEASE_PROOF,
        DEFAULT_UI_RELEASE_GATE,
        DEFAULT_VETERAN_TASK_GATE,
        DEFAULT_WORKFLOW_PACK,
        DEFAULT_CLASSIC_DENSE_GATE,
        build_payload,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify the EA M142 family-local proof packet.")
    parser.add_argument("--artifact", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--task-local-telemetry", default=str(DEFAULT_TASK_LOCAL_TELEMETRY))
    parser.add_argument("--runtime-handoff", default=str(DEFAULT_RUNTIME_HANDOFF))
    parser.add_argument("--readiness", default=str(DEFAULT_READINESS))
    parser.add_argument("--workflow-pack", default=str(DEFAULT_WORKFLOW_PACK))
    parser.add_argument("--parity-audit", default=str(DEFAULT_PARITY_AUDIT))
    parser.add_argument("--screenshot-review-gate", default=str(DEFAULT_SCREENSHOT_REVIEW_GATE))
    parser.add_argument("--desktop-visual-gate", default=str(DEFAULT_DESKTOP_VISUAL_GATE))
    parser.add_argument("--ui-release-gate", default=str(DEFAULT_UI_RELEASE_GATE))
    parser.add_argument("--ui-local-release-proof", default=str(DEFAULT_UI_LOCAL_RELEASE_PROOF))
    parser.add_argument("--section-host-parity", default=str(DEFAULT_SECTION_HOST_PARITY))
    parser.add_argument("--dialog-parity", default=str(DEFAULT_DIALOG_PARITY))
    parser.add_argument("--gm-runboard-route", default=str(DEFAULT_GM_RUNBOARD_ROUTE))
    parser.add_argument("--veteran-task-gate", default=str(DEFAULT_VETERAN_TASK_GATE))
    parser.add_argument("--classic-dense-gate", default=str(DEFAULT_CLASSIC_DENSE_GATE))
    parser.add_argument("--core-dense-receipts", default=str(DEFAULT_CORE_DENSE_RECEIPTS))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def _read_yaml(path: Path) -> Dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _normalize(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(payload)
    normalized.pop("generated_at", None)
    sync_context = normalized.get("sync_context")
    if isinstance(sync_context, dict):
        sync_context = dict(sync_context)
        sync_context.pop("readiness_generated_at", None)
        normalized["sync_context"] = sync_context
    source_inputs = normalized.get("source_inputs")
    if isinstance(source_inputs, dict):
        source_inputs = dict(source_inputs)
        readiness = source_inputs.get("readiness")
        if isinstance(readiness, dict):
            readiness = dict(readiness)
            readiness.pop("generated_at", None)
            readiness.pop("sha256", None)
            source_inputs["readiness"] = readiness
        runtime_handoff = source_inputs.get("runtime_handoff")
        if isinstance(runtime_handoff, dict):
            runtime_handoff = dict(runtime_handoff)
            runtime_handoff.pop("sha256", None)
            source_inputs["runtime_handoff"] = runtime_handoff
        workflow_pack = source_inputs.get("workflow_pack")
        if isinstance(workflow_pack, dict):
            workflow_pack = dict(workflow_pack)
            workflow_pack.pop("sha256", None)
            source_inputs["workflow_pack"] = workflow_pack
        normalized["source_inputs"] = source_inputs
    return normalized


def main() -> int:
    args = parse_args()
    artifact = Path(args.artifact).resolve()
    issues = []
    actual = _read_yaml(artifact)
    if not actual:
        issues.append(f"artifact missing or invalid: {artifact}")
    else:
        expected = build_payload(
            task_local_telemetry_path=Path(args.task_local_telemetry).resolve(),
            runtime_handoff_path=Path(args.runtime_handoff).resolve(),
            readiness_path=Path(args.readiness).resolve(),
            workflow_pack_path=Path(args.workflow_pack).resolve(),
            parity_audit_path=Path(args.parity_audit).resolve(),
            screenshot_review_gate_path=Path(args.screenshot_review_gate).resolve(),
            desktop_visual_gate_path=Path(args.desktop_visual_gate).resolve(),
            ui_release_gate_path=Path(args.ui_release_gate).resolve(),
            ui_local_release_proof_path=Path(args.ui_local_release_proof).resolve(),
            section_host_parity_path=Path(args.section_host_parity).resolve(),
            dialog_parity_path=Path(args.dialog_parity).resolve(),
            gm_runboard_route_path=Path(args.gm_runboard_route).resolve(),
            veteran_task_gate_path=Path(args.veteran_task_gate).resolve(),
            classic_dense_gate_path=Path(args.classic_dense_gate).resolve(),
            core_dense_receipts_path=Path(args.core_dense_receipts).resolve(),
            generated_at=actual.get("generated_at"),
        )
        if _normalize(actual) != _normalize(expected):
            for key in ("sync_context", "family_local_proof_packets", "whole_product_frontier_coverage", "packet_summary", "source_inputs"):
                if _normalize({key: actual.get(key)}) != _normalize({key: expected.get(key)}):
                    issues.append(f"{key} drifted from recomputed M142 packet truth")
            if not issues:
                issues.append("artifact drifted outside the allowed generated_at field")
    result = {"status": "pass" if not issues else "fail", "artifact": str(artifact), "issues": issues}
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif issues:
        print("M142 family-local proof packet verifier failed:", file=sys.stderr)
        for issue in issues:
            print(f" - {issue}", file=sys.stderr)
    else:
        print("M142 family-local proof packet verifier passed")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
