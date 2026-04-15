from __future__ import annotations

import importlib.util
import json
import sys
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
      - /docker/fleet/.codex-studio/published/SUPPORT_CASE_PACKETS.generated.json
      - /docker/fleet/.codex-studio/published/WEEKLY_GOVERNOR_PACKET.generated.json
      - /docker/fleet/feedback/2026-04-15-next90-m102-fleet-reporter-receipts-closeout.md
      - python3 -m py_compile scripts/materialize_support_case_packets.py scripts/verify_next90_m102_fleet_reporter_receipts.py tests/test_materialize_support_case_packets.py tests/test_verify_next90_m102_fleet_reporter_receipts.py scripts/materialize_weekly_governor_packet.py tests/test_materialize_weekly_governor_packet.py
      - installation-bound receipt gating blocks reporter followthrough when installed-build receipt installation id disagrees with the linked install
      - fixed-version receipts and fixed-channel receipts are required before reporter followthrough leaves hold
      - direct tmp_path fixture invocation for receipt-gated support followthrough tests exits 0
      - successor frontier 2454416974 pinned for next90-m102-fleet-reporter-receipts repeat prevention
      - generated support-packet proof hygiene requires empty disallowed active-run proof entries
      - stale generated support proof gaps fail the standalone verifier
      - weekly/support receipt-count drift fails the standalone verifier
      - weekly/support generated_at freshness fails the standalone verifier
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
            "registry_work_task_status": "complete",
            "queue_status": "complete",
            "queue_frontier_id": "2454416974",
            "design_queue_source_path": "",
            "design_queue_source_item_found": True,
            "design_queue_source_status": "complete",
            "design_queue_source_frontier_id": "2454416974",
            "missing_registry_evidence_markers": [],
            "missing_queue_proof_markers": [],
            "missing_registry_proof_anchor_paths": [],
            "missing_queue_proof_anchor_paths": [],
            "disallowed_registry_evidence_entries": [],
            "disallowed_queue_proof_entries": [],
        },
    }


def _weekly_payload() -> dict:
    return {
        "generated_at": "2026-04-15T14:13:33Z",
        "source_input_health": {
            "required_inputs": {
                "support_packets": {"successor_package_verification_status": "pass"}
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


def _fixture_paths(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path, Path]:
    support = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    weekly = tmp_path / "WEEKLY_GOVERNOR_PACKET.generated.json"
    weekly_markdown = tmp_path / "WEEKLY_GOVERNOR_PACKET.generated.md"
    registry = tmp_path / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
    queue = tmp_path / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    design_queue = tmp_path / "DESIGN_NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    _write_json(weekly, _weekly_payload())
    weekly_markdown.write_text(_weekly_markdown(), encoding="utf-8")
    _write_registry(registry)
    _write_queue(queue, design_queue)
    support_payload = _support_packets_payload()
    support_payload["successor_package_verification"]["design_queue_source_path"] = str(design_queue)
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


def test_verify_next90_m102_fleet_reporter_receipts_fails_support_packet_closure_field_drift(
    tmp_path: Path,
) -> None:
    module = _load_module()
    support, weekly, weekly_markdown, registry, queue, design_queue = _fixture_paths(tmp_path)
    payload = _support_packets_payload()
    payload["successor_package_verification"]["design_queue_source_path"] = str(design_queue)
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
