from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import yaml


SCRIPT = Path("/docker/fleet/scripts/materialize_weekly_governor_packet.py")
UTC = dt.timezone.utc
BLOCKED_WORKER_PROOF_MARKERS = [
    "/var/lib/codex-fleet",
    "ACTIVE_RUN_HANDOFF.generated.md",
    "run_ooda_design_supervisor_until_quiet",
    "ooda_design_supervisor.py",
    "TASK_LOCAL_TELEMETRY.generated.json",
    "operator telemetry",
    "supervisor status polling",
    "supervisor eta polling",
    "active-run telemetry",
    "active-run helper",
    "active run helper",
    "active worker run",
    "--telemetry-answer",
    "codexea --telemetry",
    "chummer_design_supervisor status",
    "chummer_design_supervisor eta",
    "chummer_design_supervisor.py",
    "chummer_design_supervisor.py status",
    "chummer_design_supervisor.py eta",
]


def _iso_now() -> str:
    return dt.datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _fixture_tree(tmp_path: Path) -> dict[str, Path]:
    root = tmp_path / "repo"
    published = root / ".codex-studio" / "published"
    registry = tmp_path / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
    design_queue = tmp_path / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    queue = published / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    weekly = published / "WEEKLY_PRODUCT_PULSE.generated.json"
    readiness = published / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    journeys = published / "JOURNEY_GATES.generated.json"
    support = published / "SUPPORT_CASE_PACKETS.generated.json"
    status = published / "STATUS_PLANE.generated.yaml"
    projects = root / "config" / "projects"
    projects.mkdir(parents=True, exist_ok=True)
    _write_yaml(projects / "fleet.yaml", {"id": "fleet", "path": str(root), "queue": []})
    for proof_anchor in (
        root / "scripts" / "materialize_weekly_governor_packet.py",
        root / "scripts" / "verify_next90_m106_fleet_governor_packet.py",
        root / "scripts" / "verify_script_bootstrap_no_pythonpath.py",
        root / "tests" / "test_materialize_weekly_governor_packet.py",
        root / "tests" / "test_fleet_script_bootstrap_without_pythonpath.py",
    ):
        proof_anchor.parent.mkdir(parents=True, exist_ok=True)
        proof_anchor.write_text("# fixture proof anchor\n", encoding="utf-8")
    _write_yaml(
        registry,
        {
            "product": "chummer",
            "program_wave": "next_90_day_product_advance",
            "waves": [
                {
                    "id": "W8",
                    "name": "Make continuity and product-governor boring",
                    "status": "in_progress",
                    "milestone_ids": [105, 106],
                }
            ],
            "milestones": [
                {
                    "id": 106,
                    "title": "Product-governor weekly adoption and measured rollout loop",
                    "status": "in_progress",
                    "owners": ["fleet", "executive-assistant", "chummer6-design", "chummer6-hub"],
                    "dependencies": [101, 102, 103, 104, 105],
                    "work_tasks": [
                        {
                            "id": "106.1",
                            "owner": "fleet",
                            "title": "Publish a weekly governor packet with launch, freeze, canary, rollback, and risk-cluster decisions.",
                            "status": "complete",
                            "evidence": [
                                "/docker/fleet/scripts/materialize_weekly_governor_packet.py compiles readiness inputs.",
                                "/docker/fleet/scripts/verify_next90_m106_fleet_governor_packet.py verifies the checked-in packet closeout without regenerating timestamps.",
                                "/docker/fleet/scripts/verify_script_bootstrap_no_pythonpath.py includes the standalone M106 verifier in no-PYTHONPATH bootstrap proof.",
                                "/docker/fleet/tests/test_materialize_weekly_governor_packet.py fail-closes drift.",
                                "/docker/fleet/tests/test_fleet_script_bootstrap_without_pythonpath.py launches the standalone M106 verifier help without PYTHONPATH.",
                                "/docker/fleet/.codex-studio/published/WEEKLY_GOVERNOR_PACKET.generated.json reports current decisions.",
                                "/docker/fleet/.codex-studio/published/WEEKLY_GOVERNOR_PACKET.generated.md mirrors the operator packet.",
                                "python3 -m py_compile scripts/materialize_weekly_governor_packet.py scripts/verify_next90_m106_fleet_governor_packet.py tests/test_materialize_weekly_governor_packet.py exits 0.",
                                "python3 -m py_compile scripts/verify_script_bootstrap_no_pythonpath.py tests/test_fleet_script_bootstrap_without_pythonpath.py exits 0.",
                                "python3 scripts/verify_next90_m106_fleet_governor_packet.py exits 0.",
                                "Direct tmp_path fixture invocation exits 0.",
                                "Verifier rebuilds the decision-critical packet projection from live source inputs.",
                                "Verifier rejects checked-in packet freshness drift against generated readiness, journey, support, weekly pulse, and status-plane inputs.",
                                "Verifier rejects compile manifest freshness drift after weekly packet refresh.",
                                "Verifier rejects support-packet source_sha256 drift against SUPPORT_CASE_PACKETS.generated.json.",
                                "Verifier requires every measured rollout action to appear in both the decision board and decision gate ledger.",
                                "status-plane final claim drift blocks launch expansion and measured rollout readiness.",
                                "forbidden worker proof strings are rejected case-insensitively.",
                                "Verifier rejects Fleet proof paths outside package allowed path roots.",
                                "no-PYTHONPATH bootstrap guard includes the standalone M106 verifier.",
                                "successor frontier 2376135131 is pinned for next90-m106-fleet-governor-packet repeat prevention.",
                                "local proof floor commit eeafd9e pinned for M106 governor packet repeat prevention.",
                                "do-not-reopen handoff routes remaining M106 work to dependency or sibling packages.",
                            ],
                        },
                        {
                            "id": "106.2",
                            "owner": "executive-assistant",
                            "title": "Synthesize support, parity, and release signals into operator-ready packets and reporter followthrough mail.",
                            "status": "complete",
                        },
                        {
                            "id": "106.3",
                            "owner": "chummer6-hub",
                            "title": "Expose install-aware support, status, and recovery surfaces downstream of the same release truth.",
                        },
                        {
                            "id": "106.4",
                            "owner": "chummer6-design",
                            "title": "Keep the successor wave registry current and prune closed work without reopening architecture-cleanup debt.",
                        },
                    ],
                }
            ],
        },
    )
    _write_yaml(
        queue,
        {
            "program_wave": "next_90_day_product_advance",
            "status": "live_parallel_successor",
            "source_registry_path": "/docker/chummercomplete/chummer-design/products/chummer/NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml",
            "source_design_queue_path": "/docker/chummercomplete/chummer-design/products/chummer/NEXT_90_DAY_QUEUE_STAGING.generated.yaml",
            "items": [
                {
                    "title": "Publish weekly governor packets with measured launch, freeze, canary, and rollback decisions",
                    "task": "Turn readiness, parity, support, and rollout truth into a weekly governor packet that drives measured product decisions.",
                    "package_id": "next90-m106-fleet-governor-packet",
                    "frontier_id": 2376135131,
                    "milestone_id": 106,
                    "wave": "W8",
                    "repo": "fleet",
                    "status": "complete",
                    "proof": [
                        "/docker/fleet/scripts/materialize_weekly_governor_packet.py",
                        "/docker/fleet/scripts/verify_next90_m106_fleet_governor_packet.py",
                        "/docker/fleet/scripts/verify_script_bootstrap_no_pythonpath.py",
                        "/docker/fleet/tests/test_materialize_weekly_governor_packet.py",
                        "/docker/fleet/tests/test_fleet_script_bootstrap_without_pythonpath.py",
                        "/docker/fleet/.codex-studio/published/WEEKLY_GOVERNOR_PACKET.generated.json",
                        "/docker/fleet/.codex-studio/published/WEEKLY_GOVERNOR_PACKET.generated.md",
                        "python3 -m py_compile scripts/materialize_weekly_governor_packet.py scripts/verify_next90_m106_fleet_governor_packet.py tests/test_materialize_weekly_governor_packet.py",
                        "python3 -m py_compile scripts/verify_script_bootstrap_no_pythonpath.py tests/test_fleet_script_bootstrap_without_pythonpath.py",
                        "python3 scripts/verify_next90_m106_fleet_governor_packet.py exits 0",
                        "direct tmp_path fixture invocation for tests/test_materialize_weekly_governor_packet.py exits 0",
                        "verifier rebuilds the decision-critical packet projection from live source inputs",
                        "verifier rejects checked-in packet freshness drift against generated readiness, journey, support, weekly pulse, and status-plane inputs",
                        "verifier rejects compile manifest freshness drift after weekly packet refresh",
                        "verifier rejects support-packet source_sha256 drift against SUPPORT_CASE_PACKETS.generated.json",
                        "verifier requires every measured rollout action to appear in both the decision board and decision gate ledger",
                        "status-plane final claim drift blocks launch expansion and measured rollout readiness",
                        "forbidden worker proof strings are rejected case-insensitively",
                        "verifier rejects Fleet proof paths outside package allowed path roots",
                        "no-PYTHONPATH bootstrap guard includes the standalone M106 verifier",
                        "successor frontier 2376135131 pinned for next90-m106-fleet-governor-packet repeat prevention",
                        "local proof floor commit eeafd9e pinned for M106 governor packet repeat prevention",
                        "do-not-reopen handoff routes remaining M106 work to dependency or sibling packages",
                    ],
                    "allowed_paths": ["admin", "scripts", "tests", ".codex-studio"],
                    "owned_surfaces": ["weekly_governor_packet", "measured_rollout_loop"],
                }
            ],
        },
    )
    design_queue_payload = yaml.safe_load(queue.read_text(encoding="utf-8"))
    design_queue_payload.pop("source_design_queue_path", None)
    _write_yaml(design_queue, design_queue_payload)
    _write_json(
        weekly,
        {
            "contract_name": "chummer.weekly_product_pulse",
            "contract_version": 3,
            "generated_at": _iso_now(),
            "as_of": "2026-04-15",
            "release_health": {"state": "green_or_explained"},
            "journey_gate_health": {"state": "ready"},
            "governor_decisions": [
                {
                    "decision_id": "launch",
                    "action": "freeze_launch",
                    "reason": "Freeze launch expansion until fresh local release proof passes.",
                    "cited_signals": [
                        "journey_gate_state=ready",
                        "journey_gate_blocked_count=0",
                        "local_release_proof_status=unknown",
                        "provider_canary_status=Canary evidence is still accumulating",
                        "closure_health_state=clear",
                    ],
                }
            ],
            "supporting_signals": {
                "provider_route_stewardship": {
                    "canary_status": "Canary evidence is still accumulating",
                    "next_decision": "Hold broad promotion until public route canary coverage exists.",
                },
                "closure_health": {"state": "clear"},
                "adoption_health": {"local_release_proof_status": "unknown"},
            },
            "top_support_or_feedback_clusters": [
                {"cluster_id": "release_truth", "summary": "Release proof controls launch."}
            ],
        },
    )
    _write_json(
        readiness,
        {
            "generated_at": _iso_now(),
            "status": "pass",
            "readiness_planes": {
                "flagship_ready": {
                    "status": "ready",
                    "evidence": {
                        "registry_path": "/docker/fleet/.codex-design/product/FLAGSHIP_PARITY_REGISTRY.yaml",
                        "registry_present": True,
                        "status_counts": {
                            "documented": 0,
                            "implemented": 0,
                            "task_proven": 0,
                            "veteran_approved": 0,
                            "gold_ready": 11,
                            "unknown": 0,
                        },
                        "families_below_task_proven": [],
                        "families_below_veteran_approved": [],
                        "families_below_gold_ready": [],
                    },
                }
            },
        },
    )
    _write_json(journeys, {"generated_at": _iso_now(), "summary": {"overall_state": "ready"}})
    _write_json(
        support,
        {
            "generated_at": _iso_now(),
            "summary": {
                "open_packet_count": 0,
                "open_non_external_packet_count": 0,
                "closure_waiting_on_release_truth": 0,
                "update_required_misrouted_case_count": 0,
                "reporter_followthrough_ready_count": 2,
                "fix_available_ready_count": 1,
                "please_test_ready_count": 1,
                "recovery_loop_ready_count": 0,
                "reporter_followthrough_blocked_missing_install_receipts_count": 0,
                "reporter_followthrough_blocked_receipt_mismatch_count": 0,
            },
            "followthrough_receipt_gates": {
                "ready_count": 2,
                "blocked_missing_install_receipts_count": 0,
                "blocked_receipt_mismatch_count": 0,
                "gate_counts": {
                    "installed_build_receipted": 2,
                    "installed_build_receipt_installation_bound": 2,
                },
            },
            "successor_package_verification": {
                "status": "pass",
                "package_id": "next90-m102-fleet-reporter-receipts",
            },
        },
    )
    _write_yaml(status, {"generated_at": _iso_now(), "whole_product_final_claim_status": "pass"})
    return {
        "root": root,
        "published": published,
        "registry": registry,
        "design_queue": design_queue,
        "queue": queue,
        "weekly": weekly,
        "readiness": readiness,
        "journeys": journeys,
        "support": support,
        "status": status,
    }


def _verifier_args(paths: dict[str, Path], packet: Path) -> list[str]:
    return [
        sys.executable,
        "/docker/fleet/scripts/verify_next90_m106_fleet_governor_packet.py",
        "--repo-root",
        str(paths["root"]),
        "--packet",
        str(packet),
        "--markdown",
        str(paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.md"),
        "--successor-registry",
        str(paths["registry"]),
        "--design-queue-staging",
        str(paths["design_queue"]),
        "--queue-staging",
        str(paths["queue"]),
        "--weekly-pulse",
        str(paths["weekly"]),
        "--flagship-readiness",
        str(paths["readiness"]),
        "--journey-gates",
        str(paths["journeys"]),
        "--support-packets",
        str(paths["support"]),
        "--status-plane",
        str(paths["status"]),
    ]


def _run_materializer(paths: dict[str, Path], out: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )


def test_materialize_weekly_governor_packet_freezes_when_canary_and_release_proof_are_not_green(tmp_path: Path) -> None:
    paths = _fixture_tree(tmp_path)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["contract_name"] == "fleet.weekly_governor_packet"
    assert payload["status"] == "ready"
    assert (
        payload["status_reason"]
        == "Fleet package is closed and the weekly measured rollout loop is ready."
    )
    assert payload["package_verification"]["status"] == "pass"
    assert payload["package_verification"]["registry_work_task_status"] == "complete"
    assert payload["package_verification"]["queue_status"] == "complete"
    assert (
        payload["package_verification"]["queue_source_registry_path"]
        == "/docker/chummercomplete/chummer-design/products/chummer/NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
    )
    assert (
        payload["package_verification"]["queue_source_design_queue_path"]
        == "/docker/chummercomplete/chummer-design/products/chummer/NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    )
    assert payload["package_verification"]["design_queue_status"] == "complete"
    assert payload["package_verification"]["queue_frontier_id"] == "2376135131"
    assert payload["package_verification"]["design_queue_frontier_id"] == "2376135131"
    assert payload["package_verification"]["queue_mirror_status"] == "in_sync"
    assert payload["package_verification"]["queue_mirror_drift"] == []
    assert (
        payload["package_verification"]["design_queue_source_registry_path"]
        == "/docker/chummercomplete/chummer-design/products/chummer/NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
    )
    assert payload["successor_frontier_ids"] == ["2376135131"]
    assert payload["package_verification"]["successor_frontier_ids"] == ["2376135131"]
    assert payload["package_verification"]["local_proof_floor_commits"] == [
        "065c653",
        "fb47ce8",
        "5e6a468",
        "f66dbaa",
        "f490e53",
        "e9ea391",
        "aefd72c",
        "21e00dd",
        "3eec697",
        "6fd5bfe",
        "3418b3c",
        "3580ba8",
        "eeafd9e",
    ]
    assert payload["package_verification"]["local_commit_resolution"]["status"] == "not_checked"
    assert payload["package_closeout"]["status"] == "fleet_package_complete"
    assert payload["package_closeout"]["do_not_reopen_package"] is True
    assert payload["package_closeout"]["successor_frontier_ids"] == ["2376135131"]
    assert payload["package_closeout"]["remaining_milestone_dependency_ids"] == [
        101,
        102,
        103,
        104,
        105,
    ]
    assert payload["package_closeout"]["remaining_sibling_work_task_ids"] == [
        "106.3",
        "106.4",
    ]
    assert (
        payload["package_closeout"]["milestone_106_still_open_because"]
        == "successor dependencies and sibling work tasks remain outside this Fleet package"
    )
    assert payload["repeat_prevention"]["status"] == "closed_for_fleet_package"
    assert payload["repeat_prevention"]["closed_package_id"] == "next90-m106-fleet-governor-packet"
    assert payload["repeat_prevention"]["closed_work_task_id"] == "106.1"
    assert payload["repeat_prevention"]["closed_successor_frontier_ids"] == ["2376135131"]
    assert payload["repeat_prevention"]["local_proof_floor_commits"] == [
        "065c653",
        "fb47ce8",
        "5e6a468",
        "f66dbaa",
        "f490e53",
        "e9ea391",
        "aefd72c",
        "21e00dd",
        "3eec697",
        "6fd5bfe",
        "3418b3c",
        "3580ba8",
        "eeafd9e",
    ]
    assert payload["repeat_prevention"]["local_commit_resolution"]["status"] == "not_checked"
    assert payload["repeat_prevention"]["do_not_reopen_owned_surfaces"] is True
    assert payload["repeat_prevention"]["owned_surfaces"] == [
        "weekly_governor_packet",
        "measured_rollout_loop",
    ]
    assert payload["repeat_prevention"]["remaining_dependency_ids"] == [101, 102, 103, 104, 105]
    assert payload["repeat_prevention"]["remaining_sibling_work_task_ids"] == ["106.3", "106.4"]
    assert (
        payload["repeat_prevention"]["worker_command_guard"]["status"]
        == "active_run_helpers_forbidden"
    )
    assert payload["repeat_prevention"]["worker_command_guard"]["blocked_markers"] == BLOCKED_WORKER_PROOF_MARKERS
    assert (
        payload["repeat_prevention"]["flagship_wave_guard"]["status"]
        == "closed_wave_not_reopened"
    )
    assert (
        payload["repeat_prevention"]["flagship_wave_guard"]["closed_wave"]
        == "next_12_biggest_wins"
    )
    assert (
        "must not reopen"
        in payload["repeat_prevention"]["flagship_wave_guard"]["rule"]
    )
    assert payload["weekly_input_health"]["status"] == "pass"
    assert payload["source_input_health"]["status"] == "pass"
    assert payload["decision_alignment"]["status"] == "pass"
    assert payload["decision_alignment"]["expected_action"] == "freeze_launch"
    assert payload["decision_alignment"]["actual_action"] == "freeze_launch"
    assert payload["source_input_health"]["required_inputs"]["flagship_readiness"]["state"] == "present"
    assert payload["source_input_health"]["required_inputs"]["design_queue_staging"]["state"] == "present"
    assert (
        payload["source_input_health"]["required_inputs"]["support_packets"]["source_sha256"]
        == hashlib.sha256(paths["support"].read_bytes()).hexdigest()
    )
    assert payload["package_verification"]["registry_dependencies"] == [101, 102, 103, 104, 105]
    assert payload["truth_inputs"]["successor_dependency_status"] == "open"
    assert payload["decision_board"]["launch_expand"]["state"] == "blocked"
    assert payload["decision_board"]["freeze_launch"]["state"] == "active"
    assert payload["decision_board"]["canary"]["state"] == "accumulating"
    assert payload["decision_board"]["rollback"]["state"] == "armed"
    assert payload["decision_board"]["focus_shift"]["state"] == "queued_successor_wave"
    assert payload["truth_inputs"]["flagship_parity_release_truth"]["release_truth_status"] == "gold_ready"
    launch_gates = {
        row["name"]: row for row in payload["decision_gate_ledger"]["launch_expand"]
    }
    assert launch_gates["local_release_proof"]["state"] == "blocked"
    assert launch_gates["provider_canary"]["state"] == "blocked"
    assert launch_gates["successor_dependencies"]["observed"] == "open"
    assert launch_gates["status_plane_final_claim"]["state"] == "pass"
    focus_shift_gates = {
        row["name"]: row for row in payload["decision_gate_ledger"]["focus_shift"]
    }
    assert focus_shift_gates["successor_wave_scope"]["state"] == "queued_successor_wave"
    assert (
        focus_shift_gates["successor_wave_scope"]["observed"]
        == "next90-m106-fleet-governor-packet"
    )
    assert payload["public_status_copy"]["state"] == "freeze_launch"
    assert payload["public_status_copy"]["headline"] == "Launch expansion remains frozen."
    assert payload["truth_inputs"]["support_summary"]["reporter_followthrough_ready_count"] == 2
    assert payload["truth_inputs"]["support_summary"]["fix_available_ready_count"] == 1
    assert payload["truth_inputs"]["support_summary"]["please_test_ready_count"] == 1
    assert payload["truth_inputs"]["support_summary"]["followthrough_receipt_gates_ready_count"] == 2
    assert (
        payload["truth_inputs"]["support_summary"]["followthrough_receipt_gates_installed_build_receipted_count"]
        == 2
    )
    assert payload["truth_inputs"]["support_summary"]["followthrough_receipt_gates_installation_bound_count"] == 2
    assert payload["measured_rollout_loop"]["loop_status"] == "ready"
    assert payload["measured_rollout_loop"]["required_decision_actions"] == [
        "launch_expand",
        "freeze_launch",
        "canary",
        "rollback",
        "focus_shift",
    ]
    assert [row["action"] for row in payload["governor_decisions"]] == [
        "launch_expand",
        "freeze_launch",
        "canary",
        "rollback",
        "focus_shift",
    ]
    governor_decisions = {
        row["action"]: row for row in payload["governor_decisions"]
    }
    assert governor_decisions["launch_expand"]["state"] == "blocked"
    assert governor_decisions["freeze_launch"]["state"] == "active"
    assert governor_decisions["canary"]["state"] == "accumulating"
    assert governor_decisions["rollback"]["gate_count"] == 3
    assert governor_decisions["focus_shift"]["gate_count"] == 1
    markdown = (paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.md").read_text(encoding="utf-8")
    assert "# Weekly Governor Packet" in markdown
    assert "| Launch expand | blocked |" in markdown
    assert "| Freeze launch | active |" in markdown
    assert "## Public Status Copy" in markdown
    assert "## Launch Gate Ledger" in markdown
    assert "| local_release_proof | blocked | passed | unknown |" in markdown
    assert "- Successor dependency posture: open" in markdown
    assert "- Package closeout: fleet_package_complete" in markdown
    assert "- Decision alignment: pass" in markdown
    assert "| decision_alignment | pass | freeze_launch | freeze_launch |" in markdown
    assert "- Do not reopen package: True" in markdown
    assert "## Repeat Prevention" in markdown
    assert "- Status: closed_for_fleet_package" in markdown
    assert "- Closed package: next90-m106-fleet-governor-packet" in markdown
    assert "- Closed work task: 106.1" in markdown
    assert "- Closed successor frontier ids: 2376135131" in markdown
    assert "- Local proof floor commits: 065c653, fb47ce8, 5e6a468, f66dbaa, f490e53, e9ea391, aefd72c, 21e00dd, 3eec697, 6fd5bfe, 3418b3c, 3580ba8, eeafd9e" in markdown
    assert "- Do not reopen owned surfaces: True" in markdown
    assert "- Worker command guard: active_run_helpers_forbidden" in markdown
    assert f"- Blocked helper markers: {', '.join(BLOCKED_WORKER_PROOF_MARKERS)}" in markdown
    assert "- Flagship wave guard: closed_wave_not_reopened" in markdown
    assert "- Closed flagship wave: next_12_biggest_wins" in markdown
    assert "- Remaining sibling work tasks: 106.3, 106.4" in markdown
    assert "- Registry work task 106.1 status: complete" in markdown
    assert (
        "- Required resolving proof paths: "
        "scripts/materialize_weekly_governor_packet.py, "
        "scripts/verify_next90_m106_fleet_governor_packet.py, "
        "scripts/verify_script_bootstrap_no_pythonpath.py, "
        "tests/test_materialize_weekly_governor_packet.py, "
        "tests/test_fleet_script_bootstrap_without_pythonpath.py"
    ) in markdown
    assert "- Queue mirror status: in_sync" in markdown
    assert "- Provider canary: Canary evidence is still accumulating" in markdown
    assert "- Reporter followthrough ready: 2" in markdown
    assert "- Fix-available ready: 1" in markdown
    assert "- Please-test ready: 1" in markdown
    assert "- Receipt-gated followthrough ready: 2" in markdown
    assert "- Receipt-gated installed-build receipts: 2" in markdown
    assert "- design-owned queue staging and Fleet queue mirror both carry the completed package proof" in markdown
    assert "- status-plane final claim remains pass before launch expansion or measured rollout readiness" in markdown
    manifest = json.loads((paths["published"] / "compile.manifest.json").read_text(encoding="utf-8"))
    assert "WEEKLY_GOVERNOR_PACKET.generated.json" in manifest["artifacts"]
    assert "WEEKLY_GOVERNOR_PACKET.generated.md" in manifest["artifacts"]


def test_weekly_governor_packet_blocks_launch_expand_when_successor_dependencies_are_open(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    weekly = json.loads(paths["weekly"].read_text(encoding="utf-8"))
    weekly["governor_decisions"][0]["action"] = "launch_expand"
    weekly["governor_decisions"][0]["reason"] = "Expand launch only when every measured gate is green."
    weekly["governor_decisions"][0]["cited_signals"] = [
        "journey_gate_state=ready",
        "journey_gate_blocked_count=0",
        "local_release_proof_status=passed",
        "provider_canary_status=Canary green on all active lanes",
        "closure_health_state=clear",
    ]
    weekly["supporting_signals"]["provider_route_stewardship"] = {
        "canary_status": "Canary green on all active lanes",
        "next_decision": "Expand only after dependency closure is canonical.",
    }
    weekly["supporting_signals"]["adoption_health"] = {"local_release_proof_status": "passed"}
    _write_json(paths["weekly"], weekly)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["weekly_input_health"]["status"] == "pass"
    assert payload["decision_alignment"]["status"] == "fail"
    assert payload["decision_alignment"]["expected_action"] == "freeze_launch"
    assert payload["decision_alignment"]["actual_action"] == "launch_expand"
    assert (
        "weekly pulse launch action launch_expand does not match measured gate action freeze_launch"
        in payload["decision_alignment"]["issues"]
    )
    assert payload["truth_inputs"]["successor_dependency_status"] == "open"
    assert payload["truth_inputs"]["successor_dependency_posture"]["missing_dependency_ids"] == [
        101,
        102,
        103,
        104,
        105,
    ]
    assert payload["decision_board"]["current_launch_action"] == "launch_expand"
    assert payload["decision_board"]["launch_expand"]["state"] == "blocked"
    assert "successor dependencies" in payload["decision_board"]["launch_expand"]["reason"]
    launch_gates = {
        row["name"]: row for row in payload["decision_gate_ledger"]["launch_expand"]
    }
    assert launch_gates["successor_dependencies"]["state"] == "blocked"
    assert launch_gates["decision_alignment"]["state"] == "fail"
    assert payload["public_status_copy"]["state"] == "freeze_launch"
    assert payload["measured_rollout_loop"]["loop_status"] == "blocked"


def test_weekly_governor_packet_blocks_launch_expand_when_status_plane_final_claim_regresses(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    registry = yaml.safe_load(paths["registry"].read_text(encoding="utf-8"))
    registry["milestones"] = [
        {
            "id": dep_id,
            "title": f"Dependency {dep_id}",
            "status": "complete",
            "owners": ["fleet"],
        }
        for dep_id in (101, 102, 103, 104, 105)
    ] + registry["milestones"]
    _write_yaml(paths["registry"], registry)
    weekly = json.loads(paths["weekly"].read_text(encoding="utf-8"))
    weekly["governor_decisions"][0]["action"] = "launch_expand"
    weekly["governor_decisions"][0]["reason"] = "All measured gates are green."
    weekly["governor_decisions"][0]["cited_signals"] = [
        "journey_gate_state=ready",
        "journey_gate_blocked_count=0",
        "local_release_proof_status=passed",
        "provider_canary_status=Canary green on all active lanes",
        "closure_health_state=clear",
    ]
    weekly["supporting_signals"]["provider_route_stewardship"] = {
        "canary_status": "Canary green on all active lanes",
        "next_decision": "Continue weekly launch expansion.",
    }
    weekly["supporting_signals"]["adoption_health"] = {"local_release_proof_status": "passed"}
    _write_json(paths["weekly"], weekly)
    status = yaml.safe_load(paths["status"].read_text(encoding="utf-8"))
    status["whole_product_final_claim_status"] = "fail"
    _write_yaml(paths["status"], status)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"

    result = _run_materializer(paths, out)

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["truth_inputs"]["status_plane_final_claim"] == "fail"
    assert payload["decision_alignment"]["status"] == "fail"
    assert payload["decision_alignment"]["expected_action"] == "freeze_launch"
    assert payload["decision_board"]["launch_expand"]["state"] == "blocked"
    assert "status-plane final claim" in payload["decision_board"]["launch_expand"]["reason"]
    launch_gates = {
        row["name"]: row for row in payload["decision_gate_ledger"]["launch_expand"]
    }
    assert launch_gates["status_plane_final_claim"]["state"] == "blocked"
    assert launch_gates["status_plane_final_claim"]["observed"] == "fail"
    assert payload["measured_rollout_loop"]["loop_status"] == "blocked"


def test_verify_next90_m106_governor_packet_accepts_checked_in_closeout(tmp_path: Path) -> None:
    paths = _fixture_tree(tmp_path)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"
    materialize = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )
    assert materialize.returncode == 0, materialize.stderr

    verifier = subprocess.run(
        _verifier_args(paths, out),
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )
    assert verifier.returncode == 0, verifier.stderr
    assert "verified next90-m106-fleet-governor-packet" in verifier.stdout


def test_verify_next90_m106_governor_packet_accepts_source_blocked_freeze_packet(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    support = json.loads(paths["support"].read_text(encoding="utf-8"))
    support["successor_package_verification"] = {
        "status": "fail",
        "issues": ["queue proof missing receipt-gated M102 marker"],
    }
    _write_json(paths["support"], support)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"

    materialize = _run_materializer(paths, out)
    assert materialize.returncode == 0, materialize.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["package_verification"]["status"] == "pass"
    assert payload["source_input_health"]["status"] == "fail"
    assert payload["status"] == "blocked"
    assert payload["decision_board"]["current_launch_action"] == "freeze_launch"
    assert payload["measured_rollout_loop"]["loop_status"] == "blocked"

    verifier = subprocess.run(
        _verifier_args(paths, out),
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert verifier.returncode == 0, verifier.stderr
    assert "verified next90-m106-fleet-governor-packet" in verifier.stdout


def test_verify_next90_m106_governor_packet_rejects_stale_embedded_verification(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"
    materialize = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )
    assert materialize.returncode == 0, materialize.stderr

    packet = json.loads(out.read_text(encoding="utf-8"))
    packet["package_verification"]["registry_milestone_title"] = "stale title"
    _write_json(out, packet)

    verifier = subprocess.run(
        _verifier_args(paths, out),
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert verifier.returncode == 1
    assert (
        "packet package_verification no longer matches live successor registry and queue verification"
        in verifier.stderr
    )


def test_verify_next90_m106_governor_packet_rejects_support_source_hash_drift(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"
    materialize = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )
    assert materialize.returncode == 0, materialize.stderr

    packet = json.loads(out.read_text(encoding="utf-8"))
    packet["source_input_health"]["required_inputs"]["support_packets"]["source_sha256"] = "0" * 64
    _write_json(out, packet)

    verifier = subprocess.run(
        _verifier_args(paths, out),
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert verifier.returncode == 1
    assert (
        "packet support_packets source_sha256 no longer matches SUPPORT_CASE_PACKETS.generated.json"
        in verifier.stderr
    )


def test_verify_next90_m106_governor_packet_rejects_packet_identity_drift(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"
    materialize = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )
    assert materialize.returncode == 0, materialize.stderr

    packet = json.loads(out.read_text(encoding="utf-8"))
    packet["program_wave"] = "next_12_biggest_wins"
    packet["wave_id"] = "W5"
    packet["schema_version"] = 0
    _write_json(out, packet)

    verifier = subprocess.run(
        _verifier_args(paths, out),
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert verifier.returncode == 1
    assert (
        "checked-in packet decision ledger no longer matches live source inputs for field(s): "
        in verifier.stderr
    )
    assert "program_wave" in verifier.stderr
    assert "wave_id" in verifier.stderr
    assert "schema_version" in verifier.stderr


def test_weekly_governor_packet_fails_package_verification_on_package_meaning_drift(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"
    registry = yaml.safe_load(paths["registry"].read_text(encoding="utf-8"))
    design_queue = yaml.safe_load(paths["design_queue"].read_text(encoding="utf-8"))
    queue = yaml.safe_load(paths["queue"].read_text(encoding="utf-8"))
    registry["milestones"][0]["title"] = "A different milestone"
    for payload in (design_queue, queue):
        item = next(
            row
            for row in payload["items"]
            if row["package_id"] == "next90-m106-fleet-governor-packet"
        )
        item["title"] = "A different package title"
        item["task"] = "A different package task."
    _write_yaml(paths["registry"], registry)
    _write_yaml(paths["design_queue"], design_queue)
    _write_yaml(paths["queue"], queue)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["package_verification"]["status"] == "fail"
    assert "milestone 106 title no longer matches package authority" in payload["package_verification"]["issues"]
    assert "design queue item title no longer matches package authority" in payload["package_verification"]["issues"]
    assert "design queue item task no longer matches package authority" in payload["package_verification"]["issues"]
    assert "queue item title no longer matches package authority" in payload["package_verification"]["issues"]
    assert "queue item task no longer matches package authority" in payload["package_verification"]["issues"]


def test_verify_next90_m106_governor_packet_rejects_stale_decision_ledger(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"
    materialize = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )
    assert materialize.returncode == 0, materialize.stderr

    packet = json.loads(out.read_text(encoding="utf-8"))
    packet["decision_board"]["launch_expand"]["state"] = "allowed"
    _write_json(out, packet)

    verifier = subprocess.run(
        _verifier_args(paths, out),
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert verifier.returncode == 1
    assert (
        "checked-in packet decision ledger no longer matches live source inputs for field(s): "
        in verifier.stderr
    )
    assert "decision_board" in verifier.stderr


def test_verify_next90_m106_governor_packet_rejects_packet_older_than_support_source(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"
    materialize = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )
    assert materialize.returncode == 0, materialize.stderr

    packet = json.loads(out.read_text(encoding="utf-8"))
    support = json.loads(paths["support"].read_text(encoding="utf-8"))
    packet["generated_at"] = "2026-04-15T10:00:00Z"
    support["generated_at"] = "2026-04-15T10:00:01Z"
    _write_json(out, packet)
    _write_json(paths["support"], support)

    verifier = subprocess.run(
        _verifier_args(paths, out),
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert verifier.returncode == 1
    assert (
        "checked-in packet generated_at predates support_packets; regenerate "
        "WEEKLY_GOVERNOR_PACKET.generated.json after refreshing source inputs"
        in verifier.stderr
    )


def test_verify_next90_m106_governor_packet_rejects_packet_older_than_status_plane(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"
    materialize = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )
    assert materialize.returncode == 0, materialize.stderr

    packet = json.loads(out.read_text(encoding="utf-8"))
    status = yaml.safe_load(paths["status"].read_text(encoding="utf-8"))
    packet["generated_at"] = "2026-04-15T10:00:00Z"
    status["generated_at"] = "2026-04-15T10:00:01Z"
    _write_json(out, packet)
    _write_yaml(paths["status"], status)

    verifier = subprocess.run(
        _verifier_args(paths, out),
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert verifier.returncode == 1
    assert (
        "checked-in packet generated_at predates status_plane; regenerate "
        "WEEKLY_GOVERNOR_PACKET.generated.json after refreshing source inputs"
        in verifier.stderr
    )


def test_verify_next90_m106_governor_packet_rejects_worker_guard_drift(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"
    materialize = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )
    assert materialize.returncode == 0, materialize.stderr

    packet = json.loads(out.read_text(encoding="utf-8"))
    packet["repeat_prevention"]["worker_command_guard"]["status"] = "missing"
    packet["repeat_prevention"]["worker_command_guard"]["blocked_markers"] = []
    packet["repeat_prevention"]["worker_command_guard"]["rule"] = "proof may cite handoff telemetry"
    _write_json(out, packet)

    verifier = subprocess.run(
        _verifier_args(paths, out),
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert verifier.returncode == 1
    assert (
        "repeat prevention worker command guard is not active_run_helpers_forbidden"
        in verifier.stderr
    )
    assert (
        "repeat prevention worker command guard blocked marker list drifted"
        in verifier.stderr
    )
    assert (
        "repeat prevention worker command guard rule no longer requires repo-local proof"
        in verifier.stderr
    )


def test_verify_next90_m106_governor_packet_rejects_out_of_scope_fleet_proof_paths(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"
    design_queue = yaml.safe_load(paths["design_queue"].read_text(encoding="utf-8"))
    queue = yaml.safe_load(paths["queue"].read_text(encoding="utf-8"))
    registry = yaml.safe_load(paths["registry"].read_text(encoding="utf-8"))
    for payload in (design_queue, queue):
        item = next(
            row
            for row in payload["items"]
            if row["package_id"] == "next90-m106-fleet-governor-packet"
        )
        item["proof"].append("/docker/fleet/README.md is not inside this package scope")
    registry_task = registry["milestones"][0]["work_tasks"][0]
    registry_task["evidence"].append(
        "/docker/fleet/README.md is not inside this package scope"
    )
    _write_yaml(paths["design_queue"], design_queue)
    _write_yaml(paths["queue"], queue)
    _write_yaml(paths["registry"], registry)

    materialize = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )
    assert materialize.returncode == 0, materialize.stderr

    verifier = subprocess.run(
        _verifier_args(paths, out),
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert verifier.returncode == 1
    assert "outside allowed package roots" in verifier.stderr
    assert "/docker/fleet/README.md" in verifier.stderr


def test_weekly_governor_packet_rejects_embedded_out_of_scope_fleet_proof_paths(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    queue = yaml.safe_load(paths["queue"].read_text(encoding="utf-8"))
    queue["items"][0]["proof"].append(
        "proof bundle cites /docker/fleet/README.md after scoped anchors"
    )
    _write_yaml(paths["queue"], queue)
    registry = yaml.safe_load(paths["registry"].read_text(encoding="utf-8"))
    registry["milestones"][0]["work_tasks"][0]["evidence"].append(
        "registry note cites /docker/fleet/docker-compose.yml after scoped anchors"
    )
    _write_yaml(paths["registry"], registry)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["package_verification"]["status"] == "fail"
    assert payload["package_closeout"]["status"] == "blocked"
    assert any(
        "queue item proof includes Fleet proof path(s) outside allowed package roots"
        in issue
        and "/docker/fleet/README.md" in issue
        for issue in payload["package_verification"]["issues"]
    )
    assert any(
        "registry work task 106.1 evidence includes Fleet proof path(s) outside allowed package roots"
        in issue
        and "/docker/fleet/docker-compose.yml" in issue
        for issue in payload["package_verification"]["issues"]
    )


def test_weekly_governor_packet_rejects_sibling_repo_proof_paths(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    queue = yaml.safe_load(paths["queue"].read_text(encoding="utf-8"))
    queue["items"][0]["proof"].append(
        "/docker/EA/docs/chummer_governor_packets/README.md belongs to a sibling package"
    )
    _write_yaml(paths["queue"], queue)
    registry = yaml.safe_load(paths["registry"].read_text(encoding="utf-8"))
    registry["milestones"][0]["work_tasks"][0]["evidence"].append(
        "registry note cites /docker/chummercomplete/chummer.run-services/README.md as Fleet closeout proof"
    )
    _write_yaml(paths["registry"], registry)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["package_verification"]["status"] == "fail"
    assert payload["package_closeout"]["status"] == "blocked"
    assert any(
        "queue item proof includes Fleet proof path(s) outside allowed package roots"
        in issue
        and "/docker/EA/docs/chummer_governor_packets/README.md" in issue
        for issue in payload["package_verification"]["issues"]
    )
    assert any(
        "registry work task 106.1 evidence includes Fleet proof path(s) outside allowed package roots"
        in issue
        and "/docker/chummercomplete/chummer.run-services/README.md" in issue
        for issue in payload["package_verification"]["issues"]
    )


def test_verify_next90_m106_governor_packet_rejects_flagship_reopen_guard_drift(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"
    materialize = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )
    assert materialize.returncode == 0, materialize.stderr

    packet = json.loads(out.read_text(encoding="utf-8"))
    packet["repeat_prevention"]["flagship_wave_guard"] = {
        "status": "reopen_allowed",
        "closed_wave": "next_12_biggest_wins",
        "rule": "successor workers may reopen flagship scope",
    }
    _write_json(out, packet)

    verifier = subprocess.run(
        _verifier_args(paths, out),
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert verifier.returncode == 1
    assert (
        "repeat prevention flagship wave guard is not closed_wave_not_reopened"
        in verifier.stderr
    )
    assert (
        "repeat prevention flagship wave guard rule no longer blocks reopening the closed flagship wave"
        in verifier.stderr
    )


def test_verify_next90_m106_governor_packet_rejects_resolving_proof_path_drift(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"
    materialize = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )
    assert materialize.returncode == 0, materialize.stderr

    packet = json.loads(out.read_text(encoding="utf-8"))
    packet["package_verification"]["required_resolving_proof_paths"] = [
        "scripts/materialize_weekly_governor_packet.py"
    ]
    _write_json(out, packet)

    verifier = subprocess.run(
        _verifier_args(paths, out),
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert verifier.returncode == 1
    assert "packet required_resolving_proof_paths drifted" in verifier.stderr


def test_verify_next90_m106_governor_packet_rejects_local_proof_floor_drift(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"
    materialize = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )
    assert materialize.returncode == 0, materialize.stderr

    packet = json.loads(out.read_text(encoding="utf-8"))
    packet["package_verification"]["local_proof_floor_commits"] = ["stale"]
    packet["repeat_prevention"]["local_proof_floor_commits"] = ["stale"]
    _write_json(out, packet)

    verifier = subprocess.run(
        _verifier_args(paths, out),
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert verifier.returncode == 1
    assert "packet local proof floor commit list drifted" in verifier.stderr
    assert "repeat prevention local proof floor commit list drifted" in verifier.stderr


def test_verify_next90_m106_governor_packet_rejects_compile_manifest_artifact_drift(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"
    materialize = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )
    assert materialize.returncode == 0, materialize.stderr

    manifest_path = paths["published"] / "compile.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"] = [
        artifact
        for artifact in manifest["artifacts"]
        if artifact != "WEEKLY_GOVERNOR_PACKET.generated.md"
    ]
    _write_json(manifest_path, manifest)

    verifier = subprocess.run(
        _verifier_args(paths, out),
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert verifier.returncode == 1
    assert (
        "compile manifest does not list weekly governor packet artifact(s): "
        "WEEKLY_GOVERNOR_PACKET.generated.md"
        in verifier.stderr
    )


def test_verify_next90_m106_governor_packet_rejects_stale_compile_manifest(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"
    materialize = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )
    assert materialize.returncode == 0, materialize.stderr

    manifest_path = paths["published"] / "compile.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["published_at"] = "2026-04-14T00:00:00Z"
    _write_json(manifest_path, manifest)

    verifier = subprocess.run(
        _verifier_args(paths, out),
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert verifier.returncode == 1
    assert (
        "compile.manifest.json published_at predates "
        "WEEKLY_GOVERNOR_PACKET.generated.json; regenerate compile.manifest.json "
        "after refreshing the weekly governor packet"
        in verifier.stderr
    )


def test_verify_next90_m106_governor_packet_rejects_closeout_handoff_drift(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"
    materialize = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )
    assert materialize.returncode == 0, materialize.stderr

    packet = json.loads(out.read_text(encoding="utf-8"))
    packet["package_closeout"]["status"] = "reopen"
    packet["package_closeout"]["do_not_reopen_package"] = False
    packet["package_closeout"]["remaining_milestone_dependency_ids"] = []
    packet["package_closeout"]["remaining_sibling_work_task_ids"] = []
    packet["repeat_prevention"]["remaining_dependency_ids"] = []
    packet["repeat_prevention"]["remaining_sibling_work_task_ids"] = []
    packet["repeat_prevention"]["handoff_rule"] = "repeat this package on the next shard"
    _write_json(out, packet)

    verifier = subprocess.run(
        _verifier_args(paths, out),
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert verifier.returncode == 1
    assert "package closeout is not fleet_package_complete" in verifier.stderr
    assert (
        "package closeout no longer marks this Fleet slice do-not-reopen"
        in verifier.stderr
    )
    assert (
        "package closeout remaining dependency list no longer matches live successor registry posture"
        in verifier.stderr
    )
    assert (
        "repeat prevention remaining dependency list no longer matches live successor registry posture"
        in verifier.stderr
    )
    assert (
        "repeat prevention remaining sibling list no longer matches package closeout posture"
        in verifier.stderr
    )
    assert (
        "package closeout remaining sibling list no longer matches live successor registry posture"
        in verifier.stderr
    )
    assert (
        "repeat prevention handoff rule no longer routes remaining M106 work away from this closed Fleet slice"
        in verifier.stderr
    )
    assert (
        "repeat prevention handoff rule no longer matches the live closeout projection"
        in verifier.stderr
    )


def test_verify_next90_m106_governor_packet_rejects_missing_decision_action_ledger(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"
    materialize = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )
    assert materialize.returncode == 0, materialize.stderr

    packet = json.loads(out.read_text(encoding="utf-8"))
    packet["measured_rollout_loop"]["required_decision_actions"] = [
        "launch_expand",
        "freeze_launch",
        "canary",
        "rollback",
        "focus_shift",
    ]
    packet["decision_board"].pop("focus_shift")
    packet["decision_gate_ledger"].pop("focus_shift")
    packet["governor_decisions"] = [
        row for row in packet["governor_decisions"] if row["action"] != "focus_shift"
    ]
    _write_json(out, packet)

    verifier = subprocess.run(
        _verifier_args(paths, out),
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert verifier.returncode == 1
    assert "decision board is missing required action(s): focus_shift" in verifier.stderr
    assert "decision gate ledger is missing required action(s): focus_shift" in verifier.stderr
    assert (
        "governor decision projection is missing required action(s): focus_shift"
        in verifier.stderr
    )


def test_verify_next90_m106_governor_packet_rejects_stale_markdown_packet(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"
    materialize = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )
    assert materialize.returncode == 0, materialize.stderr

    markdown = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.md"
    markdown.write_text(
        markdown.read_text(encoding="utf-8").replace(
            "| Launch expand | blocked |",
            "| Launch expand | allowed |",
        ),
        encoding="utf-8",
    )

    verifier = subprocess.run(
        _verifier_args(paths, out),
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert verifier.returncode == 1
    assert (
        "checked-in markdown packet no longer matches the live source-input projection"
        in verifier.stderr
    )


def test_weekly_governor_packet_allows_launch_expand_when_dependencies_and_gates_are_green(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    registry = yaml.safe_load(paths["registry"].read_text(encoding="utf-8"))
    registry["milestones"] = [
        {
            "id": dep_id,
            "title": f"Dependency {dep_id}",
            "status": "complete",
            "owners": ["fleet"],
        }
        for dep_id in (101, 102, 103, 104, 105)
    ] + registry["milestones"]
    _write_yaml(paths["registry"], registry)
    weekly = json.loads(paths["weekly"].read_text(encoding="utf-8"))
    weekly["governor_decisions"][0]["action"] = "launch_expand"
    weekly["governor_decisions"][0]["reason"] = "All measured gates are green."
    weekly["governor_decisions"][0]["cited_signals"] = [
        "journey_gate_state=ready",
        "journey_gate_blocked_count=0",
        "local_release_proof_status=passed",
        "provider_canary_status=Canary green on all active lanes",
        "closure_health_state=clear",
    ]
    weekly["supporting_signals"]["provider_route_stewardship"] = {
        "canary_status": "Canary green on all active lanes",
        "next_decision": "Continue weekly launch expansion.",
    }
    weekly["supporting_signals"]["adoption_health"] = {"local_release_proof_status": "passed"}
    _write_json(paths["weekly"], weekly)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["truth_inputs"]["successor_dependency_status"] == "satisfied"
    assert payload["decision_alignment"]["status"] == "pass"
    assert payload["decision_alignment"]["expected_action"] == "launch_expand"
    assert payload["decision_alignment"]["actual_action"] == "launch_expand"
    assert payload["decision_board"]["current_launch_action"] == "launch_expand"
    assert payload["decision_board"]["launch_expand"]["state"] == "allowed"
    assert payload["decision_board"]["freeze_launch"]["state"] == "available"
    assert payload["decision_board"]["rollback"]["state"] == "armed"
    assert payload["public_status_copy"]["state"] == "launch_expand_allowed"
    assert {
        row["action"]: row["state"] for row in payload["governor_decisions"]
    } == {
        "launch_expand": "allowed",
        "freeze_launch": "available",
        "canary": "ready",
        "rollback": "armed",
        "focus_shift": "queued_successor_wave",
    }
    launch_gates = {
        row["name"]: row for row in payload["decision_gate_ledger"]["launch_expand"]
    }
    assert all(row["state"] == "pass" for row in launch_gates.values())
    markdown = (paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.md").read_text(encoding="utf-8")
    assert "| Launch expand | allowed |" in markdown
    assert "- Successor dependency posture: satisfied" in markdown


def test_weekly_governor_packet_fails_package_verification_on_queue_authority_drift(tmp_path: Path) -> None:
    paths = _fixture_tree(tmp_path)
    queue = yaml.safe_load(paths["queue"].read_text(encoding="utf-8"))
    queue["items"][0]["allowed_paths"] = ["scripts"]
    _write_yaml(paths["queue"], queue)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["status"] == "blocked"
    assert (
        payload["status_reason"]
        == "Fleet package closeout or measured rollout loop verification is blocked."
    )
    assert payload["package_verification"]["status"] == "fail"
    assert payload["package_closeout"]["status"] == "blocked"
    assert payload["package_closeout"]["do_not_reopen_package"] is False
    assert payload["repeat_prevention"]["status"] == "blocked"
    assert payload["repeat_prevention"]["do_not_reopen_owned_surfaces"] is False
    assert "queue item allowed_paths no longer match package authority" in payload["package_verification"]["issues"]
    assert payload["measured_rollout_loop"]["loop_status"] == "blocked"


def test_weekly_governor_packet_fails_package_verification_on_design_queue_drift(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    design_queue = yaml.safe_load(paths["design_queue"].read_text(encoding="utf-8"))
    design_queue["items"][0]["status"] = "in_progress"
    design_queue["items"][0]["proof"] = [
        proof
        for proof in design_queue["items"][0]["proof"]
        if "successor frontier 2376135131" not in proof
    ]
    _write_yaml(paths["design_queue"], design_queue)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["package_verification"]["status"] == "fail"
    assert "design queue item is not marked complete" in payload["package_verification"]["issues"]
    assert (
        "design queue item proof is missing required weekly governor receipt(s): "
        "successor frontier 2376135131 pinned for next90-m106-fleet-governor-packet repeat prevention"
        in payload["package_verification"]["issues"]
    )
    assert payload["package_closeout"]["status"] == "blocked"
    assert payload["repeat_prevention"]["status"] == "blocked"
    assert payload["measured_rollout_loop"]["loop_status"] == "blocked"


def test_weekly_governor_packet_fails_package_verification_on_missing_structured_frontier_id(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    design_queue = yaml.safe_load(paths["design_queue"].read_text(encoding="utf-8"))
    queue = yaml.safe_load(paths["queue"].read_text(encoding="utf-8"))
    design_queue["items"][0].pop("frontier_id")
    queue["items"][0].pop("frontier_id")
    _write_yaml(paths["design_queue"], design_queue)
    _write_yaml(paths["queue"], queue)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["package_verification"]["status"] == "fail"
    assert (
        "design queue item frontier_id does not match successor frontier 2376135131"
        in payload["package_verification"]["issues"]
    )
    assert (
        "queue item frontier_id does not match successor frontier 2376135131"
        in payload["package_verification"]["issues"]
    )
    assert payload["repeat_prevention"]["status"] == "blocked"
    assert payload["measured_rollout_loop"]["loop_status"] == "blocked"


def test_weekly_governor_packet_fails_package_verification_on_duplicate_queue_rows(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    queue = yaml.safe_load(paths["queue"].read_text(encoding="utf-8"))
    queue["items"].append(dict(queue["items"][0]))
    _write_yaml(paths["queue"], queue)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"

    result = _run_materializer(paths, out)

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["package_verification"]["status"] == "fail"
    assert (
        "queue staging has duplicate package rows for next90-m106-fleet-governor-packet"
        in payload["package_verification"]["issues"]
    )
    assert payload["package_closeout"]["status"] == "blocked"
    assert payload["repeat_prevention"]["status"] == "blocked"
    assert payload["measured_rollout_loop"]["loop_status"] == "blocked"


def test_weekly_governor_packet_fails_package_verification_on_duplicate_design_queue_rows(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    design_queue = yaml.safe_load(paths["design_queue"].read_text(encoding="utf-8"))
    design_queue["items"].append(dict(design_queue["items"][0]))
    _write_yaml(paths["design_queue"], design_queue)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"

    result = _run_materializer(paths, out)

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["package_verification"]["status"] == "fail"
    assert (
        "design queue staging has duplicate package rows for next90-m106-fleet-governor-packet"
        in payload["package_verification"]["issues"]
    )
    assert payload["package_closeout"]["status"] == "blocked"
    assert payload["repeat_prevention"]["status"] == "blocked"
    assert payload["measured_rollout_loop"]["loop_status"] == "blocked"


def test_weekly_governor_packet_fails_package_verification_on_fleet_queue_mirror_drift(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    queue = yaml.safe_load(paths["queue"].read_text(encoding="utf-8"))
    queue["items"][0]["task"] = "Locally edited task text must not override design-owned staging."
    _write_yaml(paths["queue"], queue)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["package_verification"]["status"] == "fail"
    assert payload["package_verification"]["queue_mirror_status"] == "drift"
    assert payload["package_verification"]["queue_mirror_drift"] == [
        {
            "field": "task",
            "design_queue": (
                "Turn readiness, parity, support, and rollout truth into a weekly governor "
                "packet that drives measured product decisions."
            ),
            "fleet_queue": "Locally edited task text must not override design-owned staging.",
        }
    ]
    assert (
        "Fleet queue mirror package row diverges from design-owned queue staging for field(s): task"
        in payload["package_verification"]["issues"]
    )
    assert payload["package_closeout"]["status"] == "blocked"
    assert payload["repeat_prevention"]["status"] == "blocked"
    assert payload["measured_rollout_loop"]["loop_status"] == "blocked"


def test_weekly_governor_packet_fails_package_verification_on_successor_wave_drift(tmp_path: Path) -> None:
    paths = _fixture_tree(tmp_path)
    registry = yaml.safe_load(paths["registry"].read_text(encoding="utf-8"))
    registry["program_wave"] = "next_12_biggest_wins"
    _write_yaml(paths["registry"], registry)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["package_verification"]["status"] == "fail"
    assert "successor registry program_wave is not next_90_day_product_advance" in payload["package_verification"]["issues"]
    assert payload["package_closeout"]["status"] == "blocked"
    assert payload["repeat_prevention"]["status"] == "blocked"
    assert payload["measured_rollout_loop"]["loop_status"] == "blocked"


def test_weekly_governor_packet_fails_package_verification_when_m106_leaves_w8(tmp_path: Path) -> None:
    paths = _fixture_tree(tmp_path)
    registry = yaml.safe_load(paths["registry"].read_text(encoding="utf-8"))
    registry["waves"][0]["milestone_ids"] = [105]
    _write_yaml(paths["registry"], registry)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["package_verification"]["status"] == "fail"
    assert "successor registry wave W8 does not include milestone 106" in payload["package_verification"]["issues"]
    assert payload["package_closeout"]["status"] == "blocked"
    assert payload["measured_rollout_loop"]["loop_status"] == "blocked"


def test_weekly_governor_packet_fails_package_verification_on_queue_wave_drift(tmp_path: Path) -> None:
    paths = _fixture_tree(tmp_path)
    queue = yaml.safe_load(paths["queue"].read_text(encoding="utf-8"))
    queue["program_wave"] = "next_12_biggest_wins"
    queue["items"][0]["wave"] = "W5"
    _write_yaml(paths["queue"], queue)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["package_verification"]["status"] == "fail"
    assert "queue staging program_wave is not next_90_day_product_advance" in payload["package_verification"]["issues"]
    assert "queue item wave is not W8" in payload["package_verification"]["issues"]
    assert payload["package_closeout"]["status"] == "blocked"
    assert payload["measured_rollout_loop"]["loop_status"] == "blocked"


def test_weekly_governor_packet_fails_package_verification_on_queue_source_drift(tmp_path: Path) -> None:
    paths = _fixture_tree(tmp_path)
    queue = yaml.safe_load(paths["queue"].read_text(encoding="utf-8"))
    queue["status"] = "stale"
    queue["source_registry_path"] = "/docker/chummercomplete/chummer-design/products/chummer/NEXT_12_BIGGEST_WINS_REGISTRY.yaml"
    queue["source_design_queue_path"] = "/docker/chummercomplete/chummer-design/products/chummer/NEXT_12_QUEUE_STAGING.generated.yaml"
    _write_yaml(paths["queue"], queue)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["package_verification"]["status"] == "fail"
    assert "queue staging status is not live_parallel_successor" in payload["package_verification"]["issues"]
    assert (
        "queue staging source_registry_path is not the canonical successor registry"
        in payload["package_verification"]["issues"]
    )
    assert (
        "queue staging source_design_queue_path is not the canonical design staging queue"
        in payload["package_verification"]["issues"]
    )
    assert payload["package_closeout"]["status"] == "blocked"
    assert payload["measured_rollout_loop"]["loop_status"] == "blocked"


def test_weekly_governor_packet_fails_package_verification_when_registry_task_is_not_complete(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    registry = yaml.safe_load(paths["registry"].read_text(encoding="utf-8"))
    registry["milestones"][0]["work_tasks"][0]["status"] = "in_progress"
    _write_yaml(paths["registry"], registry)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["package_verification"]["status"] == "fail"
    assert "registry work task 106.1 is not marked complete" in payload["package_verification"]["issues"]
    assert payload["measured_rollout_loop"]["loop_status"] == "blocked"


def test_weekly_governor_packet_fails_package_verification_on_duplicate_registry_task_rows(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    registry = yaml.safe_load(paths["registry"].read_text(encoding="utf-8"))
    registry["milestones"][0]["work_tasks"].append(
        dict(registry["milestones"][0]["work_tasks"][0])
    )
    _write_yaml(paths["registry"], registry)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"

    result = _run_materializer(paths, out)

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["package_verification"]["status"] == "fail"
    assert (
        "milestone 106 has duplicate registry work task 106.1 rows"
        in payload["package_verification"]["issues"]
    )
    assert payload["package_closeout"]["status"] == "blocked"
    assert payload["repeat_prevention"]["status"] == "blocked"
    assert payload["measured_rollout_loop"]["loop_status"] == "blocked"


def test_weekly_governor_packet_fails_package_verification_when_registry_evidence_is_missing(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    registry = yaml.safe_load(paths["registry"].read_text(encoding="utf-8"))
    registry["milestones"][0]["work_tasks"][0]["evidence"] = [
        evidence
        for evidence in registry["milestones"][0]["work_tasks"][0]["evidence"]
        if "WEEKLY_GOVERNOR_PACKET.generated.json" not in evidence
    ]
    _write_yaml(paths["registry"], registry)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["package_verification"]["status"] == "fail"
    assert (
        "registry work task 106.1 evidence is missing required weekly governor marker(s): "
        "WEEKLY_GOVERNOR_PACKET.generated.json"
        in payload["package_verification"]["issues"]
    )
    assert payload["measured_rollout_loop"]["loop_status"] == "blocked"


def test_weekly_governor_packet_fails_package_verification_when_queue_not_complete(tmp_path: Path) -> None:
    paths = _fixture_tree(tmp_path)
    queue = yaml.safe_load(paths["queue"].read_text(encoding="utf-8"))
    queue["items"][0]["status"] = "in_progress"
    _write_yaml(paths["queue"], queue)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["package_verification"]["status"] == "fail"
    assert "queue item is not marked complete in staging queue" in payload["package_verification"]["issues"]
    assert payload["measured_rollout_loop"]["loop_status"] == "blocked"


def test_weekly_governor_packet_fails_package_verification_when_queue_proof_is_missing(tmp_path: Path) -> None:
    paths = _fixture_tree(tmp_path)
    queue = yaml.safe_load(paths["queue"].read_text(encoding="utf-8"))
    queue["items"][0]["proof"] = [
        proof
        for proof in queue["items"][0]["proof"]
        if proof != "/docker/fleet/.codex-studio/published/WEEKLY_GOVERNOR_PACKET.generated.md"
    ]
    _write_yaml(paths["queue"], queue)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["package_verification"]["status"] == "fail"
    assert (
        "queue item proof is missing required weekly governor receipt(s): "
        "/docker/fleet/.codex-studio/published/WEEKLY_GOVERNOR_PACKET.generated.md"
        in payload["package_verification"]["issues"]
    )
    assert payload["measured_rollout_loop"]["loop_status"] == "blocked"


def test_weekly_governor_packet_fails_package_verification_when_frontier_pin_is_missing(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    queue = yaml.safe_load(paths["queue"].read_text(encoding="utf-8"))
    queue["items"][0]["proof"] = [
        proof for proof in queue["items"][0]["proof"] if "successor frontier 2376135131" not in proof
    ]
    _write_yaml(paths["queue"], queue)
    registry = yaml.safe_load(paths["registry"].read_text(encoding="utf-8"))
    registry["milestones"][0]["work_tasks"][0]["evidence"] = [
        evidence
        for evidence in registry["milestones"][0]["work_tasks"][0]["evidence"]
        if "successor frontier 2376135131" not in evidence
    ]
    _write_yaml(paths["registry"], registry)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["package_verification"]["status"] == "fail"
    assert (
        "queue item proof is missing required weekly governor receipt(s): "
        "successor frontier 2376135131 pinned for next90-m106-fleet-governor-packet repeat prevention"
        in payload["package_verification"]["issues"]
    )
    assert (
        "registry work task 106.1 evidence is missing required weekly governor marker(s): "
        "successor frontier 2376135131"
        in payload["package_verification"]["issues"]
    )
    assert payload["package_closeout"]["status"] == "blocked"
    assert payload["repeat_prevention"]["status"] == "blocked"
    assert payload["measured_rollout_loop"]["loop_status"] == "blocked"


def test_weekly_governor_packet_fails_package_verification_when_source_anchor_is_missing(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    (paths["root"] / "scripts" / "materialize_weekly_governor_packet.py").unlink()
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["package_verification"]["status"] == "fail"
    assert payload["package_closeout"]["status"] == "blocked"
    assert payload["repeat_prevention"]["status"] == "blocked"
    assert payload["package_verification"]["required_resolving_proof_paths"] == [
        "scripts/materialize_weekly_governor_packet.py",
        "scripts/verify_next90_m106_fleet_governor_packet.py",
        "scripts/verify_script_bootstrap_no_pythonpath.py",
        "tests/test_materialize_weekly_governor_packet.py",
        "tests/test_fleet_script_bootstrap_without_pythonpath.py",
    ]
    assert (
        "queue item proof includes source anchor(s) that no longer resolve: "
        "scripts/materialize_weekly_governor_packet.py"
        in payload["package_verification"]["issues"]
    )
    assert (
        "registry work task 106.1 evidence includes source anchor(s) that no longer resolve: "
        "scripts/materialize_weekly_governor_packet.py"
        in payload["package_verification"]["issues"]
    )
    assert payload["measured_rollout_loop"]["loop_status"] == "blocked"


def test_weekly_governor_packet_fails_when_bootstrap_guard_anchor_is_missing(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    (paths["root"] / "scripts" / "verify_script_bootstrap_no_pythonpath.py").unlink()
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["package_verification"]["status"] == "fail"
    assert payload["package_closeout"]["status"] == "blocked"
    assert payload["repeat_prevention"]["status"] == "blocked"
    assert (
        "queue item proof includes source anchor(s) that no longer resolve: "
        "scripts/verify_script_bootstrap_no_pythonpath.py"
        in payload["package_verification"]["issues"]
    )
    assert (
        "registry work task 106.1 evidence includes source anchor(s) that no longer resolve: "
        "scripts/verify_script_bootstrap_no_pythonpath.py"
        in payload["package_verification"]["issues"]
    )
    assert payload["measured_rollout_loop"]["loop_status"] == "blocked"


def test_weekly_governor_packet_rejects_active_run_helper_proof_commands(tmp_path: Path) -> None:
    paths = _fixture_tree(tmp_path)
    queue = yaml.safe_load(paths["queue"].read_text(encoding="utf-8"))
    queue["items"][0]["proof"].append("python3 scripts/run_ooda_design_supervisor_until_quiet.py --once")
    queue["items"][0]["proof"].append("python3 scripts/chummer_design_supervisor.py launch-health")
    _write_yaml(paths["queue"], queue)
    registry = yaml.safe_load(paths["registry"].read_text(encoding="utf-8"))
    registry["milestones"][0]["work_tasks"][0]["evidence"].append(
        "python3 scripts/ooda_design_supervisor.py --telemetry"
    )
    _write_yaml(paths["registry"], registry)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["package_verification"]["status"] == "fail"
    assert payload["package_closeout"]["status"] == "blocked"
    assert payload["package_closeout"]["do_not_reopen_package"] is False
    assert payload["measured_rollout_loop"]["loop_status"] == "blocked"
    assert any(
        "queue item proof includes active-run or operator-helper command evidence" in issue
        and "python3 scripts/chummer_design_supervisor.py launch-health" in issue
        for issue in payload["package_verification"]["issues"]
    )
    assert any(
        "queue item proof includes active-run or operator-helper command evidence" in issue
        for issue in payload["package_verification"]["issues"]
    )
    assert any(
        "registry work task 106.1 evidence includes active-run or operator-helper command evidence" in issue
        for issue in payload["package_verification"]["issues"]
    )
    assert payload["package_verification"]["disallowed_worker_proof_command_markers"] == BLOCKED_WORKER_PROOF_MARKERS


def test_weekly_governor_packet_rejects_active_run_state_artifact_proof(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    queue = yaml.safe_load(paths["queue"].read_text(encoding="utf-8"))
    queue["items"][0]["proof"].append(
        "/var/lib/codex-fleet/chummer_design_supervisor/shard-6/ACTIVE_RUN_HANDOFF.generated.md"
    )
    _write_yaml(paths["queue"], queue)
    registry = yaml.safe_load(paths["registry"].read_text(encoding="utf-8"))
    registry["milestones"][0]["work_tasks"][0]["evidence"].append(
        "/var/lib/codex-fleet/chummer_design_supervisor/shard-6/runs/20260415T114918Z-shard-6/TASK_LOCAL_TELEMETRY.generated.json"
    )
    _write_yaml(paths["registry"], registry)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["package_verification"]["status"] == "fail"
    assert payload["package_closeout"]["status"] == "blocked"
    assert payload["repeat_prevention"]["status"] == "blocked"
    assert payload["measured_rollout_loop"]["loop_status"] == "blocked"
    assert any(
        "queue item proof includes active-run or operator-helper command evidence" in issue
        and "ACTIVE_RUN_HANDOFF.generated.md" in issue
        for issue in payload["package_verification"]["issues"]
    )
    assert any(
        "registry work task 106.1 evidence includes active-run or operator-helper command evidence"
        in issue
        and "TASK_LOCAL_TELEMETRY.generated.json" in issue
        for issue in payload["package_verification"]["issues"]
    )


def test_weekly_governor_packet_rejects_generic_operator_telemetry_proof(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    queue = yaml.safe_load(paths["queue"].read_text(encoding="utf-8"))
    queue["items"][0]["proof"].append("Operator telemetry says this worker package is complete")
    queue["items"][0]["proof"].append("Supervisor status polling was observed from inside the active worker run")
    queue["items"][0]["proof"].append("chummer_design_supervisor status --json reported green")
    _write_yaml(paths["queue"], queue)
    registry = yaml.safe_load(paths["registry"].read_text(encoding="utf-8"))
    registry["milestones"][0]["work_tasks"][0]["evidence"].append(
        "codexea --telemetry-answer --json 1min credits"
    )
    registry["milestones"][0]["work_tasks"][0]["evidence"].append(
        "chummer_design_supervisor eta --json reported done"
    )
    _write_yaml(paths["registry"], registry)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["package_verification"]["status"] == "fail"
    assert payload["repeat_prevention"]["status"] == "blocked"
    assert payload["measured_rollout_loop"]["loop_status"] == "blocked"
    assert any(
        "queue item proof includes active-run or operator-helper command evidence" in issue
        and "Operator telemetry says this worker package is complete" in issue
        for issue in payload["package_verification"]["issues"]
    )
    assert any(
        "queue item proof includes active-run or operator-helper command evidence" in issue
        and "Supervisor status polling was observed from inside the active worker run" in issue
        for issue in payload["package_verification"]["issues"]
    )
    assert any(
        "queue item proof includes active-run or operator-helper command evidence" in issue
        and "chummer_design_supervisor status --json reported green" in issue
        for issue in payload["package_verification"]["issues"]
    )
    assert any(
        "registry work task 106.1 evidence includes active-run or operator-helper command evidence"
        in issue
        and "codexea --telemetry-answer --json 1min credits" in issue
        for issue in payload["package_verification"]["issues"]
    )
    assert any(
        "registry work task 106.1 evidence includes active-run or operator-helper command evidence"
        in issue
        and "chummer_design_supervisor eta --json reported done" in issue
        for issue in payload["package_verification"]["issues"]
    )


def test_weekly_governor_packet_blocks_loop_ready_when_launch_signal_is_missing(tmp_path: Path) -> None:
    paths = _fixture_tree(tmp_path)
    weekly = json.loads(paths["weekly"].read_text(encoding="utf-8"))
    weekly["governor_decisions"][0]["cited_signals"] = [
        "journey_gate_state=ready",
        "journey_gate_blocked_count=0",
        "local_release_proof_status=unknown",
        "closure_health_state=clear",
    ]
    _write_json(paths["weekly"], weekly)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["package_verification"]["status"] == "pass"
    assert payload["weekly_input_health"]["status"] == "fail"
    assert payload["source_input_health"]["status"] == "pass"
    assert "provider_canary_status" in payload["weekly_input_health"]["issues"][0]
    launch_gates = {
        row["name"]: row for row in payload["decision_gate_ledger"]["launch_expand"]
    }
    assert launch_gates["weekly_input_health"]["state"] == "fail"
    assert payload["measured_rollout_loop"]["loop_status"] == "blocked"


def test_weekly_governor_packet_blocks_loop_ready_when_required_source_is_missing(tmp_path: Path) -> None:
    paths = _fixture_tree(tmp_path)
    paths["journeys"].unlink()
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["package_verification"]["status"] == "pass"
    assert payload["weekly_input_health"]["status"] == "pass"
    assert payload["source_input_health"]["status"] == "fail"
    assert payload["source_input_health"]["required_inputs"]["journey_gates"]["state"] == "missing_or_unparseable"
    assert "journey_gates" in payload["source_input_health"]["issues"][0]
    assert payload["measured_rollout_loop"]["loop_status"] == "blocked"


def test_weekly_governor_packet_blocks_loop_ready_when_source_path_cites_active_run_artifact(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    active_run_named_support = (
        tmp_path
        / "chummer_design_supervisor"
        / "shard-6"
        / "runs"
        / "20260415T141605Z-shard-6"
        / "ACTIVE_RUN_HANDOFF.generated.md"
    )
    active_run_named_support.parent.mkdir(parents=True, exist_ok=True)
    active_run_named_support.write_text(paths["support"].read_text(encoding="utf-8"), encoding="utf-8")
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(active_run_named_support),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["package_verification"]["status"] == "pass"
    assert payload["weekly_input_health"]["status"] == "pass"
    assert payload["source_input_health"]["status"] == "fail"
    assert payload["source_input_health"]["required_inputs"]["support_packets"]["state"] == "present"
    assert payload["source_input_health"]["required_inputs"]["source_path_hygiene"]["state"] == "fail"
    assert any(
        "weekly governor source paths include active-run or operator-helper evidence"
        in issue
        and "ACTIVE_RUN_HANDOFF.generated.md" in issue
        for issue in payload["source_input_health"]["issues"]
    )
    assert payload["measured_rollout_loop"]["loop_status"] == "blocked"


def test_weekly_governor_packet_blocks_loop_ready_when_support_package_proof_regresses(tmp_path: Path) -> None:
    paths = _fixture_tree(tmp_path)
    support = json.loads(paths["support"].read_text(encoding="utf-8"))
    support["successor_package_verification"] = {
        "status": "fail",
        "issues": ["queue proof missing WEEKLY_GOVERNOR_PACKET.generated.json"],
    }
    _write_json(paths["support"], support)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["package_verification"]["status"] == "pass"
    assert payload["weekly_input_health"]["status"] == "pass"
    assert payload["source_input_health"]["status"] == "fail"
    assert (
        payload["source_input_health"]["required_inputs"]["support_packets"][
            "successor_package_verification_status"
        ]
        == "fail"
    )
    assert (
        "support_packets successor_package_verification.status is not pass"
        in payload["source_input_health"]["issues"][0]
    )
    assert payload["measured_rollout_loop"]["loop_status"] == "blocked"


def test_weekly_governor_packet_blocks_loop_ready_when_support_packets_are_stale(tmp_path: Path) -> None:
    paths = _fixture_tree(tmp_path)
    support = json.loads(paths["support"].read_text(encoding="utf-8"))
    support["generated_at"] = (
        dt.datetime.now(UTC) - dt.timedelta(days=9)
    ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    _write_json(paths["support"], support)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["package_verification"]["status"] == "pass"
    assert payload["weekly_input_health"]["status"] == "pass"
    assert payload["source_input_health"]["status"] == "fail"
    assert payload["source_input_health"]["required_inputs"]["support_packets"]["state"] == "present"
    assert (
        payload["source_input_health"]["required_inputs"]["support_packets"]["max_age_seconds"]
        == 691200
    )
    assert any(
        issue.startswith("support_packets are stale")
        for issue in payload["source_input_health"]["issues"]
    )
    assert payload["measured_rollout_loop"]["loop_status"] == "blocked"


def test_weekly_governor_packet_blocks_loop_ready_when_parity_truth_drops_below_veteran_ready(tmp_path: Path) -> None:
    paths = _fixture_tree(tmp_path)
    readiness = json.loads(paths["readiness"].read_text(encoding="utf-8"))
    evidence = readiness["readiness_planes"]["flagship_ready"]["evidence"]
    evidence["status_counts"] = {
        "documented": 1,
        "implemented": 0,
        "task_proven": 10,
        "veteran_approved": 0,
        "gold_ready": 0,
        "unknown": 0,
    }
    evidence["families_below_task_proven"] = ["settings_and_source_toggles"]
    evidence["families_below_veteran_approved"] = ["settings_and_source_toggles"]
    evidence["families_below_gold_ready"] = ["settings_and_source_toggles"]
    _write_json(paths["readiness"], readiness)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(paths["root"]),
            "--out",
            str(out),
            "--successor-registry",
            str(paths["registry"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--queue-staging",
            str(paths["queue"]),
            "--weekly-pulse",
            str(paths["weekly"]),
            "--flagship-readiness",
            str(paths["readiness"]),
            "--journey-gates",
            str(paths["journeys"]),
            "--support-packets",
            str(paths["support"]),
            "--status-plane",
            str(paths["status"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["package_verification"]["status"] == "pass"
    assert payload["weekly_input_health"]["status"] == "pass"
    assert payload["truth_inputs"]["flagship_parity_release_truth"]["release_truth_status"] == "blocked"
    assert payload["decision_board"]["launch_expand"]["state"] == "blocked"
    assert payload["measured_rollout_loop"]["loop_status"] == "blocked"
