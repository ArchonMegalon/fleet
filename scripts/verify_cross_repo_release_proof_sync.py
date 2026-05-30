#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PASS_STATES = {"pass", "passed", "ready", "published", "public_stable"}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify that EA, fleet, hub-registry, UI, and mobile release-proof artifacts agree "
            "with each other and with the exact checked-out repository heads."
        )
    )
    parser.add_argument("--fleet-root", type=Path, default=Path("."))
    parser.add_argument("--ea-root", type=Path, required=True)
    parser.add_argument("--hub-registry-root", type=Path, required=True)
    parser.add_argument("--ui-root", type=Path, required=True)
    parser.add_argument("--mobile-root", type=Path, required=True)
    parser.add_argument(
        "--mobile-proof",
        type=Path,
        default=None,
        help="Optional explicit mobile local release proof path. Defaults to <mobile-root>/.codex-studio/published/MOBILE_LOCAL_RELEASE_PROOF.generated.json",
    )
    parser.add_argument(
        "--max-mobile-proof-age-hours",
        type=int,
        default=48,
        help="Fail when the mobile proof is older than this many hours.",
    )
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def _load_json(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise AssertionError(f"{label} not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AssertionError(f"{label} root must be a JSON object: {path}")
    return payload


def _git_head(root: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _state(value: Any) -> str:
    return str(value or "").strip().lower()


def _parse_iso(value: Any, *, label: str) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise AssertionError(f"{label} is missing")
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise AssertionError(f"{label} is not a valid ISO timestamp: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _assert(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def _verify(args: argparse.Namespace) -> dict[str, Any]:
    fleet_root = args.fleet_root.resolve()
    ea_root = args.ea_root.resolve()
    hub_root = args.hub_registry_root.resolve()
    ui_root = args.ui_root.resolve()
    mobile_root = args.mobile_root.resolve()
    mobile_proof_path = (
        args.mobile_proof.resolve()
        if args.mobile_proof is not None
        else (mobile_root / ".codex-studio" / "published" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json").resolve()
    )

    fleet_head = _git_head(fleet_root)
    ea_head = _git_head(ea_root)
    hub_head = _git_head(hub_root)
    ui_head = _git_head(ui_root)
    mobile_head = _git_head(mobile_root)

    pulse = _load_json(
        ea_root / ".codex-design" / "product" / "WEEKLY_PRODUCT_PULSE.generated.json",
        label="EA weekly product pulse",
    )
    gate = _load_json(
        ea_root / ".codex-design" / "product" / "EA_FLAGSHIP_RELEASE_GATE.generated.json",
        label="EA flagship release gate",
    )
    journey_gates = _load_json(
        fleet_root / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json",
        label="fleet journey gates",
    )
    readiness = _load_json(
        fleet_root / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json",
        label="fleet flagship readiness",
    )
    release_channel = _load_json(
        hub_root / ".codex-studio" / "published" / "RELEASE_CHANNEL.generated.json",
        label="hub-registry release channel",
    )
    ui_local_release = _load_json(
        ui_root / ".codex-studio" / "published" / "UI_LOCAL_RELEASE_PROOF.generated.json",
        label="UI local release proof",
    )
    ui_exec_gate = _load_json(
        ui_root / ".codex-studio" / "published" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json",
        label="UI desktop executable exit gate",
    )
    ui_windows_gate = _load_json(
        ui_root / ".codex-studio" / "published" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json",
        label="UI windows desktop exit gate",
    )
    ui_macos_gate = _load_json(
        ui_root / ".codex-studio" / "published" / "UI_MACOS_AVALONIA_OSX_ARM64_DESKTOP_EXIT_GATE.generated.json",
        label="UI macOS desktop exit gate",
    )
    mobile_proof = _load_json(mobile_proof_path, label="mobile local release proof")

    failures: list[str] = []

    supporting = pulse.get("supporting_signals") or {}
    pulse_governor_decisions = pulse.get("governor_decisions") or []
    pulse_clusters = pulse.get("top_support_or_feedback_clusters") or []
    pulse_release_provenance = pulse.get("release_truth_provenance") or {}
    pulse_journey_provenance = pulse.get("journey_gate_provenance") or {}
    journey_summary = journey_gates.get("summary") or {}
    tuple_coverage = release_channel.get("desktopTupleCoverage") or {}
    external_host_proof = readiness.get("external_host_proof") or {}
    completion_audit = readiness.get("completion_audit") or {}
    windows_checks = ui_windows_gate.get("checks") or {}
    macos_checks = ui_macos_gate.get("checks") or {}

    _assert(pulse.get("contract_name") == "ea.weekly_product_pulse", "EA weekly pulse contract_name drifted", failures)
    _assert(
        _state(gate.get("receipt_status") or gate.get("status")) == "pass",
        "EA flagship release gate is not pass",
        failures,
    )
    _assert(
        supporting.get("journey_gate_source") == "/docker/fleet/.codex-studio/published/JOURNEY_GATES.generated.json",
        "EA weekly pulse journey_gate_source drifted",
        failures,
    )
    _assert(supporting.get("journey_gate_git_head") == fleet_head, "EA weekly pulse fleet git head does not match checked-out fleet main", failures)
    _assert(
        supporting.get("flagship_release_receipt_git_head") == ea_head,
        "EA weekly pulse EA git head does not match checked-out executive-assistant main",
        failures,
    )
    _assert(
        pulse_release_provenance.get("git_head") == ea_head,
        "EA weekly pulse release-truth provenance head does not match executive-assistant main",
        failures,
    )
    _assert(
        pulse_journey_provenance.get("git_head") == fleet_head,
        "EA weekly pulse journey-gate provenance head does not match fleet main",
        failures,
    )

    _assert(journey_summary.get("overall_state") == "ready", "fleet journey gates are not ready", failures)
    _assert(int(journey_summary.get("blocked_count") or 0) == 0, "fleet journey gates still report blocked journeys", failures)
    _assert(_state(readiness.get("status")) == "pass", "fleet flagship readiness is not pass", failures)
    _assert(not (readiness.get("missing_keys") or []), "fleet flagship readiness still reports missing coverage keys", failures)
    _assert(not (readiness.get("warning_keys") or []), "fleet flagship readiness still reports warning coverage keys", failures)
    _assert(int(completion_audit.get("unresolved_external_proof_request_count") or 0) == 0, "fleet completion audit still reports unresolved external proof requests", failures)
    _assert(_state(external_host_proof.get("status")) == "pass", "fleet external_host_proof is not pass", failures)

    _assert(_state(release_channel.get("rolloutState")) == "public_stable", "hub-registry rolloutState is not public_stable", failures)
    _assert(not (tuple_coverage.get("missingRequiredPlatforms") or []), "hub-registry still reports missing required desktop platforms", failures)
    _assert(not (tuple_coverage.get("missingRequiredPlatformHeadPairs") or []), "hub-registry still reports missing required platform/head pairs", failures)
    _assert(not (tuple_coverage.get("missingRequiredPlatformHeadRidTuples") or []), "hub-registry still reports missing required platform/head/rid tuples", failures)

    _assert(_state(ui_local_release.get("status")) in PASS_STATES, "UI local release proof is not passed", failures)
    _assert(_state(ui_exec_gate.get("status")) in PASS_STATES, "UI desktop executable exit gate is not pass", failures)
    _assert(not (ui_exec_gate.get("reasons") or []), "UI desktop executable exit gate still reports reasons", failures)
    _assert(_state(ui_windows_gate.get("status")) in PASS_STATES, "UI Windows desktop exit gate is not passed", failures)
    _assert(_state(ui_macos_gate.get("status")) in PASS_STATES, "UI macOS desktop exit gate is not passed", failures)
    _assert(
        str(windows_checks.get("release_channel_version") or "").strip()
        == str(release_channel.get("version") or "").strip(),
        "UI Windows gate release-channel version does not match hub-registry version",
        failures,
    )
    _assert(
        bool((macos_checks.get("startup_smoke") or {}).get("version_matches_release_channel")),
        "UI macOS gate startup-smoke receipt no longer matches the promoted release-channel version",
        failures,
    )

    _assert(_state(mobile_proof.get("status")) in PASS_STATES, "mobile local release proof is not passed", failures)
    mobile_generated_at = _parse_iso(mobile_proof.get("generated_at"), label="mobile local release proof generated_at")
    mobile_max_age = timedelta(hours=max(int(args.max_mobile_proof_age_hours), 0))
    if mobile_max_age:
        _assert(
            mobile_generated_at >= datetime.now(timezone.utc) - mobile_max_age,
            "mobile local release proof is stale beyond the configured max age",
            failures,
        )

    if journey_summary.get("overall_state") == "ready":
        for decision in pulse_governor_decisions:
            cited = set(str(item) for item in (decision.get("cited_signals") or []))
            _assert(
                "cross_host_tuple_coverage=blocked" not in cited,
                "EA weekly pulse still cites blocked cross-host coverage after fleet turned ready",
                failures,
            )
        for cluster in pulse_clusters:
            summary = str(cluster.get("summary") or "")
            _assert(
                "still block the install/claim/restore/continue story" not in summary,
                "EA weekly pulse still describes fleet journey coverage as blocked after fleet turned ready",
                failures,
            )

    return {
        "ok": not failures,
        "failures": failures,
        "heads": {
            "fleet": fleet_head,
            "executive_assistant": ea_head,
            "hub_registry": hub_head,
            "ui": ui_head,
            "mobile": mobile_head,
        },
        "artifacts": {
            "ea_weekly_pulse": str((ea_root / ".codex-design" / "product" / "WEEKLY_PRODUCT_PULSE.generated.json").resolve()),
            "fleet_journey_gates": str((fleet_root / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json").resolve()),
            "fleet_flagship_readiness": str((fleet_root / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json").resolve()),
            "hub_release_channel": str((hub_root / ".codex-studio" / "published" / "RELEASE_CHANNEL.generated.json").resolve()),
            "ui_desktop_executable_exit_gate": str((ui_root / ".codex-studio" / "published" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json").resolve()),
            "mobile_local_release_proof": str(mobile_proof_path),
        },
    }


def main() -> int:
    args = _parse_args()
    result = _verify(args)
    if args.json:
        print(json.dumps(result, indent=2))
    elif result["ok"]:
        print("cross-repo release proof sync ok")
    else:
        for failure in result["failures"]:
            print(f"release-proof-sync failure: {failure}", file=sys.stderr)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
