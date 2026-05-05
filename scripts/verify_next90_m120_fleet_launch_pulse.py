#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

try:
    from scripts.materialize_next90_m120_fleet_launch_pulse import (
        DEFAULT_OUTPUT,
        PACKAGE_ID,
        build_payload,
    )
except ModuleNotFoundError:
    from materialize_next90_m120_fleet_launch_pulse import (
        DEFAULT_OUTPUT,
        PACKAGE_ID,
        build_payload,
    )


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify the Fleet M120 launch-pulse and public followthrough packet against governed release truth "
            "for queue alignment, launch/action truth, and publication-link stability."
        )
    )
    parser.add_argument("--artifact", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--successor-registry", required=True)
    parser.add_argument("--queue-staging", required=True)
    parser.add_argument("--design-queue-staging", required=True)
    parser.add_argument("--weekly-governor-packet", required=True)
    parser.add_argument("--weekly-product-pulse", required=True)
    parser.add_argument("--support-packets", required=True)
    parser.add_argument("--progress-report", required=True)
    parser.add_argument("--flagship-readiness", required=True)
    parser.add_argument("--journey-gates", required=True)
    parser.add_argument("--proof-orchestration", required=True)
    parser.add_argument("--status-plane", required=True)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _compare_issue(issues: List[str], expected: Any, actual: Any, message: str) -> None:
    if expected != actual:
        issues.append(f"{message} (expected={expected!r}, actual={actual!r})")


def _get_nested(value: Dict[str, Any], key: str) -> Any:
    current: Any = value
    for part in key.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _compare_launch_pulse(issues: List[str], expected: Dict[str, Any], actual: Dict[str, Any]) -> None:
    for key in (
        "state",
        "alignment_ok",
        "governor_action",
        "pulse_action",
        "decision_alignment.actual_action",
        "decision_alignment.expected_action",
        "decision_alignment.status",
    ):
        _compare_issue(issues, _get_nested(expected, key), _get_nested(actual, key), f"launch_pulse {key} drifted")


def _compare_adoption_support(issues: List[str], expected: Dict[str, Any], actual: Dict[str, Any], source: str) -> None:
    for key in ("state", "raw_state"):
        if source in {"adoption_health", "support_risk"}:
            _compare_issue(issues, expected.get(key), actual.get(key), f"{source} {key} drifted")


def _compare_payload_status_rows(
    issues: List[str],
    expected: Dict[str, Any],
    actual: Dict[str, Any],
    key: str,
    focus_fields: tuple[str, ...],
) -> None:
    expected_rows = expected if isinstance(expected, dict) else {}
    actual_rows = actual if isinstance(actual, dict) else {}
    for row_key in expected_rows:
        expected_row = expected_rows.get(row_key, {})
        actual_row = actual_rows.get(row_key, {})
        for field in focus_fields:
            _compare_issue(
                issues,
                expected_row.get(field),
                actual_row.get(field),
                f"{key}::{row_key}.{field} drifted",
            )


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    artifact_path = Path(args.artifact)
    actual = _read_json(artifact_path)
    issues: List[str] = []

    if not actual:
        issues.append(f"generated artifact is missing or invalid: {artifact_path}")
    else:
        expected = build_payload(
            registry_path=Path(args.successor_registry),
            queue_path=Path(args.queue_staging),
            design_queue_path=Path(args.design_queue_staging),
            weekly_governor_packet_path=Path(args.weekly_governor_packet),
            weekly_product_pulse_path=Path(args.weekly_product_pulse),
            support_packets_path=Path(args.support_packets),
            progress_report_path=Path(args.progress_report),
            flagship_readiness_path=Path(args.flagship_readiness),
            journey_gates_path=Path(args.journey_gates),
            proof_orchestration_path=Path(args.proof_orchestration),
            status_plane_path=Path(args.status_plane),
            generated_at=str(actual.get("generated_at") or ""),
        )

        for field in [
            ("contract_name", "fleet.next90_m120_launch_pulse", "contract_name changed"),
            ("package_id", PACKAGE_ID, "package_id changed from the assigned M120 Fleet package"),
            ("frontier_id", 2614855152, "frontier id drifted from m120 frontier contract"),
            ("milestone_id", 120, "milestone id drifted from m120 task ownership"),
            ("work_task_id", "120.3", "work task id drifted from next90-m120-fleet-launch-pulse"),
            ("wave_id", "W14", "wave id drifted from m120 package definition"),
            ("queue_title", "Compile launch pulse and adoption health into governor packets", "queue title drifted"),
            ("queue_task", (
                "Produce launch pulse, adoption health, support risk, proof freshness, "
                "and public followthrough packets from governed release truth."
            ), "queue task drifted"),
        ]:
            expected_value, actual_value = expected.get(field[0]), actual.get(field[0])
            if expected_value != actual_value:
                issues.append(f"{field[2]} (expected={expected_value!r}, actual={actual_value!r})")

        # Ensure queue and registry scope agreements still bind back to this package.
        agreement = actual.get("agreement") if isinstance(actual.get("agreement"), dict) else {}
        if not agreement.get("queue_scope_matches_package"):
            issues.append("queue scope agreement indicates package drift")
        if not agreement.get("registry_scope_matches_package"):
            issues.append("registry scope agreement indicates package drift")
        if not agreement.get("registry_closure_matches_package"):
            issues.append("registry closure agreement does not match the source package closure")
        if not agreement.get("queue_closure_matches_package"):
            issues.append("queue closure agreement does not match the source package closure")

        _compare_launch_pulse(issues, expected.get("launch_pulse", {}), actual.get("launch_pulse", {}))
        _compare_adoption_support(issues, expected.get("adoption_health", {}), actual.get("adoption_health", {}), "adoption_health")
        _compare_adoption_support(issues, expected.get("support_risk", {}), actual.get("support_risk", {}), "support_risk")
        _compare_issue(
            issues,
            expected.get("proof_freshness", {}).get("state"),
            actual.get("proof_freshness", {}).get("state"),
            "proof_freshness state drifted",
        )
        _compare_issue(
            issues,
            expected.get("proof_freshness", {}).get("missing_input_count"),
            actual.get("proof_freshness", {}).get("missing_input_count"),
            "proof_freshness missing_input_count drifted",
        )
        _compare_issue(
            issues,
            expected.get("proof_freshness", {}).get("stale_input_count"),
            actual.get("proof_freshness", {}).get("stale_input_count"),
            "proof_freshness stale_input_count drifted",
        )
        _compare_issue(
            issues,
            expected.get("public_followthrough", {}).get("state"),
            actual.get("public_followthrough", {}).get("state"),
            "public_followthrough state drifted",
        )

        _compare_payload_status_rows(
            issues,
            expected.get("source_packet_links", {}),
            actual.get("source_packet_links", {}),
            "source_packet_links",
            ("contract_name", "current_launch_action", "pulse_action"),
        )
        _compare_payload_status_rows(
            issues,
            expected.get("source_input_health", {}),
            actual.get("source_input_health", {}),
            "source_input_health",
            ("exists", "status", "state"),
        )

    result = {
        "status": "pass" if not issues else "fail",
        "artifact": str(artifact_path),
        "issues": issues,
    }

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif issues:
        print("M120 launch-pulse verifier failed:", file=sys.stderr)
        for issue in issues:
            print(f" - {issue}", file=sys.stderr)
    else:
        print("M120 launch-pulse verifier passed")

    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
