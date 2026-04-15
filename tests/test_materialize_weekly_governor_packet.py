from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import yaml


SCRIPT = Path("/docker/fleet/scripts/materialize_weekly_governor_packet.py")
UTC = dt.timezone.utc


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
    queue = published / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    weekly = published / "WEEKLY_PRODUCT_PULSE.generated.json"
    readiness = published / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    journeys = published / "JOURNEY_GATES.generated.json"
    support = published / "SUPPORT_CASE_PACKETS.generated.json"
    status = published / "STATUS_PLANE.generated.yaml"
    projects = root / "config" / "projects"
    projects.mkdir(parents=True, exist_ok=True)
    _write_yaml(projects / "fleet.yaml", {"id": "fleet", "path": str(root), "queue": []})
    _write_yaml(
        registry,
        {
            "product": "chummer",
            "program_wave": "next_90_day_product_advance",
            "milestones": [
                {
                    "id": 106,
                    "title": "Product-governor weekly adoption and measured rollout loop",
                    "status": "in_progress",
                    "owners": ["fleet", "executive-assistant", "chummer6-design", "chummer6-hub"],
                    "dependencies": [101, 102, 103, 104, 105],
                }
            ],
        },
    )
    _write_yaml(
        queue,
        {
            "program_wave": "next_90_day_product_advance",
            "items": [
                {
                    "title": "Publish weekly governor packets with measured launch, freeze, canary, and rollback decisions",
                    "task": "Turn readiness, parity, support, and rollout truth into a weekly governor packet that drives measured product decisions.",
                    "package_id": "next90-m106-fleet-governor-packet",
                    "milestone_id": 106,
                    "repo": "fleet",
                    "allowed_paths": ["admin", "scripts", "tests", ".codex-studio"],
                    "owned_surfaces": ["weekly_governor_packet", "measured_rollout_loop"],
                }
            ],
        },
    )
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
    _write_json(journeys, {"summary": {"overall_state": "ready"}})
    _write_json(
        support,
        {
            "summary": {
                "open_packet_count": 0,
                "open_non_external_packet_count": 0,
                "closure_waiting_on_release_truth": 0,
                "update_required_misrouted_case_count": 0,
            }
        },
    )
    _write_yaml(status, {"whole_product_final_claim_status": "pass"})
    return {
        "root": root,
        "published": published,
        "registry": registry,
        "queue": queue,
        "weekly": weekly,
        "readiness": readiness,
        "journeys": journeys,
        "support": support,
        "status": status,
    }


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
    assert payload["package_verification"]["status"] == "pass"
    assert payload["weekly_input_health"]["status"] == "pass"
    assert payload["package_verification"]["registry_dependencies"] == [101, 102, 103, 104, 105]
    assert payload["decision_board"]["launch_expand"]["state"] == "blocked"
    assert payload["decision_board"]["freeze_launch"]["state"] == "active"
    assert payload["decision_board"]["canary"]["state"] == "accumulating"
    assert payload["decision_board"]["rollback"]["state"] == "armed"
    assert payload["truth_inputs"]["flagship_parity_release_truth"]["release_truth_status"] == "gold_ready"
    assert payload["measured_rollout_loop"]["loop_status"] == "ready"
    assert payload["measured_rollout_loop"]["required_decision_actions"] == [
        "launch_expand",
        "freeze_launch",
        "canary",
        "rollback",
        "focus_shift",
    ]
    manifest = json.loads((paths["published"] / "compile.manifest.json").read_text(encoding="utf-8"))
    assert "WEEKLY_GOVERNOR_PACKET.generated.json" in manifest["artifacts"]


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
    assert "queue item allowed_paths no longer match package authority" in payload["package_verification"]["issues"]
    assert payload["measured_rollout_loop"]["loop_status"] == "blocked"


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
    assert "provider_canary_status" in payload["weekly_input_health"]["issues"][0]
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
