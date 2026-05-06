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
PUBLISHED = ROOT / ".codex-studio" / "published"
PRODUCT_MIRROR = Path("/docker/chummercomplete/chummer-design/products/chummer")
PRESENTATION_PUBLISHED = Path("/docker/chummercomplete/chummer-presentation/.codex-studio/published")
CORE_DOCS = Path("/docker/chummercomplete/chummer-core-engine/docs")

PACKAGE_ID = "next90-m143-fleet-fail-closeout-when-these-families-remain-green-only-by-broad-family-pr"
FRONTIER_ID = 8787562259
MILESTONE_ID = 143
WORK_TASK_ID = "143.6"
WAVE_ID = "W22P"
QUEUE_TITLE = "Fail closeout when these families remain green only by broad family prose, missing outputs, or stale route-local receipts."
OWNED_SURFACES = ["fail_closeout_when_these_families_remain_green_only_by_b:fleet"]
ALLOWED_PATHS = ["scripts", "tests", ".codex-studio", "feedback"]
COMPLETION_ACTION = "verify_closed_package_only"
LANDED_COMMIT = "c851228a"
DO_NOT_REOPEN_REASON = (
    "M143 fleet route-local output closeout gate is complete; future shards must verify the repo-local gate scripts, "
    "generated proof artifacts, and canonical queue/registry mirrors instead of reopening print or export or exchange "
    "and SR6 supplement or house-rule parity closeout by broad family prose."
)
QUEUE_PROOF = [
    "/docker/fleet/scripts/materialize_next90_m143_fleet_route_local_output_closeout_gates.py",
    "/docker/fleet/scripts/verify_next90_m143_fleet_route_local_output_closeout_gates.py",
    "/docker/fleet/tests/test_materialize_next90_m143_fleet_route_local_output_closeout_gates.py",
    "/docker/fleet/tests/test_verify_next90_m143_fleet_route_local_output_closeout_gates.py",
    "/docker/fleet/.codex-studio/published/NEXT90_M143_FLEET_ROUTE_LOCAL_OUTPUT_CLOSEOUT_GATES.generated.json",
    "/docker/fleet/.codex-studio/published/NEXT90_M143_FLEET_ROUTE_LOCAL_OUTPUT_CLOSEOUT_GATES.generated.md",
    "/docker/fleet/feedback/2026-05-05-next90-m143-fleet-route-local-output-closeout.md",
]
REGISTRY_EVIDENCE = [
    "/docker/fleet/scripts/materialize_next90_m143_fleet_route_local_output_closeout_gates.py and /docker/fleet/scripts/verify_next90_m143_fleet_route_local_output_closeout_gates.py now fail closed when milestone 143 families rely on broad family prose, missing outputs, or reopened canonical closeout metadata instead of route-local output receipts.",
    "/docker/fleet/tests/test_materialize_next90_m143_fleet_route_local_output_closeout_gates.py and /docker/fleet/tests/test_verify_next90_m143_fleet_route_local_output_closeout_gates.py now cover route-local output evidence requirements plus canonical closeout metadata so stale or reopened rows break the gate.",
    "/docker/fleet/.codex-studio/published/NEXT90_M143_FLEET_ROUTE_LOCAL_OUTPUT_CLOSEOUT_GATES.generated.json and /docker/fleet/.codex-studio/published/NEXT90_M143_FLEET_ROUTE_LOCAL_OUTPUT_CLOSEOUT_GATES.generated.md record the current pass state for print/export/exchange and SR6 supplement/house-rule families against route-local receipts and output proof surfaces.",
    "python3 scripts/materialize_next90_m143_fleet_route_local_output_closeout_gates.py, python3 scripts/verify_next90_m143_fleet_route_local_output_closeout_gates.py --json, and python3 -m unittest tests.test_materialize_next90_m143_fleet_route_local_output_closeout_gates tests.test_verify_next90_m143_fleet_route_local_output_closeout_gates all exit 0.",
]

DEFAULT_OUTPUT = PUBLISHED / "NEXT90_M143_FLEET_ROUTE_LOCAL_OUTPUT_CLOSEOUT_GATES.generated.json"
DEFAULT_MARKDOWN = PUBLISHED / "NEXT90_M143_FLEET_ROUTE_LOCAL_OUTPUT_CLOSEOUT_GATES.generated.md"

SUCCESSOR_REGISTRY = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
FLEET_QUEUE_STAGING = PUBLISHED / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
DESIGN_QUEUE_STAGING = PRODUCT_MIRROR / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
NEXT90_GUIDE = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_GUIDE.md"
WORKFLOW_PACK = ROOT / "docs" / "chummer5a-oracle" / "veteran_workflow_packs.yaml"
PARITY_AUDIT = PRESENTATION_PUBLISHED / "CHUMMER5A_UI_ELEMENT_PARITY_AUDIT.generated.json"
SCREENSHOT_REVIEW_GATE = PRESENTATION_PUBLISHED / "CHUMMER5A_SCREENSHOT_REVIEW_GATE.generated.json"
DESKTOP_VISUAL_FAMILIARITY_GATE = PRESENTATION_PUBLISHED / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
SECTION_HOST_RULESET_PARITY = PRESENTATION_PUBLISHED / "SECTION_HOST_RULESET_PARITY.generated.json"
GENERATED_DIALOG_PARITY = PRESENTATION_PUBLISHED / "GENERATED_DIALOG_ELEMENT_PARITY.generated.json"
M114_RULE_STUDIO = PRESENTATION_PUBLISHED / "NEXT90_M114_UI_RULE_STUDIO.generated.json"
CORE_M143_RECEIPTS_DOC = CORE_DOCS / "NEXT90_M143_EXPORT_PRINT_SUPPLEMENT_RULE_ENVIRONMENT_RECEIPTS.md"

GUIDE_MARKERS = {
    "wave_22p": "## Wave 22P - close human-tested parity proof and desktop executable trust before successor breadth",
    "milestone_143": "### 143. Direct parity proof for print/export/exchange and SR6 supplements or house-rule workflows",
    "exit_contract": "Exit: print/export/exchange plus SR6 supplement/house-rule families all flip to direct `yes/yes` parity with current screenshot/runtime proof and receipt-backed outputs.",
}

MAX_PROOF_AGE_DAYS = 45

TARGET_FAMILIES: Dict[str, Dict[str, Any]] = {
    "family:sheet_export_print_viewer_and_exchange": {
        "label": "Sheet export, print viewer, and exchange",
        "compare_artifacts": ["menu:open_for_printing", "menu:open_for_export", "menu:file_print_multiple"],
        "required_row_direct_evidence_suffixes": [
            "SECTION_HOST_RULESET_PARITY.generated.json",
            "GENERATED_DIALOG_ELEMENT_PARITY.generated.json",
            "NEXT90_M143_EXPORT_PRINT_SUPPLEMENT_RULE_ENVIRONMENT_RECEIPTS.md",
            "CHUMMER5A_SCREENSHOT_REVIEW_GATE.generated.json",
        ],
        "required_global_receipt_groups": [
            {
                "route_id": "menu:open_for_printing",
                "artifact_key": "section_host_ruleset_parity",
                "tokens": ["open_for_printing"],
            },
            {
                "route_id": "menu:open_for_export",
                "artifact_key": "section_host_ruleset_parity",
                "tokens": ["open_for_export"],
            },
            {
                "route_id": "menu:file_print_multiple",
                "artifact_key": "generated_dialog_parity",
                "tokens": ["print_multiple"],
            },
            {
                "route_id": "receipt:workspace_exchange",
                "artifact_key": "core_m143_receipts_doc",
                "tokens": [
                    "WorkspaceExchangeDeterministicReceipt",
                    "family:sheet_export_print_viewer_and_exchange",
                ],
            },
            {
                "route_id": "screenshot:print_export_exchange",
                "artifact_key": "screenshot_review_gate",
                "tokens": [
                    "print_export_exchange",
                    "open_for_printing_menu_route",
                    "open_for_export_menu_route",
                    "print_multiple_menu_route",
                ],
            },
        ],
    },
    "family:sr6_supplements_designers_and_house_rules": {
        "label": "SR6 supplements, designers, and house rules",
        "compare_artifacts": ["workflow:sr6_supplements", "workflow:house_rules"],
        "required_row_direct_evidence_suffixes": [
            "NEXT90_M114_UI_RULE_STUDIO.generated.json",
            "NEXT90_M143_EXPORT_PRINT_SUPPLEMENT_RULE_ENVIRONMENT_RECEIPTS.md",
            "CHUMMER5A_SCREENSHOT_REVIEW_GATE.generated.json",
        ],
        "required_global_receipt_groups": [
            {
                "route_id": "workflow:sr6_supplements",
                "artifact_key": "core_m143_receipts_doc",
                "tokens": [
                    "Sr6SuccessorLaneDeterministicReceipt",
                    "family:sr6_supplements_designers_and_house_rules",
                    "supplement",
                ],
            },
            {
                "route_id": "workflow:house_rules",
                "artifact_key": "core_m143_receipts_doc",
                "tokens": [
                    "Sr6SuccessorLaneDeterministicReceipt",
                    "family:sr6_supplements_designers_and_house_rules",
                    "house-rule",
                ],
            },
            {
                "route_id": "surface:rule_environment_studio",
                "artifact_key": "m114_rule_studio",
                "tokens": ["rule_environment_studio"],
            },
            {
                "route_id": "screenshot:sr6_supplements_and_house_rules",
                "artifact_key": "screenshot_review_gate",
                "tokens": [
                    "sr6_rule_environment",
                    "sr6_supplements",
                    "house_rules",
                ],
            },
        ],
    },
}

ROUTE_SPECIFIC_PACKS: Dict[str, Dict[str, Any]] = {
    "sheet_export_print_viewer_and_exchange": {
        "compare_artifacts": ["menu:open_for_printing", "menu:open_for_export", "menu:file_print_multiple"],
        "route_proofs": {
            "menu:open_for_printing": {
                "proof_receipt_suffixes": ["SECTION_HOST_RULESET_PARITY.generated.json"],
                "required_tokens": ["open_for_printing"],
            },
            "menu:open_for_export": {
                "proof_receipt_suffixes": ["SECTION_HOST_RULESET_PARITY.generated.json"],
                "required_tokens": ["open_for_export"],
            },
            "menu:file_print_multiple": {
                "proof_receipt_suffixes": ["GENERATED_DIALOG_ELEMENT_PARITY.generated.json"],
                "required_tokens": ["print_multiple"],
            },
        },
        "artifact_proofs": {
            "screenshot_receipt_suffixes": ["CHUMMER5A_SCREENSHOT_REVIEW_GATE.generated.json"],
            "required_screenshot_markers": [
                "print_export_exchange",
                "open_for_printing_menu_route",
                "open_for_export_menu_route",
                "print_multiple_menu_route",
            ],
            "output_receipt_suffixes": ["NEXT90_M143_EXPORT_PRINT_SUPPLEMENT_RULE_ENVIRONMENT_RECEIPTS.md"],
            "required_output_tokens": [
                "WorkspaceExchangeDeterministicReceipt",
                "family:sheet_export_print_viewer_and_exchange",
            ],
        },
    },
    "sr6_supplements_designers_and_house_rules": {
        "compare_artifacts": ["workflow:sr6_supplements", "workflow:house_rules"],
        "route_proofs": {
            "workflow:sr6_supplements": {
                "proof_receipt_suffixes": ["NEXT90_M143_EXPORT_PRINT_SUPPLEMENT_RULE_ENVIRONMENT_RECEIPTS.md"],
                "required_tokens": [
                    "Sr6SuccessorLaneDeterministicReceipt",
                    "family:sr6_supplements_designers_and_house_rules",
                    "supplement",
                ],
            },
            "workflow:house_rules": {
                "proof_receipt_suffixes": ["NEXT90_M143_EXPORT_PRINT_SUPPLEMENT_RULE_ENVIRONMENT_RECEIPTS.md"],
                "required_tokens": [
                    "Sr6SuccessorLaneDeterministicReceipt",
                    "family:sr6_supplements_designers_and_house_rules",
                    "house-rule",
                ],
            },
            "surface:rule_environment_studio": {
                "proof_receipt_suffixes": ["NEXT90_M114_UI_RULE_STUDIO.generated.json"],
                "required_tokens": ["rule_environment_studio"],
            },
        },
        "artifact_proofs": {
            "screenshot_receipt_suffixes": ["CHUMMER5A_SCREENSHOT_REVIEW_GATE.generated.json"],
            "required_screenshot_markers": ["sr6_rule_environment", "sr6_supplements", "house_rules"],
            "output_receipt_suffixes": [],
            "required_output_tokens": [],
        },
    },
}


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize the Fleet M143 route-local output closeout gate packet.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--markdown-output", default=str(DEFAULT_MARKDOWN))
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--fleet-queue-staging", default=str(FLEET_QUEUE_STAGING))
    parser.add_argument("--design-queue-staging", default=str(DESIGN_QUEUE_STAGING))
    parser.add_argument("--next90-guide", default=str(NEXT90_GUIDE))
    parser.add_argument("--workflow-pack", default=str(WORKFLOW_PACK))
    parser.add_argument("--parity-audit", default=str(PARITY_AUDIT))
    parser.add_argument("--screenshot-review-gate", default=str(SCREENSHOT_REVIEW_GATE))
    parser.add_argument("--desktop-visual-familiarity-gate", default=str(DESKTOP_VISUAL_FAMILIARITY_GATE))
    parser.add_argument("--section-host-ruleset-parity", default=str(SECTION_HOST_RULESET_PARITY))
    parser.add_argument("--generated-dialog-parity", default=str(GENERATED_DIALOG_PARITY))
    parser.add_argument("--m114-rule-studio", default=str(M114_RULE_STUDIO))
    parser.add_argument("--core-m143-receipts-doc", default=str(CORE_M143_RECEIPTS_DOC))
    return parser.parse_args(argv)


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_list(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []
    return [_normalize_text(value) for value in values if _normalize_text(value)]


def _load_yaml(path: Path) -> Dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        payload = yaml.safe_load(raw) or {}
    except yaml.YAMLError:
        marker = "\nitems:\n"
        if marker not in raw:
            return {}
        try:
            payload = yaml.safe_load("items:\n" + raw.split(marker, 1)[1]) or {}
        except yaml.YAMLError:
            return {}
    return payload if isinstance(payload, dict) else {}


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve())
    except OSError:
        return str(path)


def _parse_generated_at(path: Path, payload: Dict[str, Any]) -> tuple[str, str]:
    generated_at = _normalize_text(payload.get("generated_at") or payload.get("generatedAt"))
    if generated_at:
        return generated_at, "payload"
    try:
        fallback = dt.datetime.fromtimestamp(path.stat().st_mtime, tz=dt.timezone.utc).replace(microsecond=0).isoformat().replace(
            "+00:00", "Z"
        )
    except OSError:
        return "", ""
    return fallback, "file_mtime"


def _parse_iso_utc(value: str) -> dt.datetime | None:
    text = _normalize_text(value)
    if not text:
        return None
    try:
        return dt.datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(dt.timezone.utc)
    except ValueError:
        return None


def _age_days(value: str, *, now: dt.datetime) -> float | None:
    parsed = _parse_iso_utc(value)
    if parsed is None:
        return None
    return max((now - parsed).total_seconds() / 86400.0, 0.0)


def _source_link(path: Path, payload: Dict[str, Any]) -> Dict[str, Any]:
    generated_at, generated_at_source = _parse_generated_at(path, payload)
    return {
        "path": _display_path(path),
        "sha256": _sha256_file(path),
        "generated_at": generated_at,
        "generated_at_source": generated_at_source,
    }


def _text_source_link(path: Path) -> Dict[str, Any]:
    generated_at, generated_at_source = _parse_generated_at(path, {})
    return {
        "path": _display_path(path),
        "sha256": _sha256_file(path),
        "generated_at": generated_at,
        "generated_at_source": generated_at_source,
    }


def _write_json_file(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _find_milestone(registry: Dict[str, Any], milestone_id: int) -> Dict[str, Any]:
    for row in registry.get("milestones") or []:
        if isinstance(row, dict) and int(row.get("id") or 0) == milestone_id:
            return dict(row)
    return {}


def _find_work_task(milestone: Dict[str, Any], work_task_id: str) -> Dict[str, Any]:
    for row in milestone.get("work_tasks") or []:
        if isinstance(row, dict) and _normalize_text(row.get("id")) == work_task_id:
            return dict(row)
    return {}


def _find_queue_item(queue: Dict[str, Any], work_task_id: str) -> Dict[str, Any]:
    for row in queue.get("items") or []:
        if isinstance(row, dict) and _normalize_text(row.get("work_task_id")) == work_task_id:
            return dict(row)
    return {}


def _marker_monitor(text: str, markers: Dict[str, str], *, label: str) -> Dict[str, Any]:
    checks = {name: marker in text for name, marker in markers.items()}
    issues = [f"{label} missing required marker: {name}" for name, present in checks.items() if not present]
    return {"state": "pass" if not issues else "fail", "checks": checks, "issues": issues}


def _queue_alignment(*, work_task: Dict[str, Any], fleet_queue_item: Dict[str, Any], design_queue_item: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    warnings: List[str] = []
    if not work_task:
        issues.append("Canonical registry work task is missing.")
    if not design_queue_item:
        issues.append("Design queue row is missing.")
    if not fleet_queue_item:
        issues.append("Fleet queue mirror row is missing for work task 143.6.")
    expected = {
        "title": QUEUE_TITLE,
        "task": QUEUE_TITLE,
        "package_id": PACKAGE_ID,
        "work_task_id": WORK_TASK_ID,
        "frontier_id": FRONTIER_ID,
        "milestone_id": MILESTONE_ID,
        "wave": WAVE_ID,
        "repo": "fleet",
        "status": "complete",
        "completion_action": COMPLETION_ACTION,
        "landed_commit": LANDED_COMMIT,
        "do_not_reopen_reason": DO_NOT_REOPEN_REASON,
    }
    if work_task and _normalize_text(work_task.get("owner")) != "fleet":
        issues.append("Canonical registry work task owner drifted from fleet.")
    if work_task and _normalize_text(work_task.get("title")) != QUEUE_TITLE:
        issues.append("Canonical registry work task title drifted from the M143 Fleet closeout contract.")
    if work_task and _normalize_text(work_task.get("status")) != "complete":
        issues.append("Canonical registry work task status must be complete before M143 can close.")
    if work_task and _normalize_list(work_task.get("evidence")) != REGISTRY_EVIDENCE:
        issues.append("Canonical registry work task evidence drifted from the M143 Fleet closeout proof set.")
    for label, row in (("design", design_queue_item), ("fleet", fleet_queue_item)):
        if not row:
            continue
        for field, expected_value in expected.items():
            if _normalize_text(row.get(field)) != _normalize_text(expected_value):
                issues.append(f"{label.title()} queue {field} drifted.")
        if _normalize_list(row.get("allowed_paths")) != ALLOWED_PATHS:
            issues.append(f"{label.title()} queue allowed_paths drifted.")
        if _normalize_list(row.get("owned_surfaces")) != OWNED_SURFACES:
            issues.append(f"{label.title()} queue owned_surfaces drifted.")
        if _normalize_list(row.get("proof")) != QUEUE_PROOF:
            issues.append(f"{label.title()} queue proof drifted.")
    return {"state": "pass" if not issues else "fail", "issues": issues, "warnings": warnings}


def _workflow_pack_contract_monitor(workflow_pack: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    family_rows = {
        _normalize_text(row.get("id")): dict(row)
        for row in (workflow_pack.get("families") or [])
        if isinstance(row, dict) and _normalize_text(row.get("id"))
    }
    for family_id, spec in TARGET_FAMILIES.items():
        compact_id = family_id.split("family:", 1)[-1]
        row = family_rows.get(compact_id) or {}
        if not row:
            issues.append(f"Workflow pack is missing `{compact_id}`.")
            continue
        if _normalize_list(row.get("compare_artifacts")) != spec["compare_artifacts"]:
            issues.append(f"Workflow pack compare_artifacts drifted for `{compact_id}`.")
    route_rows = {
        _normalize_text(row.get("family_id")): dict(row)
        for row in (workflow_pack.get("route_specific_compare_packs") or [])
        if isinstance(row, dict) and _normalize_text(row.get("family_id"))
    }
    for compact_id, spec in ROUTE_SPECIFIC_PACKS.items():
        row = route_rows.get(compact_id) or {}
        if not row:
            issues.append(f"Workflow pack is missing route_specific_compare_packs entry `{compact_id}`.")
            continue
        if _normalize_list(row.get("compare_artifacts")) != spec["compare_artifacts"]:
            issues.append(f"Workflow pack route_specific_compare_packs compare_artifacts drifted for `{compact_id}`.")
        route_proofs = {
            _normalize_text(route.get("route_id")): dict(route)
            for route in (row.get("route_proofs") or [])
            if isinstance(route, dict) and _normalize_text(route.get("route_id"))
        }
        for route_id, route_spec in spec["route_proofs"].items():
            route_row = route_proofs.get(route_id) or {}
            if not route_row:
                issues.append(f"Workflow pack route_specific_compare_packs `{compact_id}` is missing route `{route_id}`.")
                continue
            proof_receipt_names = [Path(item).name for item in _normalize_list(route_row.get("proof_receipts"))]
            if proof_receipt_names != route_spec["proof_receipt_suffixes"]:
                issues.append(
                    f"Workflow pack route_specific_compare_packs `{compact_id}` proof receipts drifted for route `{route_id}`."
                )
            if _normalize_list(route_row.get("required_tokens")) != route_spec["required_tokens"]:
                issues.append(
                    f"Workflow pack route_specific_compare_packs `{compact_id}` required_tokens drifted for route `{route_id}`."
                )
        artifact_proofs = dict(row.get("artifact_proofs") or {})
        screenshot_names = [Path(item).name for item in _normalize_list(artifact_proofs.get("screenshot_receipts"))]
        if screenshot_names != spec["artifact_proofs"]["screenshot_receipt_suffixes"]:
            issues.append(f"Workflow pack route_specific_compare_packs `{compact_id}` screenshot receipts drifted.")
        if _normalize_list(artifact_proofs.get("required_screenshot_markers")) != spec["artifact_proofs"]["required_screenshot_markers"]:
            issues.append(f"Workflow pack route_specific_compare_packs `{compact_id}` screenshot markers drifted.")
        output_names = [Path(item).name for item in _normalize_list(artifact_proofs.get("output_receipts"))]
        if output_names != spec["artifact_proofs"]["output_receipt_suffixes"]:
            issues.append(f"Workflow pack route_specific_compare_packs `{compact_id}` output receipts drifted.")
        if _normalize_list(artifact_proofs.get("required_output_tokens")) != spec["artifact_proofs"]["required_output_tokens"]:
            issues.append(f"Workflow pack route_specific_compare_packs `{compact_id}` output tokens drifted.")
    return {"state": "pass" if not issues else "fail", "issues": issues}


def _proof_texts(
    *,
    screenshot_review_gate: Dict[str, Any],
    desktop_visual_familiarity_gate: Dict[str, Any],
    section_host_ruleset_parity: Dict[str, Any],
    generated_dialog_parity: Dict[str, Any],
    m114_rule_studio: Dict[str, Any],
    core_m143_receipts_doc: str,
) -> Dict[str, str]:
    return {
        "screenshot_review_gate": json.dumps(screenshot_review_gate, sort_keys=True),
        "desktop_visual_familiarity_gate": json.dumps(desktop_visual_familiarity_gate, sort_keys=True),
        "section_host_ruleset_parity": json.dumps(section_host_ruleset_parity, sort_keys=True),
        "generated_dialog_parity": json.dumps(generated_dialog_parity, sort_keys=True),
        "m114_rule_studio": json.dumps(m114_rule_studio, sort_keys=True),
        "core_m143_receipts_doc": core_m143_receipts_doc,
    }


def _proof_corpus_monitor(
    texts: Dict[str, str],
    *,
    artifact_generated_at: Dict[str, str],
    now: dt.datetime,
) -> Dict[str, Any]:
    runtime_blockers: List[str] = []
    warnings: List[str] = []
    for label, generated_at in artifact_generated_at.items():
        age_days = _age_days(generated_at, now=now)
        if age_days is None:
            warnings.append(f"{label} generated_at is missing; using filesystem freshness only.")
        elif age_days > MAX_PROOF_AGE_DAYS:
            runtime_blockers.append(
                f"{label} is stale at {age_days:.1f} days old, exceeding the {MAX_PROOF_AGE_DAYS}-day proof budget."
            )
    family_receipt_summary: Dict[str, Any] = {}
    for family_id, spec in TARGET_FAMILIES.items():
        missing_groups: List[str] = []
        satisfied_groups: List[str] = []
        for group in spec["required_global_receipt_groups"]:
            text = texts.get(group["artifact_key"], "")
            if all(token in text for token in group["tokens"]):
                satisfied_groups.append(group["route_id"])
            else:
                missing_groups.append(group["route_id"])
        family_receipt_summary[family_id] = {
            "satisfied_route_receipts": satisfied_groups,
            "missing_route_receipts": missing_groups,
        }
        if missing_groups:
            runtime_blockers.append(
                f"{family_id}: live proof corpus still lacks direct route-local receipts for "
                + ", ".join(missing_groups)
                + "."
            )
    return {
        "state": "pass",
        "issues": [],
        "warnings": warnings,
        "runtime_blockers": runtime_blockers,
        "family_receipt_summary": family_receipt_summary,
    }


def _row_lookup(parity_audit: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    rows: Dict[str, Dict[str, Any]] = {}
    for row in parity_audit.get("rows") or parity_audit.get("elements") or []:
        if isinstance(row, dict):
            row_id = _normalize_text(row.get("id") or row.get("row_key"))
            if row_id:
                rows[row_id] = dict(row)
    return rows


def _target_rows_monitor(parity_audit: Dict[str, Any]) -> Dict[str, Any]:
    runtime_blockers: List[str] = []
    warnings: List[str] = []
    row_reports: List[Dict[str, Any]] = []
    rows = _row_lookup(parity_audit)
    if not rows:
        runtime_blockers.append("Parity audit is missing or no longer publishes rows/elements.")
        return {"state": "pass", "issues": [], "warnings": warnings, "runtime_blockers": runtime_blockers, "rows": row_reports}
    broad_evidence_suffixes = {
        "veteran_workflow_packs.yaml",
        "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json",
        "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json",
    }
    for family_id, spec in TARGET_FAMILIES.items():
        row = rows.get(family_id) or {}
        row_issues: List[str] = []
        evidence = _normalize_list(row.get("evidence"))
        if not row:
            row_issues.append("row is missing from the parity audit")
        else:
            if _normalize_text(row.get("visual_parity")).lower() != "yes":
                row_issues.append("visual_parity is not `yes`")
            if _normalize_text(row.get("behavioral_parity")).lower() != "yes":
                row_issues.append("behavioral_parity is not `yes`")
            if _normalize_text(row.get("present_in_chummer5a")).lower() != "yes":
                row_issues.append("present_in_chummer5a is not `yes`")
            if _normalize_text(row.get("present_in_chummer6")).lower() != "yes":
                row_issues.append("present_in_chummer6 is not `yes`")
            if _normalize_text(row.get("removable_if_not_in_chummer5a")).lower() != "no":
                row_issues.append("removable_if_not_in_chummer5a is not `no`")
            reason = _normalize_text(row.get("reason"))
            if reason.startswith("All declared compare artifacts for this Chummer5A family are directly backed by current parity proof:"):
                row_issues.append("row still closes on broad family prose instead of route-local proof receipts")
            if not any(
                evidence_item.endswith(suffix)
                for evidence_item in evidence
                for suffix in spec["required_row_direct_evidence_suffixes"]
            ):
                row_issues.append("row evidence does not cite any direct runtime/output receipt artifacts for this family")
            if evidence and {Path(item).name for item in evidence}.issubset(broad_evidence_suffixes):
                row_issues.append("row evidence still relies only on broad family proof artifacts")
        if row_issues:
            runtime_blockers.append(f"{family_id}: " + "; ".join(row_issues))
        row_reports.append(
            {
                "id": family_id,
                "label": spec["label"],
                "compare_artifacts": list(spec["compare_artifacts"]),
                "visual_parity": _normalize_text(row.get("visual_parity")),
                "behavioral_parity": _normalize_text(row.get("behavioral_parity")),
                "present_in_chummer5a": _normalize_text(row.get("present_in_chummer5a")),
                "present_in_chummer6": _normalize_text(row.get("present_in_chummer6")),
                "removable_if_not_in_chummer5a": _normalize_text(row.get("removable_if_not_in_chummer5a")),
                "reason": _normalize_text(row.get("reason")),
                "evidence": evidence,
                "source_reason": _normalize_text(row.get("reason")),
                "source_evidence": evidence,
                "issues": row_issues,
            }
        )
    return {
        "state": "pass",
        "issues": [],
        "warnings": warnings,
        "runtime_blockers": runtime_blockers,
        "rows": row_reports,
    }


def build_payload(
    *,
    registry_path: Path,
    fleet_queue_path: Path,
    design_queue_path: Path,
    next90_guide_path: Path,
    workflow_pack_path: Path,
    parity_audit_path: Path,
    screenshot_review_gate_path: Path,
    desktop_visual_familiarity_gate_path: Path,
    section_host_ruleset_parity_path: Path,
    generated_dialog_parity_path: Path,
    m114_rule_studio_path: Path,
    core_m143_receipts_doc_path: Path,
    generated_at: str | None = None,
) -> Dict[str, Any]:
    generated_at = generated_at or _utc_now()
    now = _parse_iso_utc(generated_at) or dt.datetime.now(dt.timezone.utc)

    registry = _load_yaml(registry_path)
    fleet_queue = _load_yaml(fleet_queue_path)
    design_queue = _load_yaml(design_queue_path)
    next90_guide = _load_text(next90_guide_path)
    workflow_pack = _load_yaml(workflow_pack_path)
    parity_audit = _load_json(parity_audit_path)
    screenshot_review_gate = _load_json(screenshot_review_gate_path)
    desktop_visual_familiarity_gate = _load_json(desktop_visual_familiarity_gate_path)
    section_host_ruleset_parity = _load_json(section_host_ruleset_parity_path)
    generated_dialog_parity = _load_json(generated_dialog_parity_path)
    m114_rule_studio = _load_json(m114_rule_studio_path)
    core_m143_receipts_doc = _load_text(core_m143_receipts_doc_path)

    milestone = _find_milestone(registry, MILESTONE_ID)
    work_task = _find_work_task(milestone, WORK_TASK_ID)
    fleet_queue_item = _find_queue_item(fleet_queue, WORK_TASK_ID)
    design_queue_item = _find_queue_item(design_queue, WORK_TASK_ID)

    canonical_monitors = {
        "guide_markers": _marker_monitor(next90_guide, GUIDE_MARKERS, label="Next90 guide canon"),
        "queue_alignment": _queue_alignment(
            work_task=work_task,
            fleet_queue_item=fleet_queue_item,
            design_queue_item=design_queue_item,
        ),
        "workflow_pack_contract": _workflow_pack_contract_monitor(workflow_pack),
    }

    texts = _proof_texts(
        screenshot_review_gate=screenshot_review_gate,
        desktop_visual_familiarity_gate=desktop_visual_familiarity_gate,
        section_host_ruleset_parity=section_host_ruleset_parity,
        generated_dialog_parity=generated_dialog_parity,
        m114_rule_studio=m114_rule_studio,
        core_m143_receipts_doc=core_m143_receipts_doc,
    )
    artifact_generated_at = {}
    for key, path, payload in (
        ("screenshot_review_gate", screenshot_review_gate_path, screenshot_review_gate),
        ("desktop_visual_familiarity_gate", desktop_visual_familiarity_gate_path, desktop_visual_familiarity_gate),
        ("section_host_ruleset_parity", section_host_ruleset_parity_path, section_host_ruleset_parity),
        ("generated_dialog_parity", generated_dialog_parity_path, generated_dialog_parity),
        ("m114_rule_studio", m114_rule_studio_path, m114_rule_studio),
    ):
        generated_value, _ = _parse_generated_at(path, payload)
        artifact_generated_at[key] = generated_value
    core_receipts_generated_at, _ = _parse_generated_at(core_m143_receipts_doc_path, {})
    artifact_generated_at["core_m143_receipts_doc"] = core_receipts_generated_at

    runtime_monitors = {
        "proof_corpus": _proof_corpus_monitor(texts, artifact_generated_at=artifact_generated_at, now=now),
        "target_rows": _target_rows_monitor(parity_audit),
    }

    canonical_issues = [
        issue
        for monitor in canonical_monitors.values()
        for issue in monitor.get("issues") or []
        if _normalize_text(issue)
    ]
    warnings = [
        warning
        for monitor in list(canonical_monitors.values()) + list(runtime_monitors.values())
        for warning in monitor.get("warnings") or []
        if _normalize_text(warning)
    ]
    runtime_blockers = [
        blocker
        for monitor in runtime_monitors.values()
        for blocker in monitor.get("runtime_blockers") or []
        if _normalize_text(blocker)
    ]

    route_local_output_closeout_status = "blocked" if runtime_blockers else ("warning" if warnings else "pass")
    package_status = "pass" if not canonical_issues else "fail"
    package_closeout = {
        "ready": package_status == "pass" and not runtime_blockers,
        "status": route_local_output_closeout_status if package_status == "pass" else "blocked",
        "reasons": canonical_issues + runtime_blockers,
        "warnings": warnings,
    }

    return {
        "generated_at": generated_at,
        "contract_name": "fleet.next90_m143_route_local_output_closeout_gates",
        "package_id": PACKAGE_ID,
        "frontier_id": FRONTIER_ID,
        "milestone_id": MILESTONE_ID,
        "work_task_id": WORK_TASK_ID,
        "wave": WAVE_ID,
        "status": package_status,
        "queue_title": QUEUE_TITLE,
        "monitor_summary": {
            "route_local_output_closeout_status": route_local_output_closeout_status,
            "canonical_issue_count": len(canonical_issues),
            "runtime_blocker_count": len(runtime_blockers),
            "warning_count": len(warnings),
            "runtime_blockers": runtime_blockers,
            "warnings": warnings,
        },
        "canonical_monitors": canonical_monitors,
        "runtime_monitors": runtime_monitors,
        "package_closeout": package_closeout,
        "source_inputs": {
            "successor_registry": _text_source_link(registry_path),
            "fleet_queue_staging": _text_source_link(fleet_queue_path),
            "design_queue_staging": _text_source_link(design_queue_path),
            "next90_guide": _text_source_link(next90_guide_path),
            "workflow_pack": _text_source_link(workflow_pack_path),
            "parity_audit": _source_link(parity_audit_path, parity_audit),
            "screenshot_review_gate": _source_link(screenshot_review_gate_path, screenshot_review_gate),
            "desktop_visual_familiarity_gate": _source_link(desktop_visual_familiarity_gate_path, desktop_visual_familiarity_gate),
            "section_host_ruleset_parity": _source_link(section_host_ruleset_parity_path, section_host_ruleset_parity),
            "generated_dialog_parity": _source_link(generated_dialog_parity_path, generated_dialog_parity),
            "m114_rule_studio": _source_link(m114_rule_studio_path, m114_rule_studio),
            "core_m143_receipts_doc": _text_source_link(core_m143_receipts_doc_path),
        },
    }


def _render_markdown(payload: Dict[str, Any]) -> str:
    summary = dict(payload.get("monitor_summary") or {})
    package_closeout = dict(payload.get("package_closeout") or {})
    target_rows = [dict(row) for row in (((payload.get("runtime_monitors") or {}).get("target_rows") or {}).get("rows") or [])]
    proof_corpus = dict(((payload.get("runtime_monitors") or {}).get("proof_corpus") or {}))
    lines = [
        "# Next90 M143 Fleet Route-Local Output Closeout Gates",
        "",
        f"- status: `{payload.get('status', '')}`",
        f"- route_local_output_closeout_status: `{summary.get('route_local_output_closeout_status', '')}`",
        f"- ready: `{package_closeout.get('ready', False)}`",
        "",
        "## Runtime blockers",
    ]
    runtime_blockers = list(summary.get("runtime_blockers") or [])
    if runtime_blockers:
        for item in runtime_blockers:
            lines.append(f"- {item}")
    else:
        lines.append("- none")
    lines.extend(["", "## Warnings"])
    warnings = list(summary.get("warnings") or [])
    if warnings:
        for item in warnings:
            lines.append(f"- {item}")
    else:
        lines.append("- none")
    lines.extend(["", "## Route Packs"])
    family_summary = dict(proof_corpus.get("family_receipt_summary") or {})
    for row in target_rows:
        family_id = _normalize_text(row.get("id"))
        family_runtime = dict(family_summary.get(family_id) or {})
        lines.append(f"- `{family_id}`: {row.get('label', '')}")
        lines.append(f"  compare_artifacts={', '.join(_normalize_list(row.get('compare_artifacts')))}")
        lines.append(f"  evidence={', '.join(_normalize_list(row.get('evidence')))}")
        lines.append(
            f"  satisfied_route_receipts={', '.join(_normalize_list(family_runtime.get('satisfied_route_receipts'))) or 'none'}"
        )
        missing = _normalize_list(family_runtime.get("missing_route_receipts"))
        lines.append(f"  missing_route_receipts={', '.join(missing) if missing else 'none'}")
        row_issues = _normalize_list(row.get("issues"))
        lines.append(f"  row_issues={'; '.join(row_issues) if row_issues else 'none'}")
    return "\n".join(lines) + "\n"


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(
        registry_path=Path(args.successor_registry).resolve(),
        fleet_queue_path=Path(args.fleet_queue_staging).resolve(),
        design_queue_path=Path(args.design_queue_staging).resolve(),
        next90_guide_path=Path(args.next90_guide).resolve(),
        workflow_pack_path=Path(args.workflow_pack).resolve(),
        parity_audit_path=Path(args.parity_audit).resolve(),
        screenshot_review_gate_path=Path(args.screenshot_review_gate).resolve(),
        desktop_visual_familiarity_gate_path=Path(args.desktop_visual_familiarity_gate).resolve(),
        section_host_ruleset_parity_path=Path(args.section_host_ruleset_parity).resolve(),
        generated_dialog_parity_path=Path(args.generated_dialog_parity).resolve(),
        m114_rule_studio_path=Path(args.m114_rule_studio).resolve(),
        core_m143_receipts_doc_path=Path(args.core_m143_receipts_doc).resolve(),
    )
    output_path = Path(args.output).resolve()
    markdown_path = Path(args.markdown_output).resolve()
    _write_json_file(output_path, payload)
    _write_markdown_file(markdown_path, _render_markdown(payload))
    print(str(output_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
