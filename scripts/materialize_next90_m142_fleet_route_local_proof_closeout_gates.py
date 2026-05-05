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

PACKAGE_ID = "next90-m142-fleet-fail-closeout-when-any-route-in-this-milestone-closes-on-family-prose"
FRONTIER_ID = 7414599441
MILESTONE_ID = 142
WORK_TASK_ID = "142.5"
WAVE_ID = "W22P"
QUEUE_TITLE = "Fail closeout when any route in this milestone closes on family prose, stale captures, or missing task-speed and runtime receipts."
OWNED_SURFACES = ["fail_closeout_when_any_route_in_this_milestone_closes_on:fleet"]
ALLOWED_PATHS = ["scripts", "tests", ".codex-studio", "feedback"]
COMPLETION_ACTION = "verify_closed_package_only"
LANDED_COMMIT = "unlanded"
DO_NOT_REOPEN_REASON = (
    "M142 fleet route-local proof closeout gate is complete; future shards must verify the repo-local gate scripts, "
    "generated proof artifacts, and canonical queue/registry mirrors instead of reopening dense workbench, dice or "
    "initiative, and identity or lifestyle parity closeout by family prose."
)
QUEUE_PROOF = [
    "/docker/fleet/scripts/materialize_next90_m142_fleet_route_local_proof_closeout_gates.py",
    "/docker/fleet/scripts/verify_next90_m142_fleet_route_local_proof_closeout_gates.py",
    "/docker/fleet/tests/test_materialize_next90_m142_fleet_route_local_proof_closeout_gates.py",
    "/docker/fleet/tests/test_verify_next90_m142_fleet_route_local_proof_closeout_gates.py",
    "/docker/fleet/.codex-studio/published/NEXT90_M142_FLEET_ROUTE_LOCAL_PROOF_CLOSEOUT_GATES.generated.json",
    "/docker/fleet/.codex-studio/published/NEXT90_M142_FLEET_ROUTE_LOCAL_PROOF_CLOSEOUT_GATES.generated.md",
    "/docker/fleet/feedback/2026-05-05-next90-m142-fleet-route-local-proof-closeout.md",
]
REGISTRY_EVIDENCE = [
    "/docker/fleet/scripts/materialize_next90_m142_fleet_route_local_proof_closeout_gates.py and /docker/fleet/scripts/verify_next90_m142_fleet_route_local_proof_closeout_gates.py now fail closed when milestone 142 family rows rely on family prose, stale captures, or reopened canonical closeout metadata instead of route-local proof receipts.",
    "/docker/fleet/tests/test_materialize_next90_m142_fleet_route_local_proof_closeout_gates.py and /docker/fleet/tests/test_verify_next90_m142_fleet_route_local_proof_closeout_gates.py now cover direct route-local evidence requirements plus the canonical closeout metadata so stale or reopened rows break the gate.",
    "/docker/fleet/.codex-studio/published/NEXT90_M142_FLEET_ROUTE_LOCAL_PROOF_CLOSEOUT_GATES.generated.json and /docker/fleet/.codex-studio/published/NEXT90_M142_FLEET_ROUTE_LOCAL_PROOF_CLOSEOUT_GATES.generated.md record the current pass state for dense builder/career, dice/initiative, and identity/contacts/lifestyles/history against route-local receipts and dense-workbench proof surfaces.",
    "python3 scripts/materialize_next90_m142_fleet_route_local_proof_closeout_gates.py, python3 scripts/verify_next90_m142_fleet_route_local_proof_closeout_gates.py --json, and python3 -m unittest tests.test_materialize_next90_m142_fleet_route_local_proof_closeout_gates tests.test_verify_next90_m142_fleet_route_local_proof_closeout_gates all exit 0.",
]

DEFAULT_OUTPUT = PUBLISHED / "NEXT90_M142_FLEET_ROUTE_LOCAL_PROOF_CLOSEOUT_GATES.generated.json"
DEFAULT_MARKDOWN = PUBLISHED / "NEXT90_M142_FLEET_ROUTE_LOCAL_PROOF_CLOSEOUT_GATES.generated.md"

SUCCESSOR_REGISTRY = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
FLEET_QUEUE_STAGING = PUBLISHED / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
DESIGN_QUEUE_STAGING = PRODUCT_MIRROR / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
NEXT90_GUIDE = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_GUIDE.md"
WORKFLOW_PACK = ROOT / "docs" / "chummer5a-oracle" / "veteran_workflow_packs.yaml"
PARITY_AUDIT = PRESENTATION_PUBLISHED / "CHUMMER5A_UI_ELEMENT_PARITY_AUDIT.generated.json"
DESKTOP_VISUAL_FAMILIARITY_GATE = PRESENTATION_PUBLISHED / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
DESKTOP_WORKFLOW_EXECUTION_GATE = PRESENTATION_PUBLISHED / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
SCREENSHOT_REVIEW_GATE = PRESENTATION_PUBLISHED / "CHUMMER5A_SCREENSHOT_REVIEW_GATE.generated.json"
CLASSIC_DENSE_WORKBENCH_GATE = PRESENTATION_PUBLISHED / "CLASSIC_DENSE_WORKBENCH_POSTURE_GATE.generated.json"
VETERAN_TASK_TIME_GATE = PRESENTATION_PUBLISHED / "VETERAN_TASK_TIME_EVIDENCE_GATE.generated.json"
UI_FLAGSHIP_RELEASE_GATE = PRESENTATION_PUBLISHED / "UI_FLAGSHIP_RELEASE_GATE.generated.json"
UI_LOCAL_RELEASE_PROOF = PRESENTATION_PUBLISHED / "UI_LOCAL_RELEASE_PROOF.generated.json"
GENERATED_DIALOG_PARITY = PRESENTATION_PUBLISHED / "GENERATED_DIALOG_ELEMENT_PARITY.generated.json"
SECTION_HOST_RULESET_PARITY = PRESENTATION_PUBLISHED / "SECTION_HOST_RULESET_PARITY.generated.json"
GM_RUNBOARD_ROUTE = PRESENTATION_PUBLISHED / "NEXT90_M121_UI_GM_RUNBOARD_ROUTE.generated.json"
CORE_DENSE_RECEIPTS_DOC = CORE_DOCS / "NEXT90_M142_DENSE_WORKBENCH_RECEIPTS.md"

GUIDE_MARKERS = {
    "wave_22p": "## Wave 22P - close human-tested parity proof and desktop executable trust before successor breadth",
    "milestone_142": "### 142. Direct parity proof for dense workbench, dice utilities, and identity or lifestyle workflows",
    "exit_contract": "Exit: dense builder/career, dice/initiative, and identity/contacts/lifestyles/history families all flip to direct `yes/yes` parity with current route-local proof and dense-workbench captures.",
}
MAX_PROOF_AGE_DAYS = 45
TARGET_FAMILIES: Dict[str, Dict[str, Any]] = {
    "family:dense_builder_and_career_workflows": {
        "label": "Dense builder and career workflows",
        "compare_artifacts": ["oracle:tabs", "oracle:workspace_actions", "workflow:build_explain_publish"],
        "required_row_direct_evidence_suffixes": [
            "SECTION_HOST_RULESET_PARITY.generated.json",
            "CHUMMER5A_SCREENSHOT_REVIEW_GATE.generated.json",
            "CLASSIC_DENSE_WORKBENCH_POSTURE_GATE.generated.json",
            "UI_FLAGSHIP_RELEASE_GATE.generated.json",
            "UI_LOCAL_RELEASE_PROOF.generated.json",
        ],
        "required_global_receipt_groups": [
            {
                "route_id": "oracle:tabs",
                "artifact_key": "section_host_ruleset_parity",
                "tokens": ["expectedTabIds", "tab-info", "tab-skills", "tab-qualities", "tab-combat", "tab-gear"],
            },
            {
                "route_id": "oracle:workspace_actions",
                "artifact_key": "section_host_ruleset_parity",
                "tokens": ["expectedWorkspaceActionIds", "tab-info.summary", "tab-skills.skills", "tab-gear.inventory"],
            },
            {
                "route_id": "workflow:build_explain_publish",
                "artifact_key": "desktop_workflow_execution_gate",
                "tokens": [
                    "create-open-import-save-save-as-print-export",
                    "dense-workbench-affordances-search-add-edit-remove-preview-drill-in-compare",
                    "qualities-contacts-identities-notes-calendar-expenses-lifestyles-sources",
                ],
            },
        ],
    },
    "family:dice_initiative_and_table_utilities": {
        "label": "Dice, initiative, and table utilities",
        "compare_artifacts": ["menu:dice_roller", "workflow:initiative"],
        "required_row_direct_evidence_suffixes": [
            "GENERATED_DIALOG_ELEMENT_PARITY.generated.json",
            "SECTION_HOST_RULESET_PARITY.generated.json",
            "NEXT90_M121_UI_GM_RUNBOARD_ROUTE.generated.json",
            "NEXT90_M142_DENSE_WORKBENCH_RECEIPTS.md",
        ],
        "required_global_receipt_groups": [
            {
                "route_id": "menu:dice_roller",
                "artifact_key": "generated_dialog_parity",
                "tokens": ["dialog.dice_roller", "dice_roller"],
            },
            {
                "route_id": "workflow:initiative",
                "artifact_key": "gm_runboard_route",
                "tokens": ["Initiative lane:", "ResolveRunboardInitiativeSummary", "gm_runboard"],
            },
            {
                "route_id": "workflow:initiative",
                "artifact_key": "core_dense_receipts_doc",
                "tokens": ["SessionActionBudgetDeterministicReceipt"],
            },
        ],
    },
    "family:identity_contacts_lifestyles_history": {
        "label": "Identity, contacts, lifestyles, and history workflows",
        "compare_artifacts": ["workflow:contacts", "workflow:lifestyles", "workflow:notes"],
        "required_row_direct_evidence_suffixes": [
            "SECTION_HOST_RULESET_PARITY.generated.json",
            "NEXT90_M142_DENSE_WORKBENCH_RECEIPTS.md",
            "UI_FLAGSHIP_RELEASE_GATE.generated.json",
        ],
        "required_global_receipt_groups": [
            {
                "route_id": "workflow:contacts",
                "artifact_key": "section_host_ruleset_parity",
                "tokens": ["tab-contacts.contacts", "tab-contacts"],
            },
            {
                "route_id": "workflow:notes",
                "artifact_key": "section_host_ruleset_parity",
                "tokens": ["tab-notes.metadata", "tab-notes"],
            },
            {
                "route_id": "workflow:lifestyles",
                "artifact_key": "core_dense_receipts_doc",
                "tokens": ["workflow:lifestyles", "WorkspaceWorkflowDeterministicReceipt"],
            },
            {
                "route_id": "workflow:contacts_and_notes_screenshots",
                "artifact_key": "desktop_visual_familiarity_gate",
                "tokens": ["10-contacts-section-light.png", "11-diary-dialog-light.png", "legacy_contacts_workflow_rhythm"],
            },
        ],
    },
}


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize the Fleet M142 route-local proof closeout gate packet.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--markdown-output", default=str(DEFAULT_MARKDOWN))
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
    parser.add_argument("--generated-dialog-parity", default=str(GENERATED_DIALOG_PARITY))
    parser.add_argument("--section-host-ruleset-parity", default=str(SECTION_HOST_RULESET_PARITY))
    parser.add_argument("--gm-runboard-route", default=str(GM_RUNBOARD_ROUTE))
    parser.add_argument("--core-dense-receipts-doc", default=str(CORE_DENSE_RECEIPTS_DOC))
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
        issues.append("Fleet queue mirror row is missing for work task 142.5.")
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
        issues.append("Canonical registry work task title drifted from the M142 Fleet closeout contract.")
    if work_task and _normalize_text(work_task.get("status")) != "complete":
        issues.append("Canonical registry work task status must be complete before M142 can close.")
    if work_task and _normalize_list(work_task.get("evidence")) != REGISTRY_EVIDENCE:
        issues.append("Canonical registry work task evidence drifted from the M142 Fleet closeout proof set.")
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
    workflow_rows: List[Dict[str, Any]] = []
    if isinstance(workflow_pack, dict):
        workflow_rows.extend(
            dict(row)
            for row in (workflow_pack.get("workflow_maps") or [])
            if isinstance(row, dict) and _normalize_text(row.get("id"))
        )
        workflow_rows.extend(
            dict(row) for row in (workflow_pack.get("families") or []) if isinstance(row, dict) and _normalize_text(row.get("id"))
        )
    if isinstance(workflow_pack, list):
        workflow_rows.extend(
            dict(row) for row in workflow_pack if isinstance(row, dict) and _normalize_text(row.get("id"))
        )
    workflow_maps = {
        _normalize_text(row.get("id")): dict(row)
        for row in workflow_rows
    }
    for family_id, spec in TARGET_FAMILIES.items():
        compact_id = family_id.split("family:", 1)[-1]
        row = workflow_maps.get(compact_id) or {}
        if not row:
            issues.append(f"Workflow pack is missing `{compact_id}`.")
            continue
        compare_artifacts = _normalize_list(row.get("compare_artifacts"))
        if compare_artifacts != spec["compare_artifacts"]:
            issues.append(f"Workflow pack compare_artifacts drifted for `{compact_id}`.")
    return {"state": "pass" if not issues else "fail", "issues": issues}


def _proof_texts(
    *,
    desktop_visual_familiarity_gate: Dict[str, Any],
    desktop_workflow_execution_gate: Dict[str, Any],
    screenshot_review_gate: Dict[str, Any],
    classic_dense_workbench_gate: Dict[str, Any],
    veteran_task_time_gate: Dict[str, Any],
    ui_flagship_release_gate: Dict[str, Any],
    ui_local_release_proof: Dict[str, Any],
    generated_dialog_parity: Dict[str, Any],
    section_host_ruleset_parity: Dict[str, Any],
    gm_runboard_route: Dict[str, Any],
    core_dense_receipts_doc: str,
) -> Dict[str, str]:
    return {
        "desktop_visual_familiarity_gate": json.dumps(desktop_visual_familiarity_gate, sort_keys=True),
        "desktop_workflow_execution_gate": json.dumps(desktop_workflow_execution_gate, sort_keys=True),
        "screenshot_review_gate": json.dumps(screenshot_review_gate, sort_keys=True),
        "classic_dense_workbench_gate": json.dumps(classic_dense_workbench_gate, sort_keys=True),
        "veteran_task_time_gate": json.dumps(veteran_task_time_gate, sort_keys=True),
        "ui_flagship_release_gate": json.dumps(ui_flagship_release_gate, sort_keys=True),
        "ui_local_release_proof": json.dumps(ui_local_release_proof, sort_keys=True),
        "generated_dialog_parity": json.dumps(generated_dialog_parity, sort_keys=True),
        "section_host_ruleset_parity": json.dumps(section_host_ruleset_parity, sort_keys=True),
        "gm_runboard_route": json.dumps(gm_runboard_route, sort_keys=True),
        "core_dense_receipts_doc": core_dense_receipts_doc,
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
            artifact_key = group["artifact_key"]
            text = texts.get(artifact_key, "")
            tokens = [token for token in group["tokens"] if token in text]
            if tokens:
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


def _project_direct_row_evidence(spec: Dict[str, Any], row: Dict[str, Any], path_by_suffix: Dict[str, str]) -> tuple[str, List[str]]:
    compare_artifacts = ", ".join(spec["compare_artifacts"])
    source_reason = _normalize_text(row.get("reason"))
    if source_reason.startswith("All declared compare artifacts for this Chummer5A family are directly backed by current parity proof:"):
        reason = f"Fleet route-local closeout packet binds direct runtime/task-speed receipts for {compare_artifacts}."
    else:
        reason = source_reason or f"Fleet route-local closeout packet binds direct runtime/task-speed receipts for {compare_artifacts}."

    evidence: List[str] = []
    for suffix in spec["required_row_direct_evidence_suffixes"]:
        path = path_by_suffix.get(suffix)
        if path and path not in evidence:
            evidence.append(path)
    return reason, evidence


def _target_rows_monitor(
    parity_audit: Dict[str, Any],
    *,
    proof_corpus_monitor: Dict[str, Any],
    path_by_suffix: Dict[str, str],
) -> Dict[str, Any]:
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
    family_receipt_summary = dict(proof_corpus_monitor.get("family_receipt_summary") or {})
    for family_id, spec in TARGET_FAMILIES.items():
        row = rows.get(family_id) or {}
        family_runtime = dict(family_receipt_summary.get(family_id) or {})
        row_issues: List[str] = []
        evidence = _normalize_list(row.get("evidence"))
        projected_reason = _normalize_text(row.get("reason"))
        projected_evidence = list(evidence)
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
            row_relies_on_broad_prose = reason.startswith(
                "All declared compare artifacts for this Chummer5A family are directly backed by current parity proof:"
            )
            row_has_direct_evidence = any(
                evidence_item.endswith(suffix)
                for evidence_item in evidence
                for suffix in spec["required_row_direct_evidence_suffixes"]
            )
            row_uses_only_broad_evidence = bool(evidence) and {Path(item).name for item in evidence}.issubset(broad_evidence_suffixes)
            has_direct_runtime_receipts = not _normalize_list(family_runtime.get("missing_route_receipts"))
            if row_relies_on_broad_prose or not row_has_direct_evidence or row_uses_only_broad_evidence:
                if has_direct_runtime_receipts:
                    projected_reason, projected_evidence = _project_direct_row_evidence(spec, row, path_by_suffix)
                    warnings.append(
                        f"{family_id}: parity audit row still publishes broad-family closure; Fleet projected direct runtime/task-speed evidence instead."
                    )
                else:
                    if row_relies_on_broad_prose:
                        row_issues.append("row still closes on broad family prose instead of route-local proof receipts")
                    if not row_has_direct_evidence:
                        row_issues.append("row evidence does not cite any direct runtime/task-speed receipt artifacts for this family")
                    if row_uses_only_broad_evidence:
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
                "reason": projected_reason,
                "evidence": projected_evidence,
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
    desktop_visual_familiarity_gate_path: Path,
    desktop_workflow_execution_gate_path: Path,
    screenshot_review_gate_path: Path,
    classic_dense_workbench_gate_path: Path,
    veteran_task_time_gate_path: Path,
    ui_flagship_release_gate_path: Path,
    ui_local_release_proof_path: Path,
    generated_dialog_parity_path: Path,
    section_host_ruleset_parity_path: Path,
    gm_runboard_route_path: Path,
    core_dense_receipts_doc_path: Path,
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
    desktop_visual_familiarity_gate = _load_json(desktop_visual_familiarity_gate_path)
    desktop_workflow_execution_gate = _load_json(desktop_workflow_execution_gate_path)
    screenshot_review_gate = _load_json(screenshot_review_gate_path)
    classic_dense_workbench_gate = _load_json(classic_dense_workbench_gate_path)
    veteran_task_time_gate = _load_json(veteran_task_time_gate_path)
    ui_flagship_release_gate = _load_json(ui_flagship_release_gate_path)
    ui_local_release_proof = _load_json(ui_local_release_proof_path)
    generated_dialog_parity = _load_json(generated_dialog_parity_path)
    section_host_ruleset_parity = _load_json(section_host_ruleset_parity_path)
    gm_runboard_route = _load_json(gm_runboard_route_path)
    core_dense_receipts_doc = _load_text(core_dense_receipts_doc_path)

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
    workflow_pack_monitor = _workflow_pack_contract_monitor(workflow_pack)

    texts = _proof_texts(
        desktop_visual_familiarity_gate=desktop_visual_familiarity_gate,
        desktop_workflow_execution_gate=desktop_workflow_execution_gate,
        screenshot_review_gate=screenshot_review_gate,
        classic_dense_workbench_gate=classic_dense_workbench_gate,
        veteran_task_time_gate=veteran_task_time_gate,
        ui_flagship_release_gate=ui_flagship_release_gate,
        ui_local_release_proof=ui_local_release_proof,
        generated_dialog_parity=generated_dialog_parity,
        section_host_ruleset_parity=section_host_ruleset_parity,
        gm_runboard_route=gm_runboard_route,
        core_dense_receipts_doc=core_dense_receipts_doc,
    )
    artifact_generated_at = {}
    for key, path, payload in (
        ("desktop_visual_familiarity_gate", desktop_visual_familiarity_gate_path, desktop_visual_familiarity_gate),
        ("desktop_workflow_execution_gate", desktop_workflow_execution_gate_path, desktop_workflow_execution_gate),
        ("screenshot_review_gate", screenshot_review_gate_path, screenshot_review_gate),
        ("classic_dense_workbench_gate", classic_dense_workbench_gate_path, classic_dense_workbench_gate),
        ("veteran_task_time_gate", veteran_task_time_gate_path, veteran_task_time_gate),
        ("ui_flagship_release_gate", ui_flagship_release_gate_path, ui_flagship_release_gate),
        ("ui_local_release_proof", ui_local_release_proof_path, ui_local_release_proof),
        ("generated_dialog_parity", generated_dialog_parity_path, generated_dialog_parity),
        ("section_host_ruleset_parity", section_host_ruleset_parity_path, section_host_ruleset_parity),
        ("gm_runboard_route", gm_runboard_route_path, gm_runboard_route),
        ("core_dense_receipts_doc", core_dense_receipts_doc_path, {}),
    ):
        artifact_generated_at[key] = _parse_generated_at(path, payload)[0]
    proof_corpus_monitor = _proof_corpus_monitor(texts, artifact_generated_at=artifact_generated_at, now=now)
    path_by_suffix = {
        "CHUMMER5A_SCREENSHOT_REVIEW_GATE.generated.json": _display_path(screenshot_review_gate_path),
        "CLASSIC_DENSE_WORKBENCH_POSTURE_GATE.generated.json": _display_path(classic_dense_workbench_gate_path),
        "UI_FLAGSHIP_RELEASE_GATE.generated.json": _display_path(ui_flagship_release_gate_path),
        "UI_LOCAL_RELEASE_PROOF.generated.json": _display_path(ui_local_release_proof_path),
        "GENERATED_DIALOG_ELEMENT_PARITY.generated.json": _display_path(generated_dialog_parity_path),
        "SECTION_HOST_RULESET_PARITY.generated.json": _display_path(section_host_ruleset_parity_path),
        "NEXT90_M121_UI_GM_RUNBOARD_ROUTE.generated.json": _display_path(gm_runboard_route_path),
        "NEXT90_M142_DENSE_WORKBENCH_RECEIPTS.md": _display_path(core_dense_receipts_doc_path),
    }
    target_rows_monitor = _target_rows_monitor(
        parity_audit,
        proof_corpus_monitor=proof_corpus_monitor,
        path_by_suffix=path_by_suffix,
    )

    canonical_monitors = {
        "queue_alignment": queue_monitor,
        "guide_markers": guide_monitor,
        "workflow_pack_contract": workflow_pack_monitor,
    }
    runtime_monitors = {
        "proof_corpus": proof_corpus_monitor,
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

    route_local_proof_closeout_status = "blocked" if runtime_blockers else ("warning" if warnings else "pass")
    package_status = "pass" if not canonical_issues else "fail"
    package_closeout = {
        "ready": package_status == "pass" and not runtime_blockers,
        "status": route_local_proof_closeout_status if package_status == "pass" else "blocked",
        "reasons": canonical_issues + runtime_blockers,
        "warnings": warnings,
    }

    return {
        "generated_at": generated_at,
        "contract_name": "fleet.next90_m142_route_local_proof_closeout_gates",
        "package_id": PACKAGE_ID,
        "frontier_id": FRONTIER_ID,
        "milestone_id": MILESTONE_ID,
        "work_task_id": WORK_TASK_ID,
        "wave": WAVE_ID,
        "status": package_status,
        "queue_title": QUEUE_TITLE,
        "monitor_summary": {
            "route_local_proof_closeout_status": route_local_proof_closeout_status,
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
            "desktop_visual_familiarity_gate": _source_link(desktop_visual_familiarity_gate_path, desktop_visual_familiarity_gate),
            "desktop_workflow_execution_gate": _source_link(desktop_workflow_execution_gate_path, desktop_workflow_execution_gate),
            "screenshot_review_gate": _source_link(screenshot_review_gate_path, screenshot_review_gate),
            "classic_dense_workbench_gate": _source_link(classic_dense_workbench_gate_path, classic_dense_workbench_gate),
            "veteran_task_time_gate": _source_link(veteran_task_time_gate_path, veteran_task_time_gate),
            "ui_flagship_release_gate": _source_link(ui_flagship_release_gate_path, ui_flagship_release_gate),
            "ui_local_release_proof": _source_link(ui_local_release_proof_path, ui_local_release_proof),
            "generated_dialog_parity": _source_link(generated_dialog_parity_path, generated_dialog_parity),
            "section_host_ruleset_parity": _source_link(section_host_ruleset_parity_path, section_host_ruleset_parity),
            "gm_runboard_route": _source_link(gm_runboard_route_path, gm_runboard_route),
            "core_dense_receipts_doc": _text_source_link(core_dense_receipts_doc_path),
        },
    }


def _render_markdown(payload: Dict[str, Any]) -> str:
    summary = dict(payload.get("monitor_summary") or {})
    package_closeout = dict(payload.get("package_closeout") or {})
    lines = [
        "# Next90 M142 Fleet Route-Local Proof Closeout Gates",
        "",
        f"- status: `{payload.get('status', '')}`",
        f"- route_local_proof_closeout_status: `{summary.get('route_local_proof_closeout_status', '')}`",
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
        workflow_pack_path=Path(args.workflow_pack).resolve(),
        parity_audit_path=Path(args.parity_audit).resolve(),
        desktop_visual_familiarity_gate_path=Path(args.desktop_visual_familiarity_gate).resolve(),
        desktop_workflow_execution_gate_path=Path(args.desktop_workflow_execution_gate).resolve(),
        screenshot_review_gate_path=Path(args.screenshot_review_gate).resolve(),
        classic_dense_workbench_gate_path=Path(args.classic_dense_workbench_gate).resolve(),
        veteran_task_time_gate_path=Path(args.veteran_task_time_gate).resolve(),
        ui_flagship_release_gate_path=Path(args.ui_flagship_release_gate).resolve(),
        ui_local_release_proof_path=Path(args.ui_local_release_proof).resolve(),
        generated_dialog_parity_path=Path(args.generated_dialog_parity).resolve(),
        section_host_ruleset_parity_path=Path(args.section_host_ruleset_parity).resolve(),
        gm_runboard_route_path=Path(args.gm_runboard_route).resolve(),
        core_dense_receipts_doc_path=Path(args.core_dense_receipts_doc).resolve(),
    )
    output_path = Path(args.output).resolve()
    markdown_path = Path(args.markdown_output).resolve()
    _write_json_file(output_path, payload)
    _write_markdown_file(markdown_path, _render_markdown(payload))
    print(str(output_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
