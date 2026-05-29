#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List

import yaml


ROOT = Path("/docker/fleet")
DOCS_ROOT = ROOT / "docs" / "chummer5a-oracle"
PUBLISHED_ROOT = Path("/docker/chummercomplete/chummer-presentation/.codex-studio/published")
CORE_ROOT = Path("/docker/chummercomplete/chummer6-core/.codex-studio/published")
CORE_DOCS = Path("/docker/chummercomplete/chummer-core-engine/docs")

DEFAULT_OUTPUT = DOCS_ROOT / "m141_import_route_compare_packets.yaml"
DEFAULT_MARKDOWN_OUTPUT = DOCS_ROOT / "m141_import_route_compare_packets.md"
DEFAULT_SUPERVISOR_ROOT = Path("/var/lib/codex-fleet/chummer_design_supervisor")
DEFAULT_RUNTIME_HANDOFF = None
DEFAULT_TASK_LOCAL_TELEMETRY = None
DEFAULT_READINESS = ROOT / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
DEFAULT_CAPTURE_PACK = DOCS_ROOT / "parity_lab_capture_pack.yaml"
DEFAULT_WORKFLOW_PACK = DOCS_ROOT / "veteran_workflow_packs.yaml"
DEFAULT_PARITY_AUDIT = PUBLISHED_ROOT / "CHUMMER5A_UI_ELEMENT_PARITY_AUDIT.generated.json"
DEFAULT_SCREENSHOT_REVIEW_GATE = PUBLISHED_ROOT / "CHUMMER5A_SCREENSHOT_REVIEW_GATE.generated.json"
DEFAULT_DESKTOP_VISUAL_GATE = PUBLISHED_ROOT / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
DEFAULT_VETERAN_TASK_GATE = PUBLISHED_ROOT / "VETERAN_TASK_TIME_EVIDENCE_GATE.generated.json"
DEFAULT_UI_RELEASE_GATE = PUBLISHED_ROOT / "UI_FLAGSHIP_RELEASE_GATE.generated.json"
DEFAULT_IMPORT_RECEIPTS_DOC = CORE_DOCS / "NEXT90_M141_IMPORT_ROUTE_RECEIPTS.md"
DEFAULT_IMPORT_RECEIPTS_JSON = CORE_ROOT / "NEXT90_M141_IMPORT_ROUTE_RECEIPTS.generated.json"
DEFAULT_IMPORT_PARITY_CERTIFICATION = CORE_ROOT / "IMPORT_PARITY_CERTIFICATION.generated.json"
TASK_LOCAL_TELEMETRY_ENV = "CHUMMER_DESIGN_SUPERVISOR_TASK_LOCAL_TELEMETRY_PATH"

PACKAGE_ID = "next90-m141-ea-compile-route-local-screenshot-packs-and-compare-packets-for-translator-x"
WORK_TASK_ID = "141.4"
MILESTONE_ID = 141
WAVE_ID = "W22P"
OWNED_SURFACES = ["compile_route_local_screenshot_packs_and_compare_packets:ea"]

ROUTE_SPECS: Dict[str, Dict[str, Any]] = {
    "source:translator_route": {
        "compact_id": "translator_route",
        "label": "Translator route",
        "legacy_source_anchor_id": "translator_route",
        "route_local_receipt_id": "translator_xml_custom_data",
        "workflow_family_id": "improvements-explain-result-parity",
        "legacy_behavior_lineage": "Validation lineage",
        "compare_artifacts": ["menu:translator", "source:translator_route"],
        "screenshots": ["38-translator-dialog-light.png"],
        "review_jobs": ["translator"],
        "route_ids": [
            "translator",
            "xml_editor",
            "source:translator_route",
            "source:xml_amendment_editor_route",
            "family:custom_data_xml_and_translator_bridge",
        ],
        "runtime_receipt_tokens": [
            "translator_xml_custom_data",
            "ExecuteCommandAsync_translator_opens_dialog_with_master_index_lane_posture",
        ],
        "core_receipt_tokens": ["translatorDeterministicReceipt"],
    },
    "source:xml_amendment_editor_route": {
        "compact_id": "xml_amendment_editor_route",
        "label": "XML amendment editor route",
        "legacy_source_anchor_id": "xml_amendment_editor_route",
        "route_local_receipt_id": "translator_xml_custom_data",
        "workflow_family_id": "improvements-explain-result-parity",
        "legacy_behavior_lineage": "Validation lineage",
        "compare_artifacts": ["menu:xml_editor", "source:xml_amendment_editor_route"],
        "screenshots": ["39-xml-editor-dialog-light.png"],
        "review_jobs": ["xml_editor"],
        "route_ids": [
            "translator",
            "xml_editor",
            "source:translator_route",
            "source:xml_amendment_editor_route",
            "family:custom_data_xml_and_translator_bridge",
        ],
        "runtime_receipt_tokens": [
            "translator_xml_custom_data",
            "ExecuteCommandAsync_xml_editor_opens_dialog_with_xml_bridge_posture",
        ],
        "core_receipt_tokens": ["customDataXmlBridgeDeterministicReceipt"],
    },
    "source:hero_lab_importer_route": {
        "compact_id": "hero_lab_importer_route",
        "label": "Hero Lab importer route",
        "legacy_source_anchor_id": "hero_lab_importer_route",
        "route_local_receipt_id": "hero_lab_import_oracle",
        "workflow_family_id": "create-open-import-save-save-as-print-export",
        "legacy_behavior_lineage": "File menu lineage",
        "compare_artifacts": ["menu:hero_lab_importer", "source:hero_lab_importer_route"],
        "screenshots": ["40-hero-lab-importer-dialog-light.png"],
        "review_jobs": ["hero_lab_importer"],
        "route_ids": [
            "hero_lab_importer",
            "source:hero_lab_importer_route",
            "family:legacy_and_adjacent_import_oracles",
        ],
        "runtime_receipt_tokens": [
            "hero_lab_import_oracle",
            "ExecuteCommandAsync_hero_lab_importer_opens_dialog_with_import_oracle_lane_posture",
        ],
        "core_receipt_tokens": ["importOracleDeterministicReceipt"],
    },
}

FAMILY_SPECS: Dict[str, Dict[str, Any]] = {
    "family:custom_data_xml_and_translator_bridge": {
        "compact_id": "custom_data_xml_and_translator_bridge",
        "label": "Custom data/XML and translator bridge family",
        "route_local_receipt_id": "translator_xml_custom_data",
        "workflow_family_id": "improvements-explain-result-parity",
        "legacy_behavior_lineage": "Validation lineage",
        "compare_artifacts": ["menu:translator", "menu:xml_editor"],
        "screenshots": ["38-translator-dialog-light.png", "39-xml-editor-dialog-light.png"],
        "review_jobs": ["translator", "xml_editor"],
        "route_ids": [
            "translator",
            "xml_editor",
            "source:translator_route",
            "source:xml_amendment_editor_route",
            "family:custom_data_xml_and_translator_bridge",
        ],
        "runtime_receipt_tokens": [
            "translator_xml_custom_data",
            "ExecuteCommandAsync_translator_opens_dialog_with_master_index_lane_posture",
            "ExecuteCommandAsync_xml_editor_opens_dialog_with_xml_bridge_posture",
        ],
        "core_receipt_tokens": [
            "customDataXmlBridgeDeterministicReceipt",
            "translatorDeterministicReceipt",
            "family:custom_data_xml_and_translator_bridge",
        ],
    },
    "family:legacy_and_adjacent_import_oracles": {
        "compact_id": "legacy_and_adjacent_import_oracles",
        "label": "Legacy and adjacent import-oracle family",
        "route_local_receipt_id": "hero_lab_import_oracle",
        "workflow_family_id": "create-open-import-save-save-as-print-export",
        "legacy_behavior_lineage": "File menu lineage",
        "compare_artifacts": ["menu:hero_lab_importer", "workflow:import_oracle"],
        "screenshots": ["40-hero-lab-importer-dialog-light.png"],
        "review_jobs": ["hero_lab_importer"],
        "route_ids": [
            "hero_lab_importer",
            "source:hero_lab_importer_route",
            "family:legacy_and_adjacent_import_oracles",
        ],
        "runtime_receipt_tokens": [
            "hero_lab_import_oracle",
            "ExecuteCommandAsync_hero_lab_importer_opens_dialog_with_import_oracle_lane_posture",
        ],
        "core_receipt_tokens": [
            "importOracleDeterministicReceipt",
            "family:legacy_and_adjacent_import_oracles",
        ],
    },
}


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize EA route-local compare packets for milestone 141.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--markdown-output", default=str(DEFAULT_MARKDOWN_OUTPUT))
    parser.add_argument("--task-local-telemetry")
    parser.add_argument("--runtime-handoff")
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


def _resolve_task_local_telemetry_path(explicit_path: str | None, runtime_handoff_path: Path) -> Path:
    if explicit_path:
        return Path(explicit_path)
    env_path = _normalize_text(os.environ.get(TASK_LOCAL_TELEMETRY_ENV))
    if env_path:
        candidate = Path(env_path)
        if candidate.exists():
            return candidate
    handoff_text = _load_text(runtime_handoff_path)
    for line in handoff_text.splitlines():
        if line.startswith("- Run id: "):
            run_id = line.split(": ", 1)[1].strip()
            if run_id:
                candidate = runtime_handoff_path.parent / "runs" / run_id / "TASK_LOCAL_TELEMETRY.generated.json"
                if candidate.exists():
                    return candidate
    runs_root = runtime_handoff_path.parent / "runs"
    candidates = sorted(runs_root.glob("*/TASK_LOCAL_TELEMETRY.generated.json"))
    if candidates:
        return candidates[-1]
    raise FileNotFoundError(f"no task-local telemetry found for {runtime_handoff_path}")


def _resolve_runtime_handoff_path(explicit_path: str | None) -> Path:
    if explicit_path:
        return Path(explicit_path)
    env_path = _normalize_text(os.environ.get(TASK_LOCAL_TELEMETRY_ENV))
    if env_path:
        candidate = Path(env_path)
        if candidate.exists() and len(candidate.parents) >= 3:
            handoff = candidate.parents[2] / "ACTIVE_RUN_HANDOFF.generated.md"
            if handoff.exists():
                return handoff
    candidates = sorted(
        DEFAULT_SUPERVISOR_ROOT.glob("shard-*/ACTIVE_RUN_HANDOFF.generated.md"),
        key=lambda path: path.stat().st_mtime,
    )
    if candidates:
        return candidates[-1]
    raise FileNotFoundError(f"no shard runtime handoff found under {DEFAULT_SUPERVISOR_ROOT}")


def _parse_generated_at(path: Path, payload: Dict[str, Any]) -> str:
    value = _normalize_text(payload.get("generated_at") or payload.get("generatedAt"))
    if value:
        return value
    return dt.datetime.fromtimestamp(path.stat().st_mtime, tz=dt.timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _path_snapshot(path: Path, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    payload = payload or {}
    return {
        "path": str(path),
        "generated_at": _parse_generated_at(path, payload),
        "sha256": _sha256(path),
    }


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


def _parity_rows(parity_audit: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    rows = [dict(item) for item in (parity_audit.get("rows") or []) if isinstance(item, dict)]
    return {_normalize_text(row.get("id")): row for row in rows if _normalize_text(row.get("id"))}


def _legacy_source_anchors(capture_pack: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    groups = dict((capture_pack.get("oracle_surface_extract") or {}).get("source_line_proofs") or {})
    rows: Dict[str, Dict[str, Any]] = {}
    for group_rows in groups.values():
        if not isinstance(group_rows, list):
            continue
        for row in group_rows:
            if not isinstance(row, dict):
                continue
            row_id = _normalize_text(row.get("id"))
            if row_id:
                rows[row_id] = row
    return rows


def _route_local_receipts(screenshot_review_gate: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    receipts = dict(((screenshot_review_gate.get("evidence") or {}).get("routeLocalReceipts")) or {})
    receipts.update(dict(screenshot_review_gate.get("routeLocalReceipts") or {}))
    return {key: value for key, value in receipts.items() if isinstance(value, dict)}


def _workflow_screenshot_coverage(ui_release_gate: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    rows = list((((ui_release_gate.get("workflowEquivalenceProof") or {}).get("workflowScreenshotCoverage")) or []))
    return {
        _normalize_text(row.get("workflowFamilyId")): row
        for row in rows
        if isinstance(row, dict) and _normalize_text(row.get("workflowFamilyId"))
    }


def _fallback_route_local_receipt(spec: Dict[str, Any], ui_release_gate: Dict[str, Any]) -> Dict[str, Any]:
    workflow = dict(_workflow_screenshot_coverage(ui_release_gate).get(spec["workflow_family_id"]) or {})
    return {
        "workflowFamilyId": _normalize_text(workflow.get("workflowFamilyId")) or spec["workflow_family_id"],
        "legacyBehaviorLineage": _normalize_text(workflow.get("legacyBehaviorLineage")) or spec["legacy_behavior_lineage"],
        "routeIds": list(spec["route_ids"]),
        "screenshots": list(spec["screenshots"]),
    }


def _proofs(gate: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    proofs = gate.get("proofs") or {}
    return {key: value for key, value in proofs.items() if isinstance(value, dict)}


def _review_jobs(screenshot_review_gate: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    jobs = screenshot_review_gate.get("reviewJobs") or {}
    return {key: value for key, value in jobs.items() if isinstance(value, dict)}


def _workflow_pack_family(workflow_pack: Dict[str, Any], family_id: str) -> Dict[str, Any]:
    for row in workflow_pack.get("families") or []:
        if isinstance(row, dict) and _normalize_text(row.get("id")) == family_id:
            return row
    raise KeyError(f"workflow family missing: {family_id}")


def _contains_tokens(text: str, tokens: List[str]) -> List[str]:
    return [token for token in tokens if token not in text]


def _receipt_checks(paths: List[Path], tokens: List[str]) -> List[Dict[str, Any]]:
    checks: List[Dict[str, Any]] = []
    for path in paths:
        text = _load_text(path)
        checks.append(
            {
                "path": str(path),
                "required_tokens": list(tokens),
                "missing_tokens": _contains_tokens(text, tokens),
            }
        )
    return checks


def _combined_missing_tokens(paths: List[Path], tokens: List[str]) -> List[str]:
    combined_text = "\n".join(_load_text(path) for path in paths)
    return _contains_tokens(combined_text, tokens)


def _artifact_proof_pack(
    *,
    screenshots: List[str],
    review_jobs: List[str],
    screenshot_review_gate_path: Path,
    screenshot_review_gate: Dict[str, Any],
    ui_release_gate_path: Path,
    ui_release_gate: Dict[str, Any],
) -> Dict[str, Any]:
    screenshot_review_jobs = _review_jobs(screenshot_review_gate)
    screenshot_review_text = json.dumps(screenshot_review_gate, sort_keys=True)
    ui_release_text = json.dumps(ui_release_gate, sort_keys=True)
    screenshot_checks = []
    for path, text in (
        (screenshot_review_gate_path, screenshot_review_text),
        (ui_release_gate_path, ui_release_text),
    ):
        screenshot_checks.append(
            {
                "path": str(path),
                "required_screenshots": list(screenshots),
                "missing_screenshots": _contains_tokens(text, screenshots),
            }
        )

    missing_review_jobs = [job for job in review_jobs if job not in screenshot_review_jobs]
    review_job_status = []
    for job in review_jobs:
        payload = dict(screenshot_review_jobs.get(job) or {})
        review_job_status.append(
            {
                "job_id": job,
                "status": _normalize_text(payload.get("status")) or ("missing" if not payload else ""),
                "screenshots": _normalize_list(payload.get("screenshots")),
            }
        )

    missing_screenshots = sorted(
        {
            item
            for check in screenshot_checks
            for item in check.get("missing_screenshots", [])
            if item
        }
    )

    return {
        "screenshot_receipts": [
            str(screenshot_review_gate_path),
            str(ui_release_gate_path),
        ],
        "required_screenshots": list(screenshots),
        "screenshot_checks": screenshot_checks,
        "review_jobs": review_job_status,
        "missing_review_jobs": missing_review_jobs,
        "missing_screenshots": missing_screenshots,
        "status": "pass" if not missing_screenshots and not missing_review_jobs else "fail",
    }


def build_payload(
    *,
    task_local_telemetry_path: Path,
    runtime_handoff_path: Path,
    readiness_path: Path,
    capture_pack_path: Path,
    workflow_pack_path: Path,
    parity_audit_path: Path,
    screenshot_review_gate_path: Path,
    desktop_visual_gate_path: Path,
    veteran_task_gate_path: Path,
    ui_release_gate_path: Path,
    import_receipts_doc_path: Path,
    import_receipts_json_path: Path,
    import_parity_certification_path: Path,
    generated_at: str,
) -> Dict[str, Any]:
    telemetry = _load_json(task_local_telemetry_path)
    readiness = _load_json(readiness_path)
    capture_pack = _load_yaml(capture_pack_path)
    workflow_pack = _load_yaml(workflow_pack_path)
    parity_audit = _load_json(parity_audit_path)
    screenshot_review_gate = _load_json(screenshot_review_gate_path)
    desktop_visual_gate = _load_json(desktop_visual_gate_path)
    veteran_task_gate = _load_json(veteran_task_gate_path)
    ui_release_gate = _load_json(ui_release_gate_path)
    import_receipts_json = _load_json(import_receipts_json_path)
    import_parity_certification = _load_json(import_parity_certification_path)
    import_receipts_doc = _load_text(import_receipts_doc_path)

    parity_row_map = _parity_rows(parity_audit)
    capture_anchor_map = _legacy_source_anchors(capture_pack)
    route_local_receipt_map = _route_local_receipts(screenshot_review_gate)
    veteran_proofs = _proofs(veteran_task_gate)
    ui_proofs = _proofs(ui_release_gate)
    veteran_task_text = json.dumps(veteran_task_gate, sort_keys=True)
    ui_release_text = json.dumps(ui_release_gate, sort_keys=True)
    screenshot_dir = _normalize_text(((screenshot_review_gate.get("evidence") or {}).get("screenshotDirectory")))
    required_visuals = set(_normalize_list(((ui_release_gate.get("visualReviewEvidence") or {}).get("expectedScreenshots"))))
    required_visuals.update(_normalize_list(((ui_release_gate.get("directImportRouteProof") or {}).get("screenshots"))))
    required_visuals.update(_normalize_list(((screenshot_review_gate.get("screenshotAssetReview") or {}).get("requiredScreenshots"))))
    core_receipt_text = json.dumps(import_receipts_json, indent=2, sort_keys=True) + "\n" + json.dumps(
        import_parity_certification, indent=2, sort_keys=True
    ) + "\n" + import_receipts_doc

    route_packets: List[Dict[str, Any]] = []
    family_packets: List[Dict[str, Any]] = []

    for row_id, spec in ROUTE_SPECS.items():
        parity_row = dict(parity_row_map[row_id])
        route_receipt = dict(
            route_local_receipt_map.get(spec["route_local_receipt_id"]) or _fallback_route_local_receipt(spec, ui_release_gate)
        )
        anchor = dict(capture_anchor_map[spec["legacy_source_anchor_id"]])
        missing_visuals = sorted(set(spec["screenshots"]) - required_visuals)
        runtime_evidence_paths = [
            veteran_task_gate_path,
            ui_release_gate_path,
        ]
        runtime_receipt_checks = _receipt_checks(runtime_evidence_paths, spec["runtime_receipt_tokens"])
        missing_runtime_tokens = _combined_missing_tokens(runtime_evidence_paths, spec["runtime_receipt_tokens"])
        missing_ui_tokens = _contains_tokens(ui_release_text, [spec["route_local_receipt_id"]] + list(spec["screenshots"]))
        core_evidence_paths = [
            import_receipts_doc_path,
            import_receipts_json_path,
            import_parity_certification_path,
        ]
        core_receipt_checks = _receipt_checks(core_evidence_paths, spec["core_receipt_tokens"])
        missing_core_tokens = _combined_missing_tokens(core_evidence_paths, spec["core_receipt_tokens"])
        if missing_visuals or missing_runtime_tokens or missing_ui_tokens or missing_core_tokens:
            raise ValueError(
                f"{row_id} drifted from live proof: visuals={missing_visuals} runtime={missing_runtime_tokens} "
                f"ui={missing_ui_tokens} core={missing_core_tokens}"
            )
        route_packets.append(
            {
                "id": spec["compact_id"],
                "parity_audit_row_id": row_id,
                "label": spec["label"],
                "legacy_source_anchor": anchor,
                "compare_artifacts": list(spec["compare_artifacts"]),
                "parity_verdict": {
                    "present_in_chummer5a": _normalize_text(parity_row.get("present_in_chummer5a")),
                    "present_in_chummer6": _normalize_text(parity_row.get("present_in_chummer6")),
                    "visual_parity": _normalize_text(parity_row.get("visual_parity")),
                    "behavioral_parity": _normalize_text(parity_row.get("behavioral_parity")),
                    "removable_if_not_in_chummer5a": _normalize_text(parity_row.get("removable_if_not_in_chummer5a")),
                    "reason": _normalize_text(parity_row.get("reason")),
                },
                "route_local_screenshot_pack": {
                    "receipt_id": spec["route_local_receipt_id"],
                    "workflow_family_id": _normalize_text(route_receipt.get("workflowFamilyId")),
                    "legacy_behavior_lineage": _normalize_text(route_receipt.get("legacyBehaviorLineage")),
                    "screenshot_dir": screenshot_dir,
                    "screenshots": list(spec["screenshots"]),
                    "route_ids": _normalize_list(route_receipt.get("routeIds")),
                },
                "artifact_proof_pack": _artifact_proof_pack(
                    screenshots=list(spec["screenshots"]),
                    review_jobs=list(spec["review_jobs"]),
                    screenshot_review_gate_path=screenshot_review_gate_path,
                    screenshot_review_gate=screenshot_review_gate,
                    ui_release_gate_path=ui_release_gate_path,
                    ui_release_gate=ui_release_gate,
                ),
                "runtime_compare_packet": {
                    "veteran_task_gate_receipt_id": spec["route_local_receipt_id"],
                    "required_tokens": list(spec["runtime_receipt_tokens"]),
                    "evidence_paths": [str(path) for path in runtime_evidence_paths],
                    "receipt_checks": runtime_receipt_checks,
                    "status": "pass" if not missing_runtime_tokens else "fail",
                },
                "core_compare_packet": {
                    "required_tokens": list(spec["core_receipt_tokens"]),
                    "evidence_paths": [str(path) for path in core_evidence_paths],
                    "receipt_checks": core_receipt_checks,
                    "status": "pass" if not missing_core_tokens else "fail",
                },
                "parity_evidence_paths": _normalize_list(parity_row.get("evidence")),
            }
        )

    for row_id, spec in FAMILY_SPECS.items():
        parity_row = dict(parity_row_map[row_id])
        route_receipt = dict(
            route_local_receipt_map.get(spec["route_local_receipt_id"]) or _fallback_route_local_receipt(spec, ui_release_gate)
        )
        workflow_family = dict(_workflow_pack_family(workflow_pack, spec["compact_id"]))
        missing_visuals = sorted(set(spec["screenshots"]) - required_visuals)
        runtime_evidence_paths = [
            screenshot_review_gate_path,
            veteran_task_gate_path,
            ui_release_gate_path,
        ]
        runtime_receipt_checks = _receipt_checks(runtime_evidence_paths, spec["runtime_receipt_tokens"])
        missing_runtime_tokens = _combined_missing_tokens(runtime_evidence_paths, spec["runtime_receipt_tokens"])
        core_evidence_paths = [
            import_receipts_doc_path,
            import_receipts_json_path,
            import_parity_certification_path,
        ]
        core_receipt_checks = _receipt_checks(core_evidence_paths, spec["core_receipt_tokens"])
        missing_core_tokens = _combined_missing_tokens(core_evidence_paths, spec["core_receipt_tokens"])
        if missing_visuals or missing_runtime_tokens or missing_core_tokens:
            raise ValueError(
                f"{row_id} drifted from live proof: visuals={missing_visuals} runtime={missing_runtime_tokens} "
                f"core={missing_core_tokens}"
            )
        family_packets.append(
            {
                "id": spec["compact_id"],
                "parity_audit_row_id": row_id,
                "label": spec["label"],
                "compare_artifacts": list(spec["compare_artifacts"]),
                "workflow_pack_compare_artifacts": _normalize_list(workflow_family.get("compare_artifacts")),
                "parity_verdict": {
                    "present_in_chummer5a": _normalize_text(parity_row.get("present_in_chummer5a")),
                    "present_in_chummer6": _normalize_text(parity_row.get("present_in_chummer6")),
                    "visual_parity": _normalize_text(parity_row.get("visual_parity")),
                    "behavioral_parity": _normalize_text(parity_row.get("behavioral_parity")),
                    "removable_if_not_in_chummer5a": _normalize_text(parity_row.get("removable_if_not_in_chummer5a")),
                    "reason": _normalize_text(parity_row.get("reason")),
                },
                "route_local_screenshot_pack": {
                    "receipt_id": spec["route_local_receipt_id"],
                    "workflow_family_id": _normalize_text(route_receipt.get("workflowFamilyId")),
                    "legacy_behavior_lineage": _normalize_text(route_receipt.get("legacyBehaviorLineage")),
                    "screenshot_dir": screenshot_dir,
                    "screenshots": list(spec["screenshots"]),
                    "route_ids": _normalize_list(route_receipt.get("routeIds")),
                },
                "artifact_proof_pack": _artifact_proof_pack(
                    screenshots=list(spec["screenshots"]),
                    review_jobs=list(spec["review_jobs"]),
                    screenshot_review_gate_path=screenshot_review_gate_path,
                    screenshot_review_gate=screenshot_review_gate,
                    ui_release_gate_path=ui_release_gate_path,
                    ui_release_gate=ui_release_gate,
                ),
                "runtime_compare_packet": {
                    "required_tokens": list(spec["runtime_receipt_tokens"]),
                    "evidence_paths": [str(path) for path in runtime_evidence_paths],
                    "receipt_checks": runtime_receipt_checks,
                    "status": "pass" if not missing_runtime_tokens else "fail",
                },
                "core_compare_packet": {
                    "required_tokens": list(spec["core_receipt_tokens"]),
                    "evidence_paths": [str(path) for path in core_evidence_paths],
                    "receipt_checks": core_receipt_checks,
                    "status": "pass" if not missing_core_tokens else "fail",
                },
                "parity_evidence_paths": _normalize_list(parity_row.get("evidence")),
            }
        )

    readiness_coverage = dict(readiness.get("coverage") or {})
    readiness_details = dict(readiness.get("coverage_details") or {})

    return {
        "contract_name": "executive_assistant.m141_route_local_compare_packets",
        "schema_version": 1,
        "generated_at": generated_at,
        "milestone": {
            "id": MILESTONE_ID,
            "wave": WAVE_ID,
            "package_id": PACKAGE_ID,
            "work_task_id": WORK_TASK_ID,
            "frontier_id": _frontier_id(telemetry),
            "owned_surfaces": OWNED_SURFACES,
        },
        "sync_context": {
            "task_local_telemetry_path": str(task_local_telemetry_path),
            "task_local_telemetry_snapshot": _task_local_snapshot(telemetry),
            "runtime_handoff_path": str(runtime_handoff_path),
            "readiness_path": str(readiness_path),
            "readiness_generated_at": _parse_generated_at(readiness_path, readiness),
            "parity_audit_path": str(parity_audit_path),
            "parity_audit_generated_at": _parse_generated_at(parity_audit_path, parity_audit),
            "screenshot_review_gate_path": str(screenshot_review_gate_path),
            "screenshot_review_gate_generated_at": _parse_generated_at(screenshot_review_gate_path, screenshot_review_gate),
            "desktop_visual_gate_path": str(desktop_visual_gate_path),
            "desktop_visual_gate_generated_at": _parse_generated_at(desktop_visual_gate_path, desktop_visual_gate),
            "veteran_task_gate_path": str(veteran_task_gate_path),
            "veteran_task_gate_generated_at": _parse_generated_at(veteran_task_gate_path, veteran_task_gate),
            "ui_release_gate_path": str(ui_release_gate_path),
            "ui_release_gate_generated_at": _parse_generated_at(ui_release_gate_path, ui_release_gate),
            "import_receipts_doc_path": str(import_receipts_doc_path),
            "import_receipts_json_path": str(import_receipts_json_path),
            "import_receipts_json_generated_at": _parse_generated_at(import_receipts_json_path, import_receipts_json),
            "import_parity_certification_path": str(import_parity_certification_path),
            "import_parity_certification_generated_at": _parse_generated_at(
                import_parity_certification_path, import_parity_certification
            ),
        },
        "worker_run_guard": {
            "implementation_only": True,
            "polling_disabled": bool(telemetry.get("polling_disabled")),
            "allowed_evidence_sources": [
                "task-local telemetry file",
                "shard runtime handoff",
                "Chummer5A oracle capture pack",
                "published parity audit and screenshot review receipts",
                "published veteran-task and UI release receipts",
                "published core M141 import receipts",
            ],
            "blocked_helper_evidence": [
                "supervisor status helpers",
                "supervisor eta helpers",
                "operator-only handoff commands",
            ],
        },
        "route_local_screenshot_packs": route_packets,
        "family_compare_packets": family_packets,
        "live_readiness_projection": {
            "coverage_key": "desktop_client",
            "status": _normalize_text(readiness_coverage.get("desktop_client")),
            "summary": _normalize_text(dict(readiness_details.get("desktop_client") or {}).get("summary")),
            "missing_keys": _normalize_list(readiness.get("missing_keys")),
        },
        "notes": [
            "This packet compiles direct route-local screenshot packs and compare packets for milestone 141; it does not overwrite live readiness receipts.",
            "Every screenshot, runtime token, and deterministic core receipt token is projected from already-published proof instead of inventing new parity claims.",
        ],
        "source_inputs": {
            "task_local_telemetry": _path_snapshot(task_local_telemetry_path, telemetry),
            "readiness": _path_snapshot(readiness_path, readiness),
            "capture_pack": _path_snapshot(capture_pack_path, capture_pack),
            "workflow_pack": _path_snapshot(workflow_pack_path, workflow_pack),
            "parity_audit": _path_snapshot(parity_audit_path, parity_audit),
            "screenshot_review_gate": _path_snapshot(screenshot_review_gate_path, screenshot_review_gate),
            "desktop_visual_gate": _path_snapshot(desktop_visual_gate_path, desktop_visual_gate),
            "veteran_task_gate": _path_snapshot(veteran_task_gate_path, veteran_task_gate),
            "ui_release_gate": _path_snapshot(ui_release_gate_path, ui_release_gate),
            "import_receipts_doc": _path_snapshot(import_receipts_doc_path),
            "import_receipts_json": _path_snapshot(import_receipts_json_path, import_receipts_json),
            "import_parity_certification": _path_snapshot(import_parity_certification_path, import_parity_certification),
        },
    }


def build_markdown(payload: Dict[str, Any]) -> str:
    lines = [
        "# M141 route-local compare packets",
        "",
        "This EA-owned packet compiles the direct screenshot and compare evidence for translator, XML amendment, Hero Lab, and adjacent import-oracle parity without inventing a second proof plane.",
        "",
        f"- milestone: `{payload['milestone']['id']}`",
        f"- package: `{payload['milestone']['package_id']}`",
        f"- work task: `{payload['milestone']['work_task_id']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- live desktop readiness: `{payload['live_readiness_projection']['status']}`",
        "",
        "## Route-local screenshot packs",
        "",
    ]
    for row in payload["route_local_screenshot_packs"]:
        lines.extend(
            [
                f"### {row['label']}",
                "",
                f"- parity row: `{row['parity_audit_row_id']}`",
                f"- compare artifacts: {', '.join(f'`{item}`' for item in row['compare_artifacts'])}",
                f"- screenshots: {', '.join(f'`{item}`' for item in row['route_local_screenshot_pack']['screenshots'])}",
                f"- screenshot proof status: `{row['artifact_proof_pack']['status']}`",
                f"- runtime tokens: {', '.join(f'`{item}`' for item in row['runtime_compare_packet']['required_tokens'])}",
                f"- runtime proof status: `{row['runtime_compare_packet']['status']}`",
                f"- core receipt tokens: {', '.join(f'`{item}`' for item in row['core_compare_packet']['required_tokens'])}",
                f"- core proof status: `{row['core_compare_packet']['status']}`",
                f"- parity verdict: visual `{row['parity_verdict']['visual_parity']}`, behavioral `{row['parity_verdict']['behavioral_parity']}`",
                f"- reason: {row['parity_verdict']['reason']}",
                "",
            ]
        )
    lines.extend(["## Family compare packets", ""])
    for row in payload["family_compare_packets"]:
        lines.extend(
            [
                f"### {row['label']}",
                "",
                f"- parity row: `{row['parity_audit_row_id']}`",
                f"- compare artifacts: {', '.join(f'`{item}`' for item in row['compare_artifacts'])}",
                f"- screenshots: {', '.join(f'`{item}`' for item in row['route_local_screenshot_pack']['screenshots'])}",
                f"- screenshot proof status: `{row['artifact_proof_pack']['status']}`",
                f"- runtime tokens: {', '.join(f'`{item}`' for item in row['runtime_compare_packet']['required_tokens'])}",
                f"- runtime proof status: `{row['runtime_compare_packet']['status']}`",
                f"- core receipt tokens: {', '.join(f'`{item}`' for item in row['core_compare_packet']['required_tokens'])}",
                f"- core proof status: `{row['core_compare_packet']['status']}`",
                f"- parity verdict: visual `{row['parity_verdict']['visual_parity']}`, behavioral `{row['parity_verdict']['behavioral_parity']}`",
                f"- reason: {row['parity_verdict']['reason']}",
                "",
            ]
        )
    lines.extend(
        [
            "## Live readiness note",
            "",
            f"- desktop_client status: `{payload['live_readiness_projection']['status']}`",
            f"- summary: {payload['live_readiness_projection']['summary']}",
            f"- missing keys: {', '.join(f'`{item}`' for item in payload['live_readiness_projection']['missing_keys']) or '`none`'}",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    output_path = Path(args.output).resolve()
    markdown_output_path = Path(args.markdown_output).resolve()
    runtime_handoff_path = _resolve_runtime_handoff_path(args.runtime_handoff).resolve()
    payload = build_payload(
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
        generated_at=_utc_now(),
    )
    output_path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")
    markdown_output_path.write_text(build_markdown(payload), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
