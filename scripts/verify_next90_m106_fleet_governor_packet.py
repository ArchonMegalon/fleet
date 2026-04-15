#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
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
        weekly_pulse=weekly._read_json(weekly_pulse_path),
        flagship_readiness=weekly._read_json(flagship_readiness_path),
        journey_gates=weekly._read_json(journey_gates_path),
        support_packets=weekly._read_json(support_packets_path),
        status_plane=weekly._read_yaml(status_plane_path),
        source_paths=source_paths,
    )
    packet_verification = dict(packet.get("package_verification") or {})
    repeat_prevention = dict(packet.get("repeat_prevention") or {})
    loop = dict(packet.get("measured_rollout_loop") or {})
    packet_projection = _decision_projection(packet)
    live_projection = _decision_projection(live_payload)
    projection_drift = _projection_drift(live_projection, packet_projection)

    _require(verification["status"] == "pass", issues, f"live package verification is not pass: {verification['issues']}")
    _require(
        not projection_drift,
        issues,
        "checked-in packet decision ledger no longer matches live source inputs for field(s): "
        + ", ".join(projection_drift),
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
    _require(loop.get("loop_status") == "ready", issues, "measured rollout loop is not ready")
    _require(repeat_prevention.get("status") == "closed_for_fleet_package", issues, "repeat prevention is not closed_for_fleet_package")
    _require(repeat_prevention.get("do_not_reopen_owned_surfaces") is True, issues, "owned surfaces are not protected from reopen")
    _require(
        repeat_prevention.get("closed_successor_frontier_ids") == [SUCCESSOR_FRONTIER_ID],
        issues,
        "repeat prevention successor frontier pin drifted",
    )
    required_packet_markers = packet_verification.get("required_queue_proof_markers") or []
    _require(
        "/docker/fleet/scripts/verify_next90_m106_fleet_governor_packet.py" in required_packet_markers,
        issues,
        "packet does not require the M106 verifier script proof marker",
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
