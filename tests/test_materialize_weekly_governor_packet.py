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
    "run_chummer_design_supervisor.sh",
    "run_ooda_design_supervisor.sh",
    "ooda_design_supervisor.py",
    "TASK_LOCAL_TELEMETRY.generated.json",
    "first_commands",
    "focus_owners",
    "focus_profiles",
    "focus_texts",
    "frontier_briefs",
    "status: complete; owners:",
    "deps: 101, 102, 103, 104, 105",
    "own and prove the surface slice(s): weekly_governor_packet, measured_rollout_loop",
    "refresh flagship proof and close out the queue slice honestly",
    "frontier ids:",
    "open milestone ids:",
    "polling_disabled",
    "runtime_handoff_path",
    "shard runtime handoff",
    "status_query_supported",
    "task-local telemetry file",
    "local machine-readable context",
    "remaining milestones",
    "remaining queue items",
    "critical path",
    "successor-wave telemetry:",
    "eta:",
    "eta ",
    "successor frontier detail:",
    "successor frontier ids to prioritize first",
    "current steering focus",
    "assigned successor queue package",
    "assigned slice authority",
    "execution rules inside this run",
    "execution discipline",
    "first action rule",
    "writable scope roots",
    "operator telemetry",
    "do not invoke operator telemetry",
    "do not invoke operator telemetry or active-run helper commands from inside worker runs",
    "supervisor status polling",
    "supervisor eta polling",
    "do not query supervisor status",
    "do not query supervisor status or eta",
    "polling the supervisor again",
    "current flagship closeout",
    "do not reopen the closed flagship wave",
    "reopen the closed flagship wave",
    "active-run telemetry",
    "active run",
    "run id:",
    "selected account",
    "selected model",
    "prompt path",
    "recent stderr tail",
    "active-run helper",
    "active-run helper commands",
    "active run helper",
    "active worker run",
    "worker runs",
    "operator/OODA loop",
    "operator ooda loop",
    "operator/OODA loop owns telemetry",
    "operator/OODA loop owns telemetry; keep working the assigned slice",
    "operator ooda loop owns telemetry",
    "ooda loop owns telemetry",
    "operator-owned telemetry",
    "operator-owned run-helper",
    "operator-owned helper",
    "inside worker runs",
    "run failure",
    "count as run failure",
    "hard-blocked",
    "helpers are hard-blocked",
    "hard blocked",
    "non-zero during active runs",
    "return non-zero during active runs",
    "nonzero during active runs",
    "--telemetry-answer",
    "codexea telemetry",
    "codexea status",
    "codexea eta",
    "codexea watch",
    "codexea-watchdog",
    "codexea --telemetry",
    "chummer_design_supervisor status",
    "chummer_design_supervisor eta",
    "supervisor status",
    "supervisor eta",
    "operator telemetry helper",
    "active-run status helper",
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
    closed_flagship_registry = tmp_path / "NEXT_12_BIGGEST_WINS_REGISTRY.yaml"
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
        root / "scripts" / "run_next90_m106_weekly_governor_packet_tests.py",
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
                                "/docker/fleet/scripts/run_next90_m106_weekly_governor_packet_tests.py executes the pytest-style M106 fixture tests without requiring pytest.",
                                "/docker/fleet/scripts/verify_script_bootstrap_no_pythonpath.py includes the standalone M106 verifier in no-PYTHONPATH bootstrap proof.",
                                "/docker/fleet/tests/test_materialize_weekly_governor_packet.py fail-closes drift.",
                                "/docker/fleet/tests/test_fleet_script_bootstrap_without_pythonpath.py launches the standalone M106 verifier help without PYTHONPATH.",
                                "/docker/fleet/.codex-studio/published/WEEKLY_GOVERNOR_PACKET.generated.json reports current decisions.",
                                "/docker/fleet/.codex-studio/published/WEEKLY_GOVERNOR_PACKET.generated.md mirrors the operator packet.",
                                "python3 -m py_compile scripts/materialize_weekly_governor_packet.py scripts/verify_next90_m106_fleet_governor_packet.py tests/test_materialize_weekly_governor_packet.py exits 0.",
                                "python3 -m py_compile scripts/run_next90_m106_weekly_governor_packet_tests.py exits 0.",
                                "python3 -m py_compile scripts/verify_script_bootstrap_no_pythonpath.py tests/test_fleet_script_bootstrap_without_pythonpath.py exits 0.",
                                "python3 scripts/verify_next90_m106_fleet_governor_packet.py exits 0.",
                                "python3 scripts/run_next90_m106_weekly_governor_packet_tests.py exits 0.",
                                "Direct tmp_path fixture invocation exits 0.",
                                "Verifier rebuilds the decision-critical packet projection from live source inputs.",
                                "markdown Generated timestamp must match JSON generated_at.",
                                "Verifier rejects checked-in packet freshness drift against generated readiness, journey, support, weekly pulse, and status-plane inputs.",
                                "future-dated weekly and source generated_at receipts are rejected.",
                                "Verifier rejects compile manifest freshness drift after weekly packet refresh.",
                                "Verifier rejects support-packet source_sha256 drift against SUPPORT_CASE_PACKETS.generated.json.",
                                "Verifier requires every measured rollout action to appear in both the decision board and decision gate ledger.",
                                "weekly pulse duplicate or ambiguous launch governance actions are rejected.",
                                "status-plane final claim drift blocks launch expansion and measured rollout readiness.",
                                "status_reason distinguishes closed Fleet package proof from blocked rollout gates.",
                                "forbidden worker proof strings are rejected case-insensitively.",
                                "task-local telemetry field names are rejected as worker proof strings.",
                                "successor-wave telemetry summary strings are rejected as worker proof strings.",
                                "literal successor-wave telemetry labels are rejected as worker proof strings.",
                                "frontier-detail prompt strings are rejected as worker proof strings.",
                                "frontier-detail body strings are rejected as worker proof strings.",
                                "run-prompt authority labels are rejected as worker proof strings.",
                                "execution-discipline prompt strings are rejected as worker proof strings.",
                                "runtime handoff header and model metadata strings are rejected as worker proof strings.",
                                "runtime handoff frontier metadata strings are rejected as worker proof strings.",
                                "handoff polling phrase guard is enforced case-insensitively.",
                                "control-plane polling prohibition guard is enforced case-insensitively.",
                                "worker-run OODA helper guard is enforced case-insensitively.",
                                "telemetry-ownership handoff prompt strings are rejected as worker proof strings.",
                                "worker-run supervisor launcher guard is enforced case-insensitively.",
                                "run-helper failure proof strings are rejected case-insensitively.",
                                "repeat-prevention worker command guard records helper failure posture.",
                                "Verifier rejects Fleet proof paths outside package allowed path roots.",
                                "Production verifier rejects non-canonical source path overrides.",
                                "Verifier rejects reused closed successor frontier rows outside the Fleet M106 package.",
                                "blocked support-packet proof routes exactly to the M102 reporter-receipts dependency package.",
                                "no-PYTHONPATH bootstrap guard includes the standalone M106 verifier.",
                                "successor frontier 2376135131 is pinned for next90-m106-fleet-governor-packet repeat prevention.",
                                "local proof floor commit 1ba508e pinned for M106 governor packet repeat prevention.",
                                "local proof floor commit 6d1663c pinned for M106 governor packet dependency-routing guard.",
                                "local proof floor commit ade57ae pinned for M106 task-local telemetry field guard.",
                                "local proof floor commit 55d8282 pinned for M106 source-authority guard.",
                                "local proof floor commit 144eae5 pinned for M106 worker-run helper guard.",
                                "local proof floor commit 543dfd5 pinned for M106 markdown proof-floor guard.",
                                "local proof floor commit f16f13b pinned for M106 run-helper failure guard.",
                                "local proof floor commit 999231f pinned for M106 source-input refresh guard.",
                                "local proof floor commit 25836f6 pinned for M106 source refresh proof floor.",
                                "local proof floor commit 3e7ee9b pinned for M106 governor packet proof floor.",
                                "local proof floor commit 17189be pinned for M106 future-dated source timestamp guard.",
                                "local proof floor commit 9d2ea4c pinned for M106 timestamp guard proof floor.",
                                "local proof floor commit bb49fc1 pinned for M106 run-prompt authority guard.",
                                "local proof floor commit 26679c7 pinned for M106 refreshed packet artifact floor.",
                                "local proof floor commit ef50370 pinned for M106 refreshed proof-floor guard.",
                                "local proof floor commit a1be389 pinned for M106 successor telemetry prompt-label guard.",
                                "local proof floor commit 83d2d21 pinned for M106 OODA telemetry ownership guard.",
                                "local proof floor commit e74a7ec pinned for M106 OODA telemetry proof floor.",
                                "local proof floor commit 8fb8d40 pinned for M106 refreshed packet artifact floor.",
                                "local proof floor commit dd5fdb5 pinned for M106 weekly governor proof floor.",
                                "local proof floor commit 52fe086 pinned for M106 governor packet proof floor.",
                                "local proof floor commit 6c429cb pinned for M106 verified closeout proof floor.",
                                "local proof floor commit 5193bce pinned for M106 refreshed packet artifact floor.",
                                "local proof floor commit f662ad3 pinned for M106 shorthand telemetry command guard.",
                                "local proof floor commit 5882234 pinned for M106 blocked dependency route guard.",
                                "local proof floor commit 6c376e0 pinned for M106 execution-discipline proof guard.",
                                "local proof floor commit 00e870e pinned for M106 direct fixture runner guard.",
                                "local proof floor commit 81e1de8 pinned for M106 refreshed source-input packet floor.",
                                "local proof floor commit 941c54d pinned for M106 handoff frontier metadata guard.",
                                "local proof floor commit 6981667 pinned for M106 worker helper rule guard.",
                                "local proof floor commit 4a13b47 pinned for M106 markdown timestamp proof guard.",
                                "local proof floor commit d597376 pinned for M106 telemetry handoff proof guard.",
                                "local proof floor commit 233a52a pinned for M106 shard-runtime-handoff guard.",
                                "local proof floor commit fba96cc pinned for M106 helper failure posture guard.",
                                "local proof floor commit 15efd7c pinned for M106 refreshed packet artifact floor.",
                                "local proof floor commit f3bfb8d pinned for M106 refreshed packet artifact floor.",
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
        closed_flagship_registry,
        {
            "product": "chummer",
            "program_wave": "next_12_biggest_wins",
            "status": "complete",
            "waves": [
                {
                    "id": "W1",
                    "name": "Ship the flagship desktop",
                    "status": "complete",
                    "milestone_ids": [1],
                }
            ],
            "milestones": [
                {
                    "id": 1,
                    "title": "Gold install, update, and recovery lane across macOS, Windows, and Linux",
                    "status": "complete",
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
                        "/docker/fleet/scripts/run_next90_m106_weekly_governor_packet_tests.py",
                        "/docker/fleet/scripts/verify_script_bootstrap_no_pythonpath.py",
                        "/docker/fleet/tests/test_materialize_weekly_governor_packet.py",
                        "/docker/fleet/tests/test_fleet_script_bootstrap_without_pythonpath.py",
                        "/docker/fleet/.codex-studio/published/WEEKLY_GOVERNOR_PACKET.generated.json",
                        "/docker/fleet/.codex-studio/published/WEEKLY_GOVERNOR_PACKET.generated.md",
                        "python3 -m py_compile scripts/materialize_weekly_governor_packet.py scripts/verify_next90_m106_fleet_governor_packet.py tests/test_materialize_weekly_governor_packet.py",
                        "python3 -m py_compile scripts/run_next90_m106_weekly_governor_packet_tests.py",
                        "python3 -m py_compile scripts/verify_script_bootstrap_no_pythonpath.py tests/test_fleet_script_bootstrap_without_pythonpath.py",
                        "python3 scripts/verify_next90_m106_fleet_governor_packet.py exits 0",
                        "python3 scripts/run_next90_m106_weekly_governor_packet_tests.py exits 0",
                        "direct tmp_path fixture invocation for tests/test_materialize_weekly_governor_packet.py exits 0",
                        "verifier rebuilds the decision-critical packet projection from live source inputs",
                        "markdown Generated timestamp must match JSON generated_at",
                        "verifier rejects checked-in packet freshness drift against generated readiness, journey, support, weekly pulse, and status-plane inputs",
                        "future-dated weekly and source generated_at receipts are rejected",
                        "verifier rejects compile manifest freshness drift after weekly packet refresh",
                        "verifier rejects support-packet source_sha256 drift against SUPPORT_CASE_PACKETS.generated.json",
                        "verifier requires every measured rollout action to appear in both the decision board and decision gate ledger",
                        "weekly pulse duplicate or ambiguous launch governance actions are rejected",
                        "status-plane final claim drift blocks launch expansion and measured rollout readiness",
                        "status_reason distinguishes closed Fleet package proof from blocked rollout gates",
                        "forbidden worker proof strings are rejected case-insensitively",
                        "task-local telemetry field names are rejected as worker proof strings",
                        "successor-wave telemetry summary strings are rejected as worker proof strings",
                        "literal successor-wave telemetry labels are rejected as worker proof strings",
                        "frontier-detail prompt strings are rejected as worker proof strings",
                        "frontier-detail body strings are rejected as worker proof strings",
                        "run-prompt authority labels are rejected as worker proof strings",
                        "execution-discipline prompt strings are rejected as worker proof strings",
                        "runtime handoff header and model metadata strings are rejected as worker proof strings",
                        "runtime handoff frontier metadata strings are rejected as worker proof strings",
                        "handoff polling phrase guard is enforced case-insensitively",
                        "control-plane polling prohibition guard is enforced case-insensitively",
                        "worker-run OODA helper guard is enforced case-insensitively",
                        "telemetry-ownership handoff prompt strings are rejected as worker proof strings",
                        "worker-run supervisor launcher guard is enforced case-insensitively",
                        "run-helper failure proof strings are rejected case-insensitively",
                        "repeat-prevention worker command guard records helper failure posture",
                        "verifier rejects Fleet proof paths outside package allowed path roots",
                        "production verifier rejects non-canonical source path overrides",
                        "verifier rejects reused closed successor frontier rows outside the Fleet M106 package",
                        "blocked support-packet proof routes exactly to the M102 reporter-receipts dependency package",
                        "no-PYTHONPATH bootstrap guard includes the standalone M106 verifier",
                        "successor frontier 2376135131 pinned for next90-m106-fleet-governor-packet repeat prevention",
                        "local proof floor commit 1ba508e pinned for M106 governor packet repeat prevention",
                        "local proof floor commit 6d1663c pinned for M106 governor packet dependency-routing guard",
                        "local proof floor commit ade57ae pinned for M106 task-local telemetry field guard",
                        "local proof floor commit 55d8282 pinned for M106 source-authority guard",
                        "local proof floor commit 144eae5 pinned for M106 worker-run helper guard",
                        "local proof floor commit 543dfd5 pinned for M106 markdown proof-floor guard",
                        "local proof floor commit f16f13b pinned for M106 run-helper failure guard",
                        "local proof floor commit 999231f pinned for M106 source-input refresh guard",
                        "local proof floor commit 25836f6 pinned for M106 source refresh proof floor",
                        "local proof floor commit 3e7ee9b pinned for M106 governor packet proof floor",
                        "local proof floor commit 17189be pinned for M106 future-dated source timestamp guard",
                        "local proof floor commit 9d2ea4c pinned for M106 timestamp guard proof floor",
                        "local proof floor commit bb49fc1 pinned for M106 run-prompt authority guard",
                        "local proof floor commit 26679c7 pinned for M106 refreshed packet artifact floor",
                        "local proof floor commit ef50370 pinned for M106 refreshed proof-floor guard",
                        "local proof floor commit a1be389 pinned for M106 successor telemetry prompt-label guard",
                        "local proof floor commit 83d2d21 pinned for M106 OODA telemetry ownership guard",
                        "local proof floor commit e74a7ec pinned for M106 OODA telemetry proof floor",
                        "local proof floor commit 8fb8d40 pinned for M106 refreshed packet artifact floor",
                        "local proof floor commit dd5fdb5 pinned for M106 weekly governor proof floor",
                        "local proof floor commit 52fe086 pinned for M106 governor packet proof floor",
                        "local proof floor commit 6c429cb pinned for M106 verified closeout proof floor",
                        "local proof floor commit 5193bce pinned for M106 refreshed packet artifact floor",
                        "local proof floor commit f662ad3 pinned for M106 shorthand telemetry command guard",
                        "local proof floor commit 5882234 pinned for M106 blocked dependency route guard",
                        "local proof floor commit 6c376e0 pinned for M106 execution-discipline proof guard",
                        "local proof floor commit 00e870e pinned for M106 direct fixture runner guard",
                        "local proof floor commit 81e1de8 pinned for M106 refreshed source-input packet floor",
                        "local proof floor commit 941c54d pinned for M106 handoff frontier metadata guard",
                        "local proof floor commit 6981667 pinned for M106 worker helper rule guard",
                        "local proof floor commit 4a13b47 pinned for M106 markdown timestamp proof guard",
                        "local proof floor commit d597376 pinned for M106 telemetry handoff proof guard",
                        "local proof floor commit 233a52a pinned for M106 shard-runtime-handoff guard",
                        "local proof floor commit fba96cc pinned for M106 helper failure posture guard",
                        "local proof floor commit 15efd7c pinned for M106 refreshed packet artifact floor",
                        "local proof floor commit f3bfb8d pinned for M106 refreshed packet artifact floor",
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
        "closed_flagship_registry": closed_flagship_registry,
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
        "--closed-flagship-registry",
        str(paths["closed_flagship_registry"]),
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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


def test_weekly_governor_packet_rejects_duplicate_or_ambiguous_launch_decisions(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    weekly = json.loads(paths["weekly"].read_text(encoding="utf-8"))
    duplicate_freeze = dict(weekly["governor_decisions"][0])
    ambiguous_launch = dict(weekly["governor_decisions"][0])
    ambiguous_launch["action"] = "launch_expand"
    weekly["governor_decisions"].extend([duplicate_freeze, ambiguous_launch])
    _write_json(paths["weekly"], weekly)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"

    result = _run_materializer(paths, out)

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["weekly_input_health"]["status"] == "fail"
    assert (
        "weekly pulse governor_decisions has duplicate action row(s): freeze_launch"
        in payload["weekly_input_health"]["issues"]
    )
    assert (
        "weekly pulse must contain exactly one launch governance action (freeze_launch or launch_expand); found 3"
        in payload["weekly_input_health"]["issues"]
    )
    assert payload["status"] == "blocked"
    assert payload["decision_board"]["launch_expand"]["state"] == "blocked"


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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
        "1ba508e",
        "6d1663c",
        "ade57ae",
        "55d8282",
        "144eae5",
        "543dfd5",
        "f16f13b",
        "999231f",
        "25836f6",
        "3e7ee9b",
        "17189be",
        "9d2ea4c",
        "bb49fc1",
        "26679c7",
        "ef50370",
        "a1be389",
        "83d2d21",
        "e74a7ec",
        "8fb8d40",
        "dd5fdb5",
        "52fe086",
        "6c429cb",
        "5193bce",
        "f662ad3",
        "5882234",
        "6c376e0",
        "00e870e",
        "81e1de8",
        "941c54d",
        "6981667",
        "4a13b47",
        "d597376",
        "233a52a",
        "fba96cc",
        "15efd7c",
        "f3bfb8d",
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
        "1ba508e",
        "6d1663c",
        "ade57ae",
        "55d8282",
        "144eae5",
        "543dfd5",
        "f16f13b",
        "999231f",
        "25836f6",
        "3e7ee9b",
        "17189be",
        "9d2ea4c",
        "bb49fc1",
        "26679c7",
        "ef50370",
        "a1be389",
        "83d2d21",
        "e74a7ec",
        "8fb8d40",
        "dd5fdb5",
        "52fe086",
        "6c429cb",
        "5193bce",
        "f662ad3",
        "5882234",
        "6c376e0",
        "00e870e",
        "81e1de8",
        "941c54d",
        "6981667",
        "4a13b47",
        "d597376",
        "233a52a",
        "fba96cc",
        "15efd7c",
        "f3bfb8d",
    ]
    assert payload["repeat_prevention"]["local_commit_resolution"]["status"] == "not_checked"
    assert payload["repeat_prevention"]["do_not_reopen_owned_surfaces"] is True
    assert payload["repeat_prevention"]["owned_surfaces"] == [
        "weekly_governor_packet",
        "measured_rollout_loop",
    ]
    assert payload["repeat_prevention"]["remaining_dependency_ids"] == [101, 102, 103, 104, 105]
    assert payload["repeat_prevention"]["blocked_dependency_package_ids"] == []
    assert payload["repeat_prevention"]["remaining_sibling_work_task_ids"] == ["106.3", "106.4"]
    assert (
        payload["repeat_prevention"]["worker_command_guard"]["status"]
        == "active_run_helpers_forbidden"
    )
    assert payload["repeat_prevention"]["worker_command_guard"]["blocked_markers"] == BLOCKED_WORKER_PROOF_MARKERS
    assert (
        "hard-blocked"
        in payload["repeat_prevention"]["worker_command_guard"]["rule"]
    )
    assert (
        "run failure"
        in payload["repeat_prevention"]["worker_command_guard"]["rule"]
    )
    assert (
        "non-zero during active runs"
        in payload["repeat_prevention"]["worker_command_guard"]["rule"]
    )
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
    assert payload["source_input_health"]["required_inputs"]["source_path_authority"]["state"] == "pass"
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
    assert "- Local proof floor commits: 065c653, fb47ce8, 5e6a468, f66dbaa, f490e53, e9ea391, aefd72c, 21e00dd, 3eec697, 6fd5bfe, 3418b3c, 3580ba8, eeafd9e, 1ba508e, 6d1663c, ade57ae, 55d8282, 144eae5, 543dfd5, f16f13b, 999231f, 25836f6, 3e7ee9b, 17189be, 9d2ea4c, bb49fc1, 26679c7, ef50370, a1be389, 83d2d21, e74a7ec, 8fb8d40, dd5fdb5, 52fe086, 6c429cb, 5193bce, f662ad3, 5882234, 6c376e0, 00e870e, 81e1de8, 941c54d, 6981667, 4a13b47, d597376, 233a52a, fba96cc, 15efd7c, f3bfb8d" in markdown
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
        "scripts/run_next90_m106_weekly_governor_packet_tests.py, "
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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


def test_verify_next90_m106_governor_packet_rejects_ready_status_reason_drift(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"

    materialize = _run_materializer(paths, out)
    assert materialize.returncode == 0, materialize.stderr

    packet = json.loads(out.read_text(encoding="utf-8"))
    packet["status_reason"] = "Ready because no work remains anywhere in milestone 106."
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
        "ready packet status_reason no longer confirms closed package and ready measured rollout"
        in verifier.stderr
    )


def test_verify_next90_m106_governor_packet_rejects_production_source_path_override(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)

    verifier = subprocess.run(
        [
            sys.executable,
            "/docker/fleet/scripts/verify_next90_m106_fleet_governor_packet.py",
            "--repo-root",
            "/docker/fleet",
            "--successor-registry",
            str(paths["registry"]),
        ],
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert verifier.returncode != 0
    assert "production verifier source paths are not canonical" in verifier.stderr
    assert "successor_registry" in verifier.stderr


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
    assert (
        payload["status_reason"]
        == "Fleet package is closed; measured rollout remains blocked by current source, dependency, or sibling gates."
    )
    assert payload["decision_board"]["current_launch_action"] == "freeze_launch"
    assert payload["measured_rollout_loop"]["loop_status"] == "blocked"
    assert payload["measured_rollout_loop"]["blocked_dependency_package_ids"] == [
        "next90-m102-fleet-reporter-receipts"
    ]
    assert payload["package_closeout"]["blocked_dependency_package_ids"] == [
        "next90-m102-fleet-reporter-receipts"
    ]
    assert payload["repeat_prevention"]["blocked_dependency_package_ids"] == [
        "next90-m102-fleet-reporter-receipts"
    ]

    verifier = subprocess.run(
        _verifier_args(paths, out),
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert verifier.returncode == 0, verifier.stderr
    assert "verified next90-m106-fleet-governor-packet" in verifier.stdout


def test_verify_next90_m106_governor_packet_rejects_source_blocked_status_reason_drift(
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

    packet = json.loads(out.read_text(encoding="utf-8"))
    packet["status_reason"] = "Fleet package still needs weekly governor implementation."
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
        "source-blocked packet status_reason no longer distinguishes closed package proof from rollout blockage"
        in verifier.stderr
    )


def test_verify_next90_m106_governor_packet_rejects_ambiguous_blocked_dependency_routes(
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

    packet = json.loads(out.read_text(encoding="utf-8"))
    for section in (
        packet["package_closeout"],
        packet["repeat_prevention"],
        packet["measured_rollout_loop"],
    ):
        section["blocked_dependency_package_ids"] = [
            "next90-m102-fleet-reporter-receipts",
            "next90-m999-unowned-repeat",
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
    assert "package closeout blocked dependency package route list drifted" in verifier.stderr
    assert "repeat prevention blocked dependency package route list drifted" in verifier.stderr
    assert (
        "measured rollout loop blocked dependency package route list drifted"
        in verifier.stderr
    )


def test_verify_next90_m106_governor_packet_rejects_active_run_source_path(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    active_run_named_support = (
        tmp_path
        / "chummer_design_supervisor"
        / "shard-6"
        / "runs"
        / "20260416T172742Z-shard-6"
        / "ACTIVE_RUN_HANDOFF.generated.md"
    )
    active_run_named_support.parent.mkdir(parents=True, exist_ok=True)
    active_run_named_support.write_text(paths["support"].read_text(encoding="utf-8"), encoding="utf-8")
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
    assert materialize.returncode == 0, materialize.stderr

    verifier_args = _verifier_args(paths, out)
    verifier_args[verifier_args.index("--support-packets") + 1] = str(active_run_named_support)
    verifier = subprocess.run(
        verifier_args,
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert verifier.returncode == 1
    assert (
        "verifier source paths include active-run or operator-helper evidence"
        in verifier.stderr
    )
    assert "ACTIVE_RUN_HANDOFF.generated.md" in verifier.stderr


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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
    assert (
        "repeat prevention worker command guard rule no longer forbids operator telemetry and active-run helper commands"
        in verifier.stderr
    )
    assert (
        "repeat prevention worker command guard rule no longer records hard-blocked run-failure helper posture"
        in verifier.stderr
    )


def test_verify_next90_m106_governor_packet_rejects_worker_guard_rule_omitting_helper_ban(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"
    materialize = _run_materializer(paths, out)
    assert materialize.returncode == 0, materialize.stderr

    packet = json.loads(out.read_text(encoding="utf-8"))
    packet["repeat_prevention"]["worker_command_guard"]["rule"] = (
        "Worker proof must come from repo-local files, generated packets, and tests."
    )
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
        "repeat prevention worker command guard rule no longer forbids operator telemetry and active-run helper commands"
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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


def test_verify_next90_m106_governor_packet_rejects_reopened_closed_flagship_registry(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    closed_registry = yaml.safe_load(
        paths["closed_flagship_registry"].read_text(encoding="utf-8")
    )
    closed_registry["status"] = "in_progress"
    closed_registry["waves"][0]["status"] = "in_progress"
    closed_registry["milestones"][0]["status"] = "in_progress"
    _write_yaml(paths["closed_flagship_registry"], closed_registry)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"

    result = _run_materializer(paths, out)

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["source_input_health"]["status"] == "fail"
    assert payload["status"] == "blocked"
    assert (
        payload["source_input_health"]["required_inputs"]["closed_flagship_registry"][
            "status"
        ]
        == "in_progress"
    )
    assert (
        "closed_flagship_registry status is not complete"
        in payload["source_input_health"]["issues"]
    )
    assert any(
        issue.startswith("closed_flagship_registry has reopened wave(s): W1")
        for issue in payload["source_input_health"]["issues"]
    )
    assert any(
        issue.startswith("closed_flagship_registry has reopened milestone(s): 1")
        for issue in payload["source_input_health"]["issues"]
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
        "source input health no longer proves the closed flagship registry status is complete"
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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


def test_verify_next90_m106_governor_packet_rejects_markdown_proof_floor_prefix(
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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

    markdown_path = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.md"
    markdown = markdown_path.read_text(encoding="utf-8")
    markdown_path.write_text(
        markdown.replace(", 52fe086", ""),
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
    assert "markdown local proof floor commit pin is missing" in verifier.stderr


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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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


def test_verify_next90_m106_governor_packet_rejects_markdown_generated_at_drift(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"
    materialize = _run_materializer(paths, out)
    assert materialize.returncode == 0, materialize.stderr

    markdown = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.md"
    markdown_lines = markdown.read_text(encoding="utf-8").splitlines()
    markdown_lines = [
        "Generated: 2026-04-14T10:00:00Z" if line.startswith("Generated: ") else line
        for line in markdown_lines
    ]
    markdown.write_text("\n".join(markdown_lines) + "\n", encoding="utf-8")

    verifier = subprocess.run(
        _verifier_args(paths, out),
        cwd="/docker/fleet",
        check=False,
        capture_output=True,
        text=True,
    )

    assert verifier.returncode == 1
    assert (
        "checked-in markdown packet Generated timestamp no longer matches JSON packet generated_at"
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
        == "Fleet package closeout is blocked; inspect package_verification issues before treating this slice as closed."
    )
    assert payload["package_verification"]["status"] == "fail"
    assert payload["package_closeout"]["status"] == "blocked"
    assert payload["package_closeout"]["do_not_reopen_package"] is False
    assert payload["repeat_prevention"]["status"] == "blocked"
    assert payload["repeat_prevention"]["do_not_reopen_owned_surfaces"] is False
    assert "queue item allowed_paths no longer match package authority" in payload["package_verification"]["issues"]
    assert payload["measured_rollout_loop"]["loop_status"] == "blocked"


def test_weekly_governor_packet_rejects_reused_closed_frontier_rows(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    queue = yaml.safe_load(paths["queue"].read_text(encoding="utf-8"))
    duplicate = dict(queue["items"][0])
    duplicate["package_id"] = "next90-m106-fleet-governor-packet-repeat"
    duplicate["title"] = "Repeat closed weekly governor packet"
    queue["items"].append(duplicate)
    _write_yaml(paths["queue"], queue)

    design_queue = yaml.safe_load(paths["design_queue"].read_text(encoding="utf-8"))
    design_duplicate = dict(design_queue["items"][0])
    design_duplicate["package_id"] = "next90-m106-fleet-governor-packet-repeat"
    design_duplicate["title"] = "Repeat closed weekly governor packet"
    design_queue["items"].append(design_duplicate)
    _write_yaml(paths["design_queue"], design_queue)

    out = paths["published"] / "WEEKLY_GOVERNOR_PACKET.generated.json"
    result = _run_materializer(paths, out)

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["status"] == "blocked"
    assert payload["package_verification"]["status"] == "fail"
    assert payload["package_closeout"]["do_not_reopen_package"] is False
    assert payload["repeat_prevention"]["status"] == "blocked"
    assert (
        "design queue reuses closed successor frontier 2376135131 outside "
        "next90-m106-fleet-governor-packet: next90-m106-fleet-governor-packet-repeat"
        in payload["package_verification"]["issues"]
    )
    assert (
        "queue reuses closed successor frontier 2376135131 outside "
        "next90-m106-fleet-governor-packet: next90-m106-fleet-governor-packet-repeat"
        in payload["package_verification"]["issues"]
    )


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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
        "scripts/run_next90_m106_weekly_governor_packet_tests.py",
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
    queue["items"][0]["proof"].append("bash scripts/run_chummer_design_supervisor.sh")
    queue["items"][0]["proof"].append("Current flagship closeout is green, so do not reopen the closed flagship wave.")
    _write_yaml(paths["queue"], queue)
    registry = yaml.safe_load(paths["registry"].read_text(encoding="utf-8"))
    registry["milestones"][0]["work_tasks"][0]["evidence"].append(
        "python3 scripts/ooda_design_supervisor.py --telemetry"
    )
    registry["milestones"][0]["work_tasks"][0]["evidence"].append(
        "bash scripts/run_ooda_design_supervisor.sh"
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
        and "Current flagship closeout is green" in issue
        and "bash scripts/run_chummer_design_supervisor.sh" in issue
        for issue in payload["package_verification"]["issues"]
    )
    assert any(
        "queue item proof includes active-run or operator-helper command evidence" in issue
        for issue in payload["package_verification"]["issues"]
    )
    assert any(
        "registry work task 106.1 evidence includes active-run or operator-helper command evidence" in issue
        and "bash scripts/run_ooda_design_supervisor.sh" in issue
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
    queue["items"][0]["proof"].append(
        "The shard runtime handoff says this package is already complete"
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
        "queue item proof includes active-run or operator-helper command evidence" in issue
        and "shard runtime handoff" in issue
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
    queue["items"][0]["proof"].append("codexea status --json reported this queue slice is done")
    queue["items"][0]["proof"].append("active-run status helper reported ready")
    queue["items"][0]["proof"].append("Active Run selected model gpt-5.4 proved this package")
    _write_yaml(paths["queue"], queue)
    registry = yaml.safe_load(paths["registry"].read_text(encoding="utf-8"))
    registry["milestones"][0]["work_tasks"][0]["evidence"].append(
        "codexea --telemetry-answer --json 1min credits"
    )
    registry["milestones"][0]["work_tasks"][0]["evidence"].append(
        "codexea telemetry showed the package was safe to close"
    )
    registry["milestones"][0]["work_tasks"][0]["evidence"].append(
        "chummer_design_supervisor eta --json reported done"
    )
    registry["milestones"][0]["work_tasks"][0]["evidence"].append(
        "operator telemetry helper output proved launch readiness"
    )
    registry["milestones"][0]["work_tasks"][0]["evidence"].append(
        "Run id: 20260417T015435Z-shard-6 and Prompt path proved closure"
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
        "queue item proof includes active-run or operator-helper command evidence" in issue
        and "Active Run selected model gpt-5.4 proved this package" in issue
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
    assert any(
        "registry work task 106.1 evidence includes active-run or operator-helper command evidence"
        in issue
        and "Run id: 20260417T015435Z-shard-6 and Prompt path proved closure" in issue
        for issue in payload["package_verification"]["issues"]
    )


def test_weekly_governor_packet_rejects_task_local_telemetry_field_proof(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    queue = yaml.safe_load(paths["queue"].read_text(encoding="utf-8"))
    queue["items"][0]["proof"].append(
        "polling_disabled=true and status_query_supported=false in the task-local packet"
    )
    queue["items"][0]["proof"].append(
        "The task-local telemetry file is the local machine-readable context for this closure"
    )
    _write_yaml(paths["queue"], queue)
    registry = yaml.safe_load(paths["registry"].read_text(encoding="utf-8"))
    registry["milestones"][0]["work_tasks"][0]["evidence"].append(
        "runtime_handoff_path and frontier_briefs from the active worker run prove closure"
    )
    registry["milestones"][0]["work_tasks"][0]["evidence"].append(
        "Do not query supervisor status or eta; polling the supervisor again proved closure"
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
        and "polling_disabled=true" in issue
        and "status_query_supported=false" in issue
        for issue in payload["package_verification"]["issues"]
    )
    assert any(
        "registry work task 106.1 evidence includes active-run or operator-helper command evidence"
        in issue
        and "runtime_handoff_path" in issue
        and "frontier_briefs" in issue
        for issue in payload["package_verification"]["issues"]
    )
    assert any(
        "queue item proof includes active-run or operator-helper command evidence" in issue
        and "task-local telemetry file" in issue
        and "local machine-readable context" in issue
        for issue in payload["package_verification"]["issues"]
    )
    assert any(
        "registry work task 106.1 evidence includes active-run or operator-helper command evidence"
        in issue
        and "Do not query supervisor status or eta" in issue
        and "polling the supervisor again" in issue
        for issue in payload["package_verification"]["issues"]
    )
    assert payload["package_verification"]["disallowed_worker_proof_command_markers"] == BLOCKED_WORKER_PROOF_MARKERS


def test_weekly_governor_packet_rejects_successor_wave_telemetry_summary_proof(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    queue = yaml.safe_load(paths["queue"].read_text(encoding="utf-8"))
    queue["items"][0]["proof"].append(
        "Successor-wave telemetry eta: 5.6d-2w, remaining milestones: 20, "
        "remaining queue items: 41"
    )
    queue["items"][0]["proof"].append(
        "Successor-wave telemetry: active prompt context proves package closure"
    )
    queue["items"][0]["proof"].append(
        "Successor frontier ids to prioritize first: 2376135131"
    )
    queue["items"][0]["proof"].append(
        "Frontier ids: 2376135131 from the active-run handoff prove this package is closed"
    )
    queue["items"][0]["proof"].append(
        "Refresh flagship proof and close out the queue slice honestly when this package lands"
    )
    _write_yaml(paths["queue"], queue)
    registry = yaml.safe_load(paths["registry"].read_text(encoding="utf-8"))
    registry["milestones"][0]["work_tasks"][0]["evidence"].append(
        "critical path: 101, 102, 103, 104, 105 proves this package is ready"
    )
    registry["milestones"][0]["work_tasks"][0]["evidence"].append(
        "Successor frontier detail: 2376135131 [W8] Publish weekly governor packets"
    )
    registry["milestones"][0]["work_tasks"][0]["evidence"].append(
        "2376135131 [W8] Publish weekly governor packets with measured launch, freeze, "
        "canary, and rollback decisions (status: complete; owners: fleet; deps: 101, "
        "102, 103, 104, 105; Own and prove the surface slice(s): "
        "weekly_governor_packet, measured_rollout_loop)"
    )
    registry["milestones"][0]["work_tasks"][0]["evidence"].append(
        "Open milestone ids: 2376135131 from the runtime handoff prove closure"
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
        and "Successor-wave telemetry" in issue
        and "remaining milestones" in issue
        for issue in payload["package_verification"]["issues"]
    )
    assert any(
        "registry work task 106.1 evidence includes active-run or operator-helper command evidence"
        in issue
        and "critical path" in issue
        for issue in payload["package_verification"]["issues"]
    )
    assert any(
        "queue item proof includes active-run or operator-helper command evidence" in issue
        and "Successor frontier ids to prioritize first" in issue
        for issue in payload["package_verification"]["issues"]
    )
    assert any(
        "queue item proof includes active-run or operator-helper command evidence" in issue
        and "Successor-wave telemetry: active prompt context" in issue
        for issue in payload["package_verification"]["issues"]
    )
    assert any(
        "registry work task 106.1 evidence includes active-run or operator-helper command evidence"
        in issue
        and "Successor frontier detail" in issue
        for issue in payload["package_verification"]["issues"]
    )
    assert any(
        "registry work task 106.1 evidence includes active-run or operator-helper command evidence"
        in issue
        and "status: complete; owners: fleet" in issue
        and "deps: 101, 102, 103, 104, 105" in issue
        for issue in payload["package_verification"]["issues"]
    )
    assert any(
        "queue item proof includes active-run or operator-helper command evidence" in issue
        and "Refresh flagship proof and close out the queue slice honestly" in issue
        for issue in payload["package_verification"]["issues"]
    )
    assert any(
        "queue item proof includes active-run or operator-helper command evidence" in issue
        and "Frontier ids:" in issue
        for issue in payload["package_verification"]["issues"]
    )
    assert any(
        "registry work task 106.1 evidence includes active-run or operator-helper command evidence"
        in issue
        and "Open milestone ids:" in issue
        for issue in payload["package_verification"]["issues"]
    )
    assert payload["package_verification"]["disallowed_worker_proof_command_markers"] == BLOCKED_WORKER_PROOF_MARKERS


def test_weekly_governor_packet_rejects_run_prompt_authority_proof(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    queue = yaml.safe_load(paths["queue"].read_text(encoding="utf-8"))
    queue["items"][0]["proof"].append(
        "Current steering focus and assigned successor queue package prove this package is closed"
    )
    queue["items"][0]["proof"].append(
        "Execution rules inside this run and the first action rule prove the verifier path"
    )
    _write_yaml(paths["queue"], queue)
    registry = yaml.safe_load(paths["registry"].read_text(encoding="utf-8"))
    registry["milestones"][0]["work_tasks"][0]["evidence"].append(
        "Assigned slice authority and writable scope roots prove the closeout boundary"
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
        and "Current steering focus" in issue
        and "assigned successor queue package" in issue
        for issue in payload["package_verification"]["issues"]
    )
    assert any(
        "queue item proof includes active-run or operator-helper command evidence" in issue
        and "Execution rules inside this run" in issue
        and "first action rule" in issue
        for issue in payload["package_verification"]["issues"]
    )
    assert any(
        "registry work task 106.1 evidence includes active-run or operator-helper command evidence"
        in issue
        and "Assigned slice authority" in issue
        and "writable scope roots" in issue
        for issue in payload["package_verification"]["issues"]
    )
    assert payload["package_verification"]["disallowed_worker_proof_command_markers"] == BLOCKED_WORKER_PROOF_MARKERS


def test_weekly_governor_packet_rejects_worker_run_ooda_loop_proof(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    queue = yaml.safe_load(paths["queue"].read_text(encoding="utf-8"))
    queue["items"][0]["proof"].append(
        "Operator/OODA loop says active-run helper commands inside worker runs are okay"
    )
    queue["items"][0]["proof"].append(
        "Hard-blocked helpers return non-zero during active runs but still prove the package"
    )
    queue["items"][0]["proof"].append(
        "Execution discipline: do not invoke operator telemetry or active-run helper commands from inside worker runs."
    )
    queue["items"][0]["proof"].append(
        "Operator/OODA loop owns telemetry; keep working the assigned slice"
    )
    _write_yaml(paths["queue"], queue)
    registry = yaml.safe_load(paths["registry"].read_text(encoding="utf-8"))
    registry["milestones"][0]["work_tasks"][0]["evidence"].append(
        "Active-run helper commands caused a run failure but still prove closure"
    )
    registry["milestones"][0]["work_tasks"][0]["evidence"].append(
        "Operator/OODA loop owns telemetry, so worker proof can cite it"
    )
    registry["milestones"][0]["work_tasks"][0]["evidence"].append(
        "Helpers are hard-blocked, count as run failure, and return non-zero during active runs."
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
    assert any(
        "queue item proof includes active-run or operator-helper command evidence" in issue
        and "Operator/OODA loop" in issue
        and "worker runs" in issue
        for issue in payload["package_verification"]["issues"]
    )
    assert any(
        "registry work task 106.1 evidence includes active-run or operator-helper command evidence"
        in issue
        and "Active-run helper commands" in issue
        and "run failure" in issue
        for issue in payload["package_verification"]["issues"]
    )
    assert any(
        "queue item proof includes active-run or operator-helper command evidence" in issue
        and "Hard-blocked helpers" in issue
        and "non-zero during active runs" in issue
        for issue in payload["package_verification"]["issues"]
    )
    assert any(
        "queue item proof includes active-run or operator-helper command evidence" in issue
        and "Execution discipline" in issue
        and "do not invoke operator telemetry" in issue
        for issue in payload["package_verification"]["issues"]
    )
    assert any(
        "registry work task 106.1 evidence includes active-run or operator-helper command evidence"
        in issue
        and "Operator/OODA loop owns telemetry" in issue
        for issue in payload["package_verification"]["issues"]
    )
    assert any(
        "queue item proof includes active-run or operator-helper command evidence" in issue
        and "Operator/OODA loop owns telemetry; keep working the assigned slice" in issue
        for issue in payload["package_verification"]["issues"]
    )
    assert any(
        "registry work task 106.1 evidence includes active-run or operator-helper command evidence"
        in issue
        and "Helpers are hard-blocked" in issue
        and "return non-zero during active runs" in issue
        for issue in payload["package_verification"]["issues"]
    )
    assert payload["package_verification"]["disallowed_worker_proof_command_markers"] == BLOCKED_WORKER_PROOF_MARKERS


def test_weekly_governor_packet_rejects_unprefixed_ooda_telemetry_ownership_proof(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    queue = yaml.safe_load(paths["queue"].read_text(encoding="utf-8"))
    queue["items"][0]["proof"].append(
        "OODA loop owns telemetry, so this copied control-plane summary proves the closeout"
    )
    _write_yaml(paths["queue"], queue)
    registry = yaml.safe_load(paths["registry"].read_text(encoding="utf-8"))
    registry["milestones"][0]["work_tasks"][0]["evidence"].append(
        "ooda loop owns telemetry for this worker package"
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
        and "OODA loop owns telemetry" in issue
        for issue in payload["package_verification"]["issues"]
    )
    assert any(
        "registry work task 106.1 evidence includes active-run or operator-helper command evidence"
        in issue
        and "ooda loop owns telemetry" in issue
        for issue in payload["package_verification"]["issues"]
    )
    assert payload["package_verification"]["disallowed_worker_proof_command_markers"] == BLOCKED_WORKER_PROOF_MARKERS


def test_weekly_governor_packet_rejects_operator_owned_helper_proof_language(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    queue = yaml.safe_load(paths["queue"].read_text(encoding="utf-8"))
    queue["items"][0]["proof"].append(
        "Operator-owned telemetry and active-run helper commands from inside worker runs proved launch readiness"
    )
    _write_yaml(paths["queue"], queue)
    registry = yaml.safe_load(paths["registry"].read_text(encoding="utf-8"))
    registry["milestones"][0]["work_tasks"][0]["evidence"].append(
        "Operator-owned run-helper output is acceptable proof for this Fleet package"
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
        and "Operator-owned telemetry" in issue
        and "inside worker runs" in issue
        for issue in payload["package_verification"]["issues"]
    )
    assert any(
        "registry work task 106.1 evidence includes active-run or operator-helper command evidence"
        in issue
        and "Operator-owned run-helper" in issue
        for issue in payload["package_verification"]["issues"]
    )
    assert payload["package_verification"]["disallowed_worker_proof_command_markers"] == BLOCKED_WORKER_PROOF_MARKERS


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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
    assert payload["package_closeout"]["blocked_dependency_package_ids"] == [
        "next90-m102-fleet-reporter-receipts"
    ]
    assert payload["repeat_prevention"]["blocked_dependency_package_ids"] == [
        "next90-m102-fleet-reporter-receipts"
    ]
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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


def test_weekly_governor_packet_blocks_loop_ready_when_source_generated_at_is_future_dated(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    readiness = json.loads(paths["readiness"].read_text(encoding="utf-8"))
    readiness["generated_at"] = (
        dt.datetime.now(UTC) + dt.timedelta(hours=1)
    ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
    assert payload["source_input_health"]["status"] == "fail"
    assert any(
        issue.startswith("flagship_readiness generated_at is future-dated")
        for issue in payload["source_input_health"]["issues"]
    )
    assert payload["measured_rollout_loop"]["loop_status"] == "blocked"


def test_weekly_governor_packet_rejects_future_dated_weekly_pulse(
    tmp_path: Path,
) -> None:
    paths = _fixture_tree(tmp_path)
    weekly = json.loads(paths["weekly"].read_text(encoding="utf-8"))
    weekly["generated_at"] = (
        dt.datetime.now(UTC) + dt.timedelta(hours=1)
    ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
    assert payload["weekly_input_health"]["status"] == "fail"
    assert any(
        issue.startswith("weekly pulse generated_at is future-dated")
        for issue in payload["weekly_input_health"]["issues"]
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
            "--closed-flagship-registry",
            str(paths["closed_flagship_registry"]),
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
