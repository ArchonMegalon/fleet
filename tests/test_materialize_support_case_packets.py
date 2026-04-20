from __future__ import annotations

import http.server
import hashlib
import importlib.util
import inspect
import json
import os
import socketserver
import subprocess
import sys
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path


SCRIPT = Path("/docker/fleet/scripts/materialize_support_case_packets.py")
DESIGN_QUEUE_ENV = "FLEET_DESIGN_NEXT_90_QUEUE_STAGING_PATH"


class _DirectMonkeyPatch:
    def __init__(self) -> None:
        self._restores: list[tuple[object, str, object]] = []

    def setattr(self, target: object, name: str, value: object) -> None:
        self._restores.append((target, name, getattr(target, name)))
        setattr(target, name, value)

    def undo(self) -> None:
        for target, name, value in reversed(self._restores):
            setattr(target, name, value)
        self._restores.clear()


def _load_module():
    previous_sys_path = list(sys.path)
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        spec = importlib.util.spec_from_file_location("materialize_support_case_packets", SCRIPT)
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path[:] = previous_sys_path


@contextmanager
def _override_design_queue_path(path: Path):
    previous = os.environ.get(DESIGN_QUEUE_ENV)
    os.environ[DESIGN_QUEUE_ENV] = str(path)
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(DESIGN_QUEUE_ENV, None)
        else:
            os.environ[DESIGN_QUEUE_ENV] = previous


def _write_registry(path: Path) -> None:
    path.write_text(
        """
product: chummer
program_wave: next_90_day_product_advance
milestones:
  - id: 102
    title: Desktop-native claim, update, rollback, and support followthrough
    wave: W6
    owners:
      - fleet
    status: in_progress
    dependencies:
      - 101
    work_tasks:
      - id: 102.4
        owner: fleet
        title: Gate the staged reporter mail loop against real install and fix receipts, not only queued support state.
        status: complete
        evidence:
          - /docker/fleet/scripts/materialize_support_case_packets.py verifies next90-m102-fleet-reporter-receipts against the canonical successor registry and staging queue, then compiles reporter followthrough from support packets only after install truth, installation-bound installed-build receipts, fixed-version receipts, fixed-channel receipts, and release-channel receipts agree.
          - /docker/fleet/tests/test_materialize_support_case_packets.py covers receipt gating.
          - python3 tests/test_materialize_support_case_packets.py exits 0.
          - /docker/fleet/.codex-studio/published/SUPPORT_CASE_PACKETS.generated.json reports successor_package_verification.status=pass and projects reporter_followthrough_plan from install-aware receipt gates.
          - /docker/fleet/.codex-studio/published/WEEKLY_GOVERNOR_PACKET.generated.json and .md project fix-available, please-test, recovery, missing-install-receipt, and receipt-mismatch counts from the support packet receipt gates.
          - /docker/fleet/scripts/verify_next90_m102_fleet_reporter_receipts.py fail-closes weekly/support generated_at freshness drift so WEEKLY_GOVERNOR_PACKET.generated.json cannot predate the SUPPORT_CASE_PACKETS.generated.json receipt gates it summarizes.
          - /docker/fleet/scripts/verify_next90_m102_fleet_reporter_receipts.py fail-closes weekly support-packet source sha256 drift so WEEKLY_GOVERNOR_PACKET.generated.json must name the exact SUPPORT_CASE_PACKETS.generated.json bytes it summarizes.
          - /docker/fleet/scripts/verify_next90_m102_fleet_reporter_receipts.py fail-closes future-dated generated_at receipts so support and weekly proof cannot outrun wall-clock truth.
          - /docker/fleet/scripts/verify_script_bootstrap_no_pythonpath.py includes the standalone M102 verifier in no-PYTHONPATH bootstrap proof so repeat-prevention cannot silently break on import path assumptions.
          - python3 scripts/verify_next90_m102_fleet_reporter_receipts.py exits 0.
          - /docker/fleet/scripts/materialize_support_case_packets.py now fail-closes duplicate next90-m102-fleet-reporter-receipts queue rows, duplicate design-queue rows, and duplicate registry work-task rows so stale closure proof cannot hide behind the first matching row.
          - /docker/fleet/scripts/materialize_support_case_packets.py now requires generated successor scope-drift, closure-field drift, and missing Fleet proof-anchor markers in both the Fleet queue mirror and design-owned queue source so future shards verify the closed proof floor instead of repeating it.
          - /docker/fleet/scripts/verify_next90_m102_fleet_reporter_receipts.py now fail-closes runtime handoff metadata proof markers so copied worker-run metadata cannot close the package.
          - /docker/fleet/scripts/verify_next90_m102_fleet_reporter_receipts.py now fail-closes stale ready action-group receipt mismatches so fix-available, please-test, feedback, or recovery rows cannot stay "ready" when install receipt, release receipt, fixed receipt, or installed-build values drift from the claimed packet truth.
          - /docker/fleet/scripts/verify_next90_m102_fleet_reporter_receipts.py now fail-closes missing per-row install-aware receipt gates so ready action-group rows cannot pass on summary counters alone.
          - /docker/fleet/scripts/verify_next90_m102_fleet_reporter_receipts.py now records the cached packet fallback provenance guard and seeded cached-packet mirror provenance guard so ready followthrough cannot survive `cached_packets_fallback` or `seeded_from_cached_packets_generated_at`.
          - /docker/fleet/scripts/materialize_support_case_packets.py now fail-closes completed queue rows that omit `verify_closed_package_only` or the package-specific do-not-reopen reason in either the Fleet queue mirror or the design-owned queue source.
          - /docker/fleet/feedback/2026-04-15-next90-m102-fleet-reporter-receipts-closeout.md records the closed-scope anti-reopen rule and exact proof anchors for future shards.
""".lstrip(),
        encoding="utf-8",
    )


def _write_queue(path: Path, design_queue: Path) -> None:
    payload = f"""
program_wave: next_90_day_product_advance
source_design_queue_path: {design_queue}
items:
  - title: Gate fix followthrough against real install and receipt truth
    task: Compile feedback, fix-available, please-test, and recovery loops from install-aware release receipts instead of queued support state alone.
    package_id: next90-m102-fleet-reporter-receipts
    frontier_id: 2454416974
    milestone_id: 102
    wave: W6
    repo: fleet
    status: complete
    completion_action: verify_closed_package_only
    do_not_reopen_reason: M102 Fleet reporter receipts are complete; future shards must verify the support-packet receipt, standalone verifier, registry row, queue row, and design queue row instead of reopening the install-aware followthrough package.
    proof:
      - /docker/fleet/scripts/materialize_support_case_packets.py
      - /docker/fleet/scripts/verify_next90_m102_fleet_reporter_receipts.py
      - /docker/fleet/tests/test_materialize_support_case_packets.py
      - /docker/fleet/tests/test_verify_next90_m102_fleet_reporter_receipts.py
      - /docker/fleet/scripts/verify_script_bootstrap_no_pythonpath.py
      - /docker/fleet/tests/test_fleet_script_bootstrap_without_pythonpath.py
      - /docker/fleet/.codex-studio/published/SUPPORT_CASE_PACKETS.generated.json
      - /docker/fleet/.codex-studio/published/WEEKLY_GOVERNOR_PACKET.generated.json
      - /docker/fleet/.codex-studio/published/WEEKLY_GOVERNOR_PACKET.generated.md
      - /docker/fleet/feedback/2026-04-15-next90-m102-fleet-reporter-receipts-closeout.md
      - python3 -m py_compile scripts/materialize_support_case_packets.py scripts/verify_next90_m102_fleet_reporter_receipts.py tests/test_materialize_support_case_packets.py tests/test_verify_next90_m102_fleet_reporter_receipts.py scripts/materialize_weekly_governor_packet.py tests/test_materialize_weekly_governor_packet.py
      - python3 tests/test_materialize_support_case_packets.py exits 0
      - python3 scripts/verify_next90_m102_fleet_reporter_receipts.py exits 0
      - python3 tests/test_verify_next90_m102_fleet_reporter_receipts.py exits 0
      - installation-bound receipt gating blocks reporter followthrough when installed-build receipt installation id disagrees with the linked install
      - fixed-version receipts and fixed-channel receipts are required before reporter followthrough leaves hold
      - direct tmp_path fixture invocation for receipt-gated support followthrough tests exits 0
      - standalone verifier rejects missing receipt-gate names, missing weekly receipt counters, and active-run telemetry helper proof entries
      - generated support-packet proof hygiene requires empty disallowed active-run proof entries
      - stale generated support proof gaps fail the standalone verifier
      - generated support successor scope drift fails the standalone verifier
      - generated support successor closure-field drift fails the standalone verifier
      - weekly/support receipt-count drift fails the standalone verifier
      - weekly/support generated_at freshness fails the standalone verifier
      - weekly support-packet source sha256 drift fails the standalone verifier
      - future-dated support and weekly generated_at receipts fail the standalone verifier
      - weekly support-packet source-path drift fails the standalone verifier
      - standalone verifier rejects fix-available, please-test, feedback, or recovery action-group rows that omit their own install-aware receipt gates
      - standalone verifier rejects ready action-group rows whose install receipt, release receipt, fixed receipt, or installed-build values disagree even when stale generated booleans claim ready
      - design queue source path rejects active-run helper paths
      - weekly governor source-path hygiene and worker command guard fail the standalone verifier
      - no-PYTHONPATH bootstrap guard includes the standalone M102 verifier
      - successor frontier 2454416974 pinned for next90-m102-fleet-reporter-receipts repeat prevention
      - design-owned queue source row matches the Fleet completed queue proof assignment
      - design-owned queue source proof markers fail the standalone verifier
      - successor verifier fail-closes missing Fleet proof anchors and SUPPORT_CASE_PACKETS.generated.json reports missing_registry_proof_anchor_paths=[] and missing_queue_proof_anchor_paths=[]
      - telemetry command proof markers fail the standalone verifier and shared successor authority check
      - runtime handoff frontier metadata proof markers fail the standalone verifier and shared successor authority check
      - distinct queue proof anti-collapse guard prevents broad prose proof lines from satisfying command and negative-proof rows
      - duplicate queue, design-queue, and registry work-task rows for next90-m102-fleet-reporter-receipts fail the shared successor authority check
      - cached packet fallback provenance guard keeps ready followthrough closed when `source.refresh_mode=cached_packets_fallback`
      - seeded cached-packet mirror provenance guard keeps ready followthrough closed when `seeded_from_cached_packets_generated_at` is present
      - completed queue action guard requires verify_closed_package_only and package-specific do_not_reopen_reason on Fleet and design queue rows
    allowed_paths:
      - scripts
      - tests
      - .codex-studio
      - feedback
    owned_surfaces:
      - feedback_loop_ready:install_receipts
      - product_governor:followthrough
""".lstrip()
    path.write_text(payload, encoding="utf-8")
    design_queue.write_text(payload.replace(f"source_design_queue_path: {design_queue}\n", ""), encoding="utf-8")


def test_normalize_proof_capture_commands_preserves_canonical_startup_smoke_tail() -> None:
    module = _load_module()

    commands, stripped_count = module._normalize_proof_capture_commands_with_metadata(
        [
            "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=macos-host CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=macOS ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg avalonia osx-arm64 Chummer.Avalonia /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke run-20260414-1836",
            "cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh",
        ]
    )

    assert commands == [
        "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=macos-host CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=macOS ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg avalonia osx-arm64 Chummer.Avalonia /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke run-20260414-1836",
        "cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh",
    ]
    assert stripped_count == 0


def test_lookup_promoted_tuple_uses_canonical_install_receipt_tuple_order() -> None:
    module = _load_module()

    match = module._lookup_promoted_tuple(
        index={
            "promoted_tuples": [
                {
                    "tuple_id": "avalonia:linux-x64:linux",
                    "head": "avalonia",
                    "platform": "linux",
                    "rid": "linux-x64",
                    "artifact_id": "avalonia-linux-x64-installer",
                }
            ]
        },
        head="avalonia",
        platform="linux",
        arch="x64",
    )

    assert match["tuple_id"] == "avalonia:linux-x64:linux"
    assert match["artifact_id"] == "avalonia-linux-x64-installer"


def test_external_proof_local_evidence_reports_stale_receipt(tmp_path: Path) -> None:
    module = _load_module()
    previous_root = module.UI_DOCKER_DOWNLOADS_ROOT
    stale_recorded_at = (
        datetime.now(timezone.utc) - timedelta(seconds=module.REQUIRED_STARTUP_SMOKE_MAX_AGE_SECONDS + 60)
    ).isoformat()
    try:
        module.UI_DOCKER_DOWNLOADS_ROOT = tmp_path
        files_dir = tmp_path / "files"
        startup_smoke_dir = tmp_path / "startup-smoke"
        files_dir.mkdir(parents=True, exist_ok=True)
        startup_smoke_dir.mkdir(parents=True, exist_ok=True)
        installer_path = files_dir / "chummer-avalonia-osx-arm64-installer.dmg"
        installer_bytes = b"test-installer-bytes"
        installer_path.write_bytes(installer_bytes)
        receipt_path = startup_smoke_dir / "startup-smoke-avalonia-osx-arm64.receipt.json"
        receipt_path.write_text(
            json.dumps(
                {
                    "headId": "avalonia",
                    "platform": "macos",
                    "rid": "osx-arm64",
                    "hostClass": "macos-host",
                    "readyCheckpoint": "pre_ui_event_loop",
                    "status": "pass",
                    "recordedAtUtc": stale_recorded_at,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        evidence = module._external_proof_local_evidence(
            {
                "expected_installer_relative_path": "files/chummer-avalonia-osx-arm64-installer.dmg",
                "expected_installer_sha256": hashlib.sha256(installer_bytes).hexdigest(),
                "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json",
                "startup_smoke_receipt_contract": {
                    "head_id": "avalonia",
                    "platform": "macos",
                    "rid": "osx-arm64",
                    "ready_checkpoint": "pre_ui_event_loop",
                    "host_class_contains": "macos",
                    "status_any_of": ["pass", "passed", "ready"],
                },
            }
        )
    finally:
        module.UI_DOCKER_DOWNLOADS_ROOT = previous_root

    assert evidence["installer_artifact"]["state"] == "present_sha256_match"
    assert evidence["startup_smoke_receipt"]["state"] == "stale"
    assert evidence["startup_smoke_receipt"]["recorded_at_utc"] == stale_recorded_at
    assert evidence["startup_smoke_receipt"]["contract_matches_expected"] is True
    assert evidence["startup_smoke_receipt"]["age_seconds"] > module.REQUIRED_STARTUP_SMOKE_MAX_AGE_SECONDS


def test_source_items_from_cached_packets_preserves_installed_build_receipts() -> None:
    module = _load_module()

    items = module._source_items_from_cached_packets(
        {
            "packets": [
                {
                    "support_case_backed": True,
                    "packet_id": "support_packet_cached",
                    "kind": "bug_report",
                    "status": "fixed",
                    "target_repo": "chummer6-ui",
                    "installation_id": "install-cached-1",
                    "release_channel": "preview",
                    "head_id": "avalonia",
                    "platform": "linux",
                    "arch": "x64",
                    "installed_version": "1.2.3",
                    "fixed_version": "1.2.3",
                    "fixed_channel": "preview",
                    "reporter_followthrough": {
                        "installed_build_receipt_id": "install-receipt-cached-1",
                        "installed_build_receipt_installation_id": "install-cached-1",
                        "installed_build_receipt_version": "1.2.3",
                        "installed_build_receipt_channel": "preview",
                    },
                }
            ]
        }
    )

    assert items == [
        {
            "caseId": "support_packet_cached",
            "clusterKey": "support_packet_cached",
            "kind": "bug_report",
            "status": "fixed",
            "candidateOwnerRepo": "chummer6-ui",
            "designImpactSuspected": False,
            "installationId": "install-cached-1",
            "releaseChannel": "preview",
            "headId": "avalonia",
            "platform": "linux",
            "arch": "x64",
            "fixedVersion": "1.2.3",
            "fixedChannel": "preview",
            "installedVersion": "1.2.3",
            "installedBuildReceiptId": "install-receipt-cached-1",
            "installedBuildReceiptInstallationId": "install-cached-1",
            "installedBuildReceiptVersion": "1.2.3",
            "installedBuildReceiptChannel": "preview",
        }
    ]


def test_source_mirror_preserves_install_and_fix_receipt_feeds_for_fallback() -> None:
    module = _load_module()
    source_payload = {
        "installReceipts": [
            {
                "receiptId": "install-receipt-mirror-1",
                "installationId": "install-mirror-1",
                "version": "1.2.3",
                "channel": "preview",
                "headId": "avalonia",
                "platform": "linux",
                "rid": "linux-x64",
            }
        ],
        "fixedReleaseReceipts": [
            {
                "caseId": "support_case_mirror_receipts",
                "installationId": "install-mirror-1",
                "fixedVersion": "1.2.3",
                "fixedChannel": "preview",
                "fixedVersionReceiptId": "fix-version-receipt-mirror-1",
                "fixedChannelReceiptId": "fix-channel-receipt-mirror-1",
            }
        ],
        "items": [
            {
                "caseId": "support_case_mirror_receipts",
                "clusterKey": "support:mirror-receipts",
                "kind": "bug_report",
                "status": "fixed",
                "candidateOwnerRepo": "chummer6-ui",
                "installationId": "install-mirror-1",
                "releaseChannel": "preview",
                "headId": "avalonia",
                "platform": "linux",
                "arch": "x64",
                "fixedVersion": "1.2.3",
                "fixedChannel": "preview",
            }
        ],
    }
    release_channel_index = module._release_channel_index(
        {
            "channelId": "preview",
            "status": "published",
            "version": "1.2.3",
            "releaseProof": {"status": "passed"},
            "desktopTupleCoverage": {
                "promotedInstallerTuples": [
                    {
                        "tupleId": "avalonia:linux:linux-x64",
                        "head": "avalonia",
                        "platform": "linux",
                        "rid": "linux-x64",
                        "artifactId": "avalonia-linux-x64-installer",
                    }
                ]
            },
        }
    )

    mirror_payload = module._build_source_mirror_payload(source_payload, source_label="https://chummer.run/api/v1/support/cases/triage")
    fallback_payload = module.build_packets_payload(
        mirror_payload,
        "SUPPORT_CASE_SOURCE_MIRROR.generated.json",
        release_channel_index=release_channel_index,
    )

    assert mirror_payload["installReceipts"] == source_payload["installReceipts"]
    assert mirror_payload["fixedReleaseReceipts"] == source_payload["fixedReleaseReceipts"]
    assert fallback_payload["source"]["install_receipt_feed_state"] == "provided"
    assert fallback_payload["source"]["fix_receipt_feed_state"] == "provided"
    assert fallback_payload["summary"]["fix_available_ready_count"] == 0
    assert fallback_payload["summary"]["reporter_followthrough_blocked_missing_install_receipts_count"] == 0
    packet = fallback_payload["packets"][0]
    assert packet["installed_build_receipt_id"] == "install-receipt-mirror-1"
    assert packet["fixed_version_receipt_id"] == "fix-version-receipt-mirror-1"
    assert packet["reporter_followthrough"]["state"] == "please_test_ready"
    assert packet["reporter_followthrough"]["installed_build_receipt_source"] == "install_receipts"
    assert packet["reporter_followthrough"]["fixed_version_receipt_source"] == "fix_receipts"


def test_followthrough_row_gate_evidence_requires_install_and_release_truth_for_installed_build_counts() -> None:
    module = _load_module()

    gate_evidence = module._followthrough_row_gate_evidence(
        {
            "installation_id": "install-gate-1",
            "install_receipt_ready": True,
            "install_truth_state": "channel_mismatch",
            "release_receipt_state": "release_receipt_missing",
            "release_receipt_id": "",
            "release_receipt_source": "",
            "release_receipt_channel": "",
            "release_receipt_version": "",
            "installed_build_receipted": True,
            "installed_build_receipt_id": "install-receipt-gate-1",
            "installed_build_receipt_installation_id": "install-gate-1",
            "installed_build_receipt_version": "1.2.3",
            "installed_build_receipt_channel": "preview",
            "installed_build_receipt_source": "install_receipts",
            "installed_build_receipt_installation_source": "install_receipts",
            "installed_build_receipt_version_source": "install_receipts",
            "installed_build_receipt_channel_source": "install_receipts",
            "installed_build_receipt_installation_matches": True,
            "installed_build_receipt_version_matches": True,
            "installed_build_receipt_channel_matches": True,
            "installed_build_receipt_identity_matches": True,
        }
    )

    assert gate_evidence["install_truth_ready"] is False
    assert gate_evidence["release_receipt_ready"] is False
    assert gate_evidence["installed_build_receipt_id_present"] is False
    assert gate_evidence["installed_build_receipted"] is False
    assert gate_evidence["installed_build_receipt_installation_bound"] is False


def test_materialize_support_case_packets_proves_successor_package_authority(tmp_path: Path) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    registry = tmp_path / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
    queue = tmp_path / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    design_queue = tmp_path / "DESIGN_NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(json.dumps({"items": []}, indent=2) + "\n", encoding="utf-8")
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "desktopTupleCoverage": {"promotedInstallerTuples": []},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    _write_registry(registry)
    _write_queue(queue, design_queue)

    with _override_design_queue_path(design_queue):
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--source",
                str(source),
                "--release-channel",
                str(release_channel),
                "--successor-registry",
                str(registry),
                "--queue-staging",
                str(queue),
                "--out",
                str(out_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    verification = payload["successor_package_verification"]
    assert verification["status"] == "pass"
    assert verification["package_id"] == "next90-m102-fleet-reporter-receipts"
    assert verification["frontier_id"] == "2454416974"
    assert verification["milestone_id"] == 102
    assert verification["registry_dependencies"] == [101]
    assert verification["registry_work_task_id"] == "102.4"
    assert verification["registry_work_task_count"] == 1
    assert verification["registry_work_task_status"] == "complete"
    assert verification["missing_registry_evidence_markers"] == []
    assert verification["missing_registry_proof_anchor_paths"] == []
    assert verification["disallowed_registry_evidence_entries"] == []
    assert verification["queue_status"] == "complete"
    assert verification["queue_frontier_id"] == "2454416974"
    assert verification["queue_item_count"] == 1
    assert verification["design_queue_source_path"] == str(design_queue)
    assert verification["design_queue_source_item_count"] == 1
    assert verification["design_queue_source_item_found"] is True
    assert verification["design_queue_source_status"] == "complete"
    assert verification["design_queue_source_frontier_id"] == "2454416974"
    assert verification["missing_design_queue_source_proof_markers"] == []
    assert verification["missing_queue_design_source_proof_markers"] == []
    assert verification["missing_design_queue_source_proof_anchor_paths"] == []
    assert verification["disallowed_design_queue_source_proof_entries"] == []
    assert verification["missing_queue_proof_markers"] == []
    assert verification["missing_queue_proof_anchor_paths"] == []
    assert verification["disallowed_queue_proof_entries"] == []
    assert verification["allowed_paths"] == ["scripts", "tests", ".codex-studio", "feedback"]
    assert verification["owned_surfaces"] == [
        "feedback_loop_ready:install_receipts",
        "product_governor:followthrough",
    ]
    assert "fixed-version receipts" in verification["required_registry_evidence_markers"]
    assert "fixed-channel receipts" in verification["required_registry_evidence_markers"]
    assert "runtime handoff metadata proof markers" in verification["required_registry_evidence_markers"]
    assert "cached packet fallback provenance guard" in verification["required_registry_evidence_markers"]
    assert "seeded cached-packet mirror provenance guard" in verification["required_registry_evidence_markers"]
    assert (
        "feedback/2026-04-15-next90-m102-fleet-reporter-receipts-closeout.md"
        in verification["required_registry_evidence_markers"]
    )
    assert (
        "python3 scripts/verify_next90_m102_fleet_reporter_receipts.py exits 0"
        in verification["required_registry_evidence_markers"]
    )
    assert (
        "python3 tests/test_materialize_support_case_packets.py exits 0"
        in verification["required_registry_evidence_markers"]
    )
    assert "fixed-version receipts" in verification["required_queue_proof_markers"]
    assert "fixed-channel receipts" in verification["required_queue_proof_markers"]
    assert (
        "python3 scripts/verify_next90_m102_fleet_reporter_receipts.py exits 0"
        in verification["required_queue_proof_markers"]
    )
    assert (
        "python3 tests/test_materialize_support_case_packets.py exits 0"
        in verification["required_queue_proof_markers"]
    )
    assert (
        "/docker/fleet/scripts/verify_next90_m102_fleet_reporter_receipts.py"
        in verification["required_queue_proof_markers"]
    )
    assert (
        "/docker/fleet/tests/test_verify_next90_m102_fleet_reporter_receipts.py"
        in verification["required_queue_proof_markers"]
    )
    assert "successor frontier 2454416974" in verification["required_queue_proof_markers"]
    assert "design-owned queue source" in verification["required_queue_proof_markers"]
    assert "generated support-packet proof hygiene" in verification["required_queue_proof_markers"]
    assert "stale generated support proof gaps" in verification["required_queue_proof_markers"]
    assert (
        "weekly support-packet source sha256 drift fails the standalone verifier"
        in verification["required_queue_proof_markers"]
    )
    assert "design-owned queue source proof markers" in verification["required_queue_proof_markers"]
    assert "distinct queue proof anti-collapse guard" in verification["required_queue_proof_markers"]
    assert "cached packet fallback provenance guard" in verification["required_queue_proof_markers"]
    assert "seeded cached-packet mirror provenance guard" in verification["required_queue_proof_markers"]
    assert (
        "/docker/fleet/feedback/2026-04-15-next90-m102-fleet-reporter-receipts-closeout.md"
        in verification["required_queue_proof_markers"]
    )


def test_materialize_support_case_packets_fails_successor_package_authority_without_closeout_proof(tmp_path: Path) -> None:
    module = _load_module()
    registry = tmp_path / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
    queue = tmp_path / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    registry.write_text(
        """
product: chummer
program_wave: next_90_day_product_advance
milestones:
  - id: 102
    title: Desktop-native claim, update, rollback, and support followthrough
    wave: W6
    owners:
      - fleet
    status: in_progress
    dependencies:
      - 101
    work_tasks:
      - id: 102.4
        owner: fleet
        title: Gate the staged reporter mail loop against real install and fix receipts, not only queued support state.
        status: complete
        evidence:
          - /docker/fleet/scripts/materialize_support_case_packets.py
""".lstrip(),
        encoding="utf-8",
    )
    queue.write_text(
        """
program_wave: next_90_day_product_advance
items:
  - title: Gate fix followthrough against real install and receipt truth
    task: Compile feedback, fix-available, please-test, and recovery loops from install-aware release receipts instead of queued support state alone.
    package_id: next90-m102-fleet-reporter-receipts
    milestone_id: 102
    wave: W6
    repo: fleet
    status: queued
    proof:
      - /docker/fleet/scripts/materialize_support_case_packets.py
    allowed_paths:
      - scripts
      - tests
      - .codex-studio
      - feedback
    owned_surfaces:
      - feedback_loop_ready:install_receipts
      - product_governor:followthrough
""".lstrip(),
        encoding="utf-8",
    )

    verification = module._successor_package_verification(registry, queue)

    assert verification["status"] == "fail"
    assert "successor queue item is not complete" in verification["issues"]
    assert "successor queue staging source_design_queue_path missing" in verification["issues"]
    assert verification["missing_registry_evidence_markers"]
    assert verification["missing_queue_proof_markers"]
    assert any("WEEKLY_GOVERNOR_PACKET.generated.json" in issue for issue in verification["issues"])


def test_materialize_support_case_packets_fails_when_queue_mirror_omits_design_source_proof_marker(
    tmp_path: Path,
) -> None:
    module = _load_module()
    registry = tmp_path / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
    queue = tmp_path / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    design_queue = tmp_path / "design_NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    _write_registry(registry)
    _write_queue(queue, design_queue)
    queue.write_text(
        queue.read_text(encoding="utf-8").replace(
            "      - weekly support-packet source sha256 drift fails the standalone verifier\n",
            "",
        ),
        encoding="utf-8",
    )

    with _override_design_queue_path(design_queue):
        verification = module._successor_package_verification(registry, queue)

    assert verification["status"] == "fail"
    assert verification["missing_queue_proof_markers"] == [
        "weekly support-packet source sha256 drift fails the standalone verifier"
    ]
    assert verification["missing_queue_design_source_proof_markers"] == [
        "weekly support-packet source sha256 drift fails the standalone verifier"
    ]
    assert (
        "successor queue item proof missing design-queue source marker: "
        "weekly support-packet source sha256 drift fails the standalone verifier"
        in verification["issues"]
    )


def test_materialize_support_case_packets_fails_when_design_queue_path_is_not_canonical(
    tmp_path: Path,
) -> None:
    module = _load_module()
    registry = tmp_path / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
    queue = tmp_path / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    design_queue = tmp_path / "design_NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    sibling_queue = tmp_path / "sibling_NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    _write_registry(registry)
    _write_queue(queue, design_queue)
    sibling_queue.write_text(design_queue.read_text(encoding="utf-8"), encoding="utf-8")
    queue.write_text(
        queue.read_text(encoding="utf-8").replace(str(design_queue), str(sibling_queue)),
        encoding="utf-8",
    )

    with _override_design_queue_path(design_queue):
        verification = module._successor_package_verification(registry, queue)

    assert verification["status"] == "fail"
    assert verification["design_queue_source_path"] == str(sibling_queue)
    assert (
        "successor queue staging source_design_queue_path drifted from canonical design queue path"
        in verification["issues"]
    )


def test_materialize_support_case_packets_fails_when_completed_queue_action_fields_are_missing(
    tmp_path: Path,
) -> None:
    module = _load_module()
    registry = tmp_path / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
    queue = tmp_path / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    design_queue = tmp_path / "design_NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    _write_registry(registry)
    _write_queue(queue, design_queue)
    queue.write_text(
        queue.read_text(encoding="utf-8")
        .replace("    completion_action: verify_closed_package_only\n", "")
        .replace(
            "    do_not_reopen_reason: M102 Fleet reporter receipts are complete; future shards must verify the support-packet receipt, standalone verifier, registry row, queue row, and design queue row instead of reopening the install-aware followthrough package.\n",
            "",
        ),
        encoding="utf-8",
    )

    with _override_design_queue_path(design_queue):
        verification = module._successor_package_verification(registry, queue)

    assert verification["status"] == "fail"
    assert verification["queue_completion_action"] == ""
    assert verification["queue_do_not_reopen_reason"] == ""
    assert "successor queue item completion_action must be verify_closed_package_only" in verification["issues"]
    assert "successor queue item do_not_reopen_reason drifted" in verification["issues"]


def test_materialize_support_case_packets_fails_when_design_queue_action_fields_are_missing(
    tmp_path: Path,
) -> None:
    module = _load_module()
    registry = tmp_path / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
    queue = tmp_path / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    design_queue = tmp_path / "design_NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    _write_registry(registry)
    _write_queue(queue, design_queue)
    design_queue.write_text(
        design_queue.read_text(encoding="utf-8")
        .replace("    completion_action: verify_closed_package_only\n", "")
        .replace(
            "    do_not_reopen_reason: M102 Fleet reporter receipts are complete; future shards must verify the support-packet receipt, standalone verifier, registry row, queue row, and design queue row instead of reopening the install-aware followthrough package.\n",
            "",
        ),
        encoding="utf-8",
    )

    with _override_design_queue_path(design_queue):
        verification = module._successor_package_verification(registry, queue)

    assert verification["status"] == "fail"
    assert verification["design_queue_source_completion_action"] == ""
    assert verification["design_queue_source_do_not_reopen_reason"] == ""
    assert "successor design queue source completion_action must be verify_closed_package_only" in verification["issues"]
    assert "successor design queue source do_not_reopen_reason drifted" in verification["issues"]


def test_materialize_support_case_packets_rejects_active_run_proof_markers_case_insensitively() -> None:
    module = _load_module()

    entries = module._disallowed_proof_entries(
        [
            "/VAR/LIB/CODEX-FLEET/chummer_design_supervisor/shard-7/active_run_handoff.generated.md",
            "python3 scripts/RUN_OODA_DESIGN_SUPERVISOR_UNTIL_QUIET.py",
            "codexea --telemetry --telemetry-answer remaining",
            "Frontier ids: 2454416974",
            "status: complete; owners: fleet; deps: 101",
            "python3 chummer_design_supervisor.py status",
        ]
    )

    assert entries == [
        "/VAR/LIB/CODEX-FLEET/chummer_design_supervisor/shard-7/active_run_handoff.generated.md",
        "python3 scripts/RUN_OODA_DESIGN_SUPERVISOR_UNTIL_QUIET.py",
        "codexea --telemetry --telemetry-answer remaining",
        "Frontier ids: 2454416974",
        "status: complete; owners: fleet; deps: 101",
        "python3 chummer_design_supervisor.py status",
    ]


def test_materialize_support_case_packets_fails_successor_package_authority_on_canonical_assignment_drift(
    tmp_path: Path,
) -> None:
    module = _load_module()
    registry = tmp_path / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
    queue = tmp_path / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    registry.write_text(
        """
product: chummer
program_wave: next_90_day_product_advance
milestones:
  - id: 102
    title: Desktop-native claim, update, rollback, and support followthrough
    wave: W7
    owners:
      - fleet
    status: in_progress
    dependencies:
      - 999
    work_tasks:
      - id: 102.4
        owner: fleet
        title: Drifted reporter task title
        status: complete
        evidence:
          - /docker/fleet/scripts/materialize_support_case_packets.py compiles reporter followthrough from support packets only after install truth, installation-bound installed-build receipts, and release-channel receipts agree.
          - fixed-version receipts and fixed-channel receipts are required before reporter followthrough leaves hold.
          - /docker/fleet/tests/test_materialize_support_case_packets.py covers receipt gating.
          - /docker/fleet/.codex-studio/published/SUPPORT_CASE_PACKETS.generated.json reports successor_package_verification.status=pass.
          - /docker/fleet/.codex-studio/published/WEEKLY_GOVERNOR_PACKET.generated.json projects fix-available, please-test, and recovery counts.
""".lstrip(),
        encoding="utf-8",
    )
    queue.write_text(
        """
program_wave: next_90_day_product_advance
source_design_queue_path: /docker/chummercomplete/chummer-design/products/chummer/NEXT_90_DAY_QUEUE_STAGING.generated.yaml
items:
  - title: Drifted queue title
    task: Compile feedback, fix-available, please-test, and recovery loops from install-aware release receipts instead of queued support state alone.
    package_id: next90-m102-fleet-reporter-receipts
    frontier_id: 2454416974
    milestone_id: 102
    wave: W9
    repo: fleet
    status: complete
    proof:
      - /docker/fleet/scripts/materialize_support_case_packets.py
      - /docker/fleet/tests/test_materialize_support_case_packets.py
      - /docker/fleet/.codex-studio/published/SUPPORT_CASE_PACKETS.generated.json
      - /docker/fleet/.codex-studio/published/WEEKLY_GOVERNOR_PACKET.generated.json
      - /docker/fleet/.codex-studio/published/WEEKLY_GOVERNOR_PACKET.generated.md
      - /docker/fleet/feedback/2026-04-15-next90-m102-fleet-reporter-receipts-closeout.md
      - python3 -m py_compile scripts/materialize_support_case_packets.py tests/test_materialize_support_case_packets.py scripts/materialize_weekly_governor_packet.py tests/test_materialize_weekly_governor_packet.py
      - installation-bound receipt gating blocks reporter followthrough when installed-build receipt installation id disagrees with the linked install
      - fixed-version receipts and fixed-channel receipts are required before reporter followthrough leaves hold
      - direct tmp_path fixture invocation for receipt-gated support followthrough tests exits 0
      - successor frontier 2454416974 pinned for next90-m102-fleet-reporter-receipts repeat prevention
      - stale generated support proof gaps fail the standalone verifier
      - design-owned queue source row matches the Fleet completed queue proof assignment
    allowed_paths:
      - scripts
      - tests
      - .codex-studio
      - feedback
    owned_surfaces:
      - feedback_loop_ready:install_receipts
      - product_governor:followthrough
""".lstrip(),
        encoding="utf-8",
    )

    verification = module._successor_package_verification(registry, queue)

    assert verification["status"] == "fail"
    assert "successor milestone 102 wave drifted" in verification["issues"]
    assert "successor milestone 102 dependencies drifted" in verification["issues"]
    assert "successor registry work task 102.4 title drifted" in verification["issues"]
    assert "successor queue item title drifted" in verification["issues"]
    assert "successor queue item wave drifted" in verification["issues"]


def test_materialize_support_case_packets_fails_successor_package_authority_without_structured_frontier_id(
    tmp_path: Path,
) -> None:
    module = _load_module()
    registry = tmp_path / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
    queue = tmp_path / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    registry.write_text(
        """
product: chummer
program_wave: next_90_day_product_advance
milestones:
  - id: 102
    title: Desktop-native claim, update, rollback, and support followthrough
    wave: W6
    owners:
      - fleet
    status: in_progress
    dependencies:
      - 101
    work_tasks:
      - id: 102.4
        owner: fleet
        title: Gate the staged reporter mail loop against real install and fix receipts, not only queued support state.
        status: complete
        evidence:
          - /docker/fleet/scripts/materialize_support_case_packets.py compiles reporter followthrough from support packets only after install truth, installation-bound installed-build receipts, and release-channel receipts agree.
          - fixed-version receipts and fixed-channel receipts are required before reporter followthrough leaves hold.
          - /docker/fleet/tests/test_materialize_support_case_packets.py covers receipt gating.
          - /docker/fleet/.codex-studio/published/SUPPORT_CASE_PACKETS.generated.json reports successor_package_verification.status=pass.
          - /docker/fleet/.codex-studio/published/WEEKLY_GOVERNOR_PACKET.generated.json projects fix-available, please-test, and recovery counts.
""".lstrip(),
        encoding="utf-8",
    )
    queue.write_text(
        """
program_wave: next_90_day_product_advance
items:
  - title: Gate fix followthrough against real install and receipt truth
    task: Compile feedback, fix-available, please-test, and recovery loops from install-aware release receipts instead of queued support state alone.
    package_id: next90-m102-fleet-reporter-receipts
    milestone_id: 102
    wave: W6
    repo: fleet
    status: complete
    proof:
      - /docker/fleet/scripts/materialize_support_case_packets.py
      - /docker/fleet/tests/test_materialize_support_case_packets.py
      - /docker/fleet/.codex-studio/published/SUPPORT_CASE_PACKETS.generated.json
      - /docker/fleet/.codex-studio/published/WEEKLY_GOVERNOR_PACKET.generated.json
      - /docker/fleet/.codex-studio/published/WEEKLY_GOVERNOR_PACKET.generated.md
      - /docker/fleet/feedback/2026-04-15-next90-m102-fleet-reporter-receipts-closeout.md
      - python3 -m py_compile scripts/materialize_support_case_packets.py tests/test_materialize_support_case_packets.py scripts/materialize_weekly_governor_packet.py tests/test_materialize_weekly_governor_packet.py
      - installation-bound receipt gating blocks reporter followthrough when installed-build receipt installation id disagrees with the linked install
      - fixed-version receipts and fixed-channel receipts are required before reporter followthrough leaves hold
      - direct tmp_path fixture invocation for receipt-gated support followthrough tests exits 0
      - successor frontier 2454416974 pinned for next90-m102-fleet-reporter-receipts repeat prevention
      - stale generated support proof gaps fail the standalone verifier
    allowed_paths:
      - scripts
      - tests
      - .codex-studio
      - feedback
    owned_surfaces:
      - feedback_loop_ready:install_receipts
      - product_governor:followthrough
""".lstrip(),
        encoding="utf-8",
    )

    verification = module._successor_package_verification(registry, queue)

    assert verification["status"] == "fail"
    assert verification["queue_frontier_id"] == ""
    assert "successor queue item frontier_id does not match 2454416974" in verification["issues"]


def test_materialize_support_case_packets_fails_successor_package_authority_on_design_queue_source_drift(
    tmp_path: Path,
) -> None:
    module = _load_module()
    registry = tmp_path / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
    queue = tmp_path / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    design_queue = tmp_path / "DESIGN_NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    registry.write_text(
        """
product: chummer
program_wave: next_90_day_product_advance
milestones:
  - id: 102
    title: Desktop-native claim, update, rollback, and support followthrough
    wave: W6
    owners:
      - fleet
    status: in_progress
    dependencies:
      - 101
    work_tasks:
      - id: 102.4
        owner: fleet
        title: Gate the staged reporter mail loop against real install and fix receipts, not only queued support state.
        status: complete
        evidence:
          - /docker/fleet/scripts/materialize_support_case_packets.py compiles reporter followthrough from support packets only after install truth, installation-bound installed-build receipts, fixed-version receipts, fixed-channel receipts, and release-channel receipts agree.
          - /docker/fleet/tests/test_materialize_support_case_packets.py covers receipt gating.
          - /docker/fleet/.codex-studio/published/SUPPORT_CASE_PACKETS.generated.json reports successor_package_verification.status=pass.
          - /docker/fleet/.codex-studio/published/WEEKLY_GOVERNOR_PACKET.generated.json projects fix-available, please-test, and recovery counts.
""".lstrip(),
        encoding="utf-8",
    )
    queue.write_text(
        f"""
program_wave: next_90_day_product_advance
source_design_queue_path: {design_queue}
items:
  - title: Gate fix followthrough against real install and receipt truth
    task: Compile feedback, fix-available, please-test, and recovery loops from install-aware release receipts instead of queued support state alone.
    package_id: next90-m102-fleet-reporter-receipts
    frontier_id: 2454416974
    milestone_id: 102
    wave: W6
    repo: fleet
    status: complete
    proof:
      - /docker/fleet/scripts/materialize_support_case_packets.py
      - /docker/fleet/tests/test_materialize_support_case_packets.py
      - /docker/fleet/.codex-studio/published/SUPPORT_CASE_PACKETS.generated.json
      - /docker/fleet/.codex-studio/published/WEEKLY_GOVERNOR_PACKET.generated.json
      - /docker/fleet/.codex-studio/published/WEEKLY_GOVERNOR_PACKET.generated.md
      - /docker/fleet/feedback/2026-04-15-next90-m102-fleet-reporter-receipts-closeout.md
      - python3 -m py_compile scripts/materialize_support_case_packets.py tests/test_materialize_support_case_packets.py scripts/materialize_weekly_governor_packet.py tests/test_materialize_weekly_governor_packet.py
      - installation-bound receipt gating blocks reporter followthrough when installed-build receipt installation id disagrees with the linked install
      - fixed-version receipts and fixed-channel receipts are required before reporter followthrough leaves hold
      - direct tmp_path fixture invocation for receipt-gated support followthrough tests exits 0
      - successor frontier 2454416974 pinned for next90-m102-fleet-reporter-receipts repeat prevention
      - stale generated support proof gaps fail the standalone verifier
      - design-owned queue source row matches the Fleet completed queue proof assignment
    allowed_paths:
      - scripts
      - tests
      - .codex-studio
      - feedback
    owned_surfaces:
      - feedback_loop_ready:install_receipts
      - product_governor:followthrough
""".lstrip(),
        encoding="utf-8",
    )
    design_queue.write_text(
        """
program_wave: next_90_day_product_advance
items:
  - title: Gate fix followthrough against real install and receipt truth
    task: Compile feedback, fix-available, please-test, and recovery loops from install-aware release receipts instead of queued support state alone.
    package_id: next90-m102-fleet-reporter-receipts
    milestone_id: 102
    wave: W6
    repo: fleet
    allowed_paths:
      - scripts
      - .codex-studio
      - feedback
    owned_surfaces:
      - feedback_loop_ready:install_receipts
      - product_governor:followthrough
""".lstrip(),
        encoding="utf-8",
    )

    with _override_design_queue_path(design_queue):
        verification = module._successor_package_verification(registry, queue)

    assert verification["status"] == "fail"
    assert verification["design_queue_source_path"] == str(design_queue)
    assert verification["design_queue_source_item_found"] is True
    assert "successor design queue source allowed_paths drifted" in verification["issues"]


def test_materialize_support_case_packets_fails_successor_package_authority_on_duplicate_registry_work_task(
    tmp_path: Path,
) -> None:
    module = _load_module()
    registry = tmp_path / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
    queue = tmp_path / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    design_queue = tmp_path / "DESIGN_NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    registry.write_text(
        """
product: chummer
program_wave: next_90_day_product_advance
milestones:
  - id: 102
    title: Desktop-native claim, update, rollback, and support followthrough
    wave: W6
    owners:
      - fleet
    status: in_progress
    dependencies:
      - 101
    work_tasks:
      - id: 102.4
        owner: fleet
        title: Gate the staged reporter mail loop against real install and fix receipts, not only queued support state.
        status: complete
        evidence:
          - /docker/fleet/scripts/materialize_support_case_packets.py compiles reporter followthrough from support packets only after install truth, installation-bound installed-build receipts, fixed-version receipts, fixed-channel receipts, installed-build receipts, and release-channel receipts agree.
          - /docker/fleet/tests/test_materialize_support_case_packets.py covers receipt gating.
          - /docker/fleet/.codex-studio/published/SUPPORT_CASE_PACKETS.generated.json reports successor_package_verification.status=pass.
          - /docker/fleet/.codex-studio/published/WEEKLY_GOVERNOR_PACKET.generated.json projects fix-available, please-test, and recovery counts.
          - /docker/fleet/scripts/verify_next90_m102_fleet_reporter_receipts.py fail-closes weekly/support generated_at freshness drift so WEEKLY_GOVERNOR_PACKET.generated.json cannot predate the SUPPORT_CASE_PACKETS.generated.json receipt gates it summarizes.
          - /docker/fleet/scripts/verify_next90_m102_fleet_reporter_receipts.py fail-closes weekly support-packet source sha256 drift so WEEKLY_GOVERNOR_PACKET.generated.json must name the exact SUPPORT_CASE_PACKETS.generated.json bytes it summarizes.
          - /docker/fleet/scripts/verify_script_bootstrap_no_pythonpath.py includes the standalone M102 verifier in no-PYTHONPATH bootstrap proof.
          - python3 scripts/verify_next90_m102_fleet_reporter_receipts.py exits 0.
      - id: 102.4
        owner: fleet
        title: Gate the staged reporter mail loop against real install and fix receipts, not only queued support state.
        status: complete
        evidence:
          - stale duplicate registry evidence row
""".lstrip(),
        encoding="utf-8",
    )
    queue.write_text(
        f"""
program_wave: next_90_day_product_advance
source_design_queue_path: {design_queue}
items:
  - title: Gate fix followthrough against real install and receipt truth
    task: Compile feedback, fix-available, please-test, and recovery loops from install-aware release receipts instead of queued support state alone.
    package_id: next90-m102-fleet-reporter-receipts
    frontier_id: 2454416974
    milestone_id: 102
    wave: W6
    repo: fleet
    status: complete
    proof:
      - /docker/fleet/scripts/materialize_support_case_packets.py
      - /docker/fleet/scripts/verify_next90_m102_fleet_reporter_receipts.py
      - /docker/fleet/tests/test_materialize_support_case_packets.py
      - /docker/fleet/tests/test_verify_next90_m102_fleet_reporter_receipts.py
      - /docker/fleet/scripts/verify_script_bootstrap_no_pythonpath.py
      - /docker/fleet/tests/test_fleet_script_bootstrap_without_pythonpath.py
      - /docker/fleet/.codex-studio/published/SUPPORT_CASE_PACKETS.generated.json
      - /docker/fleet/.codex-studio/published/WEEKLY_GOVERNOR_PACKET.generated.json
      - /docker/fleet/.codex-studio/published/WEEKLY_GOVERNOR_PACKET.generated.md
      - /docker/fleet/feedback/2026-04-15-next90-m102-fleet-reporter-receipts-closeout.md
      - python3 -m py_compile scripts/materialize_support_case_packets.py scripts/verify_next90_m102_fleet_reporter_receipts.py tests/test_materialize_support_case_packets.py tests/test_verify_next90_m102_fleet_reporter_receipts.py scripts/materialize_weekly_governor_packet.py tests/test_materialize_weekly_governor_packet.py
      - python3 scripts/verify_next90_m102_fleet_reporter_receipts.py exits 0
      - python3 tests/test_verify_next90_m102_fleet_reporter_receipts.py exits 0
      - installation-bound receipt gating blocks reporter followthrough when installed-build receipt installation id disagrees with the linked install
      - fixed-version receipts and fixed-channel receipts are required before reporter followthrough leaves hold
      - direct tmp_path fixture invocation for receipt-gated support followthrough tests exits 0
      - standalone verifier rejects missing receipt-gate names, missing weekly receipt counters, and active-run telemetry helper proof entries
      - successor frontier 2454416974 pinned for next90-m102-fleet-reporter-receipts repeat prevention
      - no-PYTHONPATH bootstrap guard includes the standalone M102 verifier
      - generated support-packet proof hygiene requires empty disallowed active-run proof entries
      - stale generated support proof gaps fail the standalone verifier
      - weekly/support receipt-count drift fails the standalone verifier
      - weekly/support generated_at freshness fails the standalone verifier
      - weekly support-packet source sha256 drift fails the standalone verifier
      - weekly support-packet source-path drift fails the standalone verifier
      - design queue source path rejects active-run helper paths
      - weekly governor source-path hygiene and worker command guard fail the standalone verifier
      - design-owned queue source proof markers fail the standalone verifier
      - telemetry command proof markers fail the standalone verifier and shared successor authority check
      - runtime handoff frontier metadata proof markers fail the standalone verifier and shared successor authority check
      - distinct queue proof anti-collapse guard prevents broad prose proof lines from satisfying command and negative-proof rows
      - design-owned queue source row matches the Fleet completed queue proof assignment
    allowed_paths:
      - scripts
      - tests
      - .codex-studio
      - feedback
    owned_surfaces:
      - feedback_loop_ready:install_receipts
      - product_governor:followthrough
""".lstrip(),
        encoding="utf-8",
    )
    design_queue.write_text(queue.read_text(encoding="utf-8").replace(f"source_design_queue_path: {design_queue}\n", ""), encoding="utf-8")

    with _override_design_queue_path(design_queue):
        verification = module._successor_package_verification(registry, queue)

    assert verification["status"] == "fail"
    assert verification["registry_work_task_count"] == 2
    assert "successor registry work task 102.4 appears more than once" in verification["issues"]


def test_materialize_support_case_packets_fails_successor_package_authority_on_design_queue_closure_drift(
    tmp_path: Path,
) -> None:
    module = _load_module()
    registry = tmp_path / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
    queue = tmp_path / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    design_queue = tmp_path / "DESIGN_NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    registry.write_text(
        """
product: chummer
program_wave: next_90_day_product_advance
milestones:
  - id: 102
    title: Desktop-native claim, update, rollback, and support followthrough
    wave: W6
    owners:
      - fleet
    status: in_progress
    dependencies:
      - 101
    work_tasks:
      - id: 102.4
        owner: fleet
        title: Gate the staged reporter mail loop against real install and fix receipts, not only queued support state.
        status: complete
        evidence:
          - /docker/fleet/scripts/materialize_support_case_packets.py compiles reporter followthrough from support packets only after install truth, installation-bound installed-build receipts, fixed-version receipts, fixed-channel receipts, and release-channel receipts agree.
          - /docker/fleet/tests/test_materialize_support_case_packets.py covers receipt gating.
          - /docker/fleet/.codex-studio/published/SUPPORT_CASE_PACKETS.generated.json reports successor_package_verification.status=pass.
          - /docker/fleet/.codex-studio/published/WEEKLY_GOVERNOR_PACKET.generated.json projects fix-available, please-test, and recovery counts.
""".lstrip(),
        encoding="utf-8",
    )
    queue.write_text(
        f"""
program_wave: next_90_day_product_advance
source_design_queue_path: {design_queue}
items:
  - title: Gate fix followthrough against real install and receipt truth
    task: Compile feedback, fix-available, please-test, and recovery loops from install-aware release receipts instead of queued support state alone.
    package_id: next90-m102-fleet-reporter-receipts
    frontier_id: 2454416974
    milestone_id: 102
    wave: W6
    repo: fleet
    status: complete
    proof:
      - /docker/fleet/scripts/materialize_support_case_packets.py
      - /docker/fleet/tests/test_materialize_support_case_packets.py
      - /docker/fleet/.codex-studio/published/SUPPORT_CASE_PACKETS.generated.json
      - /docker/fleet/.codex-studio/published/WEEKLY_GOVERNOR_PACKET.generated.json
      - /docker/fleet/.codex-studio/published/WEEKLY_GOVERNOR_PACKET.generated.md
      - /docker/fleet/feedback/2026-04-15-next90-m102-fleet-reporter-receipts-closeout.md
      - python3 -m py_compile scripts/materialize_support_case_packets.py tests/test_materialize_support_case_packets.py scripts/materialize_weekly_governor_packet.py tests/test_materialize_weekly_governor_packet.py
      - installation-bound receipt gating blocks reporter followthrough when installed-build receipt installation id disagrees with the linked install
      - fixed-version receipts and fixed-channel receipts are required before reporter followthrough leaves hold
      - direct tmp_path fixture invocation for receipt-gated support followthrough tests exits 0
      - successor frontier 2454416974 pinned for next90-m102-fleet-reporter-receipts repeat prevention
      - stale generated support proof gaps fail the standalone verifier
      - design-owned queue source row matches the Fleet completed queue proof assignment
    allowed_paths:
      - scripts
      - tests
      - .codex-studio
      - feedback
    owned_surfaces:
      - feedback_loop_ready:install_receipts
      - product_governor:followthrough
""".lstrip(),
        encoding="utf-8",
    )
    design_queue.write_text(
        """
program_wave: next_90_day_product_advance
items:
  - title: Gate fix followthrough against real install and receipt truth
    task: Compile feedback, fix-available, please-test, and recovery loops from install-aware release receipts instead of queued support state alone.
    package_id: next90-m102-fleet-reporter-receipts
    frontier_id: wrong-frontier
    milestone_id: 102
    wave: W6
    repo: fleet
    status: queued
    allowed_paths:
      - scripts
      - tests
      - .codex-studio
      - feedback
    owned_surfaces:
      - feedback_loop_ready:install_receipts
      - product_governor:followthrough
""".lstrip(),
        encoding="utf-8",
    )

    with _override_design_queue_path(design_queue):
        verification = module._successor_package_verification(registry, queue)

    assert verification["status"] == "fail"
    assert verification["design_queue_source_status"] == "queued"
    assert verification["design_queue_source_frontier_id"] == "wrong-frontier"
    assert "successor design queue source status drifted" in verification["issues"]
    assert "successor design queue source frontier_id drifted" in verification["issues"]


def test_materialize_support_case_packets_fails_successor_package_authority_when_design_queue_closure_missing(
    tmp_path: Path,
) -> None:
    module = _load_module()
    registry = tmp_path / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
    queue = tmp_path / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    design_queue = tmp_path / "DESIGN_NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    registry.write_text(
        """
product: chummer
program_wave: next_90_day_product_advance
milestones:
  - id: 102
    title: Desktop-native claim, update, rollback, and support followthrough
    wave: W6
    owners:
      - fleet
    status: in_progress
    dependencies:
      - 101
    work_tasks:
      - id: 102.4
        owner: fleet
        title: Gate the staged reporter mail loop against real install and fix receipts, not only queued support state.
        status: complete
        evidence:
          - /docker/fleet/scripts/materialize_support_case_packets.py compiles reporter followthrough from support packets only after install truth, installation-bound installed-build receipts, fixed-version receipts, fixed-channel receipts, and release-channel receipts agree.
          - /docker/fleet/tests/test_materialize_support_case_packets.py covers receipt gating.
          - /docker/fleet/.codex-studio/published/SUPPORT_CASE_PACKETS.generated.json reports successor_package_verification.status=pass.
          - /docker/fleet/.codex-studio/published/WEEKLY_GOVERNOR_PACKET.generated.json projects fix-available, please-test, and recovery counts.
""".lstrip(),
        encoding="utf-8",
    )
    queue.write_text(
        f"""
program_wave: next_90_day_product_advance
source_design_queue_path: {design_queue}
items:
  - title: Gate fix followthrough against real install and receipt truth
    task: Compile feedback, fix-available, please-test, and recovery loops from install-aware release receipts instead of queued support state alone.
    package_id: next90-m102-fleet-reporter-receipts
    frontier_id: 2454416974
    milestone_id: 102
    wave: W6
    repo: fleet
    status: complete
    proof:
      - /docker/fleet/scripts/materialize_support_case_packets.py
      - /docker/fleet/tests/test_materialize_support_case_packets.py
      - /docker/fleet/.codex-studio/published/SUPPORT_CASE_PACKETS.generated.json
      - /docker/fleet/.codex-studio/published/WEEKLY_GOVERNOR_PACKET.generated.json
      - /docker/fleet/.codex-studio/published/WEEKLY_GOVERNOR_PACKET.generated.md
      - /docker/fleet/feedback/2026-04-15-next90-m102-fleet-reporter-receipts-closeout.md
      - python3 -m py_compile scripts/materialize_support_case_packets.py tests/test_materialize_support_case_packets.py scripts/materialize_weekly_governor_packet.py tests/test_materialize_weekly_governor_packet.py
      - installation-bound receipt gating blocks reporter followthrough when installed-build receipt installation id disagrees with the linked install
      - fixed-version receipts and fixed-channel receipts are required before reporter followthrough leaves hold
      - direct tmp_path fixture invocation for receipt-gated support followthrough tests exits 0
      - successor frontier 2454416974 pinned for next90-m102-fleet-reporter-receipts repeat prevention
      - stale generated support proof gaps fail the standalone verifier
      - design-owned queue source row matches the Fleet completed queue proof assignment
    allowed_paths:
      - scripts
      - tests
      - .codex-studio
      - feedback
    owned_surfaces:
      - feedback_loop_ready:install_receipts
      - product_governor:followthrough
""".lstrip(),
        encoding="utf-8",
    )
    design_queue.write_text(
        """
program_wave: next_90_day_product_advance
items:
  - title: Gate fix followthrough against real install and receipt truth
    task: Compile feedback, fix-available, please-test, and recovery loops from install-aware release receipts instead of queued support state alone.
    package_id: next90-m102-fleet-reporter-receipts
    milestone_id: 102
    wave: W6
    repo: fleet
    allowed_paths:
      - scripts
      - tests
      - .codex-studio
      - feedback
    owned_surfaces:
      - feedback_loop_ready:install_receipts
      - product_governor:followthrough
""".lstrip(),
        encoding="utf-8",
    )

    with _override_design_queue_path(design_queue):
        verification = module._successor_package_verification(registry, queue)

    assert verification["status"] == "fail"
    assert verification["design_queue_source_status"] == ""
    assert verification["design_queue_source_frontier_id"] == ""
    assert "successor design queue source status drifted" in verification["issues"]
    assert "successor design queue source frontier_id drifted" in verification["issues"]


def test_materialize_support_case_packets_fails_successor_package_authority_when_proof_anchors_do_not_resolve(
    tmp_path: Path,
) -> None:
    module = _load_module()
    registry = tmp_path / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
    queue = tmp_path / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    missing_anchor = "/docker/fleet/feedback/missing-next90-m102-proof-anchor.md"
    registry.write_text(
        f"""
product: chummer
program_wave: next_90_day_product_advance
milestones:
  - id: 102
    title: Desktop-native claim, update, rollback, and support followthrough
    wave: W6
    owners:
      - fleet
    status: in_progress
    dependencies:
      - 101
    work_tasks:
      - id: 102.4
        owner: fleet
        title: Gate the staged reporter mail loop against real install and fix receipts, not only queued support state.
        status: complete
        evidence:
          - /docker/fleet/scripts/materialize_support_case_packets.py compiles reporter followthrough from support packets only after install truth, installation-bound installed-build receipts, fixed-version receipts, fixed-channel receipts, and release-channel receipts agree.
          - /docker/fleet/tests/test_materialize_support_case_packets.py covers receipt gating.
          - /docker/fleet/.codex-studio/published/SUPPORT_CASE_PACKETS.generated.json reports successor_package_verification.status=pass.
          - /docker/fleet/.codex-studio/published/WEEKLY_GOVERNOR_PACKET.generated.json projects fix-available, please-test, and recovery counts.
          - {missing_anchor} records the anti-reopen proof.
""".lstrip(),
        encoding="utf-8",
    )
    queue.write_text(
        f"""
program_wave: next_90_day_product_advance
items:
  - title: Gate fix followthrough against real install and receipt truth
    task: Compile feedback, fix-available, please-test, and recovery loops from install-aware release receipts instead of queued support state alone.
    package_id: next90-m102-fleet-reporter-receipts
    frontier_id: 2454416974
    milestone_id: 102
    wave: W6
    repo: fleet
    status: complete
    proof:
      - /docker/fleet/scripts/materialize_support_case_packets.py
      - /docker/fleet/tests/test_materialize_support_case_packets.py
      - /docker/fleet/.codex-studio/published/SUPPORT_CASE_PACKETS.generated.json
      - /docker/fleet/.codex-studio/published/WEEKLY_GOVERNOR_PACKET.generated.json
      - /docker/fleet/.codex-studio/published/WEEKLY_GOVERNOR_PACKET.generated.md
      - {missing_anchor}
      - /docker/fleet/feedback/2026-04-15-next90-m102-fleet-reporter-receipts-closeout.md
      - python3 -m py_compile scripts/materialize_support_case_packets.py tests/test_materialize_support_case_packets.py scripts/materialize_weekly_governor_packet.py tests/test_materialize_weekly_governor_packet.py
      - installation-bound receipt gating blocks reporter followthrough when installed-build receipt installation id disagrees with the linked install
      - fixed-version receipts and fixed-channel receipts are required before reporter followthrough leaves hold
      - direct tmp_path fixture invocation for receipt-gated support followthrough tests exits 0
      - successor frontier 2454416974 pinned for next90-m102-fleet-reporter-receipts repeat prevention
      - stale generated support proof gaps fail the standalone verifier
    allowed_paths:
      - scripts
      - tests
      - .codex-studio
      - feedback
    owned_surfaces:
      - feedback_loop_ready:install_receipts
      - product_governor:followthrough
""".lstrip(),
        encoding="utf-8",
    )

    verification = module._successor_package_verification(registry, queue)

    assert verification["status"] == "fail"
    assert verification["missing_registry_proof_anchor_paths"] == [missing_anchor]
    assert verification["missing_queue_proof_anchor_paths"] == [missing_anchor]
    assert (
        f"successor registry work task evidence anchor missing on disk: {missing_anchor}"
        in verification["issues"]
    )
    assert f"successor queue item proof anchor missing on disk: {missing_anchor}" in verification["issues"]


def test_materialize_support_case_packets(tmp_path: Path) -> None:
    source = tmp_path / "support_cases.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    source.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "caseId": "support_case_a",
                        "clusterKey": "support:aaaa",
                        "kind": "bug_report",
                        "status": "new",
                        "title": "Desktop crash on save",
                        "summary": "Save explodes in preview.",
                        "candidateOwnerRepo": "chummer6-ui",
                        "designImpactSuspected": False,
                        "installationId": "install-alpha",
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "linux",
                        "arch": "x64",
                    },
                    {
                        "caseId": "support_case_b",
                        "clusterKey": "support:bbbb",
                        "kind": "feedback",
                        "status": "clustered",
                        "title": "Downloads copy is confusing",
                        "summary": "I cannot tell which build to install.",
                        "candidateOwnerRepo": "chummer6-hub",
                        "designImpactSuspected": True,
                        "releaseChannel": "preview",
                    },
                    {
                        "caseId": "support_case_c",
                        "clusterKey": "support:cccc",
                        "kind": "feedback",
                        "status": "deferred",
                        "title": "Already closed",
                        "summary": "This should not remain in the public packet list.",
                        "candidateOwnerRepo": "chummer6-hub",
                        "designImpactSuspected": False,
                    },
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source",
            str(source),
            "--release-channel",
            str(release_channel),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["contract_name"] == "fleet.support_case_packets"
    assert payload["summary"]["open_case_count"] == 2
    assert payload["summary"]["open_non_external_packet_count"] == 2
    assert payload["summary"]["support_case_backed_open_count"] == 2
    assert payload["summary"]["design_impact_count"] == 1
    assert payload["summary"]["owner_repo_counts"] == {
        "chummer6-design": 1,
        "chummer6-ui": 1,
    }
    assert payload["summary"]["closure_waiting_on_release_truth"] == 0
    assert payload["summary"]["needs_human_response"] == 2
    assert payload["summary"]["non_external_needs_human_response"] == 2
    assert payload["summary"]["non_external_packets_without_named_owner"] == 0
    assert payload["summary"]["non_external_packets_without_lane"] == 0
    assert payload["summary"]["update_required_case_count"] == 0
    assert payload["summary"]["update_required_routed_to_downloads_count"] == 0
    assert payload["summary"]["update_required_misrouted_case_count"] == 0
    assert payload["summary"]["external_proof_required_case_count"] == 0
    assert payload["summary"]["external_proof_required_host_counts"] == {}
    assert payload["summary"]["external_proof_required_tuple_counts"] == {}
    assert payload["summary"]["unresolved_external_proof_request_count"] == 0
    assert payload["summary"]["unresolved_external_proof_request_host_counts"] == {}
    assert payload["summary"]["unresolved_external_proof_request_tuple_counts"] == {}
    assert payload["summary"]["unresolved_external_proof_request_hosts"] == []
    assert payload["summary"]["unresolved_external_proof_request_tuples"] == []
    assert payload["summary"]["unresolved_external_proof_request_specs"] == {}
    assert payload["unresolved_external_proof_execution_plan"]["request_count"] == 0
    assert payload["unresolved_external_proof_execution_plan"]["hosts"] == []
    assert payload["unresolved_external_proof_execution_plan"]["host_groups"] == {}
    assert payload["unresolved_external_proof_execution_plan"]["capture_deadline_hours"] == 24
    assert payload["unresolved_external_proof_execution_plan"]["command_root"] == (
        "/docker/fleet/.codex-studio/published/external-proof-commands"
    )
    assert payload["unresolved_external_proof_execution_plan"]["generated_at"]
    assert (
        payload["unresolved_external_proof_execution_plan"]["recommended_action"]
        == "No unresolved external desktop host-proof requests remain."
    )
    assert payload["source"]["source_kind"] == "local_file"
    assert len(payload["packets"]) == 2
    bug_packet = next(item for item in payload["packets"] if item["kind"] == "bug_report")
    canon_packet = next(item for item in payload["packets"] if item["target_repo"] == "chummer6-design")
    assert bug_packet["primary_lane"] == "code"
    assert bug_packet["target_repo"] == "chummer6-ui"
    assert bug_packet["install_truth_state"] in {
        "registry_unavailable",
        "channel_mismatch",
        "promoted_tuple_match",
        "tuple_not_on_promoted_shelf",
        "insufficient_install_context",
    }
    assert isinstance(bug_packet["install_diagnosis"], dict)
    assert isinstance(bug_packet["fix_confirmation"], dict)
    assert isinstance(bug_packet["recovery_path"], dict)
    assert canon_packet["primary_lane"] == "canon"
    assert "FEEDBACK_AND_SIGNAL_OODA_LOOP.md" in canon_packet["affected_canon_files"]
    assert "reporter_subject_id" not in bug_packet
    assert "case_id" not in bug_packet
    assert "cluster_key" not in bug_packet
    assert "title" not in bug_packet
    assert "summary" not in bug_packet


def test_materialize_support_case_packets_refreshes_compile_manifest(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    published = repo_root / ".codex-studio" / "published"
    published.mkdir(parents=True)
    source = tmp_path / "support_cases.json"
    source.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "caseId": "support_case_install",
                        "clusterKey": "support:install",
                        "kind": "install_help",
                        "status": "new",
                        "title": "Need install help",
                        "summary": "Updater is blocked.",
                        "candidateOwnerRepo": "chummer6-hub",
                        "designImpactSuspected": False,
                    }
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source",
            str(source),
            "--out",
            str(published / "SUPPORT_CASE_PACKETS.generated.json"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    manifest_payload = json.loads((published / "compile.manifest.json").read_text(encoding="utf-8"))
    assert "SUPPORT_CASE_PACKETS.generated.json" in manifest_payload["artifacts"]


def test_refresh_weekly_governor_packet_if_possible_materializes_weekly_packet(tmp_path: Path) -> None:
    module = _load_module()
    patch = _DirectMonkeyPatch()
    try:
        repo_root = tmp_path / "repo"
        published = repo_root / ".codex-studio" / "published"
        published.mkdir(parents=True)
        support_packets = published / "SUPPORT_CASE_PACKETS.generated.json"
        support_packets.write_text("{}\n", encoding="utf-8")

        successor_registry = tmp_path / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
        closed_flagship_registry = tmp_path / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
        design_queue = tmp_path / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
        queue = tmp_path / "QUEUE.generated.yaml"
        weekly_pulse = tmp_path / "WEEKLY_PRODUCT_PULSE.generated.json"
        flagship_readiness = tmp_path / "FLAGSHIP_PRODUCT_READINESS.generated.json"
        journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
        status_plane = tmp_path / "STATUS.generated.yaml"
        for path in (
            successor_registry,
            closed_flagship_registry,
            design_queue,
            queue,
            weekly_pulse,
            flagship_readiness,
            journey_gates,
            status_plane,
        ):
            path.write_text("{}\n", encoding="utf-8")

        calls: dict[str, object] = {}

        class _FakeWeekly:
            @staticmethod
            def parse_args(argv: list[str]):
                calls["argv"] = list(argv)
                return type(
                    "Args",
                    (),
                    {
                        "out": str(published / "WEEKLY_GOVERNOR_PACKET.generated.json"),
                        "successor_registry": str(successor_registry),
                        "closed_flagship_registry": str(closed_flagship_registry),
                        "design_queue_staging": str(design_queue),
                        "queue_staging": str(queue),
                        "weekly_pulse": str(weekly_pulse),
                        "flagship_readiness": str(flagship_readiness),
                        "journey_gates": str(journey_gates),
                        "support_packets": str(support_packets),
                        "status_plane": str(status_plane),
                    },
                )()

            @staticmethod
            def materialize(args):
                calls["materialized_out"] = args.out
                return Path(args.out)

        patch.setattr(module, "_load_weekly_governor_materializer_module", lambda: _FakeWeekly)

        refreshed = module._refresh_weekly_governor_packet_if_possible(repo_root, support_packets)

        assert refreshed is True
        assert calls["argv"] == ["--out", str(published / "WEEKLY_GOVERNOR_PACKET.generated.json")]
        assert calls["materialized_out"] == str(published / "WEEKLY_GOVERNOR_PACKET.generated.json")
    finally:
        patch.undo()


def test_materialize_support_case_packets_reads_authenticated_remote_source(tmp_path: Path) -> None:
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    payload = {
        "items": [
            {
                "caseId": "support_case_remote",
                "clusterKey": "support:remote",
                "kind": "install_help",
                "status": "new",
                "title": "Need install help",
                "summary": "Remote triage feed works.",
                "candidateOwnerRepo": "chummer6-hub",
                "designImpactSuspected": False,
            }
        ]
    }
    token = "remote-token"

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.headers.get("Authorization") != f"Bearer {token}":
                self.send_response(401)
                self.end_headers()
                return
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):  # noqa: A003
            return

    with socketserver.TCPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--source",
                    f"http://127.0.0.1:{server.server_address[1]}/api/v1/support/cases/triage",
                    "--bearer-token",
                    token,
                    "--out",
                    str(out_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        finally:
            server.shutdown()
            thread.join(timeout=5)

    assert result.returncode == 0, result.stderr
    rendered = json.loads(out_path.read_text(encoding="utf-8"))
    assert rendered["source"]["source_kind"] == "remote_url"
    assert rendered["summary"]["open_case_count"] == 1


def test_load_json_source_via_curl_keeps_bearer_token_out_of_argv(tmp_path: Path, monkeypatch) -> None:
    module = _load_module()
    capture: dict[str, object] = {}

    def fake_run(cmd, **kwargs):
        assert kwargs["check"] is False
        assert kwargs["capture_output"] is True
        assert kwargs["text"] is True
        capture["cmd"] = list(cmd)
        config_path = Path(cmd[cmd.index("-K") + 1])
        capture["config_path"] = str(config_path)
        capture["config_text"] = config_path.read_text(encoding="utf-8")

        class _Completed:
            returncode = 0
            stdout = '{"items":[],"count":0}'

        return _Completed()

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    payload = module._load_json_source_via_curl(
        "https://example.invalid/api/v1/support/cases/triage",
        bearer_token="secret-support-token",
    )

    assert payload == {"items": [], "count": 0}
    cmd = capture["cmd"]
    assert isinstance(cmd, list)
    assert "secret-support-token" not in " ".join(str(item) for item in cmd)
    assert "-K" in cmd
    assert 'Authorization: Bearer secret-support-token' in str(capture["config_text"])
    assert not Path(str(capture["config_path"])).exists()


def test_materialize_support_case_packets_falls_back_from_host_docker_internal(tmp_path: Path) -> None:
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    payload = {
        "items": [
            {
                "caseId": "support_case_host_fallback",
                "clusterKey": "support:host-fallback",
                "kind": "install_help",
                "status": "new",
                "title": "Need install help",
                "summary": "host.docker.internal fallback works.",
                "candidateOwnerRepo": "chummer6-hub",
                "designImpactSuspected": False,
            }
        ]
    }

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.headers.get("X-Forwarded-Proto") != "https":
                self.send_response(307)
                self.send_header("Location", f"https://127.0.0.1{self.path}")
                self.end_headers()
                return
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):  # noqa: A003
            return

    with socketserver.TCPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--source",
                    f"http://host.docker.internal:{server.server_address[1]}/api/v1/support/cases/triage",
                    "--out",
                    str(out_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        finally:
            server.shutdown()
            thread.join(timeout=5)

    assert result.returncode == 0, result.stderr
    rendered = json.loads(out_path.read_text(encoding="utf-8"))
    assert rendered["source"]["source_kind"] == "remote_url"
    assert rendered["summary"]["open_case_count"] == 1


def test_materialize_support_case_packets_reads_source_from_runtime_env_file(tmp_path: Path) -> None:
    source = tmp_path / "support_cases.json"
    env_file = tmp_path / "runtime.env"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "caseId": "support_case_env",
                        "clusterKey": "support:env",
                        "kind": "install_help",
                        "status": "new",
                        "title": "Need install help",
                        "summary": "Runtime env source works.",
                        "candidateOwnerRepo": "chummer6-hub",
                        "designImpactSuspected": False,
                    }
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    env_file.write_text(
        f"FLEET_SUPPORT_CASE_SOURCE={source}\nFLEET_INTERNAL_API_TOKEN=token-from-runtime-env\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        env={"PATH": os.environ.get("PATH", ""), "FLEET_RUNTIME_ENV_PATHS": str(env_file)},
    )

    assert result.returncode == 0, result.stderr
    rendered = json.loads(out_path.read_text(encoding="utf-8"))
    assert rendered["source"]["source_kind"] == "local_file"
    assert rendered["summary"]["open_case_count"] == 1


def test_materialize_support_case_packets_falls_back_to_cached_snapshot_when_remote_source_is_unavailable(tmp_path: Path) -> None:
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    out_path.write_text(
        json.dumps(
            {
                "contract_name": "fleet.support_case_packets",
                "schema_version": 1,
                "generated_at": "2026-04-08T00:00:00Z",
                "source": {
                    "source_kind": "remote_url",
                    "reported_count": 1,
                    "materialized_count": 1,
                    "case_materialized_count": 1,
                    "operator_packet_count": 0,
                },
                "summary": {
                    "open_case_count": 1,
                    "open_packet_count": 1,
                    "operator_packet_count": 0,
                    "design_impact_count": 0,
                    "owner_repo_counts": {"chummer6-ui": 1},
                    "lane_counts": {"code": 1},
                    "status_counts": {"new": 1},
                },
                "unresolved_external_proof": {
                    "count": 0,
                    "host_counts": {},
                    "tuple_counts": {},
                    "hosts": [],
                    "tuples": [],
                    "specs": {},
                },
                "unresolved_external_proof_execution_plan": {
                    "request_count": 0,
                    "hosts": [],
                    "host_groups": {},
                    "capture_deadline_hours": 24,
                    "generated_at": "2026-04-08T00:00:00Z",
                },
                "packets": [
                    {
                        "support_case_backed": True,
                        "target_repo": "chummer6-ui",
                        "primary_lane": "code",
                        "status": "new",
                        "design_impact_suspected": False,
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source",
            "http://127.0.0.1:9/api/v1/support/cases/triage",
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    rendered = json.loads(out_path.read_text(encoding="utf-8"))
    assert rendered["source"]["refresh_mode"] in {"source_mirror_fallback", "cached_packets_fallback"}
    assert rendered["source"]["refresh_error"]
    assert rendered["summary"]["open_case_count"] == 1


def test_cached_packet_fallback_rebuilds_followthrough_without_trusting_cached_receipt_state() -> None:
    module = _load_module()
    release_channel_index = module._release_channel_index(
        {
            "channelId": "preview",
            "status": "published",
            "version": "1.2.3",
            "releaseProof": {"status": "passed"},
            "desktopTupleCoverage": {
                "promotedInstallerTuples": [
                    {
                        "tupleId": "avalonia:linux-x64:linux",
                        "head": "avalonia",
                        "platform": "linux",
                        "rid": "linux-x64",
                        "artifactId": "avalonia-linux-x64-installer",
                    }
                ]
            },
        }
    )

    payload = module._cached_packets_fallback_payload(
        {
            "generated_at": "2026-04-17T18:00:00Z",
            "packets": [
                {
                    "support_case_backed": True,
                    "packet_id": "support_packet_cached_ready",
                    "kind": "bug_report",
                    "status": "fixed",
                    "target_repo": "chummer6-ui",
                    "installation_id": "install-cached-ready",
                    "release_channel": "preview",
                    "head_id": "avalonia",
                    "platform": "linux",
                    "arch": "x64",
                    "installed_version": "1.2.3",
                    "fixed_version": "1.2.3",
                    "fixed_channel": "preview",
                    "reporter_followthrough": {
                        "state": "please_test_ready",
                        "feedback_loop_ready": True,
                        "installed_build_receipt_id": "install-receipt-cached-ready",
                        "installed_build_receipt_installation_id": "install-cached-ready",
                        "installed_build_receipt_version": "1.2.3",
                        "installed_build_receipt_channel": "preview",
                        "fixed_version_receipt_id": "fix-version-receipt-cached-ready",
                        "fixed_channel_receipt_id": "fix-channel-receipt-cached-ready",
                    },
                }
            ],
        },
        source_label="https://chummer.run/api/v1/support/cases/triage",
        release_channel_index=release_channel_index,
        refresh_error="HTTP Error 401: Unauthorized",
    )

    assert payload["source"]["refresh_mode"] == "cached_packets_fallback"
    assert payload["source"]["install_receipt_feed_state"] == "not_provided"
    assert payload["source"]["fix_receipt_feed_state"] == "not_provided"
    assert payload["summary"]["reporter_followthrough_ready_count"] == 0
    assert payload["summary"]["feedback_followthrough_ready_count"] == 0
    assert payload["summary"]["please_test_ready_count"] == 0
    packet = payload["packets"][0]
    assert packet["reporter_followthrough"]["state"] == "blocked_missing_install_receipts"
    assert packet["reporter_followthrough"]["installed_build_receipted"] is False
    assert packet["reporter_followthrough"]["fixed_version_receipted"] is False
    assert payload["reporter_followthrough_plan"]["ready_count"] == 0
    assert payload["reporter_followthrough_plan"]["action_groups"]["please_test"] == []


def test_source_mirror_fallback_seeded_from_cached_packets_preserves_cached_provenance() -> None:
    module = _load_module()
    release_channel_index = module._release_channel_index(
        {
            "channelId": "preview",
            "status": "published",
            "version": "1.2.3",
            "releaseProof": {"status": "passed"},
            "desktopTupleCoverage": {
                "promotedInstallerTuples": [
                    {
                        "tupleId": "avalonia:linux-x64:linux",
                        "head": "avalonia",
                        "platform": "linux",
                        "rid": "linux-x64",
                        "artifactId": "avalonia-linux-x64-installer",
                    }
                ]
            },
        }
    )

    payload = module._source_mirror_fallback_payload(
        {
            "items": [
                {
                    "caseId": "support_case_cached_seed",
                    "clusterKey": "support:cached-seed",
                    "kind": "bug_report",
                    "status": "fixed",
                    "candidateOwnerRepo": "chummer6-ui",
                    "installationId": "install-cached-seed",
                    "releaseChannel": "preview",
                    "headId": "avalonia",
                    "platform": "linux",
                    "arch": "x64",
                    "installedVersion": "1.2.3",
                    "fixedVersion": "1.2.3",
                    "fixedChannel": "preview",
                    "installedBuildReceiptId": "install-receipt-cached-seed",
                    "installedBuildReceiptInstallationId": "install-cached-seed",
                    "installedBuildReceiptVersion": "1.2.3",
                    "installedBuildReceiptChannel": "preview",
                }
            ],
            "count": 1,
            "mirrored_at": "2026-04-18T18:00:00Z",
            "origin_source_label": "https://chummer.run/api/v1/support/cases/triage",
            "origin_source_kind": "remote_url",
            "seeded_from_cached_packets_generated_at": "2026-04-18T17:55:00Z",
        },
        source_label="https://chummer.run/api/v1/support/cases/triage",
        source_mirror_path=Path("/tmp/SUPPORT_CASE_SOURCE_MIRROR.generated.json"),
        release_channel_index=release_channel_index,
        refresh_error="HTTP Error 401: Unauthorized",
    )

    assert payload["source"]["refresh_mode"] == "cached_packets_fallback"
    assert payload["source"]["seeded_from_cached_packets_generated_at"] == "2026-04-18T17:55:00Z"
    assert payload["summary"]["reporter_followthrough_ready_count"] == 0
    assert payload["summary"]["please_test_ready_count"] == 0


def test_materialize_support_case_packets_enriches_install_truth_from_release_channel(tmp_path: Path) -> None:
    module = _load_module()
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "caseId": "support_case_release_waiting",
                        "clusterKey": "support:release",
                        "kind": "bug_report",
                        "status": "fixed",
                        "title": "Fix is staged",
                        "summary": "Reporter still needs to verify.",
                        "candidateOwnerRepo": "chummer6-ui",
                        "designImpactSuspected": False,
                        "installationId": "install-release-1",
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "linux",
                        "arch": "x64",
                        "installedVersion": "1.2.3",
                        "installedBuildReceiptId": "install-receipt-release-1",
                        "installedBuildReceiptInstallationId": "install-release-1",
                        "installedBuildReceiptVersion": "1.2.3",
                        "installedBuildReceiptChannel": "preview",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                    },
                    {
                        "caseId": "support_case_confirmed",
                        "clusterKey": "support:confirmed",
                        "kind": "install_help",
                        "status": "user_notified",
                        "title": "Confirmed fix",
                        "summary": "Reporter confirmed the fix.",
                        "candidateOwnerRepo": "chummer6-hub",
                        "designImpactSuspected": False,
                        "installationId": "install-release-2",
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "linux",
                        "arch": "x64",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                        "reporterVerificationState": "confirmed_fixed",
                    },
                ],
                "installReceipts": [
                    {
                        "installationId": "install-release-1",
                        "receiptId": "install-receipt-release-1",
                        "version": "1.2.3",
                        "channel": "preview",
                    },
                    {
                        "installationId": "install-release-2",
                        "receiptId": "install-receipt-release-2",
                        "version": "1.2.3",
                        "channel": "preview",
                    },
                ],
                "fixedReleaseReceipts": [
                    {
                        "caseId": "support_case_release_waiting",
                        "installationId": "install-release-1",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                        "fixedVersionReceiptId": "fix-version-receipt-release-1",
                        "fixedChannelReceiptId": "fix-channel-receipt-release-1",
                    },
                    {
                        "caseId": "support_case_confirmed",
                        "installationId": "install-release-2",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                        "fixedVersionReceiptId": "fix-version-receipt-release-2",
                        "fixedChannelReceiptId": "fix-channel-receipt-release-2",
                    },
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "rolloutState": "published",
                "supportabilityState": "supported",
                "fixAvailabilitySummary": "Fix is on the preview shelf.",
                "desktopTupleCoverage": {
                    "promotedInstallerTuples": [
                        {
                            "tupleId": "avalonia:linux:linux-x64",
                            "head": "avalonia",
                            "platform": "linux",
                            "rid": "linux-x64",
                            "artifactId": "avalonia-linux-x64-installer",
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source",
            str(source),
            "--release-channel",
            str(release_channel),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["open_case_count"] == 1
    assert payload["summary"]["closure_waiting_on_release_truth"] == 1
    assert payload["summary"]["needs_human_response"] == 0
    assert payload["summary"]["open_non_external_packet_count"] == 1
    assert payload["summary"]["non_external_needs_human_response"] == 0
    assert payload["summary"]["non_external_packets_without_named_owner"] == 0
    assert payload["summary"]["non_external_packets_without_lane"] == 0
    assert payload["summary"]["install_truth_state_counts"]["promoted_tuple_match"] == 1
    assert payload["summary"]["update_required_case_count"] == 0
    assert payload["summary"]["update_required_routed_to_downloads_count"] == 0
    assert payload["summary"]["update_required_misrouted_case_count"] == 0
    assert payload["summary"]["reporter_followthrough_ready_count"] == 1
    assert payload["summary"]["feedback_followthrough_ready_count"] == 1
    assert payload["summary"]["reporter_followthrough_blocked_missing_install_receipts_count"] == 0
    assert payload["summary"]["fix_available_ready_count"] == 0
    assert payload["summary"]["please_test_ready_count"] == 1
    assert payload["summary"]["recovery_loop_ready_count"] == 1
    assert payload["summary"]["external_proof_required_case_count"] == 0
    assert payload["summary"]["external_proof_required_host_counts"] == {}
    assert payload["summary"]["external_proof_required_tuple_counts"] == {}
    assert payload["summary"]["unresolved_external_proof_request_count"] == 0
    assert payload["summary"]["unresolved_external_proof_request_host_counts"] == {}
    assert payload["summary"]["unresolved_external_proof_request_tuple_counts"] == {}
    assert payload["summary"]["unresolved_external_proof_request_hosts"] == []
    assert payload["summary"]["unresolved_external_proof_request_tuples"] == []
    assert payload["summary"]["unresolved_external_proof_request_specs"] == {}
    waiting_packet = next(item for item in payload["packets"] if item["kind"] == "bug_report")
    assert waiting_packet["install_diagnosis"]["registry_channel_id"] == "preview"
    assert waiting_packet["install_diagnosis"]["registry_release_channel_status"] == "published"
    assert waiting_packet["install_diagnosis"]["tuple_present_on_promoted_shelf"] is True
    assert waiting_packet["install_diagnosis"]["registry_release_proof_status"] == "passed"
    assert waiting_packet["install_diagnosis"]["external_proof_required"] is False
    assert waiting_packet["install_diagnosis"]["external_proof_request"] == {
        "tuple_id": "",
        "channel_id": "",
        "tuple_entry_count": 0,
        "tuple_unique": False,
        "required_host": "",
        "required_proofs": [],
        "expected_artifact_id": "",
        "expected_installer_file_name": "",
        "expected_installer_relative_path": "",
        "expected_public_install_route": "",
        "expected_startup_smoke_receipt_path": "",
        "startup_smoke_receipt_contract": {},
        "proof_capture_commands": [],
        "local_evidence": {
            "installer_artifact": {
                "path": "",
                "present": False,
                "state": "missing",
            },
            "startup_smoke_receipt": {
                "path": "",
                "present": False,
                "state": "missing",
                "max_age_seconds": module.REQUIRED_STARTUP_SMOKE_MAX_AGE_SECONDS,
            },
        },
    }
    assert waiting_packet["recovery_path"]["href"] == "/account/support"
    assert waiting_packet["reporter_followthrough"]["state"] == "please_test_ready"
    assert waiting_packet["reporter_followthrough"]["next_action"] == "send_please_test"
    assert waiting_packet["reporter_followthrough"]["feedback_loop_ready"] is True
    assert waiting_packet["reporter_followthrough"]["install_receipt_ready"] is True
    assert waiting_packet["reporter_followthrough"]["release_receipt_state"] == "release_receipt_ready"
    assert waiting_packet["reporter_followthrough"]["release_receipt_id"] == "release-channel:preview:1.2.3:passed"
    assert waiting_packet["reporter_followthrough"]["release_receipt_source"] == "release_channel"
    assert waiting_packet["reporter_followthrough"]["release_receipt_version"] == "1.2.3"
    assert waiting_packet["reporter_followthrough"]["release_receipt_channel"] == "preview"
    assert waiting_packet["reporter_followthrough"]["fixed_version_receipted"] is True
    assert waiting_packet["reporter_followthrough"]["fixed_channel_receipted"] is True
    assert waiting_packet["reporter_followthrough"]["installed_build_receipted"] is True
    assert waiting_packet["reporter_followthrough"]["installed_build_receipt_id"] == "install-receipt-release-1"
    assert waiting_packet["reporter_followthrough"]["installed_build_receipt_source"] == "install_receipts"
    assert (
        waiting_packet["reporter_followthrough"]["installed_build_receipt_installation_source"]
        == "install_receipts"
    )
    assert waiting_packet["reporter_followthrough"]["installed_build_receipt_version_source"] == "install_receipts"
    assert waiting_packet["reporter_followthrough"]["installed_build_receipt_channel_source"] == "install_receipts"
    assert waiting_packet["reporter_followthrough"]["fixed_version_receipt_source"] == "fix_receipts"
    assert waiting_packet["reporter_followthrough"]["fixed_channel_receipt_source"] == "fix_receipts"
    assert waiting_packet["reporter_followthrough"]["fixed_receipt_installation_source"] == "fix_receipts"
    assert waiting_packet["reporter_followthrough"]["current_install_on_fixed_build"] is True
    assert waiting_packet["reporter_followthrough"]["blockers"] == []
    followthrough_plan = payload["reporter_followthrough_plan"]
    assert followthrough_plan["package_id"] == "next90-m102-fleet-reporter-receipts"
    assert followthrough_plan["ready_count"] == 1
    assert followthrough_plan["feedback_ready_count"] == 1
    assert followthrough_plan["fix_available_ready_count"] == 0
    assert followthrough_plan["please_test_ready_count"] == 1
    assert followthrough_plan["recovery_loop_ready_count"] == 1
    assert followthrough_plan["blocked_missing_install_receipts_count"] == 0
    assert len(followthrough_plan["action_groups"]["feedback"]) == 1
    assert followthrough_plan["action_groups"]["feedback"][0]["next_action"] == "send_feedback_progress"
    assert followthrough_plan["action_groups"]["fix_available"] == []
    assert len(followthrough_plan["action_groups"]["recovery"]) == 1
    assert followthrough_plan["action_groups"]["recovery"][0]["packet_id"] == waiting_packet["packet_id"]
    assert followthrough_plan["action_groups"]["recovery"][0]["recovery_loop_ready"] is True
    assert followthrough_plan["action_groups"]["recovery"][0]["next_action"] == "send_recovery"
    assert len(followthrough_plan["action_groups"]["please_test"]) == 1
    please_test_row = followthrough_plan["action_groups"]["please_test"][0]
    assert please_test_row["packet_id"] == waiting_packet["packet_id"]
    assert please_test_row["next_action"] == "send_please_test"
    assert please_test_row["installed_build_receipt_id"] == "install-receipt-release-1"
    assert please_test_row["installed_build_receipt_source"] == "install_receipts"
    assert please_test_row["release_receipt_state"] == "release_receipt_ready"
    assert please_test_row["release_receipt_id"] == "release-channel:preview:1.2.3:passed"
    assert please_test_row["release_receipt_source"] == "release_channel"
    assert please_test_row["release_receipt_version"] == "1.2.3"
    assert please_test_row["release_receipt_channel"] == "preview"
    receipt_gates = payload["followthrough_receipt_gates"]
    assert receipt_gates["package_id"] == "next90-m102-fleet-reporter-receipts"
    assert receipt_gates["ready_count"] == 1
    assert receipt_gates["blocked_missing_install_receipts_count"] == 0
    assert receipt_gates["blocked_receipt_mismatch_count"] == 0
    assert receipt_gates["gate_counts"]["install_receipt_ready"] == 1
    assert receipt_gates["gate_counts"]["install_truth_ready"] == 1
    assert receipt_gates["gate_counts"]["feedback_loop_ready"] == 1
    assert receipt_gates["gate_counts"]["release_receipt_ready"] == 1
    assert receipt_gates["gate_counts"]["release_receipt_id_present"] == 1
    assert receipt_gates["gate_counts"]["fixed_version_receipted"] == 1
    assert receipt_gates["gate_counts"]["fixed_channel_receipted"] == 1
    assert "fixed_receipt_installation_bound" in receipt_gates["required_gates"]
    assert receipt_gates["gate_counts"]["fixed_receipt_installation_bound"] == 1
    assert receipt_gates["gate_counts"]["installed_build_receipted"] == 1
    assert receipt_gates["gate_counts"]["installed_build_receipt_installation_bound"] == 1
    assert receipt_gates["gate_counts"]["installed_build_receipt_version_matches"] == 1
    assert receipt_gates["gate_counts"]["installed_build_receipt_channel_matches"] == 1
    assert receipt_gates["blocker_counts"] == {}
    fix_states = sorted(item["fix_confirmation"]["state"] for item in payload["packets"])
    assert fix_states == ["awaiting_reporter_verification"]


def test_followthrough_plan_recomputes_ready_groups_from_receipt_truth() -> None:
    module = _load_module()

    plan = module._reporter_followthrough_plan(
        [
            {
                "support_case_backed": True,
                "packet_id": "support_packet_stale_ready",
                "kind": "bug_report",
                "status": "fixed",
                "target_repo": "chummer6-ui",
                "installation_id": "install-stale-ready-1",
                "release_channel": "preview",
                "head_id": "avalonia",
                "platform": "linux",
                "arch": "x64",
                "installed_version": "1.2.3",
                "fixed_version": "1.2.3",
                "fixed_channel": "preview",
                "recovery_path": {"action_id": "open_downloads", "href": "/downloads"},
                "reporter_followthrough": {
                    "state": "please_test_ready",
                    "next_action": "send_please_test",
                    "feedback_loop_ready": True,
                    "install_receipt_ready": True,
                    "fixed_version_receipted": True,
                    "fixed_channel_receipted": True,
                    "installed_build_receipted": True,
                    "current_install_on_fixed_build": True,
                    "recovery_loop_ready": True,
                    "release_receipt_state": "release_receipt_ready",
                    "release_receipt_id": "release-channel:preview:1.2.3:passed",
                    "release_receipt_source": "release_channel",
                    "release_receipt_channel": "preview",
                    "release_receipt_version": "1.2.3",
                    "installed_build_receipt_id": "install-receipt-stale-ready-1",
                    "installed_build_receipt_installation_id": "install-stale-ready-1",
                    "installed_build_receipt_version": "1.2.3",
                    "installed_build_receipt_channel": "preview",
                    "installed_build_receipt_head_id": "avalonia",
                    "installed_build_receipt_platform": "linux",
                    "installed_build_receipt_rid": "linux-x64",
                    "installed_build_receipt_tuple_id": "avalonia:linux-x64:linux",
                    "installed_build_receipt_source": "queued_support_state",
                    "installed_build_receipt_installation_source": "queued_support_state",
                    "installed_build_receipt_version_source": "queued_support_state",
                    "installed_build_receipt_channel_source": "queued_support_state",
                    "installed_build_receipt_installation_matches": True,
                    "installed_build_receipt_version_matches": True,
                    "installed_build_receipt_channel_matches": True,
                    "installed_build_receipt_identity_matches": True,
                    "fixed_version_receipt_id": "fix-version-receipt-stale-ready-1",
                    "fixed_channel_receipt_id": "fix-channel-receipt-stale-ready-1",
                    "fixed_receipt_installation_id": "install-stale-ready-1",
                    "fixed_receipt_installation_source": "queued_support_state",
                    "fixed_receipt_installation_matches": True,
                    "fixed_version_receipt_source": "queued_support_state",
                    "fixed_channel_receipt_source": "queued_support_state",
                    "blockers": [],
                },
            }
        ],
        generated_at="2026-04-18T18:30:00Z",
    )

    assert plan["ready_count"] == 0
    assert plan["feedback_ready_count"] == 0
    assert plan["fix_available_ready_count"] == 0
    assert plan["please_test_ready_count"] == 0
    assert plan["recovery_loop_ready_count"] == 0
    assert plan["action_groups"]["feedback"] == []
    assert plan["action_groups"]["fix_available"] == []
    assert plan["action_groups"]["please_test"] == []
    assert plan["action_groups"]["recovery"] == []


def test_derived_followthrough_grouping_preserves_fix_available_update_posture() -> None:
    module = _load_module()

    no_update = module._derived_followthrough_grouping(
        {"fixed_version": "1.2.3", "fixed_channel": "preview", "update_required": False, "blockers": []},
        {
            "feedback_loop_ready": True,
            "fix_available_ready": True,
            "please_test_ready": False,
            "recovery_loop_ready": False,
        },
    )
    with_update = module._derived_followthrough_grouping(
        {"fixed_version": "1.2.3", "fixed_channel": "preview", "update_required": True, "blockers": []},
        {
            "feedback_loop_ready": True,
            "fix_available_ready": True,
            "please_test_ready": False,
            "recovery_loop_ready": False,
        },
    )

    assert no_update["fix_available_ready"] is True
    assert no_update["fix_available_next_action"] == "send_fix_available"
    assert with_update["fix_available_ready"] is True
    assert with_update["fix_available_next_action"] == "send_fix_available_with_update"


def test_followthrough_receipt_gates_recompute_counts_from_receipt_truth() -> None:
    module = _load_module()

    gates = module._followthrough_receipt_gates(
        [
            {
                "support_case_backed": True,
                "reporter_followthrough": {
                    "state": "fix_available_ready",
                    "feedback_loop_ready": True,
                    "install_receipt_ready": True,
                    "release_receipt_state": "release_receipt_ready",
                    "release_receipt_id": "release-channel:preview:1.2.3:passed",
                    "release_receipt_source": "release_channel",
                    "release_receipt_channel": "preview",
                    "release_receipt_version": "1.2.3",
                    "installed_build_receipted": True,
                    "installed_build_receipt_id": "install-receipt-gates-1",
                    "installed_build_receipt_installation_id": "install-gates-1",
                    "installed_build_receipt_version": "1.2.3",
                    "installed_build_receipt_channel": "preview",
                    "installed_build_receipt_source": "queued_support_state",
                    "installed_build_receipt_installation_source": "queued_support_state",
                    "installed_build_receipt_version_source": "queued_support_state",
                    "installed_build_receipt_channel_source": "queued_support_state",
                    "installed_build_receipt_installation_matches": True,
                    "installed_build_receipt_version_matches": True,
                    "installed_build_receipt_channel_matches": True,
                    "installed_build_receipt_identity_matches": True,
                    "fixed_version_receipted": True,
                    "fixed_channel_receipted": True,
                    "fixed_version_receipt_id": "fix-version-receipt-gates-1",
                    "fixed_channel_receipt_id": "fix-channel-receipt-gates-1",
                    "fixed_receipt_installation_id": "install-gates-1",
                    "fixed_receipt_installation_source": "queued_support_state",
                    "fixed_receipt_installation_matches": True,
                    "fixed_version_receipt_source": "queued_support_state",
                    "fixed_channel_receipt_source": "queued_support_state",
                    "blockers": [],
                },
                "installation_id": "install-gates-1",
                "install_truth_state": "promoted_tuple_match",
                "status": "fixed",
                "fixed_version": "1.2.3",
                "fixed_channel": "preview",
                "release_channel": "preview",
                "installed_version": "1.2.3",
                "head_id": "avalonia",
                "platform": "linux",
                "arch": "x64",
                "recovery_path": {"action_id": "open_downloads", "href": "/downloads"},
            }
        ],
        generated_at="2026-04-18T18:30:00Z",
    )

    assert gates["ready_count"] == 0
    assert gates["gate_counts"]["install_receipt_ready"] == 1
    assert gates["gate_counts"]["install_truth_ready"] == 1
    assert gates["gate_counts"]["feedback_loop_ready"] == 0
    assert gates["gate_counts"]["fixed_version_receipted"] == 0
    assert gates["gate_counts"]["fixed_channel_receipted"] == 0
    assert gates["gate_counts"]["fixed_receipt_installation_bound"] == 0
    assert gates["gate_counts"]["installed_build_receipted"] == 0
    assert gates["gate_counts"]["installed_build_receipt_installation_bound"] == 0
    assert gates["gate_counts"]["installed_build_receipt_version_matches"] == 0
    assert gates["gate_counts"]["installed_build_receipt_channel_matches"] == 0
    assert gates["gate_counts"]["installed_build_receipt_tuple_bound"] == 0
    assert gates["gate_counts"]["current_install_on_fixed_build"] == 0


def test_materialize_support_case_packets_blocks_reporter_followthrough_without_install_receipts(tmp_path: Path) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "caseId": "support_case_fixed_without_install_receipts",
                        "clusterKey": "support:missing-install-receipts",
                        "kind": "bug_report",
                        "status": "fixed",
                        "title": "Fix is staged but install truth is incomplete",
                        "summary": "Reporter should not get a please-test loop without installed-build truth.",
                        "candidateOwnerRepo": "chummer6-ui",
                        "designImpactSuspected": False,
                        "installationId": "install-release-3",
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "linux",
                        "arch": "x64",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                    }
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "rolloutState": "published",
                "supportabilityState": "supported",
                "desktopTupleCoverage": {
                    "promotedInstallerTuples": [
                        {
                            "tupleId": "avalonia:linux:linux-x64",
                            "head": "avalonia",
                            "platform": "linux",
                            "rid": "linux-x64",
                            "artifactId": "avalonia-linux-x64-installer",
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source",
            str(source),
            "--release-channel",
            str(release_channel),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["reporter_followthrough_ready_count"] == 0
    assert payload["summary"]["reporter_followthrough_blocked_missing_install_receipts_count"] == 1
    assert payload["summary"]["fix_available_ready_count"] == 0
    assert payload["summary"]["please_test_ready_count"] == 0
    packet = payload["packets"][0]
    assert packet["fix_confirmation"]["state"] == "awaiting_reporter_verification"
    assert packet["reporter_followthrough"]["state"] == "blocked_missing_install_receipts"
    assert packet["reporter_followthrough"]["next_action"] == "hold_reporter_followthrough"
    assert packet["reporter_followthrough"]["install_receipt_ready"] is True
    assert packet["reporter_followthrough"]["release_receipt_state"] == "release_receipt_ready"
    assert packet["reporter_followthrough"]["fixed_version_receipted"] is False
    assert packet["reporter_followthrough"]["fixed_version_matches_release_receipt"] is True
    assert packet["reporter_followthrough"]["installed_build_receipted"] is False
    assert packet["reporter_followthrough"]["blockers"] == ["installed_version_missing"]
    followthrough_plan = payload["reporter_followthrough_plan"]
    assert followthrough_plan["ready_count"] == 0
    assert followthrough_plan["blocked_missing_install_receipts_count"] == 1
    blocked_row = followthrough_plan["action_groups"]["blocked_missing_install_receipts"][0]
    assert blocked_row["packet_id"] == packet["packet_id"]
    assert blocked_row["next_action"] == "hold_reporter_followthrough"
    assert blocked_row["blockers"] == ["installed_version_missing"]


def test_materialize_support_case_packets_blocks_embedded_support_receipts_without_receipt_feeds(tmp_path: Path) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "caseId": "support_case_embedded_receipts_only",
                        "clusterKey": "support:embedded-receipts-only",
                        "kind": "bug_report",
                        "status": "fixed",
                        "title": "Queued fields look complete but receipt feeds are absent",
                        "summary": "Reporter followthrough must not leave hold from queued support state alone.",
                        "candidateOwnerRepo": "chummer6-ui",
                        "designImpactSuspected": False,
                        "installationId": "install-embedded-only",
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "linux",
                        "arch": "x64",
                        "installedVersion": "1.2.3",
                        "installedBuildReceiptId": "queued-install-receipt",
                        "installedBuildReceiptInstallationId": "install-embedded-only",
                        "installedBuildReceiptVersion": "1.2.3",
                        "installedBuildReceiptChannel": "preview",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                        "fixedVersionReceiptId": "queued-fix-version-receipt",
                        "fixedChannelReceiptId": "queued-fix-channel-receipt",
                    }
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "rolloutState": "published",
                "supportabilityState": "supported",
                "desktopTupleCoverage": {
                    "promotedInstallerTuples": [
                        {
                            "tupleId": "avalonia:linux:linux-x64",
                            "head": "avalonia",
                            "platform": "linux",
                            "rid": "linux-x64",
                            "artifactId": "avalonia-linux-x64-installer",
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--source", str(source), "--release-channel", str(release_channel), "--out", str(out_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["source"]["install_receipt_feed_state"] == "not_provided"
    assert payload["source"]["fix_receipt_feed_state"] == "not_provided"
    assert payload["summary"]["reporter_followthrough_ready_count"] == 0
    assert payload["summary"]["feedback_followthrough_ready_count"] == 0
    assert payload["summary"]["fix_available_ready_count"] == 0
    assert payload["summary"]["please_test_ready_count"] == 0
    packet = payload["packets"][0]
    assert packet["reporter_followthrough"]["state"] == "blocked_missing_install_receipts"
    assert packet["reporter_followthrough"]["installed_build_receipted"] is False
    assert packet["reporter_followthrough"]["fixed_version_receipted"] is False
    assert packet["reporter_followthrough"]["fixed_channel_receipted"] is False
    assert packet["reporter_followthrough"]["installed_build_receipt_matches_install"] is True
    assert packet["reporter_followthrough"]["fixed_version_matches_release_receipt"] is True
    assert packet["reporter_followthrough"]["fixed_channel_matches_release_receipt"] is True
    assert payload["reporter_followthrough_plan"]["ready_count"] == 0


def test_materialize_support_case_packets_blocks_inactive_install_receipt_rows(tmp_path: Path) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(
        json.dumps(
            {
                "installReceipts": [
                    {
                        "receiptId": "install-receipt-inactive",
                        "installationId": "install-inactive",
                        "version": "1.2.3",
                        "channel": "preview",
                        "current": False,
                    }
                ],
                "fixedReleaseReceipts": [
                    {
                        "caseId": "support_case_inactive_install_receipt",
                        "installationId": "install-inactive",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                        "fixedVersionReceiptId": "fix-version-active",
                        "fixedChannelReceiptId": "fix-channel-active",
                    }
                ],
                "items": [
                    {
                        "caseId": "support_case_inactive_install_receipt",
                        "clusterKey": "support:inactive-install-receipt",
                        "kind": "bug_report",
                        "status": "fixed",
                        "candidateOwnerRepo": "chummer6-ui",
                        "installationId": "install-inactive",
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "linux",
                        "arch": "x64",
                        "installedVersion": "1.2.3",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "desktopTupleCoverage": {
                    "promotedInstallerTuples": [
                        {
                            "tupleId": "avalonia:linux:linux-x64",
                            "head": "avalonia",
                            "platform": "linux",
                            "rid": "linux-x64",
                            "artifactId": "avalonia-linux-x64-installer",
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--source", str(source), "--release-channel", str(release_channel), "--out", str(out_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["source"]["install_receipt_indexed_count"] == 0
    assert payload["source"]["install_receipt_missing_case_count"] == 1
    assert payload["summary"]["reporter_followthrough_ready_count"] == 0
    assert payload["summary"]["please_test_ready_count"] == 0
    packet = payload["packets"][0]
    assert packet["reporter_followthrough"]["state"] == "blocked_missing_install_receipts"
    assert packet["reporter_followthrough"]["installed_build_receipted"] is False
    assert packet["reporter_followthrough"]["blockers"] == ["installed_build_receipt_missing"]


def test_materialize_support_case_packets_blocks_inactive_fix_receipt_rows(tmp_path: Path) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(
        json.dumps(
            {
                "installReceipts": [
                    {
                        "receiptId": "install-receipt-active",
                        "installationId": "install-fix-inactive",
                        "version": "1.2.3",
                        "channel": "preview",
                    }
                ],
                "fixedReleaseReceipts": [
                    {
                        "caseId": "support_case_inactive_fix_receipt",
                        "installationId": "install-fix-inactive",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                        "fixedVersionReceiptId": "fix-version-inactive",
                        "fixedChannelReceiptId": "fix-channel-inactive",
                        "status": "superseded",
                    }
                ],
                "items": [
                    {
                        "caseId": "support_case_inactive_fix_receipt",
                        "clusterKey": "support:inactive-fix-receipt",
                        "kind": "bug_report",
                        "status": "fixed",
                        "candidateOwnerRepo": "chummer6-ui",
                        "installationId": "install-fix-inactive",
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "linux",
                        "arch": "x64",
                        "installedVersion": "1.2.3",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "desktopTupleCoverage": {
                    "promotedInstallerTuples": [
                        {
                            "tupleId": "avalonia:linux:linux-x64",
                            "head": "avalonia",
                            "platform": "linux",
                            "rid": "linux-x64",
                            "artifactId": "avalonia-linux-x64-installer",
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--source", str(source), "--release-channel", str(release_channel), "--out", str(out_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["source"]["fix_receipt_indexed_count"] == 0
    assert payload["source"]["fix_receipt_missing_case_count"] == 1
    assert payload["summary"]["fix_available_ready_count"] == 0
    assert payload["summary"]["please_test_ready_count"] == 0
    assert payload["summary"]["feedback_followthrough_ready_count"] == 1
    packet = payload["packets"][0]
    assert packet["reporter_followthrough"]["state"] == "no_fix_recorded"
    assert packet["reporter_followthrough"]["next_action"] == "send_feedback_progress"
    assert packet["reporter_followthrough"]["fixed_version_receipted"] is False
    assert packet["reporter_followthrough"]["fixed_channel_receipted"] is False


def test_materialize_support_case_packets_blocks_future_dated_install_receipt_rows(tmp_path: Path) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(
        json.dumps(
            {
                "installReceipts": [
                    {
                        "receiptId": "install-receipt-future",
                        "installationId": "install-future",
                        "version": "1.2.3",
                        "channel": "preview",
                        "observedAtUtc": "2020-04-17T19:00:00Z",
                        "updatedAt": "2099-04-17T19:00:00Z",
                    }
                ],
                "fixedReleaseReceipts": [
                    {
                        "caseId": "support_case_future_install_receipt",
                        "installationId": "install-future",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                        "fixedVersionReceiptId": "fix-version-active",
                        "fixedChannelReceiptId": "fix-channel-active",
                    }
                ],
                "items": [
                    {
                        "caseId": "support_case_future_install_receipt",
                        "clusterKey": "support:future-install-receipt",
                        "kind": "bug_report",
                        "status": "fixed",
                        "candidateOwnerRepo": "chummer6-ui",
                        "installationId": "install-future",
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "linux",
                        "arch": "x64",
                        "installedVersion": "1.2.3",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "desktopTupleCoverage": {
                    "promotedInstallerTuples": [
                        {
                            "tupleId": "avalonia:linux:linux-x64",
                            "head": "avalonia",
                            "platform": "linux",
                            "rid": "linux-x64",
                            "artifactId": "avalonia-linux-x64-installer",
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--source", str(source), "--release-channel", str(release_channel), "--out", str(out_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["source"]["install_receipt_source_count"] == 1
    assert payload["source"]["install_receipt_indexed_count"] == 0
    assert payload["source"]["install_receipt_missing_case_count"] == 1
    assert payload["summary"]["please_test_ready_count"] == 0
    packet = payload["packets"][0]
    assert packet["reporter_followthrough"]["state"] == "blocked_missing_install_receipts"
    assert packet["reporter_followthrough"]["installed_build_receipted"] is False
    assert packet["reporter_followthrough"]["blockers"] == ["installed_build_receipt_missing"]


def test_materialize_support_case_packets_blocks_future_dated_fix_receipt_rows(tmp_path: Path) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(
        json.dumps(
            {
                "installReceipts": [
                    {
                        "receiptId": "install-receipt-active",
                        "installationId": "install-fix-future",
                        "version": "1.2.3",
                        "channel": "preview",
                    }
                ],
                "fixedReleaseReceipts": [
                    {
                        "caseId": "support_case_future_fix_receipt",
                        "installationId": "install-fix-future",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                        "fixedVersionReceiptId": "fix-version-future",
                        "fixedChannelReceiptId": "fix-channel-future",
                        "observedAtUtc": "2020-04-17T19:00:00Z",
                        "updatedAt": "2099-04-17T19:00:00Z",
                    }
                ],
                "items": [
                    {
                        "caseId": "support_case_future_fix_receipt",
                        "clusterKey": "support:future-fix-receipt",
                        "kind": "bug_report",
                        "status": "fixed",
                        "candidateOwnerRepo": "chummer6-ui",
                        "installationId": "install-fix-future",
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "linux",
                        "arch": "x64",
                        "installedVersion": "1.2.3",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "desktopTupleCoverage": {
                    "promotedInstallerTuples": [
                        {
                            "tupleId": "avalonia:linux:linux-x64",
                            "head": "avalonia",
                            "platform": "linux",
                            "rid": "linux-x64",
                            "artifactId": "avalonia-linux-x64-installer",
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--source", str(source), "--release-channel", str(release_channel), "--out", str(out_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["source"]["fix_receipt_source_count"] == 1
    assert payload["source"]["fix_receipt_indexed_count"] == 0
    assert payload["source"]["fix_receipt_missing_case_count"] == 1
    assert payload["summary"]["fix_available_ready_count"] == 0
    assert payload["summary"]["please_test_ready_count"] == 0
    assert payload["summary"]["feedback_followthrough_ready_count"] == 1
    packet = payload["packets"][0]
    assert packet["reporter_followthrough"]["state"] == "no_fix_recorded"
    assert packet["reporter_followthrough"]["next_action"] == "send_feedback_progress"
    assert packet["reporter_followthrough"]["fixed_version_receipted"] is False
    assert packet["reporter_followthrough"]["fixed_channel_receipted"] is False


def test_materialize_support_case_packets_blocks_fix_available_without_fixed_version_receipt(tmp_path: Path) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(
        json.dumps(
            {
                "installReceipts": [
                    {
                        "receiptId": "install-receipt-channel-only",
                        "installationId": "install-release-channel-only",
                        "version": "1.2.3",
                        "channel": "preview",
                    }
                ],
                "fixReceipts": [
                    {
                        "caseId": "support_case_fixed_channel_only",
                        "receiptId": "fix-channel-receipt-channel-only",
                        "fixedChannel": "preview",
                    }
                ],
                "items": [
                    {
                        "caseId": "support_case_fixed_channel_only",
                        "clusterKey": "support:fixed-channel-only",
                        "kind": "bug_report",
                        "status": "fixed",
                        "title": "Fix channel is staged but version receipt is missing",
                        "summary": "Fix-available mail must be version-aware, not channel-only support state.",
                        "candidateOwnerRepo": "chummer6-ui",
                        "designImpactSuspected": False,
                        "installationId": "install-release-channel-only",
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "linux",
                        "arch": "x64",
                        "installedVersion": "1.2.3",
                        "installedBuildReceiptId": "install-receipt-channel-only",
                        "installedBuildReceiptInstallationId": "install-release-channel-only",
                        "installedBuildReceiptVersion": "1.2.3",
                        "installedBuildReceiptChannel": "preview",
                        "fixedChannel": "preview",
                    }
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "rolloutState": "published",
                "supportabilityState": "supported",
                "desktopTupleCoverage": {
                    "promotedInstallerTuples": [
                        {
                            "tupleId": "avalonia:linux:linux-x64",
                            "head": "avalonia",
                            "platform": "linux",
                            "rid": "linux-x64",
                            "artifactId": "avalonia-linux-x64-installer",
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source",
            str(source),
            "--release-channel",
            str(release_channel),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["reporter_followthrough_ready_count"] == 0
    assert payload["summary"]["reporter_followthrough_blocked_missing_install_receipts_count"] == 1
    assert payload["summary"]["fix_available_ready_count"] == 0
    assert payload["summary"]["please_test_ready_count"] == 0
    packet = payload["packets"][0]
    assert packet["reporter_followthrough"]["state"] == "blocked_missing_install_receipts"
    assert packet["reporter_followthrough"]["install_receipt_ready"] is True
    assert packet["reporter_followthrough"]["release_receipt_state"] == "release_receipt_ready"
    assert packet["reporter_followthrough"]["installed_build_receipted"] is True
    assert packet["reporter_followthrough"]["fixed_channel_receipted"] is True
    assert packet["reporter_followthrough"]["fixed_version_receipted"] is False
    assert packet["reporter_followthrough"]["blockers"] == ["fixed_version_missing"]
    plan = payload["reporter_followthrough_plan"]
    assert plan["ready_count"] == 0
    assert plan["action_groups"]["blocked_missing_install_receipts"][0]["blockers"] == [
        "fixed_version_missing"
    ]


def test_materialize_support_case_packets_blocks_reporter_followthrough_without_installed_build_receipt_id(tmp_path: Path) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "caseId": "support_case_fixed_with_version_only",
                        "clusterKey": "support:version-only",
                        "kind": "bug_report",
                        "status": "fixed",
                        "title": "Fix is staged but installed build is not receipt-backed",
                        "summary": "Queued support state alone must not trigger reporter followthrough.",
                        "candidateOwnerRepo": "chummer6-ui",
                        "designImpactSuspected": False,
                        "installationId": "install-release-4",
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "linux",
                        "arch": "x64",
                        "installedVersion": "1.2.3",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                    }
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "rolloutState": "published",
                "supportabilityState": "supported",
                "desktopTupleCoverage": {
                    "promotedInstallerTuples": [
                        {
                            "tupleId": "avalonia:linux:linux-x64",
                            "head": "avalonia",
                            "platform": "linux",
                            "rid": "linux-x64",
                            "artifactId": "avalonia-linux-x64-installer",
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source",
            str(source),
            "--release-channel",
            str(release_channel),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["reporter_followthrough_ready_count"] == 0
    assert payload["summary"]["reporter_followthrough_blocked_missing_install_receipts_count"] == 1
    assert payload["summary"]["fix_available_ready_count"] == 0
    assert payload["summary"]["please_test_ready_count"] == 0
    packet = payload["packets"][0]
    assert packet["installed_build_receipt_id"] == ""
    assert packet["install_diagnosis"]["case_installed_build_receipt_id"] == ""
    assert packet["fix_confirmation"]["installed_build_receipt_id"] == ""
    assert packet["reporter_followthrough"]["state"] == "blocked_missing_install_receipts"
    assert packet["reporter_followthrough"]["installed_build_receipted"] is False
    assert packet["reporter_followthrough"]["blockers"] == ["installed_build_receipt_missing"]


def test_materialize_support_case_packets_blocks_fix_available_without_fixed_channel_receipt(tmp_path: Path) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(
        json.dumps(
            {
                "installReceipts": [
                    {
                        "receiptId": "install-receipt-version-only",
                        "installationId": "install-release-version-only",
                        "version": "1.2.3",
                        "channel": "preview",
                    }
                ],
                "fixReceipts": [
                    {
                        "caseId": "support_case_fixed_version_only",
                        "receiptId": "fix-version-receipt-version-only",
                        "fixedVersion": "1.2.3",
                    }
                ],
                "items": [
                    {
                        "caseId": "support_case_fixed_version_only",
                        "clusterKey": "support:fixed-version-only",
                        "kind": "bug_report",
                        "status": "fixed",
                        "title": "Fix is staged but channel receipt is missing",
                        "summary": "Fix-available mail must be channel-aware, not version-only support state.",
                        "candidateOwnerRepo": "chummer6-ui",
                        "designImpactSuspected": False,
                        "installationId": "install-release-version-only",
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "linux",
                        "arch": "x64",
                        "installedVersion": "1.2.3",
                        "installedBuildReceiptId": "install-receipt-version-only",
                        "installedBuildReceiptInstallationId": "install-release-version-only",
                        "installedBuildReceiptVersion": "1.2.3",
                        "installedBuildReceiptChannel": "preview",
                        "fixedVersion": "1.2.3",
                    }
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "rolloutState": "published",
                "supportabilityState": "supported",
                "desktopTupleCoverage": {
                    "promotedInstallerTuples": [
                        {
                            "tupleId": "avalonia:linux:linux-x64",
                            "head": "avalonia",
                            "platform": "linux",
                            "rid": "linux-x64",
                            "artifactId": "avalonia-linux-x64-installer",
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source",
            str(source),
            "--release-channel",
            str(release_channel),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["reporter_followthrough_ready_count"] == 0
    assert payload["summary"]["reporter_followthrough_blocked_missing_install_receipts_count"] == 1
    assert payload["summary"]["fix_available_ready_count"] == 0
    assert payload["summary"]["please_test_ready_count"] == 0
    packet = payload["packets"][0]
    assert packet["reporter_followthrough"]["state"] == "blocked_missing_install_receipts"
    assert packet["reporter_followthrough"]["install_receipt_ready"] is True
    assert packet["reporter_followthrough"]["release_receipt_state"] == "release_receipt_ready"
    assert packet["reporter_followthrough"]["installed_build_receipted"] is True
    assert packet["reporter_followthrough"]["fixed_version_receipted"] is True
    assert packet["reporter_followthrough"]["fixed_channel_receipted"] is False
    assert packet["reporter_followthrough"]["blockers"] == ["fixed_channel_missing"]
    receipt_gates = payload["followthrough_receipt_gates"]
    assert receipt_gates["ready_count"] == 0
    assert receipt_gates["gate_counts"]["fixed_version_receipted"] == 1
    assert receipt_gates["gate_counts"]["fixed_channel_receipted"] == 0
    assert receipt_gates["blocker_counts"] == {"fixed_channel_missing": 1}


def test_materialize_support_case_packets_blocks_reporter_followthrough_without_receipt_facts(tmp_path: Path) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "caseId": "support_case_fixed_with_id_only_receipt",
                        "clusterKey": "support:receipt-id-only",
                        "kind": "bug_report",
                        "status": "fixed",
                        "title": "Fix is staged but install receipt facts are missing",
                        "summary": "Reporter followthrough must not trust a receipt id without version and channel facts.",
                        "candidateOwnerRepo": "chummer6-ui",
                        "designImpactSuspected": False,
                        "installationId": "install-release-id-only",
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "linux",
                        "arch": "x64",
                        "installedVersion": "1.2.3",
                        "installedBuildReceiptId": "install-receipt-id-only",
                        "installedBuildReceiptInstallationId": "install-release-id-only",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                    }
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "rolloutState": "published",
                "supportabilityState": "supported",
                "desktopTupleCoverage": {
                    "promotedInstallerTuples": [
                        {
                            "tupleId": "avalonia:linux:linux-x64",
                            "head": "avalonia",
                            "platform": "linux",
                            "rid": "linux-x64",
                            "artifactId": "avalonia-linux-x64-installer",
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source",
            str(source),
            "--release-channel",
            str(release_channel),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["reporter_followthrough_ready_count"] == 0
    assert payload["summary"]["reporter_followthrough_blocked_missing_install_receipts_count"] == 1
    assert payload["summary"]["reporter_followthrough_blocked_receipt_mismatch_count"] == 0
    assert payload["summary"]["fix_available_ready_count"] == 0
    assert payload["summary"]["please_test_ready_count"] == 0
    packet = payload["packets"][0]
    assert packet["installed_build_receipt_id"] == "install-receipt-id-only"
    assert packet["install_diagnosis"]["case_installed_build_receipt_version"] == ""
    assert packet["install_diagnosis"]["case_installed_build_receipt_channel"] == ""
    assert packet["reporter_followthrough"]["state"] == "blocked_missing_install_receipts"
    assert packet["reporter_followthrough"]["installed_build_receipted"] is False
    assert packet["reporter_followthrough"]["blockers"] == [
        "installed_build_receipt_version_missing",
        "installed_build_receipt_channel_missing",
    ]


def test_materialize_support_case_packets_blocks_reporter_followthrough_on_receipt_fact_mismatch(tmp_path: Path) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "caseId": "support_case_fixed_with_mismatched_receipt",
                        "clusterKey": "support:receipt-mismatch",
                        "kind": "bug_report",
                        "status": "fixed",
                        "title": "Fix is staged but receipt facts contradict the install",
                        "summary": "Reporter followthrough must not trust a receipt id alone.",
                        "candidateOwnerRepo": "chummer6-ui",
                        "designImpactSuspected": False,
                        "installationId": "install-release-6",
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "linux",
                        "arch": "x64",
                        "installedVersion": "1.2.3",
                        "installedBuildReceiptId": "install-receipt-mismatch-1",
                        "installedBuildReceiptInstallationId": "install-release-6",
                        "installedBuildReceiptVersion": "1.2.2",
                        "installedBuildReceiptChannel": "nightly",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                    }
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "rolloutState": "published",
                "supportabilityState": "supported",
                "desktopTupleCoverage": {
                    "promotedInstallerTuples": [
                        {
                            "tupleId": "avalonia:linux:linux-x64",
                            "head": "avalonia",
                            "platform": "linux",
                            "rid": "linux-x64",
                            "artifactId": "avalonia-linux-x64-installer",
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source",
            str(source),
            "--release-channel",
            str(release_channel),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["reporter_followthrough_ready_count"] == 0
    assert payload["summary"]["reporter_followthrough_blocked_missing_install_receipts_count"] == 1
    assert payload["summary"]["reporter_followthrough_blocked_receipt_mismatch_count"] == 1
    assert payload["summary"]["fix_available_ready_count"] == 0
    assert payload["summary"]["please_test_ready_count"] == 0
    packet = payload["packets"][0]
    assert packet["install_diagnosis"]["case_installed_build_receipt_version"] == "1.2.2"
    assert packet["install_diagnosis"]["case_installed_build_receipt_channel"] == "nightly"
    assert packet["fix_confirmation"]["installed_build_receipt_version"] == "1.2.2"
    assert packet["fix_confirmation"]["installed_build_receipt_channel"] == "nightly"
    assert packet["reporter_followthrough"]["state"] == "blocked_receipt_mismatch"
    assert packet["reporter_followthrough"]["installed_build_receipted"] is False
    assert packet["reporter_followthrough"]["installed_build_receipt_version_matches"] is False
    assert packet["reporter_followthrough"]["installed_build_receipt_channel_matches"] is False
    assert packet["reporter_followthrough"]["blockers"] == [
        "installed_build_receipt_version_mismatch",
        "installed_build_receipt_channel_mismatch",
    ]
    receipt_gates = payload["followthrough_receipt_gates"]
    assert receipt_gates["ready_count"] == 0
    assert receipt_gates["blocked_missing_install_receipts_count"] == 1
    assert receipt_gates["blocked_receipt_mismatch_count"] == 1
    assert receipt_gates["gate_counts"]["installed_build_receipted"] == 0
    assert receipt_gates["gate_counts"]["installed_build_receipt_id_present"] == 0
    assert receipt_gates["gate_counts"]["installed_build_receipt_installation_bound"] == 0
    assert receipt_gates["gate_counts"]["installed_build_receipt_version_matches"] == 0
    assert receipt_gates["gate_counts"]["installed_build_receipt_channel_matches"] == 0
    assert receipt_gates["blocker_counts"] == {
        "installed_build_receipt_channel_mismatch": 1,
        "installed_build_receipt_version_mismatch": 1,
    }


def test_materialize_support_case_packets_blocks_reporter_followthrough_on_install_receipt_tuple_mismatch(tmp_path: Path) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(
        json.dumps(
            {
                "installReceipts": [
                    {
                        "installationId": "install-release-tuple-mismatch",
                        "receiptId": "install-receipt-wrong-tuple",
                        "version": "1.2.3",
                        "channel": "preview",
                        "headId": "avalonia",
                        "platform": "windows",
                        "rid": "win-x64",
                    }
                ],
                "fixReceipts": [
                    {
                        "caseId": "support_case_fixed_with_wrong_tuple_receipt",
                        "installationId": "install-release-tuple-mismatch",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                        "fixedVersionReceiptId": "fix-version-receipt-tuple",
                        "fixedChannelReceiptId": "fix-channel-receipt-tuple",
                    }
                ],
                "items": [
                    {
                        "caseId": "support_case_fixed_with_wrong_tuple_receipt",
                        "clusterKey": "support:receipt-tuple-mismatch",
                        "kind": "bug_report",
                        "status": "fixed",
                        "title": "Fix is staged but install receipt tuple contradicts the linked install",
                        "summary": "Reporter followthrough must not trust a same-install receipt from the wrong desktop tuple.",
                        "candidateOwnerRepo": "chummer6-ui",
                        "designImpactSuspected": False,
                        "installationId": "install-release-tuple-mismatch",
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "linux",
                        "arch": "x64",
                        "installedVersion": "1.2.3",
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "rolloutState": "published",
                "supportabilityState": "supported",
                "desktopTupleCoverage": {
                    "promotedInstallerTuples": [
                        {
                            "tupleId": "avalonia:linux:linux-x64",
                            "head": "avalonia",
                            "platform": "linux",
                            "rid": "linux-x64",
                            "artifactId": "avalonia-linux-x64-installer",
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source",
            str(source),
            "--release-channel",
            str(release_channel),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["reporter_followthrough_ready_count"] == 0
    assert payload["summary"]["reporter_followthrough_blocked_missing_install_receipts_count"] == 1
    assert payload["summary"]["reporter_followthrough_blocked_receipt_mismatch_count"] == 1
    assert payload["summary"]["fix_available_ready_count"] == 0
    packet = payload["packets"][0]
    assert packet["installed_build_receipt_platform"] == "windows"
    assert packet["installed_build_receipt_rid"] == "win-x64"
    assert packet["installed_build_receipt_tuple_id"] == "avalonia:win-x64:windows"
    assert packet["reporter_followthrough"]["installed_build_receipted"] is False
    assert packet["reporter_followthrough"]["installed_build_receipt_platform_matches"] is False
    assert packet["reporter_followthrough"]["installed_build_receipt_rid_matches"] is False
    assert packet["reporter_followthrough"]["installed_build_receipt_tuple_matches"] is False
    assert packet["reporter_followthrough"]["blockers"] == [
        "installed_build_receipt_platform_mismatch",
        "installed_build_receipt_rid_mismatch",
        "installed_build_receipt_tuple_mismatch",
    ]
    plan = payload["reporter_followthrough_plan"]
    assert plan["action_groups"]["blocked_receipt_mismatch"][0]["installed_build_receipt_tuple_id"] == (
        "avalonia:win-x64:windows"
    )
    receipt_gates = payload["followthrough_receipt_gates"]
    assert receipt_gates["blocked_receipt_mismatch_count"] == 1
    assert receipt_gates["blocker_counts"]["installed_build_receipt_tuple_mismatch"] == 1


def test_materialize_support_case_packets_blocks_reporter_followthrough_on_receipt_installation_mismatch(tmp_path: Path) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "caseId": "support_case_fixed_with_cross_install_receipt",
                        "clusterKey": "support:receipt-installation-mismatch",
                        "kind": "bug_report",
                        "status": "fixed",
                        "title": "Fix is staged but receipt belongs to another install",
                        "summary": "Reporter followthrough must bind installed-build receipts to the linked install.",
                        "candidateOwnerRepo": "chummer6-ui",
                        "designImpactSuspected": False,
                        "installationId": "install-release-7",
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "linux",
                        "arch": "x64",
                        "installedVersion": "1.2.3",
                        "installedBuildReceiptId": "install-receipt-cross-install-1",
                        "installedBuildReceiptInstallationId": "install-other-7",
                        "installedBuildReceiptVersion": "1.2.3",
                        "installedBuildReceiptChannel": "preview",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                    }
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "rolloutState": "published",
                "supportabilityState": "supported",
                "desktopTupleCoverage": {
                    "promotedInstallerTuples": [
                        {
                            "tupleId": "avalonia:linux:linux-x64",
                            "head": "avalonia",
                            "platform": "linux",
                            "rid": "linux-x64",
                            "artifactId": "avalonia-linux-x64-installer",
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source",
            str(source),
            "--release-channel",
            str(release_channel),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["reporter_followthrough_ready_count"] == 0
    assert payload["summary"]["reporter_followthrough_blocked_missing_install_receipts_count"] == 1
    assert payload["summary"]["reporter_followthrough_blocked_receipt_mismatch_count"] == 1
    assert payload["summary"]["fix_available_ready_count"] == 0
    assert payload["summary"]["please_test_ready_count"] == 0
    packet = payload["packets"][0]
    assert packet["install_diagnosis"]["case_installed_build_receipt_installation_id"] == "install-other-7"
    assert packet["fix_confirmation"]["installed_build_receipt_installation_id"] == "install-other-7"
    assert packet["reporter_followthrough"]["state"] == "blocked_receipt_mismatch"
    assert packet["reporter_followthrough"]["installed_build_receipted"] is False
    assert packet["reporter_followthrough"]["installed_build_receipt_installation_matches"] is False
    assert packet["reporter_followthrough"]["blockers"] == [
        "installed_build_receipt_installation_mismatch"
    ]


def test_materialize_support_case_packets_rejects_generic_release_receipt_as_installed_build_receipt(
    tmp_path: Path,
) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "caseId": "support_case_release_receipt_only",
                        "clusterKey": "support:release-receipt-only",
                        "kind": "bug_report",
                        "status": "fixed",
                        "title": "Fix is staged but only release receipt is present",
                        "summary": "Reporter followthrough must not treat a release receipt id as an installed-build receipt.",
                        "candidateOwnerRepo": "chummer6-ui",
                        "designImpactSuspected": False,
                        "installationId": "install-release-only-1",
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "linux",
                        "arch": "x64",
                        "installedVersion": "1.2.3",
                        "releaseReceiptId": "release-receipt-preview-1",
                        "receiptInstallationId": "install-release-only-1",
                        "receiptVersion": "1.2.3",
                        "receiptChannel": "preview",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                    }
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "rolloutState": "published",
                "supportabilityState": "supported",
                "desktopTupleCoverage": {
                    "promotedInstallerTuples": [
                        {
                            "tupleId": "avalonia:linux:linux-x64",
                            "head": "avalonia",
                            "platform": "linux",
                            "rid": "linux-x64",
                            "artifactId": "avalonia-linux-x64-installer",
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source",
            str(source),
            "--release-channel",
            str(release_channel),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["reporter_followthrough_ready_count"] == 0
    assert payload["summary"]["reporter_followthrough_blocked_missing_install_receipts_count"] == 1
    assert payload["summary"]["fix_available_ready_count"] == 0
    assert payload["summary"]["please_test_ready_count"] == 0
    packet = payload["packets"][0]
    assert packet["installed_build_receipt_id"] == ""
    assert packet["installed_build_receipt_source"] == ""
    assert packet["install_diagnosis"]["case_installed_build_receipt_id"] == ""
    assert packet["fix_confirmation"]["installed_build_receipt_id"] == ""
    assert packet["reporter_followthrough"]["state"] == "blocked_missing_install_receipts"
    assert packet["reporter_followthrough"]["installed_build_receipted"] is False
    assert packet["reporter_followthrough"]["blockers"] == ["installed_build_receipt_missing"]


def test_materialize_support_case_packets_overrides_queued_support_receipt_with_install_receipt_feed(
    tmp_path: Path,
) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(
        json.dumps(
            {
                "installReceipts": [
                    {
                        "receiptId": "install-receipt-authoritative-1",
                        "installationId": "install-authoritative-1",
                        "version": "1.2.3",
                        "channel": "preview",
                    }
                ],
                "fixedReleaseReceipts": [
                    {
                        "caseId": "support_case_authoritative_receipt",
                        "installationId": "install-authoritative-1",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                        "fixedVersionReceiptId": "fix-version-receipt-authoritative-1",
                        "fixedChannelReceiptId": "fix-channel-receipt-authoritative-1",
                    }
                ],
                "items": [
                    {
                        "caseId": "support_case_authoritative_receipt",
                        "clusterKey": "support:authoritative-receipt",
                        "kind": "bug_report",
                        "status": "fixed",
                        "title": "Fix is staged and install receipt feed has the current build",
                        "summary": "Queued support fields are stale but install receipts are authoritative.",
                        "candidateOwnerRepo": "chummer6-ui",
                        "installationId": "install-authoritative-1",
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "linux",
                        "arch": "x64",
                        "installedVersion": "1.2.3",
                        "installedBuildReceiptId": "queued-stale-receipt",
                        "installedBuildReceiptInstallationId": "install-authoritative-1",
                        "installedBuildReceiptVersion": "1.2.2",
                        "installedBuildReceiptChannel": "nightly",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "desktopTupleCoverage": {
                    "promotedInstallerTuples": [
                        {
                            "tupleId": "avalonia:linux:linux-x64",
                            "head": "avalonia",
                            "platform": "linux",
                            "rid": "linux-x64",
                            "artifactId": "avalonia-linux-x64-installer",
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--source", str(source), "--release-channel", str(release_channel), "--out", str(out_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["source"]["install_receipt_feed_state"] == "provided"
    assert payload["source"]["install_receipt_hydrated_case_count"] == 1
    assert payload["summary"]["fix_available_ready_count"] == 0
    packet = payload["packets"][0]
    assert packet["installed_build_receipt_id"] == "install-receipt-authoritative-1"
    assert packet["installed_build_receipt_source"] == "install_receipts"
    assert packet["install_diagnosis"]["case_installed_build_receipt_truth_source"] == "install_receipts"
    assert packet["reporter_followthrough"]["installed_build_receipted"] is True
    assert packet["reporter_followthrough"]["blockers"] == []


def test_materialize_support_case_packets_rejects_cross_case_fix_receipt_on_same_install(
    tmp_path: Path,
) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(
        json.dumps(
            {
                "installReceipts": [
                    {
                        "receiptId": "install-receipt-shared-install-1",
                        "installationId": "install-shared-case-1",
                        "version": "1.2.3",
                        "channel": "preview",
                        "headId": "avalonia",
                        "platform": "linux",
                        "rid": "linux-x64",
                    }
                ],
                "fixReceipts": [
                    {
                        "caseId": "support_case_other_same_install",
                        "installationId": "install-shared-case-1",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                        "fixedVersionReceiptId": "fix-version-receipt-other-case",
                        "fixedChannelReceiptId": "fix-channel-receipt-other-case",
                    }
                ],
                "items": [
                    {
                        "caseId": "support_case_waiting_same_install",
                        "clusterKey": "support:wrong-case-fix-receipt",
                        "kind": "bug_report",
                        "status": "fixed",
                        "title": "Queued fix should not borrow another case receipt",
                        "summary": "The linked install is current, but the only fix receipt belongs to a different support case.",
                        "candidateOwnerRepo": "chummer6-ui",
                        "installationId": "install-shared-case-1",
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "linux",
                        "arch": "x64",
                        "installedVersion": "1.2.3",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "desktopTupleCoverage": {
                    "promotedInstallerTuples": [
                        {
                            "tupleId": "avalonia:linux:linux-x64",
                            "head": "avalonia",
                            "platform": "linux",
                            "rid": "linux-x64",
                            "artifactId": "avalonia-linux-x64-installer",
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source",
            str(source),
            "--release-channel",
            str(release_channel),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["source"]["fix_receipt_feed_state"] == "provided"
    assert payload["source"]["fix_receipt_indexed_count"] == 2
    assert payload["source"]["fix_receipt_hydrated_case_count"] == 0
    assert payload["source"]["fix_receipt_missing_case_count"] == 1
    assert payload["summary"]["reporter_followthrough_ready_count"] == 1
    assert payload["summary"]["feedback_followthrough_ready_count"] == 1
    assert payload["summary"]["fix_available_ready_count"] == 0
    assert payload["summary"]["please_test_ready_count"] == 0
    assert payload["summary"]["recovery_loop_ready_count"] == 0
    assert payload["summary"]["reporter_followthrough_hold_until_fix_receipt_count"] == 1
    packet = payload["packets"][0]
    assert packet["fixed_version"] == ""
    assert packet["fixed_channel"] == ""
    assert packet["reporter_followthrough"]["state"] == "no_fix_recorded"
    assert packet["reporter_followthrough"]["next_action"] == "send_feedback_progress"
    plan = payload["reporter_followthrough_plan"]
    assert plan["action_groups"]["fix_available"] == []
    assert plan["action_groups"]["please_test"] == []
    assert plan["action_groups"]["recovery"] == []
    assert plan["action_groups"]["hold_until_fix_receipt"][0]["packet_id"] == packet["packet_id"]


def test_materialize_support_case_packets_uses_current_install_receipt_over_stale_later_row(
    tmp_path: Path,
) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(
        json.dumps(
            {
                "installReceipts": [
                    {
                        "receiptId": "install-receipt-current-1",
                        "installationId": "install-current-1",
                        "version": "1.2.3",
                        "channel": "preview",
                        "isCurrent": True,
                        "recordedAtUtc": "2026-04-17T10:00:00Z",
                    },
                    {
                        "receiptId": "install-receipt-stale-1",
                        "installationId": "install-current-1",
                        "version": "1.2.2",
                        "channel": "preview",
                        "isCurrent": False,
                        "recordedAtUtc": "2026-04-17T10:00:00Z",
                    },
                ],
                "fixedReleaseReceipts": [
                    {
                        "caseId": "support_case_current_install_receipt",
                        "installationId": "install-current-1",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                        "fixedVersionReceiptId": "fix-version-receipt-current-install-1",
                        "fixedChannelReceiptId": "fix-channel-receipt-current-install-1",
                    }
                ],
                "items": [
                    {
                        "caseId": "support_case_current_install_receipt",
                        "clusterKey": "support:current-install-receipt",
                        "kind": "bug_report",
                        "status": "fixed",
                        "title": "Fix is staged and install receipt feed has duplicate rows",
                        "summary": "The current receipt should win even when a stale row appears later.",
                        "candidateOwnerRepo": "chummer6-ui",
                        "installationId": "install-current-1",
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "linux",
                        "arch": "x64",
                        "installedVersion": "1.2.3",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "desktopTupleCoverage": {
                    "promotedInstallerTuples": [
                        {
                            "tupleId": "avalonia:linux:linux-x64",
                            "head": "avalonia",
                            "platform": "linux",
                            "rid": "linux-x64",
                            "artifactId": "avalonia-linux-x64-installer",
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--source", str(source), "--release-channel", str(release_channel), "--out", str(out_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["fix_available_ready_count"] == 0
    packet = payload["packets"][0]
    assert packet["installed_build_receipt_id"] == "install-receipt-current-1"
    assert packet["installed_build_receipt_version"] == "1.2.3"
    assert packet["reporter_followthrough"]["installed_build_receipted"] is True
    assert packet["reporter_followthrough"]["blockers"] == []


def test_materialize_support_case_packets_suppresses_queued_receipt_when_install_receipt_feed_lacks_install(
    tmp_path: Path,
) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(
        json.dumps(
            {
                "installReceipts": [
                    {
                        "receiptId": "install-receipt-other-1",
                        "installationId": "install-other-1",
                        "version": "1.2.3",
                        "channel": "preview",
                    }
                ],
                "items": [
                    {
                        "caseId": "support_case_queued_receipt_only",
                        "clusterKey": "support:queued-receipt-only",
                        "kind": "bug_report",
                        "status": "fixed",
                        "title": "Fix is staged but install receipt feed has no linked receipt",
                        "summary": "Queued support receipt fields must not substitute for receipt truth.",
                        "candidateOwnerRepo": "chummer6-ui",
                        "installationId": "install-missing-from-feed",
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "linux",
                        "arch": "x64",
                        "installedVersion": "1.2.3",
                        "installedBuildReceiptId": "queued-would-pass",
                        "installedBuildReceiptInstallationId": "install-missing-from-feed",
                        "installedBuildReceiptVersion": "1.2.3",
                        "installedBuildReceiptChannel": "preview",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "desktopTupleCoverage": {
                    "promotedInstallerTuples": [
                        {
                            "tupleId": "avalonia:linux:linux-x64",
                            "head": "avalonia",
                            "platform": "linux",
                            "rid": "linux-x64",
                            "artifactId": "avalonia-linux-x64-installer",
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--source", str(source), "--release-channel", str(release_channel), "--out", str(out_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["source"]["install_receipt_feed_state"] == "provided"
    assert payload["source"]["install_receipt_missing_case_count"] == 1
    assert payload["summary"]["fix_available_ready_count"] == 0
    packet = payload["packets"][0]
    assert packet["installed_build_receipt_id"] == ""
    assert packet["fix_confirmation"]["installed_build_receipt_truth_source"] == "install_receipts_missing"
    assert packet["reporter_followthrough"]["state"] == "blocked_missing_install_receipts"
    assert packet["reporter_followthrough"]["blockers"] == ["installed_build_receipt_missing"]


def test_materialize_support_case_packets_suppresses_queued_receipt_when_install_receipt_feed_is_empty(
    tmp_path: Path,
) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(
        json.dumps(
            {
                "installReceipts": [],
                "fixedReleaseReceipts": [
                    {
                        "caseId": "support_case_empty_install_feed",
                        "installationId": "install-empty-feed",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                        "fixedVersionReceiptId": "fix-version-receipt-empty-install-feed",
                        "fixedChannelReceiptId": "fix-channel-receipt-empty-install-feed",
                    }
                ],
                "items": [
                    {
                        "caseId": "support_case_empty_install_feed",
                        "clusterKey": "support:empty-install-feed",
                        "kind": "bug_report",
                        "status": "fixed",
                        "title": "Empty install receipt feed must still be authoritative",
                        "summary": "Queued support install receipt fields must not unlock followthrough.",
                        "candidateOwnerRepo": "chummer6-ui",
                        "installationId": "install-empty-feed",
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "linux",
                        "arch": "x64",
                        "installedVersion": "1.2.3",
                        "installedBuildReceiptId": "queued-would-pass-empty-feed",
                        "installedBuildReceiptInstallationId": "install-empty-feed",
                        "installedBuildReceiptVersion": "1.2.3",
                        "installedBuildReceiptChannel": "preview",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "desktopTupleCoverage": {
                    "promotedInstallerTuples": [
                        {
                            "tupleId": "avalonia:linux:linux-x64",
                            "head": "avalonia",
                            "platform": "linux",
                            "rid": "linux-x64",
                            "artifactId": "avalonia-linux-x64-installer",
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--source", str(source), "--release-channel", str(release_channel), "--out", str(out_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["source"]["install_receipt_feed_state"] == "provided"
    assert payload["source"]["install_receipt_source_count"] == 0
    assert payload["source"]["install_receipt_missing_case_count"] == 1
    assert payload["summary"]["fix_available_ready_count"] == 0
    packet = payload["packets"][0]
    assert packet["installed_build_receipt_id"] == ""
    assert packet["install_diagnosis"]["case_installed_build_receipt_truth_source"] == "install_receipts_missing"
    assert packet["reporter_followthrough"]["state"] == "blocked_missing_install_receipts"
    assert packet["reporter_followthrough"]["blockers"] == ["installed_build_receipt_missing"]


def test_materialize_support_case_packets_prefers_case_fix_receipt_over_install_fallback(
    tmp_path: Path,
) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(
        json.dumps(
            {
                "installReceipts": [
                    {
                        "receiptId": "install-receipt-case-specific-fix",
                        "installationId": "install-case-specific-fix",
                        "version": "1.2.3",
                        "channel": "preview",
                    }
                ],
                "fixedReleaseReceipts": [
                    {
                        "caseId": "support_case_specific_fix_receipt",
                        "installationId": "install-case-specific-fix",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                        "fixedVersionReceiptId": "fix-version-receipt-case-specific",
                        "fixedChannelReceiptId": "fix-channel-receipt-case-specific",
                        "recordedAtUtc": "2026-04-17T10:00:00Z",
                    },
                    {
                        "installationId": "install-case-specific-fix",
                        "fixedVersion": "1.2.4",
                        "fixedChannel": "preview",
                        "fixedVersionReceiptId": "fix-version-receipt-install-fallback",
                        "fixedChannelReceiptId": "fix-channel-receipt-install-fallback",
                        "recordedAtUtc": "2026-04-17T10:00:00Z",
                    },
                ],
                "items": [
                    {
                        "caseId": "support_case_specific_fix_receipt",
                        "clusterKey": "support:case-specific-fix-receipt",
                        "kind": "bug_report",
                        "status": "fixed",
                        "title": "Case fix receipt should beat install fallback",
                        "summary": "Install-level fallback receipt has the same rank but belongs behind the exact case receipt.",
                        "candidateOwnerRepo": "chummer6-ui",
                        "installationId": "install-case-specific-fix",
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "linux",
                        "arch": "x64",
                        "installedVersion": "1.2.3",
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "desktopTupleCoverage": {
                    "promotedInstallerTuples": [
                        {
                            "tupleId": "avalonia:linux:linux-x64",
                            "head": "avalonia",
                            "platform": "linux",
                            "rid": "linux-x64",
                            "artifactId": "avalonia-linux-x64-installer",
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--source", str(source), "--release-channel", str(release_channel), "--out", str(out_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    packet = payload["packets"][0]
    assert packet["fixed_version"] == "1.2.3"
    assert packet["fixed_version_receipt_id"] == "fix-version-receipt-case-specific"
    assert packet["reporter_followthrough"]["fixed_version_receipted"] is True
    assert packet["reporter_followthrough"]["blockers"] == []


def test_materialize_support_case_packets_overrides_queued_fix_fields_with_fix_receipt_feed(
    tmp_path: Path,
) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(
        json.dumps(
            {
                "installReceipts": [
                    {
                        "receiptId": "install-receipt-fix-1",
                        "installationId": "install-fix-receipt-1",
                        "version": "1.2.3",
                        "channel": "preview",
                    }
                ],
                "fixReceipts": [
                    {
                        "caseId": "support_case_fix_receipt_authoritative",
                        "installationId": "install-fix-receipt-1",
                        "fixedVersionReceiptId": "fix-version-receipt-authoritative-1",
                        "fixedChannelReceiptId": "fix-channel-receipt-authoritative-1",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                    }
                ],
                "items": [
                    {
                        "caseId": "support_case_fix_receipt_authoritative",
                        "clusterKey": "support:fix-receipt-authoritative",
                        "kind": "bug_report",
                        "status": "fixed",
                        "title": "Fix receipt feed owns the version and channel truth",
                        "summary": "Queued support fixed fields are stale but fix receipts are authoritative.",
                        "candidateOwnerRepo": "chummer6-ui",
                        "installationId": "install-fix-receipt-1",
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "linux",
                        "arch": "x64",
                        "installedVersion": "1.2.3",
                        "installedBuildReceiptId": "install-receipt-fix-1",
                        "installedBuildReceiptInstallationId": "install-fix-receipt-1",
                        "installedBuildReceiptVersion": "1.2.3",
                        "installedBuildReceiptChannel": "preview",
                        "fixedVersion": "1.2.2",
                        "fixedChannel": "nightly",
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "desktopTupleCoverage": {
                    "promotedInstallerTuples": [
                        {
                            "tupleId": "avalonia:linux:linux-x64",
                            "head": "avalonia",
                            "platform": "linux",
                            "rid": "linux-x64",
                            "artifactId": "avalonia-linux-x64-installer",
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--source", str(source), "--release-channel", str(release_channel), "--out", str(out_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["source"]["fix_receipt_feed_state"] == "provided"
    assert payload["source"]["fix_receipt_hydrated_case_count"] == 1
    assert payload["summary"]["fix_available_ready_count"] == 0
    packet = payload["packets"][0]
    assert packet["fixed_version"] == "1.2.3"
    assert packet["fixed_channel"] == "preview"
    assert packet["fix_confirmation"]["fixed_version_receipt_id"] == "fix-version-receipt-authoritative-1"
    assert packet["fix_confirmation"]["fixed_channel_receipt_id"] == "fix-channel-receipt-authoritative-1"
    assert packet["fix_confirmation"]["fixed_receipt_truth_source"] == "fix_receipts"
    assert packet["reporter_followthrough"]["fixed_version_receipted"] is True
    assert packet["reporter_followthrough"]["fixed_channel_receipted"] is True
    plan_row = payload["reporter_followthrough_plan"]["action_groups"]["please_test"][0]
    assert plan_row["fixed_version_receipt_id"] == "fix-version-receipt-authoritative-1"
    assert plan_row["fixed_channel_receipt_id"] == "fix-channel-receipt-authoritative-1"
    assert plan_row["fixed_channel_receipt_source"] == "fix_receipts"
    assert plan_row["fixed_receipt_installation_source"] == "fix_receipts"


def test_materialize_support_case_packets_rejects_release_receipt_as_fix_version_and_channel_receipts(
    tmp_path: Path,
) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(
        json.dumps(
            {
                "installReceipts": [
                    {
                        "receiptId": "install-receipt-generic-fix-1",
                        "installationId": "install-generic-fix-1",
                        "version": "1.2.3",
                        "channel": "preview",
                    }
                ],
                "fixReceipts": [
                    {
                        "caseId": "support_case_generic_fix_receipt",
                        "installationId": "install-generic-fix-1",
                        "releaseReceiptId": "generic-release-receipt-only",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                    }
                ],
                "items": [
                    {
                        "caseId": "support_case_generic_fix_receipt",
                        "clusterKey": "support:generic-fix-receipt",
                        "kind": "bug_report",
                        "status": "fixed",
                        "title": "Release receipt id cannot unlock reporter followthrough as a fix receipt",
                        "summary": "Fixed-version and fixed-channel receipts must be fix receipt facts.",
                        "candidateOwnerRepo": "chummer6-ui",
                        "installationId": "install-generic-fix-1",
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "linux",
                        "arch": "x64",
                        "installedVersion": "1.2.3",
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "desktopTupleCoverage": {
                    "promotedInstallerTuples": [
                        {
                            "tupleId": "avalonia:linux:linux-x64",
                            "head": "avalonia",
                            "platform": "linux",
                            "rid": "linux-x64",
                            "artifactId": "avalonia-linux-x64-installer",
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--source", str(source), "--release-channel", str(release_channel), "--out", str(out_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["source"]["fix_receipt_feed_state"] == "provided"
    assert payload["source"]["fix_receipt_hydrated_case_count"] == 1
    assert payload["summary"]["fix_available_ready_count"] == 0
    assert payload["summary"]["please_test_ready_count"] == 0
    packet = payload["packets"][0]
    assert packet["fixed_version"] == "1.2.3"
    assert packet["fixed_channel"] == "preview"
    assert packet["fixed_version_receipt_id"] == ""
    assert packet["fixed_channel_receipt_id"] == ""
    assert packet["reporter_followthrough"]["fixed_version_receipted"] is False
    assert packet["reporter_followthrough"]["fixed_channel_receipted"] is False
    assert packet["reporter_followthrough"]["state"] == "blocked_missing_install_receipts"
    assert packet["reporter_followthrough"]["blockers"] == []
    assert payload["reporter_followthrough_plan"]["action_groups"]["fix_available"] == []
    assert payload["reporter_followthrough_plan"]["action_groups"]["please_test"] == []


def test_materialize_support_case_packets_blocks_fix_receipt_without_install_binding(
    tmp_path: Path,
) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(
        json.dumps(
            {
                "installReceipts": [
                    {
                        "receiptId": "install-receipt-fix-missing-bind-1",
                        "installationId": "install-fix-missing-bind-1",
                        "version": "1.2.3",
                        "channel": "preview",
                    }
                ],
                "fixReceipts": [
                    {
                        "caseId": "support_case_fix_missing_install_bind",
                        "receiptId": "fix-receipt-missing-install-bind-1",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                    }
                ],
                "items": [
                    {
                        "caseId": "support_case_fix_missing_install_bind",
                        "clusterKey": "support:fix-missing-install-bind",
                        "kind": "bug_report",
                        "status": "fixed",
                        "title": "Fix receipt lacks install binding",
                        "summary": "The fix receipt must name the same install before reporter followthrough leaves hold.",
                        "candidateOwnerRepo": "chummer6-ui",
                        "installationId": "install-fix-missing-bind-1",
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "linux",
                        "arch": "x64",
                        "installedVersion": "1.2.3",
                        "installedBuildReceiptId": "install-receipt-fix-missing-bind-1",
                        "installedBuildReceiptInstallationId": "install-fix-missing-bind-1",
                        "installedBuildReceiptVersion": "1.2.3",
                        "installedBuildReceiptChannel": "preview",
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "desktopTupleCoverage": {
                    "promotedInstallerTuples": [
                        {
                            "tupleId": "avalonia:linux:linux-x64",
                            "head": "avalonia",
                            "platform": "linux",
                            "rid": "linux-x64",
                            "artifactId": "avalonia-linux-x64-installer",
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--source", str(source), "--release-channel", str(release_channel), "--out", str(out_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["fix_available_ready_count"] == 0
    assert payload["summary"]["please_test_ready_count"] == 0
    packet = payload["packets"][0]
    assert packet["fixed_receipt_installation_id"] == ""
    assert packet["reporter_followthrough"]["fixed_receipt_installation_matches"] is False
    assert packet["reporter_followthrough"]["state"] == "blocked_missing_install_receipts"
    assert packet["reporter_followthrough"]["blockers"] == ["fixed_receipt_installation_missing"]
    assert payload["reporter_followthrough_plan"]["action_groups"]["fix_available"] == []


def test_materialize_support_case_packets_blocks_fix_receipt_for_different_install(
    tmp_path: Path,
) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(
        json.dumps(
            {
                "installReceipts": [
                    {
                        "receiptId": "install-receipt-fix-install-bind-1",
                        "installationId": "install-fix-install-bind-1",
                        "version": "1.2.3",
                        "channel": "preview",
                    }
                ],
                "fixReceipts": [
                    {
                        "caseId": "support_case_fix_receipt_wrong_install",
                        "installationId": "install-other-fix-receipt",
                        "receiptId": "fix-receipt-wrong-install-1",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                    }
                ],
                "items": [
                    {
                        "caseId": "support_case_fix_receipt_wrong_install",
                        "clusterKey": "support:fix-receipt-wrong-install",
                        "kind": "bug_report",
                        "status": "fixed",
                        "title": "Fix receipt belongs to a different install",
                        "summary": "Case id matches, but receipt truth must stay bound to the linked installation.",
                        "candidateOwnerRepo": "chummer6-ui",
                        "installationId": "install-fix-install-bind-1",
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "linux",
                        "arch": "x64",
                        "installedVersion": "1.2.3",
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "desktopTupleCoverage": {
                    "promotedInstallerTuples": [
                        {
                            "tupleId": "avalonia:linux:linux-x64",
                            "head": "avalonia",
                            "platform": "linux",
                            "rid": "linux-x64",
                            "artifactId": "avalonia-linux-x64-installer",
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--source", str(source), "--release-channel", str(release_channel), "--out", str(out_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["source"]["fix_receipt_hydrated_case_count"] == 1
    assert payload["summary"]["fix_available_ready_count"] == 0
    assert payload["summary"]["reporter_followthrough_blocked_receipt_mismatch_count"] == 1
    packet = payload["packets"][0]
    assert packet["fixed_receipt_installation_id"] == "install-other-fix-receipt"
    assert packet["reporter_followthrough"]["fixed_version_receipted"] is True
    assert packet["reporter_followthrough"]["fixed_channel_receipted"] is True
    assert packet["reporter_followthrough"]["fixed_receipt_installation_matches"] is False
    assert packet["reporter_followthrough"]["blockers"] == ["fixed_receipt_installation_mismatch"]
    assert payload["reporter_followthrough_plan"]["action_groups"]["fix_available"] == []
    blocked_row = payload["reporter_followthrough_plan"]["action_groups"]["blocked_receipt_mismatch"][0]
    assert blocked_row["fixed_receipt_installation_id"] == "install-other-fix-receipt"


def test_materialize_support_case_packets_uses_latest_fix_receipt_over_stale_later_row(
    tmp_path: Path,
) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(
        json.dumps(
            {
                "installReceipts": [
                    {
                        "receiptId": "install-receipt-latest-fix-1",
                        "installationId": "install-latest-fix-1",
                        "version": "1.2.3",
                        "channel": "preview",
                    }
                ],
                "fixReceipts": [
                    {
                        "caseId": "support_case_latest_fix_receipt",
                        "installationId": "install-latest-fix-1",
                        "receiptId": "fix-receipt-latest-1",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                        "recordedAtUtc": "2026-04-17T10:00:00Z",
                    },
                    {
                        "caseId": "support_case_latest_fix_receipt",
                        "installationId": "install-latest-fix-1",
                        "receiptId": "fix-receipt-stale-1",
                        "fixedVersion": "1.2.2",
                        "fixedChannel": "nightly",
                        "recordedAtUtc": "2026-04-17T09:00:00Z",
                    },
                ],
                "items": [
                    {
                        "caseId": "support_case_latest_fix_receipt",
                        "clusterKey": "support:latest-fix-receipt",
                        "kind": "bug_report",
                        "status": "fixed",
                        "title": "Fix receipt feed has duplicate rows",
                        "summary": "Latest fix receipt should win instead of stale queued or stale feed values.",
                        "candidateOwnerRepo": "chummer6-ui",
                        "installationId": "install-latest-fix-1",
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "linux",
                        "arch": "x64",
                        "installedVersion": "1.2.3",
                        "fixedVersion": "1.2.2",
                        "fixedChannel": "nightly",
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "desktopTupleCoverage": {
                    "promotedInstallerTuples": [
                        {
                            "tupleId": "avalonia:linux:linux-x64",
                            "head": "avalonia",
                            "platform": "linux",
                            "rid": "linux-x64",
                            "artifactId": "avalonia-linux-x64-installer",
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--source", str(source), "--release-channel", str(release_channel), "--out", str(out_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["fix_available_ready_count"] == 0
    packet = payload["packets"][0]
    assert packet["fixed_version"] == "1.2.3"
    assert packet["fixed_channel"] == "preview"
    assert packet["fix_confirmation"]["fixed_version_receipt_id"] == "fix-receipt-latest-1"
    assert packet["reporter_followthrough"]["fixed_version_receipted"] is True
    assert packet["reporter_followthrough"]["fixed_channel_receipted"] is True


def test_materialize_support_case_packets_uses_latest_install_bound_fix_receipt_over_stale_case_row(
    tmp_path: Path,
) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(
        json.dumps(
            {
                "installReceipts": [
                    {
                        "receiptId": "install-receipt-latest-install-fix-1",
                        "installationId": "install-latest-install-fix-1",
                        "version": "1.2.3",
                        "channel": "preview",
                    }
                ],
                "fixReceipts": [
                    {
                        "caseId": "support_case_latest_install_fix_receipt",
                        "installationId": "install-latest-install-fix-1",
                        "receiptId": "fix-receipt-stale-case-1",
                        "fixedVersion": "1.2.2",
                        "fixedChannel": "nightly",
                        "recordedAtUtc": "2026-04-17T10:00:00Z",
                    },
                    {
                        "installationId": "install-latest-install-fix-1",
                        "receiptId": "fix-receipt-latest-install-1",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                        "recordedAtUtc": "2026-04-17T11:00:00Z",
                    },
                ],
                "items": [
                    {
                        "caseId": "support_case_latest_install_fix_receipt",
                        "clusterKey": "support:latest-install-fix-receipt",
                        "kind": "bug_report",
                        "status": "fixed",
                        "title": "Install-bound fix receipt is newer than stale case row",
                        "summary": "Case and install receipt candidates must be ranked together.",
                        "candidateOwnerRepo": "chummer6-ui",
                        "installationId": "install-latest-install-fix-1",
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "linux",
                        "arch": "x64",
                        "installedVersion": "1.2.3",
                        "fixedVersion": "1.2.2",
                        "fixedChannel": "nightly",
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "desktopTupleCoverage": {
                    "promotedInstallerTuples": [
                        {
                            "tupleId": "avalonia:linux:linux-x64",
                            "head": "avalonia",
                            "platform": "linux",
                            "rid": "linux-x64",
                            "artifactId": "avalonia-linux-x64-installer",
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--source", str(source), "--release-channel", str(release_channel), "--out", str(out_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    packet = payload["packets"][0]
    assert packet["fixed_version"] == "1.2.3"
    assert packet["fixed_channel"] == "preview"
    assert packet["fix_confirmation"]["fixed_version_receipt_id"] == "fix-receipt-latest-install-1"
    assert packet["reporter_followthrough"]["fixed_version_receipted"] is True
    assert packet["reporter_followthrough"]["fixed_channel_receipted"] is True
    assert payload["reporter_followthrough_plan"]["action_groups"]["please_test"][0][
        "fixed_version_receipt_id"
    ] == "fix-receipt-latest-install-1"


def test_materialize_support_case_packets_suppresses_queued_fix_fields_when_fix_receipt_feed_lacks_case(
    tmp_path: Path,
) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(
        json.dumps(
            {
                "fixReceipts": [
                    {
                        "caseId": "support_case_other_fix",
                        "receiptId": "fix-receipt-other-1",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                    }
                ],
                "items": [
                    {
                        "caseId": "support_case_queued_fix_only",
                        "clusterKey": "support:queued-fix-only",
                        "kind": "bug_report",
                        "status": "fixed",
                        "title": "Fix is queued but fix receipt feed has no matching receipt",
                        "summary": "Queued support fix fields must not trigger followthrough when fix receipts are authoritative.",
                        "candidateOwnerRepo": "chummer6-ui",
                        "installationId": "install-queued-fix-only",
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "linux",
                        "arch": "x64",
                        "installedVersion": "1.2.3",
                        "installedBuildReceiptId": "install-receipt-queued-fix-only",
                        "installedBuildReceiptInstallationId": "install-queued-fix-only",
                        "installedBuildReceiptVersion": "1.2.3",
                        "installedBuildReceiptChannel": "preview",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "desktopTupleCoverage": {
                    "promotedInstallerTuples": [
                        {
                            "tupleId": "avalonia:linux:linux-x64",
                            "head": "avalonia",
                            "platform": "linux",
                            "rid": "linux-x64",
                            "artifactId": "avalonia-linux-x64-installer",
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--source", str(source), "--release-channel", str(release_channel), "--out", str(out_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["source"]["fix_receipt_feed_state"] == "provided"
    assert payload["source"]["fix_receipt_missing_case_count"] == 1
    assert payload["summary"]["fix_available_ready_count"] == 0
    packet = payload["packets"][0]
    assert packet["fixed_version"] == ""
    assert packet["fixed_channel"] == ""
    assert packet["fix_confirmation"]["fixed_receipt_truth_source"] == "fix_receipts_missing"
    assert packet["reporter_followthrough"]["state"] == "no_fix_recorded"


def test_materialize_support_case_packets_prefers_install_bound_fix_receipt_over_wrong_case_receipt(
    tmp_path: Path,
) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(
        json.dumps(
            {
                "installReceipts": [
                    {
                        "receiptId": "install-receipt-install-bound-fix",
                        "installationId": "install-bound-fix",
                        "version": "1.2.3",
                        "channel": "preview",
                    }
                ],
                "fixReceipts": [
                    {
                        "caseId": "support_case_install_bound_fix",
                        "installationId": "other-install",
                        "receiptId": "fix-receipt-wrong-case-install",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                        "recordedAtUtc": "2026-04-17T11:00:00Z",
                    },
                    {
                        "installationId": "install-bound-fix",
                        "receiptId": "fix-receipt-correct-install",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                        "recordedAtUtc": "2026-04-17T10:00:00Z",
                    },
                ],
                "items": [
                    {
                        "caseId": "support_case_install_bound_fix",
                        "clusterKey": "support:install-bound-fix",
                        "kind": "bug_report",
                        "status": "fixed",
                        "title": "Case receipt points at another install",
                        "summary": "The real linked install receipt must drive reporter followthrough.",
                        "candidateOwnerRepo": "chummer6-ui",
                        "installationId": "install-bound-fix",
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "linux",
                        "arch": "x64",
                        "installedVersion": "1.2.3",
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "desktopTupleCoverage": {
                    "promotedInstallerTuples": [
                        {
                            "tupleId": "avalonia:linux:linux-x64",
                            "head": "avalonia",
                            "platform": "linux",
                            "rid": "linux-x64",
                            "artifactId": "avalonia-linux-x64-installer",
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--source", str(source), "--release-channel", str(release_channel), "--out", str(out_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["reporter_followthrough_ready_count"] == 1
    assert payload["summary"]["please_test_ready_count"] == 1
    packet = payload["packets"][0]
    assert packet["fixed_version"] == "1.2.3"
    assert packet["fixed_channel"] == "preview"
    assert packet["fix_confirmation"]["fixed_receipt_installation_id"] == "install-bound-fix"
    assert packet["reporter_followthrough"]["fixed_version_receipt_id"] == "fix-receipt-correct-install"
    assert packet["reporter_followthrough"]["fixed_receipt_installation_matches"] is True
    assert packet["reporter_followthrough"]["blockers"] == []
    assert payload["reporter_followthrough_plan"]["action_groups"]["please_test"][0][
        "fixed_receipt_installation_id"
    ] == "install-bound-fix"


def test_materialize_support_case_packets_derives_please_test_from_receipts_even_when_case_is_accepted(
    tmp_path: Path,
) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(
        json.dumps(
            {
                "installReceipts": [
                    {
                        "receiptId": "install-receipt-open-case-1",
                        "installationId": "install-open-case-1",
                        "version": "1.2.3",
                        "channel": "preview",
                        "headId": "avalonia",
                        "platform": "linux",
                        "rid": "linux-x64",
                        "recordedAtUtc": "2026-04-17T11:30:00Z",
                    }
                ],
                "fixReceipts": [
                    {
                        "installationId": "install-open-case-1",
                        "receiptId": "fix-receipt-open-case-1",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                        "recordedAtUtc": "2026-04-17T12:00:00Z",
                    }
                ],
                "items": [
                    {
                        "caseId": "support_case_open_but_receipted",
                        "clusterKey": "support:open-but-receipted",
                        "kind": "bug_report",
                        "status": "accepted",
                        "title": "Receipts show the fix is installed before support state closes",
                        "summary": "Reporter followthrough should come from the install-aware receipt truth, not the queued case status.",
                        "candidateOwnerRepo": "chummer6-ui",
                        "installationId": "install-open-case-1",
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "linux",
                        "arch": "x64",
                        "installedVersion": "1.2.3",
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "desktopTupleCoverage": {
                    "promotedInstallerTuples": [
                        {
                            "tupleId": "avalonia:linux:linux-x64",
                            "head": "avalonia",
                            "platform": "linux",
                            "rid": "linux-x64",
                            "artifactId": "avalonia-linux-x64-installer",
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--source", str(source), "--release-channel", str(release_channel), "--out", str(out_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["reporter_followthrough_ready_count"] == 1
    assert payload["summary"]["fix_available_ready_count"] == 0
    assert payload["summary"]["please_test_ready_count"] == 1
    packet = payload["packets"][0]
    assert packet["status"] == "accepted"
    assert packet["reporter_followthrough"]["state"] == "please_test_ready"
    assert packet["reporter_followthrough"]["next_action"] == "send_please_test"
    assert packet["reporter_followthrough"]["feedback_loop_ready"] is True
    assert packet["reporter_followthrough"]["current_install_on_fixed_build"] is True
    assert packet["reporter_followthrough"]["blockers"] == []
    please_test_row = payload["reporter_followthrough_plan"]["action_groups"]["please_test"][0]
    assert please_test_row["status"] == "accepted"
    assert please_test_row["receipt_ready_for_please_test"] is True


def test_materialize_support_case_packets_suppresses_queued_fix_fields_when_fix_receipt_feed_is_empty(
    tmp_path: Path,
) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(
        json.dumps(
            {
                "installReceipts": [
                    {
                        "receiptId": "install-receipt-empty-fix-feed",
                        "installationId": "install-empty-fix-feed",
                        "version": "1.2.3",
                        "channel": "preview",
                    }
                ],
                "fixReceipts": [],
                "items": [
                    {
                        "caseId": "support_case_empty_fix_feed",
                        "clusterKey": "support:empty-fix-feed",
                        "kind": "bug_report",
                        "status": "fixed",
                        "title": "Empty fix receipt feed must still be authoritative",
                        "summary": "Queued support fix fields must not unlock followthrough.",
                        "candidateOwnerRepo": "chummer6-ui",
                        "installationId": "install-empty-fix-feed",
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "linux",
                        "arch": "x64",
                        "installedVersion": "1.2.3",
                        "installedBuildReceiptId": "install-receipt-empty-fix-feed",
                        "installedBuildReceiptInstallationId": "install-empty-fix-feed",
                        "installedBuildReceiptVersion": "1.2.3",
                        "installedBuildReceiptChannel": "preview",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                        "fixedVersionReceiptId": "queued-fix-version-empty-feed",
                        "fixedChannelReceiptId": "queued-fix-channel-empty-feed",
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "desktopTupleCoverage": {
                    "promotedInstallerTuples": [
                        {
                            "tupleId": "avalonia:linux:linux-x64",
                            "head": "avalonia",
                            "platform": "linux",
                            "rid": "linux-x64",
                            "artifactId": "avalonia-linux-x64-installer",
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--source", str(source), "--release-channel", str(release_channel), "--out", str(out_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["source"]["fix_receipt_feed_state"] == "provided"
    assert payload["source"]["fix_receipt_source_count"] == 0
    assert payload["source"]["fix_receipt_missing_case_count"] == 1
    assert payload["summary"]["fix_available_ready_count"] == 0
    packet = payload["packets"][0]
    assert packet["fixed_version"] == ""
    assert packet["fixed_channel"] == ""
    assert packet["fix_confirmation"]["fixed_receipt_truth_source"] == "fix_receipts_missing"
    assert packet["reporter_followthrough"]["state"] == "no_fix_recorded"


def test_materialize_support_case_packets_blocks_recovery_loop_without_installed_build_receipt_id(tmp_path: Path) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "caseId": "support_case_recovery_without_build_receipt",
                        "clusterKey": "support:recovery-version-only",
                        "kind": "install_help",
                        "status": "new",
                        "title": "Install is linked but build receipt is missing",
                        "summary": "Recovery followthrough must not compile from support state alone.",
                        "candidateOwnerRepo": "chummer6-hub",
                        "designImpactSuspected": False,
                        "installationId": "install-recovery-1",
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "linux",
                        "arch": "x64",
                        "installedVersion": "1.2.3",
                    }
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "rolloutState": "published",
                "supportabilityState": "supported",
                "desktopTupleCoverage": {
                    "promotedInstallerTuples": [
                        {
                            "tupleId": "avalonia:linux:linux-x64",
                            "head": "avalonia",
                            "platform": "linux",
                            "rid": "linux-x64",
                            "artifactId": "avalonia-linux-x64-installer",
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source",
            str(source),
            "--release-channel",
            str(release_channel),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["reporter_followthrough_ready_count"] == 0
    assert payload["summary"]["feedback_followthrough_ready_count"] == 0
    assert payload["summary"]["recovery_loop_ready_count"] == 0
    packet = payload["packets"][0]
    assert packet["reporter_followthrough"]["state"] == "no_fix_recorded"
    assert packet["reporter_followthrough"]["next_action"] == "hold_until_fix_receipt"
    assert packet["reporter_followthrough"]["install_receipt_ready"] is True
    assert packet["reporter_followthrough"]["release_receipt_state"] == "release_receipt_ready"
    assert packet["reporter_followthrough"]["installed_build_receipted"] is False
    assert packet["reporter_followthrough"]["recovery_loop_ready"] is False
    assert packet["reporter_followthrough"]["blockers"] == ["installed_build_receipt_missing_for_recovery"]


def test_materialize_support_case_packets_blocks_recovery_until_fix_receipt_even_with_install_receipt(tmp_path: Path) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(
        json.dumps(
            {
                "installReceipts": [
                    {
                        "receiptId": "install-receipt-recovery-1",
                        "installationId": "install-recovery-receipted",
                        "version": "1.2.3",
                        "channel": "preview",
                    }
                ],
                "items": [
                    {
                        "caseId": "support_case_recovery_with_build_receipt",
                        "clusterKey": "support:recovery-receipted",
                        "kind": "install_help",
                        "status": "new",
                        "title": "Install is linked and receipt-backed but no fix is receipted",
                        "summary": "Recovery followthrough must wait for the same fixed-version and fixed-channel receipts as fix mail.",
                        "candidateOwnerRepo": "chummer6-hub",
                        "designImpactSuspected": False,
                        "installationId": "install-recovery-receipted",
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "linux",
                        "arch": "x64",
                        "installedVersion": "1.2.3",
                        "installedBuildReceiptId": "install-receipt-recovery-1",
                        "installedBuildReceiptInstallationId": "install-recovery-receipted",
                        "installedBuildReceiptVersion": "1.2.3",
                        "installedBuildReceiptChannel": "preview",
                    }
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "rolloutState": "published",
                "supportabilityState": "supported",
                "desktopTupleCoverage": {
                    "promotedInstallerTuples": [
                        {
                            "tupleId": "avalonia:linux:linux-x64",
                            "head": "avalonia",
                            "platform": "linux",
                            "rid": "linux-x64",
                            "artifactId": "avalonia-linux-x64-installer",
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source",
            str(source),
            "--release-channel",
            str(release_channel),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["reporter_followthrough_ready_count"] == 1
    assert payload["summary"]["feedback_followthrough_ready_count"] == 1
    assert payload["summary"]["recovery_loop_ready_count"] == 0
    packet = payload["packets"][0]
    assert packet["recovery_path"]["action_id"] == "open_support_timeline"
    assert packet["reporter_followthrough"]["state"] == "no_fix_recorded"
    assert packet["reporter_followthrough"]["next_action"] == "send_feedback_progress"
    assert packet["reporter_followthrough"]["feedback_loop_ready"] is True
    assert packet["reporter_followthrough"]["installed_build_receipted"] is True
    assert packet["reporter_followthrough"]["blockers"] == []
    plan = payload["reporter_followthrough_plan"]
    assert plan["ready_count"] == 1
    assert plan["feedback_ready_count"] == 1
    assert len(plan["action_groups"]["feedback"]) == 1
    assert plan["action_groups"]["feedback"][0]["next_action"] == "send_feedback_progress"
    assert plan["hold_until_fix_receipt_count"] == 1
    assert payload["summary"]["reporter_followthrough_hold_until_fix_receipt_count"] == 1
    assert plan["action_groups"]["recovery"] == []
    assert len(plan["action_groups"]["hold_until_fix_receipt"]) == 1
    assert plan["action_groups"]["hold_until_fix_receipt"][0]["recovery_path"]["action_id"] == "open_support_timeline"
    receipt_gates = payload["followthrough_receipt_gates"]
    assert receipt_gates["ready_count"] == 1
    assert receipt_gates["gate_counts"]["feedback_loop_ready"] == 1


def test_materialize_support_case_packets_blocks_recovery_followthrough_on_channel_mismatch(tmp_path: Path) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "caseId": "support_case_fixed_wrong_channel",
                        "clusterKey": "support:wrong-channel",
                        "kind": "bug_report",
                        "status": "fixed",
                        "title": "Fix is staged but reporter channel disagrees",
                        "summary": "Recovery mail must wait for the same promoted install truth as fix mail.",
                        "candidateOwnerRepo": "chummer6-ui",
                        "designImpactSuspected": False,
                        "installationId": "install-release-5",
                        "releaseChannel": "nightly",
                        "headId": "avalonia",
                        "platform": "linux",
                        "arch": "x64",
                        "installedVersion": "1.2.2",
                        "installedBuildReceiptId": "install-receipt-nightly-1",
                        "installedBuildReceiptInstallationId": "install-release-5",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                    }
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "rolloutState": "published",
                "supportabilityState": "supported",
                "desktopTupleCoverage": {
                    "promotedInstallerTuples": [
                        {
                            "tupleId": "avalonia:linux:linux-x64",
                            "head": "avalonia",
                            "platform": "linux",
                            "rid": "linux-x64",
                            "artifactId": "avalonia-linux-x64-installer",
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source",
            str(source),
            "--release-channel",
            str(release_channel),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["reporter_followthrough_ready_count"] == 0
    assert payload["summary"]["reporter_followthrough_blocked_missing_install_receipts_count"] == 1
    assert payload["summary"]["fix_available_ready_count"] == 0
    assert payload["summary"]["please_test_ready_count"] == 0
    assert payload["summary"]["recovery_loop_ready_count"] == 0
    packet = payload["packets"][0]
    assert packet["install_truth_state"] == "channel_mismatch"
    assert packet["recovery_path"]["action_id"] == "open_downloads"
    assert packet["reporter_followthrough"]["state"] == "blocked_missing_install_receipts"
    assert packet["reporter_followthrough"]["next_action"] == "hold_reporter_followthrough"
    assert packet["reporter_followthrough"]["install_receipt_ready"] is False
    assert packet["reporter_followthrough"]["release_receipt_state"] == "release_receipt_ready"
    assert packet["reporter_followthrough"]["recovery_loop_ready"] is False
    assert packet["reporter_followthrough"]["blockers"] == ["install_truth_state:channel_mismatch"]


def test_materialize_support_case_packets_projects_external_proof_requests_for_missing_tuple(tmp_path: Path) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "caseId": "support_case_windows_tuple_missing",
                        "clusterKey": "support:windows-missing",
                        "kind": "install_help",
                        "status": "accepted",
                        "title": "Windows tuple missing from promoted shelf",
                        "summary": "Support needs host-proof request truth for this install tuple.",
                        "candidateOwnerRepo": "chummer6-hub",
                        "designImpactSuspected": False,
                        "installationId": "install-windows-1",
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "windows",
                        "arch": "x64",
                        "installedVersion": "1.2.3",
                    }
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "rolloutState": "coverage_incomplete",
                "supportabilityState": "review_required",
                "desktopTupleCoverage": {
                    "promotedInstallerTuples": [
                        {
                            "tupleId": "avalonia:linux:linux-x64",
                            "head": "avalonia",
                            "platform": "linux",
                            "rid": "linux-x64",
                            "artifactId": "avalonia-linux-x64-installer",
                        }
                    ],
                    "externalProofRequests": [
                        {
                            "tupleId": "avalonia:win-x64:windows",
                            "head": "avalonia",
                            "platform": "windows",
                            "rid": "win-x64",
                            "requiredHost": "windows",
                            "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                            "expectedArtifactId": "avalonia-win-x64-installer",
                            "expectedInstallerFileName": "chummer-avalonia-win-x64-installer.exe",
                            "expectedInstallerSha256": "b" * 64,
                            "expectedPublicInstallRoute": "/downloads/install/avalonia-win-x64-installer",
                            "expectedStartupSmokeReceiptPath": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                            "startupSmokeReceiptContract": {
                                "statusAnyOf": ["pass", "passed", "ready"],
                                "readyCheckpoint": "pre_ui_event_loop",
                                "headId": "avalonia",
                                "platform": "windows",
                                "rid": "win-x64",
                                "hostClassContains": "windows",
                            },
                        }
                    ],
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source",
            str(source),
            "--release-channel",
            str(release_channel),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["install_truth_state_counts"]["tuple_not_on_promoted_shelf"] == 1
    assert payload["summary"]["external_proof_required_case_count"] == 1
    assert payload["summary"]["external_proof_required_host_counts"] == {"windows": 1}
    assert payload["summary"]["external_proof_required_tuple_counts"] == {"avalonia:win-x64:windows": 1}
    assert payload["summary"]["unresolved_external_proof_request_count"] == 1
    assert payload["summary"]["unresolved_external_proof_request_host_counts"] == {"windows": 1}
    assert payload["summary"]["unresolved_external_proof_request_tuple_counts"] == {"avalonia:win-x64:windows": 1}
    assert payload["summary"]["unresolved_external_proof_request_hosts"] == ["windows"]
    assert payload["summary"]["unresolved_external_proof_request_tuples"] == ["avalonia:win-x64:windows"]
    spec = payload["summary"]["unresolved_external_proof_request_specs"]["avalonia:win-x64:windows"]
    assert spec["channel_id"] == "preview"
    assert spec["tuple_entry_count"] == 1
    assert spec["tuple_unique"] is True
    assert spec["required_host"] == "windows"
    assert spec["required_proofs"] == ["promoted_installer_artifact", "startup_smoke_receipt"]
    assert spec["expected_artifact_id"] == "avalonia-win-x64-installer"
    assert spec["expected_installer_file_name"] == "chummer-avalonia-win-x64-installer.exe"
    assert spec["expected_installer_relative_path"] == "files/chummer-avalonia-win-x64-installer.exe"
    assert spec["expected_installer_sha256"] == "b" * 64
    assert spec["expected_public_install_route"] == "/downloads/install/avalonia-win-x64-installer"
    assert spec["expected_startup_smoke_receipt_path"] == "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json"
    assert spec["startup_smoke_receipt_contract"] == {
        "head_id": "avalonia",
        "host_class_contains": "windows",
        "platform": "windows",
        "ready_checkpoint": "pre_ui_event_loop",
        "rid": "win-x64",
        "status_any_of": ["pass", "passed", "ready"],
    }
    assert spec["proof_capture_commands"] == [
        "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=Windows ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe avalonia win-x64 Chummer.Avalonia.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke 1.2.3",
        "cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh",
    ]
    assert spec["local_evidence"]["installer_artifact"]["path"].endswith(
        "files/chummer-avalonia-win-x64-installer.exe"
    )
    assert spec["local_evidence"]["startup_smoke_receipt"]["path"].endswith(
        "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json"
    )
    packet = payload["packets"][0]
    assert packet["install_truth_state"] == "tuple_not_on_promoted_shelf"
    assert packet["install_diagnosis"]["case_tuple_id"] == "avalonia:win-x64:windows"
    assert packet["install_diagnosis"]["external_proof_required"] is True
    packet_request = packet["install_diagnosis"]["external_proof_request"]
    assert packet_request["tuple_id"] == "avalonia:win-x64:windows"
    assert packet_request["channel_id"] == "preview"
    assert packet_request["tuple_entry_count"] == 1
    assert packet_request["tuple_unique"] is True
    assert packet_request["required_host"] == "windows"
    assert packet_request["required_proofs"] == ["promoted_installer_artifact", "startup_smoke_receipt"]
    assert packet_request["expected_artifact_id"] == "avalonia-win-x64-installer"
    assert packet_request["expected_installer_file_name"] == "chummer-avalonia-win-x64-installer.exe"
    assert packet_request["expected_installer_relative_path"] == "files/chummer-avalonia-win-x64-installer.exe"
    assert packet_request["expected_installer_sha256"] == "b" * 64
    assert packet_request["expected_public_install_route"] == "/downloads/install/avalonia-win-x64-installer"
    assert packet_request["expected_startup_smoke_receipt_path"] == "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json"
    assert packet_request["local_evidence"]["installer_artifact"]["path"].endswith(
        "files/chummer-avalonia-win-x64-installer.exe"
    )
    assert packet_request["local_evidence"]["startup_smoke_receipt"]["path"].endswith(
        "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json"
    )
    assert packet["recovery_path"]["action_id"] == "open_downloads"


def test_materialize_support_case_packets_normalizes_legacy_capture_operating_system_token(tmp_path: Path) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(json.dumps({"items": []}, indent=2) + "\n", encoding="utf-8")
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "desktopTupleCoverage": {
                    "externalProofRequests": [
                        {
                            "tupleId": "avalonia:win-x64:windows",
                            "head": "avalonia",
                            "platform": "windows",
                            "rid": "win-x64",
                            "requiredHost": "windows",
                            "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                            "proofCaptureCommands": [
                                "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=Windows CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe avalonia win-x64 Chummer.Avalonia.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke",
                            ],
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source",
            str(source),
            "--release-channel",
            str(release_channel),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["unresolved_external_proof_request_count"] == 1
    spec = payload["summary"]["unresolved_external_proof_request_specs"]["avalonia:win-x64:windows"]
    assert spec["proof_capture_commands"] == [
        "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=Windows ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe avalonia win-x64 Chummer.Avalonia.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke",
    ]
    assert "CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=linux" not in json.dumps(spec["proof_capture_commands"])
    assert "CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=Windows" in json.dumps(spec["proof_capture_commands"])


def test_materialize_support_case_packets_matches_external_proof_request_when_case_uses_legacy_tuple_order(
    tmp_path: Path,
) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "caseId": "support_case_windows_tuple_legacy_order",
                        "clusterKey": "support:windows-legacy-order",
                        "kind": "install_help",
                        "status": "accepted",
                        "title": "Windows tuple captured in legacy tuple order",
                        "summary": "Case payload provides head:platform:rid without arch metadata.",
                        "candidateOwnerRepo": "chummer6-hub",
                        "designImpactSuspected": False,
                        "installationId": "install-windows-legacy-1",
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "windows",
                        "tupleId": "avalonia:windows:win-x64",
                        "installedVersion": "1.2.3",
                    }
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "rolloutState": "coverage_incomplete",
                "supportabilityState": "review_required",
                "desktopTupleCoverage": {
                    "promotedInstallerTuples": [
                        {
                            "tupleId": "avalonia:linux:linux-x64",
                            "head": "avalonia",
                            "platform": "linux",
                            "rid": "linux-x64",
                            "artifactId": "avalonia-linux-x64-installer",
                        }
                    ],
                    "externalProofRequests": [
                        {
                            "tupleId": "avalonia:win-x64:windows",
                            "head": "avalonia",
                            "platform": "windows",
                            "rid": "win-x64",
                            "requiredHost": "windows",
                            "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                        }
                    ],
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source",
            str(source),
            "--release-channel",
            str(release_channel),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["external_proof_required_case_count"] == 1
    assert payload["summary"]["external_proof_required_tuple_counts"] == {"avalonia:win-x64:windows": 1}
    packet = payload["packets"][0]
    assert packet["install_diagnosis"]["case_tuple_id"] == "avalonia:win-x64:windows"
    assert packet["install_diagnosis"]["external_proof_required"] is True
    assert packet["install_diagnosis"]["external_proof_request"]["tuple_id"] == "avalonia:win-x64:windows"


def test_materialize_support_case_packets_reports_release_channel_external_proof_backlog_without_open_cases(
    tmp_path: Path,
) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(json.dumps({"items": []}, indent=2) + "\n", encoding="utf-8")
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "desktopTupleCoverage": {
                    "externalProofRequests": [
                        {
                            "tupleId": "avalonia:win-x64:windows",
                            "head": "avalonia",
                            "platform": "windows",
                            "rid": "win-x64",
                            "requiredHost": "windows",
                            "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                        },
                        {
                            "tupleId": "blazor-desktop:osx-arm64:macos",
                            "head": "blazor-desktop",
                            "platform": "macos",
                            "rid": "osx-arm64",
                            "requiredHost": "macos",
                            "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                        },
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source",
            str(source),
            "--release-channel",
            str(release_channel),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["open_case_count"] == 0
    assert payload["summary"]["open_non_external_packet_count"] == 0
    assert payload["summary"]["external_proof_required_case_count"] == 0
    assert payload["summary"]["needs_human_response"] == 2
    assert payload["summary"]["non_external_needs_human_response"] == 0
    assert payload["summary"]["non_external_packets_without_named_owner"] == 0
    assert payload["summary"]["non_external_packets_without_lane"] == 0
    assert payload["summary"]["unresolved_external_proof_request_count"] == 2
    assert payload["summary"]["unresolved_external_proof_request_host_counts"] == {"macos": 1, "windows": 1}
    assert payload["summary"]["unresolved_external_proof_request_tuple_counts"] == {
        "avalonia:win-x64:windows": 1,
        "blazor-desktop:osx-arm64:macos": 1,
    }
    assert payload["summary"]["unresolved_external_proof_request_hosts"] == ["macos", "windows"]
    assert payload["summary"]["unresolved_external_proof_request_tuples"] == [
        "avalonia:win-x64:windows",
        "blazor-desktop:osx-arm64:macos",
    ]
    win_spec = payload["summary"]["unresolved_external_proof_request_specs"]["avalonia:win-x64:windows"]
    mac_spec = payload["summary"]["unresolved_external_proof_request_specs"]["blazor-desktop:osx-arm64:macos"]
    assert win_spec["required_host"] == "windows"
    assert win_spec["local_evidence"]["installer_artifact"]["state"] == "missing"
    assert win_spec["local_evidence"]["startup_smoke_receipt"]["state"] == "missing"
    assert mac_spec["required_host"] == "macos"
    assert mac_spec["local_evidence"]["installer_artifact"]["state"] == "missing"
    assert mac_spec["local_evidence"]["startup_smoke_receipt"]["state"] == "missing"
    execution_plan = payload["unresolved_external_proof_execution_plan"]
    assert execution_plan["request_count"] == 2
    assert execution_plan["hosts"] == ["macos", "windows"]
    assert execution_plan["capture_deadline_hours"] == 24
    assert execution_plan["capture_deadline_utc"]
    assert execution_plan["generated_at"]
    assert execution_plan["command_root"] == "/docker/fleet/.codex-studio/published/external-proof-commands"
    assert execution_plan["host_groups"]["macos"]["request_count"] == 1
    assert execution_plan["host_groups"]["windows"]["request_count"] == 1
    assert execution_plan["host_groups"]["macos"]["tuples"] == ["blazor-desktop:osx-arm64:macos"]
    assert execution_plan["host_groups"]["windows"]["tuples"] == ["avalonia:win-x64:windows"]
    macos_request = execution_plan["host_groups"]["macos"]["requests"][0]
    windows_request = execution_plan["host_groups"]["windows"]["requests"][0]
    assert macos_request["capture_deadline_utc"] == execution_plan["capture_deadline_utc"]
    assert windows_request["capture_deadline_utc"] == execution_plan["capture_deadline_utc"]
    assert macos_request["required_proofs"] == ["promoted_installer_artifact", "startup_smoke_receipt"]
    assert windows_request["required_proofs"] == ["promoted_installer_artifact", "startup_smoke_receipt"]
    assert execution_plan["host_groups"]["windows"]["command_pack_path"].endswith(
        "/windows-proof-command-pack.tgz"
    )
    assert execution_plan["host_groups"]["windows"]["operator_commands"]["preflight"] == (
        "bash /docker/fleet/.codex-studio/published/external-proof-commands/preflight-windows-proof.sh"
    )
    assert execution_plan["host_groups"]["windows"]["operator_commands"]["capture"] == (
        "bash /docker/fleet/.codex-studio/published/external-proof-commands/capture-windows-proof.sh"
    )
    assert execution_plan["host_groups"]["windows"]["operator_commands"]["capture_powershell"] == (
        "powershell -ExecutionPolicy Bypass -File "
        "/docker/fleet/.codex-studio/published/external-proof-commands/capture-windows-proof.ps1"
    )
    assert "capture-windows-proof.sh" in execution_plan["recommended_action"]
    assert "ingest-windows-proof-bundle.sh" in execution_plan["recommended_action"]


def test_materialize_support_case_packets_dedupes_duplicate_external_proof_tuples(tmp_path: Path) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(json.dumps({"items": []}, indent=2) + "\n", encoding="utf-8")
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "desktopTupleCoverage": {
                    "externalProofRequests": [
                        {
                            "tupleId": "avalonia:win-x64:windows",
                            "head": "avalonia",
                            "platform": "windows",
                            "rid": "win-x64",
                            "requiredHost": "windows",
                            "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                        },
                        {
                            "tupleId": "avalonia:win-x64:windows",
                            "head": "avalonia",
                            "platform": "windows",
                            "rid": "win-x64",
                            "requiredHost": "windows",
                            "requiredProofs": ["promoted_installer_artifact"],
                        },
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source",
            str(source),
            "--release-channel",
            str(release_channel),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["operator_packet_count"] == 1
    assert payload["summary"]["unresolved_external_proof_request_count"] == 1
    assert payload["summary"]["unresolved_external_proof_request_tuple_counts"] == {
        "avalonia:win-x64:windows": 1
    }
    deduped_spec = payload["summary"]["unresolved_external_proof_request_specs"]["avalonia:win-x64:windows"]
    assert deduped_spec["tuple_entry_count"] == 2
    assert deduped_spec["tuple_unique"] is False
    assert deduped_spec["required_proofs"] == ["promoted_installer_artifact"]
    assert deduped_spec["local_evidence"]["startup_smoke_receipt"]["state"] == "missing"
    packet = payload["packets"][0]
    assert packet["packet_kind"] == "external_proof_request"
    assert packet["install_diagnosis"]["external_proof_request"]["tuple_entry_count"] == 2
    assert packet["install_diagnosis"]["external_proof_request"]["tuple_unique"] is False
    execution_plan_request = payload["unresolved_external_proof_execution_plan"]["host_groups"]["windows"]["requests"][0]
    assert execution_plan_request["tuple_entry_count"] == 2
    assert execution_plan_request["tuple_unique"] is False


def test_materialize_support_case_packets_normalizes_external_proof_required_proofs_tokens(tmp_path: Path) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(json.dumps({"items": []}, indent=2) + "\n", encoding="utf-8")
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "desktopTupleCoverage": {
                    "externalProofRequests": [
                        {
                            "tupleId": "avalonia:win-x64:windows",
                            "head": "avalonia",
                            "platform": "windows",
                            "rid": "win-x64",
                            "requiredHost": "windows",
                            "requiredProofs": [
                                "STARTUP_SMOKE_RECEIPT",
                                "promoted_installer_artifact",
                                "startup_smoke_receipt",
                            ],
                        },
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source",
            str(source),
            "--release-channel",
            str(release_channel),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    normalized_spec = payload["summary"]["unresolved_external_proof_request_specs"]["avalonia:win-x64:windows"]
    assert normalized_spec["required_proofs"] == ["promoted_installer_artifact", "startup_smoke_receipt"]
    assert normalized_spec["local_evidence"]["installer_artifact"]["state"] == "missing"


def test_materialize_support_case_packets_marks_update_required_when_fixed_version_differs_from_installed_version(tmp_path: Path) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(
        json.dumps(
            {
                "installReceipts": [
                    {
                        "receiptId": "install-receipt-update-1",
                        "installationId": "install-update-1",
                        "version": "1.2.2",
                        "channel": "preview",
                    }
                ],
                "fixedReleaseReceipts": [
                    {
                        "caseId": "support_case_update_required",
                        "installationId": "install-update-1",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                        "fixedVersionReceiptId": "fix-version-receipt-update-1",
                        "fixedChannelReceiptId": "fix-channel-receipt-update-1",
                    }
                ],
                "items": [
                    {
                        "caseId": "support_case_update_required",
                        "clusterKey": "support:update-required",
                        "kind": "bug_report",
                        "status": "fixed",
                        "title": "Fix published but user still on old build",
                        "summary": "User install version is behind the fixed version.",
                        "candidateOwnerRepo": "chummer6-ui",
                        "designImpactSuspected": False,
                        "installationId": "install-update-1",
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "linux",
                        "arch": "x64",
                        "installedVersion": "1.2.2",
                        "installedBuildReceiptId": "install-receipt-update-1",
                        "installedBuildReceiptInstallationId": "install-update-1",
                        "installedBuildReceiptVersion": "1.2.2",
                        "installedBuildReceiptChannel": "preview",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                    }
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "rolloutState": "published",
                "supportabilityState": "supported",
                "desktopTupleCoverage": {
                    "promotedInstallerTuples": [
                        {
                            "tupleId": "avalonia:linux:linux-x64",
                            "head": "avalonia",
                            "platform": "linux",
                            "rid": "linux-x64",
                            "artifactId": "avalonia-linux-x64-installer",
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source",
            str(source),
            "--release-channel",
            str(release_channel),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["open_case_count"] == 1
    assert payload["summary"]["update_required_case_count"] == 1
    assert payload["summary"]["update_required_routed_to_downloads_count"] == 1
    assert payload["summary"]["update_required_misrouted_case_count"] == 0
    assert payload["summary"]["reporter_followthrough_ready_count"] == 1
    assert payload["summary"]["feedback_followthrough_ready_count"] == 1
    assert payload["summary"]["fix_available_ready_count"] == 1
    assert payload["summary"]["please_test_ready_count"] == 0
    assert payload["summary"]["recovery_loop_ready_count"] == 1
    packet = payload["packets"][0]
    assert packet["install_diagnosis"]["case_installed_version"] == "1.2.2"
    assert packet["install_diagnosis"]["registry_release_channel_status"] == "published"
    assert packet["install_diagnosis"]["registry_release_proof_status"] == "passed"
    assert packet["install_diagnosis"]["case_version_matches_registry_release"] is False
    assert packet["install_diagnosis"]["case_fixed_version_matches_registry_release"] is True
    assert packet["fix_confirmation"]["update_required"] is True
    assert packet["reporter_followthrough"]["state"] == "fix_available_update_required"
    assert packet["reporter_followthrough"]["next_action"] == "send_fix_available_with_update"
    assert packet["reporter_followthrough"]["feedback_loop_ready"] is True
    assert packet["reporter_followthrough"]["fixed_version_receipted"] is True
    assert packet["reporter_followthrough"]["installed_build_receipted"] is True
    assert packet["reporter_followthrough"]["current_install_on_fixed_build"] is False
    assert packet["reporter_followthrough"]["blockers"] == ["installed_build_behind_fixed_receipt"]
    assert packet["recovery_path"]["action_id"] == "open_downloads"
    assert packet["recovery_path"]["href"] == "/downloads"
    plan = payload["reporter_followthrough_plan"]
    assert plan["ready_count"] == 1
    assert plan["feedback_ready_count"] == 1
    assert len(plan["action_groups"]["feedback"]) == 1
    assert len(plan["action_groups"]["fix_available"]) == 1
    assert len(plan["action_groups"]["recovery"]) == 1
    fix_row = plan["action_groups"]["fix_available"][0]
    assert fix_row["next_action"] == "send_fix_available_with_update"
    assert fix_row["install_receipt_ready"] is True
    assert fix_row["release_receipt_version"] == "1.2.3"
    assert fix_row["release_receipt_channel"] == "preview"
    assert fix_row["installed_build_receipted"] is True
    assert fix_row["fixed_version_receipted"] is True
    assert fix_row["fixed_channel_receipted"] is True
    assert fix_row["update_required"] is True
    assert fix_row["current_install_on_fixed_build"] is False
    assert plan["action_groups"]["recovery"][0]["packet_id"] == packet["packet_id"]
    assert plan["action_groups"]["recovery"][0]["recovery_loop_ready"] is True
    assert plan["action_groups"]["recovery"][0]["next_action"] == "send_recovery"


def _run_direct_tests() -> int:
    failures: list[str] = []
    test_functions = [
        (name, value)
        for name, value in sorted(globals().items())
        if name.startswith("test_") and callable(value)
    ]
    for name, test_function in test_functions:
        signature = inspect.signature(test_function)
        monkeypatch = _DirectMonkeyPatch()
        try:
            kwargs = {}
            if "tmp_path" in signature.parameters:
                with tempfile.TemporaryDirectory(prefix=f"{name}-") as tmp_dir:
                    kwargs["tmp_path"] = Path(tmp_dir)
                    if "monkeypatch" in signature.parameters:
                        kwargs["monkeypatch"] = monkeypatch
                    test_function(**kwargs)
            else:
                if "monkeypatch" in signature.parameters:
                    kwargs["monkeypatch"] = monkeypatch
                test_function(**kwargs)
        except Exception as exc:  # pragma: no cover - only used by direct test harness.
            failures.append(f"{name}: {exc!r}")
        finally:
            monkeypatch.undo()
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1
    print(f"direct support packet tests passed: {len(test_functions)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run_direct_tests())
