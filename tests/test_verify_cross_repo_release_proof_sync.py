from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from argparse import Namespace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.verify_cross_repo_release_proof_sync import _verify


def _init_repo(path: Path) -> str:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "-C", str(path), "init", "-b", "main"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Test User"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@example.com"], check=True, capture_output=True)
    (path / ".gitkeep").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", ".gitkeep"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "commit", "-m", "init"], check=True, capture_output=True)
    return (
        subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], check=True, capture_output=True, text=True)
        .stdout.strip()
    )


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _build_fixture_roots(tmp_path: Path) -> Namespace:
    fleet_root = tmp_path / "fleet"
    ea_root = tmp_path / "executive-assistant"
    hub_root = tmp_path / "hub-registry"
    ui_root = tmp_path / "ui"
    mobile_root = tmp_path / "mobile"

    fleet_head = _init_repo(fleet_root)
    ea_head = _init_repo(ea_root)
    _init_repo(hub_root)
    _init_repo(ui_root)
    _init_repo(mobile_root)

    _write_json(
        ea_root / ".codex-design/product/WEEKLY_PRODUCT_PULSE.generated.json",
        {
            "contract_name": "ea.weekly_product_pulse",
            "supporting_signals": {
                "journey_gate_source": "/docker/fleet/.codex-studio/published/JOURNEY_GATES.generated.json",
                "journey_gate_git_head": fleet_head,
                "flagship_release_receipt_git_head": ea_head,
            },
            "release_truth_provenance": {"git_head": ea_head},
            "journey_gate_provenance": {"git_head": fleet_head},
            "governor_decisions": [
                {"cited_signals": ["cross_host_tuple_coverage=ready"]},
            ],
            "top_support_or_feedback_clusters": [
                {"summary": "Fleet journey gates are ready across the install/claim/restore/continue story."}
            ],
        },
    )
    _write_json(
        ea_root / ".codex-design/product/EA_FLAGSHIP_RELEASE_GATE.generated.json",
        {"receipt_status": "pass"},
    )
    _write_json(
        fleet_root / ".codex-studio/published/JOURNEY_GATES.generated.json",
        {"summary": {"overall_state": "ready", "blocked_count": 0}},
    )
    _write_json(
        fleet_root / ".codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json",
        {
            "status": "pass",
            "missing_keys": [],
            "warning_keys": [],
            "completion_audit": {"unresolved_external_proof_request_count": 0},
            "external_host_proof": {"status": "pass"},
        },
    )
    _write_json(
        hub_root / ".codex-studio/published/RELEASE_CHANNEL.generated.json",
        {
            "rolloutState": "public_stable",
            "version": "run-1",
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": [],
                "missingRequiredPlatformHeadPairs": [],
                "missingRequiredPlatformHeadRidTuples": [],
            },
        },
    )
    _write_json(
        ui_root / ".codex-studio/published/UI_LOCAL_RELEASE_PROOF.generated.json",
        {"status": "passed"},
    )
    _write_json(
        ui_root / ".codex-studio/published/DESKTOP_EXECUTABLE_EXIT_GATE.generated.json",
        {"status": "pass", "reasons": []},
    )
    _write_json(
        ui_root / ".codex-studio/published/UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json",
        {"status": "passed", "checks": {"release_channel_version": "run-1"}},
    )
    _write_json(
        ui_root / ".codex-studio/published/UI_MACOS_AVALONIA_OSX_ARM64_DESKTOP_EXIT_GATE.generated.json",
        {"status": "passed", "checks": {"startup_smoke": {"version_matches_release_channel": True}}},
    )
    _write_json(
        mobile_root / ".codex-studio/published/MOBILE_LOCAL_RELEASE_PROOF.generated.json",
        {
            "status": "passed",
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        },
    )

    return Namespace(
        fleet_root=fleet_root,
        ea_root=ea_root,
        hub_registry_root=hub_root,
        ui_root=ui_root,
        mobile_root=mobile_root,
        mobile_proof=None,
        max_mobile_proof_age_hours=48,
    )


def test_verify_cross_repo_release_proof_sync_passes_for_aligned_fixture(tmp_path: Path) -> None:
    args = _build_fixture_roots(tmp_path)
    result = _verify(args)
    assert result["ok"] is True
    assert result["failures"] == []


def test_verify_cross_repo_release_proof_sync_fails_when_ea_pulse_still_claims_blocked_cross_host(tmp_path: Path) -> None:
    args = _build_fixture_roots(tmp_path)
    pulse_path = args.ea_root / ".codex-design/product/WEEKLY_PRODUCT_PULSE.generated.json"
    pulse = json.loads(pulse_path.read_text(encoding="utf-8"))
    pulse["governor_decisions"][0]["cited_signals"] = ["cross_host_tuple_coverage=blocked"]
    pulse["top_support_or_feedback_clusters"][0]["summary"] = (
        "Fleet journey gates still block the install/claim/restore/continue story on cross-host coverage."
    )
    _write_json(pulse_path, pulse)

    result = _verify(args)

    assert result["ok"] is False
    assert any("blocked cross-host coverage" in failure for failure in result["failures"])
