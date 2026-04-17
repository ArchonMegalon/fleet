from __future__ import annotations

import importlib.util
import inspect
import hashlib
import json
import sys
import tempfile
from pathlib import Path


SCRIPT = Path("/docker/fleet/scripts/verify_next90_m102_fleet_reporter_receipts.py")


def _load_module():
    previous_sys_path = list(sys.path)
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        spec = importlib.util.spec_from_file_location("verify_next90_m102_fleet_reporter_receipts", SCRIPT)
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path[:] = previous_sys_path


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _release_receipt_fields() -> dict:
    return {
        "release_receipt_id": "release-channel:preview:1.2.3:passed",
        "release_receipt_source": "release_channel",
        "release_receipt_channel": "preview",
        "release_receipt_version": "1.2.3",
        "head_id": "avalonia",
        "platform": "linux",
        "arch": "x64",
        "installed_build_receipt_head_id": "avalonia",
        "installed_build_receipt_platform": "linux",
        "installed_build_receipt_rid": "linux-x64",
        "installed_build_receipt_tuple_id": "avalonia:linux-x64:linux",
        "installed_build_receipt_identity_matches": True,
    }


def _write_registry(path: Path, *, evidence_tail: str = "") -> None:
    path.write_text(
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
          - /docker/fleet/scripts/materialize_support_case_packets.py compiles reporter followthrough from support packets only after install truth, installation-bound installed-build receipts, fixed-version receipts, fixed-channel receipts, installed-build receipts, and release-channel receipts agree.
          - /docker/fleet/tests/test_materialize_support_case_packets.py covers receipt gating.
          - /docker/fleet/.codex-studio/published/SUPPORT_CASE_PACKETS.generated.json reports successor_package_verification.status=pass.
          - /docker/fleet/.codex-studio/published/WEEKLY_GOVERNOR_PACKET.generated.json projects fix-available, please-test, and recovery counts.
          - /docker/fleet/scripts/verify_next90_m102_fleet_reporter_receipts.py fail-closes weekly/support generated_at freshness drift so WEEKLY_GOVERNOR_PACKET.generated.json cannot predate the SUPPORT_CASE_PACKETS.generated.json receipt gates it summarizes.
          - /docker/fleet/scripts/verify_next90_m102_fleet_reporter_receipts.py fail-closes weekly support-packet source sha256 drift so WEEKLY_GOVERNOR_PACKET.generated.json must name the exact SUPPORT_CASE_PACKETS.generated.json bytes it summarizes.
          - /docker/fleet/scripts/verify_next90_m102_fleet_reporter_receipts.py fail-closes future-dated generated_at receipts so support and weekly proof cannot outrun wall-clock truth.
          - /docker/fleet/scripts/verify_script_bootstrap_no_pythonpath.py includes the standalone M102 verifier in no-PYTHONPATH bootstrap proof.
          - python3 scripts/verify_next90_m102_fleet_reporter_receipts.py exits 0.
          - /docker/fleet/scripts/materialize_support_case_packets.py now fail-closes duplicate next90-m102-fleet-reporter-receipts queue rows, duplicate design-queue rows, and duplicate registry work-task rows so stale closure proof cannot hide behind the first matching row.
          - /docker/fleet/scripts/materialize_support_case_packets.py now requires generated successor scope-drift, closure-field drift, and missing Fleet proof-anchor markers in both the Fleet queue mirror and design-owned queue source so future shards verify the closed proof floor instead of repeating it.
          - /docker/fleet/scripts/verify_next90_m102_fleet_reporter_receipts.py now fail-closes runtime handoff metadata proof markers so copied worker-run metadata cannot close the package.
{evidence_tail}
""".lstrip(),
        encoding="utf-8",
    )


def _write_queue(path: Path, design_queue: Path, *, proof_tail: str = "") -> None:
    path.write_text(
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
      - generated support successor scope drift fails the standalone verifier
      - generated support successor closure-field drift fails the standalone verifier
      - weekly/support receipt-count drift fails the standalone verifier
      - weekly/support generated_at freshness fails the standalone verifier
      - future-dated support and weekly generated_at receipts fail the standalone verifier
      - weekly support-packet source-path drift fails the standalone verifier
      - design queue source path rejects active-run helper paths
      - weekly governor source-path hygiene and worker command guard fail the standalone verifier
      - design-owned queue source proof markers fail the standalone verifier
      - successor verifier fail-closes missing Fleet proof anchors and SUPPORT_CASE_PACKETS.generated.json reports missing_registry_proof_anchor_paths=[] and missing_queue_proof_anchor_paths=[]
      - telemetry command proof markers fail the standalone verifier and shared successor authority check
      - runtime handoff frontier metadata proof markers fail the standalone verifier and shared successor authority check
      - distinct queue proof anti-collapse guard prevents broad prose proof lines from satisfying command and negative-proof rows
      - duplicate queue, design-queue, and registry work-task rows for next90-m102-fleet-reporter-receipts fail the shared successor authority check
      - design-owned queue source row matches the Fleet completed queue proof assignment
{proof_tail}
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
      - generated support successor scope drift fails the standalone verifier
      - generated support successor closure-field drift fails the standalone verifier
      - weekly/support receipt-count drift fails the standalone verifier
      - weekly/support generated_at freshness fails the standalone verifier
      - future-dated support and weekly generated_at receipts fail the standalone verifier
      - weekly support-packet source-path drift fails the standalone verifier
      - design queue source path rejects active-run helper paths
      - weekly governor source-path hygiene and worker command guard fail the standalone verifier
      - design-owned queue source proof markers fail the standalone verifier
      - successor verifier fail-closes missing Fleet proof anchors and SUPPORT_CASE_PACKETS.generated.json reports missing_registry_proof_anchor_paths=[] and missing_queue_proof_anchor_paths=[]
      - telemetry command proof markers fail the standalone verifier and shared successor authority check
      - runtime handoff frontier metadata proof markers fail the standalone verifier and shared successor authority check
      - distinct queue proof anti-collapse guard prevents broad prose proof lines from satisfying command and negative-proof rows
      - duplicate queue, design-queue, and registry work-task rows for next90-m102-fleet-reporter-receipts fail the shared successor authority check
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


def _support_packets_payload() -> dict:
    return {
        "contract_name": "fleet.support_case_packets",
        "generated_at": "2026-04-15T14:11:15Z",
        "source": {
            "install_receipt_feed_state": "provided",
            "install_receipt_source_count": 0,
            "install_receipt_indexed_count": 0,
            "install_receipt_hydrated_case_count": 0,
            "install_receipt_missing_case_count": 0,
            "fix_receipt_feed_state": "provided",
            "fix_receipt_source_count": 0,
            "fix_receipt_indexed_count": 0,
            "fix_receipt_hydrated_case_count": 0,
            "fix_receipt_missing_case_count": 0,
        },
        "summary": {
            "reporter_followthrough_ready_count": 0,
            "feedback_followthrough_ready_count": 0,
            "fix_available_ready_count": 0,
            "please_test_ready_count": 0,
            "recovery_loop_ready_count": 0,
            "reporter_followthrough_blocked_missing_install_receipts_count": 0,
            "reporter_followthrough_blocked_receipt_mismatch_count": 0,
        },
        "followthrough_receipt_gates": {
            "package_id": "next90-m102-fleet-reporter-receipts",
            "milestone_id": 102,
            "generated_at": "2026-04-15T14:11:15Z",
            "source_rule": (
                "Feedback, fix-available, please-test, and recovery followthrough may leave hold only when install truth, "
                "installation-bound installed-build receipts, and release-channel receipts agree; fix-bearing loops additionally require "
                "fixed-version receipts and fixed-channel receipts."
            ),
            "required_gates": [
                "feedback_loop_ready",
                "install_truth_ready",
                "release_receipt_ready",
                "release_receipt_id_present",
                "fixed_version_receipted",
                "fixed_channel_receipted",
                "fixed_receipt_installation_bound",
                "installed_build_receipt_id_present",
                "installed_build_receipt_installation_bound",
                "installed_build_receipt_version_matches",
                "installed_build_receipt_channel_matches",
                "installed_build_receipt_tuple_bound",
            ],
            "gate_counts": {
                "install_receipt_ready": 0,
                "install_truth_ready": 0,
                "feedback_loop_ready": 0,
                "release_receipt_ready": 0,
                "release_receipt_id_present": 0,
                "fixed_version_receipted": 0,
                "fixed_channel_receipted": 0,
                "fixed_receipt_installation_bound": 0,
                "installed_build_receipted": 0,
                "installed_build_receipt_id_present": 0,
                "installed_build_receipt_installation_bound": 0,
                "installed_build_receipt_version_matches": 0,
                "installed_build_receipt_channel_matches": 0,
                "installed_build_receipt_tuple_bound": 0,
                "current_install_on_fixed_build": 0,
            },
        },
        "reporter_followthrough_plan": {
            "package_id": "next90-m102-fleet-reporter-receipts",
            "generated_at": "2026-04-15T14:11:15Z",
            "source_rule": (
                "Reporter feedback, fix-available, please-test, and recovery followthrough is compiled from support packets only after install truth, "
                "installation-bound installed-build receipts, and release-channel receipts agree; fix-bearing loops additionally require "
                "fixed-version receipts and fixed-channel receipts."
            ),
            "ready_count": 0,
            "feedback_ready_count": 0,
            "fix_available_ready_count": 0,
            "please_test_ready_count": 0,
            "recovery_loop_ready_count": 0,
            "blocked_missing_install_receipts_count": 0,
            "blocked_receipt_mismatch_count": 0,
            "hold_until_fix_receipt_count": 0,
            "action_groups": {
                "feedback": [],
                "fix_available": [],
                "please_test": [],
                "recovery": [],
                "blocked_missing_install_receipts": [],
                "blocked_receipt_mismatch": [],
                "hold_until_fix_receipt": [],
            },
        },
        "successor_package_verification": {
            "status": "pass",
            "package_id": "next90-m102-fleet-reporter-receipts",
            "frontier_id": "2454416974",
            "milestone_id": 102,
            "repo": "fleet",
            "registry_path": "/docker/chummercomplete/chummer-design/products/chummer/NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml",
            "queue_staging_path": "/docker/fleet/.codex-studio/published/NEXT_90_DAY_QUEUE_STAGING.generated.yaml",
            "allowed_paths": ["scripts", "tests", ".codex-studio", "feedback"],
            "owned_surfaces": ["feedback_loop_ready:install_receipts", "product_governor:followthrough"],
            "registry_wave": "W6",
            "registry_status": "in_progress",
            "registry_title": "Desktop-native claim, update, rollback, and support followthrough",
            "registry_dependencies": [101],
            "registry_work_task_id": "102.4",
            "registry_work_task_count": 1,
            "registry_work_task_title": "Gate the staged reporter mail loop against real install and fix receipts, not only queued support state.",
            "registry_work_task_status": "complete",
            "queue_title": "Gate fix followthrough against real install and receipt truth",
            "queue_task": "Compile feedback, fix-available, please-test, and recovery loops from install-aware release receipts instead of queued support state alone.",
            "queue_wave": "W6",
            "queue_repo": "fleet",
            "queue_milestone_id": 102,
            "queue_status": "complete",
            "queue_frontier_id": "2454416974",
            "queue_item_count": 1,
            "design_queue_source_path": "",
            "design_queue_source_item_count": 1,
            "design_queue_source_item_found": True,
            "design_queue_source_title": "Gate fix followthrough against real install and receipt truth",
            "design_queue_source_task": "Compile feedback, fix-available, please-test, and recovery loops from install-aware release receipts instead of queued support state alone.",
            "design_queue_source_wave": "W6",
            "design_queue_source_repo": "fleet",
            "design_queue_source_milestone_id": 102,
            "design_queue_source_status": "complete",
            "design_queue_source_frontier_id": "2454416974",
            "missing_registry_evidence_markers": [],
            "missing_queue_proof_markers": [],
            "missing_design_queue_source_proof_markers": [],
            "missing_registry_proof_anchor_paths": [],
            "missing_queue_proof_anchor_paths": [],
            "missing_design_queue_source_proof_anchor_paths": [],
            "disallowed_registry_evidence_entries": [],
            "disallowed_queue_proof_entries": [],
            "disallowed_design_queue_source_proof_entries": [],
            "issues": [],
            "required_registry_evidence_markers": [
                "scripts/materialize_support_case_packets.py",
                "tests/test_materialize_support_case_packets.py",
                "SUPPORT_CASE_PACKETS.generated.json",
                "WEEKLY_GOVERNOR_PACKET.generated.json",
                "install truth",
                "installation-bound installed-build receipts",
                "installed-build receipts",
                "fixed-version receipts",
                "fixed-channel receipts",
                "release-channel receipts",
                "weekly/support generated_at freshness",
                "future-dated generated_at receipts",
                "verify_script_bootstrap_no_pythonpath.py",
                "python3 scripts/verify_next90_m102_fleet_reporter_receipts.py exits 0",
                "duplicate next90-m102-fleet-reporter-receipts queue rows",
                "generated successor scope-drift",
                "missing Fleet proof-anchor markers",
                "runtime handoff metadata proof markers",
            ],
            "required_queue_proof_markers": [
                "/docker/fleet/scripts/materialize_support_case_packets.py",
                "/docker/fleet/scripts/verify_next90_m102_fleet_reporter_receipts.py",
                "/docker/fleet/tests/test_materialize_support_case_packets.py",
                "/docker/fleet/tests/test_verify_next90_m102_fleet_reporter_receipts.py",
                "/docker/fleet/scripts/verify_script_bootstrap_no_pythonpath.py",
                "/docker/fleet/tests/test_fleet_script_bootstrap_without_pythonpath.py",
                "/docker/fleet/.codex-studio/published/SUPPORT_CASE_PACKETS.generated.json",
                "/docker/fleet/.codex-studio/published/WEEKLY_GOVERNOR_PACKET.generated.json",
                "/docker/fleet/.codex-studio/published/WEEKLY_GOVERNOR_PACKET.generated.md",
                "/docker/fleet/feedback/2026-04-15-next90-m102-fleet-reporter-receipts-closeout.md",
                "python3 -m py_compile",
                "python3 scripts/verify_next90_m102_fleet_reporter_receipts.py exits 0",
                "python3 tests/test_verify_next90_m102_fleet_reporter_receipts.py exits 0",
                "installation-bound receipt gating",
                "fixed-version receipts",
                "fixed-channel receipts",
                "receipt-gated support followthrough tests",
                "successor frontier 2454416974",
                "design-owned queue source",
                "generated support-packet proof hygiene",
                "stale generated support proof gaps",
                "generated support successor scope drift",
                "generated support successor closure-field drift",
                "weekly/support receipt-count drift",
                "weekly/support generated_at freshness",
                "future-dated support and weekly generated_at receipts fail the standalone verifier",
                "weekly support-packet source-path drift",
                "design queue source path rejects active-run helper paths",
                "weekly governor source-path hygiene and worker command guard",
                "design-owned queue source proof markers",
                "successor verifier fail-closes missing Fleet proof anchors",
                "telemetry command proof markers fail the standalone verifier and shared successor authority check",
                "runtime handoff frontier metadata proof markers fail the standalone verifier and shared successor authority check",
                "distinct queue proof anti-collapse guard",
                "duplicate queue, design-queue, and registry work-task rows for next90-m102-fleet-reporter-receipts fail the shared successor authority check",
            ],
        },
    }


def _weekly_payload() -> dict:
    return {
        "generated_at": "2026-04-15T14:13:33Z",
        "source_input_health": {
            "required_inputs": {
                "support_packets": {
                    "successor_package_verification_status": "pass",
                    "source_path": "",
                },
                "source_path_hygiene": {
                    "state": "pass",
                    "disallowed_source_paths": [],
                    "blocked_markers": [
                        "/var/lib/codex-fleet",
                        "ACTIVE_RUN_HANDOFF.generated.md",
                        "TASK_LOCAL_TELEMETRY.generated.json",
                        "frontier ids:",
                        "open milestone ids:",
                        "successor frontier detail:",
                        "mode: successor_wave",
                        "active run",
                        "run id:",
                        "prompt path",
                        "recent stderr tail",
                        "status: complete; owners:",
                        "operator telemetry",
                        "active-run telemetry",
                        "active-run helper",
                        "active run helper",
                        "run_ooda_design_supervisor_until_quiet",
                        "ooda_design_supervisor.py",
                        "chummer_design_supervisor.py",
                        "chummer_design_supervisor.py status",
                        "chummer_design_supervisor.py eta",
                        "codexea --telemetry",
                        "--telemetry-answer",
                    ],
                },
            }
        },
        "repeat_prevention": {
            "worker_command_guard": {
                "status": "active_run_helpers_forbidden",
                "blocked_markers": [
                    "/var/lib/codex-fleet",
                    "ACTIVE_RUN_HANDOFF.generated.md",
                    "TASK_LOCAL_TELEMETRY.generated.json",
                    "frontier ids:",
                    "open milestone ids:",
                    "successor frontier detail:",
                    "mode: successor_wave",
                    "active run",
                    "run id:",
                    "prompt path",
                    "recent stderr tail",
                    "status: complete; owners:",
                    "operator telemetry",
                    "active-run telemetry",
                    "active-run helper",
                    "active run helper",
                    "run_ooda_design_supervisor_until_quiet",
                    "ooda_design_supervisor.py",
                    "chummer_design_supervisor.py",
                    "chummer_design_supervisor.py status",
                    "chummer_design_supervisor.py eta",
                    "codexea --telemetry",
                    "--telemetry-answer",
                ],
                "rule": (
                    "Worker proof must come from repo-local files, generated packets, and tests, "
                    "not operator telemetry or active-run helper commands."
                ),
            }
        },
        "truth_inputs": {
            "support_summary": {
                "reporter_followthrough_ready_count": 0,
                "followthrough_receipt_gates_ready_count": 0,
                "followthrough_receipt_gates_blocked_missing_install_receipts_count": 0,
                "followthrough_receipt_gates_blocked_receipt_mismatch_count": 0,
                "followthrough_receipt_gates_installation_bound_count": 0,
                "followthrough_receipt_gates_installed_build_receipted_count": 0,
                "feedback_followthrough_ready_count": 0,
                "fix_available_ready_count": 0,
                "please_test_ready_count": 0,
                "recovery_loop_ready_count": 0,
                "reporter_followthrough_blocked_missing_install_receipts_count": 0,
                "reporter_followthrough_blocked_receipt_mismatch_count": 0,
                "reporter_followthrough_plan_ready_count": 0,
                "reporter_followthrough_plan_blocked_missing_install_receipts_count": 0,
                "reporter_followthrough_plan_blocked_receipt_mismatch_count": 0,
            }
        },
    }


def _weekly_markdown() -> str:
    return """
# Weekly Governor Packet

Generated: 2026-04-15T14:13:33Z

## Measured Truth

- Reporter followthrough ready: 0
- Feedback followthrough ready: 0
- Fix-available ready: 0
- Please-test ready: 0
- Recovery-loop ready: 0
- Followthrough blocked on install receipts: 0
- Followthrough receipt mismatches: 0
- Receipt-gated followthrough ready: 0
- Receipt-gated installed-build receipts: 0
""".lstrip()


def _align_successor_verification_paths(
    payload: dict,
    *,
    registry: Path,
    queue: Path,
    design_queue: Path,
) -> None:
    verification = payload["successor_package_verification"]
    verification["registry_path"] = str(registry)
    verification["queue_staging_path"] = str(queue)
    verification["design_queue_source_path"] = str(design_queue)


def _align_weekly_support_path(payload: dict, *, support: Path) -> None:
    support_input = payload["source_input_health"]["required_inputs"]["support_packets"]
    support_input["source_path"] = str(support)
    if support.is_file():
        support_input["source_sha256"] = hashlib.sha256(support.read_bytes()).hexdigest()


def _fixture_paths(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path, Path]:
    support = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    weekly = tmp_path / "WEEKLY_GOVERNOR_PACKET.generated.json"
    weekly_markdown = tmp_path / "WEEKLY_GOVERNOR_PACKET.generated.md"
    registry = tmp_path / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
    queue = tmp_path / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    design_queue = tmp_path / "DESIGN_NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    weekly_payload = _weekly_payload()
    _align_weekly_support_path(weekly_payload, support=support)
    _write_json(weekly, weekly_payload)
    weekly_markdown.write_text(_weekly_markdown(), encoding="utf-8")
    _write_registry(registry)
    _write_queue(queue, design_queue)
    support_payload = _support_packets_payload()
    _align_successor_verification_paths(
        support_payload,
        registry=registry,
        queue=queue,
        design_queue=design_queue,
    )
    _write_json(support, support_payload)
    _align_weekly_support_path(weekly_payload, support=support)
    _write_json(weekly, weekly_payload)
    return support, weekly, weekly_markdown, registry, queue, design_queue


def test_verify_next90_m102_fleet_reporter_receipts_passes_closed_package(tmp_path: Path) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, _ = _fixture_paths(tmp_path)

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "pass"
    assert result["issues"] == []


def test_verify_next90_m102_fleet_reporter_receipts_rejects_ready_rows_from_cached_packet_fallback(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, _ = _fixture_paths(tmp_path)
    payload = _support_packets_payload()
    payload["source"].update(
        {
            "refresh_mode": "cached_packets_fallback",
            "install_receipt_feed_state": "provided",
            "install_receipt_source_count": 1,
            "install_receipt_indexed_count": 1,
            "install_receipt_hydrated_case_count": 1,
        }
    )
    payload["reporter_followthrough_plan"]["ready_count"] = 1
    payload["reporter_followthrough_plan"]["feedback_ready_count"] = 1
    payload["reporter_followthrough_plan"]["action_groups"]["feedback"].append(
        {
            "packet_id": "support_packet_cached_fallback_ready",
            "state": "no_fix_recorded",
            "next_action": "send_feedback_progress",
            "feedback_loop_ready": True,
            "install_receipt_ready": True,
            "install_truth_state": "promoted_tuple_match",
            "release_receipt_state": "release_receipt_ready",
            **_release_receipt_fields(),
            "installation_id": "install-cached-fallback",
            "release_channel": "preview",
            "installed_version": "1.2.3",
            "installed_build_receipt_id": "install-receipt-cached-fallback",
            "installed_build_receipt_installation_id": "install-cached-fallback",
            "installed_build_receipt_version": "1.2.3",
            "installed_build_receipt_channel": "preview",
            "installed_build_receipt_source": "install_receipts",
            "installed_build_receipt_installation_source": "install_receipts",
            "installed_build_receipt_version_source": "install_receipts",
            "installed_build_receipt_channel_source": "install_receipts",
            "installed_build_receipted": True,
        }
    )
    payload["followthrough_receipt_gates"]["ready_count"] = 1
    payload["followthrough_receipt_gates"]["gate_counts"]["feedback_loop_ready"] = 1
    payload["followthrough_receipt_gates"]["gate_counts"]["install_receipt_ready"] = 1
    payload["followthrough_receipt_gates"]["gate_counts"]["install_truth_ready"] = 1
    payload["followthrough_receipt_gates"]["gate_counts"]["release_receipt_ready"] = 1
    payload["followthrough_receipt_gates"]["gate_counts"]["release_receipt_id_present"] = 1
    payload["followthrough_receipt_gates"]["gate_counts"]["installed_build_receipted"] = 1
    payload["followthrough_receipt_gates"]["gate_counts"]["installed_build_receipt_installation_bound"] = 1
    payload["followthrough_receipt_gates"]["gate_counts"]["installed_build_receipt_version_matches"] = 1
    payload["followthrough_receipt_gates"]["gate_counts"]["installed_build_receipt_channel_matches"] = 1
    payload["summary"]["reporter_followthrough_ready_count"] = 1
    payload["summary"]["feedback_followthrough_ready_count"] = 1
    _write_json(support, payload)

    weekly_payload = _weekly_payload()
    weekly_payload["truth_inputs"]["support_summary"]["reporter_followthrough_ready_count"] = 1
    weekly_payload["truth_inputs"]["support_summary"]["feedback_followthrough_ready_count"] = 1
    weekly_payload["truth_inputs"]["support_summary"]["reporter_followthrough_plan_ready_count"] = 1
    weekly_payload["truth_inputs"]["support_summary"]["followthrough_receipt_gates_ready_count"] = 1
    weekly_payload["truth_inputs"]["support_summary"]["followthrough_receipt_gates_installed_build_receipted_count"] = 1
    weekly_payload["truth_inputs"]["support_summary"]["followthrough_receipt_gates_installation_bound_count"] = 1
    _align_weekly_support_path(weekly_payload, support=support)
    _write_json(weekly, weekly_payload)
    weekly_markdown.write_text(
        _weekly_markdown()
        .replace("- Reporter followthrough ready: 0", "- Reporter followthrough ready: 1")
        .replace("- Feedback followthrough ready: 0", "- Feedback followthrough ready: 1")
        .replace("- Receipt-gated followthrough ready: 0", "- Receipt-gated followthrough ready: 1")
        .replace("- Receipt-gated installed-build receipts: 0", "- Receipt-gated installed-build receipts: 1"),
        encoding="utf-8",
    )

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert "support packet source receipt-feed metadata does not back ready followthrough" in result["issues"]
    assert result["receipt_feed_source_issues"] == [
        "ready reporter followthrough exists from cached packet fallback instead of refreshed receipt truth"
    ]


def test_verify_next90_m102_fleet_reporter_receipts_fails_missing_gate_names(tmp_path: Path) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, _ = _fixture_paths(tmp_path)
    payload = _support_packets_payload()
    payload["followthrough_receipt_gates"]["required_gates"].remove("fixed_channel_receipted")
    _write_json(support, payload)

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert "followthrough receipt gates are missing required gate names" in result["issues"]
    assert result["missing_gate_names"] == ["fixed_channel_receipted"]


def test_verify_next90_m102_fleet_reporter_receipts_fails_stale_plan_ready_count_without_rows(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, _ = _fixture_paths(tmp_path)
    support_payload = _support_packets_payload()
    support_payload["reporter_followthrough_plan"]["ready_count"] = 1
    support_payload["summary"]["reporter_followthrough_ready_count"] = 1
    _write_json(support, support_payload)

    weekly_payload = _weekly_payload()
    weekly_payload["truth_inputs"]["support_summary"]["reporter_followthrough_ready_count"] = 1
    weekly_payload["truth_inputs"]["support_summary"]["reporter_followthrough_plan_ready_count"] = 1
    _align_weekly_support_path(weekly_payload, support=support)
    _write_json(weekly, weekly_payload)
    weekly_markdown.write_text(
        _weekly_markdown().replace("- Reporter followthrough ready: 0", "- Reporter followthrough ready: 1"),
        encoding="utf-8",
    )

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert "reporter followthrough plan counts disagree with receipt-backed action groups" in result["issues"]
    assert "SUPPORT_CASE_PACKETS.generated.json summary disagrees with receipt-backed followthrough plan" in result["issues"]
    assert "weekly governor support summary disagrees with support-packet receipt gates" in result["issues"]
    assert "weekly governor markdown disagrees with support-packet receipt gates" in result["issues"]
    assert result["plan_count_mismatches"] == {
        "ready_count": {
            "receipt_backed_action_groups": 0,
            "reporter_followthrough_plan": 1,
        }
    }
    assert result["support_summary_count_mismatches"]["reporter_followthrough_ready_count"] == {
        "receipt_backed_plan": 0,
        "support_packet_summary": 1,
    }
    assert result["weekly_count_mismatches"]["reporter_followthrough_ready_count"] == {
        "support_packets": 0,
        "weekly_governor_packet": 1,
    }
    assert result["weekly_markdown_count_mismatches"]["Reporter followthrough ready"] == {
        "support_packets": 0,
        "weekly_governor_markdown": 1,
    }


def test_verify_next90_m102_fleet_reporter_receipts_fails_action_group_rows_without_receipts(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, _ = _fixture_paths(tmp_path)
    payload = _support_packets_payload()
    payload["reporter_followthrough_plan"]["action_groups"]["fix_available"].append(
        {
            "packet_id": "support_packet_stale_fix_row",
            "state": "fix_available_ready",
            "next_action": "send_fix_available",
            "feedback_loop_ready": True,
            "install_receipt_ready": True,
            "install_truth_state": "promoted_tuple_match",
            "release_receipt_state": "release_receipt_ready",
            "installation_id": "install-stale-1",
            "installed_build_receipt_id": "",
            "installed_build_receipt_installation_id": "",
            "installed_build_receipt_version": "",
            "installed_build_receipt_channel": "",
            "installed_build_receipted": False,
            "fixed_version": "1.2.3",
            "fixed_channel": "preview",
            "fixed_version_receipted": True,
            "fixed_channel_receipted": True,
            "fixed_version_receipt_id": "fix-version-receipt-stale-1",
            "fixed_channel_receipt_id": "fix-channel-receipt-stale-1",
            "fixed_version_receipt_source": "fix_receipts",
            "fixed_channel_receipt_source": "fix_receipts",
        }
    )
    _write_json(support, payload)

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert "reporter followthrough action groups contain rows without receipt gates" in result["issues"]
    assert result["action_group_receipt_issues"] == [
        "fix_available row support_packet_stale_fix_row is missing install-aware receipt gates: "
        "installed_build_receipt_channel, installed_build_receipt_channel_source, "
        "installed_build_receipt_channel_source=install_receipts, installed_build_receipt_id, "
        "installed_build_receipt_installation_id, installed_build_receipt_installation_source, "
        "installed_build_receipt_installation_source=install_receipts, "
        "installed_build_receipt_source, installed_build_receipt_source=install_receipts, "
        "installed_build_receipt_version, installed_build_receipt_version_source, "
        "installed_build_receipt_version_source=install_receipts, "
        "installed_build_receipted, release_receipt_channel, release_receipt_id, "
        "release_receipt_source=release_channel, release_receipt_version",
        "fix_available row support_packet_stale_fix_row is missing fix receipt gates: "
        "fixed_receipt_installation_bound, fixed_receipt_installation_id, "
        "fixed_receipt_installation_source, fixed_receipt_installation_source=fix_receipts"
    ]


def test_verify_next90_m102_fleet_reporter_receipts_fails_ready_row_without_promoted_install_truth(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, _ = _fixture_paths(tmp_path)
    payload = _support_packets_payload()
    payload["reporter_followthrough_plan"]["action_groups"]["feedback"].append(
        {
            "packet_id": "support_packet_install_truth_drift",
            "kind": "feedback",
            "status": "released_to_reporter_channel",
            "state": "no_fix_recorded",
            "next_action": "send_feedback_progress",
            "feedback_loop_ready": True,
            "install_receipt_ready": True,
            "install_truth_state": "queued_support_state_only",
            "release_receipt_state": "release_receipt_ready",
            **_release_receipt_fields(),
            "installation_id": "install-truth-drift-1",
            "release_channel": "preview",
            "installed_version": "1.2.3",
            "installed_build_receipt_id": "install-receipt-truth-drift-1",
            "installed_build_receipt_installation_id": "install-truth-drift-1",
            "installed_build_receipt_version": "1.2.3",
            "installed_build_receipt_channel": "preview",
            "installed_build_receipt_source": "install_receipts",
            "installed_build_receipt_installation_source": "install_receipts",
            "installed_build_receipt_version_source": "install_receipts",
            "installed_build_receipt_channel_source": "install_receipts",
            "installed_build_receipted": True,
        }
    )
    _write_json(support, payload)

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert "reporter followthrough action groups contain rows without receipt gates" in result["issues"]
    assert result["action_group_receipt_issues"] == [
        "feedback row support_packet_install_truth_drift is missing install-aware receipt gates: "
        "install_truth_state=promoted_tuple_match"
    ]


def test_verify_next90_m102_fleet_reporter_receipts_fails_recovery_row_with_fix_available_action(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, _ = _fixture_paths(tmp_path)
    payload = _support_packets_payload()
    payload["reporter_followthrough_plan"]["action_groups"]["recovery"].append(
        {
            "packet_id": "support_packet_recovery_action_drift",
            "state": "fix_available_update_required",
            "next_action": "send_fix_available_with_update",
            "feedback_loop_ready": True,
            "install_receipt_ready": True,
            "install_truth_state": "promoted_tuple_match",
            "release_receipt_state": "release_receipt_ready",
            **_release_receipt_fields(),
            "installation_id": "install-recovery-action-1",
            "release_channel": "preview",
            "installed_version": "1.2.2",
            "installed_build_receipt_id": "install-receipt-recovery-action-1",
            "installed_build_receipt_installation_id": "install-recovery-action-1",
            "installed_build_receipt_version": "1.2.2",
            "installed_build_receipt_channel": "preview",
            "installed_build_receipt_source": "install_receipts",
            "installed_build_receipt_installation_source": "install_receipts",
            "installed_build_receipt_version_source": "install_receipts",
            "installed_build_receipt_channel_source": "install_receipts",
            "installed_build_receipted": True,
            "fixed_version": "1.2.3",
            "fixed_channel": "preview",
            "fixed_version_receipted": True,
            "fixed_channel_receipted": True,
            "fixed_version_receipt_id": "fix-version-receipt-recovery-action-1",
            "fixed_channel_receipt_id": "fix-channel-receipt-recovery-action-1",
            "fixed_receipt_installation_id": "install-recovery-action-1",
            "fixed_receipt_installation_source": "fix_receipts",
            "fixed_receipt_installation_matches": True,
            "fixed_version_receipt_source": "fix_receipts",
            "fixed_channel_receipt_source": "fix_receipts",
            "current_install_on_fixed_build": False,
            "recovery_loop_ready": True,
        }
    )
    _write_json(support, payload)

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert "reporter followthrough action groups contain rows without receipt gates" in result["issues"]
    assert result["action_group_receipt_issues"] == [
        "recovery row support_packet_recovery_action_drift routes to send_fix_available_with_update "
        "instead of receipt-backed send_recovery"
    ]


def test_verify_next90_m102_fleet_reporter_receipts_fails_fix_bearing_feedback_without_fix_receipts(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, _ = _fixture_paths(tmp_path)
    payload = _support_packets_payload()
    payload["reporter_followthrough_plan"]["action_groups"]["feedback"].append(
        {
            "packet_id": "support_packet_feedback_fix_row",
            "state": "released_to_reporter_channel",
            "next_action": "send_feedback_progress",
            "feedback_loop_ready": True,
            "install_receipt_ready": True,
            "install_truth_state": "promoted_tuple_match",
            "release_receipt_state": "release_receipt_ready",
            **_release_receipt_fields(),
            "installation_id": "install-feedback-1",
            "installed_build_receipt_id": "install-receipt-feedback-1",
            "installed_build_receipt_installation_id": "install-feedback-1",
            "installed_build_receipt_version": "1.2.3",
            "installed_build_receipt_channel": "preview",
            "installed_build_receipt_source": "installedBuildReceiptId",
            "installed_build_receipt_installation_source": "installedBuildReceiptInstallationId",
            "installed_build_receipt_version_source": "installedBuildReceiptVersion",
            "installed_build_receipt_channel_source": "installedBuildReceiptChannel",
            "installed_build_receipted": True,
            "fixed_version": "1.2.3",
            "fixed_channel": "preview",
            "fixed_version_receipted": False,
            "fixed_channel_receipted": False,
        }
    )
    _write_json(support, payload)

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert "reporter followthrough action groups contain rows without receipt gates" in result["issues"]
    assert result["action_group_receipt_issues"] == [
        "feedback row support_packet_feedback_fix_row is missing install-aware receipt gates: "
        "installed_build_receipt_channel_source=install_receipts, "
        "installed_build_receipt_installation_source=install_receipts, "
        "installed_build_receipt_source=install_receipts, "
        "installed_build_receipt_version_source=install_receipts",
        "feedback row support_packet_feedback_fix_row is missing fix receipt gates: "
        "fixed_channel_receipt_id, fixed_channel_receipt_source, fixed_channel_receipt_source=fix_receipts, "
        "fixed_channel_receipted, fixed_receipt_installation_bound, fixed_receipt_installation_id, "
        "fixed_receipt_installation_source, fixed_receipt_installation_source=fix_receipts, "
        "fixed_version_receipt_id, fixed_version_receipt_source, fixed_version_receipt_source=fix_receipts, "
        "fixed_version_receipted"
    ]


def test_verify_next90_m102_fleet_reporter_receipts_fails_fix_row_without_fix_receipt_identity(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, _ = _fixture_paths(tmp_path)
    payload = _support_packets_payload()
    payload["reporter_followthrough_plan"]["action_groups"]["fix_available"].append(
        {
            "packet_id": "support_packet_fix_without_receipt_identity",
            "state": "fix_available_ready",
            "next_action": "send_fix_available",
            "feedback_loop_ready": True,
            "install_receipt_ready": True,
            "install_truth_state": "promoted_tuple_match",
            "release_receipt_state": "release_receipt_ready",
            **_release_receipt_fields(),
            "installation_id": "install-fix-identity-1",
            "installed_build_receipt_id": "install-receipt-fix-identity-1",
            "installed_build_receipt_installation_id": "install-fix-identity-1",
            "installed_build_receipt_version": "1.2.3",
            "installed_build_receipt_channel": "preview",
            "installed_build_receipt_source": "install_receipts",
            "installed_build_receipt_installation_source": "install_receipts",
            "installed_build_receipt_version_source": "install_receipts",
            "installed_build_receipt_channel_source": "install_receipts",
            "installed_build_receipted": True,
            "fixed_version": "1.2.3",
            "fixed_channel": "preview",
            "fixed_version_receipted": True,
            "fixed_channel_receipted": True,
        }
    )
    _write_json(support, payload)

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert "reporter followthrough action groups contain rows without receipt gates" in result["issues"]
    assert result["action_group_receipt_issues"] == [
        "fix_available row support_packet_fix_without_receipt_identity is missing fix receipt gates: "
        "fixed_channel_receipt_id, fixed_channel_receipt_source, fixed_channel_receipt_source=fix_receipts, "
        "fixed_receipt_installation_bound, fixed_receipt_installation_id, "
        "fixed_receipt_installation_source, fixed_receipt_installation_source=fix_receipts, "
        "fixed_version_receipt_id, fixed_version_receipt_source, fixed_version_receipt_source=fix_receipts"
    ]


def test_verify_next90_m102_fleet_reporter_receipts_fails_ready_row_receipt_value_mismatch(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, _ = _fixture_paths(tmp_path)
    payload = _support_packets_payload()
    payload["reporter_followthrough_plan"]["action_groups"]["please_test"].append(
        {
            "packet_id": "support_packet_mismatched_receipt_values",
            "state": "please_test_ready",
            "next_action": "send_please_test",
            "feedback_loop_ready": True,
            "install_receipt_ready": True,
            "install_truth_state": "promoted_tuple_match",
            "release_receipt_state": "release_receipt_ready",
            **_release_receipt_fields(),
            "installation_id": "install-value-match-1",
            "installed_version": "1.2.2",
            "installed_build_receipt_id": "install-receipt-value-match-1",
            "installed_build_receipt_installation_id": "install-other-1",
            "installed_build_receipt_version": "1.2.2",
            "installed_build_receipt_channel": "stable",
            "installed_build_receipt_source": "install_receipts",
            "installed_build_receipt_installation_source": "install_receipts",
            "installed_build_receipt_version_source": "install_receipts",
            "installed_build_receipt_channel_source": "install_receipts",
            "installed_build_receipted": True,
            "fixed_version": "1.2.3",
            "fixed_channel": "stable",
            "fixed_version_receipted": True,
            "fixed_channel_receipted": True,
            "fixed_version_receipt_id": "fix-version-receipt-value-match-1",
            "fixed_channel_receipt_id": "fix-channel-receipt-value-match-1",
            "fixed_receipt_installation_id": "install-other-fix-1",
            "fixed_receipt_installation_source": "fix_receipts",
            "fixed_version_receipt_source": "fix_receipts",
            "fixed_channel_receipt_source": "fix_receipts",
            "current_install_on_fixed_build": True,
        }
    )
    _write_json(support, payload)

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert "reporter followthrough action groups contain rows without receipt gates" in result["issues"]
    assert result["action_group_receipt_issues"] == [
        "please_test row support_packet_mismatched_receipt_values has install-aware receipt value mismatches: "
        "installed_build_receipt_channel!=release_receipt_channel, "
        "installed_build_receipt_installation_id!=installation_id",
        "please_test row support_packet_mismatched_receipt_values is missing fix receipt gates: "
        "fixed_receipt_installation_bound",
        "please_test row support_packet_mismatched_receipt_values has fix receipt value mismatches: "
        "fixed_channel!=release_receipt_channel, fixed_receipt_installation_id!=installation_id, "
        "installed_version!=fixed_version",
    ]


def test_verify_next90_m102_fleet_reporter_receipts_fails_ready_row_install_tuple_mismatch(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, _ = _fixture_paths(tmp_path)
    payload = _support_packets_payload()
    payload["reporter_followthrough_plan"]["action_groups"]["fix_available"].append(
        {
            "packet_id": "support_packet_install_tuple_drift",
            "state": "fix_available_ready",
            "next_action": "send_fix_available",
            "feedback_loop_ready": True,
            "install_receipt_ready": True,
            "install_truth_state": "promoted_tuple_match",
            "release_receipt_state": "release_receipt_ready",
            **_release_receipt_fields(),
            "installation_id": "install-tuple-drift-1",
            "release_channel": "preview",
            "head_id": "avalonia",
            "platform": "linux",
            "arch": "x64",
            "installed_version": "1.2.3",
            "installed_build_receipt_id": "install-receipt-tuple-drift-1",
            "installed_build_receipt_installation_id": "install-tuple-drift-1",
            "installed_build_receipt_version": "1.2.3",
            "installed_build_receipt_channel": "preview",
            "installed_build_receipt_head_id": "avalonia",
            "installed_build_receipt_platform": "windows",
            "installed_build_receipt_rid": "win-x64",
            "installed_build_receipt_tuple_id": "avalonia:win-x64:windows",
            "installed_build_receipt_source": "install_receipts",
            "installed_build_receipt_installation_source": "install_receipts",
            "installed_build_receipt_version_source": "install_receipts",
            "installed_build_receipt_channel_source": "install_receipts",
            "installed_build_receipted": True,
            "fixed_version": "1.2.3",
            "fixed_channel": "preview",
            "fixed_version_receipted": True,
            "fixed_channel_receipted": True,
            "fixed_version_receipt_id": "fix-version-receipt-tuple-drift-1",
            "fixed_channel_receipt_id": "fix-channel-receipt-tuple-drift-1",
            "fixed_receipt_installation_id": "install-tuple-drift-1",
            "fixed_receipt_installation_source": "fix_receipts",
            "fixed_receipt_installation_matches": True,
            "fixed_version_receipt_source": "fix_receipts",
            "fixed_channel_receipt_source": "fix_receipts",
        }
    )
    _write_json(support, payload)

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert "reporter followthrough action groups contain rows without receipt gates" in result["issues"]
    assert result["action_group_receipt_issues"] == [
        "fix_available row support_packet_install_tuple_drift has install-aware receipt value mismatches: "
        "installed_build_receipt_platform!=platform, installed_build_receipt_rid!=expected_rid, "
        "installed_build_receipt_tuple_id!=expected_tuple_id",
    ]


def test_verify_next90_m102_fleet_reporter_receipts_fails_ready_row_release_channel_drift(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, _ = _fixture_paths(tmp_path)
    payload = _support_packets_payload()
    payload["reporter_followthrough_plan"]["action_groups"]["fix_available"].append(
        {
            "packet_id": "support_packet_release_channel_drift",
            "state": "fix_available_ready",
            "next_action": "send_fix_available",
            "feedback_loop_ready": True,
            "install_receipt_ready": True,
            "install_truth_state": "promoted_tuple_match",
            "release_receipt_state": "release_receipt_ready",
            "release_channel": "stable",
            **_release_receipt_fields(),
            "installation_id": "install-release-channel-drift-1",
            "installed_version": "1.2.2",
            "installed_build_receipt_id": "install-receipt-release-channel-drift-1",
            "installed_build_receipt_installation_id": "install-release-channel-drift-1",
            "installed_build_receipt_version": "1.2.2",
            "installed_build_receipt_channel": "preview",
            "installed_build_receipt_source": "install_receipts",
            "installed_build_receipt_installation_source": "install_receipts",
            "installed_build_receipt_version_source": "install_receipts",
            "installed_build_receipt_channel_source": "install_receipts",
            "installed_build_receipted": True,
            "fixed_version": "1.2.3",
            "fixed_channel": "preview",
            "fixed_version_receipted": True,
            "fixed_channel_receipted": True,
            "fixed_version_receipt_id": "fix-version-receipt-release-channel-drift-1",
            "fixed_channel_receipt_id": "fix-channel-receipt-release-channel-drift-1",
            "fixed_receipt_installation_id": "install-release-channel-drift-1",
            "fixed_receipt_installation_source": "fix_receipts",
            "fixed_receipt_installation_matches": True,
            "fixed_version_receipt_source": "fix_receipts",
            "fixed_channel_receipt_source": "fix_receipts",
        }
    )
    _write_json(support, payload)

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert "reporter followthrough action groups contain rows without receipt gates" in result["issues"]
    assert result["action_group_receipt_issues"] == [
        "fix_available row support_packet_release_channel_drift has install-aware receipt value mismatches: "
        "release_channel!=release_receipt_channel",
    ]


def test_verify_next90_m102_fleet_reporter_receipts_fails_ready_rows_without_receipt_feed_source(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, _ = _fixture_paths(tmp_path)
    payload = _support_packets_payload()
    payload["source"].update(
        {
            "install_receipt_feed_state": "not_provided",
            "install_receipt_source_count": 0,
            "install_receipt_indexed_count": 0,
            "install_receipt_hydrated_case_count": 0,
            "fix_receipt_feed_state": "not_provided",
            "fix_receipt_source_count": 0,
            "fix_receipt_indexed_count": 0,
            "fix_receipt_hydrated_case_count": 0,
        }
    )
    payload["reporter_followthrough_plan"]["action_groups"]["fix_available"].append(
        {
            "packet_id": "support_packet_feed_source_missing",
            "state": "fix_available_ready",
            "next_action": "send_fix_available",
            "feedback_loop_ready": True,
            "install_receipt_ready": True,
            "install_truth_state": "promoted_tuple_match",
            "release_receipt_state": "release_receipt_ready",
            **_release_receipt_fields(),
            "installation_id": "install-feed-source-1",
            "release_channel": "preview",
            "head_id": "avalonia",
            "platform": "linux",
            "arch": "x64",
            "installed_version": "1.2.3",
            "installed_build_receipt_id": "install-receipt-feed-source-1",
            "installed_build_receipt_installation_id": "install-feed-source-1",
            "installed_build_receipt_version": "1.2.3",
            "installed_build_receipt_channel": "preview",
            "installed_build_receipt_head_id": "avalonia",
            "installed_build_receipt_platform": "linux",
            "installed_build_receipt_rid": "linux-x64",
            "installed_build_receipt_tuple_id": "avalonia:linux-x64:linux",
            "installed_build_receipt_source": "install_receipts",
            "installed_build_receipt_installation_source": "install_receipts",
            "installed_build_receipt_version_source": "install_receipts",
            "installed_build_receipt_channel_source": "install_receipts",
            "installed_build_receipted": True,
            "fixed_version": "1.2.3",
            "fixed_channel": "preview",
            "fixed_version_receipted": True,
            "fixed_channel_receipted": True,
            "fixed_version_receipt_id": "fix-version-receipt-feed-source-1",
            "fixed_channel_receipt_id": "fix-channel-receipt-feed-source-1",
            "fixed_receipt_installation_id": "install-feed-source-1",
            "fixed_receipt_installation_source": "fix_receipts",
            "fixed_receipt_installation_matches": True,
            "fixed_version_receipt_source": "fix_receipts",
            "fixed_channel_receipt_source": "fix_receipts",
        }
    )
    _write_json(support, payload)

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert "support packet source receipt-feed metadata does not back ready followthrough" in result["issues"]
    assert result["receipt_feed_source_issues"] == [
        "ready reporter followthrough exists without an authoritative install receipt feed",
        "ready reporter followthrough exists without indexed install receipts",
        "ready reporter followthrough exists without hydrated install receipt cases",
        "fix-bearing reporter followthrough exists without an authoritative fix receipt feed",
        "fix-bearing reporter followthrough exists without indexed fix receipts",
        "fix-bearing reporter followthrough exists without hydrated fix receipt cases",
    ]


def test_verify_next90_m102_fleet_reporter_receipts_fails_queued_summary_overclaim(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, _ = _fixture_paths(tmp_path)
    payload = _support_packets_payload()
    payload["summary"]["reporter_followthrough_ready_count"] = 3
    payload["summary"]["feedback_followthrough_ready_count"] = 2
    payload["summary"]["fix_available_ready_count"] = 1
    _write_json(support, payload)

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert (
        "SUPPORT_CASE_PACKETS.generated.json summary disagrees with receipt-backed followthrough plan"
        in result["issues"]
    )
    assert result["support_summary_count_mismatches"] == {
        "feedback_followthrough_ready_count": {
            "receipt_backed_plan": 0,
            "support_packet_summary": 2,
        },
        "fix_available_ready_count": {
            "receipt_backed_plan": 0,
            "support_packet_summary": 1,
        },
        "reporter_followthrough_ready_count": {
            "receipt_backed_plan": 0,
            "support_packet_summary": 3,
        },
    }


def test_verify_next90_m102_fleet_reporter_receipts_fails_receipt_gate_count_overclaim(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, _ = _fixture_paths(tmp_path)
    support_payload = _support_packets_payload()
    support_payload["followthrough_receipt_gates"]["ready_count"] = 1
    _write_json(support, support_payload)

    weekly_payload = _weekly_payload()
    weekly_payload["truth_inputs"]["support_summary"]["followthrough_receipt_gates_ready_count"] = 1
    _align_weekly_support_path(weekly_payload, support=support)
    _write_json(weekly, weekly_payload)
    weekly_markdown.write_text(
        _weekly_markdown().replace(
            "- Receipt-gated followthrough ready: 0",
            "- Receipt-gated followthrough ready: 1",
        ),
        encoding="utf-8",
    )

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert "followthrough receipt gate counts disagree with receipt-backed action groups" in result["issues"]
    assert result["receipt_gate_plan_count_mismatches"] == {
        "ready_count": {
            "receipt_backed_action_groups": 0,
            "followthrough_receipt_gates": 1,
        }
    }


def test_verify_next90_m102_fleet_reporter_receipts_fails_stale_successor_issues(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, _ = _fixture_paths(tmp_path)
    payload = _support_packets_payload()
    _align_successor_verification_paths(
        payload,
        registry=registry,
        queue=queue,
        design_queue=tmp_path / "DESIGN_NEXT_90_DAY_QUEUE_STAGING.generated.yaml",
    )
    payload["successor_package_verification"]["issues"] = [
        "successor queue item proof missing marker: receipt gate drift"
    ]
    _write_json(support, payload)

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert "SUPPORT_CASE_PACKETS.generated.json successor verification carries stale proof gaps" in result["issues"]
    assert result["support_packet_stale_proof_gaps"]["issues"] == [
        "successor queue item proof missing marker: receipt gate drift"
    ]


def test_verify_next90_m102_fleet_reporter_receipts_fails_active_run_helper_proof(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, design_queue = _fixture_paths(tmp_path)
    _write_queue(
        queue,
        design_queue,
        proof_tail="      - /VAR/LIB/CODEX-FLEET/chummer_design_supervisor/shard-7/active_run_handoff.generated.md\n",
    )

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert result["successor_authority_status"] == "fail"
    assert "successor queue proof cites active-run telemetry or helper commands" in result["issues"]
    assert result["blocked_queue_proof_entries"] == [
        "/VAR/LIB/CODEX-FLEET/chummer_design_supervisor/shard-7/active_run_handoff.generated.md"
    ]
    assert result["blocked_proof_entries"] == result["blocked_queue_proof_entries"]


def test_verify_next90_m102_fleet_reporter_receipts_fails_telemetry_command_proof(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, design_queue = _fixture_paths(tmp_path)
    _write_queue(
        queue,
        design_queue,
        proof_tail="      - codexea --telemetry --telemetry-answer remaining\n",
    )

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert result["successor_authority_status"] == "fail"
    assert "successor queue proof cites active-run telemetry or helper commands" in result["issues"]
    assert result["blocked_queue_proof_entries"] == [
        "codexea --telemetry --telemetry-answer remaining"
    ]


def test_verify_next90_m102_fleet_reporter_receipts_fails_runtime_handoff_metadata_proof(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, design_queue = _fixture_paths(tmp_path)
    _write_queue(
        queue,
        design_queue,
        proof_tail="      - 'Frontier ids: 2454416974'\n",
    )

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert result["successor_authority_status"] == "fail"
    assert "successor queue proof cites active-run telemetry or helper commands" in result["issues"]
    assert result["blocked_queue_proof_entries"] == ["Frontier ids: 2454416974"]


def test_verify_next90_m102_fleet_reporter_receipts_fails_supervisor_helper_command_proof(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, design_queue = _fixture_paths(tmp_path)
    _write_queue(
        queue,
        design_queue,
        proof_tail="      - python3 scripts/chummer_design_supervisor.py active-runs\n",
    )

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert result["successor_authority_status"] == "fail"
    assert "successor queue proof cites active-run telemetry or helper commands" in result["issues"]
    assert result["blocked_queue_proof_entries"] == [
        "python3 scripts/chummer_design_supervisor.py active-runs"
    ]


def test_verify_next90_m102_fleet_reporter_receipts_fails_missing_bootstrap_guard_proof(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, _ = _fixture_paths(tmp_path)
    queue.write_text(
        queue.read_text(encoding="utf-8").replace(
            "      - /docker/fleet/scripts/verify_script_bootstrap_no_pythonpath.py\n"
            "      - /docker/fleet/tests/test_fleet_script_bootstrap_without_pythonpath.py\n",
            "",
        ),
        encoding="utf-8",
    )

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert result["successor_authority_status"] == "fail"
    assert "successor authority reports missing_queue_proof_markers" in result["issues"]


def test_verify_next90_m102_fleet_reporter_receipts_fails_design_source_missing_proof_marker(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, design_queue = _fixture_paths(tmp_path)
    design_queue.write_text(
        design_queue.read_text(encoding="utf-8").replace(
            "      - /docker/fleet/scripts/verify_next90_m102_fleet_reporter_receipts.py\n",
            "",
        ),
        encoding="utf-8",
    )

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert result["successor_authority_status"] == "fail"
    assert (
        "successor design queue source proof missing marker: "
        "/docker/fleet/scripts/verify_next90_m102_fleet_reporter_receipts.py"
        in result["successor_authority_issues"]
    )


def test_verify_next90_m102_fleet_reporter_receipts_fails_design_source_helper_proof(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, design_queue = _fixture_paths(tmp_path)
    design_queue.write_text(
        design_queue.read_text(encoding="utf-8").replace(
            "      - design-owned queue source row matches the Fleet completed queue proof assignment\n",
            "      - design-owned queue source row matches the Fleet completed queue proof assignment\n"
            "      - python3 scripts/chummer_design_supervisor.py worker-status\n",
        ),
        encoding="utf-8",
    )

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert result["successor_authority_status"] == "fail"
    assert (
        "successor design queue source proof cites active-run telemetry or helper commands"
        in result["issues"]
    )
    assert result["blocked_design_queue_source_proof_entries"] == [
        "python3 scripts/chummer_design_supervisor.py worker-status"
    ]
    assert result["blocked_proof_entries"] == result["blocked_design_queue_source_proof_entries"]


def test_verify_next90_m102_fleet_reporter_receipts_fails_missing_command_proof(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, _ = _fixture_paths(tmp_path)
    queue.write_text(
        queue.read_text(encoding="utf-8").replace(
            "      - python3 scripts/verify_next90_m102_fleet_reporter_receipts.py exits 0\n",
            "",
        ),
        encoding="utf-8",
    )

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert result["successor_authority_status"] == "fail"
    assert "successor authority reports missing_queue_proof_markers" in result["issues"]


def test_verify_next90_m102_fleet_reporter_receipts_fails_missing_negative_proof_marker(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, _ = _fixture_paths(tmp_path)
    queue.write_text(
        queue.read_text(encoding="utf-8").replace(
            "      - telemetry command proof markers fail the standalone verifier and shared successor authority check\n",
            "",
        ),
        encoding="utf-8",
    )

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert "successor queue proof is missing standalone verifier negative-proof markers" in result["issues"]
    assert result["missing_queue_negative_proof_markers"] == [
        "telemetry command proof markers fail the standalone verifier and shared successor authority check"
    ]


def test_verify_next90_m102_fleet_reporter_receipts_fails_collapsed_queue_proof_entries(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, _ = _fixture_paths(tmp_path)
    queue_text = queue.read_text(encoding="utf-8")
    collapsed_marker = (
        "standalone verifier rejects missing receipt-gate names; "
        "no-PYTHONPATH bootstrap guard includes the standalone M102 verifier; "
        "telemetry command proof markers fail the standalone verifier and shared successor authority check"
    )
    queue_text = queue_text.replace(
        "      - standalone verifier rejects missing receipt-gate names, missing weekly receipt counters, and active-run telemetry helper proof entries\n"
        "      - successor frontier 2454416974 pinned for next90-m102-fleet-reporter-receipts repeat prevention\n"
        "      - no-PYTHONPATH bootstrap guard includes the standalone M102 verifier\n",
        "      - " + collapsed_marker + "\n"
        "      - successor frontier 2454416974 pinned for next90-m102-fleet-reporter-receipts repeat prevention\n",
    )
    queue.write_text(queue_text, encoding="utf-8")

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert "successor queue proof collapses required command or negative-proof entries" in result["issues"]
    assert result["missing_queue_negative_proof_markers"] == []
    assert result["missing_distinct_queue_proof_entries"] == [
        "no-PYTHONPATH bootstrap guard includes the standalone M102 verifier",
        "standalone verifier rejects missing receipt-gate names, missing weekly receipt counters, and active-run telemetry helper proof entries",
    ]


def test_verify_next90_m102_fleet_reporter_receipts_fails_duplicate_queue_package_rows(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, _ = _fixture_paths(tmp_path)
    queue.write_text(
        queue.read_text(encoding="utf-8")
        + """
  - title: Gate fix followthrough against real install and receipt truth
    task: Compile feedback, fix-available, please-test, and recovery loops from install-aware release receipts instead of queued support state alone.
    package_id: next90-m102-fleet-reporter-receipts
    frontier_id: 2454416974
    milestone_id: 102
    wave: W6
    repo: fleet
    status: complete
    proof:
      - stale duplicate row
    allowed_paths:
      - scripts
      - tests
      - .codex-studio
      - feedback
    owned_surfaces:
      - feedback_loop_ready:install_receipts
      - product_governor:followthrough
""",
        encoding="utf-8",
    )

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert result["successor_authority_status"] == "fail"
    assert (
        "successor queue item next90-m102-fleet-reporter-receipts appears more than once"
        in result["successor_authority_issues"]
    )


def test_verify_next90_m102_fleet_reporter_receipts_fails_duplicate_design_queue_rows(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, design_queue = _fixture_paths(tmp_path)
    design_queue.write_text(
        design_queue.read_text(encoding="utf-8")
        + """
  - title: Gate fix followthrough against real install and receipt truth
    task: Compile feedback, fix-available, please-test, and recovery loops from install-aware release receipts instead of queued support state alone.
    package_id: next90-m102-fleet-reporter-receipts
    frontier_id: 2454416974
    milestone_id: 102
    wave: W6
    repo: fleet
    status: complete
    proof:
      - stale duplicate design-source row
    allowed_paths:
      - scripts
      - tests
      - .codex-studio
      - feedback
    owned_surfaces:
      - feedback_loop_ready:install_receipts
      - product_governor:followthrough
""",
        encoding="utf-8",
    )

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert result["successor_authority_status"] == "fail"
    assert (
        "successor design queue source item next90-m102-fleet-reporter-receipts appears more than once"
        in result["successor_authority_issues"]
    )


def test_verify_next90_m102_fleet_reporter_receipts_fails_duplicate_registry_work_tasks(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, _ = _fixture_paths(tmp_path)
    registry.write_text(
        registry.read_text(encoding="utf-8")
        + """
      - id: 102.4
        owner: fleet
        title: Gate the staged reporter mail loop against real install and fix receipts, not only queued support state.
        status: complete
        evidence:
          - stale duplicate registry work-task row
""",
        encoding="utf-8",
    )

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert result["successor_authority_status"] == "fail"
    assert (
        "successor registry work task 102.4 appears more than once"
        in result["successor_authority_issues"]
    )


def test_verify_next90_m102_fleet_reporter_receipts_fails_missing_weekly_markdown_proof(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, _ = _fixture_paths(tmp_path)
    queue.write_text(
        queue.read_text(encoding="utf-8").replace(
            "      - /docker/fleet/.codex-studio/published/WEEKLY_GOVERNOR_PACKET.generated.md\n",
            "",
        ),
        encoding="utf-8",
    )

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert result["successor_authority_status"] == "fail"
    assert "successor authority reports missing_queue_proof_markers" in result["issues"]


def test_verify_next90_m102_fleet_reporter_receipts_fails_active_run_registry_evidence(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, _ = _fixture_paths(tmp_path)
    _write_registry(
        registry,
        evidence_tail=(
            "          - /VAR/LIB/CODEX-FLEET/chummer_design_supervisor/shard-7/"
            "task_local_telemetry.generated.json\n"
        ),
    )

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert result["successor_authority_status"] == "fail"
    assert "successor registry evidence cites active-run telemetry or helper commands" in result["issues"]
    assert result["blocked_registry_evidence_entries"] == [
        "/VAR/LIB/CODEX-FLEET/chummer_design_supervisor/shard-7/task_local_telemetry.generated.json"
    ]
    assert result["blocked_proof_entries"] == result["blocked_registry_evidence_entries"]


def test_verify_next90_m102_fleet_reporter_receipts_fails_active_run_input_paths(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, _ = _fixture_paths(tmp_path)

    result = module.verify(
        support_packets_path=Path(
            "/var/lib/codex-fleet/chummer_design_supervisor/shard-7/ACTIVE_RUN_HANDOFF.generated.md"
        ),
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert "verifier inputs cite active-run telemetry or helper paths" in result["issues"]
    assert result["blocked_input_paths"] == [
        "/var/lib/codex-fleet/chummer_design_supervisor/shard-7/ACTIVE_RUN_HANDOFF.generated.md"
    ]
    assert "weekly governor support-packets input path disagrees with verified support packet" in result["issues"]


def test_verify_next90_m102_fleet_reporter_receipts_requires_weekly_support_input(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, _ = _fixture_paths(tmp_path)
    payload = _weekly_payload()
    payload["source_input_health"]["required_inputs"].pop("support_packets")
    _write_json(weekly, payload)

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert "weekly governor support-packets input is missing" in result["issues"]


def test_verify_next90_m102_fleet_reporter_receipts_fails_weekly_support_input_path_drift(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, _ = _fixture_paths(tmp_path)
    payload = _weekly_payload()
    _align_weekly_support_path(
        payload,
        support=support.parent / "OTHER_SUPPORT_CASE_PACKETS.generated.json",
    )
    _write_json(weekly, payload)

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert (
        "weekly governor support-packets input path disagrees with verified support packet"
        in result["issues"]
    )


def test_verify_next90_m102_fleet_reporter_receipts_requires_weekly_support_input_sha256(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, _ = _fixture_paths(tmp_path)
    payload = json.loads(weekly.read_text(encoding="utf-8"))
    payload["source_input_health"]["required_inputs"]["support_packets"].pop("source_sha256")
    _write_json(weekly, payload)

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert "weekly governor support-packets input is missing source_sha256" in result["issues"]


def test_verify_next90_m102_fleet_reporter_receipts_fails_weekly_support_input_sha256_drift(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, _ = _fixture_paths(tmp_path)
    payload = json.loads(weekly.read_text(encoding="utf-8"))
    payload["source_input_health"]["required_inputs"]["support_packets"]["source_sha256"] = "0" * 64
    _write_json(weekly, payload)

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert (
        "weekly governor support-packets input sha256 disagrees with verified support packet"
        in result["issues"]
    )


def test_verify_next90_m102_fleet_reporter_receipts_fails_weekly_support_input_helper_path(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, _ = _fixture_paths(tmp_path)
    payload = _weekly_payload()
    _align_weekly_support_path(
        payload,
        support=Path(
            "/var/lib/codex-fleet/chummer_design_supervisor/shard-7/TASK_LOCAL_TELEMETRY.generated.json"
        ),
    )
    _write_json(weekly, payload)

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert (
        "weekly governor support-packets input path cites active-run telemetry or helper paths"
        in result["issues"]
    )
    assert (
        "weekly governor support-packets input path disagrees with verified support packet"
        not in result["issues"]
    )


def test_verify_next90_m102_fleet_reporter_receipts_fails_design_queue_source_helper_path(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, _ = _fixture_paths(tmp_path)
    queue_text = queue.read_text(encoding="utf-8")
    queue_text = queue_text.replace(
        "source_design_queue_path: " + str(tmp_path / "DESIGN_NEXT_90_DAY_QUEUE_STAGING.generated.yaml"),
        "source_design_queue_path: /var/lib/codex-fleet/chummer_design_supervisor/shard-7/ACTIVE_RUN_HANDOFF.generated.md",
    )
    queue.write_text(queue_text, encoding="utf-8")

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert result["successor_authority_status"] == "fail"
    assert (
        "successor queue staging source_design_queue_path cites active-run telemetry/helper path"
        in result["successor_authority_issues"]
    )


def test_verify_next90_m102_fleet_reporter_receipts_requires_weekly_source_path_hygiene(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, _ = _fixture_paths(tmp_path)
    payload = _weekly_payload()
    payload["source_input_health"]["required_inputs"]["source_path_hygiene"] = {
        "state": "fail",
        "disallowed_source_paths": [
            "/var/lib/codex-fleet/chummer_design_supervisor/shard-7/ACTIVE_RUN_HANDOFF.generated.md"
        ],
        "blocked_markers": [],
    }
    _write_json(weekly, payload)

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert "weekly governor source-path hygiene is not pass" in result["issues"]
    assert "weekly governor source-path hygiene reports disallowed source paths" in result["issues"]
    assert "weekly governor source-path hygiene is missing blocked helper markers" in result["issues"]
    assert "/var/lib/codex-fleet" in result["missing_weekly_source_path_hygiene_markers"]


def test_verify_next90_m102_fleet_reporter_receipts_requires_weekly_worker_command_guard(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, _ = _fixture_paths(tmp_path)
    payload = _weekly_payload()
    payload["repeat_prevention"]["worker_command_guard"] = {
        "status": "missing",
        "blocked_markers": [],
        "rule": "proof can cite operator telemetry",
    }
    _write_json(weekly, payload)

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert "weekly governor worker command guard is not active" in result["issues"]
    assert "weekly governor worker command guard is missing blocked helper markers" in result["issues"]
    assert "weekly governor worker command guard rule drifted" in result["issues"]
    assert "codexea --telemetry" in result["missing_weekly_worker_guard_markers"]


def test_verify_next90_m102_fleet_reporter_receipts_fails_support_packet_active_run_proof(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, _ = _fixture_paths(tmp_path)
    payload = _support_packets_payload()
    payload["successor_package_verification"]["disallowed_queue_proof_entries"] = [
        "/var/lib/codex-fleet/chummer_design_supervisor/shard-7/ACTIVE_RUN_HANDOFF.generated.md"
    ]
    _write_json(support, payload)

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert (
        "SUPPORT_CASE_PACKETS.generated.json exposes active-run telemetry or helper proof entries"
        in result["issues"]
    )
    assert result["support_packet_blocked_proof_entries"] == [
        "/var/lib/codex-fleet/chummer_design_supervisor/shard-7/ACTIVE_RUN_HANDOFF.generated.md"
    ]


def test_verify_next90_m102_fleet_reporter_receipts_fails_support_packet_design_source_helper_proof(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, _ = _fixture_paths(tmp_path)
    payload = _support_packets_payload()
    payload["successor_package_verification"]["disallowed_design_queue_source_proof_entries"] = [
        "codexea --telemetry --telemetry-answer m102"
    ]
    _write_json(support, payload)

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert (
        "SUPPORT_CASE_PACKETS.generated.json exposes active-run telemetry or helper proof entries"
        in result["issues"]
    )
    assert result["support_packet_blocked_proof_entries"] == [
        "codexea --telemetry --telemetry-answer m102"
    ]


def test_verify_next90_m102_fleet_reporter_receipts_fails_support_packet_stale_proof_gaps(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, _ = _fixture_paths(tmp_path)
    payload = _support_packets_payload()
    payload["successor_package_verification"]["missing_queue_proof_anchor_paths"] = [
        "/docker/fleet/tests/test_verify_next90_m102_fleet_reporter_receipts.py"
    ]
    _write_json(support, payload)

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert (
        "SUPPORT_CASE_PACKETS.generated.json successor verification carries stale proof gaps"
        in result["issues"]
    )
    assert result["support_packet_stale_proof_gaps"] == {
        "missing_queue_proof_anchor_paths": [
            "/docker/fleet/tests/test_verify_next90_m102_fleet_reporter_receipts.py"
        ]
    }
    assert result["missing_support_packet_proof_gap_fields"] == []


def test_verify_next90_m102_fleet_reporter_receipts_fails_missing_generated_proof_gap_field(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, _ = _fixture_paths(tmp_path)
    payload = _support_packets_payload()
    payload["successor_package_verification"].pop("missing_design_queue_source_proof_markers")
    _write_json(support, payload)

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert (
        "SUPPORT_CASE_PACKETS.generated.json successor verification carries stale proof gaps"
        in result["issues"]
    )
    assert result["missing_support_packet_proof_gap_fields"] == [
        "missing_design_queue_source_proof_markers"
    ]


def test_verify_next90_m102_fleet_reporter_receipts_fails_support_packet_closure_field_drift(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, design_queue = _fixture_paths(tmp_path)
    payload = _support_packets_payload()
    _align_successor_verification_paths(
        payload,
        registry=registry,
        queue=queue,
        design_queue=design_queue,
    )
    payload["successor_package_verification"]["queue_status"] = "queued"
    payload["successor_package_verification"]["design_queue_source_frontier_id"] = ""
    _write_json(support, payload)

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert (
        "SUPPORT_CASE_PACKETS.generated.json successor verification closure fields drifted"
        in result["issues"]
    )
    assert result["support_packet_successor_field_mismatches"] == {
        "design_queue_source_frontier_id": {
            "support_packets": "",
            "computed_successor_authority": "2454416974",
        },
        "queue_status": {
            "support_packets": "queued",
            "computed_successor_authority": "complete",
        },
    }


def test_verify_next90_m102_fleet_reporter_receipts_fails_support_packet_scope_drift(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, design_queue = _fixture_paths(tmp_path)
    payload = _support_packets_payload()
    _align_successor_verification_paths(
        payload,
        registry=registry,
        queue=queue,
        design_queue=design_queue,
    )
    payload["successor_package_verification"]["allowed_paths"] = ["scripts", "tests"]
    payload["successor_package_verification"]["owned_surfaces"] = ["product_governor:followthrough"]
    _write_json(support, payload)

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert (
        "SUPPORT_CASE_PACKETS.generated.json successor verification closure fields drifted"
        in result["issues"]
    )
    assert result["support_packet_successor_field_mismatches"] == {
        "allowed_paths": {
            "support_packets": ["scripts", "tests"],
            "computed_successor_authority": ["scripts", "tests", ".codex-studio", "feedback"],
        },
        "owned_surfaces": {
            "support_packets": ["product_governor:followthrough"],
            "computed_successor_authority": [
                "feedback_loop_ready:install_receipts",
                "product_governor:followthrough",
            ],
        },
    }


def test_verify_next90_m102_fleet_reporter_receipts_fails_support_packet_assignment_drift(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, design_queue = _fixture_paths(tmp_path)
    payload = _support_packets_payload()
    _align_successor_verification_paths(
        payload,
        registry=registry,
        queue=queue,
        design_queue=design_queue,
    )
    payload["successor_package_verification"]["repo"] = "chummer6-hub"
    payload["successor_package_verification"]["registry_title"] = "Old desktop support loop"
    payload["successor_package_verification"]["queue_task"] = (
        "Compile reporter followthrough from queued support state."
    )
    _write_json(support, payload)

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert (
        "SUPPORT_CASE_PACKETS.generated.json successor verification closure fields drifted"
        in result["issues"]
    )
    assert result["support_packet_successor_field_mismatches"] == {
        "queue_task": {
            "support_packets": "Compile reporter followthrough from queued support state.",
            "computed_successor_authority": (
                "Compile feedback, fix-available, please-test, and recovery loops from "
                "install-aware release receipts instead of queued support state alone."
            ),
        },
        "registry_title": {
            "support_packets": "Old desktop support loop",
            "computed_successor_authority": "Desktop-native claim, update, rollback, and support followthrough",
        },
        "repo": {
            "support_packets": "chummer6-hub",
            "computed_successor_authority": "fleet",
        },
    }


def test_verify_next90_m102_fleet_reporter_receipts_fails_support_packet_source_path_drift(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, design_queue = _fixture_paths(tmp_path)
    payload = _support_packets_payload()
    _align_successor_verification_paths(
        payload,
        registry=registry,
        queue=queue,
        design_queue=design_queue,
    )
    payload["successor_package_verification"]["registry_path"] = "/tmp/stale-registry.yaml"
    payload["successor_package_verification"]["queue_staging_path"] = "/tmp/stale-queue.yaml"
    payload["successor_package_verification"]["registry_work_task_id"] = "102.0"
    _write_json(support, payload)

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert (
        "SUPPORT_CASE_PACKETS.generated.json successor verification closure fields drifted"
        in result["issues"]
    )
    assert result["support_packet_successor_field_mismatches"] == {
        "queue_staging_path": {
            "support_packets": "/tmp/stale-queue.yaml",
            "computed_successor_authority": str(queue),
        },
        "registry_path": {
            "support_packets": "/tmp/stale-registry.yaml",
            "computed_successor_authority": str(registry),
        },
        "registry_work_task_id": {
            "support_packets": "102.0",
            "computed_successor_authority": "102.4",
        },
    }


def test_verify_next90_m102_fleet_reporter_receipts_fails_generated_queue_assignment_drift(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, design_queue = _fixture_paths(tmp_path)
    payload = _support_packets_payload()
    _align_successor_verification_paths(
        payload,
        registry=registry,
        queue=queue,
        design_queue=design_queue,
    )
    payload["successor_package_verification"]["queue_repo"] = "chummer6-hub"
    payload["successor_package_verification"]["queue_wave"] = "W7"
    payload["successor_package_verification"]["queue_milestone_id"] = 103
    payload["successor_package_verification"]["design_queue_source_repo"] = "chummer6-ui"
    payload["successor_package_verification"]["design_queue_source_wave"] = "W8"
    payload["successor_package_verification"]["design_queue_source_milestone_id"] = 105
    payload["successor_package_verification"]["registry_work_task_title"] = "Old reporter loop"
    _write_json(support, payload)

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert (
        "SUPPORT_CASE_PACKETS.generated.json successor verification closure fields drifted"
        in result["issues"]
    )
    assert result["support_packet_successor_field_mismatches"] == {
        "design_queue_source_milestone_id": {
            "support_packets": 105,
            "computed_successor_authority": 102,
        },
        "design_queue_source_repo": {
            "support_packets": "chummer6-ui",
            "computed_successor_authority": "fleet",
        },
        "design_queue_source_wave": {
            "support_packets": "W8",
            "computed_successor_authority": "W6",
        },
        "queue_milestone_id": {
            "support_packets": 103,
            "computed_successor_authority": 102,
        },
        "queue_repo": {
            "support_packets": "chummer6-hub",
            "computed_successor_authority": "fleet",
        },
        "queue_wave": {
            "support_packets": "W7",
            "computed_successor_authority": "W6",
        },
        "registry_work_task_title": {
            "support_packets": "Old reporter loop",
            "computed_successor_authority": "Gate the staged reporter mail loop against real install and fix receipts, not only queued support state.",
        },
    }


def test_verify_next90_m102_fleet_reporter_receipts_fails_generated_required_marker_drift(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, design_queue = _fixture_paths(tmp_path)
    payload = _support_packets_payload()
    expected_required_queue_proof_markers = list(
        payload["successor_package_verification"]["required_queue_proof_markers"]
    )
    expected_required_registry_evidence_markers = list(
        payload["successor_package_verification"]["required_registry_evidence_markers"]
    )
    _align_successor_verification_paths(
        payload,
        registry=registry,
        queue=queue,
        design_queue=design_queue,
    )
    payload["successor_package_verification"]["required_queue_proof_markers"] = [
        "/docker/fleet/scripts/materialize_support_case_packets.py"
    ]
    payload["successor_package_verification"]["required_registry_evidence_markers"] = [
        "scripts/materialize_support_case_packets.py"
    ]
    _write_json(support, payload)

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert (
        "SUPPORT_CASE_PACKETS.generated.json successor verification closure fields drifted"
        in result["issues"]
    )
    assert result["support_packet_successor_field_mismatches"] == {
        "required_queue_proof_markers": {
            "support_packets": ["/docker/fleet/scripts/materialize_support_case_packets.py"],
            "computed_successor_authority": expected_required_queue_proof_markers,
        },
        "required_registry_evidence_markers": {
            "support_packets": ["scripts/materialize_support_case_packets.py"],
            "computed_successor_authority": expected_required_registry_evidence_markers,
        },
    }


def test_verify_next90_m102_fleet_reporter_receipts_fails_weekly_count_drift(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, _ = _fixture_paths(tmp_path)
    support_payload = _support_packets_payload()
    support_payload["followthrough_receipt_gates"]["ready_count"] = 2
    support_payload["followthrough_receipt_gates"]["gate_counts"][
        "installed_build_receipt_installation_bound"
    ] = 2
    support_payload["followthrough_receipt_gates"]["gate_counts"]["installed_build_receipted"] = 1
    support_payload["reporter_followthrough_plan"]["ready_count"] = 2
    _write_json(support, support_payload)

    weekly_payload = _weekly_payload()
    weekly_payload["truth_inputs"]["support_summary"][
        "followthrough_receipt_gates_ready_count"
    ] = 1
    weekly_payload["truth_inputs"]["support_summary"][
        "followthrough_receipt_gates_installation_bound_count"
    ] = 0
    weekly_payload["truth_inputs"]["support_summary"][
        "followthrough_receipt_gates_installed_build_receipted_count"
    ] = 0
    weekly_payload["truth_inputs"]["support_summary"][
        "reporter_followthrough_plan_ready_count"
    ] = 1
    weekly_payload["truth_inputs"]["support_summary"]["reporter_followthrough_ready_count"] = 1
    weekly_payload["truth_inputs"]["support_summary"]["fix_available_ready_count"] = 1
    weekly_payload["truth_inputs"]["support_summary"]["please_test_ready_count"] = 1
    weekly_payload["truth_inputs"]["support_summary"]["recovery_loop_ready_count"] = 1
    _write_json(weekly, weekly_payload)
    weekly_markdown.write_text(
        _weekly_markdown()
        .replace("Reporter followthrough ready: 0", "Reporter followthrough ready: 1")
        .replace("Receipt-gated followthrough ready: 0", "Receipt-gated followthrough ready: 1")
        .replace(
            "Receipt-gated installed-build receipts: 0",
            "Receipt-gated installed-build receipts: 0",
        ),
        encoding="utf-8",
    )

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert (
        "weekly governor support summary disagrees with support-packet receipt gates"
        in result["issues"]
    )
    assert result["weekly_count_mismatches"][
        "followthrough_receipt_gates_installed_build_receipted_count"
    ] == {"support_packets": 1, "weekly_governor_packet": 0}
    assert result["weekly_count_mismatches"][
        "followthrough_receipt_gates_installation_bound_count"
    ] == {"support_packets": 2, "weekly_governor_packet": 0}
    assert result["weekly_count_mismatches"]["followthrough_receipt_gates_ready_count"] == {
        "support_packets": 2,
        "weekly_governor_packet": 1,
    }
    assert result["weekly_count_mismatches"]["reporter_followthrough_ready_count"] == {
        "support_packets": 0,
        "weekly_governor_packet": 1,
    }
    assert result["weekly_count_mismatches"]["reporter_followthrough_plan_ready_count"] == {
        "support_packets": 0,
        "weekly_governor_packet": 1,
    }
    assert result["weekly_count_mismatches"]["fix_available_ready_count"] == {
        "support_packets": 0,
        "weekly_governor_packet": 1,
    }
    assert result["weekly_count_mismatches"]["please_test_ready_count"] == {
        "support_packets": 0,
        "weekly_governor_packet": 1,
    }
    assert result["weekly_count_mismatches"]["recovery_loop_ready_count"] == {
        "support_packets": 0,
        "weekly_governor_packet": 1,
    }


def test_verify_next90_m102_fleet_reporter_receipts_fails_stale_weekly_packet(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, _ = _fixture_paths(tmp_path)
    weekly_payload = _weekly_payload()
    weekly_payload["generated_at"] = "2026-04-15T14:00:00Z"
    _write_json(weekly, weekly_payload)

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert "weekly governor packet predates support-packet receipt gates" in result["issues"]
    assert result["support_packets_generated_at"] == "2026-04-15T14:11:15Z"
    assert result["weekly_governor_packet_generated_at"] == "2026-04-15T14:00:00Z"


def test_verify_next90_m102_fleet_reporter_receipts_fails_future_generated_at(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, _ = _fixture_paths(tmp_path)
    future_generated_at = "2099-04-15T14:11:15Z"
    support_payload = json.loads(support.read_text(encoding="utf-8"))
    support_payload["generated_at"] = future_generated_at
    support_payload["followthrough_receipt_gates"]["generated_at"] = future_generated_at
    support_payload["reporter_followthrough_plan"]["generated_at"] = future_generated_at
    _write_json(support, support_payload)
    weekly_payload = json.loads(weekly.read_text(encoding="utf-8"))
    weekly_payload["generated_at"] = future_generated_at
    _write_json(weekly, weekly_payload)
    weekly_markdown.write_text(
        _weekly_markdown().replace("2026-04-15T14:13:33Z", future_generated_at),
        encoding="utf-8",
    )

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert "generated receipt timestamps are future-dated" in result["issues"]
    assert result["future_timestamp_drifts"] == {
        "followthrough_receipt_gates.generated_at": future_generated_at,
        "reporter_followthrough_plan.generated_at": future_generated_at,
        "support_packets.generated_at": future_generated_at,
        "weekly_governor_markdown.generated_at": future_generated_at,
        "weekly_governor_packet.generated_at": future_generated_at,
    }


def test_verify_next90_m102_fleet_reporter_receipts_fails_stale_embedded_support_timestamps(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, _ = _fixture_paths(tmp_path)
    support_payload = _support_packets_payload()
    support_payload["followthrough_receipt_gates"]["generated_at"] = "2026-04-15T14:00:00Z"
    support_payload["reporter_followthrough_plan"]["generated_at"] = "2026-04-15T14:10:00Z"
    _write_json(support, support_payload)

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert "followthrough receipt gates generated_at disagrees with support packet" in result["issues"]
    assert "reporter followthrough plan generated_at disagrees with support packet" in result["issues"]
    assert result["support_packets_generated_at"] == "2026-04-15T14:11:15Z"
    assert result["followthrough_receipt_gates_generated_at"] == "2026-04-15T14:00:00Z"
    assert result["reporter_followthrough_plan_generated_at"] == "2026-04-15T14:10:00Z"


def test_verify_next90_m102_fleet_reporter_receipts_fails_weekly_markdown_count_drift(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, _ = _fixture_paths(tmp_path)
    support_payload = _support_packets_payload()
    support_payload["followthrough_receipt_gates"]["ready_count"] = 2
    support_payload["followthrough_receipt_gates"]["blocked_receipt_mismatch_count"] = 1
    support_payload["followthrough_receipt_gates"]["gate_counts"]["installed_build_receipted"] = 2
    support_payload["reporter_followthrough_plan"]["ready_count"] = 2
    support_payload["reporter_followthrough_plan"]["action_groups"]["fix_available"] = [{"id": "case-1"}]
    _write_json(support, support_payload)
    weekly_payload = _weekly_payload()
    weekly_payload["truth_inputs"]["support_summary"]["followthrough_receipt_gates_ready_count"] = 2
    weekly_payload["truth_inputs"]["support_summary"][
        "followthrough_receipt_gates_blocked_receipt_mismatch_count"
    ] = 1
    weekly_payload["truth_inputs"]["support_summary"][
        "followthrough_receipt_gates_installed_build_receipted_count"
    ] = 2
    weekly_payload["truth_inputs"]["support_summary"]["reporter_followthrough_plan_ready_count"] = 2
    _write_json(weekly, weekly_payload)

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert "weekly governor markdown disagrees with support-packet receipt gates" in result["issues"]
    assert result["weekly_markdown_count_mismatches"] == {
        "Fix-available ready": {"support_packets": 1, "weekly_governor_markdown": 0},
        "Followthrough receipt mismatches": {
            "support_packets": 1,
            "weekly_governor_markdown": 0,
        },
        "Receipt-gated followthrough ready": {
            "support_packets": 2,
            "weekly_governor_markdown": 0,
        },
        "Receipt-gated installed-build receipts": {
            "support_packets": 2,
            "weekly_governor_markdown": 0,
        },
    }


def test_verify_next90_m102_fleet_reporter_receipts_fails_weekly_markdown_timestamp_drift(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, _ = _fixture_paths(tmp_path)
    weekly_markdown.write_text(
        _weekly_markdown().replace(
            "Generated: 2026-04-15T14:13:33Z",
            "Generated: 2026-04-15T14:12:00Z",
        ),
        encoding="utf-8",
    )

    result = module.verify(
        support_packets_path=support,
        weekly_governor_packet_path=weekly,
        weekly_governor_markdown_path=weekly_markdown,
        successor_registry_path=registry,
        queue_staging_path=queue,
    )

    assert result["status"] == "fail"
    assert "weekly governor markdown generated timestamp disagrees with JSON packet" in result["issues"]
    assert result["weekly_governor_markdown_generated_at"] == "2026-04-15T14:12:00Z"


def _run_direct_tests() -> int:
    failures: list[str] = []
    test_functions = [
        (name, value)
        for name, value in sorted(globals().items())
        if name.startswith("test_") and callable(value)
    ]
    for name, test_function in test_functions:
        signature = inspect.signature(test_function)
        try:
            if "tmp_path" in signature.parameters:
                with tempfile.TemporaryDirectory(prefix=f"{name}-") as tmp_dir:
                    test_function(Path(tmp_dir))
            else:
                test_function()
        except Exception as exc:  # pragma: no cover - only used by direct test harness.
            failures.append(f"{name}: {exc!r}")
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1
    print(f"direct verifier tests passed: {len(test_functions)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run_direct_tests())
