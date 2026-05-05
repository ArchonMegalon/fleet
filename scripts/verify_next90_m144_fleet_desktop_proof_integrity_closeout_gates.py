#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

try:
    from scripts.materialize_next90_m144_fleet_desktop_proof_integrity_closeout_gates import (
        DEFAULT_OUTPUT,
        DESKTOP_EXECUTABLE_EXIT_GATE,
        DESIGN_QUEUE_STAGING,
        FLEET_QUEUE_STAGING,
        FLAGSHIP_READINESS,
        NEXT90_GUIDE,
        RELEASE_CHANNEL,
        SUCCESSOR_REGISTRY,
        UI_WINDOWS_EXIT_GATE,
        build_payload,
    )
except ModuleNotFoundError:
    script_dir = Path(__file__).resolve().parent
    if str(script_dir) not in sys.path:
        sys.path.insert(0, str(script_dir))
    from materialize_next90_m144_fleet_desktop_proof_integrity_closeout_gates import (  # type: ignore
        DEFAULT_OUTPUT,
        DESKTOP_EXECUTABLE_EXIT_GATE,
        DESIGN_QUEUE_STAGING,
        FLEET_QUEUE_STAGING,
        FLAGSHIP_READINESS,
        NEXT90_GUIDE,
        RELEASE_CHANNEL,
        SUCCESSOR_REGISTRY,
        UI_WINDOWS_EXIT_GATE,
        build_payload,
    )


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify the Fleet M144 desktop proof integrity closeout gate packet.")
    parser.add_argument("--artifact", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--fleet-queue-staging", default=str(FLEET_QUEUE_STAGING))
    parser.add_argument("--design-queue-staging", default=str(DESIGN_QUEUE_STAGING))
    parser.add_argument("--next90-guide", default=str(NEXT90_GUIDE))
    parser.add_argument("--flagship-readiness", default=str(FLAGSHIP_READINESS))
    parser.add_argument("--ui-windows-exit-gate", default=str(UI_WINDOWS_EXIT_GATE))
    parser.add_argument("--desktop-executable-exit-gate", default=str(DESKTOP_EXECUTABLE_EXIT_GATE))
    parser.add_argument("--release-channel", default=str(RELEASE_CHANNEL))
    parser.add_argument("--startup-smoke-receipt", default="")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def verify(args: argparse.Namespace) -> Dict[str, Any]:
    artifact_path = Path(args.artifact).resolve()
    actual = _load_json(artifact_path)
    startup_smoke_receipt_path = Path(args.startup_smoke_receipt).resolve() if str(args.startup_smoke_receipt or "").strip() else None
    expected = build_payload(
        registry_path=Path(args.successor_registry).resolve(),
        fleet_queue_path=Path(args.fleet_queue_staging).resolve(),
        design_queue_path=Path(args.design_queue_staging).resolve(),
        next90_guide_path=Path(args.next90_guide).resolve(),
        flagship_readiness_path=Path(args.flagship_readiness).resolve(),
        ui_windows_exit_gate_path=Path(args.ui_windows_exit_gate).resolve(),
        desktop_executable_exit_gate_path=Path(args.desktop_executable_exit_gate).resolve(),
        release_channel_path=Path(args.release_channel).resolve(),
        startup_smoke_receipt_path=startup_smoke_receipt_path,
        generated_at=str(actual.get("generated_at") or ""),
    )

    issues: List[str] = []
    if not actual:
        issues.append("generated artifact is missing or invalid JSON")
    else:
        if actual.get("contract_name") != "fleet.next90_m144_desktop_proof_integrity_closeout_gates":
            issues.append("generated artifact contract_name drifted from the assigned Fleet M144 packet")
        if actual.get("package_id") != "next90-m144-fleet-fail-closeout-when-desktop-client-readiness-is-green-without-matching":
            issues.append("generated artifact package_id drifted from the assigned Fleet M144 package")
        for field, message in (
            ("status", "closeout-gate status drifted from recomputed M144 truth"),
            ("canonical_monitors", "canonical monitors drifted from recomputed M144 truth"),
            ("runtime_monitors", "runtime monitors drifted from recomputed M144 truth"),
            ("monitor_summary", "monitor summary drifted from recomputed M144 truth"),
            ("package_closeout", "package closeout drifted from recomputed M144 truth"),
        ):
            if actual.get(field) != expected.get(field):
                issues.append(message)

    return {"artifact": str(artifact_path), "issues": issues, "status": "pass" if not issues else "fail"}


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    payload = verify(args)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif payload["status"] != "pass":
        print("M144 desktop proof integrity closeout gate verifier failed:", file=sys.stderr)
        for issue in payload["issues"]:
            print(f"- {issue}", file=sys.stderr)
    else:
        print("M144 desktop proof integrity closeout gate verifier passed")
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
