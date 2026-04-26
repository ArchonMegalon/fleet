#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

try:
    from scripts.materialize_next90_m111_fleet_install_aware_followthrough import (
        DEFAULT_OUTPUT,
        PACKAGE_ID,
        build_payload,
    )
except ModuleNotFoundError:
    from materialize_next90_m111_fleet_install_aware_followthrough import (
        DEFAULT_OUTPUT,
        PACKAGE_ID,
        build_payload,
    )


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify the Fleet M111 install-aware followthrough gate against published support, "
            "governor, pulse, progress, registry, and queue truth."
        )
    )
    parser.add_argument("--artifact", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--support-packets", required=True)
    parser.add_argument("--weekly-governor-packet", required=True)
    parser.add_argument("--weekly-product-pulse", required=True)
    parser.add_argument("--progress-report", required=True)
    parser.add_argument("--successor-registry", required=True)
    parser.add_argument("--queue-staging", required=True)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _compare_issue(issues: List[str], actual: Dict[str, Any], expected: Dict[str, Any], key: str, message: str) -> None:
    if actual.get(key) != expected.get(key):
        issues.append(message)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    artifact_path = Path(args.artifact).resolve()
    actual = _read_json(artifact_path)
    issues: List[str] = []

    if not actual:
        issues.append(f"generated artifact is missing or invalid: {artifact_path}")
    else:
        expected = build_payload(
            support_packets_path=Path(args.support_packets).resolve(),
            weekly_governor_packet_path=Path(args.weekly_governor_packet).resolve(),
            weekly_product_pulse_path=Path(args.weekly_product_pulse).resolve(),
            progress_report_path=Path(args.progress_report).resolve(),
            registry_path=Path(args.successor_registry).resolve(),
            queue_path=Path(args.queue_staging).resolve(),
            generated_at=str(actual.get("generated_at") or "").strip() or None,
        )

        if actual.get("contract_name") != "fleet.install_aware_followthrough_gate":
            issues.append("generated artifact contract_name is missing or unexpected")
        if actual.get("package_id") != PACKAGE_ID:
            issues.append("generated artifact package_id drifted from the assigned Fleet M111 package")

        _compare_issue(
            issues,
            actual,
            expected,
            "queue_title",
            "queue title drifted from the canonical M111 Fleet package row",
        )
        _compare_issue(
            issues,
            actual,
            expected,
            "registry_work_task_title",
            "registry work-task title drifted from milestone 111.4",
        )
        _compare_issue(
            issues,
            actual,
            expected,
            "support_receipt_truth",
            "support receipt truth no longer matches the published install-aware support packet",
        )
        _compare_issue(
            issues,
            actual,
            expected,
            "launch_truth",
            "launch truth no longer matches the published governor packet and weekly pulse",
        )
        _compare_issue(
            issues,
            actual,
            expected,
            "publication_refs",
            "publication refs no longer match the promoted support, governor, pulse, and progress artifacts",
        )
        _compare_issue(
            issues,
            actual,
            expected,
            "agreement",
            "agreement summary no longer matches recomputed install-aware receipt and publication-ref truth",
        )
        _compare_issue(
            issues,
            actual,
            expected,
            "kill_switch_posture",
            "kill-switch posture no longer matches the weekly governor decision board",
        )
        _compare_issue(
            issues,
            actual,
            expected,
            "gates",
            "followthrough gate state no longer matches recomputed receipt and publication-ref truth",
        )
        agreement = actual.get("agreement") if isinstance(actual.get("agreement"), dict) else {}
        if not agreement.get("queue_scope_matches_package"):
            issues.append("canonical Fleet queue scope no longer matches the assigned M111 package contract")
        if not agreement.get("registry_scope_matches_package"):
            issues.append("canonical successor registry scope no longer matches the assigned M111 work-task contract")
        if not agreement.get("queue_closure_matches_package"):
            issues.append("canonical Fleet queue closure metadata no longer matches the assigned M111 package contract")
        if not agreement.get("registry_closure_matches_package"):
            issues.append("canonical successor registry closure metadata no longer matches the assigned M111 work-task contract")

    result = {
        "status": "pass" if not issues else "fail",
        "artifact": str(artifact_path),
        "issues": issues,
    }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif issues:
        print("M111 install-aware followthrough verifier failed:", file=sys.stderr)
        for issue in issues:
            print(f" - {issue}", file=sys.stderr)
    else:
        print("M111 install-aware followthrough verifier passed")

    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
