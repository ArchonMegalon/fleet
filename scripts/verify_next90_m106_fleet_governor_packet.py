#!/usr/bin/env python3
from __future__ import annotations

import argparse
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
        "Generated: <ignored>" if line.startswith("Generated: ") else line
        for line in lines
    )


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


def verify(args: argparse.Namespace) -> List[str]:
    repo_root = Path(args.repo_root).resolve()
    packet_path = Path(args.packet).resolve()
    markdown_path = Path(args.markdown).resolve()
    registry_path = Path(args.successor_registry).resolve()
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
        "design_queue_staging": str(design_queue_path),
        "queue_staging": str(queue_path),
        "weekly_pulse": str(weekly_pulse_path),
        "flagship_readiness": str(flagship_readiness_path),
        "journey_gates": str(journey_gates_path),
        "support_packets": str(support_packets_path),
        "status_plane": str(status_plane_path),
    }
    live_payload = weekly.build_payload(
        repo_root=repo_root,
        registry=registry,
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
    local_commit_resolution = dict(packet_verification.get("local_commit_resolution") or {})
    package_closeout = dict(packet.get("package_closeout") or {})
    loop = dict(packet.get("measured_rollout_loop") or {})
    decision_board = dict(packet.get("decision_board") or {})
    decision_gate_ledger = dict(packet.get("decision_gate_ledger") or {})
    governor_decisions = packet.get("governor_decisions") or []
    required_resolving_paths = packet_verification.get("required_resolving_proof_paths") or []
    required_decision_actions = loop.get("required_decision_actions") or []
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
    _require(packet.get("status") == "ready", issues, "packet status is not ready")
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
    _require(loop.get("loop_status") == "ready", issues, "measured rollout loop is not ready")
    _require(
        required_decision_actions
        == ["launch_expand", "freeze_launch", "canary", "rollback", "focus_shift"],
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
    _require(
        repeat_prevention.get("remaining_dependency_ids") == expected_remaining_dependencies,
        issues,
        "repeat prevention remaining dependency list no longer matches live successor registry posture",
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
        "- Closed successor frontier ids: 2376135131" in markdown,
        issues,
        "markdown successor frontier closeout pin is missing",
    )
    _require(
        "- Local proof floor commits: 065c653, fb47ce8, 5e6a468" in markdown,
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
