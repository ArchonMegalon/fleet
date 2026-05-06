#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml

try:
    from scripts.materialize_next90_m141_ea_route_local_compare_packets import (
        DEFAULT_CAPTURE_PACK,
        DEFAULT_DESKTOP_VISUAL_GATE,
        DEFAULT_IMPORT_PARITY_CERTIFICATION,
        DEFAULT_IMPORT_RECEIPTS_DOC,
        DEFAULT_IMPORT_RECEIPTS_JSON,
        DEFAULT_MARKDOWN_OUTPUT,
        DEFAULT_OUTPUT,
        DEFAULT_PARITY_AUDIT,
        DEFAULT_READINESS,
        DEFAULT_RUNTIME_HANDOFF,
        DEFAULT_SCREENSHOT_REVIEW_GATE,
        DEFAULT_UI_RELEASE_GATE,
        DEFAULT_VETERAN_TASK_GATE,
        DEFAULT_WORKFLOW_PACK,
        _resolve_task_local_telemetry_path,
        build_markdown,
        build_payload,
    )
except ModuleNotFoundError:
    from materialize_next90_m141_ea_route_local_compare_packets import (  # type: ignore
        DEFAULT_CAPTURE_PACK,
        DEFAULT_DESKTOP_VISUAL_GATE,
        DEFAULT_IMPORT_PARITY_CERTIFICATION,
        DEFAULT_IMPORT_RECEIPTS_DOC,
        DEFAULT_IMPORT_RECEIPTS_JSON,
        DEFAULT_MARKDOWN_OUTPUT,
        DEFAULT_OUTPUT,
        DEFAULT_PARITY_AUDIT,
        DEFAULT_READINESS,
        DEFAULT_RUNTIME_HANDOFF,
        DEFAULT_SCREENSHOT_REVIEW_GATE,
        DEFAULT_UI_RELEASE_GATE,
        DEFAULT_VETERAN_TASK_GATE,
        DEFAULT_WORKFLOW_PACK,
        _resolve_task_local_telemetry_path,
        build_markdown,
        build_payload,
    )


def _yaml(path: Path) -> Dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify EA route-local compare packets for milestone 141.")
    parser.add_argument("--artifact", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--markdown-artifact", default=str(DEFAULT_MARKDOWN_OUTPUT))
    parser.add_argument("--task-local-telemetry")
    parser.add_argument("--runtime-handoff", default=str(DEFAULT_RUNTIME_HANDOFF))
    parser.add_argument("--readiness", default=str(DEFAULT_READINESS))
    parser.add_argument("--capture-pack", default=str(DEFAULT_CAPTURE_PACK))
    parser.add_argument("--workflow-pack", default=str(DEFAULT_WORKFLOW_PACK))
    parser.add_argument("--parity-audit", default=str(DEFAULT_PARITY_AUDIT))
    parser.add_argument("--screenshot-review-gate", default=str(DEFAULT_SCREENSHOT_REVIEW_GATE))
    parser.add_argument("--desktop-visual-gate", default=str(DEFAULT_DESKTOP_VISUAL_GATE))
    parser.add_argument("--veteran-task-gate", default=str(DEFAULT_VETERAN_TASK_GATE))
    parser.add_argument("--ui-release-gate", default=str(DEFAULT_UI_RELEASE_GATE))
    parser.add_argument("--import-receipts-doc", default=str(DEFAULT_IMPORT_RECEIPTS_DOC))
    parser.add_argument("--import-receipts-json", default=str(DEFAULT_IMPORT_RECEIPTS_JSON))
    parser.add_argument("--import-parity-certification", default=str(DEFAULT_IMPORT_PARITY_CERTIFICATION))
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
        normalized["source_inputs"] = source_inputs
    return normalized


def main() -> int:
    args = parse_args()
    artifact_path = Path(args.artifact).resolve()
    markdown_artifact_path = Path(args.markdown_artifact).resolve()
    runtime_handoff_path = Path(args.runtime_handoff).resolve()
    actual = _yaml(artifact_path)
    issues: List[str] = []
    if not actual:
        issues.append(f"artifact missing or invalid: {artifact_path}")
    else:
        expected = build_payload(
            task_local_telemetry_path=_resolve_task_local_telemetry_path(args.task_local_telemetry, runtime_handoff_path).resolve(),
            runtime_handoff_path=runtime_handoff_path,
            readiness_path=Path(args.readiness).resolve(),
            capture_pack_path=Path(args.capture_pack).resolve(),
            workflow_pack_path=Path(args.workflow_pack).resolve(),
            parity_audit_path=Path(args.parity_audit).resolve(),
            screenshot_review_gate_path=Path(args.screenshot_review_gate).resolve(),
            desktop_visual_gate_path=Path(args.desktop_visual_gate).resolve(),
            veteran_task_gate_path=Path(args.veteran_task_gate).resolve(),
            ui_release_gate_path=Path(args.ui_release_gate).resolve(),
            import_receipts_doc_path=Path(args.import_receipts_doc).resolve(),
            import_receipts_json_path=Path(args.import_receipts_json).resolve(),
            import_parity_certification_path=Path(args.import_parity_certification).resolve(),
            generated_at=str(actual.get("generated_at") or ""),
        )
        if _normalized(actual) != _normalized(expected):
            issues.append("yaml artifact drifted from recomputed route-local compare packet truth")
        actual_markdown = markdown_artifact_path.read_text(encoding="utf-8") if markdown_artifact_path.exists() else ""
        expected_markdown = build_markdown(expected)
        if actual_markdown != expected_markdown:
            issues.append("markdown artifact drifted from recomputed route-local compare packet summary")

    result = {
        "status": "pass" if not issues else "fail",
        "artifact": str(artifact_path),
        "markdown_artifact": str(markdown_artifact_path),
        "issues": issues,
    }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif issues:
        print("M141 EA route-local compare packet verifier failed:", file=sys.stderr)
        for issue in issues:
            print(f" - {issue}", file=sys.stderr)
    else:
        print("M141 EA route-local compare packet verifier passed")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
