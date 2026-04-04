from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
from argparse import Namespace
from pathlib import Path

import yaml


MODULE_PATH = Path("/docker/fleet/scripts/chummer_design_supervisor.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("chummer_design_supervisor", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


def _worktree_fingerprint(root: Path, *, exclude_paths: tuple[Path, ...] = ()) -> tuple[str, int]:
    exclude_markers: list[str] = []
    for candidate in exclude_paths:
        try:
            relative = candidate.resolve().relative_to(root.resolve())
        except Exception:
            continue
        marker = relative.as_posix().rstrip("/")
        if marker:
            exclude_markers.append(marker)

    def is_excluded(relative: str) -> bool:
        return any(relative == marker or relative.startswith(f"{marker}/") for marker in exclude_markers)

    entries: list[str] = []
    if (root / ".git").exists():
        listing = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            check=True,
            capture_output=True,
        ).stdout.decode("utf-8", errors="surrogateescape")
        seen: set[str] = set()
        for raw_item in listing.split("\0"):
            relative = raw_item.strip()
            if not relative or relative in seen or is_excluded(relative):
                continue
            seen.add(relative)
            entries.append(relative)
        entries.sort()
    else:
        for path in sorted(root.rglob("*")):
            if path == root / ".git":
                continue
            try:
                relative = path.relative_to(root).as_posix()
            except Exception:
                continue
            if relative == ".git" or relative.startswith(".git/") or is_excluded(relative):
                continue
            if path.is_dir():
                continue
            entries.append(relative)

    digest = hashlib.sha256()
    entry_count = 0
    for relative in entries:
        path = root / relative
        try:
            stat_result = os.lstat(path)
        except FileNotFoundError:
            digest.update(f"missing\0{relative}\0".encode("utf-8"))
            entry_count += 1
            continue
        mode = stat.S_IMODE(stat_result.st_mode)
        if stat.S_ISLNK(stat_result.st_mode):
            digest.update(f"symlink\0{relative}\0{mode:o}\0{os.readlink(path)}\0".encode("utf-8"))
            entry_count += 1
            continue
        if not stat.S_ISREG(stat_result.st_mode):
            continue
        digest.update(f"file\0{relative}\0{mode:o}\0".encode("utf-8"))
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        digest.update(b"\0")
        entry_count += 1
    return digest.hexdigest(), entry_count


def _write_registry(path: Path) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "waves": [
                    {"id": "W1"},
                    {"id": "W2"},
                    {"id": "W3"},
                    {"id": "W4"},
                ],
                "milestones": [
                    {
                        "id": 6,
                        "title": "Build Lab progression planner",
                        "wave": "W2",
                        "status": "in_progress",
                        "owners": ["chummer6-core", "chummer6-ui"],
                        "exit_criteria": ["Planner exists."],
                        "dependencies": [1],
                    },
                    {
                        "id": 15,
                        "title": "Artifact shelf v2",
                        "wave": "W3",
                        "status": "in_progress",
                        "owners": ["chummer6-hub", "chummer6-ui"],
                        "exit_criteria": ["Views exist."],
                        "dependencies": [11, 13],
                    },
                    {
                        "id": 18,
                        "title": "Public trust surface v3",
                        "wave": "W4",
                        "status": "in_progress",
                        "owners": ["chummer6-hub", "fleet"],
                        "exit_criteria": ["Trust rows are visible."],
                        "dependencies": [15, 17],
                    },
                    {
                        "id": 19,
                        "title": "Guided onboarding",
                        "wave": "W4",
                        "status": "not_started",
                        "owners": ["chummer6-ui", "chummer6-hub"],
                        "exit_criteria": ["Starter lane is real."],
                        "dependencies": [18],
                    },
                    {
                        "id": 21,
                        "title": "Rules Navigator v2",
                        "wave": "W2",
                        "status": "not_started",
                        "owners": ["chummer6-core", "chummer6-ui", "chummer6-hub"],
                        "exit_criteria": ["SR4, SR5, and SR6 rule diffs are visible."],
                        "dependencies": [6],
                    },
                    {
                        "id": 20,
                        "title": "Pulse v2",
                        "wave": "W4",
                        "status": "complete",
                        "owners": ["fleet"],
                        "exit_criteria": ["Done."],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def _args(root: Path) -> Namespace:
    return Namespace(
        command="once",
        registry_path=str(root / "registry.yaml"),
        program_milestones_path=str(root / "PROGRAM_MILESTONES.yaml"),
        roadmap_path=str(root / "ROADMAP.md"),
        handoff_path=str(root / "NEXT_SESSION_HANDOFF.md"),
        projects_dir=str(root / "projects"),
        journey_gates_path=str(root / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"),
        weekly_pulse_path=str(root / "WEEKLY_PRODUCT_PULSE.generated.json"),
        accounts_path=str(root / "accounts.yaml"),
        workspace_root=str(root),
        scope_root=[str(root / "extra"), str(root / "more")],
        state_root=str(root / "state"),
        status_plane_path=str(root / "STATUS_PLANE.generated.yaml"),
        progress_report_path=str(root / "PROGRESS_REPORT.generated.json"),
        progress_history_path=str(root / "PROGRESS_HISTORY.generated.json"),
        support_packets_path=str(root / "SUPPORT_CASE_PACKETS.generated.json"),
        flagship_product_readiness_path=str(root / "FLAGSHIP_PRODUCT_READINESS.generated.json"),
        ui_linux_desktop_exit_gate_path=str(root / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"),
        ui_executable_exit_gate_path=str(root / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"),
        ui_linux_desktop_repo_root=str(root),
        worker_bin="codex",
        worker_model="gpt-5.4",
        worker_lane="",
        fallback_worker_model=[],
        fallback_worker_lane=[],
        frontier_id=[],
        account_owner_id=[],
        account_alias=[],
        focus_owner=[],
        focus_profile=[],
        focus_text=[],
        dry_run=False,
        worker_timeout_seconds=0.0,
        ea_provider_health_url="http://127.0.0.1:8090/v1/responses/_provider_health",
        ea_provider_health_timeout_seconds=4.0,
    )


def test_default_worker_timeout_seconds_tracks_stream_budget(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(
        module,
        "_runtime_env_default",
        lambda name, default="": {
            "CHUMMER_DESIGN_SUPERVISOR_STREAM_IDLE_TIMEOUT_MS": "900000",
            "CHUMMER_DESIGN_SUPERVISOR_STREAM_MAX_RETRIES": "8",
        }.get(name, default),
    )

    assert module._default_worker_timeout_seconds() == 9000.0


def test_candidate_models_for_account_respects_allowed_models() -> None:
    module = _load_module()
    account = module.WorkerAccount(
        alias="acct-chatgpt-b",
        owner_id="the.girscheles",
        auth_kind="chatgpt_auth_json",
        auth_json_file="/run/secrets/acct-chatgpt-b.auth.json",
        api_key_env="",
        api_key_file="",
        allowed_models=["gpt-5.3-codex"],
        health_state="ready",
        spark_enabled=False,
        bridge_priority=0,
        forced_login_method="",
        forced_chatgpt_workspace_id="",
        openai_base_url="",
        home_dir="",
    )

    models = module._candidate_models_for_account(
        account,
        ["gpt-5.3-codex", "gpt-5.3-codex-spark", "gpt-5.4"],
        {},
    )

    assert models == ["gpt-5.3-codex"]


def test_explicit_worker_timeout_seconds_overrides_stream_budget(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(
        module,
        "_runtime_env_default",
        lambda name, default="": {
            "CHUMMER_DESIGN_SUPERVISOR_WORKER_TIMEOUT_SECONDS": "21600",
            "CHUMMER_DESIGN_SUPERVISOR_STREAM_IDLE_TIMEOUT_MS": "900000",
            "CHUMMER_DESIGN_SUPERVISOR_STREAM_MAX_RETRIES": "8",
        }.get(name, default),
    )

    assert module._default_worker_timeout_seconds() == 21600.0


def test_default_worker_timeout_seconds_tracks_codexea_stream_budget(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(
        module,
        "_runtime_env_default",
        lambda name, default="": {
            "CODEXEA_STREAM_IDLE_TIMEOUT_MS": "900000",
            "CODEXEA_STREAM_MAX_RETRIES": "8",
        }.get(name, default),
    )

    assert module._default_worker_timeout_seconds() == 9000.0


def test_derive_context_applies_focus_within_explicit_handoff_frontier() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text(
            "\n".join(
                [
                    "# Handoff",
                    "",
                    "Current active frontier from design plus handoff:",
                    "- `6` Build Lab progression planner",
                    "- `15` Artifact shelf v2",
                    "- `18` Public trust surface v3",
                    "- `19` Guided onboarding",
                    "- `21` Rules Navigator v2",
                    "",
                    "Frontier milestone ids to prioritize first: 6, 15, 18, 19, 21",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        args = _args(root)
        args.focus_owner = ["chummer6-hub"]
        args.focus_text = ["trust", "publication"]

        context = module.derive_context(args)

        assert [item.id for item in context["frontier"]] == [18, 15, 19, 21]


def test_derive_context_honors_frontier_id_override_without_shard_reslicing() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text(
            "Frontier milestone ids to prioritize first: 6, 15, 18, 19, 21\n",
            encoding="utf-8",
        )
        aggregate_root = root / "state" / "chummer_design_supervisor"
        shard_roots = [aggregate_root / f"shard-{index}" for index in range(1, 6)]
        for shard_root in shard_roots:
            shard_root.mkdir(parents=True, exist_ok=True)
        (aggregate_root / "active_shards.json").write_text(
            json.dumps({"active_shards": [path.name for path in shard_roots]}),
            encoding="utf-8",
        )
        args = _args(root)
        args.state_root = str(shard_roots[3])
        args.frontier_id = [6, 15, 18, 19]

        context = module.derive_context(args)

        assert [item.id for item in context["frontier"]] == [6, 15, 18, 19]
        assert [item.id for item in context["open_milestones"]] == [6, 15, 18, 19]


def test_status_command_on_shard_root_reports_shard_local_frontier_not_aggregate_union() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}, {"id": "W2"}],
                    "milestones": [
                        {
                            "id": 1,
                            "title": "Install lane",
                            "wave": "W1",
                            "status": "planned",
                            "owners": ["chummer6-ui"],
                            "exit_criteria": ["Install lane exists."],
                        },
                        {
                            "id": 2,
                            "title": "Workbench lane",
                            "wave": "W1",
                            "status": "planned",
                            "owners": ["chummer6-ui"],
                            "exit_criteria": ["Workbench exists."],
                        },
                        {
                            "id": 13,
                            "title": "Sourcebook parity",
                            "wave": "W2",
                            "status": "planned",
                            "owners": ["chummer6-core"],
                            "exit_criteria": ["Sourcebooks exist."],
                        },
                        {
                            "id": 14,
                            "title": "Settings parity",
                            "wave": "W2",
                            "status": "planned",
                            "owners": ["chummer6-core"],
                            "exit_criteria": ["Settings exist."],
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text(
            "Frontier milestone ids to prioritize first: 1, 2, 13, 14\n",
            encoding="utf-8",
        )
        aggregate_root = root / "state" / "chummer_design_supervisor"
        shard_one = aggregate_root / "shard-1"
        shard_two = aggregate_root / "shard-2"
        for shard_root, frontier_ids in ((shard_one, [13, 14]), (shard_two, [1, 2])):
            shard_root.mkdir(parents=True, exist_ok=True)
            (shard_root / "state.json").write_text(
                json.dumps(
                    {
                        "updated_at": "2026-04-04T15:20:00Z",
                        "mode": "loop",
                        "frontier_ids": frontier_ids,
                        "open_milestone_ids": [1, 2, 13, 14],
                    }
                ),
                encoding="utf-8",
            )
        (aggregate_root / "active_shards.json").write_text(
            json.dumps(
                {
                    "generated_at": "2026-04-04T15:20:00Z",
                    "topology_fingerprint": "abc123",
                    "active_shards": [
                        {"name": "shard-1", "index": 1, "frontier_ids": [13, 14]},
                        {"name": "shard-2", "index": 2, "frontier_ids": [1, 2]},
                    ],
                }
            ),
            encoding="utf-8",
        )

        result = subprocess.run(
            [
                sys.executable,
                str(MODULE_PATH),
                "status",
                "--json",
                "--registry-path",
                str(root / "registry.yaml"),
                "--program-milestones-path",
                str(root / "PROGRAM_MILESTONES.yaml"),
                "--roadmap-path",
                str(root / "ROADMAP.md"),
                "--handoff-path",
                str(root / "NEXT_SESSION_HANDOFF.md"),
                "--workspace-root",
                str(root),
                "--state-root",
                str(shard_one),
                "--frontier-id",
                "13",
                "--frontier-id",
                "14",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(result.stdout)

        assert payload["frontier_ids"] == [13, 14]
        assert "shards" not in payload


def _write_project_backlog(root: Path, *, project_id: str, repo_slug: str, task: str) -> None:
    projects_dir = root / "projects"
    projects_dir.mkdir(parents=True, exist_ok=True)
    (projects_dir / f"{project_id}.yaml").write_text(
        yaml.safe_dump(
            {
                "id": project_id,
                "path": str(root),
                "review": {"repo": repo_slug},
                "queue": [],
                "queue_sources": [{"kind": "worklist", "path": "WORKLIST.md", "mode": "replace"}],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (root / "WORKLIST.md").write_text(f"- [queued] wl-1 {task}\n", encoding="utf-8")


def _write_project_backlog_tasks(root: Path, *, project_id: str, repo_slug: str, tasks: list[str]) -> None:
    projects_dir = root / "projects"
    projects_dir.mkdir(parents=True, exist_ok=True)
    (projects_dir / f"{project_id}.yaml").write_text(
        yaml.safe_dump(
            {
                "id": project_id,
                "path": str(root),
                "review": {"repo": repo_slug},
                "queue": [],
                "queue_sources": [{"kind": "worklist", "path": "WORKLIST.md", "mode": "replace"}],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (root / "WORKLIST.md").write_text(
        "\n".join(f"- [queued] wl-{index + 1} {task}" for index, task in enumerate(tasks)) + "\n",
        encoding="utf-8",
    )


def _write_completion_evidence(
    root: Path,
    *,
    ui_posture: str = "public",
    ui_stage: str = "publicly_promoted",
    design_drift_count: int = 0,
    public_promise_drift_count: int = 0,
    oldest_blocker_days: int = 0,
    release_health_state: str = "green_or_explained",
    journey_gate_health_state: str = "ready",
    active_wave_status: str = "complete",
    automation_alignment_state: str = "aligned",
    write_linux_desktop_exit_gate: bool = True,
    linux_desktop_exit_gate_status: str = "passed",
    linux_desktop_exit_gate_test_total: int = 14,
    linux_desktop_exit_gate_test_failed: int = 0,
    linux_desktop_exit_gate_test_skipped: int = 0,
    linux_desktop_exit_gate_generated_at: str | None = None,
    linux_desktop_exit_gate_app_key: str = "avalonia",
    linux_desktop_exit_gate_launch_target: str = "Chummer.Avalonia",
    linux_desktop_exit_gate_test_project_path: str = "Chummer.Desktop.Runtime.Tests/Chummer.Desktop.Runtime.Tests.csproj",
    linux_desktop_exit_gate_test_assembly_name: str = "Chummer.Desktop.Runtime.Tests.dll",
) -> None:
    now_text = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    (root / "UI_LOCAL_RELEASE_PROOF.generated.json").write_text(
        json.dumps({"contract_name": "chummer6-ui.local_release_proof", "status": "passed"}),
        encoding="utf-8",
    )
    (root / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json").write_text(
        json.dumps(
            {
                "contract_name": "chummer6-ui.desktop_executable_exit_gate",
                "status": "pass",
                "generatedAt": now_text,
            }
        ),
        encoding="utf-8",
    )
    (root / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json").write_text(
        json.dumps({"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass"}),
        encoding="utf-8",
    )
    (root / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json").write_text(
        json.dumps({"contract_name": "chummer6-ui.desktop_visual_familiarity_exit_gate", "status": "pass"}),
        encoding="utf-8",
    )
    (root / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json").write_text(
        json.dumps({"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"}),
        encoding="utf-8",
    )
    (root / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json").write_text(
        json.dumps({"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"}),
        encoding="utf-8",
    )
    (root / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json").write_text(
        json.dumps({"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"}),
        encoding="utf-8",
    )
    (root / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json").write_text(
        json.dumps({"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"}),
        encoding="utf-8",
    )
    (root / "GOLDEN_JOURNEY_RELEASE_GATES.yaml").write_text(
        yaml.safe_dump(
            {
                "product": "chummer",
                "journey_gates": [
                    {
                        "id": "desktop_release_truth",
                        "title": "Desktop release truth",
                        "user_promise": "Desktop release truth is boringly proven.",
                        "canonical_journeys": ["journeys/install-and-update.md"],
                        "owner_repos": ["chummer6-ui", "fleet"],
                        "scorecard_refs": {},
                        "fleet_gate": {
                            "required_artifacts": ["status_plane", "progress_report"],
                            "minimum_history_snapshots": 2,
                            "target_history_snapshots": 4,
                            "required_project_posture": [
                                {
                                    "project_id": "ui",
                                    "minimum_stage": "pre_repo_local_complete",
                                    "target_stage": "publicly_promoted",
                                    "minimum_deployment_posture": "protected_preview",
                                    "target_deployment_posture": "public",
                                }
                            ],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (root / "STATUS_PLANE.generated.yaml").write_text(
        yaml.safe_dump(
            {
                "contract_name": "fleet.status_plane",
                "generated_at": now_text,
                "projects": [
                    {
                        "id": "ui",
                        "readiness_stage": ui_stage,
                        "deployment_access_posture": ui_posture,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (root / "PROGRESS_REPORT.generated.json").write_text(
        json.dumps({"generated_at": now_text, "history_snapshot_count": 4}),
        encoding="utf-8",
    )
    (root / "PROGRESS_HISTORY.generated.json").write_text(
        json.dumps({"generated_at": now_text, "snapshot_count": 4}),
        encoding="utf-8",
    )
    (root / "SUPPORT_CASE_PACKETS.generated.json").write_text(
        json.dumps(
            {
                "generated_at": now_text,
                "summary": {
                    "closure_waiting_on_release_truth": 0,
                    "needs_human_response": 0,
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "WEEKLY_PRODUCT_PULSE.generated.json").write_text(
        json.dumps(
            {
                "contract_name": "chummer.weekly_product_pulse",
                "contract_version": 3,
                "generated_at": now_text,
                "as_of": now_text[:10],
                "active_wave": "Next 20 Big Wins After Post-Audit Closeout",
                "active_wave_status": active_wave_status,
                "release_health": {
                    "state": release_health_state,
                    "reason": "green",
                },
                "flagship_readiness": {
                    "state": "ready",
                    "reason": "fixture",
                },
                "rule_environment_trust": {
                    "state": "ready",
                    "reason": "fixture",
                },
                "journey_gate_health": {
                    "state": journey_gate_health_state,
                    "reason": "steady",
                    "blocked_count": 0,
                    "warning_count": 0,
                },
                "edition_authorship_and_import_confidence": {
                    "state": "monitor",
                    "reason": "fixture",
                },
                "top_support_or_feedback_clusters": [],
                "oldest_blocker_days": oldest_blocker_days,
                "design_drift_count": design_drift_count,
                "public_promise_drift_count": public_promise_drift_count,
                "governor_decisions": [
                    {
                        "decision_id": "fixture-focus",
                        "action": "focus_shift",
                        "reason": "fixture",
                        "cited_signals": [
                            "overall_progress_percent=100",
                        ],
                    },
                    {
                        "decision_id": "fixture-launch",
                        "action": "freeze_launch",
                        "reason": "fixture",
                        "cited_signals": [
                            "journey_gate_state=ready",
                            "journey_gate_blocked_count=0",
                            "local_release_proof_status=passed",
                            "provider_canary_status=Canary green on all active lanes",
                            "closure_health_state=clear",
                        ],
                    },
                ],
                "next_checkpoint_question": "What remains?",
                "snapshot": {
                    "release_health": {
                        "state": release_health_state,
                        "reason": "green",
                    },
                    "flagship_readiness": {
                        "state": "ready",
                        "reason": "fixture",
                    },
                    "rule_environment_trust": {
                        "state": "ready",
                        "reason": "fixture",
                    },
                    "journey_gate_health": {
                        "state": journey_gate_health_state,
                        "reason": "steady",
                        "blocked_count": 0,
                        "warning_count": 0,
                    },
                    "edition_authorship_and_import_confidence": {
                        "state": "monitor",
                        "reason": "fixture",
                    },
                    "top_support_or_feedback_clusters": [],
                    "oldest_blocker_days": oldest_blocker_days,
                    "design_drift_count": design_drift_count,
                    "public_promise_drift_count": public_promise_drift_count,
                    "governor_decisions": [
                        {
                            "decision_id": "fixture-focus",
                            "action": "focus_shift",
                            "reason": "fixture",
                            "cited_signals": [
                                "overall_progress_percent=100",
                            ],
                        },
                        {
                            "decision_id": "fixture-launch",
                            "action": "freeze_launch",
                            "reason": "fixture",
                            "cited_signals": [
                                "journey_gate_state=ready",
                                "journey_gate_blocked_count=0",
                                "local_release_proof_status=passed",
                                "provider_canary_status=Canary green on all active lanes",
                                "closure_health_state=clear",
                            ],
                        },
                    ],
                    "next_checkpoint_question": "What remains?",
                },
                "supporting_signals": {
                    "launch_readiness": "fixture",
                    "provider_route_stewardship": {
                        "canary_status": "Canary green on all active lanes",
                        "next_decision": "fixture",
                    },
                    "automation_alignment": {
                        "state": automation_alignment_state,
                        "active_wave_registry": "products/chummer/NEXT_12_BIGGEST_WINS_REGISTRY.yaml",
                        "active_open_milestone_ids": [10, 11, 12, 15],
                        "handoff_frontier_milestone_ids": [10, 11, 12, 15],
                        "out_of_program_frontier_milestone_ids": [],
                        "summary": "fixture",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    if write_linux_desktop_exit_gate:
        linux_gate_generated_at = linux_desktop_exit_gate_generated_at or now_text
        linux_gate_test_passed = max(
            0,
            linux_desktop_exit_gate_test_total
            - linux_desktop_exit_gate_test_failed
            - linux_desktop_exit_gate_test_skipped,
        )
        output_base_root = root / ".codex-studio" / "out" / "linux-desktop-exit-gate"
        run_root = output_base_root / "run.fixture"
        publish_dir = run_root / "publish" / "avalonia-linux-x64"
        dist_dir = run_root / "dist"
        test_results_dir = run_root / "test-results"
        archive_smoke_dir = run_root / "startup-smoke-archive"
        installer_smoke_dir = run_root / "startup-smoke-installer"
        publish_dir.mkdir(parents=True, exist_ok=True)
        dist_dir.mkdir(parents=True, exist_ok=True)
        test_results_dir.mkdir(parents=True, exist_ok=True)
        archive_smoke_dir.mkdir(parents=True, exist_ok=True)
        installer_smoke_dir.mkdir(parents=True, exist_ok=True)
        binary_path = publish_dir / linux_desktop_exit_gate_launch_target
        archive_path = dist_dir / "chummer-avalonia-linux-x64.tar.gz"
        installer_path = dist_dir / "chummer-avalonia-linux-x64-installer.deb"
        snapshot_root = root / ".linux-desktop-exit-gate-source.fixture"
        snapshot_root.mkdir(parents=True, exist_ok=True)
        binary_path.write_text("binary\n", encoding="utf-8")
        archive_path.write_text("archive\n", encoding="utf-8")
        installer_path.write_text("installer\n", encoding="utf-8")
        os.chmod(binary_path, 0o755)
        archive_digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
        installer_digest = hashlib.sha256(installer_path.read_bytes()).hexdigest()
        installed_launch_sha = hashlib.sha256(binary_path.read_bytes()).hexdigest()
        wrapper_content = (
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            'exec "/opt/chummer6/avalonia-linux-x64/Chummer.Avalonia" "$@"\n'
        )
        desktop_entry_content = (
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=Chummer\n"
            "Exec=/usr/bin/chummer6-avalonia\n"
            "Icon=/opt/chummer6/avalonia-linux-x64/chummer-icon.png\n"
            "Terminal=false\n"
            "Categories=Game;\n"
            "StartupNotify=true\n"
        )
        receipt_payload = {
            "headId": linux_desktop_exit_gate_app_key,
            "platform": "linux",
            "arch": "x64",
            "readyCheckpoint": "pre_ui_event_loop",
            "channelId": "local-hard-gate",
            "version": "local-hard-gate",
            "processPath": str(binary_path),
        }
        installer_receipt_payload = dict(receipt_payload)
        installer_receipt_payload["artifactDigest"] = f"sha256:{installer_digest}"
        archive_receipt_payload = dict(receipt_payload)
        archive_receipt_payload["artifactDigest"] = f"sha256:{archive_digest}"
        installer_receipt_path = installer_smoke_dir / "startup-smoke-avalonia-linux-x64.receipt.json"
        archive_receipt_path = archive_smoke_dir / "startup-smoke-avalonia-linux-x64.receipt.json"
        install_verification_path = installer_smoke_dir / "install-verification-avalonia-linux-x64.json"
        dpkg_log_path = installer_smoke_dir / "dpkg-avalonia-linux-x64.log"
        installed_launch_capture_path = installer_smoke_dir / "installed-launch-avalonia-linux-x64.bin"
        wrapper_capture_path = installer_smoke_dir / "installed-wrapper-avalonia-linux-x64.sh"
        desktop_entry_capture_path = installer_smoke_dir / "installed-desktop-entry-avalonia-linux-x64.desktop"
        installer_receipt_payload["artifactInstallMode"] = "dpkg_rootless_install"
        installer_receipt_payload["artifactInstallVerificationPath"] = str(install_verification_path)
        installer_receipt_path.write_text(json.dumps(installer_receipt_payload), encoding="utf-8")
        archive_receipt_path.write_text(json.dumps(archive_receipt_payload), encoding="utf-8")
        installed_launch_capture_path.write_bytes(binary_path.read_bytes())
        wrapper_capture_path.write_text(wrapper_content, encoding="utf-8")
        desktop_entry_capture_path.write_text(desktop_entry_content, encoding="utf-8")
        dpkg_log_path.write_text(
            "\n".join(
                [
                    "2026-03-31 11:33:24 install chummer6-avalonia:amd64 <none> 0~local-hard-gate",
                    "2026-03-31 11:33:26 status installed chummer6-avalonia:amd64 0~local-hard-gate",
                    "2026-03-31 11:33:26 remove chummer6-avalonia:amd64 0~local-hard-gate <none>",
                    "2026-03-31 11:33:26 status not-installed chummer6-avalonia:amd64 <none>",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        install_verification_path.write_text(
            json.dumps(
                {
                    "mode": "dpkg_rootless_install",
                    "packageName": "chummer6-avalonia",
                    "packageArch": "amd64",
                    "installRoot": str(root / "tmp-install-root"),
                    "dpkgAdminDir": str(root / "tmp-install-root" / "var" / "lib" / "dpkg"),
                    "dpkgLogPath": str(dpkg_log_path),
                    "installedLaunchPath": str(root / "tmp-install-root" / "opt" / "chummer6" / "avalonia-linux-x64" / linux_desktop_exit_gate_launch_target),
                    "installedLaunchCapturePath": str(installed_launch_capture_path),
                    "installedLaunchPathSha256": installed_launch_sha,
                    "wrapperPath": str(root / "tmp-install-root" / "usr" / "bin" / "chummer6-avalonia"),
                    "wrapperCapturePath": str(wrapper_capture_path),
                    "wrapperSha256": hashlib.sha256(wrapper_content.encode("utf-8")).hexdigest(),
                    "wrapperContent": wrapper_content,
                    "desktopEntryPath": str(root / "tmp-install-root" / "usr" / "share" / "applications" / "chummer6-avalonia.desktop"),
                    "desktopEntryCapturePath": str(desktop_entry_capture_path),
                    "desktopEntrySha256": hashlib.sha256(desktop_entry_content.encode("utf-8")).hexdigest(),
                    "desktopEntryContent": desktop_entry_content,
                    "statusAfterInstall": "install ok installed",
                    "statusAfterPurge": "not-installed",
                    "installedLaunchPathExistsAfterInstall": True,
                    "wrapperExistsAfterInstall": True,
                    "desktopEntryExistsAfterInstall": True,
                    "installedLaunchPathExistsAfterPurge": False,
                    "wrapperExistsAfterPurge": False,
                    "desktopEntryExistsAfterPurge": False,
                }
            ),
            encoding="utf-8",
        )
        test_code_base = (
            root
            / "Chummer.Desktop.Runtime.Tests"
            / "bin"
            / "Release"
            / "net10.0"
            / linux_desktop_exit_gate_test_assembly_name
        )
        (test_results_dir / "desktop-runtime-tests.trx").write_text(
            (
                "<TestRun>"
                "<Results>"
                "<UnitTestResult executionId=\"execution-1\" testId=\"test-1\" testName=\"DesktopSmoke\" outcome=\"Passed\" />"
                "</Results>"
                "<TestDefinitions>"
                f"<UnitTest name=\"DesktopSmoke\" storage=\"{test_code_base}\">"
                "<Execution id=\"execution-1\" />"
                f"<TestMethod codeBase=\"{test_code_base}\" className=\"Chummer.Tests.DesktopSmoke\" name=\"DesktopSmoke\" />"
                "</UnitTest>"
                "</TestDefinitions>"
                "<ResultSummary>"
                f"<Counters total=\"{linux_desktop_exit_gate_test_total}\" "
                f"passed=\"{linux_gate_test_passed}\" "
                f"failed=\"{linux_desktop_exit_gate_test_failed}\" "
                f"skipped=\"{linux_desktop_exit_gate_test_skipped}\" />"
                "</ResultSummary>"
                "</TestRun>"
            ),
            encoding="utf-8",
        )
        worktree_sha, worktree_entry_count = _worktree_fingerprint(
            root,
            exclude_paths=(output_base_root, root / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"),
        )
        (root / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json").write_text(
            json.dumps(
                {
                    "contract_name": "chummer6-ui.linux_desktop_exit_gate",
                    "generated_at": linux_gate_generated_at,
                    "status": linux_desktop_exit_gate_status,
                    "reason": (
                        "linux desktop build, startup smoke, and unit tests passed"
                        if linux_desktop_exit_gate_status == "passed"
                        else "stage unit_tests failed"
                    ),
                    "stage": "complete" if linux_desktop_exit_gate_status == "passed" else "unit_tests",
                    "run_root": str(run_root),
                    "head": {
                        "app_key": linux_desktop_exit_gate_app_key,
                        "project_path": "Chummer.Avalonia/Chummer.Avalonia.csproj",
                        "launch_target": linux_desktop_exit_gate_launch_target,
                        "platform": "linux",
                        "rid": "linux-x64",
                        "version": "local-hard-gate",
                        "channel": "local-hard-gate",
                        "ready_checkpoint": "pre_ui_event_loop",
                    },
                    "build": {
                        "output_base_root": str(output_base_root),
                        "publish_dir": str(publish_dir),
                        "dist_dir": str(dist_dir),
                        "binary_path": str(binary_path),
                        "binary_exists": linux_desktop_exit_gate_status == "passed",
                        "binary_sha256": hashlib.sha256(binary_path.read_bytes()).hexdigest(),
                        "binary_bytes": binary_path.stat().st_size,
                        "binary_executable": True,
                        "publish_exists": True,
                        "self_contained": True,
                        "single_file": True,
                        "primary_package_kind": "deb",
                        "fallback_package_kind": "archive",
                        "archive_path": str(archive_path),
                        "archive_exists": linux_desktop_exit_gate_status == "passed",
                        "archive_sha256": archive_digest,
                        "archive_bytes": archive_path.stat().st_size,
                        "installer_path": str(installer_path),
                        "installer_exists": linux_desktop_exit_gate_status == "passed",
                        "installer_sha256": installer_digest,
                        "installer_bytes": installer_path.stat().st_size,
                    },
                    "startup_smoke": {
                        "primary": {
                            "package_kind": "deb",
                            "artifact_path": str(installer_path),
                            "receipt_path": str(installer_receipt_path),
                            "status": linux_desktop_exit_gate_status,
                            "receipt": {"status": linux_desktop_exit_gate_status},
                        },
                        "fallback": {
                            "package_kind": "archive",
                            "artifact_path": str(archive_path),
                            "receipt_path": str(archive_receipt_path),
                            "status": linux_desktop_exit_gate_status,
                            "receipt": {"status": linux_desktop_exit_gate_status},
                        },
                    },
                    "unit_tests": {
                        "project_path": linux_desktop_exit_gate_test_project_path,
                        "framework": "net10.0",
                        "results_directory": str(test_results_dir),
                        "trx_path": str(test_results_dir / "desktop-runtime-tests.trx"),
                        "assembly_name": linux_desktop_exit_gate_test_assembly_name,
                        "status": "passed" if linux_desktop_exit_gate_status == "passed" else "failed",
                        "summary": {
                            "total": linux_desktop_exit_gate_test_total,
                            "passed": linux_gate_test_passed,
                            "failed": linux_desktop_exit_gate_test_failed,
                            "skipped": linux_desktop_exit_gate_test_skipped,
                        },
                    },
                    "source_snapshot": {
                        "mode": "filesystem_copy",
                        "repo_root": str(root),
                        "snapshot_root": str(snapshot_root),
                        "entry_count": worktree_entry_count,
                        "worktree_sha256": worktree_sha,
                        "finish_entry_count": worktree_entry_count,
                        "finish_worktree_sha256": worktree_sha,
                        "identity_stable": True,
                    },
                    "git": {
                        "repo_root": str(root),
                        "available": False,
                        "head": "",
                        "tracked_diff_sha256": "",
                        "tracked_diff_line_count": 0,
                        "start": {},
                        "finish": {},
                        "identity_stable": False,
                    },
                }
            ),
            encoding="utf-8",
        )
        if (root / ".git").exists():
            head = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            diff_sha, entry_count = _worktree_fingerprint(
                root,
                exclude_paths=(output_base_root, root / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"),
            )
            payload = json.loads((root / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json").read_text(encoding="utf-8"))
            payload["git"] = {
                "repo_root": str(root),
                "available": True,
                "head": head,
                "tracked_diff_sha256": diff_sha,
                "tracked_diff_line_count": entry_count,
                "start": {
                    "repo_root": str(root),
                    "available": True,
                    "head": head,
                    "tracked_diff_sha256": diff_sha,
                    "tracked_diff_line_count": entry_count,
                },
                "finish": {
                    "repo_root": str(root),
                    "available": True,
                    "head": head,
                    "tracked_diff_sha256": diff_sha,
                    "tracked_diff_line_count": entry_count,
                },
                "identity_stable": True,
            }
            (root / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json").write_text(
                json.dumps(payload),
                encoding="utf-8",
            )


def _write_flagship_product_readiness(
    root: Path,
    *,
    status: str = "pass",
    generated_at: str | None = None,
    ready_keys: tuple[str, ...] = (
        "desktop_client",
        "rules_engine_and_import",
        "hub_and_registry",
        "mobile_play_shell",
        "ui_kit_and_flagship_polish",
        "media_artifacts",
        "horizons_and_public_surface",
        "fleet_and_operator_loop",
    ),
    unresolved_parity_families: tuple[dict[str, object], ...] = (),
) -> None:
    now_text = generated_at or dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    coverage = {key: ("ready" if key in ready_keys else "missing") for key in (
        "desktop_client",
        "rules_engine_and_import",
        "hub_and_registry",
        "mobile_play_shell",
        "ui_kit_and_flagship_polish",
        "media_artifacts",
        "horizons_and_public_surface",
        "fleet_and_operator_loop",
    )}
    (root / "FLAGSHIP_PRODUCT_READINESS.generated.json").write_text(
        json.dumps(
            {
                "contract_name": "fleet.flagship_product_readiness",
                "generated_at": now_text,
                "status": status,
                "coverage": coverage,
                "parity_registry": {
                    "excluded_scope": ["plugin-framework"],
                    "unresolved_families": list(unresolved_parity_families),
                },
            }
        ),
        encoding="utf-8",
    )


def test_refresh_flagship_product_readiness_artifact_uses_workspace_sibling_generated_inputs(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Flagship work remains.\n", encoding="utf-8")
        (root / ".codex-design" / "product").mkdir(parents=True, exist_ok=True)
        (root / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml").write_text("product: chummer\n", encoding="utf-8")
        args = _args(root)
        calls: dict[str, str] = {}
        monkeypatch.setattr(module, "DEFAULT_WORKSPACE_ROOT", root)

        def fake_materialize_flagship_product_readiness(**kwargs):
            for key, value in kwargs.items():
                calls[key] = str(value)
            return {"status": "fail"}

        monkeypatch.setattr(module, "materialize_flagship_product_readiness", fake_materialize_flagship_product_readiness)

        payload = module._refresh_flagship_product_readiness_artifact(args)

        assert payload == {"status": "fail"}
        assert calls["out_path"] == str(root / "FLAGSHIP_PRODUCT_READINESS.generated.json")
        assert calls["journey_gates_path"] == str(root / "JOURNEY_GATES.generated.json")
        assert calls["acceptance_path"] == str(root / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml")
        assert calls["mirror_path"] == str(root / ".codex-design" / "product" / "FLAGSHIP_PRODUCT_READINESS.generated.json")
        assert calls["ui_windows_exit_gate_path"] == "/docker/chummercomplete/chummer6-ui/.codex-studio/published/UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
        assert calls["ui_workflow_parity_proof_path"] == "/docker/chummercomplete/chummer6-ui/.codex-studio/published/CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
        assert calls["ui_executable_exit_gate_path"] == "/docker/chummercomplete/chummer6-ui/.codex-studio/published/DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
        assert calls["ui_workflow_execution_gate_path"] == "/docker/chummercomplete/chummer6-ui/.codex-studio/published/DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
        assert calls["ui_visual_familiarity_exit_gate_path"] == "/docker/chummercomplete/chummer6-ui/.codex-studio/published/DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
        assert calls["ui_localization_release_gate_path"] == "/docker/chummercomplete/chummer6-ui/.codex-studio/published/UI_LOCALIZATION_RELEASE_GATE.generated.json"
        assert calls["sr4_workflow_parity_proof_path"] == "/docker/chummercomplete/chummer6-ui/.codex-studio/published/SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
        assert calls["sr6_workflow_parity_proof_path"] == "/docker/chummercomplete/chummer6-ui/.codex-studio/published/SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
        assert calls["sr4_sr6_frontier_receipt_path"] == "/docker/chummercomplete/chummer6-ui/.codex-studio/published/SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"


def test_derive_context_prefers_handoff_frontier_ids() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text(
            "W3 milestone `15` plus W4 milestones `18`, `19`, and `20` remain active.\n",
            encoding="utf-8",
        )
        args = _args(root)

        context = module.derive_context(args)

        assert [item.id for item in context["frontier"]] == [15, 18, 19]
        assert [item.id for item in context["open_milestones"]] == [6, 15, 18, 21, 19]
        assert "Frontier milestone ids to prioritize first: 15, 18, 19" in context["prompt"]
        assert str(root / "NEXT_SESSION_HANDOFF.md") in context["prompt"]


def test_parse_frontier_ids_from_handoff_prefers_explicit_frontier_line() -> None:
    module = _load_module()

    text = "\n".join(
        [
            "Status and metrics: 1, 2, 3.",
            "Current active frontier from design plus handoff: 1, 3, 4, 5, 2",
            "W3 milestone `15` plus W4 milestones `18`, `19`, and `20` remain active.",
        ]
    )

    assert module._parse_frontier_ids_from_handoff(text) == [1, 3, 4, 5, 2]


def test_parse_frontier_ids_from_handoff_prefers_latest_entry_at_top() -> None:
    module = _load_module()

    text = "\n".join(
        [
            "Frontier milestone ids to prioritize first: 1, 2, 4, 5, 3",
            "",
            "## 2026-04-02",
            "Frontier milestone ids to prioritize first: 1, 2, 3, 4, 6",
        ]
    )

    assert module._parse_frontier_ids_from_handoff(text) == [1, 2, 4, 5, 3]


def test_parse_frontier_ids_from_handoff_reads_multiline_frontier_block() -> None:
    module = _load_module()

    text = "\n".join(
        [
            "Current active frontier from design plus handoff:",
            "- 1 [W1] Gold install lane",
            "- 3 [W1] Packaged-binary desktop proof",
            "- 4 [W2] Campaign workspace v4",
            "- 5 [W2] GM operations lane",
            "- 2 [W1] Legacy-familiar flagship workbench",
            "",
            "Older note: Frontier milestone ids to prioritize first: 1, 2, 3, 4, 6",
        ]
    )

    assert module._parse_frontier_ids_from_handoff(text) == [1, 3, 4, 5, 2]


def test_parse_frontier_ids_from_handoff_ignores_non_frontier_number_noise() -> None:
    module = _load_module()

    text = "\n".join(
        [
            "Verification summary: 8 coverage keys are ready on 3 shards.",
            "No explicit frontier line is present in this note.",
        ]
    )

    assert module._parse_frontier_ids_from_handoff(text) == []


def test_derive_context_preserves_explicit_handoff_frontier_over_focus_profiles() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}, {"id": "W2"}],
                    "milestones": [
                        {
                            "id": 1,
                            "title": "Gold install lane",
                            "wave": "W1",
                            "status": "in_progress",
                            "owners": ["chummer6-ui", "fleet"],
                            "exit_criteria": ["Install lane works."],
                        },
                        {
                            "id": 2,
                            "title": "Legacy-familiar flagship workbench",
                            "wave": "W1",
                            "status": "in_progress",
                            "owners": ["chummer6-ui", "chummer6-core"],
                            "exit_criteria": ["Workbench posture is familiar."],
                        },
                        {
                            "id": 3,
                            "title": "Packaged-binary desktop proof",
                            "wave": "W1",
                            "status": "in_progress",
                            "owners": ["fleet", "chummer6-ui"],
                            "exit_criteria": ["Packaged proof exists."],
                        },
                        {
                            "id": 4,
                            "title": "Campaign workspace v4",
                            "wave": "W2",
                            "status": "in_progress",
                            "owners": ["chummer6-hub", "chummer6-core"],
                            "exit_criteria": ["Campaign lane is coherent."],
                        },
                        {
                            "id": 5,
                            "title": "GM operations lane",
                            "wave": "W2",
                            "status": "in_progress",
                            "owners": ["chummer6-hub", "chummer6-core"],
                            "exit_criteria": ["GM operations are first-class."],
                        },
                        {
                            "id": 6,
                            "title": "Offline and mobile continuity",
                            "wave": "W2",
                            "status": "in_progress",
                            "owners": ["chummer6-mobile", "chummer6-hub"],
                            "exit_criteria": ["Offline continuity works."],
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text(
            "Current active frontier from design plus handoff:\n"
            "- 1 [W1] Gold install lane\n"
            "- 2 [W1] Legacy-familiar flagship workbench\n"
            "- 4 [W2] Campaign workspace v4\n"
            "- 5 [W2] GM operations lane\n"
            "- 3 [W1] Packaged-binary desktop proof\n"
            "Frontier milestone ids to prioritize first: 1, 2, 4, 5, 3\n",
            encoding="utf-8",
        )
        args = _args(root)
        args.focus_profile = ["desktop_client"]

        context = module.derive_context(args)

        assert [item.id for item in context["frontier"]] == [1, 2, 4, 5, 3]


def test_derive_context_uses_multiline_handoff_frontier_without_priority_line() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}, {"id": "W2"}],
                    "milestones": [
                        {
                            "id": 1,
                            "title": "Gold install lane",
                            "wave": "W1",
                            "status": "in_progress",
                            "owners": ["chummer6-ui", "fleet"],
                            "exit_criteria": ["Install lane works."],
                        },
                        {
                            "id": 2,
                            "title": "Legacy-familiar flagship workbench",
                            "wave": "W1",
                            "status": "in_progress",
                            "owners": ["chummer6-ui", "chummer6-core"],
                            "exit_criteria": ["Workbench posture is familiar."],
                        },
                        {
                            "id": 3,
                            "title": "Packaged-binary desktop proof",
                            "wave": "W1",
                            "status": "in_progress",
                            "owners": ["fleet", "chummer6-ui"],
                            "exit_criteria": ["Packaged proof exists."],
                        },
                        {
                            "id": 4,
                            "title": "Campaign workspace v4",
                            "wave": "W2",
                            "status": "in_progress",
                            "owners": ["chummer6-hub", "chummer6-core"],
                            "exit_criteria": ["Campaign lane is coherent."],
                        },
                        {
                            "id": 5,
                            "title": "GM operations lane",
                            "wave": "W2",
                            "status": "in_progress",
                            "owners": ["chummer6-hub", "chummer6-core"],
                            "exit_criteria": ["GM operations are first-class."],
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text(
            "Current active frontier from design plus handoff:\n"
            "- 1 [W1] Gold install lane\n"
            "- 3 [W1] Packaged-binary desktop proof\n"
            "- 4 [W2] Campaign workspace v4\n"
            "- 5 [W2] GM operations lane\n"
            "- 2 [W1] Legacy-familiar flagship workbench\n",
            encoding="utf-8",
        )
        args = _args(root)
        args.focus_profile = ["desktop_client"]

        context = module.derive_context(args)

        assert [item.id for item in context["frontier"]] == [1, 3, 4, 5, 2]


def test_derive_context_can_focus_frontier_by_owner() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text(
            "W3 milestone `15` plus W4 milestones `18`, `19`, and `20` remain active.\n",
            encoding="utf-8",
        )
        args = _args(root)
        args.focus_owner = ["chummer6-ui"]

        context = module.derive_context(args)

        assert [item.id for item in context["frontier"]] == [15, 19]
        assert "Current steering focus:" in context["prompt"]
        assert "owner focus: chummer6-ui" in context["prompt"]


def test_derive_context_can_focus_frontier_by_desktop_profile() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text(
            "W3 milestone `15` plus W4 milestones `18`, `19`, and `20` remain active.\n",
            encoding="utf-8",
        )
        args = _args(root)
        args.focus_profile = ["desktop_client"]

        context = module.derive_context(args)

        assert [item.id for item in context["frontier"]] == [6, 21, 19]
        assert context["focus_profiles"] == ["desktop_client"]
        assert "profile focus: desktop_client" in context["prompt"]
        assert "owner focus: chummer6-ui, chummer6-core, chummer6-hub" in context["prompt"]
        assert "text focus: desktop, client, workbench" in context["prompt"]


def test_default_worker_command_adds_scope_roots_and_output_file() -> None:
    module = _load_module()
    workspace = Path("/docker/fleet")
    scope_roots = [workspace, Path("/docker/chummercomplete"), Path("/docker/EA")]
    run_dir = Path("/tmp/fleet-supervisor-run")

    command = module._default_worker_command(
        worker_bin="codex",
        worker_lane="",
        workspace_root=workspace,
        scope_roots=scope_roots,
        run_dir=run_dir,
        worker_model="gpt-5.4",
    )

    assert command[0:2] == ["codex", "exec"]
    assert "--add-dir" in command
    assert "/docker/chummercomplete" in command
    assert "/docker/EA" in command
    assert "-m" in command
    assert "gpt-5.4" in command
    assert str(run_dir / "last_message.txt") in command
    assert command[-1] == "-"


def test_default_worker_command_supports_lane_prefixed_worker_bin() -> None:
    module = _load_module()
    command = module._default_worker_command(
        worker_bin="codexea",
        worker_lane="core",
        workspace_root=Path("/docker/fleet"),
        scope_roots=[Path("/docker/fleet")],
        run_dir=Path("/tmp/fleet-supervisor-run"),
        worker_model="",
    )

    assert command[:3] == ["codexea", "core", "exec"]
    assert "-C" in command
    assert "-m" not in command


def test_parse_final_message_sections_reads_required_fields() -> None:
    module = _load_module()
    parsed = module._parse_final_message_sections(
        "What shipped: alpha\nWhat remains: beta\nExact blocker: none\n"
    )

    assert parsed["shipped"] == "alpha"
    assert parsed["remains"] == "beta"
    assert parsed["blocker"] == "none"


def test_parse_final_message_sections_reads_json_wrapped_closeout_text() -> None:
    module = _load_module()
    parsed = module._parse_final_message_sections(
        "\n".join(
            [
                "I am going to fix the blocker.",
                '{"questions":[{"header":"x"}]}',
                '{"decision":"final","text":"What shipped: alpha\\nWhat remains: beta\\nExact blocker: none"}',
            ]
        )
    )

    assert parsed["shipped"] == "alpha"
    assert parsed["remains"] == "beta"
    assert parsed["blocker"] == "none"


def test_assess_worker_result_rejects_timeout_text_even_with_zero_exit() -> None:
    module = _load_module()

    accepted, reason = module._assess_worker_result(0, "Error: upstream_timeout:300s\n")

    assert accepted is False
    assert "upstream_timeout:300s" in reason


def test_assess_worker_result_rejects_missing_structured_closeout() -> None:
    module = _load_module()

    accepted, reason = module._assess_worker_result(0, "What shipped: alpha\n")

    assert accepted is False
    assert "What remains" in reason
    assert "Exact blocker" in reason


def test_assess_worker_result_accepts_json_wrapped_structured_closeout() -> None:
    module = _load_module()

    accepted, reason = module._assess_worker_result(
        0,
        "\n".join(
            [
                "I am going to fix the blocker.",
                '{"decision":"final","text":"What shipped: alpha\\nWhat remains: beta\\nExact blocker: none"}',
            ]
        ),
    )

    assert accepted is True
    assert reason == ""


def test_assess_worker_result_rejects_unpublished_remote_work() -> None:
    module = _load_module()

    accepted, reason = module._assess_worker_result(
        0,
        "What shipped: `/docker/fleet/NEXT_SESSION_HANDOFF.md` refreshed locally with both slices "
        "(local Fleet commits `fbc5b1d`, `370495d`).\n\n"
        "What remains: Fleet handoff commits are not yet pushed to remote.\n\n"
        "Exact blocker: none\n",
    )

    assert accepted is False
    assert "not yet pushed to remote" in reason


def test_run_once_dry_run_persists_state_without_launching_worker() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text(
            "W4 milestones `18` and `19` remain active.\n",
            encoding="utf-8",
        )
        args = _args(root)
        args.dry_run = True

        exit_code = module.run_once(args)

        assert exit_code == 0
        state_payload = json.loads((root / "state" / "state.json").read_text(encoding="utf-8"))
        assert state_payload["mode"] == "once"
        assert state_payload["frontier_ids"] == [18, 19]
        assert state_payload["last_run"]["worker_exit_code"] == 0
        assert state_payload["last_run"]["worker_command"][0] == "codex"
        assert state_payload["last_run"]["attempted_models"] == ["gpt-5.4"]


def test_launch_worker_retries_retryable_model_failure_with_fallback(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text(
            "W4 milestones `18` and `19` remain active.\n",
            encoding="utf-8",
        )
        args = _args(root)
        args.worker_model = "gpt-5.3-codex-spark"
        args.fallback_worker_model = ["gpt-5.4"]
        context = module.derive_context(args)

        calls: list[list[str]] = []

        def fake_run(command, *, input, text, capture_output, cwd, check, env=None):
            calls.append(list(command))
            message_path = Path(command[command.index("-o") + 1])
            model = command[command.index("-m") + 1]
            if model == "gpt-5.3-codex-spark":
                return subprocess.CompletedProcess(
                    command,
                    1,
                    stdout="",
                    stderr="ERROR: You've hit your usage limit for GPT-5.3-Codex-Spark.",
                )
            message_path.write_text(
                "What shipped: fallback landed\nWhat remains: follow-through\nExact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        monkeypatch.setattr(module.subprocess, "run", fake_run)

        run = module.launch_worker(args, context, root / "state")

        assert run.worker_exit_code == 0
        assert run.accepted is True
        assert run.attempted_models == ["gpt-5.3-codex-spark", "gpt-5.4"]
        assert run.attempted_accounts == ["default", "default"]
        assert "gpt-5.4" in run.worker_command
        assert run.shipped == "fallback landed"
        assert len(calls) == 2


def test_launch_worker_rejects_zero_exit_timeout_receipt(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text(
            "W4 milestones `18` and `19` remain active.\n",
            encoding="utf-8",
        )
        args = _args(root)
        context = module.derive_context(args)

        def fake_run(command, *, input, text, capture_output, cwd, check, env=None):
            message_path = Path(command[command.index("-o") + 1])
            message_path.write_text("Error: upstream_timeout:300s\n", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        monkeypatch.setattr(module.subprocess, "run", fake_run)

        run = module.launch_worker(args, context, root / "state")

        assert run.worker_exit_code == 0
        assert run.accepted is False
        assert "upstream_timeout:300s" in run.acceptance_reason


def test_launch_worker_rotates_across_configured_owner_accounts(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text(
            "W4 milestones `18` and `19` remain active.\n",
            encoding="utf-8",
        )
        auth_a = root / "acct-a.auth.json"
        auth_b = root / "acct-b.auth.json"
        auth_a.write_text('{"access_token":"a"}\n', encoding="utf-8")
        auth_b.write_text('{"access_token":"b"}\n', encoding="utf-8")
        (root / "accounts.yaml").write_text(
            yaml.safe_dump(
                {
                    "account_policy": {
                        "protected_owner_ids": ["tibor.girschele", "archon.megalon"],
                    },
                    "accounts": {
                        "acct-tibor-a": {
                            "auth_kind": "chatgpt_auth_json",
                            "auth_json_file": str(auth_a),
                            "owner_id": "tibor.girschele",
                            "health_state": "ready",
                            "spark_enabled": True,
                        },
                        "acct-archon-a": {
                            "auth_kind": "chatgpt_auth_json",
                            "auth_json_file": str(auth_b),
                            "owner_id": "archon.megalon",
                            "health_state": "ready",
                            "spark_enabled": True,
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        args = _args(root)
        args.worker_model = "gpt-5.3-codex-spark"
        args.account_owner_id = ["tibor.girschele", "archon.megalon"]
        context = module.derive_context(args)

        calls: list[tuple[list[str], str]] = []

        def fake_run(command, *, input, text, capture_output, cwd, check, env=None):
            assert env is not None
            calls.append((list(command), str(env.get("CODEX_HOME") or "")))
            message_path = Path(command[command.index("-o") + 1])
            home = Path(str(env["CODEX_HOME"]))
            auth_contents = (home / "auth.json").read_text(encoding="utf-8")
            if '"access_token":"a"' in auth_contents:
                return subprocess.CompletedProcess(
                    command,
                    1,
                    stdout="",
                    stderr="ERROR: You've hit your usage limit for GPT-5.3-Codex-Spark.",
                )
            message_path.write_text(
                "What shipped: archon lane picked up the loop\nWhat remains: follow-through\nExact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        monkeypatch.setattr(module.subprocess, "run", fake_run)

        run = module.launch_worker(args, context, root / "state")

        assert run.worker_exit_code == 0
        assert run.accepted is True
        assert run.selected_account_alias == "acct-archon-a"
        assert run.attempted_accounts == ["acct-tibor-a", "acct-archon-a"]
        assert run.attempted_models == ["gpt-5.3-codex-spark", "gpt-5.3-codex-spark"]
        account_runtime = json.loads((root / "state" / "account_runtime.json").read_text(encoding="utf-8"))
        assert len(account_runtime["sources"]) == 2
        assert len(calls) == 2


def test_launch_worker_can_use_direct_worker_lane_without_account_rotation(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("W2 milestone `21` remains active.\n", encoding="utf-8")
        (root / "runtime.env").write_text(
            "\n".join(
                [
                    "CHUMMER_DESIGN_SUPERVISOR_STREAM_IDLE_TIMEOUT_MS=900000",
                    "CHUMMER_DESIGN_SUPERVISOR_STREAM_MAX_RETRIES=8",
                    "CHUMMER_DESIGN_SUPERVISOR_CORE_RESPONSES_PROFILE=core_batch",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        args = _args(root)
        args.worker_bin = "codexea"
        args.worker_lane = "core"
        args.worker_model = ""
        context = module.derive_context(args)

        calls: list[list[str]] = []

        def fake_run(command, *, input, text, capture_output, cwd, check, env=None):
            calls.append(list(command))
            assert env is not None
            assert str(env.get("CODEX_HOME") or "").endswith("/direct-core")
            assert env.get("HOME") == env.get("CODEX_HOME")
            assert env.get("CODEXEA_STREAM_IDLE_TIMEOUT_MS") == "900000"
            assert env.get("CODEXEA_STREAM_MAX_RETRIES") == "8"
            assert env.get("CODEXEA_CORE_RESPONSES_PROFILE") == "core_batch"
            message_path = Path(command[command.index("-o") + 1])
            message_path.write_text(
                "What shipped: core lane worked\nWhat remains: follow-through\nExact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        monkeypatch.setattr(module.subprocess, "run", fake_run)

        run = module.launch_worker(args, context, root / "state")

        assert run.worker_exit_code == 0
        assert run.accepted is True
        assert run.selected_account_alias == "lane:core"
        assert run.attempted_accounts == ["lane:core"]
        assert calls[0][:3] == ["codexea", "core", "exec"]


def test_prepare_direct_worker_environment_preserves_host_git_and_gh_auth(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        host_home = root / "host-home"
        gh_dir = host_home / ".config" / "gh"
        gh_dir.mkdir(parents=True, exist_ok=True)
        (host_home / ".gitconfig").write_text("[user]\n\tname = Test\n", encoding="utf-8")
        (gh_dir / "hosts.yml").write_text("github.com:\n  user: test\n", encoding="utf-8")
        monkeypatch.setenv("HOME", str(host_home))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        env = module._prepare_direct_worker_environment(
            root / "state",
            "core",
            workspace_root=root,
            worker_bin="codex",
        )

        assert str(env.get("CODEX_HOME") or "").endswith("/direct-core")
        assert env.get("HOME") == env.get("CODEX_HOME")
        worker_home = Path(str(env["HOME"]))
        assert env.get("GIT_CONFIG_GLOBAL") == str(worker_home / ".gitconfig")
        assert env.get("XDG_CONFIG_HOME") == str(worker_home / ".config")
        assert env.get("GH_CONFIG_DIR") == str(worker_home / ".config" / "gh")
        assert (worker_home / ".gitconfig").read_text(encoding="utf-8") == (host_home / ".gitconfig").read_text(encoding="utf-8")
        assert (worker_home / ".config" / "gh" / "hosts.yml").read_text(encoding="utf-8") == (
            gh_dir / "hosts.yml"
        ).read_text(encoding="utf-8")


def test_prepare_account_environment_preserves_host_git_and_gh_auth(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        host_home = root / "host-home"
        gh_dir = host_home / ".config" / "gh"
        gh_dir.mkdir(parents=True, exist_ok=True)
        (host_home / ".gitconfig").write_text(
            "[credential \"https://github.com\"]\n\thelper = !/usr/bin/gh auth git-credential\n",
            encoding="utf-8",
        )
        (gh_dir / "hosts.yml").write_text("github.com:\n  user: test\n", encoding="utf-8")
        monkeypatch.setenv("HOME", str(host_home))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.setenv("TEST_API_KEY", "secret")

        account = module.WorkerAccount(
            alias="acct-test",
            owner_id="owner",
            auth_kind="api_key",
            auth_json_file="",
            api_key_env="TEST_API_KEY",
            api_key_file="",
            allowed_models=[],
            health_state="ready",
            spark_enabled=True,
            bridge_priority=0,
            forced_login_method="",
            forced_chatgpt_workspace_id="",
            openai_base_url="",
            home_dir="",
            max_parallel_runs=1,
        )

        env = module._prepare_account_environment(root / "state", root, account)

        assert str(env.get("CODEX_HOME") or "").endswith("/acct-test")
        assert env.get("HOME") == env.get("CODEX_HOME")
        worker_home = Path(str(env["HOME"]))
        assert env.get("GIT_CONFIG_GLOBAL") == str(worker_home / ".gitconfig")
        assert env.get("XDG_CONFIG_HOME") == str(worker_home / ".config")
        assert env.get("GH_CONFIG_DIR") == str(worker_home / ".config" / "gh")
        assert (worker_home / ".gitconfig").read_text(encoding="utf-8") == (
            host_home / ".gitconfig"
        ).read_text(encoding="utf-8")
        assert (worker_home / ".config" / "gh" / "hosts.yml").read_text(encoding="utf-8") == (
            gh_dir / "hosts.yml"
        ).read_text(encoding="utf-8")
        assert env.get("CODEX_API_KEY") == "secret"


def test_prepare_direct_worker_environment_falls_back_to_passwd_home_for_git_auth(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        host_home = root / "passwd-home"
        gh_dir = host_home / ".config" / "gh"
        gh_dir.mkdir(parents=True, exist_ok=True)
        (host_home / ".gitconfig").write_text("[user]\n\tname = Test\n", encoding="utf-8")
        (gh_dir / "hosts.yml").write_text("github.com:\n  user: test\n", encoding="utf-8")
        monkeypatch.setenv("HOME", "/")
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        class _PwdEntry:
            pw_dir = str(host_home)

        monkeypatch.setattr(module.pwd, "getpwuid", lambda _uid: _PwdEntry())

        env = module._prepare_direct_worker_environment(
            root / "state",
            "core",
            workspace_root=root,
            worker_bin="codex",
        )

        assert env.get("HOME") == env.get("CODEX_HOME")
        worker_home = Path(str(env["HOME"]))
        assert env.get("GIT_CONFIG_GLOBAL") == str(worker_home / ".gitconfig")
        assert env.get("XDG_CONFIG_HOME") == str(worker_home / ".config")
        assert env.get("GH_CONFIG_DIR") == str(worker_home / ".config" / "gh")
        assert (worker_home / ".gitconfig").read_text(encoding="utf-8") == (host_home / ".gitconfig").read_text(encoding="utf-8")
        assert (worker_home / ".config" / "gh" / "hosts.yml").read_text(encoding="utf-8") == (
            gh_dir / "hosts.yml"
        ).read_text(encoding="utf-8")


def test_prepare_account_environment_falls_back_to_workspace_secret_mirror_for_auth_json(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        host_home = root / "host-home"
        gh_dir = host_home / ".config" / "gh"
        gh_dir.mkdir(parents=True, exist_ok=True)
        (host_home / ".gitconfig").write_text(
            "[credential \"https://github.com\"]\n\thelper = !/usr/bin/gh auth git-credential\n",
            encoding="utf-8",
        )
        (gh_dir / "hosts.yml").write_text("github.com:\n  user: test\n", encoding="utf-8")
        monkeypatch.setenv("HOME", str(host_home))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        secrets_dir = root / "secrets"
        secrets_dir.mkdir(parents=True, exist_ok=True)
        mirrored_auth = secrets_dir / "acct-chatgpt-b.auth.json"
        mirrored_auth.write_text('{"access_token":"token"}\n', encoding="utf-8")

        account = module.WorkerAccount(
            alias="acct-chatgpt-b",
            owner_id="owner",
            auth_kind="chatgpt_auth_json",
            auth_json_file="/run/secrets/acct-chatgpt-b.auth.json",
            api_key_env="",
            api_key_file="",
            allowed_models=[],
            health_state="ready",
            spark_enabled=False,
            bridge_priority=0,
            forced_login_method="",
            forced_chatgpt_workspace_id="",
            openai_base_url="",
            home_dir="",
            max_parallel_runs=1,
        )

        env = module._prepare_account_environment(root / "state", root, account)

        worker_home = Path(str(env["HOME"]))
        assert (worker_home / "auth.json").read_text(encoding="utf-8") == mirrored_auth.read_text(encoding="utf-8")


def test_worker_reported_git_push_repos_parses_unique_repos() -> None:
    module = _load_module()
    stderr_text = """
exec
/usr/bin/bash -lc 'cd /docker/chummercomplete/chummer.run-services && git push' in /docker/fleet exited 128 in 11ms:
fatal: could not read Username for 'https://github.com': No such device or address
exec
/usr/bin/bash -lc 'cd /docker/fleet && git push' in /docker/fleet exited 128 in 14ms:
fatal: could not read Username for 'https://github.com': No such device or address
exec
/usr/bin/bash -lc 'cd /docker/fleet && git push' in /docker/fleet exited 128 in 14ms:
fatal: could not read Username for 'https://github.com': No such device or address
exec
/usr/bin/bash -lc 'cd /docker/chummercomplete/chummer6-core && git add Chummer.Application/Workspaces/HeroLabShadowrunImporter.cs Chummer.CoreEngine.Tests/HeroLabRulesParityAudit.cs && git commit -m "test(w17): lock Hero Lab online metadata-shape ruleset detection" && git push' in /docker/fleet exited 128 in 67ms:
fatal: could not read Username for 'https://github.com': No such device or address
"""
    repos = module._worker_reported_git_push_repos(stderr_text)
    assert repos == [
        Path("/docker/chummercomplete/chummer.run-services"),
        Path("/docker/fleet"),
        Path("/docker/chummercomplete/chummer6-core"),
    ]


def test_retry_worker_reported_git_pushes_uses_host_git_auth(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        host_home = root / "host-home"
        gh_dir = host_home / ".config" / "gh"
        gh_dir.mkdir(parents=True, exist_ok=True)
        (host_home / ".gitconfig").write_text(
            "[credential \"https://github.com\"]\n\thelper = !/usr/bin/gh auth git-credential\n",
            encoding="utf-8",
        )
        (gh_dir / "hosts.yml").write_text("github.com:\n  user: test\n", encoding="utf-8")
        monkeypatch.setenv("HOME", "/")

        class _PwdEntry:
            pw_dir = str(host_home)

        monkeypatch.setattr(module.pwd, "getpwuid", lambda _uid: _PwdEntry())

        calls: list[tuple[list[str], dict[str, str]]] = []

        def fake_run(command, *, text, capture_output, check, env=None):
            assert env is not None
            calls.append((list(command), dict(env)))
            if command[:5] == ["git", "-C", "/docker/fleet", "remote", "get-url"]:
                return subprocess.CompletedProcess(command, 0, stdout="https://github.com/ArchonMegalon/fleet.git\n", stderr="")
            if command[:3] == ["gh", "auth", "token"]:
                return subprocess.CompletedProcess(command, 0, stdout="gho_test_token\n", stderr="")
            return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

        monkeypatch.setattr(module.subprocess, "run", fake_run)

        result = module._retry_worker_reported_git_pushes(
            "exec\n/usr/bin/bash -lc 'cd /docker/fleet && git push' in /docker/fleet exited 128 in 14ms:\n"
        )

        assert result["attempted"] == ["/docker/fleet"]
        assert result["succeeded"] == ["/docker/fleet"]
        assert result["failed"] == {}
        assert calls[0][0] == ["git", "-C", "/docker/fleet", "remote", "get-url", "origin"]
        assert calls[1][0] == ["gh", "auth", "token"]
        assert calls[2][0][:3] == ["git", "-C", "/docker/fleet"]
        assert any(part.startswith("http.https://github.com/.extraheader=AUTHORIZATION: basic ") for part in calls[2][0])
        assert calls[2][1]["HOME"] == str(host_home)
        assert calls[2][1]["GIT_CONFIG_GLOBAL"] == str(host_home / ".gitconfig")
        assert calls[2][1]["XDG_CONFIG_HOME"] == str(host_home / ".config")
        assert calls[2][1]["GH_CONFIG_DIR"] == str(gh_dir)


def test_github_https_auth_extraheader_returns_empty_when_gh_missing(monkeypatch) -> None:
    module = _load_module()

    def fake_run(command, *, text, capture_output, check, env=None):
        if command[:5] == ["git", "-C", "/docker/fleet", "remote", "get-url"]:
            return subprocess.CompletedProcess(command, 0, stdout="https://github.com/ArchonMegalon/fleet.git\n", stderr="")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(module, "_github_auth_token", lambda _env: "")

    assert module._github_https_auth_extraheader({}, Path("/docker/fleet")) == ""


def test_github_auth_token_reads_hosts_yml_without_gh(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        gh_dir = Path(tmp) / "gh"
        gh_dir.mkdir(parents=True, exist_ok=True)
        (gh_dir / "hosts.yml").write_text(
            "github.com:\n"
            "  users:\n"
            "    ArchonMegalon:\n"
            "      oauth_token: gho_hosts_token\n"
            "  git_protocol: https\n",
            encoding="utf-8",
        )

        def fake_run(command, *, text, capture_output, check, env=None):
            if command[:3] == ["gh", "auth", "token"]:
                raise FileNotFoundError("gh")
            raise AssertionError(f"unexpected command: {command}")

        monkeypatch.setattr(module.subprocess, "run", fake_run)

        assert module._github_auth_token({"GH_CONFIG_DIR": str(gh_dir)}) == "gho_hosts_token"


def test_is_missing_github_push_blocker_accepts_remote_push_wording() -> None:
    module = _load_module()

    assert (
        module._is_missing_github_push_blocker(
            "`fleet` remote push is still blocked by missing GitHub HTTPS credentials: "
            "`fatal: could not read Username for 'https://github.com': No such device or address`."
        )
        is True
    )
    assert (
        module._is_missing_github_push_blocker(
            "host-side git push recovery failed after worker credential error: "
            "/docker/fleet: fatal: could not read Username for 'https://github.com': No such device or address"
        )
        is True
    )


def test_launch_worker_can_escape_retryable_direct_lane_failure_to_openai_account(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("W2 milestone `21` remains active.\n", encoding="utf-8")
        auth_path = root / "acct-chatgpt-core.auth.json"
        auth_path.write_text('{"access_token":"token"}\n', encoding="utf-8")
        (root / "accounts.yaml").write_text(
            yaml.safe_dump(
                {
                    "account_policy": {"protected_owner_ids": ["tibor.girschele"]},
                    "accounts": {
                        "acct-chatgpt-core": {
                            "auth_kind": "chatgpt_auth_json",
                            "auth_json_file": str(auth_path),
                            "allowed_models": ["gpt-5.3-codex"],
                            "spark_enabled": False,
                            "health_state": "ready",
                            "owner_id": "tibor.girschele",
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        args = _args(root)
        args.worker_bin = "codexea"
        args.worker_lane = "core"
        args.worker_model = ""
        context = module.derive_context(args)
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_FALLBACK_LANES", "")
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_OPENAI_ESCAPE_ACCOUNT_ALIASES", "acct-chatgpt-core")
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_OPENAI_ESCAPE_MODELS", "gpt-5.3-codex")

        calls: list[list[str]] = []

        def fake_run(command, *, input, text, capture_output, cwd, check, env=None):
            calls.append(list(command))
            message_path = Path(command[command.index("-o") + 1])
            if command[0] == "codexea":
                message_path.write_text("Error: upstream_timeout:300s\n", encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
            assert env is not None
            assert env.get("CODEX_HOME")
            message_path.write_text(
                "What shipped: openai escape hatch landed the slice\nWhat remains: none\nExact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        monkeypatch.setattr(module.subprocess, "run", fake_run)

        run = module.launch_worker(args, context, root / "state")

        assert run.worker_exit_code == 0
        assert run.accepted is True
        assert run.selected_account_alias == "acct-chatgpt-core"
        assert run.attempted_accounts == ["lane:core", "acct-chatgpt-core"]
        assert run.attempted_models == ["default", "gpt-5.3-codex"]
        assert calls[0][:3] == ["codexea", "core", "exec"]
        assert calls[1][0] == "codex"


def test_launch_worker_falls_back_from_account_primary_to_direct_ea_lane_on_usage_limit(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("W2 milestone `21` remains active.\n", encoding="utf-8")
        auth_path = root / "acct-chatgpt-b.auth.json"
        auth_path.write_text('{"access_token":"token"}\n', encoding="utf-8")
        (root / "accounts.yaml").write_text(
            yaml.safe_dump(
                {
                    "account_policy": {"protected_owner_ids": ["the.girscheles", "archon.megalon"]},
                    "accounts": {
                        "acct-chatgpt-b": {
                            "auth_kind": "chatgpt_auth_json",
                            "auth_json_file": str(auth_path),
                            "allowed_models": ["gpt-5.3-codex"],
                            "spark_enabled": False,
                            "health_state": "ready",
                            "owner_id": "the.girscheles",
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        args = _args(root)
        args.worker_bin = "codex"
        args.worker_lane = ""
        args.worker_model = "gpt-5.3-codex"
        args.account_alias = ["acct-chatgpt-b"]
        context = module.derive_context(args)
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_FALLBACK_WORKER_BIN", "codexea")
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_FALLBACK_WORKER_LANE", "core")
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_FALLBACK_MODELS", "ea-coder-hard-batch")
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_FALLBACK_LANES", "core_rescue,survival,repair")
        monkeypatch.setattr(
            module,
            "_direct_worker_lane_health_snapshot",
            lambda _args, _lanes: {
                "status": "pass",
                "reason": "all checked direct lanes are currently routable",
                "routable_lanes": ["core", "core_rescue", "survival", "repair"],
                "unroutable_lanes": [],
                "lanes": {
                    "core": {"worker_lane": "core", "profile": "core_batch", "state": "ready", "routable": True, "reason": ""},
                    "core_rescue": {"worker_lane": "core_rescue", "profile": "core_rescue", "state": "ready", "routable": True, "reason": ""},
                    "survival": {"worker_lane": "survival", "profile": "survival", "state": "ready", "routable": True, "reason": ""},
                    "repair": {"worker_lane": "repair", "profile": "repair", "state": "ready", "routable": True, "reason": ""},
                },
            },
        )

        calls: list[list[str]] = []

        def fake_run(command, *, input, text, capture_output, cwd, check, env=None, timeout=None):
            calls.append(list(command))
            message_path = Path(command[command.index("-o") + 1])
            if command[0] == "codex":
                return subprocess.CompletedProcess(
                    command,
                    1,
                    stdout="",
                    stderr="Error: usage limit reached. Send a request to your admin.\n",
                )
            message_path.write_text(
                "What shipped: direct ea fallback kept the shard moving\n"
                "What remains: follow-through\n"
                "Exact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        monkeypatch.setattr(module.subprocess, "run", fake_run)

        run = module.launch_worker(args, context, root / "state")

        assert run.worker_exit_code == 0
        assert run.accepted is True
        assert run.selected_account_alias == "lane:core"
        assert run.attempted_accounts == ["acct-chatgpt-b", "lane:core"]
        assert run.attempted_models == ["gpt-5.3-codex", "ea-coder-hard-batch"]
        assert calls[0][0] == "codex"
        assert calls[1][:3] == ["codexea", "core", "exec"]
        stderr_text = (root / "state" / "runs" / run.run_id / "worker.stderr.log").read_text(encoding="utf-8")
        assert "escalating account-lane failure to direct fallback" in stderr_text


def test_launch_worker_reads_account_direct_fallback_from_runtime_env(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("W2 milestone `21` remains active.\n", encoding="utf-8")
        auth_path = root / "acct-chatgpt-b.auth.json"
        auth_path.write_text('{"access_token":"token"}\n', encoding="utf-8")
        (root / "accounts.yaml").write_text(
            yaml.safe_dump(
                {
                    "account_policy": {"protected_owner_ids": ["the.girscheles", "archon.megalon"]},
                    "accounts": {
                        "acct-chatgpt-b": {
                            "auth_kind": "chatgpt_auth_json",
                            "auth_json_file": str(auth_path),
                            "allowed_models": ["gpt-5.3-codex"],
                            "spark_enabled": False,
                            "health_state": "ready",
                            "owner_id": "the.girscheles",
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        (root / "runtime.env").write_text(
            "\n".join(
                [
                    "CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_FALLBACK_WORKER_BIN=codexea",
                    "CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_FALLBACK_WORKER_LANE=easy",
                    "CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_FALLBACK_MODELS=ea-gemini-flash",
                    "CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_FALLBACK_LANES=groundwork,repair",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        args = _args(root)
        args.worker_bin = "codex"
        args.worker_lane = ""
        args.worker_model = "gpt-5.3-codex"
        args.account_alias = ["acct-chatgpt-b"]
        context = module.derive_context(args)
        monkeypatch.setattr(module, "_RUNTIME_ENV_CANDIDATES", (root / "runtime.env",))
        monkeypatch.setattr(
            module,
            "_direct_worker_lane_health_snapshot",
            lambda _args, _lanes: {
                "status": "pass",
                "reason": "all checked direct lanes are currently routable",
                "routable_lanes": ["easy", "groundwork", "repair"],
                "unroutable_lanes": [],
                "lanes": {
                    "easy": {"worker_lane": "easy", "profile": "easy", "state": "ready", "routable": True, "reason": ""},
                    "groundwork": {
                        "worker_lane": "groundwork",
                        "profile": "groundwork",
                        "state": "ready",
                        "routable": True,
                        "reason": "",
                    },
                    "repair": {"worker_lane": "repair", "profile": "repair", "state": "ready", "routable": True, "reason": ""},
                },
            },
        )

        calls: list[list[str]] = []

        def fake_run(command, *, input, text, capture_output, cwd, check, env=None, timeout=None):
            calls.append(list(command))
            message_path = Path(command[command.index("-o") + 1])
            if command[0] == "codex":
                return subprocess.CompletedProcess(
                    command,
                    1,
                    stdout="",
                    stderr="ERROR: unexpected status 401 Unauthorized: Incorrect API key provided\n",
                )
            message_path.write_text(
                "What shipped: runtime env fallback kept the shard moving\n"
                "What remains: follow-through\n"
                "Exact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        monkeypatch.setattr(module.subprocess, "run", fake_run)

        run = module.launch_worker(args, context, root / "state")

        assert run.worker_exit_code == 0
        assert run.accepted is True
        assert run.selected_account_alias == "lane:easy"
        assert run.attempted_accounts == ["acct-chatgpt-b", "lane:easy"]
        assert run.attempted_models == ["gpt-5.3-codex", "ea-gemini-flash"]
        assert calls[0][0] == "codex"
        assert calls[1][:3] == ["codexea", "easy", "exec"]


def test_account_restore_probe_due_respects_configured_interval(monkeypatch) -> None:
    module = _load_module()
    now = dt.datetime(2026, 4, 2, 12, 0, tzinfo=dt.timezone.utc)

    monkeypatch.setattr(module, "_RUNTIME_ENV_CANDIDATES", ())
    monkeypatch.delenv("CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_RESTORE_PROBE_SECONDS", raising=False)
    assert module._account_restore_probe_due(None, now=now) is False

    monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_RESTORE_PROBE_SECONDS", "300")
    assert module._account_restore_probe_due(None, now=now) is True
    assert module._account_restore_probe_due(now, now=now + dt.timedelta(seconds=299)) is False
    assert module._account_restore_probe_due(now, now=now + dt.timedelta(seconds=300)) is True


def test_launch_worker_skips_saturated_account_when_sibling_shards_already_claim_it(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("W2 milestone `21` remains active.\n", encoding="utf-8")
        auth_b = root / "acct-chatgpt-b.auth.json"
        auth_archon = root / "acct-chatgpt-archon.auth.json"
        auth_b.write_text('{"access_token":"token-b"}\n', encoding="utf-8")
        auth_archon.write_text('{"access_token":"token-archon"}\n', encoding="utf-8")
        (root / "accounts.yaml").write_text(
            yaml.safe_dump(
                {
                    "account_policy": {"protected_owner_ids": ["the.girscheles", "archon.megalon"]},
                    "accounts": {
                        "acct-chatgpt-b": {
                            "auth_kind": "chatgpt_auth_json",
                            "auth_json_file": str(auth_b),
                            "allowed_models": ["gpt-5.3-codex"],
                            "spark_enabled": False,
                            "health_state": "ready",
                            "owner_id": "the.girscheles",
                            "max_parallel_runs": 2,
                            "bridge_priority": 0,
                        },
                        "acct-chatgpt-archon": {
                            "auth_kind": "chatgpt_auth_json",
                            "auth_json_file": str(auth_archon),
                            "allowed_models": ["gpt-5.3-codex"],
                            "spark_enabled": False,
                            "health_state": "ready",
                            "owner_id": "archon.megalon",
                            "max_parallel_runs": 8,
                            "bridge_priority": 2,
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        aggregate_root = root / "state"
        for index in (1, 2):
            shard_root = aggregate_root / f"shard-{index}"
            shard_root.mkdir(parents=True, exist_ok=True)
            module._write_json(
                shard_root / "state.json",
                {
                    "updated_at": "2026-04-02T12:00:00Z",
                    "active_run": {
                        "run_id": f"run-{index}",
                        "selected_account_alias": "acct-chatgpt-b",
                        "frontier_ids": [index],
                        "open_milestone_ids": [],
                    },
                },
            )
        shard_three_root = aggregate_root / "shard-3"
        shard_three_root.mkdir(parents=True, exist_ok=True)

        args = _args(root)
        args.worker_bin = "codex"
        args.worker_lane = ""
        args.worker_model = "gpt-5.3-codex"
        args.account_alias = ["acct-chatgpt-b", "acct-chatgpt-archon"]
        context = module.derive_context(args)

        calls: list[list[str]] = []

        def fake_run(command, *, input, text, capture_output, cwd, check, env=None, timeout=None):
            calls.append(list(command))
            message_path = Path(command[command.index("-o") + 1])
            message_path.write_text(
                "What shipped: sibling shard saturation respected account concurrency\n"
                "What remains: follow-through\n"
                "Exact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        monkeypatch.setattr(module.subprocess, "run", fake_run)

        run = module.launch_worker(args, context, shard_three_root)

        assert run.worker_exit_code == 0
        assert run.accepted is True
        assert run.selected_account_alias == "acct-chatgpt-archon"
        assert run.attempted_accounts == ["acct-chatgpt-archon"]
        stderr_text = (shard_three_root / "runs" / run.run_id / "worker.stderr.log").read_text(encoding="utf-8")
        assert "skip account=acct-chatgpt-b owner=the.girscheles reason=max_parallel_runs 2/2" in stderr_text
        assert calls[0][0] == "codex"


def test_launch_worker_retries_retryable_timeout_on_fallback_direct_lane(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("W2 milestone `21` remains active.\n", encoding="utf-8")
        args = _args(root)
        args.worker_bin = "codexea"
        args.worker_lane = "core"
        args.worker_model = ""
        context = module.derive_context(args)

        calls: list[list[str]] = []

        def fake_run(command, *, input, text, capture_output, cwd, check, env=None):
            calls.append(list(command))
            message_path = Path(command[command.index("-o") + 1])
            lane = command[1]
            if lane == "core":
                message_path.write_text("Error: upstream_timeout:300s\n", encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
            message_path.write_text(
                "What shipped: rescue lane recovered the slice\n"
                "What remains: follow-through\n"
                "Exact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        monkeypatch.setattr(module.subprocess, "run", fake_run)

        run = module.launch_worker(args, context, root / "state")

        assert run.worker_exit_code == 0
        assert run.accepted is True
        assert run.selected_account_alias == "lane:core_rescue"
        assert run.attempted_accounts == ["lane:core", "lane:core_rescue"]
        assert run.attempted_models == ["default", "default"]
        assert calls[0][:3] == ["codexea", "core", "exec"]
        assert calls[1][:3] == ["codexea", "core_rescue", "exec"]
        assert run.shipped == "rescue lane recovered the slice"


def test_launch_worker_retries_supervisor_watchdog_timeout_on_fallback_direct_lane(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("W2 milestone `21` remains active.\n", encoding="utf-8")
        args = _args(root)
        args.worker_bin = "codexea"
        args.worker_lane = "core"
        args.worker_model = ""
        args.fallback_worker_lane = ["repair"]
        args.worker_timeout_seconds = 5.0
        context = module.derive_context(args)
        monkeypatch.setattr(
            module,
            "_direct_worker_lane_health_snapshot",
            lambda _args, _lanes: {
                "status": "pass",
                "reason": "all checked direct lanes are currently routable",
                "routable_lanes": ["core", "repair"],
                "unroutable_lanes": [],
                "lanes": {
                    "core": {"worker_lane": "core", "profile": "core_batch", "state": "ready", "routable": True, "reason": ""},
                    "repair": {"worker_lane": "repair", "profile": "repair", "state": "ready", "routable": True, "reason": ""},
                },
            },
        )

        calls: list[tuple[list[str], float | None]] = []

        def fake_run(command, *, input, text, capture_output, cwd, check, env=None, timeout=None):
            calls.append((list(command), timeout))
            message_path = Path(command[command.index("-o") + 1])
            lane = command[1]
            if lane == "core":
                raise subprocess.TimeoutExpired(command, timeout=timeout or 5.0, output="", stderr="")
            message_path.write_text(
                "What shipped: watchdog timeout retried on repair\n"
                "What remains: follow-through\n"
                "Exact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        monkeypatch.setattr(module.subprocess, "run", fake_run)

        run = module.launch_worker(args, context, root / "state")

        assert run.worker_exit_code == 0
        assert run.accepted is True
        assert run.selected_account_alias == "lane:repair"
        assert run.attempted_accounts == ["lane:core", "lane:repair"]
        assert calls[0][1] == 5.0
        stderr_text = (root / "state" / "runs" / run.run_id / "worker.stderr.log").read_text(encoding="utf-8")
        assert "worker_timeout:5s" in stderr_text
        assert run.shipped == "watchdog timeout retried on repair"


def test_launch_worker_raises_direct_codexea_watchdog_to_workspace_stream_budget(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("W2 milestone `21` remains active.\n", encoding="utf-8")
        (root / "runtime.env").write_text(
            "\n".join(
                [
                    "CHUMMER_DESIGN_SUPERVISOR_STREAM_IDLE_TIMEOUT_MS=900000",
                    "CHUMMER_DESIGN_SUPERVISOR_STREAM_MAX_RETRIES=8",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        args = _args(root)
        args.worker_bin = "codexea"
        args.worker_lane = "core"
        args.worker_model = ""
        args.worker_timeout_seconds = 1200.0
        context = module.derive_context(args)
        monkeypatch.setattr(
            module,
            "_direct_worker_lane_health_snapshot",
            lambda _args, _lanes: {
                "status": "pass",
                "reason": "all checked direct lanes are currently routable",
                "routable_lanes": ["core"],
                "unroutable_lanes": [],
                "lanes": {
                    "core": {"worker_lane": "core", "profile": "core_batch", "state": "ready", "routable": True, "reason": ""},
                },
            },
        )

        calls: list[tuple[list[str], float | None]] = []

        def fake_run(command, *, input, text, capture_output, cwd, check, env=None, timeout=None):
            calls.append((list(command), timeout))
            message_path = Path(command[command.index("-o") + 1])
            message_path.write_text(
                "What shipped: core lane stayed on the long watchdog\nWhat remains: follow-through\nExact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        monkeypatch.setattr(module.subprocess, "run", fake_run)

        run = module.launch_worker(args, context, root / "state")

        assert run.worker_exit_code == 0
        assert run.accepted is True
        assert calls[0][1] == 9000.0
        stderr_text = (root / "state" / "runs" / run.run_id / "worker.stderr.log").read_text(encoding="utf-8")
        assert "raised direct worker watchdog from 1200s to 9000s" in stderr_text


def test_worker_lane_candidates_prioritize_core_rescue_before_survival_for_core() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        args = _args(root)
        args.worker_lane = "core"

        lanes = module._worker_lane_candidates(args)

        assert lanes == ["core", "core_rescue", "survival", "repair"]


def test_direct_worker_lane_health_snapshot_flags_unroutable_repair_profile(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        args = _args(root)
        args.worker_bin = "codexea"
        args.worker_lane = "core"
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_CORE_RESPONSES_PROFILE", "core_batch")

        def fake_urlopen(request, timeout=0):
            payload = {
                "provider_registry": {
                    "lanes": [
                        {
                            "profile": "core_batch",
                            "primary_provider_key": "onemin",
                            "primary_state": "ready",
                            "capacity_summary": {
                                "state": "ready",
                                "configured_slots": 49,
                                "ready_slots": 47,
                                "degraded_slots": 0,
                                "unavailable_slots": 2,
                                "remaining_percent_of_max": 0.05,
                            },
                            "providers": [{"provider_key": "onemin", "state": "ready", "detail": ""}],
                        },
                        {
                            "profile": "repair",
                            "primary_provider_key": "magixai",
                            "primary_state": "degraded",
                            "capacity_summary": {
                                "state": "degraded",
                                "configured_slots": 1,
                                "ready_slots": 0,
                                "degraded_slots": 1,
                                "unavailable_slots": 0,
                            },
                            "providers": [
                                {
                                    "provider_key": "magixai",
                                    "state": "degraded",
                                    "detail": "rate limit exceeded",
                                    "enabled": True,
                                    "executable": True,
                                }
                            ],
                        },
                    ]
                }
            }

            class _Response:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def read(self):
                    return json.dumps(payload).encode("utf-8")

            return _Response()

        monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)
        lanes = ["core", "repair"]

        snapshot = module._direct_worker_lane_health_snapshot(args, lanes)

        assert snapshot["status"] == "pass"
        assert snapshot["routable_lanes"] == ["core"]
        assert snapshot["unroutable_lanes"] == ["repair"]
        assert snapshot["lanes"]["core"]["profile"] == "core_batch"
        assert snapshot["lanes"]["repair"]["profile"] == "repair"
        assert snapshot["lanes"]["repair"]["routable"] is False
        assert snapshot["lanes"]["repair"]["state"] == "degraded"


def test_direct_worker_lane_health_snapshot_sends_runtime_ea_auth_headers(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        args = _args(root)
        args.worker_bin = "codexea"
        args.worker_lane = "core"
        monkeypatch.setenv("EA_MCP_API_TOKEN", "test-token")
        monkeypatch.setenv("EA_MCP_PRINCIPAL_ID", "codex-fleet")
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_CORE_RESPONSES_PROFILE", "core_batch")
        seen_headers = {}

        def fake_urlopen(request, timeout=0):
            seen_headers.update({key.lower(): value for key, value in request.header_items()})
            payload = {
                "provider_registry": {
                    "lanes": [
                        {
                            "profile": "core_batch",
                            "primary_provider_key": "onemin",
                            "primary_state": "ready",
                            "capacity_summary": {
                                "state": "ready",
                                "configured_slots": 49,
                                "ready_slots": 47,
                                "degraded_slots": 0,
                                "unavailable_slots": 2,
                            },
                            "providers": [{"provider_key": "onemin", "state": "ready", "detail": ""}],
                        }
                    ]
                }
            }

            class _Response:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def read(self):
                    return json.dumps(payload).encode("utf-8")

            return _Response()

        monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)

        snapshot = module._direct_worker_lane_health_snapshot(args, ["core"])

        assert snapshot["status"] == "pass"
        assert seen_headers["authorization"] == "Bearer test-token"
        assert seen_headers["x-ea-principal-id"] == "codex-fleet"


def test_codexea_profile_for_lane_uses_dedicated_repair_profile(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        monkeypatch.delenv("CODEXEA_CORE_RESPONSES_PROFILE", raising=False)
        monkeypatch.delenv("CHUMMER_DESIGN_SUPERVISOR_CORE_RESPONSES_PROFILE", raising=False)

        assert module._codexea_profile_for_lane("repair", workspace_root=root) == "repair"


def test_ea_provider_health_candidate_urls_adds_host_gateway_fallback_for_loopback() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        args = _args(root)
        args.ea_provider_health_url = "http://127.0.0.1:8090/v1/responses/_provider_health"

        urls = module._ea_provider_health_candidate_urls(args)

        assert urls == [
            "http://127.0.0.1:8090/v1/responses/_provider_health",
            "http://host.docker.internal:8090/v1/responses/_provider_health",
        ]


def test_ea_provider_health_candidate_urls_adds_loopback_fallback_for_host_gateway() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        args = _args(root)
        args.ea_provider_health_url = "http://host.docker.internal:8090/v1/responses/_provider_health"

        urls = module._ea_provider_health_candidate_urls(args)

        assert urls == [
            "http://host.docker.internal:8090/v1/responses/_provider_health",
            "http://127.0.0.1:8090/v1/responses/_provider_health",
        ]


def test_direct_worker_lane_health_snapshot_falls_back_to_host_gateway_when_loopback_refuses(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        args = _args(root)
        args.worker_bin = "codexea"
        args.worker_lane = "core"
        args.ea_provider_health_url = "http://127.0.0.1:8090/v1/responses/_provider_health"
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_CORE_RESPONSES_PROFILE", "core_batch")
        seen_urls: list[str] = []

        def fake_urlopen(request, timeout=0):
            url = request.full_url if hasattr(request, "full_url") else str(request)
            seen_urls.append(url)
            if url.startswith("http://127.0.0.1:8090/"):
                raise module.urllib.error.URLError(ConnectionRefusedError(111, "Connection refused"))
            payload = {
                "provider_registry": {
                    "lanes": [
                        {
                            "profile": "core_batch",
                            "primary_provider_key": "onemin",
                            "primary_state": "ready",
                            "capacity_summary": {
                                "state": "ready",
                                "configured_slots": 49,
                                "ready_slots": 47,
                                "degraded_slots": 0,
                                "unavailable_slots": 2,
                            },
                            "providers": [{"provider_key": "onemin", "state": "ready", "detail": ""}],
                        }
                    ]
                }
            }

            class _Response:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def read(self):
                    return json.dumps(payload).encode("utf-8")

            return _Response()

        monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)

        snapshot = module._direct_worker_lane_health_snapshot(args, ["core"])

        assert seen_urls == [
            "http://127.0.0.1:8090/v1/responses/_provider_health",
            "http://host.docker.internal:8090/v1/responses/_provider_health",
        ]
        assert snapshot["status"] == "pass"
        assert snapshot["source_url"] == "http://host.docker.internal:8090/v1/responses/_provider_health"
        assert snapshot["routable_lanes"] == ["core"]


def test_direct_worker_lane_health_snapshot_falls_back_to_loopback_when_host_gateway_is_unresolved(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        args = _args(root)
        args.worker_bin = "codexea"
        args.worker_lane = "core"
        args.ea_provider_health_url = "http://host.docker.internal:8090/v1/responses/_provider_health"
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_CORE_RESPONSES_PROFILE", "core_batch")
        seen_urls: list[str] = []

        def fake_urlopen(request, timeout=0):
            url = request.full_url if hasattr(request, "full_url") else str(request)
            seen_urls.append(url)
            if url.startswith("http://host.docker.internal:8090/"):
                raise module.urllib.error.URLError(OSError(-2, "Name or service not known"))
            payload = {
                "provider_registry": {
                    "lanes": [
                        {
                            "profile": "core_batch",
                            "primary_provider_key": "onemin",
                            "primary_state": "ready",
                            "capacity_summary": {
                                "state": "ready",
                                "configured_slots": 49,
                                "ready_slots": 47,
                                "degraded_slots": 0,
                                "unavailable_slots": 2,
                            },
                            "providers": [{"provider_key": "onemin", "state": "ready", "detail": ""}],
                        }
                    ]
                }
            }

            class _Response:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def read(self):
                    return json.dumps(payload).encode("utf-8")

            return _Response()

        monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)

        snapshot = module._direct_worker_lane_health_snapshot(args, ["core"])

        assert seen_urls == [
            "http://host.docker.internal:8090/v1/responses/_provider_health",
            "http://127.0.0.1:8090/v1/responses/_provider_health",
        ]
        assert snapshot["status"] == "pass"
        assert snapshot["source_url"] == "http://127.0.0.1:8090/v1/responses/_provider_health"
        assert snapshot["routable_lanes"] == ["core"]


def test_direct_worker_lane_health_snapshot_retries_same_url_after_timeout(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        args = _args(root)
        args.worker_bin = "codexea"
        args.worker_lane = "core"
        args.ea_provider_health_url = "http://127.0.0.1:8090/v1/responses/_provider_health"
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_CORE_RESPONSES_PROFILE", "core_batch")
        seen: list[tuple[str, float]] = []
        call_count = {"value": 0}

        def fake_urlopen(request, timeout=0):
            url = request.full_url if hasattr(request, "full_url") else str(request)
            seen.append((url, float(timeout)))
            call_count["value"] += 1
            if call_count["value"] == 1:
                raise TimeoutError("timed out")
            payload = {
                "provider_registry": {
                    "lanes": [
                        {
                            "profile": "core_batch",
                            "primary_provider_key": "onemin",
                            "primary_state": "ready",
                            "capacity_summary": {
                                "state": "ready",
                                "configured_slots": 49,
                                "ready_slots": 47,
                                "degraded_slots": 0,
                                "unavailable_slots": 2,
                            },
                            "providers": [{"provider_key": "onemin", "state": "ready", "detail": ""}],
                        }
                    ]
                }
            }

            class _Response:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def read(self):
                    return json.dumps(payload).encode("utf-8")

            return _Response()

        monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)

        snapshot = module._direct_worker_lane_health_snapshot(args, ["core"])

        assert seen == [
            ("http://127.0.0.1:8090/v1/responses/_provider_health", 4.0),
            ("http://127.0.0.1:8090/v1/responses/_provider_health", 8.0),
        ]
        assert snapshot["status"] == "pass"
        assert snapshot["source_url"] == "http://127.0.0.1:8090/v1/responses/_provider_health"
        assert snapshot["routable_lanes"] == ["core"]


def test_launch_worker_skips_unroutable_direct_lane_before_attempt(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("W2 milestone `21` remains active.\n", encoding="utf-8")
        args = _args(root)
        args.worker_bin = "codexea"
        args.worker_lane = "core"
        context = module.derive_context(args)

        monkeypatch.setattr(
            module,
            "_direct_worker_lane_health_snapshot",
            lambda _args, _lanes: {
                "status": "pass",
                "reason": "repair is degraded with no ready slots",
                "routable_lanes": ["core", "core_rescue"],
                "unroutable_lanes": ["repair"],
                "lanes": {
                    "core": {"worker_lane": "core", "profile": "core_batch", "state": "ready", "routable": True, "reason": ""},
                    "repair": {
                        "worker_lane": "repair",
                        "profile": "easy",
                        "state": "degraded",
                        "routable": False,
                        "reason": "magixai degraded and has no ready slots",
                    },
                    "core_rescue": {
                        "worker_lane": "core_rescue",
                        "profile": "core_rescue",
                        "state": "ready",
                        "routable": True,
                        "reason": "",
                    },
                },
            },
        )

        calls: list[list[str]] = []

        def fake_run(command, *, input, text, capture_output, cwd, check, env=None, timeout=None):
            calls.append(list(command))
            message_path = Path(command[command.index("-o") + 1])
            lane = command[1]
            if lane == "core":
                message_path.write_text("Error: upstream_timeout:300s\n", encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
            message_path.write_text(
                "What shipped: rescue lane recovered the slice\nWhat remains: none\nExact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        monkeypatch.setattr(module.subprocess, "run", fake_run)

        run = module.launch_worker(args, context, root / "state")

        assert run.accepted is True
        assert run.attempted_accounts == ["lane:core", "lane:core_rescue"]
        assert [call[1] for call in calls] == ["core", "core_rescue"]
        stderr_text = (root / "state" / "runs" / run.run_id / "worker.stderr.log").read_text(encoding="utf-8")
        assert "skip direct lane=repair" in stderr_text


def test_build_completion_review_prompt_compacts_verbose_sections() -> None:
    module = _load_module()
    frontier = [
        module.Milestone(
            id=1394756221,
            title="Repo backlog: ui-kit token canon",
            wave="completion_review",
            status="review_required",
            owners=["chummer6-ui-kit"],
            exit_criteria=["Close the active repo-local backlog item."],
            dependencies=[],
        )
    ]
    audit = {
        "status": "fail",
        "reason": "latest worker receipt is not trusted",
        "journey_gate_audit": {
            "blocked_journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "state": "warning",
                    "owner_repos": ["chummer6-ui", "fleet"],
                    "warning_reasons": ["x" * 320],
                }
            ]
        },
        "linux_desktop_exit_gate_audit": {
            "path": "/tmp/proof.json",
            "generated_at": "2026-03-31T14:36:03Z",
            "age_seconds": 12,
            "proof_status": "passed",
            "stage": "complete",
            "head_id": "avalonia",
            "launch_target": "Chummer.Avalonia",
            "rid": "linux-x64",
            "source_snapshot_mode": "filesystem_copy",
            "primary_install_mode": "dpkg_rootless_install",
            "primary_install_verification_status": "passed",
            "primary_smoke_status": "passed",
            "fallback_smoke_status": "passed",
            "unit_test_status": "passed",
            "test_total": 14,
            "test_passed": 14,
            "test_failed": 0,
            "test_skipped": 0,
            "primary_install_verification_path": "/tmp/install-verification.json",
            "source_snapshot_entry_count": 377,
            "source_snapshot_finish_entry_count": 377,
            "source_snapshot_worktree_sha256": "a" * 128,
            "source_snapshot_finish_worktree_sha256": "b" * 128,
            "source_snapshot_identity_stable": True,
            "primary_install_wrapper_sha256": "c" * 128,
            "primary_install_desktop_entry_sha256": "d" * 128,
            "proof_git_head": "e" * 64,
            "current_git_head": "f" * 64,
            "reason": "linux desktop proof ready",
        },
        "weekly_pulse_audit": {
            "path": "/tmp/pulse.json",
            "generated_at": "2026-03-31T01:19:26Z",
            "as_of": "2026-03-31",
            "release_health_state": "green_or_explained",
            "journey_gate_health_state": "ready",
            "design_drift_count": 0,
            "public_promise_drift_count": 0,
            "oldest_blocker_days": 0,
        },
        "repo_backlog_audit": {
            "status": "fail",
            "open_items": [
                {
                    "project_id": "ui-kit",
                    "repo_slug": "chummer6-ui-kit",
                    "task": "Seed token canon " + ("and preview gallery " * 20),
                }
                for _ in range(6)
            ],
        },
    }
    history = [
        {
            "run_id": "20260331T161153Z",
            "worker_exit_code": 0,
            "frontier_ids": [1394756221],
            "primary_milestone_id": 1394756221,
            "final_message": "Error: upstream_timeout:300s",
        }
    ]

    prompt = module.build_completion_review_prompt(
        registry_path=Path("/tmp/registry.yaml"),
        program_milestones_path=Path("/tmp/PROGRAM_MILESTONES.yaml"),
        roadmap_path=Path("/tmp/ROADMAP.md"),
        handoff_path=Path("/tmp/NEXT_SESSION_HANDOFF.md"),
        frontier_artifact_path=Path("/tmp/COMPLETION_REVIEW_FRONTIER.generated.yaml"),
        frontier=frontier,
        scope_roots=[Path("/docker/fleet"), Path("/docker/chummercomplete")],
        focus_profiles=[],
        focus_owners=["chummer6-ui", "chummer6-ui-kit"],
        focus_texts=["desktop", "client"],
        audit=audit,
        history=history,
    )

    assert "snapshot_sha=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" not in prompt
    assert "- + 2 more" in prompt or "- + 1 more" in prompt


def test_build_completion_review_prompt_compact_mode_is_artifact_first() -> None:
    module = _load_module()
    frontier = [
        module.Milestone(
            id=1394756221,
            title="Repo backlog: ui-kit token canon",
            wave="completion_review",
            status="review_required",
            owners=["chummer6-ui-kit"],
            exit_criteria=["Close the active repo-local backlog item."],
            dependencies=[],
        )
    ]
    audit = {
        "status": "fail",
        "reason": "latest worker receipt is not trusted",
        "repo_backlog_audit": {
            "status": "fail",
            "open_items": [
                {
                    "project_id": "ui-kit",
                    "repo_slug": "chummer6-ui-kit",
                    "task": "Seed token canon " + ("and preview gallery " * 20),
                }
            ],
        },
    }

    prompt = module.build_completion_review_prompt(
        registry_path=Path("/tmp/registry.yaml"),
        program_milestones_path=Path("/tmp/PROGRAM_MILESTONES.yaml"),
        roadmap_path=Path("/tmp/ROADMAP.md"),
        handoff_path=Path("/tmp/NEXT_SESSION_HANDOFF.md"),
        frontier_artifact_path=Path("/tmp/COMPLETION_REVIEW_FRONTIER.generated.yaml"),
        frontier=frontier,
        scope_roots=[Path("/docker/fleet"), Path("/docker/chummercomplete")],
        focus_profiles=[],
        focus_owners=["chummer6-ui-kit"],
        focus_texts=["desktop", "sr6"],
        audit=audit,
        history=[],
        compact_prompt=True,
    )

    assert "Read these files directly first:" in prompt
    assert "/tmp/COMPLETION_REVIEW_FRONTIER.generated.yaml" in prompt
    assert "Linux desktop exit-gate gaps:" not in prompt
    assert "Weekly product pulse gaps:" not in prompt
    assert len(prompt) < 2200


def test_focused_frontier_biases_owner_and_text_without_requiring_both() -> None:
    module = _load_module()
    frontier = [
        module.Milestone(
            id=1,
            title="Hub registry contracts",
            wave="completion_review",
            status="review_required",
            owners=["chummer6-hub-registry"],
            exit_criteria=["Extract registry contracts."],
            dependencies=[],
        ),
        module.Milestone(
            id=2,
            title="Ruleset-specific workbench adaptation",
            wave="completion_review",
            status="review_required",
            owners=["chummer6-ui"],
            exit_criteria=["Make SR4/SR5/SR6 posture explicit in the workbench."],
            dependencies=[],
        ),
        module.Milestone(
            id=3,
            title="Seed Ui Kit token canon",
            wave="completion_review",
            status="review_required",
            owners=["chummer6-ui-kit"],
            exit_criteria=["Theme compilation ships."],
            dependencies=[],
        ),
    ]
    args = Namespace(
        focus_profile=[],
        focus_owner=["chummer6-ui", "chummer6-ui-kit"],
        focus_text=["workbench", "desktop"],
    )

    focused = module._focused_frontier(args, frontier, frontier)

    assert [item.id for item in focused] == [2, 3]


def test_launch_worker_records_and_clears_active_run_state(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("W2 milestone `21` remains active.\n", encoding="utf-8")
        args = _args(root)
        args.worker_bin = "codexea"
        args.worker_lane = "core"
        args.worker_model = ""
        context = module.derive_context(args)

        seen_active_runs: list[dict[str, object]] = []

        def fake_run(command, *, input, text, capture_output, cwd, check, env=None):
            state = json.loads((root / "state" / "state.json").read_text(encoding="utf-8"))
            seen_active_runs.append(dict(state["active_run"]))
            message_path = Path(command[command.index("-o") + 1])
            message_path.write_text(
                "What shipped: active run was visible\nWhat remains: follow-through\nExact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        monkeypatch.setattr(module.subprocess, "run", fake_run)

        run = module.launch_worker(args, context, root / "state")

        assert seen_active_runs
        assert seen_active_runs[0]["run_id"] == run.run_id
        assert seen_active_runs[0]["selected_account_alias"] == "lane:core"
        final_state = json.loads((root / "state" / "state.json").read_text(encoding="utf-8"))
        assert "active_run" not in final_state


def test_completion_audit_rejects_untrusted_latest_receipt() -> None:
    module = _load_module()

    audit = module._completion_audit(
        [
            {
                "run_id": "run-1",
                "worker_exit_code": 0,
                "accepted": True,
                "acceptance_reason": "",
                "shipped": "trusted closeout",
                "remains": "none",
                "blocker": "none",
            },
            {
                "run_id": "run-2",
                "worker_exit_code": 0,
                "final_message": "Error: upstream_timeout:300s\n",
            },
        ]
    )

    assert audit["status"] == "fail"
    assert audit["latest_run_id"] == "run-2"
    assert "not trusted" in audit["reason"]
    assert audit["rejected_zero_exit_run_ids"] == ["run-2"]


def test_completion_audit_ignores_rejected_zero_exit_receipts_superseded_by_later_trusted_receipt() -> None:
    module = _load_module()

    audit = module._completion_audit(
        [
            {
                "run_id": "run-1",
                "worker_exit_code": 0,
                "final_message": "Error: upstream_timeout:300s\n",
            },
            {
                "run_id": "run-2",
                "worker_exit_code": 0,
                "accepted": True,
                "acceptance_reason": "",
                "shipped": "trusted closeout",
                "remains": "none",
                "blocker": "none",
            },
        ]
    )

    assert audit["status"] == "pass"
    assert audit["latest_run_id"] == "run-2"
    assert audit["rejected_zero_exit_run_ids"] == []


def test_design_completion_audit_passes_with_ready_release_proof() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root)
        args = _args(root)

        audit = module._design_completion_audit(
            args,
            [
                {
                    "run_id": "run-1",
                    "worker_exit_code": 0,
                    "accepted": True,
                    "acceptance_reason": "",
                    "shipped": "desktop release proof is trusted",
                    "remains": "none",
                    "blocker": "none",
                }
            ],
        )

        assert audit["status"] == "pass"
        assert audit["journey_gate_audit"]["status"] == "pass"
        assert audit["weekly_pulse_audit"]["status"] == "pass"


def test_design_completion_audit_fails_when_desktop_executable_exit_gate_is_stale() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root)
        stale_text = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=2)).replace(microsecond=0).isoformat().replace(
            "+00:00", "Z"
        )
        executable_gate_path = root / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
        executable_payload = json.loads(executable_gate_path.read_text(encoding="utf-8"))
        executable_payload["generatedAt"] = stale_text
        executable_gate_path.write_text(json.dumps(executable_payload), encoding="utf-8")
        args = _args(root)

        audit = module._design_completion_audit(
            args,
            [
                {
                    "run_id": "run-1",
                    "worker_exit_code": 0,
                    "accepted": True,
                    "acceptance_reason": "",
                    "shipped": "desktop release proof is trusted",
                    "remains": "none",
                    "blocker": "none",
                }
            ],
        )

        assert audit["status"] == "fail"
        assert audit["desktop_executable_exit_gate_audit"]["status"] == "fail"
        assert "stale" in str(audit["desktop_executable_exit_gate_audit"]["reason"]).lower()


def test_design_completion_audit_rejects_release_proof_warning() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root, ui_posture="protected_preview")
        args = _args(root)

        audit = module._design_completion_audit(
            args,
            [
                {
                    "run_id": "run-1",
                    "worker_exit_code": 0,
                    "accepted": True,
                    "acceptance_reason": "",
                    "shipped": "trusted receipt",
                    "remains": "none",
                    "blocker": "none",
                }
            ],
        )

        assert audit["status"] == "fail"
        assert audit["journey_gate_audit"]["status"] == "fail"
        assert audit["journey_gate_audit"]["overall_state"] == "warning"
        assert "before claiming" in audit["reason"]


def test_design_completion_audit_accepts_lagging_weekly_pulse_journey_warning_when_live_proof_is_ready() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root, journey_gate_health_state="warning")
        args = _args(root)

        audit = module._design_completion_audit(
            args,
            [
                {
                    "run_id": "run-1",
                    "worker_exit_code": 0,
                    "accepted": True,
                    "acceptance_reason": "",
                    "shipped": "trusted receipt",
                    "remains": "none",
                    "blocker": "none",
                }
            ],
        )

        assert audit["status"] == "pass"
        assert audit["journey_gate_audit"]["status"] == "pass"
        assert audit["weekly_pulse_audit"]["status"] == "pass"
        assert audit["weekly_pulse_audit"]["live_journey_gate_override"] is True
        assert audit["weekly_pulse_audit"]["lagging_journey_gate_health_state"] == "warning"


def test_design_completion_audit_keeps_weekly_pulse_fail_when_release_health_is_not_green() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(
            root,
            journey_gate_health_state="warning",
            release_health_state="yellow",
        )
        args = _args(root)

        audit = module._design_completion_audit(
            args,
            [
                {
                    "run_id": "run-1",
                    "worker_exit_code": 0,
                    "accepted": True,
                    "acceptance_reason": "",
                    "shipped": "trusted receipt",
                    "remains": "none",
                    "blocker": "none",
                }
            ],
        )

        assert audit["status"] == "fail"
        assert audit["journey_gate_audit"]["status"] == "pass"
        assert audit["weekly_pulse_audit"]["status"] == "fail"
        assert audit["weekly_pulse_audit"].get("live_journey_gate_override") is not True


def test_design_completion_audit_fails_when_weekly_pulse_reports_automation_frontier_misalignment() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(
            root,
            automation_alignment_state="misaligned",
        )
        args = _args(root)

        audit = module._design_completion_audit(
            args,
            [
                {
                    "run_id": "run-1",
                    "worker_exit_code": 0,
                    "accepted": True,
                    "acceptance_reason": "",
                    "shipped": "trusted receipt",
                    "remains": "none",
                    "blocker": "none",
                }
            ],
        )

        assert audit["status"] == "fail"
        assert audit["journey_gate_audit"]["status"] == "pass"
        assert audit["weekly_pulse_audit"]["status"] == "fail"
        assert "automation frontier misalignment" in str(audit["weekly_pulse_audit"]["reason"]).lower()


def test_design_completion_audit_fails_when_weekly_pulse_missing_launch_governance_decision() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root)
        pulse_path = root / "WEEKLY_PRODUCT_PULSE.generated.json"
        pulse_payload = json.loads(pulse_path.read_text(encoding="utf-8"))
        pulse_payload["governor_decisions"] = [
            {
                "decision_id": "fixture-focus",
                "action": "focus_shift",
                "reason": "fixture",
                "cited_signals": ["overall_progress_percent=100"],
            }
        ]
        pulse_payload["snapshot"]["governor_decisions"] = pulse_payload["governor_decisions"]
        pulse_path.write_text(json.dumps(pulse_payload), encoding="utf-8")
        args = _args(root)

        audit = module._design_completion_audit(
            args,
            [
                {
                    "run_id": "run-1",
                    "worker_exit_code": 0,
                    "accepted": True,
                    "acceptance_reason": "",
                    "shipped": "trusted receipt",
                    "remains": "none",
                    "blocker": "none",
                }
            ],
        )

        assert audit["status"] == "fail"
        assert audit["weekly_pulse_audit"]["status"] == "fail"
        assert "launch governance decision" in str(audit["weekly_pulse_audit"]["reason"]).lower()


def test_design_completion_audit_fails_when_weekly_pulse_launch_expand_without_green_canary() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root)
        pulse_path = root / "WEEKLY_PRODUCT_PULSE.generated.json"
        pulse_payload = json.loads(pulse_path.read_text(encoding="utf-8"))
        pulse_payload["governor_decisions"] = [
            {
                "decision_id": "fixture-focus",
                "action": "focus_shift",
                "reason": "fixture",
                "cited_signals": ["overall_progress_percent=100"],
            },
            {
                "decision_id": "fixture-launch",
                "action": "launch_expand",
                "reason": "fixture",
                "cited_signals": [
                    "journey_gate_state=ready",
                    "journey_gate_blocked_count=0",
                    "local_release_proof_status=passed",
                    "provider_canary_status=Canary watch on 1 active lane(s)",
                    "closure_health_state=clear",
                ],
            },
        ]
        pulse_payload["snapshot"]["governor_decisions"] = pulse_payload["governor_decisions"]
        pulse_payload["supporting_signals"]["provider_route_stewardship"]["canary_status"] = (
            "Canary watch on 1 active lane(s)"
        )
        pulse_path.write_text(json.dumps(pulse_payload), encoding="utf-8")
        args = _args(root)

        audit = module._design_completion_audit(
            args,
            [
                {
                    "run_id": "run-1",
                    "worker_exit_code": 0,
                    "accepted": True,
                    "acceptance_reason": "",
                    "shipped": "trusted receipt",
                    "remains": "none",
                    "blocker": "none",
                }
            ],
        )

        assert audit["status"] == "fail"
        assert audit["weekly_pulse_audit"]["status"] == "fail"
        assert "launch_expand" in str(audit["weekly_pulse_audit"]["reason"]).lower()


def test_run_receipt_status_rejects_accepted_receipt_without_structured_content() -> None:
    module = _load_module()

    accepted, reason = module._run_receipt_status(
        {
            "run_id": "run-dry",
            "worker_exit_code": 0,
            "accepted": True,
            "acceptance_reason": "",
            "shipped": "",
            "remains": "",
            "blocker": "",
            "final_message": "",
        }
    )

    assert accepted is False
    assert "missing structured closeout content" in reason


def test_run_receipt_status_reheals_stale_false_reject_when_final_message_parses() -> None:
    module = _load_module()

    accepted, reason = module._run_receipt_status(
        {
            "run_id": "run-healed",
            "worker_exit_code": 0,
            "accepted": False,
            "acceptance_reason": "missing structured closeout fields: What shipped, What remains, Exact blocker",
            "final_message": (
                "I am going to fix the blocker.\n"
                '{"decision":"final","text":"What shipped: alpha\\nWhat remains: beta\\nExact blocker: none"}'
            ),
        }
    )

    assert accepted is True
    assert reason == ""


def test_derive_completion_review_context_targets_recent_untrusted_frontier() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}],
                    "milestones": [
                        {
                            "id": 13,
                            "title": "Desktop package proof",
                            "wave": "W4",
                            "status": "complete",
                            "owners": ["chummer6-ui", "fleet"],
                            "exit_criteria": ["Desktop package ships."],
                        },
                        {
                            "id": 14,
                            "title": "Rules parity proof",
                            "wave": "W4",
                            "status": "complete",
                            "owners": ["chummer6-core", "chummer6-ui"],
                            "exit_criteria": ["SR4-SR6 parity is proven."],
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        _write_completion_evidence(root)
        state_root = root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        (state_root / "history.jsonl").write_text(
            json.dumps(
                {
                    "run_id": "run-9",
                    "worker_exit_code": 0,
                    "primary_milestone_id": 13,
                    "frontier_ids": [13, 14],
                    "final_message": "Error: upstream_timeout:300s\n",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        args = _args(root)
        base_context = module.derive_context(args)
        audit = module._completion_audit(module._read_history(state_root / "history.jsonl", limit=10))

        context = module.derive_completion_review_context(args, state_root, base_context=base_context, audit=audit)

        assert context["frontier_ids"] == [13, 14]
        assert "false-complete recovery pass" in context["prompt"]
        assert "run run-9 primary=13 frontier=13, 14" in context["prompt"]
        assert "Desktop package proof" in context["prompt"]


def test_design_completion_audit_fails_when_repo_backlog_remains_outside_registry() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}],
                    "milestones": [
                        {
                            "id": 13,
                            "title": "Desktop package proof",
                            "wave": "W1",
                            "status": "complete",
                            "owners": ["chummer6-ui", "fleet"],
                            "exit_criteria": ["Desktop package ships."],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        _write_completion_evidence(root)
        _write_project_backlog(
            root,
            project_id="ui",
            repo_slug="chummer6-ui",
            task="Finish ruleset-specific workbench adaptation lane",
        )
        args = _args(root)

        audit = module._design_completion_audit(
            args,
            [
                {
                    "run_id": "run-1",
                    "worker_exit_code": 0,
                    "accepted": True,
                    "acceptance_reason": "",
                    "shipped": "trusted receipt",
                    "remains": "none",
                    "blocker": "none",
                }
            ],
        )

        assert audit["status"] == "fail"
        assert audit["repo_backlog_audit"]["status"] == "fail"
        assert audit["repo_backlog_audit"]["open_item_count"] == 1
        assert audit["repo_backlog_audit"]["open_items"][0]["project_id"] == "ui"
        assert "ruleset-specific workbench adaptation lane" in audit["repo_backlog_audit"]["open_items"][0]["task"]


def test_design_completion_audit_includes_absolute_secondary_worklist_sources() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}],
                    "milestones": [
                        {
                            "id": 13,
                            "title": "Desktop package proof",
                            "wave": "W1",
                            "status": "complete",
                            "owners": ["chummer6-ui", "fleet"],
                            "exit_criteria": ["Desktop package ships."],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        _write_completion_evidence(root)
        projects_dir = root / "projects"
        projects_dir.mkdir(parents=True, exist_ok=True)
        ui_root = root / "chummer6-ui"
        presentation_root = root / "chummer-presentation"
        ui_root.mkdir(parents=True, exist_ok=True)
        presentation_root.mkdir(parents=True, exist_ok=True)
        (ui_root / "WORKLIST.md").write_text("- [done] wl-217 Close Chummer5a desktop parity\n", encoding="utf-8")
        presentation_task = "Close SR4 desktop workflow parity against Chummer4"
        (presentation_root / "WORKLIST.md").write_text(
            f"- [queued] wl-218 {presentation_task}\n",
            encoding="utf-8",
        )
        (projects_dir / "ui.yaml").write_text(
            yaml.safe_dump(
                {
                    "id": "ui",
                    "path": str(ui_root),
                    "review": {"repo": "chummer6-ui"},
                    "queue": [],
                    "queue_sources": [
                        {"kind": "worklist", "path": "WORKLIST.md", "mode": "replace"},
                        {
                            "kind": "worklist",
                            "path": str(presentation_root / "WORKLIST.md"),
                            "mode": "append",
                        },
                    ],
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        args = _args(root)

        audit = module._design_completion_audit(
            args,
            [
                {
                    "run_id": "run-1",
                    "worker_exit_code": 0,
                    "accepted": True,
                    "acceptance_reason": "",
                    "shipped": "trusted receipt",
                    "remains": "none",
                    "blocker": "none",
                }
            ],
        )

        assert audit["status"] == "fail"
        assert audit["repo_backlog_audit"]["status"] == "fail"
        assert audit["repo_backlog_audit"]["open_item_count"] == 1
        assert audit["repo_backlog_audit"]["open_items"][0]["project_id"] == "ui"
        assert presentation_task in audit["repo_backlog_audit"]["open_items"][0]["task"]


def test_design_completion_audit_rejects_false_complete_receipt_when_repo_backlog_is_open() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}],
                    "milestones": [
                        {
                            "id": 13,
                            "title": "Desktop package proof",
                            "wave": "W1",
                            "status": "complete",
                            "owners": ["chummer6-ui", "fleet"],
                            "exit_criteria": ["Desktop package ships."],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        _write_completion_evidence(root)
        _write_project_backlog(
            root,
            project_id="ui",
            repo_slug="chummer6-ui",
            task="Close SR4 desktop workflow parity against Chummer4",
        )
        args = _args(root)

        audit = module._design_completion_audit(
            args,
            [
                {
                    "run_id": "run-1",
                    "worker_exit_code": 0,
                    "accepted": True,
                    "acceptance_reason": "",
                    "shipped": "Closed the queue.",
                    "remains": "none",
                    "blocker": "none",
                    "final_message": (
                        "What shipped: Closed the queue.\n"
                        "What remains: none.\n"
                        "Exact blocker: none.\n"
                    ),
                }
            ],
        )

        assert audit["status"] == "fail"
        assert audit["receipt_audit"]["status"] == "fail"
        assert audit["receipt_audit"]["contradiction"] == "repo_backlog"
        assert audit["receipt_audit"]["latest_run_id"] == "run-1"
        assert "contradicts live repo backlog" in audit["receipt_audit"]["reason"]
        assert "SR4 desktop workflow parity" in audit["receipt_audit"]["latest_run_reason"]


def test_design_completion_audit_keeps_partial_progress_receipt_trusted_when_repo_backlog_is_open() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}],
                    "milestones": [
                        {
                            "id": 13,
                            "title": "Desktop package proof",
                            "wave": "W1",
                            "status": "complete",
                            "owners": ["chummer6-ui", "fleet"],
                            "exit_criteria": ["Desktop package ships."],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        _write_completion_evidence(root)
        _write_project_backlog(
            root,
            project_id="ui",
            repo_slug="chummer6-ui",
            task="Close SR4 desktop workflow parity against Chummer4",
        )
        args = _args(root)

        audit = module._design_completion_audit(
            args,
            [
                {
                    "run_id": "run-2",
                    "worker_exit_code": 0,
                    "accepted": True,
                    "acceptance_reason": "",
                    "shipped": "Built three SR4 family receipts.",
                    "remains": "Need the remaining SR4 family receipts.",
                    "blocker": "none",
                    "final_message": (
                        "What shipped: Built three SR4 family receipts.\n"
                        "What remains: Need the remaining SR4 family receipts.\n"
                        "Exact blocker: none.\n"
                    ),
                }
            ],
        )

        assert audit["status"] == "fail"
        assert audit["repo_backlog_audit"]["status"] == "fail"
        assert audit["receipt_audit"]["status"] == "pass"
        assert "contradiction" not in audit["receipt_audit"]


def test_completion_review_frontier_drops_stale_generic_history_targets() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}],
                    "milestones": [
                        {
                            "id": 13,
                            "title": "Desktop package proof",
                            "wave": "W1",
                            "status": "complete",
                            "owners": ["chummer6-ui", "fleet"],
                            "exit_criteria": ["Desktop package ships."],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        _write_completion_evidence(root)
        _write_project_backlog(
            root,
            project_id="ui",
            repo_slug="chummer6-ui",
            task="Finish ruleset-specific workbench adaptation lane",
        )
        args = _args(root)
        audit = module._design_completion_audit(args, [])
        frontier = module._completion_review_frontier(
            audit,
            (root / "registry.yaml").resolve(),
            [
                {
                    "run_id": "run-stale",
                    "worker_exit_code": 0,
                    "accepted": False,
                    "acceptance_reason": "Error: survival_no_backend_available",
                    "frontier_ids": [999999001],
                    "primary_milestone_id": 999999001,
                }
            ],
        )

        frontier_ids = [item.id for item in frontier]
        assert 999999001 not in frontier_ids


def test_derive_completion_review_context_synthesizes_repo_backlog_milestones() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}],
                    "milestones": [
                        {
                            "id": 13,
                            "title": "Desktop package proof",
                            "wave": "W1",
                            "status": "complete",
                            "owners": ["chummer6-ui", "fleet"],
                            "exit_criteria": ["Desktop package ships."],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        _write_completion_evidence(root)
        task = "Finish ruleset-specific workbench adaptation lane"
        _write_project_backlog(root, project_id="ui", repo_slug="chummer6-ui", task=task)
        state_root = root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        history = [
            {
                "run_id": "run-good",
                "worker_exit_code": 0,
                "accepted": True,
                "acceptance_reason": "",
                "shipped": "trusted receipt",
                "remains": "none",
                "blocker": "none",
            }
        ]
        (state_root / "history.jsonl").write_text(json.dumps(history[0]) + "\n", encoding="utf-8")
        args = _args(root)
        base_context = module.derive_context(args)
        audit = module._design_completion_audit(args, history)

        context = module.derive_completion_review_context(args, state_root, base_context=base_context, audit=audit)
        synthetic_id = module._synthetic_completion_review_id(f"repo-backlog:ui:{task}")
        frontier_path = root / ".codex-studio" / "published" / "COMPLETION_REVIEW_FRONTIER.generated.yaml"
        mirror_path = root / ".codex-design" / "product" / "COMPLETION_REVIEW_FRONTIER.generated.yaml"

        assert context["frontier_ids"] == [synthetic_id]
        assert "Repo backlog: ui: Finish ruleset-specific workbench adaptation lane" in context["prompt"]
        assert "Repo-local backlog gaps" in context["prompt"]
        assert str(frontier_path) in context["prompt"]
        assert context["completion_review_frontier_path"] == str(frontier_path)
        assert context["completion_review_frontier_mirror_path"] == str(mirror_path)
        frontier_payload = yaml.safe_load(frontier_path.read_text(encoding="utf-8"))
        mirror_payload = yaml.safe_load(mirror_path.read_text(encoding="utf-8"))
        assert frontier_payload["contract_name"] == "fleet.completion_review_frontier"
        assert frontier_payload["mode"] == "completion_review"
        assert frontier_payload["frontier_ids"] == [synthetic_id]
        assert frontier_payload["repo_backlog_audit"]["open_item_count"] == 1
        assert mirror_payload["frontier_ids"] == [synthetic_id]


def test_completion_review_frontier_decomposes_visual_familiarity_backlog() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text("waves: []\nmilestones: []\n", encoding="utf-8")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        _write_completion_evidence(root)
        _write_project_backlog_tasks(
            root,
            project_id="ui",
            repo_slug="chummer6-ui",
            tasks=[
                "Add a release-blocking desktop visual familiarity gate so flagship desktop readiness requires Chummer-adjacent light/dark palette anchors, compact classic shell posture, and a visible loaded-runner tab rhythm instead of passing on executable proof alone.",
                "Add workflow-local visual familiarity proof for the dense legacy builder surfaces so character creation, gear, armor, weapons, cyberware, cyberlimbs, magic/resonance, and vehicle/drone workflows keep a Chummer-familiar browse/detail/confirm mental model instead of only passing data-parity receipts.",
            ],
        )
        args = _args(root)
        audit = module._design_completion_audit(args, [])

        frontier = module._completion_review_frontier(audit, Path(args.registry_path).resolve(), [])
        titles = [item.title for item in frontier]

        assert titles == [
            "Repo backlog: ui: Desktop shell visual familiarity",
            "Repo backlog: ui: Theme readability and loaded-runner tab posture",
            "Repo backlog: ui: Character creation and gear workflow visual familiarity",
            "Repo backlog: ui: Cyberware and cyberlimb dialog familiarity",
            "Repo backlog: ui: SR4 and SR6 workflow orientation familiarity",
        ]


def test_derive_completion_review_context_adds_visual_familiarity_focus_and_guidance() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text("waves: []\nmilestones: []\n", encoding="utf-8")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        _write_completion_evidence(root)
        _write_project_backlog_tasks(
            root,
            project_id="ui",
            repo_slug="chummer6-ui",
            tasks=[
                "Add a release-blocking desktop visual familiarity gate so flagship desktop readiness requires Chummer-adjacent light/dark palette anchors, compact classic shell posture, and a visible loaded-runner tab rhythm instead of passing on executable proof alone.",
                "Add workflow-local visual familiarity proof for the dense legacy builder surfaces so character creation, gear, armor, weapons, cyberware, cyberlimbs, magic/resonance, and vehicle/drone workflows keep a Chummer-familiar browse/detail/confirm mental model instead of only passing data-parity receipts.",
            ],
        )
        state_root = root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        args = _args(root)

        context = module.derive_completion_review_context(
            args,
            state_root,
            base_context=module.derive_context(args),
            audit=module._design_completion_audit(args, []),
        )

        assert context["focus_profiles"] == ["desktop_visual_familiarity"]
        assert "cyberware" in context["focus_texts"]
        assert "palette" in context["focus_texts"]
        assert str(Path("/docker/fleet/.codex-design/product/CHUMMER5A_FAMILIARITY_BRIDGE.md")) in context["prompt"]
        assert str(Path("/docker/fleet/.codex-design/product/DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.md")) in context["prompt"]
        assert len(context["frontier_ids"]) == 5


def test_derive_completion_review_context_fair_shares_visual_familiarity_backlog_across_three_shards() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text("waves: []\nmilestones: []\n", encoding="utf-8")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        _write_completion_evidence(root)
        _write_project_backlog_tasks(
            root,
            project_id="ui",
            repo_slug="chummer6-ui",
            tasks=[
                "Add a release-blocking desktop visual familiarity gate so flagship desktop readiness requires Chummer-adjacent light/dark palette anchors, compact classic shell posture, and a visible loaded-runner tab rhythm instead of passing on executable proof alone.",
                "Add workflow-local visual familiarity proof for the dense legacy builder surfaces so character creation, gear, armor, weapons, cyberware, cyberlimbs, magic/resonance, and vehicle/drone workflows keep a Chummer-familiar browse/detail/confirm mental model instead of only passing data-parity receipts.",
            ],
        )
        aggregate_root = root / "state" / "chummer_design_supervisor"
        shard_one_root = aggregate_root / "shard-1"
        shard_two_root = aggregate_root / "shard-2"
        shard_three_root = aggregate_root / "shard-3"
        for shard_root in (shard_one_root, shard_two_root, shard_three_root):
            shard_root.mkdir(parents=True, exist_ok=True)

        args = _args(root)
        audit = module._design_completion_audit(args, [])
        full_frontier_ids = [item.id for item in module._completion_review_frontier(audit, Path(args.registry_path).resolve(), [])]

        context_one = module.derive_completion_review_context(
            args,
            shard_one_root,
            base_context=module.derive_context(args),
            audit=audit,
        )
        module._write_json(
            shard_one_root / "state.json",
            {
                "updated_at": "2026-04-03T06:02:00Z",
                "mode": "completion_review",
                "frontier_ids": context_one["frontier_ids"],
                "active_run": {
                    "run_id": "run-1",
                    "frontier_ids": context_one["frontier_ids"],
                    "open_milestone_ids": [],
                },
            },
        )

        context_two = module.derive_completion_review_context(
            args,
            shard_two_root,
            base_context=module.derive_context(args),
            audit=audit,
        )
        module._write_json(
            shard_two_root / "state.json",
            {
                "updated_at": "2026-04-03T06:02:05Z",
                "mode": "completion_review",
                "frontier_ids": context_two["frontier_ids"],
                "active_run": {
                    "run_id": "run-2",
                    "frontier_ids": context_two["frontier_ids"],
                    "open_milestone_ids": [],
                },
            },
        )

        context_three = module.derive_completion_review_context(
            args,
            shard_three_root,
            base_context=module.derive_context(args),
            audit=audit,
        )

        combined_ids = context_one["frontier_ids"] + context_two["frontier_ids"] + context_three["frontier_ids"]

        assert len(full_frontier_ids) == 5
        assert len(context_one["frontier_ids"]) == 2
        assert len(context_two["frontier_ids"]) == 2
        assert len(context_three["frontier_ids"]) == 1
        assert sorted(combined_ids) == sorted(full_frontier_ids)
        assert len(set(combined_ids)) == len(full_frontier_ids)
        assert context_one["focus_profiles"] == ["desktop_visual_familiarity"]
        assert context_two["focus_profiles"] == ["desktop_visual_familiarity"]
        assert context_three["focus_profiles"] == ["desktop_visual_familiarity"]


def test_completion_review_frontier_decomposes_workflow_depth_backlog() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text("waves: []\nmilestones: []\n", encoding="utf-8")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        _write_completion_evidence(root)
        _write_project_backlog_tasks(
            root,
            project_id="ui",
            repo_slug="chummer6-ui",
            tasks=[
                "Add exhaustive executable desktop workflow click-through and binary UX proof so packaged Avalonia and Blazor Desktop builds prove live menu wiring, demo-runner discovery, Spotlight-launchable app posture, public feedback routes, and smooth builder journeys for character creation, karma, critters, adept powers, initiation, cyberdeck/programs, spells, drugs, contacts, diary/career-log, spirits/familiars, and vehicles/drones/rigger flows.",
            ],
        )
        args = _args(root)
        audit = module._design_completion_audit(args, [])

        frontier = module._completion_review_frontier(audit, Path(args.registry_path).resolve(), [])
        titles = [item.title for item in frontier]

        assert titles == [
            "Repo backlog: ui: Desktop shell and binary first-run smoothness",
            "Repo backlog: ui: Character creation, karma, and advancement workflow depth",
            "Repo backlog: ui: Magic, matrix, and consumables workflow depth",
            "Repo backlog: ui: Contacts, diary, and support-loop workflow depth",
            "Repo backlog: ui: Spirits, critters, familiars, vehicles, and rigger workflow depth",
        ]


def test_derive_completion_review_context_adds_workflow_depth_focus_and_guidance() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text("waves: []\nmilestones: []\n", encoding="utf-8")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        _write_completion_evidence(root)
        _write_project_backlog_tasks(
            root,
            project_id="ui",
            repo_slug="chummer6-ui",
            tasks=[
                "Add exhaustive executable desktop workflow click-through and binary UX proof so packaged Avalonia and Blazor Desktop builds prove live menu wiring, demo-runner discovery, Spotlight-launchable app posture, public feedback routes, and smooth builder journeys for character creation, karma, critters, adept powers, initiation, cyberdeck/programs, spells, drugs, contacts, diary/career-log, spirits/familiars, and vehicles/drones/rigger flows.",
            ],
        )
        state_root = root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        args = _args(root)

        context = module.derive_completion_review_context(
            args,
            state_root,
            base_context=module.derive_context(args),
            audit=module._design_completion_audit(args, []),
        )

        assert context["focus_profiles"] == ["desktop_visual_familiarity", "desktop_workflow_depth"]
        assert "spotlight-launchable" in context["focus_texts"]
        assert "adept powers" in context["focus_texts"]
        assert str(Path("/docker/fleet/.codex-design/product/DESKTOP_EXECUTABLE_EXIT_GATES.md")) in context["prompt"]
        assert str(Path("/docker/fleet/.codex-design/product/CHUMMER5A_FAMILIARITY_BRIDGE.md")) in context["prompt"]
        assert len(context["frontier_ids"]) == 5


def test_derive_completion_review_context_uses_shard_specific_frontier_artifacts() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text("waves: []\nmilestones: []\n", encoding="utf-8")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        _write_completion_evidence(root)
        task = "Publish and execute the ruleset-specific workbench adaptation lane"
        _write_project_backlog(root, project_id="ui", repo_slug="chummer6-ui", task=task)
        aggregate_root = root / "state" / "chummer_design_supervisor"
        shard_root = aggregate_root / "shard-2"
        shard_root.mkdir(parents=True, exist_ok=True)
        history = [
            {
                "run_id": "run-good",
                "worker_exit_code": 0,
                "accepted": True,
                "acceptance_reason": "",
                "shipped": "trusted receipt",
                "remains": "none",
                "blocker": "none",
            }
        ]
        (shard_root / "history.jsonl").write_text(json.dumps(history[0]) + "\n", encoding="utf-8")
        args = _args(root)
        base_context = module.derive_context(args)
        audit = module._design_completion_audit(args, history)

        context = module.derive_completion_review_context(args, shard_root, base_context=base_context, audit=audit)

        frontier_path = (
            root / ".codex-studio" / "published" / "completion-review-frontiers" / "shard-2.generated.yaml"
        )
        mirror_path = (
            root / ".codex-design" / "product" / "completion-review-frontiers" / "shard-2.generated.yaml"
        )
        assert context["completion_review_frontier_path"] == str(frontier_path)
        assert context["completion_review_frontier_mirror_path"] == str(mirror_path)
        assert str(frontier_path) in context["prompt"]
        assert frontier_path.exists()
        assert mirror_path.exists()


def test_derive_completion_review_context_excludes_prior_active_shard_claims() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text("waves: []\nmilestones: []\n", encoding="utf-8")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        _write_completion_evidence(root)
        task_a = "Seed Chummer.Ui.Kit with token canon"
        task_b = "Publish and execute the ruleset-specific workbench adaptation lane"
        projects_dir = root / "projects"
        projects_dir.mkdir(parents=True, exist_ok=True)
        ui_kit_root = root / "chummer6-ui-kit"
        ui_root = root / "chummer6-ui"
        ui_kit_root.mkdir(parents=True, exist_ok=True)
        ui_root.mkdir(parents=True, exist_ok=True)
        (ui_kit_root / "WORKLIST.md").write_text(f"- [queued] wl-1 {task_a}\n", encoding="utf-8")
        (ui_root / "WORKLIST.md").write_text(f"- [queued] wl-1 {task_b}\n", encoding="utf-8")
        (projects_dir / "ui-kit.yaml").write_text(
            yaml.safe_dump(
                {
                    "id": "ui-kit",
                    "path": str(ui_kit_root),
                    "review": {"repo": "chummer6-ui-kit"},
                    "queue": [],
                    "queue_sources": [{"kind": "worklist", "path": "WORKLIST.md", "mode": "replace"}],
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (projects_dir / "ui.yaml").write_text(
            yaml.safe_dump(
                {
                    "id": "ui",
                    "path": str(ui_root),
                    "review": {"repo": "chummer6-ui"},
                    "queue": [],
                    "queue_sources": [{"kind": "worklist", "path": "WORKLIST.md", "mode": "replace"}],
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        aggregate_root = root / "state" / "chummer_design_supervisor"
        shard_one_root = aggregate_root / "shard-1"
        shard_two_root = aggregate_root / "shard-2"
        shard_one_root.mkdir(parents=True, exist_ok=True)
        shard_two_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            shard_one_root / "state.json",
            {
                "updated_at": "2026-03-31T17:22:15Z",
                "mode": "completion_review",
                "frontier_ids": [],
                "active_run": {
                    "run_id": "run-1",
                    "frontier_ids": [
                        module._synthetic_completion_review_id(f"repo-backlog:ui-kit:{task_a}"),
                    ],
                    "open_milestone_ids": [],
                },
            },
        )
        args = _args(root)
        base_context = module.derive_context(args)
        audit = module._design_completion_audit(args, [])

        context = module.derive_completion_review_context(args, shard_two_root, base_context=base_context, audit=audit)

        assert context["completion_review_prior_claimed_frontier_ids"] == [
            module._synthetic_completion_review_id(f"repo-backlog:ui-kit:{task_a}")
        ]
        assert context["frontier_ids"] == [
            module._synthetic_completion_review_id(f"repo-backlog:ui:{task_b}")
        ]


def test_prior_active_shard_frontier_ids_ignores_aggregate_root() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        aggregate_root = root / "state" / "chummer_design_supervisor"
        shard_root = aggregate_root / "shard-1"
        shard_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            shard_root / "state.json",
            {
                "active_run": {
                    "run_id": "run-1",
                    "frontier_ids": [13, 14],
                    "open_milestone_ids": [],
                }
            },
        )

        assert module._prior_active_shard_frontier_ids(aggregate_root) == []


def test_configured_shard_roots_prefers_active_manifest_over_stale_dirs() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        aggregate_root = Path(tmp) / "state" / "chummer_design_supervisor"
        shard_one_root = aggregate_root / "shard-1"
        shard_two_root = aggregate_root / "shard-2"
        shard_three_root = aggregate_root / "shard-3"
        shard_four_root = aggregate_root / "shard-4"
        for shard_root in (shard_one_root, shard_two_root, shard_three_root, shard_four_root):
            shard_root.mkdir(parents=True, exist_ok=True)
        (aggregate_root / "active_shards.json").write_text(
            json.dumps({"active_shards": ["shard-1", "shard-3"]}),
            encoding="utf-8",
        )

        configured_roots = module._configured_shard_roots(aggregate_root)

        assert configured_roots == [shard_one_root, shard_three_root]


def test_configured_shard_roots_accepts_structured_manifest_entries() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        aggregate_root = Path(tmp) / "state" / "chummer_design_supervisor"
        shard_one_root = aggregate_root / "shard-1"
        shard_two_root = aggregate_root / "shard-2"
        shard_three_root = aggregate_root / "shard-3"
        for shard_root in (shard_one_root, shard_two_root, shard_three_root):
            shard_root.mkdir(parents=True, exist_ok=True)
            module._write_json(shard_root / "state.json", {"updated_at": "2026-03-31T08:00:00Z"})
        (aggregate_root / "active_shards.json").write_text(
            json.dumps(
                {
                    "generated_at": "2026-04-04T15:20:00Z",
                    "topology_fingerprint": "abc123",
                    "active_shards": [
                        {"name": "shard-1", "index": 1, "frontier_ids": [1, 2, 3]},
                        {"name": "shard-3", "index": 3, "frontier_ids": [7, 8, 9]},
                    ],
                }
            ),
            encoding="utf-8",
        )

        configured_roots = module._configured_shard_roots(aggregate_root)

        assert configured_roots == [shard_one_root, shard_three_root]


def test_heal_state_push_blockers_repairs_recorded_missing_github_push_blocker() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        state_root = Path(tmp) / "state" / "chummer_design_supervisor" / "shard-5"
        run_dir = state_root / "runs" / "run-1"
        run_dir.mkdir(parents=True, exist_ok=True)
        stderr_path = run_dir / "worker.stderr.log"
        stderr_path.write_text(
            "exec\n/usr/bin/bash -lc 'cd /docker/fleet && git push' in /docker/fleet exited 128 in 14ms:\n",
            encoding="utf-8",
        )
        last_message_path = run_dir / "last_message.txt"
        last_message_path.write_text(
            "What shipped: pushed nothing\n\n"
            "What remains: handoff still local\n\n"
            "Exact blocker: host-side git push recovery failed after worker credential error: "
            "/docker/fleet: fatal: could not read Username for 'https://github.com': No such device or address\n",
            encoding="utf-8",
        )
        run_payload = {
            "run_id": "run-1",
            "accepted": True,
            "worker_exit_code": 0,
            "started_at": "2026-04-04T15:00:00Z",
            "finished_at": "2026-04-04T15:05:00Z",
            "open_milestone_ids": [10, 11, 12, 15],
            "frontier_ids": [10, 11, 12, 15],
            "blocker": "host-side git push recovery failed after worker credential error: /docker/fleet: fatal: could not read Username for 'https://github.com': No such device or address",
            "shipped": "pushed nothing",
            "remains": "handoff still local",
            "final_message": last_message_path.read_text(encoding="utf-8"),
            "stderr_path": str(stderr_path),
            "last_message_path": str(last_message_path),
        }
        module._write_json(
            state_root / "state.json",
            {
                "updated_at": "2026-04-04T15:05:00Z",
                "mode": "loop",
                "open_milestone_ids": [10, 11, 12, 15],
                "frontier_ids": [10, 11, 12, 15],
                "last_run": dict(run_payload),
            },
        )
        (state_root / "history.jsonl").write_text(json.dumps(run_payload) + "\n", encoding="utf-8")

        original_retry = module._retry_worker_reported_git_pushes
        module._retry_worker_reported_git_pushes = (
            lambda _stderr: {"attempted": ["/docker/fleet"], "succeeded": ["/docker/fleet"], "failed": {}}
        )
        try:
            module._heal_state_push_blockers(state_root)
        finally:
            module._retry_worker_reported_git_pushes = original_retry

        state = module._read_state(state_root / "state.json")
        history = module._read_history(state_root / "history.jsonl", limit=0)

        assert state["last_run"]["blocker"] == "none"
        assert history[-1]["blocker"] == "none"
        assert "Exact blocker: none" in last_message_path.read_text(encoding="utf-8")


def test_heal_state_push_blockers_repairs_verified_remote_push_residue() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        state_root = Path(tmp) / "state" / "chummer_design_supervisor" / "shard-2"
        run_dir = state_root / "runs" / "run-1"
        run_dir.mkdir(parents=True, exist_ok=True)
        stderr_path = run_dir / "worker.stderr.log"
        stderr_path.write_text("", encoding="utf-8")
        last_message_path = run_dir / "last_message.txt"
        last_message_path.write_text(
            "What shipped: `/docker/fleet/NEXT_SESSION_HANDOFF.md` refreshed locally with both slices "
            "(local Fleet commits `fbc5b1d`, `370495d`).\n\n"
            "What remains: frontier milestones `14`, `17` residuals; "
            "Fleet handoff commits are not yet pushed to remote.\n\n"
            "Exact blocker: none\n",
            encoding="utf-8",
        )
        run_payload = {
            "run_id": "run-1",
            "accepted": True,
            "worker_exit_code": 0,
            "started_at": "2026-04-04T15:00:00Z",
            "finished_at": "2026-04-04T15:05:00Z",
            "open_milestone_ids": [13, 14, 17, 18],
            "frontier_ids": [13, 14, 17, 18],
            "blocker": "none",
            "shipped": "`/docker/fleet/NEXT_SESSION_HANDOFF.md` refreshed locally with both slices (local Fleet commits `fbc5b1d`, `370495d`).",
            "remains": "frontier milestones `14`, `17` residuals; Fleet handoff commits are not yet pushed to remote.",
            "final_message": last_message_path.read_text(encoding="utf-8"),
            "stderr_path": str(stderr_path),
            "last_message_path": str(last_message_path),
        }
        module._write_json(
            state_root / "state.json",
            {
                "updated_at": "2026-04-04T15:05:00Z",
                "mode": "loop",
                "open_milestone_ids": [13, 14, 17, 18],
                "frontier_ids": [13, 14, 17, 18],
                "last_run": dict(run_payload),
            },
        )
        (state_root / "history.jsonl").write_text(json.dumps(run_payload) + "\n", encoding="utf-8")

        original_contains = module._git_remote_contains_commit
        module._git_remote_contains_commit = lambda _repo, _commit, env=None: True
        try:
            module._heal_state_push_blockers(state_root)
        finally:
            module._git_remote_contains_commit = original_contains

        state = module._read_state(state_root / "state.json")
        history = module._read_history(state_root / "history.jsonl", limit=0)
        repaired_message = last_message_path.read_text(encoding="utf-8")

        assert state["last_run"]["blocker"] == "none"
        assert state["last_run"]["remains"] == "frontier milestones `14`, `17` residuals"
        assert "not yet pushed to remote" not in repaired_message
        assert "(Fleet commits `fbc5b1d`, `370495d`)" in repaired_message
        assert history[-1]["remains"] == "frontier milestones `14`, `17` residuals"


def test_heal_state_push_blockers_repairs_verified_not_yet_on_remote_phrase() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        state_root = Path(tmp) / "state" / "chummer_design_supervisor" / "shard-1"
        run_dir = state_root / "runs" / "run-1"
        run_dir.mkdir(parents=True, exist_ok=True)
        stderr_path = run_dir / "worker.stderr.log"
        stderr_path.write_text("", encoding="utf-8")
        last_message_path = run_dir / "last_message.txt"
        last_message_path.write_text(
            "What shipped: `chummer-hub-registry` hardening landed; `fleet` handoff was refreshed locally in `8140fd4`.\n\n"
            "What remains: frontier milestones `1`, `2`, `3` remain open; `fleet` commit `8140fd4` is not yet on remote.\n\n"
            "Exact blocker: none\n",
            encoding="utf-8",
        )
        run_payload = {
            "run_id": "run-1",
            "accepted": True,
            "worker_exit_code": 0,
            "started_at": "2026-04-04T16:15:57Z",
            "finished_at": "2026-04-04T16:24:46Z",
            "open_milestone_ids": [1, 2, 3],
            "frontier_ids": [1, 2, 3],
            "blocker": "none",
            "shipped": "`chummer-hub-registry` hardening landed; `fleet` handoff was refreshed locally in `8140fd4`.",
            "remains": "frontier milestones `1`, `2`, `3` remain open; `fleet` commit `8140fd4` is not yet on remote.",
            "final_message": last_message_path.read_text(encoding="utf-8"),
            "stderr_path": str(stderr_path),
            "last_message_path": str(last_message_path),
        }
        module._write_json(
            state_root / "state.json",
            {
                "updated_at": "2026-04-04T16:24:46Z",
                "mode": "loop",
                "open_milestone_ids": [1, 2, 3],
                "frontier_ids": [1, 2, 3],
                "last_run": dict(run_payload),
            },
        )
        (state_root / "history.jsonl").write_text(json.dumps(run_payload) + "\n", encoding="utf-8")

        original_contains = module._git_remote_contains_commit
        module._git_remote_contains_commit = lambda _repo, _commit, env=None: True
        try:
            module._heal_state_push_blockers(state_root)
        finally:
            module._git_remote_contains_commit = original_contains

        state = module._read_state(state_root / "state.json")
        history = module._read_history(state_root / "history.jsonl", limit=0)
        repaired_message = last_message_path.read_text(encoding="utf-8")

        assert state["last_run"]["blocker"] == "none"
        assert state["last_run"]["remains"] == "frontier milestones `1`, `2`, `3` remain open"
        assert "not yet on remote" not in repaired_message
        assert history[-1]["remains"] == "frontier milestones `1`, `2`, `3` remain open"


def test_open_milestone_shard_frontier_uses_active_manifest_to_avoid_stranded_slices() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        aggregate_root = Path(tmp) / "state" / "chummer_design_supervisor"
        shard_one_root = aggregate_root / "shard-1"
        shard_two_root = aggregate_root / "shard-2"
        shard_three_root = aggregate_root / "shard-3"
        shard_four_root = aggregate_root / "shard-4"
        for shard_root in (shard_one_root, shard_two_root, shard_three_root, shard_four_root):
            shard_root.mkdir(parents=True, exist_ok=True)
        (aggregate_root / "active_shards.json").write_text(
            json.dumps({"active_shards": ["shard-1", "shard-2", "shard-3"]}),
            encoding="utf-8",
        )
        frontier = [
            module.Milestone(
                id=index,
                title=f"Milestone {index}",
                wave="W1",
                status="in_progress",
                owners=["fleet"],
                exit_criteria=["Ship it."],
                dependencies=[],
            )
            for index in range(1, 7)
        ]

        shard_one_frontier = module._open_milestone_shard_frontier(shard_one_root, frontier, default_limit=5)
        shard_two_frontier = module._open_milestone_shard_frontier(shard_two_root, frontier, default_limit=5)
        shard_three_frontier = module._open_milestone_shard_frontier(shard_three_root, frontier, default_limit=5)

        assert [item.id for item in shard_one_frontier] == [1, 2]
        assert [item.id for item in shard_two_frontier] == [3, 4]
        assert [item.id for item in shard_three_frontier] == [5, 6]


def test_effective_supervisor_state_filters_history_that_does_not_match_current_manifest_pack() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        aggregate_root = Path(tmp) / "state" / "chummer_design_supervisor"
        shard_root = aggregate_root / "shard-1"
        shard_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            shard_root / "state.json",
            {
                "updated_at": "2026-04-04T15:20:00Z",
                "mode": "loop",
                "frontier_ids": [13, 14],
            },
        )
        module._append_jsonl(
            shard_root / "history.jsonl",
            {
                "run_id": "run-old",
                "finished_at": "2026-04-04T15:10:00Z",
                "frontier_ids": [4, 5],
                "worker_exit_code": 0,
            },
        )
        module._append_jsonl(
            shard_root / "history.jsonl",
            {
                "run_id": "run-current",
                "finished_at": "2026-04-04T15:15:00Z",
                "frontier_ids": [13, 14],
                "worker_exit_code": 0,
            },
        )
        (aggregate_root / "active_shards.json").write_text(
            json.dumps(
                {
                    "generated_at": "2026-04-04T15:20:00Z",
                    "topology_fingerprint": "abc123",
                    "active_shards": [
                        {"name": "shard-1", "index": 1, "frontier_ids": [13, 14]},
                    ],
                }
            ),
            encoding="utf-8",
        )

        state, history = module._effective_supervisor_state(aggregate_root, history_limit=10)

        assert state["last_run"]["run_id"] == "run-current"
        assert [run["run_id"] for run in history] == ["run-current"]


def test_effective_supervisor_state_filters_history_with_nonlocal_open_milestones() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        aggregate_root = Path(tmp) / "state" / "chummer_design_supervisor"
        shard_root = aggregate_root / "shard-2"
        shard_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            shard_root / "state.json",
            {
                "updated_at": "2026-04-04T15:20:00Z",
                "mode": "loop",
                "frontier_ids": [13, 14, 17, 18],
                "open_milestone_ids": [13, 14, 17, 18],
            },
        )
        module._append_jsonl(
            shard_root / "history.jsonl",
            {
                "run_id": "run-wide-open",
                "finished_at": "2026-04-04T15:10:00Z",
                "frontier_ids": [13, 14, 17, 18],
                "open_milestone_ids": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
                "worker_exit_code": 0,
            },
        )
        module._append_jsonl(
            shard_root / "history.jsonl",
            {
                "run_id": "run-local-open",
                "finished_at": "2026-04-04T15:15:00Z",
                "frontier_ids": [13, 14, 17, 18],
                "open_milestone_ids": [13, 14, 17, 18],
                "worker_exit_code": 0,
            },
        )
        (aggregate_root / "active_shards.json").write_text(
            json.dumps({"active_shards": [{"name": "shard-2", "frontier_ids": [13, 14, 17, 18]}]}),
            encoding="utf-8",
        )

        state, history = module._effective_supervisor_state(aggregate_root, history_limit=10)

        assert state["last_run"]["run_id"] == "run-local-open"
        assert [run["run_id"] for run in history] == ["run-local-open"]


def test_effective_supervisor_state_ignores_base_history_when_sharded() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        aggregate_root = Path(tmp) / "state" / "chummer_design_supervisor"
        shard_root = aggregate_root / "shard-1"
        shard_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            aggregate_root / "state.json",
            {
                "updated_at": "2026-04-04T15:00:00Z",
                "mode": "loop",
                "frontier_ids": [1, 2, 3, 4, 5],
                "open_milestone_ids": [1, 2, 3, 4, 5],
            },
        )
        module._append_jsonl(
            aggregate_root / "history.jsonl",
            {
                "run_id": "run-base",
                "finished_at": "2026-04-04T15:00:00Z",
                "frontier_ids": [1, 2, 3, 4, 5],
                "open_milestone_ids": [1, 2, 3, 4, 5],
                "worker_exit_code": 0,
            },
        )
        module._write_json(
            shard_root / "state.json",
            {
                "updated_at": "2026-04-04T15:10:00Z",
                "mode": "loop",
                "frontier_ids": [1, 2, 3],
                "open_milestone_ids": [1, 2, 3],
            },
        )
        module._append_jsonl(
            shard_root / "history.jsonl",
            {
                "run_id": "run-shard",
                "finished_at": "2026-04-04T15:10:00Z",
                "frontier_ids": [1, 2, 3],
                "open_milestone_ids": [1, 2, 3],
                "worker_exit_code": 0,
            },
        )
        (aggregate_root / "active_shards.json").write_text(
            json.dumps({"active_shards": [{"name": "shard-1", "frontier_ids": [1, 2, 3]}]}),
            encoding="utf-8",
        )

        state, history = module._effective_supervisor_state(aggregate_root, history_limit=10)

        assert state["frontier_ids"] == [1, 2, 3]
        assert [run["run_id"] for run in history] == ["run-shard"]


def test_effective_supervisor_state_ignores_stale_shard_dirs_not_in_manifest() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        aggregate_root = Path(tmp) / "state" / "chummer_design_supervisor"
        active_root = aggregate_root / "shard-1"
        stale_root = aggregate_root / "shard-9"
        active_root.mkdir(parents=True, exist_ok=True)
        stale_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            active_root / "state.json",
            {
                "updated_at": "2026-04-04T15:10:00Z",
                "mode": "loop",
                "frontier_ids": [1, 2, 3],
                "open_milestone_ids": [1, 2, 3],
            },
        )
        module._write_json(
            stale_root / "state.json",
            {
                "updated_at": "2026-04-04T15:20:00Z",
                "mode": "loop",
                "frontier_ids": [99],
                "open_milestone_ids": [99],
            },
        )
        (aggregate_root / "active_shards.json").write_text(
            json.dumps({"active_shards": [{"name": "shard-1", "frontier_ids": [1, 2, 3]}]}),
            encoding="utf-8",
        )

        state, _history = module._effective_supervisor_state(aggregate_root, history_limit=10)

        assert state["shard_count"] == 1
        assert state["frontier_ids"] == [1, 2, 3]
        assert state["open_milestone_ids"] == [1, 2, 3]


def test_effective_supervisor_state_surfaces_shard_blockers_in_aggregate_status() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        aggregate_root = Path(tmp) / "state" / "chummer_design_supervisor"
        shard_one_root = aggregate_root / "shard-1"
        shard_two_root = aggregate_root / "shard-2"
        shard_one_root.mkdir(parents=True, exist_ok=True)
        shard_two_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            shard_one_root / "state.json",
            {
                "updated_at": "2026-04-04T16:05:54Z",
                "mode": "loop",
                "open_milestone_ids": [1, 2, 3],
                "frontier_ids": [1, 2, 3],
                "last_run": {
                    "run_id": "run-blocked",
                    "finished_at": "2026-04-04T15:53:10Z",
                    "open_milestone_ids": [1, 2, 3],
                    "frontier_ids": [1, 2, 3],
                    "blocker": "Concurrent unseen local commits are landing in `/docker/fleet` during execution.",
                },
                "active_run": {
                    "run_id": "run-live",
                    "frontier_ids": [1, 2, 3],
                    "open_milestone_ids": [1, 2, 3],
                },
            },
        )
        module._write_json(
            shard_two_root / "state.json",
            {
                "updated_at": "2026-04-04T16:05:57Z",
                "mode": "loop",
                "open_milestone_ids": [13, 14],
                "frontier_ids": [13, 14],
                "last_run": {
                    "run_id": "run-clean",
                    "finished_at": "2026-04-04T15:53:50Z",
                    "open_milestone_ids": [13, 14],
                    "frontier_ids": [13, 14],
                    "blocker": "none",
                },
            },
        )
        (aggregate_root / "active_shards.json").write_text(
            json.dumps(
                {
                    "active_shards": [
                        {"name": "shard-1", "frontier_ids": [1, 2, 3]},
                        {"name": "shard-2", "frontier_ids": [13, 14]},
                    ]
                }
            ),
            encoding="utf-8",
        )

        state, _history = module._effective_supervisor_state(aggregate_root, history_limit=10)

        assert state["shard_blockers"] == [
            {
                "name": "shard-1",
                "run_id": "run-blocked",
                "blocker": "Concurrent unseen local commits are landing in `/docker/fleet` during execution.",
            }
        ]
        shard_rows = {row["name"]: row for row in state["shards"]}
        assert shard_rows["shard-1"]["last_run_blocker"] == (
            "Concurrent unseen local commits are landing in `/docker/fleet` during execution."
        )
        assert shard_rows["shard-2"]["last_run_blocker"] == ""


def test_effective_supervisor_state_recomputes_aggregate_eta_from_active_shards() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        aggregate_root = Path(tmp) / "state" / "chummer_design_supervisor"
        shard_one_root = aggregate_root / "shard-1"
        shard_two_root = aggregate_root / "shard-2"
        shard_one_root.mkdir(parents=True, exist_ok=True)
        shard_two_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            shard_one_root / "state.json",
            {
                "updated_at": "2026-04-04T16:05:54Z",
                "mode": "loop",
                "open_milestone_ids": [1, 2, 3],
                "frontier_ids": [1, 2, 3],
                "eta": {
                    "status": "estimated",
                    "eta_human": "4.5d-1.7w",
                    "eta_confidence": "low",
                    "basis": "heuristic_status_mix",
                    "summary": "3 open milestones remain (0 in progress, 3 not started); range is a fallback heuristic from the current status mix.",
                    "remaining_open_milestones": 3,
                    "remaining_in_progress_milestones": 0,
                    "remaining_not_started_milestones": 3,
                    "blocking_reason": "",
                },
                "active_run": {
                    "run_id": "run-live-1",
                    "frontier_ids": [1, 2, 3],
                    "open_milestone_ids": [1, 2, 3],
                },
            },
        )
        module._write_json(
            shard_two_root / "state.json",
            {
                "updated_at": "2026-04-04T16:05:57Z",
                "mode": "loop",
                "open_milestone_ids": [13, 14],
                "frontier_ids": [13, 14],
                "active_run": {
                    "run_id": "run-live-2",
                    "frontier_ids": [13, 14],
                    "open_milestone_ids": [13, 14],
                },
            },
        )
        (aggregate_root / "active_shards.json").write_text(
            json.dumps(
                {
                    "active_shards": [
                        {"name": "shard-1", "frontier_ids": [1, 2, 3]},
                        {"name": "shard-2", "frontier_ids": [13, 14]},
                    ]
                }
            ),
            encoding="utf-8",
        )

        state, _history = module._effective_supervisor_state(aggregate_root, history_limit=10)

        assert state["eta"]["remaining_open_milestones"] == 5
        assert state["eta"]["remaining_in_progress_milestones"] == 5
        assert state["eta"]["remaining_not_started_milestones"] == 0
        assert "5 open milestones remain (5 in progress, 0 not started)" in state["eta"]["summary"]


def test_reconcile_aggregate_shard_truth_updates_eta_and_blockers() -> None:
    module = _load_module()

    updated = module._reconcile_aggregate_shard_truth(
        {
            "open_milestone_ids": [1, 2, 3, 13],
            "eta": {
                "status": "estimated",
                "eta_human": "4.5d-1.7w",
                "eta_confidence": "low",
                "basis": "heuristic_status_mix",
                "summary": "4 open milestones remain (0 in progress, 4 not started); range is a fallback heuristic from the current status mix.",
                "remaining_open_milestones": 4,
                "remaining_in_progress_milestones": 0,
                "remaining_not_started_milestones": 4,
                "blocking_reason": "",
            },
            "shards": [
                {
                    "name": "shard-1",
                    "frontier_ids": [1, 2, 3],
                    "active_frontier_ids": [1, 2, 3],
                    "last_run_id": "run-1",
                    "last_run_blocker": "concurrent local commits",
                },
                {
                    "name": "shard-2",
                    "frontier_ids": [13],
                    "active_frontier_ids": [13],
                    "last_run_id": "run-2",
                    "last_run_blocker": "",
                },
            ],
        }
    )

    assert updated["eta"]["remaining_open_milestones"] == 4
    assert updated["eta"]["remaining_in_progress_milestones"] == 4
    assert updated["eta"]["remaining_not_started_milestones"] == 0
    assert "4 open milestones remain (4 in progress, 0 not started)" in updated["eta"]["summary"]
    assert updated["eta"]["status"] == "blocked"
    assert updated["eta"]["eta_human"].endswith("after unblock")
    assert updated["eta"]["blocking_reason"] == "shard-1: concurrent local commits"
    assert updated["shard_blockers"] == [
        {"name": "shard-1", "run_id": "run-1", "blocker": "concurrent local commits"}
    ]


def test_run_supervisor_launcher_exits_loudly_when_frontier_probe_fails() -> None:
    launcher = Path("/docker/fleet/scripts/run_chummer_design_supervisor.sh")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        wrapper = root / "python3"
        wrapper.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env bash",
                    "set -euo pipefail",
                    "if [[ \"${1:-}\" == \"scripts/chummer_design_supervisor.py\" && \"${2:-}\" == \"status\" && \"${3:-}\" == \"--json\" ]]; then",
                    "  echo 'probe boom' >&2",
                    "  exit 17",
                    "fi",
                    "echo 'unexpected python3 invocation' >&2",
                    "exit 99",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        wrapper.chmod(0o755)
        result = subprocess.run(
            [str(launcher)],
            cwd="/docker/fleet",
            env={
                **os.environ,
                "PATH": f"{root}:{os.environ['PATH']}",
                "CHUMMER_DESIGN_SUPERVISOR_PARALLEL_SHARDS": "2",
                "CHUMMER_DESIGN_SUPERVISOR_STATE_ROOT": str(root / "state" / "chummer_design_supervisor"),
            },
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0
        assert "failed to derive frontier via status --json" in result.stderr


def test_derive_completion_review_context_can_focus_repo_backlog_items_beyond_first_five() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text("waves: []\nmilestones: []\n", encoding="utf-8")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        _write_completion_evidence(root)
        projects_dir = root / "projects"
        projects_dir.mkdir(parents=True, exist_ok=True)
        project_rows = [
            ("hub-registry", "chummer6-hub-registry", "Extract registry contracts"),
            ("hub-registry", "chummer6-hub-registry", "Move registry seam"),
            ("hub-registry", "chummer6-hub-registry", "Wire registry package boundaries"),
            ("ui-kit", "chummer6-ui-kit", "Seed token canon"),
            ("ui-kit", "chummer6-ui-kit", "Extract shell chrome"),
            ("ui", "chummer6-ui", "Publish and execute the ruleset-specific workbench adaptation lane"),
        ]
        grouped_rows: dict[str, tuple[str, list[str]]] = {}
        for project_id, repo_slug, task in project_rows:
            if project_id not in grouped_rows:
                grouped_rows[project_id] = (repo_slug, [])
            grouped_rows[project_id][1].append(task)
        for project_id, (repo_slug, tasks) in grouped_rows.items():
            project_root = root / repo_slug
            project_root.mkdir(parents=True, exist_ok=True)
            (project_root / "WORKLIST.md").write_text(
                "\n".join(f"- [queued] wl-{index + 1} {task}" for index, task in enumerate(tasks)) + "\n",
                encoding="utf-8",
            )
            (projects_dir / f"{project_id}.yaml").write_text(
                yaml.safe_dump(
                    {
                        "id": project_id,
                        "path": str(project_root),
                        "review": {"repo": repo_slug},
                        "queue": [],
                        "queue_sources": [{"kind": "worklist", "path": "WORKLIST.md", "mode": "replace"}],
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
        state_root = root / "state" / "chummer_design_supervisor" / "shard-2"
        state_root.mkdir(parents=True, exist_ok=True)
        args = _args(root)
        args.focus_owner = ["chummer6-core"]
        args.focus_text = ["workbench", "desktop", "sr4", "sr5", "sr6"]
        base_context = module.derive_context(args)
        audit = module._design_completion_audit(args, [])

        context = module.derive_completion_review_context(args, state_root, base_context=base_context, audit=audit)

        assert any("workbench adaptation lane" in item.title for item in context["frontier"])


def test_derive_completion_review_context_fair_shares_repo_backlog_across_three_shards() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text("waves: []\nmilestones: []\n", encoding="utf-8")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        _write_completion_evidence(root)
        projects_dir = root / "projects"
        projects_dir.mkdir(parents=True, exist_ok=True)
        project_rows = [
            ("hub-registry", "chummer6-hub-registry", "Extract registry contracts"),
            ("hub-registry", "chummer6-hub-registry", "Move registry seam"),
            ("hub-registry", "chummer6-hub-registry", "Wire registry package boundaries"),
            ("ui-kit", "chummer6-ui-kit", "Seed token canon"),
            ("ui-kit", "chummer6-ui-kit", "Extract shell chrome"),
            ("ui-kit", "chummer6-ui-kit", "Migrate package-only ui kit"),
            ("ui", "chummer6-ui", "Publish and execute the ruleset-specific workbench adaptation lane"),
        ]
        grouped_rows: dict[str, tuple[str, list[str]]] = {}
        for project_id, repo_slug, task in project_rows:
            if project_id not in grouped_rows:
                grouped_rows[project_id] = (repo_slug, [])
            grouped_rows[project_id][1].append(task)
        for project_id, (repo_slug, tasks) in grouped_rows.items():
            project_root = root / repo_slug
            project_root.mkdir(parents=True, exist_ok=True)
            (project_root / "WORKLIST.md").write_text(
                "\n".join(f"- [queued] wl-{index + 1} {task}" for index, task in enumerate(tasks)) + "\n",
                encoding="utf-8",
            )
            (projects_dir / f"{project_id}.yaml").write_text(
                yaml.safe_dump(
                    {
                        "id": project_id,
                        "path": str(project_root),
                        "review": {"repo": repo_slug},
                        "queue": [],
                        "queue_sources": [{"kind": "worklist", "path": "WORKLIST.md", "mode": "replace"}],
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
        aggregate_root = root / "state" / "chummer_design_supervisor"
        shard_one_root = aggregate_root / "shard-1"
        shard_two_root = aggregate_root / "shard-2"
        shard_three_root = aggregate_root / "shard-3"
        for shard_root in (shard_one_root, shard_two_root, shard_three_root):
            shard_root.mkdir(parents=True, exist_ok=True)

        registry_path = root / "registry.yaml"
        args_one = _args(root)
        args_one.focus_owner = ["chummer6-ui", "chummer6-ui-kit"]
        args_one.focus_text = ["desktop", "client", "workbench", "rules", "sr4", "sr5", "sr6"]
        audit = module._design_completion_audit(args_one, [])
        full_frontier_ids = [
            item.id for item in module._completion_review_frontier(audit, registry_path.resolve(), [])
        ]
        context_one = module.derive_completion_review_context(
            args_one,
            shard_one_root,
            base_context=module.derive_context(args_one),
            audit=audit,
        )
        assert len(context_one["frontier_ids"]) == 3
        module._write_json(
            shard_one_root / "state.json",
            {
                "updated_at": "2026-03-31T18:20:47Z",
                "mode": "completion_review",
                "frontier_ids": context_one["frontier_ids"],
                "active_run": {
                    "run_id": "run-1",
                    "frontier_ids": context_one["frontier_ids"],
                    "open_milestone_ids": [],
                },
            },
        )

        args_two = _args(root)
        args_two.focus_owner = ["chummer6-core"]
        args_two.focus_text = ["desktop", "client", "workbench", "rules", "sr4", "sr5", "sr6"]
        context_two = module.derive_completion_review_context(
            args_two,
            shard_two_root,
            base_context=module.derive_context(args_two),
            audit=audit,
        )
        assert len(context_two["frontier_ids"]) == 3
        module._write_json(
            shard_two_root / "state.json",
            {
                "updated_at": "2026-03-31T18:20:50Z",
                "mode": "completion_review",
                "frontier_ids": context_two["frontier_ids"],
                "active_run": {
                    "run_id": "run-2",
                    "frontier_ids": context_two["frontier_ids"],
                    "open_milestone_ids": [],
                },
            },
        )

        args_three = _args(root)
        args_three.focus_owner = ["chummer6-hub", "chummer6-hub-registry", "chummer6-design"]
        args_three.focus_text = ["registry", "contracts", "desktop", "client"]
        context_three = module.derive_completion_review_context(
            args_three,
            shard_three_root,
            base_context=module.derive_context(args_three),
            audit=audit,
        )

        combined_ids = context_one["frontier_ids"] + context_two["frontier_ids"] + context_three["frontier_ids"]
        assert len(context_three["frontier_ids"]) == 1
        assert sorted(combined_ids) == sorted(full_frontier_ids)
        assert len(set(combined_ids)) == len(full_frontier_ids)


def test_run_once_keeps_completion_review_when_local_shard_slice_is_empty() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text("waves: []\nmilestones: []\n", encoding="utf-8")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        _write_completion_evidence(root)
        task = "Publish and execute the ruleset-specific workbench adaptation lane"
        _write_project_backlog(root, project_id="ui", repo_slug="chummer6-ui", task=task)
        aggregate_root = root / "state" / "chummer_design_supervisor"
        shard_one_root = aggregate_root / "shard-1"
        shard_two_root = aggregate_root / "shard-2"
        shard_one_root.mkdir(parents=True, exist_ok=True)
        shard_two_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            shard_one_root / "state.json",
            {
                "updated_at": "2026-03-31T17:22:15Z",
                "mode": "completion_review",
                "frontier_ids": [],
                "active_run": {
                    "run_id": "run-1",
                    "frontier_ids": [
                        module._synthetic_completion_review_id(f"repo-backlog:ui:{task}"),
                    ],
                    "open_milestone_ids": [],
                },
            },
        )
        args = _args(root)
        args.state_root = str(shard_two_root)
        args.command = "once"
        prompts: list[str] = []

        def fake_run(command, *, input, text, capture_output, cwd, check, env=None):
            prompts.append(input)
            message_path = Path(command[command.index("-o") + 1])
            message_path.write_text(
                "What shipped: reinforced repo-backlog recovery while review work was already claimed\n"
                "What remains: repo-backlog recovery still needs the remaining frontier\n"
                "Exact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        original_run = module.subprocess.run
        module.subprocess.run = fake_run
        try:
            exit_code = module.run_once(args)
        finally:
            module.subprocess.run = original_run

        state_payload = json.loads((shard_two_root / "state.json").read_text(encoding="utf-8"))
        assert exit_code == 0
        assert prompts
        assert state_payload["mode"] == "completion_review"
        assert state_payload["frontier_ids"] == [
            module._synthetic_completion_review_id(f"repo-backlog:ui:{task}")
        ]
        assert state_payload["completion_audit"]["status"] == "fail"
        assert state_payload["eta"]["status"] == "recovery"


def test_live_state_with_open_milestones_clears_stale_shard_activity() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}],
                    "milestones": [
                        {
                            "id": 1,
                            "title": "Gold install lane",
                            "wave": "W1",
                            "status": "planned",
                            "owners": ["fleet", "chummer6-ui"],
                            "exit_criteria": ["Install lane is real."],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Gold install lane remains active.\n", encoding="utf-8")
        state_root = root / "state" / "chummer_design_supervisor"
        shard_root = state_root / "shard-1"
        shard_root.mkdir(parents=True, exist_ok=True)
        stale_frontier_id = module._synthetic_completion_review_id("repo-backlog:ui:stale")
        module._write_json(
            state_root / "state.json",
            {
                "updated_at": "2026-04-03T15:20:21Z",
                "mode": "sharded",
                "frontier_ids": [stale_frontier_id],
                "active_run": {
                    "run_id": "stale-run",
                    "frontier_ids": [stale_frontier_id],
                    "open_milestone_ids": [],
                },
            },
        )
        module._write_json(
            shard_root / "state.json",
            {
                "updated_at": "2026-04-03T15:20:21Z",
                "mode": "complete",
                "frontier_ids": [stale_frontier_id],
                "active_run": {
                    "run_id": "stale-shard-run",
                    "frontier_ids": [stale_frontier_id],
                    "open_milestone_ids": [],
                },
            },
        )
        args = _args(root)
        args.state_root = str(state_root)

        state, history = module._effective_supervisor_state(state_root, history_limit=module.ETA_HISTORY_LIMIT)
        updated, _ = module._live_state_with_current_completion_audit(args, state_root, state, history)

        assert updated["open_milestone_ids"] == [1]
        assert updated["frontier_ids"] == [1]
        assert "active_run" not in updated
        assert updated["mode"] == "loop"
        assert updated["shards"][0]["frontier_ids"] == [1]
        assert updated["shards"][0]["active_frontier_ids"] == []
        assert updated["shards"][0]["active_run_id"] == ""


def test_live_state_with_open_milestones_does_not_inherit_stale_focus_from_prior_wave() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}],
                    "milestones": [
                        {
                            "id": 1,
                            "title": "Gold install lane",
                            "wave": "W1",
                            "status": "planned",
                            "owners": ["fleet", "chummer6-ui"],
                            "exit_criteria": ["Install lane is real."],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Legacy desktop visual parity remains open.\n", encoding="utf-8")
        state_root = root / "state" / "chummer_design_supervisor"
        state_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            state_root / "state.json",
            {
                "updated_at": "2026-04-03T15:20:21Z",
                "mode": "completion_review",
                "frontier_ids": [99],
                "focus_profiles": ["desktop_visual_familiarity"],
                "focus_owners": ["chummer6-ui", "chummer6-ui-kit", "chummer6-design"],
                "focus_texts": ["palette", "tab", "shell", "legacy"],
            },
        )
        args = _args(root)
        args.state_root = str(state_root)

        state, history = module._effective_supervisor_state(state_root, history_limit=module.ETA_HISTORY_LIMIT)
        updated, _ = module._live_state_with_current_completion_audit(args, state_root, state, history)

        assert updated["mode"] == "loop"
        assert updated["open_milestone_ids"] == [1]
        assert updated["frontier_ids"] == [1]
        assert updated["focus_profiles"] == []
        assert updated["focus_owners"] == []
        assert updated["focus_texts"] == []


def test_derive_context_fair_shares_open_milestone_frontier_across_three_shards() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}],
                    "milestones": [
                        {
                            "id": milestone_id,
                            "title": f"Milestone {milestone_id}",
                            "wave": "W1",
                            "status": "planned",
                            "owners": ["fleet"],
                            "exit_criteria": [f"Milestone {milestone_id} ships."],
                        }
                        for milestone_id in range(1, 7)
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        aggregate_root = root / "state" / "chummer_design_supervisor"
        shard_one_root = aggregate_root / "shard-1"
        shard_two_root = aggregate_root / "shard-2"
        shard_three_root = aggregate_root / "shard-3"
        for shard_root in (shard_one_root, shard_two_root, shard_three_root):
            shard_root.mkdir(parents=True, exist_ok=True)

        args_one = _args(root)
        args_one.state_root = str(shard_one_root)
        args_two = _args(root)
        args_two.state_root = str(shard_two_root)
        args_three = _args(root)
        args_three.state_root = str(shard_three_root)

        context_one = module.derive_context(args_one)
        context_two = module.derive_context(args_two)
        context_three = module.derive_context(args_three)

        combined_ids = context_one["frontier_ids"] + context_two["frontier_ids"] + context_three["frontier_ids"]

        assert context_one["frontier_ids"] == [1, 2]
        assert context_two["frontier_ids"] == [3, 4]
        assert context_three["frontier_ids"] == [5]
        assert sorted(combined_ids) == [1, 2, 3, 4, 5]


def test_live_shard_summaries_fair_share_open_milestones_across_three_shards() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}],
                    "milestones": [
                        {
                            "id": milestone_id,
                            "title": f"Milestone {milestone_id}",
                            "wave": "W1",
                            "status": "planned",
                            "owners": ["fleet"],
                            "exit_criteria": [f"Milestone {milestone_id} ships."],
                        }
                        for milestone_id in range(1, 7)
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        aggregate_root = root / "state" / "chummer_design_supervisor"
        for shard_name in ("shard-1", "shard-2", "shard-3"):
            shard_root = aggregate_root / shard_name
            shard_root.mkdir(parents=True, exist_ok=True)
            module._write_json(
                shard_root / "state.json",
                {
                    "updated_at": "2026-04-03T15:20:21Z",
                    "mode": "loop",
                    "frontier_ids": [],
                    "open_milestone_ids": [1, 2, 3, 4, 5, 6],
                },
            )
        args = _args(root)
        args.state_root = str(aggregate_root)

        summaries = module._live_shard_summaries(args, aggregate_root)

        assert [item["frontier_ids"] for item in summaries] == [[1, 2], [3, 4], [5]]


def test_run_once_keeps_loop_when_open_wave_local_slice_is_empty(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}],
                    "milestones": [
                        {
                            "id": milestone_id,
                            "title": f"Milestone {milestone_id}",
                            "wave": "W1",
                            "status": "planned",
                            "owners": ["fleet"],
                            "exit_criteria": [f"Milestone {milestone_id} ships."],
                        }
                        for milestone_id in range(1, 3)
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        aggregate_root = root / "state" / "chummer_design_supervisor"
        for shard_name in ("shard-1", "shard-2", "shard-3"):
            (aggregate_root / shard_name).mkdir(parents=True, exist_ok=True)
        args = _args(root)
        args.state_root = str(aggregate_root / "shard-3")
        monkeypatch.setattr(module, "_refresh_flagship_product_readiness_artifact", lambda _args: None)

        exit_code = module.run_once(args)
        state_payload = json.loads((Path(args.state_root) / "state.json").read_text(encoding="utf-8"))

        assert exit_code == 0
        assert state_payload["mode"] == "loop"
        assert state_payload["open_milestone_ids"] == [1, 2]
        assert state_payload["frontier_ids"] == []
        assert "last_run" not in state_payload


def test_run_once_launches_completion_review_worker_when_repo_backlog_remains(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}],
                    "milestones": [
                        {
                            "id": 13,
                            "title": "Desktop package proof",
                            "wave": "W1",
                            "status": "complete",
                            "owners": ["chummer6-ui", "fleet"],
                            "exit_criteria": ["Desktop package ships."],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        _write_completion_evidence(root)
        task = "Finish ruleset-specific workbench adaptation lane"
        _write_project_backlog(root, project_id="ui", repo_slug="chummer6-ui", task=task)
        state_root = root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        (state_root / "history.jsonl").write_text(
            json.dumps(
                {
                    "run_id": "run-good",
                    "worker_exit_code": 0,
                    "accepted": True,
                    "acceptance_reason": "",
                    "shipped": "trusted receipt",
                    "remains": "none",
                    "blocker": "none",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        args = _args(root)
        prompts: list[str] = []

        def fake_run(command, *, input, text, capture_output, cwd, check, env=None):
            prompts.append(input)
            message_path = Path(command[command.index("-o") + 1])
            message_path.write_text(
                "What shipped: reopened backlog-derived milestone for real implementation\n"
                "What remains: ruleset-specific workbench adaptation lane still needs implementation\n"
                "Exact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        monkeypatch.setattr(module.subprocess, "run", fake_run)

        exit_code = module.run_once(args)
        synthetic_id = module._synthetic_completion_review_id(f"repo-backlog:ui:{task}")

        assert exit_code == 0
        assert prompts
        assert "Repo backlog: ui: Finish ruleset-specific workbench adaptation lane" in prompts[0]
        state_payload = json.loads((state_root / "state.json").read_text(encoding="utf-8"))
        assert state_payload["mode"] == "completion_review"
        assert state_payload["frontier_ids"] == [synthetic_id]
        assert state_payload["completion_audit"]["repo_backlog_audit"]["status"] == "fail"


def test_run_once_enters_flagship_product_when_registry_is_empty_but_flagship_readiness_is_missing(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}],
                    "milestones": [
                        {
                            "id": 13,
                            "title": "Desktop package proof",
                            "wave": "W1",
                            "status": "complete",
                            "owners": ["chummer6-ui", "fleet"],
                            "exit_criteria": ["Desktop package ships."],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        _write_completion_evidence(root)
        state_root = root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        (state_root / "history.jsonl").write_text(
            json.dumps(
                {
                    "run_id": "run-9",
                    "worker_exit_code": 0,
                    "primary_milestone_id": 13,
                    "frontier_ids": [13],
                    "final_message": "Error: upstream_timeout:300s\n",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        args = _args(root)
        prompts: list[str] = []

        def fake_run(command, *, input, text, capture_output, cwd, check, env=None):
            prompts.append(input)
            message_path = Path(command[command.index("-o") + 1])
            message_path.write_text(
                "What shipped: reopened milestone 13 for real verification\n"
                "What remains: implementation still needs to continue from milestone 13\n"
                "Exact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        monkeypatch.setattr(module.subprocess, "run", fake_run)

        exit_code = module.run_once(args)

        assert exit_code == 0
        assert prompts
        assert "Run the flagship full-product delivery pass for Chummer." in prompts[0]
        state_payload = json.loads((state_root / "state.json").read_text(encoding="utf-8"))
        assert state_payload["mode"] == "flagship_product"
        assert state_payload["frontier_ids"]
        assert state_payload["completion_audit"]["status"] == "pass"
        assert state_payload["completion_audit"]["receipt_audit"]["synthetic"] is True
        assert state_payload["full_product_audit"]["status"] == "fail"
        assert state_payload["eta"]["status"] == "blocked"
        assert "full_product_frontier_heuristic" in state_payload["eta"]["basis"]


def test_run_once_reinforces_repo_backlog_slice_when_completion_review_slice_is_already_claimed(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}],
                    "milestones": [
                        {
                            "id": 13,
                            "title": "Desktop package proof",
                            "wave": "W1",
                            "status": "complete",
                            "owners": ["chummer6-ui", "fleet"],
                            "exit_criteria": ["Desktop package ships."],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        _write_completion_evidence(root)
        task = "Finish ruleset-specific workbench adaptation lane"
        _write_project_backlog(root, project_id="ui", repo_slug="chummer6-ui", task=task)
        aggregate_root = root / "state" / "chummer_design_supervisor"
        shard_1 = aggregate_root / "shard-1"
        shard_2 = aggregate_root / "shard-2"
        shard_1.mkdir(parents=True, exist_ok=True)
        shard_2.mkdir(parents=True, exist_ok=True)
        synthetic_id = module._synthetic_completion_review_id(f"repo-backlog:ui:{task}")
        module._write_json(
            shard_1 / "state.json",
            {
                "updated_at": "2026-03-31T08:00:00Z",
                "mode": "completion_review",
                "frontier_ids": [synthetic_id],
                "active_run": {
                    "run_id": "active-1",
                    "frontier_ids": [synthetic_id],
                    "open_milestone_ids": [],
                },
            },
        )
        args = _args(root)
        args.state_root = str(shard_2)
        args.focus_owner = ["chummer6-core"]
        prompts: list[str] = []

        def fake_run(command, *, input, text, capture_output, cwd, check, env=None):
            prompts.append(input)
            message_path = Path(command[command.index("-o") + 1])
            message_path.write_text(
                "What shipped: reinforced repo-backlog recovery slice in parallel\n"
                "What remains: completion review still needs the rest of the repo backlog frontier\n"
                "Exact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        monkeypatch.setattr(module.subprocess, "run", fake_run)

        exit_code = module.run_once(args)

        assert exit_code == 0
        assert prompts
        assert "Run a false-complete recovery pass for the Chummer design supervisor." in prompts[0]
        state_payload = json.loads((shard_2 / "state.json").read_text(encoding="utf-8"))
        assert state_payload["mode"] == "completion_review"
        assert state_payload["frontier_ids"] == [synthetic_id]
        assert state_payload["completion_audit"]["status"] == "fail"
        assert state_payload["eta"]["status"] == "recovery"


def test_run_once_launches_completion_review_worker_when_release_proof_is_not_ready(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}],
                    "milestones": [
                        {
                            "id": 13,
                            "title": "Desktop package proof",
                            "wave": "W1",
                            "status": "complete",
                            "owners": ["chummer6-ui", "fleet"],
                            "exit_criteria": ["Desktop package ships."],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        _write_completion_evidence(root, ui_posture="protected_preview")
        state_root = root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        (state_root / "history.jsonl").write_text(
            json.dumps(
                {
                    "run_id": "run-9",
                    "worker_exit_code": 0,
                    "accepted": True,
                    "acceptance_reason": "",
                    "primary_milestone_id": 13,
                    "frontier_ids": [13],
                    "shipped": "trusted receipt",
                    "remains": "none",
                    "blocker": "none",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        args = _args(root)
        prompts: list[str] = []

        def fake_run(command, *, input, text, capture_output, cwd, check, env=None):
            prompts.append(input)
            message_path = Path(command[command.index("-o") + 1])
            message_path.write_text(
                "What shipped: reopened release proof\n"
                "What remains: public promotion proof still needs work\n"
                "Exact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        monkeypatch.setattr(module.subprocess, "run", fake_run)

        exit_code = module.run_once(args)

        assert exit_code == 0
        assert prompts
        assert "Golden journey release-proof gaps" in prompts[0]
        assert "desktop_release_truth" in prompts[0]
        state_payload = json.loads((state_root / "state.json").read_text(encoding="utf-8"))
        assert state_payload["mode"] == "completion_review"
        assert state_payload["completion_audit"]["journey_gate_audit"]["status"] == "fail"
        assert state_payload["frontier_ids"]


def test_run_once_launches_completion_review_worker_when_linux_exit_gate_is_missing(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}],
                    "milestones": [
                        {
                            "id": 13,
                            "title": "Desktop package proof",
                            "wave": "W1",
                            "status": "complete",
                            "owners": ["chummer6-ui", "fleet"],
                            "exit_criteria": ["Desktop package ships."],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        _write_completion_evidence(root, write_linux_desktop_exit_gate=False)
        state_root = root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        (state_root / "history.jsonl").write_text(
            json.dumps(
                {
                    "run_id": "run-10",
                    "worker_exit_code": 0,
                    "accepted": True,
                    "acceptance_reason": "",
                    "primary_milestone_id": 13,
                    "frontier_ids": [13],
                    "shipped": "trusted receipt",
                    "remains": "none",
                    "blocker": "none",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        args = _args(root)
        prompts: list[str] = []

        def fake_run(command, *, input, text, capture_output, cwd, check, env=None):
            prompts.append(input)
            message_path = Path(command[command.index("-o") + 1])
            message_path.write_text(
                "What shipped: reopened linux desktop exit gate\n"
                "What remains: linux package proof still needs work\n"
                "Exact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        monkeypatch.setattr(module.subprocess, "run", fake_run)

        exit_code = module.run_once(args)

        assert exit_code == 0
        assert prompts
        assert "Linux desktop exit-gate gaps" in prompts[0]
        assert "linux desktop binary build/start/test proof is missing" in prompts[0]
        state_payload = json.loads((state_root / "state.json").read_text(encoding="utf-8"))
        assert state_payload["mode"] == "completion_review"
        assert state_payload["completion_audit"]["linux_desktop_exit_gate_audit"]["status"] == "fail"
        assert state_payload["frontier_ids"]


def test_run_once_launches_completion_review_worker_when_linux_exit_gate_is_stale(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}],
                    "milestones": [
                        {
                            "id": 13,
                            "title": "Desktop package proof",
                            "wave": "W1",
                            "status": "complete",
                            "owners": ["chummer6-ui", "fleet"],
                            "exit_criteria": ["Desktop package ships."],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        stale_text = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=2)).replace(microsecond=0).isoformat().replace(
            "+00:00", "Z"
        )
        _write_completion_evidence(root, linux_desktop_exit_gate_generated_at=stale_text)
        state_root = root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        (state_root / "history.jsonl").write_text(
            json.dumps(
                {
                    "run_id": "run-11",
                    "worker_exit_code": 0,
                    "accepted": True,
                    "acceptance_reason": "",
                    "primary_milestone_id": 13,
                    "frontier_ids": [13],
                    "shipped": "trusted receipt",
                    "remains": "none",
                    "blocker": "none",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        args = _args(root)
        prompts: list[str] = []

        def fake_run(command, *, input, text, capture_output, cwd, check, env=None):
            prompts.append(input)
            message_path = Path(command[command.index("-o") + 1])
            message_path.write_text(
                "What shipped: reopened stale linux exit gate\n"
                "What remains: rebuild fresh linux proof\n"
                "Exact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        monkeypatch.setattr(module.subprocess, "run", fake_run)

        exit_code = module.run_once(args)

        assert exit_code == 0
        assert prompts
        assert "linux desktop exit gate proof is stale" in prompts[0]
        state_payload = json.loads((state_root / "state.json").read_text(encoding="utf-8"))
        assert state_payload["mode"] == "completion_review"
        assert state_payload["completion_audit"]["linux_desktop_exit_gate_audit"]["status"] == "fail"


def test_run_once_launches_completion_review_worker_when_linux_exit_gate_targets_wrong_head(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}],
                    "milestones": [
                        {
                            "id": 13,
                            "title": "Desktop package proof",
                            "wave": "W1",
                            "status": "complete",
                            "owners": ["chummer6-ui", "fleet"],
                            "exit_criteria": ["Desktop package ships."],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        _write_completion_evidence(
            root,
            linux_desktop_exit_gate_app_key="blazor-desktop",
            linux_desktop_exit_gate_launch_target="Chummer.Blazor.Desktop",
        )
        state_root = root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        (state_root / "history.jsonl").write_text(
            json.dumps(
                {
                    "run_id": "run-12",
                    "worker_exit_code": 0,
                    "accepted": True,
                    "acceptance_reason": "",
                    "primary_milestone_id": 13,
                    "frontier_ids": [13],
                    "shipped": "trusted receipt",
                    "remains": "none",
                    "blocker": "none",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        args = _args(root)
        prompts: list[str] = []

        def fake_run(command, *, input, text, capture_output, cwd, check, env=None):
            prompts.append(input)
            message_path = Path(command[command.index("-o") + 1])
            message_path.write_text(
                "What shipped: reopened wrong-head linux exit gate\n"
                "What remains: rebuild avalonia linux proof\n"
                "Exact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        monkeypatch.setattr(module.subprocess, "run", fake_run)

        exit_code = module.run_once(args)

        assert exit_code == 0
        assert prompts
        assert "flagship Avalonia head" in prompts[0]
        state_payload = json.loads((state_root / "state.json").read_text(encoding="utf-8"))
        assert state_payload["mode"] == "completion_review"
        assert state_payload["completion_audit"]["linux_desktop_exit_gate_audit"]["status"] == "fail"


def test_run_once_marks_complete_when_release_proof_is_ready() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}],
                    "milestones": [
                        {
                            "id": 13,
                            "title": "Desktop package proof",
                            "wave": "W1",
                            "status": "complete",
                            "owners": ["chummer6-ui", "fleet"],
                            "exit_criteria": ["Desktop package ships."],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        _write_completion_evidence(root)
        _write_flagship_product_readiness(root)
        state_root = root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        (state_root / "history.jsonl").write_text(
            json.dumps(
                {
                    "run_id": "run-9",
                    "worker_exit_code": 0,
                    "accepted": True,
                    "acceptance_reason": "",
                    "primary_milestone_id": 13,
                    "frontier_ids": [13],
                    "shipped": "trusted receipt",
                    "remains": "none",
                    "blocker": "none",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        args = _args(root)

        exit_code = module.run_once(args)

        assert exit_code == 0
        state_payload = json.loads((state_root / "state.json").read_text(encoding="utf-8"))
        assert state_payload["mode"] == "complete"
        assert state_payload["eta"]["status"] == "ready"
        assert state_payload["eta"]["eta_human"] == "ready now"
        assert state_payload["completion_audit"]["status"] == "pass"
        assert state_payload["full_product_audit"]["status"] == "pass"
        assert state_payload["completion_audit"]["journey_gate_audit"]["status"] == "pass"
        assert state_payload["completion_audit"]["linux_desktop_exit_gate_audit"]["status"] == "pass"
        assert state_payload["completion_audit"]["weekly_pulse_audit"]["status"] == "pass"
        assert state_payload["completion_review_frontier_path"].endswith(
            "COMPLETION_REVIEW_FRONTIER.generated.yaml"
        )
        completion_frontier_payload = yaml.safe_load(
            Path(state_payload["completion_review_frontier_path"]).read_text(encoding="utf-8")
        )
        assert completion_frontier_payload["mode"] == "complete"
        assert completion_frontier_payload["completion_audit"]["status"] == "pass"
        assert completion_frontier_payload["frontier_count"] == 0


def test_linux_desktop_exit_gate_audit_allows_git_head_mismatch_when_worktree_fingerprint_is_identical() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "codex@example.com"], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Codex"], cwd=root, check=True, capture_output=True)
        (root / "tracked.txt").write_text("one\n", encoding="utf-8")
        subprocess.run(["git", "add", "tracked.txt"], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=root, check=True, capture_output=True)

        _write_completion_evidence(root)
        proof_path = root / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
        payload = json.loads(proof_path.read_text(encoding="utf-8"))
        current_state = module._repo_git_state(
            root,
            exclude_paths=(
                root / ".codex-studio" / "out" / "linux-desktop-exit-gate",
                proof_path,
            ),
            include_markers=module.FLAGSHIP_UI_LINUX_GATE_INPUT_MARKERS,
            include_untracked=False,
        )
        payload["git"] = {
            "repo_root": str(root),
            "available": True,
            "head": "deadbeef",
            "tracked_diff_sha256": current_state["tracked_diff_sha256"],
            "tracked_diff_line_count": current_state["tracked_diff_line_count"],
            "start": {
                "repo_root": str(root),
                "available": True,
                "head": "deadbeef",
                "tracked_diff_sha256": current_state["tracked_diff_sha256"],
                "tracked_diff_line_count": current_state["tracked_diff_line_count"],
            },
            "finish": {
                "repo_root": str(root),
                "available": True,
                "head": "deadbeef",
                "tracked_diff_sha256": current_state["tracked_diff_sha256"],
                "tracked_diff_line_count": current_state["tracked_diff_line_count"],
            },
            "identity_stable": True,
        }
        payload["source_snapshot"]["worktree_sha256"] = current_state["tracked_diff_sha256"]
        payload["source_snapshot"]["finish_worktree_sha256"] = current_state["tracked_diff_sha256"]
        payload["source_snapshot"]["entry_count"] = current_state["tracked_diff_line_count"]
        payload["source_snapshot"]["finish_entry_count"] = current_state["tracked_diff_line_count"]
        proof_path.write_text(json.dumps(payload), encoding="utf-8")

        audit = module._linux_desktop_exit_gate_audit(_args(root))

        assert audit["status"] == "pass"
        assert audit["proof_git_head_matches_current"] is False


def test_exit_gate_audits_preserve_configured_symlink_paths() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root)
        alias_root = root / "aliases"
        alias_root.mkdir(parents=True, exist_ok=True)
        linux_alias = alias_root / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
        linux_alias.symlink_to(root / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json")
        executable_alias = alias_root / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
        executable_alias.symlink_to(root / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json")

        args = _args(root)
        args.ui_linux_desktop_exit_gate_path = str(linux_alias)
        args.ui_executable_exit_gate_path = str(executable_alias)

        linux_audit = module._linux_desktop_exit_gate_audit(args)
        executable_audit = module._desktop_executable_exit_gate_audit(args)

        assert linux_audit["status"] == "pass"
        assert linux_audit["path"] == str(linux_alias)
        assert executable_audit["status"] == "pass"
        assert executable_audit["path"] == str(executable_alias)


def test_linux_desktop_exit_gate_audit_uses_top_level_current_git_fields_without_rejecting_stable_proof() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "codex@example.com"], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Codex"], cwd=root, check=True, capture_output=True)
        (root / "tracked.txt").write_text("one\n", encoding="utf-8")
        subprocess.run(["git", "add", "tracked.txt"], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=root, check=True, capture_output=True)

        _write_completion_evidence(root)
        proof_path = root / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
        payload = json.loads(proof_path.read_text(encoding="utf-8"))
        current_state = module._repo_git_state(
            root,
            exclude_paths=(
                root / ".codex-studio" / "out" / "linux-desktop-exit-gate",
                proof_path,
            ),
            include_markers=module.FLAGSHIP_UI_LINUX_GATE_INPUT_MARKERS,
            include_untracked=False,
        )
        payload["git"] = {
            "repo_root": str(root),
            "available": True,
            "head": current_state["head"],
            "tracked_diff_sha256": current_state["tracked_diff_sha256"],
            "tracked_diff_line_count": current_state["tracked_diff_line_count"],
            "start": dict(current_state),
            "finish": dict(current_state),
            "identity_stable": True,
        }
        payload["source_snapshot"]["worktree_sha256"] = current_state["tracked_diff_sha256"]
        payload["source_snapshot"]["finish_worktree_sha256"] = current_state["tracked_diff_sha256"]
        payload["source_snapshot"]["entry_count"] = current_state["tracked_diff_line_count"]
        payload["source_snapshot"]["finish_entry_count"] = current_state["tracked_diff_line_count"]
        payload["current_git_available"] = True
        payload["current_git_head"] = current_state["head"]
        payload["current_tracked_diff_sha256"] = "f" * 64
        proof_path.write_text(json.dumps(payload), encoding="utf-8")

        audit = module._linux_desktop_exit_gate_audit(_args(root))

        assert audit["status"] == "pass"
        assert audit["proof_git_head_matches_current"] is True
        assert audit["current_tracked_diff_sha256"] == "f" * 64
        assert audit["proof_tracked_diff_sha256"] == current_state["tracked_diff_sha256"]


def test_linux_desktop_exit_gate_audit_ignores_unrelated_repo_changes() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "codex@example.com"], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Codex"], cwd=root, check=True, capture_output=True)
        (root / "Chummer.Avalonia").mkdir(parents=True, exist_ok=True)
        (root / "Chummer.Presentation").mkdir(parents=True, exist_ok=True)
        (root / "docs").mkdir(parents=True, exist_ok=True)
        (root / "Chummer.Avalonia" / "Chummer.Avalonia.csproj").write_text("<Project />\n", encoding="utf-8")
        (root / "Chummer.Presentation" / "Surface.cs").write_text("namespace Chummer.Presentation;\n", encoding="utf-8")
        (root / "docs" / "notes.md").write_text("baseline\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=root, check=True, capture_output=True)

        _write_completion_evidence(root)
        proof_path = root / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
        payload = json.loads(proof_path.read_text(encoding="utf-8"))
        scoped_state = module._repo_git_state(
            root,
            exclude_paths=(
                root / ".codex-studio" / "out" / "linux-desktop-exit-gate",
                proof_path,
            ),
            include_markers=module.FLAGSHIP_UI_LINUX_GATE_INPUT_MARKERS,
        )
        payload["git"] = {
            "repo_root": str(root),
            "available": True,
            "head": scoped_state["head"],
            "tracked_diff_sha256": scoped_state["tracked_diff_sha256"],
            "tracked_diff_line_count": scoped_state["tracked_diff_line_count"],
            "start": dict(scoped_state),
            "finish": dict(scoped_state),
            "identity_stable": True,
        }
        payload["source_snapshot"] = {
            "mode": "filesystem_copy",
            "repo_root": str(root),
            "snapshot_root": str(root / ".linux-desktop-exit-gate-source.fixture"),
            "entry_count": scoped_state["tracked_diff_line_count"],
            "worktree_sha256": scoped_state["tracked_diff_sha256"],
            "finish_entry_count": scoped_state["tracked_diff_line_count"],
            "finish_worktree_sha256": scoped_state["tracked_diff_sha256"],
            "identity_stable": True,
        }
        proof_path.write_text(json.dumps(payload), encoding="utf-8")

        (root / "docs" / "notes.md").write_text("baseline\nchanged\n", encoding="utf-8")

        audit = module._linux_desktop_exit_gate_audit(_args(root))

        assert audit["status"] == "pass"


def test_linux_desktop_exit_gate_audit_rejects_wrong_unit_test_project() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root, linux_desktop_exit_gate_test_project_path="Chummer.Tests/Chummer.Tests.csproj")

        audit = module._linux_desktop_exit_gate_audit(_args(root))

        assert audit["status"] == "fail"
        assert "wrong unit-test project" in audit["reason"]


def test_linux_desktop_exit_gate_audit_rejects_wrong_unit_test_framework() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root)
        proof_path = root / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
        payload = json.loads(proof_path.read_text(encoding="utf-8"))
        payload["unit_tests"]["framework"] = "net9.0"
        proof_path.write_text(json.dumps(payload), encoding="utf-8")

        audit = module._linux_desktop_exit_gate_audit(_args(root))

        assert audit["status"] == "fail"
        assert "wrong unit-test target framework" in audit["reason"]


def test_linux_desktop_exit_gate_audit_rejects_missing_binary_on_disk() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root)
        (
            root
            / ".codex-studio"
            / "out"
            / "linux-desktop-exit-gate"
            / "run.fixture"
            / "publish"
            / "avalonia-linux-x64"
            / "Chummer.Avalonia"
        ).unlink()

        audit = module._linux_desktop_exit_gate_audit(_args(root))

        assert audit["status"] == "fail"
        assert "built Linux desktop binary" in audit["reason"]


def test_linux_desktop_exit_gate_audit_rejects_missing_deb_install_verification() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root)
        receipt_path = (
            root
            / ".codex-studio"
            / "out"
            / "linux-desktop-exit-gate"
            / "run.fixture"
            / "startup-smoke-installer"
            / "startup-smoke-avalonia-linux-x64.receipt.json"
        )
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
        payload.pop("artifactInstallVerificationPath", None)
        receipt_path.write_text(json.dumps(payload), encoding="utf-8")

        audit = module._linux_desktop_exit_gate_audit(_args(root))

        assert audit["status"] == "fail"
        assert "primary .deb install/remove verification is missing" in audit["reason"]


def test_linux_desktop_exit_gate_audit_rejects_invalid_deb_install_verification_log() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root)
        verification_path = (
            root
            / ".codex-studio"
            / "out"
            / "linux-desktop-exit-gate"
            / "run.fixture"
            / "startup-smoke-installer"
            / "install-verification-avalonia-linux-x64.json"
        )
        payload = json.loads(verification_path.read_text(encoding="utf-8"))
        payload["dpkgLogPath"] = str(root / "outside.log")
        verification_path.write_text(json.dumps(payload), encoding="utf-8")

        audit = module._linux_desktop_exit_gate_audit(_args(root))

        assert audit["status"] == "fail"
        assert "primary .deb install/remove verification is invalid" in audit["reason"]


def test_linux_desktop_exit_gate_audit_rejects_receipt_digest_mismatch() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root)
        receipt_path = (
            root
            / ".codex-studio"
            / "out"
            / "linux-desktop-exit-gate"
            / "run.fixture"
            / "startup-smoke-installer"
            / "startup-smoke-avalonia-linux-x64.receipt.json"
        )
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
        payload["artifactDigest"] = "sha256:" + ("0" * 64)
        receipt_path.write_text(json.dumps(payload), encoding="utf-8")

        audit = module._linux_desktop_exit_gate_audit(_args(root))

        assert audit["status"] == "fail"
        assert "primary startup smoke is invalid" in audit["reason"]


def test_linux_desktop_exit_gate_audit_accepts_release_channel_promoted_receipt_digest() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root)
        proof_path = root / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
        receipt_path = (
            root
            / ".codex-studio"
            / "out"
            / "linux-desktop-exit-gate"
            / "run.fixture"
            / "startup-smoke-installer"
            / "startup-smoke-avalonia-linux-x64.receipt.json"
        )

        promoted_digest = "a" * 64
        receipt_payload = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt_payload["artifactDigest"] = f"sha256:{promoted_digest}"
        receipt_path.write_text(json.dumps(receipt_payload), encoding="utf-8")

        proof_payload = json.loads(proof_path.read_text(encoding="utf-8"))
        proof_payload.setdefault("checks", {})
        proof_payload["checks"]["release_channel_linux_artifact"] = {
            "sha256": promoted_digest
        }
        proof_path.write_text(json.dumps(proof_payload), encoding="utf-8")

        audit = module._linux_desktop_exit_gate_audit(_args(root))

        assert audit["status"] == "pass"
        assert audit["primary_smoke_status"] == "passed"


def test_linux_desktop_exit_gate_audit_rejects_wrong_unit_test_assembly() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root, linux_desktop_exit_gate_test_assembly_name="Some.Other.Tests.dll")

        audit = module._linux_desktop_exit_gate_audit(_args(root))

        assert audit["status"] == "fail"
        assert "wrong unit-test assembly" in audit["reason"] or "unit-test status is invalid" in audit["reason"]


def test_linux_desktop_exit_gate_audit_rejects_run_root_escape() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root)
        proof_path = root / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
        payload = json.loads(proof_path.read_text(encoding="utf-8"))
        escaped_run_root = root / "escaped-run"
        escaped_run_root.mkdir(parents=True, exist_ok=True)
        payload["run_root"] = str(escaped_run_root)
        proof_path.write_text(json.dumps(payload), encoding="utf-8")

        audit = module._linux_desktop_exit_gate_audit(_args(root))

        assert audit["status"] == "fail"
        assert "outside the canonical output root" in audit["reason"]


def test_linux_desktop_exit_gate_audit_rejects_repo_mutation_during_run() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "codex@example.com"], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Codex"], cwd=root, check=True, capture_output=True)
        (root / "tracked.txt").write_text("one\n", encoding="utf-8")
        subprocess.run(["git", "add", "tracked.txt"], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=root, check=True, capture_output=True)

        _write_completion_evidence(root)
        proof_path = root / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
        payload = json.loads(proof_path.read_text(encoding="utf-8"))
        payload["git"]["start"]["tracked_diff_sha256"] = "deadbeef"
        payload["git"]["identity_stable"] = False
        proof_path.write_text(json.dumps(payload), encoding="utf-8")

        audit = module._linux_desktop_exit_gate_audit(_args(root))

        assert audit["status"] == "fail"
        assert "repo changed while the proof run was executing" in audit["reason"]


def test_linux_desktop_exit_gate_audit_rejects_missing_source_snapshot() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root)
        proof_path = root / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
        payload = json.loads(proof_path.read_text(encoding="utf-8"))
        payload.pop("source_snapshot", None)
        proof_path.write_text(json.dumps(payload), encoding="utf-8")

        audit = module._linux_desktop_exit_gate_audit(_args(root))

        assert audit["status"] == "fail"
        assert "immutable source-snapshot metadata" in audit["reason"]


def test_linux_desktop_exit_gate_audit_rejects_unstable_source_snapshot() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root)
        proof_path = root / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
        payload = json.loads(proof_path.read_text(encoding="utf-8"))
        payload["source_snapshot"]["finish_worktree_sha256"] = "deadbeef"
        payload["source_snapshot"]["finish_entry_count"] = payload["source_snapshot"]["entry_count"]
        payload["source_snapshot"]["identity_stable"] = False
        proof_path.write_text(json.dumps(payload), encoding="utf-8")

        audit = module._linux_desktop_exit_gate_audit(_args(root))

        assert audit["status"] == "fail"
        assert "did not stay stable through the full run" in audit["reason"]


def test_refresh_source_credential_state_clears_backoff_when_auth_changes() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        auth_path = root / "acct.auth.json"
        auth_path.write_text('{"access_token":"fresh"}\n', encoding="utf-8")
        account = module.WorkerAccount(
            alias="acct-archon-a",
            owner_id="archon.megalon",
            auth_kind="chatgpt_auth_json",
            auth_json_file=str(auth_path),
            api_key_env="",
            api_key_file="",
            allowed_models=[],
            health_state="ready",
            spark_enabled=True,
            bridge_priority=1,
            forced_login_method="",
            forced_chatgpt_workspace_id="",
            openai_base_url="",
            home_dir="",
        )
        until = module._utc_now() + module.dt.timedelta(hours=6)
        payload = {
            "sources": {
                module._credential_source_key(account): {
                    "alias": account.alias,
                    "owner_id": account.owner_id,
                    "source_key": module._credential_source_key(account),
                    "credential_fingerprint": "stale-fingerprint",
                    "backoff_until": module._iso(until),
                    "last_error": "chatgpt auth session is expired",
                }
            }
        }

        changed = module._refresh_source_credential_state(payload, account, root)

        assert changed is True
        item = payload["sources"][module._credential_source_key(account)]
        assert item["credential_fingerprint"] != "stale-fingerprint"
        assert item["backoff_until"] == ""
        assert item["last_error"] == ""


def test_render_trace_includes_recent_history_entries() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        state_root = root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        stderr_run_2 = state_root / "run-2.stderr.log"
        stderr_run_2.write_text(
            "worker boot\nERROR: You've hit your usage limit for GPT-5.3-Codex-Spark.\n",
            encoding="utf-8",
        )
        (state_root / "state.json").write_text(
            json.dumps(
                {
                    "updated_at": "2026-03-30T12:00:00Z",
                    "mode": "loop",
                    "open_milestone_ids": [3, 4, 5],
                    "frontier_ids": [3, 4, 5],
                    "last_run": {
                        "run_id": "run-3",
                        "worker_exit_code": 0,
                        "primary_milestone_id": 3,
                        "blocker": "",
                        "stderr_path": "",
                        "last_message_path": "/tmp/run-3.txt",
                    },
                }
            ),
            encoding="utf-8",
        )
        (state_root / "history.jsonl").write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "run_id": "run-1",
                            "finished_at": "2026-03-30T10:00:00Z",
                            "worker_exit_code": 0,
                            "primary_milestone_id": 6,
                            "frontier_ids": [6],
                            "shipped": "planner baseline",
                            "remains": "team optimizer",
                            "blocker": "",
                        }
                    ),
                    json.dumps(
                        {
                            "run_id": "run-2",
                            "finished_at": "2026-03-30T11:00:00Z",
                            "worker_exit_code": 1,
                            "primary_milestone_id": 4,
                            "frontier_ids": [4, 5],
                            "shipped": "",
                            "remains": "prep packets",
                            "blocker": "",
                            "stderr_path": str(stderr_run_2),
                        }
                    ),
                    json.dumps(
                        {
                            "run_id": "run-3",
                            "finished_at": "2026-03-30T12:00:00Z",
                            "worker_exit_code": 0,
                            "selected_account_alias": "acct-archon-a",
                            "primary_milestone_id": 3,
                            "frontier_ids": [3, 4, 5],
                            "shipped": "roster audit trail",
                            "remains": "travel prefetch",
                            "blocker": "",
                        }
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        history = module._read_history(state_root / "history.jsonl", limit=2)

        assert [row["run_id"] for row in history] == ["run-2", "run-3"]

        rendered = module._render_trace(
            module._read_state(state_root / "state.json"),
            history,
        )

        assert "run=run-3" in rendered
        assert "account=acct-archon-a" in rendered
        assert "frontier=3,4,5" in rendered
        assert "run=run-2" in rendered
        assert "hint=ERROR: You've hit your usage limit for GPT-5.3-Codex-Spark." in rendered
        assert "run=run-1" not in rendered


def test_render_status_includes_eta_fields() -> None:
    module = _load_module()

    rendered = module._render_status(
        {
            "updated_at": "2026-03-31T10:00:00Z",
            "mode": "loop",
            "open_milestone_ids": [6, 21],
            "frontier_ids": [6],
            "focus_profiles": ["desktop_client"],
            "focus_owners": ["chummer6-ui"],
            "focus_texts": ["desktop"],
            "eta": {
                "status": "estimated",
                "eta_human": "8-16h",
                "eta_confidence": "medium",
                "basis": "empirical_open_milestone_burn",
                "summary": "2 open milestones remain.",
                "predicted_completion_at": "2026-03-31T22:00:00Z",
                "blocking_reason": "",
            },
        }
    )

    assert "eta.status: estimated" in rendered
    assert "eta.human: 8-16h" in rendered
    assert "eta.confidence: medium" in rendered
    assert "eta.basis: empirical_open_milestone_burn" in rendered
    assert "eta.summary: 2 open milestones remain." in rendered


def test_render_status_includes_completion_review_frontier_and_backlog_fields() -> None:
    module = _load_module()

    rendered = module._render_status(
        {
            "updated_at": "2026-03-31T10:00:00Z",
            "mode": "completion_review",
            "open_milestone_ids": [],
            "frontier_ids": [1394756221],
            "completion_review_frontier_path": "/tmp/COMPLETION_REVIEW_FRONTIER.generated.yaml",
            "completion_review_frontier_mirror_path": "/tmp/.codex-design/product/COMPLETION_REVIEW_FRONTIER.generated.yaml",
            "completion_audit": {
                "status": "fail",
                "reason": "repo-local backlog audit failed",
                "repo_backlog_audit": {
                    "status": "fail",
                    "reason": "active repo-local backlog remains outside the closed design registry: ui",
                    "open_item_count": 1,
                    "open_project_count": 1,
                },
            },
        }
    )

    assert "completion_review_frontier.path: /tmp/COMPLETION_REVIEW_FRONTIER.generated.yaml" in rendered
    assert "completion_review_frontier.mirror_path: /tmp/.codex-design/product/COMPLETION_REVIEW_FRONTIER.generated.yaml" in rendered
    assert "completion_audit.repo_backlog_status: fail" in rendered
    assert "completion_audit.repo_backlog_open_item_count: 1" in rendered


def test_render_status_includes_worker_lane_health_fields() -> None:
    module = _load_module()

    rendered = module._render_status(
        {
            "updated_at": "2026-03-31T10:00:00Z",
            "mode": "completion_review",
            "open_milestone_ids": [],
            "frontier_ids": [1394756221],
            "worker_lane_health": {
                "status": "pass",
                "reason": "provider-health preflight marked repair unroutable",
                "fetched_at": "2026-03-31T10:00:05Z",
                "source_url": "http://127.0.0.1:8090/v1/responses/_provider_health",
                "routable_lanes": ["core", "survival"],
                "unroutable_lanes": ["repair"],
                "lanes": {
                    "core": {
                        "profile": "core_batch",
                        "state": "ready",
                        "routable": True,
                        "ready_slots": 47,
                        "remaining_percent_of_max": 0.05,
                        "reason": "onemin:ready",
                    },
                    "repair": {
                        "profile": "repair",
                        "state": "degraded",
                        "routable": False,
                        "ready_slots": 0,
                        "remaining_percent_of_max": None,
                        "reason": "magixai degraded with no ready slots",
                    },
                },
            },
        }
    )

    assert "worker_lane_health.status: pass" in rendered
    assert "worker_lane_health.routable_lanes: core, survival" in rendered
    assert "worker_lane_health.unroutable_lanes: repair" in rendered
    assert "worker_lane_health.repair: profile=repair state=degraded routable=no" in rendered


def test_render_status_includes_active_run_watchdog_timeout_seconds() -> None:
    module = _load_module()

    rendered = module._render_status(
        {
            "updated_at": "2026-03-31T10:00:00Z",
            "mode": "completion_review",
            "open_milestone_ids": [],
            "frontier_ids": [1394756221],
            "active_run": {
                "run_id": "run-1",
                "started_at": "2026-03-31T09:55:00Z",
                "selected_account_alias": "lane:core",
                "selected_model": "default",
                "attempt_index": 1,
                "total_attempts": 4,
                "primary_milestone_id": 1394756221,
                "last_message_path": "/tmp/last_message.txt",
                "watchdog_timeout_seconds": 21600.0,
            },
        }
    )

    assert "active_run.watchdog_timeout_seconds: 21600.0" in rendered


def test_effective_supervisor_state_merges_shard_state_and_history() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        state_root = root / "state"
        shard_1 = state_root / "shard-1"
        shard_2 = state_root / "shard-2"
        shard_1.mkdir(parents=True, exist_ok=True)
        shard_2.mkdir(parents=True, exist_ok=True)
        module._write_json(
            shard_1 / "state.json",
            {
                "updated_at": "2026-03-31T10:00:00Z",
                "mode": "completion_review",
                "open_milestone_ids": [],
                "frontier_ids": [13],
                "focus_owners": ["chummer6-ui"],
                "eta": {"status": "blocked"},
                "last_run": {
                    "run_id": "run-1",
                    "finished_at": "2026-03-31T10:00:00Z",
                    "worker_exit_code": 0,
                },
            },
        )
        module._write_json(
            shard_2 / "state.json",
            {
                "updated_at": "2026-03-31T10:05:00Z",
                "mode": "completion_review",
                "open_milestone_ids": [],
                "frontier_ids": [14],
                "focus_owners": ["chummer6-core"],
                "eta": {"status": "blocked"},
                "active_run": {
                    "run_id": "run-3",
                    "started_at": "2026-03-31T10:06:00Z",
                    "selected_account_alias": "lane:core",
                },
                "last_run": {
                    "run_id": "run-2",
                    "finished_at": "2026-03-31T10:05:00Z",
                    "worker_exit_code": 0,
                },
            },
        )
        module._append_jsonl(
            shard_1 / "history.jsonl",
            {
                "run_id": "run-1",
                "finished_at": "2026-03-31T10:00:00Z",
                "worker_exit_code": 0,
                "frontier_ids": [13],
            },
        )
        module._append_jsonl(
            shard_2 / "history.jsonl",
            {
                "run_id": "run-2",
                "finished_at": "2026-03-31T10:05:00Z",
                "worker_exit_code": 0,
                "frontier_ids": [14],
            },
        )

        state, history = module._effective_supervisor_state(state_root, history_limit=10)

        assert state["shard_count"] == 2
        assert state["frontier_ids"] == [13, 14]
        assert state["focus_owners"] == ["chummer6-core", "chummer6-ui"]
        assert state["last_run"]["run_id"] == "run-2"
        assert state["active_run"]["run_id"] == "run-3"
        assert state["shards"][1]["active_run_id"] == "run-3"
        assert [item["run_id"] for item in history] == ["run-1", "run-2"]
        assert history[-1]["_shard"] == "shard-2"


def test_render_status_and_trace_include_shard_metadata() -> None:
    module = _load_module()
    state = {
        "updated_at": "2026-03-31T10:05:00Z",
        "mode": "completion_review",
        "open_milestone_ids": [],
        "frontier_ids": [13, 14],
        "shards": [
            {
                "name": "shard-1",
                "updated_at": "2026-03-31T10:00:00Z",
                "mode": "completion_review",
                "open_milestone_ids": [],
                "frontier_ids": [13],
                "eta_status": "blocked",
                "last_run_id": "run-1",
                "active_run_id": "run-2",
            }
        ],
        "active_run": {
            "run_id": "run-2",
            "started_at": "2026-03-31T10:06:00Z",
            "selected_account_alias": "lane:core",
            "selected_model": "ea-coder-hard-batch",
            "attempt_index": 1,
            "total_attempts": 2,
            "primary_milestone_id": 13,
            "frontier_ids": [13],
            "last_message_path": "/tmp/run-2/last_message.txt",
        },
    }
    history = [
        {
            "run_id": "run-1",
            "_shard": "shard-1",
            "finished_at": "2026-03-31T10:00:00Z",
            "worker_exit_code": 0,
            "frontier_ids": [13],
            "selected_account_alias": "lane:core",
            "primary_milestone_id": 13,
            "accepted": False,
            "acceptance_reason": "Error: upstream_timeout:300s",
            "blocker": "",
            "shipped": "",
            "remains": "",
        }
    ]

    rendered_status = module._render_status(state)
    rendered_trace = module._render_trace(state, history)

    assert "shards: 1" in rendered_status
    assert "shard.shard-1:" in rendered_status
    assert "active_run.run_id: run-2" in rendered_status
    assert "active_run=run-2" in rendered_status
    assert "shard=shard-1" in rendered_trace
    assert "state=in_progress" in rendered_trace


def test_build_eta_snapshot_uses_empirical_burn_when_history_shows_open_count_closing() -> None:
    module = _load_module()
    open_milestones = [
        module.Milestone(6, "Build Lab progression planner", "W2", "in_progress", ["chummer6-ui"], ["Planner exists."], []),
        module.Milestone(21, "Rules Navigator v2", "W2", "not_started", ["chummer6-ui"], ["Rules differ."], [6]),
    ]
    history = [
        {
            "run_id": "run-1",
            "started_at": "2026-03-30T08:00:00Z",
            "finished_at": "2026-03-30T09:00:00Z",
            "worker_exit_code": 0,
            "accepted": True,
            "open_milestone_ids": [6, 15, 18, 19, 21],
        },
        {
            "run_id": "run-2",
            "started_at": "2026-03-30T15:00:00Z",
            "finished_at": "2026-03-30T16:00:00Z",
            "worker_exit_code": 0,
            "accepted": True,
            "open_milestone_ids": [6, 19, 21],
        },
    ]

    eta = module._build_eta_snapshot(
        mode="loop",
        open_milestones=open_milestones,
        frontier=open_milestones[:1],
        history=history,
        completion_audit=None,
        now=module._parse_iso("2026-03-30T20:00:00Z"),
    )

    assert eta["status"] == "estimated"
    assert eta["basis"] == "empirical_open_milestone_burn"
    assert eta["eta_confidence"] in {"medium", "high"}
    assert eta["remaining_open_milestones"] == 2
    assert eta["observed_burn_milestones_per_day"] > 0


def test_build_eta_snapshot_reports_blocked_on_external_worker_failure() -> None:
    module = _load_module()
    open_milestones = [
        module.Milestone(6, "Build Lab progression planner", "W2", "in_progress", ["chummer6-ui"], ["Planner exists."], []),
    ]
    history = [
        {
            "run_id": "run-1",
            "finished_at": "2026-03-31T08:00:00Z",
            "worker_exit_code": 1,
            "accepted": False,
            "acceptance_reason": "worker exit 1",
            "blocker": "",
            "stderr_path": "",
        }
    ]

    eta = module._build_eta_snapshot(
        mode="loop",
        open_milestones=open_milestones,
        frontier=open_milestones,
        history=history,
        completion_audit={"reason": "worker lane hit usage limit and needs refreshed quota"},
        now=module._parse_iso("2026-03-31T09:00:00Z"),
    )

    assert eta["status"] == "blocked"
    assert eta["eta_human"].endswith("after unblock")
    assert eta["eta_confidence"] in {"low", "medium"}
    assert "external_blocker" in eta["basis"]
    assert "usage limit" in eta["blocking_reason"].lower()
    assert eta["range_high_hours"] > 0


def test_build_eta_snapshot_reports_blocked_when_provider_health_leaves_no_routable_direct_lanes() -> None:
    module = _load_module()
    open_milestones = [
        module.Milestone(6, "Build Lab progression planner", "W2", "in_progress", ["chummer6-ui"], ["Planner exists."], []),
    ]

    eta = module._build_eta_snapshot(
        mode="loop",
        open_milestones=open_milestones,
        frontier=open_milestones,
        history=[],
        completion_audit=None,
        worker_lane_health={
            "status": "pass",
            "routable_lanes": [],
            "unroutable_lanes": ["core", "core_rescue"],
            "lanes": {
                "core": {
                    "routable": False,
                    "reason": "onemin quota exhausted",
                },
                "core_rescue": {
                    "routable": False,
                    "reason": "onemin quota exhausted",
                },
            },
        },
        now=module._parse_iso("2026-03-31T09:00:00Z"),
    )

    assert eta["status"] == "blocked"
    assert eta["eta_human"].endswith("after unblock")
    assert "provider-health preflight left no routable direct lanes" in eta["blocking_reason"]


def test_derive_eta_returns_completion_review_recovery_when_registry_is_closed_but_gate_is_stale() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}],
                    "milestones": [
                        {
                            "id": 13,
                            "title": "Linux desktop hard gate",
                            "wave": "W1",
                            "status": "complete",
                            "owners": ["chummer6-ui", "fleet"],
                            "exit_criteria": ["Done."],
                            "dependencies": [],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        _write_completion_evidence(
            root,
            linux_desktop_exit_gate_generated_at="2026-03-28T00:00:00Z",
        )
        state_root = root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        (state_root / "history.jsonl").write_text(
            json.dumps(
                {
                    "run_id": "run-eta-1",
                    "started_at": "2026-03-31T07:00:00Z",
                    "finished_at": "2026-03-31T08:00:00Z",
                    "worker_exit_code": 0,
                    "accepted": True,
                    "acceptance_reason": "",
                    "primary_milestone_id": 13,
                    "frontier_ids": [13],
                    "open_milestone_ids": [13],
                    "shipped": "desktop receipt",
                    "remains": "none",
                    "blocker": "none",
                }
            )
            + "\n",
            encoding="utf-8",
        )

        eta = module.derive_eta(_args(root))

        assert eta["status"] == "recovery"
        assert eta["basis"] == "completion_review_recovery"
        assert "Linux desktop exit gate" in eta["summary"]


def test_estimate_completion_review_eta_uses_decomposed_frontier_breakdown() -> None:
    module = _load_module()
    frontier = [
        module.Milestone(
            id=1394756221,
            title="Repo backlog: ui-kit: Seed Chummer.Ui.Kit with token canon, theme compilation, and preview/gallery ownership.",
            wave="completion_review",
            status="review_required",
            owners=["chummer6-ui-kit"],
            exit_criteria=["Seed token canon and preview/gallery ownership."],
            dependencies=[],
        ),
        module.Milestone(
            id=1873346391,
            title="Repo backlog: ui: Publish and execute the ruleset-specific workbench adaptation lane.",
            wave="completion_review",
            status="review_required",
            owners=["chummer6-ui"],
            exit_criteria=["Make SR4/SR5/SR6 posture explicit in the workbench."],
            dependencies=[],
        ),
    ]
    audit = {
        "status": "fail",
        "receipt_audit": {
            "status": "fail",
            "reason": "latest worker receipt is not trusted",
        },
        "repo_backlog_audit": {
            "status": "fail",
            "open_item_count": 3,
            "open_items": [
                {"project_id": "ui-kit", "repo_slug": "chummer6-ui-kit", "task": "Seed token canon"},
                {"project_id": "ui", "repo_slug": "chummer6-ui", "task": "Ruleset-specific workbench adaptation"},
                {"project_id": "hub-registry", "repo_slug": "chummer6-hub-registry", "task": "Wire registry package boundaries"},
            ],
        },
    }

    eta = module._estimate_completion_review_eta(
        frontier,
        audit,
        history=[],
        now=module._parse_iso("2026-03-31T09:00:00Z"),
    )

    assert eta["status"] == "recovery"
    assert eta["basis"] == "completion_review_recovery"
    assert eta["remaining_effort_units"] > 3.0
    assert "decomposed_frontier=2" in eta["summary"]
    assert "backlog_tail=1" in eta["summary"]
    components = [row["component"] for row in eta["remaining_effort_breakdown"]]
    assert components.count("repo_backlog_milestone") == 2
    assert "repo_backlog_tail" in components


def test_derive_eta_keeps_recovery_estimate_when_completion_review_is_blocked_by_upstream_timeout() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}],
                    "milestones": [
                        {
                            "id": 13,
                            "title": "Linux desktop hard gate",
                            "wave": "W1",
                            "status": "complete",
                            "owners": ["chummer6-ui", "fleet"],
                            "exit_criteria": ["Done."],
                            "dependencies": [],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        _write_completion_evidence(root, linux_desktop_exit_gate_generated_at="2026-03-28T00:00:00Z")
        state_root = root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        (state_root / "history.jsonl").write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "run_id": "run-good",
                            "started_at": "2026-03-31T06:00:00Z",
                            "finished_at": "2026-03-31T07:00:00Z",
                            "worker_exit_code": 0,
                            "accepted": True,
                            "acceptance_reason": "",
                            "primary_milestone_id": 13,
                            "frontier_ids": [13],
                            "open_milestone_ids": [13],
                            "shipped": "desktop receipt",
                            "remains": "none",
                            "blocker": "none",
                        }
                    ),
                    json.dumps(
                        {
                            "run_id": "run-bad",
                            "started_at": "2026-03-31T07:00:00Z",
                            "finished_at": "2026-03-31T08:00:00Z",
                            "worker_exit_code": 0,
                            "accepted": False,
                            "acceptance_reason": "Error: upstream_timeout:300s",
                            "primary_milestone_id": 13,
                            "frontier_ids": [13],
                            "open_milestone_ids": [],
                            "shipped": "",
                            "remains": "",
                            "blocker": "",
                        }
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        eta = module.derive_eta(_args(root))

        assert eta["status"] == "blocked"
        assert eta["eta_human"].endswith("after unblock")
        assert eta["range_high_hours"] > 0
        assert "completion_review_recovery" in eta["basis"]
        assert "upstream_timeout" in eta["blocking_reason"]


def test_derive_eta_reads_blocker_from_shard_history() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}],
                    "milestones": [
                        {
                            "id": 13,
                            "title": "Linux desktop hard gate",
                            "wave": "W1",
                            "status": "complete",
                            "owners": ["chummer6-ui", "fleet"],
                            "exit_criteria": ["Done."],
                            "dependencies": [],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        _write_completion_evidence(root, linux_desktop_exit_gate_generated_at="2026-03-28T00:00:00Z")
        shard_root = root / "state" / "shard-1"
        shard_root.mkdir(parents=True, exist_ok=True)
        (shard_root / "history.jsonl").write_text(
            json.dumps(
                {
                    "run_id": "run-bad",
                    "started_at": "2026-03-31T07:00:00Z",
                    "finished_at": "2026-03-31T08:00:00Z",
                    "worker_exit_code": 0,
                    "accepted": False,
                    "acceptance_reason": "Error: upstream_timeout:300s",
                    "primary_milestone_id": 13,
                    "frontier_ids": [13],
                    "open_milestone_ids": [],
                    "shipped": "",
                    "remains": "",
                    "blocker": "",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        module._write_json(
            shard_root / "state.json",
            {
                "updated_at": "2026-03-31T08:00:00Z",
                "mode": "completion_review",
                "open_milestone_ids": [],
                "frontier_ids": [13],
                "last_run": {"run_id": "run-bad", "finished_at": "2026-03-31T08:00:00Z"},
            },
        )

        eta = module.derive_eta(_args(root))

        assert eta["status"] == "blocked"
        assert eta["eta_human"].endswith("after unblock")
        assert "upstream_timeout" in eta["blocking_reason"]


def test_estimate_open_milestone_eta_ignores_non_wave_accepted_history() -> None:
    module = _load_module()
    now = dt.datetime(2026, 4, 3, 16, 0, tzinfo=dt.timezone.utc)
    open_milestones = [
        module.Milestone(
            id=1,
            title="Gold install lane",
            wave="W1",
            status="planned",
            owners=["fleet"],
            exit_criteria=["Install lane is real."],
            dependencies=[],
        )
    ]
    history = [
        {
            "accepted": True,
            "started_at": "2026-04-03T15:00:00Z",
            "finished_at": "2026-04-03T15:06:00Z",
            "open_milestone_ids": [],
        }
    ]

    eta = module._estimate_open_milestone_eta(open_milestones, history, now)

    assert eta["basis"] == "heuristic_status_mix"


def test_estimate_open_milestone_eta_requires_scope_coverage_for_widened_empirical_burn() -> None:
    module = _load_module()
    now = dt.datetime(2026, 4, 4, 16, 0, tzinfo=dt.timezone.utc)
    open_milestones = [
        module.Milestone(
            id=index,
            title=f"Milestone {index}",
            wave="W1",
            status="planned",
            owners=["fleet"],
            exit_criteria=["Done."],
            dependencies=[],
        )
        for index in range(1, 19)
    ]
    history = [
        {
            "accepted": True,
            "started_at": "2026-04-04T14:00:00Z",
            "finished_at": "2026-04-04T14:30:00Z",
            "open_milestone_ids": [13, 14, 17, 18],
        },
        {
            "accepted": True,
            "started_at": "2026-04-04T14:30:00Z",
            "finished_at": "2026-04-04T15:00:00Z",
            "open_milestone_ids": [13, 17, 18],
        },
        {
            "accepted": True,
            "started_at": "2026-04-04T15:00:00Z",
            "finished_at": "2026-04-04T15:30:00Z",
            "open_milestone_ids": [13, 18],
        },
    ]

    eta = module._estimate_open_milestone_eta(open_milestones, history, now)

    assert eta["basis"] == "heuristic_status_mix"
    assert eta["eta_confidence"] == "low"


def test_estimate_open_milestone_eta_rejects_shard_local_snapshot_scale_for_aggregate_wave() -> None:
    module = _load_module()
    now = dt.datetime(2026, 4, 4, 16, 0, tzinfo=dt.timezone.utc)
    open_milestones = [
        module.Milestone(
            id=index,
            title=f"Milestone {index}",
            wave="W1",
            status="planned",
            owners=["fleet"],
            exit_criteria=["Done."],
            dependencies=[],
        )
        for index in range(1, 19)
    ]
    history = [
        {
            "accepted": True,
            "started_at": "2026-04-04T14:00:00Z",
            "finished_at": "2026-04-04T14:30:00Z",
            "open_milestone_ids": [1, 2, 3, 4],
        },
        {
            "accepted": True,
            "started_at": "2026-04-04T14:30:00Z",
            "finished_at": "2026-04-04T15:00:00Z",
            "open_milestone_ids": [5, 6, 7, 8],
        },
        {
            "accepted": True,
            "started_at": "2026-04-04T15:00:00Z",
            "finished_at": "2026-04-04T15:30:00Z",
            "open_milestone_ids": [9, 10, 11, 12],
        },
        {
            "accepted": True,
            "started_at": "2026-04-04T15:30:00Z",
            "finished_at": "2026-04-04T15:45:00Z",
            "open_milestone_ids": [13, 14, 15],
        },
        {
            "accepted": True,
            "started_at": "2026-04-04T15:45:00Z",
            "finished_at": "2026-04-04T15:55:00Z",
            "open_milestone_ids": [16, 17],
        },
    ]

    eta = module._estimate_open_milestone_eta(open_milestones, history, now)

    assert eta["basis"] == "heuristic_status_mix"
    assert eta["eta_confidence"] == "low"


def test_failure_hint_recovers_timestamped_error_lines() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        stderr_path = root / "worker.stderr.log"
        stderr_path.write_text(
            "2026-03-30T20:45:03Z ERROR: Your access token could not be refreshed because your refresh token was already used.\n",
            encoding="utf-8",
        )

        hint = module._failure_hint_for_run({"stderr_path": str(stderr_path), "blocker": ""})

        assert hint.startswith("ERROR: Your access token could not be refreshed")


def test_acquire_lock_treats_reused_self_pid_without_start_ticks_as_stale() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        lock_path = root / "loop.lock"
        lock_path.write_text(
            json.dumps({"pid": os.getpid(), "created_at": module._utc_now().isoformat()}),
            encoding="utf-8",
        )

        module._acquire_lock(lock_path, ttl_seconds=300.0)

        payload = json.loads(lock_path.read_text(encoding="utf-8"))
        assert payload["pid"] == os.getpid()
        assert payload["proc_start_ticks"]
        module._release_lock(lock_path)


def test_failure_hint_maps_container_state_paths_back_to_workspace() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        previous_workspace_root = module.DEFAULT_WORKSPACE_ROOT
        try:
            module.DEFAULT_WORKSPACE_ROOT = root
            stderr_path = root / "state" / "chummer_design_supervisor" / "runs" / "run-1.stderr.log"
            stderr_path.parent.mkdir(parents=True, exist_ok=True)
            stderr_path.write_text(
                "[fleet-supervisor] no eligible worker account/model attempts were runnable\n",
                encoding="utf-8",
            )

            hint = module._failure_hint_for_run(
                {
                    "stderr_path": "/var/lib/codex-fleet/chummer_design_supervisor/runs/run-1.stderr.log",
                    "blocker": "",
                }
            )

            assert hint == "[fleet-supervisor] no eligible worker account/model attempts were runnable"
        finally:
            module.DEFAULT_WORKSPACE_ROOT = previous_workspace_root


def test_effective_supervisor_state_prefers_active_run_frontier_ids() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        aggregate_root = root / "state"
        shard_root = aggregate_root / "shard-1"
        shard_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            shard_root / "state.json",
            {
                "updated_at": "2026-03-31T17:22:15Z",
                "mode": "completion_review",
                "frontier_ids": [13],
                "open_milestone_ids": [],
                "active_run": {
                    "run_id": "run-1",
                    "frontier_ids": [21, 22],
                    "open_milestone_ids": [],
                },
            },
        )

        state, _history = module._effective_supervisor_state(aggregate_root, history_limit=10)

        assert state["frontier_ids"] == [21, 22]
        assert state["shards"][0]["frontier_ids"] == [21, 22]


def test_effective_supervisor_state_ignores_stale_base_active_run_when_shards_are_idle() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        aggregate_root = root / "state"
        shard_root = aggregate_root / "shard-1"
        shard_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            aggregate_root / "state.json",
            {
                "updated_at": "2026-03-31T17:30:00Z",
                "mode": "complete",
                "frontier_ids": [],
                "active_run": {
                    "run_id": "stale-run",
                    "frontier_ids": [99],
                },
            },
        )
        module._write_json(
            shard_root / "state.json",
            {
                "updated_at": "2026-03-31T17:35:00Z",
                "mode": "complete",
                "frontier_ids": [],
                "open_milestone_ids": [],
            },
        )

        state, _history = module._effective_supervisor_state(aggregate_root, history_limit=10)

        assert "active_run" not in state
        assert state["frontier_ids"] == []
        assert state["shards"][0]["active_run_id"] == ""


def test_effective_supervisor_state_ignores_stale_shard_active_run_when_complete_without_work() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        aggregate_root = root / "state"
        shard_root = aggregate_root / "shard-1"
        shard_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            shard_root / "state.json",
            {
                "updated_at": "2026-03-31T17:35:00Z",
                "mode": "complete",
                "frontier_ids": [],
                "open_milestone_ids": [],
                "active_run": {
                    "run_id": "stale-shard-run",
                    "frontier_ids": [],
                    "open_milestone_ids": [],
                },
            },
        )

        state, _history = module._effective_supervisor_state(aggregate_root, history_limit=10)

        assert "active_run" not in state
        assert state["frontier_ids"] == []
        assert state["shards"][0]["active_run_id"] == "stale-shard-run"


def test_live_shard_summaries_prefer_active_run_frontier_ids() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text("waves: []\nmilestones: []\n", encoding="utf-8")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        _write_completion_evidence(root)
        aggregate_root = root / "state"
        shard_root = aggregate_root / "shard-1"
        shard_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            shard_root / "state.json",
            {
                "updated_at": "2026-03-31T17:22:15Z",
                "mode": "completion_review",
                "frontier_ids": [13],
                "focus_owners": ["chummer6-ui"],
                "focus_texts": ["desktop"],
                "open_milestone_ids": [],
                "active_run": {
                    "run_id": "run-1",
                    "frontier_ids": [21, 22],
                    "open_milestone_ids": [],
                },
            },
        )
        args = _args(root)

        summaries = module._live_shard_summaries(args, aggregate_root)

        assert summaries[0]["frontier_ids"] != [21, 22]
        assert summaries[0]["active_frontier_ids"] == []
        assert summaries[0]["active_run_id"] == ""


def test_live_shard_summaries_persist_refreshed_shard_state() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}],
                    "milestones": [
                        {
                            "id": 13,
                            "title": "Desktop package proof",
                            "wave": "W1",
                            "status": "complete",
                            "owners": ["chummer6-ui", "fleet"],
                            "exit_criteria": ["Desktop package ships."],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        _write_completion_evidence(root)
        aggregate_root = root / "state"
        shard_root = aggregate_root / "shard-1"
        shard_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            shard_root / "state.json",
            {
                "updated_at": "2026-03-31T08:00:00Z",
                "mode": "completion_review",
                "frontier_ids": [13],
                "focus_owners": ["chummer6-ui", "fleet"],
                "focus_texts": ["desktop", "client"],
                "completion_audit": {"status": "fail", "reason": "stale"},
                "eta": {"status": "blocked", "eta_human": "unknown"},
                "last_run": {
                    "run_id": "run-9",
                    "worker_exit_code": 0,
                    "accepted": True,
                    "acceptance_reason": "",
                    "primary_milestone_id": 13,
                    "frontier_ids": [13],
                    "shipped": "trusted receipt",
                    "remains": "none",
                    "blocker": "none",
                },
            },
        )
        module._append_jsonl(
            shard_root / "history.jsonl",
            {
                "run_id": "run-9",
                "worker_exit_code": 0,
                "accepted": True,
                "acceptance_reason": "",
                "primary_milestone_id": 13,
                "frontier_ids": [13],
                "shipped": "trusted receipt",
                "remains": "none",
                "blocker": "none",
            },
        )

        summaries = module._live_shard_summaries(_args(root), aggregate_root)
        persisted = json.loads((shard_root / "state.json").read_text(encoding="utf-8"))

        assert summaries[0]["mode"] == "flagship_product"
        assert persisted["mode"] == "flagship_product"
        assert persisted["frontier_ids"] == summaries[0]["frontier_ids"]


def test_live_shard_summaries_refresh_each_shard_with_its_own_configured_frontier_pack(
    monkeypatch,
) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}, {"id": "W2"}],
                    "milestones": [
                        {
                            "id": 1,
                            "title": "Install lane",
                            "wave": "W1",
                            "status": "planned",
                            "owners": ["chummer6-ui"],
                            "exit_criteria": ["Install lane exists."],
                        },
                        {
                            "id": 2,
                            "title": "Legacy workbench",
                            "wave": "W1",
                            "status": "planned",
                            "owners": ["chummer6-ui"],
                            "exit_criteria": ["Workbench exists."],
                        },
                        {
                            "id": 13,
                            "title": "Sourcebook parity",
                            "wave": "W2",
                            "status": "planned",
                            "owners": ["chummer6-core"],
                            "exit_criteria": ["Sourcebooks exist."],
                        },
                        {
                            "id": 14,
                            "title": "Settings parity",
                            "wave": "W2",
                            "status": "planned",
                            "owners": ["chummer6-core"],
                            "exit_criteria": ["Settings exist."],
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Continue the work.\n", encoding="utf-8")
        aggregate_root = root / "state"
        shard_1 = aggregate_root / "shard-1"
        shard_2 = aggregate_root / "shard-2"
        shard_1.mkdir(parents=True, exist_ok=True)
        shard_2.mkdir(parents=True, exist_ok=True)
        for shard_root in (shard_1, shard_2):
            module._write_json(
                shard_root / "state.json",
                {
                    "updated_at": "2026-03-31T08:00:00Z",
                    "mode": "loop",
                    "open_milestone_ids": [1, 2, 13, 14],
                    "frontier_ids": [99],
                    "focus_owners": ["stale-owner"],
                },
            )

        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_SHARD_FRONTIER_ID_GROUPS", "1,2;13,14")
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_SHARD_OWNER_GROUPS", "chummer6-ui;chummer6-core")

        summaries = module._live_shard_summaries(_args(root), aggregate_root)
        persisted_1 = json.loads((shard_1 / "state.json").read_text(encoding="utf-8"))
        persisted_2 = json.loads((shard_2 / "state.json").read_text(encoding="utf-8"))

        assert summaries[0]["frontier_ids"] == [1, 2]
        assert summaries[1]["frontier_ids"] == [13, 14]
        assert persisted_1["frontier_ids"] == [1, 2]
        assert persisted_2["frontier_ids"] == [13, 14]


def test_live_shard_summaries_ignore_stale_dirs_not_in_manifest(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text("waves: []\nmilestones: []\n", encoding="utf-8")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Continue the work.\n", encoding="utf-8")
        aggregate_root = root / "state"
        active_root = aggregate_root / "shard-1"
        stale_root = aggregate_root / "shard-9"
        active_root.mkdir(parents=True, exist_ok=True)
        stale_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            active_root / "state.json",
            {
                "updated_at": "2026-03-31T08:00:00Z",
                "mode": "loop",
                "open_milestone_ids": [1, 2, 3],
                "frontier_ids": [1, 2, 3],
            },
        )
        module._write_json(
            stale_root / "state.json",
            {
                "updated_at": "2026-03-31T08:00:01Z",
                "mode": "loop",
                "open_milestone_ids": [99],
                "frontier_ids": [99],
            },
        )
        (aggregate_root / "active_shards.json").write_text(
            json.dumps({"active_shards": [{"name": "shard-1", "index": 1, "frontier_ids": [1, 2, 3]}]}),
            encoding="utf-8",
        )
        monkeypatch.setattr(
            module,
            "_live_state_with_current_completion_audit",
            lambda args, state_root, state, history, **kwargs: (module._read_state(state_root / "state.json"), history),
        )

        summaries = module._live_shard_summaries(_args(root), aggregate_root)

        assert [item["name"] for item in summaries] == ["shard-1"]


def test_live_shard_summaries_prefer_structured_manifest_over_env_group_defaults(
    monkeypatch,
) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}, {"id": "W2"}],
                    "milestones": [
                        {
                            "id": 1,
                            "title": "Install lane",
                            "wave": "W1",
                            "status": "planned",
                            "owners": ["chummer6-ui"],
                            "exit_criteria": ["Install lane exists."],
                        },
                        {
                            "id": 13,
                            "title": "Sourcebook parity",
                            "wave": "W2",
                            "status": "planned",
                            "owners": ["chummer6-core"],
                            "exit_criteria": ["Sourcebooks exist."],
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Continue the work.\n", encoding="utf-8")
        aggregate_root = root / "state"
        shard_root = aggregate_root / "shard-1"
        shard_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            shard_root / "state.json",
            {
                "updated_at": "2026-03-31T08:00:00Z",
                "mode": "loop",
                "open_milestone_ids": [1, 13],
                "frontier_ids": [],
            },
        )
        (aggregate_root / "active_shards.json").write_text(
            json.dumps(
                {
                    "generated_at": "2026-04-04T15:20:00Z",
                    "topology_fingerprint": "abc123",
                    "active_shards": [
                        {
                            "name": "shard-1",
                            "index": 1,
                            "frontier_ids": [13],
                            "focus_owner": ["chummer6-core"],
                            "focus_text": ["sourcebook"],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_SHARD_FRONTIER_ID_GROUPS", "1")
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_SHARD_OWNER_GROUPS", "chummer6-ui")
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_SHARD_FOCUS_TEXT_GROUPS", "install")

        summaries = module._live_shard_summaries(_args(root), aggregate_root)
        persisted = json.loads((shard_root / "state.json").read_text(encoding="utf-8"))

        assert summaries[0]["frontier_ids"] == [13]
        assert persisted["frontier_ids"] == [13]
        assert persisted["focus_owners"] == ["chummer6-core"]
        assert persisted["focus_texts"] == ["sourcebook"]


def test_live_state_with_current_completion_audit_aggregates_union_of_shard_frontier_packs(
    monkeypatch,
) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}, {"id": "W2"}],
                    "milestones": [
                        {
                            "id": 1,
                            "title": "Install lane",
                            "wave": "W1",
                            "status": "planned",
                            "owners": ["chummer6-ui"],
                            "exit_criteria": ["Install lane exists."],
                        },
                        {
                            "id": 2,
                            "title": "Workbench lane",
                            "wave": "W1",
                            "status": "planned",
                            "owners": ["chummer6-ui"],
                            "exit_criteria": ["Workbench exists."],
                        },
                        {
                            "id": 13,
                            "title": "Sourcebook parity",
                            "wave": "W2",
                            "status": "planned",
                            "owners": ["chummer6-core"],
                            "exit_criteria": ["Sourcebooks exist."],
                        },
                        {
                            "id": 14,
                            "title": "Settings parity",
                            "wave": "W2",
                            "status": "planned",
                            "owners": ["chummer6-core"],
                            "exit_criteria": ["Settings exist."],
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Continue the work.\n", encoding="utf-8")
        aggregate_root = root / "state"
        for shard_root in (aggregate_root / "shard-1", aggregate_root / "shard-2"):
            shard_root.mkdir(parents=True, exist_ok=True)
            module._write_json(
                shard_root / "state.json",
                {
                    "updated_at": "2026-03-31T08:00:00Z",
                    "mode": "loop",
                    "open_milestone_ids": [1, 2, 13, 14],
                    "frontier_ids": [],
                },
            )

        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_PARALLEL_SHARDS", "2")
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_SHARD_FRONTIER_ID_GROUPS", "1,2;13,14")
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_SHARD_OWNER_GROUPS", "chummer6-ui;chummer6-core")

        state, history = module._effective_supervisor_state(aggregate_root, history_limit=10)
        updated_state, _ = module._live_state_with_current_completion_audit(
            _args(root),
            aggregate_root,
            state,
            history,
        )

        assert updated_state["frontier_ids"] == [1, 2, 13, 14]
        assert len(updated_state["shards"]) == 2
        assert updated_state["shards"][0]["frontier_ids"] == [1, 2]
        assert updated_state["shards"][1]["frontier_ids"] == [13, 14]


def test_persist_live_state_snapshot_strips_aggregate_only_fields() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        state_root = Path(tmp)
        module._persist_live_state_snapshot(
            state_root,
            {
                "updated_at": "2026-04-01T09:00:00Z",
                "mode": "flagship_product",
                "frontier_ids": [1, 2, 3],
                "state_root": "/tmp/aggregate",
                "shard_count": 3,
                "shards": [{"name": "shard-1"}],
            },
        )

        persisted = json.loads((state_root / "state.json").read_text(encoding="utf-8"))

        assert persisted["mode"] == "flagship_product"
        assert persisted["frontier_ids"] == [1, 2, 3]
        assert "state_root" not in persisted
        assert "shard_count" not in persisted
        assert "shards" not in persisted


def test_live_state_with_current_completion_audit_overlays_fresh_completion_truth() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}],
                    "milestones": [
                        {
                            "id": 13,
                            "title": "Desktop package proof",
                            "wave": "W1",
                            "status": "complete",
                            "owners": ["chummer6-ui", "fleet"],
                            "exit_criteria": ["Desktop package ships."],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        _write_completion_evidence(root)
        state_root = root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        trusted_run = {
            "run_id": "run-9",
            "worker_exit_code": 0,
            "accepted": True,
            "acceptance_reason": "",
            "primary_milestone_id": 13,
            "frontier_ids": [13],
            "shipped": "trusted receipt",
            "remains": "none",
            "blocker": "none",
        }
        (state_root / "history.jsonl").write_text(json.dumps(trusted_run) + "\n", encoding="utf-8")

        stale_state = {
            "updated_at": "2026-03-31T08:00:00Z",
            "mode": "completion_review",
            "open_milestone_ids": [],
            "frontier_ids": [13],
            "focus_owners": ["chummer6-ui", "fleet"],
            "focus_texts": ["desktop", "client"],
            "completion_audit": {"status": "fail", "reason": "status_plane is stale."},
            "eta": {"status": "blocked", "eta_human": "unknown"},
            "last_run": trusted_run,
        }

        updated_state, updated_history = module._live_state_with_current_completion_audit(
            _args(root),
            state_root,
            stale_state,
            [trusted_run],
        )

        assert updated_history
        assert updated_state["mode"] == "flagship_product"
        assert updated_state["frontier_ids"]
        assert updated_state["focus_owners"] == ["chummer6-ui", "fleet"]
        assert updated_state["focus_texts"] == ["desktop", "client"]
        assert updated_state["completion_audit"]["status"] == "pass"
        assert updated_state["full_product_audit"]["status"] == "fail"
        assert updated_state["eta"]["status"] == "flagship_delivery"


def test_live_state_with_current_completion_audit_refreshes_completion_frontier_when_complete() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}],
                    "milestones": [
                        {
                            "id": 13,
                            "title": "Desktop package proof",
                            "wave": "W1",
                            "status": "complete",
                            "owners": ["chummer6-ui", "fleet"],
                            "exit_criteria": ["Desktop package ships."],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        _write_completion_evidence(root)
        _write_flagship_product_readiness(root, status="pass")
        state_root = root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        trusted_run = {
            "run_id": "run-10",
            "worker_exit_code": 0,
            "accepted": True,
            "acceptance_reason": "",
            "primary_milestone_id": 13,
            "frontier_ids": [13],
            "shipped": "trusted receipt",
            "remains": "none",
            "blocker": "none",
        }
        (state_root / "history.jsonl").write_text(json.dumps(trusted_run) + "\n", encoding="utf-8")

        stale_state = {
            "updated_at": "2026-03-31T08:00:00Z",
            "mode": "completion_review",
            "open_milestone_ids": [],
            "frontier_ids": [13],
            "active_run": {
                "run_id": "stale-complete-run",
                "frontier_ids": [13],
                "open_milestone_ids": [],
            },
            "focus_owners": ["chummer6-ui", "fleet"],
            "focus_texts": ["desktop", "client"],
            "completion_audit": {"status": "fail", "reason": "stale fail artifact."},
            "eta": {"status": "blocked", "eta_human": "unknown"},
            "last_run": trusted_run,
        }

        updated_state, _updated_history = module._live_state_with_current_completion_audit(
            _args(root),
            state_root,
            stale_state,
            [trusted_run],
        )

        assert updated_state["mode"] == "complete"
        assert updated_state["frontier_ids"] == []
        assert "active_run" not in updated_state
        assert updated_state["completion_audit"]["status"] == "pass"
        assert updated_state["full_product_audit"]["status"] == "pass"
        assert updated_state["completion_review_frontier_path"].endswith(
            "COMPLETION_REVIEW_FRONTIER.generated.yaml"
        )
        frontier_payload = yaml.safe_load(
            Path(updated_state["completion_review_frontier_path"]).read_text(encoding="utf-8")
        )
        assert frontier_payload["mode"] == "complete"
        assert frontier_payload["frontier_count"] == 0
        assert frontier_payload["completion_audit"]["status"] == "pass"


def test_full_product_readiness_audit_rejects_unresolved_parity_families() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_flagship_product_readiness(
            root,
            status="pass",
            unresolved_parity_families=(
                {
                    "id": "legacy_and_adjacent_import_oracles",
                    "status": "partial",
                    "milestone_ids": [17],
                },
            ),
        )

        audit = module._full_product_readiness_audit(_args(root))

        assert audit["status"] == "fail"
        assert audit["parity_excluded_scope"] == ["plugin-framework"]
        assert audit["unresolved_parity_families"][0]["id"] == "legacy_and_adjacent_import_oracles"
        assert "unresolved non-plugin parity families" in audit["reason"]


def test_full_product_frontier_decomposes_unresolved_parity_families() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_flagship_product_readiness(
            root,
            status="pass",
            unresolved_parity_families=(
                {
                    "id": "legacy_and_adjacent_import_oracles",
                    "status": "partial",
                    "milestone_ids": [17],
                    "current_design_equivalents": ["INTEROP_AND_PORTABILITY_MODEL.md"],
                },
            ),
        )

        frontier = module._full_product_frontier(_args(root))

        assert [item.title for item in frontier] == ["Parity family: Legacy And Adjacent Import Oracles"]


def test_live_state_with_current_completion_audit_refreshes_live_shard_summaries() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}],
                    "milestones": [
                        {
                            "id": 13,
                            "title": "Desktop package proof",
                            "wave": "W1",
                            "status": "complete",
                            "owners": ["chummer6-ui", "fleet"],
                            "exit_criteria": ["Desktop package ships."],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        _write_completion_evidence(root)
        task = "Finish ruleset-specific workbench adaptation lane"
        _write_project_backlog(root, project_id="ui", repo_slug="chummer6-ui", task=task)
        aggregate_root = root / "state"
        shard_1 = aggregate_root / "shard-1"
        shard_2 = aggregate_root / "shard-2"
        shard_1.mkdir(parents=True, exist_ok=True)
        shard_2.mkdir(parents=True, exist_ok=True)
        trusted_run = {
            "run_id": "run-good",
            "worker_exit_code": 0,
            "accepted": True,
            "acceptance_reason": "",
            "primary_milestone_id": 13,
            "frontier_ids": [13],
            "shipped": "trusted receipt",
            "remains": "none",
            "blocker": "none",
        }
        for shard_root, owners in ((shard_1, ["chummer6-ui"]), (shard_2, ["chummer6-core"])):
            module._write_json(
                shard_root / "state.json",
                {
                    "updated_at": "2026-03-31T08:00:00Z",
                    "mode": "complete",
                    "open_milestone_ids": [],
                    "frontier_ids": [],
                    "focus_owners": owners,
                    "completion_audit": {"status": "pass", "reason": "stale"},
                    "eta": {"status": "ready", "eta_human": "ready now"},
                    "active_run": {
                        "run_id": f"active-{shard_root.name}",
                        "frontier_ids": [13],
                    },
                    "last_run": trusted_run,
                },
            )
            module._append_jsonl(shard_root / "history.jsonl", trusted_run)

        state, history = module._effective_supervisor_state(aggregate_root, history_limit=10)
        updated_state, _updated_history = module._live_state_with_current_completion_audit(
            _args(root),
            aggregate_root,
            state,
            history,
        )
        synthetic_id = module._synthetic_completion_review_id(f"repo-backlog:ui:{task}")

        assert updated_state["mode"] == "completion_review"
        assert updated_state["frontier_ids"][0] == synthetic_id
        assert synthetic_id in updated_state["frontier_ids"]
        assert updated_state["completion_review_frontier_path"].endswith(
            "COMPLETION_REVIEW_FRONTIER.generated.yaml"
        )
        assert updated_state["full_product_audit"]["status"] == "fail"
        assert "flagship product readiness proof is missing" in updated_state["full_product_audit"]["reason"]
        assert len(updated_state["shards"]) == 2
        assert {shard["mode"] for shard in updated_state["shards"]} == {"completion_review"}
        for shard in updated_state["shards"]:
            assert shard["frontier_ids"][0] == synthetic_id
            assert synthetic_id in shard["frontier_ids"]
            assert shard["active_frontier_ids"] == []
            assert shard["active_run_id"] == ""


def test_render_status_shows_current_and_active_frontier_when_they_differ() -> None:
    module = _load_module()

    rendered = module._render_status(
        {
            "updated_at": "2026-03-31T10:00:00Z",
            "mode": "completion_review",
            "open_milestone_ids": [],
            "frontier_ids": [21],
            "shards": [
                {
                    "name": "shard-1",
                    "updated_at": "2026-03-31T10:00:00Z",
                    "mode": "completion_review",
                    "open_milestone_ids": [],
                    "frontier_ids": [21],
                    "active_frontier_ids": [99],
                    "eta_status": "recovery",
                    "last_run_id": "run-1",
                    "active_run_id": "active-1",
                }
            ],
        }
    )

    assert "shard.shard-1:" in rendered
    assert "frontier=21" in rendered
    assert "active_frontier=99" in rendered


def test_render_status_hides_stale_last_blocker_when_newer_active_run_exists() -> None:
    module = _load_module()

    rendered = module._render_status(
        {
            "updated_at": "2026-04-04T16:28:56Z",
            "mode": "sharded",
            "open_milestone_ids": [13, 14, 17, 18],
            "frontier_ids": [13, 14, 17, 18],
            "shards": [
                {
                    "name": "shard-2",
                    "updated_at": "2026-04-04T16:28:47Z",
                    "mode": "loop",
                    "open_milestone_ids": [13, 14, 17, 18],
                    "frontier_ids": [13, 14, 17, 18],
                    "eta_status": "estimated",
                    "last_run_id": "20260404T161600Z",
                    "last_run_blocker": "local commits are not yet pushed to remote",
                    "current_blocker": "",
                    "active_run_id": "20260404T162847Z",
                }
            ],
        }
    )

    assert "shard.shard-2:" in rendered
    assert "active_run=20260404T162847Z" in rendered
    assert "last_blocker=" not in rendered


def test_reconcile_aggregate_shard_truth_moves_stale_blocker_to_historical_field() -> None:
    module = _load_module()

    updated = module._reconcile_aggregate_shard_truth(
        {
            "open_milestone_ids": [13, 14, 17, 18],
            "eta": {
                "status": "estimated",
                "eta_human": "4.5d-1.7w",
                "eta_confidence": "low",
                "basis": "heuristic_status_mix",
                "summary": "4 open milestones remain (0 in progress, 4 not started); range is a fallback heuristic from the current status mix.",
                "remaining_open_milestones": 4,
                "remaining_in_progress_milestones": 0,
                "remaining_not_started_milestones": 4,
                "blocking_reason": "",
            },
            "shards": [
                {
                    "name": "shard-2",
                    "frontier_ids": [13, 14, 17, 18],
                    "active_frontier_ids": [13, 14, 17, 18],
                    "last_run_id": "20260404T161600Z",
                    "last_run_finished_at": "2026-04-04T16:23:15Z",
                    "last_run_blocker": "local commits are not yet pushed to remote",
                    "active_run_id": "20260404T162847Z",
                    "active_run_started_at": "2026-04-04T16:28:47Z",
                }
            ],
        }
    )

    shard = updated["shards"][0]
    assert shard["last_run_blocker"] == ""
    assert shard["current_blocker"] == ""
    assert shard["historical_last_run_blocker"] == "local commits are not yet pushed to remote"
    assert "shard_blockers" not in updated


def test_effective_supervisor_state_uses_active_runs_list_for_multiple_live_shards() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        aggregate_root = Path(tmp) / "state" / "chummer_design_supervisor"
        shard_one_root = aggregate_root / "shard-1"
        shard_two_root = aggregate_root / "shard-2"
        shard_one_root.mkdir(parents=True, exist_ok=True)
        shard_two_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            shard_one_root / "state.json",
            {
                "updated_at": "2026-04-04T16:31:48Z",
                "mode": "loop",
                "open_milestone_ids": [1, 2, 3],
                "frontier_ids": [1, 2, 3],
                "active_run": {
                    "run_id": "run-1",
                    "frontier_ids": [1, 2, 3],
                    "open_milestone_ids": [1, 2, 3],
                    "started_at": "2026-04-04T16:31:48Z",
                },
            },
        )
        module._write_json(
            shard_two_root / "state.json",
            {
                "updated_at": "2026-04-04T16:31:51Z",
                "mode": "loop",
                "open_milestone_ids": [13, 14, 17, 18],
                "frontier_ids": [13, 14, 17, 18],
                "active_run": {
                    "run_id": "run-2",
                    "frontier_ids": [13, 14, 17, 18],
                    "open_milestone_ids": [13, 14, 17, 18],
                    "started_at": "2026-04-04T16:31:51Z",
                },
            },
        )
        (aggregate_root / "active_shards.json").write_text(
            json.dumps(
                {
                    "active_shards": [
                        {"name": "shard-1", "frontier_ids": [1, 2, 3]},
                        {"name": "shard-2", "frontier_ids": [13, 14, 17, 18]},
                    ]
                }
            ),
            encoding="utf-8",
        )

        state, _history = module._effective_supervisor_state(aggregate_root, history_limit=10)

        assert "active_run" not in state
        assert [item["_shard"] for item in state["active_runs"]] == ["shard-1", "shard-2"]
        assert [item["run_id"] for item in state["active_runs"]] == ["run-1", "run-2"]


def test_live_state_with_current_completion_audit_accepts_synthetic_receipt_on_external_worker_blocker() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}],
                    "milestones": [
                        {
                            "id": 13,
                            "title": "Desktop package proof",
                            "wave": "W1",
                            "status": "complete",
                            "owners": ["chummer6-ui", "fleet"],
                            "exit_criteria": ["Desktop package ships."],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        _write_completion_evidence(root)
        state_root = root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        blocked_run = {
            "run_id": "run-timeout",
            "worker_exit_code": 0,
            "accepted": False,
            "acceptance_reason": "Error: upstream_timeout:300s",
            "final_message": "Error: upstream_timeout:300s\n",
            "primary_milestone_id": 13,
            "frontier_ids": [13],
            "open_milestone_ids": [],
            "shipped": "",
            "remains": "",
            "blocker": "",
        }
        (state_root / "history.jsonl").write_text(json.dumps(blocked_run) + "\n", encoding="utf-8")

        updated_state, _updated_history = module._live_state_with_current_completion_audit(
            _args(root),
            state_root,
            {
                "updated_at": "2026-03-31T08:00:00Z",
                "mode": "completion_review",
                "open_milestone_ids": [],
                "frontier_ids": [13],
                "completion_audit": {"status": "fail", "reason": "worker timed out"},
                "eta": {"status": "blocked", "eta_human": "unknown"},
                "last_run": blocked_run,
            },
            [blocked_run],
        )

        assert updated_state["mode"] == "flagship_product"
        assert updated_state["completion_audit"]["status"] == "pass"
        assert updated_state["completion_audit"]["receipt_audit"]["status"] == "pass"
        assert updated_state["completion_audit"]["receipt_audit"]["synthetic"] is True
        assert "supervisor evidence receipt" in updated_state["completion_audit"]["receipt_audit"]["reason"]
        assert "upstream_timeout:300s" in updated_state["completion_audit"]["receipt_audit"]["reason"]
        assert updated_state["full_product_audit"]["status"] == "fail"
        assert updated_state["eta"]["status"] == "blocked"
        assert "full_product_frontier_heuristic" in updated_state["eta"]["basis"]


def test_live_state_with_current_completion_audit_accepts_synthetic_receipt_when_worker_not_launched() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}],
                    "milestones": [
                        {
                            "id": 13,
                            "title": "Desktop package proof",
                            "wave": "W1",
                            "status": "complete",
                            "owners": ["chummer6-ui", "fleet"],
                            "exit_criteria": ["Desktop package ships."],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        _write_completion_evidence(root)
        state_root = root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        not_launched_run = {
            "run_id": "run-not-launched",
            "worker_exit_code": 0,
            "accepted": False,
            "acceptance_reason": "worker not launched",
            "primary_milestone_id": 13,
            "frontier_ids": [],
            "open_milestone_ids": [],
            "shipped": "",
            "remains": "",
            "blocker": "",
        }
        (state_root / "history.jsonl").write_text(json.dumps(not_launched_run) + "\n", encoding="utf-8")

        updated_state, _updated_history = module._live_state_with_current_completion_audit(
            _args(root),
            state_root,
            {
                "updated_at": "2026-03-31T08:00:00Z",
                "mode": "completion_review",
                "open_milestone_ids": [],
                "frontier_ids": [],
                "completion_audit": {"status": "fail", "reason": "worker not launched"},
                "eta": {"status": "blocked", "eta_human": "unknown"},
                "last_run": not_launched_run,
            },
            [not_launched_run],
        )

        assert updated_state["mode"] == "flagship_product"
        assert updated_state["completion_audit"]["status"] == "pass"
        assert updated_state["completion_audit"]["receipt_audit"]["status"] == "pass"
        assert updated_state["completion_audit"]["receipt_audit"]["synthetic"] is True
        assert "worker not launched" in updated_state["completion_audit"]["receipt_audit"]["reason"]
        assert updated_state["eta"]["status"] == "flagship_delivery"
        assert updated_state["completion_review_frontier_path"].endswith(
            "COMPLETION_REVIEW_FRONTIER.generated.yaml"
        )
        completion_frontier_payload = yaml.safe_load(
            Path(updated_state["completion_review_frontier_path"]).read_text(encoding="utf-8")
        )
        assert completion_frontier_payload["mode"] == "complete"
        assert completion_frontier_payload["completion_audit"]["status"] == "pass"
        assert completion_frontier_payload["frontier_count"] == 0


def test_should_defer_external_blocker_probe_only_for_non_primary_shards() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        base_state_root = root / "state"
        shard_1 = base_state_root / "shard-1"
        shard_2 = base_state_root / "shard-2"
        shard_1.mkdir(parents=True, exist_ok=True)
        shard_2.mkdir(parents=True, exist_ok=True)
        module._write_json(shard_1 / "state.json", {"updated_at": "2026-03-31T08:00:00Z"})
        module._write_json(shard_2 / "state.json", {"updated_at": "2026-03-31T08:00:00Z"})

        assert module._should_defer_external_blocker_probe(
            shard_1,
            blocker_reason="Error: upstream_timeout:300s",
        ) is False
        assert module._should_defer_external_blocker_probe(
            shard_2,
            blocker_reason="Error: upstream_timeout:300s",
        ) is True
        assert module._should_defer_external_blocker_probe(
            base_state_root,
            blocker_reason="Error: upstream_timeout:300s",
        ) is False
        assert module._should_defer_external_blocker_probe(shard_2, blocker_reason="") is False


def test_run_loop_defers_non_primary_shard_when_external_blocker_is_active(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        args = _args(root)
        args.command = "loop"
        args.state_root = str(root / "state" / "shard-2")
        args.poll_seconds = 1.0
        args.cooldown_seconds = 1.0
        args.failure_backoff_seconds = 2.0
        args.max_runs = 0
        args.stop_on_blocker = False

        aggregate_root = Path(args.state_root).parent
        (aggregate_root / "shard-1").mkdir(parents=True, exist_ok=True)
        Path(args.state_root).mkdir(parents=True, exist_ok=True)
        module._write_json(aggregate_root / "shard-1" / "state.json", {"updated_at": "2026-03-31T08:00:00Z"})
        module._write_json(Path(args.state_root) / "state.json", {"updated_at": "2026-03-31T08:00:00Z"})

        milestone = module.Milestone(
            id=13,
            title="Desktop package proof",
            wave="W1",
            status="review_required",
            owners=["chummer6-ui", "fleet"],
            exit_criteria=["Desktop package ships."],
            dependencies=[],
        )
        shared_history = [
            {
                "run_id": "run-timeout",
                "worker_exit_code": 0,
                "acceptance_reason": "Error: upstream_timeout:300s",
                "final_message": "Error: upstream_timeout:300s\n",
                "frontier_ids": [13],
            }
        ]
        completion_audit = {
            "status": "fail",
            "reason": "latest worker receipt run-timeout is not trusted: Error: upstream_timeout:300s",
            "receipt_audit": {"status": "fail", "reason": "latest worker receipt run-timeout is not trusted: Error: upstream_timeout:300s"},
            "journey_gate_audit": {"status": "pass", "reason": "ok"},
            "linux_desktop_exit_gate_audit": {"status": "pass", "reason": "ok"},
            "weekly_pulse_audit": {"status": "pass", "reason": "ok"},
        }
        base_context = {
            "registry_path": root / "registry.yaml",
            "program_milestones_path": root / "PROGRAM_MILESTONES.yaml",
            "roadmap_path": root / "ROADMAP.md",
            "handoff_path": root / "NEXT_SESSION_HANDOFF.md",
            "workspace_root": root,
            "scope_roots": [root],
            "open_milestones": [],
            "wave_order": [],
            "frontier": [],
            "frontier_ids": [],
            "focus_profiles": [],
            "focus_owners": [],
            "focus_texts": [],
            "prompt": "recovery",
        }
        review_context = dict(base_context)
        review_context.update(
            {
                "frontier": [milestone],
                "frontier_ids": [13],
                "completion_audit": completion_audit,
                "completion_history": shared_history,
                "prompt": "recovery",
            }
        )

        monkeypatch.setattr(module, "derive_context", lambda _args: dict(base_context))
        monkeypatch.setattr(module, "_completion_review_history", lambda _state_root, limit: list(shared_history[-limit:]))
        monkeypatch.setattr(module, "_design_completion_audit", lambda _args, _history: dict(completion_audit))
        monkeypatch.setattr(
            module,
            "derive_completion_review_context",
            lambda _args, _state_root, base_context=None, audit=None: dict(review_context),
        )
        monkeypatch.setattr(module, "launch_worker", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("launch_worker should not run")))

        sleeps: list[float] = []

        def fake_sleep(seconds: float) -> None:
            sleeps.append(float(seconds))
            raise RuntimeError("stop-loop")

        monkeypatch.setattr(module.time, "sleep", fake_sleep)

        try:
            module.run_loop(args)
        except RuntimeError as exc:
            assert str(exc) == "stop-loop"
        else:
            raise AssertionError("expected stop-loop")

        assert sleeps
        assert sleeps[0] >= module.DEFAULT_EXTERNAL_BLOCKER_BACKOFF_SECONDS
