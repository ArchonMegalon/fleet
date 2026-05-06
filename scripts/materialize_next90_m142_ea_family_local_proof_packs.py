#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

import yaml


ROOT = Path("/docker/fleet")
DOCS_ROOT = ROOT / "docs" / "chummer5a-oracle"
PRESENTATION_PUBLISHED = Path("/docker/chummercomplete/chummer-presentation/.codex-studio/published")
CORE_DOCS = Path("/docker/chummercomplete/chummer-core-engine/docs")
SUPERVISOR_ROOT = Path("/var/lib/codex-fleet/chummer_design_supervisor")

DEFAULT_OUTPUT = DOCS_ROOT / "m142_family_local_proof_packs.yaml"
DEFAULT_MARKDOWN = DOCS_ROOT / "m142_family_local_proof_packs.md"
def _latest_existing_path(pattern: str, fallback: Path) -> Path:
    matches = sorted(SUPERVISOR_ROOT.glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True)
    return matches[0] if matches else fallback


DEFAULT_TASK_LOCAL_TELEMETRY = _latest_existing_path(
    "shard-*/runs/*/TASK_LOCAL_TELEMETRY.generated.json",
    SUPERVISOR_ROOT / "TASK_LOCAL_TELEMETRY.generated.json",
)
DEFAULT_RUNTIME_HANDOFF = _latest_existing_path(
    "shard-*/ACTIVE_RUN_HANDOFF.generated.md",
    SUPERVISOR_ROOT / "ACTIVE_RUN_HANDOFF.generated.md",
)
DEFAULT_READINESS = ROOT / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
DEFAULT_WORKFLOW_PACK = DOCS_ROOT / "veteran_workflow_packs.yaml"
DEFAULT_PARITY_AUDIT = PRESENTATION_PUBLISHED / "CHUMMER5A_UI_ELEMENT_PARITY_AUDIT.generated.json"
DEFAULT_SCREENSHOT_REVIEW_GATE = PRESENTATION_PUBLISHED / "CHUMMER5A_SCREENSHOT_REVIEW_GATE.generated.json"
DEFAULT_DESKTOP_VISUAL_GATE = PRESENTATION_PUBLISHED / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
DEFAULT_UI_RELEASE_GATE = PRESENTATION_PUBLISHED / "UI_FLAGSHIP_RELEASE_GATE.generated.json"
DEFAULT_UI_LOCAL_RELEASE_PROOF = PRESENTATION_PUBLISHED / "UI_LOCAL_RELEASE_PROOF.generated.json"
DEFAULT_SECTION_HOST_PARITY = PRESENTATION_PUBLISHED / "SECTION_HOST_RULESET_PARITY.generated.json"
DEFAULT_DIALOG_PARITY = PRESENTATION_PUBLISHED / "GENERATED_DIALOG_ELEMENT_PARITY.generated.json"
DEFAULT_GM_RUNBOARD_ROUTE = PRESENTATION_PUBLISHED / "NEXT90_M121_UI_GM_RUNBOARD_ROUTE.generated.json"
DEFAULT_VETERAN_TASK_GATE = PRESENTATION_PUBLISHED / "VETERAN_TASK_TIME_EVIDENCE_GATE.generated.json"
DEFAULT_CLASSIC_DENSE_GATE = PRESENTATION_PUBLISHED / "CLASSIC_DENSE_WORKBENCH_POSTURE_GATE.generated.json"
DEFAULT_CORE_DENSE_RECEIPTS = CORE_DOCS / "NEXT90_M142_DENSE_WORKBENCH_RECEIPTS.md"

PACKAGE_ID = "next90-m142-ea-compile-family-local-screenshot-and-interaction-packs-for-these-workflows"
FRONTIER_ID = 2668415614
MILESTONE_ID = 142
WAVE_ID = "W22P"
OWNED_SURFACES = ["compile_family_local_screenshot_and_interaction_packs_fo:ea"]


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize the EA M142 family-local proof packet.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--markdown-output", default=str(DEFAULT_MARKDOWN))
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
    return parser.parse_args(argv)


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _read_yaml(path: Path) -> Dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _json_generated_at(path: Path) -> str | None:
    try:
        payload = _read_json(path)
    except Exception:
        return None
    for key in ("generated_at", "generatedAt"):
        value = payload.get(key)
        if value:
            return str(value)
    return None


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _receipt_text(paths: Iterable[Path]) -> str:
    parts: List[str] = []
    for path in paths:
        try:
            parts.append(_read_text(path))
        except UnicodeDecodeError:
            parts.append(json.dumps(_read_json(path), indent=2, sort_keys=True))
    return "\n".join(parts)


def _normalize_required_token(token: Any) -> str:
    if isinstance(token, dict):
        keys = [str(key).strip() for key in token.keys() if str(key).strip()]
        if len(keys) == 1:
            key = keys[0]
            return key if key.endswith(":") else f"{key}:"
    text = str(token).strip()
    if text.startswith("workflow:"):
        return text.split(":", 1)[1]
    return text


def _token_check(paths: List[Path], required_tokens: List[str]) -> Dict[str, Any]:
    text = _receipt_text(paths)
    normalized = [_normalize_required_token(token) for token in required_tokens]
    missing = [token for token in normalized if token not in text]
    return {
        "receipt_paths": [str(path) for path in paths],
        "required_tokens": normalized,
        "missing_tokens": missing,
        "status": "pass" if not missing else "fail",
    }


def _parse_handoff_first_output(text: str) -> str:
    needle = "- First output at:"
    for line in text.splitlines():
        if line.startswith(needle):
            return line.split(":", 1)[1].strip()
    return "unknown"


def _family_label(family_id: str) -> str:
    return family_id.replace("_", " ").title()


def _family_row_map(workflow_pack: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    rows = [dict(row) for row in (workflow_pack.get("family_local_proof_packs") or []) if isinstance(row, dict)]
    return {str(row.get("family_id") or "").strip(): row for row in rows}


def _parity_row_map(parity_audit: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    rows = [dict(row) for row in (parity_audit.get("rows") or []) if isinstance(row, dict)]
    return {str(row.get("id") or "").strip(): row for row in rows}


def _family_packet(
    family_id: str,
    workflow_row: Dict[str, Any],
    parity_row: Dict[str, Any],
    review_path_map: Dict[str, Path],
    interaction_path_map: Dict[str, Path],
) -> Dict[str, Any]:
    screenshot_pack = dict(workflow_row.get("screenshot_pack") or {})
    interaction_pack = dict(workflow_row.get("interaction_pack") or {})

    review_paths = [review_path_map[str(item)] for item in (screenshot_pack.get("review_receipts") or [])]
    interaction_paths = [interaction_path_map[str(item)] for item in (interaction_pack.get("runtime_receipts") or [])]

    screenshot_markers = [
        *[str(item) for item in (screenshot_pack.get("screenshots") or [])],
    ]
    advisory_focus = [str(item) for item in (screenshot_pack.get("screenshot_focus") or [])]

    screenshot_check = _token_check(review_paths, screenshot_markers)
    focus_check = _token_check(
        [*review_paths, *[path for path in interaction_paths if path.suffix == ".json"]],
        advisory_focus,
    )
    interaction_check = _token_check(
        interaction_paths,
        [item for item in (interaction_pack.get("required_tokens") or [])],
    )

    statuses = [screenshot_check["status"], interaction_check["status"]]
    status = "pass" if all(item == "pass" for item in statuses) else "fail"

    return {
        "family_id": family_id,
        "parity_audit_row_id": f"family:{family_id}",
        "label": parity_row.get("label") or _family_label(family_id),
        "compare_artifacts": [str(item) for item in (workflow_row.get("compare_artifacts") or [])],
        "parity_verdict": {
            "present_in_chummer5a": parity_row.get("present_in_chummer5a"),
            "present_in_chummer6": parity_row.get("present_in_chummer6"),
            "visual_parity": parity_row.get("visual_parity"),
            "behavioral_parity": parity_row.get("behavioral_parity"),
            "removable_if_not_in_chummer5a": parity_row.get("removable_if_not_in_chummer5a"),
            "reason": parity_row.get("reason"),
        },
        "family_local_packet": {
            "summary": workflow_row.get("summary"),
            "screenshots": [str(item) for item in (screenshot_pack.get("screenshots") or [])],
            "screenshot_focus": advisory_focus,
            "review_receipts": screenshot_check,
            "focus_receipts": focus_check,
            "interaction_receipts": interaction_check,
            "status": status,
        },
        "evidence_paths": sorted(
            {
                *[str(path) for path in review_paths],
                *[str(path) for path in interaction_paths],
                *[str(item) for item in (parity_row.get("evidence") or [])],
            }
        ),
    }


def build_payload(
    *,
    task_local_telemetry_path: Path,
    runtime_handoff_path: Path,
    readiness_path: Path,
    workflow_pack_path: Path,
    parity_audit_path: Path,
    screenshot_review_gate_path: Path,
    desktop_visual_gate_path: Path,
    ui_release_gate_path: Path,
    ui_local_release_proof_path: Path,
    section_host_parity_path: Path,
    dialog_parity_path: Path,
    gm_runboard_route_path: Path,
    veteran_task_gate_path: Path,
    classic_dense_gate_path: Path,
    core_dense_receipts_path: Path,
    generated_at: str | None = None,
) -> Dict[str, Any]:
    telemetry = _read_json(task_local_telemetry_path)
    readiness = _read_json(readiness_path)
    workflow_pack = _read_yaml(workflow_pack_path)
    parity_audit = _read_json(parity_audit_path)
    handoff_text = _read_text(runtime_handoff_path)

    workflow_rows = _family_row_map(workflow_pack)
    parity_rows = _parity_row_map(parity_audit)

    review_path_map = {
        str(screenshot_review_gate_path): screenshot_review_gate_path,
        str(desktop_visual_gate_path): desktop_visual_gate_path,
        str(ui_release_gate_path): ui_release_gate_path,
        str(classic_dense_gate_path): classic_dense_gate_path,
    }
    interaction_path_map = {
        str(section_host_parity_path): section_host_parity_path,
        str(ui_release_gate_path): ui_release_gate_path,
        str(ui_local_release_proof_path): ui_local_release_proof_path,
        str(veteran_task_gate_path): veteran_task_gate_path,
        str(dialog_parity_path): dialog_parity_path,
        str(gm_runboard_route_path): gm_runboard_route_path,
        str(core_dense_receipts_path): core_dense_receipts_path,
    }

    family_ids = [
        "dense_builder_and_career_workflows",
        "dice_initiative_and_table_utilities",
        "identity_contacts_lifestyles_history",
    ]
    packets = [
        _family_packet(
            family_id,
            workflow_rows[family_id],
            parity_rows[f"family:{family_id}"],
            review_path_map,
            interaction_path_map,
        )
        for family_id in family_ids
    ]
    missing_family_packets = [row["family_id"] for row in packets if row["family_local_packet"]["status"] != "pass"]

    return {
        "contract_name": "executive_assistant.m142_family_local_proof_packs",
        "schema_version": 1,
        "generated_at": generated_at or _utc_now(),
        "milestone": {
            "id": MILESTONE_ID,
            "wave": WAVE_ID,
            "package_id": PACKAGE_ID,
            "frontier_id": FRONTIER_ID,
            "owned_surfaces": OWNED_SURFACES,
        },
        "sync_context": {
            "task_local_telemetry_path": str(task_local_telemetry_path),
            "task_local_telemetry_snapshot": {
                "mode": telemetry.get("mode"),
                "scope_label": telemetry.get("scope_label"),
                "slice_summary": telemetry.get("slice_summary"),
                "status_query_supported": telemetry.get("status_query_supported"),
                "polling_disabled": telemetry.get("polling_disabled"),
                "remaining_open_milestones": telemetry.get("remaining_open_milestones"),
                "remaining_not_started_milestones": telemetry.get("remaining_not_started_milestones"),
                "missing_flagship_coverage": telemetry.get("missing_flagship_coverage"),
                "frontier_briefs": telemetry.get("frontier_briefs") or [],
            },
            "runtime_handoff_path": str(runtime_handoff_path),
            "runtime_handoff_first_output_at": _parse_handoff_first_output(handoff_text),
            "readiness_path": str(readiness_path),
            "readiness_generated_at": _json_generated_at(readiness_path),
            "workflow_pack_path": str(workflow_pack_path),
            "workflow_pack_generated_at": str(_read_yaml(workflow_pack_path).get("generated_at") or ""),
            "parity_audit_path": str(parity_audit_path),
            "parity_audit_generated_at": _json_generated_at(parity_audit_path),
            "screenshot_review_gate_path": str(screenshot_review_gate_path),
            "screenshot_review_gate_generated_at": _json_generated_at(screenshot_review_gate_path),
            "desktop_visual_gate_path": str(desktop_visual_gate_path),
            "desktop_visual_gate_generated_at": _json_generated_at(desktop_visual_gate_path),
            "ui_release_gate_path": str(ui_release_gate_path),
            "ui_release_gate_generated_at": _json_generated_at(ui_release_gate_path),
            "ui_local_release_proof_path": str(ui_local_release_proof_path),
            "ui_local_release_proof_generated_at": _json_generated_at(ui_local_release_proof_path),
            "section_host_parity_path": str(section_host_parity_path),
            "section_host_parity_generated_at": _json_generated_at(section_host_parity_path),
            "dialog_parity_path": str(dialog_parity_path),
            "dialog_parity_generated_at": _json_generated_at(dialog_parity_path),
            "gm_runboard_route_path": str(gm_runboard_route_path),
            "gm_runboard_route_generated_at": _json_generated_at(gm_runboard_route_path),
            "veteran_task_gate_path": str(veteran_task_gate_path),
            "veteran_task_gate_generated_at": _json_generated_at(veteran_task_gate_path),
            "classic_dense_gate_path": str(classic_dense_gate_path),
            "classic_dense_gate_generated_at": _json_generated_at(classic_dense_gate_path),
            "core_dense_receipts_path": str(core_dense_receipts_path),
        },
        "worker_run_guard": {
            "implementation_only": True,
            "polling_disabled": True,
            "allowed_evidence_sources": [
                "task-local telemetry file",
                "shard runtime handoff",
                "veteran workflow family-local proof packs",
                "published parity audit and screenshot review receipts",
                "published UI route proof receipts",
                "published core M142 dense-workbench receipts",
            ],
            "blocked_helper_evidence": [
                "supervisor status helpers",
                "supervisor eta helpers",
                "operator-only handoff commands",
            ],
        },
        "family_local_proof_packets": packets,
        "whole_product_frontier_coverage": {
            "readiness_status": readiness.get("status"),
            "package_relevant_coverage_keys": [
                "desktop_client",
                "fleet_and_operator_loop",
            ],
            "desktop_client_status": "missing" if "desktop_client" in (readiness.get("missing_keys") or []) else "ready",
            "fleet_and_operator_loop_status": (
                "missing" if "fleet_and_operator_loop" in (readiness.get("missing_keys") or []) else "ready"
            ),
            "missing_keys": readiness.get("missing_keys") or [],
            "summary": ((readiness.get("flagship_readiness_audit") or {}).get("reason") or readiness.get("summary") or ""),
        },
        "packet_summary": {
            "status": "pass" if not missing_family_packets else "fail",
            "family_count": len(packets),
            "passing_family_count": len([row for row in packets if row["family_local_packet"]["status"] == "pass"]),
            "failing_family_ids": missing_family_packets,
        },
        "source_inputs": {
            "task_local_telemetry": {
                "path": str(task_local_telemetry_path),
                "generated_at": _json_generated_at(task_local_telemetry_path),
                "sha256": _sha256(task_local_telemetry_path),
            },
            "runtime_handoff": {
                "path": str(runtime_handoff_path),
                "sha256": _sha256(runtime_handoff_path),
            },
            "readiness": {
                "path": str(readiness_path),
                "generated_at": _json_generated_at(readiness_path),
                "sha256": _sha256(readiness_path),
            },
            "workflow_pack": {
                "path": str(workflow_pack_path),
                "sha256": _sha256(workflow_pack_path),
            },
            "parity_audit": {
                "path": str(parity_audit_path),
                "generated_at": _json_generated_at(parity_audit_path),
                "sha256": _sha256(parity_audit_path),
            },
        },
    }


def _render_markdown(payload: Dict[str, Any]) -> str:
    lines = [
        "# NEXT90 M142 EA family-local proof packs",
        "",
        f"- Generated at: `{payload['generated_at']}`",
        f"- Package: `{payload['milestone']['package_id']}`",
        f"- Frontier: `{payload['milestone']['frontier_id']}`",
        f"- Readiness status: `{payload['whole_product_frontier_coverage']['readiness_status']}`",
        f"- Desktop coverage: `{payload['whole_product_frontier_coverage']['desktop_client_status']}`",
        "",
        "This packet binds each M142 family to exact screenshots, review receipts, and interaction receipts without collapsing the proof into broad family prose.",
        "",
    ]
    for row in payload["family_local_proof_packets"]:
        packet = row["family_local_packet"]
        lines.extend(
            [
                f"## {row['label']}",
                "",
                f"- Status: `{packet['status']}`",
                f"- Compare artifacts: {', '.join(f'`{item}`' for item in row['compare_artifacts'])}",
                f"- Screenshots: {', '.join(f'`{item}`' for item in packet['screenshots'])}",
                f"- Screenshot focus: {', '.join(f'`{item}`' for item in packet['screenshot_focus'])}",
                f"- Review receipts: {', '.join(f'`{item}`' for item in packet['review_receipts']['receipt_paths'])}",
                f"- Interaction receipts: {', '.join(f'`{item}`' for item in packet['interaction_receipts']['receipt_paths'])}",
                f"- Parity reason: {row['parity_verdict']['reason']}",
                "",
            ]
        )
    lines.extend(
        [
            "## Readiness note",
            "",
            f"- `{payload['whole_product_frontier_coverage']['summary']}`",
            "- This packet is evidence for the EA-owned proof slice only. It does not overwrite the live readiness receipt.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(
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
    )
    output_path = Path(args.output).resolve()
    markdown_path = Path(args.markdown_output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")
    markdown_path.write_text(_render_markdown(payload) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
