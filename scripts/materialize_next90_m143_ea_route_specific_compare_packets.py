#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

import yaml


ROOT = Path("/docker/fleet")
DOCS_ROOT = ROOT / "docs" / "chummer5a-oracle"
PUBLISHED_ROOT = Path("/docker/chummercomplete/chummer-presentation/.codex-studio/published")
CORE_DOCS = Path("/docker/chummercomplete/chummer-core-engine/docs")

DEFAULT_OUTPUT = DOCS_ROOT / "m143_route_specific_compare_packets.yaml"
DEFAULT_MARKDOWN_OUTPUT = DOCS_ROOT / "m143_route_specific_compare_packets.md"
DEFAULT_RUNTIME_HANDOFF = Path("/var/lib/codex-fleet/chummer_design_supervisor/shard-14/ACTIVE_RUN_HANDOFF.generated.md")
DEFAULT_TASK_LOCAL_TELEMETRY_FALLBACK = Path(
    "/var/lib/codex-fleet/chummer_design_supervisor/shard-14/runs/20260505T224238Z-shard-14/TASK_LOCAL_TELEMETRY.generated.json"
)
DEFAULT_TASK_LOCAL_TELEMETRY = DEFAULT_TASK_LOCAL_TELEMETRY_FALLBACK
DEFAULT_READINESS = ROOT / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
DEFAULT_WORKFLOW_PACK = DOCS_ROOT / "veteran_workflow_packs.yaml"
DEFAULT_PARITY_AUDIT = PUBLISHED_ROOT / "CHUMMER5A_UI_ELEMENT_PARITY_AUDIT.generated.json"
DEFAULT_SCREENSHOT_REVIEW_GATE = PUBLISHED_ROOT / "CHUMMER5A_SCREENSHOT_REVIEW_GATE.generated.json"
DEFAULT_SECTION_HOST_RULESET_PARITY = PUBLISHED_ROOT / "SECTION_HOST_RULESET_PARITY.generated.json"
DEFAULT_GENERATED_DIALOG_PARITY = PUBLISHED_ROOT / "GENERATED_DIALOG_ELEMENT_PARITY.generated.json"
DEFAULT_M114_RULE_STUDIO = PUBLISHED_ROOT / "NEXT90_M114_UI_RULE_STUDIO.generated.json"
DEFAULT_CORE_M143_RECEIPTS_DOC = CORE_DOCS / "NEXT90_M143_EXPORT_PRINT_SUPPLEMENT_RULE_ENVIRONMENT_RECEIPTS.md"
DEFAULT_FLEET_M143_GATE = ROOT / ".codex-studio" / "published" / "NEXT90_M143_FLEET_ROUTE_LOCAL_OUTPUT_CLOSEOUT_GATES.generated.json"

PACKAGE_ID = "next90-m143-ea-compile-route-specific-compare-packs-and-artifact-proofs-for-print-export"
WORK_TASK_ID = "143.5"
MILESTONE_ID = 143
WAVE_ID = "W22P"
OWNED_SURFACES = ["compile_route_specific_compare_packs_and_artifact_proofs:ea"]

FAMILY_LABELS = {
    "sheet_export_print_viewer_and_exchange": "Sheet export, print viewer, and exchange",
    "sr6_supplements_designers_and_house_rules": "SR6 supplements, designers, and house rules",
}


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize EA route-specific compare packets for milestone 143.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--markdown-output", default=str(DEFAULT_MARKDOWN_OUTPUT))
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
    return parser.parse_args(argv)


def _load_yaml(path: Path) -> Dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {}


def _load_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_list(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []
    return [_normalize_text(value) for value in values if _normalize_text(value)]


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_generated_at(path: Path, payload: Dict[str, Any]) -> str:
    value = _normalize_text(payload.get("generated_at") or payload.get("generatedAt"))
    if value:
        return value
    return dt.datetime.fromtimestamp(path.stat().st_mtime, tz=dt.timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _resolve_task_local_telemetry_path(explicit_path: str | None, runtime_handoff_path: Path) -> Path:
    if explicit_path:
        return Path(explicit_path)
    for line in _load_text(runtime_handoff_path).splitlines():
        if line.startswith("- Run id: "):
            run_id = line.split(": ", 1)[1].strip()
            candidate = runtime_handoff_path.parent / "runs" / run_id / "TASK_LOCAL_TELEMETRY.generated.json"
            if candidate.exists():
                return candidate
    return DEFAULT_TASK_LOCAL_TELEMETRY_FALLBACK


def _task_local_snapshot(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "mode": _normalize_text(payload.get("mode")),
        "scope_label": _normalize_text(payload.get("scope_label")),
        "slice_summary": _normalize_text(payload.get("slice_summary")),
        "status_query_supported": bool(payload.get("status_query_supported")),
        "polling_disabled": bool(payload.get("polling_disabled")),
        "remaining_open_milestones": int(payload.get("remaining_open_milestones") or 0),
        "remaining_not_started_milestones": int(payload.get("remaining_not_started_milestones") or 0),
        "missing_flagship_coverage": _normalize_text(payload.get("missing_flagship_coverage")),
        "frontier_briefs": _normalize_list(payload.get("frontier_briefs")),
    }


def _frontier_id(payload: Dict[str, Any]) -> int:
    for brief in _normalize_list(payload.get("frontier_briefs")):
        head = brief.split(" ", 1)[0]
        if head.isdigit():
            return int(head)
    return 0


def _route_packs(workflow_pack: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    rows = [dict(row) for row in (workflow_pack.get("route_specific_compare_packs") or []) if isinstance(row, dict)]
    return {_normalize_text(row.get("family_id")): row for row in rows if _normalize_text(row.get("family_id"))}


def _parity_rows(parity_audit: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    rows = [dict(item) for item in (parity_audit.get("rows") or []) if isinstance(item, dict)]
    return {_normalize_text(row.get("id")): row for row in rows if _normalize_text(row.get("id"))}


def _contains_tokens(text: str, tokens: List[str]) -> List[str]:
    return [token for token in tokens if token not in text]


def _path_snapshot(path: Path, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    payload = payload or {}
    return {
        "path": str(path),
        "generated_at": _parse_generated_at(path, payload),
        "sha256": _sha256(path),
    }


def _coverage_status(readiness: Dict[str, Any], key: str) -> str:
    missing_keys = set(_normalize_list(readiness.get("missing_keys")))
    scoped_missing_keys = set(_normalize_list(readiness.get("scoped_missing_keys")))
    warning_keys = set(_normalize_list(readiness.get("warning_keys")))
    scoped_warning_keys = set(_normalize_list(readiness.get("scoped_warning_keys")))
    if key in missing_keys or key in scoped_missing_keys:
        return "missing"
    if key in warning_keys or key in scoped_warning_keys:
        return "warning"
    return "ready"


def build_payload(
    *,
    task_local_telemetry_path: Path,
    runtime_handoff_path: Path,
    readiness_path: Path,
    workflow_pack_path: Path,
    parity_audit_path: Path,
    screenshot_review_gate_path: Path,
    section_host_ruleset_parity_path: Path,
    generated_dialog_parity_path: Path,
    m114_rule_studio_path: Path,
    core_m143_receipts_doc_path: Path,
    fleet_m143_gate_path: Path,
    generated_at: str | None = None,
) -> Dict[str, Any]:
    task_local_telemetry = _load_json(task_local_telemetry_path)
    readiness = _load_json(readiness_path)
    workflow_pack = _load_yaml(workflow_pack_path)
    parity_audit = _load_json(parity_audit_path)
    screenshot_review_gate = _load_json(screenshot_review_gate_path)
    section_host_ruleset_parity = _load_json(section_host_ruleset_parity_path)
    generated_dialog_parity = _load_json(generated_dialog_parity_path)
    m114_rule_studio = _load_json(m114_rule_studio_path)
    fleet_m143_gate = _load_json(fleet_m143_gate_path)
    core_m143_receipts_text = _load_text(core_m143_receipts_doc_path)

    source_texts = {
        "screenshot_review_gate": json.dumps(screenshot_review_gate, sort_keys=True),
        "section_host_ruleset_parity": json.dumps(section_host_ruleset_parity, sort_keys=True),
        "generated_dialog_parity": json.dumps(generated_dialog_parity, sort_keys=True),
        "m114_rule_studio": json.dumps(m114_rule_studio, sort_keys=True),
        "core_m143_receipts_doc": core_m143_receipts_text,
    }

    route_packs = _route_packs(workflow_pack)
    parity_rows = _parity_rows(parity_audit)
    gate_family_summary = dict((fleet_m143_gate.get("runtime_monitors") or {}).get("proof_corpus", {}).get("family_receipt_summary") or {})
    readiness_missing_keys = _normalize_list(readiness.get("missing_keys"))

    family_packets: List[Dict[str, Any]] = []
    for family_id in (
        "sheet_export_print_viewer_and_exchange",
        "sr6_supplements_designers_and_house_rules",
    ):
        pack = dict(route_packs[family_id])
        parity_row_id = f"family:{family_id}"
        parity_row = dict(parity_rows[parity_row_id])
        route_receipts: List[Dict[str, Any]] = []
        artifact_proofs = dict(pack.get("artifact_proofs") or {})

        for route in pack.get("route_proofs") or []:
            route = dict(route)
            proof_receipts = [Path(item) for item in _normalize_list(route.get("proof_receipts"))]
            receipt_checks: List[Dict[str, Any]] = []
            missing_tokens: List[str] = []
            for receipt_path in proof_receipts:
                text = _load_text(receipt_path)
                tokens = _normalize_list(route.get("required_tokens"))
                route_missing = _contains_tokens(text, tokens)
                missing_tokens.extend(route_missing)
                receipt_checks.append(
                    {
                        "path": str(receipt_path),
                        "required_tokens": tokens,
                        "missing_tokens": route_missing,
                    }
                )

            route_receipts.append(
                {
                    "route_id": _normalize_text(route.get("route_id")),
                    "proof_receipts": [str(path) for path in proof_receipts],
                    "required_tokens": _normalize_list(route.get("required_tokens")),
                    "receipt_checks": receipt_checks,
                    "status": "pass" if not missing_tokens else "fail",
                }
            )

        screenshot_receipts = [Path(item) for item in _normalize_list(artifact_proofs.get("screenshot_receipts"))]
        output_receipts = [Path(item) for item in _normalize_list(artifact_proofs.get("output_receipts"))]
        screenshot_markers = _normalize_list(artifact_proofs.get("required_screenshot_markers"))
        output_tokens = _normalize_list(artifact_proofs.get("required_output_tokens"))

        screenshot_missing: List[str] = []
        for receipt in screenshot_receipts:
            screenshot_missing.extend(_contains_tokens(_load_text(receipt), screenshot_markers))
        output_missing: List[str] = []
        for receipt in output_receipts:
            output_missing.extend(_contains_tokens(_load_text(receipt), output_tokens))

        family_packets.append(
            {
                "family_id": family_id,
                "parity_audit_row_id": parity_row_id,
                "label": FAMILY_LABELS[family_id],
                "compare_artifacts": _normalize_list(pack.get("compare_artifacts")),
                "parity_verdict": {
                    "present_in_chummer5a": _normalize_text(parity_row.get("present_in_chummer5a")),
                    "present_in_chummer6": _normalize_text(parity_row.get("present_in_chummer6")),
                    "visual_parity": _normalize_text(parity_row.get("visual_parity")),
                    "behavioral_parity": _normalize_text(parity_row.get("behavioral_parity")),
                    "removable_if_not_in_chummer5a": _normalize_text(parity_row.get("removable_if_not_in_chummer5a")),
                    "reason": _normalize_text(parity_row.get("reason")),
                },
                "route_specific_compare_pack": {
                    "summary": _normalize_text(pack.get("summary")),
                    "route_receipts": route_receipts,
                },
                "artifact_proof_pack": {
                    "screenshot_receipts": [str(path) for path in screenshot_receipts],
                    "required_screenshot_markers": screenshot_markers,
                    "missing_screenshot_markers": screenshot_missing,
                    "output_receipts": [str(path) for path in output_receipts],
                    "required_output_tokens": output_tokens,
                    "missing_output_tokens": output_missing,
                    "status": "pass" if not screenshot_missing and not output_missing else "fail",
                },
                "fleet_closeout_gate_receipts": dict(gate_family_summary.get(parity_row_id) or {}),
                "evidence_paths": _normalize_list(parity_row.get("evidence")),
            }
        )

    return {
        "contract_name": "executive_assistant.m143_route_specific_compare_packets",
        "schema_version": 1,
        "generated_at": generated_at or _utc_now(),
        "milestone": {
            "id": MILESTONE_ID,
            "wave": WAVE_ID,
            "package_id": PACKAGE_ID,
            "work_task_id": WORK_TASK_ID,
            "frontier_id": _frontier_id(task_local_telemetry),
            "owned_surfaces": OWNED_SURFACES,
        },
        "sync_context": {
            "task_local_telemetry_path": str(task_local_telemetry_path),
            "task_local_telemetry_snapshot": _task_local_snapshot(task_local_telemetry),
            "runtime_handoff_path": str(runtime_handoff_path),
            "readiness_path": str(readiness_path),
            "readiness_generated_at": _parse_generated_at(readiness_path, readiness),
            "workflow_pack_path": str(workflow_pack_path),
            "workflow_pack_generated_at": _parse_generated_at(workflow_pack_path, workflow_pack),
            "parity_audit_path": str(parity_audit_path),
            "parity_audit_generated_at": _parse_generated_at(parity_audit_path, parity_audit),
            "screenshot_review_gate_path": str(screenshot_review_gate_path),
            "screenshot_review_gate_generated_at": _parse_generated_at(screenshot_review_gate_path, screenshot_review_gate),
            "section_host_ruleset_parity_path": str(section_host_ruleset_parity_path),
            "section_host_ruleset_parity_generated_at": _parse_generated_at(section_host_ruleset_parity_path, section_host_ruleset_parity),
            "generated_dialog_parity_path": str(generated_dialog_parity_path),
            "generated_dialog_parity_generated_at": _parse_generated_at(generated_dialog_parity_path, generated_dialog_parity),
            "m114_rule_studio_path": str(m114_rule_studio_path),
            "m114_rule_studio_generated_at": _parse_generated_at(m114_rule_studio_path, m114_rule_studio),
            "core_m143_receipts_doc_path": str(core_m143_receipts_doc_path),
            "core_m143_receipts_doc_generated_at": _parse_generated_at(core_m143_receipts_doc_path, {}),
            "fleet_m143_gate_path": str(fleet_m143_gate_path),
            "fleet_m143_gate_generated_at": _parse_generated_at(fleet_m143_gate_path, fleet_m143_gate),
        },
        "worker_run_guard": {
            "implementation_only": True,
            "polling_disabled": bool(task_local_telemetry.get("polling_disabled")),
            "allowed_evidence_sources": [
                "task-local telemetry file",
                "shard runtime handoff",
                "veteran workflow route-specific compare packs",
                "published parity audit and screenshot review receipts",
                "published UI route proof receipts",
                "published core M143 receipts",
                "published Fleet M143 closeout gate",
            ],
            "blocked_helper_evidence": [
                "supervisor status helpers",
                "supervisor eta helpers",
                "operator-only handoff commands",
            ],
        },
        "family_route_specific_compare_packets": family_packets,
        "whole_product_frontier_coverage": {
            "readiness_status": _normalize_text(readiness.get("status")),
            "desktop_client_status": _coverage_status(readiness, "desktop_client"),
            "missing_keys": readiness_missing_keys,
            "summary": _normalize_text(
                dict(readiness.get("flagship_readiness_audit") or {}).get("reason")
                or dict(readiness.get("completion_audit") or {}).get("reason")
            ),
        },
        "source_inputs": {
            "task_local_telemetry": _path_snapshot(task_local_telemetry_path, task_local_telemetry),
            "readiness": _path_snapshot(readiness_path, readiness),
            "workflow_pack": _path_snapshot(workflow_pack_path, workflow_pack),
            "parity_audit": _path_snapshot(parity_audit_path, parity_audit),
            "screenshot_review_gate": _path_snapshot(screenshot_review_gate_path, screenshot_review_gate),
            "section_host_ruleset_parity": _path_snapshot(section_host_ruleset_parity_path, section_host_ruleset_parity),
            "generated_dialog_parity": _path_snapshot(generated_dialog_parity_path, generated_dialog_parity),
            "m114_rule_studio": _path_snapshot(m114_rule_studio_path, m114_rule_studio),
            "core_m143_receipts_doc": _path_snapshot(core_m143_receipts_doc_path),
            "fleet_m143_gate": _path_snapshot(fleet_m143_gate_path, fleet_m143_gate),
        },
    }


def build_markdown(payload: Dict[str, Any]) -> str:
    lines = [
        "# M143 route-specific compare packets",
        "",
        "This EA-owned packet compiles the direct route receipts and artifact proof bundle for print/export/exchange and SR6 supplement or house-rule workflows without widening the proof plane.",
        "",
        f"- milestone: `{payload['milestone']['id']}`",
        f"- package: `{payload['milestone']['package_id']}`",
        f"- work task: `{payload['milestone']['work_task_id']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- live desktop readiness: `{payload['whole_product_frontier_coverage']['desktop_client_status']}`",
        "",
        "## Family route-specific compare packets",
        "",
    ]
    for family in payload["family_route_specific_compare_packets"]:
        lines.append(f"### {family['label']}")
        lines.append("")
        lines.append(f"- parity row: `{family['parity_audit_row_id']}`")
        lines.append(f"- compare artifacts: `{', '.join(family['compare_artifacts'])}`")
        lines.append(
            f"- parity verdict: visual `{family['parity_verdict']['visual_parity']}`, behavioral `{family['parity_verdict']['behavioral_parity']}`"
        )
        lines.append(f"- reason: {family['parity_verdict']['reason']}")
        lines.append(f"- Fleet closeout receipts: `{', '.join(family['fleet_closeout_gate_receipts'].get('satisfied_route_receipts') or ['none'])}`")
        lines.append("")
        for route in family["route_specific_compare_pack"]["route_receipts"]:
            lines.append(f"#### {route['route_id']}")
            lines.append("")
            lines.append(f"- proof receipts: `{', '.join(route['proof_receipts'])}`")
            lines.append(f"- required tokens: `{', '.join(route['required_tokens'])}`")
            lines.append(f"- status: `{route['status']}`")
            lines.append("")
        artifact_pack = family["artifact_proof_pack"]
        lines.append("#### Artifact proof pack")
        lines.append("")
        lines.append(f"- screenshot receipts: `{', '.join(artifact_pack['screenshot_receipts']) or 'none'}`")
        lines.append(f"- screenshot markers: `{', '.join(artifact_pack['required_screenshot_markers']) or 'none'}`")
        lines.append(f"- output receipts: `{', '.join(artifact_pack['output_receipts']) or 'none'}`")
        lines.append(f"- output tokens: `{', '.join(artifact_pack['required_output_tokens']) or 'none'}`")
        lines.append(f"- status: `{artifact_pack['status']}`")
        lines.append("")
    coverage = payload["whole_product_frontier_coverage"]
    lines.extend(
        [
            "## Live readiness note",
            "",
            f"- desktop_client status: `{coverage['desktop_client_status']}`",
            f"- summary: {coverage['summary']}",
            f"- missing keys: `{', '.join(coverage['missing_keys']) or 'none'}`",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    runtime_handoff_path = Path(args.runtime_handoff).resolve()
    task_local_telemetry_path = _resolve_task_local_telemetry_path(args.task_local_telemetry, runtime_handoff_path).resolve()
    payload = build_payload(
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
    )
    output_path = Path(args.output).resolve()
    markdown_output_path = Path(args.markdown_output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    markdown_output_path.write_text(build_markdown(payload), encoding="utf-8")
    print(str(output_path))
    print(str(markdown_output_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
