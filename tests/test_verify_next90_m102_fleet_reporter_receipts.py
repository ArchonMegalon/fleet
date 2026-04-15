from __future__ import annotations

import importlib.util
import inspect
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
          - /docker/fleet/scripts/verify_script_bootstrap_no_pythonpath.py includes the standalone M102 verifier in no-PYTHONPATH bootstrap proof.
          - python3 scripts/verify_next90_m102_fleet_reporter_receipts.py exits 0.
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
      - weekly/support receipt-count drift fails the standalone verifier
      - weekly/support generated_at freshness fails the standalone verifier
      - weekly support-packet source-path drift fails the standalone verifier
      - design queue source path rejects active-run helper paths
      - weekly governor source-path hygiene and worker command guard fail the standalone verifier
      - design-owned queue source proof markers fail the standalone verifier
      - telemetry command proof markers fail the standalone verifier and shared successor authority check
      - distinct queue proof anti-collapse guard prevents broad prose proof lines from satisfying command and negative-proof rows
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
      - weekly/support receipt-count drift fails the standalone verifier
      - weekly/support generated_at freshness fails the standalone verifier
      - weekly support-packet source-path drift fails the standalone verifier
      - design queue source path rejects active-run helper paths
      - weekly governor source-path hygiene and worker command guard fail the standalone verifier
      - design-owned queue source proof markers fail the standalone verifier
      - telemetry command proof markers fail the standalone verifier and shared successor authority check
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


def _support_packets_payload() -> dict:
    return {
        "contract_name": "fleet.support_case_packets",
        "generated_at": "2026-04-15T14:11:15Z",
        "followthrough_receipt_gates": {
            "package_id": "next90-m102-fleet-reporter-receipts",
            "milestone_id": 102,
            "generated_at": "2026-04-15T14:11:15Z",
            "source_rule": (
                "Fix-available, please-test, and recovery followthrough may leave hold only when install truth, "
                "installation-bound installed-build receipts, fixed-version receipts, fixed-channel receipts, "
                "and release-channel receipts agree."
            ),
            "required_gates": [
                "install_truth_ready",
                "release_receipt_ready",
                "fixed_version_receipted",
                "fixed_channel_receipted",
                "installed_build_receipt_id_present",
                "installed_build_receipt_installation_bound",
                "installed_build_receipt_version_matches",
                "installed_build_receipt_channel_matches",
            ],
            "gate_counts": {
                "install_receipt_ready": 0,
                "install_truth_ready": 0,
                "release_receipt_ready": 0,
                "fixed_version_receipted": 0,
                "fixed_channel_receipted": 0,
                "installed_build_receipted": 0,
                "installed_build_receipt_id_present": 0,
                "installed_build_receipt_installation_bound": 0,
                "installed_build_receipt_version_matches": 0,
                "installed_build_receipt_channel_matches": 0,
                "current_install_on_fixed_build": 0,
            },
        },
        "reporter_followthrough_plan": {
            "package_id": "next90-m102-fleet-reporter-receipts",
            "generated_at": "2026-04-15T14:11:15Z",
            "source_rule": (
                "Reporter followthrough is compiled from support packets only after install truth, "
                "installation-bound installed-build receipts, fixed-version receipts, fixed-channel receipts, "
                "and release-channel receipts agree."
            ),
            "action_groups": {
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
            "registry_work_task_title": "Gate the staged reporter mail loop against real install and fix receipts, not only queued support state.",
            "registry_work_task_status": "complete",
            "queue_title": "Gate fix followthrough against real install and receipt truth",
            "queue_task": "Compile feedback, fix-available, please-test, and recovery loops from install-aware release receipts instead of queued support state alone.",
            "queue_wave": "W6",
            "queue_repo": "fleet",
            "queue_milestone_id": 102,
            "queue_status": "complete",
            "queue_frontier_id": "2454416974",
            "design_queue_source_path": "",
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
                "verify_script_bootstrap_no_pythonpath.py",
                "python3 scripts/verify_next90_m102_fleet_reporter_receipts.py exits 0",
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
                "weekly/support receipt-count drift",
                "weekly/support generated_at freshness",
                "weekly support-packet source-path drift",
                "design queue source path rejects active-run helper paths",
                "weekly governor source-path hygiene and worker command guard",
                "design-owned queue source proof markers",
                "telemetry command proof markers fail the standalone verifier and shared successor authority check",
                "distinct queue proof anti-collapse guard",
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
                "followthrough_receipt_gates_ready_count": 0,
                "followthrough_receipt_gates_blocked_missing_install_receipts_count": 0,
                "followthrough_receipt_gates_blocked_receipt_mismatch_count": 0,
                "followthrough_receipt_gates_installation_bound_count": 0,
                "followthrough_receipt_gates_installed_build_receipted_count": 0,
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
    payload["source_input_health"]["required_inputs"]["support_packets"]["source_path"] = str(support)


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
    assert result["weekly_count_mismatches"] == {
        "followthrough_receipt_gates_installed_build_receipted_count": {
            "support_packets": 1,
            "weekly_governor_packet": 0,
        },
        "followthrough_receipt_gates_installation_bound_count": {
            "support_packets": 2,
            "weekly_governor_packet": 0,
        },
        "followthrough_receipt_gates_ready_count": {
            "support_packets": 2,
            "weekly_governor_packet": 1,
        },
        "reporter_followthrough_plan_ready_count": {
            "support_packets": 2,
            "weekly_governor_packet": 1,
        },
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
        "Reporter followthrough ready": {"support_packets": 2, "weekly_governor_markdown": 0},
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
