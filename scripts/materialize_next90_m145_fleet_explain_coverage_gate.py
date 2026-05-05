#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import binascii
import datetime as dt
import gzip
import html
import json
from pathlib import Path
import quopri
import re
from typing import Any, Dict, Iterable, List
from urllib.parse import unquote
import zlib

import yaml


UTC = dt.timezone.utc
ROOT = Path("/docker/fleet")
PUBLISHED = ROOT / ".codex-studio" / "published"
DEFAULT_OUTPUT = PUBLISHED / "NEXT90_M145_FLEET_EXPLAIN_COVERAGE_GATE.generated.json"

PACKAGE_ID = "next90-m145-fleet-explain-coverage-gate"
WORK_TASK_ID = "145.6"
MILESTONE_ID = 145
FRONTIER_ID = 1456045606
QUEUE_TITLE = (
    "Fail closeout when visible values, warnings, or bounded what-if answers ship without explain coverage and fallback proof."
)
QUEUE_TASK = (
    "Fail closeout when promoted visible values, warnings, or bounded what-if answers ship without coverage-registry truth, "
    "deterministic packet proof, source-anchor posture, or text-first fallback."
)
OWNED_SURFACES = ["explain_coverage_gate:fleet", "explain_fallback_truth:fleet"]
ALLOWED_PATHS = ["scripts", "tests", ".codex-studio", "feedback"]

SUCCESSOR_REGISTRY = Path("/docker/chummercomplete/chummer-design/products/chummer/NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml")
QUEUE_STAGING = PUBLISHED / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
DESIGN_QUEUE_STAGING = Path("/docker/chummercomplete/chummer-design/products/chummer/NEXT_90_DAY_QUEUE_STAGING.generated.yaml")
DESIGN_CANON = Path("/docker/chummercomplete/chummer-design/products/chummer/EXPLAIN_EVERY_VALUE_AND_GROUNDED_FOLLOW_UP.md")
EA_PACKET_PACK = Path("/docker/EA/docs/chummer_explain_narration_packs/CHUMMER_EXPLAIN_NARRATION_PACKET_PACK.yaml")
CORE_RECEIPT_CANDIDATES = (
    Path("/docker/chummercomplete/chummer6-core/.codex-studio/published/EXPLAIN_VALUE_PACKETS.generated.json"),
    Path("/docker/chummercomplete/chummer-core-engine/.codex-studio/published/EXPLAIN_VALUE_PACKETS.generated.json"),
)
UI_RECEIPT_CANDIDATES = (
    Path("/docker/chummercomplete/chummer-presentation/.codex-studio/published/NEXT90_M145_UI_DESKTOP_EXPLAIN_DRAWER_AND_FOLLOW_UP.generated.json"),
    Path("/docker/chummercomplete/chummer6-ui/.codex-studio/published/NEXT90_M145_UI_DESKTOP_EXPLAIN_DRAWER_AND_FOLLOW_UP.generated.json"),
)
MOBILE_RECEIPT_CANDIDATES = (
    Path("/docker/chummercomplete/chummer6-mobile/.codex-studio/published/MOBILE_LOCAL_RELEASE_PROOF.generated.json"),
    Path("/docker/chummercomplete/chummer-play/.codex-studio/published/MOBILE_LOCAL_RELEASE_PROOF.generated.json"),
)
MEDIA_RECEIPT_CANDIDATES = (
    Path("/docker/fleet/repos/chummer-media-factory/.codex-studio/published/MEDIA_LOCAL_RELEASE_PROOF.generated.json"),
    Path("/docker/chummercomplete/chummer6-media-factory/.codex-studio/published/MEDIA_LOCAL_RELEASE_PROOF.generated.json"),
    Path("/docker/chummercomplete/chummer-media-factory/.codex-studio/published/MEDIA_LOCAL_RELEASE_PROOF.generated.json"),
)

DISALLOWED_MARKERS = (
    "TASK_LOCAL_TELEMETRY.generated.json",
    "ACTIVE_RUN_HANDOFF.generated.md",
    "active-run telemetry",
    "helper output",
    "supervisor status",
    "supervisor eta",
)

SIBLING_SURFACES = (
    {
        "key": "core_packets",
        "package_id": "next90-m145-core-explain-every-value-packets",
        "work_task_id": "145.1",
        "owner": "chummer6-core",
        "proof_kind": "core",
    },
    {
        "key": "desktop_drawer",
        "package_id": "next90-m145-ui-desktop-explain-drawer-and-follow-up",
        "work_task_id": "145.2",
        "owner": "chummer6-ui",
        "proof_kind": "ui",
    },
    {
        "key": "mobile_follow_up",
        "package_id": "next90-m145-mobile-quick-explain-and-follow-up",
        "work_task_id": "145.3",
        "owner": "chummer6-mobile",
        "proof_kind": "mobile",
    },
    {
        "key": "ea_grounded_follow_up",
        "package_id": "next90-m145-ea-grounded-explain-narration-packs",
        "work_task_id": "145.4",
        "owner": "executive-assistant",
        "proof_kind": "ea",
    },
    {
        "key": "presenter_siblings",
        "package_id": "next90-m145-media-factory-explain-presenter-siblings",
        "work_task_id": "145.5",
        "owner": "chummer6-media-factory",
        "proof_kind": "media",
    },
    {
        "key": "design_canon",
        "package_id": "next90-m145-design-explain-every-value-canon",
        "work_task_id": "145.7",
        "owner": "chummer6-design",
        "proof_kind": "design",
    },
)


def _utc_now() -> str:
    return dt.datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _status_closed(value: Any) -> bool:
    return str(value or "").strip().lower() in {"complete", "completed", "done", "closed", "pass", "passed", "ready"}


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_yaml(path: Path) -> Dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _resolve_existing(candidates: Iterable[Path]) -> Path:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return next(iter(candidates))


def _find_queue_item(queue: Dict[str, Any], package_id: str) -> Dict[str, Any]:
    for item in queue.get("items") or []:
        if isinstance(item, dict) and str(item.get("package_id") or "").strip() == package_id:
            return dict(item)
    return {}


def _find_milestone(registry: Dict[str, Any], milestone_id: int) -> Dict[str, Any]:
    for milestone in registry.get("milestones") or []:
        if isinstance(milestone, dict) and int(milestone.get("id") or 0) == milestone_id:
            return dict(milestone)
    return {}


def _find_work_task(milestone: Dict[str, Any], work_task_id: str) -> Dict[str, Any]:
    for task in milestone.get("work_tasks") or []:
        if isinstance(task, dict) and str(task.get("id") or "").strip() == work_task_id:
            return dict(task)
    return {}


def _normalized_scalar(value: Any) -> str:
    return str(value or "").strip()


def _normalized_string_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [_normalized_scalar(item) for item in value if _normalized_scalar(item)]


def _missing_markers(text: str, markers: Iterable[str]) -> List[str]:
    body = str(text or "")
    return [marker for marker in markers if marker not in body]


def _contains_disallowed(value: Any) -> List[str]:
    text = json.dumps(value, sort_keys=True) if not isinstance(value, str) else value
    lowered_variants = [variant.lower() for variant in _worker_proof_text_variants(text)]
    blocked = []
    for marker in DISALLOWED_MARKERS:
        lowered_marker = marker.lower()
        if any(lowered_marker in variant for variant in lowered_variants):
            blocked.append(marker)
    return blocked


def _proof_source_integrity_issues(label: str, *, payload: Any, raw_text: str) -> List[str]:
    blocked: List[str] = []
    for marker in _contains_disallowed(payload):
        blocked.append(f"{label} cites worker-local telemetry/helper proof: {marker}")
    if raw_text:
        for marker in _contains_disallowed(raw_text):
            issue = f"{label} cites worker-local telemetry/helper proof: {marker}"
            if issue not in blocked:
                blocked.append(issue)
    return blocked


def _worker_proof_text_variants(text: str) -> List[str]:
    variants = _expanded_text_decodings([text])
    variants.extend(_decoded_worker_proof_tokens(variants))
    variants = _expanded_text_decodings(variants)
    deduped: List[str] = []
    seen: set[str] = set()
    for variant in variants:
        if variant not in seen:
            deduped.append(variant)
            seen.add(variant)
    return deduped


def _expanded_text_decodings(values: List[str]) -> List[str]:
    expanded: List[str] = []
    pending = [value for value in values if value]
    seen: set[str] = set()
    for _depth in range(3):
        next_pending: List[str] = []
        for value in pending:
            if value not in seen:
                expanded.append(value)
                seen.add(value)
            candidates = [unquote(value), html.unescape(value)]
            if "=" in value:
                try:
                    candidates.append(quopri.decodestring(value).decode("utf-8"))
                except UnicodeDecodeError:
                    pass
            if "\\" in value:
                try:
                    candidates.append(value.encode("utf-8").decode("unicode_escape"))
                except UnicodeDecodeError:
                    pass
            for candidate in candidates:
                if candidate and candidate not in seen:
                    next_pending.append(candidate)
        pending = next_pending
        if not pending:
            break
    return expanded


def _decoded_worker_proof_tokens(values: List[str]) -> List[str]:
    decoded: List[str] = []
    pending = list(values)
    seen = set(values)
    for _depth in range(3):
        next_pending: List[str] = []
        for value in pending:
            for token_source in _encoded_token_sources(value):
                for token in re.findall(r"\b[A-Za-z0-9+/_-]{20,}={0,2}\b", token_source):
                    padded = token + ("=" * (-len(token) % 4))
                    try:
                        decoded_bytes = base64.b64decode(padded, validate=True)
                    except binascii.Error:
                        try:
                            decoded_bytes = base64.urlsafe_b64decode(padded)
                        except binascii.Error:
                            continue
                    for decoded_token in _decode_worker_proof_bytes(decoded_bytes):
                        if decoded_token not in seen:
                            decoded.append(decoded_token)
                            next_pending.append(decoded_token)
                            seen.add(decoded_token)
                for token in re.findall(r"(?<!\S)[!-~]{20,}(?!\S)", token_source):
                    for decoder in (base64.b85decode, base64.a85decode):
                        try:
                            decoded_candidates = _decode_worker_proof_bytes(decoder(token.encode("ascii")))
                        except (binascii.Error, ValueError):
                            continue
                        for decoded_token in decoded_candidates:
                            if decoded_token not in seen:
                                decoded.append(decoded_token)
                                next_pending.append(decoded_token)
                                seen.add(decoded_token)
                for token in re.findall(r"\b[A-Z2-7]{20,}={0,6}\b", token_source.upper()):
                    padded = token + ("=" * (-len(token) % 8))
                    try:
                        decoded_candidates = _decode_worker_proof_bytes(base64.b32decode(padded, casefold=True))
                    except binascii.Error:
                        continue
                    for decoded_token in decoded_candidates:
                        if decoded_token not in seen:
                            decoded.append(decoded_token)
                            next_pending.append(decoded_token)
                            seen.add(decoded_token)
        pending = next_pending
        if not pending:
            break
    return decoded


def _encoded_token_sources(value: str) -> List[str]:
    sources = [value]
    compact = re.sub(r"\s+", "", value)
    if compact and compact != value:
        sources.append(compact)
    deduped: List[str] = []
    seen: set[str] = set()
    for source in sources:
        if source not in seen:
            deduped.append(source)
            seen.add(source)
    return deduped


def _decode_worker_proof_bytes(payload: bytes) -> List[str]:
    decoded: List[str] = []
    candidates = [payload]
    for decompressor in (
        gzip.decompress,
        zlib.decompress,
        lambda value: zlib.decompress(value, -zlib.MAX_WBITS),
    ):
        try:
            candidates.append(decompressor(payload))
        except (OSError, zlib.error):
            continue
    for candidate in candidates:
        try:
            decoded_text = candidate.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if decoded_text not in decoded:
            decoded.append(decoded_text)
    return decoded


def _build_core_gate(receipt: Dict[str, Any], path: Path) -> tuple[bool, List[str], Dict[str, Any]]:
    issues: List[str] = []
    coverage_kinds = {str(item).strip() for item in receipt.get("coverage_registry_kinds") or []}
    counterfactual_kinds = {str(item).strip() for item in receipt.get("counterfactual_outcome_kinds") or []}
    proof_anchor_count = int(receipt.get("proof_anchor_count") or 0)
    verification_commands = list(receipt.get("verification_commands") or [])
    unresolved = receipt.get("unresolved") or {}
    if not _status_closed(receipt.get("status")):
        issues.append("core explanation-packet receipt is not closed")
    if not {"mechanical-result", "legality-state", "warning", "before-after-delta", "counterfactual", "source-anchor"}.issubset(coverage_kinds):
        issues.append(
            "core coverage-registry kinds do not cover result, legality, warning, before-after delta, counterfactual, and source-anchor truth"
        )
    if not {"why", "why-not", "what-if"}.issubset(counterfactual_kinds):
        issues.append("core bounded counterfactual kinds do not cover why, why-not, and what-if")
    if proof_anchor_count <= 0:
        issues.append("core explanation-packet receipt is missing deterministic proof anchors")
    if not verification_commands:
        issues.append("core explanation-packet receipt is missing verification commands")
    if unresolved not in ({}, {"missing_files": [], "snippet_failures": {}}):
        issues.append("core explanation-packet receipt still lists unresolved proof drift")
    return (
        not issues,
        issues,
        {
            "receipt_path": str(path),
            "status": str(receipt.get("status") or "").strip(),
            "coverage_registry_kinds": sorted(coverage_kinds),
            "counterfactual_outcome_kinds": sorted(counterfactual_kinds),
            "proof_anchor_count": proof_anchor_count,
            "verification_commands": verification_commands,
            "unresolved": unresolved,
        },
    )


def _build_ui_gate(receipt: Dict[str, Any], path: Path) -> tuple[bool, List[str], Dict[str, Any]]:
    issues: List[str] = []
    evidence = dict(receipt.get("evidence") or {})
    source_checks = dict(evidence.get("sourceChecks") or {})
    feedback_checks = dict(source_checks.get("Chummer.Avalonia/MainWindow.FeedbackCoordinator.cs") or {})
    follow_up_checks = dict(source_checks.get("Chummer.Avalonia/DesktopExplainDrawerFollowUpWindow.cs") or {})
    if not _status_closed(receipt.get("status")):
        issues.append("desktop explain-drawer receipt is not closed")
    if receipt.get("unresolved"):
        issues.append("desktop explain-drawer receipt still lists unresolved closure checks")
    if not feedback_checks.get("Explain follow-up stayed text-first with source-anchor and stale-state posture visible."):
        issues.append("desktop explain-drawer proof is missing text-first source-anchor fallback posture")
    if not follow_up_checks.get('CreateSection("Bounded follow-up", FirstNonBlank(_context.FollowUp, "No bounded follow-up is attached to this packet."))'):
        issues.append("desktop explain-drawer proof is missing bounded follow-up fallback text")
    return (
        not issues,
        issues,
        {
            "receipt_path": str(path),
            "status": str(receipt.get("status") or "").strip(),
            "unresolved": list(receipt.get("unresolved") or []),
        },
    )


def _build_mobile_gate(receipt: Dict[str, Any], path: Path) -> tuple[bool, List[str], Dict[str, Any]]:
    issues: List[str] = []
    required_markers = list(((receipt.get("required_markers") or {}).get("quick_explain_follow_up")) or [])
    journeys = {str(item).strip() for item in receipt.get("journeys_passed") or []}
    if not _status_closed(receipt.get("status")):
        issues.append("mobile quick-explain receipt is not closed")
    if "quick_explain_follow_up" not in journeys:
        issues.append("mobile release proof does not publish the quick_explain_follow_up journey")
    if "source-anchor context" not in " ".join(required_markers):
        issues.append("mobile quick-explain proof is missing source-anchor context markers")
    if "grounded text-first follow-up bounded to the claimed live-play shell" not in required_markers:
        issues.append("mobile quick-explain proof is missing grounded text-first follow-up fallback proof")
    return (
        not issues,
        issues,
        {
            "receipt_path": str(path),
            "status": str(receipt.get("status") or "").strip(),
            "journeys_passed": sorted(journeys),
        },
    )


def _build_ea_gate(packet_pack: Dict[str, Any], path: Path) -> tuple[bool, List[str], Dict[str, Any]]:
    issues: List[str] = []
    labels = {str(item).strip() for item in ((packet_pack.get("quality_gates") or {}).get("required_labels") or [])}
    fail_closed = dict(packet_pack.get("fail_closed_posture") or {})
    compile_contract = dict(packet_pack.get("compile_contract") or {})
    if not _status_closed(packet_pack.get("status")):
        issues.append("EA grounded narration packet pack is not closed")
    if not {"packet_grounded", "text_first_fallback", "no_arithmetic_authority"}.issubset(labels):
        issues.append("EA packet pack quality gates are missing packet-grounded text-first fallback labels")
    if "first-party explain drawer" not in str(fail_closed.get("missing_counterfactual") or ""):
        issues.append("EA packet pack is missing the first-party drawer fallback for absent counterfactuals")
    if "unavailable response" not in str((compile_contract.get("grounded_follow_up_pack") or {}).get("refusal_rule") or ""):
        issues.append("EA grounded follow-up pack is missing explicit unavailable-response refusal posture")
    return (
        not issues,
        issues,
        {
            "packet_pack_path": str(path),
            "status": str(packet_pack.get("status") or "").strip(),
            "required_labels": sorted(labels),
        },
    )


def _build_design_gate(canon_text: str, path: Path) -> tuple[bool, List[str], Dict[str, Any]]:
    markers = [
        "Coverage registry",
        "text explanation is always the first-party fallback",
        "source anchors stay attached to the same packet",
        "If Chummer cannot produce the required packet, it should say so plainly and fall back to text guidance instead of guessing.",
        "The gate should fail closed",
    ]
    missing = _missing_markers(canon_text, markers)
    return (
        not missing,
        [f"design canon is missing marker: {marker}" for marker in missing],
        {"canon_path": str(path), "missing_markers": missing},
    )


def _extract_successor_package(receipt: Dict[str, Any], package_id: str) -> Dict[str, Any]:
    for candidate in receipt.get("successor_packages") or []:
        if isinstance(candidate, dict) and str(candidate.get("package_id") or "").strip() == package_id:
            return dict(candidate)
    return {}


def _build_media_gate(receipt: Dict[str, Any], path: Path) -> tuple[bool, List[str], Dict[str, Any]]:
    media_package = _extract_successor_package(receipt, "next90-m145-media-factory-explain-presenter-siblings")
    gate_receipt = media_package or receipt
    if not gate_receipt:
        return False, ["presenter sibling proof is not published yet"], {"receipt_path": str(path), "status": "missing"}
    issues: List[str] = []
    explain_presenter_guards = [str(item).strip() for item in gate_receipt.get("explain_presenter_guards") or []]
    receipt_rows = {str(item).strip() for item in gate_receipt.get("receipt_rows") or []}
    if not _status_closed(gate_receipt.get("status")):
        issues.append("presenter sibling proof is published but not closed")
    if "first-party text fallback stays first-class in the render receipt and text fallback receipt so optional media surfaces never become the only explain surface" not in explain_presenter_guards:
        issues.append("presenter sibling proof is missing the first-party text fallback guard")
    if "queue and registry mirrors must match the canonical M145 package and task blocks exactly so repo-local proof cannot drift on status or scoped fields" not in explain_presenter_guards:
        issues.append("presenter sibling proof is missing the queue-and-registry mirror guard")
    if "ExplainPresenterTextFallbackReceipt" not in receipt_rows:
        issues.append("presenter sibling proof is missing ExplainPresenterTextFallbackReceipt rows")
    return (
        not issues,
        issues,
        {
            "receipt_path": str(path),
            "status": str(gate_receipt.get("status") or "").strip(),
            "proof_source": "successor_package" if media_package else "receipt_root",
            "receipt_rows": sorted(receipt_rows),
        },
    )


def _surface_is_shipped(*, queue_row: Dict[str, Any], design_queue_row: Dict[str, Any], registry_row: Dict[str, Any], proof_kind: str, proof_evidence: Dict[str, Any]) -> bool:
    if any(
        _status_closed(row.get("status"))
        for row in (queue_row, design_queue_row, registry_row)
        if isinstance(row, dict)
    ):
        return True
    if proof_kind != "media":
        return True
    return str(proof_evidence.get("status") or "").strip().lower() not in {"", "missing", "not_started"}


def _sibling_contract_issues(
    *,
    queue_row: Dict[str, Any],
    design_queue_row: Dict[str, Any],
    registry_row: Dict[str, Any],
) -> List[str]:
    issues: List[str] = []
    if not queue_row:
        issues.append("local queue row is missing")
        return issues
    if not design_queue_row:
        issues.append("design queue row is missing")
        return issues
    if not registry_row:
        issues.append("registry work-task row is missing")
        return issues

    for key, message in (
        ("title", "queue title drifted from the design queue mirror"),
        ("task", "queue task drifted from the design queue mirror"),
        ("package_id", "queue package_id drifted from the design queue mirror"),
        ("work_task_id", "queue work_task_id drifted from the design queue mirror"),
        ("repo", "queue repo drifted from the design queue mirror"),
        ("milestone_id", "queue milestone_id drifted from the design queue mirror"),
        ("frontier_id", "queue frontier_id drifted from the design queue mirror"),
    ):
        if _normalized_scalar(queue_row.get(key)) != _normalized_scalar(design_queue_row.get(key)):
            issues.append(message)
    if _normalized_string_list(queue_row.get("allowed_paths")) != _normalized_string_list(design_queue_row.get("allowed_paths")):
        issues.append("queue allowed_paths drifted from the design queue mirror")
    if _normalized_string_list(queue_row.get("owned_surfaces")) != _normalized_string_list(design_queue_row.get("owned_surfaces")):
        issues.append("queue owned_surfaces drifted from the design queue mirror")
    if _normalized_scalar(queue_row.get("title")) != _normalized_scalar(registry_row.get("title")):
        issues.append("queue title drifted from the registry work-task title")
    return issues


def build_payload(
    *,
    registry_path: Path = SUCCESSOR_REGISTRY,
    queue_path: Path = QUEUE_STAGING,
    design_queue_path: Path = DESIGN_QUEUE_STAGING,
    core_receipt_path: Path | None = None,
    ui_receipt_path: Path | None = None,
    mobile_receipt_path: Path | None = None,
    media_receipt_path: Path | None = None,
    ea_packet_pack_path: Path = EA_PACKET_PACK,
    design_canon_path: Path = DESIGN_CANON,
    generated_at: str | None = None,
) -> Dict[str, Any]:
    core_receipt_path = core_receipt_path or _resolve_existing(CORE_RECEIPT_CANDIDATES)
    ui_receipt_path = ui_receipt_path or _resolve_existing(UI_RECEIPT_CANDIDATES)
    mobile_receipt_path = mobile_receipt_path or _resolve_existing(MOBILE_RECEIPT_CANDIDATES)
    media_receipt_path = media_receipt_path or _resolve_existing(MEDIA_RECEIPT_CANDIDATES)

    registry = _read_yaml(registry_path)
    queue = _read_yaml(queue_path)
    design_queue = _read_yaml(design_queue_path)
    milestone = _find_milestone(registry, MILESTONE_ID)
    work_task = _find_work_task(milestone, WORK_TASK_ID)
    queue_item = _find_queue_item(queue, PACKAGE_ID)
    design_queue_item = _find_queue_item(design_queue, PACKAGE_ID)

    canonical_issues: List[str] = []
    if not milestone:
        canonical_issues.append("milestone 145 is missing from the canonical successor registry")
    if _normalized_scalar(work_task.get("title")) != QUEUE_TITLE:
        canonical_issues.append("registry work-task title drifted from the Fleet M145 package contract")
    if _normalized_scalar(queue_item.get("title")) != QUEUE_TITLE:
        canonical_issues.append("local queue title drifted from the Fleet M145 package contract")
    if _normalized_scalar(queue_item.get("task")) != QUEUE_TASK:
        canonical_issues.append("local queue task drifted from the Fleet M145 package contract")
    if _normalized_scalar(design_queue_item.get("title")) != QUEUE_TITLE:
        canonical_issues.append("design queue title drifted from the Fleet M145 package contract")
    if _normalized_scalar(design_queue_item.get("task")) != QUEUE_TASK:
        canonical_issues.append("design queue task drifted from the Fleet M145 package contract")
    if _normalized_scalar(queue_item.get("package_id")) != PACKAGE_ID:
        canonical_issues.append("local queue package_id drifted from the Fleet M145 package contract")
    if _normalized_scalar(design_queue_item.get("package_id")) != PACKAGE_ID:
        canonical_issues.append("design queue package_id drifted from the Fleet M145 package contract")
    if _normalized_scalar(queue_item.get("work_task_id")) != WORK_TASK_ID:
        canonical_issues.append("local queue work_task_id drifted from the Fleet M145 package contract")
    if _normalized_scalar(design_queue_item.get("work_task_id")) != WORK_TASK_ID:
        canonical_issues.append("design queue work_task_id drifted from the Fleet M145 package contract")
    if _normalized_scalar(queue_item.get("repo")) != "fleet":
        canonical_issues.append("local queue repo drifted from the Fleet M145 package contract")
    if _normalized_scalar(design_queue_item.get("repo")) != "fleet":
        canonical_issues.append("design queue repo drifted from the Fleet M145 package contract")
    if _normalized_scalar(queue_item.get("milestone_id")) != str(MILESTONE_ID):
        canonical_issues.append("local queue milestone_id drifted from the Fleet M145 package contract")
    if _normalized_scalar(design_queue_item.get("milestone_id")) != str(MILESTONE_ID):
        canonical_issues.append("design queue milestone_id drifted from the Fleet M145 package contract")
    if _normalized_scalar(queue_item.get("frontier_id")) != str(FRONTIER_ID):
        canonical_issues.append("local queue frontier_id drifted from the Fleet M145 package contract")
    if _normalized_scalar(design_queue_item.get("frontier_id")) != str(FRONTIER_ID):
        canonical_issues.append("design queue frontier_id drifted from the Fleet M145 package contract")
    if list(queue_item.get("owned_surfaces") or []) != OWNED_SURFACES:
        canonical_issues.append("local queue owned_surfaces drifted from the Fleet M145 package contract")
    if list(queue_item.get("allowed_paths") or []) != ALLOWED_PATHS:
        canonical_issues.append("local queue allowed_paths drifted from the Fleet M145 package contract")
    if list(design_queue_item.get("owned_surfaces") or []) != OWNED_SURFACES:
        canonical_issues.append("design queue owned_surfaces drifted from the Fleet M145 package contract")
    if list(design_queue_item.get("allowed_paths") or []) != ALLOWED_PATHS:
        canonical_issues.append("design queue allowed_paths drifted from the Fleet M145 package contract")
    for entry in _contains_disallowed(work_task):
        canonical_issues.append(f"registry work-task cites worker-local telemetry/helper proof: {entry}")
    for entry in _contains_disallowed({key: value for key, value in milestone.items() if key != "work_tasks"}):
        canonical_issues.append(f"registry milestone cites worker-local telemetry/helper proof: {entry}")
    for entry in _contains_disallowed({key: value for key, value in queue.items() if key != "items"}):
        canonical_issues.append(f"local queue staging cites worker-local telemetry/helper proof: {entry}")
    for entry in _contains_disallowed({key: value for key, value in design_queue.items() if key != "items"}):
        canonical_issues.append(f"design queue staging cites worker-local telemetry/helper proof: {entry}")
    for entry in _contains_disallowed(queue_item):
        canonical_issues.append(f"local queue item cites worker-local telemetry/helper proof: {entry}")
    for entry in _contains_disallowed(design_queue_item):
        canonical_issues.append(f"design queue item cites worker-local telemetry/helper proof: {entry}")
    if _status_closed(queue_item.get("status")) and not _status_closed(design_queue_item.get("status")):
        canonical_issues.append("design queue row is not closed after the local Fleet package row marked this package closed")
    if _status_closed(queue_item.get("status")) and not _status_closed(work_task.get("status")):
        canonical_issues.append("registry work-task row is not closed after the local Fleet package row marked this package closed")

    core_receipt = _read_json(core_receipt_path)
    ui_receipt = _read_json(ui_receipt_path)
    mobile_receipt = _read_json(mobile_receipt_path)
    media_receipt = _read_json(media_receipt_path)
    ea_packet_pack = _read_yaml(ea_packet_pack_path)
    design_canon_text = _read_text(design_canon_path)

    proof_builders = {
        "core": dict(zip(("passed", "issues", "evidence"), _build_core_gate(core_receipt, core_receipt_path))),
        "ui": dict(zip(("passed", "issues", "evidence"), _build_ui_gate(ui_receipt, ui_receipt_path))),
        "mobile": dict(zip(("passed", "issues", "evidence"), _build_mobile_gate(mobile_receipt, mobile_receipt_path))),
        "ea": dict(zip(("passed", "issues", "evidence"), _build_ea_gate(ea_packet_pack, ea_packet_pack_path))),
        "design": dict(zip(("passed", "issues", "evidence"), _build_design_gate(design_canon_text, design_canon_path))),
        "media": dict(zip(("passed", "issues", "evidence"), _build_media_gate(media_receipt, media_receipt_path))),
    }
    proof_source_integrity = {
        "core": _proof_source_integrity_issues("core explanation-packet receipt", payload=core_receipt, raw_text=_read_text(core_receipt_path)),
        "ui": _proof_source_integrity_issues("desktop explain-drawer receipt", payload=ui_receipt, raw_text=_read_text(ui_receipt_path)),
        "mobile": _proof_source_integrity_issues("mobile quick-explain receipt", payload=mobile_receipt, raw_text=_read_text(mobile_receipt_path)),
        "ea": _proof_source_integrity_issues("EA grounded narration packet pack", payload=ea_packet_pack, raw_text=_read_text(ea_packet_pack_path)),
        "design": _proof_source_integrity_issues("design explain canon", payload=design_canon_text, raw_text=design_canon_text),
        "media": _proof_source_integrity_issues("presenter sibling proof receipt", payload=media_receipt, raw_text=_read_text(media_receipt_path)),
    }
    for key, source_issues in proof_source_integrity.items():
        if source_issues:
            proof_builders[key]["issues"].extend(source_issues)
            proof_builders[key]["passed"] = False
            proof_builders[key]["evidence"]["worker_local_proof_markers"] = source_issues

    surface_receipts: List[Dict[str, Any]] = []
    closure_blockers: List[str] = []
    surface_receipt_by_task_id: Dict[str, Dict[str, Any]] = {}
    for surface in SIBLING_SURFACES:
        queue_row = _find_queue_item(queue, surface["package_id"])
        design_queue_row = _find_queue_item(design_queue, surface["package_id"])
        registry_row = _find_work_task(milestone, surface["work_task_id"])
        proof_bundle = proof_builders[surface["proof_kind"]]
        proof_passed = bool(proof_bundle["passed"])
        proof_issues = list(proof_bundle["issues"])
        proof_evidence = dict(proof_bundle["evidence"])
        shipped = _surface_is_shipped(
            queue_row=queue_row,
            design_queue_row=design_queue_row,
            registry_row=registry_row,
            proof_kind=str(surface["proof_kind"]),
            proof_evidence=proof_evidence,
        )
        if str(surface["proof_kind"]) == "media" and not shipped:
            proof_issues = []
        reasons = list(proof_issues)
        if shipped:
            reasons.extend(
                _sibling_contract_issues(
                    queue_row=queue_row,
                    design_queue_row=design_queue_row,
                    registry_row=registry_row,
                )
            )
        if shipped and not _status_closed(queue_row.get("status")):
            reasons.append("local queue row is not closed")
        if shipped and not _status_closed(registry_row.get("status")) and surface["proof_kind"] != "media":
            reasons.append("registry work-task row is not closed")
        if _status_closed(queue_row.get("status")) and not _status_closed(design_queue_row.get("status")):
            reasons.append("design queue row is not closed after the local queue marked this package closed")
        if shipped:
            for entry in _contains_disallowed(queue_row):
                reasons.append(f"local queue row cites worker-local telemetry/helper proof: {entry}")
            for entry in _contains_disallowed(design_queue_row):
                reasons.append(f"design queue row cites worker-local telemetry/helper proof: {entry}")
            for entry in _contains_disallowed(registry_row):
                reasons.append(f"registry work-task row cites worker-local telemetry/helper proof: {entry}")
        if reasons:
            closure_blockers.append(f"{surface['package_id']}: " + "; ".join(reasons))
        surface_receipt = {
            "key": surface["key"],
            "package_id": surface["package_id"],
            "work_task_id": surface["work_task_id"],
            "owner": surface["owner"],
            "queue_status": str(queue_row.get("status") or "").strip(),
            "design_queue_status": str(design_queue_row.get("status") or "").strip(),
            "registry_status": str(registry_row.get("status") or "").strip(),
            "shipped": shipped,
            "proof_passed": proof_passed,
            "blocking_reasons": reasons,
            "proof_evidence": proof_evidence,
        }
        surface_receipts.append(surface_receipt)
        surface_receipt_by_task_id[str(surface["work_task_id"])] = surface_receipt

    def _surface_gate_passes(*task_ids: str) -> bool:
        for task_id in task_ids:
            surface_receipt = surface_receipt_by_task_id.get(task_id) or {}
            if not surface_receipt.get("shipped"):
                continue
            if surface_receipt.get("blocking_reasons"):
                return False
        return True

    aggregate_checks = {
        "coverage_registry_truth": {
            "status": (
                "pass"
                if _surface_gate_passes("145.1", "145.7")
                else "blocked"
            ),
            "required_packages": ["145.1", "145.7"],
        },
        "deterministic_packet_proof": {
            "status": "pass" if _surface_gate_passes("145.1") else "blocked",
            "required_packages": ["145.1"],
        },
        "source_anchor_posture": {
            "status": (
                "pass"
                if _surface_gate_passes("145.2", "145.3", "145.7")
                else "blocked"
            ),
            "required_packages": ["145.2", "145.3", "145.7"],
        },
        "text_first_fallback": {
            "status": (
                "pass"
                if _surface_gate_passes("145.2", "145.3", "145.4")
                else "blocked"
            ),
            "required_packages": ["145.2", "145.3", "145.4"],
        },
        "presenter_optional_fallback": {
            "status": (
                "pass"
                if surface_receipt_by_task_id.get("145.5", {}).get("shipped")
                and _surface_gate_passes("145.5")
                else ("blocked" if surface_receipt_by_task_id.get("145.5", {}).get("shipped") else "not_shipped")
            ),
            "required_packages": ["145.5"],
        },
    }

    blocked = canonical_issues or closure_blockers
    status = "pass" if not blocked else "blocked"
    return {
        "contract_name": "fleet.next90_m145_explain_coverage_gate",
        "generated_at": generated_at or _utc_now(),
        "status": status,
        "package_id": PACKAGE_ID,
        "milestone_id": MILESTONE_ID,
        "frontier_id": FRONTIER_ID,
        "queue_title": QUEUE_TITLE,
        "queue_task": QUEUE_TASK,
        "canonical_alignment": {
            "registry_path": str(registry_path),
            "queue_path": str(queue_path),
            "design_queue_path": str(design_queue_path),
            "registry_work_task_present": bool(work_task),
            "queue_item_present": bool(queue_item),
            "design_queue_item_present": bool(design_queue_item),
            "registry_status": str(work_task.get("status") or "").strip(),
            "queue_status": str(queue_item.get("status") or "").strip(),
            "design_queue_status": str(design_queue_item.get("status") or "").strip(),
            "issues": canonical_issues,
        },
        "aggregate_checks": aggregate_checks,
        "surface_receipts": surface_receipts,
        "package_closeout": {
            "status": status,
            "blocked_reasons": canonical_issues + closure_blockers,
            "do_not_close_until": [
                "canonical queue, design-queue, and registry rows agree on this Fleet package",
                "every shipped sibling explain surface has closed packet/source-anchor/text-first proof",
                "local queue closures do not outrun the design-owned queue mirror",
            ],
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize the Fleet M145 explain-coverage closeout gate packet."
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--queue-staging", default=str(QUEUE_STAGING))
    parser.add_argument("--design-queue-staging", default=str(DESIGN_QUEUE_STAGING))
    parser.add_argument("--core-receipt", default=str(_resolve_existing(CORE_RECEIPT_CANDIDATES)))
    parser.add_argument("--ui-receipt", default=str(_resolve_existing(UI_RECEIPT_CANDIDATES)))
    parser.add_argument("--mobile-receipt", default=str(_resolve_existing(MOBILE_RECEIPT_CANDIDATES)))
    parser.add_argument("--media-receipt", default=str(_resolve_existing(MEDIA_RECEIPT_CANDIDATES)))
    parser.add_argument("--ea-packet-pack", default=str(EA_PACKET_PACK))
    parser.add_argument("--design-canon", default=str(DESIGN_CANON))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(
        registry_path=Path(args.successor_registry).resolve(),
        queue_path=Path(args.queue_staging).resolve(),
        design_queue_path=Path(args.design_queue_staging).resolve(),
        core_receipt_path=Path(args.core_receipt).resolve(),
        ui_receipt_path=Path(args.ui_receipt).resolve(),
        mobile_receipt_path=Path(args.mobile_receipt).resolve(),
        media_receipt_path=Path(args.media_receipt).resolve(),
        ea_packet_pack_path=Path(args.ea_packet_pack).resolve(),
        design_canon_path=Path(args.design_canon).resolve(),
    )
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
