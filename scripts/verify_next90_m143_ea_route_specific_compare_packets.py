#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml

try:
    from scripts.materialize_next90_m143_ea_route_specific_compare_packets import (
        DEFAULT_CORE_M143_RECEIPTS_DOC,
        DEFAULT_FLEET_M143_GATE,
        DEFAULT_GENERATED_DIALOG_PARITY,
        DEFAULT_M114_RULE_STUDIO,
        DEFAULT_MARKDOWN_OUTPUT,
        DEFAULT_OUTPUT,
        DEFAULT_PARITY_AUDIT,
        DEFAULT_READINESS,
        DEFAULT_RUNTIME_HANDOFF,
        DEFAULT_SCREENSHOT_REVIEW_GATE,
        DEFAULT_SECTION_HOST_RULESET_PARITY,
        DEFAULT_WORKFLOW_PACK,
        _resolve_task_local_telemetry_path,
        build_markdown,
        build_payload,
    )
except ModuleNotFoundError:
    from materialize_next90_m143_ea_route_specific_compare_packets import (  # type: ignore
        DEFAULT_CORE_M143_RECEIPTS_DOC,
        DEFAULT_FLEET_M143_GATE,
        DEFAULT_GENERATED_DIALOG_PARITY,
        DEFAULT_M114_RULE_STUDIO,
        DEFAULT_MARKDOWN_OUTPUT,
        DEFAULT_OUTPUT,
        DEFAULT_PARITY_AUDIT,
        DEFAULT_READINESS,
        DEFAULT_RUNTIME_HANDOFF,
        DEFAULT_SCREENSHOT_REVIEW_GATE,
        DEFAULT_SECTION_HOST_RULESET_PARITY,
        DEFAULT_WORKFLOW_PACK,
        _resolve_task_local_telemetry_path,
        build_markdown,
        build_payload,
    )


def _yaml(path: Path) -> Dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify EA route-specific compare packets for milestone 143.")
    parser.add_argument("--artifact", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--markdown-artifact", default=str(DEFAULT_MARKDOWN_OUTPUT))
    parser.add_argument("--task-local-telemetry")
    parser.add_argument("--runtime-handoff", default=str(DEFAULT_RUNTIME_HANDOFF))
    parser.add_argument("--readiness", default=str(DEFAULT_READINESS))
    parser.add_argument("--workflow-pack", default=str(DEFAULT_WORKFLOW_PACK))
    parser.add_argument("--parity-audit", default=str(DEFAULT_PARITY_AUDIT))
    parser.add_argument("--screenshot-review-gate", default=str(DEFAULT_SCREENSHOT_REVIEW_GATE))
    parser.add_argument("--section-host-ruleset-parity", default=str(DEFAULT_SECTION_HOST_RULESET_PARITY))
    parser.add_argument("--generated-dialog-parity", default=str(DEFAULT_GENERATED_DIALOG_PARITY))
    parser.add_argument("--m114-rule-studio", default=str(DEFAULT_M114_RULE_STUDIO))
    parser.add_argument("--core-m143-receipts-doc", default=str(DEFAULT_CORE_M143_RECEIPTS_DOC))
    parser.add_argument("--fleet-m143-gate", default=str(DEFAULT_FLEET_M143_GATE))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def _normalized(payload: Dict[str, Any]) -> Dict[str, Any]:
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
        workflow_pack = source_inputs.get("workflow_pack")
        if isinstance(workflow_pack, dict):
            workflow_pack = dict(workflow_pack)
            workflow_pack.pop("sha256", None)
            source_inputs["workflow_pack"] = workflow_pack
        normalized["source_inputs"] = source_inputs
    return normalized


def main() -> int:
    args = parse_args()
    artifact_path = Path(args.artifact).resolve()
    markdown_artifact_path = Path(args.markdown_artifact).resolve()
    runtime_handoff_path = Path(args.runtime_handoff).resolve()
    task_local_telemetry_path = _resolve_task_local_telemetry_path(args.task_local_telemetry, runtime_handoff_path).resolve()
    actual = _yaml(artifact_path)
    issues: List[str] = []
    if not actual:
        issues.append(f"artifact missing or invalid: {artifact_path}")
    else:
        expected = build_payload(
            task_local_telemetry_path=task_local_telemetry_path,
            runtime_handoff_path=runtime_handoff_path,
            readiness_path=Path(args.readiness).resolve(),
            workflow_pack_path=Path(args.workflow_pack).resolve(),
            parity_audit_path=Path(args.parity_audit).resolve(),
            screenshot_review_gate_path=Path(args.screenshot_review_gate).resolve(),
            section_host_ruleset_parity_path=Path(args.section_host_ruleset_parity).resolve(),
            generated_dialog_parity_path=Path(args.generated_dialog_parity).resolve(),
            m114_rule_studio_path=Path(args.m114_rule_studio).resolve(),
            core_m143_receipts_doc_path=Path(args.core_m143_receipts_doc).resolve(),
            fleet_m143_gate_path=Path(args.fleet_m143_gate).resolve(),
            generated_at=str(actual.get("generated_at") or ""),
        )
        if _normalized(actual) != _normalized(expected):
            issues.append("yaml artifact drifted from recomputed route-specific compare packet truth")
        actual_markdown = markdown_artifact_path.read_text(encoding="utf-8") if markdown_artifact_path.exists() else ""
        expected_markdown = build_markdown(expected)
        if actual_markdown != expected_markdown:
            issues.append("markdown artifact drifted from recomputed route-specific compare packet summary")

    result = {
        "status": "pass" if not issues else "fail",
        "artifact": str(artifact_path),
        "markdown_artifact": str(markdown_artifact_path),
        "issues": issues,
    }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif issues:
        print("M143 EA route-specific compare packet verifier failed:", file=sys.stderr)
        for issue in issues:
            print(f" - {issue}", file=sys.stderr)
    else:
        print("M143 EA route-specific compare packet verifier passed")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
