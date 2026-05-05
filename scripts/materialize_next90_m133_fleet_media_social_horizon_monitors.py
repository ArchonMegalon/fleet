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

PACKAGE_ID = "next90-m133-fleet-monitor-media-social-horizon-proof-freshness-consent-gat"
FRONTIER_ID = 2336165027
MILESTONE_ID = 133
WORK_TASK_ID = "133.7"
WAVE_ID = "W21"
QUEUE_TITLE = "Monitor media/social horizon proof freshness, consent gates, unsupported public claims, and provider-health stop conditions."
QUEUE_TASK = QUEUE_TITLE
WORK_TASK_TITLE = QUEUE_TITLE
WORK_TASK_DEPENDENCIES = [107, 110, 116, 117, 123, 124, 126]
OWNED_SURFACES = ["monitor_media_social_horizon_proof:fleet"]
ALLOWED_PATHS = ["scripts", "tests", ".codex-studio", "feedback"]

DEFAULT_OUTPUT = PUBLISHED / "NEXT90_M133_FLEET_MEDIA_SOCIAL_HORIZON_MONITORS.generated.json"
DEFAULT_MARKDOWN = PUBLISHED / "NEXT90_M133_FLEET_MEDIA_SOCIAL_HORIZON_MONITORS.generated.md"

SUCCESSOR_REGISTRY = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
QUEUE_STAGING = PUBLISHED / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
DESIGN_QUEUE_STAGING = PRODUCT_MIRROR / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
NEXT90_GUIDE = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_GUIDE.md"
HORIZON_REGISTRY = PRODUCT_MIRROR / "HORIZON_REGISTRY.yaml"
MEDIA_SOCIAL_LTD_GUIDE = PRODUCT_MIRROR / "HORIZON_AND_FEATURE_LTD_INTEGRATION_GUIDE.md"
EXTERNAL_TOOLS_PLANE = PRODUCT_MIRROR / "EXTERNAL_TOOLS_PLANE.md"
BUILD_EXPLAIN_ARTIFACT_TRUTH_POLICY = PRODUCT_MIRROR / "BUILD_EXPLAIN_ARTIFACT_TRUTH_POLICY.md"
COMMUNITY_SAFETY_STATES = PRODUCT_MIRROR / "COMMUNITY_SAFETY_EVENT_AND_APPEAL_STATES.yaml"
JOURNEY_GATES = PUBLISHED / "JOURNEY_GATES.generated.json"
FLAGSHIP_READINESS = PUBLISHED / "FLAGSHIP_PRODUCT_READINESS.generated.json"
PROVIDER_STEWARDSHIP = PUBLISHED / "NEXT90_M130_FLEET_PROVIDER_STEWARDSHIP.generated.json"
MEDIA_LOCAL_RELEASE_PROOF = Path(
    "/docker/fleet/repos/chummer-media-factory/.codex-studio/published/MEDIA_LOCAL_RELEASE_PROOF.generated.json"
)
HUB_LOCAL_RELEASE_PROOF = Path(
    "/docker/chummercomplete/chummer.run-services/.codex-studio/published/HUB_LOCAL_RELEASE_PROOF.generated.json"
)
RELEASE_CHANNEL = Path(
    "/docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json"
)

TARGET_HORIZON_IDS = (
    "jackpoint",
    "community-hub",
    "runsite",
    "runbook-press",
    "ghostwire",
    "table-pulse",
)
TARGET_JOURNEY_IDS = (
    "build_explain_publish",
    "campaign_session_recover_recap",
    "organize_community_and_close_loop",
)
PROOF_FRESHNESS_HOURS = 48

GUIDE_MARKERS = {
    "wave_21": "### 133. Media and social horizon implementation tranche: JACKPOINT, RUNBOOK PRESS, GHOSTWIRE, RUNSITE, TABLE PULSE, and Community Hub",
    "exit_contract": "Exit: media/social horizons become bounded implementation lanes with first-party manifests, consent, provenance, publication, revocation, inspectable artifacts, and unsupported-claim guards.",
}
LTD_GUIDE_MARKERS = {
    "jackpoint_section": "### JACKPOINT",
    "jackpoint_provenance": "evidence provenance",
    "community_hub_section": "### COMMUNITY HUB",
    "community_hub_consent": "consent truth",
    "runsite_section": "### RUNSITE",
    "runsite_tactical_boundary": "tactical authority",
    "runbook_press_section": "### RUNBOOK PRESS",
    "runbook_press_publication": "publication truth",
    "ghostwire_section": "### GHOSTWIRE",
    "ghostwire_replay_truth": "replay truth",
    "table_pulse_section": "### TABLE PULSE",
    "table_pulse_surveillance_boundary": "live surveillance",
    "cross_horizon_rule": "Those lanes may shape demand evidence.",
}
EXTERNAL_TOOLS_MARKERS = {
    "open_run_discovery_boundary": "accepted-roster truth, meeting-handoff truth, and observer-consent truth remain first-party",
    "first_party_authority": "Chummer remains the first-party authority for run, roster, rule-environment, and closeout truth",
    "receipt_and_provenance_rule": "### Rule 3 - receipt and provenance required",
    "campaign_packet_requirements": "Every BLACK LEDGER or Community Hub Signitic campaign must carry approved source receipts, first-party destination URLs, UTM campaign naming, segment scope, expiry or review date, rollback owner, and a kill-switch path.",
    "emailit_promotion_gate": "Emailit is production-eligible only while sender-domain authentication, suppression and unsubscribe policy, bounce handling, template registry, `EmailDeliveryReceipt`, kill switch, and provider-secret handling stay intact on the active lane.",
}
BUILD_EXPLAIN_MARKERS = {
    "truth_order": "## Truth order",
    "inspectable_engine_truth": "## Inspectable engine truth",
    "receipt_and_anchor_minimums": "## Receipt and anchor minimums",
    "launch_and_ui_rules": "## Launch and UI rules",
}
COMMUNITY_SAFETY_REQUIRED_FIELDS = {
    "reporter_visibility",
    "subject_visibility",
    "evidence_posture",
    "retention_posture",
    "publication_posture",
    "appeal_deadline",
}
COMMUNITY_SAFETY_REQUIRED_EVENT_FAMILIES = {
    "observer_consent_violation",
}
HORIZON_REQUIRED_FIELDS = (
    "owner_handoff_gate",
    "owning_repos",
    "allowed_surfaces",
    "proof_gate",
    "public_claim_posture",
    "stop_condition",
)


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize the Fleet M133 media/social horizon monitor packet.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--markdown-output", default=str(DEFAULT_MARKDOWN))
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--queue-staging", default=str(QUEUE_STAGING))
    parser.add_argument("--design-queue-staging", default=str(DESIGN_QUEUE_STAGING))
    parser.add_argument("--next90-guide", default=str(NEXT90_GUIDE))
    parser.add_argument("--horizon-registry", default=str(HORIZON_REGISTRY))
    parser.add_argument("--media-social-ltd-guide", default=str(MEDIA_SOCIAL_LTD_GUIDE))
    parser.add_argument("--external-tools-plane", default=str(EXTERNAL_TOOLS_PLANE))
    parser.add_argument(
        "--build-explain-artifact-truth-policy",
        default=str(BUILD_EXPLAIN_ARTIFACT_TRUTH_POLICY),
    )
    parser.add_argument("--community-safety-states", default=str(COMMUNITY_SAFETY_STATES))
    parser.add_argument("--journey-gates", default=str(JOURNEY_GATES))
    parser.add_argument("--flagship-readiness", default=str(FLAGSHIP_READINESS))
    parser.add_argument("--provider-stewardship", default=str(PROVIDER_STEWARDSHIP))
    parser.add_argument("--media-local-release-proof", default=str(MEDIA_LOCAL_RELEASE_PROOF))
    parser.add_argument("--hub-local-release-proof", default=str(HUB_LOCAL_RELEASE_PROOF))
    parser.add_argument("--release-channel", default=str(RELEASE_CHANNEL))
    return parser.parse_args(argv)


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_list(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []
    return [_normalize_text(value) for value in values if _normalize_text(value)]


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_yaml(path: Path) -> Dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_text(path: Path) -> str:
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


def _write_json_file(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _source_link(path: Path, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "path": _display_path(path),
        "sha256": _sha256_file(path),
        "generated_at": _normalize_text(payload.get("generated_at")),
    }


def _text_source_link(path: Path) -> Dict[str, Any]:
    return {"path": _display_path(path), "sha256": _sha256_file(path), "generated_at": ""}


def _find_queue_item(queue: Dict[str, Any], package_id: str) -> Dict[str, Any]:
    for row in queue.get("items") or []:
        if isinstance(row, dict) and _normalize_text(row.get("package_id")) == package_id:
            return dict(row)
    return {}


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


def _parse_iso_utc(value: str) -> dt.datetime | None:
    text = _normalize_text(value)
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return dt.datetime.fromisoformat(text)
    except ValueError:
        return None


def _age_seconds(value: str, *, now: dt.datetime) -> int | None:
    parsed = _parse_iso_utc(value)
    if parsed is None:
        return None
    return max(0, int((now - parsed).total_seconds()))


def _marker_monitor(text: str, markers: Dict[str, str], *, label: str) -> Dict[str, Any]:
    checks = {name: marker in text for name, marker in markers.items()}
    issues = [f"{label} missing required marker: {name}" for name, present in checks.items() if not present]
    return {"state": "pass" if not issues else "fail", "checks": checks, "issues": issues}


def _has_value(value: Any) -> bool:
    if isinstance(value, list):
        return any(_normalize_text(item) for item in value)
    if isinstance(value, dict):
        return any(_normalize_text(item) for item in value.values())
    return bool(_normalize_text(value))


def _queue_alignment(
    queue_item: Dict[str, Any],
    design_queue_item: Dict[str, Any],
    work_task: Dict[str, Any],
    milestone: Dict[str, Any],
) -> Dict[str, Any]:
    issues: List[str] = []
    if not queue_item:
        issues.append("Fleet queue row is missing.")
    if not design_queue_item:
        issues.append("Design queue row is missing.")
    if not work_task:
        issues.append("Canonical registry work task is missing.")
    expected = {
        "title": QUEUE_TITLE,
        "task": QUEUE_TASK,
        "milestone_id": MILESTONE_ID,
        "work_task_id": WORK_TASK_ID,
        "repo": "fleet",
        "wave": WAVE_ID,
        "frontier_id": FRONTIER_ID,
    }
    for field, expected_value in expected.items():
        expected_text = _normalize_text(expected_value)
        if queue_item and _normalize_text(queue_item.get(field)) != expected_text:
            issues.append(f"Fleet queue {field} drifted.")
        if design_queue_item and _normalize_text(design_queue_item.get(field)) != expected_text:
            issues.append(f"Design queue {field} drifted.")
    if queue_item and _normalize_list(queue_item.get("allowed_paths")) != ALLOWED_PATHS:
        issues.append("Fleet queue allowed_paths drifted.")
    if design_queue_item and _normalize_list(design_queue_item.get("allowed_paths")) != ALLOWED_PATHS:
        issues.append("Design queue allowed_paths drifted.")
    if queue_item and _normalize_list(queue_item.get("owned_surfaces")) != OWNED_SURFACES:
        issues.append("Fleet queue owned_surfaces drifted.")
    if design_queue_item and _normalize_list(design_queue_item.get("owned_surfaces")) != OWNED_SURFACES:
        issues.append("Design queue owned_surfaces drifted.")
    if work_task:
        if _normalize_text(work_task.get("owner")) != "fleet":
            issues.append("Canonical registry work task owner drifted.")
        if _normalize_text(work_task.get("title")) != WORK_TASK_TITLE:
            issues.append("Canonical registry work task title drifted.")
    if milestone and [int(value) for value in milestone.get("dependencies") or []] != WORK_TASK_DEPENDENCIES:
        issues.append("Canonical registry milestone dependencies drifted from M133 requirement set.")
    return {
        "state": "pass" if not issues else "fail",
        "issues": issues,
        "fleet_queue_status": _normalize_text(queue_item.get("status")),
        "design_queue_status": _normalize_text(design_queue_item.get("status")),
        "registry_status": _normalize_text(milestone.get("status")),
        "work_task_status": _normalize_text(work_task.get("status")),
    }


def _community_safety_monitor(payload: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    event_families = {value for value in _normalize_list(payload.get("event_families")) if value}
    required_fields = {value for value in _normalize_list(payload.get("required_fields")) if value}
    for expected in sorted(COMMUNITY_SAFETY_REQUIRED_EVENT_FAMILIES):
        if expected not in event_families:
            issues.append(f"Community safety canon is missing required event family: {expected}")
    for expected in sorted(COMMUNITY_SAFETY_REQUIRED_FIELDS):
        if expected not in required_fields:
            issues.append(f"Community safety canon is missing required field: {expected}")
    return {
        "state": "pass" if not issues else "fail",
        "event_family_count": len(event_families),
        "required_field_count": len(required_fields),
        "issues": issues,
    }


def _horizon_registry_monitor(payload: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    horizons = {
        _normalize_text(row.get("id")): dict(row)
        for row in payload.get("horizons") or []
        if isinstance(row, dict) and _normalize_text(row.get("id"))
    }
    monitored_rows: List[Dict[str, Any]] = []
    for horizon_id in TARGET_HORIZON_IDS:
        row = horizons.get(horizon_id)
        if row is None:
            issues.append(f"Horizon registry is missing `{horizon_id}`.")
            continue
        build_path = dict(row.get("build_path") or {})
        missing_required_fields: List[str] = []
        for field in HORIZON_REQUIRED_FIELDS:
            if not _has_value(row.get(field)):
                missing_required_fields.append(field)
                issues.append(f"Horizon `{horizon_id}` is missing required `{field}`.")
        owner_handoff_gate = _normalize_text(row.get("owner_handoff_gate"))
        owning_repos = _normalize_list(row.get("owning_repos"))
        if _normalize_text(build_path.get("current_state")) != "horizon":
            issues.append(f"Horizon `{horizon_id}` current_state drifted away from `horizon`.")
        if _normalize_text(build_path.get("next_state")) != "bounded_research":
            issues.append(f"Horizon `{horizon_id}` next_state drifted away from `bounded_research`.")
        monitored_rows.append(
            {
                "id": horizon_id,
                "title": _normalize_text(row.get("title")),
                "owning_repo_count": len(owning_repos),
                "current_state": _normalize_text(build_path.get("current_state")),
                "next_state": _normalize_text(build_path.get("next_state")),
                "owner_handoff_gate": owner_handoff_gate,
                "missing_required_field_count": len(missing_required_fields),
                "missing_required_fields": missing_required_fields,
            }
        )
    return {
        "state": "pass" if not issues else "fail",
        "target_horizon_count": len(TARGET_HORIZON_IDS),
        "monitored_horizons": monitored_rows,
        "issues": issues,
    }


def _journey_monitor(payload: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    runtime_blockers: List[str] = []
    warnings: List[str] = []
    journeys = {
        _normalize_text(row.get("id")): dict(row)
        for row in payload.get("journeys") or []
        if isinstance(row, dict) and _normalize_text(row.get("id"))
    }
    monitored: List[Dict[str, Any]] = []
    for journey_id in TARGET_JOURNEY_IDS:
        row = journeys.get(journey_id)
        if row is None:
            issues.append(f"Journey gates are missing `{journey_id}`.")
            continue
        state = _normalize_text(row.get("state")) or "unknown"
        if state not in {"ready", "pass", "passed"}:
            runtime_blockers.append(f"Journey `{journey_id}` is {state}.")
        for warning in _normalize_list(row.get("warning_reasons")):
            warnings.append(f"Journey `{journey_id}` warning: {warning}")
        if bool(row.get("blocked_by_external_constraints_only")):
            warnings.append(f"Journey `{journey_id}` is blocked only by external constraints.")
        monitored.append(
            {
                "id": journey_id,
                "state": state,
                "blocking_reason_count": len(_normalize_list(row.get("blocking_reasons"))),
                "warning_reason_count": len(_normalize_list(row.get("warning_reasons"))),
                "external_proof_request_count": len(row.get("external_proof_requests") or []),
            }
        )
    return {
        "state": "pass" if not issues else "fail",
        "monitored_journey_count": len(monitored),
        "journeys": monitored,
        "runtime_blockers": runtime_blockers,
        "warnings": warnings,
        "issues": issues,
    }


def _flagship_media_monitor(payload: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    runtime_blockers: List[str] = []
    warnings: List[str] = []
    coverage = dict(payload.get("coverage_details") or {})
    media_artifacts = dict(coverage.get("media_artifacts") or {})
    horizons_surface = dict(coverage.get("horizons_and_public_surface") or {})
    operator_loop = dict(coverage.get("fleet_and_operator_loop") or {})
    media_status = _normalize_text(media_artifacts.get("status")) or "unknown"
    horizon_surface_status = _normalize_text(horizons_surface.get("status")) or "unknown"
    operator_loop_status = _normalize_text(operator_loop.get("status")) or "unknown"
    media_evidence = dict(media_artifacts.get("evidence") or {})
    surface_evidence = dict(horizons_surface.get("evidence") or {})
    operator_evidence = dict(operator_loop.get("evidence") or {})
    if media_status not in {"ready", "pass", "passed"}:
        runtime_blockers.append(f"Flagship media artifacts coverage is {media_status}.")
    if horizon_surface_status not in {"ready", "pass", "passed"}:
        runtime_blockers.append(f"Flagship horizons/public-surface coverage is {horizon_surface_status}.")
    if operator_loop_status not in {"ready", "pass", "passed"}:
        warnings.append(f"Flagship fleet/operator-loop coverage is {operator_loop_status}.")
    media_proof_status = _normalize_text(media_evidence.get("media_proof_status")) or "unknown"
    if media_proof_status not in {"pass", "passed", "ready"}:
        runtime_blockers.append(f"Media proof status is {media_proof_status}.")
    build_explain_publish = _normalize_text(media_evidence.get("build_explain_publish")) or "unknown"
    if build_explain_publish not in {"ready", "pass", "passed"}:
        runtime_blockers.append(f"Build/explain publish readiness is {build_explain_publish}.")
    report_cluster_release_notify = _normalize_text(surface_evidence.get("report_cluster_release_notify")) or "unknown"
    if report_cluster_release_notify not in {"ready", "pass", "passed"}:
        warnings.append(f"Public-surface release/notify posture is {report_cluster_release_notify}.")
    if _normalize_text(surface_evidence.get("public_group_deployment_status")) not in {"public", "protected_preview"}:
        warnings.append("Public-group deployment status drifted from expected public or protected_preview posture.")
    if _normalize_text(operator_evidence.get("journey_overall_state")) not in {"ready", "pass", "passed"}:
        warnings.append(
            f"Fleet/operator-loop journey posture is {_normalize_text(operator_evidence.get('journey_overall_state')) or 'unknown'}."
        )
    return {
        "state": "pass" if not issues else "fail",
        "media_artifacts_status": media_status,
        "horizons_public_surface_status": horizon_surface_status,
        "fleet_operator_loop_status": operator_loop_status,
        "media_proof_path": _normalize_text(media_evidence.get("media_proof_path")),
        "media_proof_status": media_proof_status,
        "public_group_deployment_status": _normalize_text(surface_evidence.get("public_group_deployment_status")),
        "build_explain_publish": build_explain_publish,
        "journey_overall_state": _normalize_text(operator_evidence.get("journey_overall_state")),
        "runtime_blockers": runtime_blockers,
        "warnings": warnings,
        "issues": issues,
    }


def _single_proof_monitor(
    *,
    label: str,
    path: Path,
    now: dt.datetime,
    acceptable_statuses: set[str],
    freshness_hours: int,
    require_non_empty_fields: List[str] | None = None,
) -> Dict[str, Any]:
    issues: List[str] = []
    runtime_blockers: List[str] = []
    warnings: List[str] = []
    payload = _read_json(path)
    if not payload:
        issues.append(f"{label} proof is missing or invalid: {path}")
        return {
            "state": "fail",
            "path": _display_path(path),
            "generated_at": "",
            "age_hours": None,
            "status": "missing",
            "runtime_blockers": runtime_blockers,
            "warnings": warnings,
            "issues": issues,
        }
    status = _normalize_text(payload.get("status")) or "unknown"
    generated_at = _normalize_text(payload.get("generated_at") or payload.get("generatedAt"))
    age_seconds = _age_seconds(generated_at, now=now)
    if status.lower() not in acceptable_statuses:
        runtime_blockers.append(f"{label} proof status is {status}.")
    if age_seconds is None:
        issues.append(f"{label} proof generated_at is missing or invalid.")
    elif age_seconds > freshness_hours * 3600:
        runtime_blockers.append(
            f"{label} proof freshness exceeded threshold ({age_seconds}s > {freshness_hours * 3600}s)."
        )
    for field in require_non_empty_fields or []:
        if not _normalize_text(payload.get(field)):
            runtime_blockers.append(f"{label} proof is missing non-empty `{field}`.")
    return {
        "state": "pass" if not issues else "fail",
        "path": _display_path(path),
        "generated_at": generated_at,
        "age_hours": None if age_seconds is None else round(age_seconds / 3600.0, 2),
        "status": status,
        "runtime_blockers": runtime_blockers,
        "warnings": warnings,
        "issues": issues,
    }


def _release_channel_proof_monitor(*, path: Path, now: dt.datetime) -> Dict[str, Any]:
    monitor = _single_proof_monitor(
        label="Release channel",
        path=path,
        now=now,
        acceptable_statuses={"published", "publishable"},
        freshness_hours=PROOF_FRESHNESS_HOURS,
        require_non_empty_fields=["supportabilitySummary", "knownIssueSummary", "fixAvailabilitySummary"],
    )
    payload = _read_json(path)
    release_proof = dict(payload.get("releaseProof") or {})
    release_proof_status = _normalize_text(release_proof.get("status"))
    release_proof_generated_at = _normalize_text(
        release_proof.get("generatedAt") or release_proof.get("generated_at")
    )
    release_proof_age_seconds = _age_seconds(release_proof_generated_at, now=now)
    if release_proof_status.lower() not in {"pass", "passed", "ready"}:
        monitor["runtime_blockers"].append(
            f"Release channel proof releaseProof.status is {release_proof_status or 'unknown'}."
        )
    if release_proof_age_seconds is None:
        monitor["issues"].append("Release channel proof releaseProof.generatedAt is missing or invalid.")
    elif release_proof_age_seconds > PROOF_FRESHNESS_HOURS * 3600:
        monitor["runtime_blockers"].append(
            "Release channel proof freshness exceeded threshold "
            f"({release_proof_age_seconds}s > {PROOF_FRESHNESS_HOURS * 3600}s)."
        )
    monitor["state"] = "pass" if not monitor.get("issues") else "fail"
    monitor["release_proof_status"] = release_proof_status or "unknown"
    monitor["release_proof_generated_at"] = release_proof_generated_at
    monitor["release_proof_age_hours"] = (
        None if release_proof_age_seconds is None else round(release_proof_age_seconds / 3600.0, 2)
    )
    return monitor


def _publication_proof_monitor(
    *,
    media_proof_path: Path,
    hub_proof_path: Path,
    release_channel_path: Path,
    now: dt.datetime,
) -> Dict[str, Any]:
    issues: List[str] = []
    runtime_blockers: List[str] = []
    warnings: List[str] = []
    media = _single_proof_monitor(
        label="Media local release",
        path=media_proof_path,
        now=now,
        acceptable_statuses={"pass", "passed", "ready"},
        freshness_hours=PROOF_FRESHNESS_HOURS,
    )
    hub = _single_proof_monitor(
        label="Hub local release",
        path=hub_proof_path,
        now=now,
        acceptable_statuses={"pass", "passed", "ready"},
        freshness_hours=PROOF_FRESHNESS_HOURS,
    )
    release_channel = _release_channel_proof_monitor(path=release_channel_path, now=now)
    for section_name, section in (
        ("media", media),
        ("hub", hub),
        ("release_channel", release_channel),
    ):
        for issue in section.get("issues") or []:
            issues.append(f"{section_name}: {issue}")
        for runtime_blocker in section.get("runtime_blockers") or []:
            runtime_blockers.append(f"{section_name}: {runtime_blocker}")
        warnings.extend(section.get("warnings") or [])
    return {
        "state": "pass" if not issues else "fail",
        "media_local_release": media,
        "hub_local_release": hub,
        "release_channel": release_channel,
        "runtime_blockers": runtime_blockers,
        "warnings": warnings,
        "issues": issues,
    }


def _provider_stop_condition_monitor(payload: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    runtime_blockers: List[str] = []
    warnings: List[str] = []
    if not payload:
        issues.append("Provider stewardship packet is missing.")
        return {
            "state": "fail",
            "runtime_blockers": runtime_blockers,
            "warnings": warnings,
            "issues": issues,
        }
    if _normalize_text(payload.get("status")) != "pass":
        runtime_blockers.append(f"Provider stewardship packet status is {_normalize_text(payload.get('status')) or 'unknown'}.")
    runtime = dict(payload.get("runtime_monitors") or {})
    governor = dict(payload.get("governor_monitors") or {})
    routes = dict(runtime.get("provider_routes") or {})
    if int(routes.get("revert_now_count") or 0) > 0:
        runtime_blockers.append(
            "Provider routes require immediate revert for " + ", ".join(_normalize_list(routes.get("revert_now_lanes")))
        )
    canary_gate = dict(governor.get("provider_canary_gate") or {})
    if _normalize_text(canary_gate.get("state")) not in {"ready", "pass", "passed"}:
        runtime_blockers.append(
            f"Provider canary gate is {_normalize_text(canary_gate.get('state')) or 'unknown'}."
        )
    if int(routes.get("fallback_thin_count") or 0) > 0:
        warnings.append(
            "Provider fallback coverage is thin for " + ", ".join(_normalize_list(routes.get("fallback_thin_lanes")))
        )
    if int(routes.get("review_due_count") or 0) > 0:
        warnings.append(
            "Provider route review is due for " + ", ".join(_normalize_list(routes.get("review_due_lanes")))
        )
    current_launch_action = _normalize_text(governor.get("current_launch_action"))
    if current_launch_action and current_launch_action != "launch_expand":
        warnings.append(f"Governor current_launch_action is {current_launch_action}.")
    rollback_state = _normalize_text(governor.get("rollback_state"))
    if rollback_state in {"armed", "active", "watch"}:
        warnings.append(f"Governor rollback posture remains {rollback_state}.")
    return {
        "state": "pass" if not issues else "fail",
        "provider_packet_status": _normalize_text(payload.get("status")) or "unknown",
        "fallback_thin_count": int(routes.get("fallback_thin_count") or 0),
        "review_due_count": int(routes.get("review_due_count") or 0),
        "revert_now_count": int(routes.get("revert_now_count") or 0),
        "provider_canary_gate_state": _normalize_text(canary_gate.get("state")) or "unknown",
        "current_launch_action": current_launch_action,
        "rollback_state": rollback_state,
        "runtime_blockers": runtime_blockers,
        "warnings": warnings,
        "issues": issues,
    }


def build_payload(
    *,
    registry_path: Path,
    queue_path: Path,
    design_queue_path: Path,
    next90_guide_path: Path,
    horizon_registry_path: Path,
    media_social_ltd_guide_path: Path,
    external_tools_plane_path: Path,
    build_explain_artifact_truth_policy_path: Path,
    community_safety_states_path: Path,
    journey_gates_path: Path,
    flagship_readiness_path: Path,
    provider_stewardship_path: Path,
    media_local_release_proof_path: Path,
    hub_local_release_proof_path: Path,
    release_channel_path: Path,
    generated_at: str | None = None,
) -> Dict[str, Any]:
    generated_at = generated_at or _utc_now()
    registry = _read_yaml(registry_path)
    queue = _read_yaml(queue_path)
    design_queue = _read_yaml(design_queue_path)
    next90_guide = _read_text(next90_guide_path)
    horizon_registry = _read_yaml(horizon_registry_path)
    media_social_ltd_guide = _read_text(media_social_ltd_guide_path)
    external_tools_plane = _read_text(external_tools_plane_path)
    build_explain_truth_policy = _read_text(build_explain_artifact_truth_policy_path)
    community_safety_states = _read_yaml(community_safety_states_path)
    journey_gates = _read_json(journey_gates_path)
    flagship_readiness = _read_json(flagship_readiness_path)
    provider_stewardship = _read_json(provider_stewardship_path)
    reference_now = _parse_iso_utc(generated_at) or dt.datetime.now(dt.timezone.utc)

    milestone = _find_milestone(registry, MILESTONE_ID)
    work_task = _find_work_task(milestone, WORK_TASK_ID)
    queue_item = _find_queue_item(queue, PACKAGE_ID)
    design_queue_item = _find_queue_item(design_queue, PACKAGE_ID)

    canonical_alignment = _queue_alignment(queue_item, design_queue_item, work_task, milestone)
    guide_monitor = _marker_monitor(next90_guide, GUIDE_MARKERS, label="Next90 guide canon")
    ltd_guide_monitor = _marker_monitor(
        media_social_ltd_guide,
        LTD_GUIDE_MARKERS,
        label="Media/social LTD integration guide canon",
    )
    external_tools_monitor = _marker_monitor(
        external_tools_plane,
        EXTERNAL_TOOLS_MARKERS,
        label="External tools plane canon",
    )
    build_explain_monitor = _marker_monitor(
        build_explain_truth_policy,
        BUILD_EXPLAIN_MARKERS,
        label="Build/explain artifact truth policy canon",
    )
    community_safety_monitor = _community_safety_monitor(community_safety_states)
    horizon_registry_monitor = _horizon_registry_monitor(horizon_registry)

    journey_monitor = _journey_monitor(journey_gates)
    flagship_media_monitor = _flagship_media_monitor(flagship_readiness)
    publication_proof_monitor = _publication_proof_monitor(
        media_proof_path=media_local_release_proof_path,
        hub_proof_path=hub_local_release_proof_path,
        release_channel_path=release_channel_path,
        now=reference_now,
    )
    provider_stop_condition_monitor = _provider_stop_condition_monitor(provider_stewardship)

    blockers: List[str] = []
    runtime_blockers: List[str] = []
    warnings: List[str] = []
    for section_name, section in (
        ("canonical_alignment", canonical_alignment),
        ("next90_guide", guide_monitor),
        ("ltd_integration_guide", ltd_guide_monitor),
        ("external_tools_plane", external_tools_monitor),
        ("build_explain_artifact_truth_policy", build_explain_monitor),
        ("community_safety_states", community_safety_monitor),
        ("horizon_registry", horizon_registry_monitor),
        ("journey_monitor", journey_monitor),
        ("flagship_media_monitor", flagship_media_monitor),
        ("publication_proof_monitor", publication_proof_monitor),
        ("provider_stop_condition_monitor", provider_stop_condition_monitor),
    ):
        for issue in section.get("issues") or []:
            blockers.append(f"{section_name}: {issue}")
        for runtime_blocker in section.get("runtime_blockers") or []:
            runtime_blockers.append(f"{section_name}: {runtime_blocker}")
        warnings.extend(section.get("warnings") or [])

    media_social_status = "blocked" if runtime_blockers else "warning" if warnings else "pass"
    closeout_warnings = list(runtime_blockers) + warnings

    return {
        "contract_name": "fleet.next90_m133_media_social_horizon_monitors",
        "generated_at": generated_at,
        "status": "pass" if not blockers else "blocked",
        "package_id": PACKAGE_ID,
        "frontier_id": FRONTIER_ID,
        "milestone_id": MILESTONE_ID,
        "work_task_id": WORK_TASK_ID,
        "wave": WAVE_ID,
        "queue_title": QUEUE_TITLE,
        "queue_task": QUEUE_TASK,
        "owned_surfaces": OWNED_SURFACES,
        "allowed_paths": ALLOWED_PATHS,
        "canonical_alignment": canonical_alignment,
        "canonical_monitors": {
            "next90_guide": guide_monitor,
            "ltd_integration_guide": ltd_guide_monitor,
            "external_tools_plane": external_tools_monitor,
            "build_explain_artifact_truth_policy": build_explain_monitor,
            "community_safety_states": community_safety_monitor,
            "horizon_registry": horizon_registry_monitor,
        },
        "runtime_monitors": {
            "journeys": journey_monitor,
            "flagship_media": flagship_media_monitor,
            "publication_proof": publication_proof_monitor,
            "provider_stop_conditions": provider_stop_condition_monitor,
        },
        "monitor_summary": {
            "media_social_status": media_social_status,
            "runtime_blocker_count": len(runtime_blockers),
            "warning_count": len(warnings),
            "journey_count": journey_monitor.get("monitored_journey_count"),
            "media_proof_status": flagship_media_monitor.get("media_proof_status"),
            "provider_canary_gate_state": provider_stop_condition_monitor.get("provider_canary_gate_state"),
            "runtime_blockers": runtime_blockers,
        },
        "package_closeout": {
            "state": "pass" if not blockers else "blocked",
            "blockers": blockers,
            "warnings": closeout_warnings,
        },
        "source_inputs": {
            "successor_registry": _source_link(registry_path, registry),
            "queue_staging": _source_link(queue_path, queue),
            "design_queue_staging": _source_link(design_queue_path, design_queue),
            "next90_guide": _text_source_link(next90_guide_path),
            "horizon_registry": _source_link(horizon_registry_path, horizon_registry),
            "media_social_ltd_guide": _text_source_link(media_social_ltd_guide_path),
            "external_tools_plane": _text_source_link(external_tools_plane_path),
            "build_explain_artifact_truth_policy": _text_source_link(build_explain_artifact_truth_policy_path),
            "community_safety_states": _source_link(community_safety_states_path, community_safety_states),
            "journey_gates": _source_link(journey_gates_path, journey_gates),
            "flagship_readiness": _source_link(flagship_readiness_path, flagship_readiness),
            "provider_stewardship": _source_link(provider_stewardship_path, provider_stewardship),
            "media_local_release_proof": _source_link(media_local_release_proof_path, _read_json(media_local_release_proof_path)),
            "hub_local_release_proof": _source_link(hub_local_release_proof_path, _read_json(hub_local_release_proof_path)),
            "release_channel": _source_link(release_channel_path, _read_json(release_channel_path)),
        },
    }


def render_markdown(payload: Dict[str, Any]) -> str:
    summary = dict(payload.get("monitor_summary") or {})
    closeout = dict(payload.get("package_closeout") or {})
    lines = [
        "# Fleet M133 media/social horizon monitors",
        "",
        f"- status: {payload.get('status')}",
        f"- media_social_status: {summary.get('media_social_status')}",
        f"- package_id: {payload.get('package_id')}",
        f"- frontier_id: {payload.get('frontier_id')}",
        f"- generated_at: {payload.get('generated_at')}",
        "",
        "## Runtime summary",
        f"- journey_count: {summary.get('journey_count')}",
        f"- media_proof_status: {summary.get('media_proof_status')}",
        f"- provider_canary_gate_state: {summary.get('provider_canary_gate_state')}",
        f"- runtime_blocker_count: {summary.get('runtime_blocker_count')}",
        f"- warning_count: {summary.get('warning_count')}",
        "",
        "## Package closeout",
        f"- state: {closeout.get('state') or 'blocked'}",
    ]
    if closeout.get("warnings"):
        lines.append("- warnings:")
        lines.extend([f"  - {warning}" for warning in closeout.get("warnings") or []])
    return "\n".join(lines) + "\n"


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(
        registry_path=Path(args.successor_registry).resolve(),
        queue_path=Path(args.queue_staging).resolve(),
        design_queue_path=Path(args.design_queue_staging).resolve(),
        next90_guide_path=Path(args.next90_guide).resolve(),
        horizon_registry_path=Path(args.horizon_registry).resolve(),
        media_social_ltd_guide_path=Path(args.media_social_ltd_guide).resolve(),
        external_tools_plane_path=Path(args.external_tools_plane).resolve(),
        build_explain_artifact_truth_policy_path=Path(args.build_explain_artifact_truth_policy).resolve(),
        community_safety_states_path=Path(args.community_safety_states).resolve(),
        journey_gates_path=Path(args.journey_gates).resolve(),
        flagship_readiness_path=Path(args.flagship_readiness).resolve(),
        provider_stewardship_path=Path(args.provider_stewardship).resolve(),
        media_local_release_proof_path=Path(args.media_local_release_proof).resolve(),
        hub_local_release_proof_path=Path(args.hub_local_release_proof).resolve(),
        release_channel_path=Path(args.release_channel).resolve(),
    )
    output_path = Path(args.output).resolve()
    markdown_path = Path(args.markdown_output).resolve()
    _write_json_file(output_path, payload)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "artifact": str(output_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
