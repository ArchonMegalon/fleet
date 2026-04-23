#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

try:
    from scripts import materialize_weekly_governor_packet as weekly
except ModuleNotFoundError:
    import materialize_weekly_governor_packet as weekly


ROOT = Path("/docker/fleet")
PUBLISHED = ROOT / ".codex-studio" / "published"
PACKAGE_ID = "next90-m106-fleet-governor-packet"
SUCCESSOR_FRONTIER_ID = "2376135131"


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify the checked-in Next90 M106 Fleet weekly governor packet closeout."
    )
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument(
        "--packet",
        default=str(PUBLISHED / "WEEKLY_GOVERNOR_PACKET.generated.json"),
    )
    parser.add_argument(
        "--markdown",
        default=str(PUBLISHED / "WEEKLY_GOVERNOR_PACKET.generated.md"),
    )
    parser.add_argument("--successor-registry", default=str(weekly.SUCCESSOR_REGISTRY))
    parser.add_argument("--closed-flagship-registry", default=str(weekly.CLOSED_FLAGSHIP_REGISTRY_PATH))
    parser.add_argument("--design-queue-staging", default=str(weekly.DESIGN_QUEUE_STAGING))
    parser.add_argument("--queue-staging", default=str(weekly.QUEUE_STAGING))
    parser.add_argument("--weekly-pulse", default=str(weekly.WEEKLY_PULSE))
    parser.add_argument("--flagship-readiness", default=str(weekly.FLAGSHIP_READINESS))
    parser.add_argument("--journey-gates", default=str(weekly.JOURNEY_GATES))
    parser.add_argument("--support-packets", default=str(weekly.SUPPORT_PACKETS))
    parser.add_argument("--status-plane", default=str(weekly.STATUS_PLANE))
    return parser.parse_args(argv)


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise AssertionError(f"{path} is missing or not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise AssertionError(f"{path} must contain a JSON object")
    return payload


def _require(condition: bool, issues: List[str], message: str) -> None:
    if not condition:
        issues.append(message)


def _stable_weekly_health(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "status": payload.get("status"),
        "generated_at": payload.get("generated_at"),
        "max_age_seconds": payload.get("max_age_seconds"),
        "required_launch_signals": payload.get("required_launch_signals"),
        "risk_cluster_health": payload.get("risk_cluster_health"),
    }


def _decision_projection(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "contract_name": payload.get("contract_name"),
        "schema_version": payload.get("schema_version"),
        "as_of": payload.get("as_of"),
        "program_wave": payload.get("program_wave"),
        "wave_id": payload.get("wave_id"),
        "status": payload.get("status"),
        "status_reason": payload.get("status_reason"),
        "successor_frontier_ids": payload.get("successor_frontier_ids"),
        "package_verification": payload.get("package_verification"),
        "weekly_input_health": _stable_weekly_health(dict(payload.get("weekly_input_health") or {})),
        "source_input_health": payload.get("source_input_health"),
        "source_input_fingerprint": payload.get("source_input_fingerprint"),
        "decision_alignment": payload.get("decision_alignment"),
        "truth_inputs": payload.get("truth_inputs"),
        "decision_board": payload.get("decision_board"),
        "decision_gate_ledger": payload.get("decision_gate_ledger"),
        "governor_decisions": payload.get("governor_decisions"),
        "public_status_copy": payload.get("public_status_copy"),
        "package_closeout": payload.get("package_closeout"),
        "measured_rollout_loop": payload.get("measured_rollout_loop"),
        "repeat_prevention": payload.get("repeat_prevention"),
        "risk_clusters": payload.get("risk_clusters"),
        "source_paths": payload.get("source_paths"),
    }


def _projection_drift(expected: Dict[str, Any], actual: Dict[str, Any]) -> List[str]:
    fields = sorted(set(expected) | set(actual))
    return [field for field in fields if expected.get(field) != actual.get(field)]


def _stable_markdown(markdown: str) -> str:
    lines = markdown.splitlines()
    return "\n".join(
        "Generated: <ignored>" if line.startswith("Generated: ")
        else "- Next packet due: <ignored>" if line.startswith("- Next packet due: ")
        else line
        for line in lines
    )


def _markdown_generated_at(markdown: str) -> str:
    for line in markdown.splitlines():
        if line.startswith("Generated: "):
            return line.removeprefix("Generated: ").strip()
    return ""


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_sha256_issues(
    *,
    required_inputs: Dict[str, Any],
    source_paths: Dict[str, str],
) -> List[str]:
    issues: List[str] = []
    for name in sorted(weekly.EXPECTED_PRODUCTION_SOURCE_PATHS):
        row = dict(required_inputs.get(name) or {})
        expected_hash = str(row.get("source_sha256") or "").strip().lower()
        source_path = Path(str(source_paths.get(name) or ""))
        if not expected_hash:
            issues.append(f"packet {name} source_sha256 is missing")
            continue
        try:
            actual_hash = _sha256_file(source_path)
        except OSError as exc:
            issues.append(f"{name} source path cannot be read for source_sha256: {exc}")
            continue
        if expected_hash != actual_hash:
            issues.append(
                f"packet {name} source_sha256 no longer matches {source_path.name}"
            )
    return issues


def _markdown_local_proof_floor_line() -> str:
    return "- Local proof floor commits: " + ", ".join(weekly.LOCAL_PROOF_FLOOR_COMMITS)


def _require_generated_after_source(
    *,
    packet_generated_at: str,
    source_generated_at: str,
    source_name: str,
    issues: List[str],
) -> None:
    packet_time = weekly._parse_iso_utc(packet_generated_at)
    source_time = weekly._parse_iso_utc(source_generated_at)
    if not packet_time:
        issues.append("packet generated_at is missing or invalid")
        return
    if not source_time:
        issues.append(f"{source_name} generated_at is missing or invalid")
        return
    if packet_time < source_time:
        issues.append(
            "checked-in packet generated_at predates "
            f"{source_name}; regenerate WEEKLY_GOVERNOR_PACKET.generated.json after refreshing source inputs"
        )


def _packet_cadence_issues(
    *, packet_generated_at: str, now: dt.datetime | None = None
) -> List[str]:
    issues: List[str] = []
    packet_time = weekly._parse_iso_utc(packet_generated_at)
    if not packet_time:
        return ["checked-in weekly governor packet generated_at is missing or invalid"]
    observed_now = (now or dt.datetime.now(weekly.UTC)).astimezone(weekly.UTC)
    future_skew_seconds = int((packet_time - observed_now).total_seconds())
    if future_skew_seconds > weekly.GENERATED_AT_MAX_FUTURE_SKEW_SECONDS:
        issues.append(
            "checked-in weekly governor packet generated_at is future-dated "
            f"({future_skew_seconds}s ahead)"
        )
        return issues
    age_seconds = int((observed_now - packet_time).total_seconds())
    if age_seconds > weekly.WEEKLY_PACKET_CADENCE_SECONDS:
        issues.append(
            "checked-in weekly governor packet is overdue "
            f"({age_seconds}s old); regenerate WEEKLY_GOVERNOR_PACKET.generated.json "
            "and WEEKLY_GOVERNOR_PACKET.generated.md before using it for launch, freeze, "
            "canary, or rollback decisions"
        )
    return issues


def _compile_manifest_artifact_issues(
    *,
    repo_root: Path,
    packet_path: Path,
    markdown_path: Path,
) -> List[str]:
    manifest_path = repo_root / ".codex-studio" / "published" / "compile.manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"{manifest_path} is missing or not valid JSON: {exc}"]
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        return [f"{manifest_path} artifacts must be a list"]
    artifact_names = {str(item).strip() for item in artifacts if str(item).strip()}
    missing = [
        name
        for name in (packet_path.name, markdown_path.name)
        if name not in artifact_names
    ]
    issues = list(missing)
    packet = _read_json(packet_path)
    manifest_published_at = str(manifest.get("published_at") or "").strip()
    packet_generated_at = str(packet.get("generated_at") or "").strip()
    manifest_time = weekly._parse_iso_utc(manifest_published_at)
    packet_time = weekly._parse_iso_utc(packet_generated_at)
    if not manifest_time:
        issues.append("compile.manifest.json published_at is missing or invalid")
    elif not packet_time:
        issues.append("WEEKLY_GOVERNOR_PACKET.generated.json generated_at is missing or invalid")
    elif manifest_time < packet_time:
        issues.append(
            "compile.manifest.json published_at predates WEEKLY_GOVERNOR_PACKET.generated.json; "
            "regenerate compile.manifest.json after refreshing the weekly governor packet"
        )
    return issues


def _production_source_path_drift(repo_root: Path, source_paths: Dict[str, str]) -> List[str]:
    if repo_root.resolve() != weekly.ROOT.resolve():
        return []
    drift: List[str] = []
    for name, expected_path in weekly.EXPECTED_PRODUCTION_SOURCE_PATHS.items():
        actual_path = str(source_paths.get(name) or "").strip()
        if actual_path != expected_path:
            drift.append(f"{name}: expected {expected_path}, got {actual_path or '<missing>'}")
    return drift


def verify(args: argparse.Namespace) -> List[str]:
    repo_root = Path(args.repo_root).resolve()
    packet_path = Path(args.packet).resolve()
    markdown_path = Path(args.markdown).resolve()
    registry_path = Path(args.successor_registry).resolve()
    closed_flagship_registry_path = Path(args.closed_flagship_registry).resolve()
    design_queue_path = Path(args.design_queue_staging).resolve()
    queue_path = Path(args.queue_staging).resolve()
    weekly_pulse_path = Path(args.weekly_pulse).resolve()
    flagship_readiness_path = Path(args.flagship_readiness).resolve()
    journey_gates_path = Path(args.journey_gates).resolve()
    support_packets_path = Path(args.support_packets).resolve()
    status_plane_path = Path(args.status_plane).resolve()

    issues: List[str] = []
    packet = _read_json(packet_path)
    markdown = markdown_path.read_text(encoding="utf-8") if markdown_path.is_file() else ""
    registry = weekly._read_yaml(registry_path)
    closed_flagship_registry = weekly._read_yaml(closed_flagship_registry_path)
    design_queue = weekly._read_yaml(design_queue_path)
    queue = weekly._read_yaml(queue_path)
    weekly_pulse = weekly._read_json(weekly_pulse_path)
    flagship_readiness = weekly._read_json(flagship_readiness_path)
    journey_gates = weekly._read_json(journey_gates_path)
    support_packets = weekly._read_json(support_packets_path)
    status_plane = weekly._read_yaml(status_plane_path)
    verification = weekly.verify_package(
        registry=registry,
        design_queue=design_queue,
        queue=queue,
        repo_root=repo_root,
    )
    source_paths = {
        "successor_registry": str(registry_path),
        "closed_flagship_registry": str(closed_flagship_registry_path),
        "design_queue_staging": str(design_queue_path),
        "queue_staging": str(queue_path),
        "weekly_pulse": str(weekly_pulse_path),
        "flagship_readiness": str(flagship_readiness_path),
        "journey_gates": str(journey_gates_path),
        "support_packets": str(support_packets_path),
        "status_plane": str(status_plane_path),
    }
    disallowed_source_paths = weekly._disallowed_worker_proof_entries(
        [f"{name}: {path}" for name, path in sorted(source_paths.items())]
    )
    production_source_path_drift = _production_source_path_drift(repo_root, source_paths)
    live_payload = weekly.build_payload(
        repo_root=repo_root,
        registry=registry,
        closed_flagship_registry=closed_flagship_registry,
        design_queue=design_queue,
        queue=queue,
        weekly_pulse=weekly_pulse,
        flagship_readiness=flagship_readiness,
        journey_gates=journey_gates,
        support_packets=support_packets,
        status_plane=status_plane,
        source_paths=source_paths,
    )
    packet_verification = dict(packet.get("package_verification") or {})
    repeat_prevention = dict(packet.get("repeat_prevention") or {})
    worker_command_guard = dict(repeat_prevention.get("worker_command_guard") or {})
    flagship_wave_guard = dict(repeat_prevention.get("flagship_wave_guard") or {})
    required_inputs = dict(dict(packet.get("source_input_health") or {}).get("required_inputs") or {})
    closed_flagship_input = dict(required_inputs.get("closed_flagship_registry") or {})
    source_path_authority = dict(required_inputs.get("source_path_authority") or {})
    support_input_health = dict(required_inputs.get("support_packets") or {})
    local_commit_resolution = dict(packet_verification.get("local_commit_resolution") or {})
    package_closeout = dict(packet.get("package_closeout") or {})
    weekly_health = dict(packet.get("weekly_input_health") or {})
    schedule = dict(packet.get("governor_packet_schedule") or {})
    risk_cluster_health = dict(weekly_health.get("risk_cluster_health") or {})
    source_health = dict(packet.get("source_input_health") or {})
    decision_alignment = dict(packet.get("decision_alignment") or {})
    loop = dict(packet.get("measured_rollout_loop") or {})
    launch_gate_summary = dict(loop.get("launch_gate_summary") or {})
    decision_board = dict(packet.get("decision_board") or {})
    decision_gate_ledger = dict(packet.get("decision_gate_ledger") or {})
    public_status_copy = dict(packet.get("public_status_copy") or {})
    truth_inputs = dict(packet.get("truth_inputs") or {})
    adoption_health = dict(truth_inputs.get("adoption_health") or {})
    dependency_package_routes = dict(truth_inputs.get("successor_dependency_package_routes") or {})
    governor_decisions = packet.get("governor_decisions") or []
    required_resolving_paths = packet_verification.get("required_resolving_proof_paths") or []
    required_decision_actions = loop.get("required_decision_actions") or []
    decision_action_matrix = loop.get("decision_action_matrix") or []
    decision_action_coverage = dict(loop.get("decision_action_coverage") or {})
    decision_source_coverage = dict(loop.get("decision_source_coverage") or {})
    decision_action_routes = dict(loop.get("decision_action_routes") or {})
    decision_receipts = dict(loop.get("decision_receipts") or {})
    weekly_operator_handoff = dict(loop.get("weekly_operator_handoff") or {})
    packet_projection = _decision_projection(packet)
    live_projection = _decision_projection(live_payload)
    projection_drift = _projection_drift(live_projection, packet_projection)
    expected_markdown = weekly.render_markdown_packet(live_payload)
    live_package_closeout = dict(live_payload.get("package_closeout") or {})
    live_repeat_prevention = dict(live_payload.get("repeat_prevention") or {})
    dependency_posture = dict(verification.get("dependency_posture") or {})
    expected_remaining_dependencies = [
        weekly._coerce_int(dep, -1)
        for dep in (
            list(dependency_posture.get("open_dependency_ids") or [])
            + list(dependency_posture.get("missing_dependency_ids") or [])
        )
        if weekly._coerce_int(dep, -1) >= 0
    ]
    expected_remaining_siblings = list(
        live_package_closeout.get("remaining_sibling_work_task_ids") or []
    )

    _require(
        not disallowed_source_paths,
        issues,
        "verifier source paths include active-run or operator-helper evidence that "
        "worker package proof must not cite: "
        + ", ".join(disallowed_source_paths),
    )
    _require(
        not production_source_path_drift,
        issues,
        "production verifier source paths are not canonical: "
        + "; ".join(production_source_path_drift),
    )
    _require(verification["status"] == "pass", issues, f"live package verification is not pass: {verification['issues']}")
    _require(
        not projection_drift,
        issues,
        "checked-in packet decision ledger no longer matches live source inputs for field(s): "
        + ", ".join(projection_drift),
    )
    _require(
        _stable_markdown(markdown) == _stable_markdown(expected_markdown),
        issues,
        "checked-in markdown packet no longer matches the live source-input projection",
    )
    _require(
        _markdown_generated_at(markdown) == str(packet.get("generated_at") or "").strip(),
        issues,
        "checked-in markdown packet Generated timestamp no longer matches JSON packet generated_at",
    )
    expected_schedule = weekly._packet_schedule(str(packet.get("generated_at") or "").strip())
    _require(
        schedule == expected_schedule,
        issues,
        "packet governor_packet_schedule no longer matches generated_at plus weekly cadence",
    )
    _require(
        schedule.get("status") == "scheduled",
        issues,
        "packet governor_packet_schedule.status is not scheduled",
    )
    _require(
        schedule.get("cadence_seconds") == weekly.WEEKLY_PACKET_CADENCE_SECONDS,
        issues,
        "packet governor_packet_schedule cadence_seconds drifted",
    )
    _require(
        schedule.get("max_age_seconds") == weekly.WEEKLY_PACKET_CADENCE_SECONDS,
        issues,
        "packet governor_packet_schedule max_age_seconds drifted",
    )
    packet_cadence_issues = _packet_cadence_issues(
        packet_generated_at=str(packet.get("generated_at") or "")
    )
    _require(
        not packet_cadence_issues,
        issues,
        "packet weekly cadence is not current: " + "; ".join(packet_cadence_issues),
    )
    _require_generated_after_source(
        packet_generated_at=str(packet.get("generated_at") or ""),
        source_generated_at=str(weekly_pulse.get("generated_at") or ""),
        source_name="weekly_pulse",
        issues=issues,
    )
    _require_generated_after_source(
        packet_generated_at=str(packet.get("generated_at") or ""),
        source_generated_at=str(support_packets.get("generated_at") or ""),
        source_name="support_packets",
        issues=issues,
    )
    _require_generated_after_source(
        packet_generated_at=str(packet.get("generated_at") or ""),
        source_generated_at=str(flagship_readiness.get("generated_at") or ""),
        source_name="flagship_readiness",
        issues=issues,
    )
    _require_generated_after_source(
        packet_generated_at=str(packet.get("generated_at") or ""),
        source_generated_at=str(journey_gates.get("generated_at") or ""),
        source_name="journey_gates",
        issues=issues,
    )
    _require_generated_after_source(
        packet_generated_at=str(packet.get("generated_at") or ""),
        source_generated_at=str(status_plane.get("generated_at") or ""),
        source_name="status_plane",
        issues=issues,
    )
    _require(packet.get("contract_name") == "fleet.weekly_governor_packet", issues, "packet contract_name is not fleet.weekly_governor_packet")
    _require(weekly_health.get("status") == "pass", issues, "packet weekly_input_health.status is not pass")
    _require(
        risk_cluster_health.get("status") == "pass",
        issues,
        "packet weekly_input_health.risk_cluster_health.status is not pass",
    )
    _require(
        weekly._coerce_int(risk_cluster_health.get("cluster_count"), 0) > 0,
        issues,
        "packet weekly risk-cluster health has no measured support/feedback clusters",
    )
    _require(
        risk_cluster_health.get("required_fields") == list(weekly.REQUIRED_RISK_CLUSTER_FIELDS),
        issues,
        "packet weekly risk-cluster required fields drifted",
    )
    _require(decision_alignment.get("status") == "pass", issues, "packet decision_alignment.status is not pass")
    source_input_status = source_health.get("status")
    source_input_blocked = source_input_status != "pass"
    package_complete = (
        packet_verification.get("status") == "pass"
        and str(packet_verification.get("queue_status") or "").strip().lower()
        in weekly.COMPLETE_STATUSES
        and str(packet_verification.get("registry_work_task_status") or "").strip().lower()
        in weekly.COMPLETE_STATUSES
    )
    expected_ready_status_reason = (
        "Fleet package is closed and the weekly measured rollout loop is ready."
    )
    expected_blocked_status_reason = (
        "Fleet package is closed; measured rollout remains blocked by current "
        "source, dependency, or sibling gates."
    )
    expected_closeout_blocked_status_reason = (
        "Fleet package closeout is blocked; inspect package_verification issues "
        "before treating this slice as closed."
    )
    packet_loop_status = str(loop.get("loop_status") or "").strip()
    measured_loop_blocked = bool(package_complete) and packet_loop_status == "blocked"
    if source_input_blocked:
        _require(source_health.get("issues") != [], issues, "blocked source_input_health does not name its blocking issue")
        _require(packet.get("status") == "blocked", issues, "packet status is not blocked despite source input failure")
        _require(
            str(packet.get("status_reason") or "")
            == expected_blocked_status_reason,
            issues,
            "source-blocked packet status_reason no longer distinguishes closed package proof from rollout blockage",
        )
        source_issues = [str(issue) for issue in source_health.get("issues") or []]
        support_dependency_blocked = any(
            "support_packets successor_package_verification.status" in issue
            for issue in source_issues
        )
        expected_blocked_dependency_package_ids = (
            list(weekly.EXPECTED_SUPPORT_BLOCKED_DEPENDENCY_PACKAGE_IDS)
            if support_dependency_blocked
            else []
        )
        _require(
            package_closeout.get("blocked_dependency_package_ids")
            == expected_blocked_dependency_package_ids,
            issues,
            "package closeout blocked dependency package route list drifted",
        )
        _require(
            repeat_prevention.get("blocked_dependency_package_ids")
            == expected_blocked_dependency_package_ids,
            issues,
            "repeat prevention blocked dependency package route list drifted",
        )
        _require(
            loop.get("blocked_dependency_package_ids")
            == expected_blocked_dependency_package_ids,
            issues,
            "measured rollout loop blocked dependency package route list drifted",
        )
        if support_dependency_blocked:
            _require(
                weekly.SUPPORT_DEPENDENCY_PACKAGE_ID
                in (package_closeout.get("blocked_dependency_package_ids") or []),
                issues,
                "package closeout does not route blocked support-packet proof to the M102 dependency package",
            )
            _require(
                weekly.SUPPORT_DEPENDENCY_PACKAGE_ID
                in (repeat_prevention.get("blocked_dependency_package_ids") or []),
                issues,
                "repeat prevention does not route blocked support-packet proof to the M102 dependency package",
            )
            _require(
                weekly.SUPPORT_DEPENDENCY_PACKAGE_ID
                in (loop.get("blocked_dependency_package_ids") or []),
                issues,
                "measured rollout loop does not route blocked support-packet proof to the M102 dependency package",
            )
        _require(
            decision_board.get("current_launch_action") == "freeze_launch",
            issues,
            "source-blocked packet does not freeze launch",
        )
        _require(
            dict(decision_board.get("launch_expand") or {}).get("state") == "blocked",
            issues,
            "source-blocked packet does not block launch expansion",
        )
        _require(
            dict(decision_board.get("freeze_launch") or {}).get("state") == "active",
            issues,
            "source-blocked packet does not keep freeze_launch active",
        )
    elif measured_loop_blocked:
        _require(packet.get("status") == "blocked", issues, "packet status is not blocked despite measured rollout gates remaining open")
        _require(
            str(packet.get("status_reason") or "") == expected_blocked_status_reason,
            issues,
            "blocked packet status_reason no longer distinguishes closed package proof from rollout blockage",
        )
    elif not package_complete:
        _require(packet.get("status") == "blocked", issues, "packet status is not blocked despite package closeout failure")
        _require(
            str(packet.get("status_reason") or "") == expected_closeout_blocked_status_reason,
            issues,
            "package-closeout blocked packet status_reason no longer distinguishes blocked closeout from blocked rollout",
        )
    else:
        _require(packet.get("status") == "ready", issues, "packet status is not ready")
        _require(
            str(packet.get("status_reason") or "") == expected_ready_status_reason,
            issues,
            "ready packet status_reason no longer confirms closed package and ready measured rollout",
        )
    support_source_sha256 = str(support_input_health.get("source_sha256") or "").strip().lower()
    actual_support_source_sha256 = _sha256_file(support_packets_path)
    _require(
        bool(support_source_sha256),
        issues,
        "packet support_packets source_sha256 is missing",
    )
    _require(
        support_source_sha256 == actual_support_source_sha256,
        issues,
        "packet support_packets source_sha256 no longer matches SUPPORT_CASE_PACKETS.generated.json",
    )
    source_sha256_issues = _source_sha256_issues(
        required_inputs=required_inputs,
        source_paths=source_paths,
    )
    _require(
        not source_sha256_issues,
        issues,
        "packet source input hash proof drifted: " + "; ".join(source_sha256_issues),
    )
    expected_source_input_fingerprint = weekly._source_input_fingerprint(source_health)
    _require(
        dict(packet.get("source_input_fingerprint") or {})
        == expected_source_input_fingerprint,
        issues,
        "packet source_input_fingerprint no longer matches source_input_health hashes",
    )
    _require(
        expected_source_input_fingerprint.get("status") == "pass",
        issues,
        "packet source_input_fingerprint is not pass",
    )
    _require(
        weekly._coerce_int(expected_source_input_fingerprint.get("source_count"), 0)
        == len(weekly.EXPECTED_PRODUCTION_SOURCE_PATHS),
        issues,
        "packet source_input_fingerprint source count drifted",
    )
    _require(
        packet_verification == verification,
        issues,
        "packet package_verification no longer matches live successor registry and queue verification",
    )
    _require(packet_verification.get("status") == "pass", issues, "packet package_verification.status is not pass")
    _require(packet_verification.get("issues") == [], issues, "packet package_verification.issues is not empty")
    _require(packet_verification.get("package_id") == PACKAGE_ID, issues, "packet package_id drifted")
    _require(packet_verification.get("queue_frontier_id") == SUCCESSOR_FRONTIER_ID, issues, "packet queue_frontier_id drifted")
    _require(packet_verification.get("design_queue_frontier_id") == SUCCESSOR_FRONTIER_ID, issues, "packet design_queue_frontier_id drifted")
    _require(
        packet_verification.get("queue_landed_commit") == weekly.EXPECTED_LANDED_COMMIT,
        issues,
        "packet queue_landed_commit drifted",
    )
    _require(
        packet_verification.get("design_queue_landed_commit") == weekly.EXPECTED_LANDED_COMMIT,
        issues,
        "packet design_queue_landed_commit drifted",
    )
    _require(
        packet_verification.get("expected_landed_commit") == weekly.EXPECTED_LANDED_COMMIT,
        issues,
        "packet expected_landed_commit drifted",
    )
    _require(packet_verification.get("queue_mirror_status") == "in_sync", issues, "packet queue mirror is not in_sync")
    _require(
        required_resolving_paths == list(weekly.REQUIRED_RESOLVING_PROOF_PATHS),
        issues,
        "packet required_resolving_proof_paths drifted",
    )
    _require(
        packet_verification.get("local_proof_floor_commits")
        == list(weekly.LOCAL_PROOF_FLOOR_COMMITS),
        issues,
        "packet local proof floor commit list drifted",
    )
    _require(
        repeat_prevention.get("local_proof_floor_commits")
        == list(weekly.LOCAL_PROOF_FLOOR_COMMITS),
        issues,
        "repeat prevention local proof floor commit list drifted",
    )
    if (repo_root / ".git").exists():
        _require(
            local_commit_resolution.get("status") == "pass",
            issues,
            "packet local proof floor commit resolution is not pass",
        )
        for commit in weekly.LOCAL_PROOF_FLOOR_COMMITS:
            resolves = subprocess.run(
                ["git", "-C", str(repo_root), "cat-file", "-e", f"{commit}^{{commit}}"],
                check=False,
                capture_output=True,
                text=True,
            )
            _require(
                resolves.returncode == 0,
                issues,
                f"local proof floor commit {commit} no longer resolves in Fleet repo",
            )
    missing_resolving_paths = [
        marker
        for marker in weekly.REQUIRED_RESOLVING_PROOF_PATHS
        if not (repo_root / marker).is_file()
    ]
    _require(
        not missing_resolving_paths,
        issues,
        "packet resolving proof anchors no longer resolve: " + ", ".join(missing_resolving_paths),
    )
    missing_compile_artifacts = _compile_manifest_artifact_issues(
        repo_root=repo_root,
        packet_path=packet_path,
        markdown_path=markdown_path,
    )
    _require(
        not missing_compile_artifacts,
        issues,
        "compile manifest does not list weekly governor packet artifact(s): "
        + ", ".join(missing_compile_artifacts),
    )
    if source_input_blocked or measured_loop_blocked or not package_complete:
        _require(
            loop.get("loop_status") == "blocked",
            issues,
            "blocked packet measured rollout loop is not blocked",
        )
    else:
        _require(loop.get("loop_status") == "ready", issues, "measured rollout loop is not ready")
    _require(
        loop.get("launch_expansion_ready")
        == (dict(decision_board.get("launch_expand") or {}).get("state") == "allowed"),
        issues,
        "measured rollout loop launch_expansion_ready no longer matches launch_expand decision state",
    )
    launch_gate_rows = [
        row
        for row in decision_gate_ledger.get("launch_expand") or []
        if isinstance(row, dict)
    ]
    expected_blocking_gate_names = [
        str(row.get("name") or "").strip() or "unknown"
        for row in launch_gate_rows
        if str(row.get("state") or "unknown").strip() != "pass"
    ]
    expected_launch_gate_summary = {
        "gate_count": len(launch_gate_rows),
        "pass_count": sum(
            1 for row in launch_gate_rows if str(row.get("state") or "").strip() == "pass"
        ),
        "blocked_count": sum(
            1 for row in launch_gate_rows if str(row.get("state") or "").strip() == "blocked"
        ),
        "fail_count": sum(
            1 for row in launch_gate_rows if str(row.get("state") or "").strip() == "fail"
        ),
        "watch_count": sum(
            1 for row in launch_gate_rows if str(row.get("state") or "").strip() == "watch"
        ),
        "accumulating_count": sum(
            1 for row in launch_gate_rows if str(row.get("state") or "").strip() == "accumulating"
        ),
        "unknown_count": sum(
            1
            for row in launch_gate_rows
            if str(row.get("state") or "unknown").strip() == "unknown"
        ),
        "blocking_gate_names": expected_blocking_gate_names,
        "all_green": not expected_blocking_gate_names,
    }
    _require(
        launch_gate_summary == expected_launch_gate_summary,
        issues,
        "measured rollout launch_gate_summary no longer matches launch_expand gate ledger",
    )
    _require(
        launch_gate_summary.get("all_green") == bool(loop.get("launch_expansion_ready")),
        issues,
        "measured rollout launch_gate_summary all_green no longer matches launch expansion readiness",
    )
    _require(
        (loop.get("loop_status") == "ready") == bool(launch_gate_summary.get("all_green")),
        issues,
        "measured rollout loop_status no longer matches launch_gate_summary all_green",
    )
    weekly_adoption_gate = {}
    for row in decision_gate_ledger.get("launch_expand") or []:
        if isinstance(row, dict) and row.get("name") == "weekly_adoption_truth":
            weekly_adoption_gate = row
            break
    _require(
        bool(adoption_health),
        issues,
        "truth inputs no longer include weekly adoption_health",
    )
    _require(
        weekly_adoption_gate.get("required") == "present with measured history",
        issues,
        "launch gate ledger no longer requires weekly adoption truth with measured history",
    )
    _require(
        str(adoption_health.get("state") or "").strip() != "",
        issues,
        "weekly adoption_health state is missing",
    )
    _require(
        weekly._coerce_int(adoption_health.get("history_snapshot_count"), 0) > 0,
        issues,
        "weekly adoption_health history_snapshot_count is not measured",
    )
    _require(
        loop.get("freeze_active")
        == (dict(decision_board.get("freeze_launch") or {}).get("state") == "active"),
        issues,
        "measured rollout loop freeze_active no longer matches freeze_launch decision state",
    )
    _require(
        loop.get("canary_ready")
        == (dict(decision_board.get("canary") or {}).get("state") == "ready"),
        issues,
        "measured rollout loop canary_ready no longer matches canary decision state",
    )
    _require(
        loop.get("rollback_watch")
        == (dict(decision_board.get("rollback") or {}).get("state") == "watch"),
        issues,
        "measured rollout loop rollback_watch no longer matches rollback decision state",
    )
    if loop.get("launch_expansion_ready") is True:
        expected_public_state = "launch_expand_allowed"
        expected_public_headline = "Measured launch expansion is allowed."
        expected_public_body = (
            "Readiness, parity, support, canary, dependency, and release-proof gates "
            "are green for this weekly packet."
        )
    elif loop.get("rollback_watch") is True:
        expected_public_state = "freeze_with_rollback_watch"
        expected_public_headline = "Launch expansion is frozen with rollback watch active."
        expected_public_body = str(decision_board.get("current_launch_reason") or "").strip()
    else:
        expected_public_state = "freeze_launch"
        expected_public_headline = "Launch expansion remains frozen."
        expected_public_body = str(decision_board.get("current_launch_reason") or "").strip()
    _require(
        public_status_copy.get("state") == expected_public_state,
        issues,
        "public status copy state no longer matches measured rollout decision state",
    )
    _require(
        public_status_copy.get("headline") == expected_public_headline,
        issues,
        "public status copy headline no longer matches measured rollout decision state",
    )
    _require(
        public_status_copy.get("body") == expected_public_body,
        issues,
        "public status copy body no longer matches the current measured launch reason",
    )
    _require(
        public_status_copy.get("derived_from")
        == "measured_rollout_loop.decision_action_matrix",
        issues,
        "public status copy no longer names the measured rollout decision matrix as its source",
    )
    _require(
        public_status_copy.get("decision_actions") == required_decision_actions,
        issues,
        "public status copy decision action list no longer matches measured rollout required actions",
    )
    _require(
        required_decision_actions
        == list(weekly.REQUIRED_DECISION_ACTIONS),
        issues,
        "measured rollout loop required decision actions drifted",
    )
    missing_decision_board_actions = [
        action for action in required_decision_actions if action not in decision_board
    ]
    missing_decision_ledger_actions = [
        action for action in required_decision_actions if not decision_gate_ledger.get(action)
    ]
    if isinstance(governor_decisions, list):
        governor_decision_actions = {
            str(row.get("action") or "").strip()
            for row in governor_decisions
            if isinstance(row, dict)
        }
    else:
        governor_decision_actions = set()
    missing_governor_decision_actions = [
        action for action in required_decision_actions if action not in governor_decision_actions
    ]
    _require(
        not missing_decision_board_actions,
        issues,
        "decision board is missing required action(s): "
        + ", ".join(missing_decision_board_actions),
    )
    _require(
        not missing_decision_ledger_actions,
        issues,
        "decision gate ledger is missing required action(s): "
        + ", ".join(missing_decision_ledger_actions),
    )
    _require(
        not missing_governor_decision_actions,
        issues,
        "governor decision projection is missing required action(s): "
        + ", ".join(missing_governor_decision_actions),
    )
    if isinstance(decision_action_matrix, list):
        action_matrix_by_action = {
            str(row.get("action") or "").strip(): row
            for row in decision_action_matrix
            if isinstance(row, dict)
        }
    else:
        action_matrix_by_action = {}
    missing_action_matrix_rows = [
        action for action in required_decision_actions if action not in action_matrix_by_action
    ]
    incomplete_action_matrix_rows = [
        action
        for action in required_decision_actions
        if action in action_matrix_by_action
        and dict(action_matrix_by_action.get(action) or {}).get("complete") is not True
    ]
    inconsistent_action_matrix_rows = [
        action
        for action in required_decision_actions
        if action in action_matrix_by_action
        and dict(action_matrix_by_action.get(action) or {}).get("state_consistent") is not True
    ]
    gate_count_drift_action_matrix_rows = [
        action
        for action in required_decision_actions
        if action in action_matrix_by_action
        and dict(action_matrix_by_action.get(action) or {}).get("gate_count_consistent") is not True
    ]
    action_matrix_state_drift: List[str] = []
    governor_rows_by_action = {
        str(row.get("action") or "").strip(): row
        for row in governor_decisions
        if isinstance(row, dict)
    } if isinstance(governor_decisions, list) else {}
    for action in required_decision_actions:
        row = dict(action_matrix_by_action.get(action) or {})
        board = dict(decision_board.get(action) or {})
        ledger = decision_gate_ledger.get(action) or []
        governor = dict(governor_rows_by_action.get(action) or {})
        ledger_gate_count = len(ledger) if isinstance(ledger, list) else 0
        if not row:
            continue
        if row.get("board_state") != board.get("state"):
            action_matrix_state_drift.append(f"{action}.board_state")
        if row.get("ledger_gate_count") != ledger_gate_count:
            action_matrix_state_drift.append(f"{action}.ledger_gate_count")
        if row.get("governor_state") != governor.get("state"):
            action_matrix_state_drift.append(f"{action}.governor_state")
        if row.get("governor_gate_count") != governor.get("gate_count"):
            action_matrix_state_drift.append(f"{action}.governor_gate_count")
        expected_state_consistent = bool(
            str(board.get("state") or "").strip()
            and str(board.get("state") or "").strip()
            == str(governor.get("state") or "").strip()
        )
        expected_gate_count_consistent = bool(
            ledger_gate_count > 0
            and weekly._coerce_int(governor.get("gate_count"), -1) == ledger_gate_count
        )
        if row.get("state_consistent") is not expected_state_consistent:
            action_matrix_state_drift.append(f"{action}.state_consistent")
        if row.get("gate_count_consistent") is not expected_gate_count_consistent:
            action_matrix_state_drift.append(f"{action}.gate_count_consistent")
    _require(
        not missing_action_matrix_rows,
        issues,
        "decision action matrix is missing required action(s): "
        + ", ".join(missing_action_matrix_rows),
    )
    _require(
        not incomplete_action_matrix_rows,
        issues,
        "decision action matrix has incomplete required action row(s): "
        + ", ".join(incomplete_action_matrix_rows),
    )
    _require(
        not inconsistent_action_matrix_rows,
        issues,
        "decision action matrix has board/governor state drift for action(s): "
        + ", ".join(inconsistent_action_matrix_rows),
    )
    _require(
        not gate_count_drift_action_matrix_rows,
        issues,
        "decision action matrix has ledger/governor gate-count drift for action(s): "
        + ", ".join(gate_count_drift_action_matrix_rows),
    )
    _require(
        not action_matrix_state_drift,
        issues,
        "decision action matrix no longer matches board, ledger, and governor projection for field(s): "
        + ", ".join(action_matrix_state_drift),
    )
    expected_coverage_rows = []
    for action in weekly.REQUIRED_DECISION_ACTIONS:
        matrix_row = dict(action_matrix_by_action.get(action) or {})
        board_present = action in decision_board
        ledger_present = bool(decision_gate_ledger.get(action))
        governor_present = action in governor_rows_by_action
        matrix_complete = matrix_row.get("complete") is True
        expected_coverage_rows.append(
            {
                "action": action,
                "board_present": board_present,
                "ledger_present": ledger_present,
                "governor_present": governor_present,
                "matrix_complete": matrix_complete,
                "covered": bool(
                    board_present
                    and ledger_present
                    and governor_present
                    and matrix_complete
                ),
            }
        )
    expected_missing_coverage_actions = [
        row["action"]
        for row in expected_coverage_rows
        if not row["board_present"]
        or not row["ledger_present"]
        or not row["governor_present"]
    ]
    expected_incomplete_coverage_actions = [
        row["action"]
        for row in expected_coverage_rows
        if row["board_present"]
        and row["ledger_present"]
        and row["governor_present"]
        and not row["matrix_complete"]
    ]
    expected_decision_action_coverage = {
        "status": (
            "pass"
            if not expected_missing_coverage_actions
            and not expected_incomplete_coverage_actions
            else "fail"
        ),
        "required_actions": list(weekly.REQUIRED_DECISION_ACTIONS),
        "covered_action_count": sum(
            1 for row in expected_coverage_rows if row["covered"]
        ),
        "required_action_count": len(weekly.REQUIRED_DECISION_ACTIONS),
        "missing_actions": expected_missing_coverage_actions,
        "incomplete_actions": expected_incomplete_coverage_actions,
        "rows": expected_coverage_rows,
    }
    _require(
        decision_action_coverage == expected_decision_action_coverage,
        issues,
        "measured rollout decision_action_coverage no longer matches board, ledger, governor, and matrix coverage",
    )
    _require(
        decision_action_coverage.get("status") == "pass",
        issues,
        "measured rollout decision_action_coverage is not pass",
    )
    _require(
        decision_action_coverage.get("covered_action_count")
        == len(weekly.REQUIRED_DECISION_ACTIONS),
        issues,
        "measured rollout decision_action_coverage does not cover every required action",
    )
    expected_decision_source_coverage = weekly._decision_source_coverage(
        decision_board=decision_board,
        decision_gate_ledger=decision_gate_ledger,
    )
    _require(
        decision_source_coverage == expected_decision_source_coverage,
        issues,
        "measured rollout decision_source_coverage no longer matches required source gates",
    )
    _require(
        decision_source_coverage.get("status") == "pass",
        issues,
        "measured rollout decision_source_coverage is not pass",
    )
    _require(
        decision_source_coverage.get("covered_action_count")
        == len(weekly.REQUIRED_DECISION_ACTIONS),
        issues,
        "measured rollout decision_source_coverage does not cover every required action",
    )
    _require(
        decision_source_coverage.get("required_source_gates_by_action")
        == {
            action: list(gates)
            for action, gates in weekly.REQUIRED_DECISION_SOURCE_GATES.items()
        },
        issues,
        "measured rollout decision_source_coverage required gate map drifted",
    )
    expected_action_routes = weekly._decision_action_routes(
        decision_board=decision_board,
        decision_gate_ledger=decision_gate_ledger,
    )
    _require(
        decision_action_routes == expected_action_routes,
        issues,
        "measured rollout decision_action_routes no longer matches board and gate ledger routing",
    )
    _require(
        decision_action_routes.get("status") == "pass",
        issues,
        "measured rollout decision_action_routes is not pass",
    )
    _require(
        decision_action_routes.get("required_actions") == list(weekly.REQUIRED_DECISION_ACTIONS),
        issues,
        "measured rollout decision_action_routes required action list drifted",
    )
    _require(
        decision_action_routes.get("missing_actions") == [],
        issues,
        "measured rollout decision_action_routes is missing action route(s)",
    )
    _require(
        decision_action_routes.get("incomplete_actions") == [],
        issues,
        "measured rollout decision_action_routes has incomplete operator route(s)",
    )
    route_rows = [
        row for row in decision_action_routes.get("rows") or [] if isinstance(row, dict)
    ]
    missing_actionable_route_fields: List[str] = []
    route_operator_projection_drift: List[str] = []
    for row in route_rows:
        action = str(row.get("action") or "unknown").strip() or "unknown"
        for field in (
            "owner",
            "route",
            "cadence",
            "max_age_seconds",
            "freshness_policy",
            "trigger_gate",
            "unblock_condition",
            "operator_action_when_blocked",
            "operator_action_when_clear",
            "operator_action",
            "next_decision",
        ):
            if not str(row.get(field) or "").strip():
                missing_actionable_route_fields.append(f"{action}.{field}")
        ledger_rows = [
            item
            for item in decision_gate_ledger.get(action) or []
            if isinstance(item, dict)
        ]
        expected_gate_states = {
            str(item.get("name") or "").strip() or "unknown": str(
                item.get("state") or "unknown"
            ).strip()
            or "unknown"
            for item in ledger_rows
        }
        expected_blocking_gates = [
            str(item.get("name") or "").strip() or "unknown"
            for item in ledger_rows
            if str(item.get("state") or "unknown").strip() not in {"pass", "clear"}
        ]
        expected_route_blocked = bool(expected_blocking_gates) or str(
            dict(decision_board.get(action) or {}).get("state") or "unknown"
        ).strip() in {
            "active",
            "blocked",
            "accumulating",
            "watch",
        }
        if row.get("gate_states") != expected_gate_states:
            route_operator_projection_drift.append(f"{action}.gate_states")
        if row.get("blocking_gate_count") != len(expected_blocking_gates):
            route_operator_projection_drift.append(f"{action}.blocking_gate_count")
        if row.get("blocking_gates") != expected_blocking_gates:
            route_operator_projection_drift.append(f"{action}.blocking_gates")
        if row.get("route_blocked") is not expected_route_blocked:
            route_operator_projection_drift.append(f"{action}.route_blocked")
        if row.get("max_age_seconds") != weekly.WEEKLY_PACKET_CADENCE_SECONDS:
            route_operator_projection_drift.append(f"{action}.max_age_seconds")
        if (
            row.get("freshness_policy")
            != "refresh_before_operator_action_if_packet_is_overdue"
        ):
            route_operator_projection_drift.append(f"{action}.freshness_policy")
    _require(
        not missing_actionable_route_fields,
        issues,
        "measured rollout decision_action_routes missing operator-actionable field(s): "
        + ", ".join(missing_actionable_route_fields),
    )
    _require(
        not route_operator_projection_drift,
        issues,
        "measured rollout decision_action_routes no longer projects gate-state and blocking-count fields from the decision ledger: "
        + ", ".join(route_operator_projection_drift),
    )
    _require(
        all(str(row.get("cadence") or "").strip() == "weekly" for row in route_rows),
        issues,
        "measured rollout decision_action_routes cadence must remain weekly for every action",
    )
    expected_decision_receipts = weekly._decision_receipts(
        decision_action_matrix=decision_action_matrix,
        decision_action_routes=decision_action_routes,
    )
    _require(
        decision_receipts == expected_decision_receipts,
        issues,
        "measured rollout decision_receipts no longer match decision matrix and route projection",
    )
    _require(
        decision_receipts.get("status") == "pass",
        issues,
        "measured rollout decision_receipts is not pass",
    )
    _require(
        decision_receipts.get("required_actions") == list(weekly.REQUIRED_DECISION_ACTIONS),
        issues,
        "measured rollout decision_receipts required action list drifted",
    )
    receipt_rows = [
        row for row in decision_receipts.get("rows") or [] if isinstance(row, dict)
    ]
    receipt_rows_by_action = {
        str(row.get("action") or "").strip(): row for row in receipt_rows
    }
    missing_receipt_actions = [
        action
        for action in weekly.REQUIRED_DECISION_ACTIONS
        if action not in receipt_rows_by_action
    ]
    duplicate_receipt_count = len(receipt_rows) - len(receipt_rows_by_action)
    invalid_receipt_fields: List[str] = []
    receipt_ids = set()
    for action in weekly.REQUIRED_DECISION_ACTIONS:
        row = dict(receipt_rows_by_action.get(action) or {})
        route = dict(
            next(
                (
                    route_row
                    for route_row in route_rows
                    if str(route_row.get("action") or "").strip() == action
                ),
                {},
            )
        )
        if not row:
            continue
        receipt_id = str(row.get("receipt_id") or "").strip()
        receipt_sha = str(row.get("receipt_sha256") or "").strip()
        if not receipt_id.startswith(f"m106-{action}-"):
            invalid_receipt_fields.append(f"{action}.receipt_id")
        if len(receipt_sha) != 64 or any(ch not in "0123456789abcdef" for ch in receipt_sha):
            invalid_receipt_fields.append(f"{action}.receipt_sha256")
        if row.get("max_age_seconds") != weekly.WEEKLY_PACKET_CADENCE_SECONDS:
            invalid_receipt_fields.append(f"{action}.max_age_seconds")
        if (
            row.get("freshness_policy")
            != "refresh_before_operator_action_if_packet_is_overdue"
        ):
            invalid_receipt_fields.append(f"{action}.freshness_policy")
        if (
            not str(row.get("reason") or "").strip()
            or row.get("reason") != route.get("reason")
        ):
            invalid_receipt_fields.append(f"{action}.reason")
        if (
            not str(row.get("next_decision") or "").strip()
            or row.get("next_decision") != route.get("next_decision")
        ):
            invalid_receipt_fields.append(f"{action}.next_decision")
        if row.get("matrix_complete") is not True:
            invalid_receipt_fields.append(f"{action}.matrix_complete")
        if row.get("ready_for_operator_packet") is not True:
            invalid_receipt_fields.append(f"{action}.ready_for_operator_packet")
        if receipt_id in receipt_ids:
            invalid_receipt_fields.append(f"{action}.duplicate_receipt_id")
        receipt_ids.add(receipt_id)
    _require(
        not missing_receipt_actions,
        issues,
        "measured rollout decision_receipts is missing action receipt(s): "
        + ", ".join(missing_receipt_actions),
    )
    _require(
        duplicate_receipt_count == 0,
        issues,
        "measured rollout decision_receipts contains duplicate action rows",
    )
    _require(
        not invalid_receipt_fields,
        issues,
        "measured rollout decision_receipts has invalid receipt field(s): "
        + ", ".join(invalid_receipt_fields),
    )
    expected_operator_handoff = weekly._weekly_operator_handoff(
        schedule=schedule,
        launch_gate_summary=launch_gate_summary,
        decision_action_routes=decision_action_routes,
        decision_receipts=decision_receipts,
    )
    _require(
        weekly_operator_handoff == expected_operator_handoff,
        issues,
        "measured rollout weekly_operator_handoff no longer matches schedule, route, and receipt projection",
    )
    _require(
        weekly_operator_handoff.get("status") == "pass",
        issues,
        "measured rollout weekly_operator_handoff is not pass",
    )
    _require(
        weekly_operator_handoff.get("required_actions") == list(weekly.REQUIRED_DECISION_ACTIONS),
        issues,
        "measured rollout weekly_operator_handoff required action list drifted",
    )
    _require(
        weekly_operator_handoff.get("missing_actions") == [],
        issues,
        "measured rollout weekly_operator_handoff is missing action handoff row(s)",
    )
    _require(
        weekly_operator_handoff.get("incomplete_actions") == [],
        issues,
        "measured rollout weekly_operator_handoff has incomplete action handoff row(s)",
    )
    _require(
        weekly_operator_handoff.get("schedule_ref")
        == "governor_packet_schedule.next_packet_due_at",
        issues,
        "measured rollout weekly_operator_handoff schedule reference drifted",
    )
    _require(
        weekly_operator_handoff.get("source")
        == "measured_rollout_loop.decision_action_routes+decision_receipts",
        issues,
        "measured rollout weekly_operator_handoff source drifted",
    )
    handoff_rows = [
        row for row in weekly_operator_handoff.get("rows") or [] if isinstance(row, dict)
    ]
    handoff_rows_by_action = {
        str(row.get("action") or "").strip(): row for row in handoff_rows
    }
    invalid_handoff_fields: List[str] = []
    for action in weekly.REQUIRED_DECISION_ACTIONS:
        row = dict(handoff_rows_by_action.get(action) or {})
        if not row:
            invalid_handoff_fields.append(f"{action}.missing_row")
            continue
        route_row = dict(
            next(
                (
                    route
                    for route in route_rows
                    if str(route.get("action") or "").strip() == action
                ),
                {},
            )
        )
        receipt_row = dict(receipt_rows_by_action.get(action) or {})
        for field in (
            "state",
            "route",
            "operator_action",
            "receipt_id",
            "next_review_due_ref",
            "freshness_policy",
            "next_decision",
        ):
            if not str(row.get(field) or "").strip():
                invalid_handoff_fields.append(f"{action}.{field}")
        if row.get("route") != route_row.get("route"):
            invalid_handoff_fields.append(f"{action}.route")
        if row.get("operator_action") != route_row.get("operator_action"):
            invalid_handoff_fields.append(f"{action}.operator_action")
        if row.get("blocking_gates") != route_row.get("blocking_gates"):
            invalid_handoff_fields.append(f"{action}.blocking_gates")
        if row.get("blocking_gate_count") != route_row.get("blocking_gate_count"):
            invalid_handoff_fields.append(f"{action}.blocking_gate_count")
        if row.get("receipt_id") != receipt_row.get("receipt_id"):
            invalid_handoff_fields.append(f"{action}.receipt_id")
        if row.get("next_review_due_ref") != "governor_packet_schedule.next_packet_due_at":
            invalid_handoff_fields.append(f"{action}.next_review_due_ref")
        if row.get("max_age_seconds") != weekly.WEEKLY_PACKET_CADENCE_SECONDS:
            invalid_handoff_fields.append(f"{action}.max_age_seconds")
        if row.get("freshness_policy") != route_row.get("freshness_policy"):
            invalid_handoff_fields.append(f"{action}.freshness_policy")
    _require(
        not invalid_handoff_fields,
        issues,
        "measured rollout weekly_operator_handoff has invalid action handoff field(s): "
        + ", ".join(invalid_handoff_fields),
    )
    expected_dependency_routes = weekly._dependency_package_routes(
        dependency_posture=dependency_posture,
        design_queue=design_queue,
        queue=queue,
    )
    _require(
        dependency_package_routes == expected_dependency_routes,
        issues,
        "truth input successor_dependency_package_routes no longer matches registry and queue package routing",
    )
    _require(
        dict(loop.get("dependency_package_routes") or {}) == expected_dependency_routes,
        issues,
        "measured rollout dependency_package_routes no longer matches registry and queue package routing",
    )
    _require(
        dict(package_closeout.get("dependency_package_routes") or {}) == expected_dependency_routes,
        issues,
        "package closeout dependency_package_routes no longer matches registry and queue package routing",
    )
    _require(
        dict(repeat_prevention.get("dependency_package_routes") or {}) == expected_dependency_routes,
        issues,
        "repeat prevention dependency_package_routes no longer matches registry and queue package routing",
    )
    _require(
        dependency_package_routes.get("rule")
        == (
            "Closed dependency package rows are verified instead of reopened; "
            "launch expansion still waits for successor registry milestone status to close."
        ),
        issues,
        "dependency package route rule no longer prevents reopening closed predecessor packages",
    )
    dependency_route_rows = [
        row for row in dependency_package_routes.get("rows") or [] if isinstance(row, dict)
    ]
    _require(
        len(dependency_route_rows)
        == len(dependency_posture.get("dependencies") or []),
        issues,
        "dependency package route row count no longer matches successor dependency count",
    )
    missing_dependency_route_fields: List[str] = []
    for row in dependency_route_rows:
        milestone_id = row.get("milestone_id", "unknown")
        for field in (
            "package_id",
            "registry_status",
            "queue_status",
            "design_queue_status",
            "operator_route",
            "launch_gate_contribution",
        ):
            if not str(row.get(field) or "").strip():
                missing_dependency_route_fields.append(f"{milestone_id}.{field}")
    _require(
        not missing_dependency_route_fields,
        issues,
        "dependency package routes missing decision-facing field(s): "
        + ", ".join(missing_dependency_route_fields),
    )
    _require(
        package_closeout.get("status") == "fleet_package_complete",
        issues,
        "package closeout is not fleet_package_complete",
    )
    _require(
        package_closeout.get("do_not_reopen_package") is True,
        issues,
        "package closeout no longer marks this Fleet slice do-not-reopen",
    )
    _require(
        package_closeout.get("remaining_milestone_dependency_ids") == expected_remaining_dependencies,
        issues,
        "package closeout remaining dependency list no longer matches live successor registry posture",
    )
    expected_remaining_dependency_package_ids = weekly._remaining_dependency_package_ids(
        dependency_package_routes
    )
    _require(
        package_closeout.get("remaining_dependency_package_ids")
        == expected_remaining_dependency_package_ids,
        issues,
        "package closeout remaining dependency package list no longer matches dependency package routing",
    )
    _require(
        repeat_prevention.get("remaining_dependency_ids") == expected_remaining_dependencies,
        issues,
        "repeat prevention remaining dependency list no longer matches live successor registry posture",
    )
    _require(
        repeat_prevention.get("remaining_dependency_package_ids")
        == expected_remaining_dependency_package_ids,
        issues,
        "repeat prevention remaining dependency package list no longer matches dependency package routing",
    )
    _require(
        repeat_prevention.get("remaining_sibling_work_task_ids") == expected_remaining_siblings,
        issues,
        "repeat prevention remaining sibling list no longer matches package closeout posture",
    )
    _require(
        package_closeout.get("remaining_sibling_work_task_ids") == expected_remaining_siblings,
        issues,
        "package closeout remaining sibling list no longer matches live successor registry posture",
    )
    _require(
        loop.get("remaining_dependency_package_ids") == expected_remaining_dependency_package_ids,
        issues,
        "measured rollout loop remaining dependency package list no longer matches dependency package routing",
    )
    _require(
        "route remaining M106 work" in str(repeat_prevention.get("handoff_rule") or ""),
        issues,
        "repeat prevention handoff rule no longer routes remaining M106 work away from this closed Fleet slice",
    )
    _require(
        repeat_prevention.get("handoff_rule") == live_repeat_prevention.get("handoff_rule"),
        issues,
        "repeat prevention handoff rule no longer matches the live closeout projection",
    )
    _require(repeat_prevention.get("status") == "closed_for_fleet_package", issues, "repeat prevention is not closed_for_fleet_package")
    _require(repeat_prevention.get("do_not_reopen_owned_surfaces") is True, issues, "owned surfaces are not protected from reopen")
    _require(
        repeat_prevention.get("closed_successor_frontier_ids") == [SUCCESSOR_FRONTIER_ID],
        issues,
        "repeat prevention successor frontier pin drifted",
    )
    _require(
        worker_command_guard.get("status") == "active_run_helpers_forbidden",
        issues,
        "repeat prevention worker command guard is not active_run_helpers_forbidden",
    )
    _require(
        worker_command_guard.get("blocked_markers")
        == list(weekly.DISALLOWED_WORKER_PROOF_COMMAND_MARKERS),
        issues,
        "repeat prevention worker command guard blocked marker list drifted",
    )
    _require(
        "repo-local files" in str(worker_command_guard.get("rule") or ""),
        issues,
        "repeat prevention worker command guard rule no longer requires repo-local proof",
    )
    _require(
        "operator telemetry" in str(worker_command_guard.get("rule") or "")
        and "supervisor helper loops" in str(worker_command_guard.get("rule") or "")
        and "supervisor status/ETA helpers" in str(worker_command_guard.get("rule") or "")
        and "active-run helper commands" in str(worker_command_guard.get("rule") or ""),
        issues,
        "repeat prevention worker command guard rule no longer forbids operator telemetry, supervisor helper loops, supervisor status/ETA helpers, and active-run helper commands",
    )
    _require(
        "hard-blocked" in str(worker_command_guard.get("rule") or "")
        and "run failure" in str(worker_command_guard.get("rule") or "")
        and "non-zero during active runs" in str(worker_command_guard.get("rule") or ""),
        issues,
        "repeat prevention worker command guard rule no longer records hard-blocked run-failure helper posture",
    )
    _require(
        flagship_wave_guard.get("status") == "closed_wave_not_reopened",
        issues,
        "repeat prevention flagship wave guard is not closed_wave_not_reopened",
    )
    _require(
        flagship_wave_guard.get("closed_wave") == weekly.CLOSED_FLAGSHIP_WAVE,
        issues,
        "repeat prevention flagship wave guard closed wave drifted",
    )
    _require(
        flagship_wave_guard.get("closed_registry_status") == "complete",
        issues,
        "repeat prevention flagship wave guard no longer proves the closed registry is complete",
    )
    _require(
        flagship_wave_guard.get("closed_registry_path") == str(closed_flagship_registry_path),
        issues,
        "repeat prevention flagship wave guard closed registry path drifted",
    )
    _require(
        closed_flagship_input.get("status") == "complete",
        issues,
        "source input health no longer proves the closed flagship registry status is complete",
    )
    _require(
        closed_flagship_input.get("program_wave") == weekly.CLOSED_FLAGSHIP_WAVE,
        issues,
        "source input health no longer pins the closed flagship registry wave",
    )
    _require(
        closed_flagship_input.get("open_wave_ids") == [],
        issues,
        "closed flagship registry input reports reopened wave ids",
    )
    _require(
        closed_flagship_input.get("open_milestone_ids") == [],
        issues,
        "closed flagship registry input reports reopened milestone ids",
    )
    _require(
        source_path_authority.get("state") == "pass",
        issues,
        "source input health no longer proves canonical production source path authority",
    )
    _require(
        "must not reopen" in str(flagship_wave_guard.get("rule") or ""),
        issues,
        "repeat prevention flagship wave guard rule no longer blocks reopening the closed flagship wave",
    )
    required_packet_markers = packet_verification.get("required_queue_proof_markers") or []
    _require(
        "/docker/fleet/scripts/verify_next90_m106_fleet_governor_packet.py" in required_packet_markers,
        issues,
        "packet does not require the M106 verifier script proof marker",
    )
    for marker in weekly.REQUIRED_RESOLVING_PROOF_PATHS:
        _require(
            f"/docker/fleet/{marker}" in required_packet_markers,
            issues,
            f"packet does not require resolving source proof marker {marker}",
        )
    _require(
        "python3 scripts/verify_next90_m106_fleet_governor_packet.py exits 0" in required_packet_markers,
        issues,
        "packet does not require the M106 verifier command receipt",
    )
    _require("- Status: closed_for_fleet_package" in markdown, issues, "markdown repeat-prevention status is missing")
    _require(
        f"- Next packet due: {schedule.get('next_packet_due_at')}" in markdown,
        issues,
        "markdown weekly packet schedule due date is missing",
    )
    _require(
        "- Closed successor frontier ids: 2376135131" in markdown,
        issues,
        "markdown successor frontier closeout pin is missing",
    )
    _require(
        _markdown_local_proof_floor_line() in markdown,
        issues,
        "markdown local proof floor commit pin is missing",
    )
    _require(
        "- Flagship wave guard: closed_wave_not_reopened" in markdown,
        issues,
        "markdown flagship wave guard is missing",
    )
    _require(
        "- Closed flagship wave: next_12_biggest_wins" in markdown,
        issues,
        "markdown closed flagship wave pin is missing",
    )
    return issues


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        issues = verify(args)
    except AssertionError as exc:
        issues = [str(exc)]
    if issues:
        for issue in issues:
            print(f"next90-m106 verifier failed: {issue}", file=sys.stderr)
        return 1
    print("verified next90-m106-fleet-governor-packet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
