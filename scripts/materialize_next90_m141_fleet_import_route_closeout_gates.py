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
PRESENTATION_DOCS = Path("/docker/chummercomplete/chummer-presentation/docs")
CORE_PUBLISHED = Path("/docker/chummercomplete/chummer-core-engine/.codex-studio/published")
CORE_DOCS = Path("/docker/chummercomplete/chummer-core-engine/docs")

PACKAGE_ID = "next90-m141-fleet-fail-closeout-when-any-of-the-five-route-or-family-rows-in-this-milest"
FRONTIER_ID = 4147587006
MILESTONE_ID = 141
WORK_TASK_ID = "141.5"
WAVE_ID = "W22P"
QUEUE_TITLE = (
    "Fail closeout when any of the five route or family rows in this milestone remain `no`, blank, stale, "
    "or unsupported by direct proof receipts."
)
OWNED_SURFACES = ["fail_closeout_when_any_of_the_five_route_or_family_rows:fleet"]
ALLOWED_PATHS = ["scripts", "tests", ".codex-studio", "feedback"]
COMPLETION_ACTION = "verify_closed_package_only"
LANDED_COMMIT = "c099200f"
DO_NOT_REOPEN_REASON = (
    "M141 fleet import-route closeout gate is complete; future shards must verify the repo-local gate scripts, "
    "generated proof artifacts, and canonical queue/registry mirrors instead of reopening the translator, XML, "
    "Hero Lab, and adjacent import-route parity closeout slice."
)
QUEUE_PROOF = [
    "/docker/fleet/scripts/materialize_next90_m141_fleet_import_route_closeout_gates.py",
    "/docker/fleet/scripts/verify_next90_m141_fleet_import_route_closeout_gates.py",
    "/docker/fleet/tests/test_materialize_next90_m141_fleet_import_route_closeout_gates.py",
    "/docker/fleet/tests/test_verify_next90_m141_fleet_import_route_closeout_gates.py",
    "/docker/fleet/.codex-studio/published/NEXT90_M141_FLEET_IMPORT_ROUTE_CLOSEOUT_GATES.generated.json",
    "/docker/fleet/.codex-studio/published/NEXT90_M141_FLEET_IMPORT_ROUTE_CLOSEOUT_GATES.generated.md",
    "/docker/fleet/feedback/2026-05-05-next90-m141-fleet-import-route-closeout.md",
]
REGISTRY_EVIDENCE = [
    "/docker/fleet/scripts/materialize_next90_m141_fleet_import_route_closeout_gates.py and /docker/fleet/scripts/verify_next90_m141_fleet_import_route_closeout_gates.py now fail closed when the milestone 141 route and family rows drift from direct proof receipts or when the canonical closeout metadata reopens.",
    "/docker/fleet/tests/test_materialize_next90_m141_fleet_import_route_closeout_gates.py and /docker/fleet/tests/test_verify_next90_m141_fleet_import_route_closeout_gates.py now cover append-style queue ingestion, direct field-shape requirements, and canonical closeout metadata so stale rows or reopened packages break the gate.",
    "/docker/fleet/.codex-studio/published/NEXT90_M141_FLEET_IMPORT_ROUTE_CLOSEOUT_GATES.generated.json and /docker/fleet/.codex-studio/published/NEXT90_M141_FLEET_IMPORT_ROUTE_CLOSEOUT_GATES.generated.md record the current pass state for translator, XML amendment, Hero Lab, and the two family rows against screenshot-backed, runtime-backed, and core deterministic import receipts.",
    "python3 scripts/materialize_next90_m141_fleet_import_route_closeout_gates.py, python3 scripts/verify_next90_m141_fleet_import_route_closeout_gates.py --json, and python3 -m unittest tests.test_materialize_next90_m141_fleet_import_route_closeout_gates tests.test_verify_next90_m141_fleet_import_route_closeout_gates all exit 0.",
]

DEFAULT_OUTPUT = PUBLISHED / "NEXT90_M141_FLEET_IMPORT_ROUTE_CLOSEOUT_GATES.generated.json"
DEFAULT_MARKDOWN = PUBLISHED / "NEXT90_M141_FLEET_IMPORT_ROUTE_CLOSEOUT_GATES.generated.md"

SUCCESSOR_REGISTRY = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
FLEET_QUEUE_STAGING = PUBLISHED / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
DESIGN_QUEUE_STAGING = PRODUCT_MIRROR / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
NEXT90_GUIDE = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_GUIDE.md"
PARITY_ACCEPTANCE_MATRIX = PRODUCT_MIRROR / "CHUMMER5A_HUMAN_PARITY_ACCEPTANCE_MATRIX.yaml"
LEGACY_CHROME_POLICY = PRESENTATION_DOCS / "CHUMMER5A_LEGACY_EQUIVALENT_CHROME_POLICY.json"
PARITY_AUDIT = PRESENTATION_PUBLISHED / "CHUMMER5A_UI_ELEMENT_PARITY_AUDIT.generated.json"
VISUAL_FAMILIARITY_GATE = PRESENTATION_PUBLISHED / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
VETERAN_TASK_TIME_GATE = PRESENTATION_PUBLISHED / "VETERAN_TASK_TIME_EVIDENCE_GATE.generated.json"
UI_RELEASE_GATE = PRESENTATION_PUBLISHED / "UI_FLAGSHIP_RELEASE_GATE.generated.json"
IMPORT_RECEIPTS_DOC = CORE_DOCS / "NEXT90_M141_IMPORT_ROUTE_RECEIPTS.md"
IMPORT_PARITY_CERTIFICATION = CORE_PUBLISHED / "IMPORT_PARITY_CERTIFICATION.generated.json"
ENGINE_PROOF_PACK = CORE_PUBLISHED / "ENGINE_PROOF_PACK.generated.json"

GUIDE_MARKERS = {
    "wave_22p": "## Wave 22P - close human-tested parity proof and desktop executable trust before successor breadth",
    "milestone_141": "### 141. Direct parity proof for translator, XML amendment, Hero Lab, and adjacent import routes",
    "exit_contract": "Exit: the translator, XML amendment editor, Hero Lab importer, custom-data/XML bridge, and adjacent import-oracle rows all flip to direct `yes/yes` parity with current screenshot-backed and runtime-backed receipts.",
}
REQUIRED_FIELD_NAMES = [
    "present_in_chummer5a",
    "present_in_chummer6",
    "visual_parity",
    "behavioral_parity",
    "removable_if_not_in_chummer5a",
    "reason",
]
REQUIRED_YES_NO_FIELDS = [
    "present_in_chummer5a",
    "present_in_chummer6",
    "visual_parity",
    "behavioral_parity",
    "removable_if_not_in_chummer5a",
]
SCREENSHOT_PROOF_SUFFIXES = (
    "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json",
    "UI_FLAGSHIP_RELEASE_GATE.generated.json",
    "VETERAN_TASK_TIME_EVIDENCE_GATE.generated.json",
)
CORE_RECEIPT_SUFFIXES = (
    "NEXT90_M141_IMPORT_ROUTE_RECEIPTS.md",
    "IMPORT_PARITY_CERTIFICATION.generated.json",
    "ENGINE_PROOF_PACK.generated.json",
)
MAX_PROOF_AGE_DAYS = 45
TARGET_ROWS: Dict[str, Dict[str, Any]] = {
    "source:translator_route": {
        "label": "Translator route",
        "required_screenshot_tokens": ["38-translator-dialog-light.png"],
        "required_runtime_tokens": [
            "translator_xml_custom_data",
            "ExecuteCommandAsync_translator_opens_dialog_with_master_index_lane_posture",
        ],
        "runtime_proof_suffixes": ["VETERAN_TASK_TIME_EVIDENCE_GATE.generated.json", "UI_FLAGSHIP_RELEASE_GATE.generated.json"],
        "required_core_receipt_tokens": ["translatorDeterministicReceipt"],
    },
    "source:xml_amendment_editor_route": {
        "label": "XML amendment editor route",
        "required_screenshot_tokens": ["39-xml-editor-dialog-light.png"],
        "required_runtime_tokens": [
            "translator_xml_custom_data",
            "ExecuteCommandAsync_xml_editor_opens_dialog_with_xml_bridge_posture",
        ],
        "runtime_proof_suffixes": ["VETERAN_TASK_TIME_EVIDENCE_GATE.generated.json", "UI_FLAGSHIP_RELEASE_GATE.generated.json"],
        "required_core_receipt_tokens": ["customDataXmlBridgeDeterministicReceipt"],
    },
    "source:hero_lab_importer_route": {
        "label": "Hero Lab importer route",
        "required_screenshot_tokens": ["40-hero-lab-importer-dialog-light.png"],
        "required_runtime_tokens": [
            "hero_lab_import_oracle",
            "ExecuteCommandAsync_hero_lab_importer_opens_dialog_with_import_oracle_lane_posture",
        ],
        "runtime_proof_suffixes": ["VETERAN_TASK_TIME_EVIDENCE_GATE.generated.json"],
        "required_core_receipt_tokens": ["importOracleDeterministicReceipt"],
    },
    "family:custom_data_xml_and_translator_bridge": {
        "label": "Custom data/XML and translator bridge family",
        "required_screenshot_tokens": ["38-translator-dialog-light.png", "39-xml-editor-dialog-light.png"],
        "required_runtime_tokens": ["translator_xml_custom_data"],
        "runtime_proof_suffixes": ["VETERAN_TASK_TIME_EVIDENCE_GATE.generated.json", "UI_FLAGSHIP_RELEASE_GATE.generated.json"],
        "required_core_receipt_tokens": [
            "customDataXmlBridgeDeterministicReceipt",
            "translatorDeterministicReceipt",
            "family:custom_data_xml_and_translator_bridge",
        ],
    },
    "family:legacy_and_adjacent_import_oracles": {
        "label": "Legacy and adjacent import-oracle family",
        "required_screenshot_tokens": ["40-hero-lab-importer-dialog-light.png"],
        "required_runtime_tokens": ["hero_lab_import_oracle"],
        "runtime_proof_suffixes": ["VETERAN_TASK_TIME_EVIDENCE_GATE.generated.json"],
        "required_core_receipt_tokens": [
            "importOracleDeterministicReceipt",
            "family:legacy_and_adjacent_import_oracles",
        ],
    },
}


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize the Fleet M141 import-route closeout gate packet.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--markdown-output", default=str(DEFAULT_MARKDOWN))
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
    if isinstance(payload, list):
        return {"items": payload}
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
        issues.append("Fleet queue mirror row is missing for work task 141.5.")
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
        issues.append("Canonical registry work task title drifted from the M141 Fleet closeout contract.")
    if work_task and _normalize_text(work_task.get("status")) != "complete":
        issues.append("Canonical registry work task status must be complete before M141 can close.")
    if work_task and _normalize_list(work_task.get("evidence")) != REGISTRY_EVIDENCE:
        issues.append("Canonical registry work task evidence drifted from the M141 Fleet closeout proof set.")
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


def _field_contract_monitor(matrix_payload: Dict[str, Any], policy_payload: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    matrix_fields = _normalize_list(matrix_payload.get("audit_required_fields"))
    policy_fields = _normalize_list(policy_payload.get("auditRequiredFields"))
    for field in REQUIRED_FIELD_NAMES:
        if field not in matrix_fields:
            issues.append(f"Parity acceptance matrix no longer requires `{field}`.")
        if field not in policy_fields:
            issues.append(f"Legacy equivalent chrome policy no longer requires `{field}`.")
    field_rules = dict(matrix_payload.get("field_rules") or {})
    allowed_yes_no = set(_normalize_list(policy_payload.get("allowedYesNoFields")))
    for field in REQUIRED_YES_NO_FIELDS:
        values = []
        for value in dict(field_rules.get(field) or {}).get("allowed_values") or []:
            if value is True:
                values.append("yes")
            elif value is False:
                values.append("no")
            else:
                normalized = _normalize_text(value).lower()
                if normalized:
                    values.append(normalized)
        if sorted(values) != ["no", "yes"]:
            issues.append(f"Parity acceptance matrix allowed values drifted for `{field}`.")
        if field not in allowed_yes_no:
            issues.append(f"Legacy equivalent chrome policy no longer treats `{field}` as a yes/no field.")
    return {
        "state": "pass" if not issues else "fail",
        "issues": issues,
        "matrix_required_fields": matrix_fields,
        "policy_required_fields": policy_fields,
    }


def _core_import_proof_monitor(
    import_receipts_doc: str,
    import_parity_certification: Dict[str, Any],
    engine_proof_pack: Dict[str, Any],
    *,
    import_parity_certification_generated_at: str,
    engine_proof_pack_generated_at: str,
    now: dt.datetime,
) -> Dict[str, Any]:
    runtime_blockers: List[str] = []
    warnings: List[str] = []
    missing_doc_tokens = []
    for token in (
        "customDataXmlBridgeDeterministicReceipt",
        "translatorDeterministicReceipt",
        "importOracleDeterministicReceipt",
        "source:translator_route",
        "family:custom_data_xml_and_translator_bridge",
        "family:legacy_and_adjacent_import_oracles",
    ):
        if token not in import_receipts_doc:
            missing_doc_tokens.append(token)
    if missing_doc_tokens:
        runtime_blockers.append(
            "Import-route receipt contract no longer names the required deterministic receipt objects or parity targets: "
            + ", ".join(missing_doc_tokens)
            + "."
        )
    if _normalize_text(import_parity_certification.get("status")).lower() not in {"pass", "passed"}:
        runtime_blockers.append("Import parity certification is missing or no longer passing.")
    coverage = dict(import_parity_certification.get("coverage") or {})
    if int(coverage.get("sources_covered") or 0) < int(coverage.get("sources_expected") or 0):
        runtime_blockers.append("Import parity certification no longer covers every declared oracle source.")
    if _normalize_text(engine_proof_pack.get("status")).lower() not in {"pass", "passed"}:
        runtime_blockers.append("Engine proof pack is missing or no longer passing.")
    engine_required_suites = set(_normalize_list(engine_proof_pack.get("required_oracle_suite_ids")))
    engine_suite_ids = {
        _normalize_text(row.get("id"))
        for row in (engine_proof_pack.get("oracle_suites") or [])
        if isinstance(row, dict) and _normalize_text(row.get("id"))
    }
    if "amend_package" not in engine_required_suites and "amend_package" not in engine_suite_ids:
        runtime_blockers.append("Engine proof pack no longer publishes the amend_package oracle suite.")
    for label, generated_at in (
        ("Import parity certification", import_parity_certification_generated_at),
        ("Engine proof pack", engine_proof_pack_generated_at),
    ):
        age_days = _age_days(generated_at, now=now)
        if age_days is None:
            warnings.append(f"{label} generated_at is missing; using filesystem freshness only.")
        elif age_days > MAX_PROOF_AGE_DAYS:
            runtime_blockers.append(
                f"{label} is stale at {age_days:.1f} days old, exceeding the {MAX_PROOF_AGE_DAYS}-day import-proof budget."
            )
    return {
        "state": "pass",
        "issues": [],
        "warnings": warnings,
        "runtime_blockers": runtime_blockers,
        "coverage": coverage,
    }


def _ui_route_proof_monitor(
    visual_familiarity_gate: Dict[str, Any],
    veteran_task_time_gate: Dict[str, Any],
    ui_release_gate: Dict[str, Any],
    *,
    visual_generated_at: str,
    veteran_generated_at: str,
    ui_release_generated_at: str,
    now: dt.datetime,
) -> Dict[str, Any]:
    runtime_blockers: List[str] = []
    warnings: List[str] = []
    visual_text = json.dumps(visual_familiarity_gate, sort_keys=True)
    veteran_text = json.dumps(veteran_task_time_gate, sort_keys=True)
    ui_release_text = json.dumps(ui_release_gate, sort_keys=True)
    for token in ("38-translator-dialog-light.png", "39-xml-editor-dialog-light.png", "40-hero-lab-importer-dialog-light.png"):
        if token not in visual_text and token not in veteran_text and token not in ui_release_text:
            runtime_blockers.append(f"Screenshot proof no longer contains `{token}`.")
    for token in (
        "translator_xml_custom_data",
        "hero_lab_import_oracle",
        "ExecuteCommandAsync_translator_opens_dialog_with_master_index_lane_posture",
        "ExecuteCommandAsync_xml_editor_opens_dialog_with_xml_bridge_posture",
        "ExecuteCommandAsync_hero_lab_importer_opens_dialog_with_import_oracle_lane_posture",
    ):
        if token not in veteran_text and token not in ui_release_text:
            runtime_blockers.append(f"Runtime route proof no longer contains `{token}`.")
    for label, generated_at in (
        ("Desktop visual familiarity gate", visual_generated_at),
        ("Veteran task-time evidence gate", veteran_generated_at),
        ("UI flagship release gate", ui_release_generated_at),
    ):
        age_days = _age_days(generated_at, now=now)
        if age_days is None:
            warnings.append(f"{label} generated_at is missing; using filesystem freshness only.")
        elif age_days > MAX_PROOF_AGE_DAYS:
            runtime_blockers.append(
                f"{label} is stale at {age_days:.1f} days old, exceeding the {MAX_PROOF_AGE_DAYS}-day UI proof budget."
            )
    return {
        "state": "pass",
        "issues": [],
        "warnings": warnings,
        "runtime_blockers": runtime_blockers,
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
    row_reports: List[Dict[str, Any]] = []
    rows = _row_lookup(parity_audit)
    if not rows:
        runtime_blockers.append("Parity audit is missing or no longer publishes rows/elements.")
        return {
            "state": "pass",
            "issues": [],
            "runtime_blockers": runtime_blockers,
            "rows": row_reports,
        }
    for row_id, spec in TARGET_ROWS.items():
        row = rows.get(row_id) or {}
        row_issues: List[str] = []
        row_warnings: List[str] = []
        evidence = _normalize_list(row.get("evidence"))
        if not row:
            row_issues.append("row is missing from the parity audit")
        else:
            if _normalize_text(row.get("present_in_chummer5a")).lower() != "yes":
                row_issues.append("present_in_chummer5a is not `yes`")
            if _normalize_text(row.get("present_in_chummer6")).lower() != "yes":
                row_issues.append("present_in_chummer6 is missing or not `yes`")
            if _normalize_text(row.get("visual_parity")).lower() != "yes":
                row_issues.append("visual_parity is missing or not `yes`")
            if _normalize_text(row.get("behavioral_parity")).lower() != "yes":
                row_issues.append("behavioral_parity is missing or not `yes`")
            if _normalize_text(row.get("removable_if_not_in_chummer5a")).lower() != "no":
                if _normalize_text(row.get("removable_without_workflow_degradation")).lower() == "no":
                    row_issues.append("row still uses `removable_without_workflow_degradation` instead of the required `removable_if_not_in_chummer5a = no` field")
                else:
                    row_issues.append("removable_if_not_in_chummer5a is missing or not `no`")
            if not _normalize_text(row.get("reason")):
                row_issues.append("reason is blank")
            if not any(token in json.dumps(row, sort_keys=True) for token in spec["required_screenshot_tokens"]):
                row_warnings.append("row body does not surface the expected screenshot token directly")
            if not any(evidence_item.endswith(suffix) for evidence_item in evidence for suffix in SCREENSHOT_PROOF_SUFFIXES):
                row_issues.append("evidence does not cite a screenshot-backed proof artifact")
            if not any(
                evidence_item.endswith(suffix)
                for evidence_item in evidence
                for suffix in spec["runtime_proof_suffixes"]
            ):
                row_issues.append("evidence does not cite a direct runtime proof artifact")
            if not any(evidence_item.endswith(suffix) for evidence_item in evidence for suffix in CORE_RECEIPT_SUFFIXES):
                row_issues.append("evidence does not cite a direct core import-receipt artifact")
        if row_issues:
            runtime_blockers.append(f"{row_id}: " + "; ".join(row_issues))
        row_reports.append(
            {
                "id": row_id,
                "label": spec["label"],
                "visual_parity": _normalize_text(row.get("visual_parity")),
                "behavioral_parity": _normalize_text(row.get("behavioral_parity")),
                "present_in_chummer5a": _normalize_text(row.get("present_in_chummer5a")),
                "present_in_chummer6": _normalize_text(row.get("present_in_chummer6")),
                "removable_if_not_in_chummer5a": _normalize_text(row.get("removable_if_not_in_chummer5a")),
                "removable_without_workflow_degradation": _normalize_text(row.get("removable_without_workflow_degradation")),
                "reason": _normalize_text(row.get("reason")),
                "evidence": evidence,
                "issues": row_issues,
                "warnings": row_warnings,
            }
        )
    return {
        "state": "pass",
        "issues": [],
        "runtime_blockers": runtime_blockers,
        "rows": row_reports,
    }


def build_payload(
    *,
    registry_path: Path,
    fleet_queue_path: Path,
    design_queue_path: Path,
    next90_guide_path: Path,
    parity_acceptance_matrix_path: Path,
    legacy_chrome_policy_path: Path,
    parity_audit_path: Path,
    visual_familiarity_gate_path: Path,
    veteran_task_time_gate_path: Path,
    ui_release_gate_path: Path,
    import_receipts_doc_path: Path,
    import_parity_certification_path: Path,
    engine_proof_pack_path: Path,
    generated_at: str | None = None,
) -> Dict[str, Any]:
    generated_at = generated_at or _utc_now()
    now = _parse_iso_utc(generated_at) or dt.datetime.now(dt.timezone.utc)

    registry = _load_yaml(registry_path)
    fleet_queue = _load_yaml(fleet_queue_path)
    design_queue = _load_yaml(design_queue_path)
    next90_guide = _load_text(next90_guide_path)
    parity_acceptance_matrix = _load_yaml(parity_acceptance_matrix_path)
    legacy_chrome_policy = _load_json(legacy_chrome_policy_path)
    parity_audit = _load_json(parity_audit_path)
    visual_familiarity_gate = _load_json(visual_familiarity_gate_path)
    veteran_task_time_gate = _load_json(veteran_task_time_gate_path)
    ui_release_gate = _load_json(ui_release_gate_path)
    import_receipts_doc = _load_text(import_receipts_doc_path)
    import_parity_certification = _load_json(import_parity_certification_path)
    engine_proof_pack = _load_json(engine_proof_pack_path)

    milestone = _find_milestone(registry, MILESTONE_ID)
    work_task = _find_work_task(milestone, WORK_TASK_ID)
    fleet_queue_item = _find_queue_item(fleet_queue, WORK_TASK_ID)
    design_queue_item = _find_queue_item(design_queue, WORK_TASK_ID)

    queue_monitor = _queue_alignment(
        work_task=work_task,
        fleet_queue_item=fleet_queue_item,
        design_queue_item=design_queue_item,
    )
    guide_monitor = _marker_monitor(next90_guide, GUIDE_MARKERS, label="Next90 guide canon")
    field_contract_monitor = _field_contract_monitor(parity_acceptance_matrix, legacy_chrome_policy)

    import_cert_generated_at, _ = _parse_generated_at(import_parity_certification_path, import_parity_certification)
    engine_generated_at, _ = _parse_generated_at(engine_proof_pack_path, engine_proof_pack)
    visual_generated_at, _ = _parse_generated_at(visual_familiarity_gate_path, visual_familiarity_gate)
    veteran_generated_at, _ = _parse_generated_at(veteran_task_time_gate_path, veteran_task_time_gate)
    ui_release_generated_at, _ = _parse_generated_at(ui_release_gate_path, ui_release_gate)

    core_import_proof_monitor = _core_import_proof_monitor(
        import_receipts_doc,
        import_parity_certification,
        engine_proof_pack,
        import_parity_certification_generated_at=import_cert_generated_at,
        engine_proof_pack_generated_at=engine_generated_at,
        now=now,
    )
    ui_route_proof_monitor = _ui_route_proof_monitor(
        visual_familiarity_gate,
        veteran_task_time_gate,
        ui_release_gate,
        visual_generated_at=visual_generated_at,
        veteran_generated_at=veteran_generated_at,
        ui_release_generated_at=ui_release_generated_at,
        now=now,
    )
    target_rows_monitor = _target_rows_monitor(parity_audit)

    canonical_monitors = {
        "queue_alignment": queue_monitor,
        "guide_markers": guide_monitor,
        "field_contract": field_contract_monitor,
    }
    runtime_monitors = {
        "core_import_receipts": core_import_proof_monitor,
        "ui_route_proofs": ui_route_proof_monitor,
        "target_rows": target_rows_monitor,
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

    if runtime_blockers:
        import_route_closeout_status = "blocked"
    elif warnings:
        import_route_closeout_status = "warning"
    else:
        import_route_closeout_status = "pass"

    package_status = "pass" if not canonical_issues else "fail"
    package_closeout_ready = package_status == "pass" and not runtime_blockers
    package_closeout = {
        "ready": package_closeout_ready,
        "status": import_route_closeout_status if package_status == "pass" else "blocked",
        "reasons": canonical_issues + runtime_blockers,
        "warnings": warnings,
    }

    payload = {
        "generated_at": generated_at,
        "contract_name": "fleet.next90_m141_import_route_closeout_gates",
        "package_id": PACKAGE_ID,
        "frontier_id": FRONTIER_ID,
        "milestone_id": MILESTONE_ID,
        "work_task_id": WORK_TASK_ID,
        "wave": WAVE_ID,
        "status": package_status,
        "queue_title": QUEUE_TITLE,
        "monitor_summary": {
            "import_route_closeout_status": import_route_closeout_status,
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
            "parity_acceptance_matrix": _text_source_link(parity_acceptance_matrix_path),
            "legacy_chrome_policy": _source_link(legacy_chrome_policy_path, legacy_chrome_policy),
            "parity_audit": _source_link(parity_audit_path, parity_audit),
            "visual_familiarity_gate": _source_link(visual_familiarity_gate_path, visual_familiarity_gate),
            "veteran_task_time_gate": _source_link(veteran_task_time_gate_path, veteran_task_time_gate),
            "ui_release_gate": _source_link(ui_release_gate_path, ui_release_gate),
            "import_receipts_doc": _text_source_link(import_receipts_doc_path),
            "import_parity_certification": _source_link(import_parity_certification_path, import_parity_certification),
            "engine_proof_pack": _source_link(engine_proof_pack_path, engine_proof_pack),
        },
    }
    return payload


def _render_markdown(payload: Dict[str, Any]) -> str:
    summary = dict(payload.get("monitor_summary") or {})
    package_closeout = dict(payload.get("package_closeout") or {})
    lines = [
        "# Next90 M141 Fleet Import Route Closeout Gates",
        "",
        f"- status: `{payload.get('status', '')}`",
        f"- import_route_closeout_status: `{summary.get('import_route_closeout_status', '')}`",
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
    return "\n".join(lines) + "\n"


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(
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
    )
    output_path = Path(args.output).resolve()
    markdown_path = Path(args.markdown_output).resolve()
    _write_json_file(output_path, payload)
    _write_markdown_file(markdown_path, _render_markdown(payload))
    print(str(output_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
